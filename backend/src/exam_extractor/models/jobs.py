"""Job and stage lifecycle contracts."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum

from .artifacts import ArtifactRef
from .sources import SourceRef


class JobStatus(StrEnum):
    """Top-level job state."""

    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StageName(StrEnum):
    """Stable stage identifiers used in logs and API progress events."""

    VALIDATE = "validate"
    ACQUIRE = "acquire"
    SPEECH = "speech"
    FRAMES = "frames"
    OCR = "ocr"
    VISUAL_ANALYSIS = "visual_analysis"
    QUESTIONS = "questions"
    TASK = "task"
    REVIEW = "review"
    VALIDATE_OUTPUT = "validate_output"
    RENDER = "render"


class StageStatus(StrEnum):
    """Stage-level state."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StageResult:
    """Result returned by one pipeline stage."""

    stage: StageName
    status: StageStatus
    artifacts: list[ArtifactRef] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error_ids: list[str] = field(default_factory=list)


@dataclass
class Job:
    """Persistable job state."""

    job_id: str
    source: SourceRef
    status: JobStatus = JobStatus.CREATED
    stages: dict[StageName, StageStatus] = field(default_factory=dict)
    artifacts: list[ArtifactRef] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    warnings: list[str] = field(default_factory=list)
