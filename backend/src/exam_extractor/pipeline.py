"""Pipeline execution contracts.

The runner implementation is intentionally deferred to Phase 1. Phase 0 only
defines the context and stage boundary that CLI and FastAPI will share.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from .config import PipelineConfig
from .models import Job, StageName, StageResult


@dataclass
class PipelineContext:
    """State shared by stages during one job."""

    job: Job
    config: PipelineConfig
    workspace: Path
    values: dict[str, Any] = field(default_factory=dict)


class PipelineStage(Protocol):
    """One resumable pipeline stage."""

    name: StageName

    async def run(self, context: PipelineContext) -> StageResult:
        """Execute the stage and return produced artifacts and warnings."""
