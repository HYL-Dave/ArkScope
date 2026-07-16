import type {
  CoverageStatus,
  MacroStatus,
  MarketDataStatus,
  NewsStatus,
  ScheduleSourceState,
  TradingDayRow,
} from "./api";

export function providerHealthStatusLabel<T extends { status: string; disabled_reason?: string | null }>(p: T): string {
  const labels: Record<string, string> = {
    connected: "正常",
    stale: "過期",
    maintenance: "維護中",
    no_signal: "無訊號",
    not_configured: "未設定",
    missing_key: "缺金鑰",
    disabled: "已停用",
  };
  return labels[p.status] ?? p.status;
}

export function marketRoutingLabel(status: MarketDataStatus): string {
  if (status.routing_enabled) return "本地權威（PG fallback 已退役）";
  if (status.use_local_market_setting) return "設定已開，待建立資料庫";
  return "本地權威（legacy flag 未設定；PG fallback 已退役）";
}

export function macroRoutingLabel(status: MacroStatus): string {
  // local_first_active = (toggle OR env). Routing is local the moment it's on — the store
  // factory creates macro_calendar.db on first use and there is NO PG fallback in the local
  // path. So toggle-on is "本地優先" even before the DB is built (queries return empty until
  // ingestion fills it) — NOT a PG fallback.
  if (!status.local_first_active) return "本地快照讀取可用；自動刷新未啟用";
  const envNote = status.env_override ? " · env 強制" : "";
  return status.exists
    ? `啟用中（本地${envNote}）`
    : `啟用中（本地${envNote}）· 待 ingestion 建立`;
}

export function newsRoutingLabel(status: NewsStatus): string {
  if (status.news_hard_local) return newsWriteRouteLabel(status);
  if (status.env_override) {
    return status.direct_active
      ? "直寫本地（env 強制開啟）"
      : "回退 PG 鏡像（env 強制關閉）";
  }
  if (!status.direct_active) return "回退至 PG 同步／本地鏡像";
  return status.setting_explicit ? "直寫本地（已設定）" : "直寫本地（預設）";
}

export function newsWriteRouteLabel(status: NewsStatus): string {
  if (status.news_hard_local) return "Normalized SQLite + legacy local projection";
  switch (status.write_route) {
    case "normalized":
      return "Normalized SQLite + legacy local projection（pre-exit test）";
    case "legacy_local":
      return "Legacy local direct writer";
    case "legacy_pg":
      return "Legacy PG sync + local mirror";
    case "blocked":
      return "Blocked";
    default:
      return status.write_route;
  }
}

export function newsPostgresRouteLabel(status: NewsStatus): string {
  if (status.news_hard_local) return "已退出（不可回退到 PG）";
  return status.pg_news_route_available ? "可用（尚未退出）" : "不可用";
}

export function newsReadSurfaceLabel(status: NewsStatus): string {
  if (status.news_hard_local) return "Legacy local compatibility surface (N8b pending)";
  return status.direct_active ? "Legacy local direct surface" : "Legacy PG mirror surface";
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

function backlogCount(value: unknown): number | null {
  if (value === undefined) return 0;
  if (typeof value !== "number" || !Number.isInteger(value) || value < 0) return null;
  return value;
}

export interface SchedulerBodyBacklogPresentation {
  label: string;
  tone: "muted" | "warn";
  earliestNextRetryAt: string | null;
}

const unavailableBodyBacklog = (): SchedulerBodyBacklogPresentation => ({
  label: "內文待處理狀態暫時無法讀取",
  tone: "warn",
  earliestNextRetryAt: null,
});

export function schedulerBodyBacklogPresentation(
  durable: SchedulerDurablePresentation | null,
): SchedulerBodyBacklogPresentation | null {
  const backlog = durable?.last_result?.collect?.body_backlog;
  if (!backlog) return null;
  if (backlog.status !== "ok") return unavailableBodyBacklog();

  const due = backlogCount(backlog.due_now);
  const scheduled = backlogCount(backlog.scheduled_later);
  const neverAttempted = backlogCount(backlog.never_attempted);
  const providerNotEntitled = backlogCount(backlog.provider_not_entitled);
  if (
    due === null
    || scheduled === null
    || neverAttempted === null
    || providerNotEntitled === null
    || neverAttempted > due
  ) {
    return unavailableBodyBacklog();
  }
  if (due === 0 && scheduled === 0 && providerNotEntitled === 0) return null;

  const parts: string[] = [];
  if (due > 0) {
    parts.push(
      neverAttempted > 0
        ? `${due} 篇目前可處理（其中 ${neverAttempted} 篇尚未嘗試）`
        : `${due} 篇目前可處理`,
    );
  }
  if (scheduled > 0) parts.push(`${scheduled} 篇已排程稍後重試`);
  if (providerNotEntitled > 0) {
    parts.push(
      `${providerNotEntitled} 篇來源目前未訂閱（標題已保留，開通後自動重試）`,
    );
  }

  return {
    label: `內文佇列：${parts.join(" · ")}`,
    tone: "muted",
    earliestNextRetryAt: typeof backlog.earliest_next_retry_at === "string"
      ? backlog.earliest_next_retry_at
      : null,
  };
}

export function schedulerStateLabel(
  durable: SchedulerDurablePresentation | null,
): { label: string; tone: "ok" | "warn" | "muted" | "bad"; needsContinue: boolean } {
  const st = durable?.last_status ?? null;
  switch (st) {
    case "succeeded":
      return { label: "上次成功", tone: "ok", needsContinue: false };
    case "partial": {
      const actionable = durable?.continuation?.deferred?.length ?? 0;
      if (actionable > 0) {
        return {
          label: `部分完成（待補抓 ${actionable}）`,
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
          label: `部分完成（${tickers} 個標的、${bodies} 篇內文待後續處理）`,
          tone: "warn",
          needsContinue: false,
        };
      }
      if (bodies > 0) {
        return {
          label: `部分完成（${bodies} 篇內文待後續處理）`,
          tone: "warn",
          needsContinue: false,
        };
      }
      if (tickers > 0) {
        return {
          label: `部分完成（${tickers} 個標的待後續處理）`,
          tone: "warn",
          needsContinue: false,
        };
      }
      if (observed?.has_cursor === true) {
        return {
          label: "部分完成（尚有資料待後續處理）",
          tone: "warn",
          needsContinue: false,
        };
      }
      return { label: "部分完成", tone: "warn", needsContinue: false };
    }
    case "failed":
      return { label: "上次失敗", tone: "bad", needsContinue: false };
    case "skipped":
      return { label: "上次已跳過", tone: "muted", needsContinue: false };
    case "running":
      if (durable?.running_stale) {
        return { label: "執行過久", tone: "warn", needsContinue: false };
      }
      return { label: "執行中", tone: "muted", needsContinue: false };
    default:
      return { label: "尚未執行", tone: "muted", needsContinue: false };
  }
}
