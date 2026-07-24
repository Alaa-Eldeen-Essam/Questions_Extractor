# Phase 5: FastAPI backend

Install the web extra and start the API:

```bash
python -m pip install -e 'backend[web]'
uvicorn exam_extractor.api:app --host 127.0.0.1 --port 8000
```

The API exposes:

- `GET /health/live` and `GET /health/ready`
- `GET /api/providers` and `GET /api/config/default`
- `POST /api/jobs` for URL/path jobs
- `POST /api/jobs/file` for local media uploads
- `GET /api/jobs/{job_id}` for manifest/status
- `POST /api/jobs/{job_id}/cancel`
- `GET /api/jobs/{job_id}/events` as Server-Sent Events
- `GET /api/jobs/{job_id}/artifacts/{path}` for safe downloads

The API uses the same `run_pipeline` function as the CLI. Uploads are stored
under the configured output directory, and artifact paths are constrained to
their job workspace to prevent traversal.

This phase uses a small in-process worker pool for local deployment. A later
deployment can replace `JobManager` with a durable queue without changing the
HTTP contract.

## Verification

```bash
python -m unittest discover -s backend/tests -p 'test_*.py'
```
