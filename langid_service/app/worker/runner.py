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
from ..lang_gate import detect_lang_en_fr_only
from ..services.detector import get_model
from ..services.audio_io import load_audio_mono_16k
from ..translate import translate_en_fr_only
from ..utils import truncate_to_words
from .. import metrics
import threading

CLAIM_LOCK = threading.Lock()

def process_one(session: Session, job: Job) -> None:
    logger.info(f"Processing job {job.id}")
    job.status = JobStatus.running
    job.progress = 10
    job.updated_at = datetime.now(UTC)
    session.commit()
    metrics.LANGID_JOBS_RUNNING.inc()

    try:
        # Load audio once from disk
        audio = load_audio_mono_16k(job.input_path)

        # Detect language with EN/FR gate using the in-memory audio
        lang_info = detect_lang_en_fr_only(audio)
        lang = lang_info["language"]

        # Transcribe the full audio clip using the chosen language
        model = get_model()
        segments, info = model.transcribe(
            audio,
            language=lang,
            beam_size=5,
            best_of=5,
            vad_filter=True,
            suppress_blank=True,
        )
        text = " ".join([s.text for s in segments])

        result = {
            "language": lang,
            "text": truncate_to_words(text),
            "raw": {
                "text": text,
                "info": info._asdict() if hasattr(info, '_asdict') else vars(info),
            }
        }

        # Translate if target language is provided
        if job.target_lang and job.target_lang != lang:
            translated_text = translate_en_fr_only(text, source_lang=lang, target_lang=job.target_lang)
            result["translated"] = True
            result["result"] = translated_text
            result["target_lang"] = job.target_lang
            if lang == "en":
                metrics.LANGID_TRANSLATE_EN2FR.inc()
            else:
                metrics.LANGID_TRANSLATE_FR2EN.inc()
        else:
            result["translated"] = False

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

def work_once() -> Optional[str]:
    session = SessionLocal()
    try:
        metrics.LANGID_ACTIVE_WORKERS.inc()

        with CLAIM_LOCK:
            job = (
                session.query(Job)
                .filter(Job.status == JobStatus.queued)
                .order_by(Job.created_at.asc())
                .first()
            )
            if not job:
                return None

            job.status = JobStatus.running
            job.progress = 10
            job.updated_at = datetime.now(UTC)
            session.commit()
            claimed_id = job.id

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
