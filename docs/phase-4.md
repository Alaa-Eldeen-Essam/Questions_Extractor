# Phase 4: question-bank intelligence

Phase 4 adds a deterministic question extractor over normalized speech and
OCR. It recognizes common question stems, letter/number options, explicit
answer phrases, explanations, duplicate questions, and answer conflicts.

Every record keeps evidence references and a confidence score. If the LLM is
enabled, only missing or low-confidence records are sent for structured
enrichment; the no-LLM path remains useful and reproducible.

The generated `questions.json` is included in `extraction.json`, and the
Markdown renderer adds a Question bank section before visual evidence.

## Verification

```bash
python -m unittest discover -s backend/tests -p 'test_*.py'
```

The heuristics intentionally do not claim an answer when evidence is absent.
For unusual layouts or ambiguous screenshots, enable a vision-capable LLM and
review low-confidence records.
