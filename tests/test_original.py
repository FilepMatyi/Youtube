import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from shorts_maker.models import (
    ClipCandidate, IngestedSource, MediaInfo, SourceRights, SourceSpec, Transcript, TranscriptSegment,
)
from shorts_maker.original import evidence_for_range, generate_original_draft
from shorts_maker.original_pipeline import prepare_original
from shorts_maker.pipeline import PipelineConfig
from shorts_maker.utils import PipelineError


class OriginalScriptTests(TestCase):
    def setUp(self):
        self.evidence = evidence_for_range(
            [TranscriptSegment(10, 14, "The speaker says energy use doubled."),
             TranscriptSegment(14, 18, "They compare two experiments with different results.")],
            "source-123", 10, 18,
        )
        self.proposal = {
            "title": "Mit jelent a két kísérlet?",
            "hook": "Ugyanaz a módszer két különböző eredményt hozott.",
            "context": "A forrás két kísérletet hasonlít össze.",
            "source_evidence": "A beszélő energiahasználati változást említ.",
            "original_analysis": "A különbség értelmezéséhez a körülményeket is vizsgálni kell, nem csak a számot.",
            "conclusion": "A következtetés előtt nézd meg, mit mértek valójában.",
            "claims": [{"text": "A forrás szerint az energiahasználat megduplázódott.", "evidence_ids": [1], "requires_external_verification": False}],
        }

    def test_evidence_is_resolved_to_original_source_timestamps(self):
        with patch("shorts_maker.original._local_json", return_value={"message": {"content": json.dumps(self.proposal)}}):
            draft = generate_original_draft(self.evidence, model="installed-local-model", language="hu", style="elemző")
        self.assertEqual("AWAITING_SCRIPT_APPROVAL", draft.status)
        self.assertEqual("source-123", draft.claims[0].evidence[0].source_id)
        self.assertEqual(10, draft.claims[0].evidence[0].source_start)
        self.assertEqual("The speaker says energy use doubled.", draft.claims[0].evidence[0].supporting_text)
        self.assertEqual(1, draft.to_dict()["claims"][0]["evidence"][0]["segment_id"])

    def test_invented_evidence_id_is_rejected(self):
        self.proposal["claims"][0]["evidence_ids"] = [999]
        with patch("shorts_maker.original._local_json", return_value={"message": {"content": json.dumps(self.proposal)}}):
            with self.assertRaises(PipelineError):
                generate_original_draft(self.evidence, model="installed-local-model", language="hu", style="elemző")

    def test_uncited_fact_without_review_flag_is_rejected(self):
        self.proposal["claims"][0]["evidence_ids"] = []
        with patch("shorts_maker.original._local_json", return_value={"message": {"content": json.dumps(self.proposal)}}):
            with self.assertRaises(PipelineError):
                generate_original_draft(self.evidence, model="installed-local-model", language="hu", style="elemző")

    def test_original_preparation_persists_topics_and_original_transcript(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source_path = root / "source.mp4"
            source_path.write_bytes(b"synthetic")
            spec = SourceSpec("local", SourceRights("owned", True), local_path=source_path)
            source = IngestedSource("source-123", source_path, MediaInfo(120, 1280, 720, 30, "h264", "aac", 1, "mp4"), spec)
            track = Transcript("hu", (TranscriptSegment(10, 14, "Szia világ!"),), "faster-whisper")
            topic = ClipCandidate(8, 50, 10, "Téma", "Szia világ!")
            with patch("shorts_maker.original_pipeline.require_binary"), patch(
                "shorts_maker.original_pipeline.ingest_source", return_value=source
            ), patch("shorts_maker.original_pipeline._transcript_cache", return_value=track), patch(
                "shorts_maker.original_pipeline.select_clips", return_value=[topic]
            ):
                preparation = prepare_original(spec, PipelineConfig(root=root), lambda *_: None)
            project = json.loads((preparation.project_dir / "project.json").read_text(encoding="utf-8"))
            self.assertEqual("AWAITING_TOPIC_SELECTION", project["status"])
            self.assertEqual("hu", project["language"])
            self.assertEqual("Szia világ!", project["transcript"][0]["text"])
