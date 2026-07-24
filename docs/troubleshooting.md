# Troubleshooting decision tree

1. Is the API reachable?
   - Open `http://localhost:8000/health/live`.
   - If it fails, inspect `docker compose logs -f` or the Uvicorn terminal.
2. Does the job fail during acquire?
   - Confirm the URL/path exists and the source is supported.
   - For YouTube, check network access and yt-dlp availability.
3. Does media processing fail?
   - Check FFmpeg with `ffmpeg -version`.
   - Check Poppler with `pdftoppm -h` for PDFs.
   - Check Tesseract with `tesseract --version`.
4. Is speech empty?
   - Captions may be absent or incomplete.
   - Install `backend[speech]`, use `faster_whisper`, or configure a remote
     OpenAI-compatible endpoint.
5. Is OCR empty or inaccurate?
   - Use interval frames, increase `frames.max_resolution`, and verify the
     correct Tesseract language pack.
6. Is an LLM failing?
   - Confirm `llm.enabled`, model, endpoint, and environment variable.
   - Check rate limits and retryable error details.
7. Are results missing after restart?
   - Keep `/data/outputs` mounted and rerun the same source/config; completed
     stages are resumed from the manifest.

Do not paste API keys or private lecture URLs into public issue reports.
