"""Structured exam-question contracts."""

from dataclasses import dataclass, field
from enum import StrEnum


class EvidenceKind(StrEnum):
    """Where a fact in a question record came from."""

    AUDIO = "audio"
    CAPTION = "caption"
    OCR = "ocr"
    VISUAL = "visual"
    LLM = "llm"
    HUMAN = "human"


@dataclass(frozen=True)
class EvidenceRef:
    """Traceable evidence for an extracted claim."""

    kind: EvidenceKind
    locator: str
    excerpt: str | None = None
    confidence: float | None = None


@dataclass(frozen=True)
class AnswerOption:
    """One answer choice."""

    label: str
    text: str
    evidence: tuple[EvidenceRef, ...] = ()


@dataclass
class QuestionRecord:
    """A normalized question with optional answer and explanation."""

    question_id: str
    prompt: str
    options: list[AnswerOption] = field(default_factory=list)
    answer: str | None = None
    explanation: str | None = None
    visual_description: str | None = None
    evidence: list[EvidenceRef] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    confidence: float | None = None
    review_status: str = "pending"
    review_note: str | None = None
