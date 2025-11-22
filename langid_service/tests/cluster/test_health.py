
import pytest
from unittest.mock import patch, AsyncMock, Mock
from httpx import AsyncClient
from fastapi.testclient import TestClient
from langid_service.app.main import app

# 7.5 cluster health tests

@pytest.mark.asyncio
async def test_cluster_nodes_all_up(mock_cluster_config):
    # Mock /health for all nodes -> 200
    
    async def mock_get(url, params=None):
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json = Mock(return_value={})
        return mock_resp

    with patch("httpx.AsyncClient.get", side_effect=mock_get):
        with TestClient(app) as client:
            resp = client.get("/cluster/nodes")
            assert resp.status_code == 200
            data = resp.json()
            
            assert len(data) == 2
            for node in data:
                assert node["status"] == "up"
                assert node["last_seen"] is not None

@pytest.mark.asyncio
async def test_cluster_nodes_some_down(mock_cluster_config):
    # Mock node-b /health timeout
    
    async def mock_get(url, params=None):
        if "node-b" in url:
            raise Exception("Timeout")
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json = Mock(return_value={})
        return mock_resp

    with patch("httpx.AsyncClient.get", side_effect=mock_get):
        with TestClient(app) as client:
            resp = client.get("/cluster/nodes")
            data = resp.json()
            
            nodes_map = {n["name"]: n for n in data}
            assert nodes_map["node-a"]["status"] == "up"
            assert nodes_map["node-b"]["status"] == "down"
