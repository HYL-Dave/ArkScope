// @vitest-environment jsdom

import { createInstance } from "i18next";
import { describe, expect, it } from "vitest";

import { ApiError, type ScheduleRunResult } from "../api";
import { initializeI18n } from "../i18n/resources";
import {
  diagnosticValue,
  modelReasonLabel,
  providerClientDomainLabel,
  providerConfigFieldLabel,
  providerHealthCopy,
  providerKeySourceLabel,
  providerName,
  providerTestCopy,
  saSegmentLabel,
  scheduleBodyBacklogCopy,
  scheduleOutcomeCopy,
  scheduleSourceCopy,
  settingsErrorPresentation,
} from "./settingsBackendCopy";

type Locale = "zh-Hant" | "en";

function settingsT(locale: Locale) {
  const instance = createInstance();
  initializeI18n(instance, locale);
  return instance.getFixedT(locale, "settings");
}

describe("Settings backend copy boundary", () => {
  it("maps known provider and config field ids without backend labels", () => {
    const providerIds = [
      "polygon", "finnhub", "fred", "financial_datasets", "ibkr", "sec_edgar", "seeking_alpha",
    ];
    const fieldIds: Array<[string, string]> = [
      ["polygon", "api_key"],
      ["finnhub", "api_key"],
      ["fred", "api_key"],
      ["financial_datasets", "api_key"],
      ["ibkr", "host"],
      ["ibkr", "port"],
      ["ibkr", "client_id"],
      ["sec_edgar", "user_agent"],
    ];
    const cases = [
      {
        locale: "zh-Hant" as const,
        providers: ["Polygon", "Finnhub", "FRED", "Financial Datasets（付費）", "IBKR Gateway", "SEC EDGAR", "Seeking Alpha（Extension）"],
        fields: ["API key", "API key", "API key", "API key", "Gateway 主機", "Gateway 連接埠", "Client ID", "聯絡 Email"],
      },
      {
        locale: "en" as const,
        providers: ["Polygon", "Finnhub", "FRED", "Financial Datasets (paid)", "IBKR Gateway", "SEC EDGAR", "Seeking Alpha (Extension)"],
        fields: ["API key", "API key", "API key", "API key", "Gateway host", "Gateway port", "Client ID", "Contact email"],
      },
    ];

    for (const expected of cases) {
      const t = settingsT(expected.locale);
      expect(providerIds.map((id) => providerName(id, t))).toEqual(expected.providers);
      expect(fieldIds.map(([provider, field]) => providerConfigFieldLabel(provider, field, t)))
        .toEqual(expected.fields);
    }
  });

  it("maps every reviewed IBKR client-id domain", () => {
    const domains = [
      "manual", "options", "prices", "news", "iv", "quotes", "holdings", "portfolio_capture",
    ];
    const cases = [
      { locale: "zh-Hant" as const, labels: ["基底", "選擇權", "股價", "新聞", "IV", "即時股價", "持倉", "持倉擷取"] },
      { locale: "en" as const, labels: ["Base", "Options", "Prices", "News", "IV", "Quotes", "Holdings", "Portfolio capture"] },
    ];

    for (const expected of cases) {
      const t = settingsT(expected.locale);
      expect(domains.map((domain) => providerClientDomainLabel(domain, t))).toEqual(expected.labels);
    }
  });

  it("maps provider health states and setup code in both locales", () => {
    const statuses = [
      "connected", "stale", "maintenance", "no_signal", "not_configured", "missing_key", "disabled",
      "future_status",
    ];
    const cases = [
      {
        locale: "zh-Hant" as const,
        labels: ["正常", "過期", "維護中", "無訊號", "未設定", "缺少金鑰", "已停用", "future_status"],
        sources: ["App", "環境變數", "config/.env", "未設定", "混合來源", "免金鑰"],
        unknownDetail: "Polygon：future_status",
        setup: "Provider 設定需要修復。",
      },
      {
        locale: "en" as const,
        labels: ["Connected", "Stale", "Maintenance", "No signal", "Not configured", "Missing key", "Disabled", "future_status"],
        sources: ["App", "Environment", "config/.env", "Not configured", "Mixed sources", "No key required"],
        unknownDetail: "Polygon: future_status",
        setup: "Provider settings need repair.",
      },
    ];

    for (const expected of cases) {
      const t = settingsT(expected.locale);
      const copies = statuses.map((status) => providerHealthCopy("polygon", status, t));
      expect(copies.map(({ label }) => label)).toEqual(expected.labels);
      expect(copies.every(({ detail }) => detail.includes("Polygon"))).toBe(true);
      expect(copies.at(-1)).toEqual({
        label: "future_status",
        detail: expected.unknownDetail,
      });
      expect(["app", "env", "config/.env", "missing", "mixed", "not_required"]
        .map((source) => providerKeySourceLabel(source, t)))
        .toEqual(expected.sources);
      const setup = settingsErrorPresentation(
        new ApiError("planted backend message", "/providers/config", 503, "provider_config_setup_required", "PLANTED_SETUP_DETAIL"),
        t,
      );
      expect(setup).toEqual({
        message: expected.setup,
        code: "provider_config_setup_required",
        diagnostic: "PLANTED_SETUP_DETAIL",
      });
    }
  });

  it("maps provider test tri-state without raw detail", () => {
    const cases = [
      {
        locale: "zh-Hant" as const,
        values: ["Polygon 連線測試通過。", "Polygon 連線測試失敗。", "Polygon 不提供即時連線測試。"],
      },
      {
        locale: "en" as const,
        values: ["Polygon connection test passed.", "Polygon connection test failed.", "Polygon does not offer a live connection test."],
      },
    ];

    for (const expected of cases) {
      const t = settingsT(expected.locale);
      expect([true, false, null].map((ok) => providerTestCopy("polygon", ok, t)))
        .toEqual(expected.values);
      expect(expected.values.join(" ")).not.toContain("PLANTED_RAW_TEST_DETAIL");
    }
  });

  it("maps all seven schedule source ids without backend labels", () => {
    const ids = [
      "polygon_news",
      "finnhub_news",
      "ibkr_news",
      "ibkr_prices",
      "iv_history",
      "local_incremental",
      "price_backfill",
    ];
    const cases = [
      {
        locale: "zh-Hant" as const,
        labels: ["Polygon 新聞", "Finnhub 新聞", "IBKR 新聞", "IBKR 股價", "IV 歷史", "本地鏡像增量", "價格缺口補抓"],
      },
      {
        locale: "en" as const,
        labels: ["Polygon News", "Finnhub News", "IBKR News", "IBKR Prices", "IV History", "Local Mirror Incremental", "Price Gap Backfill"],
      },
    ];

    for (const expected of cases) {
      const t = settingsT(expected.locale);
      const copies = ids.map((id) => scheduleSourceCopy(id, t));
      expect(copies.map(({ label }) => label)).toEqual(expected.labels);
      expect(copies.every(({ description }) => description.length > 0)).toBe(true);
      expect(copies.map(({ description }) => description).join(" ")).not.toContain("PLANTED_BACKEND_LABEL");
    }
  });

  it("maps schedule history without matching an English reason substring", () => {
    const cases = [
      {
        locale: "zh-Hant" as const,
        compact: [
          "尚未執行",
          "執行中",
          "上次成功",
          "部分完成",
          "上次失敗",
          "上次已跳過",
          "上次狀態為 future_status",
        ],
        values: [
          "Polygon 新聞：尚未執行",
          "Polygon 新聞：執行中",
          "Polygon 新聞：上次成功",
          "Polygon 新聞：部分完成",
          "Polygon 新聞：上次失敗",
          "Polygon 新聞：上次已跳過",
          "Polygon 新聞：上次狀態為 future_status",
        ],
      },
      {
        locale: "en" as const,
        compact: [
          "Not run yet",
          "Running",
          "Last run succeeded",
          "Partially completed",
          "Last run failed",
          "Last run was skipped",
          "Last status was future_status",
        ],
        values: [
          "Polygon News: Not run yet",
          "Polygon News: Running",
          "Polygon News: Last run succeeded",
          "Polygon News: Partially completed",
          "Polygon News: Last run failed",
          "Polygon News: Last run was skipped",
          "Polygon News: Last status was future_status",
        ],
      },
    ];

    for (const expected of cases) {
      const t = settingsT(expected.locale);
      const results: Array<ScheduleRunResult | null> = [
        null,
        { source: "polygon_news", status: "running" },
        { source: "polygon_news", status: "succeeded" },
        { source: "polygon_news", status: "partial" },
        { source: "polygon_news", status: "failed" },
        {
          source: "polygon_news",
          status: "skipped",
          reason: "collector already running: PLANTED_REASON",
        },
        { source: "polygon_news", status: "future_status" },
      ];
      const values = results.map((result) => scheduleOutcomeCopy("polygon_news", result, t));
      const compact = [
        t(($) => $.dataSources.schedule.history.notRun),
        t(($) => $.dataSources.schedule.history.running),
        t(($) => $.dataSources.schedule.history.succeeded),
        t(($) => $.dataSources.schedule.history.partial),
        t(($) => $.dataSources.schedule.history.failed),
        t(($) => $.dataSources.schedule.history.skipped),
        t(($) => $.dataSources.schedule.history.unknown, { value: "future_status" }),
      ];
      expect(compact).toEqual(expected.compact);
      expect(compact.map((value) => t(($) => $.dataSources.schedule.history.withSource, {
        sourceId: scheduleSourceCopy("polygon_news", t).label,
        value,
      }))).toEqual(expected.values);
      expect(values).toEqual(expected.values);
      expect(values.join(" ")).not.toContain("already running");
      expect(values.join(" ")).not.toContain("PLANTED_REASON");
    }
  });

  it("maps durable body backlog counts in both locales", () => {
    const earliestNextRetryAt = "2026-07-21T03:04:05Z";
    const result: ScheduleRunResult = {
      source: "ibkr_news",
      status: "partial",
      collect: {
        body_backlog: {
          status: "ok",
          due_now: 12,
          never_attempted: 3,
          scheduled_later: 9,
          provider_not_entitled: 4,
          earliest_next_retry_at: earliestNextRetryAt,
        },
      },
    };
    const cases = [
      {
        locale: "zh-Hant" as const,
        presentation: {
          label: "內文佇列：12 篇目前可處理（其中 3 篇尚未嘗試） · 9 篇已排程稍後重試 · 4 篇來源目前未訂閱（標題已保留，開通後自動重試）",
          tone: "muted" as const,
          earliestNextRetryAt,
        },
        outcome: "IBKR 新聞：部分完成",
      },
      {
        locale: "en" as const,
        presentation: {
          label: "Body queue: 12 available now (3 not yet attempted) · 9 scheduled for a later retry · 4 unavailable under the current subscription (titles retained; retries resume automatically when access is enabled)",
          tone: "muted" as const,
          earliestNextRetryAt,
        },
        outcome: "IBKR News: Partially completed",
      },
    ];

    for (const expected of cases) {
      const t = settingsT(expected.locale);
      expect(scheduleBodyBacklogCopy(result, t)).toEqual(expected.presentation);
      expect(scheduleOutcomeCopy("ibkr_news", result, t)).toBe(expected.outcome);
    }
  });

  it("maps market coverage states without changing formatter values", () => {
    const cases = [
      {
        locale: "zh-Hant" as const,
        values: ["週末", "假日（休市日）", "盤中（未收盤）", "缺資料", "疑似不足（最多 1,234 根）", "部分覆蓋（12/20 檔完整）", "覆蓋完整"],
      },
      {
        locale: "en" as const,
        values: ["Weekend", "Holiday (Market holiday)", "In progress", "Missing data", "Possibly thin (up to 1,234 bars)", "Partial coverage (12/20 complete)", "Complete coverage"],
      },
    ];

    for (const expected of cases) {
      const t = settingsT(expected.locale);
      const values = [
        t(($) => $.dataStorage.coverage.status.weekend),
        t(($) => $.dataStorage.coverage.status.holiday, { value: expected.locale === "en" ? "Market holiday" : "休市日" }),
        t(($) => $.dataStorage.coverage.status.inProgress),
        t(($) => $.dataStorage.coverage.status.missing),
        t(($) => $.dataStorage.coverage.status.thin, { value: "1,234" }),
        t(($) => $.dataStorage.coverage.status.partial, { count: 12, value: 20 }),
        t(($) => $.dataStorage.coverage.status.completeLike),
      ];
      expect(values).toEqual(expected.values);
    }
  });

  it("maps every SA Extension segment key", () => {
    const keys = [
      "config", "manifests", "launcher", "host_ping", "telemetry_binding", "telemetry_last", "capture_readback",
    ];
    const cases = [
      { locale: "zh-Hant" as const, labels: ["設定檔", "瀏覽器註冊", "啟動器", "主機測試", "遙測綁定", "最近遙測", "資料回讀"] },
      { locale: "en" as const, labels: ["Configuration", "Browser registration", "Launcher", "Host ping", "Telemetry binding", "Latest telemetry", "Capture readback"] },
    ];

    for (const expected of cases) {
      const t = settingsT(expected.locale);
      expect(keys.map((key) => saSegmentLabel(key, t))).toEqual(expected.labels);
    }
  });

  it("localizes known and unknown ApiError outcomes", () => {
    const reasonIds = [
      "missing_active_credential",
      "task_auth_mode_unsupported",
      "task_test_unsupported",
      "task_capability_missing",
      "model_not_visible",
      "model_not_in_registry",
      "discovery_unavailable",
      "provider_call_failed",
      "reauth_required",
    ];
    const cases = [
      {
        locale: "zh-Hant" as const,
        known: "Provider 設定不完整。",
        invalidProfile: "投資人設定內容無效。",
        unknown: "要求失敗（代碼：future_error）。",
        generic: "要求失敗，請稍後再試。",
        reasons: [
          "尚未設定此 provider 的登入",
          "此登入方式不支援這個任務",
          "此登入方式尚不支援實際測試",
          "缺少任務能力",
          "此登入的探索清單未顯示此模型",
          "自訂／未知模型，尚未驗證能力",
          "暫時無法讀取模型探索狀態",
          "provider 實際呼叫失敗",
          "登入已失效，請重新登入",
        ],
      },
      {
        locale: "en" as const,
        known: "Provider configuration is incomplete.",
        invalidProfile: "The Investor Profile is invalid.",
        unknown: "Request failed (code: future_error).",
        generic: "The request failed. Try again later.",
        reasons: [
          "No sign-in is configured for this provider",
          "This sign-in method does not support the task",
          "This sign-in method does not yet support live testing",
          "Task capability is missing",
          "This model does not appear in the discovery list for this sign-in",
          "Custom or unknown model; capabilities are unverified",
          "Model discovery status is temporarily unavailable",
          "The live provider call failed",
          "The sign-in has expired. Sign in again",
        ],
      },
    ];

    for (const expected of cases) {
      const t = settingsT(expected.locale);
      expect(settingsErrorPresentation(
        new ApiError("raw", "/providers/config", 409, "provider_config_missing", "RAW_MISSING"),
        t,
      ).message).toBe(expected.known);
      expect(settingsErrorPresentation(
        new ApiError("raw", "/investor-profile", 422, "invalid_investor_profile", "RAW_PROFILE"),
        t,
      ).message).toBe(expected.invalidProfile);
      expect(settingsErrorPresentation(
        new ApiError("raw", "/future", 500, "future_error", "RAW_FUTURE"),
        t,
      ).message).toBe(expected.unknown);
      expect(settingsErrorPresentation(new Error("network exploded"), t).message).toBe(expected.generic);
      expect(reasonIds.map((id) => modelReasonLabel(id, t))).toEqual(expected.reasons);
      expect(reasonIds.map((code) => settingsErrorPresentation(
        new ApiError("raw", "/models", 409, code, `RAW_${code}`),
        t,
      ).message)).toEqual(expected.reasons);
    }
  });

  it("hides planted diagnostics in normal mode and returns them for Developer Mode", () => {
    const planted = "PLANTED_DIAGNOSTIC: token exchange failed";
    expect(diagnosticValue(false, planted)).toBeNull();
    expect(diagnosticValue(true, planted)).toBe(planted);
    expect(diagnosticValue(true, "   ")).toBeNull();
    expect(diagnosticValue(true, null)).toBeNull();
  });

  it("keeps unknown provider source and error identifiers stable", () => {
    for (const locale of ["zh-Hant", "en"] as const) {
      const t = settingsT(locale);
      expect(providerName("future_provider", t)).toBe("future_provider");
      expect(providerConfigFieldLabel("future_provider", "future_field", t))
        .toBe("future_provider.future_field");
      expect(providerClientDomainLabel("future_domain", t)).toBe("future_domain");
      expect(saSegmentLabel("future_segment", t)).toBe("future_segment");
      expect(modelReasonLabel("future_model_reason", t)).toBe("future_model_reason");
      const source = scheduleSourceCopy("future_source", t);
      expect(source.label).toBe("future_source");
      expect(source.description).toContain("future_source");
      const error = settingsErrorPresentation(
        new ApiError("raw", "/future", 500, "future_error", "future diagnostic"),
        t,
      );
      expect(error.code).toBe("future_error");
      expect(error.message).toContain("future_error");
    }
  });
});
