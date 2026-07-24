# Phase 0 — contracts and foundations

## Delivered

- Cross-platform Python package layout under `backend/src`.
- Domain contracts for sources, transcripts, frames, OCR, questions, jobs, stages, and artifacts.
- Provider protocols and an explicit registry.
- TOML configuration with safe defaults and validation.
- Verbose serializable error model.
- Dependency-free Phase 0 self-checks.
- Initial architecture, configuration, and provider documentation.

## Verification

Run from the repository root:

```powershell
python -m unittest discover -s backend/tests -p "test_*.py"
python -m compileall backend/src
```

Both commands pass. Phase 1 can now implement the deterministic CLI pipeline
against these contracts. See [the full roadmap](roadmap.md), the
[self-hosting plan](self-hosting.md), and the [Docker Hub release plan](docker-release.md).
