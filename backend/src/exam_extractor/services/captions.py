"""WebVTT/SRT parsing into the normalized transcript contract."""

import html
import re
from pathlib import Path

from ..models.transcripts import Transcript, TranscriptSegment


TIMING = re.compile(
    r"(?P<start>\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d{3})?)\s+-->\s+"
    r"(?P<end>\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d{3})?)"
)


def seconds(value: str) -> float:
    """Convert WebVTT/SRT time notation to seconds."""
    value = value.replace(",", ".")
    parts = value.split(":")
    if len(parts) == 2:
        minutes, remainder = parts
        hours = 0
    else:
        hours, minutes, remainder = parts
    minute_seconds = float(remainder)
    return int(hours) * 3600 + int(minutes) * 60 + minute_seconds


def clean_caption(text: str) -> str:
    """Remove markup and inline word-timing tags from one caption."""
    text = re.sub(r"<\d{1,2}:\d{2}(?:\.\d{3})?>", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def parse_caption_file(path: Path, language: str | None = None) -> Transcript:
    """Parse a WebVTT or SRT file."""
    lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    segments: list[TranscriptSegment] = []
    index = 0
    while index < len(lines):
        match = TIMING.search(lines[index])
        if not match:
            index += 1
            continue
        index += 1
        text_lines: list[str] = []
        while index < len(lines) and lines[index].strip():
            text_lines.append(lines[index])
            index += 1
        text = clean_caption(" ".join(text_lines))
        if text:
            segment = TranscriptSegment(
                start_seconds=seconds(match.group("start")),
                end_seconds=seconds(match.group("end")),
                text=text,
                language=language,
                source="captions",
            )
            if not segments or (
                segments[-1].text != segment.text
                or segments[-1].start_seconds != segment.start_seconds
            ):
                segments.append(segment)
        index += 1
    return Transcript(segments=segments, language=language, source="captions")
