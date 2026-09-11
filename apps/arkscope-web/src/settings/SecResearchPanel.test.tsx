/** @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import i18n from "i18next";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

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

function applyPanelStyles() {
  stylesheet = document.createElement("style");
  stylesheet.textContent = readFileSync(resolve(import.meta.dirname, "secResearch.css"), "utf8");
  document.head.append(stylesheet);
}

function fallback(url: URL) {
  if (url.pathname === "/sec-research/config") return { capture_budget_bytes: budget, capacity };
  if (url.pathname.endsWith("/refresh")) return receipt;
  if (url.pathname.endsWith("/filings")) return envelope("ok", [filing("first")], "opaque+/= &token");
  if (url.pathname.endsWith("/facts")) return envelope("ok", [{ fact_id: "fact-1", namespace: "us-gaap", concept: "Assets", value: "1234567890123456789.123", unit: "EUR", start: null, end: "2025-12-31", filed_date: "2026-02-01", accession: "000-1", source: { snapshot_id: 2 } }]);
  if (/\/sec-research\/\d+$/.test(url.pathname)) return { ...envelope(), data: { cik: url.pathname.split("/").pop(), snapshots: { recent: 1, facts: 1 } }, coverage: { completed: ["recent"], pending: ["history.json"] } };
  throw new Error(`unmocked route: ${url}`);
}
beforeEach(() => {
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
  vi.unstubAllGlobals();
});
async function render(language = "en") {
  // Dynamic import makes the absent panel an explicit RED test failure.
  const { SecResearchPanel } = await import("./SecResearchPanel");
  await i18n.changeLanguage(language);
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  await act(async () => root!.render(<SecResearchPanel />));
}
function button(name: string) {
  const result = [...host.querySelectorAll<HTMLButtonElement>("button")].find((el) => (el.getAttribute("aria-label") ?? el.textContent) === name);
  expect(result, `button ${name}`).toBeDefined();
  return result!;
}
async function click(name: string) { await act(async () => button(name).click()); }
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
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

describe("SEC structured storage", () => {
  it("limits pagination counter sizing to the counter, excluding button icon wrappers", async () => {
    applyPanelStyles();
    await render(); await load();
    const counter = host.querySelector<HTMLElement>(".sec-pagination > span")!;
    expect(getComputedStyle(counter).minWidth).toBe("64px");
    const icons = host.querySelectorAll<HTMLElement>(".sec-pagination button .ui-button-icon");
    expect(icons).toHaveLength(2);
    for (const icon of icons) expect(getComputedStyle(icon).minWidth).not.toBe("64px");
  });

  it("puts readable catalog fields before complete opaque filing IDs", async () => {
    const id = "secfiling_" + "a".repeat(64);
    handler = (url) => url.pathname.endsWith("/filings") ? envelope("ok", [{
      ...filing(id), accession: "0000000123-26-000001", primary_document: "annual-report.htm",
    }]) : fallback(url);
    await render(); await load();
    expect([...host.querySelectorAll(".sec-record-scroll th")].map((cell) => cell.textContent)).toEqual([
      "Form", "Filed date", "Report date", "Accepted at", "Primary document", "Catalog URL", "Accession", "Filing ID",
    ]);
    const cells = [...host.querySelectorAll(".sec-record-scroll tbody td")];
    expect(cells.map((cell) => cell.textContent)).toEqual([
      "10-K", "2026-02-01", "2025-12-31", "2026-02-01T10:00:00Z", "annual-report.htm", "", "0000000123-26-000001", id,
    ]);
    expect(cells[5].querySelector("a")?.href).toBe("https://www.sec.gov/Archives/edgar/data/123/report.htm");
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

  it("mounts with only config GET, actual accounting, and no issuer guessing", async () => {
    await render();
    expect(requests.map(({ url, init }) => [url.pathname, init.method ?? "GET"])).toEqual([["/sec-research/config", "GET"]]);
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
    expect(requests.map(({ init }) => init.method ?? "GET")).toEqual(["GET", "PUT", "GET"]);
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
    handler = (url) => url.searchParams.has("cursor") ? envelope("ok", [filing("second")]) : fallback(url);
    await render(); await load(); await click("Next page");
    expect(requests.at(-1)?.url.searchParams.get("cursor")).toBe("opaque+/= &token");
    expect(host.textContent).toContain("second.htm");
    await click("Previous page"); expect(host.textContent).toContain("first.htm");
    await click("Next page"); await change("Forms", "10-Q");
    expect(host.textContent).not.toContain("second.htm");
    await click("Load local");
    const last = requests.filter(({ url }) => url.pathname.endsWith("/filings")).at(-1)!.url;
    expect(last.searchParams.has("cursor")).toBe(false);
    expect(last.searchParams.getAll("forms")).toEqual(["10-Q"]);
    expect(button("Previous page").disabled).toBe(true);
  });

  it("preserves conflicting catalog variants across cached forward and back pages without key warnings", async () => {
    const first = [
      filing("conflict"), { ...filing("conflict"), form: "10-Q" },
      ...Array.from({ length: 18 }, (_, index) => filing(`first-${index}`)),
    ];
    const expectedFirst = [
      ["10-K", "2026-02-01", "2025-12-31", "2026-02-01T10:00:00Z", "conflict.htm", "", "accession-conflict", "conflict"],
      ["10-Q", "2026-02-01", "2025-12-31", "2026-02-01T10:00:00Z", "conflict.htm", "", "accession-conflict", "conflict"],
      ...Array.from({ length: 18 }, (_, index) => [
        "10-K", "2026-02-01", "2025-12-31", "2026-02-01T10:00:00Z", `first-${index}.htm`, "", `accession-first-${index}`, `first-${index}`,
      ]),
    ];
    const expectedNext = [["10-K", "2026-02-01", "2025-12-31", "2026-02-01T10:00:00Z", "next-page.htm", "", "accession-next-page", "next-page"]];
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
    const pending = deferred<unknown>();
    handler = (url) => url.pathname.endsWith("/refresh") ? pending.promise : fallback(url);
    await render(); await load(); await click("Refresh structured data");
    await change("Forms", "10-Q");
    await act(async () => pending.resolve(receipt));
    const latest = requests.filter(({ url }) => url.pathname.endsWith("/filings")).at(-1)!.url;
    expect(latest.searchParams.getAll("forms")).toEqual(["10-Q"]);
    expect(latest.searchParams.has("cursor")).toBe(false);
    expect(host.textContent).toContain("Refresh receipt");
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
    await render(); await load(); await click("Next page"); await change("Forms", "10-Q");
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
