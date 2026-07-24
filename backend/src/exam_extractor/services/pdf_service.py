"""PDF page rendering for the shared frame/OCR path."""

from pathlib import Path

from ..config import PipelineConfig
from ..errors import ErrorCode, ExtractorError
from ..models.frames import FrameEvidence
from .tools import executable, run_checked


def extract_pdf_pages(pdf: Path | None, target: Path, config: PipelineConfig) -> list[FrameEvidence]:
    """Render PDF pages to PNG evidence frames using Poppler."""
    if not pdf:
        return []
    target.mkdir(parents=True, exist_ok=True)
    for old in target.glob("page-*.png"):
        old.unlink()
    try:
        poppler = executable("pdftoppm", "PDFTOPPM_BIN")
        run_checked(
            [poppler, "-png", "-r", str(min(300, max(72, config.frames.max_resolution))), str(pdf), str(target / "page")],
            stage="frames",
        )
    except ExtractorError as error:
        raise ExtractorError(
            code=ErrorCode.PROVIDER_UNAVAILABLE,
            message="PDF page rendering requires Poppler's pdftoppm executable.",
            stage="frames",
            suggestion="Install poppler-utils on Linux or Poppler for Windows and add it to PATH.",
        ) from error
    pages = sorted(target.glob("page-*.png"))
    return [FrameEvidence(float(index), path, "pdf_page") for index, path in enumerate(pages)]
