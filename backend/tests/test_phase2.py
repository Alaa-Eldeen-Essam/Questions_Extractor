import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from exam_extractor.config import SpeechConfig
from exam_extractor.errors import ErrorCode, ExtractorError
from exam_extractor.services.speech_service import transcribe_audio


class Phase2Tests(unittest.TestCase):
    def test_unknown_provider_is_actionable(self) -> None:
        with self.assertRaises(ExtractorError) as context:
            transcribe_audio(Path("audio.wav"), SpeechConfig(provider="bad"))
        self.assertEqual(context.exception.code, ErrorCode.CONFIGURATION)

    def test_none_provider_is_dependency_free(self) -> None:
        result = transcribe_audio(Path("audio.wav"), SpeechConfig(provider="none"))
        self.assertEqual(result.source, "none")
        self.assertEqual(result.segments, [])

    def test_remote_provider_normalizes_text(self) -> None:
        response = type("Response", (), {"read": lambda self: b'{"text":"hello world"}'})()
        with tempfile.TemporaryDirectory() as directory:
            audio = Path(directory) / "audio.wav"
            audio.write_bytes(b"RIFF")
            with patch("exam_extractor.services.speech_service.request.urlopen", return_value=response):
                result = transcribe_audio(
                    audio,
                    SpeechConfig(provider="openai_compatible", remote_base_url="http://speech"),
                )
        self.assertEqual(result.segments[0].text, "hello world")
        self.assertEqual(result.source, "openai_compatible")


if __name__ == "__main__":
    unittest.main()
