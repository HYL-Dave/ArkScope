import { describe, expect, it } from "vitest";
import { parseWebPreflight, parseWebRun, parseWebStart } from "./webContract";
import { webPreflightFixture, webRunFixture } from "./webFixtures";
import { parseLifecycleReviewPacket } from "./currentReviewContract";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const reviewPacket = JSON.parse(readFileSync(resolve(import.meta.dirname, "../../../../tests/fixtures/lifecycle_current_v1.json"), "utf8")).packet;

describe("Lifecycle Web DTOs", () => {
  it("reads known four-channel provenance without exporting extra internal fields", () => {
    for (const [provider, auth_mode] of [["openai", "api_key"], ["openai", "chatgpt_oauth"], ["anthropic", "api_key"], ["anthropic", "claude_code_oauth"]]) {
      const execution = { provider, auth_mode, model: "selected-model" };
      expect(parseWebRun({ ...webRunFixture, execution, credential_id: "private" })?.execution).toEqual(execution);
      expect(parseWebPreflight({ ...webPreflightFixture, execution }).execution).toEqual(execution);
    }
    expect(JSON.stringify(parseWebRun({ ...webRunFixture, owner: "private-worker" }))).not.toContain("private-worker");
  });
  it("keeps unknown identity details and usage unknown", () => {
    expect(parseWebPreflight(webPreflightFixture).public_identity?.venue).toBeNull();
    expect(parseWebRun(webRunFixture)?.usage.input_tokens).toBeNull();
    expect(parseWebRun(webRunFixture)?.finding?.independent_source_count).toBeNull();
    expect(parseWebRun(null)).toBeNull();
  });
  it("keeps older source size declarations unknown across repeated parsing", () => {
    const legacy = structuredClone(webPreflightFixture) as any;
    delete legacy.limits.max_source_bytes; delete legacy.limits.max_decoded_source_bytes;
    const parsed = parseWebPreflight(legacy);
    expect(parsed.limits?.max_source_bytes).toBeNull();
    expect(parseWebPreflight(parsed)).toEqual(parsed);
    expect(() => parseWebPreflight({ ...legacy, limits: { ...legacy.limits, max_source_bytes: "unlimited" } })).toThrow();
  });
  it("keeps legacy source coverage unknown but validates every new coverage field", () => {
    const summary = { sources: 4, selected_sources: 3, retained_text_bytes: 134217728, model_text_bytes: 192796 };
    expect(parseWebRun({ ...webRunFixture, source_reading: summary })?.source_reading).toEqual(summary);
    const legacy = { ...webRunFixture } as any; delete legacy.source_reading;
    expect(parseWebRun(legacy)?.source_reading).toBeNull();
    for (const value of [[], {}, { ...summary, sources: "4" }, { ...summary, selected_sources: 5 },
      { ...summary, model_text_bytes: 134217729 }, { ...summary, selected_sources: 0 }, { ...summary, model_text_bytes: null }]) {
      expect(() => parseWebRun({ ...webRunFixture, source_reading: value })).toThrow("lifecycle_web_payload_invalid");
    }
  });
  it("reads bounded source diagnostics without accepting header blobs or fake counts", () => {
    const read = { request_index: 1, status: 403, framing: null, content_encoding: null, declared_body_bytes: null,
      received_body_bytes: 0, decoded_body_bytes: 0, result_code: "source_unavailable" };
    expect(parseWebRun({ ...webRunFixture, source_reads: [read] })?.source_reads).toEqual([read]);
    for (const value of [{}, [{}], [{ ...read, status: "403" }], [{ ...read, request_index: 2 }],
      [{ ...read, received_body_bytes: -1 }], [{ ...read, headers: { Authorization: "secret" } }], [read, read]]) {
      expect(() => parseWebRun({ ...webRunFixture, source_reads: value })).toThrow("lifecycle_web_payload_invalid");
    }
  });
  it("preserves the same closed source gap disclosure in result and confirmation", () => {
    const gaps = [{ url: "https://news.example.com/notice", reason: "source_unavailable" }, { url: null, reason: "source_timeout" }];
    expect(parseWebRun({ ...webRunFixture, source_gaps: gaps })?.source_gaps).toEqual(gaps);
    expect(parseLifecycleReviewPacket({ ...reviewPacket, source_gaps: gaps }).source_gaps).toEqual(gaps);
    const legacy = { ...webRunFixture } as any; delete legacy.source_gaps;
    expect(parseWebRun(legacy)?.source_gaps).toBeNull();
    expect(parseWebRun({ ...webRunFixture, source_gaps: [] })?.source_gaps).toEqual([]);
    expect(parseLifecycleReviewPacket(reviewPacket).source_gaps).toBeNull();
    expect(parseLifecycleReviewPacket(parseLifecycleReviewPacket(reviewPacket)).source_gaps).toBeNull();
  });
  it.each([
    { name: "object instead of list", source_gaps: {} },
    { name: "string instead of list", source_gaps: "unknown" },
    { name: "empty entry", source_gaps: [{}] },
    { name: "null reason", source_gaps: [{ url: "https://news.example.com", reason: null }] },
    { name: "javascript URL", source_gaps: [{ url: "javascript:alert(1)", reason: "source_unavailable" }] },
    { name: "URL credentials", source_gaps: [{ url: "https://user:secret@example.com", reason: "source_unavailable" }] },
    { name: "raw error", source_gaps: [{ url: "https://news.example.com", reason: "raw server error" }] },
    { name: "internal field", source_gaps: [{ url: "https://news.example.com", reason: "source_unavailable", source_id: "private-binding" }] },
  ])("rejects malformed gap metadata rather than hiding it: $name", ({ source_gaps }) => {
    expect(() => parseWebRun({ ...webRunFixture, source_gaps })).toThrow();
    expect(() => parseLifecycleReviewPacket({ ...reviewPacket, source_gaps })).toThrow();
  });
  it.each(["citations", "contradictions", "unresolved_conditions", "block_reasons"])("requires a real %s array", (field) => {
    const value = structuredClone(webRunFixture) as any;
    delete value.finding[field];
    expect(() => parseWebRun(value)).toThrow("lifecycle_web_payload_invalid");
    value.finding[field] = {};
    expect(() => parseWebRun(value)).toThrow("lifecycle_web_payload_invalid");
  });
  it.each(["javascript:alert(1)", "https://name:password@issuer.example/notices", "file:///home/private", "http://issuer.example/notices"])("rejects unsafe citation URL %s", (url) => {
    const value = structuredClone(webRunFixture); value.finding.citations[0].url = url;
    expect(() => parseWebRun(value)).toThrow("lifecycle_web_payload_invalid");
  });
  it("does not treat a cancellation acknowledgment or unknown outcome as success", () => {
    const pending = { ...webRunFixture, status: "cancelling", phase: "searching", finished_at: null,
      cancel_requested_at: "2026-09-06T01:00:02Z", finding: null, usage: { input_tokens: null, output_tokens: null } };
    expect(parseWebRun(pending)?.status).toBe("cancelling");
    expect(parseWebRun({ ...pending, status: "remote_outcome_unknown", failure_code: "web_execution_interrupted" })?.status).toBe("remote_outcome_unknown");
    expect(() => parseWebRun({ ...pending, status: "succeeded" })).toThrow();
    expect(() => parseWebRun({ ...webRunFixture, status: "failed", failure_code: "web_execution_failed" })).toThrow();
  });
  it("binds actionable findings to the run ticker and supported evidence", () => {
    const value = structuredClone(webRunFixture);
    value.finding.source_ticker = "UNRELATED";
    expect(() => parseWebRun(value)).toThrow();
    value.finding.source_ticker = "OLD";
    (value.finding.block_reasons as string[]).push("source_read_incomplete");
    expect(() => parseWebRun(value)).toThrow();
  });
  it("requires a complete launch preview or an explicit unavailable reason", () => {
    expect(() => parseWebPreflight({ ...webPreflightFixture, limits: null })).toThrow();
    expect(() => parseWebPreflight({ ...webPreflightFixture, available: false })).toThrow();
    expect(parseWebPreflight({ version: 1, case_id: "case-1", available: false, reason: "web_journal_not_installed",
      preflight_sha256: null, public_identity: null, execution: null, credential_label: null, limits: null }).available).toBe(false);
  });
  it("validates request receipts rather than trusting an HTTP success cast", () => {
    expect(parseWebStart({ run_id: "run-1", created: false })).toEqual({ run_id: "run-1", created: false });
    expect(() => parseWebStart({ run_id: "run-1", created: "true" })).toThrow();
  });
});
