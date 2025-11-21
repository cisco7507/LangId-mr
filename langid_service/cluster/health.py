
import httpx
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from . import config as cluster_config
from langid_service.metrics import prometheus as prom_metrics

# In-memory store for last_seen timestamps
_last_seen_map: Dict[str, str] = {}

async def check_cluster_health() -> List[Dict[str, Any]]:
    config = cluster_config.load_cluster_config()
    nodes_map = config.nodes
    
    async def check_node(name: str, url: str):
        target_url = f"{url.rstrip('/')}/health"
        try:
            async with httpx.AsyncClient(timeout=config.internal_request_timeout_seconds) as client:
                resp = await client.get(target_url)
                if resp.status_code == 200:
                    now = datetime.now(timezone.utc)
                    now_str = now.isoformat()
                    _last_seen_map[name] = now_str
                    
                    # Metrics
                    prom_metrics.set_node_up(name, 1)
                    prom_metrics.set_node_last_health_timestamp(name, now.timestamp())
                    
                    return {
                        "name": name,
                        "status": "up",
                        "last_seen": now_str
                    }
        except Exception:
            pass
        
        # Metrics
        prom_metrics.set_node_up(name, 0)
        
        return {
            "name": name,
            "status": "down",
            "last_seen": _last_seen_map.get(name)
        }

    tasks = [check_node(name, url) for name, url in nodes_map.items()]
    results = await asyncio.gather(*tasks)
    
    # Sort by name
    results.sort(key=lambda x: x["name"])
    
    return results
