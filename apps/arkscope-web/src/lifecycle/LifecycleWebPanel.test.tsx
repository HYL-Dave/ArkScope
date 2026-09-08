/** @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import i18n from "i18next";
import { LifecycleWebPanel } from "./LifecycleWebPanel";
import { webPreflightFixture, webRunFixture, webUsageFixture } from "./webFixtures";

const api = vi.hoisted(() => ({ getLifecycleWebPreflight: vi.fn(), latestLifecycleWebRun: vi.fn(), startLifecycleWebRun: vi.fn(),
  getLifecycleWebRun: vi.fn(), cancelLifecycleWebRun: vi.fn(), getLifecycleWebReview: vi.fn(), confirmLifecycleWebReview: vi.fn() }));
vi.mock("../api", async (original) => ({ ...await original<typeof import("../api")>(), ...api }));
const fixture = JSON.parse(readFileSync(resolve(import.meta.dirname, "../../../../tests/fixtures/lifecycle_current_v1.json"), "utf8"));
let root: Root, container: HTMLDivElement;
const changed = vi.fn();
beforeEach(async () => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true); vi.clearAllMocks();
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network_forbidden")));
  api.getLifecycleWebPreflight.mockResolvedValue(structuredClone(webPreflightFixture));
  api.latestLifecycleWebRun.mockResolvedValue(null);
  api.startLifecycleWebRun.mockResolvedValue({ run_id: "run-1", created: true });
  api.getLifecycleWebRun.mockResolvedValue(structuredClone(webRunFixture));
  api.getLifecycleWebReview.mockResolvedValue({ ...fixture.packet, case_id: "case-1" });
  api.confirmLifecycleWebReview.mockResolvedValue(fixture.confirmation);
  container = document.createElement("div"); document.body.append(container); root = createRoot(container);
  await i18n.changeLanguage("en");
});
afterEach(async () => { await act(async () => root.unmount()); container.remove(); vi.useRealTimers(); vi.unstubAllGlobals(); });
async function render(caseId = "case-1", locale = "en") {
  await act(async () => { await i18n.changeLanguage(locale); root.render(<LifecycleWebPanel key={caseId} caseId={caseId} ticker="OLD" onChanged={changed} />); });
}
function button(name: string) {
  const value = [...document.querySelectorAll<HTMLButtonElement>("button")].find((item) => (item.getAttribute("aria-label") ?? item.textContent?.trim()) === name);
  expect(value, name).toBeTruthy(); return value!;
}
async function click(name: string) { await act(async () => button(name).click()); }
async function acceptDialog() { await act(async () => document.querySelector<HTMLButtonElement>(".ui-confirm-dialog button:last-child")!.click()); }

it.each(["en", "zh-Hant"])("keeps usage in a collapsed record and never dispatches on expansion: %s", async (locale) => {
  api.latestLifecycleWebRun.mockResolvedValue({ ...webRunFixture, usage: webUsageFixture.totals, usage_report: webUsageFixture });
  await render("case-1", locale);
  const details = container.querySelector<HTMLDetailsElement>(".lifecycle-web-usage");
  expect(details).not.toBeNull(); expect(details?.open).toBe(false);
  expect(details?.querySelector("summary")?.textContent).toBe(locale === "en" ? "Usage record" : "\u7528\u91cf\u7d00\u9304");
  expect(details?.textContent).toContain("29,706"); expect(details?.textContent).toContain("3,976");
  expect(details?.textContent).toContain(locale === "en" ? "Input tokens" : "\u8f38\u5165 Token");
  expect(details?.textContent).toContain(locale === "en" ? "Reported counters, not a bill" : "\u56de\u5831\u8a08\u6578\uff0c\u975e\u5e33\u55ae");
  await act(async () => details!.querySelector("summary")!.click());
  expect(details?.open).toBe(true);
  expect(container.querySelector(".lifecycle-web-result")?.textContent).not.toContain("29,706");
  expect(api.startLifecycleWebRun).not.toHaveBeenCalled(); expect(api.confirmLifecycleWebReview).not.toHaveBeenCalled();
});

it("does not present a partial accounting subtotal as the complete amount or investigation success", async () => {
  api.latestLifecycleWebRun.mockResolvedValue({ ...webRunFixture, status: "failed", finding: null, failure_code: "provider_call_failed",
    usage: { input_tokens: null, output_tokens: null }, usage_report: { ...webUsageFixture,
      coverage: "partial", recorded_submissions: 1, totals: { input_tokens: null, output_tokens: null },
      known_subtotal: { input_tokens: 29706, output_tokens: 3228 }, phases: webUsageFixture.phases.slice(0, 1) } });
  await render();
  const details = container.querySelector(".lifecycle-web-usage");
  expect(details?.textContent).toContain("Known subtotal"); expect(details?.textContent).toContain("1 / 2");
  expect(details?.textContent).toContain("Some counters missing");
  expect(container.textContent).toContain("Investigation failed");
  expect(details?.textContent).not.toContain("Reported total");
});

it("shows unrecorded scope for old history instead of declaring zero or complete usage", async () => {
  api.latestLifecycleWebRun.mockResolvedValue(structuredClone(webRunFixture));
  await render();
  expect(container.querySelector(".lifecycle-web-usage")?.textContent).toContain("Counter source was not recorded");
  expect(container.querySelector(".lifecycle-web-usage")?.textContent).not.toContain("All submitted phases reported");
});

it.each(["en", "zh-Hant"])("distinguishes unknown from actual zero in displayed counters: %s", async (locale) => {
  const phase = { ...webUsageFixture.phases[0], input_tokens: null, output_tokens: null,
    cache_creation_input_tokens: 0, cache_read_input_tokens: null, web_search_requests: 0 };
  const usage = { input_tokens: null, output_tokens: null };
  api.latestLifecycleWebRun.mockResolvedValue({ ...webRunFixture, usage, usage_report: { ...webUsageFixture,
    coverage: "unknown", totals: usage, known_subtotal: usage, recorded_submissions: 1, phases: [phase] },
    status: "failed", failure_code: "provider_call_failed", finding: null });
  await render("case-1", locale);
  const details = container.querySelector(".lifecycle-web-usage");
  expect(details?.textContent).toContain(locale === "en" ? "Not reported" : "\u672a\u56de\u5831");
  const values = [...details!.querySelectorAll(".lifecycle-web-usage-phase dd")].map((item) => item.textContent);
  expect(values).toEqual(locale === "en" ? ["Not reported", "Not reported", "0", "Not reported", "0"]
    : ["\u672a\u56de\u5831", "\u672a\u56de\u5831", "0", "\u672a\u56de\u5831", "0"]);
});

it("opening, reloading and reading a saved investigation never dispatch a model", async () => {
  api.latestLifecycleWebRun.mockResolvedValue(structuredClone(webRunFixture));
  await render();
  expect(container.textContent).toContain("Trading has ended.");
  expect(container.textContent).toContain("gpt-5.6-luna");
  expect(container.querySelector("blockquote")?.textContent).toContain("ceased trading");
  expect(container.querySelector("a")?.getAttribute("href")).toBe("https://issuer.example/notices");
  await click("Reload investigation");
  expect(api.startLifecycleWebRun).not.toHaveBeenCalled();
  expect(api.confirmLifecycleWebReview).not.toHaveBeenCalled();
  expect(container.querySelector("textarea")).toBeNull();
});
it("shows selected context honestly without claiming the model read the complete source", async () => {
  api.latestLifecycleWebRun.mockResolvedValue({ ...webRunFixture,
    source_reading: { sources: 4, selected_sources: 4, retained_text_bytes: 134217728, model_text_bytes: 192796 } });
  await render();
  expect(container.textContent).toContain("Full source text retained; analysis used selected passages.");
  await render("case-1", "zh-Hant");
  expect(container.textContent).toContain("\u4fdd\u7559\u5b8c\u6574\u4f86\u6e90\u6587\u5b57\uff1b\u5206\u6790\u4f7f\u7528\u76f8\u95dc\u6bb5\u843d\u3002");
  expect(api.startLifecycleWebRun).not.toHaveBeenCalled();
  api.latestLifecycleWebRun.mockResolvedValue(structuredClone(webRunFixture));
  await click("\u91cd\u65b0\u8b80\u53d6\u8abf\u67e5");
  expect(container.textContent).not.toContain("\u4fdd\u7559\u5b8c\u6574\u4f86\u6e90\u6587\u5b57\uff1b\u5206\u6790\u4f7f\u7528\u76f8\u95dc\u6bb5\u843d\u3002");
});
it("shows measured source failure details instead of guessing a document or model failure", async () => {
  api.latestLifecycleWebRun.mockResolvedValue({ ...webRunFixture, status: "failed", model_submissions: 1, finding: null,
    failure_code: "source_read_incomplete", source_reads: [{ request_index: 1, status: 403, framing: null, content_encoding: null,
      declared_body_bytes: null, received_body_bytes: 0, decoded_body_bytes: 0, result_code: "source_unavailable" }] });
  await render();
  const details = container.querySelector("details");
  expect(details?.querySelector("summary")?.textContent).toBe("Source reading details");
  expect(details?.textContent).toContain("HTTP 403");
  expect(details?.textContent).toContain("The source server did not return the requested document.");
  expect(container.textContent).not.toContain("exceeds this model's context");
  expect(api.startLifecycleWebRun).not.toHaveBeenCalled();
});
it("shows selected OAuth and cost before one explicit launch", async () => {
  await render(); await click("Investigate on the web");
  expect(document.body.textContent).toContain("Chosen account");
  expect(document.body.textContent).toContain("ChatGPT subscription");
  expect(document.body.textContent).toContain("2 model submissions");
  expect(document.body.textContent).toContain("No fallback");
  expect(api.startLifecycleWebRun).not.toHaveBeenCalled();
  await acceptDialog();
  expect(api.startLifecycleWebRun).toHaveBeenCalledOnce();
  expect(api.startLifecycleWebRun.mock.calls[0][0]).toBe("case-1");
  expect(api.startLifecycleWebRun.mock.calls[0][1]).toMatchObject({ question: "listing_status", preflight_sha256: "a".repeat(64) });
});
it("requires action-specific confirmation after reading sources and exact effects", async () => {
  api.latestLifecycleWebRun.mockResolvedValue(structuredClone(webRunFixture));
  await render(); await click("Review removal");
  expect(container.textContent).toContain("Manual");
  expect(api.confirmLifecycleWebReview).not.toHaveBeenCalled();
  await click("Confirm and apply");
  expect(document.querySelector('[role="dialog"]')?.textContent).toContain("Stop collecting OLD");
  await acceptDialog();
  expect(api.confirmLifecycleWebReview).toHaveBeenCalledWith("run-1", expect.objectContaining({ packet_sha256: fixture.packet.packet_sha256 }));
  expect(changed).toHaveBeenCalledOnce();
});
it.each(["en", "zh-Hant"])("shows unread references and the reviewed conclusion at the last confirmation (%s)", async (locale) => {
  const gap = { url: "https://news.example.com/unread-notice", reason: "source_unavailable" };
  const packet = { ...fixture.packet, case_id: "case-1", source_gaps: [gap],
    finding: { ...fixture.packet.finding, impact_summary: "Trading has ended; stop tracking OLD, retaining its history." } };
  api.latestLifecycleWebRun.mockResolvedValue({ ...webRunFixture, source_gaps: [gap] });
  api.getLifecycleWebReview.mockResolvedValue(packet);
  await render("case-1", locale);
  const disclosure = container.querySelector(".lifecycle-web-gaps");
  expect(disclosure?.querySelector("a")?.getAttribute("href")).toBe(gap.url);
  expect(disclosure?.querySelector("a")?.getAttribute("title")).toBe(gap.url);
  expect(disclosure?.querySelector("a")?.textContent).toBe("news.example.com");
  expect(disclosure?.textContent).toContain(locale === "en" ? "not used as evidence" : "\u672a\u5217\u70ba\u5224\u65b7\u4f9d\u64da");
  expect(disclosure?.textContent).toContain(locale === "en" ? "did not return the requested document" : "\u4f86\u6e90\u4f3a\u670d\u5668\u672a\u56de\u50b3\u6240\u8981\u6c42\u7684\u6587\u4ef6");
  await click(locale === "en" ? "Review removal" : "\u78ba\u8a8d\u79fb\u9664\u7bc4\u570d");
  await click(locale === "en" ? "Confirm and apply" : "\u78ba\u8a8d\u4e26\u5957\u7528");
  const dialog = document.querySelector('[role="dialog"]');
  expect(dialog?.textContent).toContain(packet.finding.impact_summary);
  expect(dialog?.querySelector(".lifecycle-web-gaps a")?.getAttribute("href")).toBe(gap.url);
  expect(dialog?.querySelector(".lifecycle-web-gaps a")?.textContent).toBe("news.example.com");
  expect(dialog?.textContent).not.toContain("source_unavailable");
  expect(api.confirmLifecycleWebReview).not.toHaveBeenCalled();
  expect(api.startLifecycleWebRun).not.toHaveBeenCalled();
  expect(container.querySelector("textarea")).toBeNull();
  await acceptDialog();
  expect(api.confirmLifecycleWebReview).toHaveBeenCalledExactlyOnceWith("run-1", packet);
});
it("keeps a legacy missing URL explicit instead of inventing a link or claiming no gaps", async () => {
  api.latestLifecycleWebRun.mockResolvedValue({ ...webRunFixture, source_gaps: [{ url: null, reason: "source_timeout" }] });
  await render();
  const disclosure = container.querySelector(".lifecycle-web-gaps");
  expect(disclosure?.textContent).toContain("Source URL was not recorded");
  expect(disclosure?.querySelector("a")).toBeNull();
  api.latestLifecycleWebRun.mockResolvedValue({ ...webRunFixture, source_gaps: [] });
  await click("Reload investigation");
  expect(container.querySelector(".lifecycle-web-gaps")).toBeNull();
  expect(api.startLifecycleWebRun).not.toHaveBeenCalled();
});
it.each(["en", "zh-Hant"])("an unrecognized source reason does not turn a complete finding into a failed investigation (%s)", async (locale) => {
  api.latestLifecycleWebRun.mockResolvedValue({ ...webRunFixture,
    source_gaps: [{ url: "https://news.example.com/notice", reason: "future_source_read_failure" }] });
  await render("case-1", locale);
  const disclosure = container.querySelector(".lifecycle-web-gaps");
  expect(disclosure?.textContent).toContain(locale === "en" ? "This source could not be read" : "\u6b64\u4f86\u6e90\u672a\u80fd\u8b80\u53d6");
  expect(disclosure?.textContent).not.toContain(locale === "en" ? "investigation could not complete" : "\u8abf\u67e5\u672a\u80fd\u5b8c\u6210");
  expect(disclosure?.textContent).not.toContain("future_source_read_failure");
  expect(container.textContent).toContain("Trading has ended.");
});
it("does not offer human confirmation when a read gap accompanies a material conflict", async () => {
  api.latestLifecycleWebRun.mockResolvedValue({ ...webRunFixture, source_gaps: [{ url: null, reason: "source_timeout" }],
    finding: { ...webRunFixture.finding, action: null, block_reasons: ["material_contradiction"], contradictions: ["Still trading on OTC."] } });
  await render();
  expect(container.textContent).toContain("Still trading on OTC.");
  expect([...container.querySelectorAll("button")].some((item) => item.textContent?.includes("Review removal"))).toBe(false);
  expect(api.getLifecycleWebReview).not.toHaveBeenCalled();
  expect(api.confirmLifecycleWebReview).not.toHaveBeenCalled();
});
it("invalidates Web confirmation immediately when its reviewed execution date changes", async () => {
  api.latestLifecycleWebRun.mockResolvedValue(structuredClone(webRunFixture));
  await render(); await click("Review removal");
  expect(button("Confirm and apply").disabled).toBe(false);
  const input = container.querySelector<HTMLInputElement>('input[type="date"]')!;
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(input, "2026-09-07");
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
  expect(button("Confirm and apply").disabled).toBe(true);
  expect(api.getLifecycleWebReview).toHaveBeenCalledOnce();
  expect(api.confirmLifecycleWebReview).not.toHaveBeenCalled();
  expect(api.startLifecycleWebRun).not.toHaveBeenCalled();
});
it("cancel acknowledgment stays pending, then an unknown outcome stays visible without retry", async () => {
  const pending = { ...webRunFixture, status: "searching", phase: "searching", finding: null, finished_at: null };
  api.latestLifecycleWebRun.mockResolvedValue(pending);
  api.cancelLifecycleWebRun.mockResolvedValue({ ...pending, status: "cancelling", cancel_requested_at: "2026-09-06T01:00:01Z" });
  await render(); await click("Stop investigation");
  expect(container.textContent).toContain("Stopping");
  expect(api.startLifecycleWebRun).not.toHaveBeenCalled();
  api.latestLifecycleWebRun.mockResolvedValue({ ...pending, status: "remote_outcome_unknown", failure_code: "stop_requested" });
  await click("Reload investigation");
  expect(container.textContent).toContain("Remote outcome unknown");
  expect(container.textContent).toContain("Stop was requested.");
  expect(container.textContent).not.toContain("Investigation was stopped.");
  expect(api.startLifecycleWebRun).not.toHaveBeenCalled();
  await render("case-1", "zh-Hant");
  expect(container.textContent).toContain("\u9060\u7aef\u7d50\u679c\u672a\u77e5");
  expect(container.textContent).toContain("\u5df2\u8981\u6c42\u505c\u6b62\u8abf\u67e5\u3002");
  expect(container.textContent).not.toContain("\u8abf\u67e5\u5df2\u505c\u6b62\u3002");
  expect(api.startLifecycleWebRun).not.toHaveBeenCalled();
});
it("does not show another case's late response or reuse its launch confirmation", async () => {
  let resolveLate!: (value: unknown) => void;
  api.latestLifecycleWebRun.mockReturnValueOnce(new Promise((resolve) => { resolveLate = resolve; }));
  await render();
  api.getLifecycleWebPreflight.mockResolvedValue({ ...webPreflightFixture, case_id: "case-2" });
  await render("case-2");
  await act(async () => resolveLate(webRunFixture));
  expect(container.textContent).not.toContain("Trading has ended.");
  expect(api.startLifecycleWebRun).not.toHaveBeenCalled();
});
it("makes an unavailable credential visible without another credential choice or silent retry", async () => {
  api.getLifecycleWebPreflight.mockResolvedValue({ version: 1, case_id: "case-1", available: false, reason: "model_auth_unverified",
    preflight_sha256: null, public_identity: null, execution: null, credential_label: null, limits: null });
  await render();
  expect(container.textContent).toContain("not admitted on this sign-in channel");
  expect(button("Investigate on the web").disabled).toBe(true);
  expect(api.startLifecycleWebRun).not.toHaveBeenCalled();
});
it("keeps changed effects blocked and offers a fresh review, not another provider call", async () => {
  api.latestLifecycleWebRun.mockResolvedValue(structuredClone(webRunFixture));
  api.confirmLifecycleWebReview.mockRejectedValue({ code: "review_changed" });
  await render(); await click("Review removal"); await click("Confirm and apply"); await acceptDialog();
  expect(container.textContent).toContain("changed");
  expect(api.startLifecycleWebRun).not.toHaveBeenCalled();
});
it("localizes the whole web surface and its OAuth provenance", async () => {
  api.latestLifecycleWebRun.mockResolvedValue(structuredClone(webRunFixture));
  await render("case-1", "zh-Hant");
  expect(container.textContent).toContain("\u7db2\u8def\u8abf\u67e5");
  expect(container.textContent).toContain("ChatGPT \u8a02\u95b1");
  expect(container.textContent).not.toContain("Review removal");
  expect(container.textContent).not.toContain("undefined");
});
