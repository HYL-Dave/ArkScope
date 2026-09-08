export const webPreflightFixture = {
  version: 1, case_id: "case-1", available: true, reason: null, preflight_sha256: "a".repeat(64),
  public_identity: { ticker: "OLD", issuer_name: "Issuer Old Inc", security_class: null, venue: null, question: "listing_status", as_of: "2026-09-06" },
  execution: { provider: "openai", auth_mode: "chatgpt_oauth", model: "gpt-5.6-luna" }, credential_label: "Chosen account",
  limits: { model_submissions: 2, search_uses: 4, search_enforcement: "observed", source_requests: 8, sources: 4,
    max_source_bytes: 16777216, max_decoded_source_bytes: 33554432,
    model_timeout_seconds: 180, source_timeout_seconds: 45, output_token_limit: null, background_retention: false },
};
export const webRunFixture = {
  version: 1, run_id: "run-1", case_id: "case-1", ticker: "OLD", status: "succeeded", phase: null,
  created_at: "2026-09-06T01:00:00Z", finished_at: "2026-09-06T01:02:00Z", failure_code: null, cancel_requested_at: null,
  execution: webPreflightFixture.execution, model_submissions: 2, source_requests: 1, usage: { input_tokens: null, output_tokens: 100 },
  source_reading: null,
  source_reads: null,
  source_gaps: null,
  usage_report: null,
  finding: { source_ticker: "OLD", issuer_name: "Issuer Old Inc", security_class: "Class A common stock", venue: "NASDAQ",
    event_kind: "listing_ended", timing: "completed", summary: "Trading has ended.", successor_ticker: null,
    effective_date: "2026-09-01", announcement_date: null, contradictions: [], unresolved_conditions: [],
    action: "terminal_delisting", block_reasons: [], unique_passage_count: 1, independent_source_count: null,
    citations: [{ url: "https://issuer.example/notices", quote: "Issuer Old Inc OLD Class A common stock on NASDAQ ceased trading effective September 1, 2026.", retrieved_at: "2026-09-06T01:01:00Z" }] },
};

export const webUsageFixture = {
  version: 1, recorded_submissions: 2, coverage: "complete",
  totals: { input_tokens: 30006, output_tokens: 3628 }, known_subtotal: { input_tokens: 30006, output_tokens: 3628 },
  phases: [
    { phase: "search", basis: "claude_model_usage", input_tokens: 29706, output_tokens: 3228,
      cache_creation_input_tokens: 3976, cache_read_input_tokens: 3354, web_search_requests: 2 },
    { phase: "analysis", basis: "claude_model_usage", input_tokens: 300, output_tokens: 400,
      cache_creation_input_tokens: 0, cache_read_input_tokens: 0, web_search_requests: 0 },
  ],
};
