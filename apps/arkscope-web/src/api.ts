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

export interface RuntimeConfig {
  anthropic: {
    model: string;
    model_advanced: string;
    effort: string | null;
    thinking: boolean;
    key_set: boolean;
    credentials: ProviderCredential[];
  };
  openai: {
    model: string;
    model_advanced: string;
    reasoning_effort: string;
    key_set: boolean;
    credentials: ProviderCredential[];
  };
  card_synthesis: TaskRoute;
  card_translation: TaskRoute;
  data_keys: Record<string, boolean>;
}

export type ModelProvider = "anthropic" | "openai";
export type ModelTask = "card_synthesis" | "card_translation";

export interface TaskRoute {
  task: ModelTask;
  provider: ModelProvider;
  model: string;
  effort: string;
  source: "env" | "profile" | "default";
  custom: boolean;
  warning: string | null;
}

export interface EffortOption {
  id: string;
  provider: ModelProvider;
  label: string;
  description: string;
  applies_to_card_tasks: boolean;
}

export interface ModelOption {
  id: string;
  provider: ModelProvider;
  label: string;
  quality: "frontier" | "high" | "balanced" | "fast";
  speed: "slow" | "medium" | "fast";
  cost_tier: "high" | "medium" | "low";
  supports_structured_output: boolean;
  supports_tool_calling: boolean;
  recommended_for: ModelTask[];
  source_url: string;
  verified_at: string;
  notes: string;
}

export interface TaskInfo {
  id: ModelTask;
  label: string;
  description: string;
  default_provider: ModelProvider;
  recommended_model: string;
}

export interface ModelCatalog {
  providers: ModelProvider[];
  tasks: TaskInfo[];
  models: ModelOption[];
  effort_options: Record<ModelProvider, EffortOption[]>;
  routes: Record<ModelTask, TaskRoute>;
  credentials: Record<ModelProvider, ProviderCredential[]>;
  custom_allowed: boolean;
}

export interface ProviderCredential {
  id: string;
  provider: ModelProvider;
  auth_type: "api_key" | "api_key_pool" | "oauth" | "setup_token";
  label: string;
  source: string;
  available: boolean;
  masked: string | null;
  active: boolean;
  editable: boolean;
  can_discover_models: boolean;
  can_test_models: boolean;
  notes: string;
}

export interface DiscoveredModel {
  id: string;
  provider: ModelProvider;
  label: string;
  source: "provider_api" | "seed";
}

export interface ModelDiscoveryResult {
  provider: ModelProvider;
  credential_id: string | null;
  status: "ok" | "missing_credential" | "unsupported" | "error";
  models: DiscoveredModel[];
  error: string | null;
  source_url: string | null;
}

export interface ModelTestResult {
  provider: ModelProvider;
  credential_id: string | null;
  model: string;
  effort: string;
  status: "ok" | "missing_credential" | "error";
  latency_ms: number | null;
  error: string | null;
  warning: string | null;
  fallback_effort: string | null;
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

// Classification tag, two-dimensional + decoupled from list membership.
//   facet  = semantic axis: category | theme | provenance | sector | industry
//   source = authority/origin: user | legacy | system | provider:* | sec | broker
// Editable = {user, legacy}; the rest are read-only external facts.
export interface TagRef {
  facet: string;
  value: string;
  source: string;
}

const EDITABLE_TAG_SOURCES = new Set(["user", "legacy"]);
export function isEditableTag(t: TagRef): boolean {
  return EDITABLE_TAG_SOURCES.has(t.source);
}

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
  tags: TagRef[];
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
  priority: string | null;
  tags?: TagRef[];
}

// --- universe (full tracked inventory) ---

export interface UniverseRow {
  ticker: string;
  has_summary: boolean;
  group: string | null;
  priority: string | null;
  latest_close: number | null;
  change_7d_pct: number | null;
  news_count_7d: number;
  sentiment_mean: number | null;
  bullish_ratio: number | null;
  lists: string[];          // active list memberships
  all_lists: string[];      // active + archived (full provenance)
  archived_lists: string[]; // memberships that are archived
  archived: boolean;
  tags: TagRef[];
  note_count: number;
}

export interface WatchlistSummary {
  id: number;
  name: string;
  kind: string; // custom | imported_profile | holdings | interested | theme | tier
  position: number;
  archived: boolean;
  active_count: number;
  total_count: number;
}

export interface UniverseResponse {
  as_of: string | null;
  generated_at: string;
  total: number;
  shown: number;
  archived_count: number;
  summarized: number;
  rows: UniverseRow[];
}

