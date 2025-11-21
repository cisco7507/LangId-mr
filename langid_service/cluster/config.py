
from typing import Dict, Optional
import os
import json
from pathlib import Path
from pydantic import BaseModel

class ClusterConfig(BaseModel):
    self_name: str
    nodes: Dict[str, str]
    health_check_interval_seconds: int = 5
    internal_request_timeout_seconds: int = 5

_config: Optional[ClusterConfig] = None

def load_cluster_config() -> ClusterConfig:
    global _config
    if _config:
        return _config

    # Default fallback path is cluster_config.json in the current directory
    env_path = os.getenv("LANGID_CLUSTER_CONFIG_FILE")
    if env_path:
        config_path = Path(env_path)
    else:
        # Fallback to a file in the parent directory of 'langid_service' or current dir
        # Let's try to find a reasonable default.
        # Assuming running from project root.
        config_path = Path("cluster_config.json")

    if not config_path.exists():
        # If no config file, we default to a standalone mode for safety/dev
        # This allows the app to start even if not configured for cluster, 
        # acting as a single node.
        # We use a default name "standalone"
        return ClusterConfig(
            self_name="standalone",
            nodes={"standalone": "http://localhost:8000"},
            health_check_interval_seconds=5,
            internal_request_timeout_seconds=5
        )

    with open(config_path, "r") as f:
        data = json.load(f)
    
    config = ClusterConfig(**data)

    if config.self_name not in config.nodes:
        raise ValueError(f"self_name '{config.self_name}' not found in nodes: {list(config.nodes.keys())}")

    _config = config
    return config

def get_self_name() -> str:
    return load_cluster_config().self_name

def get_nodes() -> Dict[str, str]:
    return load_cluster_config().nodes

def get_node_url(name: str) -> str:
    return load_cluster_config().nodes.get(name, "")
