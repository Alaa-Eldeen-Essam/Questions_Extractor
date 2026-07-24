"""Tesseract OCR implementation for Phase 1."""

import subprocess
from pathlib import Path

from ..config import PipelineConfig
from ..errors import ErrorCode, ExtractorError
from ..models.frames import FrameEvidence, OCRResult
from .tools import executable


def extract_ocr(frames: list[FrameEvidence], config: PipelineConfig) -> list[OCRResult]:
    """Run Tesseract over retained frames and keep readable text."""
    tesseract = executable("tesseract", "TESSERACT_BIN")
    results = []
    for frame in frames:
        try:
            result = subprocess.run(
                [tesseract, str(frame.path), "stdout", "--psm", "6", "-l", config.ocr.language],
                text=True,
                capture_output=True,
                check=False,
            )
        except OSError as exc:
            raise ExtractorError(
                code=ErrorCode.PROVIDER_UNAVAILABLE,
                message=f"Could not start Tesseract: {exc}",
                stage="ocr",
                provider="tesseract",
                suggestion="Install Tesseract and set TESSERACT_BIN if it is not on PATH.",
            ) from exc
        if result.returncode:
            raise ExtractorError(
                code=ErrorCode.PROVIDER_BAD_RESPONSE,
                message=f"Tesseract failed for frame {frame.path.name}.",
                stage="ocr",
                provider="tesseract",
                details={"output": (result.stderr or result.stdout).strip()[-1000:]},
            )
        text = " ".join(line.strip() for line in result.stdout.splitlines() if line.strip())
        if text:
            results.append(OCRResult(frame=frame, text=text, engine="tesseract"))
    return results
