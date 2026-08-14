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

  it("localizes degraded capture counts and typed diagnostic causes in both locales", () => {
    const segment: SAExtensionHealthSegment = {
      key: "telemetry_last",
      state: "warn",
      code: "capture_degraded",
      job_name: "sa_alpha_picks_refresh",
      outcome: "degraded",
      counts: { repaired: 17, failed_retryable: 1, item_total: 18 },
      run_id: 16417,
      occurred_at: "2026-07-19T11:45:38+00:00",
      diagnostics_status: "recorded",
      diagnostics_error_code: null,
      diagnostics: [{
        occurred_at: "2026-07-19T11:45:30+00:00",
        stage: "page_readiness",
        reason_code: "navigation_timeout",
        target_kind: "article_detail",
        target_ref: "opaque-17",
        retryable: true,
        attempt_count: 2,
        message: "PLANTED_RAW_NAVIGATION_DETAIL",
      }],
      diagnostics_omitted_count: 0,
      diagnostic_recurrence: [],
    };

    const zh = displaySAExtensionSegments([segment], settingsT("zh-Hant"))[0].copy;
    const en = displaySAExtensionSegments([segment], settingsT("en"))[0].copy;
    expect(zh).toContain("Alpha Picks");
    expect(zh).toContain("擷取部分完成");
    expect(zh).toContain("17 筆完成");
    expect(zh).toContain("1 筆可重試");
    expect(zh).toContain("頁面尚未就緒");
    expect(zh).toContain("無法判定");
    expect(en).toContain("Alpha Picks");
    expect(en).toContain("Capture degraded");
    expect(en).toContain("17 completed");
    expect(en).toContain("1 retryable");
    expect(en).toContain("Page not ready");
    expect(en).toContain("cannot distinguish");
    expect(JSON.stringify([zh, en])).not.toContain("PLANTED_RAW_NAVIGATION_DETAIL");
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

  it("exposes only admitted diagnostic fields and bounded recurrence in Developer Mode", () => {
    const segment: SAExtensionHealthSegment = {
      key: "telemetry_last",
      state: "warn",
      code: "capture_degraded",
      job_name: "sa_market_news_refresh",
      outcome: "degraded",
      occurred_at: "2026-08-14T01:01:00+00:00",
      diagnostics_status: "recorded",
      diagnostics_error_code: null,
      diagnostics: [{
        occurred_at: "2026-08-14T01:00:40+00:00",
        stage: "local_persistence",
        reason_code: "database_busy",
        target_kind: "market_news_detail",
        target_ref: "opaque-2",
        retryable: true,
        attempt_count: 3,
        message: "PLANTED_RAW_DATABASE_MESSAGE",
      }],
      diagnostics_omitted_count: 2,
      diagnostic_recurrence: [{
        job_name: "sa_market_news_refresh",
        stage: "local_persistence",
        reason_code: "database_busy",
        affected_run_count: 4,
        latest_occurred_at: "2026-08-14T01:00:40+00:00",
      }],
    };

    const row = displaySAExtensionSegments([segment], settingsT("en"), true)[0];
    expect(row.diagnostic).toContain("Job: Market News");
    expect(row.diagnostic).toContain("Stage: Local persistence");
    expect(row.diagnostic).toContain("Reason: Local database busy");
    expect(row.diagnostic).toContain("Target: market_news_detail (opaque-2)");
    expect(row.diagnostic).toContain("Retryable: true");
    expect(row.diagnostic).toContain("Attempt: 3");
    expect(row.diagnostic).toContain("Omitted diagnostics: 2");
    expect(row.diagnostic).toContain("Recurrence: Market News / Local persistence / Local database busy / 4");
    expect(JSON.stringify(row)).not.toContain("PLANTED_RAW_DATABASE_MESSAGE");
  });

  it("distinguishes browser readiness native transport and local persistence without raw detail", () => {
    const cases = [
      ["page_readiness", "dom_not_ready", "頁面尚未就緒"],
      ["native_transport", "native_host_unavailable", "Native 傳輸"],
      ["local_persistence", "database_write_failed", "本機資料庫寫入失敗"],
    ] as const;

    const copies = cases.map(([stage, reason]) => displaySAExtensionSegments([{
      key: "telemetry_last",
      state: "fail",
      code: "capture_failed",
      job_name: "sa_market_news_refresh",
      outcome: "failed",
      occurred_at: "2026-08-14T01:01:00+00:00",
      diagnostics_status: "recorded",
      diagnostics_error_code: null,
      diagnostics: [{
        occurred_at: "2026-08-14T01:00:40+00:00",
        stage,
        reason_code: reason,
        target_kind: "phase",
        retryable: true,
        attempt_count: 1,
        message: `PLANTED_RAW_${stage}`,
      }],
      diagnostics_omitted_count: 0,
      diagnostic_recurrence: [],
    }], settingsT("zh-Hant"))[0].copy);

    cases.forEach(([, , expected], index) => expect(copies[index]).toContain(expected));
    expect(new Set(copies).size).toBe(3);
    expect(JSON.stringify(copies)).not.toContain("PLANTED_RAW_");
  });

  it("renders legacy diagnostic absence without inventing a cause", () => {
    const row = displaySAExtensionSegments([{
      key: "telemetry_last",
      state: "fail",
      code: "capture_failed",
      job_name: "sa_market_news_refresh",
      outcome: "failed",
      occurred_at: "2026-08-14T02:00:00+00:00",
      diagnostics_status: "absent",
      diagnostics_error_code: null,
      diagnostic_recurrence: [],
      detail: "PLANTED_INFERRED_NETWORK_CAUSE",
    }], settingsT("zh-Hant"))[0];

    expect(row.copy).toContain("原因未記錄（舊版資料）");
    expect(JSON.stringify(row)).not.toContain("PLANTED_INFERRED_NETWORK_CAUSE");
    expect(row.copy).not.toContain("網路");
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
      .toBe("最近一次歷史修復仍在執行 · Manifest abcdef123456");
    expect(displaySAExtensionSegments([retryable], settingsT("en"))[0].copy)
      .toBe("Latest historical repair has 2 retryable items · Manifest 123456abcdef");
  });
});
