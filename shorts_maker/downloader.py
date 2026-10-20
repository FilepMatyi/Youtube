from __future__ import annotations

from pathlib import Path
from typing import Callable

from yt_dlp import YoutubeDL

from .utils import PipelineError


def download_video(url: str, destination: Path, progress: Callable[[float, str], None]) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    output_template = str(destination / "source.%(ext)s")

    def hook(data: dict) -> None:
        if data.get("status") == "downloading":
            total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
            done = data.get("downloaded_bytes", 0)
            progress((done / total) if total else 0.0, "Downloading video")

    options = {
        # Prefer <=720p to keep transcription/editing practical, with a robust fallback.
        "format": "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
        "merge_output_format": "mp4",
        "outtmpl": output_template,
        "noplaylist": True,
        "progress_hooks": [hook],
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
    }
    try:
        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
            requested = info.get("requested_downloads") or []
            candidates = [Path(item["filepath"]) for item in requested if item.get("filepath")]
    except Exception as exc:
        raise PipelineError(f"YouTube download failed: {exc}") from exc

    candidates.extend(destination.glob("source.*"))
    files = [p for p in candidates if p.exists() and p.suffix.lower() not in {".part", ".ytdl"}]
    if not files:
        raise PipelineError("yt-dlp finished but no video file was found.")
    return max(files, key=lambda p: p.stat().st_size)

