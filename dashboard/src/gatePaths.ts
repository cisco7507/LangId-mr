export type GatePathKey =
  | "high_conf_base"
  | "vad_retry"
  | "music_only"
  | "mid_zone_stopword"
  | "fallback_scoring";

export interface GatePathMeta {
  key: GatePathKey;
  label: string;
  description: string;
  color: string;
}

export const GATE_PATH_META: Record<GatePathKey, GatePathMeta> = {
  high_conf_base: {
    key: "high_conf_base",
    label: "High-Confidence Auto Detect",
    description:
      "Language auto-detected with high probability on the first pass (no retries or fallbacks).",
    color: "#22C55E",
  },
  vad_retry: {
    key: "vad_retry",
    label: "VAD Retry (Segmentation)",
    description:
      "Required voice activity detection and segmentation before confirming language.",
    color: "#EAB308",
  },
  music_only: {
    key: "music_only",
    label: "Music Only",
    description: "Background music detected; no reliable speech found.",
    color: "#A855F7",
  },
  mid_zone_stopword: {
    key: "mid_zone_stopword",
    label: "Mid-Zone Heuristic Check",
    description:
      "Mid-confidence sample; stopword-based heuristic used to confirm EN/FR language.",
    color: "#3B82F6",
  },
  fallback_scoring: {
    key: "fallback_scoring",
    label: "Fallback EN/FR Scoring",
    description:
      "Low-confidence case; EN/FR scoring probe used as a final tie-breaker.",
    color: "#F97316",
  },
};

const GATE_PATH_ALIASES: Record<string, GatePathKey> = {
  high_conf_base: "high_conf_base",
  high_confidence: "high_conf_base",

  vad_retry: "vad_retry",
  vad_retry_seg: "vad_retry",
  vad_recheck: "vad_retry",

  music_only: "music_only",
  music: "music_only",
  bgm: "music_only",

  mid_zone_en: "mid_zone_stopword",
  mid_zone_fr: "mid_zone_stopword",
  mid_zone_stopword: "mid_zone_stopword",
  midzone_stopword: "mid_zone_stopword",

  fallback: "fallback_scoring",
  fallback_scoring: "fallback_scoring",
  fallback_probe: "fallback_scoring",
};

export function normalizeGatePathKey(raw: string | null | undefined): GatePathKey {
  if (!raw) {
    return "fallback_scoring";
  }

  const key = String(raw).trim().toLowerCase();
  if (!key) {
    return "fallback_scoring";
  }

  return GATE_PATH_ALIASES[key] ?? "fallback_scoring";
}

export function getGatePathMeta(raw: string | null | undefined): GatePathMeta {
  const key = normalizeGatePathKey(raw);
  return GATE_PATH_META[key];
}
