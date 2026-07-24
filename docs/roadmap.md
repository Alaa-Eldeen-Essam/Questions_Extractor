# Implementation roadmap

This roadmap turns the Phase 0 contracts into a self-hostable, portfolio-ready
application. Every phase has a verification gate. The next phase starts only
after its gate passes on Windows and Linux where applicable.

## Phase 1 — deterministic CLI pipeline

### Goal

Accept YouTube URLs and local media and produce reliable raw artifacts without
requiring an LLM or API key.

### Deliverables

- `exam-extractor run <source>` command.
- YouTube and local video/audio adapters.
- Metadata and caption acquisition.
- FFmpeg audio and keyframe extraction.
- Tesseract OCR implementation.
- Caption parser and normalized transcript writer.
- Markdown, JSON, and evidence-frame output.
- Per-stage artifact caching and resume support.
- Progress logs and actionable errors.

### Verification gate

- Run a captioned YouTube video.
- Run a video with no captions.
- Run a local MP4 and local audio file.
- Run on Windows and Linux.
- Re-run an interrupted job without repeating completed stages.
- Verify every generated frame link exists.
- Verify `--llm none` works without provider keys.

### Exit criteria

The CLI can create a useful raw extraction package without any cloud account.

## Phase 2 — speech providers (complete)

### Goal

Make speech extraction elastic while retaining a dependable local default.

### Deliverables

- Caption provider.
- `faster-whisper` local provider.
- CPU and CUDA device detection.
- Model download/cache management.
- Optional OpenAI-compatible speech provider.
- Language and translation settings.
- Word and segment timestamps.
- Audio-only processing path.

### Verification gate

- CPU-only machine.
- NVIDIA GPU machine.
- Missing audio stream.
- Unsupported language.
- Partial captions.
- Provider timeout and rate-limit simulation.
- Model download failure with recovery instructions.

### Exit criteria

The user can choose automatic, local, or remote speech extraction and receives
the same normalized transcript schema.

## Phase 3 — LLM and visual providers (in progress)

### Goal

Add optional AI organization and visual interpretation without coupling the
application to one vendor.

### Deliverables

- No-op provider for fully deterministic mode.
- OpenAI-compatible text/vision adapter.
- Gemini adapter.
- Ollama adapter.
- Configurable model and endpoint selection.
- Structured JSON output with schema validation.
- Context chunking and retry policy.
- Provider capability discovery.
- Vision escalation only for low-confidence or ambiguous frames.

### Verification gate

- Run with no LLM configured.
- Run with an OpenAI-compatible endpoint.
- Run with Gemini.
- Run with Ollama.
- Test invalid keys, timeouts, rate limits, malformed JSON, and unsupported
  vision capabilities.
- Confirm secrets never appear in logs or output artifacts.

### Exit criteria

Changing providers requires configuration changes, not pipeline-code changes.

## Phase 4 — question, answer, and explanation intelligence

### Goal

Turn raw multimodal evidence into a study-ready question bank.

### Deliverables

- Question boundary detection.
- Option extraction and normalization.
- Spoken-answer matching.
- On-screen-answer matching.
- Explanation extraction.
- Visual descriptions for diagrams and tables.
- Cross-video duplicate detection.
- Evidence links for every extracted claim.
- Confidence scoring.
- Audio/OCR/LLM conflict detection.
- Optional full transcript export.

### Verification gate

- Question shown only on-screen.
- Answer spoken only in audio.
- Answer shown after a countdown.
- Question spanning multiple frames.
- Duplicate questions across videos.
- Contradictory answer sources.
- Low-confidence OCR requiring human review.

### Exit criteria

The generated Markdown clearly separates observed evidence, inferred answers,
explanations, uncertainty, and timestamps.

## Phase 5 — FastAPI application backend

### Goal

Expose the same pipeline through a stable local API.

### Deliverables

- FastAPI application.
- Job creation, status, cancellation, and artifact endpoints.
- Server-Sent Events progress stream.
- Local job/artifact storage.
- Configuration/profile endpoints.
- Provider discovery endpoint.
- Health and readiness endpoints.
- OpenAPI documentation.
- Request validation and safe file handling.

