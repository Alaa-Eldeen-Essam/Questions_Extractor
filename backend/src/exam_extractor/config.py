"""Configuration with safe defaults and TOML overrides."""

from dataclasses import dataclass, field
from pathlib import Path
import os
import tomllib
from typing import Any


@dataclass
class SpeechConfig:
    provider: str = "auto"
    model: str = "base.en"
    language: str | None = None
    device: str = "auto"
    compute_type: str = "auto"
    translate: bool = False
    beam_size: int = 5
    vad_filter: bool = True
    remote_base_url: str | None = None
    remote_api_key_env: str | None = None
    timeout_seconds: float = 120.0


@dataclass
class FrameConfig:
    method: str = "scene_change"
    scene_threshold: float = 0.15
    fallback_interval_seconds: float = 10.0
    max_resolution: int = 720


@dataclass
class OCRConfig:
    provider: str = "tesseract"
    preprocess: bool = True
    confidence_threshold: float = 0.60
    language: str = "eng"


@dataclass
class LLMConfig:
    enabled: bool = False
    provider: str = "none"
    model: str | None = None
    vision_model: str | None = None
    base_url: str | None = None
    api_key_env: str | None = None
    temperature: float = 0.1
    max_tokens: int = 2048
    timeout_seconds: float = 120.0
    retry_count: int = 1
    vision_enabled: bool = True
    output_language: str = "same"


@dataclass
class OutputConfig:
    markdown: bool = True
    json: bool = True
    transcript: bool = False
    word: bool = True
    pdf: bool = False
    csv: bool = False
    include_frame_links: bool = True


@dataclass
class PrivacyConfig:
    """Controls source visibility and future retention jobs."""

    redact_source: bool = False
    retention_days: int | None = None


@dataclass
class ReviewConfig:
    """Controls automatic review flags for extracted questions."""

    enabled: bool = True
    threshold: float = 0.70
    gate_before_artifacts: bool = False


@dataclass
class TaskConfig:
    """Controls the generic instruction-driven task block."""

    kind: str = "auto"
    instruction: str = ""
    title: str | None = None
    max_items: int = 100
    include_evidence: bool = True


@dataclass
class PipelineConfig:
    workflow_id: str = "exam_study_pack"
    workflow_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)
    profile: str = "balanced"
    output_dir: Path = Path("outputs")
    speech: SpeechConfig = field(default_factory=SpeechConfig)
    frames: FrameConfig = field(default_factory=FrameConfig)
    ocr: OCRConfig = field(default_factory=OCRConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    task: TaskConfig = field(default_factory=TaskConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    privacy: PrivacyConfig = field(default_factory=PrivacyConfig)
    review: ReviewConfig = field(default_factory=ReviewConfig)

    @classmethod
    def from_toml(cls, path: Path) -> "PipelineConfig":
        """Load a TOML configuration over the safe defaults."""
        with path.open("rb") as handle:
            data: dict[str, Any] = tomllib.load(handle)
        config = cls()
        workflow_data = data.get("workflow", {})
        if isinstance(workflow_data, str):
            config.workflow_id = workflow_data
        elif isinstance(workflow_data, dict):
            config.workflow_id = workflow_data.get("id", config.workflow_id)
            config.workflow_overrides = workflow_data.get("blocks", config.workflow_overrides)
        elif workflow_data:
            raise ValueError("workflow must be a string or a TOML table")
        config.workflow_id = data.get("workflow_id", config.workflow_id)
        config.workflow_overrides = data.get("workflow_overrides", config.workflow_overrides)
        config.profile = data.get("profile", config.profile)
        from .services.profiles import apply_profile

        apply_profile(config)
        config.output_dir = Path(data.get("output_dir", config.output_dir))
        for section_name, target in (
            ("speech", config.speech),
            ("frames", config.frames),
            ("ocr", config.ocr),
            ("llm", config.llm),
            ("task", config.task),
            ("output", config.output),
            ("privacy", config.privacy),
            ("review", config.review),
        ):
            for key, value in data.get(section_name, {}).items():
                if not hasattr(target, key):
                    raise ValueError(f"Unknown configuration key: {section_name}.{key}")
                setattr(target, key, value)
        config.validate()
        return config

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PipelineConfig":
        """Rebuild a config from a redacted, resolved manifest configuration."""
        config = cls()
        config.workflow_id = data.get("workflow_id", config.workflow_id)
        config.workflow_overrides = data.get("workflow_overrides", config.workflow_overrides)
        config.profile = data.get("profile", config.profile)
        config.output_dir = Path(data.get("output_dir", config.output_dir))
        for section_name, target in (
            ("speech", config.speech),
            ("frames", config.frames),
            ("ocr", config.ocr),
            ("llm", config.llm),
            ("task", config.task),
            ("output", config.output),
            ("privacy", config.privacy),
            ("review", config.review),
        ):
            for key, value in data.get(section_name, {}).items():
                if hasattr(target, key):
                    setattr(target, key, value)
        config.validate()
        return config

    def validate(self) -> None:
        """Validate cross-platform configuration values."""
        from .services.workflows import resolve_workflow

        resolve_workflow(self.workflow_id, self.workflow_overrides)
        if not self.profile:
            raise ValueError("profile cannot be empty")
        if self.speech.language and self.speech.language.lower() == "auto":
            self.speech.language = None
        if not 0 <= self.frames.scene_threshold <= 1:
            raise ValueError("frames.scene_threshold must be between 0 and 1")
        if self.frames.fallback_interval_seconds <= 0:
            raise ValueError("frames.fallback_interval_seconds must be positive")
        if self.speech.beam_size <= 0:
            raise ValueError("speech.beam_size must be positive")
        if self.speech.timeout_seconds <= 0:
            raise ValueError("speech.timeout_seconds must be positive")
        if not 0 <= self.ocr.confidence_threshold <= 1:
            raise ValueError("ocr.confidence_threshold must be between 0 and 1")
        if not 0 <= self.review.threshold <= 1:
            raise ValueError("review.threshold must be between 0 and 1")
        if not 0 <= self.llm.temperature <= 2:
            raise ValueError("llm.temperature must be between 0 and 2")
        if self.llm.max_tokens <= 0:
            raise ValueError("llm.max_tokens must be positive")
        if self.llm.timeout_seconds <= 0:
            raise ValueError("llm.timeout_seconds must be positive")
        if self.llm.retry_count < 0:
            raise ValueError("llm.retry_count cannot be negative")
        if self.task.kind.strip().lower() not in {"auto", "questions", "summary", "visual_notes", "custom", "none"}:
            raise ValueError("task.kind must be auto, questions, summary, visual_notes, custom, or none")
        if self.task.max_items <= 0:
            raise ValueError("task.max_items must be positive")
        if self.speech.language is not None and not self.speech.language.strip():
            raise ValueError("speech.language must be a language code or null for auto detection")
        if not self.llm.output_language.strip():
            raise ValueError("llm.output_language cannot be empty")
        if self.privacy.retention_days is not None and self.privacy.retention_days <= 0:
            raise ValueError("privacy.retention_days must be positive when set")
        if self.llm.enabled and self.llm.provider == "none":
            raise ValueError("llm.provider cannot be 'none' when llm.enabled is true")

    def api_key(self) -> str | None:
        """Resolve the configured API key without storing it in the config."""
        return os.environ.get(self.llm.api_key_env) if self.llm.api_key_env else None
