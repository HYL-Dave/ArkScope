import { describe, expect, it } from "vitest";

import { mismatchLabel, stanceLabel, traceSummary } from "./personalizationDisplay";

describe("personalizationDisplay", () => {
  it("labels stances in short zh", () => {
    expect(stanceLabel("complementary")).toBe("互補投資人");
    expect(stanceLabel("aligned")).toBe("對齊投資人");
    expect(stanceLabel("strict_risk_control")).toBe("嚴格風控");
    expect(stanceLabel("off")).toBe("關閉");
  });

  it("labels mismatch as a guardrail", () => {
    expect(mismatchLabel("appetite_above_capacity")).toBe("風險意願高於承受能力");
    expect(mismatchLabel("capacity_above_appetite")).toBe("承受能力高於風險意願");
    expect(mismatchLabel("none")).toBe("一致");
    expect(mismatchLabel("unclear")).toBe("未評估");
  });

  it("summarizes traces compactly, null-safe", () => {
    expect(traceSummary(null)).toBeNull();
    expect(traceSummary(undefined)).toBeNull();
    expect(
      traceSummary({
        profile_active: false,
        assistant_stance: "off",
        skill_mode: "off",
        suggested_skills: [],
        applied_skills: [],
      }),
    ).toBeNull(); // inactive trace → nothing to show
    const s = traceSummary({
      profile_active: true,
      assistant_stance: "complementary",
      skill_mode: "off",
      suggested_skills: [],
      applied_skills: [],
    });
    expect(s).toContain("互補投資人");
  });

  it("falls back safely on unknown keys", () => {
    expect(stanceLabel("mystery" as never)).toBe("mystery");
    expect(mismatchLabel("mystery" as never)).toBe("mystery");
  });
});
