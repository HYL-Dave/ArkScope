/** @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import i18n from "i18next";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { withTestUiLocale } from "../test/testUiLocale";

const apiMocks = vi.hoisted(() => ({
  acknowledgeSecurityLifecycleCase: vi.fn(),
  acceptSecurityLifecycleAssessment: vi.fn(),
  addSecurityLifecycleEvidence: vi.fn(),
  createSecurityLifecycleAssessment: vi.fn(),
  dismissSecurityLifecycleProposal: vi.fn(),
  getSecurityLifecycleCase: vi.fn(),
  getSecurityLifecycleInvestigation: vi.fn(),
  listSecurityLifecycleCases: vi.fn(),
  reopenSecurityLifecycleAcknowledgement: vi.fn(),
  startSecurityLifecycleInvestigation: vi.fn(),
}));

vi.mock("../api", async (importOriginal) => ({
  ...await importOriginal<typeof import("../api")>(),
  ...apiMocks,
}));

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

const PROVIDER_EVIDENCE = "SEC source: Units of Beneficial Interest — 原文保留";
const CASE_ID = "slc_case_present";
const LIFECYCLE_VIEW_MODULE = "./LifecycleView";

const CASES = [
  ["slc_unresolved", "AAA", "unresolved"],
  ["slc_investigating", "BBB", "investigating"],
  ["slc_evidence", "CCC", "evidence_ready"],
  ["slc_inconclusive", "DDD", "reviewed_inconclusive"],
  ["slc_resolved", "EEE", "resolved"],
].map(([caseId, ticker, workflowState]) => ({
  case_id: caseId,
  source: "sec_edgar",
  source_ref: `ref-${ticker}`,
  ticker,
  source_presence: "present",
  workflow_state: workflowState,
  issuer_name: `${ticker} Issuer`,
  filing_date: "2026-08-20",
  kinds: [{ event_type: "listing_removal_notice", effective_date: null }],
  current_assessment: workflowState === "resolved"
    ? { relevance: "direct_tracked_security", confidence: "high" }
    : null,
  current_acknowledgement: workflowState === "reviewed_inconclusive"
    ? { acknowledgement_id: "ack-current" }
    : null,
  active_sources: ["manual_lists"],
  source_context: "available",
  components: {},
  investigation_run_count: workflowState === "investigating" ? 1 : 0,
  evidence_count: workflowState === "evidence_ready" ? 1 : 0,
  assessment_count: workflowState === "resolved" ? 1 : 0,
  acknowledgement_count: workflowState === "reviewed_inconclusive" ? 1 : 0,
  proposal_count: workflowState === "resolved" ? 1 : 0,
}));

const SUMMARY = {
  ...CASES[2],
  case_id: CASE_ID,
  ticker: "QBTS",
  issuer_name: "D-Wave Quantum Inc.",
  evidence_count: 2,
  investigation_run_count: 1,
};

function detail(overrides: Record<string, unknown> = {}) {
  return {
    ...SUMMARY,
    observation: {
      ticker: "QBTS",
      issuer_name: "D-Wave Quantum Inc.",
      source: "sec_edgar",
      source_ref: "0001907982-26-000111",
      filing_form: "25-NSE",
      filing_date: "2026-07-24",
      effective_date: null,
      evidence_url: "https://www.sec.gov/Archives/example/qbts.htm",
      description: "Class of securities: Common stock, par value $0.0001 per share.",
      kinds: [{ event_type: "listing_removal_notice", effective_date: null }],
    },
    investigation_runs: [{
      run_id: "run-zero",
      status: "succeeded",
      result_count: 0,
      failure_code: null,
      created_at: "2026-08-20T00:00:00Z",
    }],
    evidence: [{
      evidence_id: "evidence-sec",
      kind: "provider_document",
      excerpt: PROVIDER_EVIDENCE,
      source_url: "https://www.sec.gov/Archives/example/qbts.htm",
      content_sha256: "a".repeat(64),
      created_at: "2026-08-20T00:00:00Z",
    }],
    assessment_history: [{
      assessment_id: "assessment-legacy",
      status: "accepted",
      author: "legacy_review",
      relevance: "undetermined",
      confidence: "unknown",
      conclusion: "Legacy review: renamed or transferred.",
      impact_summary: "Supporting rationale was not retained.",
      outcomes: ["undetermined"],
      stale: true,
      created_at: "2026-08-17T00:00:00Z",
    }],
    acknowledgement_history: [],
    current_acknowledgement: null,
    current_assessment: null,
    proposals: [{
      proposal_id: "proposal-review",
      action_type: "review_portfolio_position",
      status: "proposed",
      block_reason: "portfolio_position_open",
      source_snapshot: ["manual_lists", "portfolio_open"],
      created_at: "2026-08-20T00:00:00Z",
    }],
    truncation: {},
    ...overrides,
  };
}

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

async function flush() {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

async function mountLifecycle(caseId: string | null = CASE_ID) {
  const { LifecycleView } = await import(/* @vite-ignore */ LIFECYCLE_VIEW_MODULE);
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(withTestUiLocale(<LifecycleView initialCaseId={caseId} />));
    await Promise.resolve();
  });
  await flush();
}

