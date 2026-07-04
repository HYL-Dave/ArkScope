/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { MacroStatus, MarketDataStatus, ModelCatalog, ModelTask, TaskRoute, TradingDayCoverage } from "./api";

const emptyCatalog: ModelCatalog = {
  providers: ["anthropic", "openai"],
  tasks: [],
  models: [],
  effort_options: { anthropic: [], openai: [] },
  routes: {} as Record<ModelTask, TaskRoute>,
  credentials: { anthropic: [], openai: [] },
  custom_allowed: true,
};

const marketStatus: MarketDataStatus = {
  market_db: "/tmp/market.db",
  exists: true,
  prices: { row_count: 2_324_487, ticker_count: 149, latest_datetime: "2026-07-03T20:00:00+0000" },
  news: { row_count: 371_672, source_count: 3, latest_published: "2026-06-27T11:11:00+0000" },
  iv: { row_count: 24, ticker_count: 4, latest_date: "2026-03-06" },
  fundamentals: { row_count: 130, ticker_count: 130, latest_date: "2026-06-01" },
  financial_cache: { row_count: 24, valid_count: 7, expired_count: 17, latest_fetched_at: "2026-07-01T00:00:00+00:00" },
  sync: { prices: null, news: null, iv: null, fundamentals: null },
  use_local_market_setting: false,
  env_override: false,
  local_market_strict_setting: false,
  strict_env_override: false,
  strict_enabled: true,
  routing_enabled: true,
  pg_fallback_active: false,
};

const macroStatus: MacroStatus = {
  macro_db: "/tmp/macro_calendar.db",
  exists: true,
  tables: {
    macro_series: { row_count: 86, last_fetched_at: "2026-07-01T00:00:00+00:00" },
    macro_observations: { row_count: 29_571, last_fetched_at: "2026-07-01T00:00:00+00:00" },
  },
  use_local_macro_setting: false,
  env_override: false,
  local_first_active: true,
};

const coverage: TradingDayCoverage = {
  interval: "15min",
  lookback_days: 10,
  universe_count: 149,
  generated_at_et: "2026-07-03T16:00:00-04:00",
  days: [],
  provider_errors: [],
};

vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return {
    ...actual,
    getModelCatalog: vi.fn(async () => emptyCatalog),
    getMarketDataStatus: vi.fn(async () => marketStatus),
    getMacroStatus: vi.fn(async () => macroStatus),
    getTradingDayCoverage: vi.fn(async () => coverage),
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
});

async function renderSettings() {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(React.createElement(SettingsView, { runtime: null, onRuntimeChanged: vi.fn() }));
  });
  await act(async () => { await Promise.resolve(); });
}

async function openSection(label: string) {
  const button = Array.from(host!.querySelectorAll("button")).find((node) =>
    node.textContent?.includes(label));
  if (!button) throw new Error(`missing ${label} section button`);
  await act(async () => {
    button.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
  });
  await act(async () => { await Promise.resolve(); });
}

describe("post-PG-exit storage panels", () => {
  it("shows Data Storage as locked local authority without retired PG mirror actions", async () => {
    await renderSettings();
    await openSection("Data Storage");

    expect(host!.textContent).toContain("本地權威（PG fallback 已退役）");
    expect(host!.textContent).toContain("local authority");
    const buttons = Array.from(host!.querySelectorAll("button")).map((button) => button.textContent ?? "");
    expect(buttons).not.toContain("建立本地市場庫");
    expect(buttons).not.toContain("重建本地市場庫");
    expect(buttons).not.toContain("增量更新");
    expect(buttons).not.toContain("驗證本地資料");
    expect(host!.textContent).not.toContain("使用本地 market data");
  });

  it("shows Macro / Calendar as local-only without a local-vs-PG toggle", async () => {
    await renderSettings();
    await openSection("Macro / Calendar");

    expect(host!.textContent).toContain("Macro / Calendar is local-only");
    expect(host!.textContent).not.toContain("使用本地 macro / calendar");
    expect(host!.textContent).not.toContain("關閉（使用 PG）");
  });

  it("does not show the completed App Records migration panel in normal settings navigation", async () => {
    await renderSettings();

    expect(host!.textContent).not.toContain("App Records");
    expect(host!.textContent).not.toContain("App Records 遷移");
    expect(host!.textContent).not.toContain("一次性 PG→本地遷移工具");
  });
});
