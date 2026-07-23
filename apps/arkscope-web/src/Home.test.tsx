/** @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import i18n from "i18next";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  ApiStatus,
  CardDetail,
  CardSummary,
  ResultCard,
  UniverseResponse,
  WatchlistSummary,
} from "./api";
import type { StatusState } from "./Dashboard";
import type { NavigationTarget } from "./shell/navigation";

const apiMocks = vi.hoisted(() => ({
  getUniverse: vi.fn(),
  getProfileLists: vi.fn(),
  getCards: vi.fn(),
  getCard: vi.fn(),
  saveCard: vi.fn(),
  translateCard: vi.fn(),
}));

vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return {
    ...actual,
    getUniverse: apiMocks.getUniverse,
    getProfileLists: apiMocks.getProfileLists,
    getCards: apiMocks.getCards,
    getCard: apiMocks.getCard,
    saveCard: apiMocks.saveCard,
    translateCard: apiMocks.translateCard,
  };
});

import { HomeView } from "./Home";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

const SOURCE_LIST = '原始清單 <img src="x" onerror="source-leak">';
const SOURCE_TICKER = "SOURCE.TW";
const SOURCE_CARD_CONCLUSION = 'SOURCE CARD <script>alert("source")</script> CONCLUSION';
const SOURCE_CARD_TIMESTAMP = "SOURCE_CARD_TIMESTAMP_NOT_A_DATE";
const UNKNOWN_CONFIDENCE = "future_confidence_v9";
const SOURCE_AS_OF = "SOURCE_WATCHLIST_AS_OF_NOT_A_DATE";
const UNSAFE_MESSAGE = "RAW backend workspace failure: postgres://admin:secret@10.0.0.8/private";
const UNSAFE_DIAGNOSTIC = "Authorization: Bearer sk-live-secret\nTraceback /srv/private.py:42";
const TRANSLATED_CONCLUSION = "PLANTED TRANSLATED RESULT 仍保持";

const API_STATUS: ApiStatus = {
  status: "ok",
  timestamp: "2026-07-23T09:00:00Z",
  tools_registered: 37,
  tool_categories: {},
  data_sources: { ibkr: 1, finnhub: 1 },
};

const STATUS: StatusState = { kind: "ready", status: API_STATUS };

const LISTS: WatchlistSummary[] = [
  {
    id: 91,
    name: SOURCE_LIST,
    kind: "custom",
    position: 0,
    archived: false,
    active_count: 2,
    total_count: 3,
  },
  {
    id: 92,
    name: "SOURCE CLASSIFICATION LIST",
    kind: "theme",
    position: 1,
    archived: false,
    active_count: 1,
    total_count: 1,
  },
];

const UNIVERSE: UniverseResponse = {
  as_of: SOURCE_AS_OF,
  generated_at: "SOURCE_UNIVERSE_GENERATED_AT",
  total: 4,
  shown: 4,
  archived_count: 1,
  summarized: 3,
  rows: [
    {
      ticker: SOURCE_TICKER,
      has_summary: true,
      group: "SOURCE GROUP",
      priority: "source-priority/raw",
      latest_close: 1234.567,
      change_7d_pct: -12.5,
      news_count_7d: 9,
      sentiment_mean: 0.4,
      bullish_ratio: 0.7,
      lists: [SOURCE_LIST],
      all_lists: [SOURCE_LIST],
      archived_lists: [],
      archived: false,
      tags: [],
      note_count: 3,
    },
    {
      ticker: "RAW-LIST",
      has_summary: true,
      group: null,
      priority: null,
      latest_close: 45.2,
      change_7d_pct: 3.25,
      news_count_7d: 2,
      sentiment_mean: null,
      bullish_ratio: null,
      lists: [SOURCE_LIST],
      all_lists: [SOURCE_LIST],
      archived_lists: [],
      archived: false,
      tags: [],
      note_count: 0,
    },
    {
      ticker: "ARCHIVED-RAW",
      has_summary: false,
      group: null,
      priority: null,
      latest_close: null,
      change_7d_pct: null,
      news_count_7d: 0,
      sentiment_mean: null,
      bullish_ratio: null,
      lists: [],
      all_lists: [SOURCE_LIST],
      archived_lists: [SOURCE_LIST],
      archived: true,
      tags: [],
      note_count: 0,
    },
    {
      ticker: "THEME-ONLY",
      has_summary: true,
      group: "SOURCE CLASSIFICATION LIST",
      priority: "source-theme-priority",
      latest_close: 88,
      change_7d_pct: 99,
      news_count_7d: 99,
      sentiment_mean: null,
      bullish_ratio: null,
      lists: ["SOURCE CLASSIFICATION LIST"],
      all_lists: ["SOURCE CLASSIFICATION LIST"],
      archived_lists: [],
      archived: false,
      tags: [],
      note_count: 0,
    },
  ],
};

const CARD_SUMMARY: CardSummary = {
  run_id: 701,
  ticker: SOURCE_TICKER,
  question: "SOURCE QUESTION <keep>",
  horizon: "source-horizon-id",
  card_type: "source-card-type",
  status: "completed-source-state",
  provider: "provider/source-id",
  model: "model/source-id",
  generated_at: SOURCE_CARD_TIMESTAMP,
  saved_report_id: null,
  conclusion: SOURCE_CARD_CONCLUSION,
  confidence_level: "high",
};

const CARDS: CardSummary[] = [
  CARD_SUMMARY,
  { ...CARD_SUMMARY, run_id: 702, confidence_level: "medium" },
  { ...CARD_SUMMARY, run_id: 703, confidence_level: "low" },
  {
    ...CARD_SUMMARY,
    run_id: 704,
    confidence_level: UNKNOWN_CONFIDENCE as CardSummary["confidence_level"],
  },
];

function resultCard(conclusion: string, prosePrefix: string): ResultCard {
  return {
    ticker: SOURCE_TICKER,
    question: `${prosePrefix} QUESTION`,
    horizon: "source-horizon-id",
    card_type: "source-card-type",
    analysis_time: "SOURCE_ANALYSIS_TIMESTAMP",
    conclusion,
    primary_reasons: [`${prosePrefix} PRIMARY REASON`],
    counter_thesis: [`${prosePrefix} COUNTER THESIS`],
    key_assumptions: [`${prosePrefix} ASSUMPTION`],
    trigger_conditions: [`${prosePrefix} TRIGGER`],
    invalidation_conditions: [`${prosePrefix} INVALIDATION`],
    risks: [`${prosePrefix} RISK`],
    watch_list: [`${prosePrefix} WATCH ITEM`],
    market_narrative: `${prosePrefix} MARKET NARRATIVE`,
    divergence: `${prosePrefix} DIVERGENCE`,
    confidence_level: "high",
    confidence_rationale: `${prosePrefix} CONFIDENCE RATIONALE`,
    traceability: {
      data_sources: [
        {
          name: "provider/source-id",
          as_of: "SOURCE_PROVIDER_TIMESTAMP",
          is_real_time: false,
          detail: "SOURCE PROVIDER DETAIL",
        },
      ],
      is_single_model_inference: true,
      completeness: {
        news: true,
        fundamentals: false,
        technicals: true,
        note: "SOURCE COMPLETENESS NOTE",
      },
      claims: [
        {
          claim: `${prosePrefix} CLAIM`,
          evidence_ids: ["source-evidence-id"],
        },
      ],
    },
  };
}

const SOURCE_DETAIL_CARD = resultCard(
  "SOURCE DETAIL CONCLUSION <keep>",
  "SOURCE DETAIL",
);
const TRANSLATED_CARD = resultCard(TRANSLATED_CONCLUSION, "TRANSLATED PROSE");

const CARD_DETAIL: CardDetail = {
  run_id: 701,
  status: "completed-source-state",
  provider: "provider/source-id",
  model: "model/source-id",
  effort: "source-effort-id",
  generated_at: SOURCE_CARD_TIMESTAMP,
  card: SOURCE_DETAIL_CARD,
  evidence_packet: null,
  personalization: null,
  ticker: SOURCE_TICKER,
  question: "SOURCE QUESTION <keep>",
  horizon: "source-horizon-id",
  card_type: "source-card-type",
  as_of: "SOURCE_CARD_AS_OF",
  saved_report_id: null,
};

type RequestName = keyof typeof apiMocks;

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

function workspaceError(code = "workspace_fixture_failed") {
  return Object.assign(new Error(UNSAFE_MESSAGE), {
    status: 503,
    code,
    path: "/profile/universe?token=private-source-value#raw-fragment",
    diagnostic: UNSAFE_DIAGNOSTIC,
  });
}

function cardError() {
  return Object.assign(new Error(UNSAFE_MESSAGE), {
    status: 503,
    code: "provider_config_missing",
    path: "/analysis/cards/701?token=private-source-value#raw-fragment",
    diagnostic: "request timed out after 12s",
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

async function flush() {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

async function waitForText(text: string) {
  for (let attempt = 0; attempt < 10; attempt += 1) {
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

function buttonByText(text: string, scope: ParentNode = host!): HTMLButtonElement {
  const match = Array.from(scope.querySelectorAll<HTMLButtonElement>("button"))
    .find((button) => button.textContent?.includes(text));
  if (!match) throw new Error(`button not found: ${text}; rendered=${scope.textContent ?? ""}`);
  return match;
}

function unmountHome() {
  if (root) act(() => root!.unmount());
  root = null;
  host?.remove();
  host = null;
}

async function mountHome({
  developerMode = false,
  onNavigate = vi.fn(),
  onOpenTicker = vi.fn(),
  onNavigateTarget = vi.fn(),
  settle = true,
}: {
  developerMode?: boolean;
  onNavigate?: (view: "Home" | "Watchlist" | "System") => void;
  onOpenTicker?: (ticker: string) => void;
  onNavigateTarget?: (target: NavigationTarget) => void;
  settle?: boolean;
} = {}) {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(
      <HomeView
        status={STATUS}
        onNavigate={onNavigate}
        onOpenTicker={onOpenTicker}
        developerMode={developerMode}
        onNavigateTarget={onNavigateTarget}
      />,
    );
    await Promise.resolve();
  });
  if (settle) await flush();
  return { onNavigate, onOpenTicker, onNavigateTarget };
}

async function switchLocale(locale: "zh-Hant" | "en") {
  await act(async () => {
    await i18n.changeLanguage(locale);
  });
  await flush();
}

function requestCounts(): Record<RequestName, number> {
  return {
    getUniverse: apiMocks.getUniverse.mock.calls.length,
    getProfileLists: apiMocks.getProfileLists.mock.calls.length,
    getCards: apiMocks.getCards.mock.calls.length,
    getCard: apiMocks.getCard.mock.calls.length,
    saveCard: apiMocks.saveCard.mock.calls.length,
    translateCard: apiMocks.translateCard.mock.calls.length,
  };
}

function expectRequestCounts(expected: Partial<Record<RequestName, number>>) {
  expect(requestCounts()).toEqual({
    getUniverse: 0,
    getProfileLists: 0,
    getCards: 0,
    getCard: 0,
    saveCard: 0,
    translateCard: 0,
    ...expected,
  });
}

function expectWorkspaceRequestShape(attempts: number) {
  expect(apiMocks.getUniverse.mock.calls).toEqual(
    Array.from({ length: attempts }, () => [true]),
  );
  expect(apiMocks.getProfileLists.mock.calls).toEqual(
    Array.from({ length: attempts }, () => [false]),
  );
  expect(apiMocks.getCards.mock.calls).toEqual(
    Array.from({ length: attempts }, () => [undefined, 8]),
  );
}

beforeEach(async () => {
  await i18n.changeLanguage("zh-Hant");
  document.documentElement.lang = "zh-Hant";
  apiMocks.getUniverse.mockReset().mockResolvedValue(UNIVERSE);
  apiMocks.getProfileLists.mockReset().mockResolvedValue({ lists: LISTS });
  apiMocks.getCards.mockReset().mockResolvedValue({ cards: CARDS });
  apiMocks.getCard.mockReset().mockResolvedValue(CARD_DETAIL);
  apiMocks.saveCard.mockReset().mockResolvedValue({
    run_id: 701,
    status: "saved",
    saved_report_id: 1701,
  });
  apiMocks.translateCard.mockReset().mockResolvedValue({
    run_id: 701,
    lang: "zh-Hant",
    card: TRANSLATED_CARD,
    cached: false,
  });
});

afterEach(() => {
  unmountHome();
});

describe("Home localization", () => {
  it("renders the reviewed zh-Hant Home chrome and planted source values", async () => {
    await mountHome();

    const text = host!.textContent ?? "";
    for (const expected of [
      "自選股",
      "共 3 · 1 已封存",
      "告警",
      "尚未啟用",
      "資料來源",
      "37 個工具",
      "資料時間",
      "自選股資料時間",
      "自選股動態",
      "7 日漲跌排行",
      "最近 AI 卡片",
      "近期研究卡片",
      SOURCE_TICKER,
      "source-priority/raw",
      SOURCE_CARD_CONCLUSION,
      SOURCE_CARD_TIMESTAMP,
      SOURCE_AS_OF,
    ]) {
      expect(text).toContain(expected);
    }

    expect(Array.from(host!.querySelectorAll(".home-table th")).map((cell) => cell.textContent))
      .toEqual(["Ticker", "收盤價", "7 日漲跌", "新聞", "優先順序"]);
    expect(Array.from(host!.querySelectorAll(".card-row .conf")).map((node) => node.textContent))
      .toEqual(["高", "中", "低", UNKNOWN_CONFIDENCE]);
    const moverRows = Array.from(host!.querySelectorAll<HTMLTableRowElement>(".home-table tbody tr"));
    expect(moverRows.map((row) => row.querySelector("td")?.textContent)).toEqual([
      SOURCE_TICKER,
      "RAW-LIST",
    ]);
    expect(moverRows[0]?.textContent).toContain("-12.50%");
    expect(host!.querySelector("script")).toBeNull();
    expectWorkspaceRequestShape(1);
    expectRequestCounts({ getUniverse: 1, getProfileLists: 1, getCards: 1 });
  });

  it("renders English Home chrome without translating tickers lists or cards", async () => {
    await switchLocale("en");
    await mountHome();

    const text = host!.textContent ?? "";
    for (const expected of [
      "Watchlist",
      "3 total · 1 archived",
      "Alerts",
      "Not enabled",
      "Data source",
      "37 tools",
      "Data as of",
      "Watchlist as of",
      "Watchlist activity",
      "Top movers · 7d",
      "Recent AI Cards",
      "Recent research cards",
      "View all →",
      "Generate in Watchlist →",
      SOURCE_TICKER,
      "source-priority/raw",
      SOURCE_CARD_CONCLUSION,
      SOURCE_CARD_TIMESTAMP,
      SOURCE_AS_OF,
    ]) {
      expect(text).toContain(expected);
    }
    expect(Array.from(host!.querySelectorAll(".home-table th")).map((cell) => cell.textContent))
      .toEqual(["Ticker", "Close", "7d change", "News", "Priority"]);
    expect(Array.from(host!.querySelectorAll(".card-row .conf")).map((node) => node.textContent))
      .toEqual(["High", "Medium", "Low", UNKNOWN_CONFIDENCE]);
    expect(text).not.toContain("來源卡片結論");
    expectWorkspaceRequestShape(1);
    expectRequestCounts({ getUniverse: 1, getProfileLists: 1, getCards: 1 });
  });

  it("preserves loading empty and operation-specific error triggers", async () => {
    const universeRequest = deferred<UniverseResponse>();
    const listsRequest = deferred<{ lists: WatchlistSummary[] }>();
    const cardsRequest = deferred<{ cards: CardSummary[] }>();
    apiMocks.getUniverse.mockReturnValueOnce(universeRequest.promise);
    apiMocks.getProfileLists.mockReturnValueOnce(listsRequest.promise);
    apiMocks.getCards.mockReturnValueOnce(cardsRequest.promise);

    await mountHome({ settle: false });
    expect(Array.from(host!.querySelectorAll("p")).filter((node) => node.textContent === "載入中…"))
      .toHaveLength(2);
    expect(host!.querySelector('[role="alert"]')).toBeNull();

    await act(async () => {
      universeRequest.resolve({ ...UNIVERSE, total: 0, shown: 0, archived_count: 0, rows: [] });
      listsRequest.resolve({ lists: [] });
      cardsRequest.resolve({ cards: [] });
      await Promise.all([universeRequest.promise, listsRequest.promise, cardsRequest.promise]);
    });
    await flush();
    expect(host!.textContent).toContain("尚無自選股。到「自選股」建立清單並加入標的。");
    expect(host!.textContent).toContain("尚無 AI 卡片。在自選股詳情頁產生第一張研究卡片。");
    expect(host!.querySelector('[role="alert"]')).toBeNull();

    unmountHome();
    apiMocks.getUniverse.mockRejectedValueOnce(workspaceError());
    await mountHome();

    const alerts = host!.querySelectorAll('[role="alert"]');
    expect(alerts).toHaveLength(1);
    expect(alerts[0]!.querySelector(".ui-status-badge")?.textContent)
      .toBe("無法載入工作台資料。");
    expect(alerts[0]!.textContent).toContain("重試");
    expect(alerts[0]!.textContent).not.toContain(UNSAFE_MESSAGE);
    expect(host!.querySelector('[aria-label="開發者診斷"]')).toBeNull();
    expectWorkspaceRequestShape(2);
    expectRequestCounts({ getUniverse: 2, getProfileLists: 2, getCards: 2 });
  });

  it("shows only safe Developer diagnostics for a failed workspace load", async () => {
    const onNavigate = vi.fn();
    const onNavigateTarget = vi.fn();
    apiMocks.getUniverse.mockRejectedValueOnce(workspaceError("active_universe_unavailable"));

    await mountHome({ developerMode: true, onNavigate, onNavigateTarget });

    const alert = host!.querySelector('[role="alert"]');
    expect(alert?.querySelector(".ui-status-badge")?.textContent).toBe("無法載入工作台資料。");
    const diagnostics = alert!.querySelector<HTMLElement>('[aria-label="開發者診斷"]');
    expect(diagnostics).not.toBeNull();
    expect(Array.from(diagnostics!.querySelectorAll("dl > div")).map((row) => [
      row.querySelector("dt")?.textContent,
      row.querySelector("dd")?.textContent,
    ])).toEqual([
      ["狀態", "503"],
      ["代碼", "active_universe_unavailable"],
      ["路徑", "/profile/universe"],
    ]);
    expect(diagnostics!.textContent).toContain("不安全的診斷細節已省略。");
    expect(alert!.textContent).not.toContain(UNSAFE_MESSAGE);
    expect(alert!.textContent).not.toContain("sk-live-secret");
    expect(alert!.textContent).not.toContain("private-source-value");

    await click(buttonByText("前往資料來源與排程", alert!));
    expect(onNavigateTarget).toHaveBeenCalledWith({
      kind: "settings_section",
      section: "data_sources",
    });
    expect(onNavigate).not.toHaveBeenCalled();
    expectWorkspaceRequestShape(1);
    expectRequestCounts({ getUniverse: 1, getProfileLists: 1, getCards: 1 });
  });

  it("retries with the existing request shape and no extra request", async () => {
    await switchLocale("en");
    apiMocks.getUniverse.mockRejectedValueOnce(workspaceError());
    await mountHome();

    expectWorkspaceRequestShape(1);
    expectRequestCounts({ getUniverse: 1, getProfileLists: 1, getCards: 1 });
    await click(buttonByText("Retry"));
    await waitForText(SOURCE_TICKER);

    expect(host!.querySelector('[role="alert"]')).toBeNull();
    expectWorkspaceRequestShape(2);
    expectRequestCounts({ getUniverse: 2, getProfileLists: 2, getCards: 2 });
  });

  it("switches locale without resetting loaded data reading position or focus", async () => {
    await mountHome();
    const main = host!.querySelector<HTMLElement>("main");
    const viewAll = buttonByText("查看全部");
    const tickerCell = Array.from(host!.querySelectorAll(".home-table td"))
      .find((cell) => cell.textContent === SOURCE_TICKER);
    const cardRow = host!.querySelector<HTMLElement>(".card-row");
    const confidenceNodes = Array.from(host!.querySelectorAll<HTMLElement>(".card-row .conf"));
    expect(main).not.toBeNull();
    expect(tickerCell).toBeDefined();
    expect(cardRow).not.toBeNull();
    expect(confidenceNodes.map((node) => node.textContent))
      .toEqual(["高", "中", "低", UNKNOWN_CONFIDENCE]);
    main!.scrollTop = 223;
    viewAll.focus();
    expect(document.activeElement).toBe(viewAll);
    const before = requestCounts();

    await switchLocale("en");

    expect(host!.textContent).toContain("Watchlist activity");
    expect(host!.querySelector("main")).toBe(main);
    expect(buttonByText("View all")).toBe(viewAll);
    expect(document.activeElement).toBe(viewAll);
    expect(main!.scrollTop).toBe(223);
    expect(Array.from(host!.querySelectorAll(".home-table td"))
      .find((cell) => cell.textContent === SOURCE_TICKER)).toBe(tickerCell);
    expect(host!.querySelector(".card-row")).toBe(cardRow);
    expect(Array.from(host!.querySelectorAll<HTMLElement>(".card-row .conf")))
      .toEqual(confidenceNodes);
    expect(confidenceNodes.map((node) => node.textContent))
      .toEqual(["High", "Medium", "Low", UNKNOWN_CONFIDENCE]);
    expect(requestCounts()).toEqual(before);
    expectWorkspaceRequestShape(1);
    expectRequestCounts({ getUniverse: 1, getProfileLists: 1, getCards: 1 });
  });

  it("keeps an open Card modal and source Card identity across locale switch", async () => {
    const onNavigateTarget = vi.fn();
    apiMocks.getCard.mockRejectedValueOnce(cardError());
    await mountHome({ developerMode: true, onNavigateTarget });
    const cardRow = host!.querySelector<HTMLElement>(".card-row");
    expect(cardRow).not.toBeNull();
    await click(cardRow!);
    await flush();

    const failedDialog = host!.querySelector<HTMLElement>('[role="dialog"]');
    const alert = failedDialog!.querySelector<HTMLElement>('[role="alert"]');
    expect(alert?.querySelector(".ui-status-badge")?.textContent).toBe("無法開啟 AI 卡片。");
    expect(Array.from(alert!.querySelectorAll('[aria-label="開發者診斷"] dl > div')).map((row) => [
      row.querySelector("dt")?.textContent,
      row.querySelector("dd")?.textContent,
    ])).toEqual([
      ["狀態", "503"],
      ["代碼", "provider_config_missing"],
      ["路徑", "/analysis/cards/{run_id}"],
      ["細節", "request timed out after 12s"],
    ]);
    expect(alert!.textContent).not.toContain(UNSAFE_MESSAGE);
    expect(alert!.textContent).not.toContain("private-source-value");
    await click(buttonByText("前往 Provider 登入與憑證", alert!));
    expect(onNavigateTarget).toHaveBeenCalledWith({
      kind: "settings_section",
      section: "providers",
    });
    await click(buttonByText("重試", alert!));
    await waitForText("SOURCE DETAIL PRIMARY REASON");

    const dialog = host!.querySelector<HTMLElement>('[role="dialog"]');
    const cardView = dialog!.querySelector<HTMLElement>(".cardview");
    expect(dialog?.getAttribute("aria-label")).toBe(`${SOURCE_TICKER} AI 卡片`);
    expect(cardView).not.toBeNull();
    await click(buttonByText("繁中", dialog!));
    await waitForText(TRANSLATED_CONCLUSION);
    expect(dialog!.querySelector(".cardview-concl")?.textContent).toBe(TRANSLATED_CONCLUSION);
    const modalControl = buttonByText("EN", dialog!);
    modalControl.focus();
    expect(document.activeElement).toBe(modalControl);
    const before = requestCounts();

    await switchLocale("en");

    expect(host!.textContent).toContain("Watchlist activity");
    expect(host!.querySelector('[role="dialog"]')).toBe(dialog);
    expect(dialog!.querySelector(".cardview")).toBe(cardView);
    expect(buttonByText("EN", dialog!)).toBe(modalControl);
    expect(document.activeElement).toBe(modalControl);
    expect(dialog!.querySelector(".cardview-concl")?.textContent).toBe(TRANSLATED_CONCLUSION);
    expect(dialog!.getAttribute("aria-label")).toBe(`${SOURCE_TICKER} AI Card`);
    expect(host!.querySelector(".card-row")).toBe(cardRow);
    expect(cardRow!.textContent).toContain(SOURCE_CARD_CONCLUSION);
    expect(apiMocks.getCard).toHaveBeenCalledWith(701);
    expect(apiMocks.translateCard).toHaveBeenCalledWith(701, "zh-Hant", undefined);
    expect(requestCounts()).toEqual(before);
    expectWorkspaceRequestShape(1);
    expectRequestCounts({
      getUniverse: 1,
      getProfileLists: 1,
      getCards: 1,
      getCard: 2,
      translateCard: 1,
    });
  });
});
