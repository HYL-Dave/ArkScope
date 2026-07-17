/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { NewsFeedResponse, SAFeedResponse } from "./api";
import { NewsView } from "./News";

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

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

const marketRows = [
  {
    published_at: "2026-07-17T04:00:00Z",
    ticker: "FULL",
    title: "Full article",
    url: "https://example.test/full",
    publisher: "Provider A",
    source: "ibkr",
    description: "Full body",
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

function marketFeed(over: Record<string, unknown> = {}): NewsFeedResponse {
  return {
    available: true,
    items: marketRows,
    total: marketRows.length,
    sources: { ibkr: 2, finnhub: 1, polygon: 1 },
    days: { "2026-07-17": marketRows.length },
    content_counts: { full: 1, headline_only: 2, unknown: 1 },
    ...over,
  } as unknown as NewsFeedResponse;
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
      title: "Seeking Alpha analysis",
      tickers: ["SA"],
      published_at: "2026-07-17T03:00:00Z",
      url: "https://example.test/sa",
      source: "seeking_alpha",
      snippet: "Analysis summary",
      has_detail: true,
      comments_count: 0,
      detail_route: null,
    },
  ],
  by_type: { article: 1 },
  by_day: { "2026-07-17": 1 },
  empty_reason: null,
};

async function flush() {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

async function mount() {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(<NewsView onOpenTicker={vi.fn()} />);
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

async function waitForText(text: string) {
  for (let attempt = 0; attempt < 8; attempt += 1) {
    if (host?.textContent?.includes(text)) return;
    await flush();
  }
  throw new Error(`text not found: ${text}; rendered=${host?.textContent ?? ""}`);
}

function contentSelect(): HTMLSelectElement {
  const select = host!.querySelector<HTMLSelectElement>('select[title="內文狀態"]');
  if (!select) throw new Error(`content select not found; rendered=${host!.textContent}`);
  return select;
}

function sourceSelect(): HTMLSelectElement {
  const select = Array.from(host!.querySelectorAll<HTMLSelectElement>("select"))
    .find((candidate) => candidate.querySelector('option[value="polygon"]'));
  if (!select) throw new Error("market source select not found");
  return select;
}

function modeSelect(): HTMLSelectElement {
  const select = Array.from(host!.querySelectorAll<HTMLSelectElement>("select"))
    .find((candidate) => candidate.querySelector('option[value="sa"]'));
  if (!select) throw new Error("mode select not found");
  return select;
}

beforeEach(() => {
  apiMocks.getNewsFeed.mockReset().mockResolvedValue(marketFeed());
  apiMocks.getSAFeed.mockReset().mockResolvedValue(saFeed);
});

afterEach(() => {
  if (root) act(() => root!.unmount());
  root = null;
  host?.remove();
  host = null;
});

describe("News content availability", () => {
  it("shows content facet counts and only honest non-full row labels", async () => {
    await mount();

    const options = Array.from(contentSelect().options).map((option) => option.textContent);
    expect(options).toEqual([
      "全部 (4)",
      "有內文 (1)",
      "僅標題 (2)",
      "狀態不明 (1)",
    ]);
    expect(Array.from(host!.querySelectorAll(".list-chip")).map((chip) => chip.textContent))
      .toEqual(["僅標題 · 內文待處理", "僅標題 · 來源未提供內文", "內文狀態不明"]);
  });

  it("changing the content filter replaces page one and sends the selector", async () => {
    apiMocks.getNewsFeed.mockImplementation(async (params: Record<string, unknown>) => (
      params.content === "headline_only"
        ? marketFeed({ items: [marketRows[2]], total: 1 })
        : marketFeed()
    ));
    await mount();

    await change(contentSelect(), "headline_only");
    await waitForText("Terminal headline");

    expect(apiMocks.getNewsFeed).toHaveBeenLastCalledWith(expect.objectContaining({
      content: "headline_only",
      offset: 0,
    }));
    expect(host!.textContent).not.toContain("Full article");
  });

  it("hides status-unknown option when its facet count is zero", async () => {
    apiMocks.getNewsFeed.mockResolvedValue(marketFeed({
      items: marketRows.slice(0, 3),
      total: 3,
      content_counts: { full: 1, headline_only: 2, unknown: 0 },
    }));
    await mount();

    const options = Array.from(contentSelect().options).map((option) => option.textContent);
    expect(options).toEqual(["全部 (3)", "有內文 (1)", "僅標題 (2)"]);
    expect(options).not.toContain("狀態不明 (0)");
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
    const more = Array.from(host!.querySelectorAll<HTMLButtonElement>("button"))
      .find((button) => button.textContent?.includes("載入更多"));
    expect(more).toBeDefined();
    await act(async () => more!.click());
    await waitForText("Retryable headline");

    expect(apiMocks.getNewsFeed).toHaveBeenLastCalledWith(expect.objectContaining({
      content: "headline_only",
      offset: 50,
    }));
    expect(host!.textContent).toContain("Terminal headline");
  });

  it("seeking alpha mode has no market content filter or market content labels", async () => {
    await mount();
    expect(contentSelect()).toBeTruthy();

    await change(modeSelect(), "sa");
    await waitForText("Seeking Alpha analysis");

    expect(host!.querySelector('select[title="內文狀態"]')).toBeNull();
    expect(host!.textContent).not.toContain("僅標題 · 內文待處理");
    expect(host!.textContent).not.toContain("來源未提供內文");
    expect(host!.textContent).not.toContain("內文狀態不明");
    expect(apiMocks.getSAFeed).toHaveBeenCalled();
    expect(apiMocks.getSAFeed.mock.calls.at(-1)?.[0]).not.toHaveProperty("content");
  });
});
