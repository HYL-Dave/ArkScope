/** @vitest-environment jsdom */
import { afterEach, expect, it, vi } from "vitest";
import * as api from "./api";

afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

it("forwards exact document identity, capture, literal filters and opaque cursor using stored GET", async () => {
  const value = { status: "unavailable", data: null, gaps: [{ code: "stored_document_unavailable" }], observed_at: null, coverage: {}, next_cursor: null };
  const fetch = vi.fn(async () => new Response(JSON.stringify(value)));
  vi.stubGlobal("fetch", fetch);
  expect(await api.getSecResearchDocument("123:000-1", { document_id: "file:a b.htm", capture_id: "capture+1", section_id: "part_II_item_1", query: " café.*中 ", cursor: "opaque+/= &?", max_chars: 6000 })).toEqual(value);
  const [input, init] = (fetch.mock.calls as unknown as [string, RequestInit][])[0];
  const url = new URL(input);
  expect(url.pathname).toBe("/sec-research/filings/123%3A000-1/document");
  expect([...url.searchParams]).toEqual([["document_id", "file:a b.htm"], ["capture_id", "capture+1"], ["section_id", "part_II_item_1"], ["query", " café.*中 "], ["cursor", "opaque+/= &?"], ["max_chars", "6000"]]);
  expect(init.method ?? "GET").toBe("GET");
  expect(init.body).toBeUndefined();
});

it("uses only primary in explicit POST with ten minutes and no retry after lost transport", async () => {
  const timer = vi.spyOn(window, "setTimeout");
  const fetch = vi.fn().mockRejectedValue(new TypeError("lost response"));
  vi.stubGlobal("fetch", fetch);
  await expect(api.acquireSecResearchDocument("123:000-1")).rejects.toThrow("lost response");
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(fetch.mock.calls[0][1]).toMatchObject({ method: "POST", body: '{"document_id":"primary"}' });
  expect(timer.mock.calls[0][1]).toBe(600000);
  await expect(api.getSecResearchDocument("123:000-1")).rejects.toThrow();
  expect(timer.mock.calls[1][1]).toBe(15000);
});

it("preserves typed document query errors", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ detail: { code: "sec_research_cursor_mismatch" } }), { status: 422 })));
  await expect(api.getSecResearchDocument("123:000-1")).rejects.toMatchObject({ status: 422, code: "sec_research_cursor_mismatch" });
});
