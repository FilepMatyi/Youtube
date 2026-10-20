from __future__ import annotations

from pathlib import Path
from typing import Callable

from .utils import PipelineError


def download_video(
    url: str, destination: Path, progress: Callable[[float, str], None], *, max_height: int = 720,
    use_cache: bool = True,
) -> Path:
    try:
        from yt_dlp import YoutubeDL
    except ImportError as exc:
        raise PipelineError("A yt-dlp hiányzik. Telepítsd a requirements.txt függőségeit.") from exc
    destination.mkdir(parents=True, exist_ok=True)
    if max_height not in {720, 1080}:
        raise PipelineError("A forrásminőség csak 720p vagy 1080p lehet.")
    cached = [p for p in destination.glob("source.*") if p.suffix.lower() in {".mp4", ".mkv", ".webm"} and p.stat().st_size > 0]
    if use_cache and cached:
        progress(1.0, "Korábbi letöltés használata")
        return max(cached, key=lambda p: p.stat().st_size)
    output_template = str(destination / "source.%(ext)s")

    def hook(data: dict) -> None:
        if data.get("status") == "downloading":
            total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
            done = data.get("downloaded_bytes", 0)
            progress((done / total) if total else 0.0, "Downloading video")

    options = {
        "format": f"bestvideo[height<={max_height}]+bestaudio/best[height<={max_height}]/best",
        "merge_output_format": "mp4",
        "outtmpl": output_template,
        "noplaylist": True,
        "progress_hooks": [hook],
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
        "overwrites": not use_cache,
    }
    try:
        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
            requested = info.get("requested_downloads") or []
            candidates = [Path(item["filepath"]) for item in requested if item.get("filepath")]
    except Exception as exc:
        raise PipelineError(f"YouTube download failed: {exc}") from exc

    # Prefer the merged output; requested_downloads may list separate audio and
    # video streams that cannot be rendered individually.
    merged = [p for p in destination.glob("source.*") if p.suffix.lower() in {".mp4", ".mkv", ".webm"}]
    candidates = merged or candidates
    files = [p for p in candidates if p.exists() and p.suffix.lower() not in {".part", ".ytdl"}]
    if not files:
        raise PipelineError("yt-dlp finished but no video file was found.")
    return max(files, key=lambda p: p.stat().st_size)
