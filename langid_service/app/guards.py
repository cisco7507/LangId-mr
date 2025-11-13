from fastapi import HTTPException
from .config import ALLOWED_LANGS

def ensure_allowed(lang: str):
    if lang not in ALLOWED_LANGS:
        raise HTTPException(status_code=400, detail=f"Unsupported language '{lang}'")
