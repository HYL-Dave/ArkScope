/** @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import i18n from "i18next";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  FinancialStatement,
  FundamentalsResult,
  IVAnalysis,
  IVHistoryResult,
  MarketDataCoverage,
  MarketDataStatus,
  Note,
  PriceChange,
  SourcePath,
  TagRef,
  TickerAggregate,
} from "./api";
import type { NavigationTarget } from "./shell/navigation";

const apiMocks = vi.hoisted(() => ({
  addNote: vi.fn(),
  addTickerTag: vi.fn(),
  deleteNote: vi.fn(),
  getIvAnalysis: vi.fn(),
  getIvHistory: vi.fn(),
  getMarketDataCoverage: vi.fn(),
  getMarketDataStatus: vi.fn(),
  getNotes: vi.fn(),
  getPriceChange: vi.fn(),
  getStoredFundamentals: vi.fn(),
  getTagCatalog: vi.fn(),
  getTickerState: vi.fn(),
  removeTickerTag: vi.fn(),
}));

vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return { ...actual, ...apiMocks };
});

vi.mock("./AICard", () => ({
  AICardTab: ({ ticker }: { ticker: string }) => <div>AI CARD SOURCE {ticker}</div>,
}));

import { TickerDetailView } from "./TickerDetail";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

const TICKER = "SRC.TW";
const SOURCE_LIST = '來源清單 <img src="x" onerror="source-leak">';
const SOURCE_TAG_VALUE = "SOURCE/TAG 原值 <keep>";
const SOURCE_TAG_SOURCE = "provider:raw/v9";
const SOURCE_DATE_RANGE = "SOURCE_DATE_RANGE_NOT_LOCALIZED";
const SOURCE_NOTE_BODY = "SOURCE NOTE / 原文 <keep>";
const SOURCE_SIGNAL = "SOURCE_SIGNAL_V9";
const SOURCE_FUNDAMENTAL_PROVIDER = "provider/source-fundamentals";
const SOURCE_ROW = "SOURCE Revenue / 營收 <keep>";
const SOURCE_NEWER_STATE_LIST = "SOURCE NEWER STATE LIST / 保留";
const SOURCE_NEWER_NOTE_BODY = "SOURCE NEWER NOTE READ / 保留";
const SOURCE_NEWER_TAG_VALUE = "SOURCE NEWER TAG CATALOG / 保留";
const UNKNOWN_SOURCE_PATH = "future_source_v9";
const RAW_ERROR = "RAW postgres://admin:secret@10.0.0.8/ticker";
const RAW_DIAGNOSTIC = "Authorization: Bearer sk-private\nTraceback /srv/private.py:42";

const ZH_OVERVIEW_KV_LABELS = [
  "最新收盤價",
  "漲跌幅",
  "區間高點",
  "區間低點",
  "區間振幅",
  "成交量",
  "K 線筆數",
  "日期範圍",
] as const;
const EN_OVERVIEW_KV_LABELS = [
  "Latest close",
  "Change %",
  "Period high",
  "Period low",
  "Range %",
  "Volume",
  "Bars",
  "Dates",
] as const;
const ZH_DATA_KV_LABELS = [
  "目前 ATM IV",
  "HV 30d",
  "VRP (IV−HV)",
  "IV rank",
  "IV percentile",
  "Spot",
  "歷史天數",
  "快照日期",
  "市值",
  "P/E",
  "Forward P/E",
  "P/S",
  "P/B",
  "ROE",
  "ROA",
  "D/E",
  "流動比率",
  "毛利率",
  "營業利益率",
  "淨利率",
  "營收成長",
  "獲利成長",
  "股息殖利率",
  "Beta",
  "自由現金流",
  "現金及約當現金",
  "總債務",
] as const;
const EN_DATA_KV_LABELS = [
  "Current ATM IV",
  "HV 30d",
  "VRP (IV−HV)",
  "IV rank",
  "IV percentile",
  "Spot",
  "History days",
  "Snapshot date",
  "Market cap",
  "P/E",
  "Forward P/E",
  "P/S",
  "P/B",
  "ROE",
  "ROA",
  "D/E",
  "Current ratio",
  "Gross margin",
  "Operating margin",
  "Net margin",
  "Revenue growth",
  "Earnings growth",
  "Dividend yield",
  "Beta",
  "Free cash flow",
  "Cash & equiv.",
  "Total debt",
] as const;

const USER_TAG: TagRef = {
  facet: "theme",
  value: SOURCE_TAG_VALUE,
  source: "user",
};

const STATE: TickerAggregate = {
  ticker: TICKER,
  lists: [SOURCE_LIST],
  list_ids: [41],
  archived: true,
  note_count: 2,
  priority: "source-priority/raw",
  tags: [
    USER_TAG,
    { facet: "source_custom_axis", value: "UNKNOWN TAG VALUE", source: SOURCE_TAG_SOURCE },
  ],
};

const PRICE: PriceChange = {
  ticker: TICKER,
  days: 30,
  bar_count: 17,
  latest_close: 1234.56,
  period_open: 1100,
  change_pct: 12.25,
  period_high: 1300,
  period_low: 1000,
  high_low_range_pct: 30,
  total_volume: 987654,
  date_range: SOURCE_DATE_RANGE,
};

const IV: IVAnalysis = {
  ticker: TICKER,
  current_iv: 0.42,
  hv_30d: 0.31,
  vrp: 0.11,
  iv_rank: 77,
  iv_percentile: 81,
  spot_price: 1234.56,
  history_days: 2,
  signal: SOURCE_SIGNAL,
  source_path: "local",
};

const IV_HISTORY: IVHistoryResult = {
  source_path: "file",
  points: [
    {
      date: "SOURCE_HISTORY_DATE",
      atm_iv: 0.42,
      hv_30d: 0.31,
      vrp: 0.11,
      spot_price: 1234.56,
      num_quotes: 29,
    },
  ],
};

const STATEMENT: FinancialStatement = {
  report_period: "SOURCE_REPORT_PERIOD",
  fiscal_period: "SOURCE_FISCAL_PERIOD",
  period_type: "source-period-type",
  data: { [SOURCE_ROW]: 7654321 },
};

const FUNDAMENTALS: FundamentalsResult = {
  ticker: TICKER,
  snapshot_date: "SOURCE_SNAPSHOT_DATE",
  data_source: SOURCE_FUNDAMENTAL_PROVIDER,
  market_cap: 1000000,
  pe_ratio: 21,
  forward_pe: 18,
  ps_ratio: 5,
  pb_ratio: 4,
  roe: 0.22,
  roa: 0.12,
  debt_to_equity: 0.3,
  current_ratio: 1.8,
  revenue_growth: 0.2,
  earnings_growth: 0.3,
  dividend_yield: 0.01,
  beta: 1.1,
  gross_margin: 0.6,
  operating_margin: 0.4,
  net_margin: 0.3,
  free_cash_flow: 500000,
  cash_and_equivalents: 250000,
  total_debt: 100000,
  income_statements: [STATEMENT],
  balance_sheet: [{ ...STATEMENT, data: { "SOURCE Total assets / 資產": 999 } }],
  cash_flow_statements: [{ ...STATEMENT, data: { "SOURCE Free cash flow / 現金": 888 } }],
  snapshot: { SOURCE_SNAPSHOT_KEY: "SOURCE_SNAPSHOT_VALUE" },
  source_path: "pg_fallback",
};

const COVERAGE: MarketDataCoverage = {
  exists: true,
  prices: true,
  news: true,
  iv: true,
  fundamentals: false,
};

const STATUS: MarketDataStatus = {
  market_db: "SOURCE_MARKET_DB_PATH",
  exists: true,
  prices: { row_count: 1, ticker_count: 1, latest_datetime: "SOURCE_PRICE_TIME" },
  news: { row_count: 1, source_count: 1, latest_published: "SOURCE_NEWS_TIME" },
  iv: { row_count: 1, ticker_count: 1, latest_date: "SOURCE_IV_DATE" },
  fundamentals: { row_count: 1, ticker_count: 1, latest_date: "SOURCE_FUND_DATE" },
  financial_cache: { row_count: 1, valid_count: 1, expired_count: 0, latest_fetched_at: "SOURCE_FETCH_TIME" },
  sync: { prices: null, news: null, iv: null, fundamentals: null },
  use_local_market_setting: true,
  env_override: false,
  local_market_strict_setting: false,
  strict_env_override: false,
  strict_enabled: false,
  routing_enabled: true,
  pg_fallback_active: true,
};

const NOTES: Note[] = [
  {
    id: 71,
    ticker: TICKER,
    body: SOURCE_NOTE_BODY,
    created_at: "SOURCE_CREATED_AT",
    updated_at: "SOURCE_UPDATED_AT",
  },
];

type RequestName = keyof typeof apiMocks;

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

function structuredError(
  code = "ticker_fixture_failed",
  path = `/profile/tickers/${TICKER}/state?token=private#fragment`,
  diagnostic = RAW_DIAGNOSTIC,
) {
  return Object.assign(new Error(RAW_ERROR), {
    status: 503,
    code,
    path,
    diagnostic,
  });
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

async function flush(delay = 0) {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, delay));
  });
}

async function waitForCalls(mock: ReturnType<typeof vi.fn>, count: number) {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    if (mock.mock.calls.length >= count) {
      await flush();
      return;
    }
    await flush();
  }
  throw new Error(`expected ${count} calls, received ${mock.mock.calls.length}`);
}

async function waitForText(text: string) {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    if (host?.textContent?.includes(text)) return;
    await flush();
  }
  throw new Error(`text not found: ${text}; rendered=${host?.textContent ?? ""}`);
}

async function click(element: Element) {
  await act(async () => {
    element.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    await Promise.resolve();
  });
  await flush();
}

async function setInput(input: HTMLInputElement | HTMLTextAreaElement, value: string) {
  const prototype = input instanceof HTMLTextAreaElement
    ? HTMLTextAreaElement.prototype
    : HTMLInputElement.prototype;
  await act(async () => {
    Object.getOwnPropertyDescriptor(prototype, "value")?.set?.call(input, value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await flush();
}

async function setSelect(select: HTMLSelectElement, value: string) {
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value")?.set?.call(select, value);
    select.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await flush();
}

function kvLabelNodes(): HTMLElement[] {
  return Array.from(host!.querySelectorAll<HTMLElement>(".kv dt"));
}

function expectKvLabels(expected: readonly string[]) {
  expect(kvLabelNodes().map((node) => node.textContent)).toEqual(
    expect.arrayContaining([...expected]),
  );
}

function buttonByText(text: string, scope: ParentNode = host!): HTMLButtonElement {
  const match = Array.from(scope.querySelectorAll<HTMLButtonElement>("button"))
    .find((button) => button.textContent?.includes(text));
  if (!match) throw new Error(`button not found: ${text}; rendered=${scope.textContent ?? ""}`);
  return match;
}

function unmountTicker() {
  if (root) act(() => root!.unmount());
  root = null;
  host?.remove();
  host = null;
}

async function mountTicker({
  developerMode = false,
  onNavigateTarget = vi.fn(),
}: {
  developerMode?: boolean;
  onNavigateTarget?: (target: NavigationTarget) => void;
} = {}) {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(
      <TickerDetailView
        ticker={TICKER}
        onBack={vi.fn()}
        developerMode={developerMode}
        onNavigateTarget={onNavigateTarget}
      />,
    );
    await Promise.resolve();
  });
  await flush();
  return { onNavigateTarget };
}

async function switchLocale(locale: "zh-Hant" | "en") {
  await act(async () => {
    await i18n.changeLanguage(locale);
  });
  await flush();
}

function requestCounts(): Record<RequestName, number> {
  return Object.fromEntries(
    Object.entries(apiMocks).map(([name, mock]) => [name, mock.mock.calls.length]),
  ) as Record<RequestName, number>;
}

beforeEach(async () => {
  await i18n.changeLanguage("zh-Hant");
  document.documentElement.lang = "zh-Hant";
  apiMocks.getTickerState.mockReset().mockResolvedValue(STATE);
  apiMocks.getPriceChange.mockReset().mockResolvedValue(PRICE);
  apiMocks.getIvAnalysis.mockReset().mockResolvedValue(IV);
  apiMocks.getIvHistory.mockReset().mockResolvedValue(IV_HISTORY);
  apiMocks.getStoredFundamentals.mockReset().mockResolvedValue(FUNDAMENTALS);
  apiMocks.getMarketDataStatus.mockReset().mockResolvedValue(STATUS);
  apiMocks.getMarketDataCoverage.mockReset().mockResolvedValue(COVERAGE);
  apiMocks.getTagCatalog.mockReset().mockResolvedValue({
    catalog: { theme: [SOURCE_TAG_VALUE], category: ["SOURCE CATEGORY"] },
  });
  apiMocks.getNotes.mockReset().mockResolvedValue({ ticker: TICKER, notes: NOTES });
  apiMocks.addNote.mockReset().mockResolvedValue(NOTES[0]);
  apiMocks.deleteNote.mockReset().mockResolvedValue({ deleted: true, id: NOTES[0]!.id });
  apiMocks.addTickerTag.mockReset().mockResolvedValue(STATE);
  apiMocks.removeTickerTag.mockReset().mockResolvedValue({
    removed: true,
    ticker: TICKER,
    facet: USER_TAG.facet,
    value: USER_TAG.value,
    source: USER_TAG.source,
  });
});

afterEach(() => {
  unmountTicker();
});

describe("Ticker Detail localization", () => {
  it("renders reviewed zh-Hant ticker chrome and planted source values", async () => {
    await mountTicker();
    await waitForText(SOURCE_DATE_RANGE);

    const overviewText = host!.textContent ?? "";
    for (const expected of [
      "← 自選股",
      "已封存",
      "總覽",
      "數據",
      "筆記（2）",
      "AI 卡片",
      "價格 (30D)",
      "圖表（價格 / 成交量）",
      "價格 / 成交量 / 區間 / 多窗報酬",
      TICKER,
      SOURCE_LIST,
      SOURCE_TAG_VALUE,
      "UNKNOWN TAG VALUE",
      "source-priority/raw",
      SOURCE_DATE_RANGE,
    ]) {
      expect(overviewText).toContain(expected);
    }
    expect(kvLabelNodes().map((node) => node.textContent)).toEqual(ZH_OVERVIEW_KV_LABELS);

    await click(buttonByText("數據"));
    await waitForText(SOURCE_ROW);
    expectKvLabels(ZH_DATA_KV_LABELS);
    expect(host!.textContent).toContain("IV 歷史（最近 1 筆 · 來源 本地檔案）");
    expect(host!.textContent).toContain("損益表（1 期）");
    expect(host!.textContent).toContain("資產負債表（1 期）");
    expect(host!.textContent).toContain("現金流量表（1 期）");
    expect(host!.textContent).toContain(SOURCE_FUNDAMENTAL_PROVIDER);
    expect(host!.textContent).toContain(SOURCE_SIGNAL);
    expect(host!.querySelector("img")).toBeNull();
    expect(apiMocks.getTickerState).toHaveBeenCalledWith(TICKER);
    expect(apiMocks.getPriceChange).toHaveBeenCalledWith(TICKER, 30);
  });

  it("renders English ticker chrome without translating financial statement rows", async () => {
    await mountTicker();
    await waitForText(SOURCE_DATE_RANGE);
    const overviewNodes = kvLabelNodes();
    expect(overviewNodes.map((node) => node.textContent)).toEqual(ZH_OVERVIEW_KV_LABELS);
    const beforeOverviewSwitch = requestCounts();

    await switchLocale("en");
    expect(kvLabelNodes().every((node, index) => node === overviewNodes[index])).toBe(true);
    expect(overviewNodes.map((node) => node.textContent)).toEqual(EN_OVERVIEW_KV_LABELS);
    expect(requestCounts()).toEqual(beforeOverviewSwitch);

    await click(buttonByText("Data"));
    await waitForText(SOURCE_ROW);
    const dataNodes = kvLabelNodes().slice(-EN_DATA_KV_LABELS.length);
    expect(dataNodes.map((node) => node.textContent)).toEqual(EN_DATA_KV_LABELS);
    const beforeDataSwitch = requestCounts();

    await switchLocale("zh-Hant");
    expect(kvLabelNodes().slice(-ZH_DATA_KV_LABELS.length)
      .every((node, index) => node === dataNodes[index])).toBe(true);
    expect(dataNodes.map((node) => node.textContent)).toEqual(ZH_DATA_KV_LABELS);

    await switchLocale("en");
    expect(kvLabelNodes().slice(-EN_DATA_KV_LABELS.length)
      .every((node, index) => node === dataNodes[index])).toBe(true);
    expect(dataNodes.map((node) => node.textContent)).toEqual(EN_DATA_KV_LABELS);
    expect(requestCounts()).toEqual(beforeDataSwitch);

    const text = host!.textContent ?? "";
    for (const expected of [
      "← Watchlist",
      "Overview",
      "Data",
      "Notes(2)",
      "AI Card",
      "Data source / freshness",
      "Implied volatility (IV)",
      "Fundamentals",
      "Income statements",
      "Balance sheet",
      "Cash flow",
      "IV history (latest 1 row · Source Local file)",
      "Income statements (1 period)",
      "Balance sheet (1 period)",
      "Cash flow (1 period)",
      SOURCE_ROW,
      "SOURCE Total assets / 資產",
      "SOURCE Free cash flow / 現金",
      SOURCE_FUNDAMENTAL_PROVIDER,
      SOURCE_SIGNAL,
    ]) {
      expect(text).toContain(expected);
    }
    expect(text).not.toContain("來源列已翻譯");
  });

  it("renders ticker-state failure by operation without raw detail", async () => {
    const olderRetry = deferred<TickerAggregate>();
    const newerRetry = deferred<TickerAggregate>();
    apiMocks.getTickerState.mockReset()
      .mockRejectedValueOnce(structuredError())
      .mockReturnValueOnce(olderRetry.promise)
      .mockReturnValueOnce(newerRetry.promise)
      .mockResolvedValue(STATE);
    await mountTicker();
    await waitForCalls(apiMocks.getTickerState, 1);

    const alert = host!.querySelector<HTMLElement>('[role="alert"]')!;
    expect(alert?.querySelector(".ui-status-badge")?.textContent).toBe("無法載入標的詳情。");
    expect(alert?.textContent).toContain("重試");
    expect(host!.textContent).not.toContain(RAW_ERROR);
    expect(host!.textContent).not.toContain("sk-private");
    expect(host!.textContent).toContain(TICKER);

    await click(buttonByText("重試", alert));
    await waitForCalls(apiMocks.getTickerState, 2);
    await click(buttonByText("重試", alert));
    await waitForCalls(apiMocks.getTickerState, 3);
    await act(async () => {
      newerRetry.resolve({ ...STATE, lists: [SOURCE_NEWER_STATE_LIST] });
      await newerRetry.promise;
    });
    await waitForText(SOURCE_NEWER_STATE_LIST);
    await act(async () => {
      olderRetry.reject(structuredError("stale_ticker_state_failure"));
      await olderRetry.promise.catch(() => undefined);
    });
    await flush();

    expect(host!.textContent).toContain(SOURCE_NEWER_STATE_LIST);
    expect(Array.from(host!.querySelectorAll("[role=alert] .ui-status-badge"))
      .map((node) => node.textContent)).not.toContain("無法載入標的詳情。");
    expect(apiMocks.getTickerState).toHaveBeenCalledTimes(3);
  });

  it("renders price failure independently from successful detail state", async () => {
    apiMocks.getPriceChange.mockRejectedValueOnce(
      structuredError("price_fixture_failed", `/prices/${TICKER}/change?days=30`),
    );
    await mountTicker();
    await waitForCalls(apiMocks.getPriceChange, 1);

    const alert = host!.querySelector('[role="alert"]');
    expect(alert?.querySelector(".ui-status-badge")?.textContent).toBe("無法載入價格概覽。");
    expect(host!.textContent).toContain(SOURCE_LIST);
    expect(host!.textContent).toContain(SOURCE_TAG_VALUE);
    expect(host!.textContent).not.toContain(RAW_ERROR);
    expect(apiMocks.getTickerState).toHaveBeenCalledTimes(1);
  });

  it("preserves successful legs while naming IV history fundamentals status and coverage failures", async () => {
    apiMocks.getIvHistory.mockRejectedValueOnce(
      structuredError("iv_history_failed", `/options/${TICKER}/history`),
    );
    apiMocks.getStoredFundamentals.mockRejectedValueOnce(
      structuredError("fundamentals_failed", `/fundamentals/${TICKER}?stored=true`),
    );
    apiMocks.getMarketDataStatus.mockRejectedValueOnce(
      structuredError("market_status_failed", "/market-data/status"),
    );
    apiMocks.getMarketDataCoverage.mockRejectedValueOnce(
      structuredError("coverage_failed", `/market-data/coverage/${TICKER}`),
    );
    await mountTicker();
    await click(buttonByText("數據"));
    await waitForCalls(apiMocks.getMarketDataCoverage, 1);

    const titles = Array.from(host!.querySelectorAll('[role="alert"] .ui-status-badge'))
      .map((node) => node.textContent);
    expect(titles).toEqual([
      "無法載入 IV 歷史。",
      "無法載入基本面。",
      "無法載入市場資料狀態。",
      "無法載入市場資料覆蓋。",
    ]);
    expect(host!.textContent).toContain("0.42");
    expect(host!.textContent).toContain(SOURCE_SIGNAL);
    expect(host!.textContent).not.toContain(RAW_ERROR);
  });

  it("maps reviewed source-path enums and preserves unknown stable IDs", async () => {
    apiMocks.getIvAnalysis.mockResolvedValueOnce({ ...IV, source_path: "local" });
    apiMocks.getIvHistory.mockResolvedValueOnce({ ...IV_HISTORY, source_path: "file" });
    apiMocks.getStoredFundamentals.mockResolvedValueOnce({ ...FUNDAMENTALS, source_path: "pg_fallback" });
    await mountTicker();
    await click(buttonByText("數據"));
    await waitForCalls(apiMocks.getMarketDataCoverage, 1);
    expect(host!.textContent).toContain("本地");
    expect(host!.textContent).toContain("本地檔案");
    expect(host!.textContent).toContain("PG（本地缺→回退）");

    unmountTicker();
    apiMocks.getIvAnalysis.mockResolvedValueOnce({ ...IV, source_path: "pg" });
    apiMocks.getIvHistory.mockResolvedValueOnce({ ...IV_HISTORY, source_path: "none" });
    apiMocks.getStoredFundamentals.mockResolvedValueOnce({
      ...FUNDAMENTALS,
      source_path: UNKNOWN_SOURCE_PATH as SourcePath,
    });
    await mountTicker();
    await click(buttonByText("數據"));
    await waitForCalls(apiMocks.getMarketDataCoverage, 2);
    expect(host!.textContent).toContain("PG");
    expect(host!.textContent).toContain("無資料");
    expect(host!.textContent).toContain(UNKNOWN_SOURCE_PATH);

    await switchLocale("en");
    expect(host!.textContent).toContain("No data");
    expect(host!.textContent).toContain(UNKNOWN_SOURCE_PATH);
  });

  it("switches locale without resetting the active tab day window data or focus", async () => {
    await mountTicker();
    const main = host!.querySelector<HTMLElement>("main");
    const windowButton = buttonByText("90D");
    await click(windowButton);
    await waitForCalls(apiMocks.getPriceChange, 2);
    const priceValue = Array.from(host!.querySelectorAll("dd"))
      .find((node) => node.textContent?.includes("1,234.56"));
    const overviewButton = buttonByText("總覽");
    main!.scrollTop = 237;
    windowButton.focus();
    const before = requestCounts();

    await switchLocale("en");

    expect(host!.querySelector("main")).toBe(main);
    expect(overviewButton.textContent).toBe("Overview");
    expect(buttonByText("90D")).toBe(windowButton);
    expect(windowButton.classList.contains("active")).toBe(true);
    expect(document.activeElement).toBe(windowButton);
    expect(main!.scrollTop).toBe(237);
    expect(Array.from(host!.querySelectorAll("dd"))
      .find((node) => node.textContent?.includes("1,234.56"))).toBe(priceValue);
    expect(requestCounts()).toEqual(before);
    expect(apiMocks.getPriceChange.mock.calls).toEqual([[TICKER, 30], [TICKER, 90]]);
  });

  it("preserves note draft and maps note load add and delete failures separately", async () => {
    const olderRetry = deferred<{ ticker: string; notes: Note[] }>();
    const newerRetry = deferred<{ ticker: string; notes: Note[] }>();
    apiMocks.getNotes.mockReset()
      .mockRejectedValueOnce(
        structuredError("notes_load_failed", `/profile/tickers/${TICKER}/notes`),
      )
      .mockReturnValueOnce(olderRetry.promise)
      .mockReturnValueOnce(newerRetry.promise)
      .mockResolvedValue({ ticker: TICKER, notes: NOTES });
    await mountTicker();
    await click(buttonByText("筆記"));
    await waitForCalls(apiMocks.getNotes, 1);
    expect(host!.querySelector('[role="alert"] .ui-status-badge')?.textContent)
      .toBe("無法載入筆記。");

    const draft = host!.querySelector<HTMLTextAreaElement>("textarea")!;
    await setInput(draft, "SOURCE NOTE DRAFT / 保留");
    await click(buttonByText("重試"));
    await waitForCalls(apiMocks.getNotes, 2);
    await click(buttonByText("重試"));
    await waitForCalls(apiMocks.getNotes, 3);
    await act(async () => {
      newerRetry.resolve({
        ticker: TICKER,
        notes: [{ ...NOTES[0]!, body: SOURCE_NEWER_NOTE_BODY }],
      });
      await newerRetry.promise;
    });
    await waitForText(SOURCE_NEWER_NOTE_BODY);
    await act(async () => {
      olderRetry.reject(structuredError("stale_notes_load_failure"));
      await olderRetry.promise.catch(() => undefined);
    });
    await flush();

    expect(host!.textContent).toContain(SOURCE_NEWER_NOTE_BODY);
    expect(Array.from(host!.querySelectorAll("[role=alert] .ui-status-badge"))
      .map((node) => node.textContent)).not.toContain("無法載入筆記。");
    expect(draft.value).toBe("SOURCE NOTE DRAFT / 保留");

    apiMocks.addNote.mockRejectedValueOnce(
      structuredError("note_add_failed", `/profile/tickers/${TICKER}/notes`),
    );
    await click(buttonByText("新增筆記"));
    await waitForCalls(apiMocks.addNote, 1);
    expect(host!.querySelector('[role="alert"] .ui-status-badge')?.textContent)
      .toBe("無法新增筆記。");
    expect(draft.value).toBe("SOURCE NOTE DRAFT / 保留");
    expect(apiMocks.addNote).toHaveBeenCalledWith(TICKER, "SOURCE NOTE DRAFT / 保留");

    await setInput(draft, "SOURCE NEWER NOTE EDIT / 保留");
    await click(buttonByText("重試"));
    await waitForCalls(apiMocks.addNote, 2);
    expect(apiMocks.addNote.mock.calls).toEqual([
      [TICKER, "SOURCE NOTE DRAFT / 保留"],
      [TICKER, "SOURCE NOTE DRAFT / 保留"],
    ]);
    expect(draft.value).toBe("SOURCE NEWER NOTE EDIT / 保留");

    apiMocks.deleteNote.mockRejectedValueOnce(
      structuredError("note_delete_failed", `/profile/tickers/${TICKER}/notes/71`),
    );
    const deleteButton = host!.querySelector<HTMLButtonElement>('button[title="刪除筆記"]')!;
    await click(deleteButton);
    await waitForCalls(apiMocks.deleteNote, 1);
    expect(host!.querySelector('[role="alert"] .ui-status-badge')?.textContent)
      .toBe("無法刪除筆記。");
    expect(draft.value).toBe("SOURCE NEWER NOTE EDIT / 保留");
    expect(apiMocks.deleteNote).toHaveBeenCalledWith(TICKER, 71);
    expect(host!.textContent).not.toContain(RAW_ERROR);
  });

  it("preserves tag draft and maps catalog add and remove failures separately", async () => {
    const olderRetry = deferred<{ catalog: Record<string, string[]> }>();
    const newerRetry = deferred<{ catalog: Record<string, string[]> }>();
    apiMocks.getTagCatalog.mockReset()
      .mockRejectedValueOnce(
        structuredError("tag_catalog_failed", "/profile/tags/catalog"),
      )
      .mockReturnValueOnce(olderRetry.promise)
      .mockReturnValueOnce(newerRetry.promise)
      .mockResolvedValue({
        catalog: { theme: [SOURCE_TAG_VALUE], category: ["SOURCE CATEGORY"] },
      });
    await mountTicker();
    await waitForCalls(apiMocks.getTagCatalog, 1);
    expect(host!.querySelector('[role="alert"] .ui-status-badge')?.textContent)
      .toBe("無法載入標籤目錄。");

    const input = host!.querySelector<HTMLInputElement>('input[list^="tagvals-"]')!;
    await setInput(input, "SOURCE TAG DRAFT / 保留");
    await click(buttonByText("重試"));
    await waitForCalls(apiMocks.getTagCatalog, 2);
    await click(buttonByText("重試"));
    await waitForCalls(apiMocks.getTagCatalog, 3);
    await act(async () => {
      newerRetry.resolve({ catalog: { theme: [SOURCE_NEWER_TAG_VALUE] } });
      await newerRetry.promise;
    });
    await flush();
    await act(async () => {
      olderRetry.reject(structuredError("stale_tag_catalog_failure"));
      await olderRetry.promise.catch(() => undefined);
    });
    await flush();

    expect(host!.querySelector(`datalist option[value="${SOURCE_NEWER_TAG_VALUE}"]`)).not.toBeNull();
    expect(Array.from(host!.querySelectorAll("[role=alert] .ui-status-badge"))
      .map((node) => node.textContent)).not.toContain("無法載入標籤目錄。");
    expect(input.value).toBe("SOURCE TAG DRAFT / 保留");

    apiMocks.addTickerTag.mockRejectedValueOnce(
      structuredError("tag_add_failed", `/profile/tickers/${TICKER}/tags`),
    );
    await click(buttonByText("新增"));
    await waitForCalls(apiMocks.addTickerTag, 1);
    expect(host!.querySelector('[role="alert"] .ui-status-badge')?.textContent)
      .toBe("無法新增標籤。");
    expect(input.value).toBe("SOURCE TAG DRAFT / 保留");
    expect(apiMocks.addTickerTag).toHaveBeenCalledWith(TICKER, "SOURCE TAG DRAFT / 保留", "theme");

    const facet = host!.querySelector<HTMLSelectElement>(".tag-add select")!;
    await setInput(input, "SOURCE NEWER TAG EDIT / 保留");
    await setSelect(facet, "category");
    await click(buttonByText("重試"));
    await waitForCalls(apiMocks.addTickerTag, 2);
    expect(apiMocks.addTickerTag.mock.calls).toEqual([
      [TICKER, "SOURCE TAG DRAFT / 保留", "theme"],
      [TICKER, "SOURCE TAG DRAFT / 保留", "theme"],
    ]);
    expect(input.value).toBe("SOURCE NEWER TAG EDIT / 保留");
    expect(facet.value).toBe("category");

    apiMocks.removeTickerTag.mockRejectedValueOnce(
      structuredError("tag_remove_failed", `/profile/tickers/${TICKER}/tags?value=private`),
    );
    await click(host!.querySelector<HTMLButtonElement>('button[title="移除標籤"]')!);
    await waitForCalls(apiMocks.removeTickerTag, 1);
    expect(host!.querySelector('[role="alert"] .ui-status-badge')?.textContent)
      .toBe("無法移除標籤。");
    expect(input.value).toBe("SOURCE NEWER TAG EDIT / 保留");
    expect(facet.value).toBe("category");
    expect(apiMocks.removeTickerTag).toHaveBeenCalledWith(
      TICKER,
      USER_TAG.value,
      USER_TAG.facet,
      USER_TAG.source,
    );
    expect(host!.textContent).not.toContain(RAW_ERROR);
  });

  it("shows only safe ticker diagnostics in Developer Mode", async () => {
    apiMocks.getTickerState.mockRejectedValueOnce(
      structuredError(
        "ticker_state_unavailable",
        `/profile/tickers/${TICKER}/state?secret=raw`,
        "request timed out after 12s",
      ),
    );
    await mountTicker({ developerMode: true });
    await waitForCalls(apiMocks.getTickerState, 1);

    const diagnostics = host!.querySelector<HTMLElement>('[aria-label="開發者診斷"]');
    expect(diagnostics).not.toBeNull();
    expect(Array.from(diagnostics!.querySelectorAll("dl > div")).map((row) => [
      row.querySelector("dt")?.textContent,
      row.querySelector("dd")?.textContent,
    ])).toEqual([
      ["狀態", "503"],
      ["代碼", "ticker_state_unavailable"],
      ["路徑", "/profile/tickers/{ticker}/state"],
      ["細節", "request timed out after 12s"],
    ]);
    expect(host!.textContent).not.toContain(RAW_ERROR);
    expect(host!.textContent).not.toContain("secret=raw");
  });

  it("updates memoized chrome in place without resetting reading position or refetching", async () => {
    await mountTicker();
    await click(buttonByText("數據"));
    await waitForText(SOURCE_FUNDAMENTAL_PROVIDER);

    const main = host!.querySelector<HTMLElement>("main")!;
    const refreshButton = buttonByText("重新整理");
    const sourceLabel = Array.from(host!.querySelectorAll("dt"))
      .find((node) => node.textContent === "IV · 本次來源")!;
    const sourceValue = sourceLabel.nextElementSibling;
    expect(sourceValue?.textContent).toBe("本地");
    main.scrollTop = 411;
    refreshButton.focus();
    const before = requestCounts();

    await switchLocale("en");

    expect(host!.textContent).toContain("Data source / freshness");
    expect(buttonByText("Refresh")).toBe(refreshButton);
    expect(sourceLabel.textContent).toBe("IV · Source this time");
    expect(sourceLabel.nextElementSibling).toBe(sourceValue);
    expect(sourceValue?.textContent).toBe("Local");
    expect(document.activeElement).toBe(refreshButton);
    expect(main.scrollTop).toBe(411);
    expect(requestCounts()).toEqual(before);
  });
});
