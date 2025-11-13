# langid_service/app/worker/runner.py
import os
import json
from datetime import datetime, UTC
from typing import Optional
from sqlalchemy.orm import Session
from loguru import logger
from ..database import SessionLocal
from ..models.models import Job, JobStatus
from ..config import MAX_RETRIES, LANG_DETECT_MIN_PROB
from ..lang_gate import detect_lang_en_fr_only
from ..services.detector import get_model
from ..services.audio_io import load_audio_mono_16k
from ..translate import translate_en_fr_only
from ..utils import truncate_to_words
from .. import metrics
import threading

CLAIM_LOCK = threading.Lock()
SNIPPET_MAX_SECONDS = 15.0  # only transcribe the first N seconds for snippet

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

        # Extract language probability from gate output (fallback to 0.0 if missing)
        prob = float(lang_info.get("language_probability", lang_info.get("probability", 0.0)))

        # Decide whether to use VAD based on configured minimum probability
        use_vad = prob < LANG_DETECT_MIN_PROB

        # Transcribe only the first SNIPPET_MAX_SECONDS of audio for the snippet
        snippet_samples = int(SNIPPET_MAX_SECONDS * 16000)  # 16 kHz mono
        snippet_audio = audio[:snippet_samples]

        model = get_model()
        segments, info = model.transcribe(
            snippet_audio,
            language=lang,
            beam_size=5,
            best_of=5,
            vad_filter=use_vad,
            suppress_blank=True,
        )
        text = " ".join([s.text for s in segments])
        # Extract only the first 10 spoken words
        snippet = " ".join(text.split()[:10])

        # Make info JSON-serializable (TranscriptionOptions and other objects may be present)
        if hasattr(info, "_asdict"):
            raw_info = info._asdict()
        else:
            raw_info = {}
            for k, v in vars(info).items():
                try:
                    # keep primitives / simple containers as-is
                    json.dumps(v)
                    raw_info[k] = v
                except TypeError:
                    # fall back to string for non-serializable objects
                    raw_info[k] = str(v)

        # Drop noisy/verbose fields we don't need to store
        raw_info.pop("transcription_options", None)

        result = {
            "language": lang,
            "probability": prob,
            "text": snippet,
            "raw": {
                "text": snippet,
                "info": raw_info,
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
