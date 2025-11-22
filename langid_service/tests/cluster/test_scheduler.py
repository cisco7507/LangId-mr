
import pytest
import json
import os
from unittest.mock import patch, MagicMock, mock_open
from langid_service.cluster.scheduler import RoundRobinScheduler
from langid_service.cluster.config import ClusterConfig

@pytest.fixture
def mock_config():
    return ClusterConfig(
        self_name="node-a",
        nodes={
            "node-a": "http://node-a:8080",
            "node-b": "http://node-b:8080",
            "node-c": "http://node-c:8080"
        },
        enable_round_robin=True,
        rr_state_file="/tmp/rr_state.json"
    )

@pytest.mark.asyncio
async def test_round_robin_sequence_basic(mock_config):
    with patch("langid_service.cluster.config.load_cluster_config", return_value=mock_config):
        scheduler = RoundRobinScheduler()
        # Prevent loading state from disk
        scheduler._load_state = MagicMock()
        # Reset index for test
        scheduler._index = 0
        
        # Expected sequence: node-a, node-b, node-c, node-a ... (sorted keys)
        
        t1 = await scheduler.next_target()
        assert t1 == "node-a"
        
        t2 = await scheduler.next_target()
        assert t2 == "node-b"
        
        t3 = await scheduler.next_target()
        assert t3 == "node-c"
        
        t4 = await scheduler.next_target()
        assert t4 == "node-a"

@pytest.mark.asyncio
async def test_round_robin_persist_index(mock_config):
    with patch("langid_service.cluster.config.load_cluster_config", return_value=mock_config):
        # Mock file operations
        with patch("builtins.open", mock_open()) as m_open:
            scheduler = RoundRobinScheduler()
            scheduler._index = 0
            
            await scheduler.next_target() # node-a, index becomes 1
            
            # Verify save
            m_open.assert_called_with("/tmp/rr_state.json", "w")
            handle = m_open()
            # We expect json.dump to write {"index": 1}
            # Note: json.dump writes chunks, so checking exact write call might be tricky.
            # But we can check if write was called.
            assert handle.write.called

@pytest.mark.asyncio
async def test_round_robin_load_state(mock_config):
    with patch("langid_service.cluster.config.load_cluster_config", return_value=mock_config):
        # Mock file existence and content
        with patch("os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data='{"index": 2}')):
                scheduler = RoundRobinScheduler()
                # Force re-init or check if it loads on init
                # The class uses __new__ singleton logic in my thought process but I implemented it as a global instance.
                # However, in the test I am instantiating a new object.
                # My implementation:
                # def __init__(self):
                #     self._index = 0
                #     self._lock = asyncio.Lock()
                #     self._initialized = False
                # ...
                # async def next_target(self):
                #     self._ensure_initialized() ...
                
                # So state is loaded on first call to next_target
                
                target = await scheduler.next_target()
                # Index was 2. Nodes: a, b, c.
                # 2 % 3 = 2 -> node-c
                assert target == "node-c"
                # Index becomes 3 -> 0
