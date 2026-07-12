/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ModelCatalog, ModelTask, ProvidersHealthResponse, TaskRoute } from "./api";

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
    getMacroSnapshot: vi.fn(async () => ({
      available: true,
      macro_db: "/tmp/macro_calendar.db",
      series_count: 11,
      observation_count: 29571,
      release_dates_count: 4659,
      latest_fetched_at: "2026-06-25T01:09:52Z",
      auto_refresh_enabled: false,
      missing_series: [],
      items: [
        {
          series_id: "FEDFUNDS",
          label: "Fed Funds",
          title: "Federal Funds Effective Rate",
          units: "Percent",
          value: 5.33,
          observation_date: "2026-06-01",
          fetched_at: "2026-06-25T01:09:52Z",
          realtime_start: "2026-06-01",
          realtime_end: "9999-12-31",
        },
        {
          series_id: "DGS10",
          label: "10Y",
          title: "Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity",
          units: "Percent",
          value: 4.24,
          observation_date: "2026-06-24",
          fetched_at: "2026-06-25T01:09:52Z",
          realtime_start: "2026-06-24",
          realtime_end: "9999-12-31",
        },
      ],
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
  vi.restoreAllMocks();
});

async function renderDataSources() {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(React.createElement(SettingsView, { runtime: null, onRuntimeChanged: vi.fn() }));
  });
  await act(async () => { await Promise.resolve(); });
  const dataButton = Array.from(host.querySelectorAll("button")).find((button) =>
    button.textContent?.includes("Data Sources"));
  if (!dataButton) throw new Error("missing Data Sources section button");
  await act(async () => {
    dataButton.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
  });
  await act(async () => { await Promise.resolve(); });
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
    expect(window.confirm).toHaveBeenCalled();
    expect(mocked.putCalls.at(-1)).toEqual({
      provider: "ibkr",
      fields: { client_id: "7" },
      confirmGuarded: { client_id: true },
    });
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

  it("renders the FRED local snapshot panel", async () => {
    await renderDataSources();
    expect(host!.textContent).toContain("FRED 資料快照");
    expect(host!.textContent).toContain("11 序列");
    expect(host!.textContent).toContain("29,571 觀測值");
    expect(host!.textContent).toContain("最後抓取 2026-06-25");
    expect(host!.textContent).toContain("自動刷新關閉");
    expect(host!.textContent).toContain("Fed Funds");
    expect(host!.textContent).toContain("5.33");
    expect(host!.textContent).toContain("2026-06-01");
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
      "fred-snapshot-scroll",
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
    expect(wrapCells.some((cell) => cell.textContent?.includes("Treasury Securities"))).toBe(true);
    expect(host!.querySelector(".ds-last-run-cell.settings-wrap-text")).not.toBeNull();
  });
});
