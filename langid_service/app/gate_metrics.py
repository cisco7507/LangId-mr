"""Gate path metric classification and recording helpers.

This module centralizes the logic that maps detailed gate results produced by
``lang_gate.detect_lang_en_fr_only`` into a small, stable set of labels that can
be safely exported to Prometheus and consumed by the dashboard.
"""
from __future__ import annotations

from typing import Mapping, Any, Optional

from loguru import logger

from . import metrics

# Canonical gate path labels expected by Prometheus queries and the dashboard.
GATE_PATH_HIGH_CONF = "high_conf_base"
GATE_PATH_MID_ZONE_EN = "mid_zone_en"
GATE_PATH_MID_ZONE_FR = "mid_zone_fr"
GATE_PATH_VAD_RETRY = "vad_retry"
GATE_PATH_MUSIC_ONLY = "music_only"
GATE_PATH_FALLBACK = "fallback"
GATE_PATH_UNKNOWN = "unknown"

GATE_PATH_CHOICES = (
    GATE_PATH_HIGH_CONF,
    GATE_PATH_MID_ZONE_EN,
    GATE_PATH_MID_ZONE_FR,
    GATE_PATH_VAD_RETRY,
    GATE_PATH_MUSIC_ONLY,
    GATE_PATH_FALLBACK,
    GATE_PATH_UNKNOWN,
)

# Canonical pipeline mode labels. These are intentionally coarse-grained so they
# remain low-cardinality when exported to Prometheus.
PIPELINE_MODE_BASE = "BASE"
PIPELINE_MODE_VAD = "VAD"
PIPELINE_MODE_MID_ZONE = "MID_ZONE"
PIPELINE_MODE_MUSIC_ONLY = "MUSIC_ONLY"
PIPELINE_MODE_FALLBACK = "FALLBACK"
PIPELINE_MODE_UNKNOWN = "UNKNOWN"


def _normalize_string(value: Optional[str]) -> str:
    return (value or "").strip()


def _to_bool(value: Any) -> bool:
    return bool(value)


def classify_gate_path(gate_result: Mapping[str, Any]) -> str:
    """Return a stable gate path label for metrics and reporting."""
    gate_decision = _normalize_string(
        gate_result.get("gate_decision") if gate_result else None
    )
    gate_decision_lower = gate_decision.lower()

    if _to_bool(gate_result.get("music_only")):
        return GATE_PATH_MUSIC_ONLY

    if gate_decision_lower == "no_speech_music_only":
        return GATE_PATH_MUSIC_ONLY

    if gate_decision_lower == "fallback":
        return GATE_PATH_FALLBACK

    if gate_decision_lower == "vad_retry":
        return GATE_PATH_VAD_RETRY

    if gate_decision_lower == "accepted_mid_zone_en":
        return GATE_PATH_MID_ZONE_EN

    if gate_decision_lower == "accepted_mid_zone_fr":
        return GATE_PATH_MID_ZONE_FR

    if gate_decision_lower == "accepted_high_conf":
        return GATE_PATH_HIGH_CONF

    # fall back to heuristics if the decision string is missing or unexpected
    gate_meta = gate_result.get("gate_meta") if gate_result else None
    if isinstance(gate_meta, Mapping) and gate_meta.get("mid_zone"):
        language = _normalize_string(gate_result.get("language")).lower()
        if language == "fr":
            return GATE_PATH_MID_ZONE_FR
        if language == "en":
            return GATE_PATH_MID_ZONE_EN
        return GATE_PATH_MID_ZONE_EN

    return GATE_PATH_UNKNOWN


def classify_pipeline_mode(gate_result: Mapping[str, Any]) -> str:
    """Return a coarse pipeline mode label for Prometheus."""
    gate_decision = _normalize_string(
        gate_result.get("gate_decision") if gate_result else None
    ).lower()
    gate_meta = gate_result.get("gate_meta") if gate_result else None
    detection_method = _normalize_string(
        gate_result.get("detection_method") if gate_result else None
    ).lower()

    if gate_decision == "fallback":
        return PIPELINE_MODE_FALLBACK

    if gate_decision == "no_speech_music_only" or _to_bool(
        gate_result.get("music_only")
    ):
        return PIPELINE_MODE_MUSIC_ONLY

    if gate_decision in {"accepted_mid_zone_en", "accepted_mid_zone_fr"}:
        return PIPELINE_MODE_MID_ZONE

    if isinstance(gate_meta, Mapping) and gate_meta.get("mid_zone"):
        return PIPELINE_MODE_MID_ZONE

    if gate_decision == "vad_retry":
        return PIPELINE_MODE_VAD

    if isinstance(gate_meta, Mapping) and gate_meta.get("vad_used"):
        return PIPELINE_MODE_VAD

    if detection_method.startswith("vad"):
        return PIPELINE_MODE_VAD

    if gate_decision == "accepted_high_conf":
        return PIPELINE_MODE_BASE

    return PIPELINE_MODE_UNKNOWN


def record_gate_path_metrics(
    gate_result: Mapping[str, Any],
    *,
    job_id: Optional[str] = None,
) -> None:
    """Increment the Prometheus counter for a finalized gate decision."""
    if not gate_result:
        logger.warning("Skipping gate metric recording for empty result")
        return

    gate_path = classify_gate_path(gate_result)
    pipeline_mode = classify_pipeline_mode(gate_result)

    gate_decision = _normalize_string(gate_result.get("gate_decision")) or "unknown"
    language = _normalize_string(gate_result.get("language")) or "unknown"
    music_only_label = "true" if _to_bool(gate_result.get("music_only")) else "false"

    metrics.LANGID_GATE_PATH_DECISIONS.labels(
        gate_path=gate_path,
        gate_decision=gate_decision,
        pipeline_mode=pipeline_mode,
        language=language,
        music_only=music_only_label,
    ).inc()

    logger.bind(job_id=job_id or gate_result.get("job_id", "-")).debug(
        "Recorded gate path metric",
        gate_path=gate_path,
        gate_decision=gate_decision,
        pipeline_mode=pipeline_mode,
        language=language,
        music_only=music_only_label,
    )
