/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import i18n from "i18next";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  MarketDataStatus,
  SecurityLifecycleAutomationConfig,
  SecurityLifecycleAutomationStatusResponse,
  SecurityLifecycleCaseListResponse,
  TradingDayCoverage,
} from "../api";
import { createSettingsReadCache } from "./settingsReadCache";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

const controls = vi.hoisted(() => ({
  automationStatus: null as SecurityLifecycleAutomationStatusResponse | null,
  automationStatusError: null as Error | null,
}));

const EMPTY_MARKET_STATUS: MarketDataStatus = {
  market_db: "/tmp/market.db",
  exists: false,
  prices: { row_count: 0, ticker_count: 0, latest_datetime: null },
  news: { row_count: 0, source_count: 0, latest_published: null },
  fundamentals: { row_count: 0, ticker_count: 0, latest_date: null },
  financial_cache: {
    row_count: 0,
    valid_count: 0,
    expired_count: 0,
    latest_fetched_at: null,
  },
  sync: { prices: null, news: null, fundamentals: null },
  prices_authority: "local",
  fundamentals_mode: "local_cache_refetch",
  use_local_market_setting: true,
  env_override: false,
  local_market_strict_setting: false,
  strict_env_override: false,
  strict_enabled: false,
  routing_enabled: true,
};

const CASES: SecurityLifecycleCaseListResponse = {
  cases: [],
  count: 9,
  queue_counts: { attention: 2, monitoring: 5, history: 2 },
  data_integrity: { source_missing_count: 1 },
};

const COVERAGE: TradingDayCoverage = {
  version: 2,
  market_scope: "us_listed_equity_proxy",
  coverage_session: "rth",
  interval: "15min",
  lookback_days: 10,
  universe_count: 0,
  generated_at_et: "2026-08-31T01:00:00-04:00",
  calendar_health: {
    status: "ok",
    reason_codes: [],
    reviewed_through: "2026-08-31",
    forward_horizon_months: 12,
  },
  observation_health: { status: "ok", reason_code: null },
  days: [],
  provider_errors: [],
};

const CONFIG: SecurityLifecycleAutomationConfig = {
  enabled: true,
  interval_minutes: 30,
  batch_limit: 2,
  apply_profile_transitions: false,
};

function status(
  overrides: Partial<SecurityLifecycleAutomationStatusResponse> = {},
): SecurityLifecycleAutomationStatusResponse {
  return {
    config_status: "valid",
    config: CONFIG,
    schedule: {
      status: "scheduled",
      last_attempt_at: "2026-08-31T04:55:00Z",
      next_scheduled_at: "2026-08-31T05:25:00Z",
    },
    telemetry_status: "valid",
    last_status: "succeeded",
    last_result: {
      status: "succeeded",
      reason: null,
      selected: 1,
      processed: 1,
      accepted: 1,
      drafted: 0,
      blocked: 0,
      failed: 0,
      skipped_current: 0,
      case_ids: ["slc_case_1"],
      result_version: 2,
      case_outcomes: { slc_case_1: "accepted" },
    },
    active_incident: null,
    latest_failed_runs: [],
    current_progress: [{
      trigger: "scheduler",
      request_id: "slao_settings",
      case_id: "slc_case_2",
      started_at: "2026-08-31T05:00:00Z",
      current_stage: "listing",
      completed_stages: ["preparing", "sec"],
      skipped_stages: [],
    }],
    ...overrides,
  } as SecurityLifecycleAutomationStatusResponse;
}

vi.mock("../api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api")>();
  return {
    ...actual,
    getMarketDataStatus: vi.fn(async () => EMPTY_MARKET_STATUS),
    listSecurityLifecycleCases: vi.fn(async () => CASES),
    getTradingDayCoverage: vi.fn(async () => COVERAGE),
    getSecurityLifecycleAutomationStatus: vi.fn(async () => {
      if (controls.automationStatusError) {
        const error = controls.automationStatusError;
        controls.automationStatusError = null;
        throw error;
      }
      if (!controls.automationStatus) throw new Error("missing automation fixture");
      return controls.automationStatus;
    }),
    updateSecurityLifecycleAutomationConfig: vi.fn(async (
      config: SecurityLifecycleAutomationConfig,
    ) => {
      controls.automationStatus = status({ config });
      return { config_status: "valid" as const, config };
    }),
    runDueSecurityLifecycleAutomation: vi.fn(async () => ({
      scope: "due" as const,
      status: "started" as const,
      request_id: "slao_manual_due",
    })),
  };
});

