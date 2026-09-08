/** @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import i18n from "i18next";
import { CurrentLifecycleAudit, translationFailurePresentation } from "./CurrentLifecycleAudit";
import type { RuntimeConfig } from "../api";

const api = vi.hoisted(() => ({ getSecurityLifecycleCaseAudit: vi.fn(), translateSecurityLifecycleEvidence: vi.fn() }));
vi.mock("../api", async (original) => ({ ...await original<typeof import("../api")>(), ...api }));
const source = "SEC source: Units of Beneficial Interest / 原文保留";
const evidence = { evidence_id: "evidence-sec", source_family: "regulator", kind: "regulator_excerpt", excerpt: source,
  source_url: "https://www.sec.gov/Archives/fixture/notice.htm", content_sha256: "a".repeat(64), title: "Listing notice",
  publisher: "SEC", source_published_at: "2026-09-04T12:00:00Z", translations: [], created_at: "2026-09-05T01:00:00Z" };
const translation = { evidence_id: evidence.evidence_id, evidence_content_sha256: evidence.content_sha256, locale: "en",
  translated_text: "Translated fixture text", provider: "openai", model: "gpt-5.3-codex-spark", harness: "codex-app-server", translated_at: "2026-09-05T01:00:00Z" };
const assessment = { assessment_id: "assessment-old", status: "accepted", author: "legacy_review", automation_method: null,
  acceptance_authority: "legacy_migration", automation_run_id: null, rule_id: null, rule_version: null, decision_provenance_sha256: null,
  relevance: "direct_tracked_security", confidence: "unknown", conclusion: "Legacy symbol or venue review.", impact_summary: "Legacy meaning is retained.",
  outcomes: ["symbol_or_venue_changed"], citations: [{ reference_kind: "observation", evidence_id: null, cited_content_sha256: "f".repeat(64) }],
  stale: false, created_at: "2026-08-17T00:00:00Z", counterparty_name: null, counterparty_ticker: null, counterparty_cik: null,
  successor_ticker: null, destination_venue: null, effective_date: null, consideration_currency: null, cash_per_security_decimal: null, exchange_ratio_decimal: null };
const audit = { case_id: "slc_original", observation_fingerprint_sha256: "f".repeat(64), evidence: [evidence], assessment_history: [assessment],
  automation_runs: [], automation_facts: [], investigation_runs: [], acknowledgement_history: [], truncation: {} };
const runtime = { fixed_task_runtime: { card_translation: { task: "card_translation", model_timeout_s: 600, source: "db", db_saved: true, warning: null } } } as RuntimeConfig;
const navigate = vi.fn();
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
      ["translation_context_window_exceeded", "The evidence text exceeds the selected model's context window. Choose another model.", "證據文字超過所選模型可接受的上下文，請改選其他模型。", "settings"],
      ["translation_protocol_resource_exhausted", "The translation response exceeded this route's safe processing limit. Choose another model.", "翻譯回應超過此路徑的安全處理上限，請改選其他模型。", "settings"],
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
let root: Root, host: HTMLDivElement;
beforeEach(async () => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true); vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network_forbidden")));
  vi.clearAllMocks(); api.getSecurityLifecycleCaseAudit.mockReset().mockResolvedValue(audit);
  api.translateSecurityLifecycleEvidence.mockReset().mockResolvedValue(translation);
  host = document.createElement("div"); document.body.append(host); root = createRoot(host); await i18n.changeLanguage("en");
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.unstubAllGlobals(); });
async function render(caseId = "slc_original", locale = "en") {
  await act(async () => { await i18n.changeLanguage(locale); root.render(<CurrentLifecycleAudit key={caseId} caseIds={[caseId]} ticker="OLD" runtime={runtime} onNavigate={navigate} />); });
}
async function toggle(open: boolean) { await act(async () => { const node = host.querySelector<HTMLDetailsElement>(".lifecycle-audit")!; node.open = open; node.dispatchEvent(new Event("toggle")); }); }
function button(label: string) { const node = [...host.querySelectorAll<HTMLButtonElement>("button")].find((x) => x.textContent?.trim() === label); expect(node, label).toBeTruthy(); return node!; }
async function click(label: string) { await act(async () => button(label).click()); }

it("loads once on disclosure and reuses the audit on close and reopen", async () => {
  await render(); expect(api.getSecurityLifecycleCaseAudit).not.toHaveBeenCalled();
  await toggle(true); await toggle(false); await toggle(true);
  expect(api.getSecurityLifecycleCaseAudit).toHaveBeenCalledExactlyOnceWith("slc_original");
  expect(api.translateSecurityLifecycleEvidence).not.toHaveBeenCalled();
});
it("discards a late response after switching to a different case", async () => {
  let release!: (value: unknown) => void;
  api.getSecurityLifecycleCaseAudit.mockImplementationOnce(() => new Promise((resolve) => { release = resolve; }))
    .mockResolvedValueOnce({ ...audit, case_id: "slc_second", evidence: [{ ...evidence, excerpt: "Only second case source" }] });
  await render(); await toggle(true); await render("slc_second"); await toggle(true);
  await act(async () => release(audit));
  expect(host.textContent).toContain("Only second case source"); expect(host.textContent).not.toContain(source);
});
it.each(["en", "zh-Hant"])("preserves original evidence and legacy assessment provenance in %s", async (locale) => {
  await render("slc_original", locale); await toggle(true);
  expect(host.textContent).toContain(source);
  expect(host.textContent).toContain(locale === "en" ? "Limited provenance" : "來源脈絡有限");
  expect(host.textContent).toContain(locale === "en" ? "Legacy review" : "舊覆核紀錄");
  expect(host.querySelector('a[href="https://www.sec.gov/Archives/fixture/notice.htm"]')).not.toBeNull();
  expect(host.querySelector("textarea")).toBeNull();
});
it("preserves the accepted legacy review meaning in both locales", async () => {
  await render(); await toggle(true);
  const legacy = host.querySelector(".lifecycle-assessment-history");
  for (const text of ["Directly concerns the tracked security", "Symbol or trading venue changed (legacy review)", "Accepted through legacy migration"]) {
    expect(legacy?.textContent).toContain(text);
  }
  expect(legacy?.textContent).not.toContain("Undetermined");
  expect(host.textContent).toContain(source);
  await act(async () => i18n.changeLanguage("zh-Hant"));
  for (const text of ["直接涉及追蹤證券", "代號或交易市場異動（舊覆核未區分）", "由舊資料遷移保留的接受結果"]) {
    expect(legacy?.textContent).toContain(text);
  }
  expect(legacy?.textContent).not.toContain("尚未判定");
  expect(host.textContent).toContain(source);
});
it("shows all structured transaction facts without deriving them from prose", async () => {
  api.getSecurityLifecycleCaseAudit.mockResolvedValue({ ...audit, assessment_history: [{ ...assessment, author: "human", acceptance_authority: "human",
    outcomes: ["symbol_changed", "acquisition_mixed"], counterparty_name: "Independent acquirer", counterparty_ticker: "ACQ", counterparty_cik: "0000123456",
    successor_ticker: "NEW", destination_venue: "NYSE", effective_date: "2026-09-30", consideration_currency: "USD", cash_per_security_decimal: "10.5000", exchange_ratio_decimal: "0.2500", stale: true }] });
  await render(); await toggle(true);
  for (const value of ["Independent acquirer", "ACQ", "0000123456", "NEW", "NYSE", "2026-09-30", "USD", "0.2500", "Revalidation required"]) expect(host.textContent).toContain(value);
});
it("keeps deterministic automation authorship and structured bilingual meaning", async () => {
  api.getSecurityLifecycleCaseAudit.mockResolvedValue({ ...audit, assessment_history: [{ ...assessment, author: "automation", status: "draft",
    acceptance_authority: null, automation_method: "deterministic_rule", automation_run_id: "run_1", rule_id: "m-and-a-review", rule_version: "2", outcomes: ["acquisition_terms_unknown"] }] });
  await render(); await toggle(true);
  expect(host.textContent).toContain("Deterministic rule");
  expect(host.textContent).toContain("Automation-generated assessment");
  expect(host.querySelector("textarea")).toBeNull();
  await act(async () => i18n.changeLanguage("zh-Hant"));
  expect(host.textContent).not.toContain("Deterministic rule");
});
it("switches a cached translation without invoking a model and keeps the source accessible", async () => {
  api.getSecurityLifecycleCaseAudit.mockResolvedValue({ ...audit, evidence: [{ ...evidence, translations: [translation] }] });
  await render(); await toggle(true);
  expect(host.textContent).toContain(source);
  await click("Machine translation"); expect(host.textContent).toContain(translation.translated_text);
  expect(host.textContent).toContain(translation.model);
  await click("Original source evidence"); expect(host.textContent).toContain(source);
  expect(api.translateSecurityLifecycleEvidence).not.toHaveBeenCalled();
});
it("uses the shared content-translation runtime only on explicit request", async () => {
  await render(); await toggle(true); await click("Translate evidence");
  expect(api.translateSecurityLifecycleEvidence).toHaveBeenCalledExactlyOnceWith(evidence.evidence_id, "en", runtime);
  expect(host.textContent).toContain(translation.translated_text);
  await click("Original source evidence"); expect(host.textContent).toContain(source);
});
it("does not attach a translation for the wrong content digest", async () => {
  api.translateSecurityLifecycleEvidence.mockResolvedValue({ ...translation, evidence_content_sha256: "b".repeat(64) });
  await render(); await toggle(true); await click("Translate evidence");
  expect(host.textContent).toContain(source);
  expect(host.textContent).not.toContain(translation.translated_text);
  expect(host.textContent).toContain("The source evidence changed");
  expect([...host.querySelectorAll("button")].some((b) => b.textContent?.trim() === "Machine translation")).toBe(false);
});
it("never automatically retries a failed translation and keeps Settings navigation local", async () => {
  api.translateSecurityLifecycleEvidence.mockRejectedValue({ code: "translation_model_unavailable", metadata: { provider: "openai", model: translation.model, harness: translation.harness, retryable: false } });
  await render(); await toggle(true); await click("Translate evidence");
  expect(host.textContent).toContain(source); expect(host.textContent).toContain("model is unavailable");
  expect(api.translateSecurityLifecycleEvidence).toHaveBeenCalledTimes(1);
  await act(async () => host.querySelector<HTMLButtonElement>('[data-action="open-content-translation-settings"]')!.click());
  expect(navigate).toHaveBeenCalledExactlyOnceWith({ kind: "settings_section", section: "models" });
});
it("offers retry only for a reviewed retryable failure", async () => {
  api.translateSecurityLifecycleEvidence.mockRejectedValue({ code: "translation_timeout", metadata: { retryable: true } });
  await render(); await toggle(true); await click("Translate evidence");
  expect(button("Retry translation").disabled).toBe(false);
  expect(api.translateSecurityLifecycleEvidence).toHaveBeenCalledTimes(1);
});
it("keeps unknown translation errors safe and never displays their raw details", async () => {
  api.translateSecurityLifecycleEvidence.mockRejectedValue({ code: "future_code", message: "private-token-in-message", metadata: { retryable: true } });
  await render(); await toggle(true); await click("Translate evidence");
  expect(host.textContent).toContain(source); expect(host.textContent).not.toContain("private-token-in-message");
  expect([...host.querySelectorAll("button")].some((b) => b.textContent === "Retry translation")).toBe(false);
});
it("does not offer prose translation for a structured listing or ticker timeline", async () => {
  api.getSecurityLifecycleCaseAudit.mockResolvedValue({ ...audit, evidence: [{ evidence_id: "listing", source_family: "listing_authority", kind: "listing_directory_snapshot", source_url: null, created_at: evidence.created_at,
    listing: { authority: "massive", directory: null, candidate_ticker: "OLD", listing_status: "inactive", market: "stocks", primary_exchange: "XNYS", source_as_of: "2026-09-04", provider_last_updated_utc: null } },
    { evidence_id: "timeline", source_family: "listing_authority", kind: "ticker_event_snapshot", source_url: null, created_at: evidence.created_at,
      ticker_event: { candidate_ticker: "OLD", events: [{ source_ticker: "OLD", successor_ticker: "NEW", effective_date: "2026-09-04" }] } }] });
  await render(); await toggle(true);
  expect(host.textContent).toContain("OLD"); expect(host.textContent).toContain("NEW");
  expect([...host.querySelectorAll("button")].some((b) => b.textContent?.includes("Translate"))).toBe(false);
});
it("retains historical failed and zero-result runs without claiming no impact", async () => {
  api.getSecurityLifecycleCaseAudit.mockResolvedValue({ ...audit, investigation_runs: [
    { run_id: "empty", status: "succeeded", result_count: 0, failure_code: null, created_at: evidence.created_at },
    { run_id: "failed", status: "failed", result_count: 0, failure_code: "rate_limited", created_at: evidence.created_at }],
    automation_facts: [{ fact_id: "fact_1", fact_type: "source_ticker", normalized_value: "OLD", extractor_rule_id: "sec-symbol", extractor_rule_version: "1" }],
    acknowledgement_history: [{ acknowledgement_id: "ack_1", reason: "evidence_insufficient", note: "Evidence was insufficient", stale: false, acknowledged_at: evidence.created_at, reopened_at: null }] });
  await render(); await toggle(true);
  expect(host.textContent).toContain("Search completed"); expect(host.textContent).toContain("Search rate limit reached");
  expect(host.textContent).toContain("sec-symbol"); expect(host.textContent).toContain("Evidence was insufficient");
});
it("keeps provider-budget diagnostics visible in the audit and marks bounded history", async () => {
  api.getSecurityLifecycleCaseAudit.mockResolvedValue({ ...audit, automation_runs: [{ run_id: "run_1", status: "blocked", failure_code: null,
    created_at: evidence.created_at, blockers: [{ blocker_code: "market_confirmation_missing", retryable: true,
      operator_detail: { code: "candidate_budget_exceeded", query_limit: 8, candidate_count: 9, provider_contacted: false } }] }], truncation: { automation_runs: { total: 30, returned: 1 } } });
  await render(); await toggle(true);
  expect(host.textContent).toContain("Market confirmation is missing");
  expect(host.textContent).toContain("9"); expect(host.textContent).toContain("8");
  expect(host.textContent).toContain("older records are retained");
});

const failures = [
  ["translation_route_unavailable", "routeUnavailable", "settings"], ["translation_credential_missing", "credentialMissing", "settings"],
  ["translation_auth_rejected", "authRejected", "settings"], ["translation_rate_limited", "rateLimited", "retry"],
  ["translation_quota_exhausted", "quotaExhausted", "settings"], ["translation_model_unavailable", "modelUnavailable", "settings"],
  ["translation_timeout", "timeout", "retry"], ["translation_output_invalid", "outputInvalid", "retry"],
  ["translation_context_window_exceeded", "contextWindowExceeded", "settings"], ["translation_protocol_resource_exhausted", "protocolResourceExhausted", "settings"],
  ["translation_provider_error", "providerError", "retry"], ["evidence_changed", "evidenceChanged", null],
] as const;
it.each(failures)("retains reviewed bilingual presentation for %s", (code, key, action) => {
  const values = ["en", "zh-Hant"].map((locale) => {
    const t = i18n.getFixedT(locale, "explore"); const value = translationFailurePresentation(code, t);
    expect(value.action).toBe(action); expect(value.message).toBe(t(($) => $.lifecycle.translation[key]));
    expect(value.message).not.toContain("missing:"); return value.message;
  });
  expect(values[0]).not.toBe(values[1]);
});
