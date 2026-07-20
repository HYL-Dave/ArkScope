// @vitest-environment jsdom

import { createInstance } from "i18next";
import { describe, expect, it } from "vitest";

import * as marketDataDisplay from "./marketDataDisplay";
import {
  coverageStatusLabel as localizedCoverageStatusLabel,
  macroRoutingLabel as localizedMacroRoutingLabel,
  marketRoutingLabel as localizedMarketRoutingLabel,
  newsPostgresRouteLabel as localizedNewsPostgresRouteLabel,
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
const coverageStatusLabel = (row: Parameters<typeof localizedCoverageStatusLabel>[0]) =>
  localizedCoverageStatusLabel(row, zhT);
const macroRoutingLabel = (value: MacroStatus) => localizedMacroRoutingLabel(value, zhT);
const marketRoutingLabel = (value: MarketDataStatus) => localizedMarketRoutingLabel(value, zhT);
const newsPostgresRouteLabel = (value: NewsStatus) => localizedNewsPostgresRouteLabel(value, zhT);
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
  iv: { row_count: 0, ticker_count: 0, latest_date: null },
  fundamentals: { row_count: 0, ticker_count: 0, latest_date: null },
  financial_cache: { row_count: 0, valid_count: 0, expired_count: 0, latest_fetched_at: null },
  sync: { prices: null, news: null, iv: null, fundamentals: null },
  use_local_market_setting: false,
  env_override: false,
  routing_enabled: false,
  pg_fallback_active: false,
  local_market_strict_setting: false,
  strict_env_override: false,
  strict_enabled: false,
  ...over,
});

