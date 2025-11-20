from typing import Optional, Any

try:
    from faster_whisper import WhisperModel  # type: ignore
except ImportError:  # pragma: no cover - optional dependency in minimal test env
    WhisperModel = None  # type: ignore

from loguru import logger

try:
    import torch
except ImportError:  # pragma: no cover - allow lightweight envs
    torch = None  # type: ignore

from ..config import (
    WHISPER_MODEL_SIZE,
    WHISPER_DEVICE,
)

_model = None

def get_model() -> Any:
    """
    Initializes and returns a singleton instance of the WhisperModel.
    """
    global _model
    if _model is None:
        if WhisperModel is None:
            raise ImportError(
                "faster-whisper is not installed. Install dependencies to run inference."
            )

        logger.info(f"Loading Whisper model '{WHISPER_MODEL_SIZE}' on device '{WHISPER_DEVICE}'")
        device_type = WHISPER_DEVICE
        if device_type == "auto":
            if torch is None:
                device_type = "cpu"
            else:
                device_type = "cuda" if torch.cuda.is_available() else "cpu"

        _model = WhisperModel(
            WHISPER_MODEL_SIZE,
            device=device_type,
            compute_type="int8" if device_type == "cpu" else "float16",
        )
        logger.info("Whisper model loaded successfully.")
    return _model
