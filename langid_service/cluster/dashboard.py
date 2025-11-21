
import httpx
import asyncio
from typing import List, Dict, Any, Optional
from . import config as cluster_config

async def aggregate_cluster_jobs(
    status: Optional[str] = None, 
    since: Optional[str] = None, 
    limit: Optional[int] = None
) -> Dict[str, Any]:
    config = cluster_config.load_cluster_config()
    nodes_map = config.nodes
    
    async def fetch_node(name: str, url: str):
        target_url = f"{url.rstrip('/')}/admin/jobs"
        params = {}
        if status: params["status"] = status
        if since: params["since"] = since
        # We add internal=1 just in case, though not strictly required by prompt for admin endpoint
        params["internal"] = "1"
        
        try:
            async with httpx.AsyncClient(timeout=config.internal_request_timeout_seconds) as client:
                resp = await client.get(target_url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    jobs = data.get("jobs", [])
                    return {
                        "name": name,
                        "reachable": True,
                        "jobs": jobs,
                        "job_count": len(jobs)
                    }
        except Exception:
            pass
        
        return {
            "name": name,
            "reachable": False,
            "jobs": [],
            "job_count": 0
        }

    tasks = [fetch_node(name, url) for name, url in nodes_map.items()]
    results = await asyncio.gather(*tasks)
    
    all_jobs = []
    nodes_summary = []
    
    for res in results:
        nodes_summary.append({
            "name": res["name"],
            "reachable": res["reachable"],
            "job_count": res["job_count"]
        })
        all_jobs.extend(res["jobs"])
        
    # Sort by created_at desc
    # We assume created_at is a string that sorts correctly (ISO8601)
    all_jobs.sort(key=lambda x: x.get("created_at", "") or "", reverse=True)
    
    if limit is not None:
        all_jobs = all_jobs[:limit]
        
    return {
        "items": all_jobs,
        "nodes": nodes_summary
    }
