# Phase 6: portfolio frontend

The separate `frontend/` application is React + Vite + TypeScript. It gives a
new visitor an immediate mental model of the product: source intake, provider
controls, live stages, warnings, question preview, evidence counts, and
download links.

## Development

Start the backend first, then run:

```bash
npm --prefix frontend install
npm --prefix frontend run dev
```

Set `VITE_API_BASE_URL` when the API is not at `http://localhost:8000`:

```bash
VITE_API_BASE_URL=http://localhost:8000 npm --prefix frontend run dev
```

The browser receives only job IDs and public artifacts. Provider API keys stay
in the backend environment.

## Production build

```bash
npm --prefix frontend run build
npm --prefix frontend run preview
```

The interface is responsive, keyboard-usable with native controls, and has
explicit loading, warning, failure, empty, and completed states. Phase 7 will
serve this build from Docker alongside the API.
