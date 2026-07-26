"""Deterministic and LLM-assisted generic task blocks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TYPE_CHECKING

from ..errors import ErrorCode, ExtractorError
from ..models import EvidenceKind, EvidenceRef, OCRResult, TaskResult, Transcript
from .llm_service import generate
from .question_service import extract_questions
from .serialization import jsonable
from .workflows import resolve_workflow

if TYPE_CHECKING:
    from ..config import PipelineConfig


TASK_KINDS = {"questions", "summary", "visual_notes", "custom", "none"}

DEFAULT_INSTRUCTIONS = {
    "questions": "Extract questions, options, answers, explanations, and source evidence.",
    "summary": "Summarize the material into clear, source-grounded study notes.",
    "visual_notes": "Describe important on-screen text, tables, diagrams, and visual evidence.",
}


def task_block_enabled(config: PipelineConfig) -> bool:
    """Return whether the selected workflow has an enabled task block."""
    workflow = resolve_workflow(config.workflow_id, config.workflow_overrides)
    return any(block.kind.value == "task" and block.enabled for block in workflow.blocks)


def resolve_task_kind(config: PipelineConfig) -> str:
    """Resolve an explicit task kind or inherit it from the workflow preset."""
    explicit = config.task.kind.strip().lower()
    if explicit != "auto":
        return explicit
    workflow = resolve_workflow(config.workflow_id, config.workflow_overrides)
    for block in workflow.blocks:
        if block.kind.value == "task" and block.enabled:
            value = str(block.config.get("task", "custom")).strip().lower()
            if value in TASK_KINDS:
                return value
    return "none"


def execute_task(transcript: Transcript, ocr: list[OCRResult], config: PipelineConfig) -> TaskResult:
    """Run one task against the available multimodal evidence."""
    kind = resolve_task_kind(config)
    instruction = config.task.instruction.strip() or DEFAULT_INSTRUCTIONS.get(kind, "Complete the requested task using only the supplied evidence.")
    title = config.task.title or {
        "questions": "Question bank",
        "summary": "Lecture summary",
        "visual_notes": "Visual notes",
        "custom": "Custom task",
        "none": "No task",
    }.get(kind, "Task result")
    if kind == "none":
        return TaskResult(kind=kind, title=title, instruction=instruction)
    if kind == "questions":
        questions = extract_questions(transcript, ocr, config)
        return TaskResult(
            kind=kind,
            title=title,
            instruction=instruction,
            content=f"Extracted {len(questions)} question(s).",
            items=[jsonable(question) for question in questions[: config.task.max_items]],
            evidence=_evidence(transcript, ocr, config.task.include_evidence),
            questions=questions,
        )
    if kind == "summary":
        result = _deterministic_summary(transcript, ocr, config)
    elif kind == "visual_notes":
        result = _deterministic_visual_notes(ocr, config)
    elif kind == "custom":
        result = _deterministic_custom(transcript, ocr, config)
    else:  # pragma: no cover - config validation catches this
        raise ValueError(f"Unsupported task kind: {kind}")
    if config.llm.enabled:
        result.content = _llm_content(instruction, transcript, ocr, config, result.content)
        result.llm_used = True
    return result


def _deterministic_summary(transcript: Transcript, ocr: list[OCRResult], config: PipelineConfig) -> TaskResult:
    paragraphs = [segment.text.strip() for segment in transcript.segments if segment.text.strip()]
    visual = [result.text.strip() for result in ocr if result.text.strip()]
    content = "\n\n".join(paragraphs[: config.task.max_items]) or "No speech transcript was available."
    if visual:
        content += "\n\nVisual evidence:\n" + "\n".join(f"- {text}" for text in visual[: config.task.max_items])
    return TaskResult(
        kind="summary",
        title=config.task.title or "Lecture summary",
        instruction=config.task.instruction.strip() or DEFAULT_INSTRUCTIONS["summary"],
        content=content,
        items=[{"type": "speech", "text": text} for text in paragraphs[: config.task.max_items]],
        evidence=_evidence(transcript, ocr, config.task.include_evidence),
    )


def _deterministic_visual_notes(ocr: list[OCRResult], config: PipelineConfig) -> TaskResult:
    items = [
        {
            "timestamp_seconds": result.frame.timestamp_seconds,
            "text": result.text,
            "confidence": result.confidence,
            "frame": str(result.frame.path),
        }
        for result in ocr[: config.task.max_items]
        if result.text.strip()
    ]
    content = "\n\n".join(f"[{item['timestamp_seconds']:.3f}s] {item['text']}" for item in items)
    return TaskResult(
        kind="visual_notes",
        title=config.task.title or "Visual notes",
        instruction=config.task.instruction.strip() or DEFAULT_INSTRUCTIONS["visual_notes"],
        content=content or "No OCR text was available from visual evidence.",
        items=items,
        evidence=_evidence(Transcript([]), ocr, config.task.include_evidence),
    )


def _deterministic_custom(transcript: Transcript, ocr: list[OCRResult], config: PipelineConfig) -> TaskResult:
    if not config.task.instruction.strip():
        raise ExtractorError(
            code=ErrorCode.CONFIGURATION,
            message="A custom task requires task.instruction.",
            stage="visual_analysis",
            suggestion="Set task.instruction or choose summary, visual_notes, or questions.",
        )
    if not config.llm.enabled:
        raise ExtractorError(
            code=ErrorCode.CONFIGURATION,
            message="Custom tasks require an enabled LLM provider.",
            stage="visual_analysis",
            suggestion="Enable an LLM or choose a deterministic built-in task.",
        )
    return TaskResult(
        kind="custom",
        title=config.task.title or "Custom task",
        instruction=config.task.instruction,
        content="",
        evidence=_evidence(transcript, ocr, config.task.include_evidence),
    )


def _llm_content(instruction: str, transcript: Transcript, ocr: list[OCRResult], config: PipelineConfig, fallback: Any) -> Any:
    evidence = _evidence_text(transcript, ocr)
    prompt = (
        "You are a careful multimodal study assistant. Follow the user instruction exactly. "
        "Use only the evidence below, distinguish uncertainty, and do not invent facts.\n\n"
        f"Instruction:\n{instruction}\n\nEvidence:\n{evidence}"
    )
    images = [result.frame.path for result in ocr if config.llm.vision_enabled]
    result = generate(prompt, config.llm, images=images)
    return fallback if result is None else result


def _evidence(transcript: Transcript, ocr: list[OCRResult], include: bool) -> list[dict[str, Any]]:
    if not include:
        return []
    refs: list[dict[str, Any]] = []
    for segment in transcript.segments:
        refs.append(jsonable(EvidenceRef(EvidenceKind.AUDIO, f"{segment.start_seconds:.3f}-{segment.end_seconds:.3f}", segment.text)))
    for result in ocr:
        refs.append(jsonable(EvidenceRef(EvidenceKind.OCR, str(result.frame.path), result.text, result.confidence)))
    return refs


def _evidence_text(transcript: Transcript, ocr: list[OCRResult]) -> str:
    lines = [f"[speech {segment.start_seconds:.3f}s] {segment.text}" for segment in transcript.segments]
    lines.extend(f"[ocr {result.frame.timestamp_seconds:.3f}s] {result.text}" for result in ocr)
    return "\n".join(lines) or "(no evidence available)"
