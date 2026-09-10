function invalid(): never { throw new Error("investigation_payload_invalid"); }
function object(value: unknown): Record<string, unknown> { if (!value || typeof value !== "object" || Array.isArray(value)) return invalid(); return value as Record<string, unknown>; }
function text(value: unknown): string { if (typeof value !== "string" || !value.trim() || value.includes("\0")) return invalid(); return value; }
function bool(value: unknown): boolean { if (typeof value !== "boolean") return invalid(); return value; }
function num(value: unknown): number { if (typeof value !== "number" || !Number.isFinite(value) || value < 0) return invalid(); return value; }
function count(value: unknown): number { const x = num(value); if (!Number.isSafeInteger(x)) return invalid(); return x; }
function one<const T extends readonly string[]>(value: unknown, values: T): T[number] { if (typeof value !== "string" || !values.includes(value)) return invalid(); return value as T[number]; }
function nullable<T>(value: unknown, parse: (value: unknown) => T): T | null { return value === null ? null : parse(value); }
function array<T>(value: unknown, parse: (value: unknown) => T): T[] { if (!Array.isArray(value)) return invalid(); return value.map(parse); }
function date(value: unknown) { const x = text(value); if (!/^\d{4}-\d{2}-\d{2}$/.test(x) || !Number.isFinite(Date.parse(x)) || new Date(x).toISOString().slice(0, 10) !== x) return invalid(); return x; }
function time(value: unknown) { const x = text(value); if (!/^\d{4}-\d{2}-\d{2}T/.test(x) || !Number.isFinite(Date.parse(x))) return invalid(); return x; }
function url(value: unknown) { const x = text(value); try { const u = new URL(x); if (u.protocol !== "https:" || u.username || u.password) return invalid(); } catch { return invalid(); } return x; }
function digest(value: unknown) { const x = text(value); if (!/^[a-f0-9]{64}$/.test(x)) return invalid(); return x; }
function ticker(value: unknown) { const x = text(value); if (!/^[A-Z0-9]{1,8}(?:[ .-][A-Z0-9]{1,8})?$/.test(x)) return invalid(); return x; }
function target(value: unknown) { const r = object(value); return { ticker: ticker(r.ticker), issuer_name: nullable(r.issuer_name, text),
  security_class: nullable(r.security_class, text), venue: nullable(r.venue, text), as_of: date(r.as_of),
  identity_status: one(r.identity_status, ["observed", "needs_lookup", "conflicting"]),
  issuer_cik: nullable(r.issuer_cik, text), composite_figi: nullable(r.composite_figi, text) }; }
function execution(value: unknown) { const r = object(value), provider = one(r.provider, ["openai", "anthropic"]),
  auth_mode = one(r.auth_mode, ["api_key", "chatgpt_oauth", "claude_code_oauth"]);
  if ((provider === "openai" && auth_mode === "claude_code_oauth") || (provider === "anthropic" && auth_mode === "chatgpt_oauth")) return invalid();
  return { provider, auth_mode, model: text(r.model), effort: text(r.effort) }; }

export const INVESTIGATION_LIMITS = { model_submissions: [1, 128], web_actions: [1, 192], source_reads: [1, 128],
  http_requests: [1, 512], local_queries: [1, 128], deadline_seconds: [60, 7200], model_timeout_seconds: [30, 1800],
  api_output_tokens: [1024, 131072], retained_source_mib: [128, 2048] } as const;
export type InvestigationRuntime = { [K in keyof typeof INVESTIGATION_LIMITS]: number };
export function parseInvestigationRuntime(value: unknown): InvestigationRuntime {
  const r = object(value), keys = Object.keys(INVESTIGATION_LIMITS) as (keyof InvestigationRuntime)[];
  if (Object.keys(r).length !== keys.length || Object.keys(r).some(key => !(key in INVESTIGATION_LIMITS))) return invalid();
  return Object.fromEntries(keys.map(key => { const n = count(r[key]), [min, max] = INVESTIGATION_LIMITS[key];
    if (n < min || n > max) return invalid(); return [key, n]; })) as InvestigationRuntime;
}
export function parseInvestigationTargets(value: unknown) { const r = object(value); if (r.version !== 2) return invalid();
  const rows = array(r.targets, value => ({ ticker: ticker(object(value).ticker) }));
  if (new Set(rows.map(row => row.ticker)).size !== rows.length) return invalid(); return rows; }
