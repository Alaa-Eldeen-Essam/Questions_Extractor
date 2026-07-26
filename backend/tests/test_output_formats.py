import tempfile
import unittest
from pathlib import Path

from exam_extractor.config import PipelineConfig
from exam_extractor.models.sources import SourceKind, SourceMetadata, SourceRef
from exam_extractor.models.tasks import TaskResult
from exam_extractor.models.transcripts import Transcript
from exam_extractor.services.output_service import write_outputs


class OutputFormatTests(unittest.TestCase):
    def test_pdf_and_csv_are_optional_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = PipelineConfig()
            config.output.word = False
            config.output.pdf = True
            config.output.csv = True
            outputs = write_outputs(
                root,
                SourceMetadata(SourceRef("lesson.mp4", SourceKind.VIDEO), title="Lesson"),
                Transcript(),
                [],
                [],
                [],
                config,
                [],
                task_result=TaskResult("summary", "Lesson summary", "Summarize", "A grounded note."),
            )
            names = {path.name for path in outputs}
            self.assertIn("extraction.pdf", names)
            self.assertIn("questions.csv", names)
            self.assertTrue((root / "extraction.pdf").read_bytes().startswith(b"%PDF-1.4"))
            self.assertIn("question_id,prompt", (root / "questions.csv").read_text(encoding="utf-8-sig"))
            self.assertIn("Lesson summary", (root / "extraction.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
