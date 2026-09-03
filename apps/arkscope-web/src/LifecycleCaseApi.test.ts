/** @vitest-environment jsdom */
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  getSecurityLifecycleCase,
  getSecurityLifecycleCaseAudit,
  listSecurityLifecycleSecCandidates,
} from "./api";

const CASE_DETAIL = {
  case_id: "slc_blbd",
  source: "sec_edgar",
  source_ref: "0001589526-26-000044",
  ticker: "BLBD",
  source_presence: "present",
  workflow_state: "evidence_ready",
  issuer_name: "Blue Bird Corporation",
  filing_date: "2026-08-05",
  kinds: [{ event_type: "merger_agreement", effective_date: null }],
  current_assessment: null,
  current_acknowledgement: null,
  active_sources: ["manual_lists", "sa_alpha_picks_former"],
  source_context: "available",
  components: {},
  investigation_run_count: 0,
  automation_run_count: 1,
  automation_fact_count: 1,
  automation_tier: null,
  action_readiness: null,
  disposition: "not_confirmed_yet",
  queue_bucket: "monitoring",
  disposition_reason: "event_completion_not_confirmed",
  disposition_as_of: "2026-08-31T00:00:00Z",
  last_checked_at: "2026-08-31T00:00:00Z",
  next_check_at: "2026-09-07T00:00:00Z",
  source_family_status: { regulator: "confirmed" },
  evidence_count: 1,
  assessment_count: 0,
  acknowledgement_count: 0,
  proposal_count: 1,
  sec_admission: {
    state: "admitted",
    reason: "material_tracked_security_fact",
  },
  corroboration: {
    regulator: "confirmed",
    nasdaq_trader: null,
    massive: {
      listing_status: "active",
      source_as_of: "2026-08-29",
      provider_last_updated_utc: "2026-08-29T00:00:00Z",
    },
    ibkr: "present",
  },
  observation: {
    ticker: "BLBD",
    cik: "0001589526",
    issuer_name: "Blue Bird Corporation",
    filing_date: "2026-08-05",
    source: "sec_edgar",
    source_ref: "0001589526-26-000044",
    filing_form: "8-K",
    filing_items: ["1.01", "7.01", "9.01"],
    evidence_url: "https://www.sec.gov/Archives/example/blbd.htm",
    description: "8-K",
    first_observed_at: "2026-08-05T00:00:00Z",
    last_observed_at: "2026-08-05T00:00:00Z",
    kinds: [{ event_type: "merger_agreement", effective_date: null }],
  },
  observation_fingerprint_sha256: "a".repeat(64),
  investigation_runs: [],
  automation_runs: [],
  automation_facts: [],
  evidence: [],
  assessment_history: [],
  acknowledgement_history: [],
  proposals: [{
    proposal_id: "proposal-blbd",
    action_type: "keep_tracking",
    status: "proposed",
    projected_block_reason: null,
    replacement_ticker: null,
    source_snapshot_json: "[\"manual_lists\"]",
    proposal_dedupe_key: "must-not-cross-the-client-boundary",
    assessment_fingerprint_sha256: "b".repeat(64),
  }],
  ticker_transition: null,
  truncation: {},
};

const CASE_AUDIT = {
  case_id: "slc_blbd",
  observation_fingerprint_sha256: "a".repeat(64),
  investigation_runs: [],
  automation_runs: [],
  automation_facts: [],
  evidence: [],
  assessment_history: [],
  acknowledgement_history: [],
  truncation: {
    investigation_runs: { total: 0, returned: 0 },
    automation_runs: { total: 0, returned: 0 },
    automation_facts: { total: 0, returned: 0 },
    evidence: { total: 0, returned: 0 },
    assessment_history: { total: 0, returned: 0 },
    acknowledgement_history: { total: 0, returned: 0 },
  },
};

