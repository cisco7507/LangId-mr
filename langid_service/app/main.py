import io, os, tempfile, time, json
import multiprocessing as mp
try:
    from datetime import datetime, timedelta, UTC
except ImportError:  # Python < 3.11
    from datetime import datetime, timedelta, timezone

    UTC = timezone.utc
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Response
from fastapi.responses import JSONResponse, FileResponse
import mimetypes
from pydantic import ValidationError
from loguru import logger
from sqlalchemy.orm import Session
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from .metrics import REGISTRY
from typing import Optional

from .config import LOG_DIR, MAX_WORKERS, WHISPER_MODEL_SIZE, MAX_FILE_SIZE_MB, ENFR_STRICT_REJECT, STORAGE_DIR
from .database import Base, engine, SessionLocal
from .models.models import Job, JobStatus
from .schemas import EnqueueResponse, JobStatusResponse, ResultResponse, SubmitByUrl, JobListResponse, DeleteJobsRequest
from .utils import gen_uuid, ensure_dirs, validate_upload, move_to_storage
from .worker.runner import work_once
from .guards import ensure_allowed
from .lang_gate import validate_language_strict
from .services.audio_io import load_audio_mono_16k

from fastapi.middleware.cors import CORSMiddleware
import shutil
import os


app = FastAPI(title="Windows LangID API", version="1.0.0")

# === CORS CONFIG ===


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],           # ← allow all origins
    allow_credentials=False,
    allow_methods=["*"],           # ← allow all HTTP verbs (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],           # ← allow all headers
)

# Configure logging
LOG_DIR.mkdir(parents=True, exist_ok=True)
logger.add((LOG_DIR / "service.log").as_posix(), rotation="10 MB", retention=10, level="INFO")

# Init database
Base.metadata.create_all(bind=engine)
ensure_dirs()

# Background worker process loop
MP_CONTEXT = mp.get_context("spawn")
_stop_event = MP_CONTEXT.Event()
worker_processes = []

def worker_loop(stop_event):
    logger.info(f"Worker process {os.getpid()} started")
    try:
        while not stop_event.is_set():
            worked = work_once()
            if not worked:
                time.sleep(0.05)
    finally:
        logger.info(f"Worker process {os.getpid()} exiting")


def start_workers():
    if _stop_event.is_set():
        _stop_event.clear()

    worker_processes.clear()

    for i in range(MAX_WORKERS):
        p = MP_CONTEXT.Process(
            target=worker_loop,
            name=f"worker-{i+1}",
            args=(_stop_event,),
            daemon=True,
        )
        p.start()
        worker_processes.append(p)
    logger.info(f"Started {len(worker_processes)} worker processes")

@app.on_event("startup")
def on_startup():
    start_workers()

@app.on_event("shutdown")
def on_shutdown():
    _stop_event.set()
    for p in worker_processes:
        p.join(timeout=10)
        if p.is_alive():
            logger.warning(f"Worker process {p.pid} did not exit in time; terminating")
            p.terminate()

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

@app.get("/metrics")
def metrics():
    data = generate_latest(REGISTRY)
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)

@app.get("/metrics/prometheus")
def prometheus_metrics():
    data = generate_latest(REGISTRY)
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)


@app.get("/metrics/json")
def metrics_json():
    """Return key service metrics in a JSON-friendly shape for the dashboard.

    This endpoint intentionally exposes a small, stable subset of metrics so
    the React dashboard can display stats without needing to parse the
    Prometheus text format.
    """
    session = SessionLocal()
    try:
        total = session.query(Job).count()

        by_status = {
            status.value: session.query(Job).filter(Job.status == status).count()
            for status in JobStatus
        }

        running = by_status.get(JobStatus.running.value, 0)
        queued = by_status.get(JobStatus.queued.value, 0)

        # Jobs completed in the last 5 minutes
        now = datetime.now(UTC)
        five_minutes_ago = now - timedelta(minutes=5)
        recent_completed_5m = (
            session.query(Job)
            .filter(
                Job.status == JobStatus.succeeded,
                Job.updated_at >= five_minutes_ago,
            )
            .count()
        )

        # Average processing time over the last 50 succeeded jobs.
        # Prefer the explicit processing_ms field in result_json when available,
        # and fall back to created_at/updated_at timing otherwise.
        last_50_succeeded = (
            session.query(Job)
            .filter(Job.status == JobStatus.succeeded)
            .order_by(Job.updated_at.desc())
            .limit(50)
            .all()
        )

        durations = []
        for job in last_50_succeeded:
            # Try to read processing_ms from result_json
            processing_seconds_from_json = None
            if job.result_json:
                try:
                    payload = json.loads(job.result_json)
                    processing_ms = payload.get("processing_ms")
                    if isinstance(processing_ms, (int, float)) and processing_ms >= 0:
                        processing_seconds_from_json = processing_ms / 1000.0
                except Exception:
                    # If result_json is malformed, ignore and fall back to timestamps
                    processing_seconds_from_json = None

            if processing_seconds_from_json is not None:
                durations.append(processing_seconds_from_json)
            elif job.updated_at and job.created_at:
                durations.append((job.updated_at - job.created_at).total_seconds())

        avg_processing = sum(durations) / len(durations) if durations else 0.0

        metrics = {
            "jobs": {
                "total": total,
                "by_status": by_status,
                "running": running,
                "queued": queued,
                "recent_completed_5m": recent_completed_5m,
            },
            "workers": {
                "configured": MAX_WORKERS,
            },
            "timing": {
                "avg_processing_seconds_last_50": avg_processing,
            },
        }

        return JSONResponse(content=metrics)
    finally:
        session.close()

