/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PortfolioRecentActivity } from "./PortfolioRecentActivity";
import type {
  PortfolioActivityPage,
  PortfolioBrokerActivityItem,
  PortfolioManualActivityItem,
  PortfolioUnmatchedActivityItem,
} from "./api";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

afterEach(() => {
  if (root) act(() => root!.unmount());
  root = null;
  host?.remove();
  host = null;
  vi.restoreAllMocks();
});

const account = {
  id: 2,
  label: "IBKR · safe-label",
  broker: "ibkr",
  broker_account_id_hash: "broker-account-raw-hash-123456789",
  archived: false,
} as const;

const manualItem = {
  id: "manual-raw-id-7",
  kind: "manual_adjustment",
  occurred_at_utc: "2026-07-15T13:00:00+00:00",
  account: {
    ...account,
    id: 1,
    label: "Manual",
    broker: "manual",
    broker_account_id_hash: null,
  },
  symbol: "TSM",
  source: "manual",
  state: "manual_adjustment",
  annotation: null,
  position_id: 7007,
  action: "update",
  changes: [{ field: "quantity", before: 5, after: 8 }],
} satisfies PortfolioManualActivityItem;

const unmatchedItem = {
  id: "unmatched-raw-id-44",
  kind: "unmatched",
  occurred_at_utc: "2026-07-15T15:00:00+00:00",
  account,
  symbol: "MSFT",
  asset_class: "stock",
  currency: "USD",
  source: "broker",
  state: "unmatched",
  annotation: null,
  from_run_id: 52,
  to_run_id: 53,
  from_as_of_utc: "2026-07-15T14:45:00+00:00",
  to_as_of_utc: "2026-07-15T15:00:00+00:00",
  before_quantity: 20,
  after_quantity: 15,
  expected_quantity: 18,
  residual_quantity: -3,
  execution_coverage: "incomplete",
  reason_code: "position_delta_unexplained",
} satisfies PortfolioUnmatchedActivityItem;

const brokerItem = {
  id: "order-raw-id-70001",
  kind: "order",
  occurred_at_utc: "2026-07-15T14:31:00+00:00",
  account,
  symbol: "AAPL",
  asset_class: "stock",
  currency: "USD",
  source: "broker",
  state: "realized_gain",
  objective: {
    side: "sell",
    quantity: 10,
    average_price: 220,
    gross_notional: 2200,
    gross_notional_kind: "deterministic_arithmetic",
    commission: 1,
    commission_currency: "USD",
    realized_pnl: 125,
    realized_outcome: "gain",
    position_direction: "reduce",
    close_scope: "partial",
    position_context: "complete",
  },
  annotation: null,
  fills: [{
    family_root_id: 310031,
    effective_revision_id: 320032,
    revisions: [{
      id: 320032,
      exec_id: "exec-raw-id-0001.01",
      origin: "gateway",
      first_observed_run_id: 51,
      first_observed_at_utc: "2026-07-15T14:35:00+00:00",
      execution_time_utc: "2026-07-15T14:31:00+00:00",
      broker_con_id: "broker-con-raw-id-265598",
      symbol: "AAPL",
      asset_class: "stock",
      currency: "USD",
      exchange: "NASDAQ",
      side: "SELL",
      quantity: 10,
      price: 220,
      order_id: 60001,
      perm_id: 70001,
      client_id: 1,
      order_ref: "trim",
      liquidation: 0,
      cumulative_quantity: 10,
      average_price: 220,
      corrects_exec_id: "exec-raw-id-0001",
      is_effective: true,
      commission_revisions: [{
        id: 900090,
        first_observed_run_id: 52,
        first_observed_at_utc: "2026-07-15T14:40:00+00:00",
        commission: 1,
        currency: "USD",
        realized_pnl: 125,
        yield_value: null,
        yield_redemption_date: null,
        is_latest: true,
      }],
    }],
  }],
} satisfies PortfolioBrokerActivityItem;

function page(over: Partial<PortfolioActivityPage> = {}): PortfolioActivityPage {
  return {
    accounts: [account],
    history_started_at_utc: "2026-07-14T05:00:00+00:00",
    items: [manualItem, unmatchedItem],
    summary: { item_count: 2, unmatched_count: 3, recent_window_days: 7 },
    next_cursor: null,
    ...over,
  };
}

async function mount(activityPage: PortfolioActivityPage, onOpenActivity = vi.fn()) {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(
      <PortfolioRecentActivity page={activityPage} onOpenActivity={onOpenActivity} />,
    );
  });
  return onOpenActivity;
}

describe("PortfolioRecentActivity", () => {
  it("renders real compact rows plus recent unmatched count and calls onOpenActivity", async () => {
    const onOpenActivity = await mount(page());

    expect(host!.textContent).toContain("近期活動");
    expect(host!.textContent).toContain("TSM 手動調整");
    expect(host!.textContent).toContain("更新 · 1 項欄位");
    expect(host!.textContent).toContain("MSFT 未匹配變動");
    expect(host!.textContent).toContain("殘差 -3");
    expect(host!.textContent).toContain("近 7 日有 3 筆未匹配變動");

    await act(async () => {
      host!.querySelector<HTMLButtonElement>('button[aria-label="開啟完整活動"]')!.click();
    });
    expect(onOpenActivity).toHaveBeenCalledTimes(1);
  });

  it("renders null when both items and unmatched_count are zero", async () => {
    await mount(page({
      items: [],
      summary: { item_count: 0, unmatched_count: 0, recent_window_days: 7 },
    }));

    expect(host!.childElementCount).toBe(0);
  });

  it("never renders broker raw-id-shaped fixture properties or activity detail authority", async () => {
    await mount(page({
      items: [brokerItem],
      summary: { item_count: 1, unmatched_count: 0, recent_window_days: 7 },
    }));

    expect(host!.textContent).toContain("AAPL 訂單成交");
    expect(host!.textContent).toContain("賣出 10 · 已實現獲利");
    for (const rawValue of [
      "order-raw-id-70001",
      "broker-account-raw-hash-123456789",
      "exec-raw-id-0001.01",
      "broker-con-raw-id-265598",
      "60001",
      "70001",
      "310031",
      "320032",
      "900090",
    ]) {
      expect(host!.textContent).not.toContain(rawValue);
    }
    expect(host!.textContent).not.toContain("成交修訂");
    expect(host!.textContent).not.toContain("佣金修訂");
    expect(host!.querySelectorAll("button")).toHaveLength(1);
  });
});
