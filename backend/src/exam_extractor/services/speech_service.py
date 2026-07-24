"""Elastic speech providers with a local-first default."""

import json
import os
import uuid
from pathlib import Path
from typing import Any
from urllib import error as urlerror
from urllib import request

from ..config import SpeechConfig
from ..errors import ErrorCode, ExtractorError
from ..models.transcripts import Transcript, TranscriptSegment, TranscriptWord


def transcribe_audio(audio: Path, config: SpeechConfig) -> Transcript:
    """Select and execute the configured speech provider."""
    provider = config.provider.lower()
    if provider in {"captions", "none"}:
        return Transcript([], None, provider)
    if provider in {"auto", "faster_whisper", "local"}:
        return _faster_whisper(audio, config)
    if provider in {"openai", "openai_compatible", "remote"}:
        return _openai_compatible(audio, config)
    raise ExtractorError(
        code=ErrorCode.CONFIGURATION,
        message=f"Unknown speech provider: {config.provider}",
        stage="speech",
        provider=config.provider,
        suggestion="Choose auto, faster_whisper, openai_compatible, captions, or none.",
    )


def _resolve_device(config: SpeechConfig) -> tuple[str, str]:
    """Choose CPU/CUDA and a safe default compute type."""
    if config.device != "auto":
        device = config.device
    else:
        try:
            import ctranslate2

            device = "cuda" if ctranslate2.get_cuda_device_count() else "cpu"
        except (ImportError, RuntimeError):
            device = "cpu"
    compute = config.compute_type
    if compute == "auto":
        compute = "float16" if device == "cuda" else "int8"
    return device, compute


def _faster_whisper(audio: Path, config: SpeechConfig) -> Transcript:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise ExtractorError(
            code=ErrorCode.PROVIDER_UNAVAILABLE,
            message="Local speech extraction needs the optional faster-whisper package.",
            stage="speech",
            provider="faster_whisper",
            suggestion="Install with: python -m pip install -e 'backend[speech]'",
        ) from exc

    device, compute_type = _resolve_device(config)
    try:
        model = WhisperModel(config.model, device=device, compute_type=compute_type)
        segments, info = model.transcribe(
            str(audio),
            language=config.language,
            task="translate" if config.translate else "transcribe",
            beam_size=config.beam_size,
            vad_filter=config.vad_filter,
            word_timestamps=True,
        )
        normalized: list[TranscriptSegment] = []
        for segment in segments:
            words = tuple(
                TranscriptWord(
                    start_seconds=float(word.start),
                    end_seconds=float(word.end),
                    word=word.word.strip(),
                    probability=getattr(word, "probability", None),
                )
                for word in (getattr(segment, "words", None) or [])
            )
            normalized.append(
                TranscriptSegment(
                    start_seconds=float(segment.start),
                    end_seconds=float(segment.end),
                    text=segment.text.strip(),
                    language=getattr(info, "language", None),
                    source="faster_whisper",
                    confidence=getattr(segment, "avg_logprob", None),
                    words=words,
                )
            )
        return Transcript(normalized, getattr(info, "language", config.language), "faster_whisper")
    except Exception as exc:
        raise ExtractorError(
            code=ErrorCode.PROVIDER_BAD_RESPONSE,
            message=f"Local speech extraction failed: {exc}",
            stage="speech",
            provider="faster_whisper",
            retryable=True,
            suggestion="Check model access, available memory, and CPU/CUDA configuration.",
        ) from exc


def _multipart(audio: Path, model: str) -> tuple[bytes, str]:
    """Build the small multipart request used by OpenAI-compatible APIs."""
    boundary = f"----exam-extractor-{uuid.uuid4().hex}"
    chunks = [
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{audio.name}"\r\n'
            "Content-Type: audio/wav\r\n\r\n"
        ).encode(),
        audio.read_bytes(),
        b"\r\n",
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="model"\r\n\r\n'
            f"{model}\r\n"
        ).encode(),
        f"--{boundary}--\r\n".encode(),
    ]
    return b"".join(chunks), boundary


def _openai_compatible(audio: Path, config: SpeechConfig) -> Transcript:
    if not config.remote_base_url:
        raise ExtractorError(
            code=ErrorCode.CONFIGURATION,
            message="speech.remote_base_url is required for a remote speech provider.",
            stage="speech",
            provider="openai_compatible",
            suggestion="Set the provider endpoint in TOML or use faster_whisper.",
        )
    body, boundary = _multipart(audio, config.model)
    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Accept": "application/json",
    }
    if config.remote_api_key_env:
        api_key = os.environ.get(config.remote_api_key_env)
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
    endpoint = config.remote_base_url.rstrip("/") + "/audio/transcriptions"
    try:
        response = request.urlopen(
            request.Request(endpoint, data=body, headers=headers, method="POST"),
            timeout=config.timeout_seconds,
        )
        payload: dict[str, Any] = json.loads(response.read().decode("utf-8"))
    except urlerror.HTTPError as exc:
        code = ErrorCode.PROVIDER_RATE_LIMIT if exc.code == 429 else ErrorCode.PROVIDER_BAD_RESPONSE
        raise ExtractorError(
            code=code,
            message=f"Remote speech provider returned HTTP {exc.code}.",
            stage="speech",
            provider="openai_compatible",
            retryable=exc.code in {408, 429, 500, 502, 503, 504},
            suggestion="Check the endpoint, API key, quota, and provider status.",
        ) from exc
    except (urlerror.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise ExtractorError(
            code=ErrorCode.PROVIDER_UNAVAILABLE,
            message=f"Remote speech provider could not be reached: {exc}",
            stage="speech",
            provider="openai_compatible",
            retryable=True,
            suggestion="Check the endpoint URL and network access.",
        ) from exc
    text = str(payload.get("text", "")).strip()
    if not text:
        raise ExtractorError(
            code=ErrorCode.PROVIDER_BAD_RESPONSE,
            message="Remote speech provider returned no transcript text.",
            stage="speech",
            provider="openai_compatible",
            suggestion="Confirm the endpoint follows the OpenAI transcription response format.",
        )
    return Transcript(
        [TranscriptSegment(0.0, 0.0, text, config.language, "openai_compatible")],
        config.language,
        "openai_compatible",
    )