describe("marketRoutingLabel", () => {
  it("renders prices as local authority after P0-C", () => {
    expect(marketRoutingLabel(status({ routing_enabled: true, pg_fallback_active: false, strict_enabled: true })))
      .toBe("本地權威（PG fallback 已退役）");
    expect(marketRoutingLabel(status({ routing_enabled: true, pg_fallback_active: true, strict_enabled: false })))
      .toBe("本地權威（PG fallback 已退役）");
  });

  it("keeps pending-db distinct while disabled setting is no longer PG fallback", () => {
    expect(marketRoutingLabel(status({ use_local_market_setting: true, routing_enabled: false })))
      .toBe("設定已開，待建立資料庫");
    expect(marketRoutingLabel(status({ use_local_market_setting: false, routing_enabled: false })))
      .toBe("本地權威（legacy flag 未設定；PG fallback 已退役）");
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

  it("toggle-on but DB not built → local-first, pending ingestion (NOT PG fallback)", () => {
    // the fix: local active even before the DB exists; the factory creates it on first use,
    // no PG fallback. So this is 'pending ingestion', not 'reads go PG'.
    expect(macroRoutingLabel(macroStatus({ local_first_active: true, exists: false })))
      .toBe("啟用中（本地）· 待 ingestion 建立");
  });

  it("never suggests PG fallback when local macro is inactive", () => {
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
  news_pg_exit_completed: false,
  news_hard_local: false,
  pg_news_route_available: true,
  sync: null,
  ...over,
});

describe("newsRoutingLabel", () => {
  it("distinguishes default direct routing from explicit rollback", () => {
    expect(newsRoutingLabel(newsStatus({}))).toBe("直寫本地（預設）");
    expect(newsRoutingLabel(newsStatus({ setting_explicit: true }))).toBe("直寫本地（已設定）");
    expect(newsRoutingLabel(newsStatus({ direct_active: false, use_local_news_setting: false, setting_explicit: true })))
      .toBe("回退至 PG 同步／本地鏡像");
  });

  it("makes env override direction explicit", () => {
    expect(newsRoutingLabel(newsStatus({ env_override: true, env_value: true })))
      .toBe("直寫本地（env 強制開啟）");
    expect(newsRoutingLabel(newsStatus({ direct_active: false, env_override: true, env_value: false })))
      .toBe("回退 PG 鏡像（env 強制關閉）");
  });
});

describe("news cutover labels", () => {
  it("renders the locked post-exit state", () => {
    const postExit = newsStatus({
      write_route: "normalized",
      news_pg_exit_completed: true,
      news_hard_local: true,
      pg_news_route_available: false,
    } as Partial<NewsStatus>);

    expect(newsWriteRouteLabel(postExit)).toBe("Normalized SQLite + legacy local projection");
    expect(newsPostgresRouteLabel(postExit)).toBe("已退出（不可回退到 PG）");
    expect(newsReadSurfaceLabel(postExit)).toBe("Legacy local compatibility surface (N8b pending)");
    expect(newsRoutingLabel(postExit)).toBe("Normalized SQLite + legacy local projection");
  });

  it("keeps normalized writes visibly pre-exit/test while PG remains available", () => {
    const preExit = newsStatus({
      normalized_writes_setting: true,
      normalized_writes_setting_explicit: true,
      write_route: "normalized",
      news_pg_exit_completed: false,
      news_hard_local: false,
      pg_news_route_available: true,
    } as Partial<NewsStatus>);

    expect(newsWriteRouteLabel(preExit)).toBe("Normalized SQLite + legacy local projection（pre-exit test）");
    expect(newsPostgresRouteLabel(preExit)).toBe("可用（尚未退出）");
    expect(newsReadSurfaceLabel(preExit)).toBe("Legacy local direct surface");
  });
});

describe("coverageStatusLabel", () => {
  const row = (over: Record<string, unknown>) => ({
    coverage_status: "complete_like" as const, reason: "regular_trading_day",
    holiday: null, max_observed_bar_count: 26, ...over,
  });
  it("renders backend coverage_status (UI does not re-derive completeness)", () => {
    expect(coverageStatusLabel(row({ coverage_status: "complete_like" })).tone).toBe("ok");
    expect(coverageStatusLabel(row({ coverage_status: "missing" })))
      .toEqual({ label: "缺資料", tone: "bad" });
    expect(coverageStatusLabel(row({ coverage_status: "thin", max_observed_bar_count: 3 })))
      .toEqual({ label: "疑似不足（最多 3 根）", tone: "warn" });
    expect(coverageStatusLabel(row({ coverage_status: "partial", well_covered: 1, covered: 148 })))
      .toEqual({ label: "部分覆蓋（1/148 檔完整）", tone: "warn" });
    expect(coverageStatusLabel(row({ coverage_status: "in_progress" })).tone).toBe("muted");
  });
  it("distinguishes weekend vs holiday for non_trading", () => {
    expect(coverageStatusLabel(row({ coverage_status: "non_trading", reason: "weekend" })).label)
      .toBe("週末");
    expect(coverageStatusLabel(row({
      coverage_status: "non_trading", reason: "us_market_holiday", holiday: "Juneteenth National Independence Day",
    })).label).toBe("假日（Juneteenth National Independence Day）");
  });
});

describe("schedulerStateLabel", () => {
  it("partial with deferred → needs manual continue (補抓)", () => {
    const r = schedulerStateLabel({ last_status: "partial", continuation: { deferred: ["NVDA", "TSLA"] } });
    expect(r).toEqual({ label: "部分完成（待補抓 2）", tone: "warn", needsContinue: true });
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
        source: "price_backfill",
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
          status: "partial",
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
          status: "partial",
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
        market: "本地權威（PG fallback 已退役）",
        macro: "啟用中（本地 · env 強制）",
        news: "直寫本地（env 強制開啟）",
        write: "Normalized SQLite + legacy local projection（pre-exit test）",
        postgres: "可用（尚未退出）",
        read: "Legacy local direct surface",
        coverage: "部分覆蓋（1/148 檔完整）",
        provider: "已停用",
        scheduler: "部分完成（待補抓 2）",
        backlog: "內文佇列：4 篇目前可處理（其中 3 篇尚未嘗試） · 2 篇已排程稍後重試",
      },
      {
        locale: "en" as const,
        market: "Local authority (PG fallback retired)",
        macro: "Active (local · forced by environment)",
        news: "Direct local writes (forced on by environment)",
        write: "Normalized SQLite + legacy local projection (pre-exit test)",
        postgres: "Available (not yet exited)",
        read: "Legacy local direct surface",
        coverage: "Partial coverage (1/148 complete)",
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
      const preExit = newsStatus({ write_route: "normalized" });
      expect(localizedMarketRoutingLabel(market, t)).toBe(expected.market);
      expect(localizedMacroRoutingLabel(macro, t)).toBe(expected.macro);
      expect(localizedNewsRoutingLabel(news, t)).toBe(expected.news);
      expect(localizedNewsWriteRouteLabel(preExit, t)).toBe(expected.write);
      expect(localizedNewsPostgresRouteLabel(preExit, t)).toBe(expected.postgres);
      expect(localizedNewsReadSurfaceLabel(preExit, t)).toBe(expected.read);
      expect(localizedCoverageStatusLabel({
        coverage_status: "partial",
        reason: "regular_trading_day",
        holiday: null,
        max_observed_bar_count: 26,
        well_covered: 1,
        covered: 148,
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
