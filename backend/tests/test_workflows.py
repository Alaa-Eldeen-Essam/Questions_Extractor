import json
import unittest

from exam_extractor.config import PipelineConfig
from exam_extractor.pipeline import _job_id
from exam_extractor.services.workflows import (
    block_enabled,
    canonical_workflow,
    resolve_workflow,
    workflow_catalog,
)


class WorkflowTests(unittest.TestCase):
    def test_catalog_exposes_general_presets_and_dependencies(self) -> None:
        catalog = workflow_catalog()
        ids = [item["id"] for item in catalog]
        self.assertEqual(
            ids,
            ["exam_study_pack", "lecture_summary", "visual_document", "transcript_only"],
        )
        exam = catalog[0]
        questions = next(item for item in exam["blocks"] if item["id"] == "questions")
        self.assertEqual(questions["config"]["task"], "questions")
        self.assertEqual(questions["depends_on"], ["transcript", "ocr"])

    def test_overrides_are_scoped_to_existing_blocks(self) -> None:
        workflow = resolve_workflow(
            "exam-study-pack",
            {"ocr": {"enabled": False, "config": {"mode": "keyframes"}}},
        )
        ocr = workflow.block("ocr")
        self.assertFalse(ocr.enabled)
        self.assertEqual(ocr.config["mode"], "keyframes")
        self.assertEqual(workflow.block("frames").enabled, True)

    def test_invalid_workflow_and_block_are_verbose(self) -> None:
        self.assertEqual(canonical_workflow("lecture-summary"), "lecture_summary")
        with self.assertRaisesRegex(ValueError, "Choose one of"):
            resolve_workflow("does-not-exist")
        with self.assertRaisesRegex(ValueError, "no block 'missing'"):
            resolve_workflow("exam_study_pack", {"missing": {"enabled": False}})

    def test_workflow_is_part_of_config_and_job_identity(self) -> None:
        exam = PipelineConfig()
        summary = PipelineConfig(workflow_id="lecture_summary")
        self.assertNotEqual(_job_id("lecture.mp4", exam), _job_id("lecture.mp4", summary))
        json.dumps(summary.workflow_overrides)
        summary.validate()

    def test_block_enabled_reflects_overrides_and_unknown_blocks_are_off(self) -> None:
        overrides = {"ocr": {"enabled": False}}
        self.assertFalse(block_enabled("exam_study_pack", overrides, "ocr"))
        self.assertTrue(block_enabled("exam_study_pack", overrides, "frames"))
        self.assertFalse(block_enabled("exam_study_pack", overrides, "summary"))


if __name__ == "__main__":
    unittest.main()
