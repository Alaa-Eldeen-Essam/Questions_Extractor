# Exam Video Extractor

Exam Video Extractor converts YouTube videos, local media, recorded lectures, and
PDFs into study-ready evidence:

- timestamped captions or speech transcripts;
- sampled video/PDF frames and Tesseract OCR;
- questions, options, explicit answers, explanations, confidence, and evidence;
- Markdown and JSON artifacts;
- a FastAPI API with a React frontend;
- optional provider-neutral LLM enrichment.

It is local-first, CPU-first, and LLM-optional. It can use captions, local
faster-whisper, OpenAI-compatible speech APIs, OpenAI, OpenRouter, Gemini,
Ollama, or another compatible endpoint.

## Current release

The published v0.1.3 image is:

~~~text
docker.io/alaaeldeenessam/exam-video-extractor:0.1.3
~~~

The workflow also publishes 0.1, latest, and a commit-SHA tag. Use 0.1.3 for
reproducible deployments and latest only when automatic upgrades are desired.

## Zero-code Docker usage

You can use the published image directly without cloning the repository,
installing Python or Node.js, or reading the source code.

Pull the image:

~~~powershell
docker pull alaaeldeenessam/exam-video-extractor:0.1.3
~~~

Create persistent Docker volumes once:

~~~powershell
docker volume create exam_extractor_outputs
docker volume create exam_extractor_models
~~~

Start the application:

~~~powershell
docker run -d `
  --name exam-video-extractor `
  --restart unless-stopped `
  --publish 8000:8000 `
  --volume exam_extractor_outputs:/data/outputs `
  --volume exam_extractor_models:/data/models `
  alaaeldeenessam/exam-video-extractor:0.1.3
~~~

Open the application in a browser:

~~~text
http://localhost:8000
~~~

Check health and logs:

~~~powershell
Invoke-RestMethod http://localhost:8000/health/live
docker logs -f exam-video-extractor
~~~

Stop, start, or remove the container:

~~~powershell
docker stop exam-video-extractor
docker start exam-video-extractor
docker rm -f exam-video-extractor
~~~

The named volumes remain after removing the container. This means downloaded
Whisper models and generated outputs are reused by a later container. Delete
the volumes only when you intentionally want to erase them:

~~~powershell
docker volume rm exam_extractor_outputs exam_extractor_models
~~~

Linux users can run the same commands after changing the PowerShell line
continuation character to a single line or a Bash backslash.

### Direct Docker usage with runtime secrets

Secrets must never be added to the Docker image. An image is shareable and its
layers can be inspected; baking an API key into it would expose that key to
anyone who can pull the image. Pass secrets to the container only at runtime.

Create a file named .env in the directory from which you will run Docker:

~~~env
OPENAI_API_KEY=
GEMINI_API_KEY=
OPENROUTER_API_KEY=
HF_TOKEN=
~~~

Add only the keys you intend to use, then start the container with --env-file:

