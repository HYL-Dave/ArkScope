/** @vitest-environment jsdom */
import React from "react";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
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

const stylesCss = readFileSync(resolve(dirname(fileURLToPath(import.meta.url)), "../styles.css"), "utf8");

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
  admission_counts: { admitted: 2, needs_review: 1, pending: 6, screened_out: 3 },
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
    getPriceRepairOperations: vi.fn(async () => ({ version: 1, operations: [], total: 0, offset: 0, has_more: false })),
    getSchedule: vi.fn(async () => ({ sources: { ibkr_prices: { running: false } } })),
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
      controls.automationStatus = controls.automationStatus
        ? { ...controls.automationStatus, config_status: "valid", config }
        : status({ config });
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
  getTradingDayCoverage,
  listSecurityLifecycleCases,
  runDueSecurityLifecycleAutomation,
  updateSecurityLifecycleAutomationConfig,
} from "../api";
import { DataStorageSection } from "./DataStorageSection";

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

async function flush() {
  await act(async () => {
    for (let pending = 0; pending < 6; pending += 1) {
      await Promise.resolve();
    }
  });
}

async function renderSection(
  language: "en" | "zh-Hant" = "zh-Hant",
  onNavigateTarget = vi.fn(),
) {
  await i18n.changeLanguage(language);
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(
      <DataStorageSection
        settingsReadCache={createSettingsReadCache()}
        onNavigateTarget={onNavigateTarget}
      />,
    );
  });
  await flush();
}

async function changeMode(value: string, label = "Automation mode") {
  await act(async () => {
    const input = modeGroup(label).querySelector<HTMLInputElement>(`input[value="${value}"]`);
    expect(input).not.toBeNull();
    input!.click();
  });
}

function modeGroup(label = "Automation mode"): HTMLElement {
  const group = host!.querySelector<HTMLElement>(`[role="radiogroup"][aria-label="${label}"]`);
  expect(group).not.toBeNull();
  return group!;
}

