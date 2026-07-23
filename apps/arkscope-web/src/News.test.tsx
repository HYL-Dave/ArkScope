/** @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import i18n from "i18next";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  NewsFeedItem,
  NewsFeedResponse,
  SAFeedResponse,
} from "./api";
import type { NavigationTarget } from "./shell/navigation";

const apiMocks = vi.hoisted(() => ({
  getNewsFeed: vi.fn(),
  getSAFeed: vi.fn(),
}));

vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return {
    ...actual,
    getNewsFeed: apiMocks.getNewsFeed,
    getSAFeed: apiMocks.getSAFeed,
  };
});

import { NewsView } from "./News";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

const MARKET_TITLE = "SOURCE Market headline / 保留 <keep>";
const MARKET_BODY = "SOURCE Market body / 原文 <keep>";
const MARKET_PUBLISHER = "Provider A / 原值";
const SA_TITLE = "SOURCE Seeking Alpha analysis / 保留 <keep>";
const SA_SNIPPET = "SOURCE SA snippet / 原文 <keep>";
const RAW_ERROR = "RAW postgres://admin:secret@10.0.0.8/news";
const RAW_DIAGNOSTIC = "Authorization: Bearer sk-private\nTraceback /srv/private.py:42";

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

const marketRows: NewsFeedItem[] = [
  {
    published_at: "2026-07-17T04:00:00Z",
    ticker: "FULL",
    title: MARKET_TITLE,
    url: "https://example.test/full",
    publisher: MARKET_PUBLISHER,
    source: "ibkr",
    description: MARKET_BODY,
    content_availability: "full",
    content_recovery: null,
  },
  {
    published_at: "2026-07-17T03:00:00Z",
    ticker: "RETRY",
    title: "Retryable headline",
    url: "https://example.test/retry",
    publisher: "Provider B",
    source: "ibkr",
    description: null,
    content_availability: "headline_only",
    content_recovery: "retryable",
  },
  {
    published_at: "2026-07-17T02:00:00Z",
    ticker: "TERM",
    title: "Terminal headline",
    url: "https://example.test/terminal",
    publisher: "Provider C",
    source: "finnhub",
    description: null,
    content_availability: "headline_only",
    content_recovery: "terminal",
  },
  {
    published_at: "2026-07-17T01:00:00Z",
    ticker: "UNKNOWN",
    title: "Unknown body state",
    url: null,
    publisher: null,
    source: "polygon",
    description: null,
    content_availability: "unknown",
    content_recovery: null,
  },
];

function marketFeed(over: Partial<NewsFeedResponse> = {}): NewsFeedResponse {
  return {
    available: true,
    items: marketRows,
    total: marketRows.length,
    sources: { ibkr: 2, finnhub: 1, polygon: 1 },
    days: { "2026-07-17": marketRows.length },
    content_counts: { full: 1, headline_only: 2, unknown: 1 },
    ...over,
  };
}

function oldSidecarFeed(): NewsFeedResponse {
  return {
    available: true,
    items: [
      {
        published_at: "2026-07-17T05:00:00Z",
        ticker: "OLD",
        title: "Old sidecar article",
        url: null,
        publisher: null,
        source: "finnhub",
        description: null,
        content_availability: "headline_only",
        content_recovery: "terminal",
      },
    ],
    total: 1,
    sources: { finnhub: 1 },
    days: { "2026-07-17": 1 },
  };
}

const saFeed: SAFeedResponse = {
  available: true,
  days: 7,
  query: null,
  total: 1,
  items: [
    {
      type: "article",
      id: "sa-1",
      title: SA_TITLE,
      tickers: ["SA"],
      published_at: "2026-07-17T03:00:00Z",
      url: "https://example.test/sa",
      source: "seeking_alpha",
      snippet: SA_SNIPPET,
      has_detail: true,
      comments_count: 1234,
      detail_route: null,
    },
  ],
  by_type: { article: 1 },
  by_day: { "2026-07-17": 1 },
  empty_reason: null,
};

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
  code = "news_fixture_failed",
  path = "/news/feed?q=private#fragment",
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

async function pressKey(element: Element, key: string) {
  await act(async () => {
    element.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true }));
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

function unmountNews() {
  if (root) act(() => root!.unmount());
  root = null;
  host?.remove();
  host = null;
}

async function mount({
  developerMode = false,
  onOpenTicker = vi.fn(),
  onNavigateTarget = vi.fn(),
}: {
  developerMode?: boolean;
  onOpenTicker?: (ticker: string) => void;
  onNavigateTarget?: (target: NavigationTarget) => void;
} = {}) {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(
      <NewsView
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

function selectWithOption(value: string): HTMLSelectElement {
  const select = Array.from(host!.querySelectorAll<HTMLSelectElement>("select"))
    .find((candidate) => candidate.querySelector(`option[value="${value}"]`));
  if (!select) throw new Error(`select not found for option: ${value}`);
  return select;
}

function contentSelect(): HTMLSelectElement {
  return selectWithOption("headline_only");
}

function sourceSelect(): HTMLSelectElement {
  return selectWithOption("polygon");
}

function modeSelect(): HTMLSelectElement {
  return selectWithOption("sa");
}

function buttonByText(text: string): HTMLButtonElement {
  const button = Array.from(host!.querySelectorAll<HTMLButtonElement>("button"))
    .find((candidate) => candidate.textContent?.includes(text));
  if (!button) throw new Error(`button not found: ${text}; rendered=${host!.textContent ?? ""}`);
  return button;
}

function requestCounts() {
  return {
    market: apiMocks.getNewsFeed.mock.calls.length,
    seekingAlpha: apiMocks.getSAFeed.mock.calls.length,
  };
}

beforeEach(async () => {
  await i18n.changeLanguage("zh-Hant");
  document.documentElement.lang = "zh-Hant";
  apiMocks.getNewsFeed.mockReset().mockResolvedValue(marketFeed());
  apiMocks.getSAFeed.mockReset().mockResolvedValue(saFeed);
});

afterEach(() => {
  unmountNews();
});

describe("News content availability", () => {
  it("shows content facet counts and only honest non-full row labels", async () => {
    await mount();

    const select = contentSelect();
    const options = Array.from(select.options).map((option) => option.textContent);
    expect(options).toEqual([
      "全部 (4)",
      "有內文 (1)",
      "僅標題 (2)",
      "狀態不明 (1)",
    ]);
    expect(Array.from(host!.querySelectorAll(".list-chip")).map((chip) => chip.textContent))
      .toEqual(["僅標題 · 內文待處理", "僅標題 · 來源未提供內文", "內文狀態不明"]);

    const before = requestCounts();
    await switchLocale("en");
    expect(contentSelect()).toBe(select);
    expect(Array.from(select.options).map((option) => option.textContent)).toEqual([
      "All (4)",
      "With content (1)",
      "Title only (2)",
      "Unknown state (1)",
    ]);
    expect(Array.from(host!.querySelectorAll(".list-chip")).map((chip) => chip.textContent))
      .toEqual([
        "Title only · Content pending",
        "Title only · Source did not provide content",
        "Content state unknown",
      ]);
    expect(requestCounts()).toEqual(before);
  });

  it("changing the content filter replaces page one and sends the selector", async () => {
    apiMocks.getNewsFeed.mockImplementation(async (params: Record<string, unknown>) => (
      params.content === "headline_only"
        ? marketFeed({ items: [marketRows[2]], total: 1 })
        : marketFeed()
    ));
    await mount();

    const select = contentSelect();
    await change(select, "headline_only");
    await waitForText("Terminal headline");

    expect(apiMocks.getNewsFeed).toHaveBeenLastCalledWith(expect.objectContaining({
      content: "headline_only",
      offset: 0,
    }));
    expect(host!.textContent).not.toContain(MARKET_TITLE);

    const before = requestCounts();
    await switchLocale("en");
    expect(contentSelect()).toBe(select);
    expect(select.value).toBe("headline_only");
    expect(select.selectedOptions[0]?.textContent).toBe("Title only (2)");
    expect(host!.textContent).toContain("Title only · Source did not provide content");
    expect(requestCounts()).toEqual(before);
  });

  it("resets a selected unknown filter when another facet has no unknown rows", async () => {
    apiMocks.getNewsFeed.mockImplementation(async (params: Record<string, unknown>) => {
      if (params.source === "finnhub") {
        const contentCounts = { full: 1, headline_only: 0, unknown: 0 };
        return params.content === "all"
          ? marketFeed({ items: [marketRows[0]], total: 1, content_counts: contentCounts })
          : marketFeed({ items: [], total: 0, content_counts: contentCounts });
      }
      if (params.content === "unknown") {
        return marketFeed({ items: [marketRows[3]], total: 1 });
      }
      return marketFeed();
    });
    await mount();

    await change(contentSelect(), "unknown");
    await waitForText("Unknown body state");
    await change(sourceSelect(), "finnhub");
    await waitForText(MARKET_TITLE);

    const select = contentSelect();
    const options = Array.from(select.options).map((option) => option.textContent);
    expect(options).toEqual(["全部 (1)", "有內文 (1)", "僅標題 (0)"]);
    expect(options).not.toContain("狀態不明 (0)");
    expect(select.value).toBe("all");
    expect(apiMocks.getNewsFeed).toHaveBeenLastCalledWith(expect.objectContaining({
      source: "finnhub",
      content: "all",
      offset: 0,
    }));

    const before = requestCounts();
    await switchLocale("en");
    expect(contentSelect()).toBe(select);
    expect(Array.from(select.options).map((option) => option.textContent))
      .toEqual(["All (1)", "With content (1)", "Title only (0)"]);
    expect(select.value).toBe("all");
    expect(requestCounts()).toEqual(before);
  });

  it("old-sidecar responses hide the filter and never guess row labels", async () => {
    apiMocks.getNewsFeed.mockImplementation(async (params: Record<string, unknown>) => (
      params.source === "polygon" ? oldSidecarFeed() : marketFeed()
    ));
    await mount();

    await change(contentSelect(), "headline_only");
    await change(sourceSelect(), "polygon");
    await waitForText("Old sidecar article");

    expect(host!.querySelector('select[title="內文狀態"]')).toBeNull();
    expect(host!.textContent).not.toContain("僅標題 ·");
    expect(host!.textContent).not.toContain("內文狀態不明");

    const before = requestCounts();
    await switchLocale("en");
    expect(host!.querySelector('select[title="Content state"]')).toBeNull();
    expect(host!.textContent).toContain("Old sidecar article");
    expect(host!.textContent).not.toContain("Title only ·");
    expect(host!.textContent).not.toContain("Content state unknown");
    expect(host!.querySelector(".surface-title")?.textContent).toBe("News · Events");
    expect(requestCounts()).toEqual(before);
  });

  it("load more preserves the selected content filter", async () => {
    apiMocks.getNewsFeed.mockImplementation(async (params: Record<string, unknown>) => {
      if (params.content !== "headline_only") return marketFeed();
      if (params.offset === 50) {
        return marketFeed({ items: [marketRows[1]], total: 2 });
      }
      return marketFeed({ items: [marketRows[2]], total: 2 });
    });
    await mount();

    await change(contentSelect(), "headline_only");
    const firstItem = host!.querySelector(".news-item");
    await click(buttonByText("載入更多"));
    await waitForText("Retryable headline");

    expect(apiMocks.getNewsFeed).toHaveBeenLastCalledWith(expect.objectContaining({
      content: "headline_only",
      offset: 50,
    }));
    expect(host!.textContent).toContain("Terminal headline");

    const before = requestCounts();
    await switchLocale("en");
    expect(host!.querySelector(".news-item")).toBe(firstItem);
    expect(host!.textContent).toContain("Terminal headline");
    expect(host!.textContent).toContain("Retryable headline");
    expect(host!.textContent).toContain("Title only · Source did not provide content");
    expect(host!.textContent).toContain("Title only · Content pending");
    expect(requestCounts()).toEqual(before);
  });

  it("seeking alpha mode has no market content filter or market content labels", async () => {
    await mount();
    expect(contentSelect()).toBeTruthy();

    const query = host!.querySelector<HTMLInputElement>(".news-search")!;
    await setInput(query, "sa source query");
    await pressKey(query, "Enter");
    const mode = modeSelect();
    await change(mode, "sa");
    await waitForText(SA_TITLE);

    const type = selectWithOption("article");
    await change(type, "article");
    await waitForText(SA_TITLE);

    expect(host!.querySelector('select[title="內文狀態"]')).toBeNull();
    expect(host!.textContent).not.toContain("僅標題 · 內文待處理");
    expect(host!.textContent).not.toContain("來源未提供內文");
    expect(host!.textContent).not.toContain("內文狀態不明");
    expect(host!.querySelector(".news-stats")?.textContent).toContain("· 搜尋「sa source query」");
    expect(host!.querySelector(".news-stats")?.textContent).not.toContain("按相關性排序");
    expect(apiMocks.getSAFeed).toHaveBeenCalled();
    expect(apiMocks.getSAFeed).toHaveBeenLastCalledWith(expect.objectContaining({
      q: "sa source query",
      item_type: "article",
    }));
    expect(apiMocks.getSAFeed.mock.calls.at(-1)?.[0]).not.toHaveProperty("content");
    expect(host!.querySelector(".news-meta")?.textContent).toBe("SA · 💬 1,234 · 原文 ↗");

    const article = host!.querySelector(".news-item");
    const before = requestCounts();
    await switchLocale("en");
    expect(modeSelect()).toBe(mode);
    expect(selectWithOption("article")).toBe(type);
    expect(type.value).toBe("article");
    expect(host!.querySelector(".news-item")).toBe(article);
    expect(host!.querySelector('select[title="Content state"]')).toBeNull();
    expect(host!.querySelector(".list-chip")?.textContent).toBe("Analysis article");
    expect(host!.textContent).toContain(SA_TITLE);
    expect(host!.textContent).toContain(SA_SNIPPET);
    expect(host!.querySelector(".news-meta")?.textContent).toBe("SA · 💬 1,234 · Original ↗");
    expect(host!.querySelector(".news-stats")?.textContent).toContain("· Search “sa source query”");
    expect(host!.querySelector(".news-stats")?.textContent)
      .not.toContain("sorted by relevance with title weighting");
    expect(host!.querySelector<HTMLAnchorElement>(`.news-title[href="${saFeed.items[0].url}"]`))
      .not.toBeNull();
    expect(requestCounts()).toEqual(before);
  });
});

describe("News localization", () => {
  it("renders English News chrome while preserving Market source content", async () => {
    await switchLocale("en");
    const onOpenTicker = vi.fn();
    await mount({ onOpenTicker });

    expect(host!.querySelector(".surface-title")?.textContent).toBe("News · Events");
    expect(host!.querySelector(".surface-head .muted")?.textContent).toBe(
      "Local news store (score-free) · Search terms use AND",
    );
    expect(modeSelect().title).toBe("Source");
    expect(modeSelect().querySelector('option[value="market"]')?.textContent).toBe("Market News");
    expect(sourceSelect().title).toBe("Source");
    expect(sourceSelect().querySelector('option[value="auto"]')?.textContent).toBe("All sources");
    expect(contentSelect().title).toBe("Content state");
    expect(host!.querySelector<HTMLInputElement>(".news-search")?.placeholder)
      .toBe("Search titles/summaries (Enter)");
    expect(host!.querySelector<HTMLInputElement>(".news-ticker")?.placeholder)
      .toBe("Ticker (Enter)");
    expect(Array.from(selectWithOption("365").options).map((option) => option.textContent))
      .toEqual(["7 days", "30 days", "90 days", "365 days"]);
    expect(host!.querySelector(".news-stats")?.textContent).toContain("Total 4 articles");
    expect(host!.querySelector(".news-stats")?.textContent).toContain("ibkr 2");
    expect(host!.textContent).toContain(MARKET_TITLE);
    expect(host!.textContent).toContain(MARKET_BODY);
    expect(host!.textContent).toContain(`${MARKET_PUBLISHER} · ibkr`);
    expect(host!.querySelector<HTMLAnchorElement>(`.news-title[href="${marketRows[0].url}"]`))
      .not.toBeNull();

    const ticker = Array.from(host!.querySelectorAll<HTMLButtonElement>(".news-ticker-chip"))
      .find((button) => button.textContent === "FULL")!;
    expect(ticker.title).toBe("Open FULL");
    await click(ticker);
    expect(onOpenTicker).toHaveBeenCalledWith("FULL");
    expect(onOpenTicker).toHaveBeenCalledTimes(1);
  });

  it("switches locale without resetting filters pagination items or refetching", async () => {
    const pageTwo = { ...marketRows[1], title: "SOURCE page two / 保留" };
    const pageThree = { ...marketRows[2], title: "SOURCE page three / 保留" };
    apiMocks.getNewsFeed.mockImplementation(async (params: Record<string, unknown>) => {
      if (params.offset === 50) return marketFeed({ items: [pageTwo], total: 3 });
      if (params.offset === 100) return marketFeed({ items: [pageThree], total: 3 });
      return marketFeed({ items: [marketRows[0]], total: 3 });
    });
    await mount();

    const query = host!.querySelector<HTMLInputElement>(".news-search")!;
    const ticker = host!.querySelector<HTMLInputElement>(".news-ticker")!;
    const source = sourceSelect();
    const content = contentSelect();
    const days = selectWithOption("365");
    await setInput(query, "source query");
    await pressKey(query, "Enter");
    await setInput(ticker, "mix.tw");
    await pressKey(ticker, "Enter");
    await change(source, "ibkr");
    await change(content, "full");
    await change(days, "30");
    await click(buttonByText("載入更多"));
    await waitForText(pageTwo.title);

    const firstItem = host!.querySelectorAll(".news-item")[0];
    const secondItem = host!.querySelectorAll(".news-item")[1];
    const more = buttonByText("載入更多");
    query.focus();
    expect(document.activeElement).toBe(query);
    const before = requestCounts();

    await switchLocale("en");

    expect(host!.querySelector<HTMLInputElement>(".news-search")).toBe(query);
    expect(host!.querySelector<HTMLInputElement>(".news-ticker")).toBe(ticker);
    expect(sourceSelect()).toBe(source);
    expect(contentSelect()).toBe(content);
    expect(selectWithOption("365")).toBe(days);
    expect(host!.querySelectorAll(".news-item")[0]).toBe(firstItem);
    expect(host!.querySelectorAll(".news-item")[1]).toBe(secondItem);
    expect(buttonByText("Load more")).toBe(more);
    expect(query.value).toBe("source query");
    expect(ticker.value).toBe("mix.tw");
    expect(source.value).toBe("ibkr");
    expect(content.value).toBe("full");
    expect(days.value).toBe("30");
    expect(more.textContent).toContain("Load more (2/3)");
    expect(host!.querySelector(".news-stats")?.textContent).toContain(
      "Search “source query” (sorted by relevance with title weighting)",
    );
    expect(document.activeElement).toBe(query);
    expect(requestCounts()).toEqual(before);

    await click(more);
    await waitForText(pageThree.title);
    expect(apiMocks.getNewsFeed).toHaveBeenLastCalledWith({
      q: "source query",
      ticker: "MIX.TW",
      source: "ibkr",
      content: "full",
      days: 30,
      limit: 50,
      offset: 100,
    });
    expect(host!.textContent).toContain(MARKET_TITLE);
    expect(host!.textContent).toContain(pageTwo.title);
    expect(host!.textContent).toContain(pageThree.title);
  });

  it("renders Market and Seeking Alpha load failures without raw detail", async () => {
    apiMocks.getNewsFeed.mockReset().mockRejectedValue(
      structuredError("market_fixture_failed", "/news/feed?q=private"),
    );
    await mount();
    await waitForText("無法載入市場新聞。");
    expect(host!.querySelector("[role='alert']")?.textContent).toContain("重試");
    expect(host!.innerHTML).not.toContain(RAW_ERROR);
    expect(host!.innerHTML).not.toContain(RAW_DIAGNOSTIC);

    unmountNews();
    apiMocks.getNewsFeed.mockReset()
      .mockResolvedValueOnce(marketFeed({ items: [marketRows[2]], total: 2 }))
      .mockRejectedValueOnce(structuredError("more_fixture_failed", "/news/feed?offset=50"))
      .mockResolvedValueOnce(marketFeed({ items: [marketRows[1]], total: 2 }));
    await mount();
    await waitForText("Terminal headline");
    const terminalItem = host!.querySelector(".news-item");
    await click(buttonByText("載入更多"));
    await waitForText("無法載入更多新聞。");
    const failedPageRequest = apiMocks.getNewsFeed.mock.calls.at(-1)?.[0];
    expect(failedPageRequest).toEqual({
      q: undefined,
      ticker: undefined,
      source: "auto",
      content: "all",
      days: 7,
      limit: 50,
      offset: 50,
    });
    expect(host!.textContent).toContain("Terminal headline");
    expect(host!.innerHTML).not.toContain(RAW_ERROR);
    expect(host!.innerHTML).not.toContain(RAW_DIAGNOSTIC);
    await click(buttonByText("重試"));
    await waitForText("Retryable headline");
    expect(apiMocks.getNewsFeed.mock.calls.at(-1)?.[0]).toEqual(failedPageRequest);
    expect(apiMocks.getNewsFeed).toHaveBeenCalledTimes(3);
    expect(host!.querySelector(".news-item")).toBe(terminalItem);
    expect(host!.textContent).toContain("Terminal headline");
    expect(host!.textContent).toContain("Retryable headline");

    unmountNews();
    apiMocks.getNewsFeed.mockReset().mockResolvedValue(marketFeed());
    apiMocks.getSAFeed.mockReset().mockRejectedValue(
      structuredError("sa_fixture_failed", "/sa/feed?search=private"),
    );
    await mount();
    await change(modeSelect(), "sa");
    await waitForText("無法載入 Seeking Alpha 內容。");
    expect(host!.querySelector("[role='alert']")?.textContent).toContain("重試");
    expect(host!.innerHTML).not.toContain(RAW_ERROR);
    expect(host!.innerHTML).not.toContain(RAW_DIAGNOSTIC);
  });

  it("offers only the reviewed News and Data Sources recovery targets", async () => {
    const onNavigateTarget = vi.fn();
    apiMocks.getNewsFeed.mockReset().mockResolvedValue(marketFeed({
      available: false,
      items: [],
      total: 0,
      sources: {},
      days: {},
      content_counts: { full: 0, headline_only: 0, unknown: 0 },
    }));
    await mount({ onNavigateTarget });
    await waitForText("本地新聞庫尚未建立 — 到設定 → 市場資料建立本地市場庫。");
    await click(buttonByText("前往新聞資料"));
    expect(onNavigateTarget).toHaveBeenLastCalledWith({
      kind: "settings_section",
      section: "news_storage",
    });

    unmountNews();
    onNavigateTarget.mockClear();
    apiMocks.getNewsFeed.mockReset().mockResolvedValue(marketFeed());
    apiMocks.getSAFeed.mockReset().mockResolvedValue({
      ...saFeed,
      available: false,
      items: [],
      total: 0,
      by_type: {},
      by_day: {},
      empty_reason: "requires_local_sa",
    });
    await mount({ onNavigateTarget });
    await change(modeSelect(), "sa");
    await waitForText("Seeking Alpha 本地資料路徑尚未就緒。");
    await click(buttonByText("前往資料來源與排程"));
    expect(onNavigateTarget).toHaveBeenLastCalledWith({
      kind: "settings_section",
      section: "data_sources",
    });

    unmountNews();
    onNavigateTarget.mockClear();
    apiMocks.getSAFeed.mockReset().mockResolvedValue({
      ...saFeed,
      available: true,
      items: [],
      total: 0,
      by_type: {},
      by_day: {},
      empty_reason: "no_items_in_window",
    });
    await mount({ onNavigateTarget });
    await change(modeSelect(), "sa");
    await waitForText("此條件下沒有 Seeking Alpha 內容。");
    expect(host!.textContent).not.toContain("前往資料來源與排程");
    expect(host!.textContent).not.toContain("前往新聞資料");
    expect(onNavigateTarget).not.toHaveBeenCalled();

    unmountNews();
    apiMocks.getSAFeed.mockReset().mockRejectedValue(
      structuredError("sa_extension_health_unavailable", "/sa/extension-health"),
    );
    await mount({ onNavigateTarget });
    await change(modeSelect(), "sa");
    await waitForText("無法載入 Seeking Alpha 內容。");
    await click(buttonByText("前往資料來源與排程"));
    expect(onNavigateTarget).toHaveBeenLastCalledWith({
      kind: "settings_section",
      section: "data_sources",
    });

    unmountNews();
    onNavigateTarget.mockClear();
    apiMocks.getNewsFeed.mockReset().mockRejectedValue(
      structuredError("provider_config_missing", "/news/feed"),
    );
    await mount({ onNavigateTarget });
    await waitForText("無法載入市場新聞。");
    expect(host!.textContent).not.toContain("前往 Provider 登入與憑證");
    expect(host!.textContent).not.toContain("前往資料來源與排程");
    expect(host!.textContent).not.toContain("前往新聞資料");
    expect(onNavigateTarget).not.toHaveBeenCalled();
  });

  it("keeps an in-flight page response and renders completion in the active locale", async () => {
    const pageRequest = deferred<NewsFeedResponse>();
    apiMocks.getNewsFeed.mockImplementation((params: Record<string, unknown>) => (
      params.offset === 50
        ? pageRequest.promise
        : Promise.resolve(marketFeed({ items: [marketRows[2]], total: 2 }))
    ));
    await mount();
    await waitForText("Terminal headline");
    await click(buttonByText("載入更多"));
    expect(apiMocks.getNewsFeed).toHaveBeenCalledTimes(2);
    const before = requestCounts();

    await switchLocale("en");
    expect(requestCounts()).toEqual(before);
    await act(async () => pageRequest.resolve(marketFeed({
      items: [marketRows[1]],
      total: 2,
    })));
    await waitForText("Retryable headline");

    expect(host!.textContent).toContain("Terminal headline");
    expect(host!.textContent).toContain("Retryable headline");
    expect(host!.textContent).toContain("Title only · Source did not provide content");
    expect(host!.textContent).toContain("Title only · Content pending");
    expect(host!.textContent).not.toContain("僅標題 ·");
    expect(apiMocks.getNewsFeed).toHaveBeenLastCalledWith(expect.objectContaining({
      content: "all",
      offset: 50,
    }));
    expect(apiMocks.getNewsFeed).toHaveBeenCalledTimes(2);
  });
});
