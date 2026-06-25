import type { MacroStatus, MarketDataStatus } from "./api";

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
