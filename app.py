from __future__ import annotations

import importlib.util
import hashlib
import json
import shutil
import uuid
from pathlib import Path
from urllib.parse import urlparse

import streamlit as st

from shorts_maker.ingestion import store_upload
from shorts_maker.models import ClipCandidate, SourceRights, SourceSpec
from shorts_maker.original import evidence_for_range, generate_original_draft, installed_ollama_models
from shorts_maker.original_pipeline import prepare_original
from shorts_maker.transcriber import available_engines
from shorts_maker.utils import PipelineError

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"


def is_youtube_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    host = (parsed.hostname or "").lower()
    return parsed.scheme in {"http", "https"} and (
        host in {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}
    ) and bool(parsed.path.strip("/"))


def previous_jobs() -> list[tuple[Path, list[tuple[Path, ClipCandidate]]]]:
    jobs = []
    if not OUTPUT.exists():
        return jobs
    for metadata_file in OUTPUT.glob("*/metadata.json"):
        try:
            metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
            clips = []
            for item in metadata.get("clips", []):
                file = metadata_file.parent / Path(item["file"]).name
                if file.is_file():
                    clips.append((file, ClipCandidate(
                        float(item["start"]), float(item["end"]), float(item["score"]),
                        str(item["title"]), str(item["transcript"]),
                    )))
            if clips:
                jobs.append((metadata_file, clips))
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return sorted(jobs, key=lambda job: job[0].stat().st_mtime, reverse=True)


st.set_page_config(page_title="ShortForge | YouTube Shorts készítő", page_icon="✂️", layout="wide")
st.markdown("""
<style>
.stApp { background: radial-gradient(circle at 15% 0%, #22203a 0%, #0d101b 43%, #090b12 100%); }
[data-testid="stHeader"] { background: transparent; }
.block-container { max-width: 1240px; padding-top: 2rem; }
.brand { color: #f8f9ff; letter-spacing: .12em; font-size: .78rem; font-weight: 800; }
.hero { padding: 1.8rem 0 1.4rem; }
.hero h1 { color: #fff; font-size: clamp(2.6rem, 6vw, 4.9rem); letter-spacing: -.065em; line-height: 1.04; margin: 0 0 1rem; }
.hero h1 span { color: #ffda4d; }
.hero p { color: #b6b9ca; font-size: 1.1rem; max-width: 720px; margin: 0; }
.eyebrow { color: #ffda4d; font-weight: 800; font-size: .78rem; letter-spacing: .13em; margin: 1.5rem 0 .5rem; }
.clip-title { font-size: 1.2rem; color: #fff; font-weight: 800; padding-top: .6rem; }
.clip-meta { color: #a9adbd; font-size: .89rem; margin-bottom: .7rem; }
div[data-testid="stForm"] { background: #151a29; border: 1px solid #353a52; border-radius: 18px; padding: 1rem 1.2rem; }
div[data-testid="stVideo"] { border-radius: 14px; overflow: hidden; }
div.stButton > button[kind="primary"], div.stFormSubmitButton > button[kind="primary"] {
    background: #ffda4d; color: #17171d; border: 0; font-weight: 800;
}
</style>
<div class="brand">✂ SHORTFORGE</div>
<div class="hero"><h1>Egy hosszú videóból<br><span>4–6 kész Short.</span></h1>
<p>Másold be a YouTube-linket vagy adj meg saját videót. Az alkalmazás kiválasztja az erős, önálló részleteket, álló formátumra vágja őket, és választott nyelvű feliratot tesz rájuk.</p></div>
""", unsafe_allow_html=True)

workflow = st.radio("Készítési mód", ["CREATE HIGHLIGHTS", "ORIGINAL CONTENT – forgatókönyv"], horizontal=True)
if workflow.startswith("ORIGINAL"):
    st.info("Az Original Content mód jelenleg forrásokhoz kötött, szerkeszthető forgatókönyvet készít helyi Ollamával. Narráció és videóexport ebben a módban még fejlesztés alatt áll.")
source_choice = st.radio("Videó forrása", ["YouTube-link", "Helyi videófájl"], horizontal=True)
local_method = st.radio("Importálás módja", ["Feltöltés", "Helyi elérési út"], horizontal=True) if source_choice == "Helyi videófájl" else None

