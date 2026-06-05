// Thin client for the local ArkScope sidecar.
//
// Connection params come from the Electron preload bridge (window.arkscope) when
// running in the desktop shell, or fall back to a dev default when running the
// Vite dev server in a plain browser.

export interface ApiStatus {
  status: string;
  timestamp: string;
  tools_registered: number;
  tool_categories: Record<string, number>;
  data_sources: Record<string, number>;
}

export interface WatchlistRow {
  ticker: string;
  group: string;
  priority: string;
  latest_close: number | null;
  change_7d_pct: number | null;
  news_count_7d: number;
  sentiment_mean: number | null;
  bullish_ratio: number;
}

export interface WatchlistOverview {
  date: string;
  ticker_count: number;
  tickers: WatchlistRow[];
}

export interface PriceChange {
  ticker: string;
  days: number;
  bar_count: number;
  latest_close: number | null;
  period_open: number | null;
  change_pct: number | null;
  period_high: number | null;
  period_low: number | null;
  high_low_range_pct: number | null;
  total_volume: number | null;
  date_range: string;
}

interface ArkscopeBridge {
  apiBase: string;
  apiToken?: string;
}

declare global {
  interface Window {
    arkscope?: ArkscopeBridge;
  }
}

export const apiBase: string =
  window.arkscope?.apiBase ??
  (import.meta.env.VITE_API_BASE as string | undefined) ??
  "http://127.0.0.1:8420";

const apiToken: string | undefined = window.arkscope?.apiToken;
const DEFAULT_TIMEOUT_MS = 15_000;

function authHeaders(): Record<string, string> {
  return apiToken ? { "x-arkscope-token": apiToken } : {};
}

async function fetchWithTimeout(path: string, timeoutMs: number): Promise<Response> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(`${apiBase}${path}`, {
      headers: authHeaders(),
      signal: controller.signal,
    });
  } catch (e) {
    if (e instanceof Error && e.name === "AbortError") {
      throw new Error(`${path} timed out after ${Math.round(timeoutMs / 1000)}s`);
    }
    throw e;
  } finally {
    window.clearTimeout(timer);
  }
}

async function getJSON<T>(path: string, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<T> {
  const r = await fetchWithTimeout(path, timeoutMs);
  if (!r.ok) throw new Error(`${path} returned ${r.status}`);
  return (await r.json()) as T;
}

export async function getHealthz(): Promise<boolean> {
  try {
    const r = await fetchWithTimeout("/healthz", 3_000);
    return r.ok;
  } catch {
    return false;
  }
}

export function getStatus(): Promise<ApiStatus> {
  return getJSON<ApiStatus>("/status", 8_000);
}

export function getOverview(): Promise<WatchlistOverview> {
  return getJSON<WatchlistOverview>("/overview");
}

export function getPriceChange(ticker: string, days = 7): Promise<PriceChange> {
  return getJSON<PriceChange>(`/prices/${encodeURIComponent(ticker)}/change?days=${days}`);
}
