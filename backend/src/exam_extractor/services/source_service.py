"""Source detection and Phase 1 acquisition."""

import json
import re
import shutil
from datetime import timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

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
        caption_languages=sorted({_caption_language(path) for path in captions}),
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


def _youtube_options(target: Path, config: PipelineConfig, *, captions: bool) -> dict[str, Any]:
    """Build yt-dlp options, allowing media acquisition without captions."""
    options: dict[str, Any] = {
        "outtmpl": str(target / "media.%(ext)s"),
        "format": f"bv*[height<={config.frames.max_resolution}]+ba/b[height<={config.frames.max_resolution}]/b",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "writeinfojson": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
    }
    if captions:
        language = config.speech.language
        subtitle_languages = (
            [language, f"{language}.*"]
            if language and language.lower() != "auto"
            else ["en", "en.*", "ar", "ar.*"]
        )
        options.update(
            {
                "writesubtitles": True,
                "writeautomaticsub": True,
                "subtitleslangs": subtitle_languages,
                "subtitlesformat": "vtt",
            }
        )
    return options


def _youtube_video_id(value: str) -> str | None:
    """Extract one video ID while ignoring playlist and timestamp parameters."""
    parsed = urlparse(value)
    query_id = parse_qs(parsed.query).get("v", [None])[0]
    if query_id:
        return query_id
    if parsed.netloc.lower().endswith("youtu.be"):
        return parsed.path.strip("/").split("/", 1)[0] or None
    match = re.search(r"/(?:shorts|embed)/([A-Za-z0-9_-]{6,})", parsed.path)
    return match.group(1) if match else None


def _seconds_to_vtt(seconds: float) -> str:
    """Format seconds as a WebVTT timestamp."""
    value = timedelta(seconds=max(0.0, seconds))
    total = value.total_seconds()
    hours = int(total // 3600)
    minutes = int((total % 3600) // 60)
    remainder = total % 60
    return f"{hours:02d}:{minutes:02d}:{remainder:06.3f}"


def _caption_language(path: Path) -> str:
    """Infer a caption language from common yt-dlp/WebVTT filenames."""
    parts = path.stem.split(".")
    return parts[-1] if len(parts) > 1 and parts[-1] else "en"


def _fetch_transcript_fallback(
    source: str,
    target: Path,
    preferred_language: str | None = None,
) -> tuple[Path, str] | None:
    """Fetch a visible YouTube transcript when yt-dlp captions are rate-limited.

    English is preferred, but a video may expose only another transcript language
    (for example, an Arabic auto-generated transcript).  Returning that language
    lets the pipeline use the transcript immediately without mislabeling it.
    """
    video_id = _youtube_video_id(source)
    if not video_id:
        return None
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        api = YouTubeTranscriptApi()
        preferred = preferred_language if preferred_language and preferred_language.lower() != "auto" else "en"
        language = preferred
        try:
            fetched = api.fetch(video_id, languages=[preferred])
        except Exception:
            transcript_list = api.list(video_id)
            try:
                candidates = list(transcript_list)
            except TypeError:
                candidates = []
                for attribute in ("manually_created_transcripts", "_manually_created_transcripts"):
                    values = getattr(transcript_list, attribute, {})
                    candidates.extend(values.values() if isinstance(values, dict) else values)
                for attribute in ("generated_transcripts", "_generated_transcripts"):
                    values = getattr(transcript_list, attribute, {})
                    candidates.extend(values.values() if isinstance(values, dict) else values)
            preferred_codes = [preferred.lower()]
            if preferred.lower() != "en":
                preferred_codes.append("en")
            selected = next(
                (
                    item
                    for wanted in preferred_codes
                    for item in candidates
                    if str(getattr(item, "language_code", "")).lower().startswith(wanted)
                ),
                next(iter(candidates), None),
            )
            if selected is None:
                return None
            fetched = selected.fetch()
            language = str(getattr(selected, "language_code", "und")) or "und"
    except Exception:
        return None
    lines = ["WEBVTT", ""]
    for index, snippet in enumerate(fetched, start=1):
        if isinstance(snippet, dict):
            text = str(snippet.get("text", "")).strip()
            start = float(snippet.get("start", 0.0))
            duration = float(snippet.get("duration", 0.0))
        else:
            text = str(getattr(snippet, "text", "")).strip()
            start = float(getattr(snippet, "start", 0.0))
            duration = float(getattr(snippet, "duration", 0.0))
        if not text:
            continue
        lines.extend(
            [
                str(index),
                f"{_seconds_to_vtt(start)} --> {_seconds_to_vtt(start + max(duration, 0.1))}",
                text.replace("\n", " "),
                "",
            ]
        )
    if len(lines) <= 2:
        return None
    destination = target / f"captions.{language}.vtt"
    destination.write_text("\n".join(lines), encoding="utf-8")
    return destination, language


def _is_caption_download_error(error: Exception) -> bool:
    """Identify subtitle/caption failures that should not block media download."""
    message = str(error).lower()
    return "subtitle" in message or "caption" in message


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

    caption_warning: str | None = None
    try:
        with yt_dlp.YoutubeDL(_youtube_options(target, config, captions=True)) as downloader:
            info = downloader.extract_info(source.value, download=True)
    except Exception as exc:  # yt-dlp exposes several version-specific exceptions.
        if not _is_caption_download_error(exc):
            raise ExtractorError(
                code=ErrorCode.SOURCE_UNAVAILABLE,
                message=f"Could not acquire YouTube source: {exc}",
                stage="acquire",
                provider="yt-dlp",
                source=source.value,
                retryable=True,
                suggestion="Check the URL, network access, video availability, and FFmpeg installation.",
            ) from exc
        fallback_caption = _fetch_transcript_fallback(source.value, target, config.speech.language)
        if fallback_caption:
            caption_warning = (
                "yt-dlp captions were rate-limited; an automatic YouTube transcript "
                f"fallback was used (language: {fallback_caption[1]})."
            )
        else:
            caption_warning = f"YouTube captions were unavailable ({exc}); continuing with media-only acquisition."
        try:
            with yt_dlp.YoutubeDL(_youtube_options(target, config, captions=False)) as downloader:
                info = downloader.extract_info(source.value, download=True)
        except Exception as retry_error:
            raise ExtractorError(
                code=ErrorCode.SOURCE_UNAVAILABLE,
                message=f"Could not acquire YouTube media after captions failed: {retry_error}",
                stage="acquire",
                provider="yt-dlp",
                source=source.value,
                retryable=True,
                suggestion="Wait for the YouTube rate limit to clear, upload a local file, or check the URL and network access.",
            ) from retry_error

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
    extra = {"id": info.get("id"), "uploader": info.get("uploader")}
    if caption_warning:
        extra["caption_warning"] = caption_warning
    metadata = SourceMetadata(
        source=source,
        title=info.get("title"),
        duration_seconds=info.get("duration"),
        language=info.get("language"),
        media_types=["video"],
        has_captions=bool(captions),
        caption_languages=sorted({_caption_language(path) for path in captions}),
        extra=extra,
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
