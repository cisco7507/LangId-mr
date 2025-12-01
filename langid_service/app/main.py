import io, os, tempfile, time, json, sys
import multiprocessing as mp
import threading
try:
    from datetime import datetime, timedelta, UTC
except ImportError:  # Python < 3.11
    from datetime import datetime, timedelta, timezone

    UTC = timezone.utc
from pathlib import Path
from queue import Empty
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Response, Query, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import mimetypes
from pydantic import ValidationError
from loguru import logger
from sqlalchemy.orm import Session
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from .metrics import REGISTRY
from .gate_metrics import GATE_PATH_CHOICES
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
from langid_service.cluster.config import get_self_name, get_nodes
from langid_service.cluster.router import is_local, proxy_to_owner, proxy_job_submission
from langid_service.cluster.scheduler import scheduler
from langid_service.cluster.dashboard import aggregate_cluster_jobs
from langid_service.cluster.health import check_cluster_health
from .models.languages import to_iso_code, get_language_label, from_iso_code
from .config import LANG_CODE_FORMAT

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
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | job={extra[job_id]} | "
    "{name}:{function}:{line} - {message}"
)
logger.remove()
logger.configure(extra={"job_id": "-"})
logger.add(sys.stderr, level=log_level, format=LOG_FORMAT)
logger.add(
    (LOG_DIR / "service.log").as_posix(),
    rotation="10 MB",
    retention=10,
    level=log_level,
    format=LOG_FORMAT,
)

# Init database
Base.metadata.create_all(bind=engine)
ensure_dirs()

# Background worker process loop
MP_CONTEXT = mp.get_context("spawn")
_stop_event = MP_CONTEXT.Event()
worker_processes = []

_metric_events_queue = None
_metric_listener_thread = None
_metric_listener_stop = threading.Event()

def worker_loop(stop_event, metric_queue):
    logger.info(f"Worker process {os.getpid()} started")
    try:
        while not stop_event.is_set():
            try:
                worked = work_once(metric_queue)
            except KeyboardInterrupt:
                logger.info(f"Worker process {os.getpid()} interrupted; stopping loop")
                break
            except Exception:
                logger.exception("Unhandled exception in worker loop")
                # Avoid tight crash loops if work_once keeps failing
                stop_event.wait(0.1)
                continue

            if not worked:
                # Use the stop event so we wake up promptly when shutting down
                stop_event.wait(0.05)
    except KeyboardInterrupt:
        logger.info(f"Worker process {os.getpid()} received KeyboardInterrupt")
    finally:
        logger.info(f"Worker process {os.getpid()} exiting")


def _ensure_metric_events_queue():
    global _metric_events_queue
    if _metric_events_queue is None:
        _metric_events_queue = MP_CONTEXT.Queue()
    _start_metric_listener()


def _metric_listener_loop():
    from .gate_metrics import record_gate_path_metrics

    logger.info("Gate metrics consumer thread started")
    while not _metric_listener_stop.is_set():
        try:
            payload = _metric_events_queue.get(timeout=0.5)
        except Empty:
            continue
        except (EOFError, OSError):
            break

        if payload is None:
            continue

        gate_result = payload.get("gate_result") if isinstance(payload, dict) else None
        job_id = payload.get("job_id") if isinstance(payload, dict) else None

        try:
            record_gate_path_metrics(gate_result or {}, job_id=job_id)
        except Exception:
            logger.bind(job_id=job_id or "-").exception(
                "Failed to record gate path metrics from queue"
            )

    logger.info("Gate metrics consumer thread exiting")


def _start_metric_listener():
    global _metric_listener_thread
    if _metric_listener_thread and _metric_listener_thread.is_alive():
        return

    _metric_listener_stop.clear()
    _metric_listener_thread = threading.Thread(
        target=_metric_listener_loop,
        name="gate-metrics-consumer",
        daemon=True,
    )
    _metric_listener_thread.start()


def _stop_metric_listener():
    global _metric_listener_thread
    if not _metric_listener_thread:
        return

    _metric_listener_stop.set()
    if _metric_events_queue is not None:
        try:
            _metric_events_queue.put_nowait(None)
        except Exception:
            pass

    _metric_listener_thread.join(timeout=5)
    _metric_listener_thread = None


