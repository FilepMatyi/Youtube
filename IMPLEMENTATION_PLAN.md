# ShortForge AI Studio — implementációs terv

Állapot: folyamatban. A teljes elfogadási lista **nincs késznek jelölve**. A fejlesztés a meglévő Streamlit alkalmazásra épül, és a korábbi `metadata.json` fájlokat olvashatóan hagyja.

## 0. Repository audit

| Terület | Jelenlegi állapot | Teendő |
| --- | --- | --- |
| UI | `app.py`: YouTube URL, 4–6 klip, előnézet, MP4 letöltés, korábbi exportok | Helyi feltöltés, két valódi mód, szerkesztés, projektállapot és jóváhagyás |
| Import | `downloader.py`: yt-dlp, 720p előnyben; nincs tartós forráscache, nincs importált fájl | URL/fájl közös forráskezelés, probe, jogosultsági adatok, cache |
| Beszéd | `transcriber.py`: openai-whisper, szavankénti időbélyeg | Eredeti átirat megőrzése; faster-whisper/VAD adapter; fordítás és időzítés szétválasztása |
| Kiválasztás | `selector.py`: kulcsszavas/sűrűségi heurisztika és súlyozott intervallum-kiválasztás | Szemantika, vizuális jel, magyarázat, duplikációszűrés, több célhossz |
| Render | `editor.py`, `captions.py`: FFmpeg, 1080×1920 középvágás, ASS felirat | Crop módok, narráció/hangkeverés, exportellenőrzés, stílusok |
| Pipeline | `pipeline.py`: szinkron, egy munkamenet, URL+beállítás hash, export JSON | Per-stage cache, állapotmentés, megszakítás, két mód |
| Modellek | `models.py`: `Word`, `TranscriptSegment`, `ClipCandidate` | Projekt, forrásjog, átirat, bizonyíték, script, storyboard, renderjob |
| Tesztek | Nincs verziózott tesztkészlet | Offline unit/integrációs tesztek, majd valódi média benchmark |

### Fő technikai kockázatok

- A jelenlegi fordítás a Whisper `translate` feladatával az eredeti átirat helyén tárolódik. A fordított szöveg időzítése nem használható automatikusan eredeti szavakhoz.
- A Streamlit hívás blokkolja a felületet, ha a videó hosszú. Nincs tartós jobállapot vagy megszakítás.
- Az export nincs visszaellenőrizve FFprobe-bal; Windowsos ASS szűrőútvonal és médiafüggőségek valódi futtatása még szükséges.
- A modellek első indítása letöltést/memóriát igényel; CPU időigényes lehet. A kötelező modelltől független UI indulás fontos.
- Nincs automatikus jogellenőrzés; az alkalmazás csak a felhasználó nyilatkozatát és az assetek ismert licencadatait rögzítheti.

## Megtartandó működés

YouTube import, helyi Streamlit indítás Docker nélkül, 4–6 highlight javaslat, 9:16 MP4, felirat, klipenkénti előnézet és letöltés, régi `output/*/metadata.json` megnyitása.

## Célarchitektúra

`SourceSpec` → forráskezelő és FFprobe → eredeti nyelvű `Transcript` → VAD/jelenethatárok → highlight jelöltek **vagy** bizonyítékokra támaszkodó original script → felhasználói review → külön renderelő → exportvalidátor → projektadattár. A régi modulok közös interfészek mögött maradnak. Opcionális helyi modellek adaptereken keresztül kapcsolódnak; a hiányuk nem akadályozza a többi mód megnyitását.

Tervezett interfészek: `TranscriptionProvider`, `RankingProvider`, `ScriptProvider`, `NarrationProvider`, `SceneDetectionProvider`, `RenderProvider`. A médiafájlok a fájlrendszerben, kis strukturált projektadatok verziózott JSON-ban, később igény szerint SQLite-ban maradnak.

## Függőségek és licencfigyelés

