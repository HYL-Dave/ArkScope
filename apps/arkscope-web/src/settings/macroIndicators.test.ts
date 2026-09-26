import { describe, expect, it } from "vitest";
import i18n from "i18next";
import type { MacroSnapshotItem } from "../api";
import { MACRO_INDICATOR_IDS, isMacroIndicator, macroIndicatorCopy, macroObservationPeriod } from "./macroIndicators";

describe("macro indicators", () => {
  it.each([
    ["Monthly", "2026-08-01", "2026-08"],
    ["Quarterly", "2026-04-01", "2026 Q2"],
    ["Daily", "2026-09-25", "2026-09-25"],
    [undefined, "2026-04-01", "2026-04-01"],
    ["Quarterly", "2026-99-01", "2026-99-01"],
    ["Monthly", null, "\u2014"],
  ])("formats %s observation without fabricating a release date", (frequency, observation_date, expected) => {
    expect(macroObservationPeriod({ frequency, observation_date } as MacroSnapshotItem)).toBe(expected);
  });

  it("covers all eleven reviewed series in both locales without exposing unknown IDs as guidance", () => {
    expect(MACRO_INDICATOR_IDS).toHaveLength(11);
    expect(isMacroIndicator("USER_CUSTOM")).toBe(false);
    for (const locale of ["en", "zh-Hant"]) {
      const t = i18n.getFixedT(locale, "settings");
      for (const id of MACRO_INDICATOR_IDS) {
        expect(isMacroIndicator(id)).toBe(true);
        expect(macroIndicatorCopy(id, t).length).toBeGreaterThan(20);
        expect(macroIndicatorCopy(id, t)).not.toContain("macroStorage.guide");
      }
    }
  });
});
