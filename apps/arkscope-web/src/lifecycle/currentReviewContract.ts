import { LISTING_CHECK_NAMES, LISTING_PROVIDER_ISSUES, LISTING_PROVIDER_NAMES } from "./listingContract";
import type { TickerIdentityHistoryDecision, TickerIdentityTransitionBlockReason } from "../api";
import { parseWebRun, parseWebSourceGaps } from "./webContract";

export const CURRENT_REVIEW_REASONS = [
  "provider_confirmation_missing", "source_missing", "active_confirmed", "continuation_requires_confirmation",
  "removal_requires_confirmation", "provider_confirmation_incomplete", "regulator_event_pending", "regulator_identity_question",
  "listing_identity_changed", "superseded_listing_identity", "prior_action_history", "action_needs_review", "action_scheduled",
  "action_pending", "listing_reappeared_after_action", "listing_recheck_required", "removal_applied",
  "continuation_followup_pending", "symbol_change_applied", "applied_state_changed",
] as const;
export const CURRENT_ACTION_STATES = ["not_prepared", "approved", "scheduled", "applied", "blocked", "cancelled", "reversed", "applied_state_changed"] as const;
const SOURCES = ["manual_lists", "portfolio_open", "sa_alpha_picks_current", "sa_alpha_picks_former", "legacy_config_seed"] as const;
const OUTCOMES = ["undetermined", "listing_ended", "venue_transfer", "symbol_changed", "symbol_or_venue_changed", "acquisition_cash",
  "acquisition_stock", "acquisition_mixed", "acquisition_terms_unknown", "issuer_security_change", "no_tracked_security_change", "other", "not_applicable"] as const;
export function invalidCurrentPayload(): never { throw new Error("lifecycle_current_payload_invalid"); }
function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return invalidCurrentPayload();
  return value as Record<string, unknown>;
}
function text(value: unknown): string {
  if (typeof value !== "string" || !value.trim() || value.includes("\0")) return invalidCurrentPayload();
  return value;
}
function bool(value: unknown): boolean { if (typeof value !== "boolean") return invalidCurrentPayload(); return value; }
function integer(value: unknown): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 0) return invalidCurrentPayload(); return value;
}
function choice<const T extends readonly string[]>(value: unknown, values: T): T[number] {
  if (typeof value !== "string" || !values.includes(value)) return invalidCurrentPayload(); return value as T[number];
}
function nullable<T>(value: unknown, parse: (x: unknown) => T): T | null { return value === null ? null : parse(value); }
function array<T>(value: unknown, parse: (x: unknown) => T): T[] {
  if (!Array.isArray(value)) return invalidCurrentPayload(); return value.map(parse);
}
function unique(value: unknown): string[] {
  const result = array(value, text); if (new Set(result).size !== result.length) return invalidCurrentPayload(); return result;
}
function day(value: unknown): string {
  const raw = text(value);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(raw)) return invalidCurrentPayload();
  const parsed = new Date(raw + "T00:00:00Z");
  if (!Number.isFinite(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== raw) return invalidCurrentPayload();
  return raw;
}
function timestamp(value: unknown): string {
  const raw = text(value);
  if (!/^\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d+)?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)$/.test(raw)
      || !Number.isFinite(Date.parse(raw))) return invalidCurrentPayload();
  day(raw.slice(0, 10)); return raw;
}
function dateOrTime(value: unknown): string { return typeof value === "string" && value.length === 10 ? day(value) : timestamp(value); }
function digest(value: unknown): string { const raw = text(value); if (!/^[a-f0-9]{64}$/.test(raw)) return invalidCurrentPayload(); return raw; }
function sources(value: unknown) { return array(value, (x) => choice(x, SOURCES)); }
function url(value: unknown): string {
  const raw = text(value);
  try {
    const parsed = new URL(raw);
    if (!["https:", "http:"].includes(parsed.protocol) || parsed.username || parsed.password) return invalidCurrentPayload();
  } catch { return invalidCurrentPayload(); }
  return raw;
}
function version(row: Record<string, unknown>) { if (row.version !== 1) invalidCurrentPayload(); }

