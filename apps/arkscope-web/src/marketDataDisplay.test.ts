// @vitest-environment jsdom

import { createInstance } from "i18next";
import { describe, expect, it } from "vitest";

import * as marketDataDisplay from "./marketDataDisplay";
import {
  coverageStatusLabel as localizedCoverageStatusLabel,
  macroRoutingLabel as localizedMacroRoutingLabel,
  marketRoutingLabel as localizedMarketRoutingLabel,
  newsAuthorityLabel as localizedNewsAuthorityLabel,
  newsReadSurfaceLabel as localizedNewsReadSurfaceLabel,
  newsRoutingLabel as localizedNewsRoutingLabel,
  newsWriteRouteLabel as localizedNewsWriteRouteLabel,
  providerHealthStatusLabel as localizedProviderHealthStatusLabel,
  schedulerStateLabel as localizedSchedulerStateLabel,
} from "./marketDataDisplay";
import type { MacroStatus, MarketDataStatus, NewsStatus } from "./api";
import { initializeI18n } from "./i18n/resources";

type Locale = "zh-Hant" | "en";

function settingsT(locale: Locale) {
  const instance = createInstance();
  initializeI18n(instance, locale);
  return instance.getFixedT(locale, "settings");
}

const zhT = settingsT("zh-Hant");

function displayFunction<T extends (...args: never[]) => unknown>(name: string): T {
  const value = (marketDataDisplay as unknown as Record<string, unknown>)[name];
  if (typeof value !== "function") throw new Error(`missing display function ${name}`);
  return value as T;
}
const macroRoutingLabel = (value: MacroStatus) => localizedMacroRoutingLabel(value, zhT);
const marketRoutingLabel = (value: MarketDataStatus) => localizedMarketRoutingLabel(value, zhT);
const newsAuthorityLabel = (value: NewsStatus) => localizedNewsAuthorityLabel(value, zhT);
const newsReadSurfaceLabel = (value: NewsStatus) => localizedNewsReadSurfaceLabel(value, zhT);
const newsRoutingLabel = (value: NewsStatus) => localizedNewsRoutingLabel(value, zhT);
const newsWriteRouteLabel = (value: NewsStatus) => localizedNewsWriteRouteLabel(value, zhT);
const providerHealthStatusLabel = (
  value: Parameters<typeof localizedProviderHealthStatusLabel>[0] & Record<string, unknown>,
) => localizedProviderHealthStatusLabel(value, zhT);
const schedulerStateLabel = (
  value: Parameters<typeof localizedSchedulerStateLabel>[0],
) => localizedSchedulerStateLabel(value, zhT);

const status = (over: Partial<MarketDataStatus>): MarketDataStatus => ({
  market_db: "/tmp/market.db",
  exists: true,
  prices: { row_count: 0, ticker_count: 0, latest_datetime: null },
  news: { row_count: 0, source_count: 0, latest_published: null },
  fundamentals: { row_count: 0, ticker_count: 0, latest_date: null },
  financial_cache: { row_count: 0, valid_count: 0, expired_count: 0, latest_fetched_at: null },
  sync: { prices: null, news: null, fundamentals: null },
  prices_authority: "local",
  fundamentals_mode: "local_cache_refetch",
  use_local_market_setting: false,
  env_override: false,
  routing_enabled: false,
  local_market_strict_setting: false,
  strict_env_override: false,
  strict_enabled: false,
  ...over,
});

describe("marketRoutingLabel", () => {
  it("renders prices as local authority after P0-C", () => {
    expect(marketRoutingLabel(status({ routing_enabled: true, strict_enabled: true })))
      .toBe("本地資料");
    expect(marketRoutingLabel(status({ routing_enabled: true, strict_enabled: false })))
      .toBe("本地資料");
  });

  it("keeps pending local database distinct from a disabled setting", () => {
    expect(marketRoutingLabel(status({ use_local_market_setting: true, routing_enabled: false })))
      .toBe("設定已開，待建立資料庫");
    expect(marketRoutingLabel(status({ use_local_market_setting: false, routing_enabled: false })))
      .toBe("本地資料");
  });
});

