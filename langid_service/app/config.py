# langid_service/app/config.py
from typing import Set
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

def _get_env_boolean(var_name: str, default: bool) -> bool:
    """Helper to read boolean env vars."""
    return os.getenv(var_name, str(default)).lower() in ("true", "1", "t")

# --- Core settings ---
LOG_DIR = Path(os.getenv("LOG_DIR", "/app/logs"))
MAX_WORKERS = int(os.getenv("MAX_WORKERS", 2))
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "base")
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", 100))
STORAGE_DIR = Path(os.getenv("STORAGE_DIR", "/app/storage"))
DB_URL = os.getenv("DB_URL", "sqlite:///langid.sqlite")
MAX_RETRIES = int(os.getenv("MAX_RETRIES", 3))
ALLOWED_EXTS = {".wav", ".mp3", ".aac", ".m4a"}
MAX_UPLOAD_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "auto")


# --- EN/FR Gate settings ---
ALLOWED_LANGS: Set[str] = set(os.getenv("ALLOWED_LANGS", "en,fr").split(","))
LANG_DETECT_MIN_PROB = float(os.getenv("LANG_DETECT_MIN_PROB", 0.60))
ENFR_STRICT_REJECT = _get_env_boolean("ENFR_STRICT_REJECT", False)
