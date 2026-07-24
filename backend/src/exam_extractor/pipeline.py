"""Deterministic Phase 1 pipeline runner and shared stage contracts."""

import hashlib
import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from .config import PipelineConfig
from .errors import ErrorCode, ExtractorError
from .models import (
    FrameEvidence,
    Job,
    JobStatus,
    OCRResult,
    SourceKind,
    SourceMetadata,
    SourceRef,
    StageName,
    StageResult,
    StageStatus,
    Transcript,
    TranscriptSegment,
)
from .services.captions import parse_caption_file
from .services.media_service import extract_audio, extract_frames
from .services.ocr_service import extract_ocr
from .services.output_service import write_json, write_outputs
from .services.serialization import jsonable
from .services.source_service import acquire_source, detect_source, load_acquired


@dataclass
class PipelineContext:
    """State shared by stages during one job."""

    job: Job
    config: PipelineConfig
    workspace: Path
    values: dict[str, Any] = field(default_factory=dict)


class PipelineStage(Protocol):
    """One resumable pipeline stage."""

    name: StageName

    async def run(self, context: PipelineContext) -> StageResult:
        """Execute the stage and return produced artifacts and warnings."""


def _job_id(source: str, config: PipelineConfig) -> str:
    """Create a stable job folder name so interrupted runs can resume."""
    fingerprint = json.dumps(
        {
            "source": source,
            "profile": config.profile,
            "frames": config.frames.__dict__,
            "ocr": config.ocr.__dict__,
            "output": config.output.__dict__,
        },
        sort_keys=True,
        default=str,
    )
    digest = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:12]
    label = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(source).stem or "source").strip("-")[:36]
    return f"{label or 'source'}-{digest}"


def _load_metadata(path: Path) -> SourceMetadata:
    data = json.loads(path.read_text(encoding="utf-8"))
    source_data = data["source"]
    return SourceMetadata(
        source=SourceRef(source_data["value"], SourceKind(source_data["kind"])),
        title=data.get("title"),
        duration_seconds=data.get("duration_seconds"),
        language=data.get("language"),
        media_types=data.get("media_types", []),
        has_captions=data.get("has_captions", False),
        caption_languages=data.get("caption_languages", []),
        extra=data.get("extra", {}),
    )


def _load_transcript(path: Path) -> Transcript:
    data = json.loads(path.read_text(encoding="utf-8"))
    return Transcript(
        segments=[TranscriptSegment(**item) for item in data.get("segments", [])],
        language=data.get("language"),
        source=data.get("source", "unknown"),
    )


def _load_frames(path: Path) -> list[FrameEvidence]:
    return [
        FrameEvidence(
            timestamp_seconds=item["timestamp_seconds"],
            path=Path(item["path"]),
            method=item["method"],
            width=item.get("width"),
            height=item.get("height"),
            scene_score=item.get("scene_score"),
        )
        for item in json.loads(path.read_text(encoding="utf-8"))
    ]


def _load_ocr(path: Path) -> list[OCRResult]:
    values = []
    for item in json.loads(path.read_text(encoding="utf-8")):
        frame = FrameEvidence(
            timestamp_seconds=item["frame"]["timestamp_seconds"],
            path=Path(item["frame"]["path"]),
            method=item["frame"]["method"],
        )
        values.append(
            OCRResult(
                frame=frame,
                text=item["text"],
                confidence=item.get("confidence"),
                engine=item.get("engine", "unknown"),
                warnings=item.get("warnings", []),
            )
        )
    return values


def _read_manifest(path: Path, source: SourceRef) -> dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {
        "job_id": path.parent.name,
        "source": jsonable(source),
        "status": JobStatus.CREATED.value,
        "stages": {},
        "warnings": [],
        "errors": [],
    }


def _write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    write_json(path, manifest)


