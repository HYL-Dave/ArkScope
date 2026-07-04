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
        fields: [{
          field: "client_id",
          label: "Client ID",
          secret: false,
          env_var: "IBKR_CLIENT_ID",
          app_value_set: true,
          app_value_masked: "1",
          effective_source: "app",
          needs_import: false,
          import_source: null,
          importable_env_vars: ["IBKR_CLIENT_ID"],
          defaulted: true,
          guarded: true,
          guard_reason: "Changing IBKR client_id can disturb active Gateway sessions.",
        }],
        testable: true,
        default_available: false,
      },
    },
    setup: { required: false, code: null, reason: null },
  },
  longSkipReason:
    "scheduler lock refused because another collector process is still holding collect.polygon_news; " +
    "pid=42391 host=ais elapsed=1842s lock_path=/mnt/md0/PycharmProjects/ArkScope/data/locks/collect.polygon_news.lock",
  longDurableError:
    "IBKR historical data request failed after bounded retries: HMDS query returned no data for HAPN on 2026-06-05 " +
    "during afternoon recovery window; clientId=11 requestId=980123 pacing bucket=hist_15m",
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
    { id: "polygon", label: "Polygon", kind: "news", status: "missing_key", enabled: true, key_present: true, key_source: "config/.env", key_vars: ["POLYGON_API_KEY"], last_success_at: null, last_attempt_at: null, last_error: null, detail: "", signals: {}, key_import_suggested: true },
    { id: "ibkr", label: "IBKR", kind: "market", status: "no_signal", enabled: true, key_present: true, key_source: "app", key_vars: ["IBKR_HOST", "IBKR_PORT"], last_success_at: null, last_attempt_at: null, last_error: null, detail: "", signals: {}, key_import_suggested: false },
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
          enabled: true,
          interval_minutes: 30,
          default_interval_minutes: 30,
          running: false,
          progress: null,
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
      },
    })),
    getProvidersHealth: vi.fn(async () => health),
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

  it("shows derived IBKR client ids live from the client-id input", async () => {
    await renderDataSources();
    // saved base "1" renders the derived table without any typing
    expect(host!.textContent).toContain("選擇權=11");
    expect(host!.textContent).toContain("報價=21");
    expect(host!.textContent).toContain("新聞=31");
    expect(host!.textContent).toContain("IV=41");
    const input = Array.from(host!.querySelectorAll("input")).find((node) =>
      node.getAttribute("placeholder") === "Client ID") as HTMLInputElement | undefined;
    if (!input) throw new Error("missing client-id input");
    await act(async () => {
      setInputValue(input, "7");
    });
    expect(host!.textContent).toContain("基底=7");
    expect(host!.textContent).toContain("選擇權=17");
    expect(host!.textContent).toContain("IV=47");
    // non-numeric draft hides the hint instead of advertising ids the backend rejects
    await act(async () => {
      setInputValue(input, "abc");
    });
    expect(host!.textContent).not.toContain("選擇權=");
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
});
