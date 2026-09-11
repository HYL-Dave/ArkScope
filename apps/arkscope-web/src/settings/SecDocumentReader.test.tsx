/** @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import i18n from "i18next";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { SecResearchPanel } from "./SecResearchPanel";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
const filing = (id = "123:000-1", primary_document = "annual.htm") => ({ filing_id: id, accession: "000-1", form: "10-K", primary_document, primary_url: "https://untrusted.example/not-authority" });
const source = "https://www.sec.gov/Archives/edgar/data/123/0001/annual.htm";
const capture = "secdoc_" + "a".repeat(64);
const citation = { filing_id: "123:000-1", document_id: "file:annual.htm", capture_id: capture, accession: "000-1", source_url: source, original_sha256: "b".repeat(64), text_sha256: "c".repeat(64), extraction_version: "sec-document-text-v3", start_byte: 0, end_byte: 80, match_start_byte: null, match_end_byte: null };
const doc = { ...citation, primary_document: "annual.htm", form: "10-K", mime_type: "text/html", text_bytes: 10000, original_bytes: 11000, directory_sha256: "d".repeat(64) };
const entry = (name: string) => ({ name, document_id: `file:${name}`, url: source, size_bytes: 10, source: { sha256: "d".repeat(64), pointer: "/directory/item/0" } });
const index = (next_cursor: string | null = null) => ({ status: "ok", data: { document: doc, documents: [entry("annual.htm"), entry("exhibit.htm")], sections: [{ section_id: "item_1", label: "Item 1. Business", start_byte: 0, end_byte: 80 }, { section_id: "item_1a", label: "Item 1A. Risk factors", start_byte: 80, end_byte: 10000 }], passages: [], text_start_cursor: "text+/= start" }, gaps: [], observed_at: "2026-09-12T01:00:00Z", coverage: { capture_id: capture, receipt_id: 1, mode: "index", catalog_complete: true, complete: true, index_total: 4, index_offset: 0 }, next_cursor });
const textPage = (text = "Item 1. Business\ncafé 中 é <script>alert(1)</script>", next_cursor: string | null = null) => ({ ...index(), data: { document: doc, documents: [], sections: [], passages: [{ text, citation }], text_start_cursor: "text+/= start" }, coverage: { capture_id: capture, receipt_id: 1, mode: "text", catalog_complete: true, complete: true }, next_cursor });
const unavailable = () => ({ status: "unavailable", data: null, gaps: [{ code: "stored_document_unavailable" }], observed_at: null, coverage: { complete: false, capture_id: null }, next_cursor: null });
type Handler = (url: URL, init: RequestInit) => unknown | Promise<unknown>;
let handler: Handler;
let requests: { url: URL; init: RequestInit }[];
let host: HTMLDivElement;
let root: ReturnType<typeof createRoot>;
function fallback(url: URL) {
  if (url.pathname.endsWith("/config")) return { capture_budget_bytes: 107374182400, capacity: null };
  if (url.pathname.endsWith("/filings")) return { ...index(), data: [filing(), filing("123:000-1", "conflicting.htm"), filing("123:000-2", "second.htm")] };
  if (url.pathname.endsWith("/document")) return url.searchParams.has("cursor") || url.searchParams.has("section_id") || url.searchParams.has("query") ? textPage() : index();
  return { ...index(), data: { cik: "0000000123", snapshots: {} } };
}
beforeEach(async () => {
  requests = []; handler = fallback;
  vi.stubGlobal("fetch", vi.fn(async (input: string, init: RequestInit = {}) => {
    const url = new URL(input); requests.push({ url, init });
    const result = await handler(url, init);
    return result instanceof Response ? result : new Response(JSON.stringify(result));
  }));
  await i18n.changeLanguage("en");
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  await act(async () => root.render(<SecResearchPanel />));
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.unstubAllGlobals(); });
function button(name: string, n = 0) {
  const result = [...host.querySelectorAll<HTMLButtonElement>("button")].filter((el) => (el.getAttribute("aria-label") ?? el.textContent) === name)[n];
  expect(result, `button ${name}`).toBeDefined(); return result;
}
async function click(name: string, n = 0) { await act(async () => button(name, n).click()); }
async function change(name: string, value: string) {
  await act(async () => {
    const el = host.querySelector<HTMLInputElement>(`input[aria-label="${name}"]`)!;
    expect(el, name).not.toBeNull();
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(el, value);
    el.dispatchEvent(new Event("input", { bubbles: true }));
  });
}
async function select(name: string, value: string) {
  await act(async () => {
    const el = host.querySelector<HTMLSelectElement>(`select[aria-label="${name}"]`)!;
    expect(el, name).not.toBeNull(); el.value = value; el.dispatchEvent(new Event("change", { bubbles: true }));
  });
}
async function open(n = 0) { await change("CIK", "123"); await click("Load local"); await click("Read filing", n); }
const reads = () => requests.filter(({ url }) => url.pathname.endsWith("/document"));
const reader = () => host.querySelector<HTMLElement>(".sec-document-reader")!;
function deferred() { let resolve!: (value: unknown) => void; let reject!: (error: unknown) => void; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; }

it("opens the exact original row using only GET and keeps conflicting catalog variants", async () => {
  await open(1);
  expect(host.querySelectorAll(".sec-record-scroll tbody tr")).toHaveLength(3);
  expect(reader().textContent).toContain("conflicting.htm");
  expect(reads()[0].url.pathname).toBe("/sec-research/filings/123%3A000-1/document");
  expect(reads().every(({ init }) => (init.method ?? "GET") === "GET")).toBe(true);
  expect(reads()[0].url.searchParams.has("capture_id")).toBe(false);
  expect(reads()[0].url.searchParams.has("primary_url")).toBe(false);
});

it("renders exact Unicode plaintext and full safe citation metadata", async () => {
  await open();
  expect(reader().querySelector(".sec-document-text")?.textContent).toBe("Item 1. Business\ncafé 中 é <script>alert(1)</script>");
  expect(reader().querySelector("script")).toBeNull();
  expect(reader().querySelector<HTMLAnchorElement>('a[aria-label="Source citation"]')?.href).toBe(source);
  expect(reader().textContent).toContain(capture);
  expect(reader().textContent).toContain(citation.original_sha256);
});

it.each(["javascript:alert(1)", "https://user:pass@www.sec.gov/a", "//www.sec.gov/a", "not a url"])("rejects unsafe or malformed citation %s", async (source_url) => {
  handler = (url) => url.pathname.endsWith("/document") && url.searchParams.has("cursor") ? { ...textPage(), data: { ...textPage().data, passages: [{ text: "safe text", citation: { ...citation, source_url } }] } } : fallback(url);
  await open(); expect(reader().querySelector('a[aria-label="Source citation"]')).toBeNull(); expect(reader().textContent).toContain("safe text");
});

it("retains capture-bound choices across text/search and forwards exact filters/cursor for next with cached back", async () => {
  handler = (url) => url.pathname.endsWith("/document") && url.searchParams.has("query") ? textPage(url.searchParams.has("cursor") ? "second" : "first", url.searchParams.has("cursor") ? null : "opaque+/= next") : fallback(url);
  await open(); await select("Section", "item_1"); await change("Literal search (case-sensitive)", " café.*中 "); await click("Search passages");
  expect(reader().querySelectorAll('select[aria-label="Document"] option')).toHaveLength(3);
  expect(reader().querySelectorAll('select[aria-label="Section"] option')).toHaveLength(3);
  await click("Next passage page");
  const params = reads().at(-1)!.url.searchParams;
  expect(params.get("capture_id")).toBe(capture); expect(params.get("document_id")).toBe("primary");
  expect(params.get("section_id")).toBe("item_1"); expect(params.get("query")).toBe(" café.*中 ");
  expect(params.get("cursor")).toBe("opaque+/= next"); expect(params.get("max_chars")).toBe("6000");
  const count = reads().length; await click("Previous passage page"); expect(reads()).toHaveLength(count); expect(reader().textContent).toContain("first");
});

it("exposes index continuation independently of text and preserves its capture and operands", async () => {
  handler = (url) => {
    if (!url.pathname.endsWith("/document")) return fallback(url);
    if (url.searchParams.get("cursor") === "index+/= next") return { ...index(), data: { ...index().data, documents: [entry("later.htm")], sections: [] } };
    return url.searchParams.has("cursor") ? textPage() : index("index+/= next");
  };
  await open(); await click("Next index page");
  expect(reads().at(-1)!.url.searchParams.get("cursor")).toBe("index+/= next");
  expect(reads().at(-1)!.url.searchParams.get("capture_id")).toBe(capture);
  expect(reads().at(-1)!.url.searchParams.has("query")).toBe(false);
  expect(reader().querySelector('option[value="file:later.htm"]')).not.toBeNull();
  const count = reads().length; await click("Previous index page"); expect(reads()).toHaveLength(count);
  expect(reader().querySelector('option[value="file:exhibit.htm"]')).not.toBeNull();
});

it("retains observed directory navigation without claiming an uncaptured secondary is captured", async () => {
  handler = (url) => url.searchParams.get("document_id") === "file:exhibit.htm" ? unavailable() : fallback(url);
  await open(); await select("Document", "file:exhibit.htm");
  expect(reader().querySelector('option[value="file:annual.htm"]')).not.toBeNull();
  expect(reader().querySelector(".sec-document-text")).toBeNull();
  expect(reader().textContent).toContain("No stored document capture");
  expect(reader().textContent).toContain("Directory observed with capture");
  expect(reads().at(-1)!.url.searchParams.has("capture_id")).toBe(false);
  await select("Document", "file:annual.htm"); expect(reader().querySelector(".sec-document-text")).not.toBeNull();
  expect(reads().every(({ init }) => (init.method ?? "GET") === "GET")).toBe(true);
});

it("shows section gaps and only uses an explicit whole-text fallback GET", async () => {
  handler = (url) => url.searchParams.has("section_id") ? { ...index(), status: "unavailable", gaps: [{ code: "section_unavailable", section_id: "item_1a" }], data: { ...index().data, documents: [], sections: [] } } : fallback(url);
  await open(); await select("Section", "item_1a");
  expect(reader().textContent).toContain("Section unavailable"); expect(reader().querySelector(".sec-document-text")).toBeNull();
  await click("Whole document");
  expect(reads().at(-1)!.url.searchParams.has("section_id")).toBe(false);
  expect(reads().at(-1)!.url.searchParams.get("cursor")).toBe("text+/= start");
});

it("shows current versus pinned explicitly, reopens the same capture, and only switches latest on command", async () => {
  await open(); expect(reader().textContent).toContain("Current at read");
  await click("Close reader"); expect(reader()).toBeNull(); await click("Read filing");
  expect(reads().at(-2)!.url.searchParams.get("capture_id")).toBe(capture);
  expect(reader().textContent).toContain("Pinned capture");
  await click("Read current capture"); expect(reads().at(-2)!.url.searchParams.has("capture_id")).toBe(false);
  expect(reader().textContent).toContain("Current at read");
});

it("keeps lost POST unknown, disables another POST and offers GET-only reread", async () => {
  handler = (url, init) => { if (init.method === "POST") throw new TypeError("response lost"); return url.pathname.endsWith("/document") ? unavailable() : fallback(url); };
  await open(); expect(reads()).toHaveLength(1); await click("Acquire primary document");
  expect(reader().textContent).toContain("Acquisition outcome unknown"); expect(button("Acquire primary document").disabled).toBe(true);
  await click("Reread stored document");
  expect(reads().filter(({ init }) => init.method === "POST")).toHaveLength(1);
  expect(reads().at(-1)!.init.method ?? "GET").toBe("GET");
  expect(reader().textContent).toContain("Acquisition outcome unknown");
});

it.each(["filing", "close", "filter", "document", "latest"])("ignores late GET after %s generation changes", async (boundary) => {
  const pending = deferred(); let delayed = false;
  handler = (url) => delayed && url.searchParams.get("query") === "old" ? pending.promise : fallback(url);
  await open(); await change("Literal search (case-sensitive)", "old"); delayed = true; await click("Search passages");
  if (boundary === "filing") await click("Read filing", 2);
  if (boundary === "close") await click("Close reader");
  if (boundary === "filter") await change("Literal search (case-sensitive)", "new");
  if (boundary === "document") await select("Document", "file:exhibit.htm");
  if (boundary === "latest") await click("Read current capture");
  await act(async () => pending.resolve(textPage("STALE RESULT")));
  expect(host.textContent).not.toContain("STALE RESULT");
});

it("ignores old acquisition completion after selecting another filing", async () => {
  const pending = deferred(); handler = (url, init) => init.method === "POST" ? pending.promise : fallback(url);
  await open(); await click("Acquire primary document"); await click("Read filing", 2); const count = reads().length;
  await act(async () => pending.resolve({ status: "ok", capture_id: capture, gaps: [], outcome: "complete", observed_at: "2026-09-12T01:00:00Z" }));
  expect(reads()).toHaveLength(count); expect(reader().textContent).toContain("second.htm");
});

it("forwards opaque observed section IDs and leaves a section gap until explicit whole-document reading", async () => {
  handler = (url) => {
    if (url.searchParams.get("section_id") === "unknown_opaque") return { ...textPage(), status: "unavailable", gaps: [{ code: "section_unavailable", section_id: "unknown_opaque" }], data: { ...textPage().data, passages: [] } };
    if (url.pathname.endsWith("/document") && !url.searchParams.has("cursor")) return { ...index(), data: { ...index().data, sections: [{ section_id: "unknown_opaque", label: "Opaque section", start_byte: 0, end_byte: 80 }] } };
    return fallback(url);
  };
  await open(); await select("Section", "unknown_opaque");
  expect(reads().at(-1)!.url.searchParams.get("section_id")).toBe("unknown_opaque");
  expect(reader().textContent).toContain("Section unavailable"); expect(reader().querySelector(".sec-document-text")).toBeNull();
  await click("Whole document"); expect(reader().querySelector(".sec-document-text")).not.toBeNull();
});

it("preserves unknown acquisition across close/reopen and rereads current primary rather than the old pin", async () => {
  handler = (url, init) => { if (init.method === "POST") throw new TypeError("lost"); return fallback(url); };
  await open(); await click("Acquire primary document"); await click("Close reader"); await click("Read filing");
  expect(reader().textContent).toContain("Acquisition outcome unknown"); expect(button("Acquire primary document").disabled).toBe(true);
  await click("Reread stored document");
  expect(reads().at(-2)!.url.searchParams.has("capture_id")).toBe(false);
  expect(reads().filter(({ init }) => init.method === "POST")).toHaveLength(1);
});

it("does not erase an unknown POST outcome when a newer same-filing GET supersedes it", async () => {
  const pending = deferred(); handler = (url, init) => init.method === "POST" ? pending.promise : fallback(url);
  await open(); await click("Acquire primary document"); await click("Read current capture");
  await act(async () => pending.reject(new TypeError("lost")));
  expect(reader().textContent).toContain("Acquisition outcome unknown"); expect(button("Acquire primary document").disabled).toBe(true);
});

it("retains older pinned text explicitly after a failed new acquisition and reopens an entered capture", async () => {
  let failed = false;
  handler = (url, init) => {
    if (init.method === "POST") { failed = true; return { attempt_id: 2, filing_id: "123:000-1", document_id: "primary", resolved_document_id: null, primary_document: null, invalidation_primary_document: "annual.htm", acquisition_id: "attempt2", status: "unavailable", capture_id: null, observed_at: "2026-09-12T02:00:00Z", outcome: "failed", gaps: [{ code: "source_timeout" }], requests: [] }; }
    if (failed && url.pathname.endsWith("/document") && !url.searchParams.has("capture_id")) return unavailable();
    return fallback(url);
  };
  await open(); await click("Acquire primary document");
  expect(reader().querySelector(".sec-document-text")).toBeNull(); expect(reader().textContent).toContain("source_timeout");
  await change("Capture ID", capture); await click("Open pinned capture");
  expect(reader().textContent).toContain("Pinned capture"); expect(reader().querySelector(".sec-document-text")).not.toBeNull();
});

it("focuses and scrolls the reader heading on row open and returns focus to that exact opener", async () => {
  const scrollIntoView = vi.fn();
  const previous = HTMLElement.prototype.scrollIntoView;
  HTMLElement.prototype.scrollIntoView = scrollIntoView;
  try {
    await open(1); const opener = button("Read filing", 1);
    const heading = reader().querySelector("h4");
    expect(document.activeElement).toBe(heading);
    expect(scrollIntoView).toHaveBeenCalledWith({ block: "start" });
    await click("Close reader"); expect(document.activeElement).toBe(opener);
  } finally { HTMLElement.prototype.scrollIntoView = previous; }
});

it("does not restore focus to a disconnected catalog opener", async () => {
  await open(); const opener = button("Read filing"); const focus = vi.spyOn(opener, "focus");
  await click("Load local"); expect(opener.isConnected).toBe(false);
  await click("Close reader"); expect(focus).not.toHaveBeenCalled();
});

const knownAttempt = (outcome = "failed") => ({
  attempt_id: 2, filing_id: "123:000-1", document_id: "primary", resolved_document_id: "file:annual.htm",
  primary_document: "annual.htm", invalidation_primary_document: "annual.htm", acquisition_id: "attempt2",
  status: outcome === "complete" ? "ok" : "unavailable", capture_id: outcome === "complete" ? capture : null,
  observed_at: "2026-09-12T02:00:00Z", outcome, gaps: outcome === "complete" ? [] : [{ code: "source_timeout" }], requests: [],
});

it.each(["complete", "failed", "rejected"])("I1: pending-close-reopen reacts to definite %s without replacing the newer reading", async (outcome) => {
  const pending = deferred();
  handler = (url, init) => init.method === "POST" ? pending.promise
    : url.searchParams.has("query") ? textPage("newer reopened search") : fallback(url);
  await open(); await click("Acquire primary document"); await click("Close reader"); await click("Read filing");
  expect(button("Acquire primary document").disabled).toBe(true);
  await click("Reread stored document");
  expect(reader().textContent).toContain("Acquisition outcome unknown");
  await change("Literal search (case-sensitive)", "newer"); await click("Search passages");
  const count = reads().length;
  await act(async () => pending.resolve(outcome === "rejected"
    ? new Response(JSON.stringify({ detail: { code: "permission_denied" } }), { status: 403 }) : knownAttempt(outcome)));
  expect(reader().textContent).not.toContain("Acquisition outcome unknown");
  expect(button("Acquire primary document").disabled).toBe(false);
  expect(reads()).toHaveLength(count);
  expect(reader().querySelector(".sec-document-text")?.textContent).toBe("newer reopened search");
  await click("Reread stored document");
  expect(button("Acquire primary document").disabled).toBe(false);
  expect(reads().filter(({ init }) => init.method === "POST")).toHaveLength(1);
});

it("I1 control: a genuinely lost POST after pending-close-reopen remains unknown and GET-only", async () => {
  const pending = deferred(); handler = (url, init) => init.method === "POST" ? pending.promise : fallback(url);
  await open(); await click("Acquire primary document"); await click("Close reader"); await click("Read filing");
  await act(async () => pending.reject(new TypeError("lost response")));
  await click("Reread stored document");
  expect(reader().textContent).toContain("Acquisition outcome unknown");
  expect(button("Acquire primary document").disabled).toBe(true);
  expect(reads().at(-2)!.url.searchParams.has("capture_id")).toBe(false);
  expect(reads().filter(({ init }) => init.method === "POST")).toHaveLength(1);
});

it("I1 control: completing another filing does not clear this filing's pending acquisition", async () => {
  const first = deferred(); const second = deferred();
  handler = (url, init) => init.method === "POST" ? (url.pathname.includes("000-1") ? first.promise : second.promise) : fallback(url);
  await open(); await click("Acquire primary document"); await click("Read filing", 2); await click("Acquire primary document");
  await act(async () => first.resolve(knownAttempt()));
  expect(reader().textContent).toContain("second.htm");
  expect(reader().textContent).toContain("Acquisition outcome unknown");
  expect(button("Acquire primary document").disabled).toBe(true);
  await act(async () => second.resolve({ ...knownAttempt(), filing_id: "123:000-2" }));
  expect(reader().textContent).not.toContain("Acquisition outcome unknown");
  expect(button("Acquire primary document").disabled).toBe(false);
});

it.each([
  ["newer capture B", false], ["failed latest", false],
  ["newer capture B", true], ["failed latest", true],
] as const)("I2: primary alias keeps A against %s, missing-secondary navigation=%s", async (latest, visitSecondary) => {
  const captureB = "secdoc_" + "b".repeat(64);
  let advanced = false;
  handler = (url) => {
    if (!url.pathname.endsWith("/document")) return fallback(url);
    if (url.searchParams.get("document_id") === "file:exhibit.htm") return unavailable();
    const pinnedA = url.searchParams.get("capture_id") === capture;
    if (advanced && !pinnedA && latest === "failed latest") return unavailable();
    const selected = advanced && !pinnedA ? captureB : capture;
    const result = url.searchParams.has("cursor") ? textPage(selected === capture ? "capture A text" : "capture B text") : index();
    return { ...result, coverage: { ...result.coverage, capture_id: selected }, data: { ...result.data,
      document: { ...doc, capture_id: selected },
      passages: result.data.passages.map((passage) => ({ ...passage, citation: { ...citation, capture_id: selected } })),
    } };
  };
  await open(); advanced = true;
  await select("Document", "file:annual.htm");
  expect(reads().at(-2)!.url.searchParams.get("capture_id")).toBe(capture);
  if (visitSecondary) {
    await select("Document", "file:exhibit.htm");
    expect(reads().at(-1)!.url.searchParams.has("capture_id")).toBe(false);
    expect(reader().querySelector(".sec-document-text")).toBeNull();
  }
  const before = reads().length;
  await select("Document", "primary");
  expect(reads()[before].url.searchParams.get("capture_id")).toBe(capture);
  expect(reads()[before].url.searchParams.get("document_id")).toBe("primary");
  expect(reader().querySelector(".sec-document-text")?.textContent).toBe("capture A text");
  expect(reader().textContent).toContain("Pinned capture");
  const beforeCurrent = reads().length; await click("Read current capture");
  expect(reads()[beforeCurrent].url.searchParams.has("capture_id")).toBe(false);
  expect(reader().querySelector(".sec-document-text")?.textContent ?? null).toBe(latest === "failed latest" ? null : "capture B text");
  expect(reads().every(({ init }) => (init.method ?? "GET") === "GET")).toBe(true);
});

it("I2 control: primary alias never borrows a nonprimary document capture", async () => {
  const secondaryCapture = "secdoc_" + "c".repeat(64);
  handler = (url) => {
    if (url.searchParams.get("document_id") !== "file:exhibit.htm") return fallback(url);
    const result = url.searchParams.has("cursor") ? textPage("secondary text") : index();
    return { ...result, coverage: { ...result.coverage, capture_id: secondaryCapture }, data: { ...result.data,
      document: { ...doc, capture_id: secondaryCapture, document_id: "file:exhibit.htm", primary_document: "annual.htm" },
      passages: result.data.passages.map((passage) => ({ ...passage, citation: { ...citation, capture_id: secondaryCapture, document_id: "file:exhibit.htm" } })),
    } };
  };
  await open(); await select("Document", "file:exhibit.htm");
  expect(reader().querySelector(".sec-document-text")?.textContent).toBe("secondary text");
  const before = reads().length; await select("Document", "primary");
  expect(reads()[before].url.searchParams.has("capture_id")).toBe(false);
  expect(reader().querySelector(".sec-document-text")?.textContent).not.toBe("secondary text");
});

it("I3: index Back preserves the visible observed section and its exact outgoing search filter", async () => {
  handler = (url) => {
    if (!url.pathname.endsWith("/document")) return fallback(url);
    if (url.searchParams.get("cursor") === "later-sections") return { ...index(), data: { ...index().data, documents: [], sections: [index().data.sections[1]] }, coverage: { ...index().coverage, index_offset: 2 } };
    if (url.searchParams.has("query")) return textPage("section search result", "search-next");
    if (url.searchParams.has("cursor") || url.searchParams.has("section_id")) return textPage("selected section text");
    return { ...index("later-sections"), data: { ...index().data, sections: [] } };
  };
  await open();
  expect(reader().querySelector('select[aria-label="Section"] option[value="item_1a"]')).toBeNull();
  await click("Next index page"); await select("Section", "item_1a");
  const beforeBack = reads().length; await click("Previous index page");
  expect(reads()).toHaveLength(beforeBack);
  const sectionSelect = reader().querySelector<HTMLSelectElement>('select[aria-label="Section"]')!;
  expect(sectionSelect.value).toBe("item_1a");
  expect(sectionSelect.selectedOptions[0].textContent).toBe("Item 1A. Risk factors");
  expect(reader().querySelector(".sec-document-text")?.textContent).toBe("selected section text");
  await change("Literal search (case-sensitive)", " Café.* "); await click("Search passages");
  expect(reads().at(-1)!.url.searchParams.get("section_id")).toBe("item_1a");
  expect(reads().at(-1)!.url.searchParams.get("query")).toBe(" Café.* ");
  await click("Next passage page");
  expect(reads().at(-1)!.url.searchParams.get("section_id")).toBe("item_1a");
  expect(reads().at(-1)!.url.searchParams.get("capture_id")).toBe(capture);
  expect(reads().at(-1)!.url.searchParams.get("cursor")).toBe("search-next");
  await click("Whole document");
  expect(sectionSelect.value).toBe("");
  expect(reads().at(-1)!.url.searchParams.has("section_id")).toBe(false);
  expect(reads().at(-1)!.url.searchParams.has("query")).toBe(false);
  const beforeForward = reads().length; await click("Next index page");
  expect(reads()).toHaveLength(beforeForward);
});