const macroStatus = (over: Partial<MacroStatus>): MacroStatus => ({
  macro_db: "/tmp/macro_calendar.db",
  exists: false,
  tables: {},
  use_local_macro_setting: false,
  env_override: false,
  local_first_active: false,
  ...over,
});

describe("macroRoutingLabel", () => {
  it("labels local-first active (toggle vs env), DB built", () => {
    expect(macroRoutingLabel(macroStatus({ local_first_active: true, exists: true, use_local_macro_setting: true })))
      .toBe("啟用中（本地）");
    expect(macroRoutingLabel(macroStatus({ local_first_active: true, exists: true, env_override: true })))
      .toBe("啟用中（本地 · env 強制）");
  });

  it("labels enabled macro with missing local database as pending collection", () => {
    expect(macroRoutingLabel(macroStatus({ local_first_active: true, exists: false })))
      .toBe("啟用中（本地）· 待建立資料庫");
  });

  it("labels inactive local macro state without an alternate authority", () => {
    expect(macroRoutingLabel(macroStatus({ local_first_active: false })))
      .toBe("本地快照讀取可用；自動刷新未啟用");
  });
});

const newsStatus = (over: Partial<NewsStatus>): NewsStatus => ({
  market_db: "/tmp/market.db",
  exists: true,
  news: { row_count: 10, source_count: 2, latest_published: "2026-06-27T00:00:00+00:00" },
  use_local_news_setting: true,
  setting_explicit: false,
  env_override: false,
  env_value: null,
  direct_active: true,
  normalized_writes_setting: false,
  normalized_writes_setting_explicit: false,
  normalized_writes_env_override: false,
  normalized_writes_env_value: null,
  write_route: "legacy_local",
  write_route_reason: "test",
  sync: null,
  ...over,
});

describe("newsRoutingLabel", () => {
  it("distinguishes default direct routing from explicit rollback", () => {
    expect(newsRoutingLabel(newsStatus({}))).toBe("直寫本地（預設）");
    expect(newsRoutingLabel(newsStatus({ setting_explicit: true }))).toBe("直寫本地（已設定）");
    expect(newsRoutingLabel(newsStatus({ direct_active: false, use_local_news_setting: false, setting_explicit: true })))
      .toBe("本地相容寫入");
  });

  it("makes env override direction explicit", () => {
    expect(newsRoutingLabel(newsStatus({ env_override: true, env_value: true })))
      .toBe("直寫本地（env 強制開啟）");
    expect(newsRoutingLabel(newsStatus({ direct_active: false, env_override: true, env_value: false })))
      .toBe("本地相容寫入（env 強制關閉）");
  });
});

describe("news cutover labels", () => {
  it("renders the locked post-exit state", () => {
    const postExit = newsStatus({
      write_route: "normalized",
    } as Partial<NewsStatus>);

    expect(newsWriteRouteLabel(postExit)).toBe("Normalized SQLite + legacy local projection");
    expect(newsAuthorityLabel(postExit)).toBe("目前的本地資料");
    expect(newsReadSurfaceLabel(postExit)).toBe("Legacy local compatibility surface (N8b pending)");
    expect(newsRoutingLabel(postExit)).toBe("直寫本地（預設）");
  });
});

describe("news routing labels", () => {
  it("renders normalized writes as the current local authority", () => {
    const current = newsStatus({
      normalized_writes_setting: true,
      normalized_writes_setting_explicit: true,
      write_route: "normalized",
    } as Partial<NewsStatus>);

    expect(newsWriteRouteLabel(current)).toBe("Normalized SQLite + legacy local projection");
    expect(newsAuthorityLabel(current)).toBe("目前的本地資料");
    expect(newsReadSurfaceLabel(current)).toBe("Legacy local compatibility surface (N8b pending)");
  });
});

