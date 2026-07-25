import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import type {
  CalendarHealthReason,
  CalendarHealthStatus,
  ClosureReasonCode,
  CoverageDayReason,
  CoverageDayStatus,
  CoverageSession,
  MarketScope,
  ObservationHealthReason,
  ObservationHealthStatus,
  SessionKind,
  TradingDayCoverage,
  TradingDayRow,
} from "./api";

type Equal<A, B> =
  (<T>() => T extends A ? 1 : 2) extends
  (<T>() => T extends B ? 1 : 2) ? true : false;

const marketScopes = ["us_listed_equity_proxy"] as const satisfies readonly MarketScope[];
const coverageSessions = ["rth"] as const satisfies readonly CoverageSession[];
const calendarHealthStatuses = ["ok", "degraded", "unavailable"] as const satisfies readonly CalendarHealthStatus[];
const observationHealthStatuses = ["ok", "unavailable"] as const satisfies readonly ObservationHealthStatus[];
const calendarHealthReasons = [
  "fixture_horizon_low",
  "date_unreviewed",
  "calendar_unavailable",
] as const satisfies readonly CalendarHealthReason[];
const observationHealthReasons = [
  "market_db_missing",
  "market_db_unreadable",
  "prices_schema_missing",
] as const satisfies readonly ObservationHealthReason[];
const coverageDayStatuses = [
  "non_trading",
  "in_progress",
  "complete",
  "partial",
  "indeterminate_tickers",
  "unknown",
] as const satisfies readonly CoverageDayStatus[];
const coverageDayReasons = [
  "calendar_unavailable",
  "date_unreviewed",
  "observation_unavailable",
  "no_observations",
] as const satisfies readonly CoverageDayReason[];
const closureReasonCodes = ["weekend", "market_closed"] as const satisfies readonly ClosureReasonCode[];
const sessionKinds = ["regular", "early_close"] as const satisfies readonly SessionKind[];

const exactCatalogs: [
  Equal<(typeof marketScopes)[number], MarketScope>,
  Equal<(typeof coverageSessions)[number], CoverageSession>,
  Equal<(typeof calendarHealthStatuses)[number], CalendarHealthStatus>,
  Equal<(typeof observationHealthStatuses)[number], ObservationHealthStatus>,
  Equal<(typeof calendarHealthReasons)[number], CalendarHealthReason>,
  Equal<(typeof observationHealthReasons)[number], ObservationHealthReason>,
  Equal<(typeof coverageDayStatuses)[number], CoverageDayStatus>,
  Equal<(typeof coverageDayReasons)[number], CoverageDayReason>,
  Equal<(typeof closureReasonCodes)[number], ClosureReasonCode>,
  Equal<(typeof sessionKinds)[number], SessionKind>,
] = [true, true, true, true, true, true, true, true, true, true];

const v2Fixture = {
  version: 2,
  market_scope: "us_listed_equity_proxy",
  coverage_session: "rth",
  interval: "15min",
  lookback_days: 10,
  universe_count: 2,
  generated_at_et: "2026-07-24T16:30:00-04:00",
  calendar_health: {
    status: "ok",
    reason_codes: [],
    reviewed_through: "2027-12-31",
    forward_horizon_months: 17,
  },
  observation_health: { status: "ok", reason_code: null },
  days: [{
    date: "2026-07-24",
    coverage_status: "partial",
    status_reason_code: null,
    closure_reason_code: null,
    session_kind: "regular",
    session_open_at_utc: "2026-07-24T13:30:00+00:00",
    session_close_at_utc: "2026-07-24T20:00:00+00:00",
    expected_slot_count: 26,
    observed_ticker_count: 2,
    complete_ticker_count: 1,
    partial_ticker_count: 1,
    unknown_ticker_count: 0,
    partial_tickers: [{ ticker: "MSFT", observed_slot_count: 12, expected_slot_count: 26 }],
    unknown_tickers: [],
    unmatched_rth_row_count: 1,
  }],
  provider_errors: [],
} satisfies TradingDayCoverage;

const retiredDayFixture = {
  ...v2Fixture.days[0],
  // @ts-expect-error Coverage v1 planner field must not return to the DTO.
  missing_tickers: ["AAPL"],
} satisfies TradingDayRow;

const retiredStatusFixture = {
  ...v2Fixture.days[0],
  // @ts-expect-error Coverage v1 status must not return to the DTO.
  coverage_status: "complete_like",
} satisfies TradingDayRow;

const retiredMaxRelativeFixture = {
  ...v2Fixture.days[0],
  // @ts-expect-error Coverage v1 max-relative field must not return to the DTO.
  max_observed_bar_count: 26,
} satisfies TradingDayRow;

describe("Coverage v2 contract", () => {
  it("exports the exact closed Coverage v2 enum catalogs", () => {
    const source = readFileSync(resolve(import.meta.dirname, "./api.ts"), "utf8");
    expect(exactCatalogs).toEqual([true, true, true, true, true, true, true, true, true, true]);
    expect(source).toContain("export type MarketScope = \"us_listed_equity_proxy\"");
    expect(source).toContain("export type CoverageDayStatus =");
    expect(source).toContain("export type ObservationHealthReason =");
  });

  it("accepts the V2 DTO and rejects retired field fixtures", () => {
    const source = readFileSync(resolve(import.meta.dirname, "./api.ts"), "utf8");
    const coverageSource = source.slice(
      source.indexOf("// --- trading-day coverage"),
      source.indexOf("// --- News feed"),
    );
    expect(v2Fixture.version).toBe(2);
    expect(retiredDayFixture.missing_tickers).toEqual(["AAPL"]);
    expect(retiredStatusFixture.coverage_status).toBe("complete_like");
    expect(retiredMaxRelativeFixture.max_observed_bar_count).toBe(26);
    expect(coverageSource).toContain("version: 2");
    expect(coverageSource).not.toMatch(/missing_tickers|max_observed_bar_count|complete_like/);
  });

  it("keeps every frontend coverage enum consumer exhaustive and exact", () => {
    const displaySource = readFileSync(
      resolve(import.meta.dirname, "./marketDataDisplay.ts"),
      "utf8",
    );
    const storageSource = readFileSync(
      resolve(import.meta.dirname, "./settings/DataStorageSection.tsx"),
      "utf8",
    );
    expect(displaySource).toContain("function unreachableCoverageValue(value: never): void");
    expect(displaySource).toContain("export function coverageMarketScopeLabel");
    expect(displaySource).toContain("export function coverageSessionLabel");
    expect(displaySource).not.toMatch(/coverage_status\.(?:startsWith|includes)/);
    expect(displaySource).not.toMatch(/status_reason_code\.(?:startsWith|includes)/);
    expect(storageSource).toContain("coverageMarketScopeLabel(cov.market_scope, t)");
    expect(storageSource).toContain("coverageSessionLabel(cov.coverage_session, t)");
  });
});