export function parseInvestigationPreflight(value: unknown) {
  const r = object(value); if (r.version !== 2) return invalid();
  const result = { version: 2 as const, ticker: ticker(r.ticker), available: bool(r.available), reason: nullable(r.reason, text),
    preflight_sha256: nullable(r.preflight_sha256, digest), target: nullable(r.target, target), execution: nullable(r.execution, execution),
    credential_label: nullable(r.credential_label, text), limits: nullable(r.limits, value => { const v = object(value);
      const runtime = Object.fromEntries(Object.keys(INVESTIGATION_LIMITS).map(key => [key, v[key]]));
      return { ...parseInvestigationRuntime(runtime), output_control: one(v.output_control, ["provider", "configured"]),
        search_enforcement: one(v.search_enforcement, ["observed", "enforced"]) }; }) };
  if (result.available ? (!!result.reason || !result.preflight_sha256 || !result.target || !result.execution || !result.limits || !result.credential_label)
    : (!result.reason || [result.preflight_sha256, result.target, result.execution, result.limits, result.credential_label].some(x => x !== null))) return invalid();
  if (result.target && result.target.ticker !== result.ticker) return invalid();
  return result;
}
export type InvestigationPreflight = ReturnType<typeof parseInvestigationPreflight>;
export function parseInvestigationStart(value: unknown) {
  const row = object(value);
  return { run_id: text(row.run_id), created: bool(row.created) };
}
function finding(value: unknown) { const r = object(value); if (r.version !== 2) return invalid(); return {
  version: 2 as const, source_ticker: ticker(r.source_ticker), issuer_name: text(r.issuer_name), security_class: text(r.security_class), venue: text(r.venue),
  event_kind: one(r.event_kind, ["listing_ended", "symbol_continuation", "active_listing", "acquisition_announced", "trading_suspended", "unresolved"]),
  timing: one(r.timing, ["completed", "scheduled", "unknown"]), successor_ticker: nullable(r.successor_ticker, ticker),
  effective_date: nullable(r.effective_date, date), summary: text(r.summary), contradictions: array(r.contradictions, text),
  unresolved_conditions: array(r.unresolved_conditions, text), limitations: array(r.limitations, text), citations: array(r.citations, value => { const v = object(value);
    return { passage_id: text(v.passage_id), supports: array(v.supports, text) }; }) }; }
export function parseInvestigationRun(value: unknown) {
  const r = object(value); if (r.version !== 2) return invalid();
  const result = { version: 2 as const, run_id: text(r.run_id), ticker: ticker(r.ticker),
    status: one(r.status, ["running", "succeeded", "incomplete", "failed", "cancelled", "remote_outcome_unknown"]), phase: text(r.phase),
    created_at: time(r.created_at), finished_at: nullable(r.finished_at, time), cancel_requested: bool(r.cancel_requested),
    failure_code: nullable(r.failure_code, text), stop_reason: nullable(r.stop_reason, text), target: target(r.target), execution: execution(r.execution),
    stats: (() => { const v = object(r.stats); return { model_submissions: count(v.model_submissions), web_actions: count(v.web_actions), sources: count(v.sources),
      http_requests: count(v.http_requests), source_reads: nullable(v.source_reads, count), local_queries: count(v.local_queries),
      retained_source_bytes: nullable(v.retained_source_bytes, count), elapsed_seconds: num(v.elapsed_seconds),
      input_tokens: nullable(v.input_tokens, count), output_tokens: nullable(v.output_tokens, count) }; })(),
    finding: nullable(r.finding, finding), action: nullable(r.action, x => one(x, ["terminal_delisting", "symbol_continuation"])),
    block_reasons: array(r.block_reasons, text), passages: array(r.passages, value => { const v = object(value); return {
      passage_id: text(v.passage_id), source_id: text(v.source_id), text: text(v.text), url: nullable(v.url, url),
      title: nullable(v.title, text), publisher: nullable(v.publisher, text), published_at: nullable(v.published_at, text),
      retrieved_at: time(v.retrieved_at), coverage: text(v.coverage), corpus: text(v.corpus) }; }),
    gaps: array(r.gaps, value => { const v = object(value); return { reason: text(v.reason), url: nullable(v.url, url), corpus: nullable(v.corpus, text) }; }),
    steps: array(r.steps, value => { const v = object(value); return { ordinal: count(v.ordinal), kind: text(v.kind), at: time(v.at),
      reason: nullable(v.reason, text), code: nullable(v.code, text) }; }) };
  if (result.target.ticker !== result.ticker || (result.finding && result.finding.source_ticker !== result.ticker)
    || (result.action && (result.status !== "succeeded" || !result.finding || result.block_reasons.length))
    || (result.status === "succeeded" && (!result.finding || !result.finished_at))) return invalid();
  return result;
}
export type InvestigationRun = ReturnType<typeof parseInvestigationRun>;

