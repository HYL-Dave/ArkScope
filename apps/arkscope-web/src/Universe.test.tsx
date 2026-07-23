/** @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import i18n from "i18next";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ImportResult, UniverseResponse, WatchlistSummary } from "./api";
import type { NavigationTarget } from "./shell/navigation";

const apiMocks = vi.hoisted(() => ({
  getProfileLists: vi.fn(),
  getUniverse: vi.fn(),
  importUniverse: vi.fn(),
  setTickerHidden: vi.fn(),
}));

vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return { ...actual, ...apiMocks };
});

import { UniverseView } from "./Universe";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

const SOURCE_LIST = '來源清單 / Alpha <keep>';
const SOURCE_LIST_TWO = "Beta 客製清單";
const SOURCE_TICKER = "SRC.TW";
const SOURCE_CATEGORY = "category:Value/RAW";
const SOURCE_THEME = "theme:Momentum/RAW";
const UNKNOWN_FACET = "source_custom_axis";
const UNKNOWN_VALUE = "UNKNOWN VALUE / %2F";
const UNKNOWN_SOURCE = "provider:RAW/v1";
const RAW_ERROR = "RAW backend failure postgres://admin:secret@10.0.0.8/universe";
const RAW_DIAGNOSTIC = "Authorization: Bearer sk-private\nTraceback /srv/private.py:42";

const LISTS: WatchlistSummary[] = [
  {
    id: 201,
    name: SOURCE_LIST,
    kind: "custom",
    position: 0,
    archived: false,
    active_count: 2,
    total_count: 2,
  },
  {
    id: 202,
    name: SOURCE_LIST_TWO,
    kind: "custom",
    position: 1,
    archived: false,
    active_count: 1,
    total_count: 1,
  },
  {
    id: 203,
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
  total: 3,
  shown: 3,
  archived_count: 1,
  summarized: 2,
  rows: [
    {
      ticker: SOURCE_TICKER,
      has_summary: true,
      group: "SOURCE GROUP",
      priority: "source-priority/raw",
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
        { facet: "category", value: SOURCE_CATEGORY, source: "user" },
        { facet: "theme", value: SOURCE_THEME, source: "system" },
        { facet: UNKNOWN_FACET, value: UNKNOWN_VALUE, source: UNKNOWN_SOURCE },
      ],
      note_count: 2,
    },
    {
      ticker: "SECOND.US",
      has_summary: false,
      group: null,
      priority: null,
      latest_close: null,
      change_7d_pct: null,
      news_count_7d: 0,
      sentiment_mean: null,
      bullish_ratio: null,
      lists: [SOURCE_LIST_TWO],
      all_lists: [SOURCE_LIST_TWO],
      archived_lists: [],
      archived: false,
      tags: [{ facet: "category", value: "OTHER CATEGORY", source: "legacy" }],
      note_count: 0,
    },
    {
      ticker: "ARCH.SRC",
      has_summary: true,
      group: null,
      priority: "medium",
      latest_close: 70,
      change_7d_pct: -2,
      news_count_7d: 1,
      sentiment_mean: null,
      bullish_ratio: null,
      lists: [SOURCE_LIST],
      all_lists: [SOURCE_LIST],
      archived_lists: [SOURCE_LIST],
      archived: true,
      tags: [{ facet: "category", value: SOURCE_CATEGORY, source: "user" }],
      note_count: 1,
    },
  ],
};

const IMPORT_RESULT: ImportResult = {
  lists_removed: 3,
  tags: { tags_added: 7 },
  groups_ok: true,
  lists: [],
};

type RequestName = keyof typeof apiMocks;

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;
let confirmMock: typeof window.confirm;

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
  code = "universe_fixture_failed",
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

function unmountUniverse() {
  if (root) act(() => root!.unmount());
  root = null;
  host?.remove();
  host = null;
}

async function mountUniverse({
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
      <UniverseView
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

function selectWithOption(value: string): HTMLSelectElement {
  const select = Array.from(host!.querySelectorAll<HTMLSelectElement>("select"))
    .find((candidate) => candidate.querySelector(`option[value="${value}"]`));
  if (!select) throw new Error(`select not found for option: ${value}`);
  return select;
}

function requestCounts(): Record<RequestName, number> {
  return Object.fromEntries(
    Object.entries(apiMocks).map(([name, mock]) => [name, mock.mock.calls.length]),
  ) as Record<RequestName, number>;
}

beforeEach(async () => {
  await i18n.changeLanguage("zh-Hant");
  document.documentElement.lang = "zh-Hant";
  apiMocks.getProfileLists.mockReset().mockResolvedValue({ lists: LISTS });
  apiMocks.getUniverse.mockReset().mockResolvedValue(UNIVERSE);
  apiMocks.importUniverse.mockReset().mockResolvedValue(IMPORT_RESULT);
  apiMocks.setTickerHidden.mockReset().mockResolvedValue({ ticker: SOURCE_TICKER, hidden: true });
  confirmMock = vi.fn(() => true);
  window.confirm = confirmMock;
});

afterEach(() => {
  unmountUniverse();
});

describe("Universe localization", () => {
  it("renders the reviewed zh-Hant Universe title and terminology corrections", async () => {
    await mountUniverse();
    await waitForText(SOURCE_TICKER);

    const text = host!.textContent ?? "";
    expect(host!.querySelector(".surface-title")?.textContent).toBe("全部標的");
    for (const expected of [
      "收盤價",
      "7 日漲跌",
      "新聞",
      "清單",
      "標籤",
      "已封存",
      SOURCE_TICKER,
      SOURCE_LIST,
      SOURCE_CATEGORY,
    ]) expect(text).toContain(expected);
    expect(text).toContain("庫存來自全部標的設定");
    expect(text).toContain("既有設定種入分類標籤（類別 / 主題 / 來源）");
    expect(host!.querySelector(".surface-head .muted")?.textContent).toBe(
      "3 檔 · 2 有摘要 · 1 無摘要 · 1 已封存",
    );
    expect(host!.querySelector(".universe-select option")?.textContent).toBe("所有清單（2）");
    expect(selectWithOption(SOURCE_CATEGORY).querySelector('option[value=""]')?.textContent)
      .toBe("類別（全部）");
    expect(rowForTicker(SOURCE_TICKER).querySelector<HTMLElement>(".note-dot")?.title).toBe("2 筆記");
    expect(text).not.toContain("全部標的 · Universe");
  });

  it("renders English Universe chrome while preserving tickers tags and lists", async () => {
    await switchLocale("en");
    await mountUniverse();
    await waitForText(SOURCE_TICKER);

    const text = host!.textContent ?? "";
    expect(host!.querySelector(".surface-title")?.textContent).toBe("Universe");
    for (const expected of [
      "Close",
      "7d %",
      "News",
      "Lists",
      "Tags",
      "Import classifications",
      SOURCE_TICKER,
      SOURCE_LIST,
      SOURCE_CATEGORY,
      SOURCE_THEME,
      UNKNOWN_VALUE,
    ]) expect(text).toContain(expected);
    expect(host!.querySelector(`.tagchip[title*="${UNKNOWN_SOURCE}"]`)?.textContent).toBe(UNKNOWN_VALUE);
    expect(host!.querySelector(".surface-head .muted")?.textContent).toBe(
      "3 files · 2 with summary · 1 without summary · 1 archived",
    );
    expect(host!.querySelector(".universe-select option")?.textContent).toBe("All lists (2)");
    expect(selectWithOption(SOURCE_CATEGORY).querySelector('option[value=""]')?.textContent)
      .toBe("Category (All)");
    expect(text).not.toContain("files · 2 With summary");
    expect(text).not.toContain("Category(All)");
    expect(text).not.toContain("Source list");
  });

  it("renders active-universe failure with the exact Data Sources recovery target", async () => {
    const onNavigateTarget = vi.fn();
    apiMocks.getUniverse.mockReset().mockRejectedValue(
      structuredError("active_universe_unavailable", "/profile/universe"),
    );
    await mountUniverse({ onNavigateTarget });
    await waitForText("無法載入全部標的。");

    expect(host!.textContent).toContain("可從相關設定檢查資料來源與連線。");
    const recovery = buttonByText("前往資料來源與排程");
    await click(recovery);
    expect(onNavigateTarget).toHaveBeenCalledTimes(1);
    expect(onNavigateTarget).toHaveBeenCalledWith({
      kind: "settings_section",
      section: "data_sources",
    });
    expect(host!.innerHTML).not.toContain(RAW_ERROR);
    expect(host!.innerHTML).not.toContain(RAW_DIAGNOSTIC);

    unmountUniverse();
    onNavigateTarget.mockClear();
    apiMocks.getUniverse.mockReset().mockRejectedValue(
      structuredError("sa_extension_health_unavailable", "/profile/universe"),
    );
    await mountUniverse({ onNavigateTarget });
    await waitForText("無法載入全部標的。");
    expect(host!.textContent).not.toContain("前往資料來源與排程");
    expect(onNavigateTarget).not.toHaveBeenCalled();
  });

  it("renders structured import counts in both locales", async () => {
    const importRequest = deferred<ImportResult>();
    apiMocks.importUniverse.mockReset().mockReturnValue(importRequest.promise);
    await mountUniverse();
    await waitForText(SOURCE_TICKER);
    await click(buttonByText("匯入分類"));
    expect(host!.textContent).toContain("匯入中…");

    await switchLocale("en");
    expect(host!.textContent).toContain("Importing…");
    await act(async () => importRequest.resolve(IMPORT_RESULT));
    await waitForText("Import complete: Classification tags added: 7 · Legacy lists removed: 3.");
    expect(apiMocks.importUniverse).toHaveBeenCalledTimes(1);
    expect(apiMocks.importUniverse).toHaveBeenCalledWith({});

    await switchLocale("zh-Hant");
    expect(host!.textContent).toContain("匯入完成：新增 7 個分類標籤、移除 3 個舊清單。");
    expect(apiMocks.importUniverse).toHaveBeenCalledTimes(1);

    await click(Array.from(host!.querySelectorAll<HTMLButtonElement>(".surface-head button"))
      .find((button) => button.textContent?.includes("重新整理"))!);
    expect(host!.querySelector(".universe-importmsg")).toBeNull();
    expect(apiMocks.importUniverse).toHaveBeenCalledTimes(1);
  });

  it("preserves the groups-unavailable import warning without source-tag translation", async () => {
    apiMocks.importUniverse.mockReset().mockResolvedValue({ ...IMPORT_RESULT, groups_ok: false });
    await mountUniverse();
    await waitForText(SOURCE_TICKER);
    await click(buttonByText("匯入分類"));
    await waitForText("⚠ 主題來源暫時無法連線，已略過主題標籤。");

    expect(host!.textContent).toContain(SOURCE_THEME);
    expect(host!.textContent).toContain(UNKNOWN_VALUE);
    await switchLocale("en");
    expect(host!.textContent).toContain(
      "⚠ The theme source is temporarily unavailable, so theme tags were skipped.",
    );
    expect(host!.textContent).toContain(SOURCE_THEME);
    expect(host!.querySelector(`.tagchip[title*="${UNKNOWN_SOURCE}"]`)?.textContent).toBe(UNKNOWN_VALUE);
  });

  it("renders import failure without raw backend detail in normal mode", async () => {
    apiMocks.importUniverse.mockReset().mockRejectedValue(
      structuredError("import_fixture_failed", "/profile/import-universe"),
    );
    await mountUniverse();
    await waitForText(SOURCE_TICKER);
    await click(buttonByText("匯入分類"));
    await waitForText("無法匯入分類。");

    expect(host!.querySelector("[role='alert']")).not.toBeNull();
    expect(host!.querySelector("[aria-label='開發者診斷']")).toBeNull();
    expect(host!.innerHTML).not.toContain(RAW_ERROR);
    expect(host!.innerHTML).not.toContain(RAW_DIAGNOSTIC);

    await click(host!.querySelector<HTMLButtonElement>("[role='alert'] button")!);
    expect(host!.querySelector("[role='alert']")).toBeNull();
    expect(apiMocks.importUniverse).toHaveBeenCalledTimes(1);
  });

  it("preserves hide confirmation and renders hide failure by operation", async () => {
    const hideRequest = deferred<{ ticker: string; hidden: boolean }>();
    apiMocks.setTickerHidden.mockReset()
      .mockRejectedValueOnce(
        structuredError("hide_fixture_failed", `/profile/tickers/${SOURCE_TICKER}/hidden`),
      )
      .mockReturnValueOnce(hideRequest.promise);
    await mountUniverse();
    await waitForText(SOURCE_TICKER);
    await click(rowForTicker(SOURCE_TICKER).querySelector(".rowx")!);
    await waitForText("無法更新標的顯示狀態。");

    expect(confirmMock).toHaveBeenCalledWith(
      `從「全部標的」移除 ${SOURCE_TICKER}？（用於已下市/重複的代號）`,
    );
    expect(apiMocks.setTickerHidden).toHaveBeenCalledWith(SOURCE_TICKER, true);
    expect(host!.innerHTML).not.toContain(RAW_ERROR);
    expect(host!.innerHTML).not.toContain(RAW_DIAGNOSTIC);

    const hideButton = rowForTicker(SOURCE_TICKER).querySelector<HTMLButtonElement>(".rowx")!;
    await click(hideButton);
    expect(host!.querySelector("[role='alert']")).toBeNull();
    expect(hideButton.disabled).toBe(true);
    expect(apiMocks.setTickerHidden).toHaveBeenCalledTimes(2);
    await switchLocale("en");
    expect(apiMocks.setTickerHidden).toHaveBeenCalledTimes(2);
    await act(async () => hideRequest.resolve({ ticker: SOURCE_TICKER, hidden: true }));
    await flush();
    expect(host!.querySelector("[role='alert']")).toBeNull();
    expect(apiMocks.setTickerHidden).toHaveBeenCalledTimes(2);
  });

  it("switches locale without clearing query list facets outcome or busy ticker", async () => {
    const hiddenRequest = deferred<{ ticker: string; hidden: boolean }>();
    apiMocks.setTickerHidden.mockReset().mockReturnValue(hiddenRequest.promise);
    await mountUniverse();
    await waitForText(SOURCE_TICKER);
    await click(buttonByText("匯入分類"));
    await waitForText("匯入完成");

    const query = host!.querySelector<HTMLInputElement>(".universe-filters input")!;
    const list = selectWithOption(SOURCE_LIST);
    const category = selectWithOption(SOURCE_CATEGORY);
    await setInput(query, "src");
    await change(list, SOURCE_LIST);
    await change(category, SOURCE_CATEGORY);
    const busyButton = rowForTicker(SOURCE_TICKER).querySelector<HTMLButtonElement>(".rowx")!;
    await click(busyButton);
    expect(busyButton.disabled).toBe(true);
    const beforeSwitch = requestCounts();

    await switchLocale("en");
    expect(query.value).toBe("src");
    expect(list.value).toBe(SOURCE_LIST);
    expect(category.value).toBe(SOURCE_CATEGORY);
    expect(rowForTicker(SOURCE_TICKER).querySelector(".rowx")).toBe(busyButton);
    expect(busyButton.disabled).toBe(true);
    expect(host!.textContent).not.toContain("Import complete: Classification tags added: 7");
    expect(requestCounts()).toEqual(beforeSwitch);

    await act(async () => hiddenRequest.resolve({ ticker: SOURCE_TICKER, hidden: true }));
    await flush();
    expect(apiMocks.setTickerHidden).toHaveBeenCalledTimes(1);
    expect(query.value).toBe("src");
    expect(list.value).toBe(SOURCE_LIST);
    expect(category.value).toBe(SOURCE_CATEGORY);
  });

  it("preserves unknown facet IDs and filter results across locale switch", async () => {
    await mountUniverse();
    await waitForText(SOURCE_TICKER);
    const list = selectWithOption(SOURCE_LIST);
    const category = selectWithOption(SOURCE_CATEGORY);
    await change(list, SOURCE_LIST);
    await change(category, SOURCE_CATEGORY);
    const unknownChip = host!.querySelector<HTMLElement>(`.tagchip[title*="${UNKNOWN_FACET}"]`)!;
    const rowsBefore = Array.from(host!.querySelectorAll("tbody tr"));
    expect(rowsBefore.map((row) => row.textContent)).toEqual([
      expect.stringContaining(SOURCE_TICKER),
      expect.stringContaining("ARCH.SRC"),
    ]);
    expect(unknownChip.title).toContain(UNKNOWN_FACET);
    expect(unknownChip.title).toContain(UNKNOWN_SOURCE);

    await switchLocale("en");
    expect(host!.querySelector(`.tagchip[title*="${UNKNOWN_FACET}"]`)).toBe(unknownChip);
    expect(unknownChip.textContent).toBe(UNKNOWN_VALUE);
    expect(unknownChip.title).toBe(
      `${UNKNOWN_FACET} · ${UNKNOWN_VALUE} (${UNKNOWN_SOURCE}) · read-only`,
    );
    expect(list.value).toBe(SOURCE_LIST);
    expect(category.value).toBe(SOURCE_CATEGORY);
    expect(Array.from(host!.querySelectorAll("tbody tr"))).toEqual(rowsBefore);
    expect(host!.querySelector(".surface-title")?.textContent).toBe("Universe");
  });
});