def start_workers():
    if _stop_event.is_set():
        _stop_event.clear()

    _ensure_metric_events_queue()
    worker_processes.clear()

    for i in range(MAX_WORKERS):
        p = MP_CONTEXT.Process(
            target=worker_loop,
            name=f"worker-{i+1}",
            args=(_stop_event, _metric_events_queue),
            daemon=True,
        )
        p.start()
        worker_processes.append(p)
    logger.info(f"Started {len(worker_processes)} worker processes")

import asyncio
from langid_service.cluster.config import load_cluster_config

# ...

async def health_check_loop():
    logger.info("Starting health check loop")
    while True:
        try:
            config = load_cluster_config()
            await check_cluster_health()
            await asyncio.sleep(config.health_check_interval_seconds)
        except Exception as e:
            logger.error(f"Health check loop error: {e}")
            await asyncio.sleep(5)

@app.on_event("startup")
async def on_startup():
    start_workers()
    # Initial node status
    prom_metrics.set_node_up(get_self_name(), 1)
    prom_metrics.set_node_last_health_timestamp(get_self_name(), datetime.now(UTC).timestamp())
    
    # Start health check loop
    asyncio.create_task(health_check_loop())

@app.on_event("shutdown")
def on_shutdown():
    _stop_event.set()
    for p in worker_processes:
        p.join(timeout=10)
        if p.is_alive():
            logger.warning(f"Worker process {p.pid} did not exit in time; terminating")
            p.terminate()
    _stop_metric_listener()

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


@app.get("/metrics/gate-paths")
def gate_path_metrics():
    """Return gate path decision metrics for the dashboard.

    Returns a breakdown of job decisions by gate path, including:
    - Total counts for each gate path
    - Percentage distribution across paths
    """
    from .metrics import LANGID_GATE_PATH_DECISIONS

    # Collect counts using public API and aggregate across label combinations
    path_counts = {path: 0 for path in GATE_PATH_CHOICES}

    for metric in LANGID_GATE_PATH_DECISIONS.collect():
        for sample in metric.samples:
            if sample.name != "langid_gate_path_decisions_total":
                continue

            gate_path = sample.labels.get("gate_path", "unknown")
            path_counts[gate_path] = path_counts.get(gate_path, 0) + int(sample.value)

    total = sum(path_counts.values())

    # Calculate percentages
    path_percentages = {}
    for gate_path, count in path_counts.items():
        path_percentages[gate_path] = round((count / total) * 100, 2) if total > 0 else 0.0

    return JSONResponse(content={
        "total_decisions": total,
        "by_gate_path": path_counts,
        "percentages": path_percentages,
    })


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
            language=to_iso_code(json.loads(job.result_json).get("language"), LANG_CODE_FORMAT) if job.result_json else None,
            language_label=get_language_label(json.loads(job.result_json).get("language")) if job.result_json else None,
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

from langid_service.metrics import prometheus as prom_metrics

# ... imports ...

# ... existing code ...

async def create_job_local(file: UploadFile, target_lang: Optional[str] = None) -> EnqueueResponse:
    # Validate target language
    if target_lang:
        canonical = from_iso_code(target_lang, LANG_CODE_FORMAT)
        if not canonical:
            raise HTTPException(status_code=400, detail=f"Invalid language code '{target_lang}' for format {LANG_CODE_FORMAT.value}")
        target_lang = canonical
        ensure_allowed(target_lang)

    # Validate upload
    # Note: file cursor should be at 0
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
        audio = load_audio_mono_16k(str(tmp_path))
        validate_language_strict(audio)

    job_id = f"{get_self_name()}-{gen_uuid()}"
    stored = move_to_storage(tmp_path, job_id, original_filename=file.filename)
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
        
        # Metric: jobs owned
        prom_metrics.increment_jobs_owned(get_self_name())
        
    finally:
        session.close()

    return EnqueueResponse(job_id=job_id, status="queued")

