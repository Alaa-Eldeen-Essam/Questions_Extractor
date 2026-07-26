"""FastAPI application over the shared extraction pipeline."""

import asyncio
import json
import mimetypes
import os
import threading
import uuid
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, fields
from pathlib import Path
from typing import Any

from .config import PipelineConfig
from .errors import ErrorCode, ExtractorError
from .pipeline import _job_id, _load_questions, run_pipeline
from .services.llm_service import available_llm_providers, llm_provider_catalog
from .services.profiles import apply_profile, profile_catalog
from .services.workflows import workflow_catalog
from .services.review_service import review_item, review_summary, update_question
from .services.output_service import write_json
from .services.serialization import jsonable

try:
    from fastapi import FastAPI, File, Form, HTTPException, UploadFile
    from fastapi.responses import FileResponse, StreamingResponse
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel, Field
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("Install the web extra: python -m pip install -e 'backend[web]'") from exc


class JobRequest(BaseModel):
    """Validated URL/path job request."""

    source: str = Field(min_length=1, max_length=4096)
    profile: str = "balanced"
    workflow: str = "exam_study_pack"
    options: dict[str, Any] = Field(default_factory=dict)


class ReviewUpdate(BaseModel):
    """Editable fields accepted by the human-review endpoint."""

    status: str | None = None
    prompt: str | None = None
    options: list[dict[str, str]] | None = None
    answer: str | None = None
    explanation: str | None = None
    review_note: str | None = None


