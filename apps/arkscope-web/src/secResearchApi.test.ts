/** @vitest-environment jsdom */
import { afterEach, describe, expect, it, vi } from "vitest";
import * as api from "./api";

afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe("SEC stored API contracts", () => {
  it.each([
    { status: "ok" as const, data: ["10-Q/A", "DEF 14A", "SC 13G/A"] },
    { status: "partial" as const, data: ["DEF 14A"] },
    { status: "empty" as const, data: [] },
    { status: "unavailable" as const, data: null },
  ])("reads the complete stored $status filing-form envelope without filters or source acquisition", async ({ status, data }) => {
    const response: api.SecResearchEnvelope<string[] | null> = {
      status, data, gaps: status === "partial" ? [{ code: "history_pending" }] : [],
      observed_at: status === "unavailable" ? null : "2026-09-15T00:00:00Z",
      coverage: { complete: status === "ok" || status === "empty" }, next_cursor: null,
    };
    const requests: { url: URL; init: RequestInit }[] = [];
    vi.stubGlobal("fetch", async (input: string, init: RequestInit = {}) => {
      requests.push({ url: new URL(input), init });
      return new Response(JSON.stringify(response));
    });
    expect(api.getSecResearchFilingForms).toBeTypeOf("function");
    expect(await api.getSecResearchFilingForms("CIK:123")).toEqual(response);
    expect(requests).toHaveLength(1);
    expect(requests[0].url.pathname).toBe("/sec-research/CIK%3A123/filing-forms");
    expect(requests[0].url.search).toBe("");
    expect(requests[0].init.method ?? "GET").toBe("GET");
    expect(requests[0].init.body).toBeUndefined();
  });

  it("admits and preserves unavailable null-data envelopes for both stored queries", async () => {
    const filings: Awaited<ReturnType<typeof api.getSecResearchFilings>> = {
      status: "unavailable", data: null, gaps: [{ code: "sec_research_not_installed" }],
      observed_at: null, coverage: {}, next_cursor: null,
    };
    const facts: Awaited<ReturnType<typeof api.getSecResearchFacts>> = { ...filings, data: null };
    vi.stubGlobal("fetch", vi.fn().mockImplementation(async () => new Response(JSON.stringify(filings))));
    expect(await api.getSecResearchFilings("123")).toEqual(filings);
    expect(await api.getSecResearchFacts("123")).toEqual(facts);
  });

  it("encodes issuer, repeatable filters and opaque cursors without changing them", async () => {
    const fetch = vi.fn().mockImplementation(async () => new Response(JSON.stringify({ data: [] })));
    vi.stubGlobal("fetch", fetch);
    await api.getSecResearchFilings("CIK:123", {
      forms: ["10-K", "10-Q/A"], filed_from: "2025-01-01", filed_to: "2026-01-01",
      include_amendments: false, limit: 20, cursor: "a+/= &?",
    });
    const url = new URL(fetch.mock.calls[0][0]);
    expect(url.pathname).toBe("/sec-research/CIK%3A123/filings");
    expect([...url.searchParams.entries()]).toEqual([
      ["forms", "10-K"], ["forms", "10-Q/A"], ["filed_from", "2025-01-01"],
      ["filed_to", "2026-01-01"], ["include_amendments", "false"],
      ["limit", "20"], ["cursor", "a+/= &?"],
    ]);
    await api.getSecResearchFacts("123", {
      metrics: ["assets", "cash"], concepts: ["us-gaap:Assets"],
      fact_ids: ["id/1", "id+2"], accession: "000-1", as_of: "2026-01-01",
      period: "annual", start: "2025-01-01", end: "2025-12-31",
      revisions: "all", limit: 40, cursor: "unchanged+token",
    });
    const facts = new URL(fetch.mock.calls[1][0]);
    expect(facts.pathname).toBe("/sec-research/123/facts");
    expect([...facts.searchParams.entries()]).toEqual([
      ["metrics", "assets"], ["metrics", "cash"], ["concepts", "us-gaap:Assets"],
      ["fact_ids", "id/1"], ["fact_ids", "id+2"], ["accession", "000-1"],
      ["as_of", "2026-01-01"], ["period", "annual"], ["start", "2025-01-01"],
      ["end", "2025-12-31"], ["revisions", "all"], ["limit", "40"], ["cursor", "unchanged+token"],
    ]);
  });

  it("uses stored GETs and a budget-only exact PUT", async () => {
    const fetch = vi.fn().mockImplementation(async () => new Response(JSON.stringify({ capture_budget_bytes: 107374182401 })));
    vi.stubGlobal("fetch", fetch);
    await api.getSecResearchConfig();
    await api.getSecResearchStatus("123");
    expect(await api.setSecResearchBudget(107374182401)).toEqual({ capture_budget_bytes: 107374182401 });
    expect(fetch.mock.calls.map(([url, init]) => [new URL(url).pathname, init.method ?? "GET", init.body])).toEqual([
      ["/sec-research/config", "GET", undefined],
      ["/sec-research/123", "GET", undefined],
      ["/sec-research/config", "PUT", '{"capture_budget_bytes":107374182401}'],
    ]);
  });

  it("keeps HTTP codes on query and save errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation(async () => new Response(JSON.stringify({ detail: { code: "sec_query_invalid" } }), { status: 422 })));
    await expect(api.getSecResearchFilings("123")).rejects.toMatchObject({ status: 422, code: "sec_query_invalid" });
    await expect(api.setSecResearchBudget(1)).rejects.toMatchObject({ status: 422, code: "sec_query_invalid" });
  });

  it("gives only refresh a ten-minute client allowance and never retries a lost POST", async () => {
    const timer = vi.spyOn(window, "setTimeout");
    const fetch = vi.fn().mockRejectedValue(new TypeError("connection lost"));
    vi.stubGlobal("fetch", fetch);
    await expect(api.refreshSecResearch("123", true)).rejects.toThrow("connection lost");
    expect(timer.mock.calls[0][1]).toBe(600000);
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch.mock.calls[0][1]).toMatchObject({ method: "POST", body: '{"resume":true}' });
    await expect(api.getSecResearchStatus("123")).rejects.toThrow();
    expect(timer.mock.calls[1][1]).toBe(15000);
  });
});
