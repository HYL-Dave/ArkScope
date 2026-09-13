/** @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import i18n from "i18next";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SecCitationView } from "./SecCitationView";
import { citationRead, documentCitation, factCitation } from "./secCitationTestUtils";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
let host: HTMLDivElement;
let root: ReturnType<typeof createRoot>;
beforeEach(async () => {
  await i18n.changeLanguage("en");
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
});
afterEach(async () => {
  act(() => root.unmount());
  host.remove();
  vi.unstubAllGlobals();
  await i18n.changeLanguage("zh-Hant");
});
async function render(citation = documentCitation) {
  await act(async () => {
    root.render(<SecCitationView citation={citation} onClose={vi.fn()} />);
    await new Promise<void>((resolve) => setTimeout(resolve, 0));
  });
}
function response(value: unknown, status = 200) { return new Response(JSON.stringify(value), { status }); }

describe("SEC citation view response boundary", () => {
  it.each([
    { ...citationRead(documentCitation), data: null },
    citationRead(factCitation),
    { ...citationRead(documentCitation), data: { citation: documentCitation, text: "UNVERIFIED" } },
    { ...citationRead(documentCitation), data: { citation: documentCitation, text: "UNVERIFIED", document: null } },
    { ...citationRead(documentCitation), status: "unavailable", data: { citation: documentCitation, text: "UNVERIFIED" }, gaps: [] },
  ])("does not render incomplete or mismatched retained evidence %#", async (payload) => {
    vi.stubGlobal("fetch", vi.fn(async () => response(payload)));
    await render();
    expect(host.textContent).not.toContain("UNVERIFIED");
    expect(host.textContent).not.toContain("12345678901234567890.00100");
    expect(host.querySelector('[aria-label="Retry SEC source"]')).not.toBeNull();
  });

  it("shows a closed query error without leaking the remote diagnostic", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => response({ detail: { code: "sec_citation_query_invalid", message: "PRIVATE_OPERAND" } }, 422)));
    await render();
    expect(host.textContent).toContain("sec_citation_query_invalid");
    expect(host.textContent).not.toContain("PRIVATE_OPERAND");
    expect(host.querySelector('[aria-label="Retry SEC source"]')).not.toBeNull();
  });

  it("keeps a selected source and its exact bytes through locale changes", async () => {
    const fetch = vi.fn(async () => response(citationRead(documentCitation, "\u8cc7\u7522 <b>exact</b>")));
    vi.stubGlobal("fetch", fetch);
    await render();
    const text = host.querySelector(".sec-citation-text");
    const close = host.querySelector('[aria-label="Close SEC source"]');
    await act(async () => { await i18n.changeLanguage("zh-Hant"); });
    expect(host.querySelector(".sec-citation-text")).toBe(text);
    expect(text?.textContent).toBe("\u8cc7\u7522 <b>exact</b>");
    expect(host.querySelector('[aria-label="關閉 SEC 來源"]')).toBe(close);
    expect(fetch).toHaveBeenCalledOnce();
  });

  it("keeps keyboard focus in the source while a retry is pending", async () => {
    let resolve!: (value: Response) => void;
    const pending = new Promise<Response>((done) => { resolve = done; });
    const fetch = vi.fn().mockResolvedValueOnce(response({}, 503)).mockReturnValueOnce(pending);
    vi.stubGlobal("fetch", fetch);
    await render();
    const retry = host.querySelector<HTMLButtonElement>('[aria-label="Retry SEC source"]')!;
    await act(async () => { retry.focus(); retry.click(); });
    expect(host.contains(document.activeElement)).toBe(true);
    expect(host.textContent).toContain("Loading SEC source");
    await act(async () => { resolve(response(citationRead(documentCitation))); });
  });
});
