"""FFmpeg/ffprobe media operations."""

import json
import re
import shutil
from pathlib import Path

from ..config import PipelineConfig
from ..errors import ErrorCode, ExtractorError
from ..models.frames import FrameEvidence
from .tools import executable, run_checked


def _probe(media: Path) -> dict[str, object]:
    ffprobe = executable("ffprobe", "FFPROBE_BIN")
    result = run_checked(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,avg_frame_rate,width,height",
            "-of",
            "json",
            str(media),
        ],
        stage="probe",
    )
    return json.loads(result.stdout)


def _fps(probe: dict[str, object]) -> float:
    for stream in probe.get("streams", []):
        if stream.get("codec_type") == "video":
            rate = str(stream.get("avg_frame_rate", "30/1"))
            numerator, denominator = rate.split("/", 1)
            return float(numerator) / float(denominator or 1)
    return 0.0


def extract_audio(media: Path, target: Path) -> Path:
    """Extract a normalized mono WAV for future speech providers."""
    ffmpeg = executable("ffmpeg", "FFMPEG_BIN")
    target.mkdir(parents=True, exist_ok=True)
    audio = target / "audio.wav"
    run_checked(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(media),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-y",
            str(audio),
        ],
        stage="audio",
    )
    return audio


def extract_frames(media: Path, target: Path, config: PipelineConfig) -> list[FrameEvidence]:
    """Extract periodic or scene-change JPEG evidence frames."""
    ffmpeg = executable("ffmpeg", "FFMPEG_BIN")
    target.mkdir(parents=True, exist_ok=True)
    for old in target.glob("*.jpg"):
        old.unlink()
    probe = _probe(media)
    fps = _fps(probe)
    if fps <= 0:
        raise ExtractorError(
            code=ErrorCode.VIDEO_UNAVAILABLE,
            message="The input does not contain a readable video stream.",
            stage="frames",
            suggestion="Use an audio-only profile or provide a video file for visual extraction.",
        )
    if config.frames.method == "interval":
        filter_value = f"fps=1/{config.frames.fallback_interval_seconds},scale=-2:{config.frames.max_resolution}"
    else:
        filter_value = (
            f"select='eq(n,0)+gt(scene,{config.frames.scene_threshold})',"
            f"scale=-2:{config.frames.max_resolution}"
        )
    run_checked(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(media),
            "-vf",
            filter_value,
            "-vsync",
            "vfr",
            "-q:v",
            "2",
            "-frame_pts",
            "1",
            str(target / "frame_%010d.jpg"),
            "-y",
        ],
        stage="frames",
    )
    paths = sorted(target.glob("*.jpg"))
    if not paths:
        raise ExtractorError(
            code=ErrorCode.VIDEO_UNAVAILABLE,
            message="FFmpeg produced no visual frames.",
            stage="frames",
            suggestion="Try interval sampling or lower the scene threshold.",
        )
    evidence = []
    for index, path in enumerate(paths):
        if config.frames.method == "interval":
            timestamp = index * config.frames.fallback_interval_seconds
        else:
            match = re.search(r"(\d+)$", path.stem)
            timestamp = int(match.group(1)) / fps if match else float(index)
        evidence.append(
            FrameEvidence(
                timestamp_seconds=round(timestamp, 3),
                path=path,
                method=config.frames.method,
            )
        )
    return evidence
