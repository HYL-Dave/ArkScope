import type {
  CoverageStatus,
  MacroStatus,
  MarketDataStatus,
  NewsStatus,
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

// coverage_status → UI label + tone. The backend owns the completeness judgement (Slice A.1);
// the UI must render this label, NOT re-derive completeness from full/partial/missing.
export function coverageStatusLabel(
  row: Pick<TradingDayRow, "coverage_status" | "reason" | "holiday" | "max_observed_bar_count"> &
    Partial<Pick<TradingDayRow, "well_covered" | "covered">>,  // only the 'partial' branch needs these
  t: SettingsT,
): { label: string; tone: "ok" | "warn" | "muted" | "bad" } {
  switch (row.coverage_status) {
    case "non_trading":
      return {
        label: row.reason === "weekend"
          ? t(($) => $.dataStorage.coverage.status.weekend)
          : t(($) => $.dataStorage.coverage.status.holiday, { value: row.holiday ?? "" }),
        tone: "muted",
      };
    case "in_progress":
      return { label: t(($) => $.dataStorage.coverage.status.inProgress), tone: "muted" };
    case "missing":
      return { label: t(($) => $.dataStorage.coverage.status.missing), tone: "bad" };
    case "thin":
      return {
        label: t(($) => $.dataStorage.coverage.status.thin, {
          value: String(row.max_observed_bar_count ?? 0),
        }),
        tone: "warn",
      };
    case "partial":
      return {
        label: t(($) => $.dataStorage.coverage.status.partial, {
          count: row.well_covered ?? 0,
          value: row.covered ?? 0,
        }),
        tone: "warn",
      };
    case "complete_like":
      return { label: t(($) => $.dataStorage.coverage.status.completeLike), tone: "ok" };
    default:
      return {
        label: t(($) => $.dataStorage.coverage.status.unknown, { value: row.coverage_status }),
        tone: "muted",
      };
  }
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
