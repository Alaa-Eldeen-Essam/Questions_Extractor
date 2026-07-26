# Phase 6: workflow-aware portfolio UI

The hidden Advanced Settings panel now exposes the generalized backend without
making the default intake form intimidating:

- workflow preset selection and descriptions;
- task kind, title, instruction, and maximum item controls;
- independent block toggles for the selected workflow;
- provider-neutral LLM, language, output-format, and review-gate controls;
- PDF, CSV, Word, and transcript download links when artifacts exist;
- live `task` stages and the `awaiting_review` state.

The simple path still defaults to the exam study pack, balanced processing, auto
language detection, and no LLM. The API remains the source of truth for all
settings, so a future workflow editor can use the same contracts.

## Verification

```bash
npm --prefix frontend run build
python -m unittest discover -s backend/tests -p 'test_*.py'
```