describe("coverageStatusLabel", () => {
  const row = (over: Record<string, unknown> = {}) => ({
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
    ...over,
  });

  it("maps every Coverage v2 day status in both locales and reserves positive tone for complete", () => {
    const cases = [
      {
        status: "non_trading",
        closureReason: "weekend",
        zh: "週末",
        en: "Weekend",
        tone: "muted",
      },
      { status: "in_progress", zh: "進行中", en: "In progress", tone: "muted" },
      { status: "complete", zh: "完整", en: "Complete", tone: "ok" },
      { status: "partial", zh: "部分", en: "Partial", tone: "warn" },
      {
        status: "indeterminate_tickers",
        zh: "部分標的未能判定",
        en: "Some tickers unresolved",
        tone: "warn",
      },
      { status: "unknown", zh: "未知", en: "Unknown", tone: "muted" },
    ];
    for (const item of cases) {
      const coverageRow = row({
        coverage_status: item.status,
        closure_reason_code: item.closureReason ?? null,
      });
      expect(localizedCoverageStatusLabel(coverageRow as never, zhT))
        .toEqual({ label: item.zh, tone: item.tone });
      expect(localizedCoverageStatusLabel(
        coverageRow as never,
        settingsT("en"),
      )).toEqual({ label: item.en, tone: item.tone });
    }
    expect(localizedCoverageStatusLabel(row({ coverage_status: "future_status" }) as never, zhT))
      .toEqual({ label: "無法判定", tone: "bad" });
  });

  it("maps non-trading closure reasons without backend prose", () => {
    const cases = [
      { reason: "weekend", zh: "週末", en: "Weekend" },
      { reason: "market_closed", zh: "休市", en: "Market closed" },
    ];
    for (const item of cases) {
      const coverageRow = row({
        coverage_status: "non_trading",
        closure_reason_code: item.reason,
      });
      expect(localizedCoverageStatusLabel(coverageRow as never, zhT))
        .toEqual({ label: item.zh, tone: "muted" });
      expect(localizedCoverageStatusLabel(coverageRow as never, settingsT("en")))
        .toEqual({ label: item.en, tone: "muted" });
    }
    expect(JSON.stringify(row({ closure_reason_code: "market_closed" })))
      .not.toContain("Juneteenth");
  });

  it("maps every Coverage v2 day reason in both locales", () => {
    const reasonLabel = displayFunction<(reason: string | null, t: typeof zhT) => string | null>(
      "coverageDayReasonLabel",
    );
    const cases = [
      ["calendar_unavailable", "交易日曆無法使用", "Calendar unavailable"],
      ["date_unreviewed", "日期超出已審日曆範圍", "Date outside reviewed calendar range"],
      ["observation_unavailable", "觀測資料無法使用", "Observations unavailable"],
      ["no_observations", "沒有觀測資料", "No observations"],
    ];
    for (const [reason, zh, en] of cases) {
      expect(reasonLabel(reason, zhT)).toBe(zh);
      expect(reasonLabel(reason, settingsT("en"))).toBe(en);
    }
    expect(reasonLabel(null, zhT)).toBeNull();
    expect(reasonLabel("raw backend prose", zhT)).toBe("無法判定");
  });

  it("maps calendar and observation health without parsing diagnostics", () => {
    const marketScopeLabel = displayFunction<(value: string, t: typeof zhT) => string>(
      "coverageMarketScopeLabel",
    );
    const coverageSessionLabel = displayFunction<(value: string, t: typeof zhT) => string>(
      "coverageSessionLabel",
    );
    const calendarLabels = displayFunction<(
      health: { status: string; reason_codes: string[] },
      t: typeof zhT,
    ) => string[]>("coverageCalendarHealthLabels");
    const observationLabel = displayFunction<(
      health: { status: string; reason_code: string | null },
      t: typeof zhT,
    ) => string | null>("coverageObservationHealthLabel");

    expect(marketScopeLabel("us_listed_equity_proxy", zhT)).toBe("美國上市股票代理範圍");
    expect(marketScopeLabel("us_listed_equity_proxy", settingsT("en")))
      .toBe("US-listed equity proxy");
    expect(coverageSessionLabel("rth", zhT)).toBe("正規交易時段（RTH）");
    expect(coverageSessionLabel("rth", settingsT("en")))
      .toBe("Regular trading hours (RTH)");
    expect(marketScopeLabel("future_scope", settingsT("en"))).toBe("Unable to determine");
    expect(coverageSessionLabel("future_session", zhT)).toBe("無法判定");

    expect(calendarLabels({
      status: "degraded",
      reason_codes: ["fixture_horizon_low", "date_unreviewed"],
    }, settingsT("en"))).toEqual([
      "Reviewed calendar horizon is low",
      "Date outside reviewed calendar range",
    ]);
    expect(observationLabel({
      status: "unavailable",
      reason_code: "market_db_unreadable",
    }, zhT)).toBe("市場資料庫無法讀取");
  });

  it("keeps partial and unknown ticker facts independent", () => {
    const facts = displayFunction<(
      value: ReturnType<typeof row>,
      t: typeof zhT,
    ) => {
      partialTitle: string | null;
      partialDetails: string[];
      unknownTitle: string | null;
      unknownDetail: string | null;
    }>("coverageTickerFactsPresentation");

    const enFacts = facts(row({
      partial_tickers: [{ ticker: "MSFT", observed_slot_count: 12, expected_slot_count: 26 }],
      unknown_tickers: ["PLANTED_UNKNOWN_A", "PLANTED_UNKNOWN_B"],
    }), settingsT("en"));
    expect(enFacts).toEqual({
      partialTitle: "Partially observed tickers",
      partialDetails: ["MSFT: 12/26 slots"],
      unknownTitle: "Unresolved tickers",
      unknownDetail: "2",
    });
    expect(JSON.stringify(enFacts)).not.toContain("PLANTED_UNKNOWN");

    const zhFacts = facts(row({
      unknown_tickers: ["PLANTED_UNKNOWN_A", "PLANTED_UNKNOWN_B"],
    }), zhT);
    expect(zhFacts.unknownDetail).toBe("2");
    expect(JSON.stringify(zhFacts)).not.toContain("PLANTED_UNKNOWN");
  });

  it("renders unmatched RTH rows as a separate data-quality warning", () => {
    const quality = displayFunction<(
      value: ReturnType<typeof row>,
      providerIssueCount: number,
      t: typeof zhT,
    ) => { unmatched: string | null; providerIssues: string | null }>(
      "coverageDataQualityPresentation",
    );

    expect(quality(row({ unmatched_rth_row_count: 2 }), 1, zhT)).toEqual({
      unmatched: "格線外的正規交易時段資料列：2",
      providerIssues: "供應商問題：1",
    });
  });

  it("separates security review signals from generic provider issues", () => {
    const labels = displayFunction<(
      issues: Array<{
        ticker: string;
        interval: string;
        last_error: string;
        reason_code: "security_definition_unavailable" | "price_data_unresolved" | "provider_request_failed" | "unknown";
        updated_at: string | null;
      }>,
      t: typeof zhT,
    ) => string[]>("coverageProviderIssueLabels");
    const issues = [
      {
        ticker: "EA",
        interval: "15min",
        last_error: "security_definition_unavailable",
        reason_code: "security_definition_unavailable" as const,
        updated_at: null,
      },
      {
        ticker: "LCID",
        interval: "15min",
        last_error: "price_day_unresolved_after_fetch",
        reason_code: "price_data_unresolved" as const,
        updated_at: null,
      },
      {
        ticker: "AAPL",
        interval: "15min",
        last_error: "provider failed",
        reason_code: "unknown" as const,
        updated_at: null,
      },
    ];

    expect(labels(issues, zhT)).toEqual([
      "IBKR 無法解析 1 個標的的合約：EA。可能是下市、代號異動或合約設定不完整；請先確認標的狀態。",
      "1 個標的在完成交易日仍無價格：LCID。可能是停牌、下市或資料來源暫時缺資料；系統不會自動移除。",
      "供應商問題：1",
    ]);
  });
});

