from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Callable

from .editor import render_clip
from .ingestion import ingest_source, source_record
from .models import ClipCandidate, SourceSpec, Transcript, TranscriptSegment, Word
from .selector import select_clips
from .transcriber import transcribe_track
from .utils import require_binary

Progress = Callable[[float, str], None]


@dataclass(frozen=True)
class PipelineConfig:
    root: Path = Path(".")
    whisper_model: str = "base"
    language: str | None = None
    clip_count: int = 5
    clip_length: int = 45
    caption_language: str = "original"
    max_height: int = 720
    transcription_engine: str = "auto"
    use_vad: bool = True
    clip_min: int = 40
    clip_max: int = 50


def _transcript_cache(
    path: Path, source: Path, model: str, language: str | None, task: str, engine: str, vad: bool
) -> Transcript:
    key = hashlib.sha256(f"{source}|{source.stat().st_size}|{model}|{language}|{task}|{engine}|{vad}".encode()).hexdigest()[:16]
    cache = path / f"{key}.json"
    if cache.exists():
        data = json.loads(cache.read_text(encoding="utf-8"))
        segments = tuple(
            TranscriptSegment(
                float(item["start"]), float(item["end"]), item["text"],
                tuple(Word(**word) for word in item.get("words", [])),
                item.get("avg_logprob"), item.get("no_speech_prob"),
            )
            for item in data["segments"]
        )
        return Transcript(data["language"], segments, data["engine"], data["task"])
    track = transcribe_track(source, model, language, task=task, engine=engine, vad=vad)
    # Translated words do not have reliable alignment with the original audio.
    # Render these as phrase-level captions until a dedicated aligner is added.
    if task == "translate":
        track = Transcript(
            track.language,
            tuple(TranscriptSegment(s.start, s.end, s.text) for s in track.segments),
            track.engine,
            track.task,
        )
    path.mkdir(parents=True, exist_ok=True)
    temporary = cache.with_suffix(".tmp")
    temporary.write_text(json.dumps(asdict(track), ensure_ascii=False), encoding="utf-8")
    temporary.replace(cache)
    return track


class ShortsPipeline:
    def __init__(self, config: PipelineConfig):
        self.config = config

    def process(self, source_spec: SourceSpec, progress: Progress = lambda _p, _m: None) -> list[tuple[Path, ClipCandidate]]:
        require_binary("ffmpeg")
        require_binary("ffprobe")
        progress(0.02, "Forrás ellenőrzése és importálása")
        source = ingest_source(
            source_spec, self.config.root,
            lambda value, message: progress(0.02 + 0.18 * value, message),
        )
        job_key = (
            f"{source.source_id}|{self.config.whisper_model}|{self.config.language}|"
            f"{self.config.clip_count}|{self.config.clip_length}|{self.config.clip_min}|{self.config.clip_max}|"
            f"{self.config.caption_language}|{self.config.transcription_engine}|{self.config.use_vad}"
        )
        job_id = hashlib.sha256(job_key.encode()).hexdigest()[:12]
        work_dir = self.config.root / "work" / job_id
        output_dir = self.config.root / "output" / job_id
        work_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        project = {
            "schema_version": 1,
            "mode": "highlights",
            "source": source_record(source),
            "config": {**asdict(self.config), "root": str(self.config.root)},
            "status": "TRANSCRIBING",
        }
        project_file = work_dir / "project.json"
        project_file.write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")

        progress(0.22, f"Eredeti nyelvű átirat ({self.config.whisper_model})")
        transcript_cache = self.config.root / "work" / "transcripts"
        original_track = _transcript_cache(
            transcript_cache, source.path, self.config.whisper_model, self.config.language,
            "transcribe", self.config.transcription_engine, self.config.use_vad,
        )
        segments = list(original_track.segments)
        caption_segments = segments
        if self.config.caption_language == "en" and original_track.language != "en":
            progress(0.45, "Külön angol feliratsáv készítése")
            caption_segments = list(_transcript_cache(
                transcript_cache, source.path, self.config.whisper_model, self.config.language,
                "translate", self.config.transcription_engine, self.config.use_vad,
            ).segments)
        progress(0.60, "Legjobb részletek kiválasztása")
        candidates = [
            replace(candidate, source_id=source.source_id)
            for candidate in select_clips(
                segments, source.info.duration, self.config.clip_count, self.config.clip_length,
                (self.config.clip_min, self.config.clip_max),
            )
        ]
        if not candidates:
            raise PipelineError("Nem találtam elég beszédet tartalmazó, megfelelő hosszúságú részletet.")

        results: list[tuple[Path, ClipCandidate]] = []
        for index, candidate in enumerate(candidates, 1):
            progress(0.62 + (index - 1) / max(1, len(candidates)) * 0.35, f"Klip renderelése {index}/{len(candidates)}")
            path = output_dir / f"short_{index:02d}.mp4"
            render_clip(source.path, candidate, caption_segments, path)
            results.append((path, candidate))

        metadata = {
            "url": source_spec.url,
            "source_id": source.source_id,
            "rights": asdict(source_spec.rights),
            "caption_language": self.config.caption_language,
            "source_language": original_track.language,
            "transcription_engine": original_track.engine,
            "clips": [{"file": p.name, **asdict(c)} for p, c in results],
        }
        (output_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        project["status"] = "COMPLETED"
        project["outputs"] = [str(path) for path, _ in results]
        project_file.write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")
        progress(1.0, "Done")
        return results