with st.form("create_shorts", clear_on_submit=False):
    url = ""
    upload = None
    local_path = ""
    if source_choice == "YouTube-link":
        url = st.text_input("YouTube-videó linkje", placeholder="https://www.youtube.com/watch?v=...", help="Egyetlen videó linkjét add meg, ne lejátszási listát.")
    elif local_method == "Feltöltés":
        upload = st.file_uploader("Saját videó feltöltése", type=["mp4", "mov", "mkv"])
    else:
        local_path = st.text_input("Videófájl teljes elérési útja", placeholder=r"C:\Videos\forras.mp4")
    count = 5
    length_label = "40–50 mp"
    caption_label = "Eredeti beszélt nyelv"
    if workflow == "CREATE HIGHLIGHTS":
        controls = st.columns([1, 1, 1.5])
        with controls[0]:
            count = st.selectbox("Shortok száma", [4, 5, 6], index=1)
        with controls[1]:
            length_label = st.selectbox("Célhossz", ["15–30 mp", "30–45 mp", "40–50 mp", "45–60 mp", "60–90 mp", "90–180 mp"], index=2)
        with controls[2]:
            language_label = st.selectbox("Videó beszélt nyelve", ["Automatikus felismerés", "Magyar", "Angol", "Román"])
        caption_label = st.selectbox("Felirat nyelve", ["Eredeti beszélt nyelv", "Angol fordítás"])
    else:
        language_label = st.selectbox("Videó beszélt nyelve", ["Automatikus felismerés", "Magyar", "Angol", "Román"])
    with st.expander("Forrásjogok nyilatkozata", expanded=True):
        rights_label = st.selectbox("Felhasználás jogalapja", ["Saját videó", "Licencelt forrás", "Jogosult engedélye"])
        rights_holder = st.text_input("Jogosult neve (ha ismert)")
        license_name = st.text_input("Licenc megnevezése (ha van)")
        permission_note = st.text_input("Engedély vagy attribúció megjegyzése")
        rights_confirmed = st.checkbox("Kijelentem, hogy jogosult vagyok a forrás feldolgozására.")
        st.caption("A nyilatkozat mentésre kerül; az alkalmazás nem végez automatikus szerzőijog-ellenőrzést.")
    with st.expander("Haladó beállítások"):
        model = st.selectbox("Whisper-modell", ["base", "small"], index=0, help="A small pontosabb lehet, de lassabb és több memóriát igényel.")
        engine_label = st.selectbox("Beszédfelismerő motor", ["Automatikus", "faster-whisper", "openai-whisper"])
        use_vad = st.checkbox("Silero beszéd/csend szűrés (faster-whisper)", value=True)
        max_height = st.selectbox("YouTube-forrás maximális magassága", [720, 1080], format_func=lambda value: f"{value}p")
        st.caption("Az eredeti átirat mindig megmarad. Az angol fordítás külön, mondatszintű feliratsávként készül; időzítése ellenőrzést igényelhet.")
    submitted = st.form_submit_button(
        "Highlightok készítése →" if workflow == "CREATE HIGHLIGHTS" else "Témák keresése →",
        type="primary", use_container_width=True,
    )

required_modules = ["yt_dlp"] if source_choice == "YouTube-link" else []
missing = [name for name in required_modules if importlib.util.find_spec(name) is None]
if not available_engines():
    missing.append("faster-whisper vagy openai-whisper")
if missing:
    st.info("A feldolgozáshoz még telepíteni kell a függőségeket. Részletek a README-ben: `pip install -r requirements.txt`.")
missing_tools = [name for name in ("ffmpeg", "ffprobe") if shutil.which(name) is None]
if missing_tools:
    st.info("Az FFmpeg és az FFprobe is szükséges. Telepítés után legyenek elérhetők a PATH környezeti változóban.")

