from typing import Dict, Any
import os
import re
from loguru import logger
import numpy as np
from fastapi import HTTPException
from .config import ALLOWED_LANGS, LANG_DETECT_MIN_PROB, ENFR_STRICT_REJECT
from .services.detector import get_model
from . import metrics

# Define constants for audio processing
SAMPLE_RATE = 16000
PROBE_DURATION_S = 30

EN_STOPWORDS = {
    "the", "and", "to", "of", "in", "you", "your", "for", "is", "on",
    "it", "that", "with", "this", "as", "at", "be", "are", "we", "our", "us",
}

FR_STOPWORDS = {
    "le", "la", "les", "un", "une", "des", "et", "ou", "mais", "que",
    "qui", "pour", "avec", "sur", "pas", "ce", "cette", "est", "sont",
    "je", "tu", "il", "elle", "nous", "vous", "ils", "elles",
}

MUSIC_KEYWORDS = {"music", "musique"}
MUSIC_UNICODE_MARKERS = {"♪", "♫", "♩", "♬", "♭", "♯"}
MUSIC_FILLER_TOKENS = {
    "background",
    "bg",
    "only",
    "instrumental",
    "ambience",
    "ambiance",
    "ambient",
    "soundtrack",
    "track",
    "outro",
    "intro",
    "playing",
    "play",
    "song",
    "soft",
    "theme",
    "jingle",
    "de",
    "du",
    "fond",
}
BRACKET_PAIRS = {
    "[": "]",
    "(": ")",
    "{": "}",
    "<": ">",
}

MID_LOWER = float(os.getenv("LANG_MID_LOWER", 0.60))
MID_UPPER = float(os.getenv("LANG_MID_UPPER", 0.79))
MID_EN_MIN_STOPWORD_RATIO = float(os.getenv("LANG_MIN_STOPWORD_EN", 0.15))
MID_FR_MIN_STOPWORD_RATIO = float(os.getenv("LANG_MIN_STOPWORD_FR", 0.15))
STOPWORD_MARGIN = float(os.getenv("LANG_STOPWORD_MARGIN", 0.05))
MIN_TOKENS_FOR_HEURISTIC = int(os.getenv("LANG_MIN_TOKENS", 10))
MIN_TOKENS_FOR_SPEECH = int(os.getenv("LANG_MIN_TOKENS_SPEECH", "6"))
MIN_STOPWORD_FOR_SPEECH = float(os.getenv("LANG_MIN_STOPWORD_SPEECH", "0.10"))

TOKEN_SPLIT_RE = re.compile(r"[^\w']+", re.UNICODE)


def tokenize_text(text: str) -> list[str]:
    """Tokenize text on whitespace/punctuation into lowercase tokens."""
    if not text:
        return []
    return [token for token in TOKEN_SPLIT_RE.split(text.lower()) if token]


def compute_stopword_ratio(text: str, stopwords: set[str]) -> float:
    """Return the fraction of tokens that appear in the provided stopword set."""
    tokens = tokenize_text(text)
    if not tokens:
        return 0.0
    hits = sum(1 for token in tokens if token in stopwords)
    return hits / len(tokens)


def _strip_outer_brackets(text: str) -> str:
    """Remove matching outer brackets, one layer at a time."""
    stripped = text
    while len(stripped) >= 2 and stripped[0] in BRACKET_PAIRS:
        closing = BRACKET_PAIRS[stripped[0]]
        if stripped[-1] != closing:
            break
        stripped = stripped[1:-1].strip()
    return stripped


def is_music_only_transcript(text: str, music_keywords: list[str] | set[str] | None = None) -> bool:
    """Return True when the transcript represents background music only."""
    if text is None:
        return False

    working = text.strip()
    if not working:
        return False

    # Normalize Unicode music symbols to a "music" placeholder before further processing
    for marker in MUSIC_UNICODE_MARKERS:
        if marker in working:
            working = working.replace(marker, " music ")

    working = _strip_outer_brackets(working.lower())
    if not working:
        return False

    tokens = tokenize_text(working)
    if not tokens:
        return False

    keywords = {token.lower() for token in (music_keywords or MUSIC_KEYWORDS)}
    fillers = MUSIC_FILLER_TOKENS

    # All tokens must be either keywords or fillers for this to count
    if not all(token in keywords or token in fillers for token in tokens):
        return False

    # Drop filler tokens; if what's left is 1–2 pure music keywords, treat as music-only
    filtered = [token for token in tokens if token not in fillers]
    if not filtered:
        return False
    if len(filtered) <= 2 and all(token in keywords for token in filtered):
        return True

    # Special-case: allow longer runs of pure music markers/keywords
    if all(token in keywords for token in filtered):
        return True

    return False


