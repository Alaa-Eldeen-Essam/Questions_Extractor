# Self-hosting guide

This guide describes the current Docker and source installation paths.

## Option A — Docker Hub installation

Prerequisites:

- Docker Engine 24 or newer.
- Docker Compose v2.
- At least 8 GB RAM for CPU processing.
- Additional disk space for downloaded media and local speech models.

Create a working directory:

```bash
mkdir exam-video-extractor
cd exam-video-extractor
mkdir -p data/models data/outputs
```

Create `.env`:

```env
EXTRACTOR_OUTPUT_DIR=/data/outputs
OPENAI_API_KEY=
GEMINI_API_KEY=
OPENROUTER_API_KEY=
```

Start the application:

```bash
docker compose up -d
```

Open:

```text
http://localhost:8000
```

Inspect logs:

```bash
docker compose logs -f
```

Stop the application:

```bash
docker compose down
```

The mounted `data/` directory retains jobs, models, outputs, and caches across
container upgrades.

## Option B — Run from source

Prerequisites:

- Python 3.11 or newer.
- FFmpeg available on `PATH`.
- Tesseract available on `PATH`.
- Poppler available on `PATH` for document work.
- Git.
- Node.js 20 or newer for the frontend.

Clone and install the backend:

```bash
git clone https://github.com/<owner>/exam-video-extractor.git
cd exam-video-extractor
python -m venv .venv
```

Activate the environment.

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Linux:

```bash
source .venv/bin/activate
```

Install the backend:

```bash
python -m pip install -e "backend[web]"
```

Install the frontend:

```bash
cd frontend
npm ci
npm run build
cd ..
```

Start the backend:

```bash
uvicorn exam_extractor.api:app --host 127.0.0.1 --port 8000
```

## Provider setup

The application must run with no provider API key by using captions, local
Whisper, Tesseract, and `llm.enabled = false`.

Cloud providers are optional. Add only the key for the provider you want to
use, then select the provider in the UI or TOML profile.

Never put keys in source files, committed configuration, browser code, or
generated artifacts.

## Troubleshooting

The final guide will include a decision tree for:

- FFmpeg not found.
- Tesseract not found.
- Whisper model download failure.
- No CUDA device.
- Insufficient disk space.
- Provider authentication failure.
- Rate limiting.
- Unsupported video or PDF.
- Job resume and cleanup.
