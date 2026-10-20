# Modellek és licencek — ellenőrzési nyilvántartás

| Összetevő | Jelenlegi felhasználás | Forrás/licenc | Megjegyzés |
| --- | --- | --- | --- |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | Alapértelmezett helyi ASR adapter | Projekt: MIT | A letöltött modell súlyainak feltételeit külön kell ellenőrizni. |
| [Silero VAD](https://github.com/snakers4/silero-vad) | A faster-whisper VAD szűrője | Projekt: MIT | Csak a faster-whisper adapterrel aktív jelenleg. |
| [OpenAI Whisper](https://github.com/openai/whisper) | Opcionális régi adapter | Projekt: MIT | Külön `requirements-openai-whisper.txt`. |
| [Ollama](https://github.com/ollama/ollama) | Opcionális helyi scriptjavaslat | Projekt: MIT | A kiválasztott LLM modell licencét modellenként ellenőrizni kell. |
| [Piper](https://github.com/OHF-Voice/piper1-gpl) | Tervezett TTS, még nem integrált | Projekt: GPL-3.0 | Hangmodellenként eltérő licenc; konkrét hangot csak ellenőrzés után szabad ajánlani. |
| FFmpeg | Külső bináris | Build és kodek függő | A telepített build licencét felhasználás előtt vizsgálni kell. |

Ez technikai nyilvántartás, nem automatikus szerzőijog-ellenőrzés. Külső videók, zenék, képek és hangmodellek jogállását a felhasználónak projektenként kell rögzítenie.
