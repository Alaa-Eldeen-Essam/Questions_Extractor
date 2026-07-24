# Phase 2: speech providers

Phase 2 adds a single normalized transcript interface for captions, local
`faster-whisper`, and OpenAI-compatible remote transcription endpoints.

## Install

Caption-only mode needs no extra package. Local speech needs the optional
dependency:

```bash
python -m pip install -e 'backend[speech]'
```

The first local run downloads the configured Whisper model into the provider's
normal cache. CPU uses `int8` automatically; CUDA uses `float16` automatically.
Override `speech.device` and `speech.compute_type` when your hardware needs a
different setting.

## Configuration

```toml
[speech]
provider = "auto"          # auto, faster_whisper, openai_compatible, none
model = "base.en"
language = "en"
device = "auto"            # auto, cpu, cuda
compute_type = "auto"      # auto, int8, float16, float32
translate = false
beam_size = 5
vad_filter = true
timeout_seconds = 120.0
```

`auto` uses captions when present. When captions are absent it uses local
`faster-whisper`; if that optional package is not installed, the job finishes
with a verbose warning and preserves the extracted audio.

For an OpenAI-compatible server:

```toml
[speech]
provider = "openai_compatible"
model = "whisper-1"
remote_base_url = "https://api.openai.com/v1"
remote_api_key_env = "OPENAI_API_KEY"
```

The API key is read only from the environment and is never written to a
manifest or log. The response must contain a JSON `text` field.

## Verification

```bash
python -m unittest discover -s backend/tests -p 'test_*.py'
```

The speech service is synchronous so it can be used by the CLI; the FastAPI
job runner in Phase 5 will execute it off the event loop.
