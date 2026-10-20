from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from shorts_maker.captions import create_ass
from shorts_maker.models import TranscriptSegment, Word
from shorts_maker.selector import select_clips


class ExistingPipelineTests(TestCase):
    def setUp(self):
        self.segments = [
            TranscriptSegment(
                start=i * 4.0,
                end=i * 4.0 + 3.5,
                text=f"How does project {i} transform case {i*i}? Here is lesson {i+7} with unique result {i*i*i}!",
                words=(
                    Word("Here", i * 4.0, i * 4.0 + 0.7),
                    Word("is", i * 4.0 + 0.7, i * 4.0 + 1.2),
                ),
            )
            for i in range(80)
        ]

    def test_six_distinct_short_candidates(self):
        clips = select_clips(self.segments, video_duration=320, count=6)
        self.assertEqual(6, len(clips))
        self.assertTrue(all(40 <= clip.end - clip.start <= 50 for clip in clips))
        for index, first in enumerate(clips):
            for second in clips[index + 1 :]:
                overlap = max(0.0, min(first.end, second.end) - max(first.start, second.start))
                self.assertLessEqual(overlap, 5.0)

    def test_captions_stay_inside_clip(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "captions.ass"
            create_ass(self.segments, 40.0, 45.0, output)
            content = output.read_text(encoding="utf-8-sig")
            self.assertIn("[Events]", content)
            self.assertIn("\\fscx122", content)
            self.assertNotIn("Dialogue: 0,0:00:06", content)

    def test_repeated_content_is_not_returned_as_six_distinct_clips(self):
        repeated = [
            TranscriptSegment(i * 4.0, i * 4.0 + 3.5, "The same repeated sentence appears again and again.")
            for i in range(80)
        ]
        clips = select_clips(repeated, 320, count=6)
        self.assertLess(len(clips), 6)

    def test_short_profile_has_explainable_scores(self):
        clips = select_clips(self.segments, 320, count=4, clip_length=22, length_range=(15, 30))
        self.assertEqual(4, len(clips))
        self.assertTrue(all(15 <= clip.end - clip.start <= 30 for clip in clips))
        self.assertTrue(all("hook" in clip.score_breakdown and clip.explanation for clip in clips))
