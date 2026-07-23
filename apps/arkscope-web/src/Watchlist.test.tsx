/** @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import i18n from "i18next";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  ConsensusSummary,
  UniverseResponse,
  WatchlistSummary,
} from "./api";
import type { NavigationTarget } from "./shell/navigation";

const apiMocks = vi.hoisted(() => ({
  addMember: vi.fn(),
  createList: vi.fn(),
  deleteList: vi.fn(),
  getConsensus: vi.fn(),
  getDefaultWatchlist: vi.fn(),
  getProfileLists: vi.fn(),
  getUniverse: vi.fn(),
  removeMember: vi.fn(),
  renameList: vi.fn(),
  searchSymbols: vi.fn(),
  setArchived: vi.fn(),
  setDefaultWatchlist: vi.fn(),
  setPriority: vi.fn(),
}));

vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return { ...actual, ...apiMocks };
});

import { WatchlistView } from "./Watchlist";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

const SOURCE_LIST = '來源清單 / Alpha <keep>';
const SOURCE_LIST_TWO = "Beta 客製清單";
const SOURCE_TICKER = "SRC.TW";
const SOURCE_TAG_VALUE = "Value:β / RAW%2F";
const SOURCE_TAG_SOURCE = "provider:RAW/v1";
const SOURCE_SEARCH_NAME = '來源公司 <script>keep</script>';
const RAW_ERROR = "RAW postgres://admin:secret@10.0.0.8/watchlist";
const RAW_DIAGNOSTIC = "Authorization: Bearer sk-private\nTraceback /srv/private.py:42";
const RAW_PROVIDER_MESSAGE = "RAW provider exception /private/consensus";

const LISTS: WatchlistSummary[] = [
  {
    id: 101,
    name: SOURCE_LIST,
    kind: "custom",
    position: 0,
    archived: false,
    active_count: 2,
    total_count: 3,
  },
  {
    id: 102,
    name: SOURCE_LIST_TWO,
    kind: "custom",
    position: 1,
    archived: false,
    active_count: 1,
    total_count: 1,
  },
  {
    id: 103,
    name: "SOURCE CLASSIFICATION LIST",
    kind: "theme",
    position: 2,
    archived: false,
    active_count: 1,
    total_count: 1,
  },
];

const UNIVERSE: UniverseResponse = {
  as_of: "SOURCE_AS_OF_NOT_A_DATE",
  generated_at: "SOURCE_GENERATED_AT",
  total: 4,
  shown: 4,
  archived_count: 1,
  summarized: 3,
  rows: [
    {
      ticker: SOURCE_TICKER,
      has_summary: true,
      group: "SOURCE GROUP",
      priority: "low",
      latest_close: 1234.56,
      change_7d_pct: 7.5,
      news_count_7d: 4,
      sentiment_mean: 0.2,
      bullish_ratio: 0.7,
      lists: [SOURCE_LIST],
      all_lists: [SOURCE_LIST],
      archived_lists: [],
      archived: false,
      tags: [
        { facet: "category", value: SOURCE_TAG_VALUE, source: SOURCE_TAG_SOURCE },
        { facet: "source_custom_axis", value: "UNKNOWN VALUE", source: "system:raw" },
      ],
      note_count: 2,
    },
    {
      ticker: "AAA.US",
      has_summary: true,
      group: null,
      priority: "high",
      latest_close: 80,
      change_7d_pct: -3,
      news_count_7d: 8,
      sentiment_mean: null,
      bullish_ratio: null,
      lists: [SOURCE_LIST, SOURCE_LIST_TWO],
      all_lists: [SOURCE_LIST, SOURCE_LIST_TWO],
      archived_lists: [],
      archived: false,
      tags: [],
      note_count: 0,
    },
    {
      ticker: "ARCH.SRC",
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
      note_count: 1,
    },
    {
      ticker: "THEME-ONLY",
      has_summary: true,
      group: "SOURCE CLASSIFICATION LIST",
      priority: "medium",
      latest_close: 90,
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

const CONSENSUS: ConsensusSummary = {
  ticker: SOURCE_TICKER,
  rating: "Strong Buy",
  score: 0.85,
  buy_ratio: 0.8,
  total: 15,
  counts: { strongBuy: 7, buy: 4, hold: 3, sell: 1, strongSell: 0 },
  price_target: { sourceValue: "RAW PRICE TARGET" },
  period: "SOURCE_PERIOD",
  source: "Provider/RAW-v1",
  cached: true,
  fetched_at: "SOURCE_FETCHED_AT_2026-07-23",
  status: "cached",
};

type RequestName = keyof typeof apiMocks;

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

function structuredError(
  code = "watchlist_fixture_failed",
  path = "/profile/universe?token=private#fragment",
) {
  return Object.assign(new Error(RAW_ERROR), {
    status: 503,
    code,
    path,
    diagnostic: RAW_DIAGNOSTIC,
  });
}

async function flush(delay = 0) {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, delay));
  });
}

async function waitForText(text: string) {
  for (let attempt = 0; attempt < 16; attempt += 1) {
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

async function setInput(input: HTMLInputElement, value: string) {
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set?.call(input, value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await flush();
}

async function change(select: HTMLSelectElement, value: string) {
  await act(async () => {
    select.value = value;
    select.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await flush();
}

async function switchLocale(locale: "zh-Hant" | "en") {
  await act(async () => {
    await i18n.changeLanguage(locale);
  });
  await flush();
}

function unmountWatchlist() {
  if (root) act(() => root!.unmount());
  root = null;
  host?.remove();
  host = null;
}

async function mountWatchlist({
  developerMode = false,
  onOpenTicker = vi.fn(),
  onNavigateTarget = vi.fn(),
}: {
  developerMode?: boolean;
  onOpenTicker?: (ticker: string) => void;
  onNavigateTarget?: (target: NavigationTarget) => void;
} = {}) {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(
      <WatchlistView
        onOpenTicker={onOpenTicker}
        developerMode={developerMode}
        onNavigateTarget={onNavigateTarget}
      />,
    );
    await Promise.resolve();
  });
  await flush();
  return { onOpenTicker, onNavigateTarget };
}

function buttonByText(text: string, scope: ParentNode = host!): HTMLButtonElement {
  const button = Array.from(scope.querySelectorAll<HTMLButtonElement>("button"))
    .find((candidate) => candidate.textContent?.includes(text));
  if (!button) throw new Error(`button not found: ${text}; rendered=${scope.textContent ?? ""}`);
  return button;
}

function rowForTicker(ticker: string): HTMLTableRowElement {
  const row = Array.from(host!.querySelectorAll<HTMLTableRowElement>("tbody tr"))
    .find((candidate) => candidate.textContent?.includes(ticker));
  if (!row) throw new Error(`row not found: ${ticker}; rendered=${host!.textContent ?? ""}`);
  return row;
}

function visibleTickers(): string[] {
  return Array.from(host!.querySelectorAll<HTMLTableRowElement>("tbody tr"))
    .map((row) => row.querySelector("td")?.textContent ?? "")
    .map((value) => ["AAA.US", "ARCH.SRC", SOURCE_TICKER, "THEME-ONLY"]
      .find((ticker) => value.includes(ticker)) ?? value);
}

function requestCounts(): Record<RequestName, number> {
  return Object.fromEntries(
    Object.entries(apiMocks).map(([name, mock]) => [name, mock.mock.calls.length]),
  ) as Record<RequestName, number>;
}

beforeEach(async () => {
  await i18n.changeLanguage("zh-Hant");
  document.documentElement.lang = "zh-Hant";
  apiMocks.addMember.mockReset().mockResolvedValue({ ticker: SOURCE_TICKER });
  apiMocks.createList.mockReset().mockResolvedValue({ ...LISTS[0], id: 501 });
  apiMocks.deleteList.mockReset().mockResolvedValue({ deleted: true });
  apiMocks.getConsensus.mockReset().mockImplementation((ticker: string) => (
    Promise.resolve({ ...CONSENSUS, ticker })
  ));
  apiMocks.getDefaultWatchlist.mockReset().mockResolvedValue({ default_watchlist_id: 101 });
  apiMocks.getProfileLists.mockReset().mockResolvedValue({ lists: LISTS });
  apiMocks.getUniverse.mockReset().mockResolvedValue(UNIVERSE);
  apiMocks.removeMember.mockReset().mockResolvedValue({ removed: true });
  apiMocks.renameList.mockReset().mockResolvedValue({ ...LISTS[0], name: "RENAMED" });
  apiMocks.searchSymbols.mockReset().mockResolvedValue({
    q: "src",
    results: [{ ticker: "SEARCH.SRC", name: SOURCE_SEARCH_NAME, tracked: true }],
  });
  apiMocks.setArchived.mockReset().mockResolvedValue({ ticker: SOURCE_TICKER, archived: true });
  apiMocks.setDefaultWatchlist.mockReset().mockResolvedValue({ default_watchlist_id: 101 });
  apiMocks.setPriority.mockReset().mockResolvedValue({ ticker: SOURCE_TICKER, priority: "high" });
});

afterEach(() => {
  unmountWatchlist();
});

describe("Watchlist localization", () => {
  it("renders the reviewed zh-Hant Watchlist corrections and source values", async () => {
    await mountWatchlist();
    await waitForText(SOURCE_TICKER);

    const text = host!.textContent ?? "";
    for (const expected of [
      "自選股",
      SOURCE_LIST,
      SOURCE_TICKER,
      SOURCE_TAG_VALUE,
      "價格",
      "7 日漲跌",
      "新聞",
      "優先順序",
      "標籤",
      "操作",
      "低",
    ]) expect(text).toContain(expected);
    expect(host!.querySelector('th[title="Finnhub 分析師共識（每日快取）"]')).not.toBeNull();
    expect(host!.querySelector(`.tagchip[title*="${SOURCE_TAG_SOURCE}"]`)).not.toBeNull();
    expect(rowForTicker(SOURCE_TICKER).querySelector<HTMLElement>(".note-dot")?.title).toBe("2 筆筆記");
    expect(host!.innerHTML).not.toContain("設定優先級");
    expect(text).not.toContain("Chg 7d");

    unmountWatchlist();
    apiMocks.getUniverse.mockResolvedValueOnce({ ...UNIVERSE, rows: [] });
    await mountWatchlist();
    await waitForText("這個清單還沒有標的");
    expect(host!.textContent).toContain(
      "這個清單還沒有標的 — 用上方搜尋加入（或試試顯示已封存）。",
    );
  });

  it("renders English Watchlist chrome without translating custom lists tags or tickers", async () => {
    await switchLocale("en");
    await mountWatchlist();
    await waitForText(SOURCE_TICKER);

    const text = host!.textContent ?? "";
    for (const expected of [
      "Watchlist",
      "Price",
      "Chg 7d",
      "News",
      "Priority",
      "Tags",
      "Actions",
      "Show archived",
      SOURCE_LIST,
      SOURCE_TICKER,
      SOURCE_TAG_VALUE,
    ]) expect(text).toContain(expected);
    expect(rowForTicker(SOURCE_TICKER).querySelector<HTMLElement>(".note-dot")?.title).toBe("2 note(s)");
    expect(host!.querySelector(`.tagchip[title*="${SOURCE_TAG_SOURCE}"]`)?.textContent).toBe(
      SOURCE_TAG_VALUE,
    );
    expect(text).not.toContain("Source list");

    unmountWatchlist();
    apiMocks.getUniverse.mockResolvedValueOnce({ ...UNIVERSE, rows: [] });
    await mountWatchlist();
    await waitForText("This list has no tickers yet");
    expect(host!.textContent).toContain(
      "This list has no tickers yet — use the search above to add one (or try Show archived).",
    );
  });

  it("preserves list Universe consensus loading and degraded trigger semantics", async () => {
    const universeRequest = deferred<UniverseResponse>();
    const consensusRequest = deferred<ConsensusSummary>();
    apiMocks.getUniverse.mockReset().mockReturnValue(universeRequest.promise);
    apiMocks.getConsensus.mockReset().mockReturnValue(consensusRequest.promise);

    await mountWatchlist();
    expect(host!.textContent).toContain("載入中…");
    expect(apiMocks.getProfileLists).toHaveBeenCalledOnce();
    expect(apiMocks.getDefaultWatchlist).toHaveBeenCalledOnce();
    expect(apiMocks.getUniverse).toHaveBeenCalledWith(true);

    await act(async () => universeRequest.resolve(UNIVERSE));
    await waitForText(SOURCE_TICKER);
    expect(host!.querySelectorAll(".wl-consensus .muted").length).toBeGreaterThan(0);

    await act(async () => consensusRequest.reject(structuredError()));
    await flush();
    expect(host!.querySelectorAll('span[title="載入失敗，重新整理可重試"]')).toHaveLength(2);
    expect(host!.textContent).not.toContain("THEME-ONLY");
    expect(host!.querySelector("[role='alert']")).toBeNull();
  });

  it("renders visible Watchlist failures by operation without raw detail", async () => {
    apiMocks.getUniverse.mockReset().mockRejectedValue(structuredError());
    await mountWatchlist();
    await waitForText("無法載入全部標的。");
    expect(host!.innerHTML).not.toContain(RAW_ERROR);
    expect(host!.innerHTML).not.toContain("sk-private");

    unmountWatchlist();
    apiMocks.getUniverse.mockReset().mockResolvedValue(UNIVERSE);
    apiMocks.setArchived.mockReset().mockRejectedValue(
      structuredError("archive_fixture_failed", `/profile/tickers/${SOURCE_TICKER}/archive`),
    );
    await mountWatchlist();
    await waitForText(SOURCE_TICKER);
    const actions = rowForTicker(SOURCE_TICKER).querySelectorAll<HTMLButtonElement>(".rowactions button");
    await click(actions[actions.length - 1]!);
    await waitForText("無法更新標的封存狀態。");
    expect(host!.innerHTML).not.toContain(RAW_ERROR);
    expect(host!.innerHTML).not.toContain(RAW_DIAGNOSTIC);
  });

  it("preserves selected list archived filter and sort across locale switch", async () => {
    await mountWatchlist();
    await waitForText(SOURCE_TICKER);
    await click(buttonByText("顯示已封存"));
    const tickerHeading = Array.from(host!.querySelectorAll<HTMLTableCellElement>("th"))
      .find((heading) => heading.textContent?.includes("Ticker"))!;
    await click(tickerHeading);
    const orderBefore = visibleTickers();
    expect(orderBefore).toEqual(["AAA.US", "ARCH.SRC", SOURCE_TICKER]);

    await switchLocale("en");
    expect(host!.querySelector(".wl-railitem.active")?.textContent).toContain(SOURCE_LIST);
    expect(host!.querySelector(".surface-head .btn-ghost.on")?.textContent).toContain("Archived");
    expect(visibleTickers()).toEqual(orderBefore);
    expect(tickerHeading.classList.contains("active")).toBe(true);
    expect(tickerHeading.textContent).toContain("▲");
  });

  it("preserves create rename and member-search drafts across locale switch", async () => {
    await mountWatchlist();
    await waitForText(SOURCE_TICKER);
    await click(host!.querySelector(".wl-railadd")!);
    const createDraft = host!.querySelector<HTMLInputElement>('input[placeholder="清單名稱…"]')!;
    await setInput(createDraft, "CREATE 草稿 <keep>");

    const sourceRail = Array.from(host!.querySelectorAll<HTMLElement>(".wl-railitem"))
      .find((item) => item.textContent?.includes(SOURCE_LIST))!;
    await click(Array.from(sourceRail.querySelectorAll("button")).find((button) => button.textContent === "✎")!);
    const renameDraft = Array.from(host!.querySelectorAll<HTMLInputElement>(".wl-railedit input"))
      .find((input) => input.value === SOURCE_LIST)!;
    await setInput(renameDraft, "RENAME 草稿 <keep>");

    const memberDraft = host!.querySelector<HTMLInputElement>(".wl-addbox input")!;
    await setInput(memberDraft, "src draft");
    await flush(230);
    await waitForText(SOURCE_SEARCH_NAME);

    await switchLocale("en");
    expect(createDraft.value).toBe("CREATE 草稿 <keep>");
    expect(renameDraft.value).toBe("RENAME 草稿 <keep>");
    expect(memberDraft.value).toBe("src draft");
    expect(createDraft.placeholder).toBe("List name…");
    expect(memberDraft.placeholder).toContain(SOURCE_LIST);
    expect(memberDraft.placeholder).toContain("Add a ticker");
    expect(host!.textContent).toContain(SOURCE_SEARCH_NAME);
    expect(apiMocks.searchSymbols).toHaveBeenCalledWith("src draft", 8);
  });

  it("keeps optimistic priority work in flight and renders completion in the active locale", async () => {
    const priorityRequest = deferred<{ ticker: string; priority: string | null }>();
    apiMocks.setPriority.mockReset().mockReturnValue(priorityRequest.promise);
    await mountWatchlist();
    await waitForText(SOURCE_TICKER);
    const priority = rowForTicker(SOURCE_TICKER).querySelector<HTMLSelectElement>(".prio-select")!;

    await change(priority, "high");
    expect(priority.value).toBe("high");
    expect(priority.selectedOptions[0]?.textContent).toBe("高");
    expect(apiMocks.setPriority).toHaveBeenCalledTimes(1);

    await switchLocale("en");
    expect(priority.value).toBe("high");
    expect(priority.selectedOptions[0]?.textContent).toBe("high");
    await act(async () => priorityRequest.resolve({ ticker: SOURCE_TICKER, priority: "high" }));
    await flush();
    expect(apiMocks.setPriority).toHaveBeenCalledWith(SOURCE_TICKER, "high");
    expect(apiMocks.getUniverse).toHaveBeenCalledTimes(1);
    expect(host!.textContent).toContain("Watchlist");
  });

  it("does not replay list membership archive or priority mutations on locale switch", async () => {
    await mountWatchlist();
    await waitForText(SOURCE_TICKER);

    let actions = rowForTicker(SOURCE_TICKER).querySelectorAll<HTMLButtonElement>(".rowactions button");
    await click(actions[1]!);
    actions = rowForTicker(SOURCE_TICKER).querySelectorAll<HTMLButtonElement>(".rowactions button");
    await click(actions[actions.length - 1]!);
    await change(rowForTicker(SOURCE_TICKER).querySelector<HTMLSelectElement>(".prio-select")!, "medium");

    expect(apiMocks.removeMember).toHaveBeenCalledTimes(1);
    expect(apiMocks.setArchived).toHaveBeenCalledTimes(1);
    expect(apiMocks.setPriority).toHaveBeenCalledTimes(1);
    const before = requestCounts();
    await switchLocale("en");
    expect(requestCounts()).toEqual(before);
    expect(apiMocks.removeMember).toHaveBeenCalledWith(101, SOURCE_TICKER);
    expect(apiMocks.setArchived).toHaveBeenCalledWith(SOURCE_TICKER, true);
    expect(apiMocks.setPriority).toHaveBeenCalledWith(SOURCE_TICKER, "medium");
    expect(host!.textContent).toContain("Watchlist");
  });

  it("keeps silent list default and search degradation silent", async () => {
    apiMocks.getProfileLists.mockReset().mockRejectedValue(new Error("RAW silent list failure"));
    await mountWatchlist();
    await flush();
    expect(host!.querySelector("[role='alert']")).toBeNull();
    expect(host!.innerHTML).not.toContain("RAW silent list failure");

    unmountWatchlist();
    apiMocks.getProfileLists.mockReset().mockResolvedValue({ lists: LISTS });
    apiMocks.setDefaultWatchlist.mockReset().mockRejectedValue(new Error("RAW silent default failure"));
    apiMocks.searchSymbols.mockReset().mockRejectedValue(new Error("RAW silent search failure"));
    await mountWatchlist();
    await waitForText(SOURCE_TICKER);
    const sourceRail = Array.from(host!.querySelectorAll<HTMLElement>(".wl-railitem"))
      .find((item) => item.textContent?.includes(SOURCE_LIST))!;
    await click(Array.from(sourceRail.querySelectorAll<HTMLButtonElement>("button"))
      .find((button) => button.textContent === "★")!);
    const search = host!.querySelector<HTMLInputElement>(".wl-addbox input")!;
    await setInput(search, "silent search");
    await flush(230);

    expect(apiMocks.setDefaultWatchlist).toHaveBeenCalledWith(null);
    expect(apiMocks.searchSymbols).toHaveBeenCalledWith("silent search", 8);
    expect(host!.querySelector("[role='alert']")).toBeNull();
    expect(host!.innerHTML).not.toContain("RAW silent");
    await switchLocale("en");
    expect(host!.textContent).toContain("Watchlist");
  });

  it("renders consensus chrome locally while preserving Provider payload values", async () => {
    apiMocks.getConsensus.mockReset().mockImplementation((ticker: string) => {
      if (ticker === "AAA.US") {
        return Promise.resolve({
          ...CONSENSUS,
          ticker,
          rating: null,
          status: "provider_error",
          message: RAW_PROVIDER_MESSAGE,
        });
      }
      return Promise.resolve({ ...CONSENSUS, ticker });
    });
    await mountWatchlist();
    await waitForText("Strong Buy");

    const consensus = rowForTicker(SOURCE_TICKER).querySelector<HTMLElement>(".consensus-tag")!;
    expect(consensus.textContent).toContain("Strong Buy");
    expect(consensus.textContent).toContain("7/4/3/1/0");
    expect(consensus.title).toContain("強力買進 7");
    expect(consensus.title).toContain("SOURCE_FET");
    expect(consensus.title).toContain("（快取）");
    expect(rowForTicker("AAA.US").querySelector<HTMLElement>(".wl-consensus span")?.title).toBe(
      "分析師資料來源錯誤；重新整理可重試",
    );
    expect(host!.innerHTML).not.toContain(RAW_PROVIDER_MESSAGE);

    await switchLocale("en");
    expect(consensus.textContent).toContain("Strong Buy");
    expect(consensus.textContent).toContain("7/4/3/1/0");
    expect(consensus.title).toContain("Strong buy 7");
    expect(consensus.title).toContain("(cached)");
    expect(rowForTicker("AAA.US").querySelector<HTMLElement>(".wl-consensus span")?.title).toBe(
      "Analyst data-source error; refresh to retry",
    );
  });

  it("preserves node identity focus and Explore request counts during locale switch", async () => {
    await mountWatchlist();
    await waitForText(SOURCE_TICKER);
    const row = rowForTicker(SOURCE_TICKER);
    const rail = host!.querySelector(".wl-railitem.active");
    const priority = row.querySelector<HTMLSelectElement>(".prio-select")!;
    priority.focus();
    host!.scrollTop = 173;
    const before = requestCounts();
    expect(before).toEqual({
      addMember: 0,
      createList: 0,
      deleteList: 0,
      getConsensus: 2,
      getDefaultWatchlist: 1,
      getProfileLists: 1,
      getUniverse: 1,
      removeMember: 0,
      renameList: 0,
      searchSymbols: 0,
      setArchived: 0,
      setDefaultWatchlist: 0,
      setPriority: 0,
    });

    await switchLocale("en");
    expect(rowForTicker(SOURCE_TICKER)).toBe(row);
    expect(host!.querySelector(".wl-railitem.active")).toBe(rail);
    expect(row.querySelector(".prio-select")).toBe(priority);
    expect(document.activeElement).toBe(priority);
    expect(host!.scrollTop).toBe(173);
    expect(requestCounts()).toEqual(before);
    expect(host!.textContent).toContain("Watchlist");
  });
});