function providerDecision(value: unknown) {
  const r = object(value);
  const result = { listing_state: one(r.listing_state, ["active", "inactive", "unresolved"]),
    continuation_state: one(r.continuation_state, ["confirmed", "candidate", "unavailable", "ambiguous", "not_observed"]),
    listing_reasons: array(r.listing_reasons, text), continuation_reasons: array(r.continuation_reasons, text),
    listing_end_date: nullable(r.listing_end_date, date), continuation_effective_date: nullable(r.continuation_effective_date, date),
    successor_ticker: nullable(r.successor_ticker, ticker), candidate_tickers: array(r.candidate_tickers, ticker),
    action: nullable(r.action, value => one(value, ["terminal_delisting", "symbol_continuation"])), check_sha256: digest(r.check_sha256) };
  if ((result.action === "terminal_delisting" && result.listing_state !== "inactive")
    || (result.action === "symbol_continuation" && (result.continuation_state !== "confirmed" || !result.successor_ticker))
    || (result.listing_state === "active" && result.action !== null)) return invalid();
  return result;
}
export function parseInvestigationProviders(value: unknown) {
  const r = object(value), v = object(r.observations); if (r.version !== 2) return invalid();
  return { ticker: ticker(r.ticker), decision: nullable(r.decision, providerDecision), observations: { observed_at: nullable(v.observed_at, time), gaps: array(v.gaps, text),
    listings: array(v.listings, value => { const row = object(value); return {
      provider: one(row.provider, ["massive", "eodhd", "nasdaq"]), candidate_ticker: ticker(row.candidate_ticker),
      listing_status: one(row.listing_status, ["active", "inactive", "not_found", "unverified"]),
      primary_exchange: nullable(row.primary_exchange, text), security_type: nullable(row.security_type, text), market: nullable(row.market, text),
      snapshot_complete: bool(row.snapshot_complete), delisted_utc: nullable(row.delisted_utc, text),
      provider_last_updated_utc: nullable(row.provider_last_updated_utc, text), directory: nullable(row.directory, text), observed_at: time(row.observed_at),
    }; }) } };
}
export type InvestigationProviders = ReturnType<typeof parseInvestigationProviders>;
export function parseInvestigationActions(value: unknown) {
  const r = object(value); if (r.version !== 2) return invalid();
  return array(r.actions, value => { const row = object(value); return {
    transition_id: text(row.transition_id), source_ticker: ticker(row.source_ticker), successor_ticker: nullable(row.successor_ticker, ticker),
    kind: one(row.kind, ["terminal_delisting", "symbol_continuation"]), state: one(row.state, ["approved", "scheduled", "blocked"]),
    execute_on: date(row.execute_on), approved_preview_sha256: digest(row.approved_preview_sha256),
  }; });
}
export type InvestigationAction = ReturnType<typeof parseInvestigationActions>[number];
