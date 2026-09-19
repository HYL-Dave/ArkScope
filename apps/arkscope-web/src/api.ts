// Thin client for the local ArkScope sidecar.
//
// Connection params come from the Electron preload bridge (window.arkscope) when
// running in the desktop shell, or fall back to a dev default when running the
// Vite dev server in a plain browser.

import { SSEFrameParser, type SSEFrame } from "./sse";
import type { UiLocale } from "./i18n/locale";
import { LISTING_CHECK_NAMES, LISTING_PROVIDER_NAMES, LISTING_PROVIDER_ISSUES } from "./lifecycle/listingContract";
export { LISTING_CHECK_NAMES, LISTING_PROVIDER_NAMES, LISTING_PROVIDER_ISSUES } from "./lifecycle/listingContract";
import {
  invalidCurrentPayload,
  parseLifecycleReviewPacket, parseLifecycleReviewConfirmation, parseCurrentActivity, parseCurrentActivityList,
  type LifecycleReviewPacket,
} from "./lifecycle/currentReviewContract";
export { parseLifecycleReviewPacket, parseLifecycleReviewConfirmation } from "./lifecycle/currentReviewContract";
export type { LifecycleReviewPacket, LifecycleReviewConfirmation } from "./lifecycle/currentReviewContract";
import { parseInvestigationTargets, parseInvestigationRuntime, parseInvestigationRun, parseInvestigationPreflight, parseInvestigationProviders, parseInvestigationActions, parseInvestigationStart, type InvestigationRuntime } from "./lifecycle/investigationContract";

export interface ApiStatus {
  status: string;
  timestamp: string;
  tools_registered: number;
  tool_categories: Record<string, number>;
  data_sources: Record<string, number>;
}

export type FixedTaskRuntimeTask = "card_synthesis";

export interface FixedTaskRuntimeSettings {
  task: FixedTaskRuntimeTask;
  model_timeout_s: number;
  source: "env" | "db" | "default";
  db_saved: boolean;
  warning: string | null;
}

export type FixedTaskRuntimeMap = Record<
  FixedTaskRuntimeTask,
  FixedTaskRuntimeSettings
>;

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
  ai_research: TaskRoute;
  // An older sidecar does not advertise the independent investigation task.
  lifecycle_investigation?: TaskRoute;
  research_runtime: ResearchRuntimeSettings;
  // Optional while the desktop UI and sidecar can be on adjacent versions.
  fixed_task_runtime?: FixedTaskRuntimeMap;
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
export type ModelTask = "card_synthesis" | "ai_research" | "lifecycle_investigation";

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
  effort_options?: string[];
  recommended_for: ModelTask[];
  source_url: string;
  verified_at: string;
  notes: string;
  task_route_status?: "current" | "retired";
  aliases?: string[];
}

export interface ModelLifecycleFact {
  id: string;
  provider: ModelProvider;
  task_route_status: "current" | "retired";
  aliases?: string[];
}

export interface TaskInfo {
  id: ModelTask;
  label: string;
  description: string;
  default_provider: ModelProvider;
  recommended_model: string;
  supports_custom_models?: boolean;
}

export interface EffectiveModelEntry {
  id: string;
  label: string;
  badge: "advanced" | "seed" | "custom" | "route" | null;
}

export type EffectiveModelStatus = "visible" | "seed" | "advanced" | "route";

export type ModelReasonCode =
  | "adapter_unavailable"
  | "context_window_exceeded"
  | "discovery_unavailable"
  | "missing_active_credential"
  | "model_auth_unverified"
  | "model_entitlement_unverified"
  | "model_not_in_registry"
  | "model_not_visible"
  | "model_output_limit_unknown"
  | "model_retired"
  | "model_task_unsupported"
  | "protocol_incompatible"
  | "protocol_resource_exhausted"
  | "provider_call_failed"
  | "reauth_required"
  | "subscription_plan_required"
  | "subscription_plan_unverified"
  | "subscription_usage_unavailable"
  | "task_auth_mode_unsupported"
  | "task_capability_missing"
  | "task_test_unsupported"
  | "timeout"
  | "version_incompatible";

export interface EffectiveProviderModelEntry {
  id: string;
  label: string;
  status: EffectiveModelStatus;
  visible_to_credential: boolean | null;
  eligible: boolean;
  reason_code: ModelReasonCode | null;
  effort_options?: string[];
  thinking_mode:
    | "none"
    | "manual_budget"
    | "adaptive_opt_in"
    | "adaptive_default_on"
    | "adaptive_always_on"
    | string;
}

export interface EffectiveProviderModels {
  executable: boolean;
  reason_code: ModelReasonCode | null;
  models: EffectiveProviderModelEntry[];
  cache_state: "ok" | "seed_only" | "never_discovered" | string;
  discovered_at: string | null;
}

export interface EffectiveProviderSummary {
  credential_id: string;
  auth_mode: CredentialAuthType;
  label: string;
  // Additive for older sidecars that emitted effective providers before plan
  // admission was projected.
  plan_type?: string | null;
}

export interface EffectiveTaskModels {
  verified: EffectiveModelEntry[];
  advanced: EffectiveModelEntry[];
  cache_state: "ok" | "seed_only" | "never_discovered" | string;
  discovered_at: string | null;
  current_provider?: ModelProvider;
  providers?: Partial<Record<ModelProvider, EffectiveProviderModels>>;
}

export interface ModelCatalog {
  providers: ModelProvider[];
  tasks: TaskInfo[];
  models: ModelOption[];
  effort_options: Record<ModelProvider, EffortOption[]>;
  // Additive for old sidecars: the backend owns task-control ordering while
  // provider/model effort arrays retain their provider-native order.
  task_route_effort_order?: ExplicitResearchEffort[];
  current_model_ids?: string[];
  retired_model_ids?: string[];
  model_lifecycle?: ModelLifecycleFact[];
  routes: Record<Exclude<ModelTask, "lifecycle_investigation">, TaskRoute> & {
    lifecycle_investigation?: TaskRoute;
  };
  credentials: Record<ModelProvider, ProviderCredential[]>;
  custom_allowed: boolean;
  // P2.7 additive: per-task verified/advanced partition (may be absent on old
  // sidecars — the picker falls back to the seed list).
  effective?: {
    providers?: Partial<Record<ModelProvider, EffectiveProviderSummary | null>>;
    tasks: Partial<Record<ModelTask, EffectiveTaskModels>>;
  };
}

// Explicit auth modes (backend normalizes legacy oauth/setup_token → these; it
// never returns the legacy values). Matches src/model_credentials.CredentialAuthType.
export type CredentialAuthType = "api_key" | "api_key_pool" | "chatgpt_oauth" | "claude_code_oauth";
export type OAuthLifecycleState =
  | "ready"
  | "refresh_required"
  | "refresh_failed_retryable"
  | "reauth_required"
  | "unverifiable";

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
  lifecycle_state?: OAuthLifecycleState | null;
  lifecycle_error_code?: string | null;
  last_refresh_attempt_at?: string | null;
  last_refresh_success_at?: string | null;
  last_refresh_error_at?: string | null;
  last_refresh_error_detail?: string | null;
  notes: string;
}

export type OAuthRateLimitStatus = "allowed" | "allowed_warning" | "rejected";
export type OAuthAccountSource = "codex_app_server" | "claude_rate_limit_event" | "anthropic_oauth_probe";

export interface OAuthRateLimitWindow {
  used_percent: number | null;
  window_duration_minutes: number | null;
  resets_at: number | null;
}

export interface OAuthCreditsSnapshot {
  balance: string | null;
  has_credits: boolean;
  unlimited: boolean;
}

export interface OAuthSpendControlLimit {
  limit: string;
  used: string;
  remaining_percent: number;
  resets_at: number;
}

export interface OAuthRateLimitSnapshot {
  limit_id: string | null;
  limit_name: string | null;
  plan_type: string | null;
  primary: OAuthRateLimitWindow | null;
  secondary: OAuthRateLimitWindow | null;
  rate_limit_reached_type: string | null;
  credits: OAuthCreditsSnapshot | null;
  individual_limit: OAuthSpendControlLimit | null;
  spend_control_reached: boolean | null;
  status: OAuthRateLimitStatus | null;
  overage_status: OAuthRateLimitStatus | null;
  overage_resets_at: number | null;
  overage_disabled_reason: string | null;
}

export interface OAuthUsageSummary {
  lifetime_tokens: number | null;
  peak_daily_tokens: number | null;
  longest_running_turn_seconds: number | null;
  current_streak_days: number | null;
  longest_streak_days: number | null;
}

export interface OAuthDailyUsageBucket {
  start_date: string;
  tokens: number;
}

export interface OAuthAccountPayload {
  rate_limits: OAuthRateLimitSnapshot;
  rate_limits_by_limit_id: Record<string, OAuthRateLimitSnapshot>;
  reset_credits_available: number | null;
  usage_summary: OAuthUsageSummary;
  daily_usage_buckets: OAuthDailyUsageBucket[];
}

export interface OAuthAccountSnapshot {
  credential_id: string;
  provider: ModelProvider;
  auth_mode: "chatgpt_oauth" | "claude_code_oauth";
  account_fingerprint: string;
  source: OAuthAccountSource;
  schema_version: 1;
  observed_at: string;
  status: "available";
  payload: OAuthAccountPayload;
  updated_at: string;
}

export interface OAuthAccountSyncView {
  credential_id: string;
  snapshot: OAuthAccountSnapshot | null;
  sync_status: "not_requested" | "succeeded" | "failed" | "unsupported";
  sync_error_code: string | null;
}

export interface DiscoveredModel {
  id: string;
  provider: ModelProvider;
  label: string;
  source: "provider_api" | "seed";
  effort_options?: string[] | null;
  default_effort?: string | null;
  input_modalities?: Array<"text" | "image" | "audio"> | null;
  task_route_tasks?: ModelTask[] | null;
}

