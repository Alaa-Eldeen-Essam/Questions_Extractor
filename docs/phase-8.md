# Phase 8: release hardening

The release now includes:

- Versioned `schema_version` fields in manifests and extraction JSON.
- Privacy controls for source redaction and documented retention settings.
- A bounded streaming upload path controlled by `MAX_UPLOAD_BYTES`.
- PDF page rendering through Poppler and the existing OCR pipeline.
- A tested Python dependency lock for the Docker release set.
- A troubleshooting decision tree and contribution templates.

## PDF usage

```bash
python -m exam_extractor run lecture-notes.pdf --output outputs
```

PDF pages become visual evidence frames and pass through OCR. Speech is not
expected for a PDF input.

## Privacy

```toml
[privacy]
redact_source = true
retention_days = 30
```

Retention is a policy value for the deployment layer; automatic deletion is
deliberately not enabled by default so users do not lose study artifacts.

## Verification

```bash
python -m unittest discover -s backend/tests -p 'test_*.py'
npm --prefix frontend run build
docker build -t exam-video-extractor:local .
```
