"""Phase 0 contract checks; intentionally dependency-free."""

import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from exam_extractor.config import PipelineConfig
from exam_extractor.errors import ErrorCode, ExtractorError
from exam_extractor.models import SourceKind, SourceRef
from exam_extractor.providers.registry import ProviderRegistry


class Phase0Tests(unittest.TestCase):
    def test_default_config_validates(self) -> None:
        config = PipelineConfig()
        config.validate()
        self.assertEqual(config.ocr.provider, "tesseract")
        self.assertFalse(config.llm.enabled)

    def test_toml_config_overrides_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_text(
                '[llm]\nenabled = true\nprovider = "ollama"\nmodel = "llama"\n',
                encoding="utf-8",
            )
            config = PipelineConfig.from_toml(path)
        self.assertTrue(config.llm.enabled)
        self.assertEqual(config.llm.provider, "ollama")

    def test_error_is_json_safe_and_actionable(self) -> None:
        error = ExtractorError(
            code=ErrorCode.PROVIDER_RATE_LIMIT,
            message="The provider rate limit was reached.",
            stage="llm",
            retryable=True,
            suggestion="Retry later or select another provider.",
        )
        payload = error.to_dict()
        json.dumps(payload)
        self.assertEqual(payload["code"], "provider_rate_limit")
        self.assertTrue(payload["retryable"])

    def test_registry_resolves_providers(self) -> None:
        registry = ProviderRegistry()
        marker = object()
        registry.register("llm", "none", marker)
        self.assertIs(registry.get("llm", "none"), marker)
        self.assertEqual(registry.names("llm"), ("none",))

    def test_source_contract_is_cross_platform(self) -> None:
        source = SourceRef("lecture.mp4", SourceKind.VIDEO)
        self.assertEqual(source.kind, SourceKind.VIDEO)


if __name__ == "__main__":
    unittest.main()
