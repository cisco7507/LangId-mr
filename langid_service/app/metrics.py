# langid_service/app/metrics.py
from prometheus_client import Counter, Gauge, Histogram, CollectorRegistry

REGISTRY = CollectorRegistry(auto_describe=True)
_initialized = False

# Define globals for type hinting and to be populated by initialization
LANGID_JOBS_TOTAL: Counter = None
LANGID_JOBS_RUNNING: Gauge = None
LANGID_PROCESSING_SECONDS: Histogram = None
LANGID_ACTIVE_WORKERS: Gauge = None
LANGID_AUDIO_SECONDS: Histogram = None
LANGID_AUTODETECT_ACCEPT: Counter = None
LANGID_AUTODETECT_REJECT: Counter = None
LANGID_FALLBACK_USED: Counter = None
LANGID_TRANSLATE_EN2FR: Counter = None
LANGID_TRANSLATE_FR2EN: Counter = None


def _initialize_metrics(registry: CollectorRegistry):
    """Helper to create and register all metrics with a given registry."""
    global LANGID_JOBS_TOTAL, LANGID_JOBS_RUNNING, LANGID_PROCESSING_SECONDS, LANGID_ACTIVE_WORKERS, LANGID_AUDIO_SECONDS, LANGID_AUTODETECT_ACCEPT, LANGID_AUTODETECT_REJECT, LANGID_FALLBACK_USED, LANGID_TRANSLATE_EN2FR, LANGID_TRANSLATE_FR2EN

    LANGID_JOBS_TOTAL = Counter(
        "langid_jobs_total",
        "Jobs processed by status",
        ["status"],
        registry=registry,
    )
    LANGID_JOBS_RUNNING = Gauge(
        "langid_jobs_running",
        "Number of jobs currently running",
        registry=registry,
    )
    LANGID_PROCESSING_SECONDS = Histogram(
        "langid_processing_seconds",
        "End-to-end processing latency per job",
        buckets=(0.5, 1, 2, 5, 10, 20, 30, 60, 120, 300),
        registry=registry,
    )
    LANGID_ACTIVE_WORKERS = Gauge(
        "langid_active_workers",
        "Number of active worker threads",
        registry=registry,
    )
    LANGID_AUDIO_SECONDS = Histogram(
        "langid_audio_seconds",
        "Input audio duration per job (seconds)",
        buckets=(1, 3, 10, 30, 60, 120, 300, 900, 1800),
        registry=registry,
    )

    LANGID_AUTODETECT_ACCEPT = Counter(
        "langid_autodetect_accept",
        "Language detections that passed the gate",
        registry=registry,
    )
    LANGID_AUTODETECT_REJECT = Counter(
        "langid_autodetect_reject",
        "Language detections that failed the gate and were rejected or sent to fallback",
        registry=registry,
    )
    LANGID_FALLBACK_USED = Counter(
        "langid_fallback_used",
        "Number of times the EN/FR scoring fallback was used",
        registry=registry,
    )

    LANGID_TRANSLATE_EN2FR = Counter(
        "langid_translate_direction_en2fr",
        "Number of translations from English to French",
        registry=registry,
    )
    LANGID_TRANSLATE_FR2EN = Counter(
        "langid_translate_direction_fr2en",
        "Number of translations from French to English",
        registry=registry,
    )

def initialize_app_metrics():
    """Initializes metrics for the application if not already done."""
    global _initialized
    if not _initialized:
        _initialize_metrics(REGISTRY)
        _initialized = True

def _swap_registry_for_tests(new_registry: CollectorRegistry):
    """Testing helper: rebind metric objects to a fresh registry."""
    global REGISTRY
    REGISTRY = new_registry
    _initialize_metrics(new_registry)


# Initialize metrics on module load for the app
initialize_app_metrics()
