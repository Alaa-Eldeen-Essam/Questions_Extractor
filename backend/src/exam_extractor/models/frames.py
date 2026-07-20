"""Visual evidence and OCR contracts."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class FrameEvidence:
    """A retained frame that can be reviewed by a human or vision model."""

    timestamp_seconds: float
    path: Path
    method: str
    width: int | None = None
    height: int | None = None
    scene_score: float | None = None


@dataclass
class OCRResult:
    """OCR text associated with one frame."""

    frame: FrameEvidence
    text: str
    confidence: float | None = None
    engine: str = "unknown"
    warnings: list[str] = field(default_factory=list)
