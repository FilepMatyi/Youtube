"""Shared ingestion/transcription path for Original Content script review."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from .ingestion import ingest_source, source_record
from .models import ClipCandidate, SourceSpec, Transcript
from .pipeline import PipelineConfig, _transcript_cache
from .selector import select_clips
from .utils import PipelineError, require_binary


@dataclass(frozen=True)
class OriginalPreparation:
    project_dir: Path
    source_id: str
    transcript: Transcript
    topics: tuple[ClipCandidate, ...]


def prepare_original(
    source_spec: SourceSpec, config: PipelineConfig, progress: Callable[[float, str], None]
) -> OriginalPreparation:
    require_binary("ffmpeg")
    require_binary("ffprobe")
    progress(0.02, "Forrás importálása")
    source = ingest_source(source_spec, config.root, lambda value, message: progress(0.02 + value * 0.25, message))
    progress(0.30, "Eredeti átirat készítése")
    track = _transcript_cache(
        config.root / "work" / "transcripts", source.path, config.whisper_model,
        config.language, "transcribe", config.transcription_engine, config.use_vad,
    )
    progress(0.80, "Önálló témák keresése")
    topics = select_clips(list(track.segments), source.info.duration, count=6, clip_length=45, length_range=(40, 60))
    if not topics:
        raise PipelineError("Nem találtam önállóan feldolgozható beszédszakaszt.")
    project_key = f"original|{source.source_id}|{config.whisper_model}|{track.engine}"
    project_id = hashlib.sha256(project_key.encode()).hexdigest()[:12]
    project_dir = config.root / "work" / "original" / project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 1,
        "mode": "original",
        "status": "AWAITING_TOPIC_SELECTION",
        "source": source_record(source),
        "language": track.language,
        "transcription_engine": track.engine,
        "topics": [asdict(topic) for topic in topics],
        "transcript": [asdict(segment) for segment in track.segments],
    }
    temporary = project_dir / "project.tmp"
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(project_dir / "project.json")
    progress(1.0, "Témák készen állnak")
    return OriginalPreparation(project_dir, source.source_id, track, tuple(topics))
