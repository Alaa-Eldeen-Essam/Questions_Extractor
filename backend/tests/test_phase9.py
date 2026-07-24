import os
import unittest
from unittest.mock import patch

from exam_extractor.services.llm_service import llm_provider_catalog


class SettingsTests(unittest.TestCase):
    def test_provider_catalog_reports_key_status_without_exposing_values(self) -> None:
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "secret-value"}, clear=False):
            catalog = llm_provider_catalog()
        openrouter = next(item for item in catalog if item["id"] == "openrouter")
        self.assertTrue(openrouter["configured"])
        self.assertNotIn("secret-value", str(openrouter))

    def test_openai_compatible_options_are_available(self) -> None:
        ids = {item["id"] for item in llm_provider_catalog()}
        self.assertTrue({"openai", "openrouter", "huggingface", "ollama"}.issubset(ids))


if __name__ == "__main__":
    unittest.main()
