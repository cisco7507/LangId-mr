from faster_whisper import WhisperModel
from loguru import logger
import torch
from ..config import (
    WHISPER_MODEL_SIZE,
    WHISPER_DEVICE,
)

_model = None

def get_model() -> WhisperModel:
    """
    Initializes and returns a singleton instance of the WhisperModel.
    """
    global _model
    if _model is None:
        logger.info(f"Loading Whisper model '{WHISPER_MODEL_SIZE}' on device '{WHISPER_DEVICE}'")
        device_type = WHISPER_DEVICE
        if device_type == "auto":
            device_type = "cuda" if torch.cuda.is_available() else "cpu"

        _model = WhisperModel(
            WHISPER_MODEL_SIZE,
            device=device_type,
            compute_type="int8" if device_type == "cpu" else "float16",
        )
        logger.info("Whisper model loaded successfully.")
    return _model
