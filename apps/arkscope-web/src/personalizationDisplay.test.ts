import { createInstance } from "i18next";
import { describe, expect, it } from "vitest";

import { initializeI18n } from "./i18n/resources";
import { mismatchLabel, stanceLabel, traceSummary } from "./personalizationDisplay";

function commonT(locale: "zh-Hant" | "en") {
  const instance = createInstance();
  initializeI18n(instance, locale);
  return instance.getFixedT(locale, "common");
}

describe("personalizationDisplay", () => {
  it("labels every Assistant Stance in both locales", () => {
    const stances = [
      "off",
      "neutral",
      "aligned",
      "complementary",
      "strict_risk_control",
      "valuation_rationalist",
      "growth_opportunity",
    ] as const;
    const expected = {
      "zh-Hant": ["關閉", "中性", "對齊投資人", "互補投資人", "嚴格風控", "估值理性派", "成長機會派"],
      en: ["Off", "Neutral", "Investor-aligned", "Complementary", "Strict risk control", "Valuation rationalist", "Growth opportunity"],
    } as const;

    for (const locale of ["zh-Hant", "en"] as const) {
      const t = commonT(locale);
      expect(stances.map((stance) => stanceLabel(stance, t))).toEqual(expected[locale]);
    }
  });

  it("labels mismatch as a guardrail", () => {
    const mismatches = [
      "none", "appetite_above_capacity", "capacity_above_appetite", "unclear",
    ] as const;
    const expected = {
      "zh-Hant": ["一致", "風險意願高於承受能力", "承受能力高於風險意願", "未評估"],
      en: ["Aligned", "Risk appetite above capacity", "Risk capacity above appetite", "Not assessed"],
    } as const;

    for (const locale of ["zh-Hant", "en"] as const) {
      const t = commonT(locale);
      expect(mismatches.map((mismatch) => mismatchLabel(mismatch, t)))
        .toEqual(expected[locale]);
    }
  });

  it("summarizes traces compactly, null-safe", () => {
    const zhT = commonT("zh-Hant");
    const enT = commonT("en");
    expect(traceSummary(null, zhT)).toBeNull();
    expect(traceSummary(undefined, zhT)).toBeNull();
    expect(
      traceSummary({
        profile_active: false,
        assistant_stance: "off",
        skill_mode: "off",
        suggested_skills: [],
        applied_skills: [],
      }, zhT),
    ).toBeNull(); // inactive trace → nothing to show
    const applied = traceSummary({
      profile_active: true,
      assistant_stance: "complementary",
      skill_mode: "off",
      suggested_skills: [],
      applied_skills: ["quality", "cash flow"],
    }, zhT);
    expect(applied).toBe("立場：互補投資人　套用技能：quality、cash flow");

    const suggested = traceSummary({
      profile_active: true,
      assistant_stance: "growth_opportunity",
      skill_mode: "suggest_only",
      suggested_skills: ["evidence-first"],
      applied_skills: [],
    }, enT);
    expect(suggested).toBe("Stance: Growth opportunity　Suggested skills: evidence-first");
  });

  it("falls back safely on unknown keys", () => {
    const t = commonT("en");
    expect(stanceLabel("mystery" as never, t)).toBe("mystery");
    expect(mismatchLabel("mystery" as never, t)).toBe("mystery");
  });
});
