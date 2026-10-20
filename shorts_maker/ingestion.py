"""Source validation, managed local files, and FFprobe media inspection."""

from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import BinaryIO, Callable
from urllib.parse import urlparse

from .models import IngestedSource, MediaInfo, SourceRights, SourceSpec
from .utils import PipelineError, require_binary, run

VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv"}
Progress = Callable[[float, str], None]


def validate_youtube_url(url: str) -> str:
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower()
    allowed = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}
    if parsed.scheme not in {"http", "https"} or host not in allowed or not parsed.path.strip("/"):
        raise PipelineError("Érvényes YouTube-videó URL szükséges.")
    if parsed.username or parsed.password:
        raise PipelineError("Felhasználónév/jelszó nem adható meg a videó URL-jében.")
    return url.strip()


def validate_rights(rights: SourceRights) -> None:
    if not rights.confirmed or rights.status not in {"owned", "licensed", "permitted"}:
        raise PipelineError("A feldolgozás előtt nyilatkozni kell a forrás felhasználási jogáról.")


def check_free_space(root: Path, required_bytes: int = 512 * 1024 * 1024) -> None:
    root.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(root).free
    if free < required_bytes:
        raise PipelineError(
            f"Nincs elég szabad lemezterület: legalább {required_bytes / (1024**3):.1f} GB szükséges."
        )


def _fps(value: str) -> float:
    try:
        numerator, denominator = value.split("/", 1)
        return float(numerator) / float(denominator)
    except (ValueError, ZeroDivisionError, AttributeError):
        return 0.0


def probe_media(path: Path) -> MediaInfo:
    ffprobe = require_binary("ffprobe")
    result = run([ffprobe, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)], capture=True)
    try:
        data = json.loads(result.stdout)
        streams = data["streams"]
        video = next(stream for stream in streams if stream.get("codec_type") == "video")
        audio = [stream for stream in streams if stream.get("codec_type") == "audio"]
        duration = float(data["format"].get("duration") or video.get("duration") or 0)
        info = MediaInfo(
            duration=duration,
            width=int(video.get("width") or 0),
            height=int(video.get("height") or 0),
            fps=_fps(video.get("avg_frame_rate") or video.get("r_frame_rate") or "0/1"),
            video_codec=str(video.get("codec_name") or "unknown"),
            audio_codec=str(audio[0].get("codec_name") or "unknown") if audio else "",
            audio_streams=len(audio),
            format_name=str(data["format"].get("format_name") or ""),
        )
    except (KeyError, TypeError, ValueError, StopIteration) as exc:
        raise PipelineError("Nem sikerült beolvasni a videó metaadatait.") from exc
    if info.duration < 10 or info.duration > 12 * 3600 or info.width < 16 or info.height < 16:
        raise PipelineError("A videó hossza vagy felbontása nem támogatott (10 mp–12 óra).")
    if info.fps <= 0 or info.fps > 120:
        raise PipelineError("A videó FPS értéke hiányzik vagy nem támogatott.")
    if not info.audio_streams:
        raise PipelineError("A videó nem tartalmaz hangsávot; a beszédfelismeréshez hang szükséges.")
    return info


def store_upload(stream: BinaryIO, filename: str, root: Path) -> Path:
    suffix = Path(filename).suffix.lower()
    if suffix not in VIDEO_SUFFIXES:
        raise PipelineError("Csak MP4, MOV vagy MKV videó tölthető fel.")
    destination = root / "work" / "sources" / "uploads"
    check_free_space(destination)
    destination.mkdir(parents=True, exist_ok=True)
    staging = destination / f"upload-{uuid.uuid4().hex}.part"
    digest = hashlib.sha256()
    size = 0
    try:
        with staging.open("wb") as target:
            while chunk := stream.read(1024 * 1024):
                size += len(chunk)
                if size > 4 * 1024**3:
                    raise PipelineError("A feltöltött fájl túllépi a 4 GB-os korlátot.")
                digest.update(chunk)
                target.write(chunk)
        if size == 0:
            raise PipelineError("A feltöltött videófájl üres.")
        final = destination / f"{digest.hexdigest()}{suffix}"
        if final.exists():
            staging.unlink()
        else:
            staging.replace(final)
        return final
    finally:
        if staging.exists():
            staging.unlink()


def ingest_source(spec: SourceSpec, root: Path, progress: Progress) -> IngestedSource:
    validate_rights(spec.rights)
    source_root = root / "work" / "sources"
    check_free_space(source_root)
    if spec.kind == "youtube":
        from .downloader import download_video

        url = validate_youtube_url(spec.url)
        if spec.max_height not in {720, 1080}:
            raise PipelineError("A forrásminőség csak 720p vagy 1080p lehet.")
        source_id = hashlib.sha256(f"{url}|{spec.max_height}".encode("utf-8")).hexdigest()[:16]
        destination = source_root / source_id
        path = download_video(url, destination, progress, max_height=spec.max_height)
        try:
            info = probe_media(path)
        except PipelineError:
            # A previous run may have left a truncated media file. Keep it for
            # inspection, then retry the source once without that cache entry.
            path.replace(path.with_name(f"{path.name}.{uuid.uuid4().hex}.invalid"))
            path = download_video(url, destination, progress, max_height=spec.max_height, use_cache=False)
            info = probe_media(path)
    elif spec.kind == "local":
        original = spec.local_path
        if original is None or not original.is_file() or original.suffix.lower() not in VIDEO_SUFFIXES:
            raise PipelineError("Válassz létező MP4, MOV vagy MKV videófájlt.")
        # The uploaded file already lives in managed storage. An external local
        # path is copied once so a later rerender does not depend on that path.
        if original.resolve().parent == (source_root / "uploads").resolve():
            source_id = original.stem[:16]
            path = original
        else:
            digest = hashlib.sha256()
            with original.open("rb") as source_file:
                while chunk := source_file.read(1024 * 1024):
                    digest.update(chunk)
            source_id = digest.hexdigest()[:16]
            destination = source_root / source_id
            destination.mkdir(parents=True, exist_ok=True)
            path = destination / f"source{original.suffix.lower()}"
            if not path.exists() or path.stat().st_size != original.stat().st_size:
                check_free_space(destination, original.stat().st_size * 2)
                temporary = destination / f"source-{uuid.uuid4().hex}.part"
                try:
                    shutil.copyfile(original, temporary)
                    temporary.replace(path)
                finally:
                    if temporary.exists():
                        temporary.unlink()
        progress(1.0, "Helyi videó importálva")
        info = probe_media(path)
    else:
        raise PipelineError("Ismeretlen videóforrás típus.")
    return IngestedSource(source_id, path, info, spec)


def source_record(source: IngestedSource) -> dict:
    record = asdict(source)
    record["path"] = str(source.path)
    if source.spec.local_path is not None:
        record["spec"]["local_path"] = str(source.spec.local_path)
    return record
