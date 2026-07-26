"""Runtime provider credential and secret-redaction checks."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from exam_extractor.config import LLMConfig, PipelineConfig
from exam_extractor.pipeline import _job_id
from exam_extractor.services.llm_service import generate
from exam_extractor.services.profiles import resolved_config


class RuntimeCredentialTests(unittest.TestCase):
    def test_runtime_key_takes_precedence_over_environment_fallback(self) -> None:
        config = PipelineConfig()
        config.llm.api_key = "runtime-secret"
        config.llm.api_key_env = "TEST_RUNTIME_KEY"
        with patch.dict(os.environ, {"TEST_RUNTIME_KEY": "environment-secret"}):
            self.assertEqual(config.api_key(), "runtime-secret")

    def test_resolved_config_redacts_runtime_keys(self) -> None:
        config = PipelineConfig()
        config.llm.api_key = "runtime-secret"
        config.speech.api_key = "speech-secret"
        payload = resolved_config(config)
        serialized = json.dumps(payload)
        self.assertNotIn("runtime-secret", serialized)
        self.assertNotIn("speech-secret", serialized)
        self.assertIsNone(payload["llm"]["api_key"])
        self.assertIsNone(payload["speech"]["api_key"])

    def test_job_id_does_not_change_with_runtime_secret(self) -> None:
        first = PipelineConfig()
        second = PipelineConfig()
        first.llm.api_key = "first-secret"
        second.llm.api_key = "second-secret"
        self.assertEqual(_job_id("lecture.mp4", first), _job_id("lecture.mp4", second))

    def test_toml_rejects_persisted_api_key(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "unsafe.toml"
            path.write_text('[llm]\napi_key = "persisted-secret"\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "supplied at runtime"):
                PipelineConfig.from_toml(path)

    def test_gemini_runtime_key_is_sent_in_header_not_url(self) -> None:
        response = type(
            "Response",
            (),
            {"read": lambda self: b'{"candidates":[{"content":{"parts":[{"text":"answer"}]}}]}'},
        )()
        captured = {}

        def fake_open(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return response

        config = LLMConfig(enabled=True, provider="gemini", model="gemini-test", api_key="runtime-secret")
        with patch("exam_extractor.services.llm_service.request.urlopen", side_effect=fake_open):
            self.assertEqual(generate("hello", config), "answer")

        request = captured["request"]
        headers = {name.lower(): value for name, value in request.header_items()}
        self.assertEqual(headers["x-goog-api-key"], "runtime-secret")
        self.assertNotIn("runtime-secret", request.full_url)


if __name__ == "__main__":
    unittest.main()
