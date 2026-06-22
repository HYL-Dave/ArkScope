// Thin client for the local ArkScope sidecar.
//
// Connection params come from the Electron preload bridge (window.arkscope) when
// running in the desktop shell, or fall back to a dev default when running the
// Vite dev server in a plain browser.

import { SSEFrameParser, type SSEFrame } from "./sse";

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
  ai_research: TaskRoute;
  research_runtime: ResearchRuntimeSettings;
  data_keys: Record<string, boolean>;
}

export interface ResearchRuntimeSettings {
  max_tool_calls: number;
  session_timeout_s: number;
  per_tool_timeout_s: number;
  source: "env" | "db" | "profile" | "default";
  db_saved: boolean;
  warning: string | null;
}

export type ModelProvider = "anthropic" | "openai";
export type ModelTask = "card_synthesis" | "card_translation" | "ai_research";

export interface TaskRoute {
  task: ModelTask;
  provider: ModelProvider;
  model: string;
  effort: string;
  source: "env" | "db" | "profile" | "default";
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

// Explicit auth modes (backend normalizes legacy oauth/setup_token → these; it
// never returns the legacy values). Matches src/model_credentials.CredentialAuthType.
export type CredentialAuthType = "api_key" | "api_key_pool" | "chatgpt_oauth" | "claude_code_oauth";

export interface ProviderCredential {
  id: string;
  provider: ModelProvider;
  auth_type: CredentialAuthType;
  label: string;
  account_label: string | null;
  expires_at: string | null;
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
  groups_ok: boolean; // false → theme-group import skipped (DAL/overview unreachable)
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

/**
 * Stream an agent query over POST /query/stream as SSE frames (C-2).
 *
 * Deliberately does NOT use fetchWithTimeout — a turn runs 1–4 min and that
 * helper's 15s AbortController would kill the stream. The caller owns aborting
 * via `signal` (unmount / explicit Stop). Frame parsing lives in the
 * unit-tested SSEFrameParser; this drives fetch + the ReadableStream reader and
 * flushes the UTF-8 decoder for multibyte chars split across network chunks.
 * Throws on a non-ok / bodyless response so the caller can surface an error.
 */
export async function* streamQuery(
  body: {
    question: string;
    provider: string;
    model?: string;
    effort?: string;
    thread_id?: string;
    ticker?: string | null;
    retry_last_failed?: boolean;
  },
  signal?: AbortSignal,
): AsyncGenerator<SSEFrame> {
  const res = await fetch(`${apiBase}/query/stream`, {
    method: "POST",
    headers: { ...authHeaders(), "content-type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) {
    throw new Error(`query stream failed: HTTP ${res.status}`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  const parser = new SSEFrameParser();
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      for (const frame of parser.push(decoder.decode(value, { stream: true }))) {
        yield frame;
      }
    }
    const tail = decoder.decode(); // flush any trailing multibyte bytes
    if (tail) for (const frame of parser.push(tail)) yield frame;
    for (const frame of parser.flush()) yield frame;
  } finally {
    reader.releaseLock();
  }
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

async function responseErrorMessage(path: string, r: Response): Promise<string> {
  let detail = "";
  try {
    const body = (await r.json()) as { detail?: unknown };
    if (typeof body.detail === "string" && body.detail.trim()) {
      detail = `: ${body.detail.trim()}`;
    }
  } catch {
    // Some routes/proxies return non-JSON bodies; the status is still useful.
  }
  return `${path} returned ${r.status}${detail}`;
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
  if (!r.ok) throw new Error(await responseErrorMessage(path, r));
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

// Agent SDK availability per provider (NOT key presence — that's runtime.key_set).
// Used by the AI Research surface to gate the provider chooser.
export interface QueryProviders {
  providers: Record<string, { available: boolean; sdk_version?: string; install?: string }>;
}
export function getQueryProviders(): Promise<QueryProviders> {
  return getJSON<QueryProviders>("/query/providers", 8_000);
}

// AI 研究 persisted threads/messages (C-2b) — for reload hydration.
export interface ResearchThreadDTO {
  id: string; title: string; ticker: string | null;
  provider: string | null; model: string | null;
  created_at: string; updated_at: string;
  active_run?: ResearchRunDTO | null;
}
export interface ResearchMessageDTO {
  role: "user" | "assistant"; content: string;
  provider: string | null; model: string | null; effort: string | null;
  tools_used: string[]; tool_calls: Array<{ name: string; input?: unknown; result_preview?: string }>;
  token_usage: Record<string, number> | null; tickers: string[] | null;
  elapsed_seconds: number | null; is_error: boolean; created_at: string;
}
export interface ResearchRunDTO {
  id: string;
  thread_id: string;
  status: "queued" | "running" | "succeeded" | "failed" | "cancelled" | "interrupted";
  question: string;
  ticker: string | null;
  provider: string;
  model: string;
  effort: string | null;
  auth_mode: string | null;
  credential_id: string | null;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
  token_usage: Record<string, number> | null;
  created_at: string;
  updated_at: string;
}
export interface ResearchRunEventDTO {
  run_id: string;
  seq: number;
  type: string;
  data: Record<string, unknown>;
  created_at: string;
}
export function getResearchThreads(limit = 50): Promise<{ threads: ResearchThreadDTO[] }> {
  return getJSON<{ threads: ResearchThreadDTO[] }>(`/research/threads?limit=${limit}`, 8_000);
}
export function getResearchMessages(threadId: string): Promise<{ thread_id: string; messages: ResearchMessageDTO[] }> {
  return getJSON<{ thread_id: string; messages: ResearchMessageDTO[] }>(`/research/threads/${encodeURIComponent(threadId)}/messages`, 8_000);
}
export function deleteResearchThread(threadId: string): Promise<{ thread_id: string; deleted: boolean }> {
  return sendJSON<{ thread_id: string; deleted: boolean }>(`/research/threads/${encodeURIComponent(threadId)}`, "DELETE", undefined, 8_000);
}
export function createResearchRun(body: {
  thread_id?: string;
  question: string;
  ticker?: string | null;
  provider: string;
  model?: string;
  effort?: string;
  retry_last_failed?: boolean;
}): Promise<{ run: ResearchRunDTO }> {
  return sendJSON<{ run: ResearchRunDTO }>("/research/runs", "POST", body, 8_000);
}
export function getResearchRunEvents(runId: string, after = 0): Promise<{ run: ResearchRunDTO; events: ResearchRunEventDTO[]; has_more: boolean }> {
  return getJSON<{ run: ResearchRunDTO; events: ResearchRunEventDTO[]; has_more: boolean }>(
    `/research/runs/${encodeURIComponent(runId)}/events?after=${after}`,
    8_000,
  );
}
export function cancelResearchRun(runId: string): Promise<{ run: ResearchRunDTO }> {
  return sendJSON<{ run: ResearchRunDTO }>(`/research/runs/${encodeURIComponent(runId)}/cancel`, "POST", undefined, 8_000);
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

// Reset one task's route to yaml/default authority (removes its DB row). Returns the
// now-resolved route so the UI can show what it reverted to.
export function deleteModelRoute(
  task: ModelTask,
): Promise<{ deleted: boolean; route: TaskRoute }> {
  return sendJSON<{ deleted: boolean; route: TaskRoute }>(
    `/config/model-routes/${task}`,
    "DELETE",
    undefined,
    8_000,
  );
}

// Promote the yaml (user_profile.local.yaml) routes into the DB authority. Explicit; never auto-runs.
export function importModelRoutes(): Promise<{ imported: ModelTask[]; skipped: ModelTask[] }> {
  return sendJSON<{ imported: ModelTask[]; skipped: ModelTask[] }>(
    "/config/model-routes/import",
    "POST",
    undefined,
    8_000,
  );
}

// Snapshot the DB routes back into the yaml fallback (mirrors DB state: writes present, clears absent).
export function exportModelRoutes(): Promise<{ exported: ModelTask[]; cleared: ModelTask[] }> {
  return sendJSON<{ exported: ModelTask[]; cleared: ModelTask[] }>(
    "/config/model-routes/export",
    "POST",
    undefined,
    8_000,
  );
}

export function saveResearchRuntime(
  body: Pick<ResearchRuntimeSettings, "max_tool_calls" | "session_timeout_s" | "per_tool_timeout_s">,
): Promise<{ research_runtime: ResearchRuntimeSettings }> {
  return sendJSON<{ research_runtime: ResearchRuntimeSettings }>(
    "/config/research-runtime",
    "PUT",
    body,
    8_000,
  );
}

export function deleteResearchRuntime(): Promise<{ deleted: boolean; research_runtime: ResearchRuntimeSettings }> {
  return sendJSON<{ deleted: boolean; research_runtime: ResearchRuntimeSettings }>(
    "/config/research-runtime",
    "DELETE",
    undefined,
    8_000,
  );
}

export function listCredentials(): Promise<{ credentials: Record<ModelProvider, ProviderCredential[]> }> {
  return getJSON<{ credentials: Record<ModelProvider, ProviderCredential[]> }>("/config/credentials", 8_000);
}

// Import a subscription OAuth/setup token. v1: anthropic + claude_code_oauth
// (Claude setup-token). The token goes to the token-store/keyring — NOT the
// credential secret column — so this is a DIFFERENT endpoint from addCredential.
export function importOAuthCredential(body: {
  provider: ModelProvider;
  auth_mode: "claude_code_oauth" | "chatgpt_oauth";
  alias: string;
  token: string;
  account_label?: string;
  expires_at?: string;
  make_active: boolean;
}): Promise<{ credential: ProviderCredential }> {
  return sendJSON<{ credential: ProviderCredential }>("/config/credentials/oauth/import", "POST", body, 8_000);
}

// P3 probe result for a claude_code_oauth credential. Redacted by the backend —
// never contains the token.
export interface ProbeResult {
  name: string;
  passed: boolean;
  expected: string;
  observed: string;
  error: string | null;
}
export interface ProbeResponse {
  passed: boolean;
  probes: ProbeResult[];
}
// The live probe runs `claude -p` (Claude) or the P1/P2 ChatGPT-backend checks
// (OpenAI) — both make real calls and can take a while, so use a generous timeout
// (well above the 15s default). The response is redacted; it never carries a token.
export function probeCredential(credentialId: string): Promise<ProbeResponse> {
  return sendJSON<ProbeResponse>(`/config/credentials/${encodeURIComponent(credentialId)}/probe`, "POST", undefined, 150_000);
}

// --- OpenAI ChatGPT subscription OAuth (in-app login) -------------------------
// COMPATIBILITY / EXPERIMENTAL path: ArkScope runs its own OAuth against the
// ChatGPT/Codex backend (NOT the public OpenAI API; NOT an API key). The token is
// captured by the backend straight into the token-store — it never reaches the UI.
export interface OAuthStartResult {
  auth_url: string;
  state: string;
  expires_at: string;
  manual_code_supported: boolean;
}
export interface OAuthStatusResult {
  status: "pending" | "success" | "error" | "unknown";
  credential: ProviderCredential | null;
  detail: string | null;
}
export function startOpenAIOAuth(makeActive = false): Promise<OAuthStartResult> {
  // make_active default false: ChatGPT OAuth execution is unwired (Research fail-closes
  // when active), so logging in must not auto-switch the active credential.
  return sendJSON<OAuthStartResult>("/config/credentials/openai/oauth/start", "POST", { make_active: makeActive }, 8_000);
}
// Cancel an in-flight login: evicts the pending state server-side so a late browser
// callback can't still create a credential (UI cancel alone only stops the FE poll).
export function cancelOpenAIOAuth(state: string): Promise<{ ok: boolean }> {
  return sendJSON<{ ok: boolean }>("/config/credentials/openai/oauth/cancel", "POST", { state }, 8_000);
}
export function openAIOAuthStatus(state: string): Promise<OAuthStatusResult> {
  return getJSON<OAuthStatusResult>(`/config/credentials/openai/oauth/status?state=${encodeURIComponent(state)}`, 8_000);
}
// Copy-code fallback — ONLY for when the localhost callback never arrived. The
// backend 400s any state/PKCE/exchange error (no fallback); it never masks a failure.
export function completeOpenAIOAuthManual(body: {
  state: string;
  code?: string;
  redirect_url?: string;
}): Promise<{ credential: ProviderCredential }> {
  return sendJSON<{ credential: ProviderCredential }>("/config/credentials/openai/oauth/complete-manual", "POST", body, 8_000);
}

export function addCredential(body: {
  provider: ModelProvider;
  // DIRECT API keys only — the backend rejects OAuth modes here (use
  // importOAuthCredential, which routes the token to the token-store).
  auth_type: "api_key";
  alias: string;
  secret: string;
  make_active: boolean;
}): Promise<{ credential: ProviderCredential }> {
  return sendJSON<{ credential: ProviderCredential }>("/config/credentials", "POST", body, 8_000);
}

export function updateCredential(
  credentialId: string,
  body: { alias?: string; secret?: string; active?: boolean; account_label?: string; expires_at?: string },
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

// --- ticker detail: IV + fundamentals (local-first via DAL routing) ---
// These read through the DAL, so they automatically hit the local market DB when
// routing is enabled and fall back to PG otherwise. Shapes mirror the Python
// IVAnalysisResult / IVHistoryPoint / FundamentalsResult schemas.

// source_path = TRUE per-call origin of the underlying read (local market DB vs PG /
// file). pg_fallback = local-first miss → PG; pg = PG primary (routing off);
// file = file-backed dev config; none = no data anywhere.
export type SourcePath = "local" | "pg_fallback" | "pg" | "file" | "none";

export interface IVAnalysis {
  ticker: string;
  current_iv: number | null;
  hv_30d: number | null;
  vrp: number | null;
  iv_rank: number | null;
  iv_percentile: number | null;
  spot_price: number | null;
  history_days: number;
  signal: string | null; // HIGH_IV_SELL | LOW_IV_BUY | NEUTRAL
  source_path?: SourcePath;
}

export interface IVHistoryPoint {
  date: string;
  atm_iv: number;
  hv_30d: number | null;
  vrp: number | null;
  spot_price: number | null;
  num_quotes: number | null;
}

export interface FinancialStatement {
  report_period: string;
  fiscal_period: string | null;
  period_type: string; // annual | quarterly
  data: Record<string, number | null>;
}

export interface FundamentalsResult {
  ticker: string;
  snapshot_date: string | null;
  data_source: string; // ibkr | sec_edgar | none
  market_cap: number | null;
  pe_ratio: number | null;
  forward_pe: number | null;
  ps_ratio: number | null;
  pb_ratio: number | null;
  roe: number | null;
  roa: number | null;
  debt_to_equity: number | null;
  current_ratio: number | null;
  revenue_growth: number | null;
  earnings_growth: number | null;
  dividend_yield: number | null;
  beta: number | null;
  gross_margin: number | null;
  operating_margin: number | null;
  net_margin: number | null;
  free_cash_flow: number | null;
  cash_and_equivalents: number | null;
  total_debt: number | null;
  income_statements: FinancialStatement[] | null;
  balance_sheet: FinancialStatement[] | null;
  cash_flow_statements: FinancialStatement[] | null;
  snapshot: Record<string, unknown> | null;
  source_path?: SourcePath; // present on the stored-only read (數據 tab)
}

// True local-DB coverage for a ticker (routing-independent fact, NOT per-call
// provenance) — powers the detail page's honest "本地覆蓋：有/無" hint.
export interface MarketDataCoverage {
  exists: boolean;
  prices: boolean;
  news: boolean;
  iv: boolean;
  fundamentals: boolean;
}

export function getIvAnalysis(ticker: string): Promise<IVAnalysis> {
  return getJSON<IVAnalysis>(`/options/${encodeURIComponent(ticker)}`, 20_000);
}

// The history table is a separate request from the IV summary, so it carries its
// OWN source_path (the two can diverge across a bootstrap/toggle boundary).
export interface IVHistoryResult {
  points: IVHistoryPoint[];
  source_path: SourcePath;
}

export function getIvHistory(ticker: string): Promise<IVHistoryResult> {
  return getJSON<IVHistoryResult>(`/options/${encodeURIComponent(ticker)}/history`, 20_000);
}

// STORED-ONLY fundamentals: DAL local-first + PG, with NO external SEC/Financial-
// Datasets fetch (?stored=true) — for the read-only 數據 tab, so opening/refreshing it
// never triggers a provider fetch. The full /fundamentals/{ticker} (provider fallback)
// stays for agents/analysis.
export function getStoredFundamentals(ticker: string): Promise<FundamentalsResult> {
  return getJSON<FundamentalsResult>(`/fundamentals/${encodeURIComponent(ticker)}?stored=true`);
}

export function getMarketDataCoverage(ticker: string): Promise<MarketDataCoverage> {
  return getJSON<MarketDataCoverage>(`/market-data/coverage/${encodeURIComponent(ticker)}`, 8_000);
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
  body: { include_groups?: boolean; include_tiers?: boolean } = {},
): Promise<ImportResult> {
  return sendJSON<ImportResult>("/profile/import-universe", "POST", body, 60_000);
}

// Suppress (or restore) a dead/duplicate ticker from the 全部標的 inventory.
export function setTickerHidden(
  ticker: string,
  hidden: boolean,
): Promise<{ ticker: string; hidden: boolean }> {
  return sendJSON(`/profile/tickers/${encodeURIComponent(ticker)}/hidden`, "POST", { hidden });
}

// Distinct tag values per facet, for the detail-page "pick from existing" classifier.
export function getTagCatalog(): Promise<{ catalog: Record<string, string[]> }> {
  return getJSON<{ catalog: Record<string, string[]> }>("/profile/tags/catalog");
}

// Default 自選股 list — 自選股 opens it instead of always landing on All Active.
export function getDefaultWatchlist(): Promise<{ default_watchlist_id: number | null }> {
  return getJSON<{ default_watchlist_id: number | null }>("/profile/settings/default-watchlist");
}
export function setDefaultWatchlist(
  listId: number | null,
): Promise<{ default_watchlist_id: number | null }> {
  return sendJSON("/profile/settings/default-watchlist", "PUT", { list_id: listId });
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

// --- market-data local-DB lifecycle (3a prices + 3b news + 3c-A iv/fundamentals) ---

export interface SyncMeta {
  last_success: string | null;
  last_error: string | null;
  rows_added: number;
  updated_at: string;
}

// iv/fundamentals are id-keyed snapshot domains → date-only "latest" (no time).
export interface MarketDataStatus {
  market_db: string;
  exists: boolean;
  prices: { row_count: number; ticker_count: number; latest_datetime: string | null };
  news: { row_count: number; source_count: number; latest_published: string | null };
  iv: { row_count: number; ticker_count: number; latest_date: string | null };
  fundamentals: { row_count: number; ticker_count: number; latest_date: string | null };
  // 3c-C local-primary cache (not a PG mirror): valid vs expired by TTL, latest fetch.
  financial_cache: {
    row_count: number;
    valid_count: number;
    expired_count: number;
    latest_fetched_at: string | null;
  };
  sync: {
    prices: SyncMeta | null;
    news: SyncMeta | null;
    iv: SyncMeta | null;
    fundamentals: SyncMeta | null;
  };
  use_local_market_setting: boolean;
  env_override: boolean;
  routing_enabled: boolean;
  pg_fallback_active: boolean;
}

// One job result covers both bootstrap (rows/total/match) and update
// (rows_added/ok) — fields are optional and read per job.kind.
interface DomainResult {
  rows?: number;
  total?: number;
  match?: boolean;
  rows_added?: number;
  ok?: boolean;
  error?: string | null;
}

export interface MarketDataJob {
  id: string;
  kind: string; // "bootstrap_market" | "update_market"
  status: "running" | "done" | "error";
  progress: { written: number; total: number };
  // Per-domain results are null on the incremental missing-DB early return
  // (bootstrap them first); bootstrap + a normal update always populate all four.
  result: {
    match?: boolean;
    ok?: boolean;
    prices: DomainResult | null;
    news: DomainResult | null;
    iv: DomainResult | null;
    fundamentals: DomainResult | null;
    // bootstrap only: rows of the local-primary cache carried over across the rebuild
    financial_cache?: { carried_over: number };
  } | null;
  error: string | null;
}

interface DomainValidate {
  local_rows: number;
  pg_rows: number;
  match: boolean;
}

export interface MarketDataValidate {
  exists: boolean;
  match: boolean;
  prices?: DomainValidate;
  news?: DomainValidate;
  iv?: DomainValidate;
  fundamentals?: DomainValidate;
}

export function getMarketDataStatus(): Promise<MarketDataStatus> {
  return getJSON<MarketDataStatus>("/market-data/status");
}

// Full rebuild of the local market DB (prices + news + iv + fundamentals).
// Returns a job to poll.
export function bootstrapMarketData(): Promise<MarketDataJob> {
  return sendJSON<MarketDataJob>("/market-data/bootstrap", "POST");
}

// Incremental delta refresh (append-only; prices + news + iv + fundamentals).
// Returns a job to poll.
export function updateMarketData(): Promise<MarketDataJob> {
  return sendJSON<MarketDataJob>("/market-data/update", "POST");
}

export function getMarketDataJob(jobId: string): Promise<MarketDataJob> {
  return getJSON<MarketDataJob>(`/market-data/jobs/${encodeURIComponent(jobId)}`);
}

// Validation runs PG aggregates over all domains (prices/news/iv/fundamentals) — allow time.
export function validateMarketData(): Promise<MarketDataValidate> {
  return sendJSON<MarketDataValidate>("/market-data/validate", "POST", undefined, 60_000);
}

export function setUseLocalMarket(enabled: boolean): Promise<{ use_local_market_setting: boolean }> {
  return sendJSON("/market-data/settings", "PUT", { enabled });
}

// --- 新聞·事件 feed (score-free, local-first over news + FTS5) ---

export interface NewsFeedItem {
  published_at: string; // full UTC timestamp
  ticker: string;
  title: string;
  url: string | null;
  publisher: string | null;
  source: string; // polygon | finnhub | ibkr
  description: string | null;
}

export interface NewsFeedResponse {
  available: boolean; // false = no local news table AND PG unavailable
  items: NewsFeedItem[];
  total: number;
  sources: Record<string, number>;
  days: Record<string, number>; // YYYY-MM-DD → count (same filters)
}

export function getNewsFeed(params: {
  q?: string;
  ticker?: string;
  source?: string;
  days?: number;
  limit?: number;
  offset?: number;
}): Promise<NewsFeedResponse> {
  const sp = new URLSearchParams();
  if (params.q) sp.set("q", params.q);
  if (params.ticker) sp.set("ticker", params.ticker);
  if (params.source && params.source !== "auto") sp.set("source", params.source);
  if (params.days) sp.set("days", String(params.days));
  if (params.limit) sp.set("limit", String(params.limit));
  if (params.offset) sp.set("offset", String(params.offset));
  return getJSON<NewsFeedResponse>(`/news/feed?${sp.toString()}`, 20_000);
}

// --- Seeking Alpha evidence feed (Layer C-1) — unified SA articles + market-news ---
export interface SAFeedItem {
  type: "article" | "market_news";
  id: string;
  title: string;
  tickers: string[];
  published_at: string;
  url: string | null;
  source: string; // "seeking_alpha"
  snippet: string | null;
  has_detail: boolean;
  comments_count: number;
  detail_route: string | null; // present → open internally; null → fall back to url
}

export interface SAFeedResponse {
  available: boolean; // false = degraded (e.g. SA not local-first), NOT an error
  days: number;
  query: string | null;
  total: number;
  items: SAFeedItem[];
  by_type: Record<string, number>;
  by_day: Record<string, number>;
  empty_reason: string | null;
}

export function getSAFeed(params: {
  q?: string;
  ticker?: string;
  item_type?: string; // article | market_news
  days?: number;
  limit?: number;
  offset?: number;
}): Promise<SAFeedResponse> {
  const sp = new URLSearchParams();
  if (params.q) sp.set("q", params.q);
  if (params.ticker) sp.set("ticker", params.ticker);
  if (params.item_type) sp.set("item_type", params.item_type);
  if (params.days) sp.set("days", String(params.days));
  if (params.limit) sp.set("limit", String(params.limit));
  if (params.offset) sp.set("offset", String(params.offset));
  return getJSON<SAFeedResponse>(`/sa/feed?${sp.toString()}`, 20_000);
}

// --- provider health (slice 3e-A; PURE READ — no provider fetch) ---
// Per-provider DTO is ProviderRun-compatible (Slice 5's per-call telemetry plugs
// in without reshaping). maintenance = derived (e.g. IBKR weekend); disabled is a
// state, never an HTTP error. Key info is presence+source only (keys stay in
// config/.env; no entry UI — that is its own future slice).

export type ProviderStatus =
  | "connected" | "stale" | "maintenance" | "no_signal" | "missing_key" | "disabled";

export interface ProviderHealth {
  id: string;
  label: string;
  kind: string; // market | news | macro | fundamentals | capture
  key_present: boolean;
  key_source: string; // env | config/.env | missing | not_required
  key_vars: string[];
  enabled: boolean | null; // null = no toggle exists for this provider
  status: ProviderStatus;
  last_success_at: string | null;
  last_attempt_at: string | null;
  last_error: string | null;
  detail: string;
  signals: Record<string, unknown>;
}

export interface ProvidersHealthResponse {
  generated_at: string;
  providers: ProviderHealth[];
  jobs: Record<string, Record<string, unknown>>; // latest job_runs row per job_name
  local_market: { db_exists: boolean; sync: Record<string, SyncMeta | null> };
  notes: string[]; // per-section degradation notes, if any
}

export function getProvidersHealth(): Promise<ProvidersHealthResponse> {
  return getJSON<ProvidersHealthResponse>("/providers/health", 20_000);
}

// --- per-source data-collection schedule (3e-D; app-owned, no cron) ---
// All sources are DISABLED by default; enabling one makes the sidecar collect →
// PG sync → local-mirror refresh on its own interval. Run-now is fire-and-return;
// poll getSchedule() for the per-source running flag and the job_runs row
// (collect.<source>, visible in getProvidersHealth().jobs) for the outcome.

export interface ScheduleSourceState {
  label: string;
  description: string;
  ibkr: boolean;
  provider_fetch: boolean; // false = app-native (no external fetch)
  enabled: boolean;
  interval_minutes: number;
  default_interval_minutes: number;
  running: boolean;
  // rough live progress (ticker N of TOTAL) — only in-process adapter sources
  // report it; subprocess sources stay indeterminate
  progress: { done: number; total: number; current: string } | null;
  last_attempt_at: string | null;
  // last run_source outcome INCLUDING skips — a skip (e.g. "the CLI is already
  // running this source", cross-process) writes no job_runs row, so this field is
  // the only way the UI can see it after a fire-and-return Run now.
  last_result: { source: string; status: string; reason?: string; at?: string } | null;
  job_name: string; // collect.<source>
}

export function getSchedule(): Promise<{ sources: Record<string, ScheduleSourceState> }> {
  return getJSON<{ sources: Record<string, ScheduleSourceState> }>("/schedule", 8_000);
}

export function putSchedule(
  source: string,
  body: { enabled?: boolean; interval_minutes?: number },
): Promise<{ source: string; enabled: boolean; interval_minutes: number }> {
  return sendJSON(`/schedule/${encodeURIComponent(source)}`, "PUT", body, 8_000);
}

export function runScheduleNow(
  source: string,
): Promise<{ source: string; status: string; job_name?: string; reason?: string }> {
  return sendJSON(`/schedule/run/${encodeURIComponent(source)}`, "POST", undefined, 8_000);
}

// --- app-managed provider keys / connection settings -------------------------
// Secrets never come back readable (masked only). Saving re-applies the env
// bridge immediately — the sidecar is the parent of every collector subprocess,
// so the change reaches all call sites without a restart. Effective precedence:
// real env var > app value > config/.env.

export interface ProviderConfigField {
  field: string; // api_key | host | port
  label: string;
  secret: boolean;
  env_var: string;
  app_value_set: boolean;
  app_value_masked: string | null;
  effective_source: string; // app | env | config/.env | missing
}

export interface ProviderConfigEntry {
  fields: ProviderConfigField[];
  testable: boolean;
  default_available: boolean; // key-free + extension-free (e.g. SEC EDGAR)
}

export function getProvidersConfig(): Promise<{ providers: Record<string, ProviderConfigEntry> }> {
  return getJSON<{ providers: Record<string, ProviderConfigEntry> }>("/providers/config", 8_000);
}

export function putProviderConfig(
  provider: string,
  fields: Record<string, string | null>,
): Promise<ProviderConfigEntry> {
  return sendJSON(`/providers/config/${encodeURIComponent(provider)}`, "PUT", { fields }, 8_000);
}

export interface ProviderTestResult {
  provider: string;
  ok: boolean | null; // null = no live test offered (paid-per-call / extension)
  latency_ms: number | null;
  detail: string;
}

export function testProvider(provider: string): Promise<ProviderTestResult> {
  // one explicit cheap probe; IBKR = TCP socket, key providers = one free call
  return sendJSON(`/providers/test/${encodeURIComponent(provider)}`, "POST", undefined, 15_000);
}