@app.post("/jobs", response_model=EnqueueResponse)
async def submit_job(
    file: UploadFile = File(...), 
    target_lang: Optional[str] = None,
    internal: Optional[str] = Query(None)
):
    if internal == "1":
        return await create_job_local(file, target_lang)

    # Round Robin Distribution
    # Read file content once to reuse in proxy
    file_content = await file.read()
    await file.seek(0)
    
    max_attempts = len(get_nodes()) if get_nodes() else 1
    attempts = 0
    
    ingress_node = get_self_name()
    
    while attempts < max_attempts:
        target = await scheduler.next_target()
        attempts += 1
        
        if target == get_self_name():
            # Metric: jobs submitted (local target)
            prom_metrics.increment_jobs_submitted(ingress_node, target)
            return await create_job_local(file, target_lang)
        
        try:
            # Proxy to target
            resp = await proxy_job_submission(
                target_node=target,
                file_content=file_content,
                filename=file.filename,
                target_lang=target_lang
            )
            
            if resp.status_code in (200, 201, 202):
                # Metric: jobs submitted (remote target)
                prom_metrics.increment_jobs_submitted(ingress_node, target)
                return EnqueueResponse(**json.loads(resp.body))
            
            # If 503, retry next node
            if resp.status_code == 503:
                continue
                
            # Propagate other errors
            return Response(
                content=resp.body,
                status_code=resp.status_code,
                headers=dict(resp.headers),
                media_type=resp.headers.get("content-type")
            )
            
        except Exception as e:
            logger.warning(f"Failed to proxy job to {target}: {e}")
            continue
            
    # Fallback to local if all else fails
    # Metric: jobs submitted (fallback local)
    prom_metrics.increment_jobs_submitted(ingress_node, get_self_name())
    return await create_job_local(file, target_lang)

@app.post("/jobs/by-url", response_model=EnqueueResponse)
async def submit_job_by_url(payload: SubmitByUrl, target_lang: Optional[str] = None):
    # Validate target language
    if target_lang:
        ensure_allowed(target_lang)

    # Simple URL fetch (no auth) — for production, prefer signed URLs or internal sources.
    import urllib.request
    job_id = f"{get_self_name()}-{gen_uuid()}"
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

        stored = move_to_storage(tmp_file, job_id, original_filename=original_filename)
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
async def get_status(job_id: str, request: Request):
    if not is_local(job_id):
        return await proxy_to_owner(job_id, "", request.method, request.query_params, headers=request.headers)

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
            language=to_iso_code(json.loads(job.result_json).get("language"), LANG_CODE_FORMAT) if job.result_json else None,
            language_label=get_language_label(json.loads(job.result_json).get("language")) if job.result_json else None,
            probability=(json.loads(job.result_json).get("probability") if job.result_json else None),
            error=job.error,
        )
    finally:
        session.close()

@app.get("/jobs/{job_id}/result", response_model=ResultResponse)
async def get_result(job_id: str, request: Request):
    if not is_local(job_id):
        return await proxy_to_owner(job_id, "/result", request.method, request.query_params, headers=request.headers)

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

        # Format language codes in the raw field recursively
        def format_lang_codes(obj):
            """Recursively format language codes in nested structures."""
            if isinstance(obj, dict):
                result = {}
                for key, value in obj.items():
                    if key == "language" and isinstance(value, str):
                        # Format language code
                        result[key] = to_iso_code(value, LANG_CODE_FORMAT)
                    else:
                        # Recurse into nested structures
                        result[key] = format_lang_codes(value)
                return result
            elif isinstance(obj, list):
                return [format_lang_codes(item) for item in obj]
            else:
                return obj
        
        formatted_raw = format_lang_codes(raw)

        return ResultResponse(
            job_id=job.id,
            language=to_iso_code(raw.get("language", "unknown"), LANG_CODE_FORMAT),
            language_label=get_language_label(raw.get("language", "unknown")),
            probability=raw.get("probability", 0.0), # Note: worker doesn't set this field
            detection_method=raw.get("detection_method"),
            gate_decision=raw.get("gate_decision"),
            gate_meta=format_lang_codes(raw.get("gate_meta")),
            music_only=raw.get("music_only", False),
            transcript_snippet=transcript_snippet,
            processing_ms=raw.get("processing_ms", 0),
            original_filename=job.original_filename,
            raw=formatted_raw,
        )
    finally:
        session.close()


