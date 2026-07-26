import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from exam_extractor.config import PipelineConfig, ReviewConfig
from exam_extractor.models import AnswerOption, EvidenceKind, EvidenceRef, QuestionRecord, TaskResult
from exam_extractor.models.sources import AcquiredSource, SourceKind, SourceMetadata, SourceRef
from exam_extractor.pipeline import run_pipeline
from exam_extractor.services.output_service import write_json


class ReviewGateTests(unittest.TestCase):
    def _config(self) -> PipelineConfig:
        return PipelineConfig(
            workflow_overrides={
                "transcript": {"enabled": False},
                "frames": {"enabled": False},
                "ocr": {"enabled": False},
                "review": {"enabled": True},
                "artifacts": {"enabled": True},
            },
            review=ReviewConfig(
                enabled=True,
                threshold=0.70,
                gate_before_artifacts=True,
            ),
        )

    def test_gated_job_waits_and_resumes_after_review_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = SourceRef("lecture.mp3", SourceKind.AUDIO)
            acquired = AcquiredSource(source=source, root=root / "acquired", media_path=root / "media.mp3")
            metadata = SourceMetadata(source=source, title="Lecture", media_types=["audio"])
            question = QuestionRecord(
                question_id="q-0001",
                prompt="What is the key idea?",
                options=[AnswerOption("A", "Evidence")],
                answer=None,
                evidence=[EvidenceRef(EvidenceKind.AUDIO, "0.000-1.000", "What is the key idea?")],
                confidence=0.40,
                review_status="needs_review",
            )
            result = TaskResult(kind="questions", title="Question bank", instruction="", questions=[question])
            config = self._config()
            with (
                patch("exam_extractor.pipeline.acquire_source", return_value=(acquired, metadata)),
                patch("exam_extractor.pipeline.execute_task", return_value=result),
            ):
                workspace = run_pipeline("lecture.mp3", config, output_root=root / "outputs")

            manifest_path = workspace / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "awaiting_review")
            self.assertFalse((workspace / "extraction.md").exists())
            self.assertEqual(manifest["stages"]["render"]["status"] if "render" in manifest["stages"] else None, None)

            questions = json.loads((workspace / "questions.json").read_text(encoding="utf-8"))
            questions[0]["review_status"] = "approved"
            questions[0]["review_note"] = "Checked by reviewer."
            write_json(workspace / "questions.json", questions)
            original_review = json.loads((workspace / "review.json").read_text(encoding="utf-8"))
            summary = original_review
            summary["needs_review"] = 0
            summary["completed"] = True
            summary["counts"]["needs_review"] = 0
            summary["counts"]["approved"] = 1
            review = {"summary": summary, "items": [{"question_id": "q-0001", "review_status": "approved"}]}
            write_json(workspace / "review.json", review)
            manifest["review"] = summary
            write_json(manifest_path, manifest)

            with (
                patch("exam_extractor.pipeline.acquire_source", return_value=(acquired, metadata)),
                patch("exam_extractor.pipeline.load_acquired", return_value=acquired),
                patch("exam_extractor.pipeline._load_metadata", return_value=metadata),
            ):
                resumed = run_pipeline("lecture.mp3", config, output_root=root / "outputs")
            final = json.loads((resumed / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(final["status"], "completed")
            self.assertTrue((resumed / "extraction.md").exists())
            self.assertEqual(final["stages"]["render"]["status"], "completed")


if __name__ == "__main__":
    unittest.main()
