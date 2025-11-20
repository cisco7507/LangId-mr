from uuid import uuid4
from pathlib import Path
import shutil
from typing import Optional
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

def move_to_storage(src: Path, job_id: str, original_filename: Optional[str] = None) -> Path:
    """
    Move an uploaded/temp file into the storage dir and preserve a usable
    filename suffix when possible.

    - If `original_filename` has a known extension (in ALLOWED_EXTS) we
      store as `<job_id><ext>`.
    - Else, if `src` already has a suffix in ALLOWED_EXTS, preserve it.
    - Otherwise fall back to storing as `STORAGE_DIR/<job_id>`.
    """
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    # Determine suffix to preserve (only allow known extensions)
    suffix = ""
    if original_filename:
        suf = Path(original_filename).suffix.lower()
        if suf in ALLOWED_EXTS:
            suffix = suf

    if not suffix:
        # Fall back to the temp/src suffix if present
        src_suf = src.suffix.lower()
        if src_suf in ALLOWED_EXTS:
            suffix = src_suf

    if suffix:
        dest = STORAGE_DIR / f"{job_id}{suffix}"
    else:
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