import {
  getSecurityLifecycleAutomationStatus,
  runDueSecurityLifecycleAutomation,
  updateSecurityLifecycleAutomationConfig,
} from "../api";
import { DataStorageSection } from "./DataStorageSection";

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

async function flush() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

async function renderSection(language: "en" | "zh-Hant" = "zh-Hant") {
  await i18n.changeLanguage(language);
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(
      <DataStorageSection
        settingsReadCache={createSettingsReadCache()}
        onNavigateTarget={vi.fn()}
      />,
    );
  });
  await flush();
}

function checkbox(label: string): HTMLInputElement {
  const input = host!.querySelector<HTMLInputElement>(`input[aria-label="${label}"]`);
  if (!input) throw new Error(`missing checkbox: ${label}`);
  return input;
}

function select(label: string): HTMLSelectElement {
  const input = host!.querySelector<HTMLSelectElement>(`select[aria-label="${label}"]`);
  if (!input) throw new Error(`missing select: ${label}`);
  return input;
}

function button(label: string): HTMLButtonElement {
  const value = Array.from(host!.querySelectorAll<HTMLButtonElement>("button"))
    .find((candidate) => candidate.textContent?.includes(label));
  if (!value) throw new Error(`missing button: ${label}`);
  return value;
}

beforeEach(() => {
  vi.clearAllMocks();
  controls.automationStatus = status();
  controls.automationStatusError = null;
});

afterEach(() => {
  if (root) act(() => root!.unmount());
  root = null;
  host?.remove();
  host = null;
  document.body.replaceChildren();
  vi.useRealTimers();
});

