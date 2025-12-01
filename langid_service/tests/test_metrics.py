import pytest
from fastapi.testclient import TestClient
from langid_service.app.main import app
from langid_service.metrics import prometheus as prom_metrics
from langid_service.app import metrics as app_metrics
from unittest.mock import patch, MagicMock, AsyncMock
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

def test_metrics_endpoint_exposes_basic_metrics():
    response = client.get("/metrics")
    assert response.status_code == 200
    assert b"langid_jobs_submitted_total" in response.content
    assert b"langid_jobs_owned_total" in response.content
    assert b"langid_jobs_active" in response.content
    assert b"langid_node_up" in response.content

@pytest.mark.asyncio
async def test_jobs_submitted_and_owned_metrics_increment(tmp_path):
    # Mock dependencies
    # Mock dependencies
    with patch("langid_service.cluster.scheduler.scheduler.next_target", new_callable=AsyncMock) as mock_next:
        mock_next.return_value = "node-a"
        with patch("langid_service.app.main.get_self_name", return_value="node-a"):
            with patch("langid_service.app.main.get_nodes", return_value={"node-a": "http://node-a"}):
                with patch("langid_service.app.main.create_job_local", new_callable=AsyncMock) as mock_local:
                    from langid_service.app.schemas import EnqueueResponse
                    mock_local.return_value = EnqueueResponse(job_id="node-a-123", status="queued")
                
                # Clear internal state
                prom_metrics._jobs_submitted_counts.clear()
                
                # Submit a job
                response = client.post("/jobs", files={"file": ("test.wav", b"fake audio")})
                assert response.status_code == 200
                
                # Check internal state for increment
                # We expect ingress=node-a, target=node-a
                assert prom_metrics._jobs_submitted_counts.get(("node-a", "node-a")) == 1
                
                # Check metrics endpoint for presence of the metric family
                response = client.get("/metrics")
                assert response.status_code == 200
                assert b"langid_jobs_submitted_total" in response.content

def test_metrics_summary_structure():
    # Reset in-memory state
    prom_metrics._jobs_submitted_counts.clear()
    prom_metrics._jobs_owned_counts.clear()
    prom_metrics._node_up_status.clear()
    
    # Set some internal state
    prom_metrics.increment_jobs_submitted("node-a", "node-b")
    prom_metrics.increment_jobs_owned("node-b")
    prom_metrics.set_node_up("node-b", 1)
    
    with patch("langid_service.cluster.config.load_cluster_config") as mock_load, \
         patch("langid_service.cluster.dashboard.httpx.AsyncClient") as mock_client_cls:
        
        mock_conf = MagicMock()
        mock_conf.nodes = {"node-a": "http://node-a", "node-b": "http://node-b"}
        mock_load.return_value = mock_conf
        
        # Mock the async client context manager and get method
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        
        # Define response for node-b (raw metrics format)
        mock_resp_b = MagicMock()
        mock_resp_b.status_code = 200
        mock_resp_b.json.return_value = {
            "jobs_submitted": {"node-a,node-b": 1},
            "jobs_owned": {"node-b": 1},
            "jobs_active": {},
            "node_up": {"node-b": True},
            "node_last_health": {"node-b": 1234567890.0}
        }
        
        # Define response for node-a (empty/default)
        mock_resp_a = MagicMock()
        mock_resp_a.status_code = 200
        mock_resp_a.json.return_value = {
            "jobs_submitted": {},
            "jobs_owned": {},
            "jobs_active": {},
            "node_up": {"node-a": True},
            "node_last_health": {"node-a": 1234567890.0}
        }

        def side_effect(url, **kwargs):
            if "node-b" in url:
                return mock_resp_b
            return mock_resp_a
            
        mock_client.get.side_effect = side_effect
        
        response = client.get("/cluster/metrics-summary")
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        
        node_b = next(n for n in data["nodes"] if n["name"] == "node-b")
        assert node_b["up"] is True
        assert node_b["jobs_owned_total"] == 1
        assert node_b["jobs_submitted_as_target"] == 1


# Tests for gate path classification and metrics
class TestGatePathClassification:
    """Tests for the gate path classification helper function."""

    @pytest.mark.parametrize("gate_decision,expected_path", [
        ("accepted_high_conf", "high_confidence"),
        ("accepted_mid_zone_en", "mid_zone_stopword"),
        ("accepted_mid_zone_fr", "mid_zone_stopword"),
        ("vad_retry", "vad_retry"),
        ("fallback", "fallback_scoring"),
        ("NO_SPEECH_MUSIC_ONLY", "music_only"),
    ])
    def test_classify_gate_path_known_decisions(self, gate_decision, expected_path):
        """Test that known gate decisions are classified correctly."""
        result = app_metrics.classify_gate_path(gate_decision)
        assert result == expected_path

    def test_classify_gate_path_unknown_decision(self):
        """Test that unknown gate decisions return 'unknown'."""
        result = app_metrics.classify_gate_path("some_unknown_decision")
        assert result == "unknown"

    def test_classify_gate_path_empty_string(self):
        """Test that empty string returns 'unknown'."""
        result = app_metrics.classify_gate_path("")
        assert result == "unknown"


class TestGatePathMetrics:
    """Tests for the gate path metrics recording."""

    def test_record_gate_path_decision_increments_counter(self):
        """Test that recording a gate path decision increments the counter."""
        # Get the current value (if any)
        gate_path = "high_confidence"
        initial_value = app_metrics.LANGID_GATE_PATH_DECISIONS.labels(gate_path=gate_path)._value.get()
        
        # Record the decision
        app_metrics.record_gate_path_decision("accepted_high_conf")
        
        # Check that the counter was incremented
        new_value = app_metrics.LANGID_GATE_PATH_DECISIONS.labels(gate_path=gate_path)._value.get()
        assert new_value == initial_value + 1

    def test_metrics_endpoint_exposes_gate_path_metric(self):
        """Test that the metrics endpoint exposes the gate path counter."""
        # Record at least one decision to ensure the metric exists
        app_metrics.record_gate_path_decision("accepted_high_conf")
        
        response = client.get("/metrics")
        assert response.status_code == 200
        assert b"langid_gate_path_decisions_total" in response.content

    def test_gate_paths_endpoint_returns_valid_json(self):
        """Test that the /metrics/gate-paths endpoint returns valid JSON."""
        response = client.get("/metrics/gate-paths")
        assert response.status_code == 200
        data = response.json()
        
        # Check structure
        assert "total_decisions" in data
        assert "by_gate_path" in data
        assert "percentages" in data
        
        # Check that expected gate paths are present
        expected_paths = {"high_confidence", "mid_zone_stopword", "vad_retry", 
                         "fallback_scoring", "music_only", "unknown"}
        assert expected_paths.issubset(set(data["by_gate_path"].keys()))
        assert expected_paths.issubset(set(data["percentages"].keys()))