@app.get("/jobs", response_model=JobListResponse)
def get_jobs():
    session = SessionLocal()
    try:
        jobs = session.query(Job).order_by(Job.created_at.desc()).all()
        return JobListResponse(jobs=[JobStatusResponse(
            job_id=job.id,
            status=job.status.value,
            progress=job.progress,
            created_at=job.created_at,
            updated_at=job.updated_at,
            attempts=job.attempts,
            filename=Path(job.input_path).name if job.input_path else None,
            original_filename=job.original_filename,
            language=(json.loads(job.result_json).get("language") if job.result_json else None),
            probability=(json.loads(job.result_json).get("probability") if job.result_json else None),
            error=job.error,
        ) for job in jobs])
    finally:
        session.close()

@app.delete("/jobs")
def delete_jobs(payload: DeleteJobsRequest):
    session = SessionLocal()
    try:
        jobs_to_delete = session.query(Job).filter(Job.id.in_(payload.job_ids)).all()
        deleted_count = 0
        # Attempt to remove any storage artifacts for each job id.
        storage_root = STORAGE_DIR.resolve()
        for job in jobs_to_delete:
            try:
                # Remove any files or directories in STORAGE_DIR that start with the job id
                pattern = f"{job.id}*"
                for p in storage_root.glob(pattern):
                    try:
                        # Ensure the matched path is inside the storage directory
                        try:
                            resolved = p.resolve()
                        except Exception:
                            resolved = p
                        if storage_root not in resolved.parents and resolved != storage_root:
                            # skip anything outside storage (extra safety)
                            logger.warning(f"Skipping deletion of path outside storage: {p}")
                            continue

                        if p.is_dir():
                            shutil.rmtree(p)
                        else:
                            p.unlink(missing_ok=True)
                        logger.info(f"Removed storage artifact for job {job.id}: {p}")
                    except Exception:
                        logger.exception(f"Failed to remove storage artifact {p} for job {job.id}")
            except Exception:
                logger.exception(f"Error while cleaning storage for job {job.id}")

            # delete DB record
            try:
                session.delete(job)
                deleted_count += 1
            except Exception:
                logger.exception(f"Failed to delete job record {job.id}")

        session.commit()
        return {"status": "ok", "deleted_count": deleted_count}
    finally:
        session.close()

@app.post("/jobs", response_model=EnqueueResponse)
async def submit_job(file: UploadFile = File(...), target_lang: Optional[str] = None):
    # Validate target language
    if target_lang:
        ensure_allowed(target_lang)

    # Validate upload
    raw = await file.read()
    try:
        validate_upload(file.filename, len(raw))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Write temp file then move to storage
    # Create temp file using the original filename's suffix where possible so
    # the temporary file preserves the extension (helps later MIME detection).
    orig_suffix = Path(file.filename).suffix or ""
    with tempfile.NamedTemporaryFile(delete=False, suffix=orig_suffix) as tmp:
        tmp.write(raw)
        tmp.flush()
        tmp_path = Path(tmp.name)

    # Strict mode validation
    if ENFR_STRICT_REJECT:
        audio = load_audio_mono_16k(str(tmp_path))
        validate_language_strict(audio)

    job_id = gen_uuid()
    stored = move_to_storage(tmp_path, job_id)
    logger.info(f"Enqueued upload for job {job_id}: {stored}")

    # Persist job
    session = SessionLocal()
    try:
        job = Job(
            id=job_id,
            status=JobStatus.queued,
            input_path=str(stored),
            original_filename=file.filename,
            target_lang=target_lang,
        )
        session.add(job)
        session.commit()
    finally:
        session.close()

    return EnqueueResponse(job_id=job_id, status="queued")

