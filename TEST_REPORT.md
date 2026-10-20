# Tesztjelentés — jelenlegi fejlesztési állapot

## Lefuttatva

- `python -m unittest discover -s tests -v` — 15/15 offline teszt sikeres.
- `python -m compileall -q app.py shorts_maker tests` — szintaxisellenőrzés sikeres.
- Streamlit `AppTest`: YouTube és helyi videó UI betöltése kivétel nélkül.

## Lefedett viselkedés

URL és jognyilatkozat validáció, feltöltés streamelt mentése és deduplikációja, FFprobe JSON feldolgozása, sérült YouTube-cache újrapróbálása, hat nem jelentősen átfedő jelölt kiválasztása, 15–30 mp-es hosszprofil, ismétlődő tartalom szűrése, ASS feliratgenerálás, faster-whisper adapter visszatérési adatainak feldolgozása, eredeti és fordított átirat külön cache-e, Highlights projekt/metaadat mentése, Original projekt/téma mentése, forrásbizonyítékok feloldása, nem létező forrásazonosítók elutasítása.

## Még nem igazolt

Ezen a gépen jelenleg nincs FFmpeg/ffprobe, yt-dlp, telepített Whisper modell vagy helyi Ollama modell. Ezért valódi YouTube letöltés, helyi videó FFprobe-futtatás, GPU/CPU modell-inferencia, Original script valódi LLM-minősége, renderelt MP4 és felirat vizuális minőség **nem** volt végponttól végpontig tesztelve. A fordítás időzítése csak mondatszintű; kézi ellenőrzés szükséges. A további fázisok tesztjei az `IMPLEMENTATION_PLAN.md` fájlban szerepelnek.
