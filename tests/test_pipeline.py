import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from shorts_maker.models import (
    ClipCandidate, IngestedSource, MediaInfo, SourceRights, SourceSpec, Transcript, TranscriptSegment,
)
from shorts_maker.pipeline import PipelineConfig, ShortsPipeline


class HighlightsPipelineTests(TestCase):
    def test_local_source_produces_project_metadata_without_overwriting_old_format(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source_path = root / "source.mp4"
            source_path.write_bytes(b"synthetic")
            spec = SourceSpec("local", SourceRights("owned", True, rights_holder="Author"), local_path=source_path)
            source = IngestedSource("source-123", source_path, MediaInfo(180, 1920, 1080, 30, "h264", "aac", 1, "mp4"), spec)
            track = Transcript("en", (TranscriptSegment(0, 50, "A complete story ends here."),), "mock")
            candidate = ClipCandidate(0, 45, 10, "Story", "A complete story ends here.")

            def fake_render(_source, _candidate, _segments, output):
                output.write_bytes(b"rendered video")
                return output

            with patch("shorts_maker.pipeline.require_binary"), patch(
                "shorts_maker.pipeline.ingest_source", return_value=source
            ), patch("shorts_maker.pipeline._transcript_cache", return_value=track), patch(
                "shorts_maker.pipeline.select_clips", return_value=[candidate]
            ), patch("shorts_maker.pipeline.render_clip", side_effect=fake_render):
                outputs = ShortsPipeline(PipelineConfig(root=root)).process(spec)

            self.assertEqual(1, len(outputs))
            metadata = json.loads((outputs[0][0].parent / "metadata.json").read_text(encoding="utf-8"))
            project_files = list((root / "work").glob("*/project.json"))
            self.assertEqual(1, len(project_files))
            project = json.loads(project_files[0].read_text(encoding="utf-8"))
            self.assertEqual("COMPLETED", project["status"])
            self.assertEqual("Author", metadata["rights"]["rights_holder"])
            self.assertEqual("source-123", metadata["clips"][0]["source_id"])
