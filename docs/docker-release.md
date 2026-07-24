# Docker Hub release

## Image strategy

Publish one CPU-first image. Keep GPU support as a documented runtime option
or a separately tagged image only if the dependency size becomes a real issue.

```text
<dockerhub-user>/exam-video-extractor:latest
<dockerhub-user>/exam-video-extractor:0.1.3
<dockerhub-user>/exam-video-extractor:sha-<commit>
```

`latest` is for convenience. Version tags are the reproducible choice.

## Image contents

- `Dockerfile` is a multi-stage CPU-first build.
- The runtime user is non-root.
- FastAPI serves both the API and the compiled frontend.
- FFmpeg, Tesseract, and Poppler are installed in the runtime.
- `/data/outputs` and `/data/models` are persistent volumes.
- API keys are supplied at runtime, never baked into image layers.

## Compose

The compose file runs one container containing the backend and built frontend.

```yaml
services:
  extractor:
    image: <dockerhub-user>/exam-video-extractor:latest
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      - ./data:/data
    restart: unless-stopped
```

## GitHub Actions release

`.github/workflows/docker-publish.yml`:

1. Logs into Docker Hub using `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN`.
2. Builds the multi-stage image.
3. Publishes version, minor, `latest`, and SHA tags.

The CI workflow separately runs backend tests and the frontend build.

Docker Hub credentials must be stored as GitHub Actions secrets. The workflow
must never print them.
