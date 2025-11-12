# langid_service/app/services/detector.py

import os
import sys
from typing import Dict, Any, Optional
from time import perf_counter
from loguru import logger

import numpy as np
from faster_whisper import WhisperModel
from faster_whisper.utils import get_assets_path

from ..config import (
    WHISPER_MODEL_SIZE,
    WHISPER_DEVICE,
    WHISPER_COMPUTE,
    CT2_TRANSLATORS_CACHE,
)
from .audio_io import load_audio_mono_16k, InvalidAudioError
from .. import metrics

# --- Model Singleton ---
_model: Optional[WhisperModel] = None


def get_model() -> WhisperModel:
    """
    Initializes and returns a thread-safe, singleton WhisperModel instance.
    Handles lazy initialization and graceful fallbacks for compute/device types.
    """
    global _model
    if _model is None:
        model_size = WHISPER_MODEL_SIZE
        device = WHISPER_DEVICE
        compute_type = WHISPER_COMPUTE
        logger.info(
            f"Attempting to load Whisper model '{model_size}' "
            f"(device: {device}, compute: {compute_type})"
        )

        try:
            # Set cache directory for CTranslate2 models
            if CT2_TRANSLATORS_CACHE:
                os.environ["CT2_CACHE_PATH"] = CT2_TRANSLATORS_CACHE

            # Monkey-patch to prevent noisy first-run download message
            if not os.path.exists(os.path.join(get_assets_path(), "mel_filters.npz")):
                 logger.info("First run: downloading vocabs and filters.")

            _model = WhisperModel(
                model_size,
                device=device,
                compute_type=compute_type,
            )
            logger.info("Whisper model loaded successfully.")
        except Exception as e:
            logger.error(f"Model initialization failed: {e}. Trying fallback.", exc_info=True)
            # Fallback for unsupported compute types (e.g., float16 on CPU)
            if "CT2_NOT_SUPPORTED" in str(e) or "INVALID_ARGUMENT" in str(e):
                 logger.warning(
                    f"Compute type '{compute_type}' not supported on device '{device}'. "
                    "Falling back to 'int8' on 'cpu'."
                )
                 device = "cpu"
                 compute_type = "int8"
                 _model = WhisperModel(model_size, device=device, compute_type=compute_type)
                 logger.info("Whisper model loaded successfully with fallback configuration.")
            else:
                logger.critical("Could not initialize the Whisper model even with fallback.")
                raise e
    return _model


# --- Language Mapping ---
# Maps detected codes to ISO 639-1, 'und' for unknown
LANG_CODE_MAPPING = {
    "en": "en", "fr": "fr", "es": "es", "de": "de", "it": "it", "pt": "pt",
    "nl": "nl", "ru": "ru", "zh": "zh", "ja": "ja", "ko": "ko", "ar": "ar",
    "hi": "hi", "tr": "tr", "pl": "pl", "sv": "sv", "fi": "fi", "no": "no",
    "da": "da", "cs": "cs", "hu": "hu", "ro": "ro", "el": "el", "he": "he",
    # Add other common languages as needed
}


def detect_language(file_path: str) -> Dict[str, Any]:
    """
    Detects the language of an audio file using a no-VAD, deterministic path.

    Args:
        file_path: Path to the audio file.

    Returns:
        A dictionary containing detection results.
    """
    log = logger.bind(job_id=os.path.basename(file_path), stage="detect_language")
    t0 = perf_counter()

    # 1. Load Audio
    try:
        log.info("Starting audio decoding.")
        audio = load_audio_mono_16k(file_path)
        log.info("Audio decoded successfully.")
        audio_duration_seconds = len(audio) / 16000.0
        metrics.LANGID_AUDIO_SECONDS.observe(audio_duration_seconds)
    except InvalidAudioError as e:
        log.error(f"Audio decoding failed: {e}", exc_info=True)
        metrics.LANGID_JOBS_TOTAL.labels(status="invalid_audio").inc()
        return {
            "error": "InvalidAudioError",
            "error_message": str(e),
            "processing_ms": int((perf_counter() - t0) * 1000),
        }

    # 2. Get Model (lazy-loaded)
    try:
        model = get_model()
    except Exception as e:
        metrics.LANGID_JOBS_TOTAL.labels(status="failed").inc()
        return {
            "error": "ModelInitializationError",
            "error_message": str(e),
            "processing_ms": int((perf_counter() - t0) * 1000),
        }


    # 3. Detect Language using transcribe
    log.info("Starting language inference via transcribe.")
    segments, info = model.transcribe(audio, vad_filter=False, beam_size=1)
    lang = info.language
    prob = info.language_probability

    # Extract the first segment as a snippet
    snippet = ""
    try:
        first_segment = next(segments, None)
        if first_segment:
            snippet = first_segment.text.strip()
    except StopIteration:
        pass # No segments found

    log.info(f"Inference complete. Language: {lang}, Probability: {prob:.2f}, Snippet: '{snippet}'")

    # 4. Map and Return Result
    mapped_lang = LANG_CODE_MAPPING.get(lang, "und")
    elapsed_ms = int((perf_counter() - t0) * 1000)

    return {
        "language_raw": lang,
        "language_mapped": mapped_lang,
        "probability": float(prob),
        "transcript_snippet": snippet,
        "processing_ms": elapsed_ms,
        "model": WHISPER_MODEL_SIZE,
        "info": {
            "duration": audio_duration_seconds,
            "vad": False # Explicitly note that VAD was not used
        },
    }
