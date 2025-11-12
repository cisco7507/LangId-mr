# langid_service/app/lang_gate.py
from typing import Dict, Any
from loguru import logger
import numpy as np
from fastapi import HTTPException
from .config import ALLOWED_LANGS, LANG_DETECT_MIN_PROB, ENFR_STRICT_REJECT
from .services.detector import get_model
from .services.audio_io import load_audio_mono_16k
from . import metrics

def pick_en_or_fr_by_scoring(audio: np.ndarray) -> str:
    """
    Runs short transcriptions for both English and French and picks the language
    with the higher average log probability.
    """
    model = get_model()
    scores = {}

    for lang in ["en", "fr"]:
        # Transcribe a short segment to get log probability
        segments, _ = model.transcribe(
            audio,
            language=lang,
            beam_size=2,
            best_of=2,
            vad_filter=True,
            initial_prompt="Hello." if lang == "en" else "Bonjour.",
        )

        # Calculate mean log probability
        logprobs = [s.avg_logprob for s in segments if s.avg_logprob is not None]
        if logprobs:
            scores[lang] = np.mean(logprobs)
        else:
            scores[lang] = -99.0  # Penalize if no speech detected

    # Pick the language with the higher score
    chosen_lang = max(scores, key=scores.get)
    logger.info(
        f"Fallback scoring: en_score={scores.get('en', -99):.2f}, "
        f"fr_score={scores.get('fr', -99):.2f} -> Chosen: {chosen_lang}"
    )
    metrics.LANGID_FALLBACK_USED.inc()
    return chosen_lang

def validate_language_strict(audio_path: str):
    """
    Performs a synchronous language check and raises an HTTPException if the
    language is not confidently detected as English or French.
    """
    model = get_model()
    audio = load_audio_mono_16k(audio_path)
    _, info = model.detect_language(audio)
    detected_lang = info.language
    probability = info.language_probability

    if detected_lang not in ALLOWED_LANGS or probability < LANG_DETECT_MIN_PROB:
        raise HTTPException(
            status_code=400,
            detail=f"Only English/French audio supported (p={probability:.2f}, got '{detected_lang}').",
        )

def detect_lang_en_fr_only(audio_path: str) -> Dict[str, Any]:
    """
    Detects language with a strict EN/FR gate. If detection is not confidently
    English or French, it either rejects the audio or uses a scoring fallback.
    """
    model = get_model()
    audio = load_audio_mono_16k(audio_path)

    # 1. Standard language detection
    _, info = model.detect_language(audio)
    detected_lang = info.language
    probability = info.language_probability
    logger.info(f"detect: autodetect={detected_lang} p={probability:.2f}")

    # 2. Decision gate
    if detected_lang in ALLOWED_LANGS and probability >= LANG_DETECT_MIN_PROB:
        logger.info(f"Autodetect successful: lang={detected_lang}, p={probability:.2f} (threshold={LANG_DETECT_MIN_PROB})")
        metrics.LANGID_AUTODETECT_ACCEPT.inc()
        return {"language": detected_lang, "probability": probability, "method": "autodetect"}

    # 3. VAD-retry for low-confidence detections
    logger.info("Initial detection below threshold, re-trying with VAD.")
    segments, info_vad = model.transcribe(audio, vad_filter=True)
    detected_lang_vad = info_vad.language
    probability_vad = info_vad.language_probability
    logger.info(f"detect(VAD): autodetect={detected_lang_vad} p={probability_vad:.2f}")

    if detected_lang_vad in ALLOWED_LANGS and probability_vad >= LANG_DETECT_MIN_PROB:
        logger.info(f"Autodetect successful [via VAD]: lang={detected_lang_vad}, p={probability_vad:.2f} (threshold={LANG_DETECT_MIN_PROB})")
        metrics.LANGID_AUTODETECT_ACCEPT.inc()
        return {"language": detected_lang_vad, "probability": probability_vad, "method": "autodetect-vad"}

    # 4. Handle non-EN/FR or low-confidence detection
    logger.warning(
        f"Autodetect rejected: lang={detected_lang}, p={probability:.2f} "
        f"(threshold={LANG_DETECT_MIN_PROB}). Entering fallback/reject logic."
    )
    metrics.LANGID_AUTODETECT_REJECT.inc()

    if ENFR_STRICT_REJECT:
        raise HTTPException(
            status_code=400,
            detail=f"Only English/French audio supported (p={probability:.2f}, got '{detected_lang}').",
        )
    else:
        # Use scoring to force a choice between English and French
        chosen_lang = pick_en_or_fr_by_scoring(audio)
        return {"language": chosen_lang, "probability": None, "method": "fallback"}
