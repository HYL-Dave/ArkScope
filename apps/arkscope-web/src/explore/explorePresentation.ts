import type { TFunction } from "i18next";

import type { NavigationTarget } from "../shell/navigation";

export type ExploreT = TFunction<"explore">;

export const EXPLORE_OPERATIONS = [
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

export type ExploreOperation = (typeof EXPLORE_OPERATIONS)[number];

export type ExploreErrorState = {
  readonly operation: ExploreOperation;
  readonly category: "http" | "network" | "unknown";
  readonly status: number | null;
  readonly code: string | null;
  readonly routeTemplate: string | null;
  readonly developerDetail: string | null;
  readonly detailOmitted: boolean;
};

export type ExploreSettingsTarget = Extract<
  NavigationTarget,
  { kind: "settings_section" }
>;

export type ExploreDiagnosticRow = {
  label: string;
  value: string;
};

export type ExploreErrorPresentation = {
  title: string;
  diagnostics: {
    title: string;
    status: ExploreDiagnosticRow | null;
    code: ExploreDiagnosticRow | null;
    path: ExploreDiagnosticRow | null;
    detail: ExploreDiagnosticRow | null;
    detailOmitted: string | null;
  };
  recovery: {
    prompt: string;
    label: string;
    target: ExploreSettingsTarget;
  } | null;
};

export type UniverseImportOutcome = {
  kind: "universe_import_succeeded";
  tagsAdded: number;
  listsRemoved: number;
  groupsAvailable: boolean;
};

export type UniverseImportPresentation = {
  title: string;
  summaryItems: string[];
  warning: string | null;
};

const OPERATION_PRESENTERS = {
  home_load_workspace: (t) => t(($) => $.errors.operations.homeLoadWorkspace),
  home_open_card: (t) => t(($) => $.errors.operations.homeOpenCard),
  home_save_card: (t) => t(($) => $.errors.operations.homeSaveCard),
  watchlist_load_lists: (t) => t(($) => $.errors.operations.watchlistLoadLists),
  watchlist_load_universe: (t) => t(($) => $.errors.operations.watchlistLoadUniverse),
  watchlist_search_symbols: (t) => t(($) => $.errors.operations.watchlistSearchSymbols),
  watchlist_load_consensus: (t) => t(($) => $.errors.operations.watchlistLoadConsensus),
  watchlist_create_list: (t) => t(($) => $.errors.operations.watchlistCreateList),
  watchlist_rename_list: (t) => t(($) => $.errors.operations.watchlistRenameList),
  watchlist_set_default_list: (t) => t(($) => $.errors.operations.watchlistSetDefaultList),
  watchlist_add_member: (t) => t(($) => $.errors.operations.watchlistAddMember),
  watchlist_remove_member: (t) => t(($) => $.errors.operations.watchlistRemoveMember),
  watchlist_set_archived: (t) => t(($) => $.errors.operations.watchlistSetArchived),
  watchlist_set_priority: (t) => t(($) => $.errors.operations.watchlistSetPriority),
  universe_load: (t) => t(($) => $.errors.operations.universeLoad),
  universe_import: (t) => t(($) => $.errors.operations.universeImport),
  universe_hide_ticker: (t) => t(($) => $.errors.operations.universeHideTicker),
  news_load_market: (t) => t(($) => $.errors.operations.newsLoadMarket),
  news_load_seeking_alpha: (t) => t(($) => $.errors.operations.newsLoadSeekingAlpha),
  news_load_more: (t) => t(($) => $.errors.operations.newsLoadMore),
  ticker_load_state: (t) => t(($) => $.errors.operations.tickerLoadState),
  ticker_load_price: (t) => t(($) => $.errors.operations.tickerLoadPrice),
  ticker_load_iv: (t) => t(($) => $.errors.operations.tickerLoadIv),
  ticker_load_iv_history: (t) => t(($) => $.errors.operations.tickerLoadIvHistory),
  ticker_load_fundamentals: (t) => t(($) => $.errors.operations.tickerLoadFundamentals),
  ticker_load_market_status: (t) => t(($) => $.errors.operations.tickerLoadMarketStatus),
  ticker_load_coverage: (t) => t(($) => $.errors.operations.tickerLoadCoverage),
  ticker_load_notes: (t) => t(($) => $.errors.operations.tickerLoadNotes),
  ticker_load_tag_catalog: (t) => t(($) => $.errors.operations.tickerLoadTagCatalog),
  ticker_add_note: (t) => t(($) => $.errors.operations.tickerAddNote),
  ticker_delete_note: (t) => t(($) => $.errors.operations.tickerDeleteNote),
  ticker_add_tag: (t) => t(($) => $.errors.operations.tickerAddTag),
  ticker_remove_tag: (t) => t(($) => $.errors.operations.tickerRemoveTag),
  card_load_recent: (t) => t(($) => $.errors.operations.cardLoadRecent),
  card_open: (t) => t(($) => $.errors.operations.cardOpen),
  card_load_investor_profile: (t) => t(($) => $.errors.operations.cardLoadInvestorProfile),
  card_generate: (t) => t(($) => $.errors.operations.cardGenerate),
  card_save: (t) => t(($) => $.errors.operations.cardSave),
  card_translate: (t) => t(($) => $.errors.operations.cardTranslate),
} satisfies Record<ExploreOperation, (t: ExploreT) => string>;

type ReviewedRoute = {
  template: string;
  pattern: RegExp;
};

const TICKER_SEGMENT = "[A-Za-z0-9][A-Za-z0-9._~-]{0,47}";
const routes = {
  profileUniverse: {
    template: "/profile/universe",
    pattern: /^\/profile\/universe$/,
  },
  profileLists: {
    template: "/profile/lists",
    pattern: /^\/profile\/lists$/,
  },
  profileList: {
    template: "/profile/lists/{list_id}",
    pattern: /^\/profile\/lists\/[0-9]+$/,
  },
  profileListMembers: {
    template: "/profile/lists/{list_id}/members",
    pattern: /^\/profile\/lists\/[0-9]+\/members$/,
  },
  profileListMember: {
    template: "/profile/lists/{list_id}/members/{ticker}",
    pattern: new RegExp(`^/profile/lists/[0-9]+/members/${TICKER_SEGMENT}$`),
  },
  defaultWatchlist: {
    template: "/profile/settings/default-watchlist",
    pattern: /^\/profile\/settings\/default-watchlist$/,
  },
  profileImportUniverse: {
    template: "/profile/import-universe",
    pattern: /^\/profile\/import-universe$/,
  },
  profileTickerState: {
    template: "/profile/tickers/{ticker}/state",
    pattern: new RegExp(`^/profile/tickers/${TICKER_SEGMENT}/state$`),
  },
  profileTickerArchive: {
    template: "/profile/tickers/{ticker}/archive",
    pattern: new RegExp(`^/profile/tickers/${TICKER_SEGMENT}/archive$`),
  },
  profileTickerPriority: {
    template: "/profile/tickers/{ticker}/priority",
    pattern: new RegExp(`^/profile/tickers/${TICKER_SEGMENT}/priority$`),
  },
  profileTickerHidden: {
    template: "/profile/tickers/{ticker}/hidden",
    pattern: new RegExp(`^/profile/tickers/${TICKER_SEGMENT}/hidden$`),
  },
  profileTickerNotes: {
    template: "/profile/tickers/{ticker}/notes",
    pattern: new RegExp(`^/profile/tickers/${TICKER_SEGMENT}/notes$`),
  },
  profileTickerNote: {
    template: "/profile/tickers/{ticker}/notes/{note_id}",
    pattern: new RegExp(`^/profile/tickers/${TICKER_SEGMENT}/notes/[0-9]+$`),
  },
  profileTickerTags: {
    template: "/profile/tickers/{ticker}/tags",
    pattern: new RegExp(`^/profile/tickers/${TICKER_SEGMENT}/tags$`),
  },
  profileTagCatalog: {
    template: "/profile/tags/catalog",
    pattern: /^\/profile\/tags\/catalog$/,
  },
  profileInvestor: {
    template: "/profile/investor",
    pattern: /^\/profile\/investor$/,
  },
  symbolSearch: {
    template: "/symbols/search",
    pattern: /^\/symbols\/search$/,
  },
  consensus: {
    template: "/analysis/consensus/{ticker}",
    pattern: new RegExp(`^/analysis/consensus/${TICKER_SEGMENT}$`),
  },
  cards: {
    template: "/analysis/cards",
    pattern: /^\/analysis\/cards$/,
  },
  card: {
    template: "/analysis/cards/{run_id}",
    pattern: /^\/analysis\/cards\/[0-9]+$/,
  },
  generateCard: {
    template: "/analysis/card/{ticker}",
    pattern: new RegExp(`^/analysis/card/${TICKER_SEGMENT}$`),
  },
  saveCard: {
    template: "/analysis/cards/{run_id}/save",
    pattern: /^\/analysis\/cards\/[0-9]+\/save$/,
  },
  translateCard: {
    template: "/analysis/cards/{run_id}/translate",
    pattern: /^\/analysis\/cards\/[0-9]+\/translate$/,
  },
  priceChange: {
    template: "/prices/{ticker}/change",
    pattern: new RegExp(`^/prices/${TICKER_SEGMENT}/change$`),
  },
  options: {
    template: "/options/{ticker}",
    pattern: new RegExp(`^/options/${TICKER_SEGMENT}$`),
  },
  optionsHistory: {
    template: "/options/{ticker}/history",
    pattern: new RegExp(`^/options/${TICKER_SEGMENT}/history$`),
  },
  fundamentals: {
    template: "/fundamentals/{ticker}",
    pattern: new RegExp(`^/fundamentals/${TICKER_SEGMENT}$`),
  },
  marketDataStatus: {
    template: "/market-data/status",
    pattern: /^\/market-data\/status$/,
  },
  marketDataCoverage: {
    template: "/market-data/coverage/{ticker}",
    pattern: new RegExp(`^/market-data/coverage/${TICKER_SEGMENT}$`),
  },
  newsFeed: {
    template: "/news/feed",
    pattern: /^\/news\/feed$/,
  },
  seekingAlphaFeed: {
    template: "/sa/feed",
    pattern: /^\/sa\/feed$/,
  },
  seekingAlphaExtensionHealth: {
    template: "/sa/extension-health",
    pattern: /^\/sa\/extension-health$/,
  },
} as const satisfies Record<string, ReviewedRoute>;

const ROUTES_BY_OPERATION = {
  home_load_workspace: [routes.profileUniverse, routes.profileLists, routes.cards],
  home_open_card: [routes.card],
  home_save_card: [routes.saveCard],
  watchlist_load_lists: [routes.profileLists, routes.defaultWatchlist],
  watchlist_load_universe: [routes.profileUniverse],
  watchlist_search_symbols: [routes.symbolSearch],
  watchlist_load_consensus: [routes.consensus],
  watchlist_create_list: [routes.profileLists],
  watchlist_rename_list: [routes.profileList],
  watchlist_set_default_list: [routes.defaultWatchlist],
  watchlist_add_member: [routes.profileListMembers],
  watchlist_remove_member: [routes.profileListMember],
  watchlist_set_archived: [routes.profileTickerArchive],
  watchlist_set_priority: [routes.profileTickerPriority],
  universe_load: [routes.profileUniverse, routes.profileLists],
  universe_import: [routes.profileImportUniverse],
  universe_hide_ticker: [routes.profileTickerHidden],
  news_load_market: [routes.newsFeed],
  news_load_seeking_alpha: [routes.seekingAlphaFeed, routes.seekingAlphaExtensionHealth],
  news_load_more: [routes.newsFeed, routes.seekingAlphaFeed],
  ticker_load_state: [routes.profileTickerState],
  ticker_load_price: [routes.priceChange],
  ticker_load_iv: [routes.options],
  ticker_load_iv_history: [routes.optionsHistory],
  ticker_load_fundamentals: [routes.fundamentals],
  ticker_load_market_status: [routes.marketDataStatus],
  ticker_load_coverage: [routes.marketDataCoverage],
  ticker_load_notes: [routes.profileTickerNotes],
  ticker_load_tag_catalog: [routes.profileTagCatalog],
  ticker_add_note: [routes.profileTickerNotes],
  ticker_delete_note: [routes.profileTickerNote],
  ticker_add_tag: [routes.profileTickerTags],
  ticker_remove_tag: [routes.profileTickerTags],
  card_load_recent: [routes.cards],
  card_open: [routes.card],
  card_load_investor_profile: [routes.profileInvestor],
  card_generate: [routes.generateCard],
  card_save: [routes.saveCard],
  card_translate: [routes.translateCard],
} satisfies Record<ExploreOperation, readonly ReviewedRoute[]>;

const STABLE_ERROR_CODE = /^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$/;
const MAX_ERROR_CODE_LENGTH = 64;
const MAX_API_PATH_LENGTH = 160;
const MAX_DIAGNOSTIC_DETAIL_LENGTH = 160;

function readOwnDataProperty(value: unknown, field: string): unknown {
  if ((typeof value !== "object" || value === null) && typeof value !== "function") {
    return undefined;
  }
  try {
    const descriptor = Object.getOwnPropertyDescriptor(value, field);
    return descriptor && "value" in descriptor ? descriptor.value : undefined;
  } catch {
    return undefined;
  }
}

function normalizedStatus(value: unknown): number | null {
  return typeof value === "number"
    && Number.isInteger(value)
    && value >= 100
    && value <= 599
    ? value
    : null;
}

function normalizedCode(value: unknown): string | null {
  return typeof value === "string"
    && value.length <= MAX_ERROR_CODE_LENGTH
    && STABLE_ERROR_CODE.test(value)
    ? value
    : null;
}

function isNativeError(value: unknown): boolean {
  try {
    return value instanceof Error;
  } catch {
    return false;
  }
}

function strippedPathname(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const queryIndex = value.indexOf("?");
  const fragmentIndex = value.indexOf("#");
  const end = [queryIndex, fragmentIndex]
    .filter((index) => index >= 0)
    .reduce((earliest, index) => Math.min(earliest, index), value.length);
  const pathname = value.slice(0, end);
  if (
    !pathname.startsWith("/")
    || pathname.startsWith("//")
    || pathname.length === 0
    || pathname.length > MAX_API_PATH_LENGTH
    || /[^\x21-\x7e]/.test(pathname)
    || pathname.includes("\\")
  ) {
    return null;
  }
  return pathname;
}

function reviewedRouteTemplate(
  operation: ExploreOperation,
  value: unknown,
): string | null {
  const pathname = strippedPathname(value);
  if (!pathname) return null;
  return ROUTES_BY_OPERATION[operation]
    .find((route) => route.pattern.test(pathname))
    ?.template ?? null;
}

const SAFE_DIAGNOSTIC_DETAIL_PATTERNS = [
  /^upstream temporarily unavailable$/,
  /^request timed out after [1-9][0-9]{0,2}s$/,
  /^provider returned retryable status \(temporary\)\.$/,
  /^queue worker-[1-9][0-9]{0,5} unavailable; retry later$/,
] as const;

export function safeDiagnosticDetail(value: unknown): string | null {
  if (
    typeof value !== "string"
    || value.length === 0
    || value.length > MAX_DIAGNOSTIC_DETAIL_LENGTH
  ) {
    return null;
  }
  return SAFE_DIAGNOSTIC_DETAIL_PATTERNS.some((pattern) => pattern.test(value))
    ? value
    : null;
}

export function captureExploreError(
  operation: ExploreOperation,
  value: unknown,
): ExploreErrorState {
  const status = normalizedStatus(readOwnDataProperty(value, "status"));
  const code = normalizedCode(readOwnDataProperty(value, "code"));
  const routeTemplate = reviewedRouteTemplate(
    operation,
    readOwnDataProperty(value, "path"),
  );
  const diagnostic = readOwnDataProperty(value, "diagnostic");
  const developerDetail = safeDiagnosticDetail(diagnostic);
  const detailOmitted = diagnostic !== null
    && diagnostic !== undefined
    && developerDetail === null;

  return {
    operation,
    category: status !== null ? "http" : isNativeError(value) ? "network" : "unknown",
    status,
    code,
    routeTemplate,
    developerDetail,
    detailOmitted,
  };
}

const RECOVERY_TARGETS = {
  active_universe_unavailable: {
    kind: "settings_section",
    section: "data_sources",
  },
  sa_extension_health_unavailable: {
    kind: "settings_section",
    section: "data_sources",
  },
  provider_config_missing: {
    kind: "settings_section",
    section: "providers",
  },
} as const satisfies Record<string, ExploreSettingsTarget>;

export function recoveryTargetForExploreError(
  state: ExploreErrorState,
): ExploreSettingsTarget | null {
  const code = normalizedCode(state.code);
  if (!code || !Object.hasOwn(RECOVERY_TARGETS, code)) return null;
  return RECOVERY_TARGETS[code as keyof typeof RECOVERY_TARGETS];
}

function recoveryActionCopy(target: ExploreSettingsTarget, t: ExploreT): string {
  return target.section === "providers"
    ? t(($) => $.errors.recovery.providers)
    : t(($) => $.errors.recovery.dataSources);
}

export function presentExploreError(
  state: ExploreErrorState,
  t: ExploreT,
): ExploreErrorPresentation {
  const status = normalizedStatus(state.status);
  const code = normalizedCode(state.code);
  const routeTemplate = typeof state.routeTemplate === "string"
    && ROUTES_BY_OPERATION[state.operation]
      .some((route) => route.template === state.routeTemplate)
    ? state.routeTemplate
    : null;
  const developerDetail = safeDiagnosticDetail(state.developerDetail);
  const detailOmitted = state.detailOmitted
    || (state.developerDetail !== null && developerDetail === null);
  const recoveryTarget = recoveryTargetForExploreError(state);
  const recovery = recoveryTarget
    ? {
        prompt: t(($) => $.errors.diagnostics.recoveryPrompt),
        label: recoveryActionCopy(recoveryTarget, t),
        target: recoveryTarget,
      }
    : null;

  return {
    title: OPERATION_PRESENTERS[state.operation](t),
    diagnostics: {
      title: t(($) => $.errors.diagnostics.title),
      status: status === null
        ? null
        : {
            label: t(($) => $.errors.diagnostics.status),
            value: String(status),
          },
      code: code === null
        ? null
        : {
            label: t(($) => $.errors.diagnostics.code),
            value: code,
          },
      path: routeTemplate === null
        ? null
        : {
            label: t(($) => $.errors.diagnostics.path),
            value: routeTemplate,
          },
      detail: developerDetail === null
        ? null
        : {
            label: t(($) => $.errors.diagnostics.detail),
            value: developerDetail,
          },
      detailOmitted: detailOmitted
        ? t(($) => $.errors.diagnostics.detailOmitted)
        : null,
    },
    recovery,
  };
}

export function presentUniverseImportOutcome(
  outcome: UniverseImportOutcome,
  t: ExploreT,
): UniverseImportPresentation {
  const summaryItems: string[] = [
    t(($) => $.universe.tagsAdded, { count: outcome.tagsAdded }),
  ];
  if (outcome.listsRemoved > 0) {
    summaryItems.push(t(($) => $.universe.listsRemoved, { count: outcome.listsRemoved }));
  }
  return {
    title: t(($) => $.universe.importSucceeded, { summary: summaryItems.join(" · ") }),
    summaryItems,
    warning: outcome.groupsAvailable ? null : t(($) => $.universe.themeUnavailable),
  };
}
