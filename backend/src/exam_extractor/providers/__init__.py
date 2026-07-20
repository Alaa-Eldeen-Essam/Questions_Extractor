"""Provider contracts and registration."""

from .base import Capability, LLMProvider, OCRProvider, ProviderInfo, SpeechProvider, VisionProvider
from .registry import ProviderRegistry

__all__ = [
    "Capability",
    "LLMProvider",
    "OCRProvider",
    "ProviderInfo",
    "ProviderRegistry",
    "SpeechProvider",
    "VisionProvider",
]
