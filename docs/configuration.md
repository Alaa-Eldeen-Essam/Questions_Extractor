# Configuration

The example configuration is [config.default.toml](../examples/config.default.toml).

Safe defaults favor local, deterministic processing:

- captions or local speech fallback selected automatically;
- FFmpeg scene-change sampling;
- Tesseract OCR;
- LLM disabled;
- Markdown and JSON enabled;
- full transcript disabled unless explicitly requested.

The web UI accepts provider API keys at runtime for one job; runtime keys are
kept in memory, redacted from manifests and logs, and cleared after execution.
Environment-variable names remain an optional fallback for CLI/server use.
Never store a raw key in TOML, source control, job artifacts, or request logs.

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
gate_before_artifacts = false
```

## Output formats

```toml
[output]
markdown = true
json = true
word = true
pdf = true
csv = true
transcript = true
```

PDF and CSV are opt-in. PDF is generated with the standard library so the
Docker image does not need a separate PDF dependency; JSON and Markdown remain
the authoritative Unicode-preserving artifacts.

Set `gate_before_artifacts = true` when a human must approve or reject every
low-confidence question before final artifacts are generated. The job status
becomes `awaiting_review`; after all queued records are resolved, call
`POST /api/jobs/{job_id}/review/complete` to resume rendering.
