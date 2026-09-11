import React, { act } from "react";
import { createRoot } from "react-dom/client";
import i18n from "i18next";
import { expect, it, vi } from "vitest";
import { SecResearchPanel } from "/tmp/arkscope-listing-sec-macro-convergence/apps/arkscope-web/src/settings/SecResearchPanel";

it("reflects a known POST completion in a reader reopened while the POST was pending", async () => {
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  await i18n.changeLanguage("en");
  let finish;
  const pending = new Promise((resolve) => { finish = resolve; });
  const absent = { status: "unavailable", data: null, gaps: [{ code: "stored_document_unavailable" }], observed_at: null, coverage: { complete: false }, next_cursor: null };
  vi.stubGlobal("fetch", vi.fn(async (input, init = {}) => {
    const url = new URL(input);
    if (init.method === "POST") return new Response(JSON.stringify(await pending));
    if (url.pathname.endsWith("/config")) return new Response(JSON.stringify({ capture_budget_bytes: 107374182400, capacity: null }));
    if (url.pathname.endsWith("/filings")) return new Response(JSON.stringify({ ...absent, status: "ok", data: [{ filing_id: "0000000123:0000000123-26-000001", accession: "0000000123-26-000001", form: "10-K", primary_document: "annual.htm" }] }));
    return new Response(JSON.stringify(absent));
  }));
  const host = document.createElement("div"); document.body.append(host);
  const root = createRoot(host);
  const button = (name) => [...host.querySelectorAll("button")].find((el) => (el.getAttribute("aria-label") ?? el.textContent) === name);
  const click = async (name) => { expect(button(name), name).toBeDefined(); await act(async () => button(name).click()); };
  try {
    await act(async () => root.render(<SecResearchPanel />));
    await act(async () => {
      const cik = host.querySelector('input[aria-label="CIK"]');
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(cik, "123");
      cik.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await click("Load local"); await click("Read filing");
    await click("Acquire primary document");
    await click("Close reader"); await click("Read filing");
    expect(button("Acquire primary document").disabled).toBe(true);
    await act(async () => finish({ attempt_id: 1, filing_id: "0000000123:0000000123-26-000001", document_id: "primary", resolved_document_id: null, primary_document: null, invalidation_primary_document: null, acquisition_id: "known-attempt", status: "unavailable", capture_id: null, observed_at: "2026-09-12T01:00:00Z", outcome: "failed", gaps: [{ code: "source_timeout" }], requests: [] }));
    await click("Reread stored document");
    expect(host.textContent).not.toContain("Acquisition outcome unknown");
    expect(button("Acquire primary document").disabled).toBe(false);
  } finally {
    await act(async () => root.unmount()); host.remove(); vi.unstubAllGlobals();
  }
});
