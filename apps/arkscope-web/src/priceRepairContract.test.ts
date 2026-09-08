/** @vitest-environment jsdom */
import { afterEach, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import * as api from "./api";

const operation = {
  repair_id: "a".repeat(32), state: "incomplete", reason: null,
  scope: { tickers: ["OLD"], provider: "ibkr", interval: "15min", as_of_date: "2026-09-05", lookback_days: 15 },
  requests: { planned: 2, dispatched: 0, received: 0, unanswered: 0 },
  coverage: { remaining_tickers: ["OLD"], missing_ticker_days: 1, partial_ticker_days: 0 },
  resume: { available: true, request_limit: 2 },
};
const page = { version: 1, operations: [operation], total: 1, offset: 0, has_more: false };
afterEach(() => vi.unstubAllGlobals());

const persistedOperations = JSON.parse(readFileSync(resolve(import.meta.dirname, "../../../tests/fixtures/price_repair_operations_v1.json"), "utf8"));
it.each(Object.entries(persistedOperations))("accepts the backend-owned persisted projection: %s", (_, operation) => {
  expect(api.parsePriceRepairOperations({ ...page, operations: [operation] }).operations).toEqual([operation]);
});

it("uses fifteen calendar days for a direct coverage read and preserves explicit overrides", async () => {
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ history_gaps: [] }), { status: 200 }));
  vi.stubGlobal("fetch", fetch);
  await api.getTradingDayCoverage();
  expect(String(fetch.mock.calls[0][0])).toContain("lookback_days=15&interval=15min");
  fetch.mockResolvedValue(new Response(JSON.stringify({ history_gaps: [] }), { status: 200 }));
  await api.getTradingDayCoverage(30);
  expect(String(fetch.mock.calls[1][0])).toContain("lookback_days=30&interval=15min");
});

it("projects durable operation facts without passing internal material to the view", () => {
  const parsed = api.parsePriceRepairOperations({ ...page, operations: [{ ...operation, market_db: "/private/market.db", plan_sha256: "secret" }] });
  expect(parsed).toEqual(page);
});

it.each([
  { operations: undefined }, { operations: null }, { operations: {} }, { version: 2 }, { has_more: true }, { total: -1 },
  { operations: [{ ...operation, state: "running" }] },
  { operations: [{ ...operation, scope: { ...operation.scope, tickers: "OLD" } }] },
  { operations: [{ ...operation, requests: { planned: 2, dispatched: 0, received: 1, unanswered: 0 } }] },
  { operations: [{ ...operation, requests: { planned: 2, dispatched: 1, received: 0, unanswered: 0 } }] },
  { operations: [{ ...operation, coverage: { ...operation.coverage, remaining_tickers: ["OTHER"] } }] },
  { operations: [{ ...operation, state: "complete" }] },
  { operations: [{ ...operation, resume: { available: true, request_limit: 3 } }] },
  { operations: [{ ...operation, resume: { available: false, request_limit: 1 } }] },
  { operations: [operation, operation], total: 2 },
])("rejects malformed operation facts instead of treating them as empty (%j)", (change) => {
  expect(() => api.parsePriceRepairOperations({ ...page, ...change })).toThrow("price_coverage_payload_invalid");
});

it("keeps unreadable journals visible without inventing an empty successful scope", () => {
  const unreadable = { ...operation, state: "unavailable", reason: "journal_unavailable", scope: null, requests: null, coverage: null,
    resume: { available: false, request_limit: 0 } };
  expect(api.parsePriceRepairOperations({ ...page, operations: [unreadable] }).operations[0]).toEqual(unreadable);
});

it("reads history with GET and resumes only the explicitly selected operation", async () => {
  const fetch = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ ...page, offset: 5, total: 6 }), { status: 200 }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ status: "accepted", repair_id: operation.repair_id }), { status: 200 }));
  vi.stubGlobal("fetch", fetch);
  await api.getPriceRepairOperations(5);
  expect(String(fetch.mock.calls[0][0])).toContain("/price-repair/operations?limit=5&offset=5");
  expect(fetch.mock.calls[0][1]?.method ?? "GET").toBe("GET");
  expect((await api.resumePriceRepair(operation.repair_id)).repair_id).toBe(operation.repair_id);
  expect(String(fetch.mock.calls[1][0])).toContain(`/price-repair/${operation.repair_id}/resume`);
  expect(fetch.mock.calls[1][1]?.method).toBe("POST");
  await expect(api.resumePriceRepair("../other")).rejects.toThrow("price_coverage_payload_invalid");
  expect(fetch).toHaveBeenCalledTimes(2);
});

it("reads one operation by its exact ID and rejects mismatched or malformed results", async () => {
  const fetch = vi.fn();
  vi.stubGlobal("fetch", fetch);
  await expect(api.getPriceRepairOperation("../other")).rejects.toThrow("price_coverage_payload_invalid");
  expect(fetch).not.toHaveBeenCalled();
  fetch.mockResolvedValueOnce(new Response(JSON.stringify(operation), { status: 200 }));
  expect(await api.getPriceRepairOperation(operation.repair_id)).toEqual(operation);
  expect(String(fetch.mock.calls[0][0])).toContain(`/price-repair/${operation.repair_id}`);
  expect(String(fetch.mock.calls[0][0])).not.toContain("operations?");
  expect(fetch.mock.calls[0][1]?.method ?? "GET").toBe("GET");
  for (const result of [{ ...operation, repair_id: "b".repeat(32) }, { ...operation, scope: { ...operation.scope, tickers: null } }]) {
    fetch.mockResolvedValueOnce(new Response(JSON.stringify(result), { status: 200 }));
    await expect(api.getPriceRepairOperation(operation.repair_id)).rejects.toThrow("price_coverage_payload_invalid");
  }
  expect(fetch).toHaveBeenCalledTimes(3);
});
