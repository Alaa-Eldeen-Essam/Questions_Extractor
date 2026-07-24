"""Human-review flags and edits for extracted questions."""

from __future__ import annotations

from typing import Any

from ..config import ReviewConfig
from ..models.questions import AnswerOption, EvidenceKind, EvidenceRef, QuestionRecord


REVIEW_STATUSES = {"pending", "needs_review", "approved", "edited", "rejected"}


def mark_for_review(questions: list[QuestionRecord], config: ReviewConfig) -> list[QuestionRecord]:
    """Mark low-confidence or structurally inconsistent questions for review."""
    for question in questions:
        if not config.enabled or question.review_status in {"approved", "edited", "rejected"}:
            continue
        needs_review = (
            question.confidence is not None and question.confidence < config.threshold
        ) or bool(question.warnings) or not question.answer
        question.review_status = "needs_review" if needs_review else "pending"
    return questions


def review_summary(questions: list[QuestionRecord], threshold: float) -> dict[str, Any]:
    """Return a compact review queue summary suitable for APIs and manifests."""
    counts = {status: 0 for status in sorted(REVIEW_STATUSES)}
    for question in questions:
        counts[question.review_status] = counts.get(question.review_status, 0) + 1
    return {
        "threshold": threshold,
        "total": len(questions),
        "needs_review": counts.get("needs_review", 0),
        "counts": counts,
        "completed": counts.get("needs_review", 0) == 0,
    }


def update_question(question: QuestionRecord, changes: dict[str, Any]) -> QuestionRecord:
    """Apply a validated human edit to one question in place."""
    status = changes.get("status")
    if status is not None:
        status = str(status)
        if status not in REVIEW_STATUSES:
            raise ValueError(f"Unknown review status '{status}'.")
        question.review_status = status
    for field_name in ("prompt", "answer", "explanation", "review_note"):
        if field_name in changes and changes[field_name] is not None:
            value = str(changes[field_name]).strip()
            if field_name == "prompt" and not value:
                raise ValueError("Question prompt cannot be empty.")
            setattr(question, field_name, value or None)
    if "options" in changes and changes["options"] is not None:
        options = changes["options"]
        if not isinstance(options, list):
            raise ValueError("Question options must be a list.")
        question.options = [
            AnswerOption(str(item.get("label", "")).strip(), str(item.get("text", "")).strip())
            for item in options
            if isinstance(item, dict) and str(item.get("text", "")).strip()
        ]
    if status in {"approved", "edited"}:
        question.evidence.append(EvidenceRef(EvidenceKind.HUMAN, "review", question.review_note))
    return question


def review_item(question: QuestionRecord) -> dict[str, Any]:
    """Serialize the editable review fields and evidence references."""
    return {
        "question_id": question.question_id,
        "prompt": question.prompt,
        "options": [{"label": option.label, "text": option.text} for option in question.options],
        "answer": question.answer,
        "explanation": question.explanation,
        "confidence": question.confidence,
        "warnings": question.warnings,
        "review_status": question.review_status,
        "review_note": question.review_note,
        "evidence": [
            {
                "kind": ref.kind.value,
                "locator": ref.locator,
                "excerpt": ref.excerpt,
                "confidence": ref.confidence,
            }
            for ref in question.evidence
        ],
    }
