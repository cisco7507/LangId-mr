import { GATE_PATH_META, normalizeGatePathKey, GatePathKey } from "./gatePaths";

describe("normalizeGatePathKey", () => {
  const cases: Array<[unknown, GatePathKey]> = [
    ["high_confidence", "high_conf_base"],
    ["HIGH_CONF_BASE", "high_conf_base"],
    ["vad_recheck", "vad_retry"],
    ["vad_retry_seg", "vad_retry"],
    ["music", "music_only"],
    ["bgm", "music_only"],
    ["mid_zone_en", "mid_zone_stopword"],
    ["midzone_stopword", "mid_zone_stopword"],
    ["fallback", "fallback_scoring"],
    ["fallback_probe", "fallback_scoring"],
    [null, "fallback_scoring"],
    ["", "fallback_scoring"],
    ["some_other_path", "fallback_scoring"],
  ];

  test.each(cases)("normalizes %p to %p", (input, expected) => {
    expect(normalizeGatePathKey(input as string | null | undefined)).toBe(expected);
  });
});

describe("GATE_PATH_META", () => {
  it("exposes labels and colors for each canonical key", () => {
    (Object.keys(GATE_PATH_META) as GatePathKey[]).forEach((key) => {
      const meta = GATE_PATH_META[key];
      expect(meta.label.length).toBeGreaterThan(0);
      expect(meta.description.length).toBeGreaterThan(0);
      expect(meta.color).toMatch(/^#/);
    });
  });

  it("provides metadata for alias keys", () => {
    const canonicalKey = normalizeGatePathKey("fallback_probe");
    const meta = GATE_PATH_META[canonicalKey];
    expect(meta.label).toBe("Fallback EN/FR Scoring");
  });
});
