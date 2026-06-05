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

// --- cockpit watchlist + profile-state (lifecycle) ---

export interface CockpitRow {
  ticker: string;
  group: string | null;
  priority: string;
  latest_close: number | null;
  change_7d_pct: number | null;
  news_count_7d: number;
  sentiment_mean: number | null;
  bullish_ratio: number | null;
  lists: string[];
  archived: boolean;
  tags: string[];
  note_count: number;
  freshness: string | null;
  per_ticker_error: string | null;
}

export interface CockpitWatchlist {
  as_of: string | null;
  generated_at: string;
  total: number;
  shown: number;
  archived_count: number;
  include_archived: boolean;
  rows: CockpitRow[];
}

export interface TickerAggregate {
  ticker: string;
  lists: string[];
  list_ids: number[];
  archived: boolean;
  note_count: number;
}

export interface Note {
  id: number;
  ticker: string;
  body: string;
  created_at: string;
  updated_at: string;
}

// --- §2 AI cards (recent runs) ---

export interface CardSummary {
  run_id: number;
  ticker: string;
  question: string | null;
  horizon: string | null;
  card_type: string;
  status: string;
  provider: string | null;
  model: string | null;
  generated_at: string;
  saved_report_id: number | null;
  conclusion: string | null;
  confidence_level: "high" | "medium" | "low" | null;
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

async function fetchWithTimeout(
  path: string,
  timeoutMs: number,
  init?: RequestInit,
): Promise<Response> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(`${apiBase}${path}`, {
      ...init,
      headers: { ...authHeaders(), ...((init?.headers as Record<string, string>) ?? {}) },
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

async function sendJSON<T>(
  path: string,
  method: "POST" | "PUT" | "DELETE",
  body?: unknown,
  timeoutMs = DEFAULT_TIMEOUT_MS,
): Promise<T> {
  const r = await fetchWithTimeout(path, timeoutMs, {
    method,
    headers: body === undefined ? {} : { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${path} returned ${r.status}`);
  if (r.status === 204) return undefined as T;
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

export function getCockpitWatchlist(includeArchived = false): Promise<CockpitWatchlist> {
  return getJSON<CockpitWatchlist>(`/cockpit/watchlist?include_archived=${includeArchived}`);
}

export function setArchived(ticker: string, archived: boolean): Promise<TickerAggregate> {
  return sendJSON<TickerAggregate>(
    `/profile/tickers/${encodeURIComponent(ticker)}/archive`,
    "POST",
    { archived },
  );
}

export function getNotes(ticker: string): Promise<{ ticker: string; notes: Note[] }> {
  return getJSON<{ ticker: string; notes: Note[] }>(
    `/profile/tickers/${encodeURIComponent(ticker)}/notes`,
  );
}

export function addNote(ticker: string, body: string): Promise<Note> {
  return sendJSON<Note>(`/profile/tickers/${encodeURIComponent(ticker)}/notes`, "POST", { body });
}

export function deleteNote(ticker: string, noteId: number): Promise<{ deleted: boolean; id: number }> {
  return sendJSON<{ deleted: boolean; id: number }>(
    `/profile/tickers/${encodeURIComponent(ticker)}/notes/${noteId}`,
    "DELETE",
  );
}

export function getCards(
  ticker?: string,
  limit = 20,
  includeArchived = false,
): Promise<{ cards: CardSummary[] }> {
  const params = new URLSearchParams({ limit: String(limit), include_archived: String(includeArchived) });
  if (ticker) params.set("ticker", ticker);
  return getJSON<{ cards: CardSummary[] }>(`/analysis/cards?${params.toString()}`);
}
