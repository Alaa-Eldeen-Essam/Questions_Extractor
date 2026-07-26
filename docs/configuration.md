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

## Workflow presets

`workflow` selects the high-level multimodal recipe. The default is
`exam_study_pack`; the other built-in presets are `lecture_summary`,
`visual_document`, and `transcript_only`. Presets are ordered block contracts,
not separate applications. This lets the executor, UI, and future custom tasks
share one configuration format. Blocks can be disabled without changing the
other extraction channels; the manifest records the resulting stage as
`skipped` and writes an empty normalized artifact where appropriate.

```toml
[workflow]
id = "lecture_summary"

[workflow.blocks.ocr]
enabled = true
```

The same structure can be sent in an API request under
`options.workflow.blocks`. Only blocks present in the selected preset are
accepted, and misspelled block ids fail with an actionable validation error.
Inspect the available contracts with `GET /api/workflows`.

## Task instructions

The task block resolves to `questions`, `summary`, `visual_notes`, or `custom`.
`auto` inherits the selected workflow's task. Built-in summary and visual-note
tasks work without an LLM. A custom task requires both an instruction and an
enabled provider.

```toml
[task]
kind = "custom"
instruction = "Create a glossary with definitions and timestamps."
title = "Lecture glossary"
max_items = 5

[llm]
enabled = true
provider = "openrouter"
model = "openai/gpt-4o-mini"
api_key_env = "OPENROUTER_API_KEY"
```

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
