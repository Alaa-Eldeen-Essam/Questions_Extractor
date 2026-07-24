import unittest

from exam_extractor.config import PipelineConfig
from exam_extractor.services.profiles import apply_profile, canonical_profile, profile_catalog


class ProfileTests(unittest.TestCase):
    def test_profiles_change_effective_settings(self) -> None:
        fast = apply_profile(PipelineConfig(), "fast")
        balanced = apply_profile(PipelineConfig(), "balanced")
        accurate = apply_profile(PipelineConfig(), "high_accuracy")

        self.assertEqual(fast.speech.model, "tiny.en")
        self.assertEqual(fast.frames.max_resolution, 480)
        self.assertEqual(balanced.frames.max_resolution, 720)
        self.assertEqual(accurate.speech.model, "small.en")
        self.assertEqual(accurate.frames.fallback_interval_seconds, 5.0)

    def test_profile_alias_and_invalid_name(self) -> None:
        self.assertEqual(canonical_profile("accurate"), "high_accuracy")
        with self.assertRaises(ValueError):
            apply_profile(PipelineConfig(), "unknown")

    def test_catalog_is_safe_for_ui(self) -> None:
        catalog = profile_catalog()
        self.assertEqual([item["id"] for item in catalog], ["fast", "balanced", "high_accuracy"])
        self.assertIn("max_resolution", catalog[0]["settings"]["frames"])


if __name__ == "__main__":
    unittest.main()
