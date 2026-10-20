# ShortForge

A local Streamlit application: paste one YouTube video URL in your browser and request 4, 5, or 6 vertical Shorts. It selects engaging 40–50 second moments, crops them to 9:16, and burns in animated English captions. Preview and download each MP4 from the same page. No Docker is required.

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

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

Open the URL printed by Streamlit, normally `http://localhost:8501`. Paste a YouTube video URL, choose 4–6 clips, and click **Videó feldolgozása**. The first transcription downloads the selected Whisper model. Choose `base` for speed or `small` for improved Hungarian/English accuracy. Processing a long video can take several minutes, especially on CPU.

Generated MP4 files are stored under `output/<job-id>/`; the latest run is shown again when the app restarts. Temporary source downloads are stored under `work/<job-id>/` and can be deleted after processing. If a source video has too little suitable speech or is too short, fewer than the requested 4–6 distinct Shorts may be produced; the UI reports the actual count.

## How selection works

The local selector starts at real speech boundaries and evaluates 40, 45, and 50-second windows. It ranks them using opening-hook strength, speech density, emotional punctuation, vocabulary variety, sentence closure, and penalties for filler, repetition, and silence. It then removes overlapping results. Whisper translates speech locally to English, and every active caption word receives a yellow pop animation. No transcript or video is sent to an LLM service.
