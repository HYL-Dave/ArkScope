/** @vitest-environment jsdom */
import { afterEach, expect, it, vi } from "vitest";
import * as api from "./api";
import { financialCoverageKey, createSettingsReadCache, settingsReadPolicy } from "./settings/settingsReadCache";

afterEach(() => vi.unstubAllGlobals());

it("keeps reads local with explicit query pins and named refresh separate", async () => {
  const fetch = vi.fn<typeof globalThis.fetch>(async () => new Response("{}", { status: 200, headers: { "content-type": "application/json" } }));
  vi.stubGlobal("fetch", fetch);
  await api.getStoredFundamentals("BRK B", { source: "seeking_alpha", period: "quarterly", currency: "USD",
    statement: "income_statement", read_id: "a".repeat(64), observation_id: "b".repeat(64),
    end_month: "2025-12", period_offset: 1, period_limit: 1 });
  await api.getFinancialCoverage({ source: "financial_datasets", period: "annual", offset: 25, limit: 25 });
  const url = new URL(String(fetch.mock.calls[0]![0]));
  expect(decodeURIComponent(url.pathname)).toContain("/fundamentals/BRK B");
  expect(url.searchParams.get("freshness")).toBe("stored");
  expect(url.searchParams.get("observation_id")).toBe("b".repeat(64));
  expect(url.searchParams.get("period_offset")).toBe("1");
  expect(fetch.mock.calls.every((args) => !args[1]?.method || args[1]?.method === "GET")).toBe(true);
  await api.refreshFinancials("AAPL", { source: "financial_datasets", period: "annual", currency: "USD" });
  expect(fetch.mock.calls[2]![1]?.method).toBe("POST");
  expect(JSON.parse(String(fetch.mock.calls[2]![1]?.body))).toEqual({ source: "financial_datasets", period: "annual", currency: "USD" });
});

it("scopes UI request reuse and invalidates every financial page independently of prices", async () => {
  const cache = createSettingsReadCache();
  const a = financialCoverageKey("annual", "auto", "USD", 0, 25);
  const b = financialCoverageKey("quarterly", "seeking_alpha", "USD", 25, 25);
  expect(a).not.toBe(b);
  expect(settingsReadPolicy(a)).toMatchObject({ freshMs: 60_000, hardRetentionMs: 900_000 });
  cache.replace(a, { a: 1 }); cache.replace(b, { b: 1 }); cache.replace("market_data_status", { p: 1 });
  cache.invalidateFinancialReads();
  expect(cache.inspect(a).status).toBe("missing");
  expect(cache.inspect(b).status).toBe("missing");
  expect(cache.inspect("market_data_status").status).toBe("fresh");
});
