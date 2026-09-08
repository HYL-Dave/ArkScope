import { describe, expect, it } from "vitest";
import { parseInvestigationRuntime, parseInvestigationRun, parseInvestigationPreflight, parseInvestigationTargets, parseInvestigationProviders, parseInvestigationActions } from "./investigationContract";

export const runtime = { model_submissions: 24, web_actions: 24, source_reads: 32, http_requests: 96,
  local_queries: 20, deadline_seconds: 1800, model_timeout_seconds: 600, api_output_tokens: 8192, retained_source_mib: 512 };
export const target = { ticker: "TA", issuer_name: "TravelCenters of America Inc.", security_class: "common stock", venue: "NASDAQ",
  issuer_cik: null, composite_figi: null, identity_status: "needs_lookup", as_of: "2026-09-08" };
export const preflight = { version: 2, ticker: "TA", available: true, reason: null, preflight_sha256: "a".repeat(64),
  target, execution: { provider: "anthropic", auth_mode: "claude_code_oauth", model: "claude-sonnet-5", effort: "high" },
  credential_label: "Subscription", limits: { ...runtime, output_control: "provider", search_enforcement: "enforced" } };
export const run = { version: 2, run_id: "li_test", ticker: "TA", status: "running", phase: "model_request",
  created_at: "2026-09-08T01:00:00Z", finished_at: null, cancel_requested: false, failure_code: null, stop_reason: null,
  target, execution: preflight.execution, stats: { model_submissions: 1, web_actions: 0, sources: 0, http_requests: 0,
    source_reads: null, local_queries: 1, retained_source_bytes: null, elapsed_seconds: 3, input_tokens: null, output_tokens: null },
  finding: null, action: null, block_reasons: [], passages: [], gaps: [], steps: [] };

describe("independent investigation payloads", () => {
  it("admits complete payloads without a case and strips unprojected private metadata", () => {
    expect(parseInvestigationPreflight(preflight).target?.ticker).toBe("TA");
    expect(parseInvestigationRun({ ...run, internal: "secret" })).not.toHaveProperty("internal");
    expect(parseInvestigationTargets({ version: 2, targets: [{ ticker: "TA", secret: "private" }] })).toEqual([{ ticker: "TA" }]);
  });
  it.each(["passages", "steps", "gaps", "block_reasons"])("requires array %s", (field) => {
    expect(() => parseInvestigationRun({ ...run, [field]: null })).toThrow();
    expect(() => parseInvestigationRun({ ...run, [field]: {} })).toThrow();
  });
  it("rejects false success, wrong target and unusable preflight", () => {
    expect(() => parseInvestigationRun({ ...run, action: "terminal_delisting" })).toThrow();
    expect(() => parseInvestigationRun({ ...run, ticker: "OTHER" })).toThrow();
    expect(() => parseInvestigationPreflight({ ...preflight, available: false })).toThrow();
  });
  it("runtime import is strict, bounded and roundtrips exactly", () => {
    expect(parseInvestigationRuntime(runtime)).toEqual(runtime);
    expect(() => parseInvestigationRuntime({ ...runtime, model_submissions: 0 })).toThrow();
    expect(() => parseInvestigationRuntime({ ...runtime, model_submissions: true })).toThrow();
    expect(() => parseInvestigationRuntime({ ...runtime, retry: true })).toThrow();
  });
  it("reads dated provider facts and pending actions without leaking locators", () => {
    const snapshot = { version: 2, ticker: "TA", decision: null, observations: { observed_at: "2026-09-08T01:00:00Z", listings: [{ provider: "massive", candidate_ticker: "TA",
      listing_status: "inactive", primary_exchange: "XNAS", security_type: "CS", market: "stocks", snapshot_complete: true, delisted_utc: "2023-05-15T00:00:00Z",
      provider_last_updated_utc: null, directory: null, observed_at: "2026-09-08T01:00:00Z", source_locator: "private" }], gaps: [] } };
    expect(parseInvestigationProviders(snapshot).observations.listings[0]).not.toHaveProperty("source_locator");
    expect(() => parseInvestigationProviders({ ...snapshot, observations: { ...snapshot.observations, listings: {} } })).toThrow();
    expect(parseInvestigationActions({ version: 2, actions: [] })).toEqual([]);
    expect(() => parseInvestigationActions({ version: 2, actions: [{ state: "applied" }] })).toThrow();
  });
  it("rejects contradictory or malformed provider actions instead of offering a false confirmation", () => {
    const decision = { listing_state: "inactive", continuation_state: "unavailable", listing_reasons: [], continuation_reasons: ["successor_check_unavailable"],
      listing_end_date: "2023-05-15", continuation_effective_date: null, successor_ticker: null, candidate_tickers: [],
      action: "terminal_delisting", check_sha256: "b".repeat(64) };
    const snapshot = { version: 2, ticker: "TA", observations: { observed_at: null, listings: [], gaps: [] }, decision };
    expect(parseInvestigationProviders(snapshot).decision?.action).toBe("terminal_delisting");
    for (const invalid of [{ listing_state: "active" }, { action: "symbol_continuation" }, { candidate_tickers: {} }, { check_sha256: "invalid" }]) {
      expect(() => parseInvestigationProviders({ ...snapshot, decision: { ...decision, ...invalid } })).toThrow();
    }
    expect(() => parseInvestigationProviders({ ...snapshot, decision: undefined })).toThrow();
  });
});
