
import json
import os
import asyncio
from typing import List, Optional
from . import config as cluster_config

class RoundRobinScheduler:
    def __init__(self):
        self._index = 0
        self._lock = asyncio.Lock()
        self._initialized = False

    def _ensure_initialized(self):
        if self._initialized:
            return
        self._load_state()
        self._initialized = True

    def _load_state(self):
        config = cluster_config.load_cluster_config()
        if config.rr_state_file and os.path.exists(config.rr_state_file):
            try:
                with open(config.rr_state_file, 'r') as f:
                    data = json.load(f)
                    self._index = data.get('index', 0)
            except Exception:
                pass

    def _save_state(self):
        config = cluster_config.load_cluster_config()
        if config.rr_state_file:
            try:
                with open(config.rr_state_file, 'w') as f:
                    json.dump({'index': self._index}, f)
            except Exception:
                pass

    async def next_target(self) -> str:
        async with self._lock:
            self._ensure_initialized()
            config = cluster_config.load_cluster_config()
            
            if not config.enable_round_robin:
                return config.self_name

            nodes = sorted(config.nodes.keys())
            if not nodes:
                return config.self_name

            # Get current target
            target = nodes[self._index % len(nodes)]
            
            # Advance index
            self._index = (self._index + 1) % len(nodes)
            self._save_state()
            
            return target

# Global instance
scheduler = RoundRobinScheduler()
