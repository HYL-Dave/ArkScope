import { describe, expect, it } from "vitest";

import { marketRoutingLabel } from "./marketDataDisplay";
import type { MarketDataStatus } from "./api";

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