def _safe_probability(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _build_gate_result(
    *,
    language: str,
    probability,
    method: str,
    gate_decision: str,
    use_vad: bool,
    en_ratio: float,
    fr_ratio: float,
    token_count: int,
    music_only: bool,
) -> Dict[str, Any]:
    raw_prob = probability
    prob_value = _safe_probability(probability)
    gate_meta = {
        "mid_zone": MID_LOWER <= prob_value < MID_UPPER,
        "language": language,
        "probability": prob_value,
        "stopword_ratio_en": en_ratio,
        "stopword_ratio_fr": fr_ratio,
        "token_count": token_count,
        "vad_used": use_vad,
        "music_only": music_only,
        "config": {
            "mid_lower": MID_LOWER,
            "mid_upper": MID_UPPER,
            "min_stopword_en": MID_EN_MIN_STOPWORD_RATIO,
            "min_stopword_fr": MID_FR_MIN_STOPWORD_RATIO,
            "stopword_margin": STOPWORD_MARGIN,
            "min_tokens": MIN_TOKENS_FOR_HEURISTIC,
            "music_keywords": sorted(MUSIC_KEYWORDS),
        },
    }
    return {
        "language": language,
        "probability": raw_prob,
        "method": method,
        "gate_decision": gate_decision,
        "gate_meta": gate_meta,
        "use_vad": use_vad,
        "music_only": music_only,
    }

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
    segments, info = model.transcribe(probe_audio, vad_filter=False, beam_size=1)
    transcript = " ".join([getattr(seg, "text", "") for seg in segments if getattr(seg, "text", "")])

    if is_music_only_transcript(transcript):
        raise HTTPException(
            status_code=400,
            detail="Only English/French speech supported (music-only content detected).",
        )

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
    Adds mid-zone heuristics based on English/French stopwords to decide whether
    to skip a VAD retry, and exposes gate metadata for downstream consumers.
    The audio provided is the full audio clip.
    """
    model = get_model()
    probe_audio = _create_audio_probe(audio)

    # 1. Standard language detection on the probe (no VAD)
    segments, info = model.transcribe(probe_audio, vad_filter=False, beam_size=1)
    transcript_parts = [getattr(seg, "text", "") for seg in segments if getattr(seg, "text", "")]
    transcript = " ".join(transcript_parts)

    detected_lang = info.language
    probability = info.language_probability
    prob_value = _safe_probability(probability)
    logger.info(f"detect(probe): autodetect={detected_lang} p={prob_value:.2f}")

    # Debug: inspect transcript, tokens, and music-only probe classification
    tokens = tokenize_text(transcript)
    token_count = len(tokens)
    music_only = is_music_only_transcript(transcript)
    logger.info(
        "GATE DEBUG: transcript={!r} tokens={!r} music_only_probe={!r}",
        transcript,
        tokens,
        music_only,
    )

    en_ratio = compute_stopword_ratio(transcript, EN_STOPWORDS)
    fr_ratio = compute_stopword_ratio(transcript, FR_STOPWORDS)

    if music_only:
        logger.info("Autodetect transcript indicates background music only; classifying as NO_SPEECH_MUSIC_ONLY.")
        return _build_gate_result(
            language="none",
            probability=probability,
            method="autodetect",
            gate_decision="NO_SPEECH_MUSIC_ONLY",
            use_vad=False,
            en_ratio=0.0,
            fr_ratio=0.0,
            token_count=token_count,
            music_only=True,
        )

    if detected_lang in ALLOWED_LANGS:
        if prob_value >= MID_UPPER:
            dominant_ratio = max(en_ratio, fr_ratio)
            if (
                token_count >= MIN_TOKENS_FOR_SPEECH
                and dominant_ratio >= MIN_STOPWORD_FOR_SPEECH
            ):
                logger.info(
                    "Autodetect high confidence with speechy transcript: "
                    "lang=%s p=%.2f tokens=%d en_ratio=%.2f fr_ratio=%.2f",
                    detected_lang,
                    prob_value,
                    token_count,
                    en_ratio,
                    fr_ratio,
                )
                metrics.LANGID_AUTODETECT_ACCEPT.inc()
                return _build_gate_result(
                    language=detected_lang,
                    probability=probability,
                    method="autodetect",
                    gate_decision="accepted_high_conf",
                    use_vad=False,
                    en_ratio=en_ratio,
                    fr_ratio=fr_ratio,
                    token_count=token_count,
                    music_only=False,
                )

            logger.info(
                "High prob but transcript not speechy enough "
                "(p=%.2f, tokens=%d, en_ratio=%.2f, fr_ratio=%.2f); "
                "skipping high-conf accept and retrying with VAD.",
                prob_value,
                token_count,
                en_ratio,
                fr_ratio,
            )

        if prob_value >= MID_LOWER and detected_lang in {"en", "fr"}:
            if (
                detected_lang == "en"
                and token_count >= MIN_TOKENS_FOR_HEURISTIC
                and en_ratio >= MID_EN_MIN_STOPWORD_RATIO
                and en_ratio > fr_ratio + STOPWORD_MARGIN
            ):
                logger.info(
                    f"Autodetect mid-zone accepted (EN): p={prob_value:.2f}, en_ratio={en_ratio:.2f}, fr_ratio={fr_ratio:.2f}, tokens={token_count}"
                )
                metrics.LANGID_AUTODETECT_ACCEPT.inc()
                return _build_gate_result(
                    language=detected_lang,
                    probability=probability,
                    method="autodetect",
                    gate_decision="accepted_mid_zone_en",
                    use_vad=False,
                    en_ratio=en_ratio,
                    fr_ratio=fr_ratio,
                    token_count=token_count,
                    music_only=False,
                )

            if (
                detected_lang == "fr"
                and token_count >= MIN_TOKENS_FOR_HEURISTIC
                and fr_ratio >= MID_FR_MIN_STOPWORD_RATIO
                and fr_ratio > en_ratio + STOPWORD_MARGIN
            ):
                logger.info(
                    f"Autodetect mid-zone accepted (FR): p={prob_value:.2f}, en_ratio={en_ratio:.2f}, fr_ratio={fr_ratio:.2f}, tokens={token_count}"
                )
                metrics.LANGID_AUTODETECT_ACCEPT.inc()
                return _build_gate_result(
                    language=detected_lang,
                    probability=probability,
                    method="autodetect",
                    gate_decision="accepted_mid_zone_fr",
                    use_vad=False,
                    en_ratio=en_ratio,
                    fr_ratio=fr_ratio,
                    token_count=token_count,
                    music_only=False,
                )

    # 2. VAD retry if confidence is low or heuristics rejected the mid-zone case
    logger.info("Initial detection insufficient; re-trying with VAD on probe.")
    segments_vad, info_vad = model.transcribe(probe_audio, vad_filter=True, beam_size=1)
    detected_lang_vad = info_vad.language
    probability_vad = info_vad.language_probability
    prob_vad_value = _safe_probability(probability_vad)
    logger.info(
        f"detect(probe, VAD): autodetect={detected_lang_vad} p={prob_vad_value:.2f}"
    )

    transcript_vad_parts = [
        getattr(seg, "text", "") for seg in segments_vad if getattr(seg, "text", "")
    ]
    transcript_vad = " ".join(transcript_vad_parts)

    if is_music_only_transcript(transcript_vad):
        logger.info(
            "VAD transcript indicates background music only; "
            "classifying as NO_SPEECH_MUSIC_ONLY."
        )
        return _build_gate_result(
            language="none",
            probability=probability_vad,
            method="autodetect-vad",
            gate_decision="NO_SPEECH_MUSIC_ONLY",
            use_vad=True,
            en_ratio=0.0,
            fr_ratio=0.0,
            token_count=len(tokenize_text(transcript_vad)),
            music_only=True,
        )
    
    if detected_lang_vad in ALLOWED_LANGS and prob_vad_value >= LANG_DETECT_MIN_PROB:
        logger.info(
            f"Autodetect successful [via VAD]: lang={detected_lang_vad}, p={prob_vad_value:.2f} (threshold={LANG_DETECT_MIN_PROB:.2f})"
        )
        metrics.LANGID_AUTODETECT_ACCEPT.inc()
        return _build_gate_result(
            language=detected_lang_vad,
            probability=probability_vad,
            method="autodetect-vad",
            gate_decision="vad_retry",
            use_vad=True,
            en_ratio=en_ratio,
            fr_ratio=fr_ratio,
            token_count=token_count,
            music_only=False,
        )

    # 3. Handle non-EN/FR or persistent low confidence
    logger.warning(
        f"Autodetect rejected: lang={detected_lang}, p={prob_value:.2f} (threshold={LANG_DETECT_MIN_PROB:.2f}). Entering fallback/reject logic."
    )
    metrics.LANGID_AUTODETECT_REJECT.inc()

    if ENFR_STRICT_REJECT:
        raise HTTPException(
            status_code=400,
            detail=f"Only English/French audio supported (p={prob_value:.2f}, got '{detected_lang}').",
        )

    chosen_lang = pick_en_or_fr_by_scoring(probe_audio)
    return _build_gate_result(
        language=chosen_lang,
        probability=None,
        method="fallback",
        gate_decision="fallback",
        use_vad=True,
        en_ratio=en_ratio,
        fr_ratio=fr_ratio,
        token_count=token_count,
        music_only=False,
    )
