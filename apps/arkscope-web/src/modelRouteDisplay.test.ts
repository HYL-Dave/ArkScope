import { createInstance } from "i18next";
import { describe, expect, it } from "vitest";

import { initializeI18n } from "./i18n/resources";
import { routeSourceBadge, routeIsOverridable } from "./modelRouteDisplay";
import type { SettingsT } from "./settings/settingsCopy";

function settingsT(locale: "zh-Hant" | "en"): SettingsT {
  const instance = createInstance();
  initializeI18n(instance, locale);
  return instance.getFixedT(locale, "settings");
}

const zhT = settingsT("zh-Hant");

describe("routeSourceBadge", () => {
  it("labels DB authority as the saved/active app setting", () => {
    expect(routeSourceBadge("db", zhT)).toEqual({ label: "DB（已儲存）", tone: "active" });
  });
  it("labels yaml profile as a fallback, not the live authority", () => {
    expect(routeSourceBadge("profile", zhT)).toEqual({ label: "設定檔 fallback", tone: "fallback" });
  });
  it("labels an env var as an operator override that outranks the DB", () => {
    expect(routeSourceBadge("env", zhT)).toEqual({ label: "env 覆蓋", tone: "override" });
  });
  it("labels default as the built-in seed", () => {
    expect(routeSourceBadge("default", zhT)).toEqual({ label: "內建預設", tone: "default" });
  });

  it("renders every route authority in English", () => {
    const t = settingsT("en");
    expect([
      routeSourceBadge("env", t).label,
      routeSourceBadge("db", t).label,
      routeSourceBadge("profile", t).label,
      routeSourceBadge("default", t).label,
    ]).toEqual([
      "Environment override",
      "DB (saved)",
      "Profile fallback",
      "Built-in default",
    ]);
  });

  it("uses the active Settings translator instead of captured source copy", async () => {
    const instance = createInstance();
    initializeI18n(instance, "zh-Hant");
    expect(routeSourceBadge("db", instance.getFixedT(null, "settings")).label)
      .toBe("DB（已儲存）");

    await instance.changeLanguage("en");

    expect(routeSourceBadge("db", instance.getFixedT(null, "settings")).label)
      .toBe("DB (saved)");
  });
});

describe("routeIsOverridable", () => {
  it("only a DB-authoritative route can be reset (there is a DB row to remove)", () => {
    expect(routeIsOverridable("db")).toBe(true);
  });
  it("yaml/default/env routes have no DB row → nothing to reset", () => {
    expect(routeIsOverridable("profile")).toBe(false);
    expect(routeIsOverridable("default")).toBe(false);
    expect(routeIsOverridable("env")).toBe(false);
  });
});
