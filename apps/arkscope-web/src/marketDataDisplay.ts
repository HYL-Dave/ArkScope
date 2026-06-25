import type { MacroStatus, MarketDataStatus } from "./api";

export function marketRoutingLabel(status: MarketDataStatus): string {
  if (status.routing_enabled) {
    return status.pg_fallback_active ? "啟用中（PG fallback）" : "啟用中（local-only strict）";
  }
  if (status.use_local_market_setting) return "設定已開，待建立資料庫";
  return "關閉（使用 PG）";
}

export function macroRoutingLabel(status: MacroStatus): string {
  // local_first_active = (toggle OR env) AND the local DB exists. The toggle/env can be on
  // before the DB is populated → "待建立" (settable, but reads still go to PG until it exists).
  if (status.local_first_active) {
    return status.env_override ? "啟用中（本地優先 · env 強制）" : "啟用中（本地優先）";
  }
  if (status.use_local_macro_setting || status.env_override) return "設定已開，待建立資料庫";
  return "關閉（使用 PG）";
}
