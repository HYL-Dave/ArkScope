export const WEB_RUN_STATES = ["queued", "searching", "reading_sources", "analyzing", "cancelling", "succeeded", "failed", "cancelled", "remote_outcome_unknown"] as const;
export const WEB_PHASES = ["queued", "searching", "reading_sources", "analyzing"] as const;
export const WEB_USAGE_BASES = ["claude_model_usage", "adapter_report", "unreported"] as const;
export const WEB_USAGE_COVERAGE = ["complete", "partial", "unknown"] as const;
export type WebQuestion = "listing_status" | "symbol_continuation";
function invalid(): never { throw new Error("lifecycle_web_payload_invalid"); }
function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return invalid();
  return value as Record<string, unknown>;
}
function text(value: unknown): string {
  if (typeof value !== "string" || !value.trim() || value.includes("\0")) return invalid(); return value;
}
function bool(value: unknown): boolean { if (typeof value !== "boolean") return invalid(); return value; }
function number(value: unknown): number {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0) return invalid(); return value;
}
function count(value: unknown): number { const result = number(value); if (!Number.isSafeInteger(result)) return invalid(); return result; }
function choice<const T extends readonly string[]>(value: unknown, choices: T): T[number] {
  if (typeof value !== "string" || !choices.includes(value)) return invalid(); return value as T[number];
}
function nullable<T>(value: unknown, parse: (value: unknown) => T): T | null { return value === null ? null : parse(value); }
function list<T>(value: unknown, parse: (value: unknown) => T): T[] { if (!Array.isArray(value)) return invalid(); return value.map(parse); }
function date(value: unknown): string {
  const result = text(value);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(result) || !Number.isFinite(Date.parse(result)) || new Date(result).toISOString().slice(0, 10) !== result) return invalid();
  return result;
}
function time(value: unknown): string {
  const result = text(value);
  if (!/^\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(result) || !Number.isFinite(Date.parse(result))) return invalid();
  date(result.slice(0, 10)); return result;
}
function digest(value: unknown): string { const result = text(value); if (!/^[a-f0-9]{64}$/.test(result)) return invalid(); return result; }
function sourceUrl(value: unknown): string {
  const result = text(value);
  try { const url = new URL(result); if (url.protocol !== "https:" || url.username || url.password) return invalid(); }
  catch { return invalid(); } return result;
}
function execution(value: unknown) {
  const row = object(value), provider = choice(row.provider, ["openai", "anthropic"]);
  const auth_mode = choice(row.auth_mode, ["api_key", "chatgpt_oauth", "claude_code_oauth"]);
  if ((provider === "openai" && auth_mode === "claude_code_oauth") || (provider === "anthropic" && auth_mode === "chatgpt_oauth")) return invalid();
  return { provider, auth_mode, model: text(row.model) };
}

export function parseWebPreflight(value: unknown) {
  const row = object(value); if (row.version !== 1) return invalid();
  const result = { version: 1 as const, case_id: text(row.case_id), available: bool(row.available), reason: nullable(row.reason, text),
    preflight_sha256: nullable(row.preflight_sha256, digest), credential_label: nullable(row.credential_label, text), execution: nullable(row.execution, execution),
    public_identity: nullable(row.public_identity, (value) => { const r = object(value); return {
      ticker: text(r.ticker), issuer_name: text(r.issuer_name), security_class: nullable(r.security_class, text), venue: nullable(r.venue, text),
      question: choice(r.question, ["listing_status", "symbol_continuation"]), as_of: date(r.as_of),
    }; }),
    limits: nullable(row.limits, (value) => { const r = object(value); return {
      model_submissions: count(r.model_submissions), search_uses: count(r.search_uses), search_enforcement: choice(r.search_enforcement, ["observed", "enforced"]),
      source_requests: count(r.source_requests), sources: count(r.sources), model_timeout_seconds: number(r.model_timeout_seconds),
      max_source_bytes: r.max_source_bytes === undefined ? null : nullable(r.max_source_bytes, count),
      max_decoded_source_bytes: r.max_decoded_source_bytes === undefined ? null : nullable(r.max_decoded_source_bytes, count),
      source_timeout_seconds: number(r.source_timeout_seconds), output_token_limit: nullable(r.output_token_limit, count), background_retention: bool(r.background_retention),
    }; }),
  };
  if (result.available ? (result.reason !== null || !result.preflight_sha256 || !result.credential_label || !result.execution || !result.public_identity || !result.limits)
    : (!result.reason || [result.preflight_sha256, result.credential_label, result.execution, result.public_identity, result.limits].some((item) => item !== null))) return invalid();
  return result;
}
export type WebPreflight = ReturnType<typeof parseWebPreflight>;

