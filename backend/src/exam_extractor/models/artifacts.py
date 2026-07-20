"""Pipeline artifact contracts."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class ArtifactKind(StrEnum):
    """Known persisted pipeline artifacts."""

    METADATA = "metadata"
    MEDIA = "media"
    AUDIO = "audio"
    CAPTIONS = "captions"
    TRANSCRIPT = "transcript"
    FRAME = "frame"
    OCR = "ocr"
    VISUAL_ANALYSIS = "visual_analysis"
    QUESTIONS = "questions"
    MARKDOWN = "markdown"
    JSON = "json"
    LOG = "log"
    ERROR = "error"


@dataclass(frozen=True)
class ArtifactRef:
    """A named file produced by a pipeline stage."""

    kind: ArtifactKind
    path: Path
    media_type: str
    size_bytes: int | None = None
    checksum: str | None = None
