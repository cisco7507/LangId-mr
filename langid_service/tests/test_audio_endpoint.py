
import pytest
import os
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from langid_service.app.main import app
from langid_service.app.models.models import Job, JobStatus
from langid_service.cluster.config import ClusterConfig

# We need to ensure the DB session is mocked correctly.
# The mock_db_session fixture from cluster/conftest.py is not automatically available here
# because this test file is in langid_service/tests/, not langid_service/tests/cluster/.
# We should copy the necessary fixture logic or import it if possible, but copying is safer for isolation.

@pytest.fixture
def mock_db_session(monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from langid_service.app.models import models
    from langid_service.app import main
    from sqlalchemy.pool import StaticPool
    
    engine = create_engine(
        "sqlite:///:memory:", 
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    models.Job.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    monkeypatch.setattr(main, "SessionLocal", SessionLocal)
    return SessionLocal()

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def mock_config():
    return ClusterConfig(
        self_name="node-a",
        nodes={
            "node-a": "http://node-a:8080",
            "node-b": "http://node-b:8080"
        },
        enable_round_robin=True
    )

def test_get_job_audio_local_success(mock_db_session, tmp_path, client):
    # Setup local job
    job_id = "node-a-audio-test"
    audio_file = tmp_path / "test_audio.wav"
    audio_file.write_bytes(b"fake audio content")
    
    job = Job(
        id=job_id,
        status=JobStatus.succeeded,
        input_path=str(audio_file),
        original_filename="original.wav"
    )
    mock_db_session.add(job)
    mock_db_session.commit()
    
    with patch("langid_service.cluster.config.load_cluster_config") as mock_load:
        mock_load.return_value = ClusterConfig(self_name="node-a", nodes={"node-a": "http://node-a"})
        
        response = client.get(f"/jobs/{job_id}/audio")
        
        assert response.status_code == 200
        assert response.content == b"fake audio content"
        assert response.headers["content-type"] in ["audio/wav", "audio/x-wav"]
        assert 'filename="original.wav"' in response.headers["content-disposition"]

def test_get_job_audio_job_not_found(mock_db_session, client):
    with patch("langid_service.cluster.config.load_cluster_config") as mock_load:
        mock_load.return_value = ClusterConfig(self_name="node-a", nodes={"node-a": "http://node-a"})
        
        response = client.get("/jobs/node-a-unknown/audio")
        assert response.status_code == 404
        assert response.json()["detail"] == "Job not found"

def test_get_job_audio_file_missing(mock_db_session, client):
    job_id = "node-a-missing-file"
    job = Job(
        id=job_id,
        status=JobStatus.succeeded,
        input_path="/non/existent/path.wav",
        original_filename="original.wav"
    )
    mock_db_session.add(job)
    mock_db_session.commit()
    
    with patch("langid_service.cluster.config.load_cluster_config") as mock_load:
        mock_load.return_value = ClusterConfig(self_name="node-a", nodes={"node-a": "http://node-a"})
        
        response = client.get(f"/jobs/{job_id}/audio")
        assert response.status_code == 404
        assert "Audio file not found" in response.json()["detail"]

@pytest.mark.asyncio
async def test_get_job_audio_remote_proxies_to_owner(mock_config, client):
    job_id = "node-b-remote-audio"
    
    with patch("langid_service.cluster.config.load_cluster_config", return_value=mock_config):
        with patch("langid_service.app.main.proxy_to_owner", new_callable=AsyncMock) as mock_proxy:
            from fastapi import Response
            mock_proxy.return_value = Response(content=b"remote audio content", media_type="audio/wav")

            response = client.get(f"/jobs/{job_id}/audio")
            
            assert response.status_code == 200
            assert response.content == b"remote audio content"
            assert response.headers["content-type"] == "audio/wav"
            
            mock_proxy.assert_called_once()
            args, kwargs = mock_proxy.call_args
            assert args[0] == job_id
            assert args[1] == "/audio"

@pytest.mark.asyncio
async def test_get_job_audio_remote_owner_unreachable(mock_config, client):
    job_id = "node-b-unreachable"
    
    with patch("langid_service.cluster.config.load_cluster_config", return_value=mock_config):
        with patch("langid_service.app.main.proxy_to_owner", new_callable=AsyncMock) as mock_proxy:
            from fastapi import Response
            import json
            mock_proxy.return_value = Response(
                content=json.dumps({"error": "owner_node_unreachable", "owner": "node-b"}),
                status_code=503,
                media_type="application/json"
            )

            response = client.get(f"/jobs/{job_id}/audio")
            
            assert response.status_code == 503
            assert response.json()["error"] == "owner_node_unreachable"
