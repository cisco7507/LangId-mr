
import pytest
from unittest.mock import patch, AsyncMock, Mock
from httpx import AsyncClient
from fastapi.testclient import TestClient
from langid_service.app.main import app

# 7.4 cluster dashboard tests

@pytest.mark.asyncio
async def test_cluster_jobs_aggregate(mock_cluster_config):
    # Mock 2 nodes responses
    # node-a -> 1 job
    # node-b -> 2 jobs
    
    node_a_jobs = {"jobs": [{"job_id": "node-a-1", "created_at": "2023-01-01T12:00:00"}]}
    node_b_jobs = {"jobs": [
        {"job_id": "node-b-1", "created_at": "2023-01-01T13:00:00"},
        {"job_id": "node-b-2", "created_at": "2023-01-01T11:00:00"}
    ]}
    
    async def mock_get(url, params=None):
        mock_resp = Mock()
        mock_resp.status_code = 200
        if "node-a" in url:
            mock_resp.json = Mock(return_value=node_a_jobs)
        elif "node-b" in url:
            mock_resp.json = Mock(return_value=node_b_jobs)
        return mock_resp

    with patch("httpx.AsyncClient.get", side_effect=mock_get):
        with TestClient(app) as client:
            resp = client.get("/cluster/jobs")
            assert resp.status_code == 200
            data = resp.json()
            
            assert len(data["items"]) == 3
            # Check sorting (desc by created_at)
            # node-b-1 (13:00) -> node-a-1 (12:00) -> node-b-2 (11:00)
            assert data["items"][0]["job_id"] == "node-b-1"
            assert data["items"][1]["job_id"] == "node-a-1"
            assert data["items"][2]["job_id"] == "node-b-2"
            
            assert len(data["nodes"]) == 2
            node_names = sorted([n["name"] for n in data["nodes"]])
            assert node_names == ["node-a", "node-b"]

@pytest.mark.asyncio
async def test_cluster_jobs_unreachable_node(mock_cluster_config):
    # node-b call fails
    async def mock_get(url, params=None):
        if "node-b" in url:
            raise Exception("Timeout")
        
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json = Mock(return_value={"jobs": [{"job_id": "node-a-1"}]})
        return mock_resp

    with patch("httpx.AsyncClient.get", side_effect=mock_get):
        with TestClient(app) as client:
            resp = client.get("/cluster/jobs")
            data = resp.json()
            
            assert len(data["items"]) == 1
            assert data["items"][0]["job_id"] == "node-a-1"
            
            nodes_map = {n["name"]: n for n in data["nodes"]}
            assert nodes_map["node-a"]["reachable"] is True
            assert nodes_map["node-b"]["reachable"] is False
            assert nodes_map["node-b"]["job_count"] == 0

@pytest.mark.asyncio
async def test_cluster_jobs_status_filter(mock_cluster_config):
    # Use ?status=running
    # Mock responses accordingly
    
    async def mock_get(url, params=None):
        assert params["status"] == "running"
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json = Mock(return_value={"jobs": []})
        return mock_resp

    with patch("httpx.AsyncClient.get", side_effect=mock_get):
        with TestClient(app) as client:
            client.get("/cluster/jobs?status=running")
