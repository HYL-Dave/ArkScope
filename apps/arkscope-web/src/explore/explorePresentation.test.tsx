/** @vitest-environment jsdom */
import React, { act, type ComponentType, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { createInstance, type TFunction } from "i18next";
import { I18nextProvider } from "react-i18next";
import { afterEach, describe, expect, it, vi } from "vitest";

import { initializeI18n } from "../i18n/resources";
import type { NavigationTarget } from "../shell/navigation";

const OPERATIONS = [
  "home_load_workspace",
  "home_open_card",
  "home_save_card",
  "watchlist_load_lists",
  "watchlist_load_universe",
  "watchlist_search_symbols",
  "watchlist_load_consensus",
  "watchlist_create_list",
  "watchlist_rename_list",
  "watchlist_set_default_list",
  "watchlist_add_member",
  "watchlist_remove_member",
  "watchlist_set_archived",
  "watchlist_set_priority",
  "universe_load",
  "universe_import",
  "universe_hide_ticker",
  "news_load_market",
  "news_load_seeking_alpha",
  "news_load_more",
  "ticker_load_state",
  "ticker_load_price",
  "ticker_load_iv",
  "ticker_load_iv_history",
  "ticker_load_fundamentals",
  "ticker_load_market_status",
  "ticker_load_coverage",
  "ticker_load_notes",
  "ticker_load_tag_catalog",
  "ticker_add_note",
  "ticker_delete_note",
  "ticker_add_tag",
  "ticker_remove_tag",
  "card_load_recent",
  "card_open",
  "card_load_investor_profile",
  "card_generate",
  "card_save",
  "card_translate",
] as const;

type Operation = (typeof OPERATIONS)[number];
type Locale = "zh-Hant" | "en";
type SettingsTarget = Extract<NavigationTarget, { kind: "settings_section" }>;

interface ExploreErrorState {
  operation: Operation;
  category: "http" | "network" | "unknown";
  status: number | null;
  code: string | null;
  routeTemplate: string | null;
  developerDetail: string | null;
  detailOmitted: boolean;
}

interface DiagnosticRow {
  label: string;
  value: string;
}

interface ExploreErrorPresentation {
  title: string;
  diagnostics: {
    title: string;
    status: DiagnosticRow | null;
    code: DiagnosticRow | null;
    path: DiagnosticRow | null;
    detail: DiagnosticRow | null;
    detailOmitted: string | null;
  };
  recovery: {
    prompt: string;
    label: string;
    target: SettingsTarget;
  } | null;
}

interface UniverseImportOutcome {
  kind: "universe_import_succeeded";
  tagsAdded: number;
  listsRemoved: number;
  groupsAvailable: boolean;
}

interface UniverseImportPresentation {
  title: string;
  summaryItems: string[];
  warning: string | null;
}

interface PresentationModule {
  EXPLORE_OPERATIONS: readonly Operation[];
  captureExploreError: (operation: Operation, value: unknown) => ExploreErrorState;
  presentExploreError: (
    state: ExploreErrorState,
    t: TFunction<"explore">,
  ) => ExploreErrorPresentation;
  safeDiagnosticDetail: (value: unknown) => string | null;
  recoveryTargetForExploreError: (state: ExploreErrorState) => SettingsTarget | null;
  presentUniverseImportOutcome: (
    outcome: UniverseImportOutcome,
    t: TFunction<"explore">,
  ) => UniverseImportPresentation;
}

interface NoticeModule {
  ExploreErrorNotice: ComponentType<{
    state: ExploreErrorState;
    developerMode: boolean;
    retryLabel: ReactNode;
    onRetry: () => void;
    onNavigate?: (target: NavigationTarget) => void;
  }>;
}

const presentationModulePath = "./explorePresentation";
const noticeModulePath = "./ExploreErrorNotice";

function loadPresentation(): Promise<PresentationModule> {
  return import(/* @vite-ignore */ presentationModulePath) as Promise<PresentationModule>;
}

function loadNotice(): Promise<NoticeModule> {
  return import(/* @vite-ignore */ noticeModulePath) as Promise<NoticeModule>;
}

function exploreT(locale: Locale): TFunction<"explore"> {
  const instance = createInstance();
  initializeI18n(instance, locale);
  return instance.getFixedT(locale, "explore");
}

function emptyState(operation: Operation): ExploreErrorState {
  return {
    operation,
    category: "unknown",
    status: null,
    code: null,
    routeTemplate: null,
    developerDetail: null,
    detailOmitted: false,
  };
}

const EXPECTED_TITLES: Record<Operation, Record<Locale, string>> = {
  home_load_workspace: {
    "zh-Hant": "無法載入工作台資料。",
    en: "Could not load workspace data.",
  },
  home_open_card: {
    "zh-Hant": "無法開啟 AI 卡片。",
    en: "Could not open the AI Card.",
  },
  home_save_card: {
    "zh-Hant": "無法儲存 AI 卡片。",
    en: "Could not save the AI Card.",
  },
  watchlist_load_lists: {
    "zh-Hant": "無法載入自選股清單。",
    en: "Could not load Watchlist lists.",
  },
  watchlist_load_universe: {
    "zh-Hant": "無法載入全部標的。",
    en: "Could not load the Universe.",
  },
  watchlist_search_symbols: {
    "zh-Hant": "無法搜尋標的。",
    en: "Could not search for tickers.",
  },
  watchlist_load_consensus: {
    "zh-Hant": "無法載入分析師共識。",
    en: "Could not load analyst consensus.",
  },
  watchlist_create_list: {
    "zh-Hant": "無法建立清單。",
    en: "Could not create the list.",
  },
  watchlist_rename_list: {
    "zh-Hant": "無法重新命名清單。",
    en: "Could not rename the list.",
  },
  watchlist_set_default_list: {
    "zh-Hant": "無法更新預設清單。",
    en: "Could not update the default list.",
  },
  watchlist_add_member: {
    "zh-Hant": "無法將標的加入清單。",
    en: "Could not add the ticker to the list.",
  },
  watchlist_remove_member: {
    "zh-Hant": "無法從清單移除標的。",
    en: "Could not remove the ticker from the list.",
  },
  watchlist_set_archived: {
    "zh-Hant": "無法更新標的封存狀態。",
    en: "Could not update the ticker's archive state.",
  },
  watchlist_set_priority: {
    "zh-Hant": "無法更新標的優先順序。",
    en: "Could not update the ticker's priority.",
  },
  universe_load: {
    "zh-Hant": "無法載入全部標的。",
    en: "Could not load the Universe.",
  },
  universe_import: {
    "zh-Hant": "無法匯入分類。",
    en: "Could not import classifications.",
  },
  universe_hide_ticker: {
    "zh-Hant": "無法更新標的顯示狀態。",
    en: "Could not update the ticker's visibility.",
  },
  news_load_market: {
    "zh-Hant": "無法載入市場新聞。",
    en: "Could not load Market News.",
  },
  news_load_seeking_alpha: {
    "zh-Hant": "無法載入 Seeking Alpha 內容。",
    en: "Could not load Seeking Alpha content.",
  },
  news_load_more: {
    "zh-Hant": "無法載入更多新聞。",
    en: "Could not load more news.",
  },
  ticker_load_state: {
    "zh-Hant": "無法載入標的詳情。",
    en: "Could not load ticker details.",
  },
  ticker_load_price: {
    "zh-Hant": "無法載入價格概覽。",
    en: "Could not load the price overview.",
  },
  ticker_load_iv: {
    "zh-Hant": "無法載入隱含波動率。",
    en: "Could not load implied volatility.",
  },
  ticker_load_iv_history: {
    "zh-Hant": "無法載入 IV 歷史。",
    en: "Could not load IV history.",
  },
  ticker_load_fundamentals: {
    "zh-Hant": "無法載入基本面。",
    en: "Could not load fundamentals.",
  },
  ticker_load_market_status: {
    "zh-Hant": "無法載入市場資料狀態。",
    en: "Could not load market-data status.",
  },
  ticker_load_coverage: {
    "zh-Hant": "無法載入市場資料覆蓋。",
    en: "Could not load market-data coverage.",
  },
  ticker_load_notes: {
    "zh-Hant": "無法載入筆記。",
    en: "Could not load notes.",
  },
  ticker_load_tag_catalog: {
    "zh-Hant": "無法載入標籤目錄。",
    en: "Could not load the tag catalog.",
  },
  ticker_add_note: {
    "zh-Hant": "無法新增筆記。",
    en: "Could not add the note.",
  },
  ticker_delete_note: {
    "zh-Hant": "無法刪除筆記。",
    en: "Could not delete the note.",
  },
  ticker_add_tag: {
    "zh-Hant": "無法新增標籤。",
    en: "Could not add the tag.",
  },
  ticker_remove_tag: {
    "zh-Hant": "無法移除標籤。",
    en: "Could not remove the tag.",
  },
  card_load_recent: {
    "zh-Hant": "無法載入最近卡片。",
    en: "Could not load recent Cards.",
  },
  card_open: {
    "zh-Hant": "無法開啟 AI 卡片。",
    en: "Could not open the AI Card.",
  },
  card_load_investor_profile: {
    "zh-Hant": "無法載入投資人設定。",
    en: "Could not load the Investor Profile.",
  },
  card_generate: {
    "zh-Hant": "無法產生 AI 卡片。",
    en: "Could not generate the AI Card.",
  },
  card_save: {
    "zh-Hant": "無法將卡片存成報告。",
    en: "Could not save the Card as a report.",
  },
  card_translate: {
    "zh-Hant": "無法翻譯卡片。",
    en: "Could not translate the Card.",
  },
};

const ROUTE_CASES: ReadonlyArray<{
  operation: Operation;
  path: string;
  expected: string;
}> = [
  { operation: "home_load_workspace", path: "/profile/universe?include_archived=true", expected: "/profile/universe" },
  { operation: "home_load_workspace", path: "/profile/lists?include_archived=false", expected: "/profile/lists" },
  { operation: "home_load_workspace", path: "/analysis/cards?limit=8", expected: "/analysis/cards" },
  { operation: "home_open_card", path: "/analysis/cards/72", expected: "/analysis/cards/{run_id}" },
  { operation: "home_save_card", path: "/analysis/cards/72/save", expected: "/analysis/cards/{run_id}/save" },
  { operation: "watchlist_load_lists", path: "/profile/lists?include_archived=false", expected: "/profile/lists" },
  { operation: "watchlist_load_lists", path: "/profile/settings/default-watchlist", expected: "/profile/settings/default-watchlist" },
  { operation: "watchlist_load_universe", path: "/profile/universe?include_archived=true", expected: "/profile/universe" },
  { operation: "watchlist_search_symbols", path: "/symbols/search?q=private-query&limit=8", expected: "/symbols/search" },
  { operation: "watchlist_load_consensus", path: "/analysis/consensus/AAPL", expected: "/analysis/consensus/{ticker}" },
  { operation: "watchlist_create_list", path: "/profile/lists", expected: "/profile/lists" },
  { operation: "watchlist_rename_list", path: "/profile/lists/41", expected: "/profile/lists/{list_id}" },
  { operation: "watchlist_set_default_list", path: "/profile/settings/default-watchlist", expected: "/profile/settings/default-watchlist" },
  { operation: "watchlist_add_member", path: "/profile/lists/41/members", expected: "/profile/lists/{list_id}/members" },
  { operation: "watchlist_remove_member", path: "/profile/lists/41/members/BRK.B", expected: "/profile/lists/{list_id}/members/{ticker}" },
  { operation: "watchlist_set_archived", path: "/profile/tickers/AAPL/archive", expected: "/profile/tickers/{ticker}/archive" },
  { operation: "watchlist_set_priority", path: "/profile/tickers/AAPL/priority", expected: "/profile/tickers/{ticker}/priority" },
  { operation: "universe_load", path: "/profile/universe?include_archived=true", expected: "/profile/universe" },
  { operation: "universe_load", path: "/profile/lists?include_archived=false", expected: "/profile/lists" },
  { operation: "universe_import", path: "/profile/import-universe", expected: "/profile/import-universe" },
  { operation: "universe_hide_ticker", path: "/profile/tickers/AAPL/hidden", expected: "/profile/tickers/{ticker}/hidden" },
  { operation: "news_load_market", path: "/news/feed?ticker=AAPL#private", expected: "/news/feed" },
  { operation: "news_load_seeking_alpha", path: "/sa/feed?search=private-query", expected: "/sa/feed" },
  { operation: "news_load_seeking_alpha", path: "/sa/extension-health", expected: "/sa/extension-health" },
  { operation: "news_load_more", path: "/news/feed?cursor=private-cursor", expected: "/news/feed" },
  { operation: "news_load_more", path: "/sa/feed?offset=80", expected: "/sa/feed" },
  { operation: "ticker_load_state", path: "/profile/tickers/AAPL/state", expected: "/profile/tickers/{ticker}/state" },
  { operation: "ticker_load_price", path: "/prices/AAPL/change?days=30", expected: "/prices/{ticker}/change" },
  { operation: "ticker_load_iv", path: "/options/AAPL", expected: "/options/{ticker}" },
  { operation: "ticker_load_iv_history", path: "/options/AAPL/history", expected: "/options/{ticker}/history" },
  { operation: "ticker_load_fundamentals", path: "/fundamentals/AAPL?stored=true", expected: "/fundamentals/{ticker}" },
  { operation: "ticker_load_market_status", path: "/market-data/status", expected: "/market-data/status" },
  { operation: "ticker_load_coverage", path: "/market-data/coverage/AAPL", expected: "/market-data/coverage/{ticker}" },
  { operation: "ticker_load_notes", path: "/profile/tickers/AAPL/notes", expected: "/profile/tickers/{ticker}/notes" },
  { operation: "ticker_load_tag_catalog", path: "/profile/tags/catalog", expected: "/profile/tags/catalog" },
  { operation: "ticker_add_note", path: "/profile/tickers/AAPL/notes", expected: "/profile/tickers/{ticker}/notes" },
  { operation: "ticker_delete_note", path: "/profile/tickers/AAPL/notes/91", expected: "/profile/tickers/{ticker}/notes/{note_id}" },
  { operation: "ticker_add_tag", path: "/profile/tickers/AAPL/tags", expected: "/profile/tickers/{ticker}/tags" },
  { operation: "ticker_remove_tag", path: "/profile/tickers/AAPL/tags?value=private-tag", expected: "/profile/tickers/{ticker}/tags" },
  { operation: "card_load_recent", path: "/analysis/cards?ticker=AAPL", expected: "/analysis/cards" },
  { operation: "card_open", path: "/analysis/cards/72", expected: "/analysis/cards/{run_id}" },
  { operation: "card_load_investor_profile", path: "/profile/investor", expected: "/profile/investor" },
  { operation: "card_generate", path: "/analysis/card/AAPL", expected: "/analysis/card/{ticker}" },
  { operation: "card_save", path: "/analysis/cards/72/save", expected: "/analysis/cards/{run_id}/save" },
  { operation: "card_translate", path: "/analysis/cards/72/translate", expected: "/analysis/cards/{run_id}/translate" },
];

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

async function mountNotice(
  locale: Locale,
  props: {
    state: ExploreErrorState;
    developerMode: boolean;
    retryLabel: ReactNode;
    onRetry: () => void;
    onNavigate?: (target: NavigationTarget) => void;
  },
) {
  const { ExploreErrorNotice } = await loadNotice();
  const instance = createInstance();
  initializeI18n(instance, locale);
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(
      <I18nextProvider i18n={instance}>
        <ExploreErrorNotice {...props} />
      </I18nextProvider>,
    );
  });
}