@app.post("/jobs/by-url", response_model=EnqueueResponse)
async def submit_job_by_url(payload: SubmitByUrl, target_lang: Optional[str] = None):
    # Validate target language
    if target_lang:
        ensure_allowed(target_lang)

    # Simple URL fetch (no auth) — for production, prefer signed URLs or internal sources.
    import urllib.request
    job_id = gen_uuid()
    tmp_file = Path(tempfile.gettempdir()) / f"{job_id}.wav"

    url = payload.url
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Invalid URL scheme")

    try:
        with urllib.request.urlopen(url) as response:
            file_size = int(response.headers.get("Content-Length", 0))
            if file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
                raise HTTPException(
                    status_code=413,
                    detail=f"File size ({file_size / 1024 / 1024:.2f} MB) exceeds limit of {MAX_FILE_SIZE_MB} MB",
                )
            with open(tmp_file, "wb") as f:
                f.write(response.read())

        validate_upload(str(tmp_file), tmp_file.stat().st_size)

        # Strict mode validation
        if ENFR_STRICT_REJECT:
            audio = load_audio_mono_16k(str(tmp_file))
            validate_language_strict(audio)

        stored = move_to_storage(tmp_file, job_id)
    except Exception as e:
        if tmp_file.exists():
            tmp_file.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Failed to download/process URL: {e}")

    session = SessionLocal()
    try:
        # Use the last path segment of the URL as a best-effort original filename
        original_filename = Path(url).name or None
        job = Job(
            id=job_id,
            status=JobStatus.queued,
            input_path=str(stored),
            original_filename=original_filename,
            target_lang=target_lang,
        )
        session.add(job)
        session.commit()
    finally:
        session.close()

    logger.info(f"Enqueued URL for job {job_id}: {stored}")
    return EnqueueResponse(job_id=job_id, status="queued")
@app.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_status(job_id: str):
    session = SessionLocal()
    try:
        job = session.get(Job, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return JobStatusResponse(
            job_id=job.id,
            status=job.status.value,
            progress=job.progress,
            created_at=job.created_at,
            updated_at=job.updated_at,
            attempts=job.attempts,
            filename=Path(job.input_path).name if job.input_path else None,
            original_filename=job.original_filename,
            language=(json.loads(job.result_json).get("language") if job.result_json else None),
            probability=(json.loads(job.result_json).get("probability") if job.result_json else None),
            error=job.error,
        )
    finally:
        session.close()

@app.get("/jobs/{job_id}/result", response_model=ResultResponse)
def get_result(job_id: str):
    session = SessionLocal()
    try:
        job = session.get(Job, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if job.status != JobStatus.succeeded or not job.result_json:
            raise HTTPException(status_code=409, detail=f"Job not completed (status={job.status.value})")
        raw = json.loads(job.result_json)
        # The worker stores the main result in the 'text' field.
        # We'll use this for the top-level snippet.
        transcript_snippet = raw.get("text")

        return ResultResponse(
            job_id=job.id,
            language=raw.get("language", "unknown"),
            probability=raw.get("probability", 0.0), # Note: worker doesn't set this field
            detection_method=raw.get("detection_method"),
            gate_decision=raw.get("gate_decision"),
            gate_meta=raw.get("gate_meta"),
            music_only=raw.get("music_only", False),
            transcript_snippet=transcript_snippet,
            processing_ms=raw.get("processing_ms", 0),
            original_filename=job.original_filename,
            raw=raw,
        )
    finally:
        session.close()


@app.get("/jobs/{job_id}/audio")
def get_job_audio(job_id: str):
    """Serve the original uploaded audio file for a job.

    This returns a `FileResponse` with an appropriate audio content-type.
    The dashboard uses this endpoint to embed an audio player.
    """
    session = SessionLocal()
    try:
        job = session.get(Job, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if not job.input_path:
            raise HTTPException(status_code=404, detail="No input audio available for this job")

        audio_path = Path(job.input_path)
        if not audio_path.exists():
            raise HTTPException(status_code=404, detail="Audio file not found on server")

        # Prefer the original filename (if available) for mime-type guessing
        mime_type = None
        if job.original_filename:
            mime_type, _ = mimetypes.guess_type(job.original_filename)

        # Fallback to the stored file's name
        if not mime_type:
            mime_type, _ = mimetypes.guess_type(str(audio_path))

        # As a last resort, avoid mislabeling non-WAV as WAV; fall back to
        # generic binary if unknown. Consumers can still play if browser
        # detects audio by content. Using 'application/octet-stream' is
        # safer than forcing 'audio/wav' for unknown types.
        if not mime_type:
            mime_type = "application/octet-stream"

        # Return as inline content so browsers can stream in an <audio> element
        # Use the original filename in the Content-Disposition when available
        disp_name = job.original_filename or audio_path.name
        headers = {"Content-Disposition": f'inline; filename="{disp_name}"'}
        return FileResponse(path=str(audio_path), media_type=mime_type, headers=headers)
    finally:
        session.close()
