from __future__ import annotations

from dataclasses import dataclass, field


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


@dataclass(frozen=True)
class ClipCandidate:
    start: float
    end: float
    score: float
    title: str
    transcript: str

