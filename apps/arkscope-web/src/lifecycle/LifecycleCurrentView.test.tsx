/** @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import i18n from "i18next";
// Legacy retained-action screen contracts; the product entry is owned by InvestigationView.test.
import { LifecycleView } from "./CurrentLifecycleView";

const mocks = vi.hoisted(() => ({
  listCurrentLifecycleReviews: vi.fn(), getCurrentLifecycleReview: vi.fn(), getLifecycleReviewPacket: vi.fn(), confirmLifecycleReview: vi.fn(),
  getSecurityLifecycleCaseAudit: vi.fn(), runSecurityLifecycleCaseAutomation: vi.fn(), getSecurityLifecycleAutomationStatus: vi.fn(),
  cancelTickerIdentityTransition: vi.fn(), retryTickerIdentityTransition: vi.fn(), reverseTickerIdentityTransition: vi.fn(),
  translateSecurityLifecycleEvidence: vi.fn(), listTickerIdentityTransitionActivity: vi.fn(), acknowledgeTickerIdentityTransitionActivity: vi.fn(),
}));
vi.mock("../api", async (original) => ({ ...await original<typeof import("../api")>(), ...mocks }));
const fixture = JSON.parse(readFileSync(resolve(import.meta.dirname, "../../../../tests/fixtures/lifecycle_current_v1.json"), "utf8"));
const row = fixture.attention.items[0];
const status = { config_status: "valid", config: { enabled: false, interval_minutes: 5, batch_limit: 2, apply_profile_transitions: false },
  schedule: { status: "disabled", last_attempt_at: null, next_scheduled_at: null }, telemetry_status: "absent", last_status: null,
  last_result: null, active_incident: null, latest_failed_runs: [], current_progress: [] };
let root: Root, container: HTMLDivElement;
beforeEach(async () => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  vi.clearAllMocks();
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network_forbidden")));
  mocks.listCurrentLifecycleReviews.mockImplementation(async ({ view = "attention" } = {}) => view === "history"
    ? { ...fixture.attention, items: [], page: { offset: 0, limit: 50, total: 0 } } : structuredClone(fixture.attention));
  mocks.getCurrentLifecycleReview.mockResolvedValue({ version: 1, as_of: fixture.attention.as_of, item: row });
  mocks.getLifecycleReviewPacket.mockResolvedValue(fixture.packet);
  mocks.confirmLifecycleReview.mockResolvedValue(fixture.confirmation);
  mocks.getSecurityLifecycleAutomationStatus.mockResolvedValue(status);
  mocks.listTickerIdentityTransitionActivity.mockResolvedValue({ items: [], count: 0, unacknowledged_count: 0 });
  mocks.getSecurityLifecycleCaseAudit.mockResolvedValue({ case_id: row.case_ids[0], observation_fingerprint_sha256: null,
    evidence: [], assessment_history: [], automation_runs: [], automation_facts: [], investigation_runs: [], acknowledgement_history: [], truncation: {} });
  container = document.createElement("div"); document.body.append(container); root = createRoot(container);
  await i18n.changeLanguage("en");
});
afterEach(async () => { await act(async () => root.unmount()); container.remove(); vi.useRealTimers(); vi.unstubAllGlobals(); });
async function render(locale = "en", initialCaseId: string | null = null) { await act(async () => { await i18n.changeLanguage(locale); root.render(<LifecycleView initialCaseId={initialCaseId} />); }); }
function button(name: string) { const found = [...document.querySelectorAll<HTMLButtonElement>("button")].find((b) => (b.getAttribute("aria-label") ?? b.textContent?.trim()) === name); expect(found, name).toBeTruthy(); return found!; }
async function click(name: string) { await act(async () => button(name).click()); }
async function open() { await click("Review OLD"); }
async function confirmDialog() { await act(async () => document.querySelector<HTMLButtonElement>(".ui-confirm-dialog button:last-child")!.click()); }
async function setInput(input: HTMLInputElement, value: string) {
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(input, value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
  });
}
const activity = { activity_id: "activity-1", transition_id: "slt_applied", case_id: row.case_ids[0], activity_type: "applied",
  source_ticker: "OLD", successor_ticker: null, effective_date: "2026-09-04", user_owned_changes: [], provider_owned_retained: [],
  state_sha256: "a".repeat(64), rule_id: null, rule_version: null, decision_provenance_sha256: "b".repeat(64),
  occurred_at: fixture.attention.as_of, acknowledged_at: null, created_at: fixture.attention.as_of,
  reverse_readiness: { reversible: true, block_reasons: [] } };
async function disclose(name: string) {
  const summary = [...document.querySelectorAll("summary")].find((n) => n.textContent === name); expect(summary).toBeTruthy();
  await act(async () => { const details = summary!.parentElement as HTMLDetailsElement; details.open = true; details.dispatchEvent(new Event("toggle")); });
}

it("shows compact collection truth, outstanding continuation and healthy coverage without spending", async () => {
  await render();
  expect(container.textContent).toContain("Old listing inactive");
  expect(container.textContent).toContain("Collecting");
  expect(container.textContent).toContain("Confirmed active");
  expect(container.textContent).toContain("Not scheduled");
  expect(container.textContent).toContain("Same-security continuation is not confirmed or excluded");
  expect(mocks.runSecurityLifecycleCaseAutomation).not.toHaveBeenCalled();
  expect(mocks.getSecurityLifecycleCaseAudit).not.toHaveBeenCalled();
  expect(mocks.confirmLifecycleReview).not.toHaveBeenCalled();
  expect(document.querySelector("textarea")).toBeNull();
});
it("prepares the action read-only then confirms with one backend command", async () => {
  await render(); await open(); await click("Review removal");
  expect(mocks.getLifecycleReviewPacket).toHaveBeenCalledWith(row.next_action.case_id, row.next_action.assessment_id, {});
  expect(document.body.textContent).toContain("Manual");
  expect(document.body.textContent).toContain("Alpha Picks tracking memberships");
  expect(mocks.confirmLifecycleReview).not.toHaveBeenCalled();
  await click("Confirm and apply");
  expect(document.querySelector('[role="dialog"].ui-confirm-dialog')).not.toBeNull();
  expect(mocks.confirmLifecycleReview).not.toHaveBeenCalled();
  const buttons = [...document.querySelectorAll<HTMLButtonElement>(".ui-confirm-dialog button")];
  await act(async () => buttons.at(-1)!.click());
  expect(mocks.confirmLifecycleReview).toHaveBeenCalledExactlyOnceWith(fixture.packet);
  expect(mocks.getCurrentLifecycleReview.mock.calls.length).toBeGreaterThan(1);
});
it("never offers confirm on a blocked or stale packet", async () => {
  mocks.getLifecycleReviewPacket.mockResolvedValue({ ...fixture.packet, ready: false, block_reasons: ["portfolio_position_open"] });
  await render(); await open(); await click("Review removal");
  expect(button("Confirm and apply").disabled).toBe(true);
  expect(mocks.confirmLifecycleReview).not.toHaveBeenCalled();
});
it("does not replay a command after an unknown response", async () => {
  mocks.confirmLifecycleReview.mockRejectedValue(new Error("timeout"));
  await render(); await open(); await click("Review removal"); await click("Confirm and apply");
  await act(async () => (document.querySelector(".ui-confirm-dialog button:last-child") as HTMLButtonElement).click());
  expect(document.body.textContent).toContain("The command result is not confirmed");
  expect(mocks.confirmLifecycleReview).toHaveBeenCalledTimes(1);
  expect(button("Confirm and apply").disabled).toBe(true);
});
it.each(["scheduled", "blocked", "cancelled", "reversed", "applied_state_changed"])("shows %s as distinct from a successful application", async (state) => {
  const item = { ...row, next_action: { ...row.next_action, state, kind: state === "scheduled" ? "none" : "recheck", transition_id: "slt_fixture", execute_on: "2026-09-10" } };
  mocks.listCurrentLifecycleReviews.mockResolvedValue({ ...fixture.attention, items: [item] });
  mocks.getCurrentLifecycleReview.mockResolvedValue({ version: 1, as_of: fixture.attention.as_of, item });
  await render(); await open();
  expect(document.body.textContent).not.toContain("Applied and checked");
  expect(mocks.confirmLifecycleReview).not.toHaveBeenCalled();
});
it("keeps completed removal with unresolved continuation in attention", async () => {
  mocks.listCurrentLifecycleReviews.mockResolvedValue(fixture.applied);
  await render();
  expect(container.textContent).toContain("Not collecting");
  expect(container.textContent).toContain("successor relationship remains unresolved");
});
it("requires explicit provider confirmation before rechecking sources", async () => {
  const item = { ...row, next_action: { ...row.next_action, kind: "recheck", assessment_id: null } };
  mocks.getCurrentLifecycleReview.mockResolvedValue({ version: 1, as_of: fixture.attention.as_of, item });
  mocks.runSecurityLifecycleCaseAutomation.mockResolvedValue({ status: "unavailable", scope: "case", reason: "provider_scan_budget_unavailable" });
  await render(); await open(); await click("Check sources");
  expect(document.body.textContent).toContain("explicitly requests provider data");
  expect(mocks.runSecurityLifecycleCaseAutomation).not.toHaveBeenCalled();
  await act(async () => (document.querySelector(".ui-confirm-dialog button:last-child") as HTMLButtonElement).click());
  expect(mocks.runSecurityLifecycleCaseAutomation).toHaveBeenCalledExactlyOnceWith(row.next_action.case_id);
  expect(document.body.textContent).toContain("Source checking is unavailable");
});
it("loads audit only on disclosure and keeps the primary view usable if it fails", async () => {
  mocks.getSecurityLifecycleCaseAudit.mockRejectedValue(new Error("failed"));
  await render(); await open();
  expect(mocks.getSecurityLifecycleCaseAudit).not.toHaveBeenCalled();
  await disclose("Sources and history");
  expect(mocks.getSecurityLifecycleCaseAudit).toHaveBeenCalledTimes(1);
  expect(document.body.textContent).toContain("History could not be loaded");
  expect(button("Review removal").disabled).toBe(false);
});
it("rejects a malformed list as an error instead of claiming no cases", async () => {
  mocks.listCurrentLifecycleReviews.mockRejectedValue(new Error("lifecycle_current_payload_invalid"));
  await render();
  expect(container.textContent).toContain("Current tracking status could not be read");
  expect(container.textContent).not.toContain("No reviews in this view");
});
it("keeps only the newest queue response", async () => {
  let resolve!: (value: unknown) => void;
  mocks.listCurrentLifecycleReviews.mockImplementationOnce(() => new Promise((done) => { resolve = done; }));
  await render(); await click("History");
  await act(async () => resolve(fixture.attention));
  expect(container.textContent).not.toContain("Old listing inactive");
});
it("keeps only the selected detail response", async () => {
  let resolve!: (value: unknown) => void;
  const second = { ...row, review_id: "slpr_second", ticker: "NEW", source_checks: row.source_checks.map((source: object) => ({ ...source, ticker: "NEW" })) };
  mocks.listCurrentLifecycleReviews.mockResolvedValue({ ...fixture.attention, items: [row, second], counts: { attention: 2, history: 0 }, page: { offset: 0, limit: 50, total: 2 } });
  mocks.getCurrentLifecycleReview.mockImplementationOnce(() => new Promise((done) => { resolve = done; }))
    .mockResolvedValueOnce({ version: 1, as_of: fixture.attention.as_of, item: second });
  await render(); await open(); await click("Review NEW");
  await act(async () => resolve({ version: 1, as_of: fixture.attention.as_of, item: row }));
  expect(document.querySelector(".lifecycle-drawer-content")?.textContent).toContain("NEW");
  expect(document.querySelector(".lifecycle-drawer-content")?.textContent).not.toContain("OLD");
});
it("renders Traditional Chinese without translating provider evidence", async () => {
  await render("zh-Hant");
  expect(container.textContent).toContain("舊掛牌已失效");
  expect(container.textContent).toContain("收集中");
  expect(container.textContent).not.toContain("Old listing inactive");
});

it("labels successful source checks neutrally and distinguishes both Nasdaq directories", async () => {
  await render(); await open();
  const checks = document.querySelector(".lifecycle-current-checks");
  expect(checks?.textContent).toContain("Dated delisting record");
  expect(checks?.textContent).toContain("Nasdaq-listed symbols");
  expect(checks?.textContent).toContain("Other listed symbols");
  expect(checks?.textContent).not.toContain("is missing");
});
it("resolves a case link outside the first attention page without spending", async () => {
  mocks.listCurrentLifecycleReviews.mockImplementation(async (filters = {}) => filters.case_id === row.case_ids[0]
    ? fixture.attention : { ...fixture.attention, items: [], page: { offset: 0, limit: 50, total: 0 } });
  await render("en", row.case_ids[0]);
  expect(mocks.listCurrentLifecycleReviews).toHaveBeenCalledWith({ case_id: row.case_ids[0] });
  expect(mocks.getCurrentLifecycleReview).toHaveBeenCalledWith(row.review_id);
  expect(document.querySelector(".lifecycle-drawer-content")?.textContent).toContain("OLD");
  expect(mocks.runSecurityLifecycleCaseAutomation).not.toHaveBeenCalled();
});
it("reports an unresolvable case link without inventing an empty review", async () => {
  mocks.listCurrentLifecycleReviews.mockResolvedValue({ ...fixture.attention, items: [], page: { offset: 0, limit: 50, total: 0 } });
  await render("en", "slc_absent");
  expect(document.body.textContent).toContain("This review is no longer available");
  expect(mocks.getCurrentLifecycleReview).not.toHaveBeenCalled();
});
it("clears the old preview lock when switching cases and discards its late result", async () => {
  let release!: (value: unknown) => void;
  const second = { ...row, review_id: "slpr_second", ticker: "NEW", source_checks: [] };
  mocks.listCurrentLifecycleReviews.mockResolvedValue({ ...fixture.attention, items: [row, second], counts: { attention: 2, history: 0 }, page: { offset: 0, limit: 50, total: 2 } });
  mocks.getCurrentLifecycleReview.mockImplementation(async (id) => ({ version: 1, as_of: fixture.attention.as_of, item: id === row.review_id ? row : second }));
  mocks.getLifecycleReviewPacket.mockImplementationOnce(() => new Promise((resolve) => { release = resolve; }));
  await render(); await open(); await click("Review removal"); await click("Review NEW");
  expect(button("Review removal").disabled).toBe(false);
  await act(async () => release(fixture.packet));
  expect(document.querySelector(".lifecycle-drawer-content")?.textContent).not.toContain("Affected lists");
  expect(mocks.confirmLifecycleReview).not.toHaveBeenCalled();
});
it("sends only one confirmation even for two clicks in the same render", async () => {
  let release!: (value: unknown) => void;
  mocks.confirmLifecycleReview.mockImplementation(() => new Promise((resolve) => { release = resolve; }));
  await render(); await open(); await click("Review removal"); await click("Confirm and apply");
  const confirm = document.querySelector<HTMLButtonElement>(".ui-confirm-dialog button:last-child")!;
  await act(async () => { confirm.click(); confirm.click(); });
  expect(mocks.confirmLifecycleReview).toHaveBeenCalledTimes(1);
  await act(async () => release(fixture.confirmation));
});
it("uses the durable transition kind when resuming a symbol change", async () => {
  const item = { ...row, next_action: { ...row.next_action, state: "approved", kind: "resume", transition_kind: "symbol_continuation", transition_id: "slt_rename", preview_sha256: "d".repeat(64) } };
  mocks.getCurrentLifecycleReview.mockResolvedValue({ version: 1, as_of: fixture.attention.as_of, item });
  mocks.retryTickerIdentityTransition.mockResolvedValue({ status: "applied" });
  await render(); await open(); await click("Run confirmed action");
  expect(document.querySelector(".ui-confirm-dialog")?.textContent).toContain("confirmed successor");
  expect(document.querySelector(".ui-confirm-dialog")?.textContent).not.toContain("Stop price");
  await act(async () => document.querySelector<HTMLButtonElement>(".ui-confirm-dialog button:last-child")!.click());
  expect(mocks.retryTickerIdentityTransition).toHaveBeenCalledExactlyOnceWith("slt_rename", { preview_sha256: "d".repeat(64) });
});
it("shows actual running stages, not skipped stages, while preserving active failure visibility", async () => {
  mocks.getSecurityLifecycleAutomationStatus.mockResolvedValue({ ...status, telemetry_status: "valid", last_status: "running",
    active_incident: { case_failures: { slc_other: { run_id: "run_other", recovery: "new_attempt" } }, scheduler_failure: null },
    current_progress: [{ request_id: "request_1", case_id: row.next_action.case_id, trigger: "manual_case", started_at: fixture.attention.as_of,
      current_stage: "evaluate", completed_stages: ["preparing", "sec", "listing"], skipped_stages: ["ibkr"] }] });
  await render();
  const progress = document.querySelector('[data-testid="lifecycle-automation-progress"]');
  expect(progress?.textContent).toContain("Preparing");
  expect(progress?.textContent).toContain("Evaluate");
  expect(progress?.textContent).not.toContain("IBKR");
  expect(document.body.textContent).toContain("The source check failed");
});
it("keeps a regulator-only notice and its source link in the lazy audit without authorizing removal", async () => {
  const item = { ...row, finding: "unresolved", reason: "regulator_event_pending", source_checks: [],
    source_notices: [{ form: "8-K", filed_on: "2026-09-04", text: "An acquisition remains pending.", url: "https://www.sec.gov/Archives/fixture.htm" }],
    next_action: { ...row.next_action, kind: "recheck", assessment_id: null } };
  mocks.getCurrentLifecycleReview.mockResolvedValue({ version: 1, as_of: fixture.attention.as_of, item });
  await render(); await open();
  expect(document.body.textContent).not.toContain("An acquisition remains pending.");
  await disclose("Sources and history");
  expect(document.body.textContent).toContain("An acquisition remains pending.");
  expect(document.querySelector('a[href="https://www.sec.gov/Archives/fixture.htm"]')).not.toBeNull();
  expect(mocks.getLifecycleReviewPacket).not.toHaveBeenCalled();
  expect(mocks.runSecurityLifecycleCaseAutomation).not.toHaveBeenCalled();
});

it("requires a fresh preview after changing a missing date, priority or successor visibility", async () => {
  const packet = { ...fixture.packet, action: "symbol_continuation", ready: false, execute_on: null,
    block_reasons: ["execution_date_required", "priority_resolution_required", "successor_hidden"],
    finding: { ...fixture.packet.finding, successor_ticker: "NEW" },
    effects: { ...fixture.packet.effects, priority: { source_value: "high", successor_value: "low", resolution: null, result_value: null, write_successor: false },
      suppression: { ...fixture.packet.effects.suppression, successor_hidden: true, unhide_successor: false },
      editable_tags_to_copy: [{ facet: "theme", value: "Reviewed tag", source: "user", ticker: "NEW" }],
      legacy_config_seed: { ...fixture.packet.effects.legacy_config_seed, add: [{ source_key: "legacy_config_seed", ticker: "NEW" }] } } };
  mocks.getLifecycleReviewPacket.mockResolvedValueOnce(packet).mockImplementation(async (_case, _assessment, options) => ({ ...packet,
    ready: true, block_reasons: [], execute_on: options.execute_on, options, packet_sha256: "d".repeat(64) }));
  await render(); await open(); await click("Review removal");
  for (const text of ["Manual", "Alpha Picks tracking memberships", "Reviewed tag", "Imported legacy settings", "high", "low"]) {
    expect(document.body.textContent).toContain(text);
  }
  expect(button("Confirm and apply").disabled).toBe(true);
  await setInput(document.querySelector<HTMLInputElement>('input[type="date"]')!, "2026-09-10");
  await act(async () => document.querySelector<HTMLInputElement>('input[type="radio"]')!.click());
  await act(async () => document.querySelector<HTMLInputElement>('.lifecycle-drawer-content input[type="checkbox"]')!.click());
  expect(button("Confirm and apply").disabled).toBe(true);
  expect(mocks.getLifecycleReviewPacket).toHaveBeenCalledTimes(1);
  await click("Update preview");
  expect(mocks.getLifecycleReviewPacket).toHaveBeenLastCalledWith(row.next_action.case_id, row.next_action.assessment_id,
    { execute_on: "2026-09-10", priority_resolution: "source", unhide_successor: true });
  await click("Confirm and apply"); await confirmDialog();
  expect(mocks.confirmLifecycleReview).toHaveBeenCalledWith(expect.objectContaining({ packet_sha256: "d".repeat(64),
    options: { execute_on: "2026-09-10", priority_resolution: "source", unhide_successor: true } }));
});
it("refreshes the currently selected view after a pending command completes", async () => {
  let release!: (value: unknown) => void;
  mocks.confirmLifecycleReview.mockImplementation(() => new Promise((resolve) => { release = resolve; }));
  await render(); await open(); await click("Review removal"); await click("Confirm and apply"); await confirmDialog();
  await click("History");
  await setInput(document.querySelector<HTMLInputElement>('input[type="search"]')!, "NEW");
  await act(async () => release(fixture.confirmation));
  expect(mocks.listCurrentLifecycleReviews).toHaveBeenLastCalledWith({ view: "history", ticker: "NEW", offset: 0, limit: 50 });
  expect(container.textContent).not.toContain("Old listing inactive");
});
it("cancels the exact durable scheduled action only after confirmation", async () => {
  const item = { ...row, next_action: { ...row.next_action, state: "scheduled", kind: "none", transition_id: "slt_scheduled", execute_on: "2026-09-10" } };
  mocks.getCurrentLifecycleReview.mockResolvedValue({ version: 1, as_of: fixture.attention.as_of, item });
  mocks.cancelTickerIdentityTransition.mockResolvedValue({ status: "cancelled", transition_id: "slt_scheduled" });
  await render(); await open(); await click("Cancel confirmed action");
  expect(mocks.cancelTickerIdentityTransition).not.toHaveBeenCalled();
  await confirmDialog();
  expect(mocks.cancelTickerIdentityTransition).toHaveBeenCalledExactlyOnceWith("slt_scheduled");
  expect(mocks.confirmLifecycleReview).not.toHaveBeenCalled();
});
it("reports changed confirmation without displaying success or retrying", async () => {
  mocks.confirmLifecycleReview.mockRejectedValue(Object.assign(new Error("changed"), { code: "transition_preview_changed" }));
  await render(); await open(); await click("Review removal"); await click("Confirm and apply"); await confirmDialog();
  expect(document.body.textContent).toContain("The reviewed material has changed");
  expect(document.body.textContent).not.toContain("Applied and checked");
  expect(button("Confirm and apply").disabled).toBe(true);
  expect(mocks.confirmLifecycleReview).toHaveBeenCalledTimes(1);
});
it("does not reverse an action whose current effects no longer match", async () => {
  const item = { ...fixture.applied.items[0], next_action: { ...fixture.applied.items[0].next_action, can_reverse: false } };
  mocks.getCurrentLifecycleReview.mockResolvedValue({ version: 1, as_of: fixture.attention.as_of, item });
  await render(); await open();
  expect(button("Reverse applied change").disabled).toBe(true);
  expect(mocks.reverseTickerIdentityTransition).not.toHaveBeenCalled();
});
it("reports a blocked global reversal without requiring an open case", async () => {
  mocks.listTickerIdentityTransitionActivity.mockResolvedValue({ items: [activity], count: 1, unacknowledged_count: 1 });
  mocks.reverseTickerIdentityTransition.mockResolvedValue({ status: "blocked", block_reasons: ["successor_has_later_transition"] });
  await render(); await disclose("Tracking changes"); await click("Reverse tracking change"); await confirmDialog();
  expect(mocks.reverseTickerIdentityTransition).toHaveBeenCalledExactlyOnceWith("slt_applied");
  expect(document.body.textContent).toContain("A later ticker transition exists");
  expect(document.body.textContent).not.toContain("The command result is not confirmed");
});
it("acknowledges activity at most once and preserves other visible case data", async () => {
  let release!: (value: unknown) => void;
  mocks.listTickerIdentityTransitionActivity.mockResolvedValue({ items: [activity], count: 1, unacknowledged_count: 1 });
  mocks.acknowledgeTickerIdentityTransitionActivity.mockImplementation(() => new Promise((resolve) => { release = resolve; }));
  await render(); await open(); await disclose("Tracking changes");
  const acknowledge = button("Acknowledge");
  await act(async () => { acknowledge.click(); acknowledge.click(); });
  expect(mocks.acknowledgeTickerIdentityTransitionActivity).toHaveBeenCalledExactlyOnceWith("activity-1");
  await act(async () => release({ activity_id: "activity-1", acknowledged_at: fixture.attention.as_of }));
  expect(document.querySelector(".lifecycle-drawer-content")?.textContent).toContain("OLD");
  expect(mocks.getCurrentLifecycleReview).toHaveBeenCalledTimes(1);
});
it("does not let a late activity read undo a newer acknowledgement", async () => {
  let release!: (value: unknown) => void;
  mocks.listTickerIdentityTransitionActivity.mockImplementationOnce(() => new Promise((resolve) => { release = resolve; }))
    .mockResolvedValue({ items: [{ ...activity, acknowledged_at: fixture.attention.as_of }], count: 1, unacknowledged_count: 0 });
  await render(); await disclose("Tracking changes");
  await disclose("Tracking changes");
  await act(async () => release({ items: [activity], count: 1, unacknowledged_count: 1 }));
  expect(document.querySelector(".lifecycle-activity-row")?.classList.contains("is-acknowledged")).toBe(true);
  expect([...document.querySelectorAll("button")].some((button) => button.textContent === "Acknowledge")).toBe(false);
});
it("does not offer another source check while durable running state has no progress", async () => {
  mocks.getSecurityLifecycleAutomationStatus.mockResolvedValue({ ...status, telemetry_status: "valid", last_status: "running" });
  mocks.getCurrentLifecycleReview.mockResolvedValue({ version: 1, as_of: fixture.attention.as_of,
    item: { ...row, next_action: { ...row.next_action, kind: "recheck", assessment_id: null } } });
  await render(); await open();
  expect(button("Check sources").disabled).toBe(true);
  expect(mocks.runSecurityLifecycleCaseAutomation).not.toHaveBeenCalled();
});
it("does not describe an attended receipt as an automatic application", async () => {
  mocks.listTickerIdentityTransitionActivity.mockResolvedValue({ items: [activity], count: 1, unacknowledged_count: 1 });
  await render(); await disclose("Tracking changes");
  expect(document.querySelector(".lifecycle-activity-row")?.textContent).not.toContain("Applied automatically");
  expect(document.querySelector(".lifecycle-activity-row")?.textContent).toContain("Applied");
});
it("invalidates a ready packet immediately when its execution date changes", async () => {
  await render(); await open(); await click("Review removal");
  expect(button("Confirm and apply").disabled).toBe(false);
  await setInput(document.querySelector<HTMLInputElement>('input[type="date"]')!, "2026-09-10");
  expect(button("Confirm and apply").disabled).toBe(true);
  expect(mocks.getLifecycleReviewPacket).toHaveBeenCalledTimes(1);
  expect(mocks.confirmLifecycleReview).not.toHaveBeenCalled();
});
it("keeps unresolved source-only rows visible instead of silently filtering them", async () => {
  mocks.listCurrentLifecycleReviews.mockResolvedValue({ ...fixture.attention,
    items: [{ ...row, ticker: "PENDING", finding: "unresolved", reason: "regulator_event_pending" }] });
  await render();
  expect(button("Review PENDING").disabled).toBe(false);
  expect(container.textContent).toContain("Status unresolved");
  expect(mocks.getLifecycleReviewPacket).not.toHaveBeenCalled();
});
