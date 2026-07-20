"""Verbose, serializable pipeline errors."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    """Stable error codes for logs, API clients, and documentation."""

    INVALID_INPUT = "invalid_input"
    SOURCE_UNAVAILABLE = "source_unavailable"
    CAPTIONS_UNAVAILABLE = "captions_unavailable"
    MEDIA_UNREADABLE = "media_unreadable"
    AUDIO_UNAVAILABLE = "audio_unavailable"
    VIDEO_UNAVAILABLE = "video_unavailable"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    PROVIDER_AUTH = "provider_auth"
    PROVIDER_RATE_LIMIT = "provider_rate_limit"
    PROVIDER_BAD_RESPONSE = "provider_bad_response"
    CONFIGURATION = "configuration"
    STORAGE = "storage"
    OUTPUT_VALIDATION = "output_validation"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


@dataclass
class ExtractorError(Exception):
    """An actionable error that can cross CLI, API, and job boundaries."""

    code: ErrorCode
    message: str
    stage: str | None = None
    retryable: bool = False
    provider: str | None = None
    source: str | None = None
    suggestion: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    error_id: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation without secrets."""
        return {
            "error_id": self.error_id,
            "code": self.code.value,
            "message": self.message,
            "stage": self.stage,
            "retryable": self.retryable,
            "provider": self.provider,
            "source": self.source,
            "suggestion": self.suggestion,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }
