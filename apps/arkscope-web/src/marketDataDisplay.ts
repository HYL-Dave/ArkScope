import type {
  CalendarHealthReason,
  ClosureReasonCode,
  CoverageCalendarHealth,
  CoverageDayReason,
  CoverageObservationHealth,
  MacroStatus,
  MarketDataStatus,
  NewsStatus,
  ObservationHealthReason,
  ScheduleSourceState,
  TradingDayRow,
} from "./api";
import {
  providerHealthCopy,
  scheduleBodyBacklogCopy,
} from "./settings/settingsBackendCopy";
import type { SettingsT } from "./settings/settingsCopy";

export function providerHealthStatusLabel<T extends {
  id: string;
  status: Parameters<typeof providerHealthCopy>[1];
}>(p: T, t: SettingsT): string {
  return providerHealthCopy(p.id, p.status, t).label;
}

export function marketRoutingLabel(status: MarketDataStatus, t: SettingsT): string {
  if (status.routing_enabled) return t(($) => $.dataStorage.routing.localAuthority);
  if (status.use_local_market_setting) {
    return t(($) => $.dataStorage.routing.settingEnabledPendingDatabase);
  }
  return t(($) => $.dataStorage.routing.localAuthorityLegacyFlagUnset);
}

export function macroRoutingLabel(status: MacroStatus, t: SettingsT): string {
  // local_first_active = (toggle OR env). Routing is local the moment it's on — the store
  // factory creates macro_calendar.db on first use and there is NO PG fallback in the local
  // path. So toggle-on is "本地優先" even before the DB is built (queries return empty until
  // ingestion fills it) — NOT a PG fallback.
  if (!status.local_first_active) return t(($) => $.macroStorage.routing.snapshotOnly);
  const envNote = status.env_override ? t(($) => $.macroStorage.routing.envForced) : "";
  return status.exists
    ? t(($) => $.macroStorage.routing.active, { value: envNote })
    : t(($) => $.macroStorage.routing.activePending, { value: envNote });
}

export function newsRoutingLabel(status: NewsStatus, t: SettingsT): string {
  if (status.news_hard_local) return newsWriteRouteLabel(status, t);
  if (status.env_override) {
    return status.direct_active
      ? t(($) => $.newsStorage.routing.directEnvOn)
      : t(($) => $.newsStorage.routing.pgMirrorEnvOff);
  }
  if (!status.direct_active) return t(($) => $.newsStorage.routing.pgSyncLocalMirror);
  return status.setting_explicit
    ? t(($) => $.newsStorage.routing.directExplicit)
    : t(($) => $.newsStorage.routing.directDefault);
}

export function newsWriteRouteLabel(status: NewsStatus, t: SettingsT): string {
  if (status.news_hard_local) return t(($) => $.newsStorage.routing.write.normalized);
  switch (status.write_route) {
    case "normalized":
      return t(($) => $.newsStorage.routing.write.normalizedPreExit);
    case "legacy_local":
      return t(($) => $.newsStorage.routing.write.legacyLocal);
    case "legacy_pg":
      return t(($) => $.newsStorage.routing.write.legacyPg);
    case "blocked":
      return t(($) => $.newsStorage.routing.write.blocked);
    default:
      return status.write_route;
  }
}

export function newsPostgresRouteLabel(status: NewsStatus, t: SettingsT): string {
  if (status.news_hard_local) return t(($) => $.newsStorage.routing.postgres.exited);
  return status.pg_news_route_available
    ? t(($) => $.newsStorage.routing.postgres.available)
    : t(($) => $.newsStorage.routing.postgres.unavailable);
}

export function newsReadSurfaceLabel(status: NewsStatus, t: SettingsT): string {
  if (status.news_hard_local) return t(($) => $.newsStorage.routing.read.compatibility);
  return status.direct_active
    ? t(($) => $.newsStorage.routing.read.localDirect)
    : t(($) => $.newsStorage.routing.read.pgMirror);
}

function unreachableCoverageValue(value: never): void {
  void value;
}

function unavailableCoverageLabel(t: SettingsT): string {
  return t(($) => $.dataStorage.coverage.status.unavailable);
}

const WEEKEND_CLOSURE_REASON = {
  label: "weekend",
} as const satisfies { label: ClosureReasonCode };
const COVERAGE_UNAVAILABLE_TONE = "bad" as const;

function closureReasonLabel(reason: ClosureReasonCode | null, t: SettingsT): string | null {
  switch (reason) {
    case WEEKEND_CLOSURE_REASON.label:
      return t(($) => $.dataStorage.coverage.status.weekend);
    case "market_closed":
      return t(($) => $.dataStorage.coverage.status.marketClosed);
    case null:
      return null;
    default:
      unreachableCoverageValue(reason);
      return unavailableCoverageLabel(t);
  }
}

