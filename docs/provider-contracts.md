# Provider contracts

Phase 0 defines small protocols for source, speech, OCR, vision, and LLM
providers. A provider implementation must expose `ProviderInfo` and implement
only the capability it supports.

The OpenAI-compatible adapter will cover services that expose a compatible
HTTP interface, including OpenRouter, Ollama, vLLM, and compatible Hugging Face
endpoints. Native adapters will be used where a service has materially different
audio or vision behavior.

Providers should raise `ExtractorError` with a stable `ErrorCode`, a stage,
retryability, and a user-facing suggestion. Secrets must not be included in
messages, details, or logs.
