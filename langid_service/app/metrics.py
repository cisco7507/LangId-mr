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
    [
        "gate_path",
        "gate_decision",
        "pipeline_mode",
        "language",
        "music_only",
    ],
    registry=REGISTRY,
)


def _swap_registry_for_tests(new_registry):
    """
    Swaps the global REGISTRY for a test-specific one.
    This is a helper for testing purposes only.
    """
    global REGISTRY
    REGISTRY = new_registry