if submitted:
    if source_choice == "YouTube-link" and not is_youtube_url(url):
        st.error("Érvényes YouTube-videó linket adj meg (youtube.com vagy youtu.be).")
    elif source_choice == "Helyi videófájl" and local_method == "Feltöltés" and upload is None:
        st.error("Válassz egy MP4, MOV vagy MKV fájlt.")
    elif source_choice == "Helyi videófájl" and local_method == "Helyi elérési út" and not local_path.strip():
        st.error("Add meg a helyi videófájl teljes elérési útját.")
    elif not rights_confirmed:
        st.error("A feldolgozás előtt nyilatkoznod kell a forrás felhasználási jogáról.")
    elif missing:
        st.error("Hiányzó Python-csomagok: " + ", ".join(missing) + ". Telepítsd őket a `pip install -r requirements.txt` paranccsal.")
    elif missing_tools:
        st.error("Hiányzó programok: " + ", ".join(missing_tools) + ". Telepítsd az FFmpeg csomagot, majd indítsd újra az alkalmazást.")
    else:
        language = {"Automatikus felismerés": None, "Magyar": "hu", "Angol": "en", "Román": "ro"}[language_label]
        clip_min, clip_max = {
            "15–30 mp": (15, 30), "30–45 mp": (30, 45), "40–50 mp": (40, 50),
            "45–60 mp": (45, 60), "60–90 mp": (60, 90), "90–180 mp": (90, 180),
        }[length_label]
        length = (clip_min + clip_max) // 2
        progress_bar = st.progress(0, text="Feldolgozás előkészítése…")
        try:
            from shorts_maker import PipelineConfig, ShortsPipeline

            rights = SourceRights(
                {"Saját videó": "owned", "Licencelt forrás": "licensed", "Jogosult engedélye": "permitted"}[rights_label],
                rights_confirmed,
                rights_holder,
                license_name,
                permission_note,
            )
            if source_choice == "YouTube-link":
                source = SourceSpec("youtube", rights, url=url.strip(), max_height=max_height)
            else:
                path = store_upload(upload, upload.name, ROOT) if upload is not None else Path(local_path.strip())
                source = SourceSpec("local", rights, local_path=path, original_name=path.name)
            config = PipelineConfig(
                root=ROOT,
                whisper_model=model,
                language=language,
                clip_count=count,
                clip_length=length,
                caption_language="en" if caption_label == "Angol fordítás" else "original",
                max_height=max_height,
                transcription_engine="auto" if engine_label == "Automatikus" else engine_label,
                use_vad=use_vad,
                clip_min=clip_min,
                clip_max=clip_max,
            )
            if workflow == "CREATE HIGHLIGHTS":
                st.session_state["clips"] = []
                st.session_state["clips"] = ShortsPipeline(config).process(
                    source, lambda value, message: progress_bar.progress(min(1.0, value), text=message)
                )
            else:
                st.session_state.pop("original_draft", None)
                st.session_state["original_preparation"] = prepare_original(
                    source, config, lambda value, message: progress_bar.progress(min(1.0, value), text=message)
                )
            progress_bar.empty()
            if workflow.startswith("ORIGINAL"):
                st.success("A témák elkészültek. Válassz témát a forgatókönyv-javaslathoz.")
            else:
                made = len(st.session_state["clips"])
                if made < count:
                    st.warning(f"{made} különálló, megfelelő hosszúságú rész készült. A videó nem tartalmazott {count} használható részt.")
                else:
                    st.success(f"Elkészült {made} short. Nézd meg és töltsd le őket alább.")
        except PipelineError as exc:
            progress_bar.empty()
            st.error(str(exc))
        except Exception as exc:
            progress_bar.empty()
            st.error(f"A feldolgozás megszakadt: {exc}")

jobs = previous_jobs()
if "clips" not in st.session_state and jobs:
    st.session_state["clips"] = jobs[0][1]

clips = st.session_state.get("clips", [])
if clips and workflow == "CREATE HIGHLIGHTS":
    st.markdown('<div class="eyebrow">ELKÉSZÜLT VIDEÓK</div>', unsafe_allow_html=True)
    st.subheader(f"{len(clips)} Short megtekintése és letöltése")
    columns = st.columns(3, gap="large")
    for index, (path, candidate) in enumerate(clips):
        with columns[index % 3]:
            st.markdown(f'<div class="clip-title">Short {index + 1:02d}</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="clip-meta">{candidate.end - candidate.start:.0f} mp · Forrás: {candidate.start:.0f}–{candidate.end:.0f} mp</div>',
                unsafe_allow_html=True,
            )
            st.video(str(path))
            if candidate.explanation:
                st.caption(f"Miért ajánlott: {candidate.explanation} · pontszám {candidate.score:.1f}")
            with path.open("rb") as clip_file:
                st.download_button(
                    "⬇ MP4 letöltése", clip_file, file_name=path.name, mime="video/mp4",
                    key=f"download-{path}", use_container_width=True,
                )
            with st.expander("Eredeti átirat"):
                st.write(candidate.transcript)

