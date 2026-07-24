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
| 0 | Contracts, configuration, errors, fixtures, documentation | Complete |
| 1 | Deterministic CLI extraction pipeline | Complete |
| 2 | Speech-provider implementations | Planned |
| 3 | LLM-provider implementations | Planned |
| 4 | Question/answer intelligence | Planned |
| 5 | FastAPI backend | Planned |
| 6 | React/Vite frontend | Planned |
| 7 | Release documentation and packaging | Planned |
| 8 | Optional release hardening | Planned |

## Development

The backend uses a `src/` layout and Python 3.11+. Optional runtime groups
will be added as each phase introduces them. Phase 0 intentionally uses the
standard library for its contracts and self-checks.

See [docs/phase-0.md](docs/phase-0.md) and [docs/architecture.md](docs/architecture.md).

## Phase 1 quick start

Create and activate a virtual environment, then install the backend:

```bash
python -m venv .venv
python -m pip install -e backend
```

Install FFmpeg and Tesseract separately and add them to `PATH`. Then run:

```bash
python -m exam_extractor run lecture.mp4 --output outputs
```

For YouTube URLs, `yt-dlp` is installed with the backend. Phase 1 is
deterministic and does not require an LLM key. See [docs/phase-1.md](docs/phase-1.md)
for Windows/Linux activation, configuration, resume behavior, output layout,
and troubleshooting.

## Roadmap and self-hosting

- [Implementation roadmap](docs/roadmap.md)
- [Self-hosting guide](docs/self-hosting.md)
- [Docker Hub release plan](docs/docker-release.md)
- [Configuration reference](docs/configuration.md)
- [Provider contracts](docs/provider-contracts.md)

The final release README will contain tested Docker Hub and source-install
commands, provider setup, GPU setup, storage/backup guidance, troubleshooting,
upgrade instructions, and cleanup procedures. Until those phases are built,
the commands in `docs/self-hosting.md` are the target release contract rather
than a claim that the full application already exists.
