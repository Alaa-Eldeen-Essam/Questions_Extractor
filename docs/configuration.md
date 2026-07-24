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

The web UI and API provide Fast, Balanced, and High Accuracy profiles. Advanced
values override the selected profile. Input language defaults to auto-detect;
LLM output language defaults to `same` as the source. Low-confidence questions
are placed in the human-review queue using `review.threshold` (default `0.70`).

Example:

```toml
profile = "balanced"

[speech]
language = "auto"

[llm]
enabled = false
output_language = "same"

[review]
enabled = true
threshold = 0.70
```
