# Configuration

The example configuration is [config.default.toml](../examples/config.default.toml).

Safe defaults favor local, deterministic processing:

- captions or local speech fallback selected automatically;
- FFmpeg scene-change sampling;
- Tesseract OCR;
- LLM disabled;
- Markdown and JSON enabled;
- full transcript disabled unless explicitly requested.

API keys are referenced by environment-variable name and are never stored in
TOML configuration or job artifacts.

Advanced profiles will be added in Phase 1 when providers become executable.