describe("schedulerStateLabel", () => {
  it("partial with deferred → needs manual continue (補抓)", () => {
    const r = schedulerStateLabel({ last_status: "partial", continuation: { deferred: ["NVDA", "TSLA"] } });
    expect(r).toEqual({ label: "部分完成（待補抓 2）", tone: "warn", needsContinue: true });
  });

  it("renders price unresolved count and bounded ticker list without continuation", () => {
    const unresolvedTickers = Array.from(
      { length: 30 },
      (_, index) => `T${String(index).padStart(2, "0")}`,
    );
    const visibleTickers = unresolvedTickers.slice(0, 25).join(", ");
    const durable = {
      last_status: "partial",
      continuation: null,
      last_result: {
        source: "ibkr_prices",
        status: "partial",
        collect: {
          status: "partial" as const,
          tickers_scanned: 150,
          succeeded_ticker_count: 120,
          unresolved_after_fetch_count: 30,
          unresolved_after_fetch_tickers: unresolvedTickers,
        },
      },
    };
    expect(localizedSchedulerStateLabel(durable, zhT)).toEqual({
      label: `部分完成（抓取後仍有 30 個標的無法確認：${visibleTickers}）`,
      tone: "warn",
      needsContinue: false,
    });
    expect(localizedSchedulerStateLabel(durable, settingsT("en"))).toEqual({
      label: `Partially completed (30 tickers remain unresolved after collection: ${visibleTickers})`,
      tone: "warn",
      needsContinue: false,
    });
    const nonPrice = {
      ...durable,
      last_result: { ...durable.last_result, source: "polygon_news" },
    };
    expect(localizedSchedulerStateLabel(nonPrice, zhT).label).toBe("部分完成");
  });

  it("renders durable IBKR body counts without promising a manual retry", () => {
    const result = schedulerStateLabel({
      last_status: "partial",
      continuation: null,
      last_result: {
        source: "ibkr_news",
        status: "partial",
        collect: {
          status: "partial",
          continuation: {
            deferred_ticker_count: 0,
            deferred_body_count: 10,
            has_cursor: false,
          },
        },
      },
    });
    expect(result).toEqual({
      label: "部分完成（10 篇內文待後續處理）",
      tone: "warn",
      needsContinue: false,
    });
  });

  it("names an IBKR headline coverage gap instead of showing generic partial", () => {
    const durable = {
      last_status: "partial" as const,
      continuation: null,
      last_result: {
        source: "ibkr_news",
        status: "partial",
        collect: {
          status: "partial" as const,
          headline_pages_requested: 150,
          headline_saturated_tickers: 85,
          headline_incomplete_tickers: 3,
        },
      },
    };

    expect(localizedSchedulerStateLabel(durable, zhT)).toEqual({
      label: "部分完成（3 個標的的新聞可能有缺漏）",
      tone: "warn",
      needsContinue: false,
    });
    expect(localizedSchedulerStateLabel(durable, settingsT("en"))).toEqual({
      label: "Partially completed (news may be missing for 3 tickers)",
      tone: "warn",
      needsContinue: false,
    });
  });

  it.each([
    [
      { deferred_ticker_count: 3, deferred_body_count: 0, has_cursor: false },
      "部分完成（3 個標的待後續處理）",
    ],
    [
      { deferred_ticker_count: 3, deferred_body_count: 10, has_cursor: false },
      "部分完成（3 個標的、10 篇內文待後續處理）",
    ],
    [
      { deferred_ticker_count: 0, deferred_body_count: 0, has_cursor: true },
      "部分完成（尚有資料待後續處理）",
    ],
  ])("renders sanitized count/cursor state %j", (continuation, label) => {
    expect(schedulerStateLabel({
      last_status: "partial",
      continuation: null,
      last_result: {
        source: "ibkr_news",
        status: "partial",
        collect: { status: "partial", continuation },
      },
    })).toEqual({ label, tone: "warn", needsContinue: false });
  });

  it("keeps actionable ticker continuation ahead of informational counts", () => {
    const result = schedulerStateLabel({
      last_status: "partial",
      continuation: { deferred: ["NVDA", "TSLA"] },
      last_result: {
        source: "finnhub_news",
        status: "partial",
        collect: {
          continuation: {
            deferred_ticker_count: 0,
            deferred_body_count: 10,
            has_cursor: false,
          },
        },
      },
    });
    expect(result).toEqual({
      label: "部分完成（待補抓 2）",
      tone: "warn",
      needsContinue: true,
    });
  });

  it("does not turn invalid observed counts into numeric promises", () => {
    for (const value of [0, -1, 1.5, Number.POSITIVE_INFINITY, Number.NaN]) {
      const result = schedulerStateLabel({
        last_status: "partial",
        continuation: null,
        last_result: {
          source: "ibkr_news",
          status: "partial",
          collect: {
            continuation: {
              deferred_ticker_count: value,
              deferred_body_count: value,
              has_cursor: false,
            },
          },
        },
      });
      expect(result).toEqual({ label: "部分完成", tone: "warn", needsContinue: false });
    }
  });

  it("distinguishes succeeded / failed / skipped / running / none", () => {
    expect(schedulerStateLabel({ last_status: "succeeded", continuation: null }).tone).toBe("ok");
    expect(schedulerStateLabel({ last_status: "failed", continuation: null }).tone).toBe("bad");
    expect(schedulerStateLabel({ last_status: "skipped", continuation: null }).label).toBe("上次已跳過");
    expect(schedulerStateLabel({ last_status: "running", continuation: null }).label).toBe("執行中");
    expect(schedulerStateLabel(null).label).toBe("尚未執行");
  });
  it("names an IBKR Gateway failure instead of collapsing it into generic failure", () => {
    expect(schedulerStateLabel({
      last_status: "failed",
      last_error: "ibkr_gateway_unavailable",
      continuation: null,
    })).toEqual({
      label: "IBKR Gateway 無法連線",
      tone: "bad",
      needsContinue: false,
    });
  });
  it("labels stale running as an interrupted/stuck state", () => {
    const r = schedulerStateLabel({
      last_status: "running",
      continuation: null,
      running_stale: true,
      running_stale_reason: "running longer than configured stale threshold",
    });
    expect(r.label).toBe("執行過久");
    expect(r.tone).toBe("warn");
  });
  it("partial without actionable or observed continuation is generic", () => {
    const result = schedulerStateLabel({
      last_status: "partial",
      continuation: { deferred: [] },
    });
    expect(result).toEqual({ label: "部分完成", tone: "warn", needsContinue: false });
    expect(result.label).not.toContain("0");
  });
});

