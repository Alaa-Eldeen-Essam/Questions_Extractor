# Phase 3: optional LLM and vision providers

The provider-neutral LLM service supports deterministic no-op mode, OpenAI
Compatible chat APIs, Gemini, and Ollama. Images are sent only when the caller
explicitly supplies them and `vision_enabled` is true.

## Configuration

```toml
[llm]
enabled = false
provider = "none"          # none, openai_compatible, gemini, ollama
model = "..."
vision_model = "..."
base_url = "..."
# api_key_env is an optional CLI/server fallback. The UI accepts a runtime key.
temperature = 0.1
max_tokens = 2048
timeout_seconds = 120.0
retry_count = 1
vision_enabled = true
```

The OpenAI-compatible adapter targets `/chat/completions`, Gemini uses its
native `generateContent` endpoint, and Ollama targets `/api/chat`. The web UI
accepts an API key per job; runtime keys are held only in memory, redacted from
manifests and logs, and cleared after the job. Environment variables remain an
optional fallback for CLI/server configuration. Gemini uses the
`x-goog-api-key` header, not a URL query parameter.

Structured output is opt-in by passing a JSON schema to the service. Invalid
JSON becomes an actionable `output_validation` error.

## Verification

```bash
python -m unittest discover -s backend/tests -p 'test_*.py'
```

Phase 4 will use this service selectively for question extraction and visual
descriptions instead of sending every frame to a model.
