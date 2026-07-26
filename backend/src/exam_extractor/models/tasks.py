"""Generic task-block result contracts."""

from dataclasses import dataclass, field
from typing import Any

from .questions import QuestionRecord


@dataclass
class TaskResult:
    """Structured output from a task block, independent of its renderer."""

    kind: str
    title: str
    instruction: str
    content: Any = ""
    items: list[Any] = field(default_factory=list)
    evidence: list[Any] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    questions: list[QuestionRecord] = field(default_factory=list)
    llm_used: bool = False
