"""Optional text and vision providers using small HTTP adapters."""

import base64
import json
import os
from pathlib import Path
from typing import Any, Sequence
from urllib import error as urlerror
from urllib import request

from ..config import LLMConfig
from ..errors import ErrorCode, ExtractorError


def available_llm_providers() -> tuple[str, ...]:
    """Return stable provider names exposed by the built-in adapters."""
    return ("none", "openai_compatible", "gemini", "ollama")


def generate(prompt: str, config: LLMConfig, *, images: Sequence[Path] = (), schema: dict[str, Any] | None = None) -> str | dict[str, Any] | None:
    """Generate optional text/JSON while keeping provider details out of callers."""
    provider = config.provider.lower()
    if not config.enabled or provider == "none":
        return None
    if provider in {"openai", "openai_compatible"}:
        return _openai(prompt, config, images, schema)
    if provider == "gemini":
        return _gemini(prompt, config, images, schema)
    if provider == "ollama":
        return _ollama(prompt, config, images)
    raise ExtractorError(
        code=ErrorCode.CONFIGURATION,
        message=f"Unknown LLM provider: {config.provider}",
        stage="visual_analysis",
        provider=config.provider,
        suggestion="Choose none, openai_compatible, gemini, or ollama.",
    )


def _key(config: LLMConfig) -> str | None:
    return os.environ.get(config.api_key_env) if config.api_key_env else None


def _post(url: str, payload: dict[str, Any], config: LLMConfig, headers: dict[str, str]) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request_headers = {"Content-Type": "application/json", **headers}
    last_error: Exception | None = None
    for _ in range(config.retry_count + 1):
        try:
            response = request.urlopen(
                request.Request(url, data=body, headers=request_headers, method="POST"),
                timeout=config.timeout_seconds,
            )
            return json.loads(response.read().decode("utf-8"))
        except urlerror.HTTPError as exc:
            last_error = exc
            if exc.code not in {408, 429, 500, 502, 503, 504}:
                break
        except (urlerror.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            last_error = exc
    if isinstance(last_error, urlerror.HTTPError):
        code = ErrorCode.PROVIDER_RATE_LIMIT if last_error.code == 429 else ErrorCode.PROVIDER_BAD_RESPONSE
        raise ExtractorError(
            code=code,
            message=f"LLM provider returned HTTP {last_error.code}.",
            stage="visual_analysis",
            provider="llm",
            retryable=last_error.code in {408, 429, 500, 502, 503, 504},
            suggestion="Check the endpoint, key, quota, and provider status.",
        ) from last_error
    raise ExtractorError(
        code=ErrorCode.PROVIDER_UNAVAILABLE,
        message=f"LLM provider could not be reached: {last_error}",
        stage="visual_analysis",
        provider="llm",
        retryable=True,
        suggestion="Check the endpoint URL and network access.",
    ) from last_error


def _openai(prompt: str, config: LLMConfig, images: Sequence[Path], schema: dict[str, Any] | None) -> Any:
    if not config.base_url or not config.model:
        raise ExtractorError(
            code=ErrorCode.CONFIGURATION,
            message="OpenAI-compatible LLMs require llm.base_url and llm.model.",
            stage="visual_analysis",
            provider="openai_compatible",
            suggestion="Set both values in the TOML configuration.",
        )
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    if config.vision_enabled:
        for image in images:
            encoded = base64.b64encode(image.read_bytes()).decode("ascii")
            content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}})
    payload: dict[str, Any] = {
        "model": config.model,
        "messages": [{"role": "user", "content": content}],
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
    }
    if schema:
        payload["response_format"] = {"type": "json_schema", "json_schema": {"name": "result", "schema": schema}}
    key = _key(config)
    data = _post(config.base_url.rstrip("/") + "/chat/completions", payload, config, {"Authorization": f"Bearer {key}"} if key else {})
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ExtractorError(
            code=ErrorCode.PROVIDER_BAD_RESPONSE,
            message="OpenAI-compatible LLM returned an unexpected response.",
            stage="visual_analysis",
            provider="openai_compatible",
            suggestion="Confirm the endpoint implements /chat/completions.",
        ) from exc
    return _parse_json_if_possible(content, schema)


def _gemini(prompt: str, config: LLMConfig, images: Sequence[Path], schema: dict[str, Any] | None) -> Any:
    key = _key(config)
    if not config.model or not key:
        raise ExtractorError(
            code=ErrorCode.CONFIGURATION,
            message="Gemini requires llm.model and an API key environment variable.",
            stage="visual_analysis",
            provider="gemini",
            suggestion="Set llm.model, llm.api_key_env, and the environment variable.",
        )
    parts: list[dict[str, Any]] = [{"text": prompt}]
    if config.vision_enabled:
        for image in images:
            parts.append({"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(image.read_bytes()).decode("ascii")}})
    generation = {"temperature": config.temperature, "maxOutputTokens": config.max_tokens}
    if schema:
        generation.update({"responseMimeType": "application/json", "responseSchema": schema})
    payload = {"contents": [{"parts": parts}], "generationConfig": generation}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.model}:generateContent?key={key}"
    data = _post(url, payload, config, {})
    try:
        content = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ExtractorError(
            code=ErrorCode.PROVIDER_BAD_RESPONSE,
            message="Gemini returned an unexpected response.",
            stage="visual_analysis",
            provider="gemini",
            suggestion="Check the model name and Gemini API response format.",
        ) from exc
    return _parse_json_if_possible(content, schema)


def _ollama(prompt: str, config: LLMConfig, images: Sequence[Path]) -> str:
    if not config.model:
        raise ExtractorError(
            code=ErrorCode.CONFIGURATION,
            message="Ollama requires llm.model.",
            stage="visual_analysis",
            provider="ollama",
            suggestion="Set llm.model to an installed Ollama model.",
        )
    base_url = config.base_url or "http://localhost:11434"
    payload = {
        "model": config.model,
        "stream": False,
        "messages": [{"role": "user", "content": prompt, "images": [base64.b64encode(image.read_bytes()).decode("ascii") for image in images]}],
        "options": {"temperature": config.temperature, "num_predict": config.max_tokens},
    }
    data = _post(base_url.rstrip("/") + "/api/chat", payload, config, {})
    try:
        return str(data["message"]["content"])
    except (KeyError, TypeError) as exc:
        raise ExtractorError(
            code=ErrorCode.PROVIDER_BAD_RESPONSE,
            message="Ollama returned an unexpected response.",
            stage="visual_analysis",
            provider="ollama",
            suggestion="Confirm Ollama is running and the model supports chat.",
        ) from exc


def _parse_json_if_possible(content: str, schema: dict[str, Any] | None) -> str | dict[str, Any]:
    if not schema:
        return content
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise ExtractorError(
            code=ErrorCode.OUTPUT_VALIDATION,
            message="The LLM response was not valid JSON for the requested schema.",
            stage="validate_output",
            provider="llm",
            suggestion="Retry with a stricter prompt or disable structured output.",
        ) from exc
