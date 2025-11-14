# langid_service/app/config.py
from typing import Set
import os
from pathlib import Path
from dotenv import load_dotenv

# Resolve BASE_DIR as the langid_service/ root (one level above app/)
BASE_DIR = Path(__file__).resolve().parents[1]

# Always load .env from the project root so settings work no matter
# which working directory uvicorn is started from.
load_dotenv(BASE_DIR / ".env")


def _get_env_boolean(var_name: str, default: bool) -> bool:
    """Helper to read boolean env vars."""
    return os.getenv(var_name, str(default)).lower() in ("true", "1", "t")


def _resolve_path(var_name: str, default: Path) -> Path:
    """Resolve env path; treat relative paths as BASE_DIR / value.

    This keeps Windows absolute paths (e.g. C:\\LangId\\logs) working
    unchanged, while making ./logs-style paths behave predictably on macOS
    and Linux.
    """

    raw = os.getenv(var_name)
    if raw:
        p = Path(raw)
        return p if p.is_absolute() else BASE_DIR / p
    return default


# --- Core settings ---
LOG_DIR = _resolve_path("LOG_DIR", BASE_DIR / "logs")
MAX_WORKERS = int(os.getenv("MAX_WORKERS", 2))
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "base")
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", 100))
STORAGE_DIR = _resolve_path("STORAGE_DIR", BASE_DIR / "storage")
DB_URL = os.getenv("DB_URL", "sqlite:///langid.sqlite")
MAX_RETRIES = int(os.getenv("MAX_RETRIES", 3))
ALLOWED_EXTS = {".wav", ".mp3", ".aac", ".m4a"}
MAX_UPLOAD_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "auto")


# --- EN/FR Gate settings ---
ALLOWED_LANGS: Set[str] = set(os.getenv("ALLOWED_LANGS", "en,fr").split(","))
LANG_DETECT_MIN_PROB = float(os.getenv("LANG_DETECT_MIN_PROB", 0.60))
ENFR_STRICT_REJECT = _get_env_boolean("ENFR_STRICT_REJECT", False)
