"""Phase 1 deterministic service checks."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from exam_extractor.config import PipelineConfig
from exam_extractor.models.sources import SourceKind
from exam_extractor.services.captions import parse_caption_file
from exam_extractor.services.source_service import detect_source


class Phase1Tests(unittest.TestCase):
    def test_caption_parser_removes_inline_markup_and_keeps_timing(self) -> None:
        path = Path(__file__).parent / "fixtures" / "sample.vtt"
        transcript = parse_caption_file(path, language="en")
        self.assertEqual(len(transcript.segments), 2)
        self.assertEqual(transcript.segments[0].text, "Hello world.")
        self.assertEqual(transcript.segments[0].start_seconds, 1.0)

    def test_source_detection_supports_phase1_inputs(self) -> None:
        self.assertEqual(detect_source("https://www.youtube.com/watch?v=abc").kind, SourceKind.YOUTUBE)
        self.assertEqual(detect_source("lecture.mp4").kind, SourceKind.VIDEO)
        self.assertEqual(detect_source("lecture.wav").kind, SourceKind.AUDIO)
        self.assertEqual(detect_source("notes.pdf").kind, SourceKind.PDF)

    def test_config_example_is_loadable(self) -> None:
        path = Path(__file__).parents[2] / "examples" / "config.default.toml"
        config = PipelineConfig.from_toml(path)
        self.assertEqual(config.profile, "balanced")
        self.assertFalse(config.llm.enabled)

    def test_caption_json_is_serializable(self) -> None:
        path = Path(__file__).parent / "fixtures" / "sample.vtt"
        payload = parse_caption_file(path)
        json.dumps({"segments": [segment.__dict__ for segment in payload.segments]})


if __name__ == "__main__":
    unittest.main()
