"""Deterministic Markdown and JSON renderers."""

import json
import csv
import io
from pathlib import Path

from ..config import PipelineConfig
from ..models.frames import FrameEvidence, OCRResult
from ..models.questions import QuestionRecord
from ..models.sources import SourceMetadata
from ..models.tasks import TaskResult
from ..models.transcripts import Transcript
from .serialization import jsonable
from .docx_service import write_docx
from .pdf_output_service import write_text_pdf
from .review_service import review_item, review_summary


def write_json(path: Path, value: object) -> None:
    """Write readable UTF-8 JSON."""
    path.write_text(json.dumps(jsonable(value), indent=2, ensure_ascii=False), encoding="utf-8")


def _stamp(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"


def write_outputs(
    target: Path,
    metadata: SourceMetadata,
    transcript: Transcript,
    frames: list[FrameEvidence],
    ocr: list[OCRResult],
    questions: list[QuestionRecord],
    config: PipelineConfig,
    warnings: list[str],
    include_review: bool = True,
    task_result: TaskResult | None = None,
) -> list[Path]:
    """Write Phase 1 output artifacts and return their paths."""
    target.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    payload = {
        "schema_version": 1,
        "metadata": metadata,
        "transcript": transcript,
        "frames": frames,
        "ocr": ocr,
        "questions": questions,
        "task": task_result,
        "review": review_summary(questions, config.review.threshold) if include_review else {"enabled": False},
        "warnings": warnings,
    }
    if config.output.json:
        path = target / "extraction.json"
        write_json(path, payload)
        outputs.append(path)
        if task_result is not None:
            task_path = target / "task.json"
            write_json(task_path, task_result)
            outputs.append(task_path)
    if include_review:
        review_path = target / "review.json"
        write_json(
            review_path,
            {
                "summary": review_summary(questions, config.review.threshold),
                "items": [review_item(question) for question in questions],
            },
        )
        outputs.append(review_path)
    if config.output.markdown:
        path = target / "extraction.md"
        lines = [
            f"# {metadata.title or metadata.source.value}",
            "",
            f"- Source: `{('[redacted]' if config.privacy.redact_source else metadata.source.value)}`",
            f"- Type: `{metadata.source.kind.value}`",
            f"- Captions: `{metadata.has_captions}`",
            "",
            "## Warnings",
            "",
        ]
        if warnings:
            lines.extend(f"- {warning}" for warning in warnings)
        else:
            lines.append("- None")
        lines += ["", "## Speech timeline", ""]
        if transcript.segments:
            for segment in transcript.segments:
                lines.append(f"- **{_stamp(segment.start_seconds)}** — {segment.text}")
        else:
            lines.append("No caption transcript was available. Audio was extracted for a future speech provider.")
        if task_result is not None and task_result.kind != "questions":
            lines += ["", f"## {task_result.title}", "", f"**Instruction:** {task_result.instruction}", ""]
            if isinstance(task_result.content, (dict, list)):
                lines += ["```json", json.dumps(jsonable(task_result.content), indent=2, ensure_ascii=False), "```", ""]
            else:
                lines += [str(task_result.content or "No task content was produced."), ""]
            if task_result.items:
                lines += ["### Structured items", ""]
                lines.extend(f"- {json.dumps(jsonable(item), ensure_ascii=False)}" for item in task_result.items)
        else:
            lines += ["", "## Question bank", ""]
        if questions and (task_result is None or task_result.kind == "questions"):
            for index, question in enumerate(questions, start=1):
                lines += [f"### {index}. {question.prompt}", ""]
                for option in question.options:
                    lines.append(f"- **{option.label}.** {option.text}")
                if question.answer:
                    lines += ["", f"**Answer:** {question.answer}"]
                if question.explanation:
                    lines += ["", f"**Explanation:** {question.explanation}"]
                if question.warnings:
                    lines += ["", *[f"> Warning: {warning}" for warning in question.warnings]]
                lines += [f"**Review status:** {question.review_status}"]
                lines.append("")
        elif task_result is None or task_result.kind == "questions":
            lines.append("No question records were detected.")
        lines += ["", "## Visual evidence", ""]
        if ocr:
            for result in ocr:
                relative = result.frame.path.relative_to(target).as_posix()
                lines += [
                    f"### {_stamp(result.frame.timestamp_seconds)}",
                    "",
                    f"![Frame at {_stamp(result.frame.timestamp_seconds)}]({relative})",
                    "",
                    f"**OCR:** {result.text}",
                    "",
                ]
        else:
            lines.append("No visual frames were extracted.")
        path.write_text("\n".join(lines), encoding="utf-8")
        outputs.append(path)
    if config.output.transcript:
        path = target / "transcript.md"
        path.write_text(
            "\n".join(
                [
                    f"# Transcript — {metadata.title or metadata.source.value}",
                    "",
                    *[f"- **{_stamp(item.start_seconds)}** — {item.text}" for item in transcript.segments],
                ]
            ),
            encoding="utf-8",
        )
        outputs.append(path)
    if config.output.word:
        path = target / "extraction.docx"
        write_docx(path, metadata, transcript, frames, ocr, questions, config, warnings, task_result)
        outputs.append(path)
    if config.output.csv:
        path = target / "questions.csv"
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer)
        writer.writerow(["question_id", "prompt", "options", "answer", "explanation", "confidence", "review_status", "evidence"])
        for question in questions:
            writer.writerow([
                question.question_id,
                question.prompt,
                " | ".join(f"{option.label}. {option.text}" for option in question.options),
                question.answer or "",
                question.explanation or "",
                question.confidence if question.confidence is not None else "",
                question.review_status,
                " | ".join(reference.locator for reference in question.evidence),
            ])
        path.write_text(buffer.getvalue(), encoding="utf-8-sig")
        outputs.append(path)
    if config.output.pdf:
        pdf_path = target / "extraction.pdf"
        markdown_path = target / "extraction.md"
        source_text = markdown_path.read_text(encoding="utf-8") if markdown_path.is_file() else json.dumps(jsonable(payload), indent=2, ensure_ascii=False)
        write_text_pdf(pdf_path, source_text, title=metadata.title or "Extraction")
        outputs.append(pdf_path)
    return outputs
