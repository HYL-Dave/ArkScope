/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  getProvidersConfig,
  getProvidersHealth,
  getSchedule,
  putProviderConfig,
  type ModelCatalog,
  type ModelTask,
  type ProvidersHealthResponse,
  type TaskRoute,
} from "./api";
import { formatSystemTimestamp } from "./timeDisplay";
import type { SettingsNavigationGuardReporter } from "./settings/settingsNavigationGuard";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

const mocked = vi.hoisted(() => ({
  providersConfig: {
    providers: {
      polygon: {
        fields: [{
          field: "api_key",
          label: "API key",
          secret: true,
          env_var: "POLYGON_API_KEY",
          app_value_set: false,
          app_value_masked: null,
          effective_source: "config/.env",
          needs_import: true,
          import_source: "POLYGON_API_KEY",
          importable_env_vars: ["POLYGON_API_KEY"],
          defaulted: false,
          guarded: false,
          guard_reason: null,
        }],
        testable: true,
        default_available: false,
      },
      ibkr: {
        fields: [
          {
            field: "host",
            label: "Gateway host",
            secret: false,
            env_var: "IBKR_HOST",
            app_value_set: true,
            app_value_masked: "192.168.0.153",
            effective_source: "app",
            needs_import: false,
            import_source: null,
            importable_env_vars: ["IBKR_HOST"],
            defaulted: false,
            guarded: false,
            guard_reason: null,
          },
          {
            field: "port",
            label: "Gateway port",
            secret: false,
            env_var: "IBKR_PORT",
            app_value_set: true,
            app_value_masked: "4001",
            effective_source: "app",
            needs_import: false,
            import_source: null,
            importable_env_vars: ["IBKR_PORT"],
            defaulted: false,
            guarded: false,
            guard_reason: null,
          },
          {
            field: "client_id",
            label: "Client ID",
            secret: false,
            env_var: "IBKR_CLIENT_ID",
            client_id_domains: [
              { domain: "manual", label: "基底", offset: 0, effective_id: 1 },
              { domain: "options", label: "選擇權", offset: 10, effective_id: 11 },
              { domain: "prices", label: "股價", offset: 20, effective_id: 21 },
              { domain: "news", label: "新聞", offset: 30, effective_id: 31 },
              { domain: "iv", label: "IV", offset: 40, effective_id: 41 },
            ],
            app_value_set: true,
            app_value_masked: "1",
            effective_source: "app",
            needs_import: false,
            import_source: null,
            importable_env_vars: ["IBKR_CLIENT_ID"],
            defaulted: true,
            guarded: true,
            guard_reason: "Changing IBKR client_id can disturb active Gateway sessions.",
          },
        ],
        testable: true,
        default_available: false,
      },
    },
    setup: { required: false, code: null, reason: null },
    env_fallback: { enabled: false, source: "default" },
  },
  longSkipReason:
    "scheduler lock refused because another collector process is still holding collect.polygon_news; " +
    "pid=42391 host=ais elapsed=1842s lock_path=/mnt/md0/PycharmProjects/ArkScope/data/locks/collect.polygon_news.lock",
  longDurableError:
    "IBKR historical data request failed after bounded retries: HMDS query returned no data for HAPN on 2026-06-05 " +
    "during afternoon recovery window; clientId=11 requestId=980123 pacing bucket=hist_15m",
  scheduleRunning: false,
  scheduleProgress: null as { done: number; total: number; current: string } | null,
  scheduleLastAttemptAt: "2026-07-14T10:00:00Z",
  scheduleUpdatedAt: "2026-07-14T10:01:00Z",
  ibkrBodyBacklogMode: "legacy" as "legacy" | "succeeded" | "partial" | "entitlement",
  importCalls: [] as Array<{ provider: string; field: string; sourceEnvVar?: string | null }>,
  putCalls: [] as Array<{ provider: string; fields: Record<string, string | null>; confirmGuarded?: Record<string, boolean> }>,
}));

const emptyCatalog: ModelCatalog = {
  providers: ["anthropic", "openai"],
  tasks: [],
  models: [],
  effort_options: { anthropic: [], openai: [] },
  routes: {} as Record<ModelTask, TaskRoute>,
  credentials: { anthropic: [], openai: [] },
  custom_allowed: true,
};

