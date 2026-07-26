"""Built-in workflow presets and safe workflow resolution."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from typing import Any

from ..models.workflows import BlockKind, BlockSpec, WorkflowDefinition


def _block(
    block_id: str,
    kind: BlockKind,
    *depends_on: str,
    config: dict[str, Any] | None = None,
) -> BlockSpec:
    return BlockSpec(block_id, kind, depends_on=list(depends_on), config=config or {})


WORKFLOW_PRESETS: dict[str, WorkflowDefinition] = {
    "exam_study_pack": WorkflowDefinition(
        id="exam_study_pack",
        name="Exam study pack",
        description="Extract speech, on-screen evidence, questions, answers, explanations, and reviewable artifacts.",
        blocks=[
            _block("acquire", BlockKind.ACQUIRE),
            _block("transcript", BlockKind.TRANSCRIPT, "acquire"),
            _block("frames", BlockKind.FRAMES, "acquire"),
            _block("ocr", BlockKind.OCR, "frames"),
            _block("questions", BlockKind.TASK, "transcript", "ocr", config={"task": "questions"}),
            _block("review", BlockKind.REVIEW, "questions"),
            _block("artifacts", BlockKind.ARTIFACT, "questions", "review"),
        ],
    ),
    "lecture_summary": WorkflowDefinition(
        id="lecture_summary",
        name="Lecture summary",
        description="Combine spoken content and visual evidence into a structured lecture summary.",
        blocks=[
            _block("acquire", BlockKind.ACQUIRE),
            _block("transcript", BlockKind.TRANSCRIPT, "acquire"),
            _block("frames", BlockKind.FRAMES, "acquire"),
            _block("ocr", BlockKind.OCR, "frames"),
            _block("summary", BlockKind.TASK, "transcript", "ocr", config={"task": "summary"}),
            _block("artifacts", BlockKind.ARTIFACT, "summary"),
        ],
    ),
    "visual_document": WorkflowDefinition(
        id="visual_document",
        name="Visual document",
        description="Extract pages or keyframes, OCR text, and visual evidence for a readable document.",
        blocks=[
            _block("acquire", BlockKind.ACQUIRE),
            _block("frames", BlockKind.FRAMES, "acquire"),
            _block("ocr", BlockKind.OCR, "frames"),
            _block("visual_notes", BlockKind.TASK, "ocr", config={"task": "visual_notes"}),
            _block("artifacts", BlockKind.ARTIFACT, "visual_notes"),
        ],
    ),
    "transcript_only": WorkflowDefinition(
        id="transcript_only",
        name="Transcript only",
        description="Capture or download speech text and produce a clean text artifact without visual processing.",
        blocks=[
            _block("acquire", BlockKind.ACQUIRE),
            _block("transcript", BlockKind.TRANSCRIPT, "acquire"),
            _block("summary", BlockKind.TASK, "transcript", config={"task": "summary"}),
            _block("artifacts", BlockKind.ARTIFACT, "summary"),
        ],
    ),
}


def canonical_workflow(workflow_id: str) -> str:
    """Normalize a workflow id and reject unknown presets."""
    value = workflow_id.strip().lower().replace("-", "_")
    if value not in WORKFLOW_PRESETS:
        choices = ", ".join(WORKFLOW_PRESETS)
        raise ValueError(f"Unknown workflow '{workflow_id}'. Choose one of: {choices}.")
    return value


def get_workflow(workflow_id: str) -> WorkflowDefinition:
    """Return a detached copy so a request cannot mutate global presets."""
    return deepcopy(WORKFLOW_PRESETS[canonical_workflow(workflow_id)])


def resolve_workflow(
    workflow_id: str,
    overrides: dict[str, dict[str, Any]] | None = None,
) -> WorkflowDefinition:
    """Apply enabled/config overrides while preserving preset order.

    Overrides are intentionally limited to existing blocks. This catches
    misspelled block ids early instead of silently producing a different job.
    """
    workflow = get_workflow(workflow_id)
    for block_id, override in (overrides or {}).items():
        if not isinstance(override, dict):
            raise ValueError(f"Workflow override for '{block_id}' must be an object.")
        try:
            block = workflow.block(block_id)
        except KeyError as exc:
            raise ValueError(str(exc)) from exc
        if "enabled" in override:
            if not isinstance(override["enabled"], bool):
                raise ValueError(f"Workflow override '{block_id}.enabled' must be boolean.")
            block.enabled = override["enabled"]
        if "config" in override:
            if not isinstance(override["config"], dict):
                raise ValueError(f"Workflow override '{block_id}.config' must be an object.")
            block.config.update(deepcopy(override["config"]))
    _validate_dependencies(workflow)
    return workflow


def _validate_dependencies(workflow: WorkflowDefinition) -> None:
    ids = {block.id for block in workflow.blocks}
    for block in workflow.blocks:
        missing = set(block.depends_on) - ids
        if missing:
            raise ValueError(f"Workflow '{workflow.id}' block '{block.id}' depends on missing block(s): {', '.join(sorted(missing))}.")


def workflow_catalog() -> list[dict[str, Any]]:
    """Return UI-safe workflow metadata and block contracts."""
    return [
        {
            "id": workflow.id,
            "name": workflow.name,
            "description": workflow.description,
            "blocks": [
                {
                    "id": block.id,
                    "kind": block.kind.value,
                    "enabled": block.enabled,
                    "depends_on": block.depends_on,
                    "config": block.config,
                }
                for block in workflow.blocks
            ],
        }
        for workflow in WORKFLOW_PRESETS.values()
    ]


def workflow_dict(workflow: WorkflowDefinition) -> dict[str, Any]:
    """Serialize a resolved workflow for manifests and diagnostics."""
    return asdict(workflow)
