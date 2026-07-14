/** @vitest-environment jsdom */
import React, { type ReactNode } from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  PortfolioAccountDetails,
  PortfolioAccountSummary,
} from "./PortfolioAccountOverview";
import type { PortfolioOverview } from "./api";
import { formatSystemTimestamp } from "./timeDisplay";

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

afterEach(() => {
  if (root) act(() => root!.unmount());
  root = null;
  host?.remove();
  host = null;
});

const overview = (over: Partial<PortfolioOverview> = {}): PortfolioOverview => ({
  accounts: [
    {
      id: 1,
      label: "Manual",
      broker: "manual",
      broker_account_id_hash: null,
      sync_mode: "manual",
      base_currency: "USD",
      include_in_total: true,
      canonical_last_sync_at: null,
      latest_snapshot: null,
    },
    {
      id: 2,
      label: "IBKR · hash-one",
      broker: "ibkr",
      broker_account_id_hash: "hash-one",
      sync_mode: "ibkr_review",
      base_currency: "USD",
      include_in_total: true,
      canonical_last_sync_at: "2026-07-14T05:01:00+00:00",
      latest_snapshot: {
        capture_run_id: 50,
        as_of_utc: "2026-07-14T05:00:00+00:00",
        as_of_kind: "capture_completed",
        source: "ibkr_gateway",
        base_currency: "USD",
        net_liquidation: 100_000,
        total_cash_value: 10_000,
        settled_cash: 9_000,
        gross_position_value: 90_000,
        buying_power: 25_000,
        available_funds: 20_000,
        initial_margin_requirement: 15_000,
        maintenance_margin_requirement: 12_000,
        daily_realized_pnl: 125,
        daily_unrealized_pnl: -25,
        daily_total_pnl: 100,
      },
    },
  ],
  manual_subtotal: {
    included_account_ids: [1],
    totals: {
      currency_basis: "per_currency",
      per_currency: {
        USD: { position_count: 1, market_value: 500, unrealized_pnl: 25 },
        TWD: { position_count: 1, market_value: 10_000, unrealized_pnl: -500 },
      },
      broker_base: null,
    },
  },
  ...over,
});

function render(node: ReactNode) {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  act(() => root!.render(node));
}

function renderSummary(
  value = overview(),
  onToggleAggregate = vi.fn(),
) {
  render(
    <PortfolioAccountSummary
      overview={value}
      busyAccountId={null}
      onToggleAggregate={onToggleAggregate}
    />,
  );
  return onToggleAggregate;
}

function metricValue(label: string): string {
  const metric = Array.from(host!.querySelectorAll<HTMLElement>(".ui-metric"))
    .find((candidate) => candidate.textContent?.includes(label));
  if (!metric) throw new Error(`metric not found: ${label}`);
  return metric.querySelector("strong")?.textContent ?? "";
}

describe("Portfolio account overview", () => {
  it("renders_every_visible_account_even_without_snapshot", () => {
    const value = overview({
      accounts: overview().accounts.map((account) => ({
        ...account,
        latest_snapshot: null,
      })),
    });

    renderSummary(value);

    expect(host!.textContent).toContain("Manual");
    expect(host!.textContent).toContain("IBKR · hash-one");
    expect(host!.textContent).toContain("無帳戶價值資料");
    expect(host!.textContent).toContain("尚無帳戶快照");
  });

  it("renders_broker_values_and_both_timestamps", () => {
    renderSummary();

    expect(metricValue("Net Liquidation")).not.toBe("—");
    expect(metricValue("Total Cash")).not.toBe("—");
    expect(metricValue("Buying Power")).not.toBe("—");
    expect(host!.textContent).toContain(
      `Broker 觀察：${formatSystemTimestamp("2026-07-14T05:00:00+00:00")}`,
    );
    expect(host!.textContent).toContain(
      `本地持倉核准 / 同步：${formatSystemTimestamp("2026-07-14T05:01:00+00:00")}`,
    );
  });

  it("labels_daily_total_as_realized_plus_unrealized", () => {
    renderSummary();

    expect(host!.textContent).toContain("今日損益合計（已實現 + 未實現，ET）");
    expect(metricValue("今日損益合計（已實現 + 未實現，ET）")).not.toBe("—");
  });

  it("does_not_invent_daily_total_when_one_provider_leg_is_missing", () => {
    const value = overview();
    value.accounts[1].latest_snapshot = {
      ...value.accounts[1].latest_snapshot!,
      daily_unrealized_pnl: null,
      daily_total_pnl: null,
    };

    renderSummary(value);

    expect(metricValue("今日已實現損益（ET）")).not.toBe("—");
    expect(metricValue("今日未實現損益（ET）")).toBe("—");
    expect(metricValue("今日損益合計（已實現 + 未實現，ET）")).toBe("—");
  });

  it("renders_manual_subtotal_by_currency_without_overall_net_worth", () => {
    renderSummary();

    const subtotal = host!.querySelector<HTMLElement>(
      '[aria-label="手動帳戶持倉小計"]',
    )!;
    expect(subtotal.textContent).toContain("手動帳戶持倉小計");
    expect(subtotal.textContent).toContain("USD");
    expect(subtotal.textContent).toContain("TWD");
    expect(host!.textContent).not.toContain("整體淨值");
  });

  it("keeps_manual_subtotal_separate_from_ibkr_net_liquidation", () => {
    renderSummary();

    const subtotal = host!.querySelector<HTMLElement>(
      '[aria-label="手動帳戶持倉小計"]',
    )!;
    expect(subtotal.textContent).toContain("不與 IBKR Net Liquidation 相加");
    expect(subtotal.textContent).not.toContain("Net Liquidation$100,000");
  });

  it("renders_all_latest_snapshot_fields_in_account_details", () => {
    render(<PortfolioAccountDetails overview={overview()} />);

    for (const label of [
      "Capture Run",
      "Base Currency",
      "Net Liquidation",
      "Total Cash",
      "Settled Cash",
      "Gross Position Value",
      "Buying Power",
      "Available Funds",
      "Initial Margin",
      "Maintenance Margin",
      "今日已實現（ET）",
      "今日未實現（ET）",
      "今日合計（已實現 + 未實現，ET）",
      "Broker 觀察",
      "本地持倉核准 / 同步",
    ]) {
      expect(host!.textContent).toContain(label);
    }
  });

  it("keeps_account_details_inside_the_data_table_scroll_owner", () => {
    render(<PortfolioAccountDetails overview={overview()} />);

    const table = host!.querySelector('table[aria-label="帳戶最新快照明細"]');
    expect(table).not.toBeNull();
    expect(table!.parentElement?.classList.contains("ui-data-table-wrap")).toBe(true);
    expect(table!.closest(".portfolio-account-details")).not.toBeNull();
  });

  it("emits_include_toggle_for_each_account", () => {
    const onToggle = renderSummary(overview(), vi.fn());
    const toggles = host!.querySelectorAll<HTMLInputElement>(
      'input[type="checkbox"][aria-label$="納入總計"]',
    );

    expect(toggles).toHaveLength(2);
    act(() => toggles[1].click());
    expect(onToggle).toHaveBeenCalledWith(2, false);
  });

  it("never_renders_an_unexpected_raw_broker_account_id_property", () => {
    const value = overview();
    value.accounts[1] = {
      ...value.accounts[1],
      broker_account_id: "DU-RAW-SHOULD-NOT-RENDER",
    } as typeof value.accounts[number] & { broker_account_id: string };

    renderSummary(value);

    expect(host!.textContent).not.toContain("DU-RAW-SHOULD-NOT-RENDER");
  });
});
