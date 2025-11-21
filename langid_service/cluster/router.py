
import httpx
import json
from fastapi import HTTPException, Request, Response, Query
from typing import Tuple, Any, Optional, Dict
from . import config as cluster_config

def parse_job_owner(job_id: str) -> Tuple[str, str]:
    """
    Parses job_id to extract owner_name and bare_id.
    Format: {owner_name}-{bare_id}
    """
    # Try to match against known nodes first (longest match)
    try:
        config = cluster_config.load_cluster_config()
        known_nodes = config.nodes.keys()
        # Sort by length desc to match longest prefix
        for node in sorted(known_nodes, key=len, reverse=True):
            prefix = f"{node}-"
            if job_id.startswith(prefix):
                return node, job_id[len(prefix):]
    except Exception:
        pass

    parts = job_id.split("-", 1)
    if len(parts) != 2:
        raise ValueError("Invalid job_id format. Expected {owner_name}-{bare_id}")
    return parts[0], parts[1]

def is_local(job_id: str) -> bool:
    try:
        owner, _ = parse_job_owner(job_id)
        return owner == cluster_config.get_self_name()
    except ValueError:
        return False

async def proxy_to_owner(
    job_id: str, 
    path_suffix: str, 
    method: str,
    query_params: Dict[str, Any],
    body: Optional[bytes] = None,
    headers: Optional[Dict[str, str]] = None
) -> Response:
    """
    Proxies the request to the owner node.
    path_suffix: e.g. "/result" or "" (empty for base job resource)
    """
    try:
        owner, _ = parse_job_owner(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job_id format")

    config = cluster_config.load_cluster_config()
    base_url = cluster_config.get_node_url(owner)
    
    if not base_url:
        # Unknown owner
        # We return 503 as per prompt requirement for "owner_node_unreachable" 
        # but strictly this is "unknown owner". 
        # Prompt says: "On error (timeout, conn error): return 503 ... owner_node_unreachable"
        # If owner is not in config, we can't reach it.
        return Response(
            content=json.dumps({"error": "owner_node_unreachable", "owner": owner, "detail": "unknown_node"}),
            status_code=503,
            media_type="application/json"
        )

    # Construct target URL
    # base_url e.g. "http://node-b.internal:8080"
    # target: http://node-b.internal:8080/jobs/{job_id}/result
    target_url = f"{base_url.rstrip('/')}/jobs/{job_id}{path_suffix}"
    
    # Add internal=1 to query params
    params = dict(query_params)
    params["internal"] = "1"

    timeout = config.internal_request_timeout_seconds

    # Prepare headers
    req_headers = dict(headers) if headers else {}
    # Remove hop-by-hop headers or host
    req_headers.pop("host", None)
    req_headers.pop("content-length", None)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.request(
                method=method,
                url=target_url,
                params=params,
                content=body,
                headers=req_headers
            )
            
            # Return response as-is
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                headers=dict(resp.headers),
                media_type=resp.headers.get("content-type")
            )
    except (httpx.RequestError, httpx.TimeoutException):
        return Response(
            content=json.dumps({"error": "owner_node_unreachable", "owner": owner}),
            status_code=503,
            media_type="application/json"
        )

async def proxy_job_submission(
    target_node: str,
    file_content: bytes,
    filename: str,
    target_lang: Optional[str] = None
) -> Response:
    config = cluster_config.load_cluster_config()
    base_url = cluster_config.get_node_url(target_node)
    
    if not base_url:
        raise ValueError(f"Unknown target node: {target_node}")

    target_url = f"{base_url.rstrip('/')}/jobs"
    params = {"internal": "1"}
    if target_lang:
        params["target_lang"] = target_lang

    # Prepare multipart upload
    files = {"file": (filename, file_content)}
    timeout = config.internal_request_timeout_seconds

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            url=target_url,
            params=params,
            files=files
        )
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=dict(resp.headers),
            media_type=resp.headers.get("content-type")
        )

