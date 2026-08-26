/** @vitest-environment jsdom */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import i18n from "i18next";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { MacroSnapshot, MacroStatus, MarketDataStatus, ModelCatalog, ModelTask, NewsStatus, SecurityLifecycleCaseListResponse, TaskRoute, TradingDayCoverage } from "./api";
import {
  LocaleProvider,
  createUiLocaleController,
  type UiLocaleController,
} from "./i18n";
import { formatSystemTimestamp } from "./timeDisplay";
import {
  createSettingsReadCache,
  tradingDayCoverageKey,
  type SettingsReadCache,
} from "./settings/settingsReadCache";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

const mocked = vi.hoisted(() => ({
  marketStatus: null as MarketDataStatus | null,
  macroStatus: null as MacroStatus | null,
  macroSnapshot: null as MacroSnapshot | null,
  marketError: null as Error | null,
  macroError: null as Error | null,
  macroSnapshotError: null as Error | null,
  coverage: null as TradingDayCoverage | null,
  lifecycle: null as SecurityLifecycleCaseListResponse | null,
  listLifecycleCases: vi.fn(),
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
  fundamentals: { row_count: 130, ticker_count: 130, latest_date: "2026-06-01" },
  financial_cache: { row_count: 24, valid_count: 7, expired_count: 17, latest_fetched_at: "2026-07-01T00:00:00+00:00" },
  sync: { prices: null, news: null, fundamentals: null },
  prices_authority: "local",
  fundamentals_mode: "local_cache_refetch",
  use_local_market_setting: false,
  env_override: false,
  local_market_strict_setting: false,
  strict_env_override: false,
  strict_enabled: true,
  routing_enabled: true,
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
  version: 2,
  market_scope: "us_listed_equity_proxy",
  coverage_session: "rth",
  interval: "15min",
  lookback_days: 10,
  universe_count: 149,
  generated_at_et: "2026-07-03T16:00:00-04:00",
  calendar_health: {
    status: "ok",
    reason_codes: [],
    reviewed_through: "2027-12-31",
    forward_horizon_months: 17,
  },
  observation_health: { status: "ok", reason_code: null },
  days: [],
  provider_errors: [],
};

const lifecycle = {
  cases: [],
  count: 33,
  queue_counts: { attention: 2, monitoring: 31, history: 0 },
  data_integrity: { source_missing_count: 2 },
} satisfies SecurityLifecycleCaseListResponse;

mocked.coverage = coverage;
mocked.lifecycle = lifecycle;

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
  sync: null,
};

vi.mock("./InvestorProfilePanel", () => ({ InvestorProfilePanel: () => null }));
vi.mock("./settings/DataSourcesSection", () => ({ DataSourcesSection: () => null }));
vi.mock("./settings/ModelRoutingSection", () => ({
  ModelRoutingSection: () => null,
  TASK_LABELS: {
    card_synthesis: "AI 卡片生成",
    card_translation: "內容翻譯",
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
    getTradingDayCoverage: vi.fn(async () => mocked.coverage!),
    listSecurityLifecycleCases: mocked.listLifecycleCases,
    getNewsStatus: vi.fn(async () => newsStatus),
  };
});

import {
  getMarketDataStatus,
  getTradingDayCoverage,
} from "./api";
import { SettingsView } from "./Settings";
import { DataStorageSection } from "./settings/DataStorageSection";
import { withTestUiLocale } from "./test/testUiLocale";

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

function dispose() {
  if (root) act(() => root!.unmount());
  host?.remove();
  root = null;
  host = null;
}

beforeEach(async () => {
  await i18n.changeLanguage("zh-Hant");
  vi.clearAllMocks();
});

afterEach(() => {
  dispose();
  mocked.marketStatus = marketStatus;
  mocked.macroStatus = macroStatus;
  mocked.macroSnapshot = macroSnapshot;
  mocked.marketError = null;
  mocked.macroError = null;
  mocked.macroSnapshotError = null;
  mocked.coverage = coverage;
  mocked.lifecycle = lifecycle;
  mocked.listLifecycleCases.mockReset().mockResolvedValue(lifecycle);
});

async function renderSettings(
  developerMode = false,
  localeController?: UiLocaleController,
) {
  window.localStorage.setItem("arkscope.settings.activeGroup.v1", "data_sync");
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  const view = React.createElement(SettingsView, {
    runtime: null,
    developerMode,
    onRuntimeChanged: vi.fn(),
  });
  await act(async () => {
    root!.render(localeController
      ? React.createElement(LocaleProvider, { controller: localeController, children: view })
      : withTestUiLocale(view));
  });
  await act(async () => { await Promise.resolve(); });
}

async function renderDataStorage(
  settingsReadCache: SettingsReadCache,
  onNavigateTarget = vi.fn(),
) {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(withTestUiLocale(React.createElement(
      DataStorageSection as React.ComponentType<Record<string, unknown>>,
      {
      developerMode: false,
      settingsReadCache,
      onNavigateTarget,
    })));
  });
  await act(async () => { await Promise.resolve(); });
  return { onNavigateTarget };
}