- Jelenleg: Streamlit, yt-dlp, OpenAI Whisper, PyTorch, FFmpeg. A pontos telepített verziókat a lock/diagnosztika fogja rögzíteni.
- Tervezett: [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (MIT), [Silero VAD](https://github.com/snakers4/silero-vad) (MIT), opcionális helyi [Ollama](https://github.com/ollama/ollama), opcionális [Piper](https://github.com/OHF-Voice/piper1-gpl) (GPL-3.0). A Piper **hangmodellek** licencét modellenként külön kell rögzíteni; addig nincs kereskedelmi felhasználásra ajánlás.
- FFmpeg build/kodek licence és minden felhasznált külső asset licence telepítés/forrás függő; `MODEL_LICENSES.md` dokumentálja az ellenőrzést.

## Fázisok, ellenőrizhető kimenet

| Fázis | Kimenet és elfogadási teszt | Állapot |
| --- | --- | --- |
| 0 Audit | Ez a terv; offline baseline tesztek; pontos hiánylista | Kész (offline audit) |
| 1 Import | YouTube és MP4/MOV/MKV; média-probe; jognyilatkozat; cache; ismételt letöltés kihagyása; érvényes fájlnév; Windows útvonal | Részben kész: offline tesztelt; valós FFmpeg/YouTube és cancel még hiányzik |
| 2 Beszéd | Eredeti HU/EN/RO átirat és szavak; VAD; nyelvválasztás; külön feliratfordítás; pontatlan szakaszok jelölése | Részben kész: adapter/cache és integrált Silero kapcsoló; modellfuttatás, szünet-szegmensek, pontos fordításalignment még hiányzik |
| 3 Highlight | 15–180 mp-es profilok, többfaktoros jelöltek, szemantika, deduplikáció és magyarázat | Részben kész: hosszprofilok, pontszám-részletek, szöveges magyarázat és n-gram ismétléscsökkentés; szemantikus/vizuális/audio értékelés még hiányzik |
| 4 Original script | Téma, forrás-időbélyegek, ellenőrizhető bizonyítékok, helyi scriptgenerátor, szerkesztői jóváhagyás | Részben kész: témák, időbélyeges bizonyítékok, Ollama/Pydantic scriptjavaslat és szerkesztett verzió mentése; narráció/export és tartalmi fact-check még hiányzik |
| 5 Narráció/storyboard | Saját hang vagy licencelt helyi TTS, narráció-előnézet, időzített vizuális terv | Tervezett |
| 6 Render | Crop módok, stílusok, audio mix, 1080×1920 export, FFprobe ellenőrzés | Tervezett |
| 7 Szerkesztés | Jelölt-választás, klipidők/felirat/script kézi korrekciója, csak érintett klip újrarenderelése | Tervezett |
| 8 Job/adat | Háttérfeladat, állapot, cancel/retry, stage-cache, újraindítás utáni helyreállítás | Tervezett |
| 9 UI/teljesítmény | Projekt dashboard, reszponzív felület, mérhető memória/CPU korlátok | Tervezett |
| 10 Minőség | Offline CI, FFmpeg-szintetikus integráció, kézi jogtiszta HU/EN/többszereplős benchmark, dokumentumok | Tervezett |

## Tesztstratégia

1. Offline unit tesztek: URL/útvonal, médiaproba JSON, időbélyegek, kiválasztás, átfedés, jogadat, állapotátmenet és hibák.
2. Helyi, saját generált rövid FFmpeg videó: import → probe → vágás → felirat → exportvalidátor. Ez modell és internet nélkül fusson.
3. Mockolt AI adapterek: a sémák, bizonyítékok, szerkesztés és cache végigjárható legyen.
4. Opcionális benchmark: jogszerű HU podcast, hosszú HU podcast, EN interjú, kétbeszélős, gyakori jelenetváltású és rossz hangú forrás. A minőséget ember értékeli; automatizált teszt nem pótolja.

## Elfogadás és következő lépés

A teljes projekt csak a csatolt specifikáció 20. fejezetének **mind a 28** pontja után tekinthető késznek. Minden fázis végén fájllista, sikeres releváns teszt, ismert hiány és következő lépés kerül ide. Publikálás csak külön felhasználói jóváhagyással történik.

### Fáziszárási napló

**0. fázis — offline audit:** `IMPLEMENTATION_PLAN.md`, `tests/test_baseline.py` jött létre. Meglévő 9 modul és függőségek áttekintve; két baseline teszt sikeres. A helyi gépen FFmpeg, yt-dlp és beszédmodell nincs telepítve, ezért teljes médiafolyamat nem igazolt.

**1. fázis — részleges implementáció:** `shorts_maker/models.py`, `ingestion.py`, `downloader.py`, `pipeline.py`, `app.py`, `tests/test_ingestion.py` változott. Van URL- és jognyilatkozat-ellenőrzés, helyi feltöltés vagy elérési út, streamelt másolás/hash, FFprobe metaadat, 720/1080p választás, forráscache, sérült cache karantén és projekt metaadat. Az offline tesztek sikeresek. Következő: valódi MP4/MOV/MKV és jogosult YouTube forrás integrációs tesztje; megszakítás a 8. fázis jobkezelőjével együtt.

**2. fázis — részleges implementáció:** `transcriber.py`, `pipeline.py`, `app.py`, `requirements.txt`, `requirements-openai-whisper.txt`, `tests/test_transcription.py` változott. Faster-whisper CPU/int8 adapter, integrált Silero VAD szűrés, régi OpenAI adapter, eredeti HU/EN/RO nyelv detektálása és időzítése, külön fordított mondatsáv/cache. A fordított szavak időzítését nem keverjük az eredeti szavakéval. Offline mock tesztek sikeresek. Következő: valódi HU/EN/RO modellteszt, külön VAD intervallumok és szünetprofilok, fordítás időzítési ellenőrzése.

**3. fázis — részleges implementáció:** `models.py`, `selector.py`, `pipeline.py`, `app.py`, `tests/test_baseline.py` változott. 15–30, 30–45, 40–50, 45–60, 60–90 és 90–180 mp-es célprofilok, bontott heurisztikus pontszám, indoklás és szöveges ismétléscsökkentés készült. 10 offline teszt sikeres. A „storytelling” és „interestingness” tényezők jelenleg **szöveges közelítések**, nem valódi multimodális/szemantikus ítéletek. Következő: opcionális helyi szemantikus és képi elemzés, valódi HU/EN minták kézi rangsorértékelése.

**4. fázis — részleges implementáció:** `original.py`, `original_pipeline.py`, `app.py`, `tests/test_original.py` változott. Külön Original munkafolyamat készít időbélyeges témákat, helyi Ollamából Pydantic-sémás scriptet kér, a hivatkozásokat tényleges forrásszakaszhoz köti, elutasítja a nem létező hivatkozást, és a felhasználó szerkesztett változatát külön fájlban menti. A hivatkozás megléte **nem** szemantikus tényellenőrzés. A teljes Original Short videó még nem készül. 15 offline teszt sikeres, valós Ollama modell futtatása hátravan.

**Legközelebbi fejlesztési pont:** 5. fázis saját hang és ellenőrzött licencű TTS, majd storyboard és narrált render. Ez még nem tekinthető késznek.