function parseCurrentReview(value: unknown) {
  const row = object(value), collection = object(row.collection), listing = object(row.listing), continuation = object(row.continuation);
  const action = object(row.next_action), diagnostic = object(row.diagnostics);
  const result = {
    review_id: text(row.review_id), case_ids: unique(row.case_ids), ticker: text(row.ticker), issuer_name: nullable(row.issuer_name, text),
    bucket: choice(row.bucket, ["attention", "history"]), finding: choice(row.finding, ["unresolved", "active", "old_listing_inactive", "replacement_confirmed"]),
    reason: choice(row.reason, CURRENT_REVIEW_REASONS),
    collection: { state: choice(collection.state, ["tracking", "not_tracking", "unavailable", "historical"]), sources: sources(collection.sources) },
    listing: { state: choice(listing.state, ["unresolved", "active", "inactive"]), basis: choice(listing.basis, ["observation", "applied_receipt"]), ended_on: nullable(listing.ended_on, day) },
    continuation: { state: choice(continuation.state, ["unavailable", "confirmed", "not_observed", "candidate", "ambiguous"]),
      successor_ticker: nullable(continuation.successor_ticker, text), candidate_tickers: unique(continuation.candidate_tickers) },
    observed_at: nullable(row.observed_at, timestamp), next_check_at: nullable(row.next_check_at, timestamp),
    diagnostics: { code: choice(diagnostic.code, ["listing_checks"]), missing_checks: array(diagnostic.missing_checks, (x) => choice(x, LISTING_CHECK_NAMES)),
      provider_issues: array(diagnostic.provider_issues, (x) => { const r = object(x); return { provider: choice(r.provider, LISTING_PROVIDER_NAMES), reason: choice(r.reason, LISTING_PROVIDER_ISSUES) }; }),
      manual_review_required: bool(diagnostic.manual_review_required) },
    next_action: { kind: choice(action.kind, ["review_removal", "review_symbol_change", "recheck", "resume", "none"]), state: choice(action.state, CURRENT_ACTION_STATES),
      case_id: text(action.case_id), assessment_id: nullable(action.assessment_id, text), transition_id: nullable(action.transition_id, text),
      transition_kind: nullable(action.transition_kind, (x) => choice(x, ["terminal_delisting", "symbol_continuation"])),
      preview_sha256: nullable(action.preview_sha256, digest), execute_on: nullable(action.execute_on, day),
      current_effects_match: nullable(action.current_effects_match, bool), can_reverse: bool(action.can_reverse), block_reasons: unique(action.block_reasons) },
    source_checks: array(row.source_checks, (x) => { const r = object(x); return {
      provider: choice(r.provider, LISTING_PROVIDER_NAMES), check: choice(r.check, ["delisting", "stocks", "otc", "eodhd", "nasdaq", "continuation"]),
      directory: nullable(r.directory, (x) => choice(x, ["nasdaq_listed", "other_listed"])),
      status: choice(r.status, ["active", "inactive", "not_found", "observed", "not_observed"]),
      ticker: text(r.ticker), observed_at: timestamp(r.observed_at), url: nullable(r.url, url),
    }; }),
    source_notices: array(row.source_notices, (x) => { const r = object(x); return {
      form: text(r.form), filed_on: day(r.filed_on), text: nullable(r.text, text), url: nullable(r.url, url),
    }; }),
  };
  const a = result.next_action;
  if (!result.case_ids.length || !result.case_ids.includes(a.case_id)
      || (result.collection.state === "tracking") !== (result.collection.sources.length > 0)
      || (a.state === "applied" && a.current_effects_match !== true)
      || (a.state === "applied_state_changed" && a.current_effects_match !== false)
      || (a.can_reverse && a.state !== "applied")
      || (a.state === "not_prepared" && [a.transition_id, a.preview_sha256, a.execute_on, a.transition_kind].some((value) => value !== null))
      || (!["applied", "applied_state_changed"].includes(a.state) && a.current_effects_match !== null)
      || (a.state !== "not_prepared" && (!a.transition_id || !a.preview_sha256 || !a.execute_on || !a.transition_kind))
      || (a.kind === "resume" && a.state !== "approved")
      || (["review_removal", "review_symbol_change"].includes(a.kind) && (!a.assessment_id || a.state !== "not_prepared"))
      || result.source_checks.some((r) => (r.provider === "nasdaq") !== (r.directory !== null))
      || (result.continuation.state === "confirmed" && !result.continuation.successor_ticker)) return invalidCurrentPayload();
  return result;
}

