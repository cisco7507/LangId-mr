import io
import os
import json
import shutil
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from langid_service.app.main import app
from langid_service.app.config import STORAGE_DIR
from langid_service.app.utils import gen_uuid
from langid_service.app.database import SessionLocal
from langid_service.app.models.models import Job, JobStatus

client = TestClient(app)

TEST_ASSETS = Path(__file__).resolve().parents[1] / "test_assets"

@pytest.fixture(autouse=True)
def setup_and_teardown(tmp_path, monkeypatch):
    # Ensure a clean storage dir for the test
    test_storage = tmp_path / "storage"
    test_storage.mkdir()
    monkeypatch.setenv("STORAGE_DIR", str(test_storage))

    # reload STORAGE_DIR from config by importing module path directly
    # (the app modules read STORAGE_DIR at import time, so we also patch the attribute)
    # Note: in-process tests rely on the app using the configured STORAGE_DIR variable
    from importlib import reload
    import langid_service.app.config as config_mod
    reload(config_mod)
    # ensure the module-level STORAGE_DIR object is updated
    from langid_service.app import utils as utils_mod
    reload(utils_mod)

    yield

    # cleanup (tmp_path is auto-removed)


def _write_sample_mp3(dest: Path):
    # Create a tiny fake MP3 header + some bytes so 'file' would detect it
    # This isn't a real MP3 but sufficient for mimetypes.guess_type to rely on extension.
    data = b"\xff\xfb\x50\x80" + b"\x00" * 1024
    with open(dest, "wb") as f:
        f.write(data)


def test_audio_endpoint_reports_wrong_mime_for_unprefixed_file(monkeypatch, tmp_path):
    """
    Simulate storing an MP3 file without an extension (saved as job_id) and
    verify the audio endpoint's Content-Type is not audio/mpeg (i.e., the bug).
    """
    # Prepare storage path and fake mp3 content stored without an extension
    job_id = gen_uuid()
    storage_dir = Path(os.getenv("STORAGE_DIR"))
    storage_dir.mkdir(parents=True, exist_ok=True)

    audio_path = storage_dir / job_id
    _write_sample_mp3(audio_path)

    # Insert a DB row for the job pointing to that input_path
    session = SessionLocal()
    try:
        job = Job(
            id=job_id,
            status=JobStatus.succeeded,
            input_path=str(audio_path),
            original_filename="sample.mp3",
        )
        session.add(job)
        session.commit()
    finally:
        session.close()

    # Request the audio endpoint
    resp = client.get(f"/jobs/{job_id}/audio")

    # Show for debugging if needed
    assert resp.status_code == 200

    content_type = resp.headers.get("content-type", "")

    # After fixing the storage and MIME detection, the endpoint should
    # return the correct audio MIME (audio/mpeg) for MP3 uploads.
    assert content_type == "audio/mpeg", f"Expected audio/mpeg, got: {content_type}"
