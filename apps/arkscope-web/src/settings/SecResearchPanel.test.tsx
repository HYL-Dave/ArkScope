/** @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import i18n from "i18next";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DataScheduleControlsProvider, DataScheduleTable, useSharedDataScheduleControls } from "./dataScheduleControls";
import { createSettingsReadCache } from "./settingsReadCache";
import type { ScheduleSourceState } from "../api";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const capacity = { persisted_bytes: 120, reserved_bytes: 30, orphan_bytes: 7, charged_bytes: 157, budget_bytes: 107374182400, remaining_bytes: 107374182243, over_budget: false };
const envelope = (status = "ok", data: unknown = [], next_cursor: string | null = null) => ({
  status, data, next_cursor, gaps: status === "partial" ? [{ code: "history_pending" }] : [],
  observed_at: "2026-09-11T01:00:00Z", coverage: { receipt_id: 7, complete: status !== "partial" },
});
const filing = (id: string) => ({ filing_id: id, accession: `accession-${id}`, form: "10-K", filed_date: "2026-02-01", report_date: "2025-12-31", accepted_at: "2026-02-01T10:00:00Z", primary_document: `${id}.htm`, primary_url: "https://www.sec.gov/Archives/edgar/data/123/report.htm", source: { snapshot_id: 1 } });
const receipt = { receipt_id: 8, cik: "0000000123", status: "partial", completed: ["recent"], pending: ["history.json"], gaps: [{ code: "history_pending" }], observed_at: "2026-09-11T02:00:00Z" };
type Handler = (url: URL, init: RequestInit) => unknown | Promise<unknown>;
let handler: Handler;
let requests: { url: URL; init: RequestInit }[];
let budget: number;
let host: HTMLDivElement;
let root: ReturnType<typeof createRoot> | undefined;
let stylesheet: HTMLStyleElement | undefined;
let scheduled: ScheduleSourceState;
let batchStatus: unknown;

function ScheduleOwner() {
  return <DataScheduleTable controller={useSharedDataScheduleControls()} scope="non_macro" />;
}

function applyPanelStyles() {
  stylesheet = document.createElement("style");
  stylesheet.textContent = ["../ui/primitives.css", "secResearch.css"]
    .map((path) => readFileSync(resolve(import.meta.dirname, path), "utf8")).join("\n");
  document.head.append(stylesheet);
}

function fallback(url: URL) {
  if (url.pathname === "/schedule") return { sources: { sec_research_filings: scheduled } };
  if (url.pathname === "/sec-research/schedule-status") return { ...envelope("ok", batchStatus),
    gaps: (batchStatus as { last_attempt: { gaps: unknown[] } | null }).last_attempt?.gaps ?? [] };
  if (url.pathname === "/sec-research/config") return { capture_budget_bytes: budget, capacity };
  if (url.pathname.endsWith("/refresh")) return receipt;
  if (url.pathname.endsWith("/filing-forms")) return envelope("ok", ["10-K", "10-Q", "10-Q/A", "8-K", "DEF 14A", "SC 13G/A"]);
  if (url.pathname.endsWith("/filings")) return envelope("ok", [filing("first")], "opaque+/= &token");
  if (url.pathname.endsWith("/facts")) return envelope("ok", [{ fact_id: "fact-1", namespace: "us-gaap", concept: "Assets", value: "1234567890123456789.123", unit: "EUR", start: null, end: "2025-12-31", filed_date: "2026-02-01", accession: "000-1", source: { snapshot_id: 2 } }]);
  if (/\/sec-research\/\d+$/.test(url.pathname)) return { ...envelope(), data: { cik: url.pathname.split("/").pop(), snapshots: { recent: 1, facts: 1 } }, coverage: { completed: ["recent"], pending: ["history.json"] } };
  throw new Error(`unmocked route: ${url}`);
}
beforeEach(() => {
  scheduled = { label: "SEC", description: "", ibkr: false, provider_fetch: true,
    source_mode: "provider_fetch", write_target: "market_data.db", source_badges: ["SEC"],
    enabled: false, interval_minutes: 1440, default_interval_minutes: 1440,
    running: false, progress: null, last_attempt_at: null, last_result: null,
    durable_state: null, job_name: "collect.sec_research_filings" };
  batchStatus = { last_attempt: null, last_acquisition_at: null, last_completed_batch: null };
  budget = 107374182400;
  requests = [];
  handler = fallback;
  vi.stubGlobal("fetch", vi.fn(async (input: string, init: RequestInit = {}) => {
    const url = new URL(input);
    requests.push({ url, init });
    const result = await handler(url, init);
    return result instanceof Response ? result : new Response(JSON.stringify(result));
  }));
});
afterEach(async () => {
  if (root) await act(async () => root!.unmount());
  root = undefined;
  host?.remove();
  stylesheet?.remove();
  stylesheet = undefined;
  vi.useRealTimers();
  vi.unstubAllGlobals();
});
async function render(language = "en", withControls = false) {
  // Dynamic import makes the absent panel an explicit RED test failure.
  const { SecResearchPanel } = await import("./SecResearchPanel");
  await i18n.changeLanguage(language);
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  await act(async () => root!.render(<DataScheduleControlsProvider settingsReadCache={createSettingsReadCache()}>
    {withControls && <ScheduleOwner />}<SecResearchPanel />
  </DataScheduleControlsProvider>));
}
function button(name: string) {
  const result = [...host.querySelectorAll<HTMLButtonElement>("button")].find((el) => (el.getAttribute("aria-label") ?? el.textContent) === name);
  expect(result, `button ${name}`).toBeDefined();
  return result!;
}
async function click(name: string) { await act(async () => button(name).click()); }
async function key(element: Element, value: string) {
  await act(async () => element.dispatchEvent(new KeyboardEvent("keydown", { key: value, bubbles: true, cancelable: true })));
}
async function openForms(name = "Forms") {
  if (button(name).getAttribute("aria-expanded") !== "true") await click(name);
  return host.querySelector<HTMLElement>('[role="menu"]')!;
}
function formOption(name: string) {
  const option = [...host.querySelectorAll<HTMLButtonElement>('[role="menuitemcheckbox"]')].find((el) => formCode(el) === name);
  expect(option, `form option ${name}`).toBeDefined();
  return option!;
}
function formCode(element: Element) { return element.getAttribute("value") ?? element.textContent; }
async function chooseForms(...values: string[]) {
  const menu = await openForms();
  const options = [...menu.querySelectorAll<HTMLButtonElement>('[role="menuitemcheckbox"]')];
  for (const option of options.slice(1)) {
    if ((option.getAttribute("aria-checked") === "true") !== values.includes(option.value)) {
      await act(async () => option.click());
    }
  }
  for (const value of values) expect(formOption(value).getAttribute("aria-checked")).toBe("true");
  await key(menu, "Escape");
}
function formRequests() { return requests.filter(({ url }) => url.pathname.endsWith("/filing-forms")); }
function input(name: string) { return host.querySelector<HTMLInputElement>(`input[aria-label="${name}"]`)!; }
async function change(name: string, value: string) {
  await act(async () => {
    const element = input(name);
    expect(element, name).not.toBeNull();
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(element, value);
    element.dispatchEvent(new Event("input", { bubbles: true }));
  });
}
async function select(name: string, value: string) {
  await act(async () => {
    const el = host.querySelector<HTMLSelectElement>(`select[aria-label="${name}"]`)!;
    el.value = value;
    el.dispatchEvent(new Event("change", { bubbles: true }));
  });
}
async function load(cik = "123") { await change("CIK", cik); await click("Load local"); }
async function settleFilters(milliseconds = 300) {
  await act(async () => { await vi.advanceTimersByTimeAsync(milliseconds); });
}
function recordRequests() {
  return requests.filter(({ url }) => /\/(filings|facts)$/.test(url.pathname));
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

describe("SEC filing form selection", () => {
  it.each(["en", "zh-Hant"])("describes and groups the complete %s filing choices without changing query codes", async (locale) => {
    vi.useFakeTimers();
    const codes = ["144", "25", "3", "10-Q/A", "10-K", "10-Q", "DEF 14A", "SC 13G", "SCHEDULE 13G", "NEW-FORM"];
    handler = (url) => url.pathname.endsWith("/filing-forms") ? envelope("ok", codes) : fallback(url);
    await render(locale); await change("CIK", "123"); await click(locale === "en" ? "Load local" : "讀取本機");
    const menu = await openForms(locale === "en" ? "Forms" : "申報類型");
    const groups = [...menu.querySelectorAll('[role="group"]')];
    expect(groups.map((el) => el.getAttribute("aria-label"))).toEqual(locale === "en"
      ? ["Financial and periodic reports", "Events and proxy materials", "Ownership and transactions", "Offerings and listing", "Other filings"]
      : ["財務與定期報告", "重大事件與委託書", "持股與交易", "發行與上市", "其他申報"]);
    const choices = [...menu.querySelectorAll<HTMLButtonElement>('[role="menuitemcheckbox"]')].slice(1);
    expect(choices.map((el) => el.value).sort()).toEqual([...codes].sort());
    expect(choices.slice(0, 3).map((el) => el.value)).toEqual(["10-K", "10-Q", "10-Q/A"]);
    const expected = locale === "en" ? {
      "144": "Proposed sale of securities", "25": "Removal from listing and/or registration",
      "3": "Initial ownership statement", "10-Q/A": "Quarterly report (amendment)", "NEW-FORM": "Unclassified filing",
    } : {
      "144": "擬出售證券通知", "25": "撤銷證券上市及／或註冊通知",
      "3": "初始持股申報", "10-Q/A": "季報（修訂）", "NEW-FORM": "未分類申報",
    };
    for (const [code, label] of Object.entries(expected)) {
      const option = choices.find((el) => el.value === code)!;
      expect(option.textContent).toBe(`${code} ${label}`);
      expect(option.getAttribute("aria-label")).toBeNull(); // Both code and meaning are accessible.
      await act(async () => option.click());
    }
    await settleFilters();
    expect(recordRequests().at(-1)?.url.searchParams.getAll("forms").sort()).toEqual(Object.keys(expected).sort());
    expect(formRequests()).toHaveLength(1);
    expect(requests.every(({ init }) => (init.method ?? "GET") === "GET")).toBe(true);
  });

  it("does not invent absent types or groups when a partial catalog only contains unfamiliar codes", async () => {
    handler = (url) => url.pathname.endsWith("/filing-forms") ? envelope("partial", ["NEW-FORM/A", "__proto__"]) : fallback(url);
    await render(); await load(); const menu = await openForms();
    expect([...menu.querySelectorAll('[role="group"]')].map((el) => el.getAttribute("aria-label"))).toEqual(["Other filings"]);
    expect([...menu.querySelectorAll<HTMLButtonElement>('[role="menuitemcheckbox"]')].slice(1).map((el) => el.textContent)).toEqual([
      "NEW-FORM/A Unclassified filing", "__proto__ Unclassified filing",
    ]);
    expect(menu.querySelector('[role="status"]')?.textContent).toBe("Partial");
    expect(menu.textContent).toContain("history_pending");
  });

  it.each(["en", "zh-Hant"])("names all 52 observed filing codes in %s, retaining historical forms and aliases", async (locale) => {
    const fixture = JSON.parse(readFileSync(resolve(import.meta.dirname,
      "../../../../docs/superpowers/evidence/2026-09-15-sec-form-selector/checks/browser.json"), "utf8"));
    const codes: string[] = fixture.options;
    expect(codes).toHaveLength(52);
    handler = (url) => url.pathname.endsWith("/filing-forms") ? envelope("ok", codes) : fallback(url);
    await render(locale); await change("CIK", "123"); await click(locale === "en" ? "Load local" : "讀取本機");
    const menu = await openForms(locale === "en" ? "Forms" : "申報類型");
    const options = [...menu.querySelectorAll<HTMLButtonElement>('[role="menuitemcheckbox"]')].slice(1);
    expect(options.map((el) => el.value).sort()).toEqual([...codes].sort());
    for (const option of options) {
      expect(option.textContent).not.toMatch(/Unclassified|未分類|secResearch\./);
      expect(option.querySelector(".sec-form-option-text > span")?.textContent).toMatch(locale === "en" ? /[A-Za-z]/ : /[\u4e00-\u9fff]/);
    }
    expect(options.slice(0, 4).map((el) => el.value)).toEqual(["10-K", "10-K/A", "10-Q", "10-Q/A"]);
    expect(formOption("10-K405").textContent).toContain(locale === "en" ? "historical" : "歷史");
    expect(formOption("144/A").textContent).toContain(locale === "en" ? "amendment" : "修訂");
  });

  it("keeps language changes and grouped keyboard focus independent of exact amendment and alias selections", async () => {
    vi.useFakeTimers();
    handler = (url) => url.pathname.endsWith("/filing-forms")
      ? envelope("ok", ["144", "144/A", "SC 13G", "SCHEDULE 13G"]) : fallback(url);
    await render(); await load(); await openForms();
    await act(async () => formOption("144/A").click());
    await act(async () => formOption("SCHEDULE 13G").click());
    formOption("SCHEDULE 13G").focus();
    await act(async () => i18n.changeLanguage("zh-Hant"));
    expect(document.activeElement).toBe(formOption("SCHEDULE 13G"));
    expect(formOption("SC 13G").getAttribute("aria-checked")).toBe("false");
    expect(formOption("144").getAttribute("aria-checked")).toBe("false");
    expect(formOption("144/A").textContent).toBe("144/A 擬出售證券通知（修訂）");
    await settleFilters();
    expect(recordRequests().at(-1)?.url.searchParams.getAll("forms")).toEqual(["144/A", "SCHEDULE 13G"]);
    expect(formRequests()).toHaveLength(1);
    await key(document.activeElement!, "Home");
    expect(document.activeElement).toBe(formOption("全部"));
    await key(document.activeElement!, "ArrowDown");
    expect(document.activeElement).toBe(formOption("144"));
    await key(document.activeElement!, "Escape");
    expect(document.activeElement).toBe(button("申報類型"));
  });

  it("loads off-page choices from the issuer catalog instead of the current result page", async () => {
    await render();
    expect(formRequests()).toHaveLength(0);
    expect(button("Forms").disabled).toBe(true);
    await change("CIK", "123");
    expect(formRequests()).toHaveLength(0);
    await click("Load local");
    const menu = await openForms();
    expect([...menu.querySelectorAll('[role="menuitemcheckbox"]')].map(formCode)).toEqual([
      "All", "10-K", "10-Q", "10-Q/A", "8-K", "DEF 14A", "SC 13G/A",
    ]);
    expect(host.querySelector(".sec-record-scroll")?.textContent).not.toContain("DEF 14A");
    expect(input("Forms")).toBeNull();
    expect(host.querySelector("select[multiple]")).toBeNull();
    expect(formRequests()).toHaveLength(1);
    expect(formRequests()[0].url.pathname).toBe("/sec-research/0000000123/filing-forms");
    expect(formRequests()[0].url.search).toBe("");
    expect(requests.every(({ init }) => (init.method ?? "GET") === "GET" && init.body === undefined)).toBe(true);
  });

  it("preserves whole form strings and resets the cursor chain when selecting multiple types", async () => {
    vi.useFakeTimers();
    handler = (url) => url.pathname.endsWith("/filings") && url.searchParams.has("forms")
      ? envelope("ok", [filing("selected")], "selected-cursor") : fallback(url);
    await render(); await load(); await click("Next page");
    await chooseForms("10-Q/A", "DEF 14A");
    expect(button("Previous page").disabled).toBe(true);
    expect(host.querySelector(".sec-pagination > span")?.textContent).toBe("Page 1");
    await settleFilters(299);
    expect(recordRequests()).toHaveLength(2);
    await settleFilters(1);
    expect(recordRequests().at(-1)?.url.searchParams.getAll("forms")).toEqual(["10-Q/A", "DEF 14A"]);
    expect(recordRequests().at(-1)?.url.searchParams.has("cursor")).toBe(false);
    expect(host.textContent).toContain("selected.htm");
    await click("Next page");
    expect(recordRequests().at(-1)?.url.searchParams.get("cursor")).toBe("selected-cursor");
    expect(formRequests()).toHaveLength(1);
    expect(requests.some(({ init }) => init.method === "POST")).toBe(false);
  });

  it("All clears every selected form and automatically returns to an unfiltered first page", async () => {
    vi.useFakeTimers();
    await render(); await load(); await chooseForms("DEF 14A", "SC 13G/A"); await settleFilters();
    await click("Next page");
    await openForms();
    await act(async () => formOption("All").click());
    expect(formOption("All").getAttribute("aria-checked")).toBe("true");
    expect(formOption("DEF 14A").getAttribute("aria-checked")).toBe("false");
    expect(formOption("SC 13G/A").getAttribute("aria-checked")).toBe("false");
    expect(button("Forms").textContent).toBe("All");
    await settleFilters();
    expect(recordRequests().at(-1)?.url.searchParams.getAll("forms")).toEqual([]);
    expect(recordRequests().at(-1)?.url.searchParams.has("cursor")).toBe(false);
    expect(button("Previous page").disabled).toBe(true);
    expect(host.textContent).toContain("first.htm");
    expect(formRequests()).toHaveLength(1);
  });

  it("reloads choices only for explicit local reads and completed refreshes, not filter or page edits", async () => {
    vi.useFakeTimers();
    await render(); await load(); await chooseForms("10-Q"); await settleFilters();
    await change("Filed from", "2025-01-01"); await settleFilters();
    await click("Next page"); await click("Previous page");
    await click("Facts"); await click("Catalog"); await openForms();
    expect(formRequests()).toHaveLength(1);
    await click("Load local");
    expect(formRequests()).toHaveLength(2);
    handler = (url) => url.pathname.endsWith("/filing-forms") ? envelope("ok", ["10-Q", "S-3"]) : fallback(url);
    await click("Refresh structured data");
    await openForms();
    expect(formRequests()).toHaveLength(3);
    expect(formOption("S-3")).toBeDefined();
    expect(formOption("10-Q").getAttribute("aria-checked")).toBe("true");
    await click("Resume refresh");
    expect(formRequests()).toHaveLength(4);
    expect(requests.filter(({ init }) => init.method === "POST").map(({ init }) => init.body)).toEqual([
      '{"resume":false}', '{"resume":true}',
    ]);
  });

  it.each([
    { state: "partial", data: ["DEF 14A"], label: "Partial", options: ["All", "DEF 14A"] },
    { state: "partial", data: null, label: "Partial", options: ["All"] },
    { state: "empty", data: [], label: "Observed empty", options: ["All"] },
    { state: "unavailable", data: null, label: "Unavailable", options: ["All"] },
  ])("reports $state choices honestly without inferring types from rows", async ({ state, data, label, options }) => {
    handler = (url) => url.pathname.endsWith("/filing-forms") ? envelope(state, data) : fallback(url);
    await render(); await load();
    const menu = await openForms();
    expect(menu.querySelector('[role="status"]')?.textContent).toContain(label);
    expect([...menu.querySelectorAll('[role="menuitemcheckbox"]')].map(formCode)).toEqual(options);
    if (state !== "empty") expect(menu.textContent).not.toContain("Observed empty");
    if (state === "partial") expect(menu.textContent).toContain("history_pending");
    expect(host.querySelector(".sec-record-scroll")?.textContent).toContain("10-K");
  });

  it("shows loading without invented choices and accepts the lookup despite intervening date reads", async () => {
    vi.useFakeTimers();
    const pending = deferred<unknown>();
    handler = (url) => url.pathname.endsWith("/filing-forms") ? pending.promise : fallback(url);
    await render(); await load();
    const menu = await openForms();
    expect(menu.textContent).toContain("Loading");
    expect(menu.querySelectorAll('[role="menuitemcheckbox"]')).toHaveLength(1);
    await change("Filed from", "2025-01-01"); await settleFilters();
    expect(formRequests()).toHaveLength(1);
    await act(async () => pending.resolve(envelope("ok", ["DEF 14A"])));
    expect(menu.textContent).not.toContain("Loading");
    expect(formOption("DEF 14A")).toBeDefined();
  });

  it("retries failed choices through Load local without a source request", async () => {
    handler = (url) => url.pathname.endsWith("/filing-forms")
      ? new Response(JSON.stringify({ detail: { code: "sec_forms_unavailable" } }), { status: 503 }) : fallback(url);
    await render(); await load();
    const menu = await openForms();
    expect(menu.textContent).toContain("Unavailable");
    expect(menu.textContent).toContain("sec_forms_unavailable");
    expect(menu.querySelectorAll('[role="menuitemcheckbox"]')).toHaveLength(1);
    handler = (url) => url.pathname.endsWith("/filing-forms") ? envelope("ok", ["DEF 14A"]) : fallback(url);
    await click("Load local");
    await openForms();
    expect(formOption("DEF 14A")).toBeDefined();
    expect(menu.textContent).not.toContain("sec_forms_unavailable");
    expect(formRequests()).toHaveLength(2);
    expect(requests.some(({ init }) => init.method === "POST")).toBe(false);
  });

  it.each(["success", "failure"])("rejects a stale same-issuer option %s after an explicit reread", async (outcome) => {
    const old = deferred<unknown>();
    handler = (url) => url.pathname.endsWith("/filing-forms") ? old.promise : fallback(url);
    await render(); await load();
    expect(formRequests()).toHaveLength(1);
    handler = (url) => url.pathname.endsWith("/filing-forms") ? envelope("ok", ["S-3"]) : fallback(url);
    await click("Load local");
    const menu = await openForms();
    await act(async () => old.resolve(outcome === "success" ? envelope("partial", ["STALE"])
      : new Response(JSON.stringify({ detail: { code: "stale_forms_error" } }), { status: 503 })));
    expect(formOption("S-3")).toBeDefined();
    expect(menu.textContent).not.toMatch(/STALE|stale_forms_error|Partial/);
    expect(formRequests()).toHaveLength(2);
  });

  it("clears the old issuer selection and rejects its late options when CIK changes", async () => {
    vi.useFakeTimers();
    const old = deferred<unknown>();
    await render(); await load(); await chooseForms("DEF 14A"); await settleFilters();
    handler = (url) => url.pathname.endsWith("/filing-forms") ? old.promise : fallback(url);
    await click("Load local"); await openForms();
    await change("CIK", "456");
    expect(host.querySelector('[role="menu"]')).toBeNull();
    expect(button("Forms").disabled).toBe(true);
    expect(button("Forms").textContent).toBe("All");
    handler = (url) => url.pathname.endsWith("/filing-forms") ? envelope("ok", ["S-3"]) : fallback(url);
    await click("Load local");
    const menu = await openForms();
    await act(async () => old.resolve(envelope("ok", ["STALE"])));
    expect([...menu.querySelectorAll('[role="menuitemcheckbox"]')].map(formCode)).toEqual(["All", "S-3"]);
    expect(recordRequests().at(-1)?.url.pathname).toBe("/sec-research/0000000456/filings");
    expect(recordRequests().at(-1)?.url.searchParams.getAll("forms")).toEqual([]);
  });

  it("does not apply an option response or retain an open menu after unmount", async () => {
    const old = deferred<unknown>();
    handler = (url) => url.pathname.endsWith("/filing-forms") ? old.promise : fallback(url);
    await render(); await load(); await openForms();
    expect(formRequests()).toHaveLength(1);
    const before = requests.length;
    await act(async () => root!.unmount()); root = undefined;
    await act(async () => old.resolve(envelope("ok", ["STALE"])));
    expect(host.textContent).toBe("");
    expect(document.querySelector('[role="menu"]')).toBeNull();
    expect(requests).toHaveLength(before);
  });

  it("keeps option loading issuer-scoped when navigating away from the filing view", async () => {
    const pending = deferred<unknown>();
    handler = (url) => url.pathname.endsWith("/filing-forms") ? pending.promise : fallback(url);
    await render(); await load(); await openForms(); await click("Facts");
    await act(async () => pending.resolve(envelope("ok", ["DEF 14A"])));
    expect(host.querySelector('[role="menu"]')).toBeNull();
    await click("Catalog"); await openForms();
    expect(formOption("DEF 14A")).toBeDefined();
    expect(formRequests()).toHaveLength(1);
  });

  it.each(["DEF 14A", "All"])("preserves menu focus from %s when a delayed refresh replaces choices", async (focused) => {
    vi.useFakeTimers();
    const refresh = deferred<unknown>();
    const forms = deferred<unknown>();
    await render(); await load(); await openForms();
    await key(formOption("All"), "Escape");
    handler = (url) => url.pathname.endsWith("/refresh") ? refresh.promise
      : url.pathname.endsWith("/filing-forms") ? forms.promise : fallback(url);
    await click("Refresh structured data");
    await key(button("Forms"), "ArrowUp");
    formOption(focused).focus();
    await act(async () => refresh.resolve(receipt));
    expect(button("Forms").getAttribute("aria-expanded")).toBe("true");
    expect(host.querySelector('[role="menu"]')?.textContent).toContain("Loading");
    expect(document.activeElement).toBe(formOption("All"));
    await key(document.activeElement!, "ArrowDown");
    expect(document.activeElement).toBe(formOption("All"));
    await act(async () => forms.resolve(envelope("ok", ["DEF 14A", "S-3"])));
    expect(document.activeElement).toBe(formOption("All"));
    await key(document.activeElement!, "ArrowDown");
    const option = formOption("DEF 14A");
    expect(document.activeElement).toBe(option);
    await act(async () => option.click());
    await settleFilters();
    expect(option.getAttribute("aria-checked")).toBe("true");
    expect(document.activeElement).toBe(option);
    expect(formRequests()).toHaveLength(2);
    expect(requests.filter(({ init }) => init.method === "POST")).toHaveLength(1);
    await key(document.activeElement!, "Escape");
    expect(button("Forms").getAttribute("aria-expanded")).toBe("false");
    expect(document.activeElement).toBe(button("Forms"));
  });

  it("supports arrow, Home/End, Escape and Tab navigation while choices stay independently checked", async () => {
    await render(); await load();
    const trigger = button("Forms");
    expect(trigger.getAttribute("aria-haspopup")).toBe("menu");
    await key(trigger, "ArrowDown");
    const menu = host.querySelector<HTMLElement>('[role="menu"]')!;
    expect(trigger.getAttribute("aria-controls")).toBe(menu.id);
    expect(document.activeElement).toBe(formOption("All"));
    await key(menu, "ArrowDown");
    expect(document.activeElement).toBe(formOption("10-K"));
    await act(async () => formOption("10-K").click());
    await key(menu, "End");
    expect(document.activeElement).toBe(formOption("SC 13G/A"));
    await act(async () => formOption("SC 13G/A").click());
    expect(formOption("10-K").getAttribute("aria-checked")).toBe("true");
    expect(formOption("SC 13G/A").getAttribute("aria-checked")).toBe("true");
    expect(trigger.getAttribute("aria-expanded")).toBe("true");
    await key(menu, "Home");
    expect(document.activeElement).toBe(formOption("All"));
    await key(menu, "Escape");
    expect(document.activeElement).toBe(trigger);
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
    await key(trigger, "ArrowUp");
    expect(document.activeElement).toBe(formOption("SC 13G/A"));
    await key(document.activeElement!, "Tab");
    expect(host.querySelector('[role="menu"]')).toBeNull();
    await openForms();
    await act(async () => document.body.dispatchEvent(new MouseEvent("mousedown", { bubbles: true })));
    expect(host.querySelector('[role="menu"]')).toBeNull();
  });

  it.each(["Enter", " "])("leaves %j activation to native trigger and option buttons", async (value) => {
    await render(); await load();
    async function activate(element: HTMLButtonElement) {
      expect(element).toBeInstanceOf(HTMLButtonElement);
      expect(element.type).toBe("button");
      expect(element.disabled).toBe(false);
      for (const type of ["keydown", "keyup"]) {
        const event = new KeyboardEvent(type, { key: value, bubbles: true, cancelable: true });
        await act(async () => element.dispatchEvent(event));
        expect(event.defaultPrevented).toBe(false);
      }
      // jsdom does not generate native keyboard clicks; exercise that click separately.
      await act(async () => element.click());
    }
    await activate(button("Forms"));
    expect(button("Forms").getAttribute("aria-expanded")).toBe("true");
    const option = formOption("DEF 14A");
    option.focus();
    await activate(option);
    expect(option.getAttribute("aria-checked")).toBe("true");
    expect(document.activeElement).toBe(option);
    expect(button("Forms").getAttribute("aria-expanded")).toBe("true");
    await activate(option);
    expect(option.getAttribute("aria-checked")).toBe("false");
  });

  it("keeps many selected forms in a fixed single-line trigger with the full value inspectable", async () => {
    vi.useFakeTimers();
    applyPanelStyles();
    await render(); await load();
    await chooseForms("10-K", "10-Q", "10-Q/A", "8-K", "DEF 14A", "SC 13G/A");
    const trigger = button("Forms");
    const value = trigger.querySelector<HTMLElement>(".sec-form-value")!;
    const summary = "10-K, 10-Q, 10-Q/A, 8-K, DEF 14A, SC 13G/A";
    expect(value.textContent).toBe(summary);
    expect(value.title).toBe(summary);
    expect(trigger.getAttribute("aria-describedby")).toBe(value.id);
    expect.soft(getComputedStyle(trigger).height).toBe("32px");
    expect.soft(getComputedStyle(trigger).minHeight).toBe("32px");
    expect.soft(getComputedStyle(trigger).boxSizing).toBe("border-box");
    expect.soft(getComputedStyle(trigger).whiteSpace).toBe("nowrap");
    const content = getComputedStyle(value.parentElement!);
    expect.soft(content.display).toMatch(/^(inline-)?flex$/);
    expect.soft(content.minWidth).toBe("0px");
    expect.soft(content.width).toBe("100%");
    const style = getComputedStyle(value);
    expect.soft(style.minWidth).toBe("0px");
    expect.soft(style.flexShrink).toBe("1");
    expect.soft(style.whiteSpace).toBe("nowrap");
    expect.soft(style.overflow).toBe("hidden");
    expect.soft(style.textOverflow).toBe("ellipsis");
    expect.soft(getComputedStyle(trigger.querySelector("svg")!).flexShrink).toBe("0");
    const menu = await openForms();
    expect([...menu.querySelectorAll('[aria-checked="true"]')].map(formCode)).toEqual([
      "10-K", "10-Q", "10-Q/A", "8-K", "DEF 14A", "SC 13G/A",
    ]);
  });

  it.each(["en", "zh-Hant"])("keeps the %s dropdown bounded with localized All and status", async (locale) => {
    applyPanelStyles();
    await render(locale); await change("CIK", "123"); await click(locale === "en" ? "Load local" : "讀取本機");
    const menu = await openForms(locale === "en" ? "Forms" : "申報類型");
    expect(formOption(locale === "en" ? "All" : "全部").getAttribute("aria-checked")).toBe("true");
    expect(menu.querySelector('[role="status"]')?.textContent).toBe(locale === "en" ? "Available" : "可用");
    expect(getComputedStyle(menu).maxHeight).toBe("260px");
    expect(getComputedStyle(menu).overflowY).toBe("auto");
    expect(getComputedStyle(menu.parentElement!).minWidth).toBe("0px");
  });

  it("keeps group headings in flow so they cannot cover keyboard-focused choices", async () => {
    applyPanelStyles();
    await render(); await load(); const menu = await openForms();
    for (const heading of menu.querySelectorAll(".sec-form-group-label")) {
      expect(getComputedStyle(heading).position).not.toMatch(/sticky|absolute|fixed/);
    }
  });

  it("retains text-input debounce for concepts", async () => {
    vi.useFakeTimers();
    await render(); await load(); await click("Facts");
    await change("Concepts", "Asset"); await settleFilters(200);
    await change("Concepts", "Assets"); await settleFilters(299);
    expect(recordRequests()).toHaveLength(2);
    await settleFilters(1);
    expect(recordRequests()).toHaveLength(3);
    expect(recordRequests().at(-1)?.url.searchParams.getAll("concepts")).toEqual(["Assets"]);
    expect(formRequests()).toHaveLength(1);
  });
});

describe("SEC structured storage", () => {
  it("debounces multiple form selections beside the results and queries only the latest local filters", async () => {
    vi.useFakeTimers();
    handler = (url) => url.searchParams.has("forms") ? envelope("ok", [filing("filtered")]) : fallback(url);
    await render(); await load();
    expect(host.querySelector('[role="tabpanel"]')?.contains(button("Forms"))).toBe(true);
    await chooseForms("10-Q");
    await settleFilters(200);
    await chooseForms("10-Q", "8-K");
    await settleFilters(299);
    expect(recordRequests()).toHaveLength(1);
    expect(host.textContent).not.toContain("first.htm");
    await settleFilters(1);
    expect(recordRequests()).toHaveLength(2);
    expect(formRequests()).toHaveLength(1);
    expect(recordRequests().at(-1)?.url.searchParams.getAll("forms")).toEqual(["10-Q", "8-K"]);
    expect(host.textContent).toContain("filtered.htm");
    expect(requests.every(({ init }) => (init.method ?? "GET") === "GET" && init.body === undefined)).toBe(true);
    await settleFilters(1000);
    expect(recordRequests()).toHaveLength(2);
  });

  it("automatically applies filing dates and amendment selection to stored results", async () => {
    vi.useFakeTimers();
    handler = (url) => url.searchParams.get("include_amendments") === "false"
      ? envelope("ok", [filing("dated")]) : fallback(url);
    await render(); await load();
    await change("Filed from", "2025-01-01");
    await change("Filed to", "2026-03-01");
    await act(async () => host.querySelector<HTMLInputElement>('.sec-checkbox input')!.click());
    await settleFilters();
    expect([...recordRequests().at(-1)!.url.searchParams]).toEqual([
      ["filed_from", "2025-01-01"], ["filed_to", "2026-03-01"],
      ["include_amendments", "false"], ["limit", "20"],
    ]);
    expect(host.textContent).toContain("dated.htm");
    expect(recordRequests()).toHaveLength(2);
    expect(requests.some(({ init }) => init.method === "POST")).toBe(false);
  });

  it("automatically applies concepts, as-of date and revisions without acquiring SEC data", async () => {
    vi.useFakeTimers();
    handler = (url) => url.searchParams.get("revisions") === "all" ? envelope("ok", [{
      fact_id: "revised", namespace: "us-gaap", concept: "Revenues", value: "999.00100",
      unit: "USD", end: "2025-12-31", filed_date: "2026-02-01", accession: "000-1",
    }]) : fallback(url);
    await render(); await load(); await click("Facts");
    expect(host.querySelector('[role="tabpanel"]')?.contains(input("Concepts"))).toBe(true);
    await change("Concepts", "us-gaap:Revenues Assets");
    await change("Available as of", "2026-03-01");
    await select("Revisions", "all");
    await settleFilters();
    expect([...recordRequests().at(-1)!.url.searchParams]).toEqual([
      ["concepts", "us-gaap:Revenues"], ["concepts", "Assets"], ["as_of", "2026-03-01"],
      ["revisions", "all"], ["limit", "40"],
    ]);
    expect(host.textContent).toContain("999.00100");
    expect(recordRequests()).toHaveLength(3);
    expect(requests.some(({ init }) => init.method === "POST")).toBe(false);
  });

  it.each(["success", "failure"])("ignores a late %s from an older automatic filter read", async (outcome) => {
    vi.useFakeTimers();
    const oldPage = deferred<unknown>();
    const oldStatus = deferred<unknown>();
    let delayStatus = false;
    handler = (url) => {
      if (delayStatus && /\/sec-research\/\d+$/.test(url.pathname)) return oldStatus.promise;
      if (url.searchParams.get("forms") === "10-K") return oldPage.promise;
      if (url.searchParams.get("forms") === "10-Q") return envelope("ok", [filing("latest-filter")]);
      return fallback(url);
    };
    await render(); await load();
    delayStatus = true;
    await chooseForms("10-K"); await settleFilters();
    expect(recordRequests()).toHaveLength(2);
    delayStatus = false;
    await chooseForms("10-Q"); await settleFilters();
    expect(host.textContent).toContain("latest-filter.htm");
    await act(async () => {
      oldPage.resolve(outcome === "success" ? envelope("ok", [filing("stale-filter")], "stale-cursor")
        : new Response(JSON.stringify({ detail: { code: "stale_filter_error" } }), { status: 422 }));
      oldStatus.resolve({ ...envelope("partial"), gaps: [{ code: "stale_status" }] });
    });
    expect(host.textContent).toContain("latest-filter.htm");
    expect(host.textContent).not.toContain("stale");
    expect(button("Next page").disabled).toBe(true);
    expect(button("Load local").disabled).toBe(false);
  });

  it("invalidates an in-flight cursor page immediately, before the new debounce fires", async () => {
    vi.useFakeTimers();
    const old = deferred<unknown>();
    handler = (url) => url.searchParams.has("cursor") ? old.promise : fallback(url);
    await render(); await load(); await click("Next page");
    await chooseForms("10-Q");
    await act(async () => old.resolve(envelope("ok", [filing("stale-page")], "stale-cursor")));
    expect(host.textContent).not.toContain("stale-page");
    expect(button("Next page").disabled).toBe(true);
    expect(host.querySelector(".sec-pagination > span")?.textContent).toBe("Page 1");
    await settleFilters();
    expect(recordRequests()).toHaveLength(3);
    expect(recordRequests().at(-1)?.url.searchParams.has("cursor")).toBe(false);
    expect(host.textContent).toContain("first.htm");
  });

  it("cancels pending filter reads on tab navigation and reads the selected view once", async () => {
    vi.useFakeTimers();
    await render(); await load(); await chooseForms("10-Q");
    await click("Facts");
    expect(host.textContent).toContain("1234567890123456789.123");
    await settleFilters(1000);
    expect(recordRequests().map(({ url }) => url.pathname)).toEqual([
      "/sec-research/0000000123/filings", "/sec-research/0000000123/facts",
    ]);
    await change("Concepts", "Assets"); await click("Catalog");
    await settleFilters(1000);
    expect(recordRequests()).toHaveLength(3);
    expect(recordRequests().at(-1)?.url.searchParams.getAll("forms")).toEqual(["10-Q"]);
    expect(host.textContent).toContain("first.htm");
  });

  it("ignores an automatic filter response after navigating to another view", async () => {
    vi.useFakeTimers();
    const old = deferred<unknown>();
    handler = (url) => url.searchParams.has("forms") ? old.promise : fallback(url);
    await render(); await load(); await chooseForms("10-Q"); await settleFilters();
    expect(recordRequests()).toHaveLength(2);
    await click("Facts");
    await act(async () => old.resolve(envelope("ok", [filing("stale-catalog")])));
    expect(host.textContent).toContain("1234567890123456789.123");
    expect(host.textContent).not.toContain("stale-catalog");
  });

  it("cancels a pending debounce on unmount without issuing another local read", async () => {
    vi.useFakeTimers();
    await render(); await load(); await chooseForms("10-Q");
    const before = requests.length;
    await act(async () => root!.unmount()); root = undefined;
    await settleFilters(1000);
    expect(requests).toHaveLength(before);
    expect(host.textContent).toBe("");
  });

  it("ignores automatic filter completion after unmount", async () => {
    vi.useFakeTimers();
    const old = deferred<unknown>();
    handler = (url) => url.searchParams.has("forms") ? old.promise : fallback(url);
    await render(); await load(); await chooseForms("10-Q"); await settleFilters();
    expect(recordRequests()).toHaveLength(2);
    const before = requests.length;
    await act(async () => root!.unmount()); root = undefined;
    await act(async () => old.resolve(envelope("ok", [filing("unmounted")])));
    await settleFilters(1000);
    expect(requests).toHaveLength(before);
    expect(host.textContent).toBe("");
  });

  it.each(["456", "invalid", ""])("cancels pending filtering when CIK changes to %s and waits for local load", async (cik) => {
    vi.useFakeTimers();
    await render(); await load(); await chooseForms("10-Q");
    await change("CIK", cik); await settleFilters(1000);
    expect(button("Forms").disabled).toBe(true);
    expect(recordRequests()).toHaveLength(1);
    expect(host.textContent).not.toContain("first.htm");
    expect(button("Load local").disabled).toBe(cik !== "456");
    if (cik === "456") {
      await click("Load local");
      await chooseForms("8-K"); await settleFilters();
      expect(recordRequests().at(-1)?.url.pathname).toBe("/sec-research/0000000456/filings");
      expect(recordRequests().at(-1)?.url.searchParams.getAll("forms")).toEqual(["8-K"]);
      expect(host.textContent).toContain("first.htm");
    }
    expect(requests.some(({ init }) => init.method === "POST")).toBe(false);
  });

  it("ignores an automatic filter response after a different CIK is loaded", async () => {
    vi.useFakeTimers();
    const old = deferred<unknown>();
    handler = (url) => url.pathname === "/sec-research/0000000123/filings" && url.searchParams.has("forms")
      ? old.promise : fallback(url);
    await render(); await load(); await chooseForms("10-Q"); await settleFilters();
    expect(recordRequests()).toHaveLength(2);
    await load("456");
    await act(async () => old.resolve(envelope("ok", [filing("stale-issuer-filter")])));
    expect(host.textContent).toContain("first.htm");
    expect(host.textContent).not.toContain("stale-issuer-filter");
    expect(recordRequests().at(-1)?.url.pathname).toBe("/sec-research/0000000456/filings");
  });

  it("an explicit local load consumes the pending debounce without a duplicate read", async () => {
    vi.useFakeTimers();
    await render(); await load(); await chooseForms("10-Q"); await click("Load local");
    await settleFilters(1000);
    expect(recordRequests()).toHaveLength(2);
    expect(recordRequests().at(-1)?.url.searchParams.getAll("forms")).toEqual(["10-Q"]);
    expect(host.textContent).toContain("first.htm");
  });

  it.each(["en", "zh-Hant"])("offers only the official browser source link for filing documents in %s", async (locale) => {
    await render(locale);
    await change("CIK", "123"); await click(locale === "en" ? "Load local" : "讀取本機");
    const row = host.querySelector(".sec-record-scroll tbody tr")!;
    const link = row.querySelector<HTMLAnchorElement>("a")!;
    expect(row.textContent).toContain("first.htm");
    expect(link.href).toBe("https://www.sec.gov/Archives/edgar/data/123/report.htm");
    expect(link.target).toBe("_blank");
    expect(link.rel).toBe("noopener noreferrer");
    expect(link.getAttribute("aria-label")).toBe(locale === "en" ? "SEC original" : "SEC 原文");
    expect(link.title).toBe(locale === "en" ? "SEC original" : "SEC 原文");
    expect(host.querySelectorAll(".sec-record-scroll th")[2]?.textContent).toBe(locale === "en" ? "SEC original" : "SEC 原文");
    expect(row.querySelectorAll("button")).toHaveLength(0);
    const before = requests.length;
    link.addEventListener("click", (event) => event.preventDefault());
    await act(async () => link.click());
    expect(requests).toHaveLength(before);
    expect(host.querySelector('[aria-label="Filing reader"], [aria-label="申報文件閱讀器"]')).toBeNull();
  });

  it("ignores unrelated source completion", async () => {
    let news = { ...scheduled, running: true };
    handler = (url) => url.pathname === "/schedule"
      ? { sources: { sec_research_filings: scheduled, polygon_news: news } } : fallback(url);
    await render(); await load(); await change("Capture budget", "150");
    const before = requests.filter(({ url }) => url.pathname.startsWith("/sec-research"));
    news = { ...news, running: false, last_result: { source: "polygon_news", status: "succeeded", at: "2026-09-13T02:00:00Z" } };
    await act(async () => window.dispatchEvent(new Event("focus")));
    expect(requests.filter(({ url }) => url.pathname.startsWith("/sec-research"))).toEqual(before);
    expect(input("Capture budget").value).toBe("150");
  });

  it("defers completion capacity refresh until an in-flight budget save settles", async () => {
    const saved = deferred<unknown>();
    handler = (url, init) => url.pathname === "/sec-research/config" && init.method === "PUT"
      ? saved.promise : fallback(url);
    await render(); await load(); await change("Capture budget", "150");
    scheduled = { ...scheduled, running: true };
    await act(async () => window.dispatchEvent(new Event("focus")));
    await click("Save budget");
    expect(input("Capture budget").disabled).toBe(true);
    const configReads = () => requests.filter(({ url, init }) => url.pathname === "/sec-research/config" && init.method !== "PUT").length;
    const before = configReads();
    scheduled = { ...scheduled, running: false, last_result: { source: "sec_research_filings", status: "succeeded", at: "2026-09-13T02:00:00Z" } };
    await act(async () => window.dispatchEvent(new Event("focus")));
    expect(configReads()).toBe(before);
    expect(input("Capture budget").value).toBe("150");
    budget = 150 * 1024**3;
    await act(async () => saved.resolve({ capture_budget_bytes: budget, capacity }));
    // Save confirmation and deferred schedule capacity observation have separate ownership.
    expect(configReads()).toBe(before + 2);
    expect(input("Capture budget").value).toBe("150");
    expect(input("Capture budget").disabled).toBe(false);
  });

  it("uses shared SEC controls and refreshes only batch status/capacity after its terminal transition", async () => {
    await render("en", true);
    expect(host.querySelector('[data-source-id="sec_research_filings"]')?.textContent).toContain("SEC Research");
    expect(host.querySelector(".sec-schedule-status")).not.toBeNull();
    await load(); await click("Next page");
    await change("Capture budget", "150");
    const beforeRecords = host.querySelector(".sec-record-scroll")?.textContent;
    const localReads = () => requests.filter(({ url }) => /\/sec-research\/\d/.test(url.pathname)).length;
    const beforeReads = localReads();
    scheduled = { ...scheduled, running: true };
    await act(async () => window.dispatchEvent(new Event("focus")));
    const beforeStatus = requests.filter(({ url }) => url.pathname.endsWith("schedule-status")).length;
    batchStatus = { last_acquisition_at: "2026-09-13T01:00:00Z", last_completed_batch: null,
      last_attempt: { status: "partial", started_at: "2026-09-13T01:00:00Z", finished_at: "2026-09-13T02:00:00Z",
        universe_tickers: ["ONE", "TWO", "MISSING"], universe_status: "available",
        attempted_ciks: ["1", "2"], confirmed_ciks: ["1"], failed_ciks: ["2"], deferred_ciks: [],
        unresolved: [{ ticker: "MISSING", code: "issuer_not_found", candidates: [] }],
        filing_count: 4, fact_count: 9, request_count: 5, gaps: [{ code: "sec_rate_limited" }], stop_reason: null } };
    scheduled = { ...scheduled, running: false, last_attempt_at: "2026-09-13T01:00:00Z",
      last_result: { source: "sec_research_filings", status: "partial", at: "2026-09-13T02:00:00Z" } };
    await act(async () => window.dispatchEvent(new Event("focus")));
    expect(requests.filter(({ url }) => url.pathname.endsWith("schedule-status"))).toHaveLength(beforeStatus + 1);
    expect(input("Capture budget").value).toBe("150");
    expect(host.querySelector(".sec-record-scroll")?.textContent).toBe(beforeRecords);
    expect(localReads()).toBe(beforeReads);
    expect(host.querySelector(".sec-schedule-status")?.textContent).toContain("sec_rate_limited");
    expect(host.querySelector(".sec-schedule-status")?.textContent).toContain("MISSING");
    expect(requests.filter(({ init }) => init.method === "POST")).toHaveLength(0);
  });
  it("limits pagination counter sizing to the counter, excluding button icon wrappers", async () => {
    applyPanelStyles();
    await render(); await load();
    const counter = host.querySelector<HTMLElement>(".sec-pagination > span")!;
    expect(getComputedStyle(counter).minWidth).toBe("64px");
    const icons = host.querySelectorAll<HTMLElement>(".sec-pagination button .ui-button-icon");
    expect(icons).toHaveLength(2);
    for (const icon of icons) expect(getComputedStyle(icon).minWidth).not.toBe("64px");
  });

  it("puts the original-source link third, before the remaining filing metadata", async () => {
    const id = "secfiling_" + "a".repeat(64);
    handler = (url) => url.pathname.endsWith("/filings") ? envelope("ok", [{
      ...filing(id), accession: "0000000123-26-000001", primary_document: "annual-report.htm",
    }]) : fallback(url);
    await render(); await load();
    expect([...host.querySelectorAll(".sec-record-scroll th")].map((cell) => cell.textContent)).toEqual([
      "Form", "Filed date", "SEC original", "Report date", "Accepted at", "Primary document", "Accession", "Filing ID",
    ]);
    const cells = [...host.querySelectorAll(".sec-record-scroll tbody td")];
    expect(cells.map((cell) => cell.textContent)).toEqual([
      "10-K", "2026-02-01", "", "2025-12-31", "2026-02-01T10:00:00Z", "annual-report.htm", "0000000123-26-000001", id,
    ]);
    expect(cells[2].querySelector("a")?.href).toBe("https://www.sec.gov/Archives/edgar/data/123/report.htm");
  });

  it("gives original-source links theme foreground contrast, hover feedback and a keyboard focus ring", async () => {
    applyPanelStyles();
    await render(); await load();
    const link = host.querySelector<HTMLAnchorElement>(".sec-record-scroll a")!;
    // jsdom does not resolve CSS variables or simulate :focus-visible reliably.
    const rules = [...stylesheet!.sheet!.cssRules] as CSSStyleRule[];
    const style = (selector: string) => rules.find((rule) => rule.selectorText === selector)?.style;
    expect(link.matches(".sec-record-scroll a")).toBe(true);
    expect.soft(style(".sec-record-scroll a")?.color).toBe("var(--fg)");
    expect.soft(style(".sec-record-scroll a:hover")?.background).toBe("var(--panel2)");
    expect.soft(style(".sec-record-scroll a:focus-visible")?.outline).toBe("2px solid var(--accent)");
    expect.soft(style(".sec-record-scroll a:focus-visible")?.outlineOffset).toBe("2px");
    link.focus();
    expect(document.activeElement).toBe(link);
  });

  it("leads facts with concept value unit and end while retaining every field and full ID", async () => {
    const id = "secfact_" + "b".repeat(64);
    const fact = {
      fact_id: id, namespace: "us-gaap", concept: "Assets", value: "1234567890123456789.123",
      unit: "EUR", start: "2025-01-01", end: "2025-12-31", filed_date: "2026-02-01", accession: "0000000123-26-000001",
    };
    handler = (url) => url.pathname.endsWith("/facts") ? envelope("ok", [fact]) : fallback(url);
    await render(); await load(); await click("Facts");
    expect([...host.querySelectorAll(".sec-record-scroll th")].map((cell) => cell.textContent)).toEqual([
      "Concept", "Reported value", "Unit", "End", "Start", "Namespace", "Filed date", "Accession", "Fact ID",
    ]);
    expect([...host.querySelectorAll(".sec-record-scroll tbody td")].map((cell) => cell.textContent)).toEqual([
      "Assets", "1234567890123456789.123", "EUR", "2025-12-31", "2025-01-01", "us-gaap", "2026-02-01", "0000000123-26-000001", id,
    ]);
  });

  it.each(["Catalog", "Facts"])("bounds the %s table viewport with both scroll axes and pagination outside", async (view) => {
    applyPanelStyles();
    const records = Array.from({ length: view === "Catalog" ? 20 : 40 }, (_, index) => view === "Catalog"
      ? filing("secfiling_" + "a".repeat(64) + index)
      : { fact_id: "secfact_" + "b".repeat(64) + index, namespace: "us-gaap", concept: "Assets", value: "1234567890123456789.123", unit: "EUR", end: "2025-12-31" });
    handler = (url) => /\/(filings|facts)$/.test(url.pathname) ? envelope("ok", records, "next") : fallback(url);
    await render(); await load();
    if (view === "Facts") await click(view);
    const scroll = host.querySelector<HTMLElement>(".sec-record-scroll")!;
    const style = getComputedStyle(scroll);
    expect(style.maxHeight).toBe("clamp(360px, 60vh, 480px)");
    expect(style.overflowX).toBe("auto");
    expect(style.overflowY).toBe("auto");
    expect(scroll.querySelectorAll("tbody tr")).toHaveLength(records.length);
    expect(scroll.contains(button("Next page"))).toBe(false);
    expect(scroll.compareDocumentPosition(button("Next page")) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it.each(["Catalog", "Facts"])("shows an actual unavailable-null %s response without observed-empty rows", async (view) => {
    handler = (url) => /\/(filings|facts)$/.test(url.pathname) ? {
      status: "unavailable", data: null, gaps: [{ code: "sec_research_not_installed" }],
      observed_at: null, coverage: {}, next_cursor: null,
    } : fallback(url);
    await render(); await load();
    if (view === "Facts") await click(view);
    const panel = host.querySelector('[role="tabpanel"]')!;
    expect(panel.textContent).toContain("Unavailable");
    expect(panel.textContent).toContain("sec_research_not_installed");
    expect(panel.textContent).not.toContain("Observed empty");
    expect(panel.querySelector("table")).toBeNull();
    expect(button("Next page").disabled).toBe(true);
  });

  it("mounts with only stored config/schedule GETs, actual accounting, and no issuer guessing", async () => {
    await render();
    expect(requests.map(({ url, init }) => [url.pathname, init.method ?? "GET"])).toEqual([
      ["/sec-research/config", "GET"], ["/sec-research/schedule-status", "GET"], ["/schedule", "GET"],
    ]);
    expect(input("CIK").value).toBe("");
    expect(input("Capture budget").value).toBe("100");
    for (const [label, value] of [["Stored objects", "120"], ["Reservations", "30"], ["Orphans", "7"], ["Accounted usage", "157"]]) {
      const term = [...host.querySelectorAll("dt")].find((el) => el.textContent === label);
      expect(term?.nextElementSibling?.textContent).toContain(value);
    }
    expect(button("Load local").disabled).toBe(true);
    await change("CIK", "AAPL");
    expect(button("Load local").disabled).toBe(true);
  });

  it("loads status and whole catalog rows only on command, then preserves exact fact strings", async () => {
    await render(); await load(" cik:123 ");
    expect(host.textContent).toContain("first.htm");
    expect(host.textContent).toContain("accession-first");
    expect(host.textContent).toContain("history.json");
    expect(host.textContent).toContain("2026");
    await click("Facts");
    expect(host.textContent).toContain("1234567890123456789.123");
    expect(host.textContent).toContain("EUR");
    expect(requests.every(({ init }) => !init.method || init.method === "GET")).toBe(true);
  });

  it.each(["empty", "partial", "unavailable"])("keeps %s query state distinct", async (state) => {
    handler = (url) => url.pathname.endsWith("/filings") ? envelope(state) : fallback(url);
    await render(); await load();
    const region = host.querySelector('[role="tabpanel"]');
    expect(region?.textContent).toContain({ empty: "Observed empty", partial: "Partial", unavailable: "Unavailable" }[state]);
    if (state === "partial") expect(region?.textContent).toContain("history_pending");
    if (state !== "empty") expect(region?.textContent).not.toContain("Observed empty");
  });

  it("keeps unknown distinct from zero capacity and does not repair configuration errors", async () => {
    handler = (url) => url.pathname.endsWith("/config") ? new Response(JSON.stringify({ detail: { code: "sec_config_invalid" } }), { status: 503 }) : fallback(url);
    await render();
    expect(host.textContent).toContain("sec_config_invalid");
    expect(host.textContent).toContain("Unknown");
    expect(input("Capture budget").value).toBe("");
    expect(button("Save budget").disabled).toBe(true);
    await load();
    expect(host.textContent).toContain("first.htm");
  });

  it("saves a budget above 100 GiB as exact bytes, then confirms the server value", async () => {
    handler = (url, init) => {
      if (init.method === "PUT") { budget = 161061273600; return { capture_budget_bytes: budget }; }
      return fallback(url);
    };
    await render(); await change("Capture budget", "150"); await click("Save budget");
    expect(requests.find(({ init }) => init.method === "PUT")?.init.body).toBe('{"capture_budget_bytes":161061273600}');
    expect(requests.map(({ init }) => init.method ?? "GET")).toEqual(["GET", "GET", "GET", "PUT", "GET"]);
    expect(host.textContent).toContain("Budget saved");
    expect(input("Capture budget").value).toBe("150");
  });

  it("reopens non-GiB-aligned persisted bytes without rounding and saves one byte exactly", async () => {
    budget = 107374182401;
    await render();
    expect(input("Capture budget").value).toBe("107374182401");
    expect(host.querySelector<HTMLSelectElement>('select[aria-label="Budget unit"]')?.value).toBe("bytes");
    await change("Capture budget", "1"); await click("Save budget");
    expect(requests.find(({ init }) => init.method === "PUT")?.init.body).toBe('{"capture_budget_bytes":1}');
    await load(); expect(host.textContent).toContain("first.htm");
  });

  it.each(["0", "-1", "0.0000000001", "9007199254740992", "1e3", "100.0000000000000000000001"])("rejects invalid GiB draft %s without PUT", async (value) => {
    await render(); await change("Capture budget", value);
    expect(button("Save budget").disabled).toBe(true);
    expect(requests.some(({ init }) => init.method === "PUT")).toBe(false);
  });

  it("accepts exact fractional GiB and rejects fractional bytes rather than rounding", async () => {
    await render(); await change("Capture budget", "0.000000000931322574615478515625");
    await click("Save budget");
    expect(requests.find(({ init }) => init.method === "PUT")?.init.body).toBe('{"capture_budget_bytes":1}');
    await select("Budget unit", "bytes"); await change("Capture budget", "1.1");
    expect(button("Save budget").disabled).toBe(true);
  });

  it("shows save errors without claiming success and preserves the dirty draft during refresh", async () => {
    handler = (url, init) => init.method === "PUT" ? new Response(JSON.stringify({ detail: { code: "permission_denied" } }), { status: 403 }) : fallback(url);
    await render(); await load(); await change("Capture budget", "155"); await click("Save budget");
    expect(host.textContent).toContain("permission_denied");
    expect(host.textContent).not.toContain("Budget saved");
    await click("Refresh structured data");
    expect(input("Capture budget").value).toBe("155");
  });

  it("passes opaque cursors unchanged, reopens previous pages and resets on filter change", async () => {
    vi.useFakeTimers();
    handler = (url) => url.searchParams.has("forms")
      ? envelope("ok", [filing(url.searchParams.has("cursor") ? "filtered-next" : "filtered-first")],
        url.searchParams.has("cursor") ? null : "filtered+/= &cursor")
      : url.searchParams.has("cursor") ? envelope("ok", [filing("second")]) : fallback(url);
    await render(); await load(); await click("Next page");
    expect(requests.at(-1)?.url.searchParams.get("cursor")).toBe("opaque+/= &token");
    expect(host.textContent).toContain("second.htm");
    await click("Previous page"); expect(host.textContent).toContain("first.htm");
    await click("Next page"); await chooseForms("10-Q");
    expect(host.textContent).not.toContain("second.htm");
    await settleFilters();
    const last = requests.filter(({ url }) => url.pathname.endsWith("/filings")).at(-1)!.url;
    expect(last.searchParams.has("cursor")).toBe(false);
    expect(last.searchParams.getAll("forms")).toEqual(["10-Q"]);
    expect(button("Previous page").disabled).toBe(true);
    expect(host.querySelector(".sec-pagination > span")?.textContent).toBe("Page 1");
    expect(host.textContent).toContain("filtered-first.htm");
    await click("Next page");
    expect(recordRequests().at(-1)?.url.searchParams.get("cursor")).toBe("filtered+/= &cursor");
    expect(host.textContent).toContain("filtered-next.htm");
    expect(host.textContent).not.toContain("second.htm");
  });

  it("preserves conflicting catalog variants across cached forward and back pages without key warnings", async () => {
    const first = [
      filing("conflict"), { ...filing("conflict"), form: "10-Q" },
      ...Array.from({ length: 18 }, (_, index) => filing(`first-${index}`)),
    ];
    const expectedFirst = [
      ["10-K", "2026-02-01", "", "2025-12-31", "2026-02-01T10:00:00Z", "conflict.htm", "accession-conflict", "conflict"],
      ["10-Q", "2026-02-01", "", "2025-12-31", "2026-02-01T10:00:00Z", "conflict.htm", "accession-conflict", "conflict"],
      ...Array.from({ length: 18 }, (_, index) => [
        "10-K", "2026-02-01", "", "2025-12-31", "2026-02-01T10:00:00Z", `first-${index}.htm`, `accession-first-${index}`, `first-${index}`,
      ]),
    ];
    const expectedNext = [["10-K", "2026-02-01", "", "2025-12-31", "2026-02-01T10:00:00Z", "next-page.htm", "accession-next-page", "next-page"]];
    handler = (url) => url.pathname.endsWith("/filings") ? {
      ...envelope("partial", url.searchParams.has("cursor") ? [filing("next-page")] : first,
        url.searchParams.has("cursor") ? null : "conflict+/= &cursor"),
      gaps: [{ code: "filing_metadata_conflict" }],
    } : fallback(url);
    const expectRows = (expected: string[][]) => {
      const rows = [...host.querySelectorAll(".sec-record-scroll tbody tr")];
      expect.soft(rows).toHaveLength(expected.length);
      expect.soft(rows.map((row) => [...row.querySelectorAll("td")].map((cell) => cell.textContent))).toEqual(expected);
      expect.soft(host.querySelector('[role="tabpanel"]')?.textContent).toContain("filing_metadata_conflict");
    };
    const consoleError = vi.spyOn(console, "error");
    try {
      await render(); await load();
      expectRows(expectedFirst);
      expect(button("Previous page").disabled).toBe(true);
      await click("Next page");
      expectRows(expectedNext);
      expect(button("Next page").disabled).toBe(true);
      const catalogRequests = requests.filter(({ url }) => url.pathname.endsWith("/filings"));
      expect(catalogRequests.map(({ url }) => url.searchParams.get("cursor"))).toEqual([null, "conflict+/= &cursor"]);
      expect(catalogRequests.map(({ url }) => url.searchParams.get("limit"))).toEqual(["20", "20"]);
      const requestCount = requests.length;
      handler = (url) => url.pathname.endsWith("/filings") ? envelope("ok", [filing("new-receipt")]) : fallback(url);
      await click("Previous page");
      expectRows(expectedFirst);
      expect(requests).toHaveLength(requestCount);
      expect(button("Previous page").disabled).toBe(true);
      await click("Next page");
      expectRows(expectedNext);
      expect(requests).toHaveLength(requestCount);
      expect(button("Next page").disabled).toBe(true);
      expect(consoleError).not.toHaveBeenCalled();
    } finally {
      consoleError.mockRestore();
    }
  });

  it("refresh and resume have distinct payloads and reset pages to the new receipt", async () => {
    await render(); await load(); await click("Next page");
    await click("Refresh structured data");
    expect(button("Previous page").disabled).toBe(true);
    expect(host.textContent).toContain("history.json");
    await click("Resume refresh");
    expect(requests.filter(({ init }) => init.method === "POST").map(({ init }) => init.body)).toEqual(['{"resume":false}', '{"resume":true}']);
    expect(requests.filter(({ url }) => url.pathname.endsWith("/filings")).at(-1)?.url.searchParams.has("cursor")).toBe(false);
  });

  it("rejects a delayed old issuer read after selection changes", async () => {
    const old = deferred<unknown>();
    handler = (url) => url.pathname === "/sec-research/0000000123/filings" ? old.promise : fallback(url);
    await render(); await load(); await change("CIK", "456"); await click("Load local");
    await act(async () => old.resolve(envelope("ok", [filing("stale-issuer")])));
    expect(host.textContent).not.toContain("stale-issuer");
    expect(host.textContent).toContain("first.htm");
  });

  it("blocks duplicate refresh and ignores its stale response after changing CIK", async () => {
    const pending = deferred<unknown>();
    handler = (url) => url.pathname.endsWith("/refresh") ? pending.promise : fallback(url);
    await render(); await load(); await click("Refresh structured data");
    expect(button("Refresh structured data").disabled).toBe(true);
    expect(button("Resume refresh").disabled).toBe(true);
    await click("Refresh structured data");
    expect(requests.filter(({ init }) => init.method === "POST")).toHaveLength(1);
    await change("CIK", "456"); await click("Load local");
    expect(button("Load local").disabled).toBe(false);
    await act(async () => pending.resolve({ ...receipt, gaps: [{ code: "stale_refresh" }] }));
    expect(host.textContent).not.toContain("stale_refresh");
    expect(button("Refresh structured data").disabled).toBe(false);
    expect(requests.filter(({ url }) => url.pathname === "/sec-research/0000000123/filings")).toHaveLength(1);
  });

  it("marks connection loss unconfirmed and offers a GET reread without retrying POST", async () => {
    handler = (url) => { if (url.pathname.endsWith("/refresh")) throw new TypeError("connection lost"); return fallback(url); };
    await render(); await load(); await click("Refresh structured data");
    expect(host.textContent).toContain("Outcome unconfirmed");
    await click("Reread stored status");
    expect(requests.filter(({ init }) => init.method === "POST")).toHaveLength(1);
    expect(requests.filter(({ url }) => url.pathname === "/sec-research/0000000123")).toHaveLength(2);
  });

  it("ignores pending read completion after unmount", async () => {
    const pending = deferred<unknown>();
    handler = (url) => url.pathname.endsWith("/filings") ? pending.promise : fallback(url);
    await render(); await load();
    await act(async () => root!.unmount()); root = undefined;
    await act(async () => pending.resolve(envelope()));
    expect(host.textContent).toBe("");
  });

  it("accepts the current issuer refresh receipt after an intervening stored reread", async () => {
    const pending = deferred<unknown>();
    handler = (url) => url.pathname.endsWith("/refresh") ? pending.promise : fallback(url);
    await render(); await load(); await click("Refresh structured data");
    await click("Load local");
    await act(async () => pending.resolve({ ...receipt, gaps: [{ code: "current_refresh_receipt" }] }));
    expect(host.textContent).toContain("current_refresh_receipt");
    expect(button("Previous page").disabled).toBe(true);
  });

  it("refresh completion reloads the current filters rather than the command-time filters", async () => {
    vi.useFakeTimers();
    const pending = deferred<unknown>();
    handler = (url) => url.pathname.endsWith("/refresh") ? pending.promise : fallback(url);
    await render(); await load(); await click("Refresh structured data");
    await chooseForms("10-Q");
    await act(async () => pending.resolve(receipt));
    const latest = requests.filter(({ url }) => url.pathname.endsWith("/filings")).at(-1)!.url;
    expect(latest.searchParams.getAll("forms")).toEqual(["10-Q"]);
    expect(latest.searchParams.has("cursor")).toBe(false);
    expect(host.textContent).toContain("Refresh receipt");
    await settleFilters(1000);
    expect(recordRequests()).toHaveLength(2);
    expect(requests.filter(({ init }) => init.method === "POST")).toHaveLength(1);
  });

  it("keeps budget confirmation owned by the save when refresh completes during PUT", async () => {
    const pending = deferred<unknown>();
    handler = (url, init) => init.method === "PUT" ? pending.promise : fallback(url);
    await render(); await load(); await change("Capture budget", "150"); await click("Save budget");
    await click("Refresh structured data");
    budget = 161061273600;
    await act(async () => pending.resolve({ capture_budget_bytes: budget }));
    expect(host.textContent).toContain("Budget saved");
    expect(input("Capture budget").value).toBe("150");
    expect(host.textContent).toContain("161061273600 bytes");
  });

  it("does not claim saved when the confirmed server budget differs from the requested value", async () => {
    handler = (url, init) => init.method === "PUT" ? { capture_budget_bytes: 161061273600 } : fallback(url);
    await render(); await change("Capture budget", "150"); await click("Save budget");
    expect(host.textContent).not.toContain("Budget saved");
    expect(host.textContent).toContain("Confirmed budget differs from the requested value");
    expect(host.textContent).toContain("107374182400 bytes");
    expect(input("Capture budget").value).toBe("150");
  });

  it("does not claim saved when the confirmation GET fails", async () => {
    let wrote = false;
    handler = (url, init) => {
      if (init.method === "PUT") { wrote = true; return { capture_budget_bytes: 161061273600 }; }
      if (wrote && url.pathname.endsWith("/config")) return new Response(JSON.stringify({ detail: { code: "sec_research_config_unavailable" } }), { status: 503 });
      return fallback(url);
    };
    await render(); await change("Capture budget", "150"); await click("Save budget");
    expect(host.textContent).not.toContain("Budget saved");
    expect(host.textContent).toContain("sec_research_config_unavailable");
    expect(input("Capture budget").value).toBe("150");
  });

  it("keeps MAX_SAFE_INTEGER exact through unit changes and rejects fractional bytes beyond Number precision", async () => {
    budget = 9007199254740991;
    await render();
    expect(input("Capture budget").value).toBe("9007199254740991");
    await select("Budget unit", "gib");
    expect(input("Capture budget").value).toBe("8388607.999999999068677425384521484375");
    await select("Budget unit", "bytes");
    expect(input("Capture budget").value).toBe("9007199254740991");
    await click("Save budget");
    expect(requests.find(({ init }) => init.method === "PUT")?.init.body).toBe('{"capture_budget_bytes":9007199254740991}');
    await change("Capture budget", "9007199254740991.00000000001");
    expect(button("Save budget").disabled).toBe(true);
  });

  it("keeps previous pages pinned even if the provider-independent latest receipt changes", async () => {
    await render(); await load(); await click("Next page");
    const before = requests.length;
    handler = (url) => url.pathname.endsWith("/filings") ? envelope("ok", [filing("new-receipt")]) : fallback(url);
    await click("Previous page");
    expect(requests).toHaveLength(before);
    expect(host.textContent).toContain("first.htm");
    expect(host.textContent).not.toContain("new-receipt.htm");
  });

  it("rejects delayed old filter pages and allows the new selection to read immediately", async () => {
    const old = deferred<unknown>();
    handler = (url) => url.searchParams.has("cursor") ? old.promise : fallback(url);
    await render(); await load(); await click("Next page"); await chooseForms("10-Q");
    expect(button("Load local").disabled).toBe(false);
    await click("Load local");
    await act(async () => old.resolve(envelope("ok", [filing("old-filter")])));
    expect(host.textContent).not.toContain("old-filter");
    expect(host.textContent).toContain("first.htm");
    expect(button("Previous page").disabled).toBe(true);
  });

  it("does not turn unsafe catalog URLs into links or claim retained documents", async () => {
    handler = (url) => url.pathname.endsWith("/filings") ? envelope("ok", [{ ...filing("unsafe"), primary_url: "javascript:alert(1)" }]) : fallback(url);
    await render(); await load();
    expect(host.textContent).toContain("unsafe.htm");
    expect(host.querySelector('a[href^="javascript:"]')).toBeNull();
    expect(host.textContent).not.toContain("Retained document");
  });

  it("renders Traditional Chinese commands and state labels", async () => {
    await render("zh-Hant");
    expect(host.textContent).toContain("SEC 結構化資料");
    expect(host.textContent).toContain("已計入容量");
    expect(host.textContent).not.toContain("計費總容量");
    expect(button("讀取本機")).toBeDefined();
    expect(button("儲存容量上限")).toBeDefined();
    expect(host.textContent).not.toContain("Load local");
  });
});
