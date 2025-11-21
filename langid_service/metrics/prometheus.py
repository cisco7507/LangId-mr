from prometheus_client import Counter, Gauge
from langid_service.app.metrics import REGISTRY

# 1) langid_jobs_submitted_total
JOBS_SUBMITTED = Counter(
    "langid_jobs_submitted_total",
    "Total jobs submitted via POST /jobs",
    ["ingress_node", "target_node"],
    registry=REGISTRY
)

# 2) langid_jobs_owned_total
JOBS_OWNED = Counter(
    "langid_jobs_owned_total",
    "Total jobs owned/created locally",
    ["owner_node"],
    registry=REGISTRY
)

# 3) langid_jobs_active
JOBS_ACTIVE = Gauge(
    "langid_jobs_active",
    "Number of currently active jobs",
    ["owner_node"],
    registry=REGISTRY
)

# 4) langid_node_up
NODE_UP = Gauge(
    "langid_node_up",
    "Node up status (1=up, 0=down)",
    ["node"],
    registry=REGISTRY
)

# 5) langid_node_last_health_timestamp_seconds
NODE_LAST_HEALTH = Gauge(
    "langid_node_last_health_timestamp_seconds",
    "Timestamp of last successful health check",
    ["node"],
    registry=REGISTRY
)

# In-memory state for summary endpoint
_jobs_submitted_counts = {} # (ingress, target) -> count
_jobs_owned_counts = {} # owner -> count
_jobs_active_counts = {} # owner -> count
_node_up_status = {} # node -> bool
_node_last_health = {} # node -> timestamp

def increment_jobs_submitted(ingress_node: str, target_node: str):
    JOBS_SUBMITTED.labels(ingress_node=ingress_node, target_node=target_node).inc()
    key = (ingress_node, target_node)
    _jobs_submitted_counts[key] = _jobs_submitted_counts.get(key, 0) + 1

def increment_jobs_owned(owner_node: str):
    JOBS_OWNED.labels(owner_node=owner_node).inc()
    _jobs_owned_counts[owner_node] = _jobs_owned_counts.get(owner_node, 0) + 1

def jobs_active_inc(owner_node: str):
    JOBS_ACTIVE.labels(owner_node=owner_node).inc()
    _jobs_active_counts[owner_node] = _jobs_active_counts.get(owner_node, 0) + 1

def jobs_active_dec(owner_node: str):
    JOBS_ACTIVE.labels(owner_node=owner_node).dec()
    current = _jobs_active_counts.get(owner_node, 0)
    if current > 0:
        _jobs_active_counts[owner_node] = current - 1

def set_node_up(node: str, is_up: int):
    NODE_UP.labels(node=node).set(is_up)
    _node_up_status[node] = bool(is_up)

def set_node_last_health_timestamp(node: str, timestamp: float):
    NODE_LAST_HEALTH.labels(node=node).set(timestamp)
    _node_last_health[node] = timestamp

def get_local_metrics():
    """
    Returns the raw local metrics state.
    """
    # Convert tuple keys to strings for JSON serialization
    jobs_submitted_str_keys = {
        f"{k[0]},{k[1]}": v for k, v in _jobs_submitted_counts.items()
    }
    
    return {
        "jobs_submitted": jobs_submitted_str_keys,
        "jobs_owned": _jobs_owned_counts.copy(),
        "jobs_active": _jobs_active_counts.copy(),
        "node_up": _node_up_status.copy(),
        "node_last_health": _node_last_health.copy()
    }

def get_metrics_summary(aggregated_data=None):
    """
    Returns a summary of the metrics for the UI.
    If aggregated_data is provided (list of local_metrics from all nodes), 
    it merges them. Otherwise, it uses local state only.
    """
    from langid_service.cluster.config import load_cluster_config
    config = load_cluster_config()
    nodes = sorted(config.nodes.keys())
    
    # If no aggregation provided, use local state as the only source
    if aggregated_data is None:
        sources = [get_local_metrics()]
    else:
        sources = aggregated_data

    # Merge sources
    merged_jobs_submitted = {}
    merged_jobs_owned = {}
    merged_jobs_active = {}
    merged_node_up = {}
    merged_node_last_health = {}

    for source in sources:
        # Merge submitted counts (ingress, target) -> count
        for k, v in source.get("jobs_submitted", {}).items():
            # k might be a tuple or a string representation if coming from JSON
            # If from JSON, it might be a list [ingress, target] or string "ingress,target"
            # But for now let's assume we handle the parsing in the caller or here.
            # Actually, JSON keys must be strings. So if we return this over HTTP, 
            # the tuple keys in _jobs_submitted_counts will become strings.
            # We need to be careful.
            # Let's assume the caller normalizes this.
            merged_jobs_submitted[k] = merged_jobs_submitted.get(k, 0) + v
            
        # Merge owned counts
        for k, v in source.get("jobs_owned", {}).items():
            merged_jobs_owned[k] = merged_jobs_owned.get(k, 0) + v
            
        # Merge active counts
        for k, v in source.get("jobs_active", {}).items():
            merged_jobs_active[k] = merged_jobs_active.get(k, 0) + v
            
        # Merge node up status (OR logic? or latest? or just take what's there)
        # Each node reports its own status and potentially others.
        # Ideally, we trust the node's report of ITSELF.
        # But _node_up_status contains what *this* node thinks of *others*.
        # If we aggregate, we might have conflicting views.
        # Strategy: For node X, trust the report from node X if available.
        # But node X might be down and not reporting.
        # So we should probably trust the "health check" view from the *current* node (the ingress node)
        # for UP/DOWN status, but use the *target* node's reported stats for owned/active.
        pass 

    # REVISED STRATEGY for Aggregation:
    # 1. Node Status (UP/DOWN) & Last Health: 
    #    Use the view from the CURRENT node (the one serving the dashboard).
    #    Why? Because if the current node can't reach Node B, Node B is effectively down for the user.
    # 2. Job Counts (Owned, Active, Traffic):
    #    Sum up counts from ALL nodes that responded.
    #    If Node B is down, we won't get its metrics, so its "Owned" count might be 0 or stale.
    #    That's acceptable.
    
    # So we primarily need to merge 'jobs_submitted', 'jobs_owned', 'jobs_active'.
    
    summary_nodes = []
    for node in nodes:
        # Calculate jobs submitted as target for this node
        submitted_as_target = 0
        for key, count in merged_jobs_submitted.items():
            # Handle tuple keys (from local) or string/list keys (from JSON if not normalized)
            if isinstance(key, list): # JSON list
                tgt = key[1]
            elif isinstance(key, str) and "," in key: # JSON string "ingress,target"
                tgt = key.split(",")[1]
            elif isinstance(key, tuple): # Tuple
                tgt = key[1]
            else:
                continue
                
            if tgt == node:
                submitted_as_target += count
        
        # For UP/Health, we prefer the local view (this node's view of the cluster)
        # because we are the dashboard.
        is_up = _node_up_status.get(node, False)
        last_health = _node_last_health.get(node)
        
        summary_nodes.append({
            "name": node,
            "up": is_up,
            "jobs_owned_total": merged_jobs_owned.get(node, 0),
            "jobs_active": merged_jobs_active.get(node, 0),
            "jobs_submitted_as_target": submitted_as_target,
            "last_health_ts": last_health
        })
        
    return {"nodes": summary_nodes}
