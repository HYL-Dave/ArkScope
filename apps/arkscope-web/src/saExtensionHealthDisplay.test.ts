// @vitest-environment jsdom

import { createInstance } from "i18next";
import { describe, expect, it } from "vitest";

import { initializeI18n } from "./i18n/resources";
import { displaySAExtensionSegments } from "./saExtensionHealthDisplay";
import type { SAExtensionHealthSegment } from "./api";

type Locale = "zh-Hant" | "en";

function settingsT(locale: Locale) {
  const instance = createInstance();
  initializeI18n(instance, locale);
  return instance.getFixedT(locale, "settings");
}

const seg = (key: string, state: SAExtensionHealthSegment["state"], detail = "detail"): SAExtensionHealthSegment => ({
  key,
  state,
  detail,
});

describe("displaySAExtensionSegments", () => {
  it("renders the fixed native-host chain order with zh labels and symbols", () => {
    const rows = displaySAExtensionSegments([
      seg("capture_readback", "warn", "尚未有第一次擷取"),
      seg("telemetry_binding", "ok", "config 綁定本次 sidecar"),
      seg("config", "ok", "設定檔有效"),
      seg("host_ping", "fail", "主機測試失敗"),
      seg("manifests", "ok", "Firefox manifest"),
      seg("launcher", "ok", "launcher 可執行"),
      seg("telemetry_last", "warn", "尚未有 telemetry"),
    ], settingsT("zh-Hant"));

    expect(rows.map((row) => row.label)).toEqual([
      "設定檔",
      "瀏覽器註冊",
      "啟動器",
      "主機測試",
      "遙測綁定",
      "最近遙測",
      "資料回讀",
    ]);
    expect(rows.map((row) => row.mark)).toEqual(["✓", "✓", "✓", "✗", "✓", "—", "—"]);
    expect(rows[3].detail).toBe("主機測試失敗");
  });

  it("keeps unknown segment keys visible", () => {
    const rows = displaySAExtensionSegments(
      [seg("future_segment", "ok", "ok")],
      settingsT("zh-Hant"),
    );

    expect(rows).toEqual([
      { key: "future_segment", label: "future_segment", mark: "✓", tone: "ok", detail: "ok" },
    ]);
  });

  it("maps every known extension segment in both locales and preserves unknown ids", () => {
    const keys = [
      "config",
      "manifests",
      "launcher",
      "host_ping",
      "telemetry_binding",
      "telemetry_last",
      "capture_readback",
      "future_segment",
    ];
    const cases = [
      {
        locale: "zh-Hant" as const,
        labels: ["設定檔", "瀏覽器註冊", "啟動器", "主機測試", "遙測綁定", "最近遙測", "資料回讀", "future_segment"],
      },
      {
        locale: "en" as const,
        labels: ["Configuration", "Browser registration", "Launcher", "Host ping", "Telemetry binding", "Latest telemetry", "Capture readback", "future_segment"],
      },
    ];

    for (const expected of cases) {
      const rows = displaySAExtensionSegments(
        keys.map((key) => seg(key, "warn", `PLANTED_DETAIL_${key}`)),
        settingsT(expected.locale),
      );
      expect(rows.map((row) => row.label)).toEqual(expected.labels);
      expect(rows.map((row) => row.detail)).toEqual(
        keys.map((key) => `PLANTED_DETAIL_${key}`),
      );
    }
  });
});
