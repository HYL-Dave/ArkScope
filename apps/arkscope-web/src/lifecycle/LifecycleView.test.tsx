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
  approveTickerIdentityTransition: vi.fn(),
  cancelTickerIdentityTransition: vi.fn(),
  createSecurityLifecycleAssessment: vi.fn(),
  dismissSecurityLifecycleProposal: vi.fn(),
  getSecurityLifecycleCase: vi.fn(),
  getSecurityLifecycleInvestigation: vi.fn(),
  getTickerIdentityTransitionPreview: vi.fn(),
  listTickerIdentityTransitionActivity: vi.fn(),
  listSecurityLifecycleCases: vi.fn(),
  acknowledgeTickerIdentityTransitionActivity: vi.fn(),
  reopenSecurityLifecycleAcknowledgement: vi.fn(),
  retryTickerIdentityTransition: vi.fn(),
  reverseTickerIdentityTransition: vi.fn(),
  translateSecurityLifecycleEvidence: vi.fn(),
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

const LEGACY_ASSESSMENT = {
  assessment_id: "assessment-legacy",
  status: "accepted",
  author: "legacy_review",
  automation_method: null,
  acceptance_authority: "legacy_migration",
  automation_run_id: null,
  rule_id: null,
  rule_version: null,
  decision_provenance_sha256: null,
  relevance: "direct_tracked_security",
  confidence: "unknown",
  conclusion: "Legacy review marked a symbol or venue change.",
  impact_summary: "The legacy label did not distinguish renaming from transfer.",
  outcomes: ["symbol_or_venue_changed"],
  citations: [{
    reference_kind: "observation",
    evidence_id: null,
    cited_content_sha256: "f".repeat(64),
  }],
  stale: false,
  created_at: "2026-08-17T00:00:00Z",
  counterparty_name: null,
  counterparty_ticker: null,
  counterparty_cik: null,
  successor_ticker: null,
  destination_venue: null,
  effective_date: null,
  consideration_currency: null,
  cash_per_security_decimal: null,
  exchange_ratio_decimal: null,
};

const AUTOMATION_DRAFT = {
  assessment_id: "assessment-automation",
  status: "draft",
  author: "automation",
  automation_method: "deterministic_rule",
  acceptance_authority: null,
  automation_run_id: "automation-run-1",
  rule_id: "m-and-a-review",
  rule_version: "2",
  decision_provenance_sha256: "d".repeat(64),
  relevance: "direct_tracked_security",
  confidence: "medium",
  conclusion: "The transaction requires review before changing tracking.",
  impact_summary: "Confirm the successor security and consideration terms.",
  outcomes: ["acquisition_terms_unknown"],
  citations: [{
    reference_kind: "observation",
    evidence_id: null,
    cited_content_sha256: "f".repeat(64),
  }, {
    reference_kind: "evidence",
    evidence_id: "evidence-sec",
    cited_content_sha256: "a".repeat(64),
  }],
  stale: false,
  created_at: "2026-08-25T10:00:00Z",
  counterparty_name: "Acquirer Corp.",
  counterparty_ticker: "ACQ",
  counterparty_cik: "0000123456",
  successor_ticker: "NEW",
  destination_venue: "Nasdaq",
  effective_date: "2026-09-30",
  consideration_currency: "USD",
  cash_per_security_decimal: "10.50",
  exchange_ratio_decimal: "0.25",
};

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

const TRANSITION_PREVIEW = {
  active_sources: ["manual_lists", "portfolio_open", "sa_alpha_picks_current"],
  assessment_fingerprint_sha256: "1".repeat(64),
  assessment_id: "assessment-transition",
  block_reasons: [],
  case_id: CASE_ID,
  caveats: ["portfolio_position_retained", "provider_owned_sources_retained"],
  effects: {
    editable_tags_to_copy: [{
      facet: "theme",
      source: "user",
      ticker: "QBTS.B",
      value: "Quantum",
    }],
    legacy_config_seed: {
      add: [],
      archive: [{ source_key: "legacy_config_seed", ticker: "QBTS" }],
      reactivate: [{ source_key: "legacy_config_seed", ticker: "QBTS.B" }],
      unchanged: [],
    },
    priority: {
      resolution: "source",
      result_value: "high",
      source_value: "high",
      successor_value: "low",
      write_successor: true,
    },
    suppression: {
      hide_source: false,
      source_hidden: false,
      successor_hidden: true,
      unhide_successor: true,
    },
    watchlists: {
      add: [{ list_id: 7, list_name: "Quantum", position: 2, ticker: "QBTS.B" }],
      archive: [{ list_id: 7, list_name: "Quantum", position: 4, ticker: "QBTS" }],
      reactivate: [],
      unchanged: [],
    },
  },
  eligible: true,
  evidence_set_sha256: "2".repeat(64),
  execute_on: "2026-09-01",
  observation_fingerprint_sha256: "3".repeat(64),
  outcomes: ["symbol_changed"],
  preview_sha256: "b".repeat(64),
  profile_state_sha256: "4".repeat(64),
  proposal_ids: ["proposal-remap"],
  provider_owned_sources: ["sa_alpha_picks_current"],
  source_ticker: "QBTS",
  successor_ticker: "QBTS.B",
  transition_kind: "symbol_continuation",
};

