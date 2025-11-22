
import pytest
from unittest.mock import patch, AsyncMock, Mock
from httpx import AsyncClient, RequestError
from fastapi.testclient import TestClient
from langid_service.app.main import app
from langid_service.cluster.router import parse_job_owner, is_local

# 7.1 job id prefix tests

def test_job_id_prefix_on_creation(client, mock_cluster_config):
    # POST /jobs -> job_id starts with "node-a-"
    # We need to mock the upload file
    files = {'file': ('test.wav', b'fake audio content', 'audio/wav')}
    response = client.post("/jobs", files=files)
    assert response.status_code == 200
    data = response.json()
    job_id = data["job_id"]
    assert job_id.startswith("node-a-")

def test_parse_job_owner_valid(mock_cluster_config):
    owner, bare_id = parse_job_owner("node-b-1234")
    assert owner == "node-b"
    assert bare_id == "1234"

def test_parse_job_owner_invalid_no_dash():
    with pytest.raises(ValueError):
        parse_job_owner("invalid")

def test_parse_job_owner_unknown_prefix(mock_cluster_config):
    # This is implicitly tested by routing logic which checks if owner is in nodes
    # But let's check is_local behavior
    assert is_local("node-a-123") is True
    assert is_local("node-b-123") is False
    assert is_local("unknown-123") is False

# 7.2 routing tests

def test_get_job_local_routes_locally(client, mock_cluster_config):
    # Create a local job first to ensure it exists in DB
    files = {'file': ('test.wav', b'fake audio content', 'audio/wav')}
    create_resp = client.post("/jobs", files=files)
    job_id = create_resp.json()["job_id"]
    
    # Ensure it is local
    assert job_id.startswith("node-a-")
    
    # Mock proxy to ensure it is NOT called
    with patch("langid_service.app.main.proxy_to_owner") as mock_proxy:
        resp = client.get(f"/jobs/{job_id}")
        assert resp.status_code == 200
        mock_proxy.assert_not_called()

@pytest.mark.asyncio
async def test_get_job_remote_routes_via_proxy(mock_cluster_config):
    job_id = "node-b-999"
    
    # Mock httpx.AsyncClient to simulate remote response
    with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value.status_code = 200
        mock_request.return_value.content = b'{"status": "queued"}'
        mock_request.return_value.headers = {"content-type": "application/json"}
        # Ensure json() returns synchronously
        mock_request.return_value.json = Mock(return_value={"status": "queued"})
        
        with TestClient(app) as client:
            resp = client.get(f"/jobs/{job_id}")
            assert resp.status_code == 200
            assert resp.json() == {"status": "queued"}
            
            # Verify proxy called with correct URL
            call_args = mock_request.call_args
            assert call_args is not None
            # call_args is (args, kwargs)
            # If called with keyword args: kwargs['url']
            # If called with positional args: args[1] (method is 0)
            args, kwargs = call_args
            if "url" in kwargs:
                url = kwargs["url"]
            else:
                # Assuming method, url, ...
                url = args[1]
                
            assert url == "http://node-b.internal:8080/jobs/node-b-999"
            assert kwargs["params"]["internal"] == "1"

@pytest.mark.asyncio
async def test_get_job_remote_owner_unreachable(mock_cluster_config):
    job_id = "node-b-999"
    
    # Mock httpx to raise error
    with patch("httpx.AsyncClient.request", side_effect=RequestError("Connection error", request=Mock())):
        with TestClient(app) as client:
            resp = client.get(f"/jobs/{job_id}")
            assert resp.status_code == 503
            data = resp.json()
            assert data["error"] == "owner_node_unreachable"
            assert data["owner"] == "node-b"
