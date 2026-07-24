import unittest
from unittest.mock import patch

from exam_extractor.config import LLMConfig
from exam_extractor.errors import ErrorCode, ExtractorError
from exam_extractor.services.llm_service import available_llm_providers, generate


class Phase3Tests(unittest.TestCase):
    def test_noop_requires_no_key(self) -> None:
        self.assertIsNone(generate("hello", LLMConfig()))

    def test_provider_discovery_is_stable(self) -> None:
        self.assertEqual(available_llm_providers(), ("none", "openai_compatible", "gemini", "ollama"))

    def test_openai_compatible_response(self) -> None:
        response = type("Response", (), {"read": lambda self: b'{"choices":[{"message":{"content":"answer"}}]}'})()
        config = LLMConfig(enabled=True, provider="openai_compatible", model="test", base_url="http://llm")
        with patch("exam_extractor.services.llm_service.request.urlopen", return_value=response):
            self.assertEqual(generate("question", config), "answer")

    def test_unknown_provider_is_actionable(self) -> None:
        with self.assertRaises(ExtractorError) as context:
            generate("hello", LLMConfig(enabled=True, provider="bad"))
        self.assertEqual(context.exception.code, ErrorCode.CONFIGURATION)


if __name__ == "__main__":
    unittest.main()
