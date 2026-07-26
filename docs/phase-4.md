# Phase 4: review gates before artifact generation

Phase 4 makes human review an optional release gate. Low-confidence question
records continue to be persisted as reviewable JSON, but a job configured with
`review.gate_before_artifacts = true` stops with status `awaiting_review`
before writing final Markdown, JSON, or Word artifacts.

Resolve each queued question through the review API:

```text
PATCH /api/jobs/{job_id}/review/{question_id}
POST  /api/jobs/{job_id}/review/complete
```

The completion endpoint rejects unresolved `needs_review` records. Once all
records are approved, edited, or rejected, it reconstructs the redacted-safe
configuration from the manifest and resumes the same job. Existing completed
stages are reused; only the final artifact stage runs.

The default remains `false` for compatibility with unattended extraction.
Enable the gate when correctness matters more than immediate artifact delivery.

## Verification

```bash
python -m unittest discover -s backend/tests -p 'test_*.py'
```

The review-gate test verifies both the `awaiting_review` state and resumable
artifact generation after the review status is resolved.
