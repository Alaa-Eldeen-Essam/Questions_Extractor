# Docker Hub release plan

## Image strategy

Publish one CPU-first image. Keep GPU support as a documented runtime option
or a separately tagged image only if the dependency size becomes a real issue.

```text
<dockerhub-user>/exam-video-extractor:latest
<dockerhub-user>/exam-video-extractor:0.1.0
<dockerhub-user>/exam-video-extractor:sha-<commit>
```

`latest` is for convenience. Version tags are the reproducible choice.

## Image requirements

- Multi-stage build.
- Non-root runtime user.
- No API keys baked into image layers.
- Healthcheck using the API readiness endpoint.
- Stable `/data` volume for jobs, models, outputs, and cache.
- Environment-variable configuration.
- Explicit image labels for version and commit.
- No downloaded user media in the image.

## Compose requirements

The first public compose file should run one container containing the backend
and built frontend. Split frontend/backend containers only if deployment needs
it; a single image keeps self-hosting simple.

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

The release workflow should:

1. Run Python tests and frontend tests.
2. Build the frontend.
3. Build the Docker image.
4. Run a container smoke test.
5. Scan the image.
6. Generate an SBOM.
7. Push immutable commit and version tags to Docker Hub.
8. Publish GitHub release notes.

Docker Hub credentials must be stored as GitHub Actions secrets. The workflow
must never print them.