### Verification gate

- Submit URL jobs through the API.
- Submit local files through the API.
- Observe progress events.
- Restart the API during a job and resume it.
- Cancel a job.
- Download all artifacts.
- Run multiple jobs without cross-contaminating outputs.

### Exit criteria

The CLI and API produce equivalent results from the same pipeline code.

## Phase 6 — portfolio-quality frontend

### Goal

Create a polished, demonstrable UI that makes the multimodal pipeline visible.

### User experience

The main screen should show:

- Clear product title and short value proposition.
- URL/file intake area.
- Fast, balanced, high-accuracy, and advanced profiles.
- Provider/model selectors.
- Live stage progress.
- Verbose but readable error panel.
- Question list and search.
- Split view: question/answer on the left, visual evidence on the right.
- Timeline scrubber with frame thumbnails.
- Markdown preview.
- Download buttons for Markdown, JSON, transcript, and ZIP.
- Confidence and conflict badges.

### Visual direction

- React, Vite, and TypeScript.
- Responsive desktop-first layout.
- Dark and light themes.
- Strong typography and generous spacing.
- Accessible keyboard navigation.
- Clear empty, loading, success, warning, and failure states.
- Minimal animation used only for progress and transitions.

### Portfolio features

- Live pipeline visualization.
- Provider switching without code changes.
- Evidence traceability from answer back to frame/audio timestamp.
- “No LLM required” mode.
- Visible error recovery and resume behavior.
- Sample demo job that works without user API keys.

### Verification gate

- Test on Chrome and Firefox.
- Test narrow and wide layouts.
- Test keyboard navigation.
- Test job failure and retry states.
- Test large Markdown outputs.
- Test API restart while the UI is open.
- Test that no API key is sent to the browser.

### Exit criteria

The application is understandable within one minute when shown in a portfolio
demo and remains usable for long-running extraction jobs.

## Phase 7 — Docker Hub release and self-hosting

### Goal

Allow a new user to install and run the system independently from GitHub or
Docker Hub.

### Deliverables

- Production multi-stage Dockerfile.
- Separate development Dockerfile or compose profile.
- Docker Compose file for the backend and frontend.
- Healthcheck endpoint.
- Persistent volumes for jobs, models, outputs, and cache.
- CPU image as the default.
- Documented optional GPU configuration.
- Docker Hub image naming and version tags.
- GitHub Actions build/test/publish workflow.
- SBOM and image vulnerability scan.
- Release notes and upgrade instructions.

### Suggested image layout

```text
docker.io/<dockerhub-user>/exam-video-extractor:latest
docker.io/<dockerhub-user>/exam-video-extractor:0.1.0
docker.io/<dockerhub-user>/exam-video-extractor:sha-<commit>
```

### Verification gate

- Build the image from a clean checkout.
- Run it without a local Python installation.
- Run it with no API keys.
- Persist and reload a completed job.
- Run it with a mounted output directory.
- Verify healthcheck behavior.
- Test the documented GPU path when available.
- Pull the published image on another machine.

### Exit criteria

A new user can run the application by following the README without asking the
author for undocumented setup steps.

## Phase 8 — release hardening

This phase is optional but recommended before public promotion.

- Pin and audit dependencies.
- Add versioned migration strategy for job artifacts.
- Add structured JSON logs.
- Add privacy and retention settings.
- Add source-license and usage warnings.
- Add performance benchmarks.
- Add a small public sample dataset/media fixture.
- Add a troubleshooting decision tree.
- Add a contribution guide and issue templates.

## Optimization rules

- Do not send every frame to an LLM.
- Cache every expensive artifact.
- Keep deterministic extraction independent from AI interpretation.
- Escalate only uncertain OCR, visuals, or conflicting answers.
- Use one OpenAI-compatible adapter for compatible providers.
- Add native provider adapters only when protocol behavior differs materially.
- Keep Docker CPU-first; add GPU support without making GPU mandatory.
- Do not add distributed workers, Kubernetes, or cloud storage until local jobs
  demonstrably need them.
