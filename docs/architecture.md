# Architecture

## Boundaries

The project has five boundaries:

1. **Sources** identify and acquire YouTube, local media, PDFs, and future lecture inputs.
2. **Extraction providers** produce normalized speech, frames, OCR, and visual evidence.
3. **Pipeline stages** combine artifacts without knowing vendor SDK details.
4. **LLM providers** optionally organize and validate extracted evidence.
5. **Views** render the same domain records as Markdown, JSON, HTML, or future formats.

The deterministic path must work with `llm.enabled = false`.

## Provider rule

Stages depend on protocols in `exam_extractor.providers.base`, never on OpenAI,
Gemini, Ollama, or OCR-specific classes. Provider selection belongs in config
and the provider registry.

## Artifact rule

Every expensive stage writes an artifact before the next stage starts. This
allows resume, debugging, and provider comparison without reprocessing the
source media.

## Future API boundary

FastAPI controllers will create jobs and stream progress. They will not contain
FFmpeg, OCR, transcription, or LLM logic. The CLI will call the same pipeline
runner.
