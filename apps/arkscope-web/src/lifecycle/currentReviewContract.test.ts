/** @vitest-environment jsdom */
import { afterEach, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import * as api from "../api";

const fixture = JSON.parse(readFileSync(resolve(import.meta.dirname, "../../../../tests/fixtures/lifecycle_current_v1.json"), "utf8"));
const decisions = JSON.parse(readFileSync(resolve(import.meta.dirname, "../../../../tests/fixtures/ticker_history_decisions_v1.json"), "utf8"));
const page = fixture.attention;
afterEach(() => vi.unstubAllGlobals());

it("keeps a legacy activity with absent decision metadata readable", async () => {
  const { decision, ...legacy } = fixture.activity.items[0];
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ ...fixture.activity, items: [legacy] }))));
  const result = await api.listTickerIdentityTransitionActivity();
  expect(result.items[0]).toEqual(legacy);
  expect(result.items[0]).not.toHaveProperty("decision");
});

it.each(["September 1, 2026", "Sep 1, 2026 08:30 ET"])("preserves recorded publisher-date text without rejecting the entire feed (%s)", async (published_at) => {
  const decision = { ...decisions.llm, sources: decisions.llm.sources.map((row: object) => ({ ...row, published_at })) };
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ ...fixture.activity, items: [{ ...fixture.activity.items[0], decision }] }))));
  expect((await api.listTickerIdentityTransitionActivity()).items[0].decision).toEqual(decision);
});

it.each(["provider", "llm"])("preserves the backend-owned historical explanation without private material (%s)", async (lane) => {
  const decision = decisions[lane];
  const withPrivate = { ...decision, credential_id: "private", sources: decision.sources.map((row: object) => ({ ...row, source_locator_json: "private" })),
    model: decision.model && { ...decision.model, remote_id: "private" } };
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ ...fixture.activity,
    items: [{ ...fixture.activity.items[0], decision: withPrivate }] }))));
  const result = await api.listTickerIdentityTransitionActivity();
  expect(result.items[0]).toHaveProperty("decision", decision);
});

it.each([null, {}, { ...decisions.llm, sources: null }, { ...decisions.llm, model: {} },
  { ...decisions.llm, source_gaps: {} }, { ...decisions.llm, limitations: "missing" },
  { ...decisions.llm, gaps: ["future_unknown"] }, { ...decisions.llm, event_date: "2026-02-30" },
  { ...decisions.llm, approval_authority: "llm" }, { ...decisions.llm, method: "provider_review" },
  { ...decisions.llm, model: { provider: "openai", auth_mode: "claude_code_oauth", model: "wrong" } },
  { ...decisions.llm, sources: [{ ...decisions.llm.sources[0], url: "javascript:alert(1)" }] },
  { ...decisions.llm, sources: [{ ...decisions.llm.sources[0], url: "https://example.com/?apiKey=private" }] },
])("rejects malformed present decision metadata, not as absent historical data (%j)", async (decision) => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ ...fixture.activity,
    items: [{ ...fixture.activity.items[0], decision }] }))));
  await expect(api.listTickerIdentityTransitionActivity()).rejects.toThrow("lifecycle_current_payload_invalid");
});

