import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from langid_service.app.main import app
from langid_service.app.models.languages import LanguageCodeFormat
from langid_service.app.schemas import JobStatusResponse, ResultResponse
import json
from datetime import datetime

client = TestClient(app)

@pytest.fixture
def mock_job_data():
    return {
        "job_id": "test-job-1",
        "status": "succeeded",
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "attempts": 1,
        "result_json": json.dumps({
            "language": "fr",
            "probability": 0.99,
            "processing_ms": 100
        }),
        "error": None,
        "input_path": "/tmp/test.wav",
        "original_filename": "test.wav"
    }

from langid_service.app.models.models import JobStatus

@pytest.fixture
def mock_job_obj(mock_job_data):
    class MockJob:
        def __init__(self, data):
            self.id = data["job_id"]
            self.status = JobStatus.succeeded
            self.created_at = data["created_at"]
            self.updated_at = data["updated_at"]
            self.attempts = data["attempts"]
            self.result_json = data["result_json"]
            self.error = data["error"]
            self.input_path = data["input_path"]
            self.original_filename = data["original_filename"]
            self.progress = 0
    return MockJob(mock_job_data)

def test_get_jobs_iso639_1(mock_job_obj):
    with patch("langid_service.app.main.SessionLocal") as mock_session_cls:
        mock_session = mock_session_cls.return_value
        mock_session.query.return_value.order_by.return_value.all.return_value = [mock_job_obj]
        
        with patch("langid_service.app.main.LANG_CODE_FORMAT", LanguageCodeFormat.ISO639_1):
            response = client.get("/jobs")
            assert response.status_code == 200
            data = response.json()
            assert data["jobs"][0]["language"] == "fr"
            assert data["jobs"][0]["language_label"] == "French"

def test_get_jobs_iso639_2b(mock_job_obj):
    with patch("langid_service.app.main.SessionLocal") as mock_session_cls:
        mock_session = mock_session_cls.return_value
        mock_session.query.return_value.order_by.return_value.all.return_value = [mock_job_obj]
        
        with patch("langid_service.app.main.LANG_CODE_FORMAT", LanguageCodeFormat.ISO639_2B):
            response = client.get("/jobs")
            assert response.status_code == 200
            data = response.json()
            assert data["jobs"][0]["language"] == "fre"
            assert data["jobs"][0]["language_label"] == "French"

def test_get_jobs_iso639_3(mock_job_obj):
    with patch("langid_service.app.main.SessionLocal") as mock_session_cls:
        mock_session = mock_session_cls.return_value
        mock_session.query.return_value.order_by.return_value.all.return_value = [mock_job_obj]
        
        with patch("langid_service.app.main.LANG_CODE_FORMAT", LanguageCodeFormat.ISO639_3):
            response = client.get("/jobs")
            assert response.status_code == 200
            data = response.json()
            assert data["jobs"][0]["language"] == "fra"
            assert data["jobs"][0]["language_label"] == "French"

def test_get_result_iso639_2t(mock_job_obj):
    with patch("langid_service.app.main.SessionLocal") as mock_session_cls:
        mock_session = mock_session_cls.return_value
        # Mock session.get() since main.py uses it
        mock_session.get.return_value = mock_job_obj
        
        with patch("langid_service.app.main.LANG_CODE_FORMAT", LanguageCodeFormat.ISO639_2T):
            with patch("langid_service.app.main.is_local", return_value=True):
                response = client.get("/jobs/test-job-1/result")
                assert response.status_code == 200
                data = response.json()
                assert data["language"] == "fra"
                assert data["language_label"] == "French"

def test_submit_job_invalid_lang():
    with patch("langid_service.app.main.LANG_CODE_FORMAT", LanguageCodeFormat.ISO639_3):
        # ISO639-3 expects "eng" or "fra", so "en" should be invalid if strict?
        # Wait, from_iso_code returns None if not found in mapping.
        # "en" is NOT in ISO639-3 mapping for EN (which is "eng").
        
        # Mock file upload
        files = {"file": ("test.wav", b"fake audio content", "audio/wav")}
        
        # Test with invalid code "en" when format is iso639-3
        response = client.post("/jobs?target_lang=en", files=files)
        assert response.status_code == 400
        assert "Invalid language code" in response.json()["detail"]

        # Test with valid code "eng"
        # We need to mock create_job_local or the internals to avoid actual processing
        with patch("langid_service.app.main.create_job_local") as mock_create:
            mock_create.return_value = {"job_id": "test-id", "status": "queued"}
            # Note: client.post calls submit_job which calls create_job_local.
            # But create_job_local is where validation happens.
            # So we cannot mock create_job_local if we want to test validation inside it.
            # We should mock what comes AFTER validation.
            pass

def test_submit_job_valid_lang_iso639_3():
    with patch("langid_service.app.main.LANG_CODE_FORMAT", LanguageCodeFormat.ISO639_3):
        files = {"file": ("test.wav", b"fake audio content", "audio/wav")}
        
        # Mock all the internals to avoid side effects
        with patch("langid_service.app.main.validate_upload"), \
             patch("langid_service.app.main.move_to_storage", return_value="/tmp/test.wav"), \
             patch("langid_service.app.main.SessionLocal") as mock_session_cls, \
             patch("langid_service.app.main.prom_metrics"), \
             patch("langid_service.app.main.ENFR_STRICT_REJECT", False), \
             patch("langid_service.app.main.gen_uuid", return_value="test-uuid-123"):
            
            mock_session = mock_session_cls.return_value
            mock_session.add.return_value = None
            mock_session.commit.return_value = None
            
            response = client.post("/jobs?target_lang=eng&internal=1", files=files)
            assert response.status_code == 200

