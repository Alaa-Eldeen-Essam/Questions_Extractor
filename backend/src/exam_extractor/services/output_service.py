"""Deterministic Markdown and JSON renderers."""

import json
from pathlib import Path

from ..config import PipelineConfig
from ..models.frames import FrameEvidence, OCRResult
from ..models.questions import QuestionRecord
from ..models.sources import SourceMetadata
from ..models.transcripts import Transcript
from .serialization import jsonable


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
) -> list[Path]:
    """Write Phase 1 output artifacts and return their paths."""
    target.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    payload = {
        "metadata": metadata,
        "transcript": transcript,
        "frames": frames,
        "ocr": ocr,
        "questions": questions,
        "warnings": warnings,
    }
    if config.output.json:
        path = target / "extraction.json"
        write_json(path, payload)
        outputs.append(path)
    if config.output.markdown:
        path = target / "extraction.md"
        lines = [
            f"# {metadata.title or metadata.source.value}",
            "",
            f"- Source: `{metadata.source.value}`",
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
        lines += ["", "## Question bank", ""]
        if questions:
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
                lines.append("")
        else:
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
    return outputs
