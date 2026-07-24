# syntax=docker/dockerfile:1
FROM node:22-alpine AS frontend
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    EXTRACTOR_OUTPUT_DIR=/data/outputs \
    FRONTEND_DIST=/app/frontend-dist \
    HF_HOME=/data/models
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg tesseract-ocr poppler-utils \
    && rm -rf /var/lib/apt/lists/*
COPY backend /app/backend
RUN python -m pip install --no-cache-dir "/app/backend[web,speech]"
COPY --from=frontend /build/frontend/dist /app/frontend-dist
RUN mkdir -p /data/outputs /data/models
RUN useradd --create-home --uid 10001 extractor \
    && chown -R extractor:extractor /app /data
USER extractor
VOLUME ["/data/outputs", "/data/models"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=3)"
CMD ["uvicorn", "exam_extractor.api:app", "--host", "0.0.0.0", "--port", "8000"]