class JobManager:
    """Small in-process job manager backed by pipeline manifests."""

    def __init__(self, output_root: Path) -> None:
        self.output_root = output_root
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.executor = ThreadPoolExecutor(max_workers=max(1, int(os.getenv("EXTRACTOR_WORKERS", "2"))))
        self.events: dict[str, list[str]] = {}
        self.cancel_events: dict[str, threading.Event] = {}
        self.lock = threading.Lock()

    def submit(self, source: str, config: PipelineConfig) -> str:
        job_id = _job_id(source, config)
        with self.lock:
            self.events.setdefault(job_id, []).append(json.dumps({"event": "queued", "job_id": job_id}))
            self.cancel_events[job_id] = threading.Event()
        self.executor.submit(self._run, job_id, source, config)
        return job_id

    def _run(self, job_id: str, source: str, config: PipelineConfig) -> None:
        def progress(message: str) -> None:
            with self.lock:
                self.events.setdefault(job_id, []).append(json.dumps({"event": "progress", "message": message}))
            if self.cancel_events[job_id].is_set():
                raise ExtractorError(ErrorCode.CANCELLED, "Job cancellation requested.", stage="pipeline")

        try:
            workspace = run_pipeline(source, config, output_root=self.output_root, progress=progress)
            self._record(job_id, {"event": "completed", "workspace": str(workspace)})
        except Exception as exc:
            self._record(job_id, {"event": "failed", "message": str(exc)})

    def _record(self, job_id: str, event: dict[str, Any]) -> None:
        with self.lock:
            self.events.setdefault(job_id, []).append(json.dumps(event))

    def cancel(self, job_id: str) -> bool:
        event = self.cancel_events.get(job_id)
        if event is None:
            return False
        event.set()
        self._record(job_id, {"event": "cancellation_requested"})
        return True

    def status(self, job_id: str) -> dict[str, Any]:
        manifest = self.output_root / job_id / "manifest.json"
        if manifest.exists():
            return json.loads(manifest.read_text(encoding="utf-8"))
        with self.lock:
            return {"job_id": job_id, "status": "queued", "events": len(self.events.get(job_id, []))}

    def artifact(self, job_id: str, relative: str) -> Path:
        workspace = (self.output_root / job_id).resolve()
        candidate = (workspace / relative).resolve()
        try:
            candidate.relative_to(workspace)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Artifact path escapes the job workspace.") from exc
        if not candidate.is_file():
            raise HTTPException(status_code=404, detail="Artifact not found.")
        return candidate

    def review(self, job_id: str) -> dict[str, Any]:
        """Load the current review queue for a completed job."""
        questions_path = self.output_root / job_id / "questions.json"
        if not questions_path.is_file():
            raise FileNotFoundError(f"No question artifact exists for job '{job_id}'.")
        questions = _load_questions(questions_path)
        config = self.output_root / job_id / "manifest.json"
        manifest = json.loads(config.read_text(encoding="utf-8")) if config.is_file() else {}
        threshold = float(manifest.get("review", {}).get("threshold", 0.70))
        return {
            "summary": review_summary(questions, threshold),
            "items": [review_item(question) for question in questions],
        }

    def update_review(self, job_id: str, question_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        """Persist one human review decision and synchronize JSON artifacts."""
        questions_path = self.output_root / job_id / "questions.json"
        if not questions_path.is_file():
            raise FileNotFoundError(f"No question artifact exists for job '{job_id}'.")
        questions = _load_questions(questions_path)
        question = next((item for item in questions if item.question_id == question_id), None)
        if question is None:
            raise KeyError(f"Question '{question_id}' was not found.")
        update_question(question, changes)
        write_json(questions_path, questions)
        manifest_path = self.output_root / job_id / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
        threshold = float(manifest.get("review", {}).get("threshold", 0.70))
        summary = review_summary(questions, threshold)
        review_payload = {"summary": summary, "items": [review_item(item) for item in questions]}
        write_json(self.output_root / job_id / "review.json", review_payload)
        manifest["review"] = summary
        if manifest_path.is_file():
            write_json(manifest_path, manifest)
        extraction_path = self.output_root / job_id / "extraction.json"
        if extraction_path.is_file():
            extraction = json.loads(extraction_path.read_text(encoding="utf-8"))
            extraction["questions"] = jsonable(questions)
            extraction["review"] = summary
            write_json(extraction_path, extraction)
        return review_item(question)

    def complete_review(self, job_id: str) -> dict[str, Any]:
        """Record that the reviewer finished the current queue."""
        payload = self.review(job_id)
        payload["completed_by_human"] = True
        write_json(self.output_root / job_id / "review.json", payload)
        return payload


def _apply_options(config: PipelineConfig, options: dict[str, Any]) -> PipelineConfig:
    """Apply only known dataclass fields from an API request."""
    workflow_values = options.get("workflow")
    if workflow_values is not None:
        if not isinstance(workflow_values, dict):
            raise ValueError("options.workflow must be an object")
        if "id" in workflow_values:
            config.workflow_id = str(workflow_values["id"])
        if "blocks" in workflow_values:
            if not isinstance(workflow_values["blocks"], dict):
                raise ValueError("options.workflow.blocks must be an object")
            config.workflow_overrides = workflow_values["blocks"]
    for section_name, values in options.items():
        if section_name == "workflow":
            continue
        target = getattr(config, section_name, None)
        if target is None or not isinstance(values, dict):
            continue
        allowed = {item.name for item in fields(target)}
        for name, value in values.items():
            if name in allowed:
                setattr(target, name, value)
    config.validate()
    return config


def create_app(output_root: Path | None = None) -> FastAPI:
    """Create an independently testable FastAPI application."""
    manager = JobManager(Path(output_root or os.getenv("EXTRACTOR_OUTPUT_DIR", "outputs")))

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        manager.executor.shutdown(wait=True, cancel_futures=True)

    app = FastAPI(title="Exam Video Extractor API", version="0.1.4", lifespan=lifespan)
    app.state.job_manager = manager

    @app.get("/health/live")
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    def ready() -> dict[str, Any]:
        return {"status": "ok", "output_root": str(manager.output_root)}

    @app.get("/api/providers")
    def providers() -> dict[str, Any]:
        return {"speech": ["auto", "faster_whisper", "openai_compatible", "none"], "llm": list(available_llm_providers())}

    @app.get("/api/settings/options")
    def settings_options() -> dict[str, Any]:
        """Return safe settings metadata for the collapsed advanced panel."""
        return {
            "profiles": profile_catalog(),
            "languages": [
                {"id": "auto", "label": "Auto-detect"},
                {"id": "en", "label": "English"},
                {"id": "ar", "label": "Arabic"},
                {"id": "fr", "label": "French"},
                {"id": "de", "label": "German"},
                {"id": "es", "label": "Spanish"},
            ],
            "ocr_languages": [
                {"id": "eng", "label": "English"},
                {"id": "ara", "label": "Arabic"},
                {"id": "eng+ara", "label": "English + Arabic"},
            ],
            "llm": llm_provider_catalog(),
            "workflows": workflow_catalog(),
        }

    @app.get("/api/workflows")
    def workflows() -> dict[str, Any]:
        """List workflow presets without exposing provider credentials."""
        return {"workflows": workflow_catalog()}

    @app.get("/api/config/default")
    def default_config() -> dict[str, Any]:
        config = PipelineConfig()
        return {"workflow": config.workflow_id, "profile": config.profile, "output_dir": str(config.output_dir), "speech": asdict(config.speech), "frames": asdict(config.frames), "ocr": asdict(config.ocr), "llm": asdict(config.llm), "task": asdict(config.task), "output": asdict(config.output), "privacy": asdict(config.privacy)}

    @app.post("/api/jobs", status_code=202)
    def create_job(payload: JobRequest) -> dict[str, str]:
        config = PipelineConfig()
        try:
            apply_profile(config, payload.profile)
            config.workflow_id = payload.workflow
            _apply_options(config, payload.options)
            config.validate()
            job_id = manager.submit(payload.source, config)
        except (ExtractorError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"job_id": job_id, "status": "queued"}

    @app.post("/api/jobs/file", status_code=202)
    async def create_file_job(
        file: UploadFile = File(...),
        profile: str = Form("balanced"),
        options_json: str = Form("{}"),
    ) -> dict[str, str]:
        config = PipelineConfig()
        try:
            apply_profile(config, profile)
            options = json.loads(options_json)
            if not isinstance(options, dict):
                raise ValueError("options_json must contain a JSON object")
            _apply_options(config, options)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=f"Invalid upload settings: {exc}") from exc
        suffix = Path(file.filename or "upload.bin").suffix.lower()
        if suffix not in {".mp4", ".mkv", ".webm", ".mov", ".m4a", ".mp3", ".wav", ".flac", ".pdf"}:
            raise HTTPException(status_code=415, detail="Unsupported upload type.")
        upload_dir = manager.output_root / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        path = upload_dir / f"{uuid.uuid4().hex}{suffix}"
        maximum = int(os.getenv("MAX_UPLOAD_BYTES", str(4 * 1024 * 1024 * 1024)))
        written = 0
        with path.open("wb") as handle:
            while chunk := await file.read(1024 * 1024):
                written += len(chunk)
                if written > maximum:
                    path.unlink(missing_ok=True)
                    raise HTTPException(status_code=413, detail="Uploaded file exceeds MAX_UPLOAD_BYTES.")
                handle.write(chunk)
        await file.close()
        return {"job_id": manager.submit(str(path), config), "status": "queued"}

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str) -> dict[str, Any]:
        return manager.status(job_id)

    @app.get("/api/jobs/{job_id}/review")
    def get_review(job_id: str) -> dict[str, Any]:
        try:
            return manager.review(job_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.patch("/api/jobs/{job_id}/review/{question_id}")
    def update_review(job_id: str, question_id: str, payload: ReviewUpdate) -> dict[str, Any]:
        try:
            return manager.update_review(job_id, question_id, payload.model_dump(exclude_none=True))
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/jobs/{job_id}/review/complete")
    def complete_review(job_id: str) -> dict[str, Any]:
        try:
            return manager.complete_review(job_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel_job(job_id: str) -> dict[str, Any]:
        if not manager.cancel(job_id):
            raise HTTPException(status_code=404, detail="Job not found.")
        return {"job_id": job_id, "status": "cancellation_requested"}

    @app.get("/api/jobs/{job_id}/artifacts/{relative:path}")
    def get_artifact(job_id: str, relative: str) -> FileResponse:
        artifact = manager.artifact(job_id, relative)
        media_type = {
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }.get(artifact.suffix.lower(), mimetypes.guess_type(artifact.name)[0] or "application/octet-stream")
        return FileResponse(artifact, media_type=media_type, filename=artifact.name)

    @app.get("/api/jobs/{job_id}/events")
    async def events(job_id: str) -> StreamingResponse:
        async def stream():
            index = 0
            while True:
                with manager.lock:
                    values = manager.events.get(job_id, [])[index:]
                    index += len(values)
                for value in values:
                    yield f"data: {value}\n\n"
                status = manager.status(job_id).get("status")
                if status in {"completed", "failed", "cancelled"} or (values and json.loads(values[-1]).get("event") in {"failed", "completed"}):
                    break
                await asyncio.sleep(0.25)
        return StreamingResponse(stream(), media_type="text/event-stream")

    frontend_dist = Path(os.getenv("FRONTEND_DIST", "frontend/dist"))
    if frontend_dist.is_dir():
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
    return app


app = create_app()