def run_pipeline(
    source_value: str,
    config: PipelineConfig,
    *,
    output_root: Path | None = None,
    force: bool = False,
    progress: Any = print,
) -> Path:
    """Run or resume the deterministic Phase 1 extraction pipeline.

    Args:
        source_value: YouTube URL or local media path.
        config: Validated pipeline configuration.
        output_root: Root directory for job artifacts.
        force: Remove this generated job workspace and start over.
        progress: Callable used for human-readable stage progress.

    Returns:
        The completed job workspace path.

    Raises:
        ExtractorError: If a stage cannot complete.
    """
    config.validate()
    source = detect_source(source_value)
    root = Path(output_root or config.output_dir).expanduser()
    workspace = root / _job_id(source_value, config)
    if force and workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    manifest_path = workspace / "manifest.json"
    manifest = _read_manifest(manifest_path, source)
    manifest["status"] = JobStatus.RUNNING.value
    _write_manifest(manifest_path, manifest)

    def complete(stage: StageName, value: Any = None) -> None:
        manifest["stages"][stage.value] = {"status": StageStatus.COMPLETED.value}
        _write_manifest(manifest_path, manifest)
        if value is not None:
            values[stage] = value

    def should_skip(stage: StageName) -> bool:
        return (
            not force
            and manifest.get("stages", {}).get(stage.value, {}).get("status")
            == StageStatus.COMPLETED.value
        )

    def begin(stage: StageName) -> None:
        progress(f"[{stage.value}] starting")
        manifest["stages"][stage.value] = {"status": StageStatus.RUNNING.value}
        _write_manifest(manifest_path, manifest)

    def fail(stage: StageName, error: ExtractorError) -> None:
        manifest["status"] = JobStatus.FAILED.value
        manifest["stages"][stage.value] = {
            "status": StageStatus.FAILED.value,
            "error": error.to_dict(),
        }
        manifest.setdefault("errors", []).append(error.to_dict())
        _write_manifest(manifest_path, manifest)

    values: dict[StageName, Any] = {}
    try:
        if should_skip(StageName.ACQUIRE):
            acquired = load_acquired(workspace / "source" / "acquired.json")
            metadata = _load_metadata(workspace / "source" / "metadata.json")
            values[StageName.ACQUIRE] = (acquired, metadata)
        else:
            begin(StageName.ACQUIRE)
            acquired, metadata = acquire_source(source, workspace / "source", config)
            complete(StageName.ACQUIRE, (acquired, metadata))
        progress(f"[acquire] {metadata.title or source_value}")

        if should_skip(StageName.SPEECH):
            transcript = _load_transcript(workspace / "transcript.json")
            warnings = manifest.get("warnings", [])
        else:
            begin(StageName.SPEECH)
            warnings: list[str] = []
            segments: list[TranscriptSegment] = []
            for caption_path in acquired.caption_paths:
                segments.extend(parse_caption_file(caption_path, language="en").segments)
            segments.sort(key=lambda item: item.start_seconds)
            transcript = Transcript(segments=segments, language="en" if segments else None, source="captions" if segments else "none")
            if acquired.media_path:
                try:
                    audio = extract_audio(acquired.media_path, workspace / "audio")
                    manifest["audio_path"] = str(audio)
                except ExtractorError as error:
                    warnings.append(error.message)
            if not segments:
                warnings.append("No captions were available; audio was extracted for a future speech provider.")
            manifest["warnings"] = warnings
            write_json(workspace / "transcript.json", transcript)
            complete(StageName.SPEECH, transcript)

        if source.kind == SourceKind.AUDIO:
            frames: list[FrameEvidence] = []
            if not should_skip(StageName.FRAMES):
                begin(StageName.FRAMES)
                complete(StageName.FRAMES, frames)
        elif should_skip(StageName.FRAMES):
            frames = _load_frames(workspace / "frames.json")
        else:
            begin(StageName.FRAMES)
            frames = extract_frames(acquired.media_path, workspace / "frames", config) if acquired.media_path else []
            write_json(workspace / "frames.json", frames)
            complete(StageName.FRAMES, frames)

        if should_skip(StageName.OCR):
            ocr = _load_ocr(workspace / "ocr.json")
        else:
            begin(StageName.OCR)
            ocr = extract_ocr(frames, config) if frames else []
            write_json(workspace / "ocr.json", ocr)
            complete(StageName.OCR, ocr)

        if not should_skip(StageName.RENDER):
            begin(StageName.RENDER)
            outputs = write_outputs(workspace, metadata, transcript, frames, ocr, config, manifest.get("warnings", []))
            manifest["outputs"] = [str(path) for path in outputs]
            complete(StageName.RENDER, outputs)

        manifest["status"] = JobStatus.COMPLETED.value
        _write_manifest(manifest_path, manifest)
        progress(f"[done] {workspace}")
        return workspace
    except ExtractorError as error:
        stage_name = error.stage or "unknown"
        try:
            fail(StageName(stage_name), error)
        except ValueError:
            manifest["status"] = JobStatus.FAILED.value
            manifest.setdefault("errors", []).append(error.to_dict())
            _write_manifest(manifest_path, manifest)
        raise