export function coverageStatusLabel(
  row: Pick<TradingDayRow, "coverage_status" | "closure_reason_code">,
  t: SettingsT,
): { label: string; tone: "ok" | "warn" | "muted" | "bad" } {
  switch (row.coverage_status) {
    case "unknown":
      return { label: t(($) => $.dataStorage.coverage.status.unknown), tone: "muted" };
    case "non_trading": {
      const label = closureReasonLabel(row.closure_reason_code, t);
      return {
        label: label ?? unavailableCoverageLabel(t),
        tone: label ? "muted" : COVERAGE_UNAVAILABLE_TONE,
      };
    }
    case "in_progress":
      return { label: t(($) => $.dataStorage.coverage.status.inProgress), tone: "muted" };
    case "partial":
      return { label: t(($) => $.dataStorage.coverage.status.partial), tone: "warn" };
    case "indeterminate_tickers":
      return {
        label: t(($) => $.dataStorage.coverage.status.indeterminateTickers),
        tone: "warn",
      };
    case "complete":
      return { label: t(($) => $.dataStorage.coverage.status.complete), tone: "ok" };
    default:
      unreachableCoverageValue(row.coverage_status);
      return { label: unavailableCoverageLabel(t), tone: "bad" };
  }
}

export function coverageDayReasonLabel(
  reason: CoverageDayReason | null,
  t: SettingsT,
): string | null {
  switch (reason) {
    case "calendar_unavailable":
      return t(($) => $.dataStorage.coverage.reasons.calendarUnavailable);
    case "date_unreviewed":
      return t(($) => $.dataStorage.coverage.reasons.dateUnreviewed);
    case "observation_unavailable":
      return t(($) => $.dataStorage.coverage.reasons.observationUnavailable);
    case "no_observations":
      return t(($) => $.dataStorage.coverage.reasons.noObservations);
    case null:
      return null;
    default:
      unreachableCoverageValue(reason);
      return unavailableCoverageLabel(t);
  }
}

function calendarHealthReasonLabel(reason: CalendarHealthReason, t: SettingsT): string {
  switch (reason) {
    case "fixture_horizon_low":
      return t(($) => $.dataStorage.coverage.health.fixtureHorizonLow);
    case "date_unreviewed":
      return t(($) => $.dataStorage.coverage.health.dateUnreviewed);
    case "calendar_unavailable":
      return t(($) => $.dataStorage.coverage.health.calendarUnavailable);
    default:
      unreachableCoverageValue(reason);
      return unavailableCoverageLabel(t);
  }
}

export function coverageCalendarHealthLabels(
  health: Pick<CoverageCalendarHealth, "status" | "reason_codes">,
  t: SettingsT,
): string[] {
  switch (health.status) {
    case "ok":
      return [];
    case "degraded":
    case "unavailable":
      return health.reason_codes.length > 0
        ? health.reason_codes.map((reason) => calendarHealthReasonLabel(reason, t))
        : [unavailableCoverageLabel(t)];
    default:
      unreachableCoverageValue(health.status);
      return [unavailableCoverageLabel(t)];
  }
}

function observationHealthReasonLabel(reason: ObservationHealthReason, t: SettingsT): string {
  switch (reason) {
    case "market_db_missing":
      return t(($) => $.dataStorage.coverage.health.marketDbMissing);
    case "market_db_unreadable":
      return t(($) => $.dataStorage.coverage.health.marketDbUnreadable);
    case "prices_schema_missing":
      return t(($) => $.dataStorage.coverage.health.pricesSchemaMissing);
    default:
      unreachableCoverageValue(reason);
      return unavailableCoverageLabel(t);
  }
}

export function coverageObservationHealthLabel(
  health: Pick<CoverageObservationHealth, "status" | "reason_code">,
  t: SettingsT,
): string | null {
  switch (health.status) {
    case "ok":
      return null;
    case "unavailable":
      return health.reason_code === null
        ? unavailableCoverageLabel(t)
        : observationHealthReasonLabel(health.reason_code, t);
    default:
      unreachableCoverageValue(health.status);
      return unavailableCoverageLabel(t);
  }
}

export interface CoverageTickerFactsPresentation {
  partialTitle: string | null;
  partialDetails: string[];
  unknownTitle: string | null;
  unknownDetail: string | null;
}

