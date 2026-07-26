import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from exam_extractor.config import PipelineConfig
from exam_extractor.models.sources import AcquiredSource, SourceKind, SourceMetadata, SourceRef
from exam_extractor.models.transcripts import Transcript, TranscriptSegment
from exam_extractor.pipeline import run_pipeline


class GenericTaskPipelineTests(unittest.TestCase):
    def test_lecture_summary_workflow_writes_generic_task_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = SourceRef("lecture.mp4", SourceKind.VIDEO)
            acquired = AcquiredSource(
                source=source,
                root=root / "acquired",
                media_path=root / "media.mp4",
                audio_path=root / "audio.wav",
            )
            metadata = SourceMetadata(source=source, title="Lecture", media_types=["video"])
            config = PipelineConfig(workflow_id="lecture_summary")
            config.output.word = False
            with (
                patch("exam_extractor.pipeline.acquire_source", return_value=(acquired, metadata)),
                patch(
                    "exam_extractor.pipeline.transcribe_audio",
                    return_value=Transcript([TranscriptSegment(0.0, 2.0, "A grounded lecture point.")], "en", "local"),
                ),
                patch("exam_extractor.pipeline.extract_frames", return_value=[]),
            ):
                workspace = run_pipeline("lecture.mp4", config, output_root=root / "outputs")

            manifest = json.loads((workspace / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["stages"]["task"]["status"], "completed")
            self.assertEqual(manifest["task"]["kind"], "summary")
            task = json.loads((workspace / "task.json").read_text(encoding="utf-8"))
            self.assertEqual(task["kind"], "summary")
            self.assertIn("grounded lecture point", task["content"])
            self.assertIn("Lecture summary", (workspace / "extraction.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
