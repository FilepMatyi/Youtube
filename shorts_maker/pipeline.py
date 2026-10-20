from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from .downloader import download_video
from .editor import render_clip
from .models import ClipCandidate
from .selector import select_clips
from .transcriber import transcribe
from .utils import media_duration, require_binary

Progress = Callable[[float, str], None]


@dataclass(frozen=True)
class PipelineConfig:
    root: Path = Path(".")
    whisper_model: str = "base"
    language: str | None = None
    clip_count: int = 5
    clip_length: int = 45
    english_captions: bool = True


class ShortsPipeline:
    def __init__(self, config: PipelineConfig):
        self.config = config

    def process(self, url: str, progress: Progress = lambda _p, _m: None) -> list[tuple[Path, ClipCandidate]]:
        require_binary("ffmpeg")
        require_binary("ffprobe")
        job_key = f"{url.strip()}|{self.config.whisper_model}|{self.config.language}|{self.config.clip_count}|{self.config.clip_length}"
        job_id = hashlib.sha256(job_key.encode()).hexdigest()[:12]
        work_dir = self.config.root / "work" / job_id
        output_dir = self.config.root / "output" / job_id
        work_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        progress(0.02, "Downloading video")
        source = download_video(url, work_dir, lambda p, m: progress(0.02 + p * 0.18, m))
        progress(0.22, f"Transcribing and translating with Whisper ({self.config.whisper_model})")
        segments = transcribe(
            source,
            self.config.whisper_model,
            self.config.language,
            translate_to_english=self.config.english_captions,
        )
        progress(0.60, "Finding the most engaging moments")
        candidates = select_clips(segments, media_duration(source), self.config.clip_count, self.config.clip_length)

        results: list[tuple[Path, ClipCandidate]] = []
        for index, candidate in enumerate(candidates, 1):
            progress(0.62 + (index - 1) / max(1, len(candidates)) * 0.35, f"Rendering clip {index}/{len(candidates)}")
            path = output_dir / f"short_{index:02d}.mp4"
            render_clip(source, candidate, segments, path)
            results.append((path, candidate))

        metadata = {"url": url, "clips": [{"file": p.name, **asdict(c)} for p, c in results]}
        (output_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        progress(1.0, "Done")
        return results
