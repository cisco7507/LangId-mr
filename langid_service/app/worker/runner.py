# langid_service/app/worker/runner.py
import os
import json
from datetime import datetime, UTC
from typing import Optional
from sqlalchemy.orm import Session
from loguru import logger
from ..database import SessionLocal
from ..models.models import Job, JobStatus
from ..config import MAX_RETRIES
from ..services.detector import detect_language
from .. import metrics
import threading

CLAIM_LOCK = threading.Lock()

def _mock_detect(file_path: str):
    name = os.path.basename(file_path).lower()
    if "fr" in name:
        lang, prob = "fr", 0.95
    elif "en" in name:
        lang, prob = "en", 0.95
    else:
        lang, prob = "en", 0.6
    return {
        "language_raw": lang,
        "language_mapped": lang if lang in ("en","fr") else "unknown",
        "probability": float(prob),
        "transcript_snippet": None,
        "processing_ms": 1,
        "model": "mock",
        "info": {"duration": None, "vad": True},
    }

def process_one(session: Session, job: Job) -> None:
    logger.info(f"Processing job {job.id}")
    job.status = JobStatus.running
    job.progress = 10
    job.updated_at = datetime.now(UTC)
    session.commit()
    metrics.LANGID_JOBS_RUNNING.inc()

    try:
        if os.environ.get("USE_MOCK_DETECTOR", "0") == "1":
            result = _mock_detect(job.input_path)
        else:
            result = detect_language(job.input_path)

        job.progress = 90
        session.commit()

        job.result_json = json.dumps(result)
        job.status = JobStatus.succeeded
        job.progress = 100
        job.updated_at = datetime.now(UTC)
        session.commit()
        logger.info(f"Job {job.id} succeeded")
        metrics.LANGID_JOBS_TOTAL.labels(status="succeeded").inc()
        processing_time = (job.updated_at - job.created_at).total_seconds()
        metrics.LANGID_PROCESSING_SECONDS.observe(processing_time)
    except Exception as e:
        logger.exception(f"Job {job.id} failed: {e}")
        job.attempts += 1
        job.error = str(e)
        job.status = JobStatus.queued if job.attempts <= MAX_RETRIES else JobStatus.failed
        job.updated_at = datetime.now(UTC)
        session.commit()
        metrics.LANGID_JOBS_TOTAL.labels(status="failed").inc()
    finally:
        metrics.LANGID_JOBS_RUNNING.dec()

#def work_once() -> Optional[str]:
#    session = SessionLocal()
#    try:
#        metrics.LANGID_ACTIVE_WORKERS.inc()
#        job = session.query(Job).filter(Job.status == JobStatus.queued).order_by(Job.created_at.asc()).with_for_update().first()
#        if not job:
#            return None
#        process_one(session, job)
#        return job.id
#    finally:
#        metrics.LANGID_ACTIVE_WORKERS.dec()
#       session.close()
def work_once() -> Optional[str]:
    session = SessionLocal()
    try:
        metrics.LANGID_ACTIVE_WORKERS.inc()

        # ---- Atomic claim section: only one thread at a time ----
        with CLAIM_LOCK:
            # 1) find the oldest queued job
            job = (
                session.query(Job)
                .filter(Job.status == JobStatus.queued)
                .order_by(Job.created_at.asc())
                .first()
            )
            if not job:
                return None

            # 2) mark it as running *before* leaving the lock
            job.status = JobStatus.running
            job.progress = 10
            job.updated_at = datetime.now(UTC)
            session.commit()
            claimed_id = job.id
        # ---- end atomic claim section ----

        # Now process outside the lock
        process_one(session, job)
        return claimed_id
    finally:
        metrics.LANGID_ACTIVE_WORKERS.dec()
        session.close()

def process_one_sync(job_id: str, db_session: Session) -> None:
    """
    Processes a single job synchronously for deterministic testing.
    """
    job = db_session.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise ValueError(f"Job not found: {job_id}")
    process_one(db_session, job)
