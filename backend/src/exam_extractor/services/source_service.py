"""Source detection and Phase 1 acquisition."""

import json
import re
import shutil
from pathlib import Path
from typing import Any

from ..config import PipelineConfig
from ..errors import ErrorCode, ExtractorError
from ..models.sources import AcquiredSource, SourceKind, SourceMetadata, SourceRef
from .serialization import jsonable


YOUTUBE = re.compile(r"https?://(?:www\.)?(?:youtube\.com|youtu\.be)/", re.I)
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v"}
AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".opus"}


def detect_source(value: str) -> SourceRef:
    """Classify a URL or local path before any expensive work."""
    if YOUTUBE.match(value):
        return SourceRef(value=value, kind=SourceKind.YOUTUBE)
    path = Path(value).expanduser()
    suffix = path.suffix.lower()
    if suffix in VIDEO_EXTENSIONS:
        return SourceRef(value=str(path), kind=SourceKind.VIDEO)
    if suffix in AUDIO_EXTENSIONS:
        return SourceRef(value=str(path), kind=SourceKind.AUDIO)
    if suffix == ".pdf":
        return SourceRef(value=str(path), kind=SourceKind.PDF)
    return SourceRef(value=str(path), kind=SourceKind.UNKNOWN)


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(jsonable(value), indent=2, ensure_ascii=False), encoding="utf-8")


def _acquired_json(acquired: AcquiredSource) -> dict[str, Any]:
    return {
        "source": {"value": acquired.source.value, "kind": acquired.source.kind.value},
        "root": str(acquired.root),
        "media_path": str(acquired.media_path) if acquired.media_path else None,
        "audio_path": str(acquired.audio_path) if acquired.audio_path else None,
        "caption_paths": [str(path) for path in acquired.caption_paths],
        "metadata_path": str(acquired.metadata_path) if acquired.metadata_path else None,
    }


def load_acquired(path: Path) -> AcquiredSource:
    """Load an acquisition result for a resumed job."""
    data = json.loads(path.read_text(encoding="utf-8"))
    source = SourceRef(data["source"]["value"], SourceKind(data["source"]["kind"]))
    return AcquiredSource(
        source=source,
        root=Path(data["root"]),
        media_path=Path(data["media_path"]) if data.get("media_path") else None,
        audio_path=Path(data["audio_path"]) if data.get("audio_path") else None,
        caption_paths=tuple(Path(item) for item in data.get("caption_paths", [])),
        metadata_path=Path(data["metadata_path"]) if data.get("metadata_path") else None,
    )


def acquire_source(source: SourceRef, target: Path, config: PipelineConfig) -> tuple[AcquiredSource, SourceMetadata]:
    """Acquire a YouTube or local media source into a job workspace."""
    target.mkdir(parents=True, exist_ok=True)
    if source.kind == SourceKind.YOUTUBE:
        return _acquire_youtube(source, target, config)
    if source.kind in {SourceKind.VIDEO, SourceKind.AUDIO}:
        return _acquire_local(source, target)
    if source.kind == SourceKind.PDF:
        return _acquire_local(source, target)
    raise ExtractorError(
        code=ErrorCode.INVALID_INPUT,
        message=f"Unsupported or unknown source: {source.value}",
        stage="validate",
        source=source.value,
        suggestion="Provide a YouTube URL or a supported local media file.",
    )


def _acquire_local(source: SourceRef, target: Path) -> tuple[AcquiredSource, SourceMetadata]:
    original = Path(source.value).expanduser().resolve()
    if not original.is_file():
        raise ExtractorError(
            code=ErrorCode.SOURCE_UNAVAILABLE,
            message=f"Local source does not exist: {original}",
            stage="acquire",
            source=source.value,
            suggestion="Check the path and file permissions.",
        )
    media = target / f"media{original.suffix.lower()}"
    if original != media:
        shutil.copy2(original, media)
    captions = []
    for sidecar in sorted(original.parent.glob(f"{original.stem}*.vtt")):
        destination = target / sidecar.name
        shutil.copy2(sidecar, destination)
        captions.append(destination)
    metadata = SourceMetadata(
        source=source,
        title=original.stem,
        media_types=[source.kind.value],
        has_captions=bool(captions),
        caption_languages=["en"] if captions else [],
        extra={"size_bytes": original.stat().st_size},
    )
    metadata_path = target / "metadata.json"
    _write_json(metadata_path, metadata.__dict__)
    acquired = AcquiredSource(
        source=source,
        root=target,
        media_path=media,
        caption_paths=tuple(captions),
        metadata_path=metadata_path,
    )
    _write_json(target / "acquired.json", _acquired_json(acquired))
    return acquired, metadata


def _acquire_youtube(source: SourceRef, target: Path, config: PipelineConfig) -> tuple[AcquiredSource, SourceMetadata]:
    try:
        import yt_dlp
    except ImportError as exc:
        raise ExtractorError(
            code=ErrorCode.PROVIDER_UNAVAILABLE,
            message="The yt-dlp package is required for YouTube sources.",
            stage="acquire",
            provider="yt-dlp",
            suggestion="Install the project with: python -m pip install -e backend",
        ) from exc

    maximum = config.frames.max_resolution
    options = {
        "outtmpl": str(target / "media.%(ext)s"),
        "format": f"bv*[height<={maximum}]+ba/b[height<={maximum}]/b",
        "merge_output_format": "mp4",
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["en", "en.*"],
        "subtitlesformat": "vtt",
        "writeinfojson": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
    }
    try:
        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(source.value, download=True)
    except Exception as exc:  # yt-dlp exposes several version-specific exceptions.
        raise ExtractorError(
            code=ErrorCode.SOURCE_UNAVAILABLE,
            message=f"Could not acquire YouTube source: {exc}",
            stage="acquire",
            provider="yt-dlp",
            source=source.value,
            retryable=True,
            suggestion="Check the URL, network access, video availability, and FFmpeg installation.",
        ) from exc

    media_candidates = [
        path for path in target.glob("media.*") if path.suffix.lower() not in {".json", ".vtt"}
    ]
    media = max(media_candidates, key=lambda item: item.stat().st_size, default=None)
    if media is None:
        raise ExtractorError(
            code=ErrorCode.MEDIA_UNREADABLE,
            message="yt-dlp completed without producing a media file.",
            stage="acquire",
            source=source.value,
            suggestion="Install FFmpeg and retry with a supported format.",
        )
    captions = tuple(sorted(target.glob("*.vtt")))
    metadata = SourceMetadata(
        source=source,
        title=info.get("title"),
        duration_seconds=info.get("duration"),
        language=info.get("language"),
        media_types=["video"],
        has_captions=bool(captions),
        caption_languages=["en"] if captions else [],
        extra={"id": info.get("id"), "uploader": info.get("uploader")},
    )
    metadata_path = target / "metadata.json"
    _write_json(metadata_path, metadata.__dict__)
    acquired = AcquiredSource(
        source=source,
        root=target,
        media_path=media,
        caption_paths=captions,
        metadata_path=metadata_path,
    )
    _write_json(target / "acquired.json", _acquired_json(acquired))
    return acquired, metadata
