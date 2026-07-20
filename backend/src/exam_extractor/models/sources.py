"""Source and acquisition contracts.

These models deliberately describe media without assuming that the source is
YouTube. A source adapter can therefore support URLs, local media, PDFs, and
future lecture providers without changing downstream stages.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class SourceKind(StrEnum):
    """Supported source families."""

    YOUTUBE = "youtube"
    VIDEO = "video"
    AUDIO = "audio"
    PDF = "pdf"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SourceRef:
    """User-supplied source reference."""

    value: str
    kind: SourceKind = SourceKind.UNKNOWN
    label: str | None = None


@dataclass
class SourceMetadata:
    """Metadata discovered before expensive processing begins."""

    source: SourceRef
    title: str | None = None
    duration_seconds: float | None = None
    language: str | None = None
    media_types: list[str] = field(default_factory=list)
    has_captions: bool = False
    caption_languages: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AcquiredSource:
    """Local files produced by a source adapter."""

    source: SourceRef
    root: Path
    media_path: Path | None = None
    audio_path: Path | None = None
    caption_paths: tuple[Path, ...] = ()
    metadata_path: Path | None = None
