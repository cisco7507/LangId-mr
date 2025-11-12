import os
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# --- Directories ---
BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = Path(os.environ.get("STORAGE_DIR", BASE_DIR.parent / "storage"))
LOG_DIR = Path(os.environ.get("LOG_DIR", BASE_DIR.parent / "logs"))

# --- Database ---
DB_PATH = Path(os.environ.get("DB_PATH", BASE_DIR / "langid.sqlite"))
DB_URL = f"sqlite:///{DB_PATH.as_posix()}"

# --- Model Configuration ---
WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "small")
WHISPER_DEVICE = os.environ.get("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE = os.environ.get("WHISPER_COMPUTE", "int8")
CT2_TRANSLATORS_CACHE = os.environ.get("CT2_TRANSLATORS_CACHE")

# Validate compute type based on device
if WHISPER_DEVICE == "cpu" and WHISPER_COMPUTE not in ("int8", "float32"):
    logging.warning(
        f"Unsupported compute type '{WHISPER_COMPUTE}' for CPU. "
        "Defaulting to 'int8'. Supported types are: int8, float32."
    )
    WHISPER_COMPUTE = "int8"
elif WHISPER_DEVICE == "cuda" and WHISPER_COMPUTE not in ("int8_float16", "float16", "float32"):
    logging.warning(
        f"Unsupported compute type '{WHISPER_COMPUTE}' for CUDA. "
        "Defaulting to 'int8_float16'. Supported types are: int8_float16, float16, float32."
    )
    WHISPER_COMPUTE = "int8_float16"

# --- Worker Configuration ---
MAX_WORKERS = int(os.environ.get("MAX_WORKERS", "2"))
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "2"))

# --- File Uploads ---
MAX_FILE_SIZE_MB = int(os.environ.get("MAX_FILE_SIZE_MB", "100"))
MAX_UPLOAD_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
ALLOWED_EXTS = {".wav", ".wave", ".mp3", ".m4a", ".aac"}

# --- Language Gate ---
# Comma-separated list of allowed languages
_allowed_langs_str = os.environ.get("ALLOWED_LANGS", "en,fr")
ALLOWED_LANGS = {lang.strip() for lang in _allowed_langs_str.split(",")}

# Minimum probability to accept a language detection
LANG_DETECT_MIN_PROB = float(os.environ.get("LANG_DETECT_MIN_PROB", "0.60"))

# If true, reject files that are not in ALLOWED_LANGS. If false, force to EN/FR.
ENFR_STRICT_REJECT = os.environ.get("ENFR_STRICT_REJECT", "false").lower() in ("true", "1", "t")

# --- Directory Creation ---
def ensure_dirs():
    """Create necessary directories if they don't exist."""
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    if CT2_TRANSLATORS_CACHE:
        Path(CT2_TRANSLATORS_CACHE).mkdir(parents=True, exist_ok=True)

# Run on import
ensure_dirs()