export interface ModelDiscoveryResult {
  provider: ModelProvider;
  credential_id: string | null;
  status: "ok" | "missing_credential" | "unsupported" | "error";
  models: DiscoveredModel[];
  error: string | null;
  source_url: string | null;
  // P2.7 additive: present only when the discovery run landed in the cache.
  cache_state?: "ok" | "seed_only" | string;
  cached_at?: string | null;
  cached?: boolean;
  // S3 additive machine-readable failure class: "reauth_required" = a fresh
  // login repairs it; "missing_credential" = driver wiring, re-login can't fix.
  error_code?: string | null;
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

export interface TaskModelTestResult {
  task: ModelTask;
  provider: ModelProvider;
  model: string;
  effort: string;
  auth_mode: CredentialAuthType | null;
  credential_id: string | null;
  status: "ok" | "error" | "unsupported";
  error_code: ModelReasonCode | null;
  latency_ms: number | null;
  tested_at: string;
  fallback_effort: string | null;
  warning: string | null;
}

export interface WatchlistRow {
  ticker: string;
  group: string;
  priority: string;
  latest_close: number | null;
  change_7d_pct: number | null;
  news_count_7d: number;
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
  lineage: {
    predecessors: TickerIdentityLineageItem[];
    successors: TickerIdentityLineageItem[];
  };
}

export interface TickerIdentityLineageItem {
  ticker: string;
  transition_id: string;
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

export type InvestorPreset =
  | "growth" | "value" | "momentum" | "income" | "event_driven" | "balanced" | "custom";
export type AssistantStance =
  | "off" | "neutral" | "aligned" | "complementary"
  | "strict_risk_control" | "valuation_rationalist" | "growth_opportunity";
export type SkillMode = "off" | "suggest_only";

export interface PersonalizationTrace {
  profile_active: boolean;
  assistant_stance: AssistantStance;
  skill_mode: SkillMode;
  suggested_skills: string[];
  applied_skills: string[];
  context_snapshot?: string | null;
}

export interface InvestorProfile {
  enabled: boolean;
  primary_preset: InvestorPreset;
  risk_appetite: number | null;
  risk_capacity: number | null;
  risk_mismatch: "none" | "appetite_above_capacity" | "capacity_above_appetite" | "unclear";
  holding_horizon: string;
  drawdown_tolerance_pct: number | null;
  concentration_limit_pct: number | null;
  preferred_edge: string[];
  avoidances: string[];
  behavioral_flags: string[];
  freeform_notes: string;
  default_stance: AssistantStance;
  skill_mode: SkillMode;
  last_reviewed_at: string | null;
  updated_at: string | null;
}

export interface InvestorProfileResponse {
  profile: InvestorProfile;
  effective_stance: AssistantStance;
  trace: PersonalizationTrace;
  context_preview: string;
}

export type CalibrationTopicId =
  | "loss_response"
  | "financial_capacity"
  | "time_horizon"
  | "single_position_limit"
  | "risk_avoidances"
  | "behavioral_patterns"
  | "investment_approach"
  | "assistant_style";

export interface CalibrationSession {
  id: string;
  status: "active" | "closed" | "superseded";
  interview_version: number | null;
  covered_topics: string[];
  current_topic_id: string | null;
  current_question_message_id: string | null;
  superseded_reason: string | null;
  created_at: string;
  updated_at: string;
  closed_at: string | null;
}

export interface CalibrationMessage {
  id: string;
  session_id: string;
  role: "user" | "assistant";
  content: string;
  turn_id: string | null;
  topic_id: string | null;
  prompt_id: string | null;
  created_at: string;
}

export interface CalibrationTurn {
  id: string;
  session_id: string;
  kind: "answer" | "proposal_request";
  status: "pending" | "completed" | "failed" | "interrupted";
  question_message_id: string | null;
  addressed_topic_id: string | null;
  next_topic_id: string | null;
  error_code: string | null;
  diagnostic: string | null;
  attempt_count: number;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface CalibrationProposal {
  id: string;
  session_id: string;
  status: "draft" | "approved" | "rejected" | "superseded";
  profile_patch: Partial<InvestorProfile>;
  proposed_fields: string[];
  covered_topics: string[];
  rationales: Record<string, string>;
  conflict_fields: string[];
  created_at: string;
  approved_at: string | null;
  rejected_at: string | null;
  conflicted_at: string | null;
  superseded_at: string | null;
  superseded_reason: string | null;
}

export interface CalibrationState {
  active_session: CalibrationSession | null;
  sessions: CalibrationSession[];
  messages: CalibrationMessage[];
  pending_turn: CalibrationTurn | null;
  latest_proposal: CalibrationProposal | null;
  topic_catalog: string[];
}

export function getInvestorProfile(): Promise<InvestorProfileResponse> {
  return getJSON<InvestorProfileResponse>("/profile/investor");
}

export function draftInvestorProfile(
  profile: Partial<InvestorProfile>,
): Promise<InvestorProfileResponse> {
  return sendJSON<InvestorProfileResponse>("/profile/investor/draft", "POST", profile);
}

export function saveInvestorProfile(
  profile: Partial<InvestorProfile>,
): Promise<InvestorProfileResponse> {
  return sendJSON<InvestorProfileResponse>("/profile/investor", "PUT", profile);
}

export function getCalibrationState(): Promise<CalibrationState> {
  return getJSON<CalibrationState>("/profile/investor/calibration", 8_000);
}

export function startCalibrationSession(supersede_active = false): Promise<CalibrationState> {
  return sendJSON<CalibrationState>(
    "/profile/investor/calibration/sessions",
    "POST",
    { supersede_active },
    8_000,
  );
}

export function sendCalibrationMessage(body: {
  turn_id: string;
  session_id?: string;
  content: string;
  provider?: string;
  model?: string;
}): Promise<CalibrationState> {
  return sendJSON<CalibrationState>(
    "/profile/investor/calibration/messages",
    "POST",
    body,
    60_000,
  );
}

export function retryCalibrationTurn(
  turnId: string,
  body: { provider?: string; model?: string } = {},
): Promise<CalibrationState> {
  return sendJSON<CalibrationState>(
    `/profile/investor/calibration/turns/${encodeURIComponent(turnId)}/retry`,
    "POST",
    body,
    60_000,
  );
}

export function requestCalibrationProposal(body: {
  turn_id: string;
  session_id?: string;
  provider?: string;
  model?: string;
}): Promise<CalibrationState> {
  return sendJSON<CalibrationState>(
    "/profile/investor/calibration/proposals/request",
    "POST",
    body,
    60_000,
  );
}

export function approveCalibrationProposal(
  proposalId: string,
): Promise<{ profile: InvestorProfile; proposal: CalibrationProposal }> {
  return sendJSON(
    `/profile/investor/calibration/proposals/${encodeURIComponent(proposalId)}/approve`,
    "POST",
    {},
    20_000,
  );
}

export function rejectCalibrationProposal(
  proposalId: string,
): Promise<{ proposal: CalibrationProposal }> {
  return sendJSON(
    `/profile/investor/calibration/proposals/${encodeURIComponent(proposalId)}/reject`,
    "POST",
    undefined,
    8_000,
  );
}

export type ExecutionReceipt = Readonly<{
  provider: string | null;
  model: string | null;
  effort: string | null;
  auth_mode: "api_key" | "chatgpt_oauth" | "claude_code_oauth" | null;
}>;

export interface CardSummary {
  run_id: number;
  ticker: string;
  question: string | null;
  horizon: string | null;
  card_type: string;
  status: string;
  provider: string | null;
  model: string | null;
  execution_receipt?: ExecutionReceipt;
  generated_at: string;
  saved_report_id: number | null;
  conclusion: string | null;
  confidence_level: "high" | "medium" | "low" | null;
  personalization?: PersonalizationTrace | null;
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
  execution_receipt?: ExecutionReceipt;
  effort?: string | null;
  fallback_effort?: string | null;
  warning?: string | null;
  generated_at: string;
  card: ResultCard;
  evidence_packet: EvidencePacket | null;
  personalization?: PersonalizationTrace | null;
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
    assistant_stance?: AssistantStance;
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

export class ApiError extends Error {
  constructor(
    message: string,
    readonly path: string,
    readonly status: number,
    readonly code: string | null,
    readonly diagnostic: string | null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

interface ParsedResponseError {
  code: string | null;
  diagnostic: string | null;
  legacySuffix: string | null;
}

async function parseResponseError(r: Response): Promise<ParsedResponseError> {
  try {
    const body = (await r.json()) as unknown;
    if (!body || typeof body !== "object" || Array.isArray(body)) {
      return { code: null, diagnostic: null, legacySuffix: null };
    }
    const detail = (body as { detail?: unknown }).detail;
    if (typeof detail === "string") {
      const diagnostic = detail.trim() || null;
      return { code: null, diagnostic, legacySuffix: diagnostic };
    }
    if (!detail || typeof detail !== "object" || Array.isArray(detail)) {
      return { code: null, diagnostic: null, legacySuffix: null };
    }
    const value = detail as Record<string, unknown>;
    const code = typeof value.code === "string" ? value.code.trim() || null : null;
    const diagnostic = typeof value.message === "string"
      ? value.message.trim() || null
      : null;
    const rawDiagnostic = (value as { diagnostic?: unknown }).diagnostic;
    const explicitDiagnostic = typeof rawDiagnostic === "string"
      ? rawDiagnostic.trim() || null
      : null;
    if (explicitDiagnostic) {
      return {
        code,
        diagnostic: explicitDiagnostic,
        legacySuffix: diagnostic ?? code,
      };
    }
    return { code, diagnostic, legacySuffix: diagnostic ?? code };
  } catch {
    return { code: null, diagnostic: null, legacySuffix: null };
  }
}

async function getJSON<T>(path: string, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<T> {
  const r = await fetchWithTimeout(path, timeoutMs);
  if (!r.ok) {
    const parsed = await parseResponseError(r);
    throw new ApiError(
      `${path} returned ${r.status}`,
      path,
      r.status,
      parsed.code,
      parsed.diagnostic,
    );
  }
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
  if (!r.ok) {
    const parsed = await parseResponseError(r);
    const suffix = parsed.legacySuffix ? `: ${parsed.legacySuffix}` : "";
    throw new ApiError(
      `${path} returned ${r.status}${suffix}`,
      path,
      r.status,
      parsed.code,
      parsed.diagnostic,
    );
  }
  if (r.status === 204) return undefined as T;
  return (await r.json()) as T;
}

export type SecResearchState = "ok" | "empty" | "partial" | "unavailable";
export interface SecResearchGap { code: string; [key: string]: unknown }
export interface SecResearchEnvelope<T> {
  status: SecResearchState;
  data: T;
  gaps: SecResearchGap[];
  observed_at: string | null;
  coverage: Record<string, unknown>;
  next_cursor: string | null;
}
export interface SecResearchCapacity {
  persisted_bytes: number;
  reserved_bytes: number;
  orphan_bytes: number;
  charged_bytes: number;
  budget_bytes: number;
  remaining_bytes: number;
  over_budget: boolean;
}
export interface SecResearchConfig {
  capture_budget_bytes: number;
  capacity: SecResearchCapacity | null;
}
export interface SecResearchBatch {
  batch_id: string;
  status: "running" | "succeeded" | "partial" | "failed";
  scope: "recent";
  forms: string[];
  started_at: string;
  finished_at: string | null;
  acquired_at: string | null;
  universe_status: "unknown" | "available" | "unavailable";
  universe_tickers: string[];
  attempted_ciks: string[];
  confirmed_ciks: string[];
  failed_ciks: string[];
  deferred_ciks: string[];
  rotation: { cik: string; tickers: string[] }[];
  unresolved: { ticker: string; code: string; candidates: string[] }[];
  outcomes: { cik: string; receipt_id: number | null; status: SecResearchState;
    completed_sources: number; filing_count: number; fact_count: number }[];
  filing_count: number;
  fact_count: number;
  request_count: number;
  gaps: SecResearchGap[];
  stop_reason: string | null;
  elapsed_seconds: number;
  issuer_map_observation_id: number | null;
}
export type SecResearchScheduleStatus = SecResearchEnvelope<{
  last_attempt: SecResearchBatch | null;
  last_acquisition_at: string | null;
  last_completed_batch: SecResearchBatch | null;
} | null>;

export function getSecResearchScheduleStatus(): Promise<SecResearchScheduleStatus> {
  return getJSON("/sec-research/schedule-status");
}
export interface SecResearchFiling {
  filing_id: string;
  accession: string;
  form?: string | null;
  filed_date?: string | null;
  report_date?: string | null;
  accepted_at?: string | null;
  primary_document?: string | null;
  primary_url?: string | null;
  [key: string]: unknown;
}
export interface SecResearchFact {
  fact_id: string;
  namespace: string;
  concept: string;
  value: string;
  unit: string;
  start?: string | null;
  end?: string | null;
  filed_date?: string | null;
  accession?: string | null;
  [key: string]: unknown;
}
export type SecResearchStoredStatus = SecResearchEnvelope<{
  cik: string;
  snapshots: Record<string, number>;
} | null>;
export interface SecResearchReceipt {
  receipt_id: number;
  cik: string;
  status: SecResearchState;
  completed: string[];
  pending: string[];
  gaps: SecResearchGap[];
  observed_at: string | null;
  [key: string]: unknown;
}
export interface SecResearchFilingsQuery {
  forms?: string[];
  filed_from?: string;
  filed_to?: string;
  include_amendments?: boolean;
  cursor?: string;
  limit?: number;
}
export interface SecResearchFactsQuery {
  metrics?: string[];
  concepts?: string[];
  fact_ids?: string[];
  accession?: string;
  as_of?: string;
  period?: "all" | "instant" | "annual" | "quarterly" | "ytd";
  start?: string;
  end?: string;
  revisions?: "latest" | "all";
  cursor?: string;
  limit?: number;
}
function secResearchQueryPath(cik: string, kind: "filings" | "facts", query: SecResearchFilingsQuery | SecResearchFactsQuery) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined) continue;
    for (const entry of Array.isArray(value) ? value : [value]) params.append(key, String(entry));
  }
  const suffix = params.size ? `?${params}` : "";
  return `/sec-research/${encodeURIComponent(cik)}/${kind}${suffix}`;
}
export function getSecResearchConfig(): Promise<SecResearchConfig> {
  return getJSON("/sec-research/config");
}
export function setSecResearchBudget(capture_budget_bytes: number): Promise<{ capture_budget_bytes: number }> {
  return sendJSON("/sec-research/config", "PUT", { capture_budget_bytes });
}
export function getSecResearchStatus(cik: string): Promise<SecResearchStoredStatus> {
  return getJSON(`/sec-research/${encodeURIComponent(cik)}`);
}
export function getSecResearchFilingForms(cik: string): Promise<SecResearchEnvelope<string[] | null>> {
  return getJSON(`/sec-research/${encodeURIComponent(cik)}/filing-forms`);
}
export function getSecResearchFilings(cik: string, query: SecResearchFilingsQuery = {}): Promise<SecResearchEnvelope<SecResearchFiling[] | null>> {
  return getJSON(secResearchQueryPath(cik, "filings", query));
}
export function getSecResearchFacts(cik: string, query: SecResearchFactsQuery = {}): Promise<SecResearchEnvelope<SecResearchFact[] | null>> {
  return getJSON(secResearchQueryPath(cik, "facts", query));
}
export function refreshSecResearch(cik: string, resume = false): Promise<SecResearchReceipt> {
  // A client wait allowance, not a server cancellation or wall-clock guarantee.
  return sendJSON(`/sec-research/${encodeURIComponent(cik)}/refresh`, "POST", { resume }, 600_000);
}

export interface SecDocumentCitation {
  filing_id: string;
  document_id: string;
  capture_id: string;
  accession: string;
  source_url: string;
  original_sha256: string;
  text_sha256: string;
  extraction_version: string;
  start_byte: number;
  end_byte: number;
  match_start_byte: number | null;
  match_end_byte: number | null;
}
interface SecObservationCitation {
  snapshot_id: string;
  source_sha256: string;
  source_pointer: string;
  source_url: string;
  observed_at: string;
}
export interface SecFactCitation extends SecObservationCitation {
  kind: "fact";
  cik: string;
  fact_id: string;
}
export interface SecFilingCitation extends SecObservationCitation {
  kind: "filing";
  filing_id: string;
}
export type SecCitation = (SecDocumentCitation & { kind: "document" }) | SecFactCitation | SecFilingCitation;
export type SecCitationGapCode = "sec_citation_invalid" | "sec_citation_result_invalid"
  | "sec_citation_query_invalid" | "sec_citation_missing" | "sec_citation_integrity_failed";
export interface SecCitationTrace {
  call_id?: string;
  sec_citations?: SecCitation[];
  sec_citation_gaps?: SecCitationGapCode[];
}
export type SecCitationRead = SecResearchEnvelope<{
  citation: SecFactCitation;
  observation: SecResearchFact;
} | {
  citation: SecFilingCitation;
  observation: SecResearchFiling;
} | {
  citation: SecDocumentCitation & { kind: "document" };
  text: string;
  document: Omit<SecDocumentMetadata, "primary_document"> & { accession: string; mime_type: string };
} | null>;

function secCitationQuery(ref: SecCitation): string {
  const invalid = () => { throw Object.assign(new Error("sec_citation_invalid"), { code: "sec_citation_invalid" }); };
  if (!ref || typeof ref !== "object" || Array.isArray(ref)) return invalid();
  const sourceFields = ["kind", "snapshot_id", "source_sha256", "source_pointer", "source_url", "observed_at"];
  const fields = ref.kind === "document"
    ? ["kind", "filing_id", "document_id", "capture_id", "accession", "source_url", "original_sha256", "text_sha256", "extraction_version", "start_byte", "end_byte", "match_start_byte", "match_end_byte"]
    : ref.kind === "fact" ? [...sourceFields, "cik", "fact_id"]
      : ref.kind === "filing" ? [...sourceFields, "filing_id"] : invalid();
  const entries = Object.entries(ref).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0);
  if (entries.length !== fields.length || entries.some(([key, value]) => !fields.includes(key)
    || (key.endsWith("_byte") ? value !== null && !Number.isSafeInteger(value) : typeof value !== "string" || !value.length))) return invalid();
  if (ref.source_url.length > 2048 || !/^https:\/\/(www|data)\.sec\.gov\/[^\s?#]+$/.test(ref.source_url)) return invalid();
  if (ref.kind === "document") {
    const { start_byte: start, end_byte: end, match_start_byte: left, match_end_byte: right } = ref;
    if (start === null || end === null || start < 0 || end <= start || end > 128 * 1024 * 1024 || end - start > 80000
      || !((left === null && right === null) || (left !== null && right !== null && start <= left && left < right && right <= end))) return invalid();
  } else if (Array.from(ref.source_pointer).length > 2048 || !ref.source_pointer.startsWith("/") || /~(?![01])/.test(ref.source_pointer)) return invalid();
  // Python ensure_ascii escapes DEL and every non-ASCII UTF-16 code unit,
  // including each half of a surrogate pair. JSON.stringify alone does not.
  const raw = JSON.stringify(Object.fromEntries(entries)).replace(/[\u007f-\uffff]/g,
    (char) => `\\u${char.charCodeAt(0).toString(16).padStart(4, "0")}`);
  if (raw.length > 6144) return invalid();
  return btoa(raw).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export async function getSecResearchCitation(ref: SecCitation): Promise<SecCitationRead> {
  return getJSON(`/sec-research/citation?ref=${secCitationQuery(ref)}`);
}
export interface SecDocumentMetadata {
  filing_id: string;
  document_id: string;
  capture_id: string;
  primary_document: string | null;
  form: string;
  source_url: string;
  original_sha256: string;
  text_sha256: string;
  extraction_version: string;
  [key: string]: unknown;
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
  archived_at?: string | null;
  latest_run_status?: ResearchRunDTO["status"] | null;
  active_run?: ResearchRunDTO | null;
}
export interface ResearchMessageDTO {
  role: "user" | "assistant"; content: string;
  provider: string | null; model: string | null; effort: string | null;
  tools_used: string[]; tool_calls: Array<SecCitationTrace & { name: string; input?: unknown; result_preview?: string }>;
  token_usage: Record<string, number> | null; tickers: string[] | null;
  elapsed_seconds: number | null; is_error: boolean; created_at: string;
  run_id?: string | null;
  error_code?: string | null;
  error?: string | null;
  personalization?: PersonalizationTrace | null;
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
  assistant_stance?: string | null;
  personalization?: PersonalizationTrace | null;
  auth_mode: string | null;
  credential_id: string | null;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
  error_code?: string | null;
  token_usage: Record<string, number> | null;
  created_at: string;
  updated_at: string;
}
export type ExplicitResearchEffort = "low" | "medium" | "high" | "xhigh" | "max";
export interface ResearchRunEventDTO {
  run_id: string;
  seq: number;
  type: string;
  data: Record<string, unknown>;
  created_at: string;
}
export type ResearchHistoryRunState =
  | "all"
  | "active"
  | "succeeded"
  | "failed"
  | "interrupted"
  | "no_run";
export type ResearchHistoryArchiveMode = "current" | "archived";
export interface ResearchThreadQueryParams {
  q?: string;
  ticker?: string;
  updated_from?: string;
  updated_before?: string;
  run_state?: ResearchHistoryRunState;
  archived?: ResearchHistoryArchiveMode;
  limit?: number;
  offset?: number;
}
export interface ResearchThreadsResponse {
  threads: ResearchThreadDTO[];
  total: number;
  limit: number;
  offset: number;
}
export type ResearchThreadPatch = {
  title?: string;
  archived?: boolean;
};

export function queryResearchThreads(
  params: ResearchThreadQueryParams = {},
): Promise<ResearchThreadsResponse> {
  const query = new URLSearchParams();
  const q = params.q?.trim();
  const ticker = params.ticker?.trim();
  if (q) query.set("q", q);
  if (ticker) query.set("ticker", ticker);
  if (params.updated_from) query.set("updated_from", params.updated_from);
  if (params.updated_before) query.set("updated_before", params.updated_before);
  if (params.run_state !== undefined) query.set("run_state", params.run_state);
  if (params.archived !== undefined) query.set("archived", params.archived);
  if (params.limit !== undefined) query.set("limit", String(params.limit));
  if (params.offset !== undefined) query.set("offset", String(params.offset));
  return getJSON<ResearchThreadsResponse>(`/research/threads?${query.toString()}`, 8_000);
}
export function getResearchThread(threadId: string): Promise<{ thread: ResearchThreadDTO }> {
  return getJSON<{ thread: ResearchThreadDTO }>(
    `/research/threads/${encodeURIComponent(threadId)}`,
    8_000,
  );
}
export function updateResearchThread(
  threadId: string,
  patch: ResearchThreadPatch,
): Promise<{ thread: ResearchThreadDTO }> {
  return sendJSON<{ thread: ResearchThreadDTO }>(
    `/research/threads/${encodeURIComponent(threadId)}`,
    "PATCH",
    patch,
    8_000,
  );
}
export function getResearchThreads(limit = 50): Promise<{ threads: ResearchThreadDTO[] }> {
  return queryResearchThreads({ limit });
}
export function getResearchMessages(threadId: string): Promise<{ thread_id: string; messages: ResearchMessageDTO[] }> {
  return getJSON<{ thread_id: string; messages: ResearchMessageDTO[] }>(`/research/threads/${encodeURIComponent(threadId)}/messages`, 8_000);
}
export function getResearchSelection(threadId: string): Promise<{
  provider: ModelProvider;
  model: string;
  effort: string | null;
} | null> {
  return getJSON<{
    provider: ModelProvider;
    model: string;
    effort: string | null;
  } | null>(`/research/threads/${encodeURIComponent(threadId)}/selection`, 8_000);
}
export function deleteResearchThread(threadId: string): Promise<{ thread_id: string; deleted: boolean }> {
  return sendJSON<{ thread_id: string; deleted: boolean }>(`/research/threads/${encodeURIComponent(threadId)}`, "DELETE", undefined, 8_000);
}
export function createResearchRun(body: {
  thread_id: string;
  question: string;
  ticker?: string | null;
  provider: ModelProvider;
  model: string;
  effort: ExplicitResearchEffort;
  retry_last_failed?: boolean;
  assistant_stance?: AssistantStance;
}): Promise<{ run: ResearchRunDTO }> {
  return sendJSON<{ run: ResearchRunDTO }>("/research/runs", "POST", body, 8_000);
}
export function getResearchRun(runId: string): Promise<{ run: ResearchRunDTO }> {
  return getJSON<{ run: ResearchRunDTO }>(
    `/research/runs/${encodeURIComponent(runId)}`,
    8_000,
  );
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

export function saveFixedTaskRuntime(body: {
  tasks: Record<FixedTaskRuntimeTask, { model_timeout_s: number }>;
}): Promise<{ fixed_task_runtime: FixedTaskRuntimeMap }> {
  return sendJSON<{ fixed_task_runtime: FixedTaskRuntimeMap }>(
    "/config/fixed-task-runtime",
    "PUT",
    body,
    8_000,
  );
}

export function deleteFixedTaskRuntime(): Promise<{
  deleted: boolean;
  fixed_task_runtime: FixedTaskRuntimeMap;
}> {
  return sendJSON<{
    deleted: boolean;
    fixed_task_runtime: FixedTaskRuntimeMap;
  }>("/config/fixed-task-runtime", "DELETE", undefined, 8_000);
}

export function listCredentials(): Promise<{ credentials: Record<ModelProvider, ProviderCredential[]> }> {
  return getJSON<{ credentials: Record<ModelProvider, ProviderCredential[]> }>("/config/credentials", 8_000);
}

export function getCredentialAccountUsage(credentialId: string): Promise<OAuthAccountSyncView> {
  return getJSON<OAuthAccountSyncView>(
    `/config/credentials/${encodeURIComponent(credentialId)}/account-usage`,
    8_000,
  );
}

export function syncCredentialAccountUsage(credentialId: string): Promise<OAuthAccountSyncView> {
  return sendJSON<OAuthAccountSyncView>(
    `/config/credentials/${encodeURIComponent(credentialId)}/account-usage/sync`,
    "POST",
    undefined,
    40_000,
  );
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
  // F4 additive: false = the single-use login state was consumed by a failed
  // completion, so the copy-code manual fallback can no longer succeed.
  manual_completable?: boolean;
}
export function startOpenAIOAuth(makeActive = false, reloginCredentialId?: string): Promise<OAuthStartResult> {
  // make_active default false: logging in (or re-logging in) must never silently
  // switch the active credential. Supported tasks use chatgpt_oauth through the
  // subscription backend; model-specific execution still requires a task test.
  // `reloginCredentialId` (S3) replaces that credential's token IN PLACE — no new row.
  const body: Record<string, unknown> = { make_active: makeActive };
  if (reloginCredentialId) body.relogin_credential_id = reloginCredentialId;
  return sendJSON<OAuthStartResult>("/config/credentials/openai/oauth/start", "POST", body, 8_000);
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

export function testTaskModelAccess(
  task: ModelTask,
  provider: ModelProvider,
  model: string,
  effort: string,
): Promise<TaskModelTestResult> {
  return sendJSON<TaskModelTestResult>(
    "/config/model-task-test",
    "POST",
    { task, provider, model, effort },
    60_000,
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

export interface PortfolioAccount {
  id: number;
  label: string;
  broker: string;
  broker_account_id?: string | null;
  broker_account_id_hash?: string | null;
  sync_mode: "manual" | "ibkr_review" | "ibkr_auto" | string;
  base_currency?: string | null;
  include_in_total?: boolean;
  archived_at?: string | null;
}

export interface PortfolioPosition {
  id: number;
  account_id: number;
  broker?: string;
  broker_con_id?: string | null;
  symbol: string;
  asset_class: string;
  quantity: number;
  avg_cost?: number | null;
  currency: string;
  market_value?: number | null;
  unrealized_pnl?: number | null;
  source?: string;
  sync_status?: string;
  last_sync_at?: string | null;
  closed_at?: string | null;
  notes?: string;
  thesis?: string;
  tags?: string[];
}

export interface PositionUpdate {
  notes?: string;
  thesis?: string;
  tags?: string[];
  symbol?: string;
  asset_class?: string;
  quantity?: number;
  avg_cost?: number | null;
  currency?: string;
}

export interface PortfolioCurrencyTotal {
  position_count: number;
  market_value?: number | null;
  unrealized_pnl?: number | null;
}

export interface PortfolioTotals {
  currency_basis: "per_currency" | "broker_base" | string;
  per_currency: Record<string, PortfolioCurrencyTotal>;
  broker_base: Record<string, number> | null;
}

export interface PortfolioSnapshot {
  accounts: PortfolioAccount[];
  positions: PortfolioPosition[];
  totals: PortfolioTotals;
  included_account_ids: number[];
}

export interface PortfolioAccountValueSnapshot {
  capture_run_id: number;
  as_of_utc: string;
  as_of_kind: "capture_completed" | string;
  source: "ibkr_gateway" | string;
  base_currency: string | null;
  net_liquidation: number | null;
  total_cash_value: number | null;
  settled_cash: number | null;
  gross_position_value: number | null;
  buying_power: number | null;
  available_funds: number | null;
  initial_margin_requirement: number | null;
  maintenance_margin_requirement: number | null;
  daily_realized_pnl: number | null;
  daily_unrealized_pnl: number | null;
  daily_total_pnl: number | null;
}

export interface PortfolioOverviewAccount {
  id: number;
  label: string;
  broker: string;
  broker_account_id_hash: string | null;
  sync_mode: "manual" | "ibkr_review" | "ibkr_auto" | string;
  base_currency: string | null;
  include_in_total: boolean;
  canonical_last_sync_at: string | null;
  latest_snapshot: PortfolioAccountValueSnapshot | null;
}

export interface PortfolioOverview {
  accounts: PortfolioOverviewAccount[];
  manual_subtotal: {
    included_account_ids: number[];
    totals: PortfolioTotals;
  };
}

export interface PortfolioSyncChange {
  kind: string;
  account_id?: number | null;
  broker_account_id?: string;
  broker_con_id?: string;
  symbol: string;
  quantity?: number;
  before?: Record<string, unknown> | null;
  after?: Record<string, unknown> | null;
}

export interface PortfolioSyncPreview {
  changes: PortfolioSyncChange[];
  applies: boolean;
}

export function getPortfolio(includeClosed = false): Promise<PortfolioSnapshot> {
  return getJSON<PortfolioSnapshot>(
    includeClosed ? "/portfolio?include_closed=true" : "/portfolio",
  );
}

export function getPortfolioOverview(): Promise<PortfolioOverview> {
  return getJSON<PortfolioOverview>("/portfolio/overview");
}

export type PortfolioIntentLabel =
  | "profit_take"
  | "stop_loss"
  | "rebalance"
  | "thesis_broken"
  | "cash_need"
  | "other";

export type PortfolioActivitySource = "broker" | "manual" | "system";

export type PortfolioActivityState =
  | "realized_gain"
  | "realized_loss"
  | "realized_flat"
  | "outcome_unknown"
  | "unmatched"
  | "manual_adjustment"
  | "coverage_gap"
  | "history_start";

export interface PortfolioActivityAccount {
  id: number;
  label: string;
  broker: string;
  broker_account_id_hash: string | null;
  archived: boolean;
}

export interface PortfolioActivityAnnotation {
  intent_label: PortfolioIntentLabel | null;
  note: string;
  updated_at_utc: string;
}

export interface PortfolioCommissionRevision {
  id: number;
  first_observed_run_id: number;
  first_observed_at_utc: string;
  commission: number | null;
  currency: string | null;
  realized_pnl: number | null;
  yield_value: number | null;
  yield_redemption_date: number | null;
  is_latest: boolean;
}

export interface PortfolioExecutionRevision {
  id: number;
  exec_id: string;
  origin: "gateway" | "flex";
  first_observed_run_id: number;
  first_observed_at_utc: string;
  execution_time_utc: string;
  broker_con_id: string;
  symbol: string;
  asset_class: string;
  currency: string;
  exchange: string;
  side: string;
  quantity: number;
  price: number;
  order_id: number | null;
  perm_id: number | null;
  client_id: number | null;
  order_ref: string | null;
  liquidation: number | null;
  cumulative_quantity: number | null;
  average_price: number | null;
  corrects_exec_id: string | null;
  is_effective: boolean;
  commission_revisions: PortfolioCommissionRevision[];
}

export interface PortfolioActivityFill {
  family_root_id: number;
  effective_revision_id: number;
  revisions: PortfolioExecutionRevision[];
}

export interface PortfolioActivityObjective {
  side: "buy" | "sell" | "mixed" | "unknown";
  quantity: number;
  average_price: number | null;
  gross_notional: number | null;
  gross_notional_kind: "deterministic_arithmetic";
  commission: number | null;
  commission_currency: string | null;
  realized_pnl: number | null;
  realized_outcome: "gain" | "loss" | "flat" | "unknown";
  position_direction: "increase" | "reduce" | "unknown";
  close_scope: "none" | "partial" | "complete" | "unknown";
  position_context: "complete" | "unknown";
}

export interface PortfolioBrokerActivityItem {
  id: string;
  kind: "order" | "execution";
  occurred_at_utc: string;
  account: PortfolioActivityAccount;
  symbol: string | null;
  asset_class: string | null;
  currency: string | null;
  source: "broker";
  state: "realized_gain" | "realized_loss" | "realized_flat" | "outcome_unknown";
  objective: PortfolioActivityObjective;
  annotation: PortfolioActivityAnnotation | null;
  fills: PortfolioActivityFill[];
}

export interface PortfolioUnmatchedActivityItem {
  id: string;
  kind: "unmatched";
  occurred_at_utc: string;
  account: PortfolioActivityAccount;
  symbol: string | null;
  asset_class: string | null;
  currency: string | null;
  source: "broker";
  state: "unmatched";
  annotation: PortfolioActivityAnnotation | null;
  from_run_id: number;
  to_run_id: number;
  from_as_of_utc: string;
  to_as_of_utc: string;
  before_quantity: number;
  after_quantity: number;
  expected_quantity: number;
  residual_quantity: number;
  execution_coverage: "complete" | "incomplete" | "gap";
  reason_code: string;
}

export interface PortfolioActivityFieldChange {
  field: string;
  before: unknown;
  after: unknown;
}

export interface PortfolioManualActivityItem {
  id: string;
  kind: "manual_adjustment";
  occurred_at_utc: string;
  account: PortfolioActivityAccount;
  symbol: string;
  source: "manual";
  state: "manual_adjustment";
  annotation: PortfolioActivityAnnotation | null;
  position_id: number;
  action: "create" | "update" | "close";
  changes: PortfolioActivityFieldChange[];
}

export interface PortfolioCoverageGapActivityItem {
  id: string;
  kind: "coverage_gap";
  occurred_at_utc: string;
  account: PortfolioActivityAccount | null;
  source: "system";
  state: "coverage_gap";
  from_run_id: number | null;
  to_run_id: number;
  from_as_of_utc: string | null;
  to_as_of_utc: string;
  reason_code: "execution_leg_incomplete" | "broker_day_gap";
}

export interface PortfolioHistoryStartActivityItem {
  id: string;
  kind: "history_start";
  occurred_at_utc: string;
  account: PortfolioActivityAccount;
  source: "system";
  state: "history_start";
  capture_run_id: number;
}

export type PortfolioActivityItem =
  | PortfolioBrokerActivityItem
  | PortfolioUnmatchedActivityItem
  | PortfolioManualActivityItem
  | PortfolioCoverageGapActivityItem
  | PortfolioHistoryStartActivityItem;

export type PortfolioAnnotatableActivityItem = Extract<
  PortfolioActivityItem,
  { annotation: PortfolioActivityAnnotation | null }
>;

export function isPortfolioBrokerActivity(
  item: PortfolioActivityItem,
): item is Extract<PortfolioActivityItem, { kind: "order" | "execution" }> {
  return item.kind === "order" || item.kind === "execution";
}

export function isPortfolioAnnotatableActivity(
  item: PortfolioActivityItem,
): item is PortfolioAnnotatableActivityItem {
  return item.kind === "order"
    || item.kind === "execution"
    || item.kind === "unmatched"
    || item.kind === "manual_adjustment";
}

export interface PortfolioActivityFilters {
  date_from_et?: string;
  date_to_et?: string;
  account_id?: number;
  symbol?: string;
  source?: PortfolioActivitySource;
  state?: PortfolioActivityState;
  recent?: boolean;
  limit?: number;
  cursor?: string;
}

export interface PortfolioActivityPage {
  accounts: PortfolioActivityAccount[];
  history_started_at_utc: string | null;
  items: PortfolioActivityItem[];
  summary: {
    item_count: number;
    unmatched_count: number;
    recent_window_days: number | null;
  };
  next_cursor: string | null;
}

export function getPortfolioActivity(
  filters: PortfolioActivityFilters = {},
): Promise<PortfolioActivityPage> {
  const query = new URLSearchParams();
  if (filters.date_from_et) query.set("date_from_et", filters.date_from_et);
  if (filters.date_to_et) query.set("date_to_et", filters.date_to_et);
  if (filters.account_id !== undefined) query.set("account_id", String(filters.account_id));
  if (filters.symbol) query.set("symbol", filters.symbol);
  if (filters.source) query.set("source", filters.source);
  if (filters.state) query.set("state", filters.state);
  if (filters.recent) query.set("recent", "true");
  if (filters.limit !== undefined && filters.limit !== 100) query.set("limit", String(filters.limit));
  if (filters.cursor) query.set("cursor", filters.cursor);
  const suffix = query.size > 0 ? `?${query.toString()}` : "";
  return getJSON<PortfolioActivityPage>(`/portfolio/activity${suffix}`);
}

export function putPortfolioActivityAnnotation(
  activityId: string,
  body: { intent_label: PortfolioIntentLabel | null; note: string },
): Promise<PortfolioActivityAnnotation> {
  return sendJSON<PortfolioActivityAnnotation>(
    `/portfolio/activity/annotations/${encodeURIComponent(activityId)}`,
    "PUT",
    body,
  );
}

export function deletePortfolioActivityAnnotation(
  activityId: string,
): Promise<{ deleted: boolean; activity_id: string }> {
  return sendJSON<{ deleted: boolean; activity_id: string }>(
    `/portfolio/activity/annotations/${encodeURIComponent(activityId)}`,
    "DELETE",
  );
}

export function updatePortfolioPosition(
  positionId: number,
  body: PositionUpdate,
): Promise<PortfolioPosition> {
  return sendJSON<PortfolioPosition>(
    `/portfolio/positions/${encodeURIComponent(positionId)}`,
    "PATCH",
    body,
  );
}

export function closePortfolioPosition(positionId: number): Promise<PortfolioPosition> {
  return sendJSON<PortfolioPosition>(
    `/portfolio/positions/${encodeURIComponent(positionId)}`,
    "DELETE",
  );
}

export function createManualPosition(body: {
  account_id?: number | null;
  symbol: string;
  asset_class?: string;
  quantity: number;
  avg_cost?: number | null;
  currency?: string;
  notes?: string;
}): Promise<PortfolioPosition> {
  return sendJSON<PortfolioPosition>("/portfolio/positions", "POST", body);
}

export function updatePortfolioAccount(
  accountId: number,
  body: {
    label?: string;
    sync_mode?: string;
    base_currency?: string | null;
    include_in_total?: boolean;
    archived?: boolean;
  },
): Promise<PortfolioAccount> {
  return sendJSON<PortfolioAccount>(
    `/portfolio/accounts/${encodeURIComponent(accountId)}`,
    "PATCH",
    body,
  );
}

export function previewIbkrPortfolioSync(): Promise<PortfolioSyncPreview> {
  return sendJSON<PortfolioSyncPreview>("/portfolio/ibkr/preview", "POST", undefined, 30_000);
}

export function applyIbkrPortfolioSync(): Promise<PortfolioSyncPreview> {
  return sendJSON<PortfolioSyncPreview>("/portfolio/ibkr/apply", "POST", undefined, 30_000);
}

export type PortfolioCaptureRunState =
  | "running"
  | "succeeded"
  | "partial"
  | "failed"
  | "blocked"
  | "interrupted";

export interface PortfolioCaptureRun {
  id: number;
  trigger: "startup" | "scheduled" | "manual";
  state: PortfolioCaptureRunState;
  started_at: string;
  finished_at?: string | null;
  account_leg_state: string;
  execution_leg_state: string;
  position_leg_state: string;
  discovered_account_count: number;
  new_account_count: number;
  archived_activity_count: number;
  inserted_execution_count: number;
  inserted_commission_count: number;
  unmatched_count: number;
  data_conflict_count: number;
  error_code?: string | null;
  error_detail?: string | null;
}

export interface PortfolioCaptureReviewChange {
  kind: string;
  account_id?: number | null;
  account_label?: string | null;
  broker_account_id_hash?: string | null;
  broker_con_id: string;
  symbol: string;
  quantity: number;
  before?: Record<string, unknown> | null;
  after?: Record<string, unknown> | null;
}

export interface PortfolioCaptureReview {
  run_id: number;
  changes: PortfolioCaptureReviewChange[];
  applies: boolean;
}

export interface PortfolioCaptureStatus {
  settings: {
    enabled: boolean;
    interval_minutes: number;
    source: "default" | "database";
    provider_configured: boolean;
  };
  provider_issue?: {
    code: "provider_config_missing" | string;
    status: "not_configured" | string;
    provider: "ibkr" | string;
    field: "host" | "port" | string;
  } | null;
  running: boolean;
  next_due_at?: string | null;
  latest_run?: PortfolioCaptureRun | null;
  recent_runs: PortfolioCaptureRun[];
  review?: PortfolioCaptureReview | null;
}

export interface PortfolioCaptureStart {
  accepted: boolean;
  state: PortfolioCaptureRunState;
  run?: PortfolioCaptureRun | null;
  error_code?: string | null;
  error_detail?: string | null;
}

export function getPortfolioCaptureStatus(): Promise<PortfolioCaptureStatus> {
  return getJSON<PortfolioCaptureStatus>("/portfolio/capture");
}

export function updatePortfolioCaptureSettings(body: {
  enabled: boolean;
  interval_minutes: number;
}): Promise<PortfolioCaptureStatus> {
  return sendJSON<PortfolioCaptureStatus>("/portfolio/capture/settings", "PUT", body);
}

export function triggerPortfolioCapture(): Promise<PortfolioCaptureStart> {
  return sendJSON<PortfolioCaptureStart>(
    "/portfolio/capture/runs",
    "POST",
    { trigger: "manual" },
  );
}

export function applyPortfolioCaptureRun(runId: number): Promise<PortfolioCaptureReview> {
  return sendJSON<PortfolioCaptureReview>(
    `/portfolio/capture/runs/${encodeURIComponent(runId)}/apply`,
    "POST",
  );
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

// --- ticker detail: stored fundamentals and local coverage ---
// source_path reports the local source used for the read. local_cache is the
// stored SEC financial-cache projection; file is a file-backed development
// configuration; none means no stored data was available.
export type SourcePath = "local" | "local_cache" | "file" | "none";

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
  fundamentals: boolean;
}

// STORED-ONLY fundamentals with no external SEC/Financial Datasets fetch
// (?stored=true). Opening or refreshing the read-only data tab never contacts a
// provider; the full /fundamentals/{ticker} route remains available to agents.
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

export interface UiLocaleResponse {
  locale: UiLocale;
  source: "default" | "stored";
}

export function getUiLocale(): Promise<UiLocaleResponse> {
  return getJSON<UiLocaleResponse>("/profile/settings/ui-locale");
}

export function setUiLocale(locale: UiLocale): Promise<UiLocaleResponse> {
  return sendJSON<UiLocaleResponse>("/profile/settings/ui-locale", "PUT", { locale });
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

function invalidCardPayload(path: string): never {
  throw new ApiError("Invalid card response", path, 502, "card_payload_invalid", null);
}

function cardResponseObject(value: unknown, path: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return invalidCardPayload(path);
  return value as Record<string, unknown>;
}

function cardExecutionReceipt(row: Record<string, unknown>, path: string): ExecutionReceipt {
  const isText = (value: unknown): value is string => typeof value === "string" && !!value.trim() && !value.includes("\0");
  if (!Object.hasOwn(row, "execution_receipt")) {
    // Older backends expose only these historical fields. Effort/auth stay unknown.
    return {
      provider: isText(row.provider) ? row.provider : null,
      model: isText(row.model) ? row.model : null,
      effort: null,
      auth_mode: null,
    };
  }
  const receipt = cardResponseObject(row.execution_receipt, path);
  const keys = ["provider", "model", "effort", "auth_mode"];
  if (Object.keys(receipt).length !== keys.length || keys.some(key => !Object.hasOwn(receipt, key))) {
    return invalidCardPayload(path);
  }
  for (const key of ["provider", "model", "effort"] as const) {
    if (receipt[key] !== null && !isText(receipt[key])) return invalidCardPayload(path);
  }
  if (receipt.auth_mode !== null && (typeof receipt.auth_mode !== "string"
    || !["api_key", "chatgpt_oauth", "claude_code_oauth"].includes(receipt.auth_mode))) {
    return invalidCardPayload(path);
  }
  return { provider: receipt.provider, model: receipt.model, effort: receipt.effort, auth_mode: receipt.auth_mode } as ExecutionReceipt;
}

function withCardReceipt<T extends CardSummary | GenerateResult>(value: unknown, path: string): T {
  const row = cardResponseObject(value, path);
  return { ...row, execution_receipt: cardExecutionReceipt(row, path) } as unknown as T;
}

export async function getCards(
  ticker?: string,
  limit = 20,
  includeArchived = false,
): Promise<{ cards: CardSummary[] }> {
  const params = new URLSearchParams({ limit: String(limit), include_archived: String(includeArchived) });
  if (ticker) params.set("ticker", ticker);
  const path = `/analysis/cards?${params.toString()}`;
  const response = cardResponseObject(await getJSON<unknown>(path), path);
  if (!Array.isArray(response.cards)) return invalidCardPayload(path);
  return { cards: response.cards.map(row => withCardReceipt<CardSummary>(row, path)) };
}

const FIXED_TASK_COMPAT_TIMEOUT_S = 900;
const FIXED_TASK_BROWSER_MARGIN_S = 60;

export function fixedTaskRequestTimeoutMs(
  runtime: RuntimeConfig | null | undefined,
  task: FixedTaskRuntimeTask,
): number {
  const seconds = runtime?.fixed_task_runtime?.[task]?.model_timeout_s
    ?? FIXED_TASK_COMPAT_TIMEOUT_S;
  return (seconds + FIXED_TASK_BROWSER_MARGIN_S) * 1_000;
}

export async function generateCard(
  ticker: string,
  body: {
    question?: string;
    horizon?: string;
    provider?: string;
    include_sa?: boolean;
    news_days?: number;
    max_news?: number;
    assistant_stance?: AssistantStance;
  } = {},
  runtime?: RuntimeConfig | null,
): Promise<GenerateResult> {
  const path = `/analysis/card/${encodeURIComponent(ticker)}`;
  return withCardReceipt<GenerateResult>(await sendJSON<unknown>(
    path,
    "POST",
    body,
    fixedTaskRequestTimeoutMs(runtime, "card_synthesis"),
  ), path);
}

export async function getCard(runId: number): Promise<CardDetail> {
  const path = `/analysis/cards/${runId}`;
  return withCardReceipt<CardDetail>(await getJSON<unknown>(path), path);
}

export function saveCard(
  runId: number,
): Promise<{ run_id: number; status: string; saved_report_id: number | null }> {
  return sendJSON(`/analysis/cards/${runId}/save`, "POST");
}

// --- market-data local-DB lifecycle (3a prices + 3b news + 3c-A iv/fundamentals) ---

export interface SyncMeta {
  last_success: string | null;
  last_error: string | null;
  rows_added: number;
  updated_at: string | null;
}

export interface NewsProviderSync {
  status: "running" | "succeeded" | "failed" | "partial";
  last_success: string | null;
  last_attempt: string | null;
  last_error: string | null;
  rows_added: number;
  tickers_scanned: number;
  ticker_errors: Array<{ ticker: string; error: string; updated_at: string }>;
}

export interface NewsDirectSync extends SyncMeta {
  status: "running" | "succeeded" | "failed" | "partial";
  last_attempt: string | null;
  providers: Record<string, NewsProviderSync>;
}

export type NewsWriteRoute = "normalized" | "legacy_local" | "blocked";

export interface NewsStatus {
  market_db: string;
  exists: boolean;
  news: { row_count: number; source_count: number; latest_published: string | null };
  normalized_writes_setting: boolean;
  normalized_writes_setting_explicit: boolean;
  normalized_writes_env_override: boolean;
  normalized_writes_env_value: boolean | null;
  write_route: NewsWriteRoute;
  write_route_reason: string;
  sync: NewsDirectSync | null;
}

// Fundamentals are date-keyed snapshots, so latest is date-only (no time).
export interface MarketDataStatus {
  market_db: string;
  exists: boolean;
  prices: { row_count: number; ticker_count: number; latest_datetime: string | null };
  news: { row_count: number; source_count: number; latest_published: string | null };
  fundamentals: { row_count: number; ticker_count: number; latest_date: string | null };
  // Local cache validity and latest fetch time.
  financial_cache: {
    row_count: number;
    valid_count: number;
    expired_count: number;
    latest_fetched_at: string | null;
  };
  sync: {
    prices: SyncMeta | null;
    news: SyncMeta | null;
    fundamentals: SyncMeta | null;
  };
  prices_authority: "local";
  fundamentals_mode: "local_cache_refetch";
  use_local_market_setting: boolean;
  env_override: boolean;
  local_market_strict_setting: boolean;
  strict_env_override: boolean;
  strict_enabled: boolean;
  routing_enabled: boolean;
}

export function getMarketDataStatus(): Promise<MarketDataStatus> {
  return getJSON<MarketDataStatus>("/market-data/status");
}

export type SecurityLifecycleEventType =
  | "merger_agreement"
  | "merger_proxy"
  | "acquisition_completed"
  | "listing_status_review"
  | "listing_removal_notice";
export type SecurityLifecycleSourcePresence = "present" | "source_missing";
export type SecurityLifecycleWorkflowState =
  | "unresolved"
  | "investigating"
  | "evidence_ready"
  | "reviewed_inconclusive"
  | "resolved";
export type SecurityLifecycleRelevance =
  | "undetermined"
  | "direct_tracked_security"
  | "issuer_related"
  | "unrelated";
export type SecurityLifecycleConfidence = "unknown" | "low" | "medium" | "high";
export type SecurityLifecycleAssessmentOutcome =
  | "undetermined"
  | "listing_ended"
  | "venue_transfer"
  | "symbol_changed"
  | "acquisition_cash"
  | "acquisition_stock"
  | "acquisition_mixed"
  | "acquisition_terms_unknown"
  | "issuer_security_change"
  | "no_tracked_security_change"
  | "other"
  | "not_applicable";
export type SecurityLifecycleOutcome =
  | SecurityLifecycleAssessmentOutcome
  | "symbol_or_venue_changed";
export type SecurityLifecycleProposalType =
  | "archive_manual_memberships"
  | "hide_from_active_universe"
  | "keep_tracking"
  | "no_action"
  | "notify"
  | "remap_symbol"
  | "review_portfolio_position";
export type SecurityLifecycleTrackingSource =
  | "manual_lists"
  | "portfolio_open"
  | "sa_alpha_picks_current"
  | "sa_alpha_picks_former"
  | "legacy_config_seed";
export type SecurityLifecycleSecAdmissionState =
  | "pending"
  | "admitted"
  | "screened_out"
  | "needs_review";
export type SecurityLifecycleSecAdmissionReason =
  | "awaiting_regulator_screening"
  | "direct_listing_item"
  | "direct_identity_filing"
  | "material_tracked_security_fact"
  | "no_material_tracked_security_fact"
  | "identity_binding_missing"
  | "regulator_screening_incomplete"
  | "regulator_monitor_only"
  | "unknown_form";
export type SecurityLifecycleProposalStatus = "proposed" | "dismissed";
export type SecurityLifecycleProposalBlockReason =
  | "portfolio_position_open"
  | "successor_evidence_missing"
  | "source_context_unavailable"
  | "stale_assessment"
  | "action_executor_not_available";
export type SecurityLifecycleInvestigationStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled";
export type SecurityLifecycleInvestigationFailureCode =
  | "adapter_unavailable"
  | "credential_missing"
  | "permission_denied"
  | "rate_limited"
  | "usage_limit_reached"
  | "network_error"
  | "extract_failed"
  | "unsupported_content";
export type SecurityLifecycleDecisionTier =
  | "verified_automatic"
  | "review_suggested";
export type SecurityLifecycleActionReadiness =
  | "not_applicable"
  | "waiting_effective_date"
  | "waiting_market_confirmation"
  | "waiting_transition_revalidation"
  | "transition_eligible"
  | "action_blocked";
export type SecurityLifecycleDisposition =
  | "confirmed_monitoring"
  | "confirmed_effective"
  | "not_confirmed_yet"
  | "exception_required";
export type SecurityLifecycleQueueBucket =
  | "attention"
  | "monitoring"
  | "history";
export type SecurityLifecycleSourceFamilyState =
  | "confirmed"
  | "present"
  | "missing"
  | "unavailable"
  | "conflict";
export type SecurityLifecycleDispositionReason =
  | "awaiting_initial_automation"
  | "automation_running"
  | "waiting_effective_date"
  | "waiting_market_confirmation"
  | "waiting_transition_revalidation"
  | "retryable_source_unavailable"
  | "event_completion_not_confirmed"
  | "not_confirmed_as_of"
  | "source_missing"
  | "source_conflict"
  | "ambiguous_event"
  | "nonretryable_provider_failure"
  | "automation_failure"
  | "automation_finalization_failure"
  | "resolved_no_change"
  | "resolved_assessment"
  | "transition_applied"
  | "transition_reversed"
  | "transition_cancelled"
  | "transition_needs_review"
  | "reviewed_inconclusive";
export type SecurityLifecycleAssessmentAuthor =
  | "human"
  | "legacy_review"
  | "automation";
export type SecurityLifecycleAutomationMethod =
  | "deterministic_rule"
  | "model_assisted";
export type SecurityLifecycleAcceptanceAuthority =
  | "human"
  | "automation_policy"
  | "legacy_migration";
export type SecurityLifecycleEvidenceSourceFamily =
  | "regulator"
  | "listing_authority"
  | "market_infrastructure"
  | "publisher"
  | "general_web"
  | "manual";
export type SecurityLifecycleListingAuthority = "nasdaq_trader" | "massive" | "eodhd";
export type SecurityLifecycleListingStatus =
  | "active"
  | "inactive"
  | "not_found"
  | "unverified";
export type SecurityLifecycleAutomationMode = "live" | "historical";
export type SecurityLifecycleAutomationRunStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "blocked"
  | "failed"
  | "cancelled";
export type SecurityLifecycleAutomationBlockerCode =
  | "sec_identity_unconfigured"
  | "sec_governor_unavailable"
  | "sec_request_budget_exhausted"
  | "sec_rate_limited"
  | "sec_access_denied"
  | "sec_transport_unavailable"
  | "sec_document_unavailable"
  | "sec_evidence_insufficient"
  | "internal_news_unavailable"
  | "internal_news_schema_mismatch"
  | "ibkr_gateway_unavailable"
  | "ibkr_contract_missing"
  | "ibkr_contract_ambiguous"
  | "ibkr_entitlement_denied"
  | "market_confirmation_missing"
  | "listing_directory_unavailable"
  | "listing_directory_schema_mismatch"
  | "listing_directory_stale"
  | "listing_status_unresolved"
  | "listing_authority_conflict"
  | "massive_credential_missing"
  | "massive_access_denied"
  | "massive_rate_limited"
  | "massive_reference_unavailable"
  | "source_conflict"
  | "impact_context_requested"
  | "transition_approval_changed"
  | "transition_approval_unavailable";
export interface SecurityLifecycleCandidateBudgetExceededOperatorDetail {
  code: "candidate_budget_exceeded";
  candidate_count: number;
  query_limit: number;
  provider_contacted: false;
}
export type SecurityLifecycleAutomationOperatorDetail =
  SecurityLifecycleCandidateBudgetExceededOperatorDetail | SecurityLifecycleListingOperatorDetail;
export interface SecurityLifecycleListingOperatorDetail {
  code: "listing_checks";
  missing_checks: Array<typeof LISTING_CHECK_NAMES[number]>;
  provider_issues: Array<{ provider: typeof LISTING_PROVIDER_NAMES[number]; reason: typeof LISTING_PROVIDER_ISSUES[number] }>;
  manual_review_required: boolean;
}
export type SecurityLifecycleFactType =
  | "source_ticker"
  | "successor_ticker"
  | "source_venue"
  | "destination_venue"
  | "effective_date"
  | "security_class"
  | "issuer_cik"
  | "transaction_structure"
  | "tracked_security_effect";

export interface SecurityLifecycleObservationKind {
  event_type: SecurityLifecycleEventType;
  effective_date: string | null;
}

export const ALPHA_TRACKING_REASONS = [
  "current_observed", "bootstrap_accepted", "capture_gap", "identity_ambiguous", "related_security",
  "user_removed", "user_restored", "user_accepted", "terminal_delisting",
] as const;
export interface AlphaTrackingMembership {
  membership_id: string;
  ticker: string;
  picked_date: string;
  portfolio_status: "current" | "closed";
  state: "tracking" | "removed" | "candidate";
  reason: typeof ALPHA_TRACKING_REASONS[number];
  accepted_at: string | null;
  removed_at: string | null;
}
export interface AlphaTrackingResponse {
  available: boolean;
  memberships: AlphaTrackingMembership[];
  sync_status: "current" | "pending" | "unavailable";
}

export function parseAlphaTracking(value: unknown): AlphaTrackingResponse {
  const row = lifecycleCaseRecord(value);
  if (typeof row.available !== "boolean") throw new Error("invalid_tracking_payload");
  const memberships = lifecycleCaseArray(row.memberships).map((raw): AlphaTrackingMembership => {
    const item = lifecycleCaseRecord(raw);
    return {
      membership_id: lifecycleCaseString(item.membership_id), ticker: lifecycleCaseString(item.ticker),
      picked_date: lifecycleCaseString(item.picked_date),
      portfolio_status: lifecycleCaseEnum(item.portfolio_status, ["current", "closed"] as const),
      state: lifecycleCaseEnum(item.state, ["tracking", "removed", "candidate"] as const),
      reason: lifecycleCaseEnum(item.reason, ALPHA_TRACKING_REASONS),
      accepted_at: lifecycleCaseNullableString(item.accepted_at), removed_at: lifecycleCaseNullableString(item.removed_at),
    };
  });
  if (!row.available && memberships.length) throw new Error("invalid_tracking_payload");
  return {
    available: row.available, memberships,
    sync_status: row.sync_status === undefined ? "unavailable" : lifecycleCaseEnum(row.sync_status, ["current", "pending", "unavailable"] as const),
  };
}

export async function getAlphaTracking(): Promise<AlphaTrackingResponse> {
  return parseAlphaTracking(await getJSON<unknown>("/profile/alpha-picks-tracking"));
}
export async function refreshAlphaTracking(): Promise<AlphaTrackingResponse> {
  return parseAlphaTracking(await sendJSON<unknown>("/profile/alpha-picks-tracking/refresh", "POST", {}));
}
export async function commandAlphaTracking(membershipId: string, action: "remove" | "restore" | "accept"): Promise<void> {
  await sendJSON(`/profile/alpha-picks-tracking/${encodeURIComponent(membershipId)}`, "POST", { action });
}

export interface SecurityLifecycleObservation {
  ticker: string;
  cik: string | null;
  issuer_name: string;
  filing_date: string;
  source: string;
  source_ref: string;
  filing_form: string;
  filing_items: string[];
  evidence_url: string;
  description: string;
  first_observed_at: string;
  last_observed_at: string;
  kinds: SecurityLifecycleObservationKind[];
}

export interface SecurityLifecycleAssessment {
  assessment_id: string;
  status: "draft" | "accepted" | "superseded";
  author: SecurityLifecycleAssessmentAuthor;
  automation_method?: SecurityLifecycleAutomationMethod | null;
  automation_narrative?: SecurityLifecycleAutomationNarrative | null;
  acceptance_authority?: SecurityLifecycleAcceptanceAuthority | null;
  automation_run_id?: string | null;
  rule_id?: string | null;
  rule_version?: string | null;
  decision_provenance_sha256?: string | null;
  relevance: SecurityLifecycleRelevance;
  confidence: SecurityLifecycleConfidence;
  conclusion: string;
  impact_summary: string;
  outcomes: SecurityLifecycleOutcome[];
  stale: boolean;
  created_at: string;
  consideration_currency?: string | null;
  cash_per_security_decimal?: string | null;
  exchange_ratio_decimal?: string | null;
  successor_ticker?: string | null;
  destination_venue?: string | null;
  counterparty_name?: string | null;
  counterparty_ticker?: string | null;
  counterparty_cik?: string | null;
  effective_date?: string | null;
  citations?: Array<{
    reference_kind: "observation" | "evidence";
    evidence_id: string | null;
    cited_content_sha256: string;
  }>;
}

export type SecurityLifecycleAutomationNarrative =
  | "terminalDelisting"
  | "noIdentityChange"
  | "simpleSymbolContinuation"
  | "venueTransfer"
  | "maReview"
  | "sourceConflict"
  | "insufficientIdentityFacts"
  | "unknownRule";

export interface SecurityLifecycleAcknowledgement {
  acknowledgement_id: string;
  reason: "evidence_insufficient";
  note: string | null;
  stale: boolean;
  acknowledged_at: string;
  reopened_at: string | null;
}

export interface SecurityLifecycleInvestigationRun {
  run_id: string;
  status: SecurityLifecycleInvestigationStatus;
  result_count: number;
  failure_code: SecurityLifecycleInvestigationFailureCode | null;
  created_at: string;
}

export interface SecurityLifecycleAutomationRun {
  run_id: string;
  case_id: string;
  mode: SecurityLifecycleAutomationMode;
  status: SecurityLifecycleAutomationRunStatus;
  policy_version: string;
  decision_tier: SecurityLifecycleDecisionTier | null;
  action_readiness: SecurityLifecycleActionReadiness | null;
  failure_code: string | null;
  blockers: Array<{
    blocker_code: SecurityLifecycleAutomationBlockerCode;
    retryable: boolean;
    operator_detail?: SecurityLifecycleAutomationOperatorDetail;
  }>;
  retry_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  created_at: string;
  updated_at?: string;
  terminal_finalization_failure?: {
    attempt_count: number;
    code: "finalization_failed";
    failed_at: string;
    retry_not_before: string | null;
  };
}

export interface SecurityLifecycleActionProposal {
  proposal_id: string;
  action_type: SecurityLifecycleProposalType;
  status: SecurityLifecycleProposalStatus;
  projected_block_reason: SecurityLifecycleProposalBlockReason | null;
  replacement_ticker: string | null;
}

export interface SecurityLifecycleSecAdmission {
  state: SecurityLifecycleSecAdmissionState;
  reason: SecurityLifecycleSecAdmissionReason;
}

export interface SecurityLifecycleSecCandidate {
  case_id: string;
  ticker: string;
  issuer_name: string;
  filing_form: string;
  filing_items: string[];
  filing_date: string;
  evidence_url: string;
  admission_state: SecurityLifecycleSecAdmissionState;
  admission_reason: SecurityLifecycleSecAdmissionReason;
}

export interface SecurityLifecycleSecCandidateResponse {
  candidates: SecurityLifecycleSecCandidate[];
  count: number;
  state_counts: Record<SecurityLifecycleSecAdmissionState, number>;
}

export type TickerIdentityTransitionKind =
  | "symbol_continuation"
  | "terminal_delisting";
export type TickerIdentityTransitionStatus =
  | "approved"
  | "needs_review"
  | "applied"
  | "cancelled"
  | "reversed";
export type TickerIdentityTransitionBlockReason =
  | "listing_authority_required"
  | "provider_listing_check_required"
  | "provider_listing_check_stale"
  | "provider_listing_check_changed"
  | "provider_terminal_not_confirmed"
  | "provider_legacy_event_review"
  | "provider_continuation_review"
  | "successor_missing"
  | "successor_not_distinct"
  | "outcome_not_executable"
  | "assessment_case_mismatch"
  | "assessment_not_accepted"
  | "assessment_not_direct"
  | "stale_assessment"
  | "observation_citation_required"
  | "execution_date_required"
  | "execution_date_invalid"
  | "source_context_unavailable"
  | "no_active_tracking_source"
  | "remap_proposal_missing"
  | "proposal_missing"
  | "priority_resolution_required"
  | "successor_hidden"
  | "portfolio_position_open"
  | "preview_changed"
  | "reverse_state_changed"
  | "successor_has_later_transition";
export type TickerIdentityTransitionCaveat =
  | "provider_owned_sources_retained"
  | "portfolio_position_retained"
  | "successor_already_tracked";
export type TickerIdentityPriorityResolution = "source" | "successor";
export type TickerIdentityTransitionApprovalAuthority =
  | "attended_user"
  | "automation_policy";
export type TickerIdentityTransitionActivityType = "applied" | "reversed";
export type TickerIdentityTransitionActivityChangeType =
  | "sa_membership_suppressed"
  | "editable_tag_copied"
  | "legacy_membership_added"
  | "legacy_membership_archived"
  | "legacy_membership_reactivated"
  | "priority_updated"
  | "source_hidden"
  | "successor_unhidden"
  | "watchlist_membership_added"
  | "watchlist_membership_archived"
  | "watchlist_membership_reactivated";

export interface TickerIdentityReverseReadiness {
  reversible: boolean;
  block_reasons: TickerIdentityTransitionBlockReason[];
}

export interface TickerIdentityHistoryDecision {
  summary: string | null;
  impact: string | null;
  method: "provider_review" | "manual_review" | "rule_engine" | "llm_investigation" | "unknown";
  approval_authority: "attended_user" | "automation_policy";
  event_date: string | null;
  observed_at: string | null;
  model: { provider: "openai" | "anthropic"; auth_mode: "api_key" | "chatgpt_oauth" | "claude_code_oauth"; model: string } | null;
  sources: Array<{
    name: string | null; url: string | null; title: string | null;
    published_at: string | null; observed_at: string | null;
    kind: "listing_snapshot" | "ticker_events" | "document" | "local_news" | "manual";
    ticker: string | null; listing_status: "active" | "inactive" | "not_found" | "unverified" | null; market: string | null;
  }>;
  limitations: string[];
  source_gaps: Array<{ url: string | null; reason: string }>;
  gaps: Array<"assessment_missing" | "record_invalid" | "sources_missing" | "model_missing" | "source_link_omitted" | "legacy_assessment_unsealed">;
}

export interface TickerIdentityTransitionActivity {
  activity_id: string;
  transition_id: string;
  case_id: string;
  activity_type: TickerIdentityTransitionActivityType;
  source_ticker: string;
  successor_ticker: string | null;
  effective_date: string;
  user_owned_changes: Array<{
    change_type: TickerIdentityTransitionActivityChangeType;
    count: number;
  }>;
  provider_owned_retained: string[];
  state_sha256: string;
  rule_id: string | null;
  rule_version: string | null;
  decision_provenance_sha256: string;
  occurred_at: string;
  acknowledged_at: string | null;
  created_at: string;
  reverse_readiness?: TickerIdentityReverseReadiness | null;
  decision?: TickerIdentityHistoryDecision;
}

export interface TickerIdentityTransitionActivityResponse {
  items: TickerIdentityTransitionActivity[];
  count: number;
  unacknowledged_count: number;
}

export interface TickerIdentityWatchlistEffect {
  list_id: number;
  list_name: string;
  position: number;
  ticker: string;
}

export interface TickerIdentityLegacySeedEffect {
  source_key: "legacy_config_seed";
  ticker: string;
}

export interface TickerIdentityEditableTagEffect {
  facet: string;
  source: string;
  ticker: string;
  value: string;
}

export interface TickerIdentityTransitionPreview {
  active_sources: SecurityLifecycleTrackingSource[];
  assessment_fingerprint_sha256: string;
  assessment_id: string;
  block_reasons: TickerIdentityTransitionBlockReason[];
  case_id: string;
  caveats: TickerIdentityTransitionCaveat[];
  effects: {
    sa_tracking_memberships?: Array<{ membership_id: string; ticker: string; picked_date: string; portfolio_status: "current" | "closed" }>;
    editable_tags_to_copy: TickerIdentityEditableTagEffect[];
    legacy_config_seed: Record<
      "add" | "archive" | "reactivate" | "unchanged",
      TickerIdentityLegacySeedEffect[]
    >;
    priority: {
      resolution: TickerIdentityPriorityResolution | null;
      result_value: string | null;
      source_value: string | null;
      successor_value: string | null;
      write_successor: boolean;
    };
    suppression: {
      hide_source: boolean;
      source_hidden: boolean;
      successor_hidden: boolean;
      unhide_successor: boolean;
    };
    watchlists: Record<
      "add" | "archive" | "reactivate" | "unchanged",
      TickerIdentityWatchlistEffect[]
    >;
  };
  eligible: boolean;
  evidence_set_sha256: string;
  execute_on: string | null;
  observation_fingerprint_sha256: string;
  outcomes: SecurityLifecycleOutcome[];
  preview_sha256: string;
  profile_state_sha256: string;
  proposal_ids: string[];
  provider_owned_sources: string[];
  source_ticker: string;
  successor_ticker: string | null;
  transition_kind: TickerIdentityTransitionKind | null;
}

export interface TickerIdentityTransitionState {
  transition_id: string;
  kind: TickerIdentityTransitionKind;
  status: TickerIdentityTransitionStatus;
  source_ticker: string;
  successor_ticker: string | null;
  execute_on: string;
  approved_preview_sha256: string;
  approved_preview: TickerIdentityTransitionPreview;
  approval_authority: TickerIdentityTransitionApprovalAuthority;
  automation_policy_version: string | null;
  rule_id: string | null;
  rule_version: string | null;
  decision_provenance_sha256: string;
  updated_at: string;
  latest_attempt: {
    status: "blocked" | "applied" | "already_applied" | "reversed";
    block_reasons: string[];
    attempted_at: string;
  } | null;
  reverse_readiness: TickerIdentityReverseReadiness | null;
  activity_history: TickerIdentityTransitionActivity[];
  activity_count: number;
  unacknowledged_activity_count: number;
}

export interface TickerIdentityTransitionRecord {
  transition_id: string;
  kind: TickerIdentityTransitionKind;
  status: TickerIdentityTransitionStatus;
  source_ticker: string;
  successor_ticker: string | null;
  execute_on: string;
  approved_preview_sha256: string;
  updated_at: string;
}

export interface TickerIdentityTransitionAttemptResult {
  status: "blocked" | "applied" | "already_applied" | "reversed";
  block_reasons: string[];
  transition: TickerIdentityTransitionRecord;
}

export interface SecurityLifecycleCaseSummary {
  case_id: string;
  source: string;
  source_ref: string;
  ticker: string;
  source_presence: SecurityLifecycleSourcePresence;
  workflow_state: SecurityLifecycleWorkflowState;
  issuer_name: string | null;
  filing_date: string | null;
  kinds: SecurityLifecycleObservationKind[];
  current_assessment: SecurityLifecycleAssessment | null;
  current_acknowledgement: SecurityLifecycleAcknowledgement | null;
  active_sources: SecurityLifecycleTrackingSource[];
  source_context: "available" | "unavailable";
  components: Record<string, unknown>;
  investigation_run_count: number;
  automation_run_count: number;
  automation_fact_count: number;
  automation_tier: SecurityLifecycleDecisionTier | null;
  action_readiness: SecurityLifecycleActionReadiness | null;
  disposition: SecurityLifecycleDisposition;
  queue_bucket: SecurityLifecycleQueueBucket;
  disposition_reason: SecurityLifecycleDispositionReason;
  disposition_as_of: string | null;
  last_checked_at: string | null;
  next_check_at: string | null;
  source_family_status: Partial<
    Record<SecurityLifecycleEvidenceSourceFamily, SecurityLifecycleSourceFamilyState>
  >;
  evidence_count: number;
  assessment_count: number;
  acknowledgement_count: number;
  proposal_count: number;
  sec_admission?: SecurityLifecycleSecAdmission | null;
}

export interface SecurityLifecyclePrimaryObservation {
  ticker: string;
  issuer_name: string;
  filing_date: string;
  filing_form: string;
  filing_items: string[];
  evidence_url: string;
  kinds: SecurityLifecycleObservationKind[];
}

export interface SecurityLifecycleListingCorroboration {
  listing_status: SecurityLifecycleListingStatus;
  source_as_of: string;
  provider_last_updated_utc: string | null;
}

export interface SecurityLifecycleCorroboration {
  regulator: SecurityLifecycleSourceFamilyState | null;
  nasdaq_trader: SecurityLifecycleListingCorroboration | null;
  massive: SecurityLifecycleListingCorroboration | null;
  eodhd?: SecurityLifecycleListingCorroboration | null;
  ibkr: SecurityLifecycleSourceFamilyState | null;
}

export interface SecurityLifecycleCaseDetail {
  case_id: string;
  ticker: string;
  source_presence: SecurityLifecycleSourcePresence;
  workflow_state: SecurityLifecycleWorkflowState;
  issuer_name: string | null;
  filing_date: string | null;
  kinds: SecurityLifecycleObservationKind[];
  current_assessment: SecurityLifecycleAssessment | null;
  current_acknowledgement: SecurityLifecycleAcknowledgement | null;
  active_sources: SecurityLifecycleTrackingSource[];
  source_context: "available" | "unavailable";
  automation_tier: SecurityLifecycleDecisionTier | null;
  action_readiness: SecurityLifecycleActionReadiness | null;
  disposition: SecurityLifecycleDisposition;
  queue_bucket: SecurityLifecycleQueueBucket;
  disposition_reason: SecurityLifecycleDispositionReason;
  disposition_as_of: string | null;
  last_checked_at: string | null;
  next_check_at: string | null;
  source_family_status: Partial<
    Record<SecurityLifecycleEvidenceSourceFamily, SecurityLifecycleSourceFamilyState>
  >;
  sec_admission: SecurityLifecycleSecAdmission | null;
  observation: SecurityLifecyclePrimaryObservation | null;
  corroboration: SecurityLifecycleCorroboration;
  current_blockers?: SecurityLifecycleAutomationRun["blockers"];
  proposals: SecurityLifecycleActionProposal[];
  ticker_transition: TickerIdentityTransitionState | null;
}

export interface SecurityLifecycleCaseListResponse {
  cases: SecurityLifecycleCaseSummary[];
  count: number;
  queue_counts: Record<SecurityLifecycleQueueBucket, number>;
  admission_counts: Record<SecurityLifecycleSecAdmissionState, number>;
  data_integrity: { source_missing_count: number };
}

export interface SecurityLifecycleAutomationConfig {
  enabled: boolean;
  interval_minutes: number;
  batch_limit: 1 | 2;
  apply_profile_transitions: boolean;
}

export type SecurityLifecycleAutomationStage =
  | "preparing"
  | "sec"
  | "listing"
  | "ibkr"
  | "evaluate"
  | "persist"
  | "approve"
  | "finalize";
export type SecurityLifecycleAutomationTrigger =
  | "scheduler"
  | "manual_due"
  | "manual_case";
export type SecurityLifecycleAutomationScheduleStatus =
  | "invalid"
  | "disabled"
  | "due"
  | "scheduled";
export type SecurityLifecycleAutomationSchedulerStatus =
  | "running"
  | "failed"
  | "succeeded"
  | "partial"
  | "unavailable"
  | "not_installed"
  | "skipped";
export type SecurityLifecycleAutomationResultStatus = Exclude<
  SecurityLifecycleAutomationSchedulerStatus,
  "running" | "failed"
>;
export type SecurityLifecycleAutomationCaseOutcome =
  | "accepted"
  | "drafted"
  | "blocked"
  | "failed"
  | "skipped_current";
export type SecurityLifecycleAutomationFailureReason =
  | "already_running"
  | "automation_schema_absent"
  | "case_processing_blocked"
  | "case_processing_failed"
  | "market_store_unavailable"
  | "profile_schema_mismatch"
  | "profile_store_unavailable"
  | "automation_scheduler_failed"
  | "execution_lock_unavailable"
  | "provider_scan_budget_unavailable";

export interface SecurityLifecycleAutomationResult {
  status: SecurityLifecycleAutomationResultStatus;
  reason: SecurityLifecycleAutomationFailureReason | null;
  selected: number;
  processed: number;
  accepted: number;
  drafted: number;
  blocked: number;
  failed: number;
  skipped_current: number;
  case_ids: string[];
  result_version?: 2;
  case_outcomes?: Record<string, SecurityLifecycleAutomationCaseOutcome>;
}

export interface SecurityLifecycleAutomationProgress {
  trigger: SecurityLifecycleAutomationTrigger;
  request_id: string;
  case_id: string;
  started_at: string;
  current_stage: SecurityLifecycleAutomationStage | null;
  completed_stages: SecurityLifecycleAutomationStage[];
  skipped_stages: SecurityLifecycleAutomationStage[];
}

export interface SecurityLifecycleAutomationIncident {
  case_failures: Record<string, {
    run_id: string | null;
    recovery: "new_attempt" | "finalization";
  }>;
  scheduler_failure: {
    reason: SecurityLifecycleAutomationFailureReason;
  } | null;
}

export interface SecurityLifecycleAutomationFailedRun {
  run_id: string;
  case_id: string;
  failure_code: string;
  started_at: string;
  finished_at: string;
  updated_at: string;
}

export type SecurityLifecycleAutomationConfigResponse =
  | {
    config_status: "valid";
    config: SecurityLifecycleAutomationConfig;
  }
  | {
    config_status: "invalid";
    config: null;
    invalid_keys: string[];
  };

export type SecurityLifecycleAutomationStatusResponse =
  SecurityLifecycleAutomationConfigResponse & {
    schedule: {
      status: SecurityLifecycleAutomationScheduleStatus;
      last_attempt_at: string | null;
      next_scheduled_at: string | null;
    };
    telemetry_status: "absent" | "valid" | "invalid";
    last_status: SecurityLifecycleAutomationSchedulerStatus | null;
    last_result: SecurityLifecycleAutomationResult | null;
    active_incident: SecurityLifecycleAutomationIncident | null;
    latest_failed_runs: SecurityLifecycleAutomationFailedRun[];
    current_progress: SecurityLifecycleAutomationProgress[];
  };

export interface SecurityLifecycleAutomationDispatchResponse {
  scope: "due" | "case";
  status: "started" | "skipped" | "unavailable" | "not_installed";
  reason?: SecurityLifecycleAutomationFailureReason;
  request_id?: string;
  case_id?: string;
}

const AUTOMATION_STAGES: readonly SecurityLifecycleAutomationStage[] = [
  "preparing", "sec", "listing", "ibkr", "evaluate", "persist", "approve", "finalize",
];
const AUTOMATION_TRIGGERS: readonly SecurityLifecycleAutomationTrigger[] = [
  "scheduler", "manual_due", "manual_case",
];
const AUTOMATION_REASONS: readonly SecurityLifecycleAutomationFailureReason[] = [
  "already_running",
  "automation_schema_absent",
  "case_processing_blocked",
  "case_processing_failed",
  "market_store_unavailable",
  "profile_schema_mismatch",
  "profile_store_unavailable",
  "automation_scheduler_failed",
  "execution_lock_unavailable",
  "provider_scan_budget_unavailable",
];

function automationContractError(): never {
  throw new Error("security_lifecycle_automation_contract");
}

function automationRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return automationContractError();
  }
  return value as Record<string, unknown>;
}

function automationString(value: unknown): string {
  if (typeof value !== "string" || !value || value.includes("\0")) {
    return automationContractError();
  }
  return value;
}

function automationNullableString(value: unknown): string | null {
  return value === null ? null : automationString(value);
}

function automationEnum<Value extends string>(
  value: unknown,
  allowed: readonly Value[],
): Value {
  if (typeof value !== "string" || !allowed.includes(value as Value)) {
    return automationContractError();
  }
  return value as Value;
}

function automationCount(value: unknown): number {
  if (!Number.isInteger(value) || (value as number) < 0) return automationContractError();
  return value as number;
}

function automationStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return automationContractError();
  return value.map(automationString);
}

function automationStageArray(value: unknown): SecurityLifecycleAutomationStage[] {
  if (!Array.isArray(value)) return automationContractError();
  return value.map((item) => automationEnum(item, AUTOMATION_STAGES));
}

function parseAutomationConfig(value: unknown): SecurityLifecycleAutomationConfig {
  const row = automationRecord(value);
  if (
    typeof row.enabled !== "boolean"
    || !Number.isInteger(row.interval_minutes)
    || (row.interval_minutes as number) < 5
    || (row.interval_minutes as number) > 10_080
    || (row.batch_limit !== 1 && row.batch_limit !== 2)
    || typeof row.apply_profile_transitions !== "boolean"
  ) {
    return automationContractError();
  }
  return {
    enabled: row.enabled,
    interval_minutes: row.interval_minutes as number,
    batch_limit: row.batch_limit,
    apply_profile_transitions: row.apply_profile_transitions,
  };
}

function parseAutomationConfigResponse(
  value: unknown,
): SecurityLifecycleAutomationConfigResponse {
  const row = automationRecord(value);
  const status = automationEnum(row.config_status, ["valid", "invalid"] as const);
  if (status === "valid") {
    return { config_status: status, config: parseAutomationConfig(row.config) };
  }
  if (row.config !== null || !Array.isArray(row.invalid_keys)) {
    return automationContractError();
  }
  return {
    config_status: status,
    config: null,
    invalid_keys: row.invalid_keys.map(automationString),
  };
}

function parseAutomationResult(value: unknown): SecurityLifecycleAutomationResult {
  const row = automationRecord(value);
  const result: SecurityLifecycleAutomationResult = {
    status: automationEnum(
      row.status,
      ["succeeded", "partial", "unavailable", "not_installed", "skipped"] as const,
    ),
    reason: row.reason === null ? null : automationEnum(row.reason, AUTOMATION_REASONS),
    selected: automationCount(row.selected),
    processed: automationCount(row.processed),
    accepted: automationCount(row.accepted),
    drafted: automationCount(row.drafted),
    blocked: automationCount(row.blocked),
    failed: automationCount(row.failed),
    skipped_current: automationCount(row.skipped_current),
    case_ids: automationStringArray(row.case_ids),
  };
  if (row.result_version !== undefined || row.case_outcomes !== undefined) {
    if (row.result_version !== 2) return automationContractError();
    const rawOutcomes = automationRecord(row.case_outcomes);
    result.result_version = 2;
    result.case_outcomes = Object.fromEntries(Object.entries(rawOutcomes).map(
      ([caseId, outcome]) => [
        automationString(caseId),
        automationEnum(
          outcome,
          ["accepted", "drafted", "blocked", "failed", "skipped_current"] as const,
        ),
      ],
    ));
  }
  return result;
}

function parseAutomationIncident(value: unknown): SecurityLifecycleAutomationIncident | null {
  if (value === null) return null;
  const row = automationRecord(value);
  const rawFailures = automationRecord(row.case_failures);
  const caseFailures = Object.fromEntries(Object.entries(rawFailures).map(([caseId, marker]) => {
    const detail = automationRecord(marker);
    return [automationString(caseId), {
      run_id: automationNullableString(detail.run_id),
      recovery: automationEnum(detail.recovery, ["new_attempt", "finalization"] as const),
    }];
  }));
  let schedulerFailure: SecurityLifecycleAutomationIncident["scheduler_failure"] = null;
  if (row.scheduler_failure !== null) {
    const detail = automationRecord(row.scheduler_failure);
    schedulerFailure = { reason: automationEnum(detail.reason, AUTOMATION_REASONS) };
  }
  return { case_failures: caseFailures, scheduler_failure: schedulerFailure };
}

function parseAutomationStatus(value: unknown): SecurityLifecycleAutomationStatusResponse {
  const row = automationRecord(value);
  const config = parseAutomationConfigResponse(row);
  const schedule = automationRecord(row.schedule);
  const progress = row.current_progress;
  const failedRuns = row.latest_failed_runs;
  if (!Array.isArray(progress) || !Array.isArray(failedRuns)) return automationContractError();
  return {
    ...config,
    schedule: {
      status: automationEnum(schedule.status, ["invalid", "disabled", "due", "scheduled"] as const),
      last_attempt_at: automationNullableString(schedule.last_attempt_at),
      next_scheduled_at: automationNullableString(schedule.next_scheduled_at),
    },
    telemetry_status: automationEnum(row.telemetry_status, ["absent", "valid", "invalid"] as const),
    last_status: row.last_status === null
      ? null
      : automationEnum(
        row.last_status,
        ["running", "failed", "succeeded", "partial", "unavailable", "not_installed", "skipped"] as const,
      ),
    last_result: row.last_result === null ? null : parseAutomationResult(row.last_result),
    active_incident: parseAutomationIncident(row.active_incident),
    latest_failed_runs: failedRuns.map((item) => {
      const detail = automationRecord(item);
      return {
        run_id: automationString(detail.run_id),
        case_id: automationString(detail.case_id),
        failure_code: automationString(detail.failure_code),
        started_at: automationString(detail.started_at),
        finished_at: automationString(detail.finished_at),
        updated_at: automationString(detail.updated_at),
      };
    }),
    current_progress: progress.map((item) => {
      const detail = automationRecord(item);
      return {
        trigger: automationEnum(detail.trigger, AUTOMATION_TRIGGERS),
        request_id: automationString(detail.request_id),
        case_id: automationString(detail.case_id),
        started_at: automationString(detail.started_at),
        current_stage: detail.current_stage === null
          ? null
          : automationEnum(detail.current_stage, AUTOMATION_STAGES),
        completed_stages: automationStageArray(detail.completed_stages),
        skipped_stages: automationStageArray(detail.skipped_stages),
      };
    }),
  };
}

function parseAutomationDispatch(
  value: unknown,
): SecurityLifecycleAutomationDispatchResponse {
  const row = automationRecord(value);
  const result: SecurityLifecycleAutomationDispatchResponse = {
    scope: automationEnum(row.scope, ["due", "case"] as const),
    status: automationEnum(
      row.status,
      ["started", "skipped", "unavailable", "not_installed"] as const,
    ),
  };
  if (row.reason !== undefined) result.reason = automationEnum(row.reason, AUTOMATION_REASONS);
  if (row.request_id !== undefined) result.request_id = automationString(row.request_id);
  if (row.case_id !== undefined) result.case_id = automationString(row.case_id);
  return result;
}

const LIFECYCLE_PROPOSAL_TYPES: readonly SecurityLifecycleProposalType[] = [
  "archive_manual_memberships",
  "hide_from_active_universe",
  "keep_tracking",
  "no_action",
  "notify",
  "remap_symbol",
  "review_portfolio_position",
];
const LIFECYCLE_PROPOSAL_STATUSES: readonly SecurityLifecycleProposalStatus[] = [
  "proposed",
  "dismissed",
];
const LIFECYCLE_PROPOSAL_BLOCK_REASONS:
readonly SecurityLifecycleProposalBlockReason[] = [
  "portfolio_position_open",
  "successor_evidence_missing",
  "source_context_unavailable",
  "stale_assessment",
  "action_executor_not_available",
];
const LIFECYCLE_TRACKING_SOURCES: readonly SecurityLifecycleTrackingSource[] = [
  "manual_lists",
  "portfolio_open",
  "sa_alpha_picks_current",
  "sa_alpha_picks_former",
  "legacy_config_seed",
];
const LIFECYCLE_SEC_ADMISSION_STATES:
readonly SecurityLifecycleSecAdmissionState[] = [
  "pending",
  "admitted",
  "screened_out",
  "needs_review",
];
const LIFECYCLE_SEC_ADMISSION_REASONS:
readonly SecurityLifecycleSecAdmissionReason[] = [
  "awaiting_regulator_screening",
  "direct_listing_item",
  "direct_identity_filing",
  "material_tracked_security_fact",
  "no_material_tracked_security_fact",
  "identity_binding_missing",
  "regulator_screening_incomplete",
  "regulator_monitor_only",
  "unknown_form",
];
const LIFECYCLE_SOURCE_FAMILY_STATES:
readonly SecurityLifecycleSourceFamilyState[] = [
  "confirmed",
  "present",
  "missing",
  "unavailable",
  "conflict",
];
const LIFECYCLE_LISTING_STATUSES: readonly SecurityLifecycleListingStatus[] = [
  "active",
  "inactive",
  "not_found",
  "unverified",
];
const LIFECYCLE_PRIMARY_SOURCE_FAMILIES:
readonly SecurityLifecycleEvidenceSourceFamily[] = [
  "regulator",
  "listing_authority",
  "market_infrastructure",
  "manual",
];

function lifecycleCaseContractError(): never {
  throw new Error("security_lifecycle_case_contract");
}

function lifecycleCaseRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return lifecycleCaseContractError();
  }
  return value as Record<string, unknown>;
}

function lifecycleCaseArray(value: unknown): unknown[] {
  if (!Array.isArray(value)) return lifecycleCaseContractError();
  return value;
}

function lifecycleCaseString(value: unknown): string {
  if (typeof value !== "string" || !value || value.includes("\0")) {
    return lifecycleCaseContractError();
  }
  return value;
}

function lifecycleCaseNullableString(value: unknown): string | null {
  return value === null ? null : lifecycleCaseString(value);
}

function lifecycleCaseBoolean(value: unknown): boolean {
  if (typeof value !== "boolean") return lifecycleCaseContractError();
  return value;
}

function lifecycleCaseCount(value: unknown): number {
  if (!Number.isInteger(value) || (value as number) < 0) {
    return lifecycleCaseContractError();
  }
  return value as number;
}

function lifecycleCaseEnum<Value extends string>(
  value: unknown,
  allowed: readonly Value[],
): Value {
  if (typeof value !== "string" || !allowed.includes(value as Value)) {
    return lifecycleCaseContractError();
  }
  return value as Value;
}

function parseLifecycleProposal(value: unknown): SecurityLifecycleActionProposal {
  const row = lifecycleCaseRecord(value);
  return {
    proposal_id: lifecycleCaseString(row.proposal_id),
    action_type: lifecycleCaseEnum(row.action_type, LIFECYCLE_PROPOSAL_TYPES),
    status: lifecycleCaseEnum(row.status, LIFECYCLE_PROPOSAL_STATUSES),
    projected_block_reason: row.projected_block_reason === null
      ? null
      : lifecycleCaseEnum(
        row.projected_block_reason,
        LIFECYCLE_PROPOSAL_BLOCK_REASONS,
      ),
    replacement_ticker: row.replacement_ticker === null
      ? null
      : lifecycleCaseString(row.replacement_ticker),
  };
}

function parseLifecycleSecAdmission(value: unknown): SecurityLifecycleSecAdmission {
  const row = lifecycleCaseRecord(value);
  return {
    state: lifecycleCaseEnum(row.state, LIFECYCLE_SEC_ADMISSION_STATES),
    reason: lifecycleCaseEnum(row.reason, LIFECYCLE_SEC_ADMISSION_REASONS),
  };
}

function parseLifecycleListingCorroboration(
  value: unknown,
): SecurityLifecycleListingCorroboration | null {
  if (value === null) return null;
  const row = lifecycleCaseRecord(value);
  return {
    listing_status: lifecycleCaseEnum(row.listing_status, LIFECYCLE_LISTING_STATUSES),
    source_as_of: lifecycleCaseString(row.source_as_of),
    provider_last_updated_utc: lifecycleCaseNullableString(
      row.provider_last_updated_utc,
    ),
  };
}

function parseLifecycleObservationKind(
  value: unknown,
): SecurityLifecycleObservationKind {
  const row = lifecycleCaseRecord(value);
  return {
    event_type: lifecycleCaseString(row.event_type) as SecurityLifecycleEventType,
    effective_date: lifecycleCaseNullableString(row.effective_date),
  };
}

const LIFECYCLE_AUTOMATION_NARRATIVES = [
  "terminalDelisting",
  "noIdentityChange",
  "simpleSymbolContinuation",
  "venueTransfer",
  "maReview",
  "sourceConflict",
  "insufficientIdentityFacts",
  "unknownRule",
] as const;

function parseLifecycleAssessment(
  value: unknown,
  audit = true,
): SecurityLifecycleAssessment {
  const row = lifecycleCaseRecord(value);
  lifecycleCaseArray(row.outcomes);
  if (audit && row.citations !== undefined) lifecycleCaseArray(row.citations);
  const primaryFields = [
    "assessment_id",
    "status",
    "author",
    "automation_method",
    "acceptance_authority",
    "relevance",
    "confidence",
    "conclusion",
    "impact_summary",
    "outcomes",
    "stale",
    "created_at",
    "consideration_currency",
    "cash_per_security_decimal",
    "exchange_ratio_decimal",
    "successor_ticker",
    "destination_venue",
    "counterparty_name",
    "counterparty_ticker",
    "effective_date",
  ] as const;
  const projected = Object.fromEntries(
    primaryFields.flatMap((field) => field in row ? [[field, row[field]]] : []),
  ) as unknown as SecurityLifecycleAssessment;
  if (row.automation_narrative !== undefined) {
    projected.automation_narrative = lifecycleCaseEnum(
      row.automation_narrative,
      LIFECYCLE_AUTOMATION_NARRATIVES,
    );
  }
  if (audit) {
    const auditFields = [
      "automation_run_id",
      "rule_id",
      "rule_version",
      "decision_provenance_sha256",
      "counterparty_cik",
      "citations",
    ] as const;
    Object.assign(projected, Object.fromEntries(
      auditFields.flatMap((field) => field in row ? [[field, row[field]]] : []),
    ));
  }
  return projected;
}

function parseLifecycleAcknowledgement(
  value: unknown,
): SecurityLifecycleAcknowledgement {
  const row = lifecycleCaseRecord(value);
  return {
    acknowledgement_id: lifecycleCaseString(row.acknowledgement_id),
    reason: lifecycleCaseString(row.reason) as SecurityLifecycleAcknowledgement["reason"],
    note: lifecycleCaseNullableString(row.note),
    stale: lifecycleCaseBoolean(row.stale),
    acknowledged_at: lifecycleCaseString(row.acknowledged_at),
    reopened_at: lifecycleCaseNullableString(row.reopened_at),
  };
}

function parseLifecycleAutomationOperatorDetail(
  value: unknown,
): SecurityLifecycleAutomationOperatorDetail {
  const row = lifecycleCaseRecord(value);
  if (row.code === "listing_checks") return {
    code: row.code,
    missing_checks: lifecycleCaseArray(row.missing_checks).map((item) => lifecycleCaseEnum(item, LISTING_CHECK_NAMES)),
    provider_issues: lifecycleCaseArray(row.provider_issues).map((item) => {
      const issue = lifecycleCaseRecord(item);
      return { provider: lifecycleCaseEnum(issue.provider, LISTING_PROVIDER_NAMES), reason: lifecycleCaseEnum(issue.reason, LISTING_PROVIDER_ISSUES) };
    }),
    manual_review_required: lifecycleCaseBoolean(row.manual_review_required),
  };
  if (row.code !== "candidate_budget_exceeded" || row.provider_contacted !== false) {
    return lifecycleCaseContractError();
  }
  return {
    code: "candidate_budget_exceeded",
    candidate_count: lifecycleCaseCount(row.candidate_count),
    query_limit: lifecycleCaseCount(row.query_limit),
    provider_contacted: false,
  };
}

function parseLifecycleAutomationBlocker(value: unknown) {
  const row = lifecycleCaseRecord(value);
  const blocker: SecurityLifecycleAutomationRun["blockers"][number] = {
    blocker_code: lifecycleCaseString(
      row.blocker_code,
    ) as SecurityLifecycleAutomationBlockerCode,
    retryable: lifecycleCaseBoolean(row.retryable),
  };
  if (row.operator_detail !== undefined) {
    blocker.operator_detail = parseLifecycleAutomationOperatorDetail(
      row.operator_detail,
    );
  }
  return blocker;
}

function parseLifecycleTransition(value: unknown): TickerIdentityTransitionState {
  const row = lifecycleCaseRecord(value);
  const fields = [
    "transition_id",
    "kind",
    "status",
    "source_ticker",
    "successor_ticker",
    "execute_on",
    "approved_preview_sha256",
    "approved_preview",
    "approval_authority",
    "automation_policy_version",
    "rule_id",
    "rule_version",
    "decision_provenance_sha256",
    "updated_at",
    "latest_attempt",
    "reverse_readiness",
    "activity_history",
    "activity_count",
    "unacknowledged_activity_count",
  ] as const;
  return Object.fromEntries(
    fields.flatMap((field) => field in row ? [[field, row[field]]] : []),
  ) as unknown as TickerIdentityTransitionState;
}

function parseLifecycleSecCandidate(value: unknown): SecurityLifecycleSecCandidate {
  const row = lifecycleCaseRecord(value);
  return {
    case_id: lifecycleCaseString(row.case_id),
    ticker: lifecycleCaseString(row.ticker),
    issuer_name: lifecycleCaseString(row.issuer_name),
    filing_form: lifecycleCaseString(row.filing_form),
    filing_items: lifecycleCaseArray(row.filing_items).map(lifecycleCaseString),
    filing_date: lifecycleCaseString(row.filing_date),
    evidence_url: lifecycleCaseString(row.evidence_url),
    admission_state: lifecycleCaseEnum(
      row.admission_state,
      LIFECYCLE_SEC_ADMISSION_STATES,
    ),
    admission_reason: lifecycleCaseEnum(
      row.admission_reason,
      LIFECYCLE_SEC_ADMISSION_REASONS,
    ),
  };
}

function parseLifecycleSecCandidateResponse(
  value: unknown,
): SecurityLifecycleSecCandidateResponse {
  const row = lifecycleCaseRecord(value);
  const counts = lifecycleCaseRecord(row.state_counts);
  return {
    candidates: lifecycleCaseArray(row.candidates).map(parseLifecycleSecCandidate),
    count: lifecycleCaseCount(row.count),
    state_counts: {
      pending: lifecycleCaseCount(counts.pending),
      admitted: lifecycleCaseCount(counts.admitted),
      screened_out: lifecycleCaseCount(counts.screened_out),
      needs_review: lifecycleCaseCount(counts.needs_review),
    },
  };
}

function parseLifecycleCaseDetail(value: unknown): SecurityLifecycleCaseDetail {
  const row = lifecycleCaseRecord(value);
  const activeSources = lifecycleCaseArray(row.active_sources).map((item) => (
    lifecycleCaseEnum(item, LIFECYCLE_TRACKING_SOURCES)
  ));
  const kinds = lifecycleCaseArray(row.kinds).map(parseLifecycleObservationKind);
  const rawSourceStatuses = lifecycleCaseRecord(row.source_family_status);
  const sourceStatuses = Object.fromEntries(
    LIFECYCLE_PRIMARY_SOURCE_FAMILIES.flatMap((family) => (
      family in rawSourceStatuses
        ? [[family, lifecycleCaseEnum(
          rawSourceStatuses[family],
          LIFECYCLE_SOURCE_FAMILY_STATES,
        )]]
        : []
    )),
  );
  const admission = row.sec_admission === null
    ? null
    : parseLifecycleSecAdmission(row.sec_admission);
  const corroboration = lifecycleCaseRecord(row.corroboration);
  if (row.observation !== null) {
    const observation = lifecycleCaseRecord(row.observation);
    lifecycleCaseArray(observation.filing_items);
    lifecycleCaseArray(observation.kinds);
  }

  return {
    case_id: lifecycleCaseString(row.case_id),
    ticker: lifecycleCaseString(row.ticker),
    source_presence: lifecycleCaseString(row.source_presence) as SecurityLifecycleSourcePresence,
    workflow_state: lifecycleCaseString(row.workflow_state) as SecurityLifecycleWorkflowState,
    issuer_name: lifecycleCaseNullableString(row.issuer_name),
    filing_date: lifecycleCaseNullableString(row.filing_date),
    kinds,
    current_assessment: row.current_assessment === null
      ? null
      : parseLifecycleAssessment(row.current_assessment, false),
    current_acknowledgement: row.current_acknowledgement === null
      ? null
      : parseLifecycleAcknowledgement(row.current_acknowledgement),
    active_sources: activeSources,
    source_context: lifecycleCaseString(row.source_context) as "available" | "unavailable",
    automation_tier: row.automation_tier === null
      ? null
      : lifecycleCaseString(row.automation_tier) as SecurityLifecycleDecisionTier,
    action_readiness: row.action_readiness === null
      ? null
      : lifecycleCaseString(row.action_readiness) as SecurityLifecycleActionReadiness,
    disposition: lifecycleCaseString(row.disposition) as SecurityLifecycleDisposition,
    queue_bucket: lifecycleCaseString(row.queue_bucket) as SecurityLifecycleQueueBucket,
    disposition_reason: lifecycleCaseString(
      row.disposition_reason,
    ) as SecurityLifecycleDispositionReason,
    disposition_as_of: lifecycleCaseNullableString(row.disposition_as_of),
    last_checked_at: lifecycleCaseNullableString(row.last_checked_at),
    next_check_at: lifecycleCaseNullableString(row.next_check_at),
    source_family_status: sourceStatuses as SecurityLifecycleCaseDetail["source_family_status"],
    sec_admission: admission,
    observation: row.observation === null
      ? null
      : (() => {
        const observation = lifecycleCaseRecord(row.observation);
        return {
          ticker: lifecycleCaseString(observation.ticker),
          issuer_name: lifecycleCaseString(observation.issuer_name),
          filing_date: lifecycleCaseString(observation.filing_date),
          filing_form: lifecycleCaseString(observation.filing_form),
          filing_items: lifecycleCaseArray(observation.filing_items).map(lifecycleCaseString),
          evidence_url: lifecycleCaseString(observation.evidence_url),
          kinds: lifecycleCaseArray(observation.kinds).map(
            parseLifecycleObservationKind,
          ),
        };
      })(),
    corroboration: {
      regulator: corroboration.regulator === null
        ? null
        : lifecycleCaseEnum(corroboration.regulator, LIFECYCLE_SOURCE_FAMILY_STATES),
      nasdaq_trader: parseLifecycleListingCorroboration(corroboration.nasdaq_trader),
      massive: parseLifecycleListingCorroboration(corroboration.massive),
      ...(corroboration.eodhd === undefined ? {} : { eodhd: parseLifecycleListingCorroboration(corroboration.eodhd) }),
      ibkr: corroboration.ibkr === null
        ? null
        : lifecycleCaseEnum(corroboration.ibkr, LIFECYCLE_SOURCE_FAMILY_STATES),
    },
    current_blockers: row.current_blockers === undefined ? [] : lifecycleCaseArray(row.current_blockers).map(parseLifecycleAutomationBlocker),
    proposals: lifecycleCaseArray(row.proposals).map(parseLifecycleProposal),
    ticker_transition: row.ticker_transition === null
      ? null
      : parseLifecycleTransition(row.ticker_transition),
  };
}

export interface SecurityLifecycleCaseFilters {
  ticker?: string;
  workflow_state?: SecurityLifecycleWorkflowState | "";
  relevance?: SecurityLifecycleRelevance | "";
  event_type?: SecurityLifecycleEventType | "";
  proposal_type?: SecurityLifecycleProposalType | "";
  queue_bucket?: SecurityLifecycleQueueBucket;
  source_presence?: SecurityLifecycleSourcePresence;
  limit?: number;
}

function lifecycleQuery(filters: object): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== "") params.set(key, String(value));
  }
  const query = params.toString();
  return query ? `?${query}` : "";
}

export async function confirmLifecycleReview(value: LifecycleReviewPacket) {
  const packet = parseLifecycleReviewPacket(value);
  if (!packet.ready || !packet.action) return invalidCurrentPayload();
  const result = parseLifecycleReviewConfirmation(await sendJSON<unknown>(
    `/security-lifecycle/cases/${encodeURIComponent(packet.case_id)}/confirm-review`, "POST",
    { assessment_id: packet.assessment_id, packet_sha256: packet.packet_sha256, action: packet.action, ...packet.options }));
  if (result.case_id !== packet.case_id || result.packet_sha256 !== packet.packet_sha256 || result.action !== packet.action
      || result.source_ticker !== packet.source_ticker || result.execute_on !== packet.execute_on) return invalidCurrentPayload();
  return result;
}

export async function getInvestigationTargets() {
  return parseInvestigationTargets(await getJSON<unknown>("/security-lifecycle/investigations/targets"));
}
export async function getInvestigationPreflight(ticker: string, language: string) {
  const result = parseInvestigationPreflight(await getJSON<unknown>(`/security-lifecycle/investigations/targets/${encodeURIComponent(ticker)}/preflight${lifecycleQuery({ language })}`));
  if (result.ticker !== ticker) return invalidCurrentPayload(); return result;
}
export async function latestInvestigation(ticker: string) {
  const value = await getJSON<unknown>(`/security-lifecycle/investigations/targets/${encodeURIComponent(ticker)}/latest`);
  if (value === null) return null; const result = parseInvestigationRun(value);
  if (result.ticker !== ticker) return invalidCurrentPayload(); return result;
}
export async function startInvestigation(ticker: string, body: { preflight_sha256: string; request_key: string; language: string }) {
  return parseInvestigationStart(await sendJSON<unknown>(`/security-lifecycle/investigations/targets/${encodeURIComponent(ticker)}/runs`, "POST", body));
}
export async function getInvestigation(runId: string) {
  const result = parseInvestigationRun(await getJSON<unknown>(`/security-lifecycle/investigations/runs/${encodeURIComponent(runId)}`));
  if (result.run_id !== runId) return invalidCurrentPayload(); return result;
}
export async function cancelInvestigation(runId: string) {
  const result = parseInvestigationRun(await sendJSON<unknown>(`/security-lifecycle/investigations/runs/${encodeURIComponent(runId)}/cancel`, "POST"));
  if (result.run_id !== runId) return invalidCurrentPayload(); return result;
}
export async function getInvestigationReview(runId: string, options: TickerIdentityTransitionPreviewOptions = {}) {
  return parseLifecycleReviewPacket(await getJSON<unknown>(`/security-lifecycle/investigations/runs/${encodeURIComponent(runId)}/review${lifecycleQuery(options)}`));
}
export async function confirmInvestigation(runId: string, value: LifecycleReviewPacket, acknowledgeSourceGaps: boolean) {
  const packet = parseLifecycleReviewPacket(value);
  if (!packet.ready || !packet.action) return invalidCurrentPayload();
  const result = parseLifecycleReviewConfirmation(await sendJSON<unknown>(`/security-lifecycle/investigations/runs/${encodeURIComponent(runId)}/confirm`, "POST",
    { packet_sha256: packet.packet_sha256, action: packet.action, ...packet.options, acknowledge_source_gaps: acknowledgeSourceGaps }));
  if (result.case_id !== packet.case_id || result.packet_sha256 !== packet.packet_sha256 || result.action !== packet.action
    || result.source_ticker !== packet.source_ticker || result.execute_on !== packet.execute_on) return invalidCurrentPayload();
  return result;
}
export async function getInvestigationRuntime() { return parseInvestigationRuntime(await getJSON<unknown>("/security-lifecycle/investigations/runtime")); }
export async function saveInvestigationRuntime(value: InvestigationRuntime) {
  return parseInvestigationRuntime(await sendJSON<unknown>("/security-lifecycle/investigations/runtime", "PUT", parseInvestigationRuntime(value)));
}
export async function resetInvestigationRuntime() { return parseInvestigationRuntime(await sendJSON<unknown>("/security-lifecycle/investigations/runtime/reset", "POST")); }
export async function getInvestigationProviders(ticker: string) {
  const result = parseInvestigationProviders(await getJSON<unknown>(`/security-lifecycle/investigations/targets/${encodeURIComponent(ticker)}/providers`));
  if (result.ticker !== ticker) throw new Error("investigation_payload_invalid"); return result;
}
export async function checkInvestigationProviders(ticker: string) {
  const result = parseInvestigationProviders(await sendJSON<unknown>(`/security-lifecycle/investigations/targets/${encodeURIComponent(ticker)}/providers/check`, "POST", undefined, 300_000));
  if (result.ticker !== ticker) throw new Error("investigation_payload_invalid"); return result;
}
export async function prepareInvestigationProviders(ticker: string, checkSha256: string, options: TickerIdentityTransitionPreviewOptions = {}) {
  const result = parseLifecycleReviewPacket(await sendJSON<unknown>(`/security-lifecycle/investigations/targets/${encodeURIComponent(ticker)}/providers/prepare`,
    "POST", { check_sha256: checkSha256, ...options }));
  if (result.source_ticker !== ticker) throw new Error("investigation_payload_invalid"); return result;
}
export async function getInvestigationActions() { return parseInvestigationActions(await getJSON<unknown>("/security-lifecycle/investigations/actions")); }

export function listSecurityLifecycleCases(
  filters: SecurityLifecycleCaseFilters = {},
): Promise<SecurityLifecycleCaseListResponse> {
  return getJSON<SecurityLifecycleCaseListResponse>(
    `/security-lifecycle/cases${lifecycleQuery(filters)}`,
  );
}

export async function listSecurityLifecycleSecCandidates(
  filters: {
    admission_state?: SecurityLifecycleSecAdmissionState;
    limit?: number;
  } = {},
): Promise<SecurityLifecycleSecCandidateResponse> {
  return parseLifecycleSecCandidateResponse(
    await getJSON<unknown>(
      `/security-lifecycle/candidates${lifecycleQuery(filters)}`,
    ),
  );
}

export async function getSecurityLifecycleAutomationStatus(): Promise<
  SecurityLifecycleAutomationStatusResponse
> {
  return parseAutomationStatus(await getJSON<unknown>("/security-lifecycle/automation"));
}

export async function updateSecurityLifecycleAutomationConfig(
  config: SecurityLifecycleAutomationConfig,
): Promise<SecurityLifecycleAutomationConfigResponse> {
  return parseAutomationConfigResponse(await sendJSON<unknown>(
    "/security-lifecycle/automation",
    "PUT",
    config,
  ));
}

export async function runDueSecurityLifecycleAutomation(): Promise<
  SecurityLifecycleAutomationDispatchResponse
> {
  return parseAutomationDispatch(await sendJSON<unknown>(
    "/security-lifecycle/automation/run",
    "POST",
  ));
}

export async function getSecurityLifecycleCase(
  caseId: string,
): Promise<SecurityLifecycleCaseDetail> {
  return parseLifecycleCaseDetail(
    await getJSON<unknown>(
      `/security-lifecycle/cases/${encodeURIComponent(caseId)}`,
    ),
  );
}

export function getSecurityLifecycleInvestigation(
  runId: string,
): Promise<SecurityLifecycleInvestigationRun> {
  return getJSON<SecurityLifecycleInvestigationRun>(
    `/security-lifecycle/investigations/${encodeURIComponent(runId)}`,
  );
}

export function addSecurityLifecycleEvidence(
  caseId: string,
  body: { text: string | null; url: string | null },
): Promise<{ evidence_id: string }> {
  return sendJSON(
    `/security-lifecycle/cases/${encodeURIComponent(caseId)}/evidence`,
    "POST",
    body,
  );
}

export interface SecurityLifecycleCitationInput {
  reference_kind: "observation" | "evidence";
  evidence_id?: string;
  cited_content_sha256?: string;
}

export interface SecurityLifecycleAssessmentInput {
  relevance: SecurityLifecycleRelevance;
  confidence: SecurityLifecycleConfidence;
  conclusion: string;
  impact_summary: string;
  outcomes: SecurityLifecycleAssessmentOutcome[];
  citations: SecurityLifecycleCitationInput[];
  counterparty_name?: string | null;
  counterparty_ticker?: string | null;
  counterparty_cik?: string | null;
  successor_ticker?: string | null;
  destination_venue?: string | null;
  effective_date?: string | null;
  consideration_currency?: string | null;
  cash_per_security_decimal?: string | null;
  exchange_ratio_decimal?: string | null;
}

export function createSecurityLifecycleAssessment(
  caseId: string,
  body: SecurityLifecycleAssessmentInput,
): Promise<{ assessment_id: string }> {
  return sendJSON(
    `/security-lifecycle/cases/${encodeURIComponent(caseId)}/assessments`,
    "POST",
    body,
  );
}

export function acceptSecurityLifecycleAssessment(
  assessmentId: string,
): Promise<{ assessment: SecurityLifecycleAssessment; proposals: SecurityLifecycleActionProposal[] }> {
  return sendJSON(
    `/security-lifecycle/assessments/${encodeURIComponent(assessmentId)}/accept`,
    "POST",
  );
}

export function acknowledgeSecurityLifecycleCase(
  caseId: string,
  body: { reason: "evidence_insufficient"; note: string | null },
): Promise<{ acknowledgement_id: string }> {
  return sendJSON(
    `/security-lifecycle/cases/${encodeURIComponent(caseId)}/acknowledgements`,
    "POST",
    body,
  );
}

export function reopenSecurityLifecycleAcknowledgement(
  acknowledgementId: string,
): Promise<{ acknowledgement_id: string; status: "reopened" }> {
  return sendJSON(
    `/security-lifecycle/acknowledgements/${encodeURIComponent(acknowledgementId)}/reopen`,
    "POST",
  );
}

export function dismissSecurityLifecycleProposal(
  proposalId: string,
): Promise<SecurityLifecycleActionProposal> {
  return sendJSON(
    `/security-lifecycle/action-proposals/${encodeURIComponent(proposalId)}/dismiss`,
    "POST",
  );
}

export interface TickerIdentityTransitionPreviewOptions {
  execute_on?: string;
  priority_resolution?: TickerIdentityPriorityResolution;
  unhide_successor?: boolean;
}

function tickerIdentityPreviewQuery(options: TickerIdentityTransitionPreviewOptions): string {
  const params = new URLSearchParams();
  if (options.execute_on) params.set("execute_on", options.execute_on);
  if (options.priority_resolution) {
    params.set("priority_resolution", options.priority_resolution);
  }
  if (options.unhide_successor) params.set("unhide_successor", "true");
  const query = params.toString();
  return query ? `?${query}` : "";
}

export function getTickerIdentityTransitionPreview(
  caseId: string,
  options: TickerIdentityTransitionPreviewOptions = {},
): Promise<TickerIdentityTransitionPreview> {
  return getJSON<TickerIdentityTransitionPreview>(
    `/security-lifecycle/cases/${encodeURIComponent(caseId)}/transition-preview${
      tickerIdentityPreviewQuery(options)
    }`,
  );
}

export function approveTickerIdentityTransition(
  caseId: string,
  body: {
    execute_on: string;
    preview_sha256: string;
    priority_resolution: TickerIdentityPriorityResolution | null;
    unhide_successor: boolean;
  },
): Promise<TickerIdentityTransitionRecord> {
  return sendJSON<TickerIdentityTransitionRecord>(
    `/security-lifecycle/cases/${encodeURIComponent(caseId)}/approve-transition`,
    "POST",
    body,
  );
}

export function cancelTickerIdentityTransition(
  transitionId: string,
): Promise<TickerIdentityTransitionRecord> {
  return sendJSON<TickerIdentityTransitionRecord>(
    `/security-lifecycle/transitions/${encodeURIComponent(transitionId)}/cancel`,
    "POST",
  );
}

export function retryTickerIdentityTransition(
  transitionId: string,
  body: { preview_sha256: string },
): Promise<TickerIdentityTransitionAttemptResult> {
  return sendJSON<TickerIdentityTransitionAttemptResult>(
    `/security-lifecycle/transitions/${encodeURIComponent(transitionId)}/retry`,
    "POST",
    body,
  );
}

export function reverseTickerIdentityTransition(
  transitionId: string,
): Promise<TickerIdentityTransitionAttemptResult> {
  return sendJSON<TickerIdentityTransitionAttemptResult>(
    `/security-lifecycle/transitions/${encodeURIComponent(transitionId)}/reverse`,
    "POST",
  );
}

export async function listTickerIdentityTransitionActivity(
  options: { limit?: number; unacknowledged_only?: boolean } = {},
): Promise<TickerIdentityTransitionActivityResponse> {
  const params = new URLSearchParams();
  if (options.limit !== undefined) params.set("limit", String(options.limit));
  if (options.unacknowledged_only !== undefined) {
    params.set("unacknowledged_only", String(options.unacknowledged_only));
  }
  const query = params.toString();
  return parseCurrentActivityList(await getJSON<unknown>(
    `/security-lifecycle/transition-activity${query ? `?${query}` : ""}`,
  ));
}

export async function acknowledgeTickerIdentityTransitionActivity(
  activityId: string,
): Promise<TickerIdentityTransitionActivity> {
  const result = parseCurrentActivity(await sendJSON<unknown>(
    `/security-lifecycle/transition-activity/${encodeURIComponent(activityId)}/acknowledge`,
    "POST",
  ));
  if (result.activity_id !== activityId || result.acknowledged_at === null) return invalidCurrentPayload();
  return result;
}

export function getNewsStatus(): Promise<NewsStatus> {
  return getJSON<NewsStatus>("/news/status");
}

export function setNormalizedNewsWrites(enabled: boolean): Promise<{ normalized_writes_setting: boolean }> {
  return sendJSON("/news/settings/normalized-writes", "PUT", { enabled });
}

// --- 本地總經/行事曆 (macro_calendar.db) — use_local_macro toggle + coverage (§4c) ---

export interface MacroTableStat {
  last_fetched_at: string | null;
  row_count: number;
}

export interface MacroStatus {
  macro_db: string;
  exists: boolean;
  // keyed by table name (cal_economic_events / cal_earnings_events / cal_ipo_events /
  // macro_series / macro_observations / macro_release_dates); {} when the DB is absent.
  tables: Record<string, MacroTableStat>;
  use_local_macro_setting: boolean;
  env_override: boolean;
  local_first_active: boolean;
}

export function getMacroStatus(): Promise<MacroStatus> {
  return getJSON<MacroStatus>("/macro/status");
}

export interface MacroSnapshotItem {
  series_id: string;
  label: string;
  title: string | null;
  units: string | null;
  value: number | null;
  observation_date: string | null;
  fetched_at: string | null;
  realtime_start: string | null;
  realtime_end: string | null;
}

export interface MacroSnapshot {
  available: boolean;
  macro_db: string;
  series_count: number;
  observation_count: number;
  release_dates_count: number;
  latest_fetched_at: string | null;
  items: MacroSnapshotItem[];
  missing_series: string[];
}

export function getMacroSnapshot(): Promise<MacroSnapshot> {
  return getJSON<MacroSnapshot>("/macro/snapshot");
}

// --- trading-day coverage (Coverage v2; read-only over market_data.db) ---

export type MarketScope = "us_listed_equity_proxy";
export type CoverageSession = "rth";
export type CalendarHealthStatus = "ok" | "degraded" | "unavailable";
export type ObservationHealthStatus = "ok" | "unavailable";
export type CalendarHealthReason =
  | "fixture_horizon_low"
  | "date_unreviewed"
  | "calendar_unavailable";
export type ObservationHealthReason =
  | "market_db_missing"
  | "market_db_unreadable"
  | "prices_schema_missing";
export type CoverageDayStatus =
  | "unknown"
  | "non_trading"
  | "in_progress"
  | "partial"
  | "indeterminate_tickers"
  | "complete";
export type CoverageDayReason =
  | "calendar_unavailable"
  | "date_unreviewed"
  | "observation_unavailable"
  | "no_observations";
export type ClosureReasonCode = "weekend" | "market_closed";
export type SessionKind = "regular" | "early_close";

export interface PartialTickerCoverage {
  ticker: string;
  observed_slot_count: number;
  expected_slot_count: number;
}

export interface CoverageCalendarHealth {
  status: CalendarHealthStatus;
  reason_codes: CalendarHealthReason[];
  reviewed_through: string;
  forward_horizon_months: number;
}

export interface CoverageObservationHealth {
  status: ObservationHealthStatus;
  reason_code: ObservationHealthReason | null;
}

export interface ProviderSyncIssue {
  ticker: string;
  interval: string;
  last_error: string;
  reason_code:
    | "security_definition_unavailable"
    | "price_data_unresolved"
    | "provider_request_failed"
    | "unknown";
  updated_at: string | null;
}

export const IBKR_GATEWAY_UNAVAILABLE = "ibkr_gateway_unavailable" as const;

export interface TradingDayRow {
  date: string;
  coverage_status: CoverageDayStatus;
  status_reason_code: CoverageDayReason | null;
  closure_reason_code: ClosureReasonCode | null;
  session_kind: SessionKind | null;
  session_open_at_utc: string | null;
  session_close_at_utc: string | null;
  expected_slot_count: number | null;
  observed_ticker_count: number | null;
  complete_ticker_count: number | null;
  partial_ticker_count: number | null;
  unknown_ticker_count: number | null;
  partial_tickers: PartialTickerCoverage[];
  unknown_tickers: string[];
  unmatched_rth_row_count: number | null;
}

export interface TradingDayCoverage {
  version: 2;
  market_scope: MarketScope;
  coverage_session: CoverageSession;
  interval: "15min";
  lookback_days: number;
  universe_count: number;
  generated_at_et: string;
  calendar_health: CoverageCalendarHealth;
  observation_health: CoverageObservationHealth;
  days: TradingDayRow[];
  provider_errors: ProviderSyncIssue[];
  scope_basis?: "current_universe_retrospective";
  history_gaps?: CoverageHistoryGap[];
}

export interface CoverageHistoryGap {
  ticker: string;
  reason: "before_first_local_bar" | "no_local_history" | "missing_observations" | "partial_observations";
  first_local_bar_at: string | null;
  missing_dates: string[];
  partial_dates: string[];
  provider_issue_reason: ProviderSyncIssue["reason_code"] | null;
}

function coverageRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("price_coverage_payload_invalid");
  return value as Record<string, unknown>;
}
function coverageStrings(value: unknown): string[] {
  if (!Array.isArray(value) || value.some((item) => typeof item !== "string" || !item.length)) throw new Error("price_coverage_payload_invalid");
  return value;
}
export function parseCoverageHistoryGaps(value: unknown): CoverageHistoryGap[] {
  if (!Array.isArray(value)) throw new Error("price_coverage_payload_invalid");
  return value.map((raw) => {
    const row = coverageRecord(raw);
    const reasons = ["before_first_local_bar", "no_local_history", "missing_observations", "partial_observations"];
    const issues = [null, "security_definition_unavailable", "price_data_unresolved", "provider_request_failed", "unknown"];
    if (typeof row.ticker !== "string" || !row.ticker || !reasons.includes(String(row.reason))
      || !issues.includes(row.provider_issue_reason as string | null)
      || !(row.first_local_bar_at === null || typeof row.first_local_bar_at === "string")) throw new Error("price_coverage_payload_invalid");
    return { ticker: row.ticker, reason: row.reason as CoverageHistoryGap["reason"],
      first_local_bar_at: row.first_local_bar_at, missing_dates: coverageStrings(row.missing_dates),
      partial_dates: coverageStrings(row.partial_dates), provider_issue_reason: row.provider_issue_reason as CoverageHistoryGap["provider_issue_reason"] };
  });
}

export interface PriceRepairPreview {
  provider: "ibkr";
  fallback_allowed: false;
  interval: "15min";
  lookback_days: number;
  as_of_date: string;
  tickers: string[];
  blocked_tickers: string[];
  preview_sha256: string;
}
export function parsePriceRepairPreview(value: unknown): PriceRepairPreview {
  const row = coverageRecord(value);
  if (row.provider !== "ibkr" || row.fallback_allowed !== false || row.interval !== "15min"
    || !Number.isInteger(row.lookback_days) || (row.lookback_days as number) < 1 || (row.lookback_days as number) > 120
    || typeof row.as_of_date !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(row.as_of_date)
    || typeof row.preview_sha256 !== "string" || !/^[a-f0-9]{64}$/.test(row.preview_sha256)) throw new Error("price_coverage_payload_invalid");
  return { provider: row.provider, fallback_allowed: row.fallback_allowed, interval: row.interval,
    lookback_days: row.lookback_days as number, as_of_date: row.as_of_date, preview_sha256: row.preview_sha256,
    tickers: coverageStrings(row.tickers), blocked_tickers: coverageStrings(row.blocked_tickers) };
}
export async function getPriceRepairPreview(lookbackDays: number): Promise<PriceRepairPreview> {
  return parsePriceRepairPreview(await getJSON<unknown>(`/market-data/price-repair/preview?lookback_days=${lookbackDays}`));
}
type PriceRepairAccepted = { status: "accepted" | "nothing_to_repair"; repair_id: string | null };
function parsePriceRepairAccepted(value: unknown): PriceRepairAccepted {
  const row = coverageRecord(value);
  if (row.status === "nothing_to_repair") return { status: row.status, repair_id: null };
  if (row.status !== "accepted" || typeof row.repair_id !== "string" || !/^[a-f0-9]{32}$/.test(row.repair_id)) throw new Error("price_coverage_payload_invalid");
  return { status: row.status, repair_id: row.repair_id };
}
export async function startPriceRepair(preview: PriceRepairPreview): Promise<PriceRepairAccepted> {
  return parsePriceRepairAccepted(await sendJSON<unknown>("/market-data/price-repair", "POST", {
    lookback_days: preview.lookback_days, preview_sha256: preview.preview_sha256,
  }));
}
export async function resumePriceRepair(repairId: string): Promise<PriceRepairAccepted> {
  if (!/^[a-f0-9]{32}$/.test(repairId)) throw new Error("price_coverage_payload_invalid");
  const result = parsePriceRepairAccepted(await sendJSON<unknown>(`/market-data/price-repair/${repairId}/resume`, "POST"));
  if (result.repair_id !== null && result.repair_id !== repairId) throw new Error("price_coverage_payload_invalid");
  return result;
}

export interface PriceRepairOperation {
  repair_id: string;
  state: "complete" | "incomplete" | "blocked" | "unavailable";
  reason: "unconfirmed_requests" | "response_incomplete" | "scope_changed" | "coverage_unavailable" | "journal_unavailable" | null;
  scope: { tickers: string[]; provider: "ibkr"; interval: "15min"; as_of_date: string; lookback_days: number } | null;
  requests: { planned: number; dispatched: number; received: number; unanswered: number } | null;
  coverage: { remaining_tickers: string[]; missing_ticker_days: number; partial_ticker_days: number } | null;
  resume: { available: boolean; request_limit: number };
}
export interface PriceRepairOperations {
  version: 1;
  operations: PriceRepairOperation[];
  total: number;
  offset: number;
  has_more: boolean;
}
function priceRepairCount(value: unknown): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 0) throw new Error("price_coverage_payload_invalid");
  return value;
}
function priceRepairTickers(value: unknown): string[] {
  const tickers = coverageStrings(value);
  if (new Set(tickers).size !== tickers.length || tickers.some((ticker) => !/^[A-Z0-9][A-Z0-9 ._-]{0,11}$/.test(ticker))) throw new Error("price_coverage_payload_invalid");
  return tickers;
}
function parsePriceRepairOperation(value: unknown): PriceRepairOperation {
  const row = coverageRecord(value);
  const resume = coverageRecord(row.resume);
  const states = ["complete", "incomplete", "blocked", "unavailable"];
  const reasons = [null, "unconfirmed_requests", "response_incomplete", "scope_changed", "coverage_unavailable", "journal_unavailable"];
  if (typeof row.repair_id !== "string" || !/^[a-f0-9]{32}$/.test(row.repair_id)
    || !states.includes(row.state as string) || !reasons.includes(row.reason as string | null)
    || typeof resume.available !== "boolean") throw new Error("price_coverage_payload_invalid");
  const requestLimit = priceRepairCount(resume.request_limit);
  let scope: PriceRepairOperation["scope"] = null;
  if (row.scope !== null) {
    const item = coverageRecord(row.scope);
    const tickers = priceRepairTickers(item.tickers);
    const days = priceRepairCount(item.lookback_days);
    if (!tickers.length || item.provider !== "ibkr" || item.interval !== "15min" || days < 1 || days > 120
      || typeof item.as_of_date !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(item.as_of_date)
      || !Number.isFinite(Date.parse(item.as_of_date)) || new Date(item.as_of_date).toISOString().slice(0, 10) !== item.as_of_date) throw new Error("price_coverage_payload_invalid");
    scope = { tickers, provider: item.provider, interval: item.interval, lookback_days: days, as_of_date: item.as_of_date };
  }
  let requests: PriceRepairOperation["requests"] = null;
  if (row.requests !== null) {
    const item = coverageRecord(row.requests);
    requests = { planned: priceRepairCount(item.planned), dispatched: priceRepairCount(item.dispatched),
      received: priceRepairCount(item.received), unanswered: priceRepairCount(item.unanswered) };
    if (requests.planned < 1 || requests.received > requests.dispatched || requests.dispatched > requests.planned
      || requests.unanswered !== requests.dispatched - requests.received) throw new Error("price_coverage_payload_invalid");
  }
  let coverage: PriceRepairOperation["coverage"] = null;
  if (row.coverage !== null) {
    const item = coverageRecord(row.coverage);
    coverage = { remaining_tickers: priceRepairTickers(item.remaining_tickers), missing_ticker_days: priceRepairCount(item.missing_ticker_days),
      partial_ticker_days: priceRepairCount(item.partial_ticker_days) };
    const count = coverage.missing_ticker_days + coverage.partial_ticker_days;
    if (!scope || coverage.remaining_tickers.some((ticker) => !scope.tickers.includes(ticker))
      || (coverage.remaining_tickers.length === 0) !== (count === 0) || count < coverage.remaining_tickers.length) throw new Error("price_coverage_payload_invalid");
  }
  if ((scope === null) !== (requests === null)
    || requestLimit > (requests ? requests.planned - requests.dispatched : 0)
    || (!resume.available && requestLimit !== 0)
    || (resume.available && (row.state !== "incomplete" || !scope || !coverage))
    || (row.state === "complete" && (!coverage || coverage.remaining_tickers.length || row.reason !== null || resume.available))
    || (row.state === "incomplete" && (!coverage?.remaining_tickers.length || ![null, "unconfirmed_requests", "response_incomplete"].includes(row.reason as string | null)))
    || (row.state === "blocked" && (row.reason !== "scope_changed" || !scope || coverage !== null || resume.available))
    || (row.reason === "unconfirmed_requests" && !requests?.unanswered)
    || (row.state === "unavailable" && (resume.available || !["journal_unavailable", "coverage_unavailable"].includes(row.reason as string)))
    || (row.reason === "journal_unavailable" && (scope !== null || requests !== null || coverage !== null))) throw new Error("price_coverage_payload_invalid");
  return { repair_id: row.repair_id, state: row.state as PriceRepairOperation["state"], reason: row.reason as PriceRepairOperation["reason"],
    scope, requests, coverage, resume: { available: resume.available, request_limit: requestLimit } };
}
export function parsePriceRepairOperations(value: unknown): PriceRepairOperations {
  const row = coverageRecord(value);
  if (row.version !== 1 || !Array.isArray(row.operations) || row.operations.length > 20 || typeof row.has_more !== "boolean") throw new Error("price_coverage_payload_invalid");
  const operations = row.operations.map(parsePriceRepairOperation);
  const total = priceRepairCount(row.total), offset = priceRepairCount(row.offset);
  if (new Set(operations.map((item) => item.repair_id)).size !== operations.length
    || (operations.length > 0 && offset + operations.length > total)
    || row.has_more !== (offset + operations.length < total)) throw new Error("price_coverage_payload_invalid");
  return { version: row.version, operations, total, offset, has_more: row.has_more };
}
export async function getPriceRepairOperations(offset = 0): Promise<PriceRepairOperations> {
  priceRepairCount(offset);
  return parsePriceRepairOperations(await getJSON<unknown>(`/market-data/price-repair/operations?limit=5&offset=${offset}`));
}
export async function getPriceRepairOperation(repairId: string): Promise<PriceRepairOperation> {
  if (!/^[a-f0-9]{32}$/.test(repairId)) throw new Error("price_coverage_payload_invalid");
  const result = parsePriceRepairOperation(await getJSON<unknown>(`/market-data/price-repair/${repairId}`));
  if (result.repair_id !== repairId) throw new Error("price_coverage_payload_invalid");
  return result;
}

