from uuid import uuid4
from pathlib import Path
import shutil
from .config import STORAGE_DIR, ALLOWED_EXTS, MAX_UPLOAD_BYTES

def gen_uuid():
    return str(uuid4())

def ensure_dirs():
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

def validate_upload(filename: str, size: int):
    if size > MAX_UPLOAD_BYTES:
        raise ValueError(f"File size {size} exceeds limit of {MAX_UPLOAD_BYTES}")
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTS:
        raise ValueError(f"File extension '{ext}' not allowed")

def move_to_storage(src: Path, job_id: str) -> Path:
    dest = STORAGE_DIR / job_id
    shutil.move(str(src), dest)
    return dest

def truncate_to_words(text: str, max_words: int = 10) -> str:
    """
    Truncates a string to a maximum number of words, adding an ellipsis if truncated.
    """
    words = text.split()
    if len(words) > max_words:
        return " ".join(words[:max_words]) + " ..."
    return text