const health: ProvidersHealthResponse = {
  providers: [
    { id: "polygon", label: "Polygon", kind: "news", status: "not_configured", config_error: { code: "provider_config_missing", status: "not_configured", provider: "polygon", field: "api_key" }, enabled: true, key_present: true, key_source: "config/.env", key_vars: ["POLYGON_API_KEY"], last_success_at: null, last_attempt_at: null, last_error: null, detail: "", signals: {}, key_import_suggested: false },
    { id: "ibkr", label: "IBKR", kind: "market", status: "no_signal", enabled: true, key_present: true, key_source: "app", key_vars: ["IBKR_HOST", "IBKR_PORT"], last_success_at: null, last_attempt_at: null, last_error: "request_id=provider-health-check-000000000000000000000000000000000000000000000000000000000000000001", detail: "", signals: {}, key_import_suggested: false },
    {
      id: "fred",
      label: "FRED",
      kind: "macro",
      status: "connected",
      enabled: null,
      key_present: true,
      key_source: "app",
      key_vars: ["FRED_API_KEY"],
      last_success_at: "2026-06-25T01:09:52Z",
      last_attempt_at: null,
      last_error: null,
      detail: "local snapshot 29571 observations · 11 series · latest fetched 2026-06-25T01:09:52Z · auto-refresh off",
      signals: {
        auto_refresh_enabled: false,
        local_snapshot: {
          available: true,
          series_count: 11,
          observation_count: 29571,
          release_dates_count: 4659,
          latest_fetched_at: "2026-06-25T01:09:52Z",
        },
      },
      key_import_suggested: false,
    },
    {
      id: "retired_provider",
      label: "Retired provider",
      kind: "macro",
      status: "disabled",
      enabled: false,
      disabled_reason: "retired",
      key_present: true,
      key_source: "not_required",
      key_vars: [],
      last_success_at: null,
      last_attempt_at: null,
      last_error: null,
      detail: "",
      signals: {},
      key_import_suggested: false,
    },
  ],
  generated_at: "2026-07-02T00:00:00+00:00",
  jobs: {},
  local_market: { db_exists: true, sync: {} },
  notes: [],
};

vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return {
    ...actual,
    getModelCatalog: vi.fn(async () => emptyCatalog),
    getSchedule: vi.fn(async () => ({
      sources: {
        polygon_news: {
          label: "Polygon news",
          description: "Polygon market-news collector",
          ibkr: false,
          provider_fetch: true,
          source_mode: "direct_local",
          write_target: "market_data.db",
          source_badges: ["Polygon", "直寫本地"],
          retired: false,
          retired_reason: null,
          enabled: true,
          interval_minutes: 30,
          default_interval_minutes: 30,
          running: mocked.scheduleRunning,
          progress: mocked.scheduleProgress,
          last_attempt_at: "2026-07-04T00:00:00+00:00",
          last_result: {
            source: "polygon_news",
            status: "skipped",
            reason: mocked.longSkipReason,
            at: "2026-07-04T00:00:00+00:00",
          },
          gap_planned: false,
          durable_state: {
            last_status: "failed",
            last_error: mocked.longDurableError,
            continuation: null,
            last_attempt: "2026-07-04T00:00:00+00:00",
            updated_at: "2026-07-04T00:01:00+00:00",
          },
          job_name: "collect.polygon_news",
        },
        ibkr_news: {
          label: "IBKR 新聞",
          description: "IBKR market-news collector",
          ibkr: true,
          provider_fetch: true,
          source_mode: "direct_local",
          write_target: "market_data.db",
          source_badges: [],
          retired: false,
          retired_reason: null,
          enabled: true,
          interval_minutes: 120,
          default_interval_minutes: 120,
          running: false,
          progress: null,
          last_attempt_at: mocked.scheduleLastAttemptAt,
          last_result: mocked.ibkrBodyBacklogMode === "legacy" ? {
            source: "ibkr_news",
            status: "partial",
            at: "2026-07-14T10:01:00Z",
            collect: {
              status: "partial",
              continuation: {
                deferred_ticker_count: 0,
                deferred_body_count: 99,
                has_cursor: false,
              },
            },
          } : null,
          gap_planned: false,
          durable_state: mocked.ibkrBodyBacklogMode === "succeeded" || mocked.ibkrBodyBacklogMode === "entitlement" ? {
            last_status: "succeeded",
            last_error: null,
            continuation: null,
            last_result: {
              source: "ibkr_news",
              status: "succeeded",
              collect: {
                status: "succeeded",
                body_backlog: {
                  status: "ok",
                  due_now: 0,
                  scheduled_later: 2,
                  never_attempted: 0,
                  earliest_next_retry_at: "2026-07-15T06:00:00Z",
                  ...(mocked.ibkrBodyBacklogMode === "entitlement"
                    ? { provider_not_entitled: 78 }
                    : {}),
                },
              },
            },
            last_attempt: mocked.scheduleLastAttemptAt,
            updated_at: mocked.scheduleUpdatedAt,
          } : mocked.ibkrBodyBacklogMode === "partial" ? {
            last_status: "partial",
            last_error: null,
            continuation: null,
            last_result: {
              source: "ibkr_news",
              status: "partial",
              collect: {
                status: "partial",
                legs: { retry: "partial", fresh: "succeeded" },
                body_backlog: {
                  status: "ok",
                  due_now: 0,
                  scheduled_later: 1,
                  never_attempted: 0,
                  earliest_next_retry_at: "2026-07-15T07:00:00Z",
                },
              },
            },
            last_attempt: mocked.scheduleLastAttemptAt,
            updated_at: mocked.scheduleUpdatedAt,
          } : {
            last_status: "partial",
            last_error: null,
            continuation: null,
            last_result: {
              source: "ibkr_news",
              status: "partial",
              collect: {
                status: "partial",
                continuation: {
                  deferred_ticker_count: 0,
                  deferred_body_count: 10,
                  has_cursor: false,
                },
              },
            },
            last_attempt: mocked.scheduleLastAttemptAt,
            updated_at: mocked.scheduleUpdatedAt,
          },
          job_name: "collect.ibkr_news",
        },
        writer_lock_deferred: {
          label: "Writer lock deferred",
          description: "writer lock fixture",
          ibkr: false,
          provider_fetch: true,
          source_mode: "direct_local",
          write_target: "market_data.db",
          source_badges: [],
          retired: false,
          retired_reason: null,
          enabled: true,
          interval_minutes: 30,
          default_interval_minutes: 30,
          running: false,
          progress: null,
          last_attempt_at: "2026-07-04T00:00:00+00:00",
          last_result: null,
          gap_planned: false,
          durable_state: {
            last_status: "skipped",
            last_error: null,
            continuation: null,
            last_attempt: "2026-07-04T00:00:00+00:00",
            updated_at: "2026-07-04T00:01:00+00:00",
          },
          job_name: "collect.writer_lock_deferred",
        },
        price_backfill: {
          label: "價格缺口補抓",
          description: "IBKR/Polygon → market_data.db DIRECT (no PG)",
          ibkr: true,
          provider_fetch: false,
          source_mode: "direct_local",
          write_target: "market_data.db",
          source_badges: ["IBKR/Polygon", "直寫本地", "缺口補抓"],
          retired: false,
          retired_reason: null,
          enabled: false,
          interval_minutes: 360,
          default_interval_minutes: 360,
          running: false,
          progress: null,
          last_attempt_at: null,
          last_result: null,
          gap_planned: true,
          durable_state: null,
          job_name: "collect.price_backfill",
        },
      },
    })),
    getProvidersHealth: vi.fn(async () => health),
    getSAExtensionHealth: vi.fn(async () => ({
      ok: false,
      generated_at: "2026-07-12T00:00:00+00:00",
      segments: [{
        key: "capture_readback",
        state: "warn" as const,
        detail:
          "No capture has arrived from the browser extension for the selected account; " +
          "check the native-host binding and retry the extension health check.",
      }],
    })),
    getProvidersConfig: vi.fn(async () => mocked.providersConfig),
    importProviderConfigField: vi.fn(async (provider: string, field: string, sourceEnvVar?: string | null) => {
      mocked.importCalls.push({ provider, field, sourceEnvVar });
      return mocked.providersConfig.providers[provider as keyof typeof mocked.providersConfig.providers];
    }),
    putProviderConfig: vi.fn(async (provider: string, fields: Record<string, string | null>, confirmGuarded?: Record<string, boolean>) => {
      mocked.putCalls.push({ provider, fields, confirmGuarded });
      return mocked.providersConfig.providers[provider as keyof typeof mocked.providersConfig.providers];
    }),
    testProvider: vi.fn(),
  };
});

