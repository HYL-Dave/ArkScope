/** @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import i18n from "i18next";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  RuntimeConfig,
  SecurityLifecycleCaseFilters,
  SecurityLifecycleCaseSummary,
} from "../api";
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
const LIFECYCLE_RUNTIME = {
  fixed_task_runtime: {
    card_translation: {
      task: "card_translation",
      model_timeout_s: 600,
      source: "db",
      db_saved: true,
      warning: null,
    },
  },
} as RuntimeConfig;

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

const SUMMARY: SecurityLifecycleCaseSummary = {
  case_id: CASE_ID,
  source: "sec_edgar",
  source_ref: "ref-CCC",
  ticker: "QBTS",
  source_presence: "present",
  workflow_state: "evidence_ready",
  issuer_name: "D-Wave Quantum Inc.",
  filing_date: "2026-08-20",
  kinds: [{ event_type: "listing_removal_notice", effective_date: null }],
  current_assessment: null,
  current_acknowledgement: null,
  active_sources: ["manual_lists"],
  source_context: "available",
  components: {},
  automation_run_count: 0,
  automation_fact_count: 0,
  automation_tier: null,
  action_readiness: null,
  disposition: "exception_required",
  queue_bucket: "attention",
  disposition_reason: "ambiguous_event",
  disposition_as_of: null,
  last_checked_at: "2026-08-25T09:00:00Z",
  next_check_at: null,
  source_family_status: { regulator: "present" },
  evidence_count: 2,
  investigation_run_count: 1,
  assessment_count: 0,
  acknowledgement_count: 0,
  proposal_count: 0,
};

const CASES: SecurityLifecycleCaseSummary[] = ([
  ["slc_unresolved", "AAA", "unresolved"],
  ["slc_investigating", "BBB", "investigating"],
  ["slc_evidence", "CCC", "evidence_ready"],
  ["slc_inconclusive", "DDD", "reviewed_inconclusive"],
  ["slc_resolved", "EEE", "resolved"],
] as const).map(([caseId, ticker, workflowState]) => ({
  ...SUMMARY,
  case_id: caseId,
  source_ref: `ref-${ticker}`,
  ticker,
  workflow_state: workflowState,
  issuer_name: `${ticker} Issuer`,
  current_assessment: null,
  current_acknowledgement: null,
  disposition: workflowState === "resolved" || workflowState === "reviewed_inconclusive"
    ? "confirmed_effective"
    : workflowState === "evidence_ready"
      ? "exception_required"
      : "not_confirmed_yet",
  queue_bucket: workflowState === "resolved" || workflowState === "reviewed_inconclusive"
    ? "history"
    : workflowState === "evidence_ready"
      ? "attention"
      : "monitoring",
  disposition_reason: workflowState === "resolved"
    ? "resolved_assessment"
    : workflowState === "reviewed_inconclusive"
      ? "reviewed_inconclusive"
      : workflowState === "evidence_ready"
        ? "ambiguous_event"
        : workflowState === "investigating"
          ? "automation_running"
          : "awaiting_initial_automation",
  disposition_as_of: null,
  last_checked_at: workflowState === "unresolved" ? null : "2026-08-25T09:00:00Z",
  next_check_at: workflowState === "unresolved" || workflowState === "investigating"
    ? "2026-08-26T09:00:00Z"
    : null,
  investigation_run_count: workflowState === "investigating" ? 1 : 0,
  automation_run_count: workflowState === "investigating" ? 1 : 0,
  evidence_count: workflowState === "evidence_ready" ? 1 : 0,
  assessment_count: workflowState === "resolved" ? 1 : 0,
  acknowledgement_count: workflowState === "reviewed_inconclusive" ? 1 : 0,
  proposal_count: workflowState === "resolved" ? 1 : 0,
}));

const FINAL_UNCONFIRMED: SecurityLifecycleCaseSummary = Object.assign({}, SUMMARY, {
  disposition: "not_confirmed_yet" as const,
  queue_bucket: "history" as const,
  disposition_reason: "not_confirmed_as_of" as const,
  disposition_as_of: "2026-08-27",
  last_checked_at: "2026-08-27T12:00:00Z",
  next_check_at: null,
});

const MONITORING_UNCONFIRMED: SecurityLifecycleCaseSummary = Object.assign({}, SUMMARY, {
  disposition: "not_confirmed_yet" as const,
  queue_bucket: "monitoring" as const,
  disposition_reason: "event_completion_not_confirmed" as const,
  disposition_as_of: null,
  last_checked_at: "2026-08-27T12:00:00Z",
  next_check_at: "2026-08-28T12:00:00Z",
});

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

function detail(overrides: object = {}) {
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

async function mountLifecycle(
  caseId: string | null = CASE_ID,
  onNavigate = vi.fn(),
) {
  const { LifecycleView } = await import(/* @vite-ignore */ LIFECYCLE_VIEW_MODULE);
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(withTestUiLocale(
      <LifecycleView
        initialCaseId={caseId}
        onNavigate={onNavigate}
        runtime={LIFECYCLE_RUNTIME}
      />,
    ));
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
    queue_counts: { attention: 2, monitoring: 2, history: 2 },
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
  it("renders truthful dated final-History reasons in both locales without acknowledgement", async () => {
    apiMocks.listSecurityLifecycleCases.mockResolvedValue({
      cases: [FINAL_UNCONFIRMED],
      count: 1,
      queue_counts: { attention: 0, monitoring: 0, history: 1 },
      data_integrity: { source_missing_count: 0 },
    });
    apiMocks.getSecurityLifecycleCase.mockResolvedValue(detail(FINAL_UNCONFIRMED));

    await mountLifecycle();

    const englishCopy = "Not confirmed as of 2026-08-27; active checking stopped.";
    expect(host!.querySelector("tbody")?.textContent).toContain(englishCopy);
    expect(document.body.querySelector('[role="dialog"]')?.textContent).toContain(englishCopy);
    expect(document.body.textContent).not.toContain("Confirmed complete");
    expect(apiMocks.acknowledgeSecurityLifecycleCase).not.toHaveBeenCalled();
    expect(apiMocks.acknowledgeTickerIdentityTransitionActivity).not.toHaveBeenCalled();

    await act(async () => { await i18n.changeLanguage("zh-Hant"); });
    await flush();

    const chineseCopy = "截至 2026-08-27 尚未確認；已停止主動追查。";
    expect(host!.querySelector("tbody")?.textContent).toContain(chineseCopy);
    expect(document.body.querySelector('[role="dialog"]')?.textContent).toContain(chineseCopy);
    expect(document.body.textContent).not.toContain("已確認完成");
    expect(apiMocks.acknowledgeSecurityLifecycleCase).not.toHaveBeenCalled();
    expect(apiMocks.acknowledgeTickerIdentityTransitionActivity).not.toHaveBeenCalled();
  });

  it("does not infer stopped checking from last check time or a monitoring reason", async () => {
    const finalWithoutDispositionDate: SecurityLifecycleCaseSummary = {
      ...FINAL_UNCONFIRMED,
      disposition_as_of: null,
      last_checked_at: "2026-08-28T12:00:00Z",
    };
    apiMocks.listSecurityLifecycleCases.mockResolvedValue({
      cases: [finalWithoutDispositionDate, MONITORING_UNCONFIRMED],
      count: 2,
      queue_counts: { attention: 0, monitoring: 1, history: 1 },
      data_integrity: { source_missing_count: 0 },
    });

    await mountLifecycle(null);

    expect(host!.textContent).not.toContain("active checking stopped");
    expect(host!.textContent).toContain("Not confirmed as of the latest completed check");
    expect(host!.textContent).toContain("Event completion has not been confirmed");
  });

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

  it("separates attention monitoring history and all without acknowledging history", async () => {
    const queueRows = [
      {
        ...SUMMARY,
        case_id: "case-conflict",
        ticker: "CONFLICT",
        disposition: "exception_required",
        queue_bucket: "attention",
        disposition_reason: "source_conflict",
        last_checked_at: "2026-08-26T08:00:00Z",
        next_check_at: null,
        source_family_status: { regulator: "conflict", publisher: "present" },
      },
      {
        ...SUMMARY,
        case_id: "case-pending",
        ticker: "PENDING",
        disposition: "not_confirmed_yet",
        queue_bucket: "monitoring",
        disposition_reason: "event_completion_not_confirmed",
        last_checked_at: "2026-08-26T08:00:00Z",
        next_check_at: "2026-08-27T08:00:00Z",
        source_family_status: { regulator: "present", publisher: "present" },
      },
      {
        ...SUMMARY,
        case_id: "case-waiting",
        ticker: "WAITING",
        disposition: "confirmed_monitoring",
        queue_bucket: "monitoring",
        disposition_reason: "waiting_effective_date",
        last_checked_at: "2026-08-26T08:00:00Z",
        next_check_at: "2026-09-01T00:00:00Z",
        source_family_status: { regulator: "confirmed" },
      },
      {
        ...SUMMARY,
        case_id: "case-done",
        ticker: "DONE",
        disposition: "confirmed_effective",
        queue_bucket: "history",
        disposition_reason: "resolved_no_change",
        last_checked_at: "2026-08-25T08:00:00Z",
        next_check_at: null,
        source_family_status: { regulator: "confirmed" },
      },
    ];
    const counts = { attention: 1, monitoring: 2, history: 1 };
    apiMocks.listTickerIdentityTransitionActivity.mockResolvedValue({
      items: [{
        activity_id: "activity-unacknowledged",
        transition_id: "transition-reversed",
        case_id: "case-done",
        activity_type: "reversed",
        source_ticker: "OLD",
        successor_ticker: "DONE",
        effective_date: "2026-08-25",
        user_owned_changes: [],
        provider_owned_retained: [],
        state_sha256: "1".repeat(64),
        rule_id: "lifecycle.simple_symbol_continuation",
        rule_version: "1",
        decision_provenance_sha256: "2".repeat(64),
        occurred_at: "2026-08-25T08:00:00Z",
        acknowledged_at: null,
        created_at: "2026-08-25T08:00:00Z",
      }],
      count: 1,
      unacknowledged_count: 1,
    });
    apiMocks.listSecurityLifecycleCases.mockImplementation(
      async (filters: SecurityLifecycleCaseFilters) => {
        const bucket = filters.queue_bucket;
        return {
          cases: bucket
            ? queueRows.filter((row) => row.queue_bucket === bucket)
            : queueRows,
          count: bucket ? counts[bucket] : queueRows.length,
          queue_counts: counts,
          data_integrity: { source_missing_count: 0 },
        };
      },
    );
    await act(async () => { await i18n.changeLanguage("zh-Hant"); });
    await mountLifecycle(null);

    const renderedTickers = () => Array.from(
      host!.querySelectorAll<HTMLElement>(".lifecycle-case-trigger .mono"),
    ).map((node) => node.textContent);
    const selectedTab = () => host!.querySelector<HTMLElement>(
      '.lifecycle-queue-switch [aria-selected="true"]',
    );

    expect(selectedTab()?.textContent).toContain("需要處理");
    expect(renderedTickers()).toEqual(["CONFLICT"]);

    await click("監看中", host!);
    expect(renderedTickers()).toEqual(["PENDING", "WAITING"]);
    expect(host!.textContent).toContain("下次查核");

    await click("歷史", host!);
    expect(renderedTickers()).toEqual(["DONE"]);
    expect(apiMocks.acknowledgeTickerIdentityTransitionActivity).not.toHaveBeenCalled();

    await click("全部", host!);
    expect(renderedTickers()).toEqual(["CONFLICT", "PENDING", "WAITING", "DONE"]);
    expect(apiMocks.listSecurityLifecycleCases).toHaveBeenLastCalledWith(
      expect.not.objectContaining({ queue_bucket: expect.anything() }),
    );
  });

  it("commits only the newest queue response when requests resolve out of order", async () => {
    const attention = deferred<{
      cases: SecurityLifecycleCaseSummary[];
      count: number;
      queue_counts: { attention: number; monitoring: number; history: number };
      data_integrity: { source_missing_count: number };
    }>();
    const monitoring = deferred<{
      cases: SecurityLifecycleCaseSummary[];
      count: number;
      queue_counts: { attention: number; monitoring: number; history: number };
      data_integrity: { source_missing_count: number };
    }>();
    const staleAttention = {
      ...SUMMARY,
      case_id: "case-stale-attention",
      ticker: "STALE",
      queue_bucket: "attention" as const,
    };
    const newestMonitoring = {
      ...MONITORING_UNCONFIRMED,
      case_id: "case-newest-monitoring",
      ticker: "NEWEST",
    };
    apiMocks.listSecurityLifecycleCases.mockImplementation(
      (request: SecurityLifecycleCaseFilters) => (
        request.queue_bucket === "monitoring" ? monitoring.promise : attention.promise
      ),
    );

    await mountLifecycle(null);
    await click("Monitoring", host!);
    await act(async () => {
      monitoring.resolve({
        cases: [newestMonitoring],
        count: 1,
        queue_counts: { attention: 1, monitoring: 1, history: 0 },
        data_integrity: { source_missing_count: 0 },
      });
      await Promise.resolve();
    });
    await flush();
    expect(host!.textContent).toContain("NEWEST");
    expect(host!.textContent).not.toContain("STALE");

    await act(async () => {
      attention.resolve({
        cases: [staleAttention],
        count: 1,
        queue_counts: { attention: 1, monitoring: 1, history: 0 },
        data_integrity: { source_missing_count: 0 },
      });
      await Promise.resolve();
    });
    await flush();

    expect(host!.textContent).toContain("NEWEST");
    expect(host!.textContent).not.toContain("STALE");
    expect(
      host!.querySelector('[data-queue-view="monitoring"]')?.getAttribute(
        "aria-selected",
      ),
    ).toBe("true");
  });

  it("refreshes a completed command against the currently selected queue", async () => {
    const command = deferred<{ acknowledgement_id: string }>();
    const attention = {
      ...SUMMARY,
      case_id: "case-attention",
      ticker: "ATTENTION",
      queue_bucket: "attention" as const,
    };
    const monitoring = {
      ...MONITORING_UNCONFIRMED,
      case_id: "case-monitoring",
      ticker: "MONITORING",
    };
    apiMocks.acknowledgeSecurityLifecycleCase.mockReturnValue(command.promise);
    apiMocks.listSecurityLifecycleCases.mockImplementation(
      async (request: SecurityLifecycleCaseFilters) => ({
        cases: request.queue_bucket === "monitoring" ? [monitoring] : [attention],
        count: 1,
        queue_counts: { attention: 1, monitoring: 1, history: 0 },
        data_integrity: { source_missing_count: 0 },
      }),
    );

    await mountLifecycle();
    await click("Record insufficient evidence");
    await click("Monitoring", host!);
    expect(host!.textContent).toContain("MONITORING");
    expect(host!.textContent).not.toContain("ATTENTION");

    await act(async () => {
      command.resolve({ acknowledgement_id: "ack-current" });
      await command.promise;
    });
    await flush();

    expect(
      host!.querySelector('[data-queue-view="monitoring"]')?.getAttribute(
        "aria-selected",
      ),
    ).toBe("true");
    expect(host!.textContent).toContain("MONITORING");
    expect(host!.textContent).not.toContain("ATTENTION");
    expect(apiMocks.listSecurityLifecycleCases).toHaveBeenLastCalledWith(
      expect.objectContaining({ queue_bucket: "monitoring" }),
    );
  });

  it("keeps detail bound to the currently selected case when responses resolve out of order", async () => {
    const first = deferred<ReturnType<typeof detail>>();
    const second = deferred<ReturnType<typeof detail>>();
    const firstSummary = {
      ...SUMMARY,
      case_id: "case-first",
      ticker: "FIRST",
    };
    const secondSummary = {
      ...SUMMARY,
      case_id: "case-second",
      ticker: "SECOND",
    };
    apiMocks.listSecurityLifecycleCases.mockResolvedValue({
      cases: [firstSummary, secondSummary],
      count: 2,
      queue_counts: { attention: 2, monitoring: 0, history: 0 },
      data_integrity: { source_missing_count: 0 },
    });
    apiMocks.getSecurityLifecycleCase.mockImplementation((caseId: string) => (
      caseId === "case-first" ? first.promise : second.promise
    ));

    await mountLifecycle(null);
    const triggers = Array.from(
      host!.querySelectorAll<HTMLButtonElement>(".lifecycle-case-trigger"),
    );
    await act(async () => triggers[0].click());
    await flush();
    await act(async () => triggers[1].click());
    await flush();

    await act(async () => {
      second.resolve(detail({
        case_id: "case-second",
        ticker: "SECOND",
        issuer_name: "Second Issuer",
      }));
      await second.promise;
    });
    await flush();
    expect(document.body.querySelector('[role="dialog"]')?.textContent).toContain(
      "SECOND",
    );

    await act(async () => {
      first.resolve(detail({
        case_id: "case-first",
        ticker: "FIRST",
        issuer_name: "First Issuer",
      }));
      await first.promise;
    });
    await flush();

    const drawer = document.body.querySelector('[role="dialog"]');
    expect(drawer?.textContent).toContain("SECOND");
    expect(drawer?.textContent).not.toContain("FIRST");
  });

  it("keeps the newly selected case detail after a pending case command completes", async () => {
    const command = deferred<{ acknowledgement_id: string }>();
    const staleCaseRefresh = deferred<ReturnType<typeof detail>>();
    const initialNextCaseDetail = deferred<ReturnType<typeof detail>>();
    const refreshedNextCaseDetail = deferred<ReturnType<typeof detail>>();
    const currentCase = {
      ...SUMMARY,
      case_id: "case-current-command",
      ticker: "CURRENT",
    };
    const nextCase = {
      ...SUMMARY,
      case_id: "case-next-command",
      ticker: "NEXT",
    };
    let currentCaseReads = 0;
    let nextCaseReads = 0;
    apiMocks.listSecurityLifecycleCases.mockResolvedValue({
      cases: [currentCase, nextCase],
      count: 2,
      queue_counts: { attention: 2, monitoring: 0, history: 0 },
      data_integrity: { source_missing_count: 0 },
    });
    apiMocks.getSecurityLifecycleCase.mockImplementation((caseId: string) => {
      if (caseId === currentCase.case_id) {
        currentCaseReads += 1;
        return currentCaseReads === 1
          ? Promise.resolve(detail({ ...currentCase, issuer_name: "Current issuer" }))
          : staleCaseRefresh.promise;
      }
      if (caseId === nextCase.case_id) {
        nextCaseReads += 1;
        return nextCaseReads === 1
          ? initialNextCaseDetail.promise
          : refreshedNextCaseDetail.promise;
      }
      throw new Error(`unexpected case read: ${caseId}`);
    });
    apiMocks.acknowledgeSecurityLifecycleCase.mockReturnValue(command.promise);

    await mountLifecycle(currentCase.case_id);
    await click("Record insufficient evidence");
    const nextCaseTrigger = Array.from(
      host!.querySelectorAll<HTMLButtonElement>(".lifecycle-case-trigger"),
    ).find((button) => button.textContent?.includes("NEXT"));
    if (!nextCaseTrigger) throw new Error("missing next-case trigger");
    await act(async () => nextCaseTrigger.click());
    await flush();

    await act(async () => {
      command.resolve({ acknowledgement_id: "ack-current" });
      await Promise.resolve();
    });
    await flush();
    await act(async () => {
      initialNextCaseDetail.resolve(detail({ ...nextCase, issuer_name: "Next issuer" }));
      staleCaseRefresh.resolve(detail({ ...currentCase, issuer_name: "Current issuer" }));
      refreshedNextCaseDetail.resolve(detail({ ...nextCase, issuer_name: "Next issuer" }));
      await Promise.resolve();
    });
    await flush();

    const drawer = document.body.querySelector('[role="dialog"]');
    expect(drawer?.textContent).toContain("NEXT");
    expect(drawer?.textContent).toContain("Next issuer");
    expect(drawer?.textContent).not.toContain("Current issuer");
  });

  it("keeps the newly selected case detail after a pending activity command completes", async () => {
    const command = deferred<{ activity_id: string; acknowledged_at: string }>();
    const staleCaseRefresh = deferred<ReturnType<typeof detail>>();
    const initialNextCaseDetail = deferred<ReturnType<typeof detail>>();
    const refreshedNextCaseDetail = deferred<ReturnType<typeof detail>>();
    const currentCase = {
      ...SUMMARY,
      case_id: "case-current-activity",
      ticker: "CURRENT",
    };
    const nextCase = {
      ...SUMMARY,
      case_id: "case-next-activity",
      ticker: "NEXT",
    };
    let currentCaseReads = 0;
    let nextCaseReads = 0;
    apiMocks.listSecurityLifecycleCases.mockResolvedValue({
      cases: [currentCase, nextCase],
      count: 2,
      queue_counts: { attention: 2, monitoring: 0, history: 0 },
      data_integrity: { source_missing_count: 0 },
    });
    apiMocks.listTickerIdentityTransitionActivity.mockResolvedValue({
      items: [{
        activity_id: "activity-pending",
        transition_id: "transition-pending",
        case_id: currentCase.case_id,
        activity_type: "reversed",
        source_ticker: "CURRENT",
        successor_ticker: "NEXT",
        effective_date: "2026-08-27",
        user_owned_changes: [],
        provider_owned_retained: [],
        state_sha256: "1".repeat(64),
        rule_id: "lifecycle.simple_symbol_continuation",
        rule_version: "1",
        decision_provenance_sha256: "2".repeat(64),
        occurred_at: "2026-08-27T12:00:00Z",
        acknowledged_at: null,
        created_at: "2026-08-27T12:00:00Z",
      }],
      count: 1,
      unacknowledged_count: 1,
    });
    apiMocks.getSecurityLifecycleCase.mockImplementation((caseId: string) => {
      if (caseId === currentCase.case_id) {
        currentCaseReads += 1;
        return currentCaseReads === 1
          ? Promise.resolve(detail({ ...currentCase, issuer_name: "Current issuer" }))
          : staleCaseRefresh.promise;
      }
      if (caseId === nextCase.case_id) {
        nextCaseReads += 1;
        return nextCaseReads === 1
          ? initialNextCaseDetail.promise
          : refreshedNextCaseDetail.promise;
      }
      throw new Error(`unexpected case read: ${caseId}`);
    });
    apiMocks.acknowledgeTickerIdentityTransitionActivity.mockReturnValue(command.promise);

    await mountLifecycle(currentCase.case_id);
    await click("Acknowledge");
    const nextCaseTrigger = Array.from(
      host!.querySelectorAll<HTMLButtonElement>(".lifecycle-case-trigger"),
    ).find((button) => button.textContent?.includes("NEXT"));
    if (!nextCaseTrigger) throw new Error("missing next-case trigger");
    await act(async () => nextCaseTrigger.click());
    await flush();

    await act(async () => {
      command.resolve({
        activity_id: "activity-pending",
        acknowledged_at: "2026-08-27T12:01:00Z",
      });
      await Promise.resolve();
    });
    await flush();
    await act(async () => {
      initialNextCaseDetail.resolve(detail({ ...nextCase, issuer_name: "Next issuer" }));
      staleCaseRefresh.resolve(detail({ ...currentCase, issuer_name: "Current issuer" }));
      refreshedNextCaseDetail.resolve(detail({ ...nextCase, issuer_name: "Next issuer" }));
      await Promise.resolve();
    });
    await flush();

    const drawer = document.body.querySelector('[role="dialog"]');
    expect(drawer?.textContent).toContain("NEXT");
    expect(drawer?.textContent).toContain("Next issuer");
    expect(drawer?.textContent).not.toContain("Current issuer");
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

  it("renders automation conclusions from structured bilingual copy", async () => {
    const assessment = {
      ...AUTOMATION_DRAFT,
      status: "accepted",
      rule_id: "lifecycle.no_identity_change",
      conclusion: "Stored English automation conclusion must stay out of the view.",
      impact_summary: "Stored English automation impact must stay out of the view.",
      successor_ticker: null,
      destination_venue: null,
      effective_date: null,
      counterparty_name: null,
      counterparty_ticker: null,
      counterparty_cik: null,
      consideration_currency: null,
      cash_per_security_decimal: null,
      exchange_ratio_decimal: null,
    };
    apiMocks.getSecurityLifecycleCase.mockResolvedValue(detail({
      current_assessment: assessment,
      assessment_history: [assessment],
    }));
    await act(async () => { await i18n.changeLanguage("zh-Hant"); });
    await mountLifecycle();

    expect(document.body.textContent).toContain(
      "未發現 QBTS 的追蹤證券身分有變更。",
    );
    expect(document.body.textContent).not.toContain(assessment.conclusion);
    expect(document.body.textContent).not.toContain(assessment.impact_summary);
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

  it("keeps original evidence authoritative when machine translation fails", async () => {
    const { ApiError } = await import("../api");
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
    apiMocks.translateSecurityLifecycleEvidence.mockRejectedValue(new ApiError(
      "private provider failure",
      "/security-lifecycle/evidence/evidence-market/translations",
      502,
      "translation_auth_rejected",
      null,
      {
        provider: "anthropic",
        model: "claude-sonnet-5",
        harness: "claude_subscription_structured_output",
        retryable: false,
      },
    ));
    const onNavigate = vi.fn();

    await mountLifecycle(CASE_ID, onNavigate);
    expect(document.body.textContent).toContain(PROVIDER_EVIDENCE);
    expect(document.body.textContent).toContain("Machine translation");
    expect(document.body.textContent).toContain(secondExcerpt);
    const translatedEvidence = document.body.querySelector("details.lifecycle-evidence-item");
    expect(translatedEvidence?.querySelector(".lifecycle-derived-translation")).toBeNull();

    await click("Translate evidence");
    expect(apiMocks.translateSecurityLifecycleEvidence).toHaveBeenCalledWith(
      "evidence-market",
      "en",
      LIFECYCLE_RUNTIME,
    );
    expect(document.body.textContent).toContain(secondExcerpt);
    expect(document.body.textContent).toContain("Anthropic · claude-sonnet-5");
    expect(document.body.textContent).toContain(
      "Content translation authentication was rejected. Sign in again or adjust Content Translation settings.",
    );
    const settings = document.body.querySelector<HTMLButtonElement>(
      "[data-action='open-content-translation-settings']",
    );
    expect(settings).not.toBeNull();
    await act(async () => settings!.click());
    expect(onNavigate).toHaveBeenCalledWith({
      kind: "settings_section",
      section: "models",
    });
    expect(document.body.textContent).not.toContain("private provider failure");
  });

  it("collapses evidence and switches between source text and LLM translation", async () => {
    await mountLifecycle();

    const evidence = document.body.querySelector<HTMLDetailsElement>(
      "details.lifecycle-evidence-item",
    );
    expect(evidence).not.toBeNull();
    expect(evidence!.open).toBe(false);
    expect(evidence!.querySelector("summary")?.textContent).toContain("Regulatory filing");
    const body = evidence!.querySelector<HTMLElement>("[data-evidence-mode]");
    expect(body?.dataset.evidenceMode).toBe("original");
    expect(body?.textContent).toContain(PROVIDER_EVIDENCE);
    expect(body?.querySelector(".lifecycle-derived-translation")).toBeNull();

    await click("Machine translation", evidence!);
    const translated = evidence!.querySelector<HTMLElement>("[data-evidence-mode]");
    expect(translated?.dataset.evidenceMode).toBe("translation");
    expect(translated?.querySelector(".lifecycle-provider-evidence")).toBeNull();
    expect(translated?.textContent).toContain("SEC source: Units of Beneficial Interest");
    expect(translated?.textContent).toContain("openai · gpt-5 · responses-api");
  });

  it("summarizes the current decision and marks deterministic automation as non-LLM", async () => {
    apiMocks.getSecurityLifecycleCase.mockResolvedValue(detail({
      current_assessment: { ...AUTOMATION_DRAFT, rule_id: "lifecycle.ma_review" },
      assessment_history: [{ ...AUTOMATION_DRAFT, rule_id: "lifecycle.ma_review" }],
    }));

    await mountLifecycle();

    const summary = document.body.querySelector<HTMLElement>(
      "[data-testid='lifecycle-decision-summary']",
    );
    expect(summary?.textContent).toContain("The transaction involving QBTS still requires review.");
    expect(summary?.textContent).toContain("Deterministic rule (not LLM)");
    const audit = document.body.querySelector<HTMLDetailsElement>(
      "details.lifecycle-audit-details",
    );
    expect(audit).not.toBeNull();
    expect(audit!.open).toBe(false);
    expect(audit!.querySelector("summary")?.textContent).toBe("Audit details");
  });

  it("keeps retry available for a retryable translation failure", async () => {
    const { ApiError } = await import("../api");
    apiMocks.getSecurityLifecycleCase.mockResolvedValue(detail({
      evidence: [{
        ...detail().evidence[0],
        translations: [],
      }],
    }));
    apiMocks.translateSecurityLifecycleEvidence.mockRejectedValue(new ApiError(
      "private provider failure",
      "/security-lifecycle/evidence/evidence-sec/translations",
      502,
      "translation_timeout",
      null,
      {
        provider: "openai",
        model: "gpt-5.4-mini",
        harness: "chatgpt_subscription_structured_output",
        retryable: true,
      },
    ));

    await mountLifecycle();
    await click("Translate evidence");
    expect(document.body.textContent).toContain("OpenAI · gpt-5.4-mini");
    expect(document.body.textContent).toContain("Translation timed out. Try again.");
    await click("Retry translation");
    expect(apiMocks.translateSecurityLifecycleEvidence).toHaveBeenCalledTimes(2);
  });

  it("provides reviewed bilingual presentation for every closed translation failure", async () => {
    const { translationFailurePresentation } = await import("./LifecycleView");
    const cases = [
      ["translation_route_unavailable", "The content translation route is unavailable.", "目前無法解析內容翻譯路由。", "settings"],
      ["translation_credential_missing", "No credential is configured for content translation.", "尚未設定內容翻譯所需憑證。", "settings"],
      ["translation_auth_rejected", "Content translation authentication was rejected. Sign in again or adjust Content Translation settings.", "內容翻譯認證遭拒，請重新登入或調整內容翻譯設定。", "settings"],
      ["translation_rate_limited", "Content translation is temporarily rate limited. Try again later.", "內容翻譯目前受到速率限制，請稍後重試。", "retry"],
      ["translation_quota_exhausted", "The selected content translation account has no remaining quota.", "所選內容翻譯帳戶的可用額度已用盡。", "settings"],
      ["translation_model_unavailable", "The selected content translation model is unavailable.", "目前無法使用所選內容翻譯模型。", "settings"],
      ["translation_timeout", "Translation timed out. Try again.", "翻譯逾時，請重試。", "retry"],
      ["translation_output_invalid", "The model returned an invalid translation output. Try again.", "模型回傳的翻譯格式無效，請重試。", "retry"],
      ["translation_provider_error", "The translation service could not complete the request. Try again.", "翻譯服務暫時無法完成要求，請重試。", "retry"],
      ["evidence_changed", "The source evidence changed. Refresh the case before translating again.", "來源證據已變更，請重新整理案件後再翻譯。", null],
    ] as const;

    for (const locale of ["en", "zh-Hant"] as const) {
      const t = i18n.getFixedT(locale, "explore");
      for (const [code, english, traditionalChinese, action] of cases) {
        expect(translationFailurePresentation(code, t)).toEqual({
          message: locale === "en" ? english : traditionalChinese,
          action,
        });
      }
    }
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
