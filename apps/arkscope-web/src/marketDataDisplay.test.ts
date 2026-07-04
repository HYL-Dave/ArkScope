import { describe, expect, it } from "vitest";

import {
  coverageStatusLabel,
  macroRoutingLabel,
  marketRoutingLabel,
  newsPostgresRouteLabel,
  newsReadSurfaceLabel,
  newsRoutingLabel,
  newsWriteRouteLabel,
  providerHealthStatusLabel,
  schedulerStateLabel,
} from "./marketDataDisplay";
import type { MacroStatus, MarketDataStatus, NewsStatus } from "./api";

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
      .toBe("本地權威（設定尚未翻成預設；PG fallback 已退役）");
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
      .toBe("本地功能未啟用（不會 fallback PG）");
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
  it("distinguishes succeeded / failed / running / none", () => {
    expect(schedulerStateLabel({ last_status: "succeeded", continuation: null }).tone).toBe("ok");
    expect(schedulerStateLabel({ last_status: "failed", continuation: null }).tone).toBe("bad");
    expect(schedulerStateLabel({ last_status: "running", continuation: null }).label).toBe("執行中");
    expect(schedulerStateLabel(null).label).toBe("尚未執行");
  });
  it("partial with no deferred is not actionable", () => {
    expect(schedulerStateLabel({ last_status: "partial", continuation: { deferred: [] } }).needsContinue).toBe(false);
  });
});

describe("providerHealthStatusLabel", () => {
  it("labels disabled FRED macro ingestion as not-enabled ingestion, not a broken provider", () => {
    expect(providerHealthStatusLabel({
      id: "fred",
      kind: "macro",
      status: "disabled",
      disabled_reason: "macro_ingestion_disabled",
    })).toBe("未啟用抓取");
  });

  it("keeps generic disabled providers as disabled", () => {
    expect(providerHealthStatusLabel({
      id: "other",
      kind: "news",
      status: "disabled",
      disabled_reason: null,
    })).toBe("已停用");
  });
});
