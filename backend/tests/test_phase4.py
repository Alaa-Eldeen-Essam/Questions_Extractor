import unittest
from pathlib import Path

from exam_extractor.config import PipelineConfig
from exam_extractor.models import FrameEvidence, OCRResult, Transcript, TranscriptSegment
from exam_extractor.services.question_service import extract_questions


class Phase4Tests(unittest.TestCase):
    def test_extracts_question_answer_and_explanation(self) -> None:
        transcript = Transcript(
            [
                TranscriptSegment(0, 8, "Which protocol is used for secure web traffic?", source="captions"),
                TranscriptSegment(8, 12, "A HTTP B HTTPS C FTP. The correct answer is B. Explanation: HTTPS encrypts traffic.", source="captions"),
            ],
            "en",
            "captions",
        )
        result = extract_questions(transcript, [], PipelineConfig())
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].answer, "B")
        self.assertEqual(result[0].explanation, "HTTPS encrypts traffic.")

    def test_extracts_multiline_ocr_options(self) -> None:
        frame = FrameEvidence(3, Path("frame.jpg"), "interval")
        ocr = [OCRResult(frame, "What is 2 + 2?\nA. 3\nB. 4\nC. 5", 0.9, "test")]
        result = extract_questions(Transcript([], None, "none"), ocr, PipelineConfig())
        self.assertEqual([(item.label, item.text) for item in result[0].options], [("A", "3"), ("B", "4"), ("C", "5")])


if __name__ == "__main__":
    unittest.main()
