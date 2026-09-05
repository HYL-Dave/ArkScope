/** @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { useTranslation } from "react-i18next";
import i18n from "i18next";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { PriceCoverageRepair } from "./PriceCoverageRepair";
import { parseCoverageHistoryGaps, parsePriceRepairPreview, type TradingDayCoverage } from "../api";

const api = vi.hoisted(() => ({ getPriceRepairPreview: vi.fn(), startPriceRepair: vi.fn(), getSchedule: vi.fn() }));
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
  api.getSchedule.mockResolvedValue({ sources: { ibkr_prices: { running: true } } });
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
  api.getSchedule.mockRejectedValue(new Error("offline"));
  await act(async () => root.render(<Harness />));
  await click("Review price backfill");
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
