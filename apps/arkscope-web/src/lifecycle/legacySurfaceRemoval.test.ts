/** @vitest-environment jsdom */
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { afterEach, expect, it, vi } from "vitest";
import * as api from "../api";
import * as investigationContract from "./investigationContract";
import en from "../i18n/resources/en/explore";
import zh from "../i18n/resources/zh-Hant/explore";

afterEach(() => vi.unstubAllGlobals());

it.each([
  "CurrentLifecycleView.tsx", "CurrentLifecycleAudit.tsx", "LifecycleWebPanel.tsx",
  "LifecycleCaseDrawer.tsx", "useLifecycleSourceCheck.ts", "webContract.ts", "webFixtures.ts",
])("removes the abandoned frontend owner %s", (file) => {
  expect(existsSync(resolve(import.meta.dirname, file))).toBe(false);
});

it.each([
  "getLifecycleWebPreflight", "latestLifecycleWebRun", "startLifecycleWebRun", "getLifecycleWebRun",
  "cancelLifecycleWebRun", "getLifecycleWebReview", "confirmLifecycleWebReview",
  "listCurrentLifecycleReviews", "getCurrentLifecycleReview", "getLifecycleReviewPacket",
  "getLifecycleReviewConfirmation", "getSecurityLifecycleCaseAudit", "translateSecurityLifecycleEvidence",
  "runSecurityLifecycleCaseAutomation", "parseCurrentReviewList",
])("does not export the old-only client or parser %s", (name) => {
  expect(api).not.toHaveProperty(name);
});

it("gives the current investigation contract ownership of start receipts", () => {
  expect(investigationContract).toHaveProperty("parseInvestigationStart", expect.any(Function));
});

it.each([true, false])("parses a current target start receipt with created=%s without exposing private fields", async (created) => {
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ run_id: "li_new", created, worker: "private" })));
  vi.stubGlobal("fetch", fetch);
  const body = { preflight_sha256: "a".repeat(64), request_key: "one-request", language: "en" };
  expect(await api.startInvestigation("BRK B", body)).toEqual({ run_id: "li_new", created });
  expect(fetch).toHaveBeenCalledOnce();
  const [url, options] = fetch.mock.calls[0];
  expect(new URL(url).pathname).toBe("/security-lifecycle/investigations/targets/BRK%20B/runs");
  expect(options.method).toBe("POST");
  expect(JSON.parse(options.body)).toEqual(body);
});

it.each([null, [], {}, { run_id: "li_new", created: "true" }, { run_id: "", created: true },
  { run_id: "bad\0id", created: false }].map(value => [value]))("rejects malformed current start receipts without retrying (%j)", async (value) => {
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(value)));
  vi.stubGlobal("fetch", fetch);
  await expect(api.startInvestigation("TA", { preflight_sha256: "a".repeat(64), request_key: "one-request", language: "en" })).rejects.toThrow();
  expect(fetch).toHaveBeenCalledOnce();
});

const fixture = JSON.parse(readFileSync(resolve(import.meta.dirname, "../../../../tests/fixtures/lifecycle_current_v1.json"), "utf8"));
const obsoleteLifecycleCopy = [
  "title", "aria", "queues.aria",
  "automationControl.stages.preparing", "automationControl.stages.sec",
  "automationControl.stages.listing", "automationControl.stages.ibkr",
  "automationControl.stages.evaluate", "automationControl.stages.persist",
  "automationControl.stages.approve", "automationControl.stages.finalize",
  "actions.reopen", "actions.openEvidence", "filters.ticker",
  "sections.acknowledgement", "sections.facts", "fields.extractionRule",
  "states.revalidation", "states.zeroResults", "states.notAvailable",
  "acknowledgementReasons.evidenceInsufficient",
  "translation.routeUnavailable", "translation.credentialMissing", "translation.authRejected",
  "translation.rateLimited", "translation.quotaExhausted", "translation.modelUnavailable",
  "translation.timeout", "translation.outputInvalid", "translation.contextWindowExceeded",
  "translation.protocolResourceExhausted", "translation.providerError",
  "translation.evidenceChanged", "translation.unknown",
  "transition.caveats.providerOwnedSourcesRetained",
  "transition.caveats.portfolioPositionRetained", "transition.caveats.successorAlreadyTracked",
  "transition.effects.add", "transition.effects.archive",
  "transition.effects.reactivate", "transition.effects.unchanged",
];
it.each([["en", en], ["zh-Hant", zh]] as const)("removes reviewed obsolete leaf copy without removing shared %s labels", (_locale, copy) => {
  for (const key of obsoleteLifecycleCopy) expect(copy.lifecycle).not.toHaveProperty(key);
  for (const key of [
    "current.checkPrompt", "current.checkIncomplete", "fields.successorTicker", "fields.effectiveDate",
    "listingEvidence.authorities.eodhd", "listingEvidence.authorities.nasdaqTrader",
    "listingEvidence.authorities.massive", "translation.providers.anthropic", "translation.providers.openai",
  ]) expect(copy.lifecycle).toHaveProperty(key, expect.any(String));
});
it.each([["en", en], ["zh-Hant", zh]] as const)("removes only the old screen's review-list and run controls from %s copy", (_locale, copy) => {
  for (const key of ["reasons", "collections", "checks", "attention", "nextCheck", "audit", "auditUnavailable"]) {
    expect(copy.lifecycle.current).not.toHaveProperty(key);
  }
  for (const key of ["status", "question", "start", "stop", "usageBasis", "usageCoverage", "sourceReadDetails"]) {
    expect(copy.lifecycle.web).not.toHaveProperty(key);
  }
});
it.each([null, []].map(value => [value]))("keeps absent or empty source gaps in the current review packet (%j)", (source_gaps) => {
  expect(api.parseLifecycleReviewPacket({ ...fixture.packet, source_gaps }).source_gaps).toEqual(source_gaps);
});
it("projects current review source gaps without weakening their validation", () => {
  const source_gaps = [{ url: "https://issuer.example/unavailable", reason: "source_timeout" }, { url: null, reason: "source_unavailable" }];
  expect(api.parseLifecycleReviewPacket({ ...fixture.packet, source_gaps }).source_gaps).toEqual(source_gaps);
});
it.each([{}, [null], [{ url: "http://issuer.example/notice", reason: "source_timeout" }],
  [{ url: "https://user:pass@issuer.example/notice", reason: "source_timeout" }],
  [{ url: "javascript:alert(1)", reason: "source_timeout" }], [{ url: null, reason: "private error text" }],
  [{ url: null, reason: "source_timeout", private_field: "hidden" }], [{ reason: "source_timeout" }],
].map(value => [value]))("rejects malformed current review source gaps (%j)", (source_gaps) => {
  expect(() => api.parseLifecycleReviewPacket({ ...fixture.packet, source_gaps })).toThrow();
});
it("keeps the provider confirmation request bound to the reviewed packet", async () => {
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(fixture.confirmation)));
  vi.stubGlobal("fetch", fetch);
  expect(await api.confirmLifecycleReview(fixture.packet)).toEqual(fixture.confirmation);
  expect(fetch).toHaveBeenCalledOnce();
  const [url, options] = fetch.mock.calls[0];
  expect(new URL(url).pathname).toBe(`/security-lifecycle/cases/${fixture.packet.case_id}/confirm-review`);
  expect(options.method).toBe("POST");
  expect(JSON.parse(options.body)).toEqual({ assessment_id: fixture.packet.assessment_id,
    packet_sha256: fixture.packet.packet_sha256, action: fixture.packet.action, ...fixture.packet.options });
});
