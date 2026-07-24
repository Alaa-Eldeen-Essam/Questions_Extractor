"""Question-bank extraction from normalized speech and OCR evidence."""

import re
from pathlib import Path
from typing import Any

from ..config import PipelineConfig
from ..models import AnswerOption, EvidenceKind, EvidenceRef, OCRResult, QuestionRecord, Transcript
from .llm_service import generate


QUESTION = re.compile(r"\b(?:what|which|who|where|when|why|how|select|choose|identify|according to)\b[^?\n]{5,}\?", re.I)
OPTION = re.compile(r"^\s*([A-Ha-h]|[1-9])\s*[.)\-:]\s*(.+?)\s*$")
ANSWER = re.compile(r"\b(?:correct\s+answer|answer|correct\s+option)\s*(?:is|:|-)?\s*(?:option\s*)?([A-Ha-h]|[1-9])\b(?:\s*[-:：]\s*(.*))?", re.I)
EXPLANATION = re.compile(r"\b(?:explanation|because|the reason|this is correct)\s*[:\-]?\s*(.+)", re.I)


def extract_questions(transcript: Transcript, ocr: list[OCRResult], config: PipelineConfig) -> list[QuestionRecord]:
    """Extract study questions and optionally enrich them with an LLM."""
    records: list[QuestionRecord] = []
    evidence_blocks: list[tuple[str, EvidenceRef, Path | None]] = []
    for segment in transcript.segments:
        evidence_blocks.append((segment.text, EvidenceRef(EvidenceKind.AUDIO, f"{segment.start_seconds:.3f}-{segment.end_seconds:.3f}", segment.text), None))
    for result in ocr:
        evidence_blocks.append((result.text, EvidenceRef(EvidenceKind.OCR, str(result.frame.path), result.text, result.confidence), result.frame.path))
    evidence_blocks.sort(key=lambda item: _locator_time(item[1].locator))
    for block_index, (text, evidence, image) in enumerate(evidence_blocks):
        for match in QUESTION.finditer(text):
            prompt = _clean(match.group(0))
            options = [AnswerOption(label=m.group(1).upper(), text=_clean(m.group(2)), evidence=(evidence,)) for line in text.splitlines() if (m := OPTION.match(line))]
            answer, explanation = _answer_and_explanation(" ".join(item[0] for item in evidence_blocks[block_index:]), evidence)
            record = QuestionRecord(
                question_id=f"q-{len(records) + 1:04d}",
                prompt=prompt,
                options=options,
                answer=answer,
                explanation=explanation,
                evidence=[evidence],
                confidence=0.75 if options else 0.55,
            )
            if answer and options and answer not in {option.label for option in options}:
                record.warnings.append("The answer label was not found among extracted options.")
                record.confidence = min(record.confidence or 0.0, 0.4)
            records.append(record)
    records = _deduplicate(records)
    if config.llm.enabled and (not records or any((item.confidence or 0) < 0.7 for item in records)):
        _enrich_with_llm(records, transcript, ocr, config)
    return records


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _locator_time(locator: str) -> float:
    try:
        return float(locator.split("-", 1)[0])
    except ValueError:
        return 0.0


def _answer_and_explanation(text: str, evidence: EvidenceRef) -> tuple[str | None, str | None]:
    match = ANSWER.search(text)
    answer = match.group(1).upper() if match else None
    explanation_match = EXPLANATION.search(text)
    explanation = _clean(explanation_match.group(1)) if explanation_match else None
    return answer, explanation


def _deduplicate(records: list[QuestionRecord]) -> list[QuestionRecord]:
    unique: list[QuestionRecord] = []
    seen: dict[str, QuestionRecord] = {}
    for record in records:
        key = re.sub(r"\W+", " ", record.prompt.lower()).strip()
        if key in seen:
            existing = seen[key]
            existing.evidence.extend(record.evidence)
            if existing.answer and record.answer and existing.answer != record.answer:
                existing.warnings.append("Duplicate evidence contains conflicting answers.")
                existing.confidence = min(existing.confidence or 0.0, 0.35)
            continue
        seen[key] = record
        unique.append(record)
    return unique


def _enrich_with_llm(records: list[QuestionRecord], transcript: Transcript, ocr: list[OCRResult], config: PipelineConfig) -> None:
    """Use the configured model only for low-confidence or missing structure."""
    context = "\n".join(item.text for item in transcript.segments)
    context += "\n" + "\n".join(item.text for item in (result for result in ocr))
    schema: dict[str, Any] = {
        "type": "array",
        "items": {"type": "object", "properties": {"prompt": {"type": "string"}, "options": {"type": "array"}, "answer": {"type": ["string", "null"]}, "explanation": {"type": ["string", "null"]}}, "required": ["prompt"]},
    }
    output_language = config.llm.output_language
    language_instruction = (
        "Write the result in the same language as the evidence."
        if output_language.lower() == "same"
        else f"Write the result in {output_language}. Translate only when necessary and do not invent missing answers."
    )
    result = generate(
        "Extract exam questions, options, answers, and explanations from this evidence. "
        f"{language_instruction} Do not invent missing answers. Return JSON.\n\n" + context,
        config.llm,
        images=[item.frame.path for item in ocr if item.confidence is None or item.confidence < config.ocr.confidence_threshold][:4],
        schema=schema,
    )
    if not isinstance(result, list):
        return
    for item in result:
        if not isinstance(item, dict) or not item.get("prompt"):
            continue
        prompt = str(item["prompt"])
        existing = next((record for record in records if record.prompt.lower() == prompt.lower()), None)
        if existing:
            existing.answer = existing.answer or _optional_text(item.get("answer"))
            existing.explanation = existing.explanation or _optional_text(item.get("explanation"))
            existing.confidence = min(0.9, (existing.confidence or 0.0) + 0.15)
            existing.evidence.append(EvidenceRef(EvidenceKind.LLM, "llm", prompt, 0.7))
            continue
        options = [AnswerOption(str(option.get("label", "")), str(option.get("text", ""))) for option in item.get("options", []) if isinstance(option, dict)]
        records.append(QuestionRecord(f"q-{len(records) + 1:04d}", prompt, options, _optional_text(item.get("answer")), _optional_text(item.get("explanation")), evidence=[EvidenceRef(EvidenceKind.LLM, "llm", prompt, 0.7)], confidence=0.7))


def _optional_text(value: object) -> str | None:
    return str(value) if value not in (None, "") else None