export const DEFAULT_PRICE_LOOKBACK_DAYS = 15;

export async function getTradingDayCoverage(
  lookbackDays = DEFAULT_PRICE_LOOKBACK_DAYS,
  interval = "15min",
): Promise<TradingDayCoverage> {
  const result = await getJSON<TradingDayCoverage>(
    `/market-data/trading-days?lookback_days=${lookbackDays}&interval=${encodeURIComponent(interval)}`,
  );
  return { ...result, history_gaps: "history_gaps" in result ? parseCoverageHistoryGaps(result.history_gaps) : [] };
}

// --- News feed (score-free, local-first over news + FTS5) ---

export type NewsContentAvailability = "full" | "headline_only" | "unknown";
export type NewsContentRecovery = "retryable" | "terminal";
export type NewsContentFilter = "all" | NewsContentAvailability;

export interface NewsFeedItem {
  published_at: string; // full UTC timestamp
  ticker: string;
  title: string;
  url: string | null;
  publisher: string | null;
  source: string; // massive (durable value: polygon) | finnhub | ibkr
  description: string | null;
  content_availability?: NewsContentAvailability;
  content_recovery?: NewsContentRecovery | null;
}

export interface NewsFeedResponse {
  available: boolean; // false when the local news table is unavailable
  items: NewsFeedItem[];
  total: number;
  sources: Record<string, number>;
  days: Record<string, number>; // YYYY-MM-DD → count (same filters)
  content_counts?: Record<NewsContentAvailability, number>;
}

