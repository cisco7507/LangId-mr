import pytest
import numpy as np
from unittest.mock import patch, MagicMock
from langid_service.app.worker.runner import process_one_sync
from langid_service.app.database import SessionLocal

@patch("langid_service.app.worker.runner.detect_lang_en_fr_only")
@patch("langid_service.app.worker.runner.load_audio_mono_16k", return_value=np.zeros(16000, dtype=np.float32))
@patch("langid_service.app.main.load_audio_mono_16k", return_value=np.zeros(16000, dtype=np.float32))
def test_submit_and_detect_sync(mock_main_load_audio, mock_runner_load_audio, mock_detect_lang, client):
    """
    Tests job submission and synchronous processing.
    """
    # Force the language gate to return a clean, high-confidence result so we
    # don't hit the fallback path and the real Whisper model.
    mock_detect_lang.return_value = {
        "language": "en",
        "probability": 0.9,
        "method": "direct",
    }

    with open("langid_service/tests/data/golden/en_1.wav", "rb") as f:
        data = {"file": ("clip_en.wav", f, "audio/wav")}
        # Submit the job
        r = client.post("/jobs", files=data)
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]
    assert r.json()["status"] == "queued"

    # Process the job synchronously
    db_session = SessionLocal()
    try:
        process_one_sync(job_id, db_session)
    finally:
        db_session.close()

    # Check the job status
    s = client.get(f"/jobs/{job_id}")
    assert s.status_code == 200
    js = s.json()
    assert js["status"] == "succeeded", f"Job failed: {js.get('error')}"

    # Confirm the result endpoint works
    res = client.get(f"/jobs/{job_id}/result")
    assert res.status_code == 200, res.text
    js = res.json()
    assert "language" in js
    assert "probability" in js

@patch("langid_service.app.main.load_audio_mono_16k", return_value=np.zeros(16000, dtype=np.float32))
def test_get_result_for_incomplete_job(mock_load_audio, client):
    """
    Tests that the result endpoint returns 409 for incomplete jobs.
    """
    with open("langid_service/tests/data/golden/en_1.wav", "rb") as f:
        data = {"file": ("clip_en.wav", f, "audio/wav")}
        # Submit the job
        r = client.post("/jobs", files=data)
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]
    # Check the result endpoint
    res = client.get(f"/jobs/{job_id}/result")
    assert res.status_code == 409, res.text

def test_get_jobs(client):
    r = client.get("/jobs")
    assert r.status_code == 200, r.text
    js = r.json()
    assert "jobs" in js
    assert isinstance(js["jobs"], list)

@patch("langid_service.app.main.load_audio_mono_16k", return_value=np.zeros(16000, dtype=np.float32))
@patch("langid_service.app.worker.runner.get_model")
def test_delete_job(mock_get_model, mock_load_audio, client):
    with open("langid_service/tests/data/golden/en_1.wav", "rb") as f:
        data = {"file": ("clip_en.wav", f, "audio/wav")}
        r = client.post("/jobs", files=data)
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]

    # Delete the job
    r = client.request("DELETE", "/jobs", json={"job_ids": [job_id]})
    assert r.status_code == 200, r.text
    js = r.json()
    assert js["status"] == "ok"
    assert js["deleted_count"] == 1

    # Verify the job is gone
    r = client.get(f"/jobs/{job_id}")
    assert r.status_code == 404, r.text

def test_metrics_prometheus(client):
    r = client.get("/metrics/prometheus")
    assert r.status_code == 200, r.text
    text = r.text
    assert "langid_jobs_total" in text
    assert "langid_jobs_running" in text
    assert "langid_processing_seconds" in text
    assert "langid_active_workers" in text
    assert "langid_audio_seconds" in text