export function coverageTickerFactsPresentation(
  row: Pick<TradingDayRow, "partial_tickers" | "unknown_tickers">,
  t: SettingsT,
): CoverageTickerFactsPresentation {
  const hasPartial = row.partial_tickers.length > 0;
  const hasUnknown = row.unknown_tickers.length > 0;
  return {
    partialTitle: hasPartial
      ? t(($) => $.dataStorage.coverage.drilldown.partialTitle)
      : null,
    partialDetails: row.partial_tickers.map((ticker) =>
      t(($) => $.dataStorage.coverage.drilldown.partialDetail, {
        ticker: ticker.ticker,
        observed: ticker.observed_slot_count,
        expected: ticker.expected_slot_count,
      })),
    unknownTitle: hasUnknown
      ? t(($) => $.dataStorage.coverage.drilldown.unknownTitle)
      : null,
    unknownDetail: hasUnknown
      ? t(($) => $.dataStorage.coverage.drilldown.unknownDetail, {
        count: row.unknown_tickers.length,
        value: row.unknown_tickers.join(", "),
      })
      : null,
  };
}

export function coverageDataQualityPresentation(
  row: Pick<TradingDayRow, "unmatched_rth_row_count">,
  providerIssueCount: number,
  t: SettingsT,
): { unmatched: string | null; providerIssues: string | null } {
  const unmatchedCount = row.unmatched_rth_row_count ?? 0;
  return {
    unmatched: unmatchedCount > 0
      ? t(($) => $.dataStorage.coverage.drilldown.unmatched, {
        count: unmatchedCount,
      })
      : null,
    providerIssues: providerIssueCount > 0
      ? t(($) => $.dataStorage.coverage.drilldown.providerIssues, {
        count: providerIssueCount,
      })
      : null,
  };
}

type SchedulerDurablePresentation = Pick<
  NonNullable<ScheduleSourceState["durable_state"]>,
  | "last_status"
  | "continuation"
  | "last_result"
  | "running_stale"
  | "running_stale_reason"
>;

function positiveCount(value: unknown): number {
  if (typeof value !== "number" || !Number.isInteger(value) || value <= 0) return 0;
  return value;
}

export interface SchedulerBodyBacklogPresentation {
  label: string;
  tone: "muted" | "warn";
  earliestNextRetryAt: string | null;
}

export function schedulerBodyBacklogPresentation(
  durable: SchedulerDurablePresentation | null,
  t: SettingsT,
): SchedulerBodyBacklogPresentation | null {
  return scheduleBodyBacklogCopy(durable?.last_result ?? null, t);
}

export function schedulerStateLabel(
  durable: SchedulerDurablePresentation | null,
  t: SettingsT,
): { label: string; tone: "ok" | "warn" | "muted" | "bad"; needsContinue: boolean } {
  const st = durable?.last_status ?? null;
  switch (st) {
    case "succeeded":
      return {
        label: t(($) => $.dataSources.schedule.history.succeeded),
        tone: "ok",
        needsContinue: false,
      };
    case "partial": {
      const actionable = durable?.continuation?.deferred?.length ?? 0;
      if (actionable > 0) {
        return {
          label: t(($) => $.dataSources.schedule.history.partialActionable, {
            count: actionable,
          }),
          tone: "warn",
          needsContinue: true,
        };
      }
      const collect = durable?.last_result?.collect;
      const observed = collect?.continuation;
      const tickers = positiveCount(observed?.deferred_ticker_count);
      const bodies = collect?.body_backlog === undefined
        ? positiveCount(observed?.deferred_body_count)
        : 0;
      if (tickers > 0 && bodies > 0) {
        return {
          label: t(($) => $.dataSources.schedule.history.partialTickersAndBodies, {
            count: tickers,
            value: bodies,
          }),
          tone: "warn",
          needsContinue: false,
        };
      }
      if (bodies > 0) {
        return {
          label: t(($) => $.dataSources.schedule.history.partialBodies, { count: bodies }),
          tone: "warn",
          needsContinue: false,
        };
      }
      if (tickers > 0) {
        return {
          label: t(($) => $.dataSources.schedule.history.partialTickers, {
            count: tickers,
          }),
          tone: "warn",
          needsContinue: false,
        };
      }
      if (observed?.has_cursor === true) {
        return {
          label: t(($) => $.dataSources.schedule.history.partialCursor),
          tone: "warn",
          needsContinue: false,
        };
      }
      return {
        label: t(($) => $.dataSources.schedule.history.partial),
        tone: "warn",
        needsContinue: false,
      };
    }
    case "failed":
      return {
        label: t(($) => $.dataSources.schedule.history.failed),
        tone: "bad",
        needsContinue: false,
      };
    case "skipped":
      return {
        label: t(($) => $.dataSources.schedule.history.skipped),
        tone: "muted",
        needsContinue: false,
      };
    case "running":
      if (durable?.running_stale) {
        return {
          label: t(($) => $.dataSources.schedule.history.runningStale),
          tone: "warn",
          needsContinue: false,
        };
      }
      return {
        label: t(($) => $.dataSources.schedule.history.running),
        tone: "muted",
        needsContinue: false,
      };
    default:
      return {
        label: t(($) => $.dataSources.schedule.history.notRun),
        tone: "muted",
        needsContinue: false,
      };
  }
}
