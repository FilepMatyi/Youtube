import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from shorts_maker.ingestion import ingest_source, probe_media, store_upload, validate_rights, validate_youtube_url
from shorts_maker.models import MediaInfo, SourceRights, SourceSpec
from shorts_maker.utils import PipelineError


class IngestionTests(TestCase):
    def test_url_and_rights_validation(self):
        self.assertEqual("https://youtu.be/abc", validate_youtube_url(" https://youtu.be/abc "))
        for url in ("https://youtube.com.evil.test/watch?v=abc", "file:///video.mp4", "https://user:pass@youtube.com/watch"):
            with self.subTest(url=url), self.assertRaises(PipelineError):
                validate_youtube_url(url)
        with self.assertRaises(PipelineError):
            validate_rights(SourceRights("owned", False))
        validate_rights(SourceRights("permitted", True, rights_holder="Creator"))

    def test_probe_parses_video_and_audio(self):
        payload = {
            "streams": [
                {"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080, "avg_frame_rate": "30000/1001"},
                {"codec_type": "audio", "codec_name": "aac"},
            ],
            "format": {"duration": "123.5", "format_name": "mov,mp4,m4a,3gp,3g2,mj2"},
        }
        with patch("shorts_maker.ingestion.require_binary", return_value="ffprobe"), patch(
            "shorts_maker.ingestion.run", return_value=SimpleNamespace(stdout=json.dumps(payload))
        ):
            info = probe_media(Path("sample.mp4"))
        self.assertEqual(1920, info.width)
        self.assertAlmostEqual(29.97, info.fps, places=2)
        self.assertEqual(1, info.audio_streams)

    def test_upload_deduplicates_and_local_source_preserves_rights(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("shorts_maker.ingestion.check_free_space"):
                first = store_upload(io.BytesIO(b"synthetic video"), "example.mp4", root)
                second = store_upload(io.BytesIO(b"synthetic video"), "example.mp4", root)
            self.assertEqual(first, second)
            self.assertEqual(b"synthetic video", first.read_bytes())
            rights = SourceRights("owned", True, rights_holder="Test author")
            fake_info = MediaInfo(120, 1920, 1080, 30, "h264", "aac", 1, "mp4")
            with patch("shorts_maker.ingestion.check_free_space"), patch(
                "shorts_maker.ingestion.probe_media", return_value=fake_info
            ):
                source = ingest_source(SourceSpec("local", rights, local_path=first), root, lambda *_: None)
            self.assertEqual(first, source.path)
            self.assertEqual("Test author", source.spec.rights.rights_holder)

    def test_corrupt_cached_youtube_file_is_preserved_and_retried(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / "source.mp4"
            video.write_bytes(b"broken cache")
            rights = SourceRights("permitted", True, rights_holder="Creator")
            info = MediaInfo(90, 1280, 720, 30, "h264", "aac", 1, "mp4")
            calls = []

            def fake_download(*args, **kwargs):
                calls.append(kwargs.get("use_cache", True))
                if kwargs.get("use_cache") is False:
                    video.write_bytes(b"repaired cache")
                return video

            def fake_probe(path):
                if path.read_bytes() == b"broken cache":
                    raise PipelineError("bad media")
                return info

            with patch("shorts_maker.ingestion.check_free_space"), patch(
                "shorts_maker.downloader.download_video", side_effect=fake_download
            ), patch("shorts_maker.ingestion.probe_media", side_effect=fake_probe):
                result = ingest_source(
                    SourceSpec("youtube", rights, url="https://youtu.be/example"), root, lambda *_: None
                )
            self.assertEqual([True, False], calls)
            self.assertEqual(info, result.info)
            self.assertEqual(1, len(list(root.glob("*.invalid"))))
