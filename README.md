# Exam Video Extractor

Cross-platform, local-first extraction of study material from YouTube videos,
local media, PDFs, and recorded lectures.

The project is being built in phases. Phase 0 defines the stable contracts for
sources, transcripts, frames, OCR, questions, jobs, configuration, errors, and
providers. Media processing and the FastAPI/React application are added in
later phases.

## Planned capabilities

- Captions-first speech extraction with local Whisper fallback.
- Pluggable OCR, visual-analysis, speech, and LLM providers.
- Optional LLM processing; deterministic extraction works without API keys.
- Markdown, JSON, transcript, and visual-evidence outputs.
- Verbose, actionable errors and resumable pipeline artifacts.
- Windows and Linux support.

## Phase status

| Phase | Scope | Status |
|---|---|---|
| 0 | Contracts, configuration, errors, fixtures, documentation | In progress |
| 1 | Deterministic CLI extraction pipeline | Planned |
| 2 | Speech-provider implementations | Planned |
| 3 | LLM-provider implementations | Planned |
| 4 | Question/answer intelligence | Planned |
| 5 | FastAPI backend | Planned |
| 6 | React/Vite frontend | Planned |
| 7 | Release documentation and packaging | Planned |

## Development

The backend uses a `src/` layout and Python 3.11+. Optional runtime groups
will be added as each phase introduces them. Phase 0 intentionally uses the
standard library for its contracts and self-checks.

See [docs/phase-0.md](docs/phase-0.md) and [docs/architecture.md](docs/architecture.md).
