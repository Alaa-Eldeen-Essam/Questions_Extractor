import unittest
from pathlib import Path
from unittest.mock import patch

from exam_extractor.config import PipelineConfig
from exam_extractor.models.frames import FrameEvidence, OCRResult
from exam_extractor.models.transcripts import Transcript, TranscriptSegment
from exam_extractor.services.task_service import execute_task, resolve_task_kind


class TaskServiceTests(unittest.TestCase):
    def test_workflow_selects_deterministic_summary_without_an_llm(self) -> None:
        config = PipelineConfig(workflow_id="lecture_summary")
        transcript = Transcript([TranscriptSegment(0.0, 4.0, "The first principle is evidence.")], "en", "captions")
        result = execute_task(transcript, [], config)
        self.assertEqual(resolve_task_kind(config), "summary")
        self.assertEqual(result.kind, "summary")
        self.assertIn("first principle", result.content)
        self.assertFalse(result.llm_used)

    def test_visual_notes_keep_frame_and_ocr_evidence(self) -> None:
        config = PipelineConfig(workflow_id="visual_document")
        frame = FrameEvidence(12.5, Path("slide.jpg"), "interval")
        result = execute_task(Transcript(), [OCRResult(frame, "Important table", 0.91)], config)
        self.assertEqual(result.kind, "visual_notes")
        self.assertIn("Important table", result.content)
        self.assertEqual(result.items[0]["frame"], "slide.jpg")
        self.assertEqual(result.evidence[0]["kind"], "ocr")

    def test_custom_task_requires_instruction_and_an_llm(self) -> None:
        config = PipelineConfig()
        config.task.kind = "custom"
        with self.assertRaisesRegex(Exception, "custom task requires task.instruction"):
            execute_task(Transcript(), [], config)

        config.task.instruction = "Create a glossary."
        with self.assertRaisesRegex(Exception, "require an enabled LLM"):
            execute_task(Transcript(), [], config)

    def test_enabled_llm_can_enrich_a_builtin_task(self) -> None:
        config = PipelineConfig(workflow_id="lecture_summary")
        config.llm.enabled = True
        config.llm.provider = "openai_compatible"
        config.llm.model = "test-model"
        config.llm.base_url = "http://example.test/v1"
        with patch("exam_extractor.services.task_service.generate", return_value={"summary": "grounded"}):
            result = execute_task(Transcript([TranscriptSegment(0, 1, "Evidence")]), [], config)
        self.assertEqual(result.content, {"summary": "grounded"})
        self.assertTrue(result.llm_used)


if __name__ == "__main__":
    unittest.main()
