from __future__ import annotations

from pathlib import Path

from .captions import create_ass
from .models import ClipCandidate, TranscriptSegment
from .utils import escape_ass_path, require_binary, run


def render_clip(
    source: Path, candidate: ClipCandidate, segments: list[TranscriptSegment], output: Path
) -> Path:
    ffmpeg = require_binary("ffmpeg")
    subtitle = output.with_suffix(".ass")
    create_ass(segments, candidate.start, candidate.end, subtitle)
    duration = candidate.end - candidate.start
    # Scale until the frame covers 1080x1920, then center-crop. setsar avoids anamorphic output.
    video_filter = (
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,setsar=1,"
        f"ass='{escape_ass_path(subtitle)}'"
    )
    run([
        ffmpeg, "-y", "-ss", f"{candidate.start:.3f}", "-i", str(source), "-t", f"{duration:.3f}",
        "-vf", video_filter, "-c:v", "libx264", "-preset", "medium", "-crf", "21",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "-pix_fmt", "yuv420p", str(output),
    ])
    return output

