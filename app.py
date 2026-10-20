from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from urllib.parse import urlparse

import streamlit as st

from shorts_maker.models import ClipCandidate
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
<p>Másold be a YouTube-linket. Az alkalmazás kiválasztja a legerősebb 40–50 másodperces részeket, álló formátumra vágja őket, és animált angol feliratot tesz rájuk.</p></div>
""", unsafe_allow_html=True)

with st.form("create_shorts", clear_on_submit=False):
    url = st.text_input("YouTube-videó linkje", placeholder="https://www.youtube.com/watch?v=...", help="Egyetlen videó linkjét add meg, ne lejátszási listát.")
    controls = st.columns([1, 1, 1.5])
    with controls[0]:
        count = st.selectbox("Shortok száma", [4, 5, 6], index=1)
    with controls[1]:
        length = st.selectbox("Célhossz", [40, 45, 50], index=1, format_func=lambda value: f"{value} mp")
    with controls[2]:
        language_label = st.selectbox("Videó beszélt nyelve", ["Automatikus felismerés", "Magyar", "Angol"])
    with st.expander("Haladó beállítások"):
        model = st.selectbox("Whisper-modell", ["base", "small"], index=0, help="A small pontosabb lehet, de lassabb és több memóriát igényel.")
        st.caption("A felirat mindig angol; magyar beszédnél a Whisper helyben fordít.")
    submitted = st.form_submit_button("Videó feldolgozása →", type="primary", use_container_width=True)

missing = [name for name in ("streamlit", "yt_dlp", "whisper", "torch") if importlib.util.find_spec(name) is None]
if missing:
    st.info("A feldolgozáshoz még telepíteni kell a függőségeket. Részletek a README-ben: `pip install -r requirements.txt`.")

if submitted:
    if not is_youtube_url(url):
        st.error("Érvényes YouTube-videó linket adj meg (youtube.com vagy youtu.be).")
    elif missing:
        st.error("Hiányzó Python-csomagok: " + ", ".join(missing) + ". Telepítsd őket a `pip install -r requirements.txt` paranccsal.")
    else:
        from shorts_maker import PipelineConfig, ShortsPipeline

        language = {"Automatikus felismerés": None, "Magyar": "hu", "Angol": "en"}[language_label]
        progress_bar = st.progress(0, text="Feldolgozás előkészítése…")
        try:
            st.session_state["clips"] = ShortsPipeline(
                PipelineConfig(ROOT, model, language, count, length)
            ).process(url.strip(), lambda value, message: progress_bar.progress(min(1.0, value), text=message))
            progress_bar.empty()
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
if clips:
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
            with path.open("rb") as clip_file:
                st.download_button(
                    "⬇ MP4 letöltése", clip_file, file_name=path.name, mime="video/mp4",
                    key=f"download-{path}", use_container_width=True,
                )
            with st.expander("Felirat szövege"):
                st.write(candidate.transcript)

if len(jobs) > 1:
    with st.expander("Korábbi feldolgozások"):
        for job_file, job_clips in jobs[:10]:
            if st.button(f"{job_file.parent.name} · {len(job_clips)} Short", key=f"history-{job_file.parent.name}"):
                st.session_state["clips"] = job_clips
                st.rerun()
