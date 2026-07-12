import type { CoverageStatus, MacroStatus, MarketDataStatus, NewsStatus, TradingDayRow } from "./api";

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

// Scheduler durable-state → UI label + tone (v1.4). Distinguishes the cases the reviewer
// stressed: partial = a budget-bounded run left work → needs manual 補抓; skipped can be
// transient or a durable writer-lock outcome and remains neutral; failed carries the error.
export function schedulerStateLabel(
  durable: {
    last_status: string | null;
    continuation: { deferred?: string[] } | null;
    running_stale?: boolean;
    running_stale_reason?: string | null;
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
