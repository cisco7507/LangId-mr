import uuid, shutil
from pathlib import Path
from .config import STORAGE_DIR, ALLOWED_EXTS, MAX_UPLOAD_BYTES

def gen_uuid() -> str:
    return str(uuid.uuid4())

def ensure_dirs():
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

def validate_upload(filename: str, size: int):
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTS:
        raise ValueError(f"Unsupported extension: {ext}. Allowed: {sorted(ALLOWED_EXTS)}")
    if size > MAX_UPLOAD_BYTES:
        raise ValueError(f"File too large: {size} bytes (limit {MAX_UPLOAD_BYTES})")

def move_to_storage(src: Path, dest_name: str) -> Path:
    dest = (STORAGE_DIR / dest_name).with_suffix(src.suffix.lower())
    shutil.move(str(src), dest)
    return dest
