import tempfile
import unittest
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from exam_extractor.config import PipelineConfig
from exam_extractor.models import FrameEvidence, OCRResult, SourceKind, SourceMetadata, SourceRef, Transcript, TranscriptSegment
from exam_extractor.models.questions import AnswerOption, QuestionRecord
from exam_extractor.services.docx_service import write_docx
from exam_extractor.services.pdf_service import extract_pdf_pages
from exam_extractor.services.source_service import _fetch_transcript_fallback, _is_caption_download_error, _youtube_video_id, acquire_source, detect_source


class Phase8Tests(unittest.TestCase):
    def test_pdf_detection_and_page_rendering_contract(self) -> None:
        self.assertEqual(detect_source("lesson.pdf").kind, SourceKind.PDF)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "pages"
            pdf = Path(directory) / "lesson.pdf"
            pdf.write_bytes(b"placeholder")

            def fake_poppler(command, stage):
                target.mkdir(parents=True, exist_ok=True)
                (target / "page-1.png").write_bytes(b"png")

            with patch("exam_extractor.services.pdf_service.executable", return_value="pdftoppm"), patch("exam_extractor.services.pdf_service.run_checked", side_effect=fake_poppler):
                pages = extract_pdf_pages(pdf, target, PipelineConfig())
        self.assertEqual(pages[0].method, "pdf_page")

    def test_privacy_defaults_are_safe_and_validated(self) -> None:
        config = PipelineConfig()
        self.assertFalse(config.privacy.redact_source)
        config.privacy.retention_days = 30
        config.validate()
        config.privacy.retention_days = 0
        with self.assertRaises(ValueError):
            config.validate()

    def test_caption_failures_are_classified_as_recoverable(self) -> None:
        self.assertTrue(_is_caption_download_error(RuntimeError("HTTP 429 subtitles")))
        self.assertFalse(_is_caption_download_error(RuntimeError("video unavailable")))
        self.assertEqual(_youtube_video_id("https://www.youtube.com/watch?v=abc123&list=playlist"), "abc123")

    def test_transcript_fallback_writes_webvtt(self) -> None:
        class FakeApi:
            def fetch(self, _video_id, languages):
                return [SimpleNamespace(text="Hello transcript", start=1.5, duration=2.0)]

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            fake_module = SimpleNamespace(YouTubeTranscriptApi=lambda: FakeApi())
            with patch.dict(sys.modules, {"youtube_transcript_api": fake_module}):
                result = _fetch_transcript_fallback("https://www.youtube.com/watch?v=abc123", target)
            self.assertIsNotNone(result)
            path, language = result
            self.assertEqual(language, "en")
            self.assertIn("00:00:01.500 --> 00:00:03.500", path.read_text(encoding="utf-8"))
            self.assertIn("Hello transcript", path.read_text(encoding="utf-8"))

    def test_transcript_fallback_uses_available_non_english_language(self) -> None:
        class FakeTranscript:
            language_code = "ar"

            def fetch(self):
                return [SimpleNamespace(text="نص المحاضرة", start=0.0, duration=1.0)]

        class FakeTranscriptList:
            manually_created_transcripts = []
            generated_transcripts = [FakeTranscript()]

        class FakeApi:
            def fetch(self, _video_id, languages):
                raise RuntimeError("No English transcript")

            def list(self, _video_id):
                return FakeTranscriptList()

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            fake_module = SimpleNamespace(YouTubeTranscriptApi=lambda: FakeApi())
            with patch.dict(sys.modules, {"youtube_transcript_api": fake_module}):
                result = _fetch_transcript_fallback("https://www.youtube.com/watch?v=abc123", target)
            self.assertIsNotNone(result)
            path, language = result
            self.assertEqual(language, "ar")
            self.assertEqual(path.name, "captions.ar.vtt")
            self.assertIn("نص المحاضرة", path.read_text(encoding="utf-8"))

    def test_youtube_media_falls_back_when_caption_download_fails(self) -> None:
        class FakeDownloader:
            def __init__(self, options):
                self.options = options

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def extract_info(self, _source, download=True):
                if self.options.get("writesubtitles"):
                    raise RuntimeError("HTTP 429: subtitles")
                (target / "media.mp4").write_bytes(b"video")
                return {"id": "abc", "title": "Fallback", "duration": 10, "uploader": "test"}

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "job"
            fake_module = SimpleNamespace(YoutubeDL=FakeDownloader)
            with patch.dict(sys.modules, {"yt_dlp": fake_module}):
                acquired, metadata = acquire_source(
                    SourceRef("https://www.youtube.com/watch?v=abc", SourceKind.YOUTUBE),
                    target,
                    PipelineConfig(),
                )
        self.assertIsNotNone(acquired.media_path)
        self.assertFalse(metadata.has_captions)
        self.assertIn("caption_warning", metadata.extra)

    def test_word_artifact_is_a_self_contained_docx(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "frame.png"
            image.write_bytes(bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360f8cfc000000301010018dd8db00000000049454e44ae426082"))
            frame = FrameEvidence(1.0, image, "interval")
            metadata = SourceMetadata(SourceRef("lesson.mp4", SourceKind.VIDEO), title="Lesson")
            question = QuestionRecord("q-1", "Which option is correct?", [AnswerOption("A", "First")], "A", "Because it matches.")
            output = root / "extraction.docx"
            write_docx(output, metadata, Transcript([TranscriptSegment(0, 2, "Which option is correct?")]), [frame], [OCRResult(frame, "A. First")], [question], PipelineConfig(), [])
            with zipfile.ZipFile(output) as archive:
                document = archive.read("word/document.xml").decode("utf-8")
                self.assertIn("Which option is correct?", document)
                self.assertIn("word/media/frame.png", archive.namelist())


if __name__ == "__main__":
    unittest.main()
