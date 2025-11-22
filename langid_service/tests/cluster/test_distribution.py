
import pytest
import json
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from langid_service.app.main import app
from langid_service.cluster.config import ClusterConfig

client = TestClient(app)

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

@pytest.mark.asyncio
async def test_rr_assignments_cycle_through_nodes(mock_config):
    # We mock scheduler.next_target to return sequence
    with patch("langid_service.cluster.config.load_cluster_config", return_value=mock_config):
        with patch("langid_service.app.main.scheduler.next_target", side_effect=["node-a", "node-b"]):
            with patch("langid_service.app.main.create_job_local", new_callable=AsyncMock) as mock_local:
                # Mock return value must be an object with dict-like access or Pydantic model
                # EnqueueResponse is a Pydantic model.
                # We can just return a dict if we mock the return value of create_job_local correctly?
                # create_job_local returns EnqueueResponse.
                # But main.py awaits it.
                
                # Let's mock the return value to be a real EnqueueResponse or similar
                from langid_service.app.schemas import EnqueueResponse
                mock_local.return_value = EnqueueResponse(job_id="node-a-123", status="queued")
                
                with patch("langid_service.app.main.proxy_job_submission", new_callable=AsyncMock) as mock_proxy:
                    mock_proxy.return_value = MagicMock(status_code=200, body=b'{"job_id": "node-b-456", "status": "queued"}')

                    # First call -> node-a (local)
                    resp1 = client.post("/jobs", files={"file": ("test.wav", b"audio data")})
                    assert resp1.status_code == 200
                    assert resp1.json()["job_id"] == "node-a-123"
                    mock_local.assert_called_once()
                    mock_proxy.assert_not_called()
                    
                    # Reset mock_local
                    mock_local.reset_mock()
                    
                    # Second call -> node-b (proxy)
                    resp2 = client.post("/jobs", files={"file": ("test.wav", b"audio data")})
                    assert resp2.status_code == 200
                    assert resp2.json()["job_id"] == "node-b-456"
                    mock_proxy.assert_called_once()
                    mock_local.assert_not_called()

@pytest.mark.asyncio
async def test_rr_internal_flag_prevents_recursion(mock_config):
    with patch("langid_service.cluster.config.load_cluster_config", return_value=mock_config):
        with patch("langid_service.app.main.scheduler.next_target") as mock_scheduler:
            with patch("langid_service.app.main.create_job_local", new_callable=AsyncMock) as mock_local:
                from langid_service.app.schemas import EnqueueResponse
                mock_local.return_value = EnqueueResponse(job_id="node-a-789", status="queued")
                
                # Call with internal=1
                resp = client.post("/jobs?internal=1", files={"file": ("test.wav", b"audio data")})
                
                assert resp.status_code == 200
                mock_local.assert_called_once()
                # Scheduler should NOT be called
                mock_scheduler.assert_not_called()

@pytest.mark.asyncio
async def test_rr_target_node_unreachable_tries_next(mock_config):
    with patch("langid_service.cluster.config.load_cluster_config", return_value=mock_config):
        # Sequence: node-b (fails), node-a (succeeds)
        with patch("langid_service.app.main.scheduler.next_target", side_effect=["node-b", "node-a"]):
            with patch("langid_service.app.main.proxy_job_submission", new_callable=AsyncMock) as mock_proxy:
                # First proxy call returns 503
                mock_proxy.side_effect = [
                    MagicMock(status_code=503, body=b'{"error": "unreachable"}'),
                ]
                
                with patch("langid_service.app.main.create_job_local", new_callable=AsyncMock) as mock_local:
                    from langid_service.app.schemas import EnqueueResponse
                    mock_local.return_value = EnqueueResponse(job_id="node-a-fallback", status="queued")
                    
                    resp = client.post("/jobs", files={"file": ("test.wav", b"audio data")})
                    
                    assert resp.status_code == 200
                    assert resp.json()["job_id"] == "node-a-fallback"
                    
                    # Verify proxy was called for node-b
                    mock_proxy.assert_called_once()
                    # Verify local was called for node-a
                    mock_local.assert_called_once()
