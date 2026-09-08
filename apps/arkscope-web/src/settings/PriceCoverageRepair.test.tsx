/** @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { useTranslation } from "react-i18next";
import i18n from "i18next";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { PriceCoverageRepair } from "./PriceCoverageRepair";
import { parseCoverageHistoryGaps, parsePriceRepairPreview, type TradingDayCoverage } from "../api";

const api = vi.hoisted(() => ({ getPriceRepairPreview: vi.fn(), startPriceRepair: vi.fn(), resumePriceRepair: vi.fn(), getPriceRepairOperation: vi.fn(), getPriceRepairOperations: vi.fn(), getSchedule: vi.fn() }));
vi.mock("../api", async (original) => ({ ...await original<typeof import("../api")>(), ...api }));
(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
const onCompleted = vi.fn();
const gap = { ticker: "OLD", reason: "before_first_local_bar" as const, first_local_bar_at: "2026-08-31T13:30:00Z", missing_dates: ["2026-08-28"], partial_dates: [], provider_issue_reason: null };
const coverage: TradingDayCoverage = { version: 2, market_scope: "us_listed_equity_proxy", coverage_session: "rth", interval: "15min", lookback_days: 15,
  universe_count: 1, generated_at_et: "2026-09-05T09:00:00-04:00", calendar_health: { status: "ok", reason_codes: [], reviewed_through: "2027-12-31", forward_horizon_months: 15 },
  observation_health: { status: "ok", reason_code: null }, days: [], provider_errors: [], history_gaps: [gap] };
const plan = { provider: "ibkr", fallback_allowed: false, interval: "15min", lookback_days: 15, as_of_date: "2026-09-05", tickers: ["OLD"], blocked_tickers: [], preview_sha256: "a".repeat(64) };
let host: HTMLDivElement;
let root: ReturnType<typeof createRoot>;
function Harness() {
  const { t } = useTranslation("settings");
  return <PriceCoverageRepair coverage={coverage} t={t} onCompleted={onCompleted} />;
}
beforeEach(async () => {
  await i18n.changeLanguage("en");
  vi.clearAllMocks(); vi.useFakeTimers();
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  api.getPriceRepairPreview.mockResolvedValue(plan);
  api.startPriceRepair.mockResolvedValue({ status: "accepted", repair_id: "b".repeat(32) });
  api.getSchedule.mockResolvedValue({ sources: { ibkr_prices: { running: false } } });
  api.getPriceRepairOperations.mockResolvedValue({ version: 1, operations: [], total: 0, offset: 0, has_more: false });
  api.getPriceRepairOperation.mockRejectedValue(new Error("missing operation"));
  api.resumePriceRepair.mockResolvedValue({ status: "accepted", repair_id: "b".repeat(32) });
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.useRealTimers(); });
async function click(label: string) {
  const button = Array.from(document.querySelectorAll<HTMLButtonElement>("button")).find((item) => item.textContent === label);
  expect(button).toBeDefined();
  await act(async () => button!.click());
}
it("does not start collection on render or preview, and never calls another job's success its own", async () => {
  await act(async () => root.render(<Harness />));
  expect(api.getPriceRepairPreview).not.toHaveBeenCalled();
  expect(api.startPriceRepair).not.toHaveBeenCalled();
  await click("Review price backfill");
  expect(document.querySelector('[role="dialog"]')?.textContent).toContain("No other provider will be used");
  expect(api.startPriceRepair).not.toHaveBeenCalled();
  api.getSchedule.mockResolvedValue({ sources: { ibkr_prices: { running: false, last_result: { status: "succeeded", price_repair_id: "c".repeat(32) } } } });
  await click("Start IBKR backfill");
  expect(api.startPriceRepair).toHaveBeenCalledExactlyOnceWith(plan);
  expect(host.textContent).toContain("Completion has not yet been verified");
  expect(onCompleted).not.toHaveBeenCalled();
  api.getSchedule.mockResolvedValue({ sources: { ibkr_prices: { running: false, durable_state: { last_result: { status: "partial", price_repair_id: "b".repeat(32) } } } } });
  await act(async () => vi.advanceTimersByTimeAsync(2000));
  expect(host.textContent).toContain("some session bars remain missing");
  expect(onCompleted).toHaveBeenCalledOnce();
});
it("cannot report unresolved contracts as a successful empty backfill", async () => {
  api.getPriceRepairPreview.mockResolvedValue({ ...plan, tickers: [], blocked_tickers: ["ARCH"] });
  await act(async () => root.render(<Harness />));
  await click("Review price backfill");
  expect(document.querySelector('[role="dialog"]')?.textContent).toContain("ARCH");
  await click("Close");
  expect(api.startPriceRepair).not.toHaveBeenCalled();
  expect(host.textContent).toContain("No eligible price gaps");
  expect(host.textContent).not.toContain("sessions have been verified");
});
it("reports a lost outcome honestly instead of retrying the provider request", async () => {
  await act(async () => root.render(<Harness />));
  await click("Review price backfill");
  api.getSchedule.mockRejectedValue(new Error("offline"));
  await click("Start IBKR backfill");
  expect(host.textContent).toContain("outcome could not be confirmed");
  expect(api.startPriceRepair).toHaveBeenCalledOnce();
});
it("rejects malformed new array fields and any fallback-enabled preview", () => {
  for (const value of [null, undefined, {}, "OLD"]) {
    expect(() => parseCoverageHistoryGaps(value)).toThrow();
    expect(() => parsePriceRepairPreview({ ...plan, tickers: value })).toThrow();
  }
  expect(() => parsePriceRepairPreview({ ...plan, fallback_allowed: true })).toThrow();
  expect(parseCoverageHistoryGaps([gap])).toEqual([gap]);
});

const unfinished = { repair_id: "b".repeat(32), state: "incomplete", reason: null,
  scope: { tickers: ["OLD"], provider: "ibkr", interval: "15min", as_of_date: "2026-09-05", lookback_days: 15 },
  requests: { planned: 2, dispatched: 2, received: 2, unanswered: 0 },
  coverage: { remaining_tickers: ["OLD"], missing_ticker_days: 1, partial_ticker_days: 0 },
  resume: { available: true, request_limit: 0 } };

it("reloads an unfinished operation and asks before a cache-only resume", async () => {
  api.getPriceRepairOperations.mockResolvedValue({ version: 1, operations: [unfinished], total: 1, offset: 0, has_more: false });
  api.getSchedule.mockResolvedValue({ sources: { ibkr_prices: { running: false } } });
  await act(async () => root.render(<Harness />));
  expect(api.resumePriceRepair).not.toHaveBeenCalled();
  expect(host.textContent).toContain("Coverage incomplete");
  expect(host.textContent).toContain("Responses received: 2 / 2");
  await act(async () => root.unmount());
  root = createRoot(host);
  await act(async () => root.render(<Harness />));
  await click("Resume backfill");
  expect(document.querySelector('[role="dialog"]')?.textContent).toContain("No new provider requests");
  expect(api.resumePriceRepair).not.toHaveBeenCalled();
  await click("Confirm resume");
  expect(api.resumePriceRepair).toHaveBeenCalledExactlyOnceWith(unfinished.repair_id);
  expect(api.startPriceRepair).not.toHaveBeenCalled();
});

it("does not offer to replay an unanswered request or report all responses as complete", async () => {
  const noResponse = { ...unfinished, reason: "unconfirmed_requests", requests: { planned: 2, dispatched: 1, received: 0, unanswered: 1 }, resume: { available: false, request_limit: 0 } };
  const emptyResponse = { ...unfinished, repair_id: "c".repeat(32), reason: "response_incomplete", resume: { available: false, request_limit: 0 } };
  api.getPriceRepairOperations.mockResolvedValue({ version: 1, operations: [noResponse, emptyResponse], total: 2, offset: 0, has_more: false });
  api.getSchedule.mockResolvedValue({ sources: { ibkr_prices: { running: false } } });
  await act(async () => root.render(<Harness />));
  expect(host.textContent).toContain("Request outcome unconfirmed");
  expect(host.textContent).toContain("Saved responses do not cover the remaining gaps");
  expect(Array.from(host.querySelectorAll("button")).some((button) => button.textContent === "Resume backfill")).toBe(false);
  await act(async () => vi.advanceTimersByTimeAsync(60_000));
  expect(api.resumePriceRepair).not.toHaveBeenCalled();
  expect(api.startPriceRepair).not.toHaveBeenCalled();
});

it("keeps failed history reads distinct from an empty history", async () => {
  api.getPriceRepairOperations.mockRejectedValue(new Error("offline"));
  await act(async () => root.render(<Harness />));
  expect(host.textContent).toContain("Repair history could not be read");
  expect(host.textContent).not.toContain("No saved backfills");
});

it("does not leave a stale running claim when collection status cannot be read", async () => {
  api.getSchedule.mockResolvedValue({ sources: { ibkr_prices: { running: true } } });
  await act(async () => root.render(<Harness />));
  expect(host.textContent).toContain("IBKR price collection is running");
  api.getSchedule.mockRejectedValue(new Error("offline"));
  await act(async () => vi.advanceTimersByTimeAsync(2000));
  expect(host.textContent).toContain("Collection activity could not be confirmed");
  expect(host.textContent).not.toContain("IBKR price collection is running");
  api.getSchedule.mockResolvedValue({ sources: { ibkr_prices: { running: false } } });
  await act(async () => vi.advanceTimersByTimeAsync(2000));
  expect(host.textContent).not.toContain("Collection activity could not be confirmed");
});

it.each(["complete", "incomplete"])("checks real coverage before accepting a succeeded worker result (%s)", async (state) => {
  await act(async () => root.render(<Harness />));
  await click("Review price backfill");
  const operation = { ...unfinished, state, resume: { available: false, request_limit: 0 },
    coverage: state === "complete" ? { remaining_tickers: [], missing_ticker_days: 0, partial_ticker_days: 0 } : unfinished.coverage };
  api.getPriceRepairOperations.mockResolvedValue({ version: 1, operations: [operation], total: 1, offset: 0, has_more: false });
  api.getPriceRepairOperation.mockResolvedValue(operation);
  api.getSchedule.mockResolvedValue({ sources: { ibkr_prices: { running: false, last_result: { status: "succeeded", price_repair_id: "b".repeat(32) } } } });
  await click("Start IBKR backfill");
  if (state === "complete") expect(host.textContent).toContain("sessions have been verified locally");
  else {
    expect(host.textContent).toContain("some session bars remain missing");
    expect(host.textContent).not.toContain("sessions have been verified locally");
  }
});

it("shows a bounded new-request budget and keeps old operations reachable", async () => {
  const rows = Array.from({ length: 5 }, (_, index) => ({ ...unfinished, repair_id: String(index).repeat(32) }));
  api.getPriceRepairOperations.mockImplementation(async (offset) => offset === 5
    ? { version: 1, operations: [{ ...unfinished, requests: { planned: 2, dispatched: 0, received: 0, unanswered: 0 }, resume: { available: true, request_limit: 2 } }], total: 6, offset: 5, has_more: false }
    : { version: 1, operations: rows, total: 6, offset: 0, has_more: true });
  await act(async () => root.render(<Harness />));
  await act(async () => host.querySelector<HTMLButtonElement>('[aria-label="Older backfills"]')!.click());
  expect(api.getPriceRepairOperations).toHaveBeenLastCalledWith(5);
  await click("Resume backfill");
  expect(document.querySelector('[role="dialog"]')?.textContent).toContain("At most 2 new IBKR requests");
  expect(api.resumePriceRepair).not.toHaveBeenCalled();
});

it("confirms a resumed operation outside the first history page", async () => {
  const rows = Array.from({ length: 5 }, (_, index) => ({ ...unfinished, repair_id: String(index).repeat(32) }));
  api.getPriceRepairOperations.mockImplementation(async (offset) => offset === 5
    ? { version: 1, operations: [unfinished], total: 6, offset: 5, has_more: false }
    : { version: 1, operations: rows, total: 6, offset: 0, has_more: true });
  await act(async () => root.render(<Harness />));
  await act(async () => host.querySelector<HTMLButtonElement>('[aria-label="Older backfills"]')!.click());
  await click("Resume backfill");
  api.getSchedule.mockResolvedValue({ sources: { ibkr_prices: { running: false, last_result: { status: "succeeded", price_repair_id: unfinished.repair_id } } } });
  api.getPriceRepairOperation.mockResolvedValue({ ...unfinished, state: "complete", resume: { available: false, request_limit: 0 },
    coverage: { remaining_tickers: [], missing_ticker_days: 0, partial_ticker_days: 0 } });
  await click("Confirm resume");
  expect(api.getPriceRepairOperation).toHaveBeenCalledExactlyOnceWith(unfinished.repair_id);
  expect(host.textContent).toContain("sessions have been verified locally");
  expect(host.textContent).not.toContain("outcome could not be confirmed");
});
