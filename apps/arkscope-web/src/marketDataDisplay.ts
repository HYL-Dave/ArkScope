import type { CoverageStatus, MacroStatus, MarketDataStatus, TradingDayRow } from "./api";

export function marketRoutingLabel(status: MarketDataStatus): string {
  if (status.routing_enabled) {
    return status.pg_fallback_active ? "啟用中（PG fallback）" : "啟用中（local-only strict）";
  }
  if (status.use_local_market_setting) return "設定已開，待建立資料庫";
  return "關閉（使用 PG）";
}

export function macroRoutingLabel(status: MacroStatus): string {
  // local_first_active = (toggle OR env). Routing is local the moment it's on — the store
  // factory creates macro_calendar.db on first use and there is NO PG fallback in the local
  // path. So toggle-on is "本地優先" even before the DB is built (queries return empty until
  // ingestion fills it) — NOT a PG fallback.
  if (!status.local_first_active) return "關閉（使用 PG）";
  const envNote = status.env_override ? " · env 強制" : "";
  return status.exists
    ? `啟用中（本地優先${envNote}）`
    : `啟用中（本地優先${envNote}）· 待 ingestion 建立`;
}

// coverage_status → UI label + tone. The backend owns the completeness judgement (Slice A.1);
// the UI must render this label, NOT re-derive completeness from full/partial/missing.
export function coverageStatusLabel(
  row: Pick<TradingDayRow, "coverage_status" | "reason" | "holiday" | "max_observed_bar_count"> &
    Partial<Pick<TradingDayRow, "well_covered" | "covered">>,  // only the 'partial' branch needs these
): { label: string; tone: "ok" | "warn" | "muted" | "bad" } {
  switch (row.coverage_status) {
    case "non_trading":
      return {
        label: row.reason === "weekend" ? "週末" : `假日${row.holiday ? `（${row.holiday}）` : ""}`,
        tone: "muted",
      };
    case "in_progress":
      return { label: "盤中（未收盤）", tone: "muted" };
    case "missing":
      return { label: "缺資料", tone: "bad" };
    case "thin":
      return { label: `疑似不足（最多 ${row.max_observed_bar_count ?? 0} 根）`, tone: "warn" };
    case "partial":
      return { label: `部分覆蓋（${row.well_covered ?? 0}/${row.covered ?? 0} 檔完整）`, tone: "warn" };
    case "complete_like":
      return { label: "覆蓋完整", tone: "ok" };
    default:
      return { label: row.coverage_status, tone: "muted" };
  }
}

// Scheduler durable-state → UI label + tone (v1.4). Distinguishes the cases the reviewer
// stressed: partial = a budget-bounded run left work → needs manual 補抓; skipped (transient,
// from last_result, not durable) = temporarily not run; failed carries the error.
export function schedulerStateLabel(
  durable: {
    last_status: string | null;
    continuation: { deferred?: string[] } | null;
  } | null,
): { label: string; tone: "ok" | "warn" | "muted" | "bad"; needsContinue: boolean } {
  const st = durable?.last_status ?? null;
  switch (st) {
    case "succeeded":
      return { label: "上次成功", tone: "ok", needsContinue: false };
    case "partial": {
      const n = durable?.continuation?.deferred?.length ?? 0;
      return { label: `部分完成（待補抓 ${n}）`, tone: "warn", needsContinue: n > 0 };
    }
    case "failed":
      return { label: "上次失敗", tone: "bad", needsContinue: false };
    case "running":
      return { label: "執行中", tone: "muted", needsContinue: false };
    default:
      return { label: "尚未執行", tone: "muted", needsContinue: false };
  }
}
