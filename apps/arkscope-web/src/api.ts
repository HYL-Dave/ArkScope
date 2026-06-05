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

export interface DataSourceRef {
  name: string;
  as_of: string | null;
  is_real_time: boolean;
  detail: string | null;
}
export interface ClaimCitation {
  claim: string;
  evidence_ids: string[];
}
export interface Completeness {
  news: boolean;
  fundamentals: boolean;
  technicals: boolean;
  note: string | null;
}
export interface Traceability {
  data_sources: DataSourceRef[];
  is_single_model_inference: boolean;
  completeness: Completeness;
  claims: ClaimCitation[];
}
export interface ResultCard {
  ticker: string;
  question: string | null;
  horizon: string | null;
  card_type: string;
  analysis_time: string;
  conclusion: string;
  primary_reasons: string[];
  counter_thesis: string[];
  key_assumptions: string[];
  trigger_conditions: string[];
  invalidation_conditions: string[];
  risks: string[];
  watch_list: string[];
  market_narrative: string | null;
  divergence: string | null;
  confidence_level: "high" | "medium" | "low";
  confidence_rationale: string | null;
  traceability: Traceability;
}
export interface GenerateResult {
  run_id: number;
  status: string;
  provider: string | null;
  model: string | null;
  generated_at: string;
  card: ResultCard;
}
export interface CardDetail extends GenerateResult {
  ticker: string;
  question: string | null;
  horizon: string | null;
  card_type: string;
  as_of: string | null;
  saved_report_id: number | null;
  evidence_packet: unknown;
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

// Generation runs the gather + LLM synthesis server-side (~1-2 min for one
// card), so it needs a generous timeout — well past the 15s default.
const CARD_GEN_TIMEOUT_MS = 240_000;

export function generateCard(
  ticker: string,
  body: { question?: string; horizon?: string; provider?: string; include_sa?: boolean } = {},
): Promise<GenerateResult> {
  return sendJSON<GenerateResult>(
    `/analysis/card/${encodeURIComponent(ticker)}`,
    "POST",
    body,
    CARD_GEN_TIMEOUT_MS,
  );
}

export function getCard(runId: number): Promise<CardDetail> {
  return getJSON<CardDetail>(`/analysis/cards/${runId}`);
}

export function saveCard(
  runId: number,
): Promise<{ run_id: number; status: string; saved_report_id: number | null }> {
  return sendJSON(`/analysis/cards/${runId}/save`, "POST");
}