function detail(overrides: Record<string, unknown> = {}) {
  return {
    ...SUMMARY,
    workflow_state: "resolved",
    current_assessment: LEGACY_ASSESSMENT,
    observation_fingerprint_sha256: "f".repeat(64),
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
      source_family: "regulator",
      kind: "regulator_excerpt",
      excerpt: PROVIDER_EVIDENCE,
      source_url: "https://www.sec.gov/Archives/example/qbts.htm",
      content_sha256: "a".repeat(64),
      title: "NYSE withdrawal notice",
      publisher: "U.S. Securities and Exchange Commission",
      source_published_at: "2026-07-24T12:00:00Z",
      translations: [{
        evidence_id: "evidence-sec",
        evidence_content_sha256: "a".repeat(64),
        locale: "en",
        translated_text: "SEC source: Units of Beneficial Interest",
        provider: "openai",
        model: "gpt-5",
        harness: "responses-api",
        translated_at: "2026-08-25T11:00:00Z",
      }],
      created_at: "2026-08-20T00:00:00Z",
    }],
    automation_runs: [{
      run_id: "automation-run-default",
      case_id: CASE_ID,
      mode: "historical",
      status: "succeeded",
      policy_version: "lifecycle-automation-v1",
      decision_tier: "verified_automatic",
      action_readiness: "not_applicable",
      failure_code: null,
      blockers: [],
      created_at: "2026-08-25T09:00:00Z",
    }],
    automation_facts: [{
      fact_id: "fact-default",
      automation_run_id: "automation-run-default",
      evidence_id: "evidence-sec",
      source_family: "regulator",
      fact_type: "source_ticker",
      normalized_value: "QBTS",
      source_span_start: 0,
      source_span_end: 4,
      cited_text_sha256: "c".repeat(64),
      extractor_rule_id: "sec-symbol",
      extractor_rule_version: "1",
      created_at: "2026-08-25T09:00:00Z",
    }],
    assessment_history: [LEGACY_ASSESSMENT],
    acknowledgement_history: [],
    current_acknowledgement: null,
    ticker_transition: null,
    proposals: [{
      proposal_id: "proposal-review",
      action_type: "review_portfolio_position",
      status: "proposed",
      block_reason: "portfolio_position_open",
      source_snapshot: ["manual_lists", "portfolio_open"],
      created_at: "2026-08-20T00:00:00Z",
    }, {
      proposal_id: "proposal-hide",
      action_type: "hide_from_active_universe",
      status: "dismissed",
      block_reason: null,
      source_snapshot: ["sa_alpha_picks_current", "legacy_config_seed"],
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

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
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

async function toggle(label: string) {
  const checkbox = document.body.querySelector<HTMLInputElement>(`input[aria-label="${label}"]`);
  if (!checkbox) throw new Error(`missing checkbox: ${label}`);
  await act(async () => checkbox.click());
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
  apiMocks.getTickerIdentityTransitionPreview.mockResolvedValue(TRANSITION_PREVIEW);
  apiMocks.listTickerIdentityTransitionActivity.mockResolvedValue({
    items: [],
    count: 0,
    unacknowledged_count: 0,
  });
  apiMocks.acknowledgeTickerIdentityTransitionActivity.mockResolvedValue({
    activity_id: "activity-1",
    acknowledged_at: "2026-08-25T13:00:00Z",
  });
  apiMocks.approveTickerIdentityTransition.mockResolvedValue({
    transition_id: "transition-1",
    status: "approved",
  });
  apiMocks.cancelTickerIdentityTransition.mockResolvedValue({
    transition_id: "transition-1",
    status: "cancelled",
  });
  apiMocks.retryTickerIdentityTransition.mockResolvedValue({
    transition_id: "transition-1",
    status: "applied",
  });
  apiMocks.reverseTickerIdentityTransition.mockResolvedValue({
    transition_id: "transition-1",
    status: "reversed",
  });
  apiMocks.translateSecurityLifecycleEvidence.mockResolvedValue({
    evidence_id: "evidence-sec",
    evidence_content_sha256: "a".repeat(64),
    locale: "en",
    translated_text: "Translated excerpt",
    provider: "openai",
    model: "gpt-5",
    harness: "responses-api",
    translated_at: "2026-08-25T13:00:00Z",
    cached: false,
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
    await click("Record insufficient evidence");
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

  it("keeps prior evidence and shows a typed safe historical run error", async () => {
    apiMocks.getSecurityLifecycleCase.mockResolvedValue(detail({
      investigation_runs: [{
        run_id: "run-failed",
        status: "failed",
        result_count: 0,
        failure_code: "usage_limit_reached",
        created_at: "2026-08-20T00:00:00Z",
      }],
    }));
    await mountLifecycle();
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
        ...LEGACY_ASSESSMENT,
        assessment_id: "assessment-stale",
        stale: true,
        conclusion: "Prior accepted conclusion",
      }],
    }));
    await mountLifecycle();
    expect(document.body.textContent).toContain("Source observation missing");
    expect(document.body.textContent).toContain("Prior accepted conclusion");
    expect(document.body.textContent).toContain("Revalidation required");
    expect(document.body.textContent).not.toMatch(
      /Record insufficient evidence|Accept assessment/,
    );
  });

  it("omits the retired search command while manual evidence remains reachable", async () => {
    await mountLifecycle();
    expect(document.body.textContent).not.toContain("Tavily");
    expect(document.body.textContent).toContain("Add text evidence");
    expect(document.body.textContent).toContain("Add URL evidence");
  });

  it("opening refreshing focusing and switching tabs keep search retired", async () => {
    await mountLifecycle();
    window.dispatchEvent(new Event("focus"));
    await click("Refresh cases");
    await click("Data integrity");
    await click("Security events");
    expect(document.body.textContent).not.toContain("Tavily");
  });

  it("opens a drawer with source evidence acknowledgement assessment and proposal sections", async () => {
    await mountLifecycle();
    for (const label of [
      "Source observation",
      "Evidence and searches",
      "Inconclusive review",
      "Assessment",
      "Action recommendations",
    ]) expect(document.body.textContent).toContain(label);
    expect(document.body.querySelector('[role="dialog"]')).not.toBeNull();
  });

  it("records successful zero-result runs without claiming no impact", async () => {
    await mountLifecycle();
    const history = Array.from(document.body.querySelectorAll("section")).find(
      (section) => section.querySelector("h3")?.textContent === "Evidence and searches",
    );
    expect(history?.textContent).toContain("Search completed · 0 results");
    expect(history?.textContent).not.toMatch(/No impact|Unrelated|Nothing happened/);
  });

  it("renders bilingual workflow copy without translating provider evidence", async () => {
    await mountLifecycle();
    expect(document.body.textContent).toContain("Security event investigation");
    expect(document.body.textContent).toContain(PROVIDER_EVIDENCE);
    await act(async () => { await i18n.changeLanguage("zh-Hant"); });
    await flush();
    expect(document.body.textContent).toContain("標的事件調查");
    expect(document.body.textContent).toContain("證據不足，未能定論");
    expect(document.body.textContent).toContain(PROVIDER_EVIDENCE);
  });

  it("renders source-aware proposals as unapplied explanations", async () => {
    await mountLifecycle();
    expect(document.body.textContent).toContain("Manual lists");
    expect(document.body.textContent).toContain("Open portfolio position");
    expect(document.body.textContent).toContain("Seeking Alpha picks");
    expect(document.body.textContent).toContain("Imported legacy settings");
    expect(document.body.textContent).toContain("Recommend hiding from the active universe");
    expect(document.body.textContent).toContain("Recommendation dismissed; not applied");
    expect(document.body.textContent).not.toMatch(
      /manual_lists|portfolio_open|sa_alpha_picks_current|legacy_config_seed/,
    );
    expect(document.body.textContent).toContain("Recommendation only; not applied");
    await click("Dismiss recommendation");
    expect(apiMocks.dismissSecurityLifecycleProposal).toHaveBeenCalledWith("proposal-review");
    await act(async () => { await i18n.changeLanguage("zh-Hant"); });
    await flush();
    for (const label of ["手動清單", "未平倉投資部位", "Seeking Alpha 選股", "舊設定匯入"]) {
      expect(document.body.textContent).toContain(label);
    }
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
    expect(document.body.querySelector<HTMLSelectElement>(
      '[aria-label="Assessment relevance"]',
    )?.value).toBe("undetermined");
    expect(document.body.querySelector<HTMLSelectElement>(
      '[aria-label="Assessment confidence"]',
    )?.value).toBe("unknown");
    expect(document.body.querySelector<HTMLInputElement>(
      'input[aria-label="Undetermined"]',
    )?.checked).toBe(true);
    await setField("Assessment conclusion", "The tracked security will stop trading.");
    await setField("Investment impact", "Review the portfolio position before acting.");
    await click("Save assessment draft");
    expect(apiMocks.createSecurityLifecycleAssessment).not.toHaveBeenCalled();
    expect(document.body.textContent).toContain(
      "Select the current source observation before saving the assessment",
    );
    const evidenceCitation = document.body.querySelector<HTMLInputElement>(
      'input[aria-label="Cite this evidence"]',
    );
    if (!evidenceCitation) throw new Error("missing evidence citation");
    await act(async () => evidenceCitation.click());
    await click("Save assessment draft");
    expect(apiMocks.createSecurityLifecycleAssessment).not.toHaveBeenCalled();
    const observationCitation = document.body.querySelector<HTMLInputElement>(
      'input[data-citation-kind="observation"]',
    );
    if (!observationCitation) throw new Error("missing current observation citation");
    await act(async () => observationCitation.click());
    await click("Save assessment draft");
    expect(apiMocks.createSecurityLifecycleAssessment).toHaveBeenCalledWith(
      CASE_ID,
      expect.objectContaining({ citations: [
        {
          reference_kind: "observation",
          cited_content_sha256: "f".repeat(64),
        },
        {
          reference_kind: "evidence",
          evidence_id: "evidence-sec",
        },
      ] }),
    );
  });

  it("preserves the accepted meaning of the real migrated legacy review in both locales", async () => {
    await mountLifecycle();
    const legacy = Array.from(document.body.querySelectorAll(".lifecycle-history-row"))
      .find((item) => item.textContent?.includes("Legacy review"));
    expect(legacy?.textContent).toContain("Directly concerns the tracked security");
    expect(legacy?.textContent).toContain("Symbol or trading venue changed (legacy review)");
    expect(legacy?.textContent).toContain("Accepted through legacy migration");
    expect(legacy?.textContent).not.toContain("Undetermined");
    expect(document.body.textContent).toContain(PROVIDER_EVIDENCE);

    await act(async () => { await i18n.changeLanguage("zh-Hant"); });
    await flush();
    expect(legacy?.textContent).toContain("直接涉及追蹤證券");
    expect(legacy?.textContent).toContain("代號或交易市場異動（舊覆核未區分）");
    expect(legacy?.textContent).toContain("由舊資料遷移保留的接受結果");
    expect(legacy?.textContent).not.toContain("尚未判定");
    expect(document.body.textContent).toContain(PROVIDER_EVIDENCE);
  });

  it("renders automation provenance grouped facts and typed blockers", async () => {
    const automated = {
      ...AUTOMATION_DRAFT,
      status: "accepted",
      acceptance_authority: "automation_policy",
    };
    apiMocks.getSecurityLifecycleCase.mockResolvedValue(detail({
      current_assessment: automated,
      assessment_history: [automated],
      automation_runs: [{
        run_id: "automation-run-1",
        case_id: CASE_ID,
        mode: "historical",
        status: "blocked",
        policy_version: "lifecycle-automation-v1",
        decision_tier: "verified_automatic",
        action_readiness: "waiting_transition_revalidation",
        failure_code: null,
        blockers: [{ blocker_code: "transition_approval_changed", retryable: true }],
        created_at: "2026-08-25T10:00:00Z",
      }, {
        run_id: "automation-run-blocked",
        case_id: CASE_ID,
        mode: "historical",
        status: "blocked",
        policy_version: "lifecycle-automation-v1",
        decision_tier: null,
        action_readiness: null,
        failure_code: null,
        blockers: [{ blocker_code: "source_conflict", retryable: false }],
        created_at: "2026-08-25T09:00:00Z",
      }],
      automation_facts: [{
        fact_id: "fact-source",
        automation_run_id: "automation-run-1",
        evidence_id: "evidence-sec",
        source_family: "regulator",
        fact_type: "source_ticker",
        normalized_value: "LC",
        source_span_start: 0,
        source_span_end: 2,
        cited_text_sha256: "1".repeat(64),
        extractor_rule_id: "sec-symbol",
        extractor_rule_version: "1",
        created_at: "2026-08-25T10:00:00Z",
      }, {
        fact_id: "fact-venue",
        automation_run_id: "automation-run-1",
        evidence_id: "evidence-ibkr",
        source_family: "market_infrastructure",
        fact_type: "destination_venue",
        normalized_value: "NASDAQ",
        source_span_start: 12,
        source_span_end: 18,
        cited_text_sha256: "2".repeat(64),
        extractor_rule_id: "ibkr-venue",
        extractor_rule_version: "1",
        created_at: "2026-08-25T10:00:00Z",
      }, {
        fact_id: "fact-effect",
        automation_run_id: "automation-run-1",
        evidence_id: "evidence-sec",
        source_family: "regulator",
        fact_type: "tracked_security_effect",
        normalized_value: "symbol_and_venue_change",
        source_span_start: 20,
        source_span_end: 36,
        cited_text_sha256: "3".repeat(64),
        extractor_rule_id: "sec-effect",
        extractor_rule_version: "1",
        created_at: "2026-08-25T10:00:00Z",
      }],
    }));

    await mountLifecycle();
    for (const value of [
      "Verified automatic",
      "Waiting to revalidate tracking transition",
      "Transition approval inputs changed; revalidation is scheduled",
      "Automation-generated assessment",
      "Accepted by automation policy",
      "Deterministic rule",
      "m-and-a-review · v2",
      "Regulatory filing",
      "Market infrastructure",
      "Source ticker",
      "LC",
      "Destination venue",
      "NASDAQ",
      "Tracked-security effect",
      "Ticker and trading venue changed",
      "Observation citation",
      "Evidence citation",
    ]) expect(document.body.textContent).toContain(value);
    expect(document.body.textContent).not.toContain("Conflicting source facts");
    expect(document.body.textContent).not.toContain("symbol_and_venue_change");
  });

  it("prefills the newest automation suggestion without rewriting its authorship", async () => {
    apiMocks.getSecurityLifecycleCase.mockResolvedValue(detail({
      current_assessment: LEGACY_ASSESSMENT,
      assessment_history: [AUTOMATION_DRAFT, LEGACY_ASSESSMENT],
      automation_runs: [{
        run_id: "automation-run-1",
        case_id: CASE_ID,
        mode: "historical",
        status: "succeeded",
        policy_version: "lifecycle-automation-v1",
        decision_tier: "review_suggested",
        action_readiness: "action_blocked",
        failure_code: null,
        blockers: [],
        created_at: "2026-08-25T10:00:00Z",
      }],
    }));

    await mountLifecycle();
    expect(document.body.querySelector<HTMLInputElement>(
      '[aria-label="Successor ticker"]',
    )?.value).toBe("NEW");
    expect(document.body.querySelector<HTMLTextAreaElement>(
      '[aria-label="Assessment conclusion"]',
    )?.value).toBe(AUTOMATION_DRAFT.conclusion);
    expect(document.body.textContent).toContain("Automation-generated assessment");

    await click("Accept unchanged suggestion");
    expect(apiMocks.acceptSecurityLifecycleAssessment).toHaveBeenCalledWith(
      "assessment-automation",
    );

    await setField("Assessment conclusion", "Human-corrected conclusion.");
    await click("Save as human revision");
    expect(apiMocks.createSecurityLifecycleAssessment).toHaveBeenCalledWith(
      CASE_ID,
      expect.objectContaining({
        conclusion: "Human-corrected conclusion.",
        successor_ticker: "NEW",
        citations: expect.arrayContaining([{
          reference_kind: "observation",
          cited_content_sha256: "f".repeat(64),
        }]),
      }),
    );
    expect(AUTOMATION_DRAFT.author).toBe("automation");
  });

  it("keeps original evidence visible beside machine translation and translation failure", async () => {
    const secondExcerpt = "交易所公告原文必須保留";
    apiMocks.getSecurityLifecycleCase.mockResolvedValue(detail({
      evidence: [
        detail().evidence[0],
        {
          evidence_id: "evidence-market",
          source_family: "market_infrastructure",
          kind: "market_infrastructure_snapshot",
          excerpt: secondExcerpt,
          source_url: "https://example.com/market-notice",
          content_sha256: "9".repeat(64),
          title: "Market notice",
          publisher: "Exchange operator",
          source_published_at: null,
          translations: [],
          created_at: "2026-08-25T10:00:00Z",
        },
      ],
    }));
    apiMocks.translateSecurityLifecycleEvidence.mockRejectedValue(Object.assign(
      new Error("private provider failure"),
      { code: "translation_timeout" },
    ));

    await mountLifecycle();
    expect(document.body.textContent).toContain(PROVIDER_EVIDENCE);
    expect(document.body.textContent).toContain("SEC source: Units of Beneficial Interest");
    expect(document.body.textContent).toContain("Machine translation");
    expect(document.body.textContent).toContain("openai · gpt-5 · responses-api");
    expect(document.body.textContent).toContain(secondExcerpt);

    await click("Translate evidence");
    expect(apiMocks.translateSecurityLifecycleEvidence).toHaveBeenCalledWith(
      "evidence-market",
      "en",
    );
    expect(document.body.textContent).toContain(secondExcerpt);
    expect(document.body.textContent).toContain("Translation timed out");
    expect(document.body.textContent).not.toContain("private provider failure");
  });

  it("shows every known structured fact on an accepted assessment", async () => {
    const assessment = {
      ...LEGACY_ASSESSMENT,
      assessment_id: "assessment-structured",
      author: "human",
      relevance: "issuer_related",
      confidence: "high",
      conclusion: "The merger consideration is confirmed.",
      impact_summary: "Review the successor security and cash component.",
      outcomes: ["symbol_changed", "acquisition_mixed"],
      counterparty_name: "Acquirer Corp.",
      counterparty_ticker: "ACQ",
      counterparty_cik: "0000123456",
      successor_ticker: "NEW",
      destination_venue: "NYSE",
      effective_date: "2026-09-30",
      consideration_currency: "USD",
      cash_per_security_decimal: "10.5000",
      exchange_ratio_decimal: "0.2500",
    };
    apiMocks.getSecurityLifecycleCase.mockResolvedValue(detail({
      current_assessment: assessment,
      assessment_history: [assessment],
    }));

    await mountLifecycle();
    const history = Array.from(document.body.querySelectorAll(".lifecycle-history-row"))
      .find((item) => item.textContent?.includes("Acquirer Corp."));
    expect(history).toBeDefined();
    expect(history!.textContent).toContain("Issuer-related; may have indirect impact");
    expect(history!.textContent).toContain("High");
    expect(history!.textContent).toContain("Ticker symbol changed");
    expect(history!.textContent).toContain("Mixed-consideration acquisition");
    for (const value of [
      "Acquirer Corp.", "ACQ", "0000123456", "NEW", "NYSE", "2026-09-30",
      "USD 10.5000", "0.2500",
    ]) expect(history!.textContent).toContain(value);
    expect(history!.textContent).toContain("Consideration currencyUSD");
  });

  it("submits structured facts and multiple outcomes without moving them into prose", async () => {
    await mountLifecycle();
    for (const label of [
      "Counterparty name", "Counterparty ticker", "Counterparty CIK", "Successor ticker",
      "Destination venue", "Effective date", "Consideration currency", "Cash per security",
      "Exchange ratio",
    ]) {
      expect(document.body.querySelector(`[aria-label="${label}"]`), label).not.toBeNull();
    }
    await change("Assessment relevance", "direct_tracked_security");
    await change("Assessment confidence", "high");
    await setField("Counterparty name", "Acquirer Corp.");
    await setField("Counterparty ticker", "ACQ");
    await setField("Counterparty CIK", "0000123456");
    await setField("Successor ticker", "NEW");
    await setField("Destination venue", "NYSE");
    await setField("Effective date", "2026-09-30");
    await setField("Consideration currency", "USD");
    await setField("Cash per security", "10.5000");
    await setField("Exchange ratio", "0.2500");
    await toggle("Ticker symbol changed");
    await toggle("Mixed-consideration acquisition");
    await setField("Assessment conclusion", "The transaction terms are confirmed.");
    await setField("Investment impact", "Review the successor security.");
    await toggle("Source observation");
    await click("Save assessment draft");

    expect(apiMocks.createSecurityLifecycleAssessment).toHaveBeenCalledWith(CASE_ID, {
      relevance: "direct_tracked_security",
      confidence: "high",
      conclusion: "The transaction terms are confirmed.",
      impact_summary: "Review the successor security.",
      outcomes: ["symbol_changed", "acquisition_mixed"],
      counterparty_name: "Acquirer Corp.",
      counterparty_ticker: "ACQ",
      counterparty_cik: "0000123456",
      successor_ticker: "NEW",
      destination_venue: "NYSE",
      effective_date: "2026-09-30",
      consideration_currency: "USD",
      cash_per_security_decimal: "10.5000",
      exchange_ratio_decimal: "0.2500",
      citations: [{
        reference_kind: "observation",
        cited_content_sha256: "f".repeat(64),
      }],
    });
  });

  it("shows legacy reviews with limited provenance", async () => {
    await mountLifecycle();
    expect(document.body.textContent).toContain("Legacy review");
    expect(document.body.textContent).toContain(
      "The legacy label did not distinguish renaming from transfer",
    );
    expect(document.body.textContent).toContain("Limited provenance");
  });

  it("reviews every owned effect and approves only the server preview digest", async () => {
    await mountLifecycle();
    await click("Review ticker transition");

    const dialog = document.body.querySelector<HTMLElement>(".ui-confirm-dialog");
    expect(dialog).not.toBeNull();
    for (const value of [
      "QBTS -> QBTS.B",
      "2026-09-01",
      "Quantum",
      "theme",
      "high",
      "low",
      "The old broker position remains on QBTS",
      "Seeking Alpha tracking stays with the provider-owned source",
      "Historical notes, evidence, prices, and filings are not rewritten",
    ]) expect(dialog!.textContent).toContain(value);
    expect(dialog!.querySelectorAll('input[type="radio"]')).toHaveLength(2);

    await click("Approve scheduled transition", dialog!);
    expect(apiMocks.approveTickerIdentityTransition).toHaveBeenCalledWith(CASE_ID, {
      execute_on: "2026-09-01",
      preview_sha256: "b".repeat(64),
      priority_resolution: "source",
      unhide_successor: true,
    });
  });

  it("renders ineligible blockers without exposing an approval command", async () => {
    apiMocks.getTickerIdentityTransitionPreview.mockResolvedValue({
      ...TRANSITION_PREVIEW,
      eligible: false,
      block_reasons: ["successor_missing", "priority_resolution_required"],
      successor_ticker: null,
      transition_kind: null,
    });
    await mountLifecycle();
    expect(document.body.textContent).toContain("Successor ticker is required");
    expect(document.body.textContent).toContain("Choose which priority to keep");
    expect(document.body.textContent).not.toContain("Approve scheduled transition");
  });

  it("lets a missing execution date be resolved through a fresh server preview", async () => {
    apiMocks.getTickerIdentityTransitionPreview
      .mockResolvedValueOnce({
        ...TRANSITION_PREVIEW,
        eligible: false,
        execute_on: null,
        block_reasons: ["execution_date_required"],
      })
      .mockResolvedValue({
        ...TRANSITION_PREVIEW,
        execute_on: "2026-09-02",
      });
    await mountLifecycle();
    await setField("Scheduled date", "2026-09-02");
    expect(apiMocks.getTickerIdentityTransitionPreview).toHaveBeenLastCalledWith(CASE_ID, {
      execute_on: "2026-09-02",
      priority_resolution: "source",
      unhide_successor: true,
    });
    expect(document.body.textContent).toContain("Review ticker transition");
  });

  it("cancels an approved transition through its durable case state", async () => {
    apiMocks.getSecurityLifecycleCase.mockResolvedValue(detail({
      ticker_transition: {
        transition_id: "transition-1",
        kind: "symbol_continuation",
        status: "approved",
        source_ticker: "QBTS",
        successor_ticker: "QBTS.B",
        execute_on: "2026-09-01",
        approved_preview_sha256: "b".repeat(64),
        approved_preview: TRANSITION_PREVIEW,
        updated_at: "2026-08-23T10:00:00Z",
        latest_attempt: null,
      },
    }));
    await mountLifecycle();
    expect(document.body.textContent).toContain("Scheduled; waiting for the effective date");
    await click("Cancel scheduled transition");
    expect(apiMocks.cancelTickerIdentityTransition).toHaveBeenCalledWith("transition-1");
  });

  it.each(["approved", "needs_review", "applied"])(
    "keeps the approved effects visible while a transition is %s",
    async (status) => {
      apiMocks.getTickerIdentityTransitionPreview.mockResolvedValue({
        ...TRANSITION_PREVIEW,
        caveats: [],
      });
      apiMocks.getSecurityLifecycleCase.mockResolvedValue(detail({
        ticker_transition: {
          transition_id: `transition-${status}`,
          kind: "symbol_continuation",
          status,
          source_ticker: "QBTS",
          successor_ticker: "QBTS.B",
          execute_on: "2026-09-01",
          approved_preview_sha256: "b".repeat(64),
          approved_preview: TRANSITION_PREVIEW,
          updated_at: "2026-08-23T10:00:00Z",
          latest_attempt: null,
        },
      }));

      await mountLifecycle();

      expect(document.body.textContent).toContain("The old broker position remains on QBTS");
      expect(document.body.textContent).toContain(
        "Seeking Alpha tracking stays with the provider-owned source",
      );
    },
  );

  it("reports a changed preview and never treats the stale approval as successful", async () => {
    apiMocks.approveTickerIdentityTransition.mockRejectedValue(Object.assign(
      new Error("stale preview"),
      { code: "transition_preview_changed" },
    ));
    await mountLifecycle();
    await click("Review ticker transition");
    await click("Approve scheduled transition");
    expect(document.body.textContent).toContain(
      "The transition preview changed; review the current effects before approving again",
    );
  });

  it("keeps reversal blocked when later state no longer matches", async () => {
    apiMocks.getSecurityLifecycleCase.mockResolvedValue(detail({
      ticker_transition: {
        transition_id: "transition-applied",
        kind: "symbol_continuation",
        status: "applied",
        source_ticker: "QBTS",
        successor_ticker: "QBTS.B",
        execute_on: "2026-08-22",
        approved_preview_sha256: "b".repeat(64),
        approved_preview: TRANSITION_PREVIEW,
        updated_at: "2026-08-23T10:00:00Z",
        latest_attempt: {
          status: "applied",
          block_reasons: [],
          attempted_at: "2026-08-22T13:00:00Z",
        },
      },
    }));
    apiMocks.reverseTickerIdentityTransition.mockResolvedValue({
      status: "blocked",
      block_reasons: ["successor_has_later_transition"],
      transition: { transition_id: "transition-applied", status: "applied" },
    });
    await mountLifecycle();
    expect(document.body.textContent).toContain("The old broker position remains on QBTS");
    expect(document.body.textContent).toContain(
      "Seeking Alpha tracking stays with the provider-owned source",
    );
    expect(document.body.textContent).toContain(
      "Historical notes, evidence, prices, and filings are not rewritten",
    );
    await click("Reverse transition");
    await click("Confirm reversal");
    expect(document.body.textContent).toContain(
      "A later ticker transition exists; this transition cannot be reversed",
    );
  });

  it("disables transition commands while approval is pending", async () => {
    const pending = deferred<{ transition_id: string; status: string }>();
    apiMocks.approveTickerIdentityTransition.mockReturnValue(pending.promise);
    await mountLifecycle();
    await click("Review ticker transition");
    const dialog = document.body.querySelector<HTMLElement>(".ui-confirm-dialog")!;
    await click("Approve scheduled transition", dialog);
    const confirm = Array.from(dialog.querySelectorAll<HTMLButtonElement>("button"))
      .find((button) => button.textContent?.includes("Approve scheduled transition"));
    expect(confirm?.disabled).toBe(true);
    expect(dialog.querySelector<HTMLButtonElement>("button")?.disabled).toBe(true);
    pending.resolve({ transition_id: "transition-1", status: "approved" });
    await flush();
  });

  it("uses the stable responsive triage and drawer structure", async () => {
    await mountLifecycle();
    expect(host!.querySelector(".lifecycle-triage")).not.toBeNull();
    expect(host!.querySelector(".lifecycle-table-wrap")).not.toBeNull();
    expect(document.body.querySelector(".lifecycle-drawer-content")).not.toBeNull();
    expect(document.body.querySelector(".ui-drawer")).not.toBeNull();
  });
});