async function click(label: string, scope: ParentNode = document.body) {
  const button = Array.from(scope.querySelectorAll<HTMLButtonElement>("button"))
    .find((candidate) => candidate.textContent?.includes(label)
      || candidate.getAttribute("aria-label")?.includes(label));
  if (!button) throw new Error(`missing button: ${label}; rendered=${scope.textContent ?? ""}`);
  await act(async () => button.click());
  await flush();
}

async function setField(label: string, value: string) {
  const field = document.body.querySelector<HTMLInputElement | HTMLTextAreaElement>(
    `[aria-label="${label}"]`,
  );
  if (!field) throw new Error(`missing field: ${label}`);
  await act(async () => {
    const prototype = field instanceof HTMLTextAreaElement
      ? HTMLTextAreaElement.prototype
      : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(prototype, "value")?.set?.call(field, value);
    field.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await flush();
}

async function change(label: string, value: string) {
  const select = document.body.querySelector<HTMLSelectElement>(`[aria-label="${label}"]`);
  if (!select) throw new Error(`missing select: ${label}`);
  await act(async () => {
    select.value = value;
    select.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await flush();
}

beforeEach(async () => {
  await i18n.changeLanguage("en");
  vi.clearAllMocks();
  apiMocks.listSecurityLifecycleCases.mockResolvedValue({
    cases: [SUMMARY, ...CASES],
    count: 6,
    data_integrity: { source_missing_count: 1 },
  });
  apiMocks.getSecurityLifecycleCase.mockResolvedValue(detail());
  apiMocks.startSecurityLifecycleInvestigation.mockResolvedValue({
    run_id: "run-new",
    status: "succeeded",
    result_count: 0,
  });
  apiMocks.addSecurityLifecycleEvidence.mockResolvedValue({ evidence_id: "evidence-new" });
  apiMocks.createSecurityLifecycleAssessment.mockResolvedValue({
    assessment_id: "assessment-new",
  });
  apiMocks.acceptSecurityLifecycleAssessment.mockResolvedValue({ assessment: {}, proposals: [] });
  apiMocks.acknowledgeSecurityLifecycleCase.mockResolvedValue({
    acknowledgement_id: "ack-new",
  });
  apiMocks.reopenSecurityLifecycleAcknowledgement.mockResolvedValue({
    acknowledgement_id: "ack-current",
    status: "reopened",
  });
  apiMocks.dismissSecurityLifecycleProposal.mockResolvedValue({
    proposal_id: "proposal-review",
    status: "dismissed",
  });
});

afterEach(() => {
  if (root) act(() => root!.unmount());
  root = null;
  host?.remove();
  host = null;
  document.body.querySelectorAll(".ui-overlay-backdrop").forEach((node) => node.remove());
});

describe("Lifecycle workflow", () => {
  it("acknowledges insufficient evidence and reopens it without creating an assessment", async () => {
    apiMocks.getSecurityLifecycleCase
      .mockResolvedValueOnce(detail())
      .mockResolvedValueOnce(detail({
        workflow_state: "reviewed_inconclusive",
        current_acknowledgement: { acknowledgement_id: "ack-current", stale: false },
        acknowledgement_history: [{ acknowledgement_id: "ack-current", stale: false }],
      }))
      .mockResolvedValueOnce(detail());
    await mountLifecycle();
    await click("Mark inconclusive");
    expect(apiMocks.acknowledgeSecurityLifecycleCase).toHaveBeenCalledWith(CASE_ID, {
      reason: "evidence_insufficient",
      note: null,
    });
    expect(apiMocks.createSecurityLifecycleAssessment).not.toHaveBeenCalled();
    await click("Reopen");
    expect(apiMocks.reopenSecurityLifecycleAcknowledgement).toHaveBeenCalledWith("ack-current");
  });

  it("adds manual URL and text evidence without network access", async () => {
    await mountLifecycle();
    await setField("Manual evidence text", "Issuer investor-relations statement.");
    await click("Add text evidence");
    await setField("Manual evidence URL", "https://example.com/issuer-notice");
    await click("Add URL evidence");
    expect(apiMocks.addSecurityLifecycleEvidence.mock.calls).toEqual([
      [CASE_ID, { text: "Issuer investor-relations statement.", url: null }],
      [CASE_ID, { text: null, url: "https://example.com/issuer-notice" }],
    ]);
    expect(apiMocks.startSecurityLifecycleInvestigation).not.toHaveBeenCalled();
  });

  it("blocks proposal controls when a portfolio position requires review", async () => {
    await mountLifecycle();
    expect(document.body.textContent).toContain("Open portfolio position requires review");
    expect(document.body.textContent).toContain("Recommendation only");
    expect(document.body.textContent).not.toMatch(/Apply|Execute/);
  });

  it("filters cases by workflow relevance event kind and proposal type", async () => {
    await mountLifecycle(null);
    await change("Workflow state", "resolved");
    await change("Relevance", "direct_tracked_security");
    await change("Event kind", "listing_removal_notice");
    await change("Proposal type", "notify");
    expect(apiMocks.listSecurityLifecycleCases).toHaveBeenLastCalledWith(expect.objectContaining({
      workflow_state: "resolved",
      relevance: "direct_tracked_security",
      event_type: "listing_removal_notice",
      proposal_type: "notify",
      source_presence: "present",
    }));
  });

  it("keeps prior evidence and shows a typed safe error when search fails", async () => {
    apiMocks.startSecurityLifecycleInvestigation.mockRejectedValue(Object.assign(
      new Error("token=private /home/private"),
      { code: "usage_limit_reached", diagnostic: "secret traceback" },
    ));
    await mountLifecycle();
    await click("Search with Tavily");
    expect(document.body.textContent).toContain(PROVIDER_EVIDENCE);
    expect(document.body.textContent).toContain("Search usage limit reached");
    expect(document.body.textContent).not.toMatch(/token=private|\/home\/private|traceback/);
  });

  it("keeps source-missing history visible and marks changed source content for revalidation", async () => {
    apiMocks.getSecurityLifecycleCase.mockResolvedValue(detail({
      source_presence: "source_missing",
      observation: null,
      workflow_state: "evidence_ready",
      assessment_history: [{
        assessment_id: "assessment-stale",
        status: "accepted",
        stale: true,
        conclusion: "Prior accepted conclusion",
      }],
    }));
    await mountLifecycle();
    expect(document.body.textContent).toContain("Source missing");
    expect(document.body.textContent).toContain("Prior accepted conclusion");
    expect(document.body.textContent).toContain("Revalidation required");
    expect(document.body.textContent).not.toMatch(/Search with Tavily|Mark inconclusive|Accept assessment/);
  });

  it("names Tavily and sends exactly one bounded request after the explicit search click", async () => {
    await mountLifecycle();
    expect(apiMocks.startSecurityLifecycleInvestigation).not.toHaveBeenCalled();
    await click("Search with Tavily");
    expect(apiMocks.startSecurityLifecycleInvestigation).toHaveBeenCalledOnce();
    expect(apiMocks.startSecurityLifecycleInvestigation).toHaveBeenCalledWith(CASE_ID, {
      adapter: "tavily",
    });
  });

  it("opening refreshing focusing and switching tabs issue zero investigation requests", async () => {
    await mountLifecycle();
    window.dispatchEvent(new Event("focus"));
    await click("Refresh cases");
    await click("Data integrity");
    await click("Investment events");
    expect(apiMocks.startSecurityLifecycleInvestigation).not.toHaveBeenCalled();
  });

  it("opens a drawer with source evidence acknowledgement assessment and proposal sections", async () => {
    await mountLifecycle();
    for (const label of [
      "Source observation",
      "Evidence and searches",
      "Acknowledgement",
      "Assessment",
      "Action recommendations",
    ]) expect(document.body.textContent).toContain(label);
    expect(document.body.querySelector('[role="dialog"]')).not.toBeNull();
  });

  it("records successful zero-result runs without claiming no impact", async () => {
    await mountLifecycle();
    expect(document.body.textContent).toContain("Search completed · 0 results");
    expect(document.body.textContent).not.toMatch(/No impact|Unrelated|Nothing happened/);
  });

  it("renders bilingual workflow copy without translating provider evidence", async () => {
    await mountLifecycle();
    expect(document.body.textContent).toContain("Lifecycle investigation");
    expect(document.body.textContent).toContain(PROVIDER_EVIDENCE);
    await act(async () => { await i18n.changeLanguage("zh-Hant"); });
    await flush();
    expect(document.body.textContent).toContain("標的生命週期調查");
    expect(document.body.textContent).toContain(PROVIDER_EVIDENCE);
  });

  it("renders source-aware proposals as unapplied explanations", async () => {
    await mountLifecycle();
    expect(document.body.textContent).toContain("manual_lists");
    expect(document.body.textContent).toContain("Recommendation only");
    await click("Dismiss recommendation");
    expect(apiMocks.dismissSecurityLifecycleProposal).toHaveBeenCalledWith("proposal-review");
  });

  it("renders unresolved investigating evidence ready inconclusive and resolved as distinct states", async () => {
    await mountLifecycle(null);
    const rows = Array.from(host!.querySelectorAll<HTMLTableRowElement>("tbody tr"));
    expect(rows.map((row) => row.dataset.workflowState)).toEqual([
      "evidence_ready",
      "unresolved",
      "investigating",
      "evidence_ready",
      "reviewed_inconclusive",
      "resolved",
    ]);
  });

  it("requires cited evidence before accepting a conclusive assessment", async () => {
    await mountLifecycle();
    await setField("Assessment conclusion", "The tracked security will stop trading.");
    await setField("Investment impact", "Review the portfolio position before acting.");
    await click("Save assessment draft");
    expect(apiMocks.createSecurityLifecycleAssessment).not.toHaveBeenCalled();
    expect(document.body.textContent).toContain("Select at least one evidence citation");
    const citation = document.body.querySelector<HTMLInputElement>(
      '[aria-label="Cite provider evidence"]',
    );
    if (!citation) throw new Error("missing evidence citation");
    await act(async () => citation.click());
    await click("Save assessment draft");
    expect(apiMocks.createSecurityLifecycleAssessment).toHaveBeenCalledWith(
      CASE_ID,
      expect.objectContaining({ citations: [{
        reference_kind: "evidence",
        evidence_id: "evidence-sec",
      }] }),
    );
  });

  it("shows legacy reviews with limited provenance", async () => {
    await mountLifecycle();
    expect(document.body.textContent).toContain("Legacy review");
    expect(document.body.textContent).toContain("Supporting rationale was not retained");
    expect(document.body.textContent).toContain("Limited provenance");
  });

  it("uses the stable responsive triage and drawer structure", async () => {
    await mountLifecycle();
    expect(host!.querySelector(".lifecycle-triage")).not.toBeNull();
    expect(host!.querySelector(".lifecycle-table-wrap")).not.toBeNull();
    expect(document.body.querySelector(".lifecycle-drawer-content")).not.toBeNull();
    expect(document.body.querySelector(".ui-drawer")).not.toBeNull();
  });
});
