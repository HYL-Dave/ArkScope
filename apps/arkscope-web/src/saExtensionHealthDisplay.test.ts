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
    expect(rows[3].copy).toBe("主機測試失敗");
  });

  it("keeps unknown segment keys visible", () => {
    const rows = displaySAExtensionSegments(
      [{
        ...seg("future_segment", "warn", "PLANTED_RAW_UNKNOWN_DETAIL"),
        code: "future_condition",
      }],
      settingsT("zh-Hant"),
    );

    expect(rows[0]).toMatchObject({
      key: "future_segment",
      label: "future_segment",
      mark: "—",
      tone: "warn",
      copy: "狀態細節目前無法確認",
    });
    expect(JSON.stringify(rows[0])).not.toContain("PLANTED_RAW_UNKNOWN_DETAIL");
  });

  it("maps every known segment and fails unknown health prose closed in both locales", () => {
    const keys = [
      "config",
      "manifests",
      "launcher",
      "host_ping",
      "telemetry_binding",
      "telemetry_last",
      "market_news_repair",
      "capture_readback",
      "future_segment",
    ];
    const cases = [
      {
        locale: "zh-Hant" as const,
        labels: ["設定檔", "瀏覽器註冊", "啟動器", "主機測試", "遙測綁定", "最近遙測", "market_news_repair", "資料回讀", "future_segment"],
        unknown: "狀態細節目前無法確認",
      },
      {
        locale: "en" as const,
        labels: ["Configuration", "Browser registration", "Launcher", "Host ping", "Telemetry binding", "Latest telemetry", "market_news_repair", "Capture readback", "future_segment"],
        unknown: "Status details are currently unavailable",
      },
    ];

    for (const expected of cases) {
      const rows = displaySAExtensionSegments(
        keys.map((key) => key === "telemetry_last" || key === "market_news_repair" || key === "future_segment"
          ? {
              ...seg(key, "warn", `PLANTED_DETAIL_${key}`),
              code: "future_condition",
            }
          : seg(key, "warn", `PLANTED_DETAIL_${key}`)),
        settingsT(expected.locale),
      );
      expect(rows.map((row) => row.label)).toEqual(expected.labels);
      expect(rows.slice(0, 5).map((row) => row.copy)).toEqual(
        keys.slice(0, 5).map((key) => `PLANTED_DETAIL_${key}`),
      );
      expect(rows[5].copy).toBe(expected.unknown);
      expect(rows[6].copy).toBe(expected.unknown);
      expect(rows[8].copy).toBe(expected.unknown);
      expect(JSON.stringify(rows.filter((row) => row.showDetail)))
        .not.toContain("PLANTED_DETAIL_");
    }
  });

  it("localizes structured detail failure counts in both locales", () => {
    const segment: SAExtensionHealthSegment = {
      key: "telemetry_last",
      state: "fail",
      code: "detail_failures_recorded",
      counts: { failed_retryable: 18, item_total: 18 },
      run_id: 16417,
      occurred_at: "2026-07-19T11:45:38+00:00",
    };

    expect(displaySAExtensionSegments([segment], settingsT("zh-Hant"))[0].copy)
      .toBe("已記錄 18 筆可重試的詳情失敗");
    expect(displaySAExtensionSegments([segment], settingsT("en"))[0].copy)
      .toBe("18 retryable detail failures recorded");
  });

  it("fails unknown structured codes closed to generic localized copy", () => {
    const segment: SAExtensionHealthSegment = {
      key: "telemetry_last",
      state: "warn",
      code: "new_backend_condition",
      detail: "PLANTED_RAW_BACKEND_PROSE",
    };

    const zh = displaySAExtensionSegments([segment], settingsT("zh-Hant"))[0];
    const en = displaySAExtensionSegments([segment], settingsT("en"))[0];
    expect(zh.copy).toBe("狀態細節目前無法確認");
    expect(en.copy).toBe("Status details are currently unavailable");
    expect(JSON.stringify([zh, en])).not.toContain("PLANTED_RAW_BACKEND_PROSE");
  });

  it("exposes only bounded stable codes as Developer diagnostics", () => {
    const valid: SAExtensionHealthSegment = {
      key: "telemetry_last",
      state: "fail",
      code: "detail_failures_recorded",
      detail: "PLANTED_RAW_DETAIL",
    };
    const unsafe: SAExtensionHealthSegment = {
      key: "market_news_repair",
      state: "fail",
      code: "../../home/operator/secret",
      detail: "PLANTED_UNSAFE_DETAIL",
    };

    const rows = displaySAExtensionSegments(
      [valid, unsafe],
      settingsT("en"),
      true,
    );
    expect(rows[0].diagnostic).toBe("Developer code: detail_failures_recorded");
    expect(rows[1].diagnostic).toBeNull();
    expect(JSON.stringify(rows)).not.toContain("PLANTED_");
  });

  it("localizes active and retryable repair state with a bounded manifest prefix", () => {
    const active: SAExtensionHealthSegment = {
      key: "market_news_repair",
      state: "warn",
      code: "repair_active",
      run_id: 51,
      manifest_hash_prefix: "abcdef123456",
    };
    const retryable: SAExtensionHealthSegment = {
      key: "market_news_repair",
      state: "fail",
      code: "repair_retryable",
      counts: { failed_retryable: 2, repaired: 6 },
      run_id: 52,
      manifest_hash_prefix: "123456abcdef",
    };

    expect(displaySAExtensionSegments([active], settingsT("zh-Hant"))[0].copy)
      .toBe("修復進行中 · Manifest abcdef123456");
    expect(displaySAExtensionSegments([retryable], settingsT("en"))[0].copy)
      .toBe("2 items remain retryable · Manifest 123456abcdef");
  });
});
