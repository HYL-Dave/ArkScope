/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { MacroStatus, MarketDataStatus, ModelCatalog, ModelTask, TaskRoute, TradingDayCoverage } from "./api";

const mocked = vi.hoisted(() => ({
  marketStatus: null as MarketDataStatus | null,
  macroStatus: null as MacroStatus | null,
  marketError: null as Error | null,
  macroError: null as Error | null,
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

mocked.marketStatus = marketStatus;
mocked.macroStatus = macroStatus;

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
    getMarketDataStatus: vi.fn(async () => {
      if (mocked.marketError) throw mocked.marketError;
      return mocked.marketStatus!;
    }),
    getMacroStatus: vi.fn(async () => {
      if (mocked.macroError) throw mocked.macroError;
      return mocked.macroStatus!;
    }),
    getTradingDayCoverage: vi.fn(async () => coverage),
  };
});

import { SettingsView } from "./Settings";

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

function dispose() {
  if (root) act(() => root!.unmount());
  host?.remove();
  root = null;
  host = null;
}

afterEach(() => {
  dispose();
  mocked.marketStatus = marketStatus;
  mocked.macroStatus = macroStatus;
  mocked.marketError = null;
  mocked.macroError = null;
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
  it("shows Data Storage as normal market data status", async () => {
    await renderSettings();
    await openSection("Data Storage");

    expect(host!.textContent).toContain("市場資料 · Market Data");
    expect(host!.textContent).toContain("價格");
    expect(host!.textContent).toContain("財務快取");
    expect(host!.textContent).not.toMatch(
      /PG fallback|SQLite|local authority|本地市場資料庫|本地市場庫|本地路由/,
    );
  });

  it("shows Macro / Calendar as normal macro and calendar status", async () => {
    await renderSettings();
    await openSection("Macro / Calendar");

    expect(host!.textContent).toContain("總經與行事曆 · Macro / Calendar");
    expect(host!.textContent).toContain("FRED 序列");
    expect(host!.textContent).toContain("Finnhub 付費方案");
    expect(host!.textContent).not.toMatch(/PostgreSQL|PG|SQLite|local-only|本地總經庫|本地路由/);
  });

  it("does not show the completed App Records migration panel in normal settings navigation", async () => {
    await renderSettings();

    expect(host!.textContent).not.toContain("App Records");
    expect(host!.textContent).not.toContain("App Records 遷移");
    expect(host!.textContent).not.toContain("一次性 PG→本地遷移工具");
  });

  it("uses_normal_user_outcomes_in_the_enabled_settings_directory", async () => {
    await renderSettings();
    expect(host!.textContent).toContain("價格、新聞、IV、基本面與財務快取狀態");
    expect(host!.textContent).toContain("新聞資料量、最新文章、收集狀態與最近錯誤");
    expect(host!.textContent).toContain("FRED 總經資料與經濟、財報、IPO 行事曆狀態");
    expect(host!.textContent).not.toMatch(/PG mirror routes|PostgreSQL exit|本地總經/);
  });

  it("renders_market_empty_and_macro_failed_states_as_user_outcomes", async () => {
    mocked.marketStatus = {
      ...marketStatus,
      exists: false,
    };
    await renderSettings();
    await openSection("Data Storage");
    expect(host!.textContent).toContain("尚無資料");
    expect(host!.textContent).not.toContain("尚未建立");

    dispose();
    mocked.marketStatus = marketStatus;
    mocked.macroError = new Error("macro status unavailable");
    await renderSettings();
    await openSection("Macro / Calendar");
    expect(host!.textContent).toContain("macro status unavailable");
    expect(host!.querySelector(".errorbox")).not.toBeNull();
    expect(host!.textContent).not.toMatch(/SQLite|PG fallback|local-only/);
  });
});
