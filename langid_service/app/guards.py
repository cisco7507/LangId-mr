# langid_service/app/guards.py
from fastapi import HTTPException
from .config import ALLOWED_LANGS

def ensure_allowed(lang: str):
    """
    Raises a 400 HTTPException if the provided language is not in the
    configured ALLOWED_LANGS set.
    """
    if lang not in ALLOWED_LANGS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported language '{lang}'. Must be one of: {', '.join(ALLOWED_LANGS)}",
        )