describe("DataStorageSection lifecycle automation controls", () => {
  it("shows real progress and sends complete config from each control shape", async () => {
    vi.useFakeTimers();
    await renderSection();

    expect(host!.textContent).toContain("目前階段");
    expect(host!.textContent).toContain("上市名錄");
    expect(host!.textContent).toContain("SEC · Nasdaq / Massive · IBKR（必要時）");
    expect(host!.textContent).toContain("2026-08-31");

    controls.automationStatus = status({ current_progress: [] });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1_000);
    });

    await act(async () => checkbox("背景自動判定").click());
    await flush();
    expect(updateSecurityLifecycleAutomationConfig).toHaveBeenLastCalledWith({
      ...CONFIG,
      enabled: false,
    });

    const interval = select("檢查間隔");
    await act(async () => {
      interval.value = "60";
      interval.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await flush();
    expect(updateSecurityLifecycleAutomationConfig).toHaveBeenLastCalledWith({
      ...CONFIG,
      enabled: false,
      interval_minutes: 60,
    });

    await act(async () => button("每批 1 件").click());
    await flush();
    expect(updateSecurityLifecycleAutomationConfig).toHaveBeenLastCalledWith({
      ...CONFIG,
      enabled: false,
      interval_minutes: 60,
      batch_limit: 1,
    });

    await act(async () => checkbox("自動套用標的變更").click());
    await flush();
    expect(updateSecurityLifecycleAutomationConfig).toHaveBeenLastCalledWith({
      enabled: false,
      interval_minutes: 60,
      batch_limit: 1,
      apply_profile_transitions: true,
    });

    await act(async () => button("立即檢查到期案件").click());
    await flush();
    expect(runDueSecurityLifecycleAutomation).toHaveBeenCalledOnce();
  });

  it("prioritizes an active incident over a stale successful result", async () => {
    controls.automationStatus = status({
      current_progress: [],
      active_incident: {
        case_failures: {
          slc_case_2: { run_id: "slar_failed", recovery: "new_attempt" },
        },
        scheduler_failure: null,
      },
    });

    await renderSection();

    expect(host!.textContent).toContain("1 件執行失敗尚未恢復");
    expect(host!.querySelector('[data-automation-state="success"]')).toBeNull();
  });

  it("keeps write controls disabled while a started run has durable running status", async () => {
    controls.automationStatus = status({
      last_status: "succeeded",
      current_progress: [],
    });
    await renderSection();
    vi.useFakeTimers();
    controls.automationStatus = status({
      last_status: "running",
      current_progress: [],
    });

    await act(async () => button("立即檢查到期案件").click());
    await flush();

    expect(runDueSecurityLifecycleAutomation).toHaveBeenCalledOnce();
    expect(getSecurityLifecycleAutomationStatus).toHaveBeenCalledTimes(2);
    const runningControls = host!.querySelectorAll<HTMLElement>(
      '[data-testid="lifecycle-automation-controls"] input, '
      + '[data-testid="lifecycle-automation-controls"] select, '
      + '[data-testid="lifecycle-automation-controls"] button',
    );
    expect(Array.from(runningControls).every((control) => (
      (control as HTMLInputElement | HTMLSelectElement | HTMLButtonElement).disabled
    ))).toBe(true);

    controls.automationStatus = status({
      last_status: "succeeded",
      current_progress: [],
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1_000);
    });

    expect(getSecurityLifecycleAutomationStatus).toHaveBeenCalledTimes(3);
    expect(button("立即檢查到期案件").disabled).toBe(false);
  });

  it("continues polling a durable running status after one request fails", async () => {
    controls.automationStatus = status({
      last_status: "succeeded",
      current_progress: [],
    });
    await renderSection();
    vi.useFakeTimers();
    controls.automationStatus = status({
      last_status: "running",
      current_progress: [],
    });

    await act(async () => button("立即檢查到期案件").click());
    await flush();
    controls.automationStatusError = new Error("temporary status failure");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1_000);
    });
    expect(getSecurityLifecycleAutomationStatus).toHaveBeenCalledTimes(3);
    expect(button("立即檢查到期案件").disabled).toBe(true);

    controls.automationStatus = status({
      last_status: "succeeded",
      current_progress: [],
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1_000);
    });

    expect(getSecurityLifecycleAutomationStatus).toHaveBeenCalledTimes(4);
    expect(button("立即檢查到期案件").disabled).toBe(false);
  });

  it("shows durable running ahead of stale invalid telemetry", async () => {
    controls.automationStatus = status({
      telemetry_status: "invalid",
      last_status: "running",
      current_progress: [],
    });

    await renderSection("en");

    expect(host!.querySelector('[data-automation-state="running"]')?.textContent)
      .toBe("Running");
    expect(host!.querySelector('[data-automation-state="invalid"]')).toBeNull();
    expect(button("Run due cases now").disabled).toBe(true);
  });

  it("disables all write controls when stored automation config is invalid", async () => {
    controls.automationStatus = {
      ...status(),
      config_status: "invalid",
      config: null,
      invalid_keys: ["security_lifecycle.automation.batch_limit"],
      schedule: { status: "invalid", last_attempt_at: null, next_scheduled_at: null },
    };

    await renderSection();

    expect(host!.textContent).toContain("自動化設定需要修正");
    const writeControls = host!.querySelectorAll<HTMLElement>(
      '[data-testid="lifecycle-automation-controls"] input, '
      + '[data-testid="lifecycle-automation-controls"] select, '
      + '[data-testid="lifecycle-automation-controls"] button',
    );
    expect(writeControls.length).toBeGreaterThan(0);
    expect(Array.from(writeControls).every((control) => (
      (control as HTMLInputElement | HTMLSelectElement | HTMLButtonElement).disabled
    ))).toBe(true);
  });

  it("renders the same control authority in English", async () => {
    controls.automationStatus = status({ current_progress: [] });

    await renderSection("en");

    expect(host!.textContent).toContain("Background automation");
    expect(host!.textContent).toContain("Run due cases now");
    expect(host!.textContent).toContain("Apply security changes automatically");
    expect(host!.textContent).toContain("SEC · Nasdaq / Massive · IBKR when needed");
  });
});