@app.get("/jobs/{job_id}/audio")
async def get_job_audio(job_id: str, request: Request):
    """Serve the original uploaded audio file for a job.

    This returns a `FileResponse` with an appropriate audio content-type.
    The dashboard uses this endpoint to embed an audio player.
    """
    if not is_local(job_id):
        return await proxy_to_owner(job_id, "/audio", request.method, request.query_params, headers=request.headers)

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

        # Prefer guessing MIME from the stored filename (which we now preserve),
        # or fall back to the original filename that was uploaded.
        mime_type, _ = mimetypes.guess_type(audio_path.name)
        if not mime_type and job.original_filename:
            mime_type, _ = mimetypes.guess_type(job.original_filename)

        # If still unknown, try content-based detection via python-magic (optional).
        if not mime_type:
            try:
                import magic
                m = magic.Magic(mime=True)
                mime_type = m.from_file(str(audio_path))
            except Exception:
                # python-magic not installed or failed — leave mime_type None
                mime_type = None

        # Fallback to a safe generic if still unknown (better than mislabeling)
        if not mime_type:
            mime_type = "application/octet-stream"

        # Use the original filename as the suggested download/playback name when available.
        suggested_filename = job.original_filename or audio_path.name or f"{job.id}"
        headers = {"Content-Disposition": f'inline; filename="{suggested_filename}"'}
        return FileResponse(path=str(audio_path), media_type=mime_type, headers=headers)
    finally:
        session.close()

@app.delete("/jobs/{job_id}")
async def delete_job(job_id: str, request: Request):
    if not is_local(job_id):
        return await proxy_to_owner(job_id, "", request.method, request.query_params, headers=request.headers)
    
    session = SessionLocal()
    try:
        job = session.get(Job, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Delete storage
        storage_root = STORAGE_DIR.resolve()
        try:
            pattern = f"{job.id}*"
            for p in storage_root.glob(pattern):
                if p.is_dir():
                    shutil.rmtree(p)
                else:
                    p.unlink(missing_ok=True)
        except Exception:
            logger.exception(f"Error cleaning storage for {job.id}")

        session.delete(job)
        session.commit()
        return {"status": "ok", "job_id": job_id}
    finally:
        session.close()

@app.get("/admin/jobs")
def get_admin_jobs(status: Optional[str] = None, since: Optional[str] = None):
    session = SessionLocal()
    try:
        query = session.query(Job)
        if status:
            query = query.filter(Job.status == status)
        if since:
            # Parse ISO8601
            try:
                dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
                query = query.filter(Job.created_at >= dt)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid since format")
        
        jobs = query.all()
        return {
            "server": get_self_name(),
            "jobs": [
                {
                    "job_id": job.id,
                    "status": job.status.value,
                    "created_at": job.created_at.isoformat() if job.created_at else None,
                    "updated_at": job.updated_at.isoformat() if job.updated_at else None,
                    "language": (to_iso_code(json.loads(job.result_json).get("language"), LANG_CODE_FORMAT) if job.result_json else None),
                    "language_label": (get_language_label(json.loads(job.result_json).get("language")) if job.result_json else None),
                    "probability": (json.loads(job.result_json).get("probability") if job.result_json else None),
                }
                for job in jobs
            ]
        }
    finally:
        session.close()

@app.get("/cluster/jobs")
async def get_cluster_jobs_endpoint(
    request: Request,
    status: Optional[str] = None, 
    since: Optional[str] = None, 
    limit: Optional[int] = None
):
    return await aggregate_cluster_jobs(status, since, limit)

@app.get("/health")
def health_check():
    return {"status": "ok", "node": get_self_name()}

@app.get("/cluster/nodes")
async def get_cluster_nodes():
    return await check_cluster_health()

@app.get("/cluster/local-metrics")
def get_local_metrics_endpoint():
    """
    Internal endpoint to expose local metrics for aggregation.
    """
    return prom_metrics.get_local_metrics()

@app.get("/cluster/metrics-summary")
async def get_metrics_summary_endpoint():
    """
    Aggregated metrics summary for the UI.
    """
    from langid_service.cluster.dashboard import aggregate_cluster_metrics
    return await aggregate_cluster_metrics()