export function getNewsFeed(params: {
  q?: string;
  ticker?: string;
  source?: string;
  days?: number;
  limit?: number;
  offset?: number;
  content?: NewsContentFilter;
}): Promise<NewsFeedResponse> {
  const sp = new URLSearchParams();
  if (params.q) sp.set("q", params.q);
  if (params.ticker) sp.set("ticker", params.ticker);
  if (params.source && params.source !== "auto") sp.set("source", params.source);
  if (params.days) sp.set("days", String(params.days));
  if (params.limit) sp.set("limit", String(params.limit));
  if (params.offset) sp.set("offset", String(params.offset));
  if (params.content && params.content !== "all") sp.set("content", params.content);
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

export type SAFeedEmptyReason =
  | "backend_unavailable"
  | "requires_local_sa"
  | "store_not_created"
  | "store_missing"
  | "store_unreadable"
  | "store_schema_incompatible"
  | "store_query_failed"
  | "no_items_in_window"
  | null;

export interface SAFeedResponse {
  available: boolean; // false = typed unavailable state, not an HTTP error
  days: number;
  query: string | null;
  total: number;
  items: SAFeedItem[];
  by_type: Record<string, number>;
  by_day: Record<string, number>;
  empty_reason: SAFeedEmptyReason;
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

export type SAExtensionChainState = "available" | "degraded" | "interrupted";
export type SAExtensionCaptureOutcome = "complete" | "skipped" | "degraded" | "failed";
export type SAExtensionJobName = "sa_alpha_picks_refresh" | "sa_market_news_refresh";
export type SAExtensionDiagnosticsStatus = "recorded" | "rejected" | "absent";
export type SAExtensionDiagnosticStage =
  | "tab_navigation"
  | "page_readiness"
  | "script_injection"
  | "content_parse"
  | "native_transport"
  | "local_persistence"
  | "reconciliation"
  | "extension_runtime";
export type SAExtensionDiagnosticTargetKind =
  | "article_detail"
  | "article_comments"
  | "market_news_detail"
  | "phase";
export type SAExtensionDiagnosticReason =
  | "access_restricted"
  | "login_required"
  | "modal_blocked"
  | "navigation_timeout"
  | "detail_timeout"
  | "dom_not_ready"
  | "parser_empty"
  | "native_host_unavailable"
  | "detail_save_failed"
  | "extension_dependency_missing"
  | "interrupted"
  | "unknown_failure"
  | "protocol_invalid"
  | "manifest_invalid"
  | "current_scope_failed"
  | "closed_scope_failed"
  | "article_metadata_failed"
  | "article_detail_failed"
  | "comment_scan_failed"
  | "reconciliation_failed"
  | "list_navigation_failed"
  | "list_scrape_failed"
  | "metadata_save_failed"
  | "detail_queue_failed"
  | "capture_readback_failed"
  | "tab_closed"
  | "browser_api_failed"
  | "script_injection_failed"
  | "native_response_invalid"
  | "database_busy"
  | "database_integrity_failed"
  | "database_write_failed";

export interface SAExtensionDiagnosticEntry {
  occurred_at: string;
  stage: SAExtensionDiagnosticStage;
  reason_code: SAExtensionDiagnosticReason;
  target_kind: SAExtensionDiagnosticTargetKind;
  target_ref?: string;
  retryable: boolean;
  attempt_count: number;
  message?: string;
}

export interface SAExtensionDiagnosticRecurrence {
  job_name: SAExtensionJobName;
  stage: SAExtensionDiagnosticStage;
  reason_code: SAExtensionDiagnosticReason;
  affected_run_count: number;
  latest_occurred_at: string;
}

export interface SAExtensionHealthSegment {
  key: string;
  state: "ok" | "warn" | "fail";
  detail?: string | null;
  code?: string | null;
  counts?: Record<string, number> | null;
  run_id?: number | null;
  manifest_hash_prefix?: string | null;
  occurred_at?: string | null;
  job_name?: SAExtensionJobName | null;
  outcome?: SAExtensionCaptureOutcome | null;
  diagnostics_status?: SAExtensionDiagnosticsStatus | null;
  diagnostics_error_code?: "invalid_extension_diagnostics" | null;
  diagnostics?: SAExtensionDiagnosticEntry[];
  diagnostics_omitted_count?: number;
  diagnostic_recurrence?: SAExtensionDiagnosticRecurrence[];
}

export interface SAExtensionHealthResponse {
  chain_state: SAExtensionChainState;
  generated_at: string;
  segments: SAExtensionHealthSegment[];
}

export function getSAExtensionHealth(): Promise<SAExtensionHealthResponse> {
  return getJSON<SAExtensionHealthResponse>("/sa/extension-health", 8_000);
}

// --- provider health (slice 3e-A; PURE READ — no provider fetch) ---
// Per-provider DTO is ProviderRun-compatible (Slice 5's per-call telemetry plugs
// in without reshaping). maintenance = derived (e.g. IBKR weekend); disabled is a
// state, never an HTTP error. Key info is presence+source only (strict default =
// real env > app DB; config/.env is import material unless explicit fallback is on; the entry UI is the Data Sources "連線與金鑰"
// panel — see getProvidersConfig/putProviderConfig below).

export type ProviderStatus =
  | "connected" | "stale" | "maintenance" | "no_signal" | "not_configured" | "missing_key" | "disabled";

export interface ProviderConfigError {
  code: "provider_config_missing";
  status: "not_configured";
  provider: string;
  field: string;
}

export interface ProviderHealth {
  id: string;
  label: string;
  kind: string; // market | news | macro | fundamentals | capture
  key_present: boolean;
  key_source: string; // app | env | config/.env | missing | mixed | not_required
  key_import_suggested: boolean;
  key_vars: string[];
  enabled: boolean | null; // null = no toggle exists for this provider
  disabled_reason?: string | null;
  status: ProviderStatus;
  config_error?: ProviderConfigError | null;
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
// All sources are DISABLED by default; enabling one makes the sidecar collect on its
// retired mirror routes; the backend owns those presentation labels. Run-now is fire-and-return;
// poll getSchedule() for the per-source running flag and the job_runs row
// (collect.<source>, visible in getProvidersHealth().jobs) for the outcome.

export interface ScheduleContinuationCounts {
  deferred_ticker_count?: number;
  deferred_body_count?: number;
  has_cursor?: boolean;
}

export interface ScheduleBodyBacklog {
  status: "ok" | "unavailable";
  due_now?: number;
  scheduled_later?: number;
  never_attempted?: number;
  provider_not_entitled?: number;
  earliest_next_retry_at?: string | null;
}

export interface ScheduleWorkerLegs {
  retry: "succeeded" | "partial" | "failed";
  fresh: "succeeded" | "partial" | "failed";
}

export interface ScheduleRunResult {
  source: string;
  status: string;
  reason?: string;
  at?: string;
  price_repair_id?: string;
  price_repair?: { remaining_tickers: string[]; observation_health: string; lookback_days: number; as_of_date: string };
  collect?: {
    status?: "succeeded" | "partial" | "failed";
    continuation?: ScheduleContinuationCounts | null;
    legs?: ScheduleWorkerLegs;
    body_backlog?: ScheduleBodyBacklog;
    retry_bodies_attempted?: number;
    retry_bodies_fetched?: number;
    tickers_scanned?: number;
    headline_pages_requested?: number;
    headline_saturated_tickers?: number;
    headline_incomplete_tickers?: number;
    succeeded_ticker_count?: number;
    gaps_found?: number;
    rows_added?: number;
    error_count?: number;
    error_tickers?: string[];
    unresolved_after_fetch_count?: number;
    unresolved_after_fetch_tickers?: string[];
  } | null;
}

export interface ScheduleSourceState {
  label: string;
  description: string;
  ibkr: boolean;
  provider_fetch: boolean; // false = app-native (no external fetch)
  source_mode: string;
  write_target: string;
  source_badges: string[];
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
  last_result: ScheduleRunResult | null;
  // v1.4: durable per-source state (survives restart). last_status 'partial' → a budget-bounded
  // run left a continuation that needs a manual continue; 'failed' carries last_error.
  durable_state: {
    last_status: string | null; // running | succeeded | failed | partial
    last_error: string | null;
    continuation: { deferred?: string[]; lookback_days?: number; candidate_count?: number } | null;
    last_result?: ScheduleRunResult | null;
    last_attempt: string | null;
    updated_at: string | null;
    running_for_seconds?: number | null;
    running_stale?: boolean;
    running_stale_reason?: string | null;
  } | null;
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
// so the change reaches all call sites without a restart. Strict precedence:
// real env var > app value; config/.env is import material unless explicit fallback is on.

export interface ProviderConfigField {
  field: string; // api_key | host | port
  label: string;
  secret: boolean;
  env_var: string;
  app_value_set: boolean;
  app_value_masked: string | null;
  effective_source: string; // app | env | config/.env | missing
  needs_import: boolean;
  import_source: string | null;
  importable_env_vars: string[];
  defaulted: boolean;
  guarded: boolean;
  guard_reason: string | null;
  // present only on the IBKR client_id field: derived per-domain ids
  client_id_domains?: {
    domain: string;
    label: string;
    offset: number;
    effective_id: number | null;
  }[];
}

export interface ProviderConfigEntry {
  fields: ProviderConfigField[];
  testable: boolean;
  default_available: boolean; // key-free + extension-free (e.g. SEC EDGAR)
}

export interface ProviderConfigSetupState {
  required: boolean;
  code: string | null;
  reason: string | null;
}

export interface ProviderEnvFallbackState {
  enabled: boolean;
  source: "default" | "profile" | "env" | string;
}

export interface ProvidersConfigResponse {
  providers: Record<string, ProviderConfigEntry>;
  setup: ProviderConfigSetupState;
  env_fallback: ProviderEnvFallbackState;
}

export function getProvidersConfig(): Promise<ProvidersConfigResponse> {
  return getJSON<ProvidersConfigResponse>("/providers/config", 8_000);
}

export function putProviderConfig(
  provider: string,
  fields: Record<string, string | null>,
  confirmGuarded?: Record<string, boolean>,
): Promise<ProviderConfigEntry> {
  return sendJSON(
    `/providers/config/${encodeURIComponent(provider)}`,
    "PUT",
    { fields, confirm_guarded: confirmGuarded ?? {} },
    8_000,
  );
}

export function putProviderEnvFallback(
  enabled: boolean | null,
): Promise<ProviderEnvFallbackState> {
  return sendJSON("/providers/config/env-fallback", "PUT", { enabled }, 8_000);
}

export function importProviderConfigField(
  provider: string,
  field: string,
  sourceEnvVar?: string | null,
  confirmGuarded = false,
): Promise<ProviderConfigEntry> {
  return sendJSON(
    `/providers/config/${encodeURIComponent(provider)}/${encodeURIComponent(field)}/import-env`,
    "POST",
    { source_env_var: sourceEnvVar ?? null, confirm_guarded: confirmGuarded },
    8_000,
  );
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
