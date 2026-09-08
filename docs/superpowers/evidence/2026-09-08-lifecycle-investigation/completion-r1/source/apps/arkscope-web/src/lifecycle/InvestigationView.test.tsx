/** @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { beforeEach, afterEach, it, expect, vi } from "vitest";
import i18n from "i18next";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { LifecycleView } from "./InvestigationView";
import { webRunFixture } from "./webFixtures";
const mocks = vi.hoisted(() => ({ getInvestigationTargets: vi.fn(), getInvestigationPreflight: vi.fn(), latestInvestigation: vi.fn(),
  startInvestigation: vi.fn(), getInvestigation: vi.fn(), cancelInvestigation: vi.fn(), listCurrentLifecycleReviews: vi.fn(),
  getInvestigationProviders: vi.fn(), checkInvestigationProviders: vi.fn(), getInvestigationActions: vi.fn(), cancelTickerIdentityTransition: vi.fn(),
  listTickerIdentityTransitionActivity: vi.fn(), getInvestigationReview: vi.fn(), confirmInvestigation: vi.fn(),
  prepareInvestigationProviders: vi.fn(), confirmLifecycleReview: vi.fn(),
  reverseTickerIdentityTransition: vi.fn(), acknowledgeTickerIdentityTransitionActivity: vi.fn() }));
vi.mock("../api", async original => ({ ...await original<typeof import("../api")>(), ...mocks }));
let root: Root, host: HTMLDivElement;
const target = { ticker: "TA", issuer_name: "TravelCenters of America Inc.", security_class: "common stock", venue: "NASDAQ", issuer_cik: null,
  composite_figi: null, identity_status: "needs_lookup", as_of: "2026-09-08" };
const execution = { provider: "anthropic", auth_mode: "claude_code_oauth", model: "claude-sonnet-5", effort: "high" };
const reviewFixture = JSON.parse(readFileSync(resolve(import.meta.dirname, "../../../../tests/fixtures/lifecycle_current_v1.json"), "utf8"));
beforeEach(async () => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true); vi.clearAllMocks();
  mocks.getInvestigationTargets.mockResolvedValue([{ ticker: "TA" }, { ticker: "SMCI" }]);
  mocks.getInvestigationPreflight.mockResolvedValue({ available: true, ticker: "TA", target, execution, reason: null, preflight_sha256: "a".repeat(64),
    credential_label: "Subscription", limits: { model_submissions: 24, web_actions: 24, source_reads: 32, search_enforcement: "enforced" } });
  mocks.latestInvestigation.mockResolvedValue(null);
  mocks.startInvestigation.mockResolvedValue({ run_id: "li_new", created: true });
  mocks.getInvestigation.mockResolvedValue({ run_id: "li_new", ticker: "TA", status: "running", phase: "local_search", execution, target,
    cancel_requested: false, stats: { model_submissions: 0, web_actions: 0, sources: 0, http_requests: 0, source_reads: 0,
      local_queries: 1, retained_source_bytes: 0, elapsed_seconds: 0, input_tokens: null, output_tokens: null }, finding: null, passages: [], gaps: [], steps: [], block_reasons: [] });
  mocks.listTickerIdentityTransitionActivity.mockResolvedValue({ items: [] });
  mocks.getInvestigationProviders.mockResolvedValue({ ticker: "TA", decision: null, observations: { observed_at: null, listings: [], gaps: [] } });
  mocks.checkInvestigationProviders.mockResolvedValue({ ticker: "TA", decision: null, observations: { observed_at: "2026-09-08T01:00:00Z", listings: [], gaps: [] } });
  mocks.getInvestigationActions.mockResolvedValue([]);
  host = document.createElement("div"); document.body.append(host); root = createRoot(host); await i18n.changeLanguage("en");
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.unstubAllGlobals(); });
function button(label: string) { const b = [...document.querySelectorAll<HTMLButtonElement>("button")].find(b => (b.getAttribute("aria-label") || b.textContent) === label); expect(b, label).toBeTruthy(); return b!; }
it("opens by ticker without legacy cases or provider calls and keeps start behind consent", async () => {
  await act(async () => root.render(<LifecycleView initialTicker="TA" />));
  expect(host.textContent).toContain("TravelCenters of America");
  expect(mocks.listCurrentLifecycleReviews).not.toHaveBeenCalled();
  expect(mocks.startInvestigation).not.toHaveBeenCalled();
  await act(async () => button("Investigate").click());
  expect(document.querySelector('[role="dialog"]')?.textContent).toContain("No model or billing fallback");
  expect(mocks.startInvestigation).not.toHaveBeenCalled();
  await act(async () => document.querySelector<HTMLButtonElement>(".ui-confirm-dialog button:last-child")!.click());
  expect(mocks.startInvestigation).toHaveBeenCalledOnce();
  expect(host.textContent).toContain("Searching local news");
  expect(button("Stop").disabled).toBe(false);
});
it("shows unavailable setup with an exit to Settings without launching", async () => {
  const navigate = vi.fn();
  mocks.getInvestigationPreflight.mockResolvedValue({ available: false, ticker: "TA", reason: "selected_credential_unavailable", target: null, execution: null, limits: null });
  await act(async () => root.render(<LifecycleView initialTicker="TA" onNavigate={navigate} />));
  expect(button("Investigate").disabled).toBe(true);
  await act(async () => button("Investigation settings").click());
  expect(navigate).toHaveBeenCalledWith({ kind: "settings_section", section: "models" });
  expect(mocks.startInvestigation).not.toHaveBeenCalled();
});
it("provider checking is separately confirmed and never launches an LLM", async () => {
  await act(async () => root.render(<LifecycleView initialTicker="TA" />));
  expect(mocks.checkInvestigationProviders).not.toHaveBeenCalled();
  await act(async () => button("Check sources").click());
  expect(document.querySelector('[role="dialog"]')?.textContent).toContain("Up to 5 Massive");
  expect(mocks.checkInvestigationProviders).not.toHaveBeenCalled();
  await act(async () => document.querySelector<HTMLButtonElement>(".ui-confirm-dialog button:last-child")!.click());
  expect(mocks.checkInvestigationProviders).toHaveBeenCalledExactlyOnceWith("TA");
  expect(mocks.startInvestigation).not.toHaveBeenCalled();
});
it("scheduled actions can be cancelled without reading any old cases", async () => {
  mocks.getInvestigationActions.mockResolvedValue([{ transition_id: "slt_pending", source_ticker: "TA", successor_ticker: null,
    kind: "terminal_delisting", state: "scheduled", execute_on: "2026-09-10", approved_preview_sha256: "a".repeat(64) }]);
  await act(async () => root.render(<LifecycleView />));
  expect(host.textContent).toContain("Scheduled, not applied");
  await act(async () => button("Cancel confirmed action").click());
  expect(mocks.cancelTickerIdentityTransition).not.toHaveBeenCalled();
  await act(async () => document.querySelector<HTMLButtonElement>(".ui-confirm-dialog button:last-child")!.click());
  expect(mocks.cancelTickerIdentityTransition).toHaveBeenCalledExactlyOnceWith("slt_pending");
  expect(mocks.listCurrentLifecycleReviews).not.toHaveBeenCalled();
});

async function openReview(sourceGaps: { url: string; reason: string }[] = []) {
  mocks.latestInvestigation.mockResolvedValue({ ...(await mocks.getInvestigation()), status: "succeeded", phase: "finished",
    action: "terminal_delisting", finding: { ...webRunFixture.finding, source_ticker: "TA", limitations: [] } });
  const packet = { ...reviewFixture.packet, source_ticker: "TA", source_gaps: sourceGaps };
  mocks.getInvestigationReview.mockResolvedValue(packet);
  mocks.confirmInvestigation.mockResolvedValue({ ...reviewFixture.confirmation, source_ticker: "TA" });
  await act(async () => root.render(<LifecycleView initialTicker="TA" />));
  await act(async () => button("Review removal").click());
  return packet;
}

it("shows the localized action instead of internal assessment prose in confirmation", async () => {
  await openReview();
  const review = host.querySelector(".investigation-review")!;
  expect(review.textContent).toContain("Old listing inactive");
  expect(review.textContent).not.toContain(reviewFixture.packet.finding.conclusion);
  expect(button("Confirm and apply").disabled).toBe(false);
});

it("requires explicit source-gap acknowledgement before confirmation", async () => {
  const packet = await openReview([{ url: "https://issuer.example/unavailable", reason: "source_timeout" }]);
  expect(button("Confirm and apply").disabled).toBe(true);
  await act(async () => button("Confirm and apply").click());
  expect(document.querySelector('[role="dialog"]')).toBeNull();
  expect(mocks.confirmInvestigation).not.toHaveBeenCalled();
  const acknowledge = host.querySelector<HTMLInputElement>('.investigation-review aside input[type="checkbox"]')!;
  expect(acknowledge.checked).toBe(false);
  await act(async () => acknowledge.click());
  expect(button("Confirm and apply").disabled).toBe(false);
  await act(async () => button("Confirm and apply").click());
  expect(mocks.confirmInvestigation).not.toHaveBeenCalled();
  await act(async () => document.querySelector<HTMLButtonElement>(".ui-confirm-dialog button:last-child")!.click());
  expect(mocks.confirmInvestigation).toHaveBeenCalledExactlyOnceWith("li_new", packet, true);
});

it("requires a refreshed preview after changing the execution date", async () => {
  const packet = await openReview();
  expect(button("Confirm and apply").disabled).toBe(false);
  const date = host.querySelector<HTMLInputElement>('.investigation-review input[type="date"]')!;
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(date, "2026-09-08");
    date.dispatchEvent(new Event("input", { bubbles: true }));
    date.dispatchEvent(new Event("change", { bubbles: true }));
  });
  expect(button("Confirm and apply").disabled).toBe(true);
  await act(async () => button("Confirm and apply").click());
  expect(mocks.confirmInvestigation).not.toHaveBeenCalled();
  const refreshed = { ...packet, packet_sha256: "d".repeat(64), execute_on: "2026-09-08",
    options: { ...packet.options, execute_on: "2026-09-08" } };
  mocks.getInvestigationReview.mockResolvedValue(refreshed);
  await act(async () => button("Update preview").click());
  expect(mocks.getInvestigationReview).toHaveBeenLastCalledWith("li_new", expect.objectContaining({ execute_on: "2026-09-08" }));
  expect(button("Confirm and apply").disabled).toBe(false);
  await act(async () => button("Confirm and apply").click());
  await act(async () => document.querySelector<HTMLButtonElement>(".ui-confirm-dialog button:last-child")!.click());
  expect(mocks.confirmInvestigation).toHaveBeenCalledExactlyOnceWith("li_new", refreshed, false);
});

it("can review provider evidence with no LLM credential and only applies after separate confirmation", async () => {
  mocks.getInvestigationPreflight.mockResolvedValue({ available: false, ticker: "TA", reason: "selected_credential_unavailable", target, execution: null, limits: null });
  const packet = { ...reviewFixture.packet, source_ticker: "TA", source_gaps: [] };
  const digest = "b".repeat(64);
  mocks.getInvestigationProviders.mockResolvedValue({ ticker: "TA", observations: { observed_at: "2026-09-08T01:00:00Z", listings: [], gaps: [] },
    decision: { listing_state: "inactive", continuation_state: "unavailable", listing_end_date: "2023-05-15", successor_ticker: null,
      candidate_tickers: [], action: "terminal_delisting", check_sha256: digest } });
  mocks.prepareInvestigationProviders.mockResolvedValue(packet);
  mocks.confirmLifecycleReview.mockResolvedValue({ ...reviewFixture.confirmation, source_ticker: "TA" });
  await act(async () => root.render(<LifecycleView initialTicker="TA" />));
  expect(button("Investigate").disabled).toBe(true);
  expect(button("Review removal").disabled).toBe(false);
  await act(async () => button("Review removal").click());
  expect(mocks.prepareInvestigationProviders).toHaveBeenCalledExactlyOnceWith("TA", digest, {});
  expect(mocks.confirmLifecycleReview).not.toHaveBeenCalled();
  expect(mocks.startInvestigation).not.toHaveBeenCalled();
  expect(mocks.checkInvestigationProviders).not.toHaveBeenCalled();
  await act(async () => button("Confirm and apply").click());
  expect(mocks.confirmLifecycleReview).not.toHaveBeenCalled();
  await act(async () => document.querySelector<HTMLButtonElement>(".ui-confirm-dialog button:last-child")!.click());
  expect(mocks.confirmLifecycleReview).toHaveBeenCalledExactlyOnceWith(packet);
  expect(mocks.confirmInvestigation).not.toHaveBeenCalled();
});

it("confirms reversal separately and refreshes the tracked targets without launching an investigation", async () => {
  mocks.getInvestigationTargets.mockResolvedValue([{ ticker: "SMCI" }]);
  const item = { ...reviewFixture.activity.items[0], source_ticker: "TA", reverse_readiness: { reversible: true, block_reasons: [] } };
  mocks.listTickerIdentityTransitionActivity.mockResolvedValue({ items: [item] });
  mocks.reverseTickerIdentityTransition.mockImplementation(async () => {
    mocks.getInvestigationTargets.mockResolvedValue([{ ticker: "TA" }, { ticker: "SMCI" }]);
    mocks.listTickerIdentityTransitionActivity.mockResolvedValue({ items: [{ ...item, reverse_readiness: { reversible: false, block_reasons: [] } }] });
    return { status: "reversed" };
  });
  await act(async () => root.render(<LifecycleView />));
  const history = host.querySelector<HTMLDetailsElement>(".investigation-history")!;
  await act(async () => { history.open = true; history.dispatchEvent(new Event("toggle")); });
  await act(async () => button("Reverse tracking change").click());
  expect(mocks.reverseTickerIdentityTransition).not.toHaveBeenCalled();
  expect(document.querySelector('[role="dialog"]')?.textContent).toContain("no intervening changes conflict");
  await act(async () => document.querySelector<HTMLButtonElement>(".ui-confirm-dialog button:last-child")!.click());
  expect(mocks.reverseTickerIdentityTransition).toHaveBeenCalledExactlyOnceWith(item.transition_id);
  expect([...host.querySelectorAll(".investigation-targets option")].map(row => row.textContent)).toContain("TA");
  expect(mocks.startInvestigation).not.toHaveBeenCalled();
  expect(mocks.checkInvestigationProviders).not.toHaveBeenCalled();
});

it("refreshes a reversal refused after a concurrent edit instead of leaving the stale action enabled", async () => {
  const item = { ...reviewFixture.activity.items[0], reverse_readiness: { reversible: true, block_reasons: [] } };
  mocks.listTickerIdentityTransitionActivity.mockResolvedValue({ items: [item] });
  mocks.reverseTickerIdentityTransition.mockImplementation(async () => {
    mocks.listTickerIdentityTransitionActivity.mockResolvedValue({ items: [{ ...item,
      reverse_readiness: { reversible: false, block_reasons: ["reverse_state_changed"] } }] });
    return { status: "blocked" };
  });
  await act(async () => root.render(<LifecycleView />));
  const history = host.querySelector<HTMLDetailsElement>(".investigation-history")!;
  await act(async () => { history.open = true; history.dispatchEvent(new Event("toggle")); });
  await act(async () => button("Reverse tracking change").click());
  await act(async () => document.querySelector<HTMLButtonElement>(".ui-confirm-dialog button:last-child")!.click());
  expect([...host.querySelectorAll("button")].some(row => row.textContent === "Reverse tracking change")).toBe(false);
  expect(host.querySelector('[role="alert"]')).not.toBeNull();
  expect(mocks.getInvestigationTargets).toHaveBeenCalledTimes(1);
  expect(mocks.startInvestigation).not.toHaveBeenCalled();
});

it("keeps a removed target readable without offering another provider removal", async () => {
  mocks.getInvestigationTargets.mockResolvedValue([{ ticker: "SMCI" }]);
  mocks.getInvestigationPreflight.mockResolvedValue({ available: false, ticker: "TA", reason: "target_not_tracked", target, execution: null, limits: null });
  mocks.getInvestigationProviders.mockResolvedValue({ ticker: "TA", observations: { observed_at: "2026-09-08T01:00:00Z", listings: [], gaps: [] },
    decision: { listing_state: "inactive", continuation_state: "unavailable", listing_end_date: "2023-05-15", successor_ticker: null,
      candidate_tickers: [], action: "terminal_delisting", check_sha256: "b".repeat(64) } });
  await act(async () => root.render(<LifecycleView initialTicker="TA" />));
  expect(host.textContent).toContain("Old listing inactive");
  expect(button("Review removal").disabled).toBe(true);
  await act(async () => button("Review removal").click());
  expect(mocks.prepareInvestigationProviders).not.toHaveBeenCalled();
});
