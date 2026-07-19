/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { MacroSnapshot, MacroStatus, MarketDataStatus, ModelCatalog, ModelTask, NewsStatus, TaskRoute, TradingDayCoverage } from "./api";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

const mocked = vi.hoisted(() => ({
  marketStatus: null as MarketDataStatus | null,
  macroStatus: null as MacroStatus | null,
  macroSnapshot: null as MacroSnapshot | null,
  marketError: null as Error | null,
  macroError: null as Error | null,
  macroSnapshotError: null as Error | null,
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

const macroSnapshot: MacroSnapshot = {
  available: true,
  macro_db: "/tmp/macro_calendar.db",
  series_count: 2,
  observation_count: 29_571,
  release_dates_count: 3,
  latest_fetched_at: "2026-07-01T00:00:00+00:00",
  auto_refresh_enabled: false,
  items: [{
    series_id: "FEDFUNDS",
    label: "Fed Funds",
    title: "Federal Funds Effective Rate",
    units: "Percent",
    value: 4.33,
    observation_date: "2026-06-01",
    fetched_at: "2026-07-01T00:00:00+00:00",
    realtime_start: "2026-06-01",
    realtime_end: "2026-06-01",
  }],
  missing_series: [],
};

mocked.marketStatus = marketStatus;
mocked.macroStatus = macroStatus;
mocked.macroSnapshot = macroSnapshot;

const coverage: TradingDayCoverage = {
  interval: "15min",
  lookback_days: 10,
  universe_count: 149,
  generated_at_et: "2026-07-03T16:00:00-04:00",
  days: [],
  provider_errors: [],
};

const newsStatus: NewsStatus = {
  market_db: "/tmp/market.db",
  exists: true,
  news: { row_count: 371_672, source_count: 3, latest_published: "2026-06-27T11:11:00+0000" },
  use_local_news_setting: true,
  setting_explicit: true,
  env_override: false,
  env_value: null,
  direct_active: true,
  normalized_writes_setting: true,
  normalized_writes_setting_explicit: true,
  normalized_writes_env_override: false,
  normalized_writes_env_value: null,
  write_route: "normalized",
  write_route_reason: "active",
  news_pg_exit_completed: true,
  news_hard_local: true,
  pg_news_route_available: false,
  sync: null,
};

vi.mock("./InvestorProfilePanel", () => ({ InvestorProfilePanel: () => null }));
vi.mock("./settings/DataSourcesSection", () => ({ DataSourcesSection: () => null }));
vi.mock("./settings/ModelRoutingSection", () => ({
  ModelRoutingSection: () => null,
  TASK_LABELS: {
    card_synthesis: "AI 卡片生成",
    card_translation: "卡片翻譯",
    ai_research: "AI 研究",
  },
}));
vi.mock("./settings/ProviderSection", () => ({
  ProviderSection: () => null,
  CredentialList: () => null,
  DiscoveryResultView: () => null,
  SetupDisclosure: () => null,
}));
vi.mock("./settings/RuntimeLimitSections", () => ({
  FixedTaskRuntimeSection: () => null,
  ResearchRuntimeSection: () => null,
}));

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
    getMacroSnapshot: vi.fn(async () => {
      if (mocked.macroSnapshotError) throw mocked.macroSnapshotError;
      return mocked.macroSnapshot!;
    }),
    getTradingDayCoverage: vi.fn(async () => coverage),
    getNewsStatus: vi.fn(async () => newsStatus),
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
  mocked.macroSnapshot = macroSnapshot;
  mocked.marketError = null;
  mocked.macroError = null;
  mocked.macroSnapshotError = null;
});

async function renderSettings() {
  window.localStorage.setItem("arkscope.settings.activeGroup.v1", "data_sync");
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(React.createElement(SettingsView, { runtime: null, onRuntimeChanged: vi.fn() }));
  });
  await act(async () => { await Promise.resolve(); });
}

describe("post-PG-exit storage panels", () => {
  it("shows Data Storage as normal market data status", async () => {
    mocked.marketStatus = {
      ...marketStatus,
      sync: {
        ...marketStatus.sync,
        prices: {
          retired: true,
          authority: "local",
        } as unknown as MarketDataStatus["sync"]["prices"],
      },
    };
    await renderSettings();

    expect(host!.querySelector('[data-settings-anchor="data_storage"]')).not.toBeNull();
    expect(host!.textContent).toContain("市場資料 · Market Data");
    expect(host!.textContent).toContain("價格");
    expect(host!.textContent).toContain("價格 —");
    expect(host!.textContent).toContain("財務快取");
    expect(host!.textContent).not.toMatch(
      /PG fallback|SQLite|local authority|本地市場資料庫|本地市場庫|本地路由/,
    );
  });

  it("shows_total_macro_data_without_claiming_calendar_product", async () => {
    await renderSettings();

    expect(host!.querySelector('[data-settings-anchor="macro_storage"]')).not.toBeNull();
    expect(host!.textContent).toContain("總經資料");
    expect(host!.textContent).toContain("FRED 序列");
    expect(host!.textContent).toContain("Fed Funds");
    expect(host!.textContent).not.toMatch(/Macro \/ Calendar|行事曆|Finnhub 付費方案/);
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
    const directory = host!.querySelector('nav[aria-label="設定目錄"]');
    expect(Array.from(directory!.querySelectorAll("button")).map((button) => button.textContent?.trim()))
      .toEqual([
        "資料來源與排程",
        "市場資料",
        "新聞資料",
        "總經資料",
      ]);
    expect(directory!.textContent).not.toMatch(/PG mirror routes|PostgreSQL exit|本地總經|一次性遷移/);
  });

  it("renders_market_empty_and_macro_partial_failures_as_user_outcomes", async () => {
    mocked.marketStatus = {
      ...marketStatus,
      exists: false,
    };
    await renderSettings();
    expect(host!.textContent).toContain("尚無資料");
    expect(host!.textContent).not.toContain("尚未建立");

    dispose();
    mocked.marketStatus = marketStatus;
    mocked.macroSnapshotError = new Error("RAW_MACRO_SNAPSHOT_TRANSPORT_DETAIL");
    await renderSettings();
    expect(host!.textContent).toContain("29,571 筆已儲存");
    expect(host!.querySelector('[data-state="partial"]')).not.toBeNull();
    expect(host!.textContent).not.toContain("RAW_MACRO_SNAPSHOT_TRANSPORT_DETAIL");
    expect(host!.textContent).not.toMatch(/SQLite|PG fallback|local-only/);
  });
});
