from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import whisper

from .models import TranscriptSegment, Word
from .utils import PipelineError


@lru_cache(maxsize=2)
def load_model(name: str):
    return whisper.load_model(name)


def transcribe(
    video: Path, model_name: str, language: str | None, *, translate_to_english: bool = True
) -> list[TranscriptSegment]:
    try:
        model = load_model(model_name)
        result = model.transcribe(
            str(video),
            language=language,
            task="translate" if translate_to_english else "transcribe",
            word_timestamps=True,
            fp16=False,
            verbose=False,
            condition_on_previous_text=True,
        )
    except Exception as exc:
        raise PipelineError(f"Transcription failed: {exc}") from exc

    segments: list[TranscriptSegment] = []
    for item in result.get("segments", []):
        words = tuple(
            Word(str(w.get("word", "")).strip(), float(w["start"]), float(w["end"]))
            for w in item.get("words", [])
            if w.get("word") and "start" in w and "end" in w
        )
        segments.append(
            TranscriptSegment(float(item["start"]), float(item["end"]), str(item["text"]).strip(), words)
        )
    if not segments:
        raise PipelineError("Whisper did not detect any speech in this video.")
    return segments
