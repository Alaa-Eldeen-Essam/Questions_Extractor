import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from exam_extractor.config import PipelineConfig
from exam_extractor.models.frames import FrameEvidence
from exam_extractor.models.sources import AcquiredSource, SourceKind, SourceMetadata, SourceRef
from exam_extractor.pipeline import run_pipeline


class WorkflowExecutionTests(unittest.TestCase):
    def test_visual_blocks_run_even_when_transcript_is_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = SourceRef("lecture.mp4", SourceKind.VIDEO)
            acquired = AcquiredSource(source=source, root=root / "acquired", media_path=root / "media.mp4")
            metadata = SourceMetadata(source=source, title="Lecture", media_types=["video"])
            frame = FrameEvidence(timestamp_seconds=1.0, path=root / "frame.jpg", method="test")
            config = PipelineConfig(
                workflow_overrides={
                    "transcript": {"enabled": False},
                    "questions": {"enabled": False},
                    "review": {"enabled": False},
                    "artifacts": {"enabled": False},
                }
            )
            with (
                patch("exam_extractor.pipeline.acquire_source", return_value=(acquired, metadata)),
                patch("exam_extractor.pipeline.extract_frames", return_value=[frame]),
                patch("exam_extractor.pipeline.extract_ocr", return_value=[]),
            ):
                workspace = run_pipeline("lecture.mp4", config, output_root=root / "outputs")

            manifest = json.loads((workspace / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["stages"]["speech"]["status"], "skipped")
            self.assertEqual(manifest["stages"]["frames"]["status"], "completed")
            self.assertEqual(manifest["stages"]["ocr"]["status"], "completed")
            self.assertEqual(len(json.loads((workspace / "frames.json").read_text())), 1)

    def test_disabled_blocks_are_recorded_and_downstream_artifacts_stay_safe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = SourceRef("lecture.mp4", SourceKind.VIDEO)
            acquired = AcquiredSource(source=source, root=root / "acquired", media_path=root / "media.mp4")
            metadata = SourceMetadata(source=source, title="Lecture", media_types=["video"])
            config = PipelineConfig(
                workflow_overrides={
                    "transcript": {"enabled": False},
                    "frames": {"enabled": False},
                    "ocr": {"enabled": False},
                    "questions": {"enabled": False},
                    "review": {"enabled": False},
                    "artifacts": {"enabled": False},
                }
            )
            with patch("exam_extractor.pipeline.acquire_source", return_value=(acquired, metadata)):
                workspace = run_pipeline("lecture.mp4", config, output_root=root / "outputs")

            manifest = json.loads((workspace / "manifest.json").read_text(encoding="utf-8"))
            statuses = manifest["stages"]
            self.assertEqual(statuses["speech"]["status"], "skipped")
            self.assertEqual(statuses["frames"]["status"], "skipped")
            self.assertEqual(statuses["ocr"]["status"], "skipped")
            self.assertEqual(statuses["questions"]["status"], "skipped")
            self.assertEqual(statuses["review"]["status"], "skipped")
            self.assertEqual(statuses["render"]["status"], "skipped")
            self.assertEqual(json.loads((workspace / "transcript.json").read_text()), {"segments": [], "language": None, "source": "disabled"})
            self.assertEqual(json.loads((workspace / "frames.json").read_text()), [])
            self.assertEqual(json.loads((workspace / "ocr.json").read_text()), [])
            self.assertEqual(json.loads((workspace / "questions.json").read_text()), [])
            self.assertEqual(manifest["outputs"], [])


if __name__ == "__main__":
    unittest.main()