import { SettingsView } from "./Settings";
import { DataSourcesSection } from "./settings/DataSourcesSection";

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

afterEach(() => {
  if (root) {
    act(() => root!.unmount());
    root = null;
  }
  host?.remove();
  host = null;
  mocked.importCalls = [];
  mocked.putCalls = [];
  mocked.scheduleRunning = false;
  mocked.scheduleProgress = null;
  mocked.scheduleLastAttemptAt = "2026-07-14T10:00:00Z";
  mocked.scheduleUpdatedAt = "2026-07-14T10:01:00Z";
  mocked.ibkrBodyBacklogMode = "legacy";
  vi.useRealTimers();
  vi.restoreAllMocks();
});

async function renderDataSources(onNavigationGuardChange?: SettingsNavigationGuardReporter) {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(onNavigationGuardChange
      ? React.createElement(DataSourcesSection, { onNavigationGuardChange })
      : React.createElement(SettingsView, { runtime: null, onRuntimeChanged: vi.fn() }));
  });
  await act(async () => { await Promise.resolve(); });
  await act(async () => { await Promise.resolve(); });
}

function clearDataSourceReadMocks() {
  vi.mocked(getSchedule).mockClear();
  vi.mocked(getProvidersHealth).mockClear();
  vi.mocked(getProvidersConfig).mockClear();
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

async function waitForReport(
  callback: ReturnType<typeof vi.fn>,
  predicate: (report: { dirty: boolean; busy: boolean; reason: string | null }) => boolean,
) {
  for (let index = 0; index < 20; index += 1) {
    const report = callback.mock.calls.at(-1)?.[0];
    if (report && predicate(report)) return;
    await act(async () => { await Promise.resolve(); });
  }
  expect(predicate(callback.mock.calls.at(-1)?.[0])).toBe(true);
}

function setInputValue(el: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
  setter?.call(el, value);
  el.dispatchEvent(new Event("input", { bubbles: true }));
}

describe("Settings provider config authority", () => {
  it("renders config-file provenance with per-field import", async () => {
    await renderDataSources();
    expect(host!.textContent).toContain("來源標示會說明每個值");
    expect(host!.textContent).not.toContain("strict DB-first");
    expect(host!.textContent).toContain("config/.env");
    expect(host!.textContent).toContain("建議匯入");
    const polygonRow = Array.from(host!.querySelectorAll("tr")).find((row) =>
      row.textContent?.includes("Polygon") && row.textContent.includes("API key"));
    if (!polygonRow) throw new Error("missing polygon config row");
    const importButton = Array.from(polygonRow.querySelectorAll("button")).find((button) =>
      button.textContent?.includes("匯入"));
    if (!importButton) throw new Error("missing import button");
    await act(async () => {
      importButton.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    });
    expect(mocked.importCalls).toEqual([{ provider: "polygon", field: "api_key", sourceEnvVar: "POLYGON_API_KEY" }]);
  });

  it("confirms guarded IBKR client id edits", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    await renderDataSources();
    const input = Array.from(host!.querySelectorAll("input")).find((node) =>
      node.getAttribute("placeholder") === "Client ID") as HTMLInputElement | undefined;
    if (!input) throw new Error("missing client-id input");
    await act(async () => {
      setInputValue(input, "7");
    });
    const ibkrRow = input.closest("tr");
    if (!ibkrRow) throw new Error("missing ibkr config row");
    const saveButton = Array.from(ibkrRow.querySelectorAll("button")).find((button) =>
      button.textContent?.includes("儲存"));
    if (!saveButton) throw new Error("missing save button");
    await act(async () => {
      saveButton.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    });
    expect(mocked.putCalls).toHaveLength(0);
    const dialog = document.querySelector<HTMLElement>('[role="dialog"]');
    expect(dialog?.textContent).toContain("Changing IBKR client_id can disturb active Gateway sessions.");
    const confirmButton = Array.from(dialog?.querySelectorAll("button") ?? [])
      .find((button) => button.textContent?.trim() === "套用變更");
    if (!confirmButton) throw new Error("missing guarded-edit confirm button");
    await act(async () => {
      confirmButton.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    });
    expect(mocked.putCalls).toEqual([{
      provider: "ibkr",
      fields: { client_id: "7" },
      confirmGuarded: { client_id: true },
    }]);
  });

  it("cancels_a_guarded_provider_edit_without_mutation_and_restores_focus", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    await renderDataSources();
    const input = Array.from(host!.querySelectorAll("input")).find((node) =>
      node.getAttribute("placeholder") === "Client ID") as HTMLInputElement | undefined;
    if (!input) throw new Error("missing client-id input");
    await act(async () => {
      setInputValue(input, "7");
    });
    const row = input.closest("tr");
    const saveButton = Array.from(row?.querySelectorAll("button") ?? []).find((button) =>
      button.textContent?.includes("儲存")) as HTMLButtonElement | undefined;
    if (!saveButton) throw new Error("missing save button");

    saveButton.focus();
    await act(async () => {
      saveButton.click();
    });
    let dialog = document.querySelector<HTMLElement>('[role="dialog"]');
    const cancelButton = Array.from(dialog?.querySelectorAll("button") ?? [])
      .find((button) => button.textContent?.trim() === "取消") as HTMLButtonElement | undefined;
    if (!cancelButton) throw new Error("missing guarded-edit cancel button");
    await act(async () => {
      cancelButton.click();
    });
    expect(mocked.putCalls).toHaveLength(0);
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    expect(document.activeElement).toBe(saveButton);
    expect(input.value).toBe("7");

    await act(async () => {
      saveButton.click();
    });
    dialog = document.querySelector<HTMLElement>('[role="dialog"]');
    expect(dialog).not.toBeNull();
    await act(async () => {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true }));
    });
    expect(mocked.putCalls).toHaveLength(0);
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    expect(document.activeElement).toBe(saveButton);
    expect(input.value).toBe("7");
  });

  it("shows backend-driven derived IBKR client ids with live draft preview", async () => {
    await renderDataSources();
    // effective ids straight from the view — no typing needed
    expect(host!.textContent).toContain("各域用戶端 ID：");
    expect(host!.textContent).toContain("基底=1");
    expect(host!.textContent).toContain("選擇權=11");
    expect(host!.textContent).toContain("股價=21");
    expect(host!.textContent).toContain("新聞=31");
    expect(host!.textContent).toContain("IV=41");
    const input = Array.from(host!.querySelectorAll("input")).find((node) =>
      node.getAttribute("placeholder") === "Client ID") as HTMLInputElement | undefined;
    if (!input) throw new Error("missing client-id input");
    await act(async () => {
      setInputValue(input, "7");
    });
    // valid draft previews post-save ids
    expect(host!.textContent).toContain("存檔後 ID：");
    expect(host!.textContent).toContain("選擇權=17");
    expect(host!.textContent).toContain("IV=47");
    // invalid draft falls back to the backend's effective ids (never fabricates)
    await act(async () => {
      setInputValue(input, "abc");
    });
    expect(host!.textContent).toContain("各域用戶端 ID：");
    expect(host!.textContent).toContain("選擇權=11");
  });

  it("env-controlled client id never shows a save preview (real env wins precedence)", async () => {
    const field = mocked.providersConfig.providers.ibkr.fields.find((f) => f.field === "client_id") as
      | { effective_source: string }
      | undefined;
    if (!field) throw new Error("missing client_id field");
    const original = field.effective_source;
    field.effective_source = "env";
    try {
      await renderDataSources();
      // effective ids come from the backend (which read the real env)
      expect(host!.textContent).toContain("環境變數控制中");
      expect(host!.textContent).toContain("選擇權=11");
      const input = Array.from(host!.querySelectorAll("input")).find((node) =>
        node.getAttribute("placeholder") === "Client ID") as HTMLInputElement | undefined;
      if (!input) throw new Error("missing client-id input");
      await act(async () => {
        setInputValue(input, "7");
      });
      // a draft must NOT preview 存檔後 ids — saving the app value changes nothing
      // while the shell env overrides it
      expect(host!.textContent).not.toContain("存檔後 ID：");
      expect(host!.textContent).toContain("選擇權=11");
      expect(host!.textContent).not.toContain("選擇權=17");
    } finally {
      field.effective_source = original;
    }
  });

  it("keeps long last-run messages out of the schedule row summary", async () => {
    await renderDataSources();
    const row = Array.from(host!.querySelectorAll("tr")).find((node) =>
      node.textContent?.includes("Polygon news"));
    if (!row) throw new Error("missing schedule row");

    const summary = row.querySelector(".ds-last-run-summary");
    expect(summary?.textContent).toContain("已跳過");
    expect(summary?.textContent).toContain("上次失敗");
    expect(summary?.textContent).not.toContain(mocked.longSkipReason);
    expect(summary?.textContent).not.toContain(mocked.longDurableError);

    const details = row.querySelector("details.ds-last-run-details");
    expect(details?.textContent).toContain(mocked.longSkipReason);
    expect(details?.textContent).toContain(mocked.longDurableError);
  });

  it("renders durable IBKR partial counts without a manual continuation action", async () => {
    await renderDataSources();
    const row = Array.from(host!.querySelectorAll("tr")).find((node) =>
      node.textContent?.includes("IBKR 新聞"));
    if (!row) throw new Error("missing IBKR news schedule row");

    expect(row.textContent).toContain("部分完成（10 篇內文待後續處理）");
    expect(row.textContent).not.toContain("待補抓");
    expect(Array.from(row.querySelectorAll("button")).some((button) =>
      button.textContent?.trim() === "補抓")).toBe(false);
    expect(Array.from(row.querySelectorAll("button")).some((button) =>
      button.textContent?.includes("Run"))).toBe(true);
  });

  it("renders succeeded IBKR run and scheduled body backlog as separate facts", async () => {
    mocked.ibkrBodyBacklogMode = "succeeded";
    await renderDataSources();
    const row = Array.from(host!.querySelectorAll("tr")).find((node) =>
      node.textContent?.includes("IBKR 新聞"));
    if (!row) throw new Error("missing IBKR news schedule row");

    expect(row.textContent).toContain("上次成功");
    expect(row.textContent).toContain("內文佇列：2 篇已排程稍後重試");
    expect(row.textContent).toContain(`最早 ${formatSystemTimestamp("2026-07-15T06:00:00Z")}`);
  });

  it("renders partial retry outcome with backlog and no continuation button", async () => {
    mocked.ibkrBodyBacklogMode = "partial";
    await renderDataSources();
    const row = Array.from(host!.querySelectorAll("tr")).find((node) =>
      node.textContent?.includes("IBKR 新聞"));
    if (!row) throw new Error("missing IBKR news schedule row");

    expect(row.textContent).toContain("部分完成");
    expect(row.textContent).toContain("內文佇列：1 篇已排程稍後重試");
    expect(row.textContent).not.toContain("待補抓 0");
    expect(Array.from(row.querySelectorAll("button")).some((button) =>
      button.textContent?.trim() === "補抓")).toBe(false);
    expect(Array.from(row.querySelectorAll("button")).some((button) =>
      button.textContent?.includes("Run"))).toBe(true);
    expect(row.textContent).not.toContain("provider_article_id");
  });

  it("renders entitlement-blocked bodies as retained headlines without a retry action", async () => {
    mocked.ibkrBodyBacklogMode = "entitlement";
    await renderDataSources();
    const row = Array.from(host!.querySelectorAll("tr")).find((node) =>
      node.textContent?.includes("IBKR 新聞"));
    if (!row) throw new Error("missing IBKR news schedule row");

    expect(row.textContent).toContain("78 篇來源目前未訂閱");
    expect(row.textContent).toContain("標題已保留");
    expect(row.textContent).toContain("開通後自動重試");
    expect(row.textContent).not.toContain("FLY");
    expect(row.textContent).not.toContain("provider_article_id");
    expect(Array.from(row.querySelectorAll("button")).some((button) =>
      button.textContent?.trim() === "補抓")).toBe(false);
    expect(Array.from(row.querySelectorAll("button")).some((button) =>
      button.textContent?.includes("Run"))).toBe(true);
  });

  it("renders_known_schedule_progress_without_covering_the_last_run_cell", async () => {
    mocked.scheduleRunning = true;
    mocked.scheduleProgress = {
      done: 17,
      total: 149,
      current: "BRK.B — long current contract name that must wrap inside the progress cell",
    };
    await renderDataSources();
    const row = Array.from(host!.querySelectorAll("tr")).find((node) =>
      node.textContent?.includes("Polygon news"));
    if (!row) throw new Error("missing schedule row");
    expect(row.querySelector(".source-run-current")?.textContent).toContain("BRK.B");
    expect(row.querySelector(".source-run-counts")?.textContent).toBe("17 / 149 · 11%");
    expect(row.querySelector("[role='progressbar']")).not.toBeNull();
    expect(row.querySelector(".ds-last-run-cell")?.textContent).toContain("已跳過");
  });

  it("shows_disabled_provider_and_schedule_states_as_neutral_text", async () => {
    await renderDataSources();
    const providerRow = Array.from(host!.querySelectorAll("tr")).find((node) =>
      node.textContent?.includes("Retired provider"));
    if (!providerRow) throw new Error("missing disabled provider row");
    expect(providerRow.textContent).toContain("已停用");
    expect(providerRow.querySelector(".ui-status-badge")).toBeNull();
    expect(providerRow.querySelector(".ds-chip")).toBeNull();
    expect(providerRow.querySelector(".muted")).not.toBeNull();

    const row = Array.from(host!.querySelectorAll("tr")).find((node) =>
      node.textContent?.includes("價格缺口補抓"));
    if (!row) throw new Error("missing price_backfill row");
    expect(row.textContent).toContain("排程關閉");
    const scheduleCell = row.querySelectorAll("td")[1];
    expect(scheduleCell?.querySelector(".ui-status-badge")).toBeNull();
    expect(scheduleCell?.querySelector(".ds-schedule-disabled")?.textContent).toBe("排程關閉");
    expect(Array.from(row.querySelectorAll("button")).some((button) =>
      button.textContent?.includes("Run"))).toBe(true);
  });

  it("renders_persisted_skipped_history_as_neutral_instead_of_never_run", async () => {
    await renderDataSources();
    const row = Array.from(host!.querySelectorAll("tr")).find((node) =>
      node.textContent?.includes("Writer lock deferred"));
    if (!row) throw new Error("missing durable skipped row");
    expect(row.textContent).toContain("上次已跳過");
    expect(row.textContent).not.toContain("尚未執行");
    expect(row.querySelector(".ui-status-badge")).toBeNull();
  });

  it("does_not_render_storage_route_source_badges", async () => {
    await renderDataSources();
    const row = Array.from(host!.querySelectorAll("tr")).find((node) =>
      node.textContent?.includes("價格缺口補抓"));
    if (!row) throw new Error("missing price_backfill row");
    expect(row.querySelector("td")?.textContent?.replace(/\s+/g, "").trim())
      .toBe("價格缺口補抓");
    expect(row.querySelector("td")?.hasAttribute("title")).toBe(false);
    expect(row.textContent).not.toContain("IBKR/Polygon");
    expect(row.textContent).not.toContain("直寫本地");
    expect(host!.textContent).not.toMatch(
      /直寫本地 SQLite|direct-local|PG 同步|鏡像|FRED 本地快照|本地快照|存本地|strict DB-first|legacy config/,
    );
    const protectionNote = host!.querySelector(".ds-schedule-protection-note");
    expect(protectionNote?.textContent).toContain("同一資料來源與 IBKR 工作同時間只執行一次");
    expect(protectionNote?.textContent).not.toMatch(/job_runs|data\/locks\/|app 與 CLI/);
    expect(host!.textContent).toContain("config/.env");
  });

  it("renders FRED as configured local snapshot with refresh off", async () => {
    await renderDataSources();
    const row = Array.from(host!.querySelectorAll("tr")).find((node) =>
      node.textContent?.includes("FRED"));
    if (!row) throw new Error("missing FRED provider row");
    expect(row.textContent).toContain("正常");
    expect(row.textContent).toContain("app");
    expect(row.textContent).toContain("資料快照");
    expect(row.textContent).toContain("自動刷新未啟用");
    expect(row.textContent).not.toContain("未啟用抓取");
    expect(row.textContent).not.toContain("已停用");
    expect(row.querySelector("td")?.hasAttribute("title")).toBe(false);
    expect(row.querySelector(".ui-status-badge")?.getAttribute("data-state")).toBe("ready");
  });

  it("does_not_request_or_render_the_detailed_fred_snapshot", async () => {
    clearDataSourceReadMocks();
    await renderDataSources();
    expect(Array.from(host!.querySelectorAll("h4"))
      .some((heading) => heading.textContent?.trim() === "FRED 資料快照")).toBe(false);
    expect(host!.textContent).not.toContain("Fed Funds");
    expect(host!.querySelector("[data-testid='fred-snapshot-scroll']")).toBeNull();
    expect(getSchedule).toHaveBeenCalledTimes(1);
    expect(getProvidersHealth).toHaveBeenCalledTimes(1);
    expect(getProvidersConfig).toHaveBeenCalledTimes(1);
  });

  it("reports_unsaved_provider_and_schedule_drafts_to_navigation_owner", async () => {
    const onNavigationGuardChange = vi.fn();
    await renderDataSources(onNavigationGuardChange);
    const interval = host!.querySelector<HTMLInputElement>("input.ds-interval:not(.ds-keyinput)");
    if (!interval) throw new Error("missing schedule interval draft");

    await act(async () => { setInputValue(interval, "777"); });
    expect(onNavigationGuardChange.mock.calls.at(-1)?.[0]).toEqual({
      dirty: true,
      busy: false,
      reason: "資料來源與排程有未儲存的變更。",
    });
    expect(JSON.stringify(onNavigationGuardChange.mock.calls)).not.toContain("777");

    const providerDraft = host!.querySelector<HTMLInputElement>('input.ds-keyinput[type="password"]');
    if (!providerDraft) throw new Error("missing provider field draft");
    await act(async () => {
      setInputValue(interval, "");
      setInputValue(providerDraft, "planted-provider-secret");
    });
    expect(onNavigationGuardChange.mock.calls.at(-1)?.[0].dirty).toBe(true);
    expect(JSON.stringify(onNavigationGuardChange.mock.calls)).not.toContain("planted-provider-secret");
  });

  it("reports_mutations_as_navigation_blocking_and_clears_after_completion", async () => {
    const onNavigationGuardChange = vi.fn();
    await renderDataSources(onNavigationGuardChange);
    const providerDraft = host!.querySelector<HTMLInputElement>('input.ds-keyinput[type="password"]');
    if (!providerDraft) throw new Error("missing provider field draft");
    await act(async () => { setInputValue(providerDraft, "planted-busy-secret"); });
    const pending = deferred<Awaited<ReturnType<typeof putProviderConfig>>>();
    vi.mocked(putProviderConfig).mockImplementationOnce(() => pending.promise);
    const row = providerDraft.closest("tr");
    const save = Array.from(row?.querySelectorAll<HTMLButtonElement>("button") ?? [])
      .find((button) => button.textContent?.trim() === "儲存");
    if (!save) throw new Error("missing provider save button");

    await act(async () => { save.click(); });
    await waitForReport(onNavigationGuardChange, (report) => report.busy);
    expect(onNavigationGuardChange.mock.calls.at(-1)?.[0]).toEqual({
      dirty: true,
      busy: true,
      reason: "資料來源設定更新正在進行。",
    });
    pending.resolve(mocked.providersConfig.providers.polygon);
    await waitForReport(onNavigationGuardChange, (report) => !report.busy && !report.dirty);
    expect(JSON.stringify(onNavigationGuardChange.mock.calls)).not.toContain("planted-busy-secret");
  });

  it("renders IBKR connection settings as one grouped block with derived ids below the client id", async () => {
    await renderDataSources();
    const group = host!.querySelector("[data-testid='ibkr-config-group']");
    expect(group?.textContent).toContain("Gateway host");
    expect(group?.textContent).toContain("Gateway port");
    expect(group?.textContent).toContain("Client ID");
    expect(group?.textContent).toContain("各域用戶端 ID：");
    expect(group?.textContent).toContain("股價=21");
  });

  it("wraps_each_wide_data_source_table_in_an_explicit_scroll_owner", async () => {
    await renderDataSources();
    for (const id of [
      "provider-health-scroll",
      "sa-health-scroll",
      "provider-config-scroll",
      "schedule-scroll",
    ]) {
      const owner = host!.querySelector(`[data-testid='${id}']`);
      expect(owner?.classList.contains("settings-table-scroll")).toBe(true);
      expect(owner?.querySelector("table")).not.toBeNull();
    }
  });

  it("marks_long_runtime_content_as_wrap_capable", async () => {
    await renderDataSources();
    const wrapCells = Array.from(host!.querySelectorAll(".settings-wrap-text"));
    expect(wrapCells.some((cell) => cell.textContent?.includes("native-host binding"))).toBe(true);
    expect(wrapCells.some((cell) => cell.textContent?.includes("request_id=provider-health-check"))).toBe(true);
    expect(host!.querySelector(".ds-last-run-cell.settings-wrap-text")).not.toBeNull();
  });

  it("settings_data_sources_does_not_own_portfolio_capture_controls", async () => {
    await renderDataSources();
    expect(host!.textContent).not.toContain("持倉擷取排程");
    expect(host!.querySelector("[data-portfolio-capture-controls]")).toBeNull();
  });

  it("polls only schedule after thirty idle seconds without a live region", async () => {
    vi.useFakeTimers();
    await renderDataSources();
    clearDataSourceReadMocks();

    await act(async () => { await vi.advanceTimersByTimeAsync(29_999); });
    expect(getSchedule).not.toHaveBeenCalled();

    await act(async () => { await vi.advanceTimersByTimeAsync(1); });
    expect(getSchedule).toHaveBeenCalledTimes(1);
    expect(getProvidersHealth).not.toHaveBeenCalled();
    expect(getProvidersConfig).not.toHaveBeenCalled();
    expect(host!.querySelector("[aria-live]")).toBeNull();
  });

  it("detects a fast idle-to-idle completion and refreshes related state once", async () => {
    vi.useFakeTimers();
    await renderDataSources();
    clearDataSourceReadMocks();
    mocked.ibkrBodyBacklogMode = "succeeded";
    mocked.scheduleLastAttemptAt = "2026-07-17T10:30:00Z";
    mocked.scheduleUpdatedAt = "2026-07-17T10:31:00Z";

    await act(async () => { await vi.advanceTimersByTimeAsync(30_000); });

    expect(getSchedule).toHaveBeenCalledTimes(2);
    expect(getProvidersHealth).toHaveBeenCalledTimes(1);
    expect(getProvidersConfig).toHaveBeenCalledTimes(1);
    const row = Array.from(host!.querySelectorAll("tr")).find((node) =>
      node.textContent?.includes("IBKR 新聞"));
    expect(row?.textContent).toContain("上次成功");
  });

  it("switches to five second polling while running and back to idle after completion", async () => {
    vi.useFakeTimers();
    await renderDataSources();
    clearDataSourceReadMocks();

    mocked.scheduleRunning = true;
    mocked.scheduleLastAttemptAt = "2026-07-17T10:30:00Z";
    await act(async () => { await vi.advanceTimersByTimeAsync(30_000); });
    expect(host!.textContent).toContain("執行中，自動更新");

    clearDataSourceReadMocks();
    await act(async () => { await vi.advanceTimersByTimeAsync(5_000); });
    expect(getSchedule).toHaveBeenCalledTimes(1);
    expect(getProvidersHealth).not.toHaveBeenCalled();

    mocked.scheduleRunning = false;
    mocked.scheduleUpdatedAt = "2026-07-17T10:31:00Z";
    await act(async () => { await vi.advanceTimersByTimeAsync(5_000); });
    expect(getProvidersHealth).toHaveBeenCalledTimes(1);
    expect(host!.textContent).not.toContain("執行中，自動更新");

    clearDataSourceReadMocks();
    await act(async () => { await vi.advanceTimersByTimeAsync(29_999); });
    expect(getSchedule).not.toHaveBeenCalled();
    await act(async () => { await vi.advanceTimersByTimeAsync(1); });
    expect(getSchedule).toHaveBeenCalledTimes(1);
  });

  it("refreshes schedule on focus and full-loads only when lifecycle truth changes", async () => {
    await renderDataSources();
    clearDataSourceReadMocks();

    await act(async () => { window.dispatchEvent(new Event("focus")); });
    expect(getSchedule).toHaveBeenCalledTimes(1);
    expect(getProvidersHealth).not.toHaveBeenCalled();

    clearDataSourceReadMocks();
    mocked.scheduleLastAttemptAt = "2026-07-17T10:30:00Z";
    mocked.scheduleUpdatedAt = "2026-07-17T10:31:00Z";
    await act(async () => { window.dispatchEvent(new Event("focus")); });
    expect(getSchedule).toHaveBeenCalledTimes(2);
    expect(getProvidersHealth).toHaveBeenCalledTimes(1);
    expect(getProvidersConfig).toHaveBeenCalledTimes(1);
  });

  it("coalesces timer and focus reads and preserves prior truth on poll failure", async () => {
    vi.useFakeTimers();
    await renderDataSources();
    const before = host!.textContent;
    clearDataSourceReadMocks();
    let rejectPoll: ((reason?: unknown) => void) | null = null;
    vi.mocked(getSchedule).mockImplementationOnce(() => new Promise((_, reject) => {
      rejectPoll = reject;
    }));

    await act(async () => { await vi.advanceTimersByTimeAsync(30_000); });
    await act(async () => { window.dispatchEvent(new Event("focus")); });
    expect(getSchedule).toHaveBeenCalledTimes(1);

    await act(async () => {
      rejectPoll!(new Error("temporary schedule read failure"));
      await Promise.resolve();
    });
    expect(host!.textContent).toBe(before);
    expect(getProvidersHealth).not.toHaveBeenCalled();
  });

  it("does not let an older full refresh replace newer schedule truth", async () => {
    await renderDataSources();
    const staleSchedule = await getSchedule();
    clearDataSourceReadMocks();
    let resolveOldFull!: (value: Awaited<ReturnType<typeof getSchedule>>) => void;
    vi.mocked(getSchedule).mockImplementationOnce(() => new Promise((resolve) => {
      resolveOldFull = resolve;
    }));

    const refresh = Array.from(host!.querySelectorAll("button")).find((button) =>
      button.textContent?.includes("重新整理"));
    if (!refresh) throw new Error("missing Data Sources refresh button");
    await act(async () => {
      refresh.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
      await Promise.resolve();
    });
    expect(getSchedule).toHaveBeenCalledTimes(1);

    mocked.scheduleRunning = true;
    mocked.scheduleLastAttemptAt = "2026-07-17T10:30:00Z";
    mocked.scheduleUpdatedAt = "2026-07-17T10:31:00Z";
    await act(async () => {
      window.dispatchEvent(new Event("focus"));
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(getSchedule).toHaveBeenCalledTimes(3);

    await act(async () => {
      resolveOldFull(staleSchedule);
      await Promise.resolve();
    });
    expect(host!.textContent).toContain("執行中，自動更新");
  });

  it("removes idle timers and focus listeners and ignores a finishing poll after unmount", async () => {
    vi.useFakeTimers();
    await renderDataSources();
    let resolvePoll: ((value: Awaited<ReturnType<typeof getSchedule>>) => void) | null = null;
    clearDataSourceReadMocks();
    vi.mocked(getSchedule).mockImplementationOnce(() => new Promise((resolve) => {
      resolvePoll = resolve;
    }));

    await act(async () => { window.dispatchEvent(new Event("focus")); });
    expect(getSchedule).toHaveBeenCalledTimes(1);

    act(() => root!.unmount());
    root = null;
    await act(async () => {
      resolvePoll!({ sources: {} });
      await Promise.resolve();
    });
    await act(async () => { await vi.advanceTimersByTimeAsync(60_000); });
    await act(async () => { window.dispatchEvent(new Event("focus")); });

    expect(getSchedule).toHaveBeenCalledTimes(1);
    expect(getProvidersHealth).not.toHaveBeenCalled();
  });
});
