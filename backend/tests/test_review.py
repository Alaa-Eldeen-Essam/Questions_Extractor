import tempfile
import unittest

from exam_extractor.config import ReviewConfig
from exam_extractor.models.questions import QuestionRecord
from exam_extractor.services.review_service import mark_for_review, review_summary, update_question


class ReviewTests(unittest.TestCase):
    def test_low_confidence_questions_enter_review_queue(self) -> None:
        questions = [
            QuestionRecord("q-1", "Which answer?", confidence=0.45),
            QuestionRecord("q-2", "Which answer?", answer="A", confidence=0.90),
        ]
        mark_for_review(questions, ReviewConfig())
        self.assertEqual(questions[0].review_status, "needs_review")
        self.assertEqual(questions[1].review_status, "pending")
        self.assertEqual(review_summary(questions, 0.70)["needs_review"], 1)

    def test_human_edit_and_approval_are_traceable(self) -> None:
        question = QuestionRecord("q-1", "Old prompt", confidence=0.4)
        update_question(
            question,
            {
                "prompt": "New prompt",
                "options": [{"label": "A", "text": "First"}],
                "answer": "A",
                "status": "edited",
                "review_note": "Verified against the frame.",
            },
        )
        self.assertEqual(question.prompt, "New prompt")
        self.assertEqual(question.options[0].text, "First")
        self.assertEqual(question.review_status, "edited")
        self.assertEqual(question.evidence[-1].kind.value, "human")


if __name__ == "__main__":
    unittest.main()