it("parses the public action packet and committed readback without internal material", () => {
  expect(api.parseLifecycleReviewPacket(fixture.packet)).toEqual({ ...fixture.packet, source_gaps: null });
  expect(api.parseLifecycleReviewConfirmation(fixture.confirmation)).toEqual(fixture.confirmation);
});
it.each([
  { ready: "true" }, { action: "acquisition" }, { effects: null }, { block_reasons: null },
  { ready: true, block_reasons: ["listing_authority_required"] },
  { execute_on: "2026-02-30" }, { effects: { ...fixture.packet.effects, watchlists: { archive: undefined } } },
  { finding: { ...fixture.packet.finding, outcomes: null } }, { source_references: null },
  { options: { ...fixture.packet.options, execute_on: "2026-09-05" } },
])("rejects malformed action packets before a confirmation can be offered (%j)", (change) => {
  expect(() => api.parseLifecycleReviewPacket({ ...fixture.packet, ...change })).toThrow("lifecycle_current_payload_invalid");
});
it("rejects false applied readbacks and preserves approved, scheduled and blocked states", () => {
  expect(() => api.parseLifecycleReviewConfirmation({ ...fixture.confirmation, current_effects_match: false })).toThrow();
  for (const status of ["approved", "scheduled", "blocked", "cancelled", "reversed"]) {
    const value = { ...fixture.confirmation, status, current_effects_match: null, applied_at: null };
    expect(api.parseLifecycleReviewConfirmation(value).status).toBe(status);
  }
});
it.each(["approved", "scheduled", "blocked", "cancelled", "reversed"])("does not attach checked applied effects to %s", (status) => {
  expect(() => api.parseLifecycleReviewConfirmation({ ...fixture.confirmation, status })).toThrow();
});
it("submits exactly one provider confirmation command", async () => {
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(fixture.confirmation)));
  vi.stubGlobal("fetch", fetch);
  await api.confirmLifecycleReview(fixture.packet);
  expect(fetch).toHaveBeenCalledOnce();
  const call = fetch.mock.calls[0];
  expect(String(call[0])).toContain("/confirm-review");
  expect(call[1].method).toBe("POST");
  expect(JSON.parse(call[1].body)).toEqual({ assessment_id: fixture.packet.assessment_id, packet_sha256: fixture.packet.packet_sha256,
    action: fixture.packet.action, ...fixture.packet.options });
});
it("rejects a different provider confirmation receipt instead of applying its result", async () => {
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ...fixture.confirmation, case_id: "slc_other" })));
  vi.stubGlobal("fetch", fetch);
  await expect(api.confirmLifecycleReview(fixture.packet)).rejects.toThrow("lifecycle_current_payload_invalid");
  expect(fetch).toHaveBeenCalledOnce();
});

it.each([null, {}, { items: null, count: 0, unacknowledged_count: 0 },
  { items: [null], count: 1, unacknowledged_count: 1 },
  { items: [{ activity_type: "applied", user_owned_changes: null }], count: 1, unacknowledged_count: 1 },
])("rejects malformed tracking activity before opening its UI (%j)", async (value) => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(value))));
  await expect(api.listTickerIdentityTransitionActivity()).rejects.toThrow("lifecycle_current_payload_invalid");
});
it("reads the actual persisted tracking receipt through a closed activity projection", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ ...fixture.activity, future_column: "private",
    items: fixture.activity.items.map((row: object) => ({ ...row, source_snapshot_json: "private" })) }))));
  expect(await api.listTickerIdentityTransitionActivity()).toEqual(fixture.activity);
});
it("binds activity acknowledgement to the requested receipt", async () => {
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ...fixture.activity.items[0], activity_id: "other", acknowledged_at: page.as_of })));
  vi.stubGlobal("fetch", fetch);
  await expect(api.acknowledgeTickerIdentityTransitionActivity(fixture.activity.items[0].activity_id)).rejects.toThrow("lifecycle_current_payload_invalid");
  fetch.mockResolvedValue(new Response(JSON.stringify({ ...fixture.activity.items[0], acknowledged_at: page.as_of })));
  expect((await api.acknowledgeTickerIdentityTransitionActivity(fixture.activity.items[0].activity_id)).acknowledged_at).toBe(page.as_of);
});
it.each([{ user_owned_changes: null }, { provider_owned_retained: {} }, { effective_date: "2026-02-30" },
  { reverse_readiness: { reversible: true, block_reasons: ["reverse_state_changed"] } },
  { reverse_readiness: { reversible: "true", block_reasons: [] } },
])("checks the nested tracking receipt used by the audit (%j)", async (change) => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ ...fixture.activity,
    items: [{ ...fixture.activity.items[0], ...change }] }))));
  await expect(api.listTickerIdentityTransitionActivity()).rejects.toThrow("lifecycle_current_payload_invalid");
});
it("does not claim an unacknowledged receipt has been acknowledged", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(fixture.activity.items[0]))));
  await expect(api.acknowledgeTickerIdentityTransitionActivity(fixture.activity.items[0].activity_id)).rejects.toThrow("lifecycle_current_payload_invalid");
});
