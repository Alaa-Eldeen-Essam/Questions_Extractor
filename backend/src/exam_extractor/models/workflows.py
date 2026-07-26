"""Serializable contracts for reusable multimodal workflows."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class BlockKind(StrEnum):
    """Broad capability represented by a workflow block."""

    ACQUIRE = "acquire"
    TRANSCRIPT = "transcript"
    FRAMES = "frames"
    OCR = "ocr"
    TASK = "task"
    REVIEW = "review"
    ARTIFACT = "artifact"


@dataclass
class BlockSpec:
    """One independently configurable unit in a workflow definition."""

    id: str
    kind: BlockKind
    enabled: bool = True
    depends_on: list[str] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowDefinition:
    """A named, ordered recipe for turning an input into useful outputs."""

    id: str
    name: str
    description: str
    blocks: list[BlockSpec] = field(default_factory=list)

    def block(self, block_id: str) -> BlockSpec:
        """Return a block by id or raise a useful configuration error."""
        for block in self.blocks:
            if block.id == block_id:
                return block
        raise KeyError(f"Workflow '{self.id}' has no block '{block_id}'.")
