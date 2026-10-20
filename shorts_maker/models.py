from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class Word:
    text: str
    start: float
    end: float


@dataclass(frozen=True)
class TranscriptSegment:
    start: float
    end: float
    text: str
    words: tuple[Word, ...] = field(default_factory=tuple)
    avg_logprob: float | None = None
    no_speech_prob: float | None = None


@dataclass(frozen=True)
class Transcript:
    language: str
    segments: tuple[TranscriptSegment, ...]
    engine: str
    task: str = "transcribe"


@dataclass(frozen=True)
class ClipCandidate:
    start: float
    end: float
    score: float
    title: str
    transcript: str
    score_breakdown: dict[str, float] = field(default_factory=dict)
    explanation: str = ""
    topic: str = ""
    source_id: str = ""
    model_version: str = "heuristic-v2"


@dataclass(frozen=True)
class SourceRights:
    status: Literal["owned", "licensed", "permitted"]
    confirmed: bool
    rights_holder: str = ""
    license_name: str = ""
    permission_note: str = ""


@dataclass(frozen=True)
class SourceSpec:
    kind: Literal["youtube", "local"]
    rights: SourceRights
    url: str = ""
    local_path: Path | None = None
    original_name: str = ""
    max_height: int = 720


@dataclass(frozen=True)
class MediaInfo:
    duration: float
    width: int
    height: int
    fps: float
    video_codec: str
    audio_codec: str
    audio_streams: int
    format_name: str


@dataclass(frozen=True)
class IngestedSource:
    source_id: str
    path: Path
    info: MediaInfo
    spec: SourceSpec
