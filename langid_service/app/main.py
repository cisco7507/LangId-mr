import io, os, tempfile, time, threading, json
from datetime import datetime, timedelta, UTC
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Response
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from loguru import logger
from sqlalchemy.orm import Session
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from .metrics import REGISTRY
from typing import Optional

from .config import LOG_DIR, MAX_WORKERS, WHISPER_MODEL_SIZE, MAX_FILE_SIZE_MB, ENFR_STRICT_REJECT
from .database import Base, engine, SessionLocal
from .models.models import Job, JobStatus
from .schemas import EnqueueResponse, JobStatusResponse, ResultResponse, SubmitByUrl, JobListResponse, DeleteJobsRequest
from .utils import gen_uuid, ensure_dirs, validate_upload, move_to_storage
from .worker.runner import work_once
from .guards import ensure_allowed
from .lang_gate import validate_language_strict

from fastapi.middleware.cors import CORSMiddleware
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

# Background worker thread loop
_stop_event = threading.Event()

def worker_loop():
    logger.info("Worker loop started")
    while not _stop_event.is_set():
        worked = work_once()
        if not worked:
            time.sleep(0.05)

worker_threads = []
def start_workers():
    for i in range(MAX_WORKERS):
        t = threading.Thread(target=worker_loop, name=f"worker-{i+1}", daemon=True)
        t.start()
        worker_threads.append(t)
    logger.info(f"Started {len(worker_threads)} worker threads")

@app.on_event("startup")
def on_startup():
    start_workers()

@app.on_event("shutdown")
def on_shutdown():
    _stop_event.set()
    for t in worker_threads:
        t.join(timeout=5)

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
            error=job.error,
        ) for job in jobs])
    finally:
        session.close()

@app.delete("/jobs")
def delete_jobs(payload: DeleteJobsRequest):
    session = SessionLocal()
    try:
        jobs_to_delete = session.query(Job).filter(Job.id.in_(payload.job_ids)).all()
        for job in jobs_to_delete:
            session.delete(job)
        session.commit()
        return {"status": "ok", "deleted_count": len(jobs_to_delete)}
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
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(raw)
        tmp.flush()
        tmp_path = Path(tmp.name)

    # Strict mode validation
    if ENFR_STRICT_REJECT:
        validate_language_strict(str(tmp_path))

    job_id = gen_uuid()
    stored = move_to_storage(tmp_path, job_id)
    logger.info(f"Enqueued upload for job {job_id}: {stored}")

    # Persist job
    session = SessionLocal()
    try:
        job = Job(id=job_id, status=JobStatus.queued, input_path=str(stored), target_lang=target_lang)
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
            validate_language_strict(str(tmp_file))

        stored = move_to_storage(tmp_file, job_id)
    except Exception as e:
        if tmp_file.exists():
            tmp_file.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Failed to download/process URL: {e}")

    session = SessionLocal()
    try:
        job = Job(id=job_id, status=JobStatus.queued, input_path=str(stored), target_lang=target_lang)
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
        # The raw dict is the full, original result.
        # We also promote a few key fields to the top level for convenience.
        # To avoid duplication, we can pop them from the raw dict.
        transcript_snippet = raw.pop("transcript_snippet", None)

        return ResultResponse(
            job_id=job.id,
            language=raw.get("language_mapped", "unknown"),
            probability=raw.get("probability", 0.0),
            transcript_snippet=transcript_snippet,
            processing_ms=raw.get("processing_ms", 0),
            raw=raw,
        )
    finally:
        session.close()