function response(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("security lifecycle case API", () => {
  it("projects a backend proposal into the closed browser DTO", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(CASE_DETAIL)));

    const result = await getSecurityLifecycleCase("slc_blbd");

    expect(result.proposals).toEqual([{
      proposal_id: "proposal-blbd",
      action_type: "keep_tracking",
      status: "proposed",
      projected_block_reason: null,
      replacement_ticker: null,
    }]);
    expect(result.active_sources).toEqual([
      "manual_lists",
      "sa_alpha_picks_former",
    ]);
    expect("evidence" in result).toBe(false);
    expect("automation_runs" in result).toBe(false);
    expect("observation_fingerprint_sha256" in result).toBe(false);
    expect(result.observation).toEqual({
      ticker: "BLBD",
      issuer_name: "Blue Bird Corporation",
      filing_date: "2026-08-05",
      filing_form: "8-K",
      filing_items: ["1.01", "7.01", "9.01"],
      evidence_url: "https://www.sec.gov/Archives/example/blbd.htm",
      kinds: [{ event_type: "merger_agreement", effective_date: null }],
    });
  });

  it("keeps automation narrative semantics while stripping primary rule authority", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({
      ...CASE_DETAIL,
      current_assessment: {
        assessment_id: "assessment-automation",
        status: "accepted",
        author: "automation",
        automation_method: "deterministic_rule",
        automation_narrative: "maReview",
        acceptance_authority: "automation_policy",
        automation_run_id: "run-private",
        rule_id: "lifecycle.ma_review",
        rule_version: "2",
        decision_provenance_sha256: "c".repeat(64),
        relevance: "direct_tracked_security",
        confidence: "high",
        conclusion: "Stored automation prose.",
        impact_summary: "Stored automation impact.",
        outcomes: ["acquisition_pending"],
        stale: false,
        created_at: "2026-08-28T01:00:00Z",
        counterparty_cik: "0000000001",
        citations: [],
      },
    })));

    const result = await getSecurityLifecycleCase("slc_blbd");

    expect(result.current_assessment?.automation_narrative).toBe("maReview");
    expect(result.current_assessment).not.toHaveProperty("rule_id");
    expect(result.current_assessment).not.toHaveProperty("automation_run_id");
    expect(result.current_assessment).not.toHaveProperty("counterparty_cik");
    expect(result.current_assessment).not.toHaveProperty("citations");
  });

  it.each([
    ["proposals", { ...CASE_DETAIL, proposals: {} }],
    ["active_sources", { ...CASE_DETAIL, active_sources: "manual_lists" }],
    ["observation items", {
      ...CASE_DETAIL,
      observation: { ...CASE_DETAIL.observation, filing_items: null },
    }],
  ])("rejects malformed %s before React receives the case", async (_field, body) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(body)));

    await expect(getSecurityLifecycleCase("slc_blbd")).rejects.toThrow(
      "security_lifecycle_case_contract",
    );
  });

  it("loads historical arrays only through the closed audit contract", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({
      ...CASE_AUDIT,
      future_audit_field: "must-not-cross-the-client-boundary",
    })));

    const result = await getSecurityLifecycleCaseAudit("slc_blbd");

    expect(result).toEqual(CASE_AUDIT);
  });

  it("strips future fields from every audit row and nested translation", async () => {
    const sentinel = "must-not-cross-audit-row-boundary";
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({
      ...CASE_AUDIT,
      investigation_runs: [{
        run_id: "investigation-1",
        status: "succeeded",
        result_count: 1,
        failure_code: null,
        created_at: "2026-08-29T00:00:00Z",
        future_field: sentinel,
      }],
      automation_runs: [{
        run_id: "automation-1",
        case_id: "slc_blbd",
        mode: "live",
        status: "blocked",
        policy_version: "1",
        decision_tier: null,
        action_readiness: null,
        failure_code: null,
        blockers: [{
          blocker_code: "market_confirmation_missing",
          retryable: true,
          future_field: sentinel,
        }],
        created_at: "2026-08-29T00:00:00Z",
        future_field: sentinel,
      }],
      automation_facts: [{
        fact_id: "fact-1",
        automation_run_id: "automation-1",
        evidence_id: "evidence-1",
        source_family: "regulator",
        fact_type: "source_ticker",
        normalized_value: "BLBD",
        source_span_start: 0,
        source_span_end: 4,
        cited_text_sha256: "c".repeat(64),
        extractor_rule_id: "sec-symbol",
        extractor_rule_version: "1",
        created_at: "2026-08-29T00:00:00Z",
        future_field: sentinel,
      }],
      evidence: [{
        evidence_id: "evidence-1",
        source_family: "regulator",
        kind: "regulator_excerpt",
        excerpt: "Official source text.",
        source_url: "https://www.sec.gov/Archives/example/blbd.htm",
        created_at: "2026-08-29T00:00:00Z",
        translations: [{
          evidence_id: "evidence-1",
          evidence_content_sha256: "d".repeat(64),
          locale: "en",
          translated_text: "Translated text.",
          provider: "openai",
          model: "gpt-5",
          harness: "responses-api",
          translated_at: "2026-08-29T00:01:00Z",
          cached: false,
          future_field: sentinel,
        }],
        future_field: sentinel,
      }],
      assessment_history: [{
        assessment_id: "assessment-1",
        status: "draft",
        author: "human",
        relevance: "undetermined",
        confidence: "unknown",
        conclusion: "Review.",
        impact_summary: "Review.",
        outcomes: ["undetermined"],
        stale: false,
        created_at: "2026-08-29T00:00:00Z",
        citations: [],
        future_field: sentinel,
      }],
      acknowledgement_history: [{
        acknowledgement_id: "ack-1",
        reason: "evidence_insufficient",
        note: null,
        stale: false,
        acknowledged_at: "2026-08-29T00:00:00Z",
        reopened_at: null,
        future_field: sentinel,
      }],
      truncation: {
        ...CASE_AUDIT.truncation,
        future_collection: { total: 1, returned: 1, future_field: sentinel },
      },
    })));

    const result = await getSecurityLifecycleCaseAudit("slc_blbd");

    expect(JSON.stringify(result)).not.toContain(sentinel);
    expect(result.investigation_runs[0]).toEqual({
      run_id: "investigation-1",
      status: "succeeded",
      result_count: 1,
      failure_code: null,
      created_at: "2026-08-29T00:00:00Z",
    });
    expect(result.evidence[0]).not.toHaveProperty("future_field");
    expect(result.truncation).not.toHaveProperty("future_collection");
  });

  it.each([
    ["evidence", { ...CASE_AUDIT, evidence: null }],
    ["automation blockers", {
      ...CASE_AUDIT,
      automation_runs: [{
        run_id: "run-1",
        case_id: "slc_blbd",
        mode: "live",
        status: "blocked",
        policy_version: "1",
        decision_tier: null,
        action_readiness: null,
        failure_code: null,
        blockers: {},
        created_at: "2026-08-29T00:00:00Z",
      }],
    }],
    ["assessment citations", {
      ...CASE_AUDIT,
      assessment_history: [{
        assessment_id: "assessment-1",
        status: "draft",
        author: "human",
        relevance: "undetermined",
        confidence: "unknown",
        conclusion: "Review",
        impact_summary: "Review",
        outcomes: ["undetermined"],
        stale: false,
        created_at: "2026-08-29T00:00:00Z",
        citations: {},
      }],
    }],
  ])("rejects malformed audit %s before React receives it", async (_field, body) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(body)));

    await expect(getSecurityLifecycleCaseAudit("slc_blbd")).rejects.toThrow(
      "security_lifecycle_case_contract",
    );
  });

  it("projects SEC candidates through the closed browser DTO", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({
      candidates: [{
        case_id: "slc_cde",
        ticker: "CDE",
        issuer_name: "Coeur Mining, Inc.",
        filing_form: "DEFA14A",
        filing_items: [],
        filing_date: "2026-08-29",
        evidence_url: "https://www.sec.gov/Archives/example/cde.htm",
        admission_state: "screened_out",
        admission_reason: "no_material_tracked_security_fact",
        assessment_fingerprint_sha256: "must-not-cross-the-client-boundary",
      }],
      count: 1,
      state_counts: {
        admitted: 0,
        needs_review: 0,
        pending: 0,
        screened_out: 1,
      },
    })));

    const result = await listSecurityLifecycleSecCandidates();

    expect(result.candidates).toEqual([{
      case_id: "slc_cde",
      ticker: "CDE",
      issuer_name: "Coeur Mining, Inc.",
      filing_form: "DEFA14A",
      filing_items: [],
      filing_date: "2026-08-29",
      evidence_url: "https://www.sec.gov/Archives/example/cde.htm",
      admission_state: "screened_out",
      admission_reason: "no_material_tracked_security_fact",
    }]);
  });

  it.each([
    ["candidate collection", { candidates: {}, count: 0, state_counts: {} }],
    ["admission state", {
      candidates: [{
        case_id: "slc_cde",
        ticker: "CDE",
        issuer_name: "Coeur Mining, Inc.",
        filing_form: "DEFA14A",
        filing_items: [],
        filing_date: "2026-08-29",
        evidence_url: "https://www.sec.gov/Archives/example/cde.htm",
        admission_state: "quietly_ignored",
        admission_reason: "no_material_tracked_security_fact",
      }],
      count: 1,
      state_counts: {
        admitted: 0,
        needs_review: 0,
        pending: 0,
        screened_out: 1,
      },
    }],
    ["admission reason", {
      candidates: [{
        case_id: "slc_cde",
        ticker: "CDE",
        issuer_name: "Coeur Mining, Inc.",
        filing_form: "DEFA14A",
        filing_items: [],
        filing_date: "2026-08-29",
        evidence_url: "https://www.sec.gov/Archives/example/cde.htm",
        admission_state: "screened_out",
        admission_reason: "silently_discarded",
      }],
      count: 1,
      state_counts: {
        admitted: 0,
        needs_review: 0,
        pending: 0,
        screened_out: 1,
      },
    }],
  ])("rejects malformed SEC %s before React receives it", async (_field, body) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(body)));

    await expect(listSecurityLifecycleSecCandidates()).rejects.toThrow(
      "security_lifecycle_case_contract",
    );
  });
});