~~~powershell
docker run -d `
  --name exam-video-extractor `
  --restart unless-stopped `
  --publish 8000:8000 `
  --env-file .env `
  --volume exam_extractor_outputs:/data/outputs `
  --volume exam_extractor_models:/data/models `
  alaaeldeenessam/exam-video-extractor:0.1.3
~~~

The .env file stays on the host and is not part of the image. Protect it, do
not commit it to Git, and do not paste its contents into an issue or chat. If
no remote provider is needed, omit --env-file entirely; captions, OCR,
deterministic question extraction, and public local Whisper models work without
API keys.

The keys make providers available to the server; they do not automatically
select a provider. The UI's collapsed Advanced settings panel can select the
LLM provider, model, endpoint, output language, OCR language, and input speech
language. The default no-key path remains fully usable.

For a GUI-only Docker Desktop workflow, create the container in Docker Desktop,
map host port 8000 to container port 8000, add named volumes at
/data/outputs and /data/models, and add the same environment variables in the
container's Environment variables panel.

## Processing pipeline

Each job is resumable and runs these stages:

~~~text
source
  -> acquire media, captions, and metadata
  -> captions or speech transcription
  -> video/PDF frame extraction
  -> Tesseract OCR
  -> deterministic question extraction
  -> optional LLM enrichment
  -> Markdown, JSON, transcript, and evidence artifacts
~~~

If a job is interrupted, rerunning the same source and configuration reuses
completed stages.

## Docker image layers versus AI model weights

A large docker pull is expected. The image contains:

- Python and application dependencies;
- FFmpeg;
- Tesseract OCR;
- Poppler PDF tools;
- the faster-whisper Python package;
- the compiled frontend.

The image does not contain Whisper model weights. The runtime sets:

~~~text
HF_HOME=/data/models
~~~

A Whisper model is downloaded only when a job actually uses local speech and
there are no usable captions:

1. the default local model is base.en;
2. faster-whisper downloads the model from Hugging Face on first use;
3. the files are cached in /data/models;
4. subsequent jobs reuse the cache.

The default Compose file stores that cache in the named Docker volume
extractor_models. docker compose down preserves it; docker compose down -v
deletes it.

No local model is downloaded for:

- a captioned video whose captions are used;
- speech none or captions;
- remote OpenAI-compatible speech;
- PDFs, which do not have a speech stage.

Remote speech and LLM providers use their own models outside this container and
may receive your material over the network.

## Docker Hub installation

### Requirements

- Docker Engine or Docker Desktop 24+;
- Docker Compose v2;
- at least 8 GB RAM for normal CPU work;
- disk space for media, outputs, and optional model weights;
- network access for YouTube, remote providers, and first-time model download.

Python and Node.js are not required for the published image.

### Run the published image

Clone the repository and create the runtime environment file.

Windows PowerShell:

~~~powershell
git clone https://github.com/Alaa-Eldeen-Essam/Questions_Extractor.git
cd Questions_Extractor
Copy-Item .env.example .env
~~~

Linux:

~~~bash
git clone https://github.com/Alaa-Eldeen-Essam/Questions_Extractor.git
cd Questions_Extractor
cp .env.example .env
~~~

Edit .env. Keep unused keys empty:

~~~env
OPENAI_API_KEY=
GEMINI_API_KEY=
OPENROUTER_API_KEY=
HF_TOKEN=

# Optional:
# EXTRACTOR_IMAGE=alaaeldeenessam/exam-video-extractor:0.1.3
# EXTRACTOR_PORT=8000
# EXTRACTOR_WORKERS=2
# MAX_UPLOAD_BYTES=4294967296
~~~

Windows PowerShell:

~~~powershell
$env:EXTRACTOR_IMAGE = "alaaeldeenessam/exam-video-extractor:0.1.3"
docker pull $env:EXTRACTOR_IMAGE
docker compose up -d --no-build
~~~

Linux:

~~~bash
export EXTRACTOR_IMAGE=alaaeldeenessam/exam-video-extractor:0.1.3
docker pull "$EXTRACTOR_IMAGE"
docker compose up -d --no-build
~~~

Open:

~~~text
http://localhost:8000
~~~

Check health:

~~~powershell
Invoke-RestMethod http://localhost:8000/health/live
~~~

~~~bash
curl http://localhost:8000/health/live
~~~

Expected response:

~~~json
{"status":"ok"}
~~~

### Build locally instead

From the repository root:

~~~powershell
docker compose up -d --build
~~~

This installs runtime packages but still does not download Whisper weights.
Those are downloaded only during a local speech job.

### Manage Compose

~~~powershell
docker compose ps
docker compose logs -f exam-extractor
docker compose restart
docker compose down
~~~

The default Compose volumes are:

~~~text
extractor_outputs -> /data/outputs
extractor_models  -> /data/models
~~~

Inspect storage:

~~~powershell
docker compose exec exam-extractor sh -lc "du -sh /data/outputs /data/models"
~~~

Delete containers and all generated data/models intentionally:

~~~powershell
docker compose down -v
~~~

For host-visible storage, replace the volume entries in docker-compose.yml with:

~~~yaml
volumes:
  - ./data/outputs:/data/outputs
  - ./data/models:/data/models
~~~

Create the host directories first. Do not use down -v unless deleting the
cached models and outputs is intentional.

## Web interface usage

1. Open http://localhost:8000.
2. Paste a YouTube URL, or choose Upload file.
3. Select a speech mode.
4. Optionally expand Advanced settings to select profiles, languages, an LLM
   provider/model, or visual analysis.
5. Click Extract study material.
6. Monitor acquire, speech, frames, OCR, questions, and render.
7. Download Markdown, JSON, Word, transcript, and review artifacts when enabled.

Uploaded extensions are .mp4, .mkv, .webm, .mov, .m4a, .mp3, .wav, .flac, and
.pdf. MAX_UPLOAD_BYTES defaults to 4 GiB.

A host path typed into a browser is not automatically visible inside Docker. Use
the upload control, bind-mount the directory, or pass a path that exists inside
the container. YouTube acquisition runs inside the container using yt-dlp and
tries to obtain English manual or automatic WebVTT captions. If YouTube
rate-limits yt-dlp subtitle requests, the application automatically queries the
video transcript, prefers English, and otherwise uses the first available
manual or auto-generated language. The actual language is recorded in
`source/metadata.json`, `transcript.json`, and the transcript segments; it is
never silently labeled as English. A video with only Arabic captions therefore
produces an Arabic transcript unless an optional translation/LLM step is
enabled.

Playlist-safe YouTube handling

You can paste a normal watch URL even when it includes `list=`, `index=`, or
`t=` parameters. The extractor forces single-video acquisition, so it does not
download the whole playlist. A visible YouTube transcript is used directly;
there is no separate subtitle-download action for the user. The fallback uses
the public `youtube-transcript-api` package, then skips local Whisper when a
transcript is found. If no transcript exists in any language, `auto` falls
back to local Whisper as documented below.

## Speech modes

The pipeline is captions-first. Captions are used whenever available, even
when the fallback is local or remote speech.

| Setting | Behavior | Local model download | Recommended use |
|---|---|---:|---|
| auto | captions, then local faster-whisper if absent | first fallback run | normal use |
| faster_whisper | captions, then local Whisper | yes, cached | local/private processing |
| openai_compatible | captions, then remote audio transcription | no | hosted speech |
| captions | captions only; no audio extraction | no | fast captioned videos |
| none | practical captions/visual-only mode | no | OCR and visual review |

The default model is base.en. tiny.en is lighter and faster; larger models need
more disk, RAM, and time. CPU selects int8 automatically. The published image
is CPU-first; CUDA requires a separately prepared GPU runtime.

### Processing profiles

The profile selector changes actual backend settings. Advanced values override
the selected profile.

| Profile | Speech | Frames | Resolution | Use when |
|---|---|---|---:|---|
| Fast | tiny.en, beam 1 | 30-second interval | 480p | quick previews and low-resource machines |
| Balanced | base.en, beam 5 | scene change, 10-second fallback | 720p | recommended default |
| High Accuracy | small.en, beam 8 | dense scene-change sampling, 5-second fallback | 1080p | important or visually dense material |

High Accuracy does not silently enable a paid LLM. Enable LLM enrichment explicitly
in Advanced settings.

Example TOML:

~~~toml
[speech]
provider = "auto"
model = "base.en"
language = "auto"
device = "auto"
compute_type = "auto"
vad_filter = true
beam_size = 5
~~~

Remote speech example:

~~~toml
[speech]
provider = "openai_compatible"
model = "whisper-1"
remote_base_url = "https://api.openai.com/v1"
remote_api_key_env = "OPENAI_API_KEY"
~~~

Remote audio leaves the local machine. Review provider privacy, quota, and
retention policies.

## Frames, OCR, and PDFs

Tesseract OCR is included and defaults to English eng data. Frames are retained
as evidence so OCR can be reviewed against the source image.

Default settings:

~~~toml
[frames]
method = "scene_change"
scene_threshold = 0.15
fallback_interval_seconds = 10.0
max_resolution = 720
~~~

Use interval sampling for predictable timing. For long lectures, 30 or 60
seconds reduces CPU, disk, and OCR cost. Use a shorter interval or scene-change
sampling when slides change frequently. A larger max_resolution helps small
on-screen text but increases processing time and storage.

PDF pages are rendered by Poppler and passed through the same frame/OCR path.
PDF jobs do not produce speech transcripts.

## Question and LLM behavior

The deterministic extractor recognizes common question stems, option lines,
explicit answer labels, and explanation phrases in transcript/OCR evidence. It
does not invent missing answers. Poor speech or OCR can therefore reduce
question quality.

LLM processing is disabled by default. When enabled, deterministic extraction
runs first. The LLM is used when there are no records or low-confidence records;
selected low-confidence frames may be provided for visual context. Structured
JSON output is validated and provider errors become actionable warnings.

Current LLM providers:

| Provider | Endpoint style | Required configuration |
|---|---|---|
| none | no network call | none |
| openai | /chat/completions | model, OPENAI_API_KEY |
| openai_compatible | /chat/completions | base_url, model, api_key_env |
| openrouter | /chat/completions | model, OPENROUTER_API_KEY |
| gemini | native generateContent | model, api_key_env |
| ollama | /api/chat | base_url, model |
| huggingface | OpenAI-compatible /chat/completions | base_url, model, HF_TOKEN |

OpenAI-compatible configuration can be used for OpenAI, OpenRouter, and
self-hosted compatible servers.

OpenRouter example:

~~~toml
[llm]
enabled = true
provider = "openai_compatible"
model = "your/openrouter-model"
base_url = "https://openrouter.ai/api/v1"
api_key_env = "OPENROUTER_API_KEY"
vision_enabled = true
temperature = 0.1
max_tokens = 2048
~~~

Gemini example:

~~~toml
[llm]
enabled = true
provider = "gemini"
model = "your-gemini-model"
api_key_env = "GEMINI_API_KEY"
vision_enabled = true
~~~

Ollama from Windows/macOS Docker:

~~~toml
[llm]
enabled = true
provider = "ollama"
model = "your-installed-ollama-model"
base_url = "http://host.docker.internal:11434"
~~~

The Ollama model must already exist on the Ollama host. On Linux, use a
reachable host address or configure a host-gateway mapping.

The UI exposes speech selection, real processing profiles, language selection,
LLM provider/model controls, and visual-analysis controls in the collapsed
Advanced settings panel. API keys are never sent to or displayed by the browser.

## Language handling

Input language controls captions and speech recognition. `auto` is the default
and preserves the detected transcript language. Output language controls the
language requested from the optional LLM; `same` preserves the source language.
For example, Arabic captions with output language English require an enabled
translation-capable LLM. OCR language is independent and supports `eng`, `ara`,
and `eng+ara` when the corresponding Tesseract packs are installed.

## Human review

Questions below the default confidence threshold of `0.70`, questions without a
detected answer, and questions with extraction warnings are marked
`needs_review`. Completed jobs show a Human review panel where you can edit the
prompt, options, answer, explanation, and reviewer note, then approve, edit, or
reject the record. Review state is persisted in `review.json`, `questions.json`,
`extraction.json`, `extraction.md`, and the Word artifact.

## Advanced API

The server is available at http://localhost:8000.

~~~text
GET  /health/live
GET  /health/ready
GET  /api/providers
GET  /api/settings/options
GET  /api/config/default
POST /api/jobs
POST /api/jobs/file
GET  /api/jobs/{job_id}
GET  /api/jobs/{job_id}/events
POST /api/jobs/{job_id}/cancel
GET  /api/jobs/{job_id}/review
PATCH /api/jobs/{job_id}/review/{question_id}
POST /api/jobs/{job_id}/review/complete
GET  /api/jobs/{job_id}/artifacts/{path}
~~~

Example request:

~~~json
{
  "source": "https://www.youtube.com/watch?v=VIDEO_ID",
  "profile": "high_accuracy",
  "options": {
    "speech": {
      "provider": "auto",
      "model": "base.en",
      "language": "auto"
    },
    "frames": {
      "method": "interval",
      "fallback_interval_seconds": 30.0,
      "max_resolution": 900
    },
    "ocr": {
      "confidence_threshold": 0.55
    },
    "llm": {
      "enabled": true,
      "provider": "openai_compatible",
      "model": "your-model",
      "base_url": "https://api.openai.com/v1",
      "api_key_env": "OPENAI_API_KEY",
      "vision_enabled": true,
      "output_language": "same"
    },
    "output": {
      "markdown": true,
      "json": true,
      "transcript": true,
      "include_frame_links": true
    }
  }
}
~~~

PowerShell request:

~~~powershell
$payload = @{
  source = "https://www.youtube.com/watch?v=VIDEO_ID"
  profile = "high_accuracy"
  options = @{
    speech = @{ provider = "auto"; model = "base.en" }
    frames = @{ method = "interval"; fallback_interval_seconds = 30.0; max_resolution = 900 }
    output = @{ markdown = $true; json = $true; transcript = $true }
  }
}
$response = Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/jobs -ContentType "application/json" -Body ($payload | ConvertTo-Json -Depth 10)
$response
Invoke-RestMethod "http://localhost:8000/api/jobs/$($response.job_id)"
~~~

Do not put raw API keys in JSON. api_key_env names an environment variable
available to the server; the actual key remains in .env or a secret store.

## Source installation

Docker is recommended. Source installation is useful for development or custom
providers.

### Windows

Install Python 3.11+, Git, FFmpeg, Tesseract, Poppler, and Node.js 20+. Ensure
ffmpeg, ffprobe, tesseract, and pdftoppm are on PATH. The project supports
FFMPEG_BIN, FFPROBE_BIN, TESSERACT_BIN, and PDFTOPPM_BIN overrides where needed.

~~~powershell
git clone https://github.com/Alaa-Eldeen-Essam/Questions_Extractor.git
cd Questions_Extractor
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install -e "backend[web,speech]"
npm --prefix frontend ci
npm --prefix frontend run build
$env:FRONTEND_DIST = "frontend/dist"
uvicorn exam_extractor.api:app --host 127.0.0.1 --port 8000
~~~

### Linux

~~~bash
sudo apt-get update
sudo apt-get install -y ffmpeg tesseract-ocr poppler-utils
git clone https://github.com/Alaa-Eldeen-Essam/Questions_Extractor.git
cd Questions_Extractor
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e 'backend[web,speech]'
npm --prefix frontend ci
npm --prefix frontend run build
uvicorn exam_extractor.api:app --host 127.0.0.1 --port 8000
~~~

CLI examples:

~~~bash
python -m exam_extractor run "https://www.youtube.com/watch?v=VIDEO_ID" --output outputs --transcript --verbose
python -m exam_extractor run lecture.mp4 --config examples/config.default.toml --output outputs --transcript
python -m exam_extractor run lecture-notes.pdf --output outputs --verbose
python -m exam_extractor run lecture.mp4 --output outputs --force
~~~

## Output artifacts

Each job may contain:

~~~text
manifest.json       status, configuration, warnings, and errors
source/             media, captions, metadata, and acquisition state
audio/audio.wav     normalized audio when speech needs it
frames/             retained JPEG evidence
frames.json         frame timestamps and methods
ocr.json            OCR text, confidence, and frame references
transcript.json     timestamped transcript segments and words
questions.json      structured questions and evidence
review.json         review queue, decisions, and confidence summary
extraction.json     combined machine-readable output
extraction.md       human-readable study output
extraction.docx     Word study document with text and embedded visual evidence
transcript.md       optional readable transcript
~~~

extraction.md is the primary study file. extraction.json is for automation or
custom frontends. Review source frames and transcript evidence for low-confidence
results.

## Recommended combinations

| Goal | Speech | LLM | Result |
|---|---|---|---|
| fast captioned video | none/captions | none | captions + frames + OCR; no model |
| private general processing | auto | none | captions or local Whisper |
| local speech control | faster_whisper | none | local cached model |
| hosted speech | openai_compatible | optional | audio sent to remote service |
| messy/ambiguous questions | any | enabled | deterministic extraction plus enrichment |
| visual PDF review | none | none | PDF pages + OCR |
| audio-only lecture | auto or remote | optional | transcript/questions without frames |

Recommended progression:

1. Start with captions/auto and LLM disabled.
2. Inspect extraction.md, transcript.json, and ocr.json.
3. If speech is missing, choose local faster_whisper or remote speech.
4. Enable an LLM only when deterministic extraction needs help.
5. Increase resolution or sampling density only when needed.

## Security and privacy

- Never commit .env, API keys, tokens, lecture files, or generated outputs.
- Keys are read from environment variables and are not written to manifests.
- Remote providers receive the data required for their request.
- Outputs may contain private transcripts, frames, OCR, and source metadata.
- The current application has no authentication. Do not expose port 8000 publicly
  without authentication, TLS, and a reverse proxy.
- The container runs as a non-root extractor user.
- privacy.retention_days is metadata only; automatic deletion is not enabled.

## Troubleshooting

### Pull is large or slow

The image contains OS libraries, FFmpeg, Poppler, Tesseract, Python packages,
and the frontend. Whisper weights are separate. Check model storage after a
local speech job:

~~~powershell
docker compose exec exam-extractor sh -lc "du -sh /data/models"
~~~

### First local-Whisper job is slow

The model is downloading to /data/models. Keep extractor_models. Use tiny.en
for a smaller CPU test, or use captions/remote speech.

### No transcript

Check `source/metadata.json` and `manifest.json` warnings. The fallback records
the language it found. If the video has no transcript in any language, use
`auto` or `faster_whisper`; an English transcript cannot be produced from an
Arabic-only caption track unless translation is enabled. For remote speech,
check endpoint, model, key environment variable, quota, and upload limits.

### No questions

There may be no transcript/readable OCR, or wording may not match deterministic
question patterns. Review transcript.json and ocr.json, sample frames more
densely, increase resolution, or enable LLM enrichment. Missing answers are not
invented.

### OCR is inaccurate

Use interval sampling, a shorter interval, higher max_resolution, and a correct
Tesseract language pack. The release image includes English OCR data.

### Ollama is unreachable

localhost inside a container means the container. On Windows/macOS use
http://host.docker.internal:11434. On Linux use a reachable host address or
host-gateway configuration.

### Port conflict

~~~powershell
$env:EXTRACTOR_PORT = "8001"
docker compose up -d
~~~

Then open http://localhost:8001.

### Outputs/models disappeared

Avoid docker compose down -v. Inspect named volumes:

~~~powershell
docker volume ls | Select-String extractor
~~~

## Release and CI

The Docker workflow runs on tags matching v*.*.* and requires these GitHub
Actions secrets:

~~~text
DOCKERHUB_USERNAME
DOCKERHUB_TOKEN
~~~

Publish a new release:

~~~bash
git tag -a v0.1.3 -m "Release v0.1.3"
git push origin main
git push origin v0.1.3
~~~

Monitor the workflow:

~~~bash
gh run list --workflow docker-publish.yml --limit 5
gh run watch RUN_ID
~~~

## Verification

~~~bash
python -m unittest discover -s backend/tests -p "test_*.py"
npm --prefix frontend run build
docker compose up -d --build
~~~

See docs/ for architecture, provider contracts, phase history, self-hosting, and
release details.
