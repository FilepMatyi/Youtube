"""Local speech recognition adapters. Translation never replaces the source track."""

from __future__ import annotations

import importlib.util
import os
from functools import lru_cache
from pathlib import Path

from .models import Transcript, TranscriptSegment, Word
from .utils import PipelineError


def available_engines() -> list[str]:
    result = []
    if importlib.util.find_spec("faster_whisper") is not None:
        result.append("faster-whisper")
    if importlib.util.find_spec("whisper") is not None:
        result.append("openai-whisper")
    return result


@lru_cache(maxsize=2)
def load_model(name: str, engine: str):
    if engine == "faster-whisper":
        from faster_whisper import WhisperModel

        return WhisperModel(name, device="cpu", compute_type="int8", cpu_threads=max(1, min(8, os.cpu_count() or 1)))
    if engine == "openai-whisper":
        import whisper

        return whisper.load_model(name)
    raise PipelineError(f"Ismeretlen beszédfelismerő motor: {engine}")


def transcribe_track(
    video: Path,
    model_name: str,
    language: str | None,
    *,
    task: str = "transcribe",
    engine: str = "auto",
    vad: bool = True,
) -> Transcript:
    if task not in {"transcribe", "translate"}:
        raise PipelineError("Érvénytelen beszédfelismerési feladat.")
    if language not in {None, "hu", "en", "ro"}:
        raise PipelineError("Csak automatikus, magyar, angol vagy román nyelv választható.")
    if engine == "auto":
        engines = available_engines()
        if not engines:
            raise PipelineError("Telepítsd a faster-whisper csomagot (vagy a régi openai-whisper motort).")
        engine = engines[0]
    try:
        model = load_model(model_name, engine)
        if engine == "faster-whisper":
            raw_segments, info = model.transcribe(
                str(video), language=language, task=task, word_timestamps=True,
                beam_size=5, vad_filter=vad, vad_parameters={"min_silence_duration_ms": 1200},
                condition_on_previous_text=True,
            )
            detected_language = info.language or language or "und"
            segments = tuple(
                TranscriptSegment(
                    float(item.start), float(item.end), item.text.strip(),
                    tuple(Word(word.word.strip(), float(word.start), float(word.end)) for word in (item.words or []) if word.word.strip()),
                    float(item.avg_logprob) if item.avg_logprob is not None else None,
                    float(item.no_speech_prob) if item.no_speech_prob is not None else None,
                )
                for item in raw_segments
            )
        elif engine == "openai-whisper":
            result = model.transcribe(
                str(video), language=language, task=task, word_timestamps=True,
                fp16=False, verbose=False, condition_on_previous_text=True,
            )
            detected_language = result.get("language") or language or "und"
            segments = tuple(
                TranscriptSegment(
                    float(item["start"]), float(item["end"]), str(item["text"]).strip(),
                    tuple(
                        Word(str(word["word"]).strip(), float(word["start"]), float(word["end"]))
                        for word in item.get("words", []) if word.get("word")
                    ),
                    float(item["avg_logprob"]) if item.get("avg_logprob") is not None else None,
                    float(item["no_speech_prob"]) if item.get("no_speech_prob") is not None else None,
                )
                for item in result.get("segments", [])
            )
        else:
            raise PipelineError(f"Ismeretlen beszédfelismerő motor: {engine}")
    except PipelineError:
        raise
    except Exception as exc:
        raise PipelineError(f"A beszédfelismerés sikertelen: {exc}") from exc
    if not segments:
        raise PipelineError("Nem sikerült beszédet felismerni a videóban.")
    return Transcript(detected_language, segments, engine, task)


def transcribe(
    video: Path, model_name: str, language: str | None, *, translate_to_english: bool = False
) -> list[TranscriptSegment]:
    """Compatibility wrapper for callers expecting only segments."""
    return list(transcribe_track(video, model_name, language, task="translate" if translate_to_english else "transcribe").segments)
