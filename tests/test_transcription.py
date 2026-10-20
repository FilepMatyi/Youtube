from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from shorts_maker.models import Transcript, TranscriptSegment, Word
from shorts_maker.pipeline import _transcript_cache
from shorts_maker.transcriber import transcribe_track


class TranscriptionTests(TestCase):
    def test_faster_whisper_keeps_detected_language_and_original_word_times(self):
        segment = SimpleNamespace(
            start=1.0, end=2.0, text=" Szia világ!",
            words=[SimpleNamespace(word=" Szia", start=1.0, end=1.4)],
            avg_logprob=-0.2, no_speech_prob=0.01,
        )
        model = SimpleNamespace(transcribe=lambda *_args, **_kwargs: (iter([segment]), SimpleNamespace(language="hu")))
        with patch("shorts_maker.transcriber.load_model", return_value=model):
            result = transcribe_track(Path("sample.mp4"), "base", None, engine="faster-whisper")
        self.assertEqual("hu", result.language)
        self.assertEqual("Szia", result.segments[0].words[0].text)
        self.assertEqual(1.0, result.segments[0].words[0].start)
        self.assertEqual(-0.2, result.segments[0].avg_logprob)

    def test_translation_is_a_separate_phrase_track_and_caches_independently(self):
        original = Transcript("hu", (TranscriptSegment(1, 2, "Szia", (Word("Szia", 1, 2),)),), "faster-whisper")
        translated = Transcript("hu", (TranscriptSegment(1, 2, "Hello", (Word("Hello", 1, 2),)),), "faster-whisper", "translate")
        with TemporaryDirectory() as directory:
            source = Path(directory) / "source.mp4"
            source.write_bytes(b"video")
            cache_dir = Path(directory) / "transcripts"
            with patch("shorts_maker.pipeline.transcribe_track", side_effect=[original, translated]) as mock_transcribe:
                first = _transcript_cache(cache_dir, source, "base", "hu", "transcribe", "faster-whisper", True)
                second = _transcript_cache(cache_dir, source, "base", "hu", "translate", "faster-whisper", True)
                cached = _transcript_cache(cache_dir, source, "base", "hu", "transcribe", "faster-whisper", True)
            self.assertEqual(2, mock_transcribe.call_count)
            self.assertEqual("Szia", first.segments[0].words[0].text)
            self.assertEqual(first, cached)
            self.assertEqual("Hello", second.segments[0].text)
            self.assertEqual((), second.segments[0].words)
