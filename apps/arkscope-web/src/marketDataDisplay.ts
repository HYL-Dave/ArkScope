import type { MarketDataStatus } from "./api";

export function marketRoutingLabel(status: MarketDataStatus): string {
  if (status.routing_enabled) {
    return status.pg_fallback_active ? "啟用中（PG fallback）" : "啟用中（local-only strict）";
  }
  if (status.use_local_market_setting) return "設定已開，待建立資料庫";
  return "關閉（使用 PG）";
}
