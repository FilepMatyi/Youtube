# Architektúra — munkaverzió

Highlights: `app.py` (Streamlit) → `SourceSpec`/`SourceRights` → `ingestion.py` (URL vagy helyi média, cache, FFprobe) → `transcriber.py` (faster-whisper vagy legacy OpenAI Whisper) → `selector.py` (jelöltek) → `editor.py` + `captions.py` (FFmpeg render) → `output/<job-id>/metadata.json` és MP4.

Original script: ugyanaz az import és átiratcache → `original_pipeline.py` (témák és időbélyegek) → `original.py` (helyi Ollama, Pydantic-séma, forráshivatkozás ellenőrzés) → Streamlit szövegszerkesztés → verziózott draft/review JSON. Narráció és videókompozíció későbbi fázis.

Az eredeti nyelvű átirat és az angol fordított feliratsáv külön cache-fájl. A nagy médiafájlok a `work/sources` és `output` könyvtárakban vannak; a projektszintű adatok `work/<job-id>/project.json` fájlban. A korábbi `output/*/metadata.json` formátum továbbra is olvasható.

Az AI Original Content **videókészítés**, jobkezelés, idővonalas szerkesztő és storyboard/render interfészek tervezett bővítések, még nem működő komponensek. Részletes sorrend: `IMPLEMENTATION_PLAN.md`.
