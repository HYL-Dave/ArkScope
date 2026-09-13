/** @vitest-environment jsdom */
import { afterEach, describe, expect, it, vi } from "vitest";
import * as api from "./api";
import { citationRead, documentCitation, factCitation, filingCitation } from "./secCitationTestUtils";

afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe("exact retained SEC citation API", () => {
  it.each([factCitation, filingCitation, documentCitation])("uses one canonical ref and preserves the six-field $kind response", async (citation) => {
    const response = citationRead(citation);
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(response)));
    vi.stubGlobal("fetch", fetch);
    expect(api.getSecResearchCitation).toBeTypeOf("function");
    expect(await api.getSecResearchCitation(citation)).toEqual(response);
    const [raw, init] = fetch.mock.calls[0];
    const url = new URL(raw);
    expect(url.pathname).toBe("/sec-research/citation");
    expect([...url.searchParams.keys()]).toEqual(["ref"]);
    const token = url.searchParams.get("ref")!;
    expect(token).toMatch(/^[A-Za-z0-9_-]+$/);
    const decoded = atob(token.replace(/-/g, "+").replace(/_/g, "/"));
    expect(JSON.parse(decoded)).toEqual(citation);
    expect(Object.keys(JSON.parse(decoded))).toEqual(Object.keys(citation).sort());
    expect(init.method ?? "GET").toBe("GET");
  });

  it("matches Python ensure_ascii for Unicode, DEL and surrogate code units without padding", async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(citationRead(factCitation))));
    vi.stubGlobal("fetch", fetch);
    const citation = { ...factCitation, source_pointer: '/facts/\u8cc7\u7522/\ud83d\ude00/\u007f/\ud800/\udc00/"\\/~0~1' };
    expect(api.getSecResearchCitation).toBeTypeOf("function");
    await api.getSecResearchCitation(citation);
    const token = new URL(fetch.mock.calls[0][0]).searchParams.get("ref")!;
    const raw = atob(token.replace(/-/g, "+").replace(/_/g, "/"));
    expect(raw).toBe('{"cik":"0000000123","fact_id":"secfact_' + "a".repeat(64)
      + '","kind":"fact","observed_at":"2026-09-12T00:00:00Z","snapshot_id":"secsnapshot_'
      + "b".repeat(64) + '","source_pointer":"/facts/\\u8cc7\\u7522/\\ud83d\\ude00/\\u007f/\\ud800/\\udc00/\\"\\\\/~0~1","source_sha256":"'
      + "c".repeat(64) + '","source_url":"https://data.sec.gov/api/xbrl/companyfacts/CIK0000000123.json"}');
    expect(token).not.toContain("=");
  });

  it.each([
    null, {}, { ...factCitation, extra: true }, { ...factCitation, source_pointer: undefined },
    { ...factCitation, source_pointer: "/" + "x".repeat(7000) },
    { ...documentCitation, end_byte: NaN }, { ...documentCitation, end_byte: Infinity },
    { ...documentCitation, end_byte: 1.5 }, { ...documentCitation, match_end_byte: undefined },
    { ...documentCitation, end_byte: true }, { ...factCitation, source_url: "https://example.com/a" },
  ])("rejects malformed references before fetch: %j", async (value) => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    expect(api.getSecResearchCitation).toBeTypeOf("function");
    await expect(api.getSecResearchCitation(value as api.SecCitation)).rejects.toMatchObject({ code: "sec_citation_invalid" });
    expect(fetch).not.toHaveBeenCalled();
  });
});
