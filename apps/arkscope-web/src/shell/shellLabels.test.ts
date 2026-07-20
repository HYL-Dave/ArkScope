import { createInstance } from "i18next";
import { describe, expect, it } from "vitest";

import { initializeI18n } from "../i18n/resources";
import { shellNavGroupLabel, shellViewLabel } from "./shellLabels";
import type { ShellNavGroupId, ShellView } from "./navigation";

describe("shell label authority", () => {
  it("maps every shell workflow group in both locales", () => {
    const ids: ShellNavGroupId[] = ["explore", "research", "monitor", "system"];
    const cases = [
      { locale: "zh-Hant" as const, labels: ["探索", "研究", "追蹤", "系統"] },
      { locale: "en" as const, labels: ["Explore", "Research", "Monitor", "System"] },
    ];

    for (const expected of cases) {
      const instance = createInstance();
      initializeI18n(instance, expected.locale);
      const t = instance.getFixedT(expected.locale, "shell");
      expect(ids.map((id) => shellNavGroupLabel(id, t))).toEqual(expected.labels);
    }
  });

  it("maps every shipped shell view in both locales", () => {
    const views: ShellView[] = [
      "Home",
      "Watchlist",
      "Universe",
      "News",
      "Research",
      "Holdings",
      "System",
      "Settings",
    ];
    const cases = [
      {
        locale: "zh-Hant" as const,
        labels: ["工作台", "自選股", "全部標的", "新聞·事件", "AI 研究", "持倉", "System / Health", "設定"],
      },
      {
        locale: "en" as const,
        labels: ["Home", "Watchlist", "Universe", "News", "AI Research", "Holdings", "System / Health", "Settings"],
      },
    ];

    for (const expected of cases) {
      const instance = createInstance();
      initializeI18n(instance, expected.locale);
      const t = instance.getFixedT(expected.locale, "shell");
      expect(views.map((view) => shellViewLabel(view, t))).toEqual(expected.labels);
    }
  });
});
