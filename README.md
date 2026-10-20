# ShortForge

A local Streamlit application: paste a YouTube video URL or import your own MP4/MOV/MKV file and request 4, 5, or 6 vertical Highlights. Choose a 15–180 second length profile (40–50 seconds by default); the app selects moments, crops them to 9:16, and burns in captions. Preview and download each MP4 from the same page. No Docker is required.

The broader AI Studio specification is being implemented in phases. The separate Original Content workflow currently produces editable, source-referenced **script proposals** with a locally running Ollama model; it does not render narrated videos yet. Background jobs, the full editor and advanced crop modes are not yet available. See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for exact status.

## Prerequisites

- Python 3.10 or 3.11 (64-bit recommended)
- [FFmpeg](https://ffmpeg.org/download.html) installed and available on `PATH` (`ffmpeg -version` and `ffprobe -version` must work)
- Enough disk space for the source video, model, and rendered clips

Only process videos you own or have permission to download and repurpose. YouTube availability and download behavior can vary by video, region, and account requirements.

## Install and run

### Windows PowerShell

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

After the first install, you can launch the app with `./start.ps1` on Windows or `bash start.sh` on macOS/Linux.

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

Open the URL printed by Streamlit, normally `http://localhost:8501`. Paste a YouTube URL or select a local file, record your source rights, choose 4–6 clips and click **Videó feldolgozása**. Choose original-language captions (default) or a separately generated English phrase-caption track. The first run downloads the selected faster-whisper model. Choose `base` for speed or `small` for accuracy. Processing a long video can take several minutes, especially on CPU.

The default install uses faster-whisper on CPU. If you need the legacy OpenAI Whisper engine as another option, install `requirements-openai-whisper.txt` in the same environment. The English translation is phrase timed and may require review; the original word timestamps remain intact.

Generated MP4 files are stored under `output/<job-id>/`; the latest run is shown again when the app restarts. Temporary source downloads are stored under `work/<job-id>/` and can be deleted after processing. If a source video has too little suitable speech or is too short, fewer than the requested 4–6 distinct Shorts may be produced; the UI reports the actual count.

## How selection works

The local selector starts at real speech boundaries and evaluates flexible windows within the selected length profile. It ranks them using opening-hook strength, speech density, emotional punctuation, vocabulary variety, sentence closure, and penalties for filler, repetition, and silence. It chooses up to six mostly distinct clips and shows its heuristic reason and score. The original-language transcript is cached separately from optional English phrase captions. No transcript or video is sent to an LLM service.