export type CurrentLifecycleReview = ReturnType<typeof parseCurrentReview>;
export function parseCurrentReviewList(value: unknown) {
  const row = object(value); version(row);
  const coverage = object(row.coverage), counts = object(row.counts), page = object(row.page);
  const result = { version: 1 as const, as_of: timestamp(row.as_of), source_context: choice(row.source_context, ["available", "unavailable"]),
    coverage: { tracked: nullable(coverage.tracked, integer), confirmed_active: nullable(coverage.confirmed_active, integer), unconfirmed: nullable(coverage.unconfirmed, integer) },
    counts: { attention: integer(counts.attention), history: integer(counts.history) }, items: array(row.items, parseCurrentReview),
    page: { offset: integer(page.offset), limit: integer(page.limit), total: integer(page.total) } };
  const c = result.coverage, p = result.page;
  if (result.source_context === "available" ? (c.tracked === null || c.confirmed_active === null || c.unconfirmed === null || c.tracked !== c.confirmed_active + c.unconfirmed)
      : (c.tracked !== null || c.confirmed_active !== null || c.unconfirmed !== null)) return invalidCurrentPayload();
  if (!p.limit || p.limit > 200 || result.items.length > p.limit || result.items.length !== Math.min(p.limit, Math.max(0, p.total - p.offset))
      || new Set(result.items.map((item) => item.review_id)).size !== result.items.length
      || p.total > result.counts.attention + result.counts.history) return invalidCurrentPayload();
  return result;
}
export type CurrentLifecycleReviewList = ReturnType<typeof parseCurrentReviewList>;
export function parseCurrentReviewDetail(value: unknown) {
  const row = object(value); version(row);
  const item = parseCurrentReview(row.item), web_runs = "web_runs" in row ? array(row.web_runs, (value) => {
    const run = parseWebRun(value); if (!run) return invalidCurrentPayload(); return run;
  }) : [];
  if (web_runs.some((run) => !item.case_ids.includes(run.case_id) || run.ticker !== item.ticker)
      || new Set(web_runs.map((run) => run.case_id)).size !== web_runs.length) return invalidCurrentPayload();
  return { version: 1 as const, as_of: timestamp(row.as_of), item, web_runs };
}

