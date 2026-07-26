"""Named pipeline profiles and their effective settings."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from ..config import PipelineConfig


PROFILE_PRESETS: dict[str, dict[str, dict[str, Any]]] = {
    "fast": {
        "speech": {"model": "tiny.en", "beam_size": 1},
        "frames": {
            "method": "interval",
            "scene_threshold": 0.25,
            "fallback_interval_seconds": 30.0,
            "max_resolution": 480,
        },
        "ocr": {"preprocess": False},
    },
    "balanced": {
        "speech": {"model": "base.en", "beam_size": 5},
        "frames": {
            "method": "scene_change",
            "scene_threshold": 0.15,
            "fallback_interval_seconds": 10.0,
            "max_resolution": 720,
        },
        "ocr": {"preprocess": True},
    },
    "high_accuracy": {
        "speech": {"model": "small.en", "beam_size": 8},
        "frames": {
            "method": "scene_change",
            "scene_threshold": 0.10,
            "fallback_interval_seconds": 5.0,
            "max_resolution": 1080,
        },
        "ocr": {"preprocess": True},
    },
}

PROFILE_ALIASES = {"accurate": "high_accuracy"}


def canonical_profile(name: str) -> str:
    """Return the canonical profile name or raise a useful error."""
    value = name.strip().lower().replace("-", "_")
    value = PROFILE_ALIASES.get(value, value)
    if value not in PROFILE_PRESETS:
        choices = ", ".join(PROFILE_PRESETS)
        raise ValueError(f"Unknown profile '{name}'. Choose one of: {choices}.")
    return value


def apply_profile(config: PipelineConfig, name: str | None = None) -> PipelineConfig:
    """Apply a named preset to a config and return the same config object.

    Profile values are deliberately applied before request/TOML overrides. This
    makes the profile a useful baseline while keeping advanced settings in
    control of the final result.
    """
    selected = canonical_profile(name or config.profile)
    config.profile = selected
    for section_name, values in PROFILE_PRESETS[selected].items():
        section = getattr(config, section_name)
        for field_name, value in values.items():
            setattr(section, field_name, value)
    return config


def profile_catalog() -> list[dict[str, Any]]:
    """Return UI-safe profile metadata without exposing secrets."""
    descriptions = {
        "fast": "Lower CPU, memory, storage, and processing time.",
        "balanced": "Recommended settings for normal exam-prep material.",
        "high_accuracy": "Denser visual sampling and stronger local speech settings.",
    }
    return [
        {
            "id": name,
            "label": name.replace("_", " ").title(),
            "description": descriptions[name],
            "settings": PROFILE_PRESETS[name],
        }
        for name in PROFILE_PRESETS
    ]


def resolved_config(config: PipelineConfig) -> dict[str, Any]:
    """Serialize effective non-secret settings for manifests and diagnostics."""
    value = asdict(config)
    value["output_dir"] = str(config.output_dir)
    value["speech"]["api_key"] = None
    value["llm"]["api_key"] = None
    value["youtube"]["cookie_file"] = None
    return value
