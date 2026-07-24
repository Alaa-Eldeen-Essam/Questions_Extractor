import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from exam_extractor.config import PipelineConfig
from exam_extractor.models import SourceKind
from exam_extractor.services.pdf_service import extract_pdf_pages
from exam_extractor.services.source_service import detect_source


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


if __name__ == "__main__":
    unittest.main()
