# langid_service/app/metrics.py
from prometheus_client import CollectorRegistry, Gauge, Counter, Histogram

REGISTRY = CollectorRegistry()

LANGID_JOBS_TOTAL = Counter(
    "langid_jobs_total",
    "Total number of jobs processed",
    ["status"],
    registry=REGISTRY,
)

LANGID_JOBS_RUNNING = Gauge(
    "langid_jobs_running",
    "Number of jobs currently running",
    registry=REGISTRY,
)

LANGID_PROCESSING_SECONDS = Histogram(
    "langid_processing_seconds",
    "Time spent processing a job",
    registry=REGISTRY,
)

LANGID_ACTIVE_WORKERS = Gauge(
    "langid_active_workers",
    "Number of active worker threads",
    registry=REGISTRY,
)

LANGID_AUDIO_SECONDS = Histogram(
    "langid_audio_seconds",
    "Duration of audio processed",
    registry=REGISTRY,
)

LANGID_AUTODETECT_ACCEPT = Counter(
    "langid_autodetect_accept",
    "Number of times autodetect was successful",
    registry=REGISTRY,
)

LANGID_AUTODETECT_REJECT = Counter(
    "langid_autodetect_reject",
    "Number of times autodetect was rejected",
    registry=REGISTRY,
)

LANGID_FALLBACK_USED = Counter(
    "langid_fallback_used",
    "Number of times fallback scoring was used",
    registry=REGISTRY,
)

LANGID_TRANSLATE_EN2FR = Counter(
    "langid_translate_en2fr",
    "Number of translations from English to French",
    registry=REGISTRY,
)

LANGID_TRANSLATE_FR2EN = Counter(
    "langid_translate_fr2en",
    "Number of translations from French to English",
    registry=REGISTRY,
)

LANGID_GATE_PATH_DECISIONS = Counter(
    "langid_gate_path_decisions_total",
    "Number of jobs finalized by gate path decision",
    ["gate_path"],
    registry=REGISTRY,
)

# Mapping of gate_decision values to human-readable gate path labels
GATE_PATH_LABELS = {
    "accepted_high_conf": "high_confidence",
    "accepted_mid_zone_en": "mid_zone_stopword",
    "accepted_mid_zone_fr": "mid_zone_stopword",
    "vad_retry": "vad_retry",
    "fallback": "fallback_scoring",
    "NO_SPEECH_MUSIC_ONLY": "music_only",
}


def classify_gate_path(gate_decision: str) -> str:
    """
    Classify a gate_decision string into a canonical gate path label.
    
    Args:
        gate_decision: The raw gate_decision value from detect_lang_en_fr_only.
        
    Returns:
        A canonical gate path label for metrics tracking.
    """
    return GATE_PATH_LABELS.get(gate_decision, "unknown")


def record_gate_path_decision(gate_decision: str) -> None:
    """
    Record a gate path decision in the Prometheus counter.
    
    Args:
        gate_decision: The raw gate_decision value from detect_lang_en_fr_only.
    """
    gate_path = classify_gate_path(gate_decision)
    LANGID_GATE_PATH_DECISIONS.labels(gate_path=gate_path).inc()


def _swap_registry_for_tests(new_registry):
    """
    Swaps the global REGISTRY for a test-specific one.
    This is a helper for testing purposes only.
    """
    global REGISTRY
    REGISTRY = new_registry