describe("schedulerBodyBacklogPresentation", () => {
  type DurablePresentation = NonNullable<
    Parameters<typeof marketDataDisplay.schedulerBodyBacklogPresentation>[0]
  >;
  const present = (durable: DurablePresentation) =>
    marketDataDisplay.schedulerBodyBacklogPresentation(durable, zhT);

  it("keeps a succeeded run successful when bodies are scheduled later", () => {
    const durable: DurablePresentation = {
      last_status: "succeeded",
      continuation: null,
      last_result: {
        source: "ibkr_news",
        status: "succeeded",
        collect: {
          status: "succeeded",
          body_backlog: {
            status: "ok",
            due_now: 0,
            scheduled_later: 2,
            never_attempted: 0,
            earliest_next_retry_at: "2026-07-15T06:00:00Z",
          },
        },
      },
    };

    expect(schedulerStateLabel(durable)).toEqual({
      label: "上次成功",
      tone: "ok",
      needsContinue: false,
    });
    expect(present(durable)).toEqual({
      label: "內文佇列：2 篇已排程稍後重試",
      tone: "muted",
      earliestNextRetryAt: "2026-07-15T06:00:00Z",
    });
  });

  it("describes due and never-attempted bodies without a manual action", () => {
    expect(present({
      last_status: "partial",
      continuation: null,
      last_result: {
        source: "ibkr_news",
        status: "partial",
        collect: {
          status: "partial" as const,
          body_backlog: {
            status: "ok",
            due_now: 4,
            scheduled_later: 2,
            never_attempted: 3,
            earliest_next_retry_at: "2026-07-15T08:00:00Z",
          },
        },
      },
    })).toEqual({
      label: "內文佇列：4 篇目前可處理（其中 3 篇尚未嘗試） · 2 篇已排程稍後重試",
      tone: "muted",
      earliestNextRetryAt: "2026-07-15T08:00:00Z",
    });
  });

  it("renders backlog-query failure as unavailable rather than zero", () => {
    expect(present({
      last_status: "partial",
      continuation: null,
      last_result: {
        source: "ibkr_news",
        status: "partial",
        collect: {
          status: "partial",
          body_backlog: { status: "unavailable" },
        },
      },
    })).toEqual({
      label: "內文待處理狀態暫時無法讀取",
      tone: "warn",
      earliestNextRetryAt: null,
    });
  });

  it("separates new body backlog from the partial run label", () => {
    const durable: DurablePresentation = {
      last_status: "partial",
      continuation: null,
      last_result: {
        source: "ibkr_news",
        status: "partial",
        collect: {
          status: "partial",
          continuation: {
            deferred_ticker_count: 0,
            deferred_body_count: 9,
            has_cursor: false,
          },
          body_backlog: {
            status: "ok",
            due_now: 1,
            scheduled_later: 1,
            never_attempted: 0,
            earliest_next_retry_at: "2026-07-15T08:00:00Z",
          },
        },
      },
    };

    expect(schedulerStateLabel(durable)).toEqual({
      label: "部分完成",
      tone: "warn",
      needsContinue: false,
    });
    expect(present(durable)?.label).toBe("內文佇列：1 篇目前可處理 · 1 篇已排程稍後重試");
  });

  it("fails closed on malformed backlog counts", () => {
    for (const malformed of [-1, 1.5, Number.POSITIVE_INFINITY, Number.NaN, "2", null]) {
      expect(present({
        last_status: "partial",
        continuation: null,
        last_result: {
          source: "ibkr_news",
          status: "partial",
          collect: {
            status: "partial",
            body_backlog: {
              status: "ok",
              due_now: malformed as unknown as number,
              scheduled_later: 0,
              never_attempted: 0,
              earliest_next_retry_at: null,
            },
          },
        },
      })).toEqual({
        label: "內文待處理狀態暫時無法讀取",
        tone: "warn",
        earliestNextRetryAt: null,
      });
    }
  });

  it("explains entitlement-blocked bodies without calling them permanently missing", () => {
    const view = present({
      last_status: "succeeded",
      continuation: null,
      last_result: {
        source: "ibkr_news",
        status: "succeeded",
        collect: {
          status: "succeeded",
          body_backlog: {
            status: "ok",
            due_now: 0,
            scheduled_later: 0,
            never_attempted: 0,
            earliest_next_retry_at: null,
            provider_not_entitled: 78,
          },
        },
      },
    });

    expect(view?.label).toContain("78 篇來源目前未訂閱");
    expect(view?.label).toContain("標題已保留");
    expect(view?.label).toContain("開通後自動重試");
    expect(view?.label).not.toContain("永久");
  });
});