describe("local storage panels", () => {
  it("shows lifecycle storage health and opens the Universe workflow without review actions", async () => {
    const cache = createSettingsReadCache();
    cache.replace("market_data_status", marketStatus);
    cache.replace("security_lifecycle", {
      ...lifecycle,
      cases: [],
      count: 33,
      data_integrity: { source_missing_count: 2 },
    });
    cache.replace(tradingDayCoverageKey(10), coverage);

    const { onNavigateTarget } = await renderDataStorage(cache);
    expect(host!.textContent).toContain("標的事件調查");
    expect(host!.textContent).toContain("33");
    expect(host!.textContent).toContain("2");
    expect(host!.textContent).not.toMatch(/確認關係|確認已下市|標記代號異動|清除覆核/);

    const open = Array.from(host!.querySelectorAll<HTMLButtonElement>("button"))
      .find((button) => button.textContent?.includes("前往全部標的調查"));
    if (!open) throw new Error("missing Universe lifecycle link");
    await act(async () => open.click());
    expect(onNavigateTarget).toHaveBeenCalledWith({ kind: "universe_lifecycle" });
  });

  it("keys_trading_day_coverage_by_lookback_and_forces_only_storage_reads", async () => {
    const cache = createSettingsReadCache();
    const coverage15 = { ...coverage, lookback_days: 15, universe_count: 215 };
    cache.replace("market_data_status", marketStatus);
    cache.replace(tradingDayCoverageKey(10), coverage);
    cache.replace(tradingDayCoverageKey(15), coverage15);
    cache.replace("news_status", { marker: "news" });
    cache.replace("macro_status", { marker: "macro" });
    cache.replace("macro_snapshot", { marker: "snapshot" });

    await renderDataStorage(cache);
    expect(getMarketDataStatus).not.toHaveBeenCalled();
    expect(getTradingDayCoverage).not.toHaveBeenCalled();
    expect(host!.textContent).toContain("149");

    const lookback = host!.querySelector<HTMLSelectElement>("select");
    if (!lookback) throw new Error("missing coverage lookback");
    await act(async () => {
      lookback.value = "15";
      lookback.dispatchEvent(new Event("change", { bubbles: true }));
      await Promise.resolve();
    });
    expect(getTradingDayCoverage).not.toHaveBeenCalled();
    expect(host!.textContent).toContain("215");

    const headings = Array.from(host!.querySelectorAll<HTMLHeadingElement>("h2"));
    const coverageRefresh = headings.find((heading) => heading.textContent?.includes("交易日"))
      ?.closest(".settings-section-head")?.querySelector<HTMLButtonElement>("button");
    const marketRefresh = headings.find((heading) => heading.textContent === "市場資料")
      ?.closest(".settings-section-head")?.querySelector<HTMLButtonElement>("button");
    if (!coverageRefresh || !marketRefresh) throw new Error("missing storage refresh commands");

    mocked.coverage = coverage15;
    await act(async () => {
      coverageRefresh.click();
      await Promise.resolve();
    });
    expect(getTradingDayCoverage).toHaveBeenCalledOnce();
    expect(getTradingDayCoverage).toHaveBeenCalledWith(15, "15min");
    expect(getMarketDataStatus).not.toHaveBeenCalled();

    await act(async () => {
      marketRefresh.click();
      await Promise.resolve();
    });
    expect(getMarketDataStatus).toHaveBeenCalledOnce();
    expect(getTradingDayCoverage).toHaveBeenCalledOnce();
    expect(cache.inspect("news_status").status).toBe("fresh");
    expect(cache.inspect("macro_status").status).toBe("fresh");
    expect(cache.inspect("macro_snapshot").status).toBe("fresh");
  });

  it("reloads_mounted_market_and_coverage_status_after_price_invalidation", async () => {
    const cache = createSettingsReadCache();
    cache.replace("market_data_status", marketStatus);
    cache.replace(tradingDayCoverageKey(10), coverage);
    mocked.marketStatus = {
      ...marketStatus,
      prices: {
        row_count: 2_400_000,
        ticker_count: 151,
        latest_datetime: "2026-08-10T19:45:00+0000",
      },
    };
    mocked.coverage = { ...coverage, universe_count: 151 };

    await renderDataStorage(cache);
    expect(getMarketDataStatus).not.toHaveBeenCalled();
    expect(getTradingDayCoverage).not.toHaveBeenCalled();
    expect(host!.textContent).toContain("2,324,487 列 · 149 檔");

    await act(async () => {
      cache.invalidateDataSource("ibkr_prices");
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(getMarketDataStatus).toHaveBeenCalledOnce();
    expect(getTradingDayCoverage).toHaveBeenCalledOnce();
    expect(host!.textContent).toContain("2,400,000 列 · 151 檔");
    expect(host!.textContent).toContain("151");
  });

  it("shows current market data status from current local facts", async () => {
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

    const storage = host!.querySelector('[data-settings-anchor="data_storage"]');
    expect(storage).not.toBeNull();
    expect(storage!.querySelector("h2")?.textContent).toBe("市場資料");
    expect(storage!.textContent).toContain("價格與新聞的抓取工作由「資料來源與排程」管理");
    expect(storage!.textContent).toContain("基本面資料尚未接入 App 排程");
    expect(storage!.textContent).not.toContain("攝入");
    expect(storage!.textContent).toContain(
      "以正規交易時段的預期 15 分鐘格線比對本地觀測；沒有獨立證據時，未觀測到的格子只標為未知。",
    );
    expect(storage!.textContent).toContain(
      "唯讀診斷；不會啟動修復，也不會產生 planner 工作。",
    );
    expect(storage!.textContent).toContain("美國上市股票代理範圍");
    expect(storage!.textContent).toContain("正規交易時段（RTH）");
    expect(storage!.textContent).toContain("2027-12-31");
    expect(host!.textContent).toContain("價格");
    expect(storage!.textContent).not.toContain("最近增量更新");
    expect(host!.textContent).toContain("已儲存的 SEC 基本面");
    expect(host!.textContent).toContain("財務快取");
    expect(host!.textContent).toContain("市場資料");
  });

  it("shows_macro_data_with_manual_and_scheduled_refresh_boundaries", async () => {
    await renderSettings();

    expect(host!.querySelector('[data-settings-anchor="macro_storage"]')).not.toBeNull();
    expect(host!.textContent).toContain("總經資料");
    expect(host!.textContent).toContain("總經資料排程");
    expect(host!.textContent).toContain(
      "可在下方設定五個資料來源的自動更新排程，或按「立即更新」手動執行",
    );
    expect(host!.textContent).toContain(
      "「重新讀取狀態」只會讀取本機資料，不會向資料供應商抓取資料。",
    );
    expect(host!.textContent).not.toContain("攝入");
    expect(host!.textContent).toContain("FRED 序列");
    expect(host!.textContent).toContain("Fed Funds");
    expect(host!.textContent).toContain("最後抓取");
    expect(host!.textContent).not.toMatch(/Macro \/ Calendar|行事曆|Finnhub 付費方案/);
    expect(host!.textContent).toContain("總經資料");
  });

  it("renders only current local storage panels in normal settings navigation", async () => {
    await renderSettings();

    expect(Array.from(host!.querySelectorAll("h2"), (node) => node.textContent)).toEqual([
      "市場資料",
      "標的事件調查",
      "交易日 / 價格覆蓋",
      "新聞資料",
      "總經資料",
    ]);
  });

  it("lists_the_active_data_group_and_its_stable_subsections", async () => {
    await renderSettings();
    const directory = host!.querySelector('nav[aria-label="設定目錄"]');
    expect(Array.from(directory!.querySelectorAll("button")).map((button) => button.textContent?.trim()))
      .toEqual([
        "資料來源與排程",
        "Provider 健康",
        "SA Extension 健康",
        "連線與金鑰",
        "資料來源排程",
        "市場資料",
        "標的事件調查",
        "交易日 / 價格覆蓋",
        "新聞資料",
        "總經資料",
      ]);
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
  });

  it("renders English market data and storage outcomes", async () => {
    const rawUnknownTicker = "PLANTED_LOCALE_UNKNOWN";
    const localePut = vi.fn(async (locale: "zh-Hant" | "en") => ({
      locale,
      source: "stored" as const,
    }));
    const localeController = createUiLocaleController({
      initialLocale: "zh-Hant",
      authority: {
        get: async () => ({ locale: "zh-Hant", source: "stored" }),
        put: localePut,
      },
      applyLocale: (locale) => {
        void i18n.changeLanguage(locale);
        document.documentElement.lang = locale;
      },
      writeCache: () => true,
    });
    mocked.marketStatus = {
      ...marketStatus,
      sync: {
        prices: {
          last_success: "2026-07-20T01:00:00Z",
          last_error: null,
          rows_added: 11,
          updated_at: "2026-07-20T01:00:01Z",
        },
        news: {
          last_success: "2026-07-20T02:00:00Z",
          last_error: null,
          rows_added: 12,
          updated_at: "2026-07-20T02:00:01Z",
        },
        fundamentals: {
          last_success: "2026-07-20T04:00:00Z",
          last_error: null,
          rows_added: 14,
          updated_at: "2026-07-20T04:00:01Z",
        },
      },
    };
    mocked.coverage = {
      ...coverage,
      calendar_health: {
        ...coverage.calendar_health,
        status: "degraded",
        reason_codes: ["fixture_horizon_low"],
        forward_horizon_months: 5,
      },
      days: [{
        date: "2026-07-18",
        coverage_status: "partial",
        status_reason_code: null,
        closure_reason_code: null,
        session_kind: "regular",
        session_open_at_utc: "2026-07-18T13:30:00+00:00",
        session_close_at_utc: "2026-07-18T20:00:00+00:00",
        expected_slot_count: 26,
        observed_ticker_count: 148,
        complete_ticker_count: 147,
        partial_ticker_count: 1,
        unknown_ticker_count: 1,
        partial_tickers: [{
          ticker: "MSFT",
          observed_slot_count: 12,
          expected_slot_count: 26,
        }],
        unknown_tickers: [rawUnknownTicker],
        unmatched_rth_row_count: 0,
      }],
    };
    await renderSettings(false, localeController);

    const mountedStorage = host!.querySelector('[data-settings-anchor="data_storage"]');
    if (!mountedStorage) throw new Error("missing mounted Market Data section");
    expect(mountedStorage.textContent).toContain(
      "查看已儲存的價格、新聞、SEC 基本面與獨立財務快取。價格與新聞的抓取工作由「資料來源與排程」管理；基本面資料尚未接入 App 排程，本頁只會重新讀取狀態。",
    );
    expect(mountedStorage.textContent).not.toContain("隱含波動率");
    expect(mountedStorage.textContent).not.toContain("最近增量更新");
    expect(mountedStorage.textContent).toContain("2,324,487 列 · 149 檔");
    expect(getMarketDataStatus).toHaveBeenCalledOnce();
    expect(getTradingDayCoverage).toHaveBeenCalledOnce();

    const lookback = mountedStorage.querySelector<HTMLSelectElement>("select");
    if (!lookback) throw new Error("missing coverage lookback input");
    lookback.dataset.identityMarker = "coverage-lookback";
    await act(async () => {
      lookback.value = "30";
      lookback.dispatchEvent(new Event("change", { bubbles: true }));
      await Promise.resolve();
    });
    const mountedCoverageRow = Array.from(
      mountedStorage.querySelectorAll<HTMLTableRowElement>("tbody tr"),
    ).find((row) => row.textContent?.includes("2026-07-18"));
    if (!mountedCoverageRow) throw new Error("missing mounted coverage row");
    const mountedCoverageToggle = mountedCoverageRow.querySelector<HTMLButtonElement>("button");
    if (!mountedCoverageToggle) throw new Error("missing mounted coverage disclosure");
    act(() => mountedCoverageToggle.click());
    expect(mountedStorage.textContent).toContain("部分觀測標的");
    expect(mountedStorage.textContent).not.toContain(rawUnknownTicker);
    const mountedCalendarHealth = mountedStorage.querySelector<HTMLElement>(
      '[data-testid="coverage-calendar-health"]',
    );
    const mountedPartialDetail = Array.from(
      mountedStorage.querySelectorAll<HTMLElement>("tbody p"),
    ).find((node) => node.textContent?.includes("MSFT"));
    if (!mountedCalendarHealth || !mountedPartialDetail) {
      throw new Error("missing coverage locale-purity witnesses");
    }
    mountedCalendarHealth.dataset.identityMarker = "coverage-calendar-health";
    mountedPartialDetail.dataset.identityMarker = "coverage-partial-detail";
    lookback.focus();
    expect(document.activeElement).toBe(lookback);
    expect(getTradingDayCoverage).toHaveBeenCalledTimes(2);

    await act(async () => {
      await localeController.setLocale("en");
      await Promise.resolve();
    });

    const storage = host!.querySelector('[data-settings-anchor="data_storage"]');
    if (!storage) throw new Error("missing Market Data section");
    expect(storage).toBe(mountedStorage);
    expect(storage.querySelector("h2")?.textContent).toBe("Market Data");
    expect(storage.textContent).toContain(
      "Review stored prices, news, SEC fundamentals, and the separate financial cache. Price and news collection is managed under Data Sources and Schedules; fundamentals data is not connected to an App schedule, and this page only reloads status.",
    );
    expect(storage.textContent).not.toContain("implied volatility");
    expect(Array.from(storage.querySelectorAll("dl.ds-kv > dt")).map((node) => node.textContent))
      .toEqual([
        "Market Data",
        "Prices",
        "News",
        "Stored SEC Fundamentals",
        "Financial Cache",
        "Cases with source observations",
        "Cases missing source observations",
        "Universe",
        "Interval",
        "Market scope",
        "Coverage session",
        "Reviewed through",
        "Forward horizon (months)",
      ]);
    expect(storage.textContent).toContain(
      "2,324,487 rows · 149 tickers · latest 2026-07-03T20:00:00+0000",
    );
    expect(storage.textContent).toContain(
      `24 rows (7 valid · 17 expired) · latest fetch ${formatSystemTimestamp("2026-07-01T00:00:00+00:00")}`,
    );
    expect(storage.textContent).not.toContain("Latest Incremental Update");
    expect(storage.textContent).not.toContain("Prices +11");
    expect(storage.textContent).not.toContain("News +12");
    expect(storage.textContent).not.toContain("Fundamentals +14");
    expect(storage.textContent).not.toContain(formatSystemTimestamp("2026-07-20T04:00:00Z"));

    const coverageHeading = Array.from(storage.querySelectorAll("h2")).find((heading) =>
      heading.textContent === "Trading-day / Price Coverage");
    if (!coverageHeading) throw new Error("missing trading-day coverage heading");
    expect(coverageHeading.parentElement?.querySelector("p.muted.tiny")).not.toBeNull();
    expect(coverageHeading.parentElement?.parentElement?.classList.contains("settings-section-head"))
      .toBe(true);
    expect(storage.textContent).toContain("Days");
    expect(storage.textContent).toContain("US-listed equity proxy");
    expect(storage.textContent).toContain("Regular trading hours (RTH)");
    expect(storage.textContent).toContain("2027-12-31");
    expect(storage.textContent).toContain(
      "Compares local observations with the expected 15-minute RTH grid; absent observations remain unknown without independent evidence.",
    );
    expect(storage.textContent).toContain(
      "Read-only diagnostic; does not start a repair or supply planner work.",
    );
    expect(Array.from(storage.querySelectorAll("table"), (table) =>
      Array.from(table.querySelectorAll("th"), (node) => node.textContent)))
      .toEqual([
        ["Date", "Status", "Expected slots", "Complete", "Partial", "Unknown"],
      ]);
    const coverageRow = Array.from(storage.querySelectorAll<HTMLTableRowElement>("tbody tr"))
      .find((row) => row.textContent?.includes("2026-07-18"));
    if (!coverageRow) throw new Error("missing English coverage row");
    expect(coverageRow).toBe(mountedCoverageRow);
    expect(coverageRow.querySelector("button")).toBe(mountedCoverageToggle);
    expect(storage.textContent).toContain("Partially observed tickers");
    expect(storage.textContent).toContain("MSFT: 12/26 slots");
    expect(storage.textContent).toContain("Unresolved tickers");
    expect(Array.from(storage.querySelectorAll("tbody p"), (node) => node.textContent))
      .toContain("1");
    expect(storage.textContent).not.toContain(rawUnknownTicker);
    const switchedLookback = storage.querySelector<HTMLSelectElement>("select");
    expect(switchedLookback).toBe(lookback);
    expect(switchedLookback?.value).toBe("30");
    expect(switchedLookback?.dataset.identityMarker).toBe("coverage-lookback");
    const switchedCalendarHealth = storage.querySelector<HTMLElement>(
      '[data-testid="coverage-calendar-health"]',
    );
    const switchedPartialDetail = Array.from(
      storage.querySelectorAll<HTMLElement>("tbody p"),
    ).find((node) => node.textContent?.includes("MSFT"));
    expect(switchedCalendarHealth).toBe(mountedCalendarHealth);
    expect(switchedCalendarHealth?.dataset.identityMarker).toBe("coverage-calendar-health");
    expect(switchedPartialDetail).toBe(mountedPartialDetail);
    expect(switchedPartialDetail?.dataset.identityMarker).toBe("coverage-partial-detail");
    expect(document.activeElement).toBe(lookback);
    expect(localePut).toHaveBeenCalledOnce();
    expect(localePut).toHaveBeenCalledWith("en");
    expect(getMarketDataStatus).toHaveBeenCalledOnce();
    expect(getTradingDayCoverage).toHaveBeenCalledTimes(2);
    const dataStorageSource = readFileSync(
      resolve(import.meta.dirname, "./settings/DataStorageSection.tsx"),
      "utf8",
    );
    expect(dataStorageSource).toContain("$.dataStorage.coverage.generatedAt");
    expect(dataStorageSource).not.toContain("dataStorage.update");
    expect(dataStorageSource).not.toContain('.join(" · ")');
    expect(dataStorageSource).not.toContain("as unknown as number");
  });

  it("keeps corrected single-locale headings", async () => {
    await renderSettings();

    const storage = host!.querySelector('[data-settings-anchor="data_storage"]');
    const news = host!.querySelector('[data-settings-anchor="news_storage"]');
    const macro = host!.querySelector('[data-settings-anchor="macro_storage"]');
    expect(Array.from(storage?.querySelectorAll("h2") ?? []).map((heading) => heading.textContent))
      .toEqual(["市場資料", "標的事件調查", "交易日 / 價格覆蓋"]);
    expect(Array.from(news?.querySelectorAll("h2") ?? []).map((heading) => heading.textContent))
      .toEqual(["新聞資料"]);
    expect(Array.from(macro?.querySelectorAll("h2") ?? []).map((heading) => heading.textContent))
      .toEqual(["總經資料"]);
  });

  it("scopes coverage diagnostics to Developer Mode", async () => {
    const syncDiagnostic = "RAW_MARKET_SYNC_DETAIL";
    const providerDiagnostic = "RAW_COVERAGE_PROVIDER_DETAIL";
    const unknownTickers = ["PLANTED_UNKNOWN_A", "PLANTED_UNKNOWN_B"];
    mocked.marketStatus = {
      ...marketStatus,
      sync: {
        ...marketStatus.sync,
        prices: {
          last_success: null,
          last_error: syncDiagnostic,
          rows_added: 0,
          updated_at: "2026-07-20T03:00:00Z",
        },
      },
    };
    mocked.coverage = {
      ...coverage,
      observation_health: {
        status: "unavailable",
        reason_code: "market_db_unreadable",
      },
      days: [{
        date: "2026-07-18",
        coverage_status: "unknown",
        status_reason_code: "observation_unavailable",
        closure_reason_code: null,
        session_kind: null,
        session_open_at_utc: null,
        session_close_at_utc: null,
        expected_slot_count: null,
        observed_ticker_count: null,
        complete_ticker_count: null,
        partial_ticker_count: null,
        unknown_ticker_count: unknownTickers.length,
        partial_tickers: [],
        unknown_tickers: unknownTickers,
        unmatched_rth_row_count: null,
      }],
      provider_errors: [{
        ticker: "AAPL",
        interval: "15min",
        last_error: providerDiagnostic,
        reason_code: "unknown",
        updated_at: "2026-07-20T03:00:00Z",
      }],
    };

    await renderSettings(false);
    expect(host!.textContent).not.toContain("增量更新失敗");
    expect(host!.textContent).toContain("市場資料庫無法讀取");
    expect(host!.textContent).toContain("觀測資料無法使用");
    expect(host!.textContent).toContain("供應商問題：1");
    expect(host!.textContent).not.toContain(syncDiagnostic);
    expect(host!.textContent).not.toContain(providerDiagnostic);
    for (const ticker of unknownTickers) expect(host!.textContent).not.toContain(ticker);
    expect(host!.querySelector('[data-testid="developer-diagnostics"]')).toBeNull();

    dispose();
    await renderSettings(true);
    const diagnosticsOwners = Array.from(
      host!.querySelectorAll<HTMLElement>('[data-testid="developer-diagnostics"]'),
    );
    const coverageDiagnostics = diagnosticsOwners.find((owner) =>
      owner.textContent?.includes(providerDiagnostic));
    expect(coverageDiagnostics).toBeDefined();
    expect(coverageDiagnostics?.textContent).toContain(
      `2026-07-18: ${unknownTickers.join(", ")}`,
    );
    expect(host!.textContent).not.toContain(syncDiagnostic);
    expect(host!.textContent).toContain(providerDiagnostic);
    expect(getMarketDataStatus).toHaveBeenCalledTimes(2);
    expect(getTradingDayCoverage).toHaveBeenCalledTimes(2);
  });

  it("keeps calendar degradation separate from reviewed-day coverage", async () => {
    mocked.coverage = {
      version: 2,
      market_scope: "us_listed_equity_proxy",
      coverage_session: "rth",
      interval: "15min",
      lookback_days: 10,
      universe_count: 2,
      generated_at_et: "2026-07-24T16:30:00-04:00",
      calendar_health: {
        status: "degraded",
        reason_codes: ["fixture_horizon_low"],
        reviewed_through: "2027-12-31",
        forward_horizon_months: 5,
      },
      observation_health: { status: "ok", reason_code: null },
      days: [{
        date: "2026-07-24",
        coverage_status: "complete",
        status_reason_code: null,
        closure_reason_code: null,
        session_kind: "regular",
        session_open_at_utc: "2026-07-24T13:30:00+00:00",
        session_close_at_utc: "2026-07-24T20:00:00+00:00",
        expected_slot_count: 26,
        observed_ticker_count: 2,
        complete_ticker_count: 2,
        partial_ticker_count: 0,
        unknown_ticker_count: 0,
        partial_tickers: [],
        unknown_tickers: [],
        unmatched_rth_row_count: 0,
      }],
      provider_errors: [],
    };

    await renderSettings();

    const storage = host!.querySelector('[data-settings-anchor="data_storage"]');
    const dayRow = Array.from(storage!.querySelectorAll("tbody tr")).find((row) =>
      row.textContent?.includes("2026-07-24"));
    expect(dayRow?.textContent).toContain("完整");
    expect(storage!.textContent).toContain("已審日曆的前瞻範圍不足");
    expect(storage!.textContent).toContain("已審至 2027-12-31");
  });

  it("keeps unmatched rows and provider issues separate from coverage state", async () => {
    const rawProviderDetail = "PLANTED_PROVIDER_DETAIL";
    const rawUnknownTickers = ["PLANTED_DAY_UNKNOWN_A", "PLANTED_DAY_UNKNOWN_B"];
    mocked.coverage = {
      version: 2,
      market_scope: "us_listed_equity_proxy",
      coverage_session: "rth",
      interval: "15min",
      lookback_days: 10,
      universe_count: 3,
      generated_at_et: "2026-07-24T16:30:00-04:00",
      calendar_health: {
        status: "ok",
        reason_codes: [],
        reviewed_through: "2027-12-31",
        forward_horizon_months: 17,
      },
      observation_health: { status: "ok", reason_code: null },
      days: [
        {
          date: "2026-07-24",
          coverage_status: "partial",
          status_reason_code: null,
          closure_reason_code: null,
          session_kind: "regular",
          session_open_at_utc: "2026-07-24T13:30:00+00:00",
          session_close_at_utc: "2026-07-24T20:00:00+00:00",
          expected_slot_count: 26,
          observed_ticker_count: 2,
          complete_ticker_count: 1,
          partial_ticker_count: 1,
          unknown_ticker_count: 1,
          partial_tickers: [{
            ticker: "MSFT",
            observed_slot_count: 12,
            expected_slot_count: 26,
          }],
          unknown_tickers: [rawUnknownTickers[0]],
          unmatched_rth_row_count: 2,
        },
        {
          date: "2026-07-23",
          coverage_status: "indeterminate_tickers",
          status_reason_code: null,
          closure_reason_code: null,
          session_kind: "regular",
          session_open_at_utc: "2026-07-23T13:30:00+00:00",
          session_close_at_utc: "2026-07-23T20:00:00+00:00",
          expected_slot_count: 26,
          observed_ticker_count: 2,
          complete_ticker_count: 2,
          partial_ticker_count: 0,
          unknown_ticker_count: 1,
          partial_tickers: [],
          unknown_tickers: [rawUnknownTickers[1]],
          unmatched_rth_row_count: 0,
        },
      ],
      provider_errors: [{
        ticker: "AAPL",
        interval: "15min",
        last_error: rawProviderDetail,
        reason_code: "unknown",
        updated_at: "2026-07-24T20:05:00+00:00",
      }],
    };

    await renderSettings(false);

    const storage = host!.querySelector('[data-settings-anchor="data_storage"]');
    const dayRow = Array.from(storage!.querySelectorAll<HTMLTableRowElement>("tbody tr")).find(
      (row) => row.textContent?.includes("2026-07-24"),
    );
    if (!dayRow) throw new Error("missing Coverage v2 day row");
    expect(dayRow.textContent).toContain("部分");
    expect(storage!.textContent).toContain("部分標的未能判定");
    const disclosure = dayRow.querySelector<HTMLButtonElement>('button[aria-expanded="false"]');
    if (!disclosure) throw new Error("missing Coverage v2 disclosure button");
    expect(disclosure.type).toBe("button");
    expect(disclosure.tabIndex).toBe(0);
    disclosure.focus();
    expect(document.activeElement).toBe(disclosure);
    const detailId = disclosure.getAttribute("aria-controls");
    expect(detailId).toBeTruthy();
    act(() => disclosure.click());
    expect(disclosure.getAttribute("aria-expanded")).toBe("true");
    const detail = document.getElementById(detailId!);
    expect(detail).not.toBeNull();
    expect(storage!.textContent).toContain("部分觀測標的");
    expect(storage!.textContent).toContain("MSFT：12/26 格");
    expect(storage!.textContent).toContain("未能判定的標的");
    expect(Array.from(detail!.querySelectorAll("p"), (node) => node.textContent)).toContain("1");
    for (const ticker of rawUnknownTickers) {
      expect(storage!.textContent).not.toContain(ticker);
    }
    expect(storage!.textContent).toContain("格線外的正規交易時段資料列：2");
    expect(storage!.textContent).toContain("供應商問題：1");
    expect(storage!.textContent).not.toContain(rawProviderDetail);
    act(() => disclosure.click());
    expect(disclosure.getAttribute("aria-expanded")).toBe("false");
    expect(document.getElementById(detailId!)).toBeNull();
  });
});
