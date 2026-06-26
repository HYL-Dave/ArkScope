import { describe, expect, it } from "vitest";

import { coverageStatusLabel, macroRoutingLabel, marketRoutingLabel, schedulerStateLabel } from "./marketDataDisplay";
import type { MacroStatus, MarketDataStatus } from "./api";

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
  it("distinguishes local-only strict routing from PG fallback routing", () => {
    expect(marketRoutingLabel(status({ routing_enabled: true, pg_fallback_active: false, strict_enabled: true })))
      .toBe("啟用中（local-only strict）");
    expect(marketRoutingLabel(status({ routing_enabled: true, pg_fallback_active: true, strict_enabled: false })))
      .toBe("啟用中（PG fallback）");
  });

  it("keeps the pending-db and disabled labels", () => {
    expect(marketRoutingLabel(status({ use_local_market_setting: true, routing_enabled: false })))
      .toBe("設定已開，待建立資料庫");
    expect(marketRoutingLabel(status({ use_local_market_setting: false, routing_enabled: false })))
      .toBe("關閉（使用 PG）");
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
      .toBe("啟用中（本地優先）");
    expect(macroRoutingLabel(macroStatus({ local_first_active: true, exists: true, env_override: true })))
      .toBe("啟用中（本地優先 · env 強制）");
  });

  it("toggle-on but DB not built → local-first, pending ingestion (NOT PG fallback)", () => {
    // the fix: local active even before the DB exists; the factory creates it on first use,
    // no PG fallback. So this is 'pending ingestion', not 'reads go PG'.
    expect(macroRoutingLabel(macroStatus({ local_first_active: true, exists: false })))
      .toBe("啟用中（本地優先）· 待 ingestion 建立");
  });

  it("off → PG", () => {
    expect(macroRoutingLabel(macroStatus({ local_first_active: false })))
      .toBe("關閉（使用 PG）");
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