function selectedMode(label = "Automation mode") {
  return modeGroup(label).querySelector<HTMLInputElement>('input[type="radio"]:checked')?.value;
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

function lifecyclePanel(): HTMLElement {
  return host!.querySelector<HTMLElement>('[data-settings-location="security_lifecycle"]')!;
}

function lifecycleWriteControls() {
  return Array.from(lifecyclePanel().querySelectorAll<
    HTMLInputElement | HTMLSelectElement | HTMLButtonElement
  >(
    '[data-testid="lifecycle-automation-controls"] input, '
    + '[data-testid="lifecycle-automation-controls"] select, '
    + '[data-testid="lifecycle-automation-controls"] button, '
    + '.lifecycle-automation-run',
  ));
}

async function expandAutomationSettings() {
  const details = lifecyclePanel().querySelector<HTMLDetailsElement>(
    ".lifecycle-automation-advanced",
  );
  expect(details).not.toBeNull();
  await act(async () => details!.querySelector("summary")!.click());
  expect(details!.open).toBe(true);
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
  it.each([
    { language: "en" as const, label: "Automation mode", apply: true },
    { language: "en" as const, label: "Automation mode", apply: false },
    { language: "zh-Hant" as const, label: "自動化模式", apply: true },
    { language: "zh-Hant" as const, label: "自動化模式", apply: false },
  ])("clicking checked Off in $language normalizes only a legacy apply=$apply conflict", async ({ language, label, apply }) => {
    controls.automationStatus = status({
      current_progress: [],
      config: { ...CONFIG, enabled: false, apply_profile_transitions: apply, batch_limit: 1 },
    });
    await renderSection(language);
    expect(selectedMode(label)).toBe("off");
    expect(updateSecurityLifecycleAutomationConfig).not.toHaveBeenCalled();
    const off = modeGroup(label).querySelector<HTMLInputElement>('input[value="off"]')!;
    const offLabel = off.labels![0].querySelector<HTMLElement>("span")!;

    // Click the visible label so native activation reaches the already-checked radio.
    await act(async () => offLabel.click());
    await flush();

    const writes = apply ? 1 : 0;
    expect(updateSecurityLifecycleAutomationConfig).toHaveBeenCalledTimes(writes);
    if (apply) {
      expect(updateSecurityLifecycleAutomationConfig).toHaveBeenCalledExactlyOnceWith({
        ...CONFIG, enabled: false, apply_profile_transitions: false, batch_limit: 1,
      });
    }
    expect(selectedMode(label)).toBe("off");
    expect(lifecyclePanel().querySelector('[data-automation-state="legacy_conflict"]')).toBeNull();

    await act(async () => offLabel.click());
    await flush();
    expect(updateSecurityLifecycleAutomationConfig).toHaveBeenCalledTimes(writes);

    for (const [index, mode] of ["check_only", "automatic", "off"].entries()) {
      await changeMode(mode, label);
      await flush();
      expect(updateSecurityLifecycleAutomationConfig).toHaveBeenCalledTimes(writes + index + 1);
      expect(updateSecurityLifecycleAutomationConfig).toHaveBeenLastCalledWith({
        ...CONFIG, enabled: mode !== "off", apply_profile_transitions: mode === "automatic", batch_limit: 1,
      });
    }
    expect(runDueSecurityLifecycleAutomation).not.toHaveBeenCalled();
  });

  it.each(["en", "zh-Hant"] as const)("keeps equal bounded mode tracks and wrapping labels in %s", async (language) => {
    controls.automationStatus = status({ current_progress: [] });
    const style = document.createElement("style");
    style.textContent = stylesCss;
    document.head.append(style);
    try {
      await renderSection(language);
      const tracks = lifecyclePanel().querySelector<HTMLElement>(".lifecycle-automation-modes");
      expect(tracks).not.toBeNull();
      for (const width of [280, 560]) {
        host!.style.width = `${width}px`;
        expect(getComputedStyle(tracks!).gridTemplateColumns).toBe("repeat(3, minmax(0, 1fr))");
        expect(getComputedStyle(tracks!).minWidth).toBe("0px");
        expect(getComputedStyle(tracks!).maxWidth).toBe("560px");
        for (const label of tracks!.querySelectorAll("label")) {
          expect(getComputedStyle(label).minWidth).toBe("0px");
          const copy = label.querySelector("span")!;
          expect(getComputedStyle(copy).whiteSpace).toBe("normal");
          expect(getComputedStyle(copy).overflowWrap).toBe("anywhere");
        }
      }
    } finally {
      style.remove();
    }
  });

  it.each([
    { language: "en" as const, label: "Automation mode", labels: ["Off", "Check only", "Automatic (verified delistings only)"], interval: "Check interval" },
    { language: "zh-Hant" as const, label: "自動化模式", labels: ["關閉", "僅檢查", "自動（僅限已驗證下市）"], interval: "檢查間隔" },
  ])("offers mutually exclusive native mode radios in $language and retains the interval select", async ({ language, label, labels, interval }) => {
    controls.automationStatus = status({ current_progress: [] });
    await renderSection(language);
    const group = modeGroup(label);
    const radios = Array.from(group.querySelectorAll<HTMLInputElement>('input[type="radio"]'));
    expect(radios).toHaveLength(3);
    expect(new Set(radios.map((radio) => radio.name)).size).toBe(1);
    expect(radios[0].name).not.toBe("");
    expect(radios.map((radio) => radio.labels?.[0]?.textContent)).toEqual(labels);
    expect(radios.filter((radio) => radio.checked).map((radio) => radio.value)).toEqual(["check_only"]);
    expect(host!.querySelector(`select[aria-label="${label}"]`)).toBeNull();
    await changeMode("automatic", label);
    await flush();
    expect(radios.filter((radio) => radio.checked).map((radio) => radio.value)).toEqual(["automatic"]);
    expect(updateSecurityLifecycleAutomationConfig).toHaveBeenCalledExactlyOnceWith({
      ...CONFIG, apply_profile_transitions: true,
    });
    await changeMode("automatic", label);
    await flush();
    expect(updateSecurityLifecycleAutomationConfig).toHaveBeenCalledOnce();
    await expandAutomationSettings();
    expect(select(interval).value).toBe("30");
  });

  it.each([
    { enabled: false, apply: false, mode: "off" },
    { enabled: true, apply: false, mode: "check_only" },
    { enabled: true, apply: true, mode: "automatic" },
    { enabled: false, apply: true, mode: "off" },
  ])("projects legacy $enabled/$apply without writing or escalating", async ({ enabled, apply, mode }) => {
    controls.automationStatus = status({
      current_progress: [],
      config: { ...CONFIG, enabled, apply_profile_transitions: apply, batch_limit: 1 },
    });
    await renderSection("en");
    expect(selectedMode()).toBe(mode);
    expect(Array.from(modeGroup().querySelectorAll<HTMLInputElement>('input[type="radio"]')).map((option) => option.value))
      .toEqual(["off", "check_only", "automatic"]);
    expect(updateSecurityLifecycleAutomationConfig).not.toHaveBeenCalled();
    const warning = lifecyclePanel().querySelector('[data-automation-state="legacy_conflict"]');
    if (!enabled && apply) {
      expect(warning?.textContent).toContain("Automatic changes are blocked");
      expect(warning?.closest("details")).toBeNull();
    } else {
      expect(warning).toBeNull();
    }
    for (const [next, nextEnabled, nextApply] of [
      ["automatic", true, true],
      ["check_only", true, false],
      ["off", false, false],
    ] as const) {
      const alreadySelected = selectedMode() === next;
      await changeMode(next);
      await flush();
      if (!alreadySelected) {
        expect(updateSecurityLifecycleAutomationConfig).toHaveBeenLastCalledWith({
          enabled: nextEnabled, apply_profile_transitions: nextApply,
          interval_minutes: 30, batch_limit: 1,
        });
      }
      expect(selectedMode()).toBe(next);
      expect(lifecyclePanel().querySelector('[data-automation-state="legacy_conflict"]')).toBeNull();
    }
    expect(runDueSecurityLifecycleAutomation).not.toHaveBeenCalled();
  });

  it("preserves an unusual interval and conflicting legacy flags on interval-only edits", async () => {
    controls.automationStatus = status({
      current_progress: [],
      config: { enabled: false, apply_profile_transitions: true, interval_minutes: 17, batch_limit: 1 },
    });
    await renderSection("en");
    await expandAutomationSettings();
    expect(select("Check interval").value).toBe("17");
    await act(async () => {
      const interval = select("Check interval");
      interval.value = "60";
      interval.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await flush();
    expect(updateSecurityLifecycleAutomationConfig).toHaveBeenLastCalledWith({
      enabled: false, apply_profile_transitions: true, interval_minutes: 60, batch_limit: 1,
    });
    expect(lifecyclePanel().querySelector('[data-automation-state="legacy_conflict"]')).not.toBeNull();
  });

  it("opens the fifteen-day coverage window and preserves an explicit longer choice", async () => {
    await renderSection("en");
    expect(getTradingDayCoverage).toHaveBeenCalledWith(15, "15min");
    const window = Array.from(host!.querySelectorAll<HTMLSelectElement>("select"))
      .find((item) => Array.from(item.options).map((option) => option.value).join(",") === "10,15,30,60");
    expect(window?.value).toBe("15");
    await act(async () => { window!.value = "30"; window!.dispatchEvent(new Event("change", { bubbles: true })); });
    await flush();
    expect(getTradingDayCoverage).toHaveBeenLastCalledWith(30, "15min");
  });

  it.each([
    { enabled: true, scheduleStatus: "due" as const },
    { enabled: false, scheduleStatus: "disabled" as const },
  ])("separates a $scheduleStatus schedule from an absent first result", async ({ enabled, scheduleStatus }) => {
    controls.automationStatus = status({
      config: { ...CONFIG, enabled },
      current_progress: [],
      telemetry_status: "absent",
      last_status: null,
      last_result: null,
      schedule: {
        status: scheduleStatus,
        last_attempt_at: null,
        next_scheduled_at: enabled ? "2026-08-31T05:25:00Z" : null,
      },
    });

    await renderSection("en");

    expect(lifecyclePanel().textContent?.match(/No completed run yet/g)).toHaveLength(1);
    expect(lifecyclePanel().querySelector(`[data-automation-schedule="${scheduleStatus}"]`))
      .not.toBeNull();
    expect(selectedMode()).toBe(enabled ? "check_only" : "off");
    expect(button("Run due cases now").disabled).toBe(false);
    expect(updateSecurityLifecycleAutomationConfig).not.toHaveBeenCalled();
    expect(runDueSecurityLifecycleAutomation).not.toHaveBeenCalled();
  });

  it("keeps a completed run separate from the enabled schedule", async () => {
    controls.automationStatus = status({ current_progress: [] });

    await renderSection("en");

    const schedule = lifecyclePanel().querySelector('[data-automation-schedule="scheduled"]');
    expect(schedule).not.toBeNull();
    expect(schedule!.textContent).not.toContain("Completed");
    expect(lifecyclePanel().textContent).toContain("1 processed");
    expect(lifecyclePanel().textContent).toContain("1 accepted");
  });

  it("shows invalid schedule health without changing enabled config or write admission", async () => {
    controls.automationStatus = status({
      current_progress: [],
      schedule: { status: "invalid", last_attempt_at: null, next_scheduled_at: null },
    });

    await renderSection("en");

    expect(lifecyclePanel().querySelector('[data-automation-schedule="invalid"]')).not.toBeNull();
    expect(selectedMode()).toBe("check_only");
    expect(button("Run due cases now").disabled).toBe(false);
    expect(lifecyclePanel().textContent).toContain("1 processed");
  });

  it("keeps advanced controls collapsed without changing their persisted values", async () => {
    controls.automationStatus = status({
      current_progress: [],
      config: { ...CONFIG, apply_profile_transitions: true },
    });

    await renderSection("en");

    const advanced = select("Check interval").closest("details");
    expect(advanced).not.toBeNull();
    expect(advanced!.open).toBe(false);
    expect(modeGroup().closest("details")).toBeNull();
    expect(lifecyclePanel().querySelector('input[type="checkbox"]')).toBeNull();
    expect(host!.querySelector('select[aria-label="Cases per batch"]')).toBeNull();
    expect(button("Run due cases now").closest("details")).toBeNull();

    await expandAutomationSettings();

    expect(select("Check interval").value).toBe("30");
    expect(selectedMode()).toBe("automatic");
    expect(updateSecurityLifecycleAutomationConfig).not.toHaveBeenCalled();
    expect(runDueSecurityLifecycleAutomation).not.toHaveBeenCalled();
  });

  it("keeps raw observation counts in non-actionable diagnostics below the controls", async () => {
    await renderSection("en");

    const observedLabel = Array.from(lifecyclePanel().querySelectorAll("dt"))
      .find((item) => item.textContent === "Cases with source observations");
    const diagnostics = observedLabel?.closest("details");
    expect(diagnostics).not.toBeNull();
    expect(diagnostics).toBeDefined();
    expect(diagnostics!.open).toBe(false);
    expect(observedLabel!.nextElementSibling?.textContent).toBe("9");
    expect(diagnostics!.textContent).toContain("Cases missing source observations");
    expect(diagnostics!.querySelector("button, a, input")).toBeNull();
    expect(button("Run due cases now").compareDocumentPosition(diagnostics!))
      .toBe(Node.DOCUMENT_POSITION_FOLLOWING);
  });

  it("keeps compact navigation and refresh available without dispatching automation", async () => {
    const onNavigateTarget = vi.fn();
    await renderSection("en", onNavigateTarget);

    const navigate = button("Open investigation in Universe");
    const refresh = lifecyclePanel().querySelector<HTMLButtonElement>('button[aria-label="Reload status"]');
    expect(refresh).not.toBeNull();
    expect(navigate.classList.contains("ui-button-primary")).toBe(true);
    expect(navigate.closest("details")).toBeNull();
    for (const command of [navigate, refresh!, button("Run due cases now")]) {
      expect(command.classList.contains("ui-button-compact")).toBe(true);
      expect(command.querySelector("svg")).not.toBeNull();
    }
    expect(button("Run due cases now").disabled).toBe(true);
    expect(navigate.disabled).toBe(false);
    expect(refresh!.disabled).toBe(false);

    await act(async () => navigate.click());
    expect(onNavigateTarget).toHaveBeenCalledExactlyOnceWith({ kind: "universe_lifecycle" });
    await act(async () => refresh!.click());
    await flush();

    expect(listSecurityLifecycleCases).toHaveBeenCalledTimes(2);
    expect(listSecurityLifecycleCases).toHaveBeenLastCalledWith({ limit: 1 });
    expect(getSecurityLifecycleAutomationStatus).toHaveBeenCalledTimes(2);
    expect(updateSecurityLifecycleAutomationConfig).not.toHaveBeenCalled();
    expect(runDueSecurityLifecycleAutomation).not.toHaveBeenCalled();
  });

  it("does not hide scheduler incidents, case incidents, running, or invalid telemetry when scheduling is disabled", async () => {
    controls.automationStatus = status({
      config: { ...CONFIG, enabled: false },
      schedule: { status: "disabled", last_attempt_at: null, next_scheduled_at: null },
      telemetry_status: "invalid",
      active_incident: {
        scheduler_failure: { reason: "automation_scheduler_failed" },
        case_failures: { slc_case_2: { run_id: "slar_failed", recovery: "new_attempt" } },
      },
    });

    await renderSection("en");

    expect(lifecyclePanel().querySelector('[data-automation-schedule="disabled"]')).not.toBeNull();
    for (const message of [
      "Scheduler failure remains unresolved",
      "1 execution failure remains unresolved",
      "Running",
      "Status unavailable",
    ]) {
      const notice = Array.from(lifecyclePanel().querySelectorAll("[data-automation-state]"))
        .find((element) => element.textContent === message);
      expect(notice, message).toBeDefined();
      expect(notice!.closest("details"), message).toBeNull();
    }
    expect(lifecyclePanel().textContent).toContain("Listing directories");
    expect(lifecycleWriteControls().length).toBeGreaterThan(0);
    expect(lifecycleWriteControls().every((control) => control.disabled)).toBe(true);
  });

  it.each([
    { lastStatus: "failed" as const, label: "Failed" },
    { lastStatus: "unavailable" as const, label: "Unavailable" },
    { lastStatus: "not_installed" as const, label: "Not installed" },
  ])("keeps a $lastStatus last attempt visible when scheduling is disabled", async ({ lastStatus, label }) => {
    controls.automationStatus = status({
      config: { ...CONFIG, enabled: false },
      schedule: { status: "disabled", last_attempt_at: null, next_scheduled_at: null },
      current_progress: [],
      last_status: lastStatus,
    });

    await renderSection("en");

    expect(lifecyclePanel().querySelector('[data-automation-schedule="disabled"]')).not.toBeNull();
    const notice = lifecyclePanel().querySelector(`[data-automation-state="${lastStatus}"]`);
    expect(notice?.textContent).toBe(label);
    expect(notice?.closest("details")).toBeNull();
    expect(button("Run due cases now").disabled).toBe(false);
  });

  it("reloads the complete schedule after each config save", async () => {
    controls.automationStatus = status({ current_progress: [] });
    vi.mocked(updateSecurityLifecycleAutomationConfig).mockImplementationOnce(async (config) => {
      controls.automationStatus = status({
        config,
        current_progress: [],
        schedule: {
          status: "disabled",
          last_attempt_at: "2026-08-31T04:55:00Z",
          next_scheduled_at: null,
        },
      });
      return { config_status: "valid" as const, config };
    });
    await renderSection();

    await changeMode("off", "自動化模式");
    await flush();

    expect(updateSecurityLifecycleAutomationConfig).toHaveBeenCalledOnce();
    expect(getSecurityLifecycleAutomationStatus).toHaveBeenCalledTimes(2);
    expect(host!.textContent).toContain("未排程");
    expect(lifecyclePanel().querySelector('[data-automation-schedule="disabled"]')).not.toBeNull();
  });

  it("shows real progress and sends complete config from each control shape", async () => {
    vi.useFakeTimers();
    await renderSection();

    expect(host!.textContent).toContain("目前階段");
    expect(host!.textContent).toContain("上市名錄");
    expect(lifecyclePanel().textContent).not.toContain("SEC · Nasdaq / Massive · IBKR（必要時）");
    expect(host!.textContent).toContain("2026-08-31");

    controls.automationStatus = status({ current_progress: [] });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1_000);
    });

    await changeMode("off", "自動化模式");
    await flush();
    expect(updateSecurityLifecycleAutomationConfig).toHaveBeenLastCalledWith({
      ...CONFIG,
      enabled: false,
    });

    await expandAutomationSettings();
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

    await changeMode("automatic", "自動化模式");
    await flush();
    expect(updateSecurityLifecycleAutomationConfig).toHaveBeenLastCalledWith({
      enabled: true,
      interval_minutes: 60,
      batch_limit: 2,
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

  it("keeps every write gated while config is saving and admits the next manual run after it settles", async () => {
    controls.automationStatus = status({ current_progress: [] });
    let finishSave!: (value: { config_status: "valid"; config: SecurityLifecycleAutomationConfig }) => void;
    vi.mocked(updateSecurityLifecycleAutomationConfig).mockImplementationOnce(() => new Promise((resolve) => {
      finishSave = resolve;
    }));
    await renderSection("en");
    await expandAutomationSettings();

    await changeMode("off");

    expect(lifecycleWriteControls()).toHaveLength(5);
    expect(lifecycleWriteControls().every((control) => control.disabled)).toBe(true);
    expect(button("Open investigation in Universe").disabled).toBe(false);
    await act(async () => button("Run due cases now").click());
    expect(runDueSecurityLifecycleAutomation).not.toHaveBeenCalled();
    expect(updateSecurityLifecycleAutomationConfig).toHaveBeenCalledExactlyOnceWith({
      ...CONFIG,
      enabled: false,
    });

    controls.automationStatus = status({
      current_progress: [],
      config: { ...CONFIG, enabled: false },
      schedule: { status: "disabled", last_attempt_at: null, next_scheduled_at: null },
    });
    await act(async () => finishSave({
      config_status: "valid",
      config: { ...CONFIG, enabled: false },
    }));
    await flush();

    expect(lifecycleWriteControls().every((control) => !control.disabled)).toBe(true);
    expect(selectedMode()).toBe("off");
    await act(async () => button("Run due cases now").click());
    await flush();
    expect(runDueSecurityLifecycleAutomation).toHaveBeenCalledOnce();
  });

  it("continues polling a running attempt when scheduling is disabled", async () => {
    vi.useFakeTimers();
    controls.automationStatus = status({
      config: { ...CONFIG, enabled: false },
      schedule: { status: "disabled", last_attempt_at: null, next_scheduled_at: null },
      current_progress: [],
      last_status: "running",
    });
    await renderSection("en");

    expect(selectedMode()).toBe("off");
    expect(button("Run due cases now").disabled).toBe(true);
    await act(async () => { await vi.advanceTimersByTimeAsync(1_000); });
    expect(getSecurityLifecycleAutomationStatus).toHaveBeenCalledTimes(2);

    controls.automationStatus = { ...controls.automationStatus!, last_status: "succeeded" };
    await act(async () => { await vi.advanceTimersByTimeAsync(1_000); });

    expect(getSecurityLifecycleAutomationStatus).toHaveBeenCalledTimes(3);
    expect(lifecyclePanel().querySelector('[data-automation-state="running"]')).toBeNull();
    expect(button("Run due cases now").disabled).toBe(false);
    expect(updateSecurityLifecycleAutomationConfig).not.toHaveBeenCalled();
    expect(runDueSecurityLifecycleAutomation).not.toHaveBeenCalled();
    await act(async () => { await vi.advanceTimersByTimeAsync(2_000); });
    expect(getSecurityLifecycleAutomationStatus).toHaveBeenCalledTimes(3);
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
    expect(lifecycleWriteControls().length).toBeGreaterThan(0);
    expect(lifecycleWriteControls().every((control) => control.disabled)).toBe(true);

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

  it("keeps durable running visible alongside invalid telemetry", async () => {
    controls.automationStatus = status({
      telemetry_status: "invalid",
      last_status: "running",
      current_progress: [],
    });

    await renderSection("en");

    expect(host!.querySelector('[data-automation-state="running"]')?.textContent)
      .toBe("Running");
    expect(host!.querySelector('[data-automation-state="invalid"]')?.textContent)
      .toBe("Status unavailable");
    expect(button("Run due cases now").disabled).toBe(true);
  });

  it.each([false, true])("disables all write controls for invalid config with running=$0", async (running) => {
    controls.automationStatus = {
      ...status({ current_progress: [], last_status: running ? "running" : "succeeded" }),
      config_status: "invalid",
      config: null,
      invalid_keys: ["security_lifecycle.automation.batch_limit"],
      schedule: { status: "invalid", last_attempt_at: null, next_scheduled_at: null },
    };

    await renderSection();

    expect(host!.textContent).toContain("自動化設定需要修正");
    expect(lifecycleWriteControls().length).toBeGreaterThan(0);
    expect(lifecycleWriteControls().every((control) => control.disabled)).toBe(true);
    expect(lifecyclePanel().querySelector('input[type="checkbox"]')).toBeNull();
    await act(async () => button("立即檢查到期案件").click());
    expect(updateSecurityLifecycleAutomationConfig).not.toHaveBeenCalled();
    expect(runDueSecurityLifecycleAutomation).not.toHaveBeenCalled();
  });

  it("renders the same control authority in English", async () => {
    controls.automationStatus = status({ current_progress: [] });

    await renderSection("en");

    expect(host!.textContent).toContain("Automation mode");
    expect(host!.textContent).toContain("Run due cases now");
    expect(host!.textContent).toContain("Automatic (verified delistings only)");
    expect(lifecyclePanel().textContent).not.toContain("SEC · Nasdaq / Massive · IBKR when needed");
  });
});
