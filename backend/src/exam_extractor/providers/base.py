"""Provider protocols.

Providers are intentionally small. Implementations can be built into this
repository or installed as optional plugins without changing the pipeline
stages that consume them.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, Sequence

from ..models.frames import OCRResult
from ..models.sources import AcquiredSource
from ..models.transcripts import Transcript


class Capability(StrEnum):
    """Capabilities that a provider may advertise."""

    TEXT = "text"
    VISION = "vision"
    AUDIO = "audio"
    STRUCTURED_OUTPUT = "structured_output"
    BATCH = "batch"
    LOCAL = "local"


@dataclass(frozen=True)
class ProviderInfo:
    """Human-readable provider metadata for the CLI and frontend."""

    name: str
    display_name: str
    capabilities: frozenset[Capability] = frozenset()
    model: str | None = None
    version: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class SourceProvider(Protocol):
    """Provider that inspects and acquires a source."""

    info: ProviderInfo

    def can_handle(self, value: str | Path) -> bool:
        """Return whether this provider can handle the input."""

    async def inspect(self, value: str | Path) -> Any:
        """Inspect a source without downloading more than necessary."""

    async def acquire(self, value: str | Path, target: Path) -> AcquiredSource:
        """Acquire source files into ``target``."""


class SpeechProvider(Protocol):
    """Provider that creates normalized timestamped speech."""

    info: ProviderInfo

    async def transcribe(
        self,
        source: Path,
        *,
        language: str | None = None,
    ) -> Transcript:
        """Transcribe audio or video into normalized segments."""


class OCRProvider(Protocol):
    """Provider that reads text from a frame."""

    info: ProviderInfo

    async def extract(self, frame: Path) -> OCRResult:
        """Extract visible text from one frame."""


class VisionProvider(Protocol):
    """Provider that interprets visual content beyond OCR."""

    info: ProviderInfo

    async def describe(
        self,
        frames: Sequence[Path],
        *,
        instruction: str,
    ) -> str:
        """Describe diagrams, tables, layouts, or other visual evidence."""


class LLMProvider(Protocol):
    """Text/vision model provider used for optional organization and validation."""

    info: ProviderInfo

    async def generate(
        self,
        prompt: str,
        *,
        images: Sequence[Path] = (),
        schema: dict[str, Any] | None = None,
    ) -> Any:
        """Generate text or structured output from text and optional images."""