async function click(button: HTMLButtonElement) {
  await act(async () => {
    button.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  });
}

afterEach(() => {
  if (root) act(() => root!.unmount());
  host?.remove();
  root = null;
  host = null;
});

describe("Explore presentation boundary", () => {
  it("maps every reviewed Explore operation in both locales", async () => {
    const presentation = await loadPresentation();

    expect(presentation.EXPLORE_OPERATIONS).toEqual(OPERATIONS);
    expect(new Set(presentation.EXPLORE_OPERATIONS)).toHaveProperty("size", 39);
    for (const locale of ["zh-Hant", "en"] as const) {
      const t = exploreT(locale);
      for (const operation of OPERATIONS) {
        expect(presentation.presentExploreError(emptyState(operation), t).title)
          .toBe(EXPECTED_TITLES[operation][locale]);
      }
    }
  });

  it("distinguishes read and mutation outcomes without a generic request owner", async () => {
    const { presentExploreError } = await loadPresentation();
    const relatedReadAndMutationPairs = [
      ["home_load_workspace", "home_save_card"],
      ["watchlist_load_lists", "watchlist_create_list"],
      ["universe_load", "universe_import"],
      ["ticker_load_notes", "ticker_add_note"],
      ["card_load_recent", "card_generate"],
    ] as const;

    for (const locale of ["zh-Hant", "en"] as const) {
      const t = exploreT(locale);
      for (const [read, mutation] of relatedReadAndMutationPairs) {
        const readTitle = presentExploreError(emptyState(read), t).title;
        const mutationTitle = presentExploreError(emptyState(mutation), t).title;
        expect(readTitle).toBe(EXPECTED_TITLES[read][locale]);
        expect(mutationTitle).toBe(EXPECTED_TITLES[mutation][locale]);
        expect(readTitle).not.toBe(mutationTitle);
      }
      const titles = OPERATIONS.map((operation) =>
        presentExploreError(emptyState(operation), t).title);
      expect(titles).not.toContain(locale === "en" ? "Request failed." : "要求失敗。");
    }
  });

  it("never reads legacy ApiError message while capturing structured fields", async () => {
    const { captureExploreError } = await loadPresentation();
    const value = new Error("legacy display copy") as Error & Record<string, unknown>;
    let messageReads = 0;
    Object.defineProperties(value, {
      message: {
        configurable: true,
        get() {
          messageReads += 1;
          throw new Error("legacy message was read");
        },
      },
      status: { value: 503 },
      path: { value: "/profile/universe?include_archived=true#private" },
      code: { value: "active_universe_unavailable" },
      diagnostic: { value: "upstream temporarily unavailable" },
    });

    expect(captureExploreError("universe_load", value)).toEqual({
      operation: "universe_load",
      category: "http",
      status: 503,
      code: "active_universe_unavailable",
      routeTemplate: "/profile/universe",
      developerDetail: "upstream temporarily unavailable",
      detailOmitted: false,
    });
    expect(messageReads).toBe(0);
  });

  it("keeps ordinary network failures generic and structured", async () => {
    const { captureExploreError } = await loadPresentation();
    const network = captureExploreError(
      "news_load_market",
      new Error("https://private.example.test?token=secret"),
    );
    expect(network).toEqual({
      operation: "news_load_market",
      category: "network",
      status: null,
      code: null,
      routeTemplate: null,
      developerDetail: null,
      detailOmitted: false,
    });
    expect(Object.prototype.hasOwnProperty.call(network, "message")).toBe(false);

    expect(captureExploreError("news_load_market", "raw failure")).toEqual({
      ...network,
      category: "unknown",
    });

    const hostile = new Proxy({}, {
      get() {
        throw new Error("hostile getter");
      },
      getPrototypeOf() {
        throw new Error("hostile prototype");
      },
    });
    expect(() => captureExploreError("news_load_market", hostile)).not.toThrow();
    expect(captureExploreError("news_load_market", hostile)).toEqual({
      ...network,
      category: "unknown",
    });
  });

  it("accepts only bounded integer status and stable error codes", async () => {
    const { captureExploreError } = await loadPresentation();
    const validStatuses = [100, 204, 418, 599];
    const invalidStatuses: unknown[] = [99, 600, 200.5, Number.NaN, Number.POSITIVE_INFINITY, "503"];
    const validCodes = [
      "active_universe_unavailable",
      "provider_config_missing",
      "a",
      "a1_b2",
      "a".repeat(64),
    ];
    const invalidCodes: unknown[] = [
      "",
      "UPPER_CASE",
      "leading-hyphen",
      "trailing_",
      "double__underscore",
      "1starts_with_digit",
      "contains space",
      "a".repeat(65),
      503,
    ];

    for (const status of validStatuses) {
      expect(captureExploreError("universe_load", { status }).status).toBe(status);
    }
    for (const status of invalidStatuses) {
      expect(captureExploreError("universe_load", { status }).status).toBeNull();
    }
    for (const code of validCodes) {
      expect(captureExploreError("universe_load", { code }).code).toBe(code);
    }
    for (const code of invalidCodes) {
      expect(captureExploreError("universe_load", { code }).code).toBeNull();
    }
  });

  it("maps only reviewed queryless API route templates", async () => {
    const { captureExploreError } = await loadPresentation();

    for (const { operation, path, expected } of ROUTE_CASES) {
      const routeTemplate = captureExploreError(operation, { path }).routeTemplate;
      expect(routeTemplate, `${operation}: ${path}`).toBe(expected);
      expect(routeTemplate).not.toMatch(/[?#]/);
      expect(routeTemplate).not.toContain("AAPL");
      expect(routeTemplate).not.toContain("BRK.B");
      expect(routeTemplate).not.toContain("72");
      expect(routeTemplate).not.toContain("private");
    }

    expect(captureExploreError("home_load_workspace", { path: "/sa/feed" }).routeTemplate)
      .toBeNull();
    expect(captureExploreError("ticker_load_notes", { path: "/profile/tags/catalog" }).routeTemplate)
      .toBeNull();
  });

  it("omits invalid dynamic absolute and over-limit API paths", async () => {
    const { captureExploreError } = await loadPresentation();
    const invalidCases: Array<[Operation, unknown]> = [
      ["ticker_load_notes", "https://api.example.test/profile/tickers/AAPL/notes"],
      ["ticker_load_notes", "//api.example.test/profile/tickers/AAPL/notes"],
      ["ticker_load_notes", "api.example.test/profile/tickers/AAPL/notes"],
      ["ticker_load_notes", "/profile/tickers/../notes"],
      ["ticker_load_notes", "/profile/tickers//notes"],
      ["ticker_delete_note", "/profile/tickers/AAPL/notes/not-a-number"],
      ["ticker_load_state", `/profile/tickers/${"A".repeat(161)}/state`],
      ["ticker_load_state", "/profile/tickers/AAPL/state\n/extra"],
      ["ticker_load_state", 42],
    ];

    for (const [operation, path] of invalidCases) {
      expect(captureExploreError(operation, { path }).routeTemplate).toBeNull();
    }

    const safe = captureExploreError("ticker_load_notes", {
      path: "/profile/tickers/PRIVATE-TICKER/notes?query=PRIVATE-QUERY#PRIVATE-FRAGMENT",
    }).routeTemplate;
    expect(safe).toBe("/profile/tickers/{ticker}/notes");
    expect(safe).not.toContain("PRIVATE");
  });

  it("accepts only bounded safe single-line diagnostic detail", async () => {
    const { safeDiagnosticDetail } = await loadPresentation();
    const safeDetails = [
      "upstream temporarily unavailable",
      "request timed out after 8s",
      "provider returned retryable status (temporary).",
      "queue worker-2 unavailable; retry later",
      "a".repeat(160),
    ];

    for (const detail of safeDetails) {
      expect(safeDiagnosticDetail(detail)).toBe(detail);
    }
    expect(safeDiagnosticDetail(null)).toBeNull();
    expect(safeDiagnosticDetail(undefined)).toBeNull();
    expect(safeDiagnosticDetail(503)).toBeNull();
    expect(safeDiagnosticDetail(" leading whitespace")).toBeNull();
    expect(safeDiagnosticDetail("trailing whitespace ")).toBeNull();
  });

  it("rejects secrets tracebacks SQL paths URLs IP HTML controls and long detail", async () => {
    const { safeDiagnosticDetail } = await loadPresentation();
    const unsafeDetails = [
      "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.secret.signature",
      "api_key=super-secret-value",
      "token: ghp_0123456789abcdefghijklmnop",
      "sk-proj-0123456789abcdef",
      "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.signature",
      "Traceback (most recent call last): handler failed",
      "stack trace at fetchMarketData",
      "sqlite3.OperationalError: no such table: news_items",
      "SELECT secret FROM credentials",
      "syntax error at or near FROM",
      "relation accounts does not exist",
      "column user_id does not exist",
      "duplicate key value violates unique constraint accounts_pkey",
      "localhost:5432 refused the connection",
      "localhost refused the connection",
      "at async fetchMarketData",
      "at fetchMarketData [as loadMarketData]",
      "frame #12 in fetchMarketData",
      "File worker_py line 42 in fetch_data",
      "Trace frame: fetchMarketData",
      "/home/alice/arkscope/app.py:42",
      "C:\\Users\\alice\\ArkScope\\config.json",
      "../private/config.json",
      "https://api.example.test/private?token=secret",
      "api.internal.example unavailable",
      "10.0.0.8 refused the connection",
      "[2001:db8::1] refused the connection",
      "<script>alert('secret')</script>",
      "unsafe &lt;script&gt;",
      "unsafe &#60;script&#62;",
      "unsafe &#x3c;script&#x3e;",
      "unsafe\u0000detail",
      "first line\nsecond line",
      "a".repeat(161),
    ];

    for (const detail of unsafeDetails) {
      expect.soft(safeDiagnosticDetail(detail), detail).toBeNull();
    }
  });

  it("maps only reviewed recovery codes to existing Settings targets", async () => {
    const { captureExploreError, recoveryTargetForExploreError } = await loadPresentation();
    const cases: Array<[string, SettingsTarget]> = [
      ["active_universe_unavailable", { kind: "settings_section", section: "data_sources" }],
      ["sa_extension_health_unavailable", { kind: "settings_section", section: "data_sources" }],
      ["provider_config_missing", { kind: "settings_section", section: "providers" }],
    ];

    for (const [code, target] of cases) {
      const state = captureExploreError("universe_load", { code });
      expect(recoveryTargetForExploreError(state)).toEqual(target);
    }

    for (const code of [null, "news_storage_unavailable", "unknown_code"]) {
      const state = captureExploreError("universe_load", {
        status: 503,
        code,
        diagnostic: "active_universe_unavailable",
      });
      expect(recoveryTargetForExploreError(state)).toBeNull();
    }

    for (const code of ["constructor", "toString", "__proto__"]) {
      expect(recoveryTargetForExploreError({
        ...emptyState("universe_load"),
        code,
      })).toBeNull();
    }
  });

  it("renders normal mode without diagnostic detail", async () => {
    const { captureExploreError } = await loadPresentation();
    const onRetry = vi.fn();
    const onNavigate = vi.fn();
    const state = captureExploreError("universe_load", {
      status: 503,
      path: "/profile/universe?private=query",
      code: "active_universe_unavailable",
      diagnostic: "api_key=must-not-render",
    });

    await mountNotice("en", {
      state,
      developerMode: false,
      retryLabel: <span>Retry Universe load</span>,
      onRetry,
      onNavigate,
    });

    expect(host!.querySelector('[role="alert"]')).not.toBeNull();
    expect(host!.textContent).toContain("Could not load the Universe.");
    expect(host!.textContent).toContain("Retry Universe load");
    expect(host!.textContent).toContain("Go to Data Sources and Schedules");
    expect(host!.textContent).not.toContain("Developer diagnostics");
    expect(host!.textContent).not.toContain("503");
    expect(host!.textContent).not.toContain("active_universe_unavailable");
    expect(host!.textContent).not.toContain("/profile/universe");
    expect(host!.textContent).not.toContain("must-not-render");
    expect(host!.textContent).not.toContain("Unsafe diagnostic detail was omitted.");

    const buttons = Array.from(host!.querySelectorAll("button"));
    await click(buttons.find((button) => button.textContent?.includes("Retry Universe load"))!);
    await click(buttons.find((button) => button.textContent?.includes("Go to Data Sources"))!);
    expect(onRetry).toHaveBeenCalledTimes(1);
    expect(onNavigate).toHaveBeenCalledWith({
      kind: "settings_section",
      section: "data_sources",
    });
  });

  it("renders Developer Mode with safe metadata and an omitted-detail state", async () => {
    const { captureExploreError } = await loadPresentation();
    const state = captureExploreError("universe_load", {
      status: 503,
      path: "/profile/universe?private=query#fragment",
      code: "active_universe_unavailable",
      diagnostic: "Bearer must-not-render",
    });

    await mountNotice("en", {
      state,
      developerMode: true,
      retryLabel: "Retry load",
      onRetry: vi.fn(),
    });

    expect(host!.textContent).toContain("Developer diagnostics");
    expect(host!.textContent).toContain("Status");
    expect(host!.textContent).toContain("503");
    expect(host!.textContent).toContain("Code");
    expect(host!.textContent).toContain("active_universe_unavailable");
    expect(host!.textContent).toContain("Path");
    expect(host!.textContent).toContain("/profile/universe");
    expect(host!.textContent).toContain("Unsafe diagnostic detail was omitted.");
    expect(host!.textContent).not.toContain("must-not-render");
  });

  it("renders structured Universe outcomes in both locales without captured copy", async () => {
    const { presentUniverseImportOutcome } = await loadPresentation();
    const expected = {
      "zh-Hant": {
        title: "匯入完成：新增 4 個分類標籤 · 移除 2 個舊清單。",
        summaryItems: ["新增 4 個分類標籤", "移除 2 個舊清單"],
        warning: null,
      },
      en: {
        title: "Import complete: Added 4 classification tags · Removed 2 legacy lists.",
        summaryItems: ["Added 4 classification tags", "Removed 2 legacy lists"],
        warning: null,
      },
    } as const;

    for (const locale of ["zh-Hant", "en"] as const) {
      const result = presentUniverseImportOutcome({
        kind: "universe_import_succeeded",
        tagsAdded: 4,
        listsRemoved: 2,
        groupsAvailable: true,
      }, exploreT(locale));
      expect(result).toEqual(expected[locale]);
    }

    const outcomeWithCapturedCopy = {
      kind: "universe_import_succeeded",
      tagsAdded: 1,
      listsRemoved: 0,
      groupsAvailable: false,
      sourceTagName: "PRIVATE THEME FROM SERVER",
      capturedSentence: "PRIVATE IMPORT COMPLETE COPY",
    } as UniverseImportOutcome;
    const result = presentUniverseImportOutcome(outcomeWithCapturedCopy, exploreT("en"));
    expect(result).toEqual({
      title: "Import complete: Added 1 classification tags.",
      summaryItems: ["Added 1 classification tags"],
      warning: "⚠ The theme source is temporarily unavailable, so theme tags were skipped.",
    });
    expect(JSON.stringify(result)).not.toContain("PRIVATE");
  });
});
