# Phase 1 — deterministic CLI pipeline

## Delivered

- `python -m exam_extractor run <source>` CLI.
- YouTube URL detection through `yt-dlp`.
- Local video/audio source detection and acquisition.
- WebVTT/SRT caption parsing.
- FFmpeg audio extraction for future speech providers.
- FFmpeg scene-change or interval frame extraction.
- Tesseract OCR over retained frames.
- Markdown, JSON, transcript, and manifest artifacts.
- Stable job folders for resume/re-run behavior.
- No-LLM operation by default.
- Verbose user-facing errors and suggestions.

## Installation

From the repository root:

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -e backend
```

Linux:

```bash
source .venv/bin/activate
python -m pip install -e backend
```

Install FFmpeg and Tesseract separately and ensure both are on `PATH`.
Overrides are available through `FFMPEG_BIN`, `FFPROBE_BIN`, and
`TESSERACT_BIN`.

## Examples

Process local video without an LLM:

```bash
python -m exam_extractor run lecture.mp4 --output outputs
```

Process a YouTube URL and include a separate transcript file:

```bash
python -m exam_extractor run "https://www.youtube.com/watch?v=VIDEO_ID" \
  --output outputs --transcript
```

Use a custom configuration:

```bash
python -m exam_extractor run lecture.mp4 \
  --config examples/config.default.toml \
  --output outputs
```

Repeat an interrupted job. Use the same source, output root, and options:

```bash
python -m exam_extractor run lecture.mp4 --output outputs --transcript
```

Force a clean rerun:

```bash
python -m exam_extractor run lecture.mp4 --output outputs --force
```

## Output

Each job produces a stable folder containing:

```text
manifest.json
source/
audio/
frames/
frames.json
ocr.json
transcript.json
extraction.json
extraction.md
transcript.md       # only with --transcript
```

Phase 1 intentionally does not transcribe audio without captions. It extracts
`audio.wav` and records a clear warning so Phase 2 can add Whisper and remote
speech providers without changing the output contract.

## Verification

```bash
python -m unittest discover -s backend/tests -p "test_*.py"
python -m compileall backend/src
```