describe("providerHealthStatusLabel", () => {
  it("labels legacy disabled FRED macro ingestion as generic disabled", () => {
    expect(providerHealthStatusLabel({
      id: "fred",
      kind: "macro",
      status: "disabled",
      disabled_reason: "macro_ingestion_disabled",
    })).toBe("已停用");
  });

  it("keeps generic disabled providers as disabled", () => {
    expect(providerHealthStatusLabel({
      id: "other",
      kind: "news",
      status: "disabled",
      disabled_reason: null,
    })).toBe("已停用");
  });

  it("labels strict missing provider config as not configured", () => {
    expect(providerHealthStatusLabel({
      id: "polygon",
      kind: "news",
      status: "not_configured",
      disabled_reason: null,
    })).toBe("未設定");
  });
});

describe("localized Settings market-data presentations", () => {
  it("renders Settings market and schedule presentations in both locales", () => {
    const durable = {
      last_status: "partial",
      continuation: { deferred: ["NVDA", "TSLA"] },
      last_result: {
        source: "ibkr_news",
        status: "partial",
        collect: {
          status: "partial" as const,
          body_backlog: {
            status: "ok" as const,
            due_now: 4,
            scheduled_later: 2,
            never_attempted: 3,
            earliest_next_retry_at: "2026-07-15T08:00:00Z",
          },
        },
      },
    };
    const cases = [
      {
        locale: "zh-Hant" as const,
        market: "本地資料",
        macro: "啟用中（本地 · env 強制）",
        news: "直寫本地（env 強制開啟）",
        write: "Normalized SQLite + legacy local projection",
        authority: "目前的本地資料",
        read: "Legacy local compatibility surface (N8b pending)",
        coverage: "部分",
        provider: "已停用",
        scheduler: "部分完成（待補抓 2）",
        backlog: "內文佇列：4 篇目前可處理（其中 3 篇尚未嘗試） · 2 篇已排程稍後重試",
      },
      {
        locale: "en" as const,
        market: "Local data authority",
        macro: "Active (local · forced by environment)",
        news: "Direct local writes (forced on by environment)",
        write: "Normalized SQLite + legacy local projection",
        authority: "Current local authority",
        read: "Legacy local compatibility surface (N8b pending)",
        coverage: "Partial",
        provider: "Disabled",
        scheduler: "Partially completed (2 remaining)",
        backlog: "Body queue: 4 available now (3 not yet attempted) · 2 scheduled for a later retry",
      },
    ];

    for (const expected of cases) {
      const t = settingsT(expected.locale);
      const market = status({ routing_enabled: true });
      const macro = macroStatus({ local_first_active: true, exists: true, env_override: true });
      const news = newsStatus({ env_override: true, env_value: true });
      const current = newsStatus({ write_route: "normalized" });
      expect(localizedMarketRoutingLabel(market, t)).toBe(expected.market);
      expect(localizedMacroRoutingLabel(macro, t)).toBe(expected.macro);
      expect(localizedNewsRoutingLabel(news, t)).toBe(expected.news);
      expect(localizedNewsWriteRouteLabel(current, t)).toBe(expected.write);
      expect(localizedNewsAuthorityLabel(current, t)).toBe(expected.authority);
      expect(localizedNewsReadSurfaceLabel(current, t)).toBe(expected.read);
      expect(localizedCoverageStatusLabel({
        coverage_status: "partial",
        closure_reason_code: null,
      }, t)).toEqual({ label: expected.coverage, tone: "warn" });
      expect(localizedProviderHealthStatusLabel({
        id: "fred",
        status: "disabled",
        disabled_reason: "PLANTED_DISABLED_REASON",
      }, t)).toBe(expected.provider);
      expect(localizedSchedulerStateLabel(durable, t)).toEqual({
        label: expected.scheduler,
        tone: "warn",
        needsContinue: true,
      });
      expect(marketDataDisplay.schedulerBodyBacklogPresentation(durable, t)).toEqual({
        label: expected.backlog,
        tone: "muted",
        earliestNextRetryAt: "2026-07-15T08:00:00Z",
      });
    }
  });

  it("keeps raw schedule reasons out of semantic status mapping", () => {
    const cases = [
      { locale: "zh-Hant" as const, skipped: "上次已跳過", stale: "執行過久" },
      { locale: "en" as const, skipped: "Last run was skipped", stale: "Running too long" },
    ];

    for (const expected of cases) {
      const t = settingsT(expected.locale);
      const skipped = [
        "collector already running: PLANTED_REASON",
        "PLANTED_REASON_WITHOUT_ENGLISH_SENTINEL",
      ].map((running_stale_reason) => localizedSchedulerStateLabel({
        last_status: "skipped",
        continuation: null,
        running_stale: false,
        running_stale_reason,
      }, t));
      expect(skipped).toEqual([
        { label: expected.skipped, tone: "muted", needsContinue: false },
        { label: expected.skipped, tone: "muted", needsContinue: false },
      ]);
      const stale = localizedSchedulerStateLabel({
        last_status: "running",
        continuation: null,
        running_stale: true,
        running_stale_reason: "PLANTED_STALE_REASON",
      }, t);
      expect(stale).toEqual({ label: expected.stale, tone: "warn", needsContinue: false });
      expect(`${skipped.map(({ label }) => label).join(" ")} ${stale.label}`)
        .not.toContain("PLANTED");
    }
  });
});