export function parseLifecycleReviewPacket(value: unknown) {
  const row = object(value); version(row);
  const effects = object(row.effects), priority = object(effects.priority), suppression = object(effects.suppression), finding = object(row.finding), options = object(row.options);
  function grouped<T>(value: unknown, parse: (value: unknown) => T) {
    const r = object(value); return { add: array(r.add, parse), archive: array(r.archive, parse), reactivate: array(r.reactivate, parse), unchanged: array(r.unchanged, parse) };
  }
  const result = {
    version: 1 as const, case_id: text(row.case_id), assessment_id: text(row.assessment_id), packet_sha256: digest(row.packet_sha256),
    source_ticker: text(row.source_ticker), action: nullable(row.action, (x) => choice(x, ["terminal_delisting", "symbol_continuation"])),
    execute_on: nullable(row.execute_on, day), provider_observed_at: nullable(row.provider_observed_at, timestamp),
    active_sources: sources(row.active_sources), caveats: unique(row.caveats), ready: bool(row.ready), block_reasons: unique(row.block_reasons),
    source_gaps: row.source_gaps === undefined ? null : nullable(row.source_gaps, parseWebSourceGaps),
    effects: {
      watchlists: grouped(effects.watchlists, (x) => { const r = object(x); return { list_name: text(r.list_name), ticker: text(r.ticker) }; }),
      legacy_config_seed: grouped(effects.legacy_config_seed, (x) => { const r = object(x); return { source_key: text(r.source_key), ticker: text(r.ticker) }; }),
      editable_tags_to_copy: array(effects.editable_tags_to_copy, (x) => { const r = object(x); return { facet: text(r.facet), value: text(r.value), source: text(r.source), ticker: text(r.ticker) }; }),
      priority: { resolution: nullable(priority.resolution, (x) => choice(x, ["source", "successor"])), result_value: nullable(priority.result_value, text),
        source_value: nullable(priority.source_value, text), successor_value: nullable(priority.successor_value, text), write_successor: bool(priority.write_successor) },
      suppression: { hide_source: bool(suppression.hide_source), source_hidden: bool(suppression.source_hidden), successor_hidden: bool(suppression.successor_hidden), unhide_successor: bool(suppression.unhide_successor) },
      ...("sa_tracking_memberships" in effects ? { sa_tracking_memberships: array(effects.sa_tracking_memberships, (x) => { const r = object(x); return {
        ticker: text(r.ticker), picked_date: day(r.picked_date), portfolio_status: choice(r.portfolio_status, ["current", "closed"]), current_tracking: bool(r.current_tracking), removed: bool(r.removed),
      }; }) } : {}),
    },
    finding: { conclusion: text(finding.conclusion), impact_summary: text(finding.impact_summary),
      relevance: choice(finding.relevance, ["undetermined", "direct_tracked_security", "issuer_related", "unrelated"]), confidence: choice(finding.confidence, ["unknown", "low", "medium", "high"]),
      outcomes: array(finding.outcomes, (x) => choice(x, OUTCOMES)), successor_ticker: nullable(finding.successor_ticker, text), destination_venue: nullable(finding.destination_venue, text),
      effective_date: nullable(finding.effective_date, day), counterparty_name: nullable(finding.counterparty_name, text), counterparty_ticker: nullable(finding.counterparty_ticker, text),
      counterparty_cik: nullable(finding.counterparty_cik, text), consideration_currency: nullable(finding.consideration_currency, text),
      cash_per_security_decimal: nullable(finding.cash_per_security_decimal, text), exchange_ratio_decimal: nullable(finding.exchange_ratio_decimal, text) },
    options: { execute_on: nullable(options.execute_on, day), priority_resolution: nullable(options.priority_resolution, (x) => choice(x, ["source", "successor"])), unhide_successor: bool(options.unhide_successor) },
    source_references: array(row.source_references, (x) => { const r = object(x); return {
      evidence_id: text(r.evidence_id), kind: text(r.kind), source_family: text(r.source_family), adapter: text(r.adapter),
      source_url: nullable(r.source_url, url), title: nullable(r.title, text), publisher: nullable(r.publisher, text), domain: nullable(r.domain, text),
      source_published_at: nullable(r.source_published_at, dateOrTime), retrieved_at: nullable(r.retrieved_at, timestamp),
      mime_type: nullable(r.mime_type, text), document_status: nullable(r.document_status, text),
    }; }),
  };
  if (!result.finding.outcomes.length || (result.ready && (!result.action || !result.execute_on || result.block_reasons.length))
      || (result.options.execute_on !== null && result.execute_on !== result.options.execute_on)) return invalidCurrentPayload();
  return result;
}
export type LifecycleReviewPacket = ReturnType<typeof parseLifecycleReviewPacket>;

export function parseLifecycleReviewConfirmation(value: unknown) {
  const row = object(value); version(row);
  const result = { version: 1 as const, status: choice(row.status, ["applied", "already_applied", "applied_state_changed", "approved", "scheduled", "blocked", "cancelled", "reversed"]),
    transition_id: text(row.transition_id), case_id: text(row.case_id), packet_sha256: digest(row.packet_sha256),
    action: choice(row.action, ["terminal_delisting", "symbol_continuation"]), source_ticker: text(row.source_ticker), successor_ticker: nullable(row.successor_ticker, text),
    execute_on: day(row.execute_on), applied_at: nullable(row.applied_at, timestamp), current_effects_match: nullable(row.current_effects_match, bool), block_reasons: unique(row.block_reasons) };
  if ((["applied", "already_applied"].includes(result.status) && (result.current_effects_match !== true || !result.applied_at))
      || (!["applied", "already_applied", "applied_state_changed"].includes(result.status) && result.current_effects_match !== null)
      || (result.status === "applied_state_changed" && result.current_effects_match !== false)) return invalidCurrentPayload();
  return result;
}
export type LifecycleReviewConfirmation = ReturnType<typeof parseLifecycleReviewConfirmation>;

function historyUrl(value: unknown) {
  const raw = url(value), parsed = new URL(raw);
  if (parsed.protocol !== "https:" || Array.from(parsed.searchParams.keys()).some((key) =>
    ["token", "key", "secret", "signature", "credential", "authorization"].some((part) => key.toLowerCase().includes(part)))) return invalidCurrentPayload();
  return raw;
}

