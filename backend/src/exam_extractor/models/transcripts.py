"""Normalized timestamped speech contracts."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TranscriptWord:
    """One optional word-level timestamp from a speech provider."""

    start_seconds: float
    end_seconds: float
    word: str
    probability: float | None = None


@dataclass(frozen=True)
class TranscriptSegment:
    """A small timestamped unit of speech or caption text."""

    start_seconds: float
    end_seconds: float
    text: str
    language: str | None = None
    source: str = "unknown"
    confidence: float | None = None
    words: tuple[TranscriptWord, ...] = ()


@dataclass
class Transcript:
    """Complete normalized transcript."""

    segments: list[TranscriptSegment] = field(default_factory=list)
    language: str | None = None
    source: str = "unknown"