export interface ImportResult {
  lists_removed: number;
  tags: { tags_added: number };
  priority_migrated: number;
  lists: { id: number; name: string; kind: string; total_count: number; active_count: number }[];
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
export interface EvidenceItem {
  evidence_id: string;
  source: string;
  source_type: string;
  as_of: string | null;
  is_real_time: boolean;
  freshness: string | null;
  derived_from: string[];
  data: Record<string, unknown>;
  note: string | null;
}
export interface EvidencePacket {
  ticker: string;
  generated_at: string;
  question: string | null;
  horizon: string | null;
  items: EvidenceItem[];
  excluded_note: string;
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
  effort?: string | null;
  fallback_effort?: string | null;
  warning?: string | null;
  generated_at: string;
  card: ResultCard;
  evidence_packet: EvidencePacket | null;
}
export interface CardDetail extends GenerateResult {
  ticker: string;
  question: string | null;
  horizon: string | null;
  card_type: string;
  as_of: string | null;
  saved_report_id: number | null;
  evidence_packet: EvidencePacket | null;
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
  method: "POST" | "PUT" | "PATCH" | "DELETE",
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

export function getRuntimeConfig(): Promise<RuntimeConfig> {
  return getJSON<RuntimeConfig>("/config/runtime", 8_000);
}

export function getModelCatalog(): Promise<ModelCatalog> {
  return getJSON<ModelCatalog>("/config/model-catalog", 8_000);
}

export function saveModelRoutes(
  routes: Partial<Record<ModelTask, { provider: ModelProvider; model: string; effort: string }>>,
): Promise<{ routes: Partial<Record<ModelTask, TaskRoute>> }> {
  return sendJSON<{ routes: Partial<Record<ModelTask, TaskRoute>> }>(
    "/config/model-routes",
    "PUT",
    { routes },
    8_000,
  );
}

export function listCredentials(): Promise<{ credentials: Record<ModelProvider, ProviderCredential[]> }> {
  return getJSON<{ credentials: Record<ModelProvider, ProviderCredential[]> }>("/config/credentials", 8_000);
}

export function addCredential(body: {
  provider: ModelProvider;
  auth_type: "api_key" | "oauth" | "setup_token";
  alias: string;
  secret: string;
  make_active: boolean;
}): Promise<{ credential: ProviderCredential }> {
  return sendJSON<{ credential: ProviderCredential }>("/config/credentials", "POST", body, 8_000);
}

export function updateCredential(
  credentialId: string,
  body: { alias?: string; secret?: string; active?: boolean },
): Promise<{ credential: ProviderCredential }> {
  return sendJSON<{ credential: ProviderCredential }>(
    `/config/credentials/${encodeURIComponent(credentialId)}`,
    "PUT",
    body,
    8_000,
  );
}

export function deleteCredential(credentialId: string): Promise<{ deleted: boolean; id: string }> {
  return sendJSON<{ deleted: boolean; id: string }>(
    `/config/credentials/${encodeURIComponent(credentialId)}`,
    "DELETE",
    undefined,
    8_000,
  );
}

export function discoverModels(
  provider: ModelProvider,
  credentialId?: string | null,
): Promise<ModelDiscoveryResult> {
  return sendJSON<ModelDiscoveryResult>(
    "/config/model-discovery",
    "POST",
    { provider, credential_id: credentialId ?? null },
    25_000,
  );
}

export function testModelAccess(
  provider: ModelProvider,
  model: string,
  effort: string,
  credentialId?: string | null,
): Promise<ModelTestResult> {
  return sendJSON<ModelTestResult>(
    "/config/model-test",
    "POST",
    { provider, model, effort, credential_id: credentialId ?? null },
    45_000,
  );
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

export function getUniverse(includeArchived = true): Promise<UniverseResponse> {
  return getJSON<UniverseResponse>(`/profile/universe?include_archived=${includeArchived}`);
}

export function getProfileLists(includeArchived = false): Promise<{ lists: WatchlistSummary[] }> {
  return getJSON<{ lists: WatchlistSummary[] }>(`/profile/lists?include_archived=${includeArchived}`);
}

// --- list CRUD + membership ---

export function createList(name: string, kind?: string): Promise<WatchlistSummary> {
  return sendJSON<WatchlistSummary>("/profile/lists", "POST", { name, kind });
}
export function renameList(listId: number, name: string): Promise<WatchlistSummary> {
  return sendJSON<WatchlistSummary>(`/profile/lists/${listId}`, "PATCH", { name });
}
export function deleteList(listId: number): Promise<{ deleted: boolean; id: number }> {
  return sendJSON(`/profile/lists/${listId}`, "DELETE");
}
export function addMember(listId: number, ticker: string): Promise<TickerAggregate> {
  return sendJSON<TickerAggregate>(`/profile/lists/${listId}/members`, "POST", { ticker });
}
export function removeMember(
  listId: number,
  ticker: string,
): Promise<{ removed: boolean; list_id: number; ticker: string }> {
  return sendJSON(`/profile/lists/${listId}/members/${encodeURIComponent(ticker)}`, "DELETE");
}

export function setPriority(
  ticker: string,
  priority: "high" | "medium" | "low" | null,
): Promise<{ ticker: string; priority: string | null }> {
  return sendJSON(`/profile/tickers/${encodeURIComponent(ticker)}/priority`, "POST", { priority });
}

// --- analyst consensus (credible, provider-native rating; daily-cached) ---

export interface ConsensusSummary {
  ticker?: string;
  rating: string | null; // Strong Buy | Buy | Hold | Sell | Strong Sell | null
  score: number | null;
  buy_ratio: number | null;
  total: number;
  counts: Record<string, number>;
  price_target: unknown;
  period: string | null;
  source: string;
  cached?: boolean;
  fetched_at?: string;
  // ok | cached | no_coverage | rate_limited | missing_key | provider_error
  status?: string;
  message?: string;
}
export function getConsensus(ticker: string): Promise<ConsensusSummary> {
  // First hit may fetch Finnhub (throttled); cached daily server-side.
  return getJSON<ConsensusSummary>(`/analysis/consensus/${encodeURIComponent(ticker)}`, 20_000);
}

// --- symbol search (local-first autocomplete; NOT fuzzy) ---

export interface SymbolHit {
  ticker: string;
  name: string;
  tracked: boolean;
}
export function searchSymbols(q: string, limit = 10): Promise<{ q: string; results: SymbolHit[] }> {
  return getJSON(`/symbols/search?q=${encodeURIComponent(q)}&limit=${limit}`, 20_000);
}

// Seeds lists from user_profile groups + tickers_core tiers. The groups source
// runs the overview (per-ticker price), so allow a generous timeout.
export function importUniverse(
  body: { include_groups?: boolean; include_tiers?: boolean; migrate_tier_priority?: boolean } = {},
): Promise<ImportResult> {
  return sendJSON<ImportResult>("/profile/import-universe", "POST", body, 60_000);
}

export function setArchived(ticker: string, archived: boolean): Promise<TickerAggregate> {
  return sendJSON<TickerAggregate>(
    `/profile/tickers/${encodeURIComponent(ticker)}/archive`,
    "POST",
    { archived },
  );
}

export function getTickerState(ticker: string): Promise<TickerAggregate> {
  return getJSON<TickerAggregate>(`/profile/tickers/${encodeURIComponent(ticker)}/state`);
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

// Adds a USER tag (source='user') on a facet (default theme). legacy/provider/
// system tags are seeded/owned elsewhere. Returns the refreshed ticker state.
export function addTickerTag(
  ticker: string,
  value: string,
  facet = "theme",
): Promise<TickerAggregate> {
  return sendJSON<TickerAggregate>(
    `/profile/tickers/${encodeURIComponent(ticker)}/tags`,
    "POST",
    { value, facet },
  );
}

// Removes an EDITABLE tag (user|legacy). value/facet/source are query params so a
// value containing '/' is safe. Read-only sources are rejected server-side (400).
export function removeTickerTag(
  ticker: string,
  value: string,
  facet = "theme",
  source = "user",
): Promise<{ removed: boolean; ticker: string; facet: string; value: string; source: string }> {
  const q = new URLSearchParams({ value, facet, source });
  return sendJSON(
    `/profile/tickers/${encodeURIComponent(ticker)}/tags?${q.toString()}`,
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
  body: {
    question?: string;
    horizon?: string;
    provider?: string;
    include_sa?: boolean;
    news_days?: number;
    max_news?: number;
  } = {},
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

// On-demand translation (cached server-side per language). Smaller than a
// generation but still an LLM call, so allow a generous timeout.
export function translateCard(
  runId: number,
  lang = "zh-Hant",
): Promise<{ run_id: number; lang: string; card: ResultCard; cached: boolean }> {
  return sendJSON(`/analysis/cards/${runId}/translate`, "POST", { lang }, 120_000);
}