function parseHistoryDecision(value: unknown): TickerIdentityHistoryDecision {
  const row = object(value);
  const result = {
    summary: nullable(row.summary, text), impact: nullable(row.impact, text),
    method: choice(row.method, ["provider_review", "manual_review", "rule_engine", "llm_investigation", "unknown"]),
    approval_authority: choice(row.approval_authority, ["attended_user", "automation_policy"]),
    event_date: nullable(row.event_date, day), observed_at: nullable(row.observed_at, timestamp),
    model: nullable(row.model, (value) => { const r = object(value); return {
      provider: choice(r.provider, ["openai", "anthropic"]), auth_mode: choice(r.auth_mode, ["api_key", "chatgpt_oauth", "claude_code_oauth"]), model: text(r.model),
    }; }),
    sources: array(row.sources, (value) => { const r = object(value); return {
      name: nullable(r.name, text), url: nullable(r.url, historyUrl), title: nullable(r.title, text),
      published_at: nullable(r.published_at, text), observed_at: nullable(r.observed_at, timestamp),
      kind: choice(r.kind, ["listing_snapshot", "ticker_events", "document", "local_news", "manual"]),
      ticker: nullable(r.ticker, text), listing_status: nullable(r.listing_status, (x) => choice(x, ["active", "inactive", "not_found", "unverified"])), market: nullable(r.market, text),
    }; }),
    limitations: array(row.limitations, text),
    source_gaps: array(row.source_gaps, (value) => { const r = object(value); return { url: nullable(r.url, historyUrl), reason: text(r.reason) }; }),
    gaps: array(row.gaps, (x) => choice(x, ["assessment_missing", "record_invalid", "sources_missing", "model_missing", "source_link_omitted", "legacy_assessment_unsealed"])),
  };
  if (result.model && (result.method !== "llm_investigation"
      || (result.model.auth_mode === "chatgpt_oauth" && result.model.provider !== "openai")
      || (result.model.auth_mode === "claude_code_oauth" && result.model.provider !== "anthropic"))) return invalidCurrentPayload();
  if ((result.method === "llm_investigation" && !result.model && !result.gaps.includes("model_missing"))
      || (result.summary === null && !result.gaps.length)) return invalidCurrentPayload();
  return result;
}

export function parseCurrentActivity(value: unknown) {
  const row = object(value);
  const result = {
    activity_id: text(row.activity_id), transition_id: text(row.transition_id), case_id: text(row.case_id),
    activity_type: choice(row.activity_type, ["applied", "reversed"]), source_ticker: text(row.source_ticker),
    successor_ticker: nullable(row.successor_ticker, text), effective_date: day(row.effective_date),
    user_owned_changes: array(row.user_owned_changes, (value) => { const r = object(value); return {
      change_type: choice(r.change_type, ["sa_membership_suppressed", "editable_tag_copied", "legacy_membership_added", "legacy_membership_archived",
        "legacy_membership_reactivated", "priority_updated", "source_hidden", "successor_unhidden", "watchlist_membership_added", "watchlist_membership_archived", "watchlist_membership_reactivated"]),
      count: integer(r.count),
    }; }),
    provider_owned_retained: sources(row.provider_owned_retained), state_sha256: digest(row.state_sha256),
    rule_id: nullable(row.rule_id, text), rule_version: nullable(row.rule_version, text), decision_provenance_sha256: digest(row.decision_provenance_sha256),
    occurred_at: timestamp(row.occurred_at), acknowledged_at: nullable(row.acknowledged_at, timestamp), created_at: timestamp(row.created_at),
    ...("decision" in row ? { decision: parseHistoryDecision(row.decision) } : {}),
    ...("reverse_readiness" in row ? { reverse_readiness: nullable(row.reverse_readiness, (value) => {
      const r = object(value);
      return { reversible: bool(r.reversible), block_reasons: unique(r.block_reasons) as TickerIdentityTransitionBlockReason[] };
    }) } : {}),
  };
  if (result.reverse_readiness?.reversible && result.reverse_readiness.block_reasons.length) return invalidCurrentPayload();
  return result;
}

export function parseCurrentActivityList(value: unknown) {
  const row = object(value);
  const result = { items: array(row.items, parseCurrentActivity), count: integer(row.count), unacknowledged_count: integer(row.unacknowledged_count) };
  if (result.count < result.items.length || result.unacknowledged_count > result.count
      || new Set(result.items.map((item) => item.activity_id)).size !== result.items.length) return invalidCurrentPayload();
  return result;
}
