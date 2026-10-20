from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class PipelineError(RuntimeError):
    """An error safe to display in the UI."""


def require_binary(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise PipelineError(
            f"'{name}' was not found. Install FFmpeg and ensure both ffmpeg and "
            "ffprobe are available on PATH, then restart the app."
        )
    return path


def run(command: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            check=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip().splitlines()
        message = detail[-1] if detail else "Unknown command error"
        raise PipelineError(message) from exc


def media_duration(path: Path) -> float:
    ffprobe = require_binary("ffprobe")
    result = run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        capture=True,
    )
    try:
        return float(result.stdout.strip())
    except ValueError as exc:
        raise PipelineError("Could not determine the downloaded video's duration.") from exc


def escape_ass_path(path: Path) -> str:
    # FFmpeg filter paths need forward slashes; drive colon and filter characters are escaped.
    value = path.resolve().as_posix().replace("\\", "/")
    return value.replace(":", r"\:").replace("'", r"\'").replace("[", r"\[").replace("]", r"\]")

