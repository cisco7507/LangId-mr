# langid_service/app/lang_gate.py
from typing import Dict, Any
from loguru import logger
import numpy as np
from fastapi import HTTPException
from .config import ALLOWED_LANGS, LANG_DETECT_MIN_PROB, ENFR_STRICT_REJECT
from .services.detector import get_model
from . import metrics

# Define constants for audio processing
SAMPLE_RATE = 16000
PROBE_DURATION_S = 30

def _create_audio_probe(audio: np.ndarray) -> np.ndarray:
    """
    Extracts a short probe from the beginning of an audio array.
    """
    probe_samples = PROBE_DURATION_S * SAMPLE_RATE
    return audio[:probe_samples]

def pick_en_or_fr_by_scoring(probe_audio: np.ndarray) -> str:
    """
    Runs cheap transcriptions on an audio probe for both English and French and
    picks the language with the higher average log probability.
    """
    model = get_model()
    scores = {}

    for lang in ["en", "fr"]:
        # Use cheap settings for the scoring probe
        segments, _ = model.transcribe(
            probe_audio,
            language=lang,
            beam_size=1,
            best_of=1,
            vad_filter=True,
        )

        logprobs = [s.avg_logprob for s in segments if s.avg_logprob is not None]
        scores[lang] = np.mean(logprobs) if logprobs else -99.0

    chosen_lang = max(scores, key=scores.get)
    logger.info(
        f"Fallback scoring: en_score={scores.get('en', -99):.2f}, "
        f"fr_score={scores.get('fr', -99):.2f} -> Chosen: {chosen_lang}"
    )
    metrics.LANGID_FALLBACK_USED.inc()
    return chosen_lang

def validate_language_strict(audio: np.ndarray):
    """
    Performs a synchronous language check on an audio probe and raises an
    HTTPException if the language is not confidently detected as English or French.
    """
    model = get_model()
    probe_audio = _create_audio_probe(audio)
    _, info = model.transcribe(probe_audio, vad_filter=False, beam_size=1)
    detected_lang = info.language
    probability = info.language_probability

    if detected_lang not in ALLOWED_LANGS or probability < LANG_DETECT_MIN_PROB:
        raise HTTPException(
            status_code=400,
            detail=f"Only English/French audio supported (p={probability:.2f}, got '{detected_lang}').",
        )

def detect_lang_en_fr_only(audio: np.ndarray) -> Dict[str, Any]:
    """
    Detects language on a short audio probe with a strict EN/FR gate.
    If detection is not confident, it either rejects or uses a scoring fallback.
    The audio provided is the full audio clip.
    """
    model = get_model()
    probe_audio = _create_audio_probe(audio)

    # 1. Standard language detection on the probe
    _, info = model.transcribe(probe_audio, vad_filter=False, beam_size=1)
    detected_lang = info.language
    probability = info.language_probability
    logger.info(f"detect(probe): autodetect={detected_lang} p={probability:.2f}")

    # 2. Decision gate
    if detected_lang in ALLOWED_LANGS and probability >= LANG_DETECT_MIN_PROB:
        logger.info(f"Autodetect successful: lang={detected_lang}, p={probability:.2f} (threshold={LANG_DETECT_MIN_PROB})")
        metrics.LANGID_AUTODETECT_ACCEPT.inc()
        return {"language": detected_lang, "probability": probability, "method": "autodetect"}

    # 3. VAD-retry on the same probe
    logger.info("Initial detection below threshold, re-trying with VAD on probe.")
    _, info_vad = model.transcribe(probe_audio, vad_filter=True, beam_size=1)
    detected_lang_vad = info_vad.language
    probability_vad = info_vad.language_probability
    logger.info(f"detect(probe, VAD): autodetect={detected_lang_vad} p={probability_vad:.2f}")

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
        # Use scoring on the probe to force a choice between English and French
        chosen_lang = pick_en_or_fr_by_scoring(probe_audio)
        return {"language": chosen_lang, "probability": None, "method": "fallback"}