if workflow.startswith("ORIGINAL") and st.session_state.get("original_preparation"):
    preparation = st.session_state["original_preparation"]
    st.subheader("Original Content · témák és források")
    topic_index = st.selectbox(
        "Téma kiválasztása",
        range(len(preparation.topics)),
        format_func=lambda index: f"{index + 1}. {preparation.topics[index].title} ({preparation.topics[index].start:.0f}–{preparation.topics[index].end:.0f} mp)",
    )
    topic = preparation.topics[topic_index]
    st.caption(topic.transcript)
    try:
        ollama_models = installed_ollama_models()
    except PipelineError:
        ollama_models = []
    if not ollama_models:
        st.warning("Forgatókönyv-generáláshoz indítsd el a helyi Ollamát és tölts le egy modellt. A témajavaslatok addig is megmaradnak.")
    else:
        selected_model = st.selectbox("Helyi Ollama modell", ollama_models)
        script_style = st.selectbox("Forgatókönyv stílusa", ["elemző", "informatív", "dinamikus", "történetmesélő"])
        script_language = st.selectbox("Forgatókönyv nyelve", ["Magyar", "Angol"])
        if st.button("Forrásokra épülő forgatókönyv-javaslat készítése"):
            try:
                evidence = evidence_for_range(
                    list(preparation.transcript.segments), preparation.source_id, topic.start, topic.end
                )
                draft = generate_original_draft(
                    evidence, model=selected_model,
                    language="hu" if script_language == "Magyar" else "en", style=script_style,
                )
                st.session_state["original_draft"] = draft
                (preparation.project_dir / f"draft-{uuid.uuid4().hex[:10]}.json").write_text(
                    json.dumps(draft.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
                )
            except PipelineError as exc:
                st.error(str(exc))
    draft = st.session_state.get("original_draft")
    if draft and draft.source_id == preparation.source_id:
        st.subheader("Forgatókönyv ellenőrzése")
        st.caption("Az alábbi állítások hivatkozásai szerkezetileg ellenőrzöttek. Tartalmi pontosságukat és a külső tényeket embernek kell ellenőriznie.")
        draft_revision = hashlib.sha256(draft.proposal.model_dump_json().encode()).hexdigest()[:10]
        title_text = st.text_input("Cím", value=draft.proposal.title, key=f"draft-title-{preparation.project_dir.name}-{draft_revision}")
        script_parts = {}
        for field_name, label in [
            ("hook", "Hook"), ("context", "Kontextus"), ("source_evidence", "Forrásállítás"),
            ("original_analysis", "Saját elemzés"), ("conclusion", "Lezárás"),
        ]:
            script_parts[field_name] = st.text_area(
                label, value=getattr(draft.proposal, field_name), key=f"draft-{field_name}-{preparation.project_dir.name}"
                + f"-{draft_revision}"
            )
        with st.expander("Forrásbizonyítékok és ellenőrizendő állítások", expanded=True):
            for claim in draft.claims:
                st.write(claim.text)
                for reference in claim.evidence:
                    st.caption(f"{reference.source_start:.1f}–{reference.source_end:.1f} mp · {reference.supporting_text}")
                if claim.requires_external_verification:
                    st.warning("Külső ellenőrzést igénylő állítás.")
        if st.button("Szerkesztett forgatókönyv mentése"):
            review = {
                "status": "AWAITING_SCRIPT_APPROVAL", "source_id": draft.source_id,
                "title": title_text, "sections": script_parts, "claims": draft.to_dict()["claims"],
            }
            (preparation.project_dir / f"script_review-{uuid.uuid4().hex[:10]}.json").write_text(
                json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            st.success("A szerkesztett forgatókönyv mentve. Narráció és videóexport későbbi fázisban érhető el.")

if len(jobs) > 1 and workflow == "CREATE HIGHLIGHTS":
    with st.expander("Korábbi feldolgozások"):
        for job_file, job_clips in jobs[:10]:
            if st.button(f"{job_file.parent.name} · {len(job_clips)} Short", key=f"history-{job_file.parent.name}"):
                st.session_state["clips"] = job_clips
                st.rerun()