function sourceReading(value: unknown) {
  const r = object(value);
  const result = { sources: count(r.sources), selected_sources: count(r.selected_sources),
    retained_text_bytes: count(r.retained_text_bytes), model_text_bytes: count(r.model_text_bytes) };
  if (!result.sources || !result.model_text_bytes || result.selected_sources > result.sources
    || result.model_text_bytes > result.retained_text_bytes
    || (result.selected_sources === 0) !== (result.model_text_bytes === result.retained_text_bytes)) return invalid();
  return result;
}

function exactKeys(row: Record<string, unknown>, keys: readonly string[]) {
  if (Object.keys(row).length !== keys.length || Object.keys(row).some((key) => !keys.includes(key))) return invalid();
}
function tokens(value: unknown) {
  const row = object(value); exactKeys(row, ["input_tokens", "output_tokens"]);
  return { input_tokens: nullable(row.input_tokens, count), output_tokens: nullable(row.output_tokens, count) };
}
function usageReport(value: unknown, submissions: number) {
  const row = object(value);
  exactKeys(row, ["version", "recorded_submissions", "coverage", "totals", "known_subtotal", "phases"]);
  if (row.version !== 1) return invalid();
  const result = { version: 1 as const, recorded_submissions: count(row.recorded_submissions),
    coverage: choice(row.coverage, WEB_USAGE_COVERAGE), totals: tokens(row.totals), known_subtotal: tokens(row.known_subtotal),
    phases: list(row.phases, (value) => {
      const r = object(value);
      exactKeys(r, ["phase", "basis", "input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "web_search_requests"]);
      const result = { phase: choice(r.phase, ["search", "analysis"]), basis: choice(r.basis, WEB_USAGE_BASES),
        input_tokens: nullable(r.input_tokens, count), output_tokens: nullable(r.output_tokens, count),
        cache_creation_input_tokens: nullable(r.cache_creation_input_tokens, count), cache_read_input_tokens: nullable(r.cache_read_input_tokens, count),
        web_search_requests: nullable(r.web_search_requests, count) };
      if (result.basis === "unreported" && [result.input_tokens, result.output_tokens, result.cache_creation_input_tokens,
        result.cache_read_input_tokens, result.web_search_requests].some((value) => value !== null)) return invalid();
      return result;
    }),
  };
  if (result.recorded_submissions !== result.phases.length || result.recorded_submissions > submissions
    || new Set(result.phases.map((phase) => phase.phase)).size !== result.phases.length) return invalid();
  for (const key of ["input_tokens", "output_tokens"] as const) {
    const values = result.phases.map((phase) => phase[key]).filter((value): value is number => value !== null);
    const subtotal = values.length ? count(values.reduce((sum, value) => sum + value, 0)) : null;
    const total = values.length === submissions ? subtotal : null;
    if (result.known_subtotal[key] !== subtotal || result.totals[key] !== total) return invalid();
  }
  const coverage = Object.values(result.totals).every((value) => value !== null) ? "complete"
    : Object.values(result.known_subtotal).some((value) => value !== null) ? "partial" : "unknown";
  if (result.coverage !== coverage) return invalid();
  return result;
}

function sourceRead(value: unknown) {
  const r = object(value);
  const keys = ["request_index", "status", "framing", "content_encoding", "declared_body_bytes", "received_body_bytes", "decoded_body_bytes", "result_code"];
  if (Object.keys(r).length !== keys.length || Object.keys(r).some((key) => !keys.includes(key))) return invalid();
  const result = { request_index: count(r.request_index), status: nullable(r.status, count),
    framing: nullable(r.framing, (x) => choice(x, ["chunked", "content_length", "close_delimited"])),
    content_encoding: nullable(r.content_encoding, (x) => choice(x, ["identity", "gzip", "unsupported"])),
    declared_body_bytes: nullable(r.declared_body_bytes, count), received_body_bytes: count(r.received_body_bytes),
    decoded_body_bytes: count(r.decoded_body_bytes), result_code: text(r.result_code) };
  if (!result.request_index || (result.status !== null && (result.status < 100 || result.status > 599))
    || !/^[a-z_]{1,100}$/.test(result.result_code)) return invalid();
  return result;
}

export function parseWebSourceGaps(value: unknown) {
  return list(value, (value) => {
    const row = object(value);
    if (Object.keys(row).length !== 2 || !("url" in row) || !("reason" in row)) return invalid();
    const result = { url: nullable(row.url, sourceUrl), reason: text(row.reason) };
    if (!/^[a-z_]{1,100}$/.test(result.reason)) return invalid();
    return result;
  });
}

function finding(value: unknown) {
  const row = object(value);
  const result = {
    source_ticker: text(row.source_ticker), issuer_name: text(row.issuer_name), security_class: text(row.security_class), venue: text(row.venue),
    event_kind: choice(row.event_kind, ["listing_ended", "symbol_continuation", "active_listing", "acquisition_announced", "trading_suspended", "unresolved"]),
    timing: choice(row.timing, ["completed", "scheduled", "unknown"]), summary: text(row.summary), successor_ticker: nullable(row.successor_ticker, text),
    effective_date: nullable(row.effective_date, date), announcement_date: nullable(row.announcement_date, date),
    contradictions: list(row.contradictions, text), unresolved_conditions: list(row.unresolved_conditions, text),
    action: nullable(row.action, (x) => choice(x, ["terminal_delisting", "symbol_continuation"])), block_reasons: list(row.block_reasons, text),
    unique_passage_count: count(row.unique_passage_count), independent_source_count: nullable(row.independent_source_count, count),
    citations: list(row.citations, (x) => { const r = object(x); return { url: sourceUrl(r.url), quote: text(r.quote), retrieved_at: time(r.retrieved_at) }; }),
  };
  if (result.action && (result.block_reasons.length || result.contradictions.length || result.unresolved_conditions.length || !result.citations.length
    || !result.effective_date || result.timing === "unknown" || (result.action === "symbol_continuation" && (!result.successor_ticker || result.event_kind !== "symbol_continuation"))
    || (result.action === "terminal_delisting" && result.event_kind !== "listing_ended"))) return invalid();
  return result;
}
export function parseWebRun(value: unknown) {
  if (value === null) return null;
  const row = object(value), usage = object(row.usage); if (row.version !== 1) return invalid();
  const result = { version: 1 as const, run_id: text(row.run_id), case_id: text(row.case_id), ticker: text(row.ticker),
    status: choice(row.status, WEB_RUN_STATES), phase: nullable(row.phase, (x) => choice(x, WEB_PHASES)),
    created_at: time(row.created_at), finished_at: nullable(row.finished_at, time), failure_code: nullable(row.failure_code, text),
    cancel_requested_at: nullable(row.cancel_requested_at, time), execution: execution(row.execution),
    model_submissions: count(row.model_submissions), source_requests: nullable(row.source_requests, count),
    usage: { input_tokens: nullable(usage.input_tokens, count), output_tokens: nullable(usage.output_tokens, count) }, finding: nullable(row.finding, finding),
    usage_report: row.usage_report === undefined ? null : nullable(row.usage_report, (value) => usageReport(value, count(row.model_submissions))),
    source_reading: row.source_reading === undefined ? null : nullable(row.source_reading, sourceReading),
    source_reads: row.source_reads === undefined ? null : nullable(row.source_reads, (x) => list(x, sourceRead)),
    source_gaps: row.source_gaps === undefined ? null : nullable(row.source_gaps, parseWebSourceGaps),
  };
  if ((result.status === "succeeded" && (!result.finding || result.failure_code || !result.finished_at || result.model_submissions !== 2))
    || (result.status !== "succeeded" && result.finding !== null)
    || (["failed", "cancelled", "remote_outcome_unknown"].includes(result.status) && !result.failure_code)
    || (result.status === "cancelling" && !result.cancel_requested_at)
    || result.model_submissions > 2 || (result.finding && result.finding.source_ticker !== result.ticker)) return invalid();
  if (result.source_reads && (result.source_requests === null || result.source_reads.some((item, index, items) =>
    item.request_index > result.source_requests! || item.request_index <= (index ? items[index - 1].request_index : 0)))) return invalid();
  if (result.usage_report && (result.usage_report.totals.input_tokens !== result.usage.input_tokens
    || result.usage_report.totals.output_tokens !== result.usage.output_tokens)) return invalid();
  return result;
}
export type WebRun = NonNullable<ReturnType<typeof parseWebRun>>;
export function parseWebStart(value: unknown) { const row = object(value); return { run_id: text(row.run_id), created: bool(row.created) }; }
export function webIsRunning(run: WebRun | null): boolean { return !!run && [...WEB_PHASES, "cancelling"].includes(run.status); }
