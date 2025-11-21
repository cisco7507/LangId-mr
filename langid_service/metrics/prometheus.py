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

def get_metrics_summary():
    """
    Returns a summary of the metrics for the UI.
    """
    from langid_service.cluster.config import load_cluster_config
    config = load_cluster_config()
    nodes = sorted(config.nodes.keys())
    
    summary_nodes = []
    for node in nodes:
        # Calculate jobs submitted as target for this node
        submitted_as_target = 0
        for (ingress, target), count in _jobs_submitted_counts.items():
            if target == node:
                submitted_as_target += count
        
        summary_nodes.append({
            "name": node,
            "up": _node_up_status.get(node, False),
            "jobs_owned_total": _jobs_owned_counts.get(node, 0),
            "jobs_active": _jobs_active_counts.get(node, 0),
            "jobs_submitted_as_target": submitted_as_target,
            "last_health_ts": _node_last_health.get(node)
        })
        
    return {"nodes": summary_nodes}
