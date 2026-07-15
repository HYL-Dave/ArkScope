/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PortfolioActivity } from "./PortfolioActivity";
import type {
  PortfolioActivityPage,
  PortfolioBrokerActivityItem,
  PortfolioCoverageGapActivityItem,
  PortfolioExecutionRevision,
  PortfolioHistoryStartActivityItem,
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
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  document.querySelectorAll(".ui-overlay-backdrop, .ui-row-action-menu")
    .forEach((node) => node.remove());
});

const account = {
  id: 2,
  label: "IBKR · 1a2b3c4d",
  broker: "ibkr",
  broker_account_id_hash: "1a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f809",
  archived: false,
} as const;

const revision = {
  id: 31,
  exec_id: "0001",
  origin: "gateway",
  first_observed_run_id: 50,
  first_observed_at_utc: "2026-07-15T14:32:00+00:00",
  execution_time_utc: "2026-07-15T14:31:00+00:00",
  broker_con_id: "265598",
  symbol: "AAPL",
  asset_class: "stock",
  currency: "USD",
  exchange: "NASDAQ",
  side: "SELL",
  quantity: 10,
  price: 219.5,
  order_id: 60001,
  perm_id: 70001,
  client_id: 1,
  order_ref: "trim",
  liquidation: 0,
  cumulative_quantity: 10,
  average_price: 219.5,
  corrects_exec_id: null,
  is_effective: false,
  commission_revisions: [],
} satisfies PortfolioExecutionRevision;

const correctedRevision = {
  ...revision,
  id: 32,
  exec_id: "0001.01",
  first_observed_run_id: 51,
  first_observed_at_utc: "2026-07-15T14:35:00+00:00",
  price: 220,
  average_price: 220,
  corrects_exec_id: "0001",
  is_effective: true,
  commission_revisions: [
    {
      id: 89,
      first_observed_run_id: 51,
      first_observed_at_utc: "2026-07-15T14:36:00+00:00",
      commission: 1.25,
      currency: "CAD",
      realized_pnl: 124.5,
      yield_value: null,
      yield_redemption_date: null,
      is_latest: false,
    },
    {
      id: 90,
      first_observed_run_id: 52,
      first_observed_at_utc: "2026-07-15T14:40:00+00:00",
      commission: 1,
      currency: "USD",
      realized_pnl: 125,
      yield_value: 2.5,
      yield_redemption_date: 20270115,
      is_latest: true,
    },
  ],
} satisfies PortfolioExecutionRevision;

const brokerItem = {
  id: "order:2:70001",
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
  annotation: {
    intent_label: "profit_take",
    note: "trimmed one third",
    updated_at_utc: "2026-07-15T14:40:00+00:00",
  },
  fills: [{
    family_root_id: 31,
    effective_revision_id: 32,
    revisions: [revision, correctedRevision],
  }],
} satisfies PortfolioBrokerActivityItem;

const unmatchedItem = {
  id: "unmatched:44",
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

const manualItem = {
  id: "manual:8",
  kind: "manual_adjustment",
  occurred_at_utc: "2026-07-15T13:00:00+00:00",
  account: { ...account, id: 1, label: "Manual", broker: "manual", broker_account_id_hash: null },
  symbol: "TSM",
  source: "manual",
  state: "manual_adjustment",
  annotation: null,
  position_id: 7,
  action: "update",
  changes: [
    { field: "quantity", before: 5, after: 8 },
    { field: "notes", before: null, after: "manual lot" },
  ],
} satisfies PortfolioManualActivityItem;

const historyItem = {
  id: "history:2:50",
  kind: "history_start",
  occurred_at_utc: "2026-07-14T05:00:00+00:00",
  account,
  source: "system",
  state: "history_start",
  capture_run_id: 50,
} satisfies PortfolioHistoryStartActivityItem;

const gapItem = {
  id: "gap:global:52:53",
  kind: "coverage_gap",
  occurred_at_utc: "2026-07-15T05:00:00+00:00",
  account: null,
  source: "system",
  state: "coverage_gap",
  from_run_id: 52,
  to_run_id: 53,
  from_as_of_utc: "2026-07-14T05:00:00+00:00",
  to_as_of_utc: "2026-07-15T05:00:00+00:00",
  reason_code: "broker_day_gap",
} satisfies PortfolioCoverageGapActivityItem;

function page(over: Partial<PortfolioActivityPage> = {}): PortfolioActivityPage {
  return {
    accounts: [account],
    history_started_at_utc: "2026-07-14T05:00:00+00:00",
    items: [brokerItem],
    summary: { item_count: 1, unmatched_count: 0, recent_window_days: null },
    next_cursor: null,
    ...over,
  };
}

type StubResult = unknown | Promise<unknown> | {
  body: unknown;
  status: number;
};

function stubFetch(handler: (url: string, init?: RequestInit) => StubResult) {
  const calls: Array<{ url: string; method: string; body: unknown }> = [];
  vi.stubGlobal("fetch", vi.fn(async (url: unknown, init?: RequestInit) => {
    const resolved = String(url);
    calls.push({
      url: resolved,
      method: init?.method ?? "GET",
      body: init?.body ? JSON.parse(String(init.body)) : null,
    });
    const result = await handler(resolved, init);
    const response = result && typeof result === "object" && "status" in result && "body" in result
      ? result as { body: unknown; status: number }
      : { body: result, status: 200 };
    return new Response(JSON.stringify(response.body), {
      status: response.status,
      headers: { "content-type": "application/json" },
    });
  }));
  return calls;
}

async function mount() {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(<PortfolioActivity localTimeZone="Asia/Taipei" />);
  });
}

async function flush() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

async function clickButton(text: string, owner: ParentNode = host!) {
  const button = Array.from(owner.querySelectorAll<HTMLButtonElement>("button"))
    .find((candidate) => candidate.textContent?.includes(text) || candidate.getAttribute("aria-label")?.includes(text));
  if (!button) throw new Error(`button not found: ${text}; text=${owner.textContent}`);
  await act(async () => button.click());
  await flush();
}

async function openRowAction(label: string, index = 0) {
  const triggers = host!.querySelectorAll<HTMLButtonElement>('button[aria-label$="操作"]');
  await act(async () => triggers[index].click());
  await flush();
  await clickButton(label, document);
}

function setInput(input: HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement, value: string) {
  const prototype = input instanceof HTMLSelectElement
    ? HTMLSelectElement.prototype
    : input instanceof HTMLTextAreaElement
      ? HTMLTextAreaElement.prototype
      : HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(prototype, "value")?.set?.call(input, value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
  input.dispatchEvent(new Event("change", { bubbles: true }));
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

describe("PortfolioActivity", () => {
  it("shows loading then an honest empty history-not-started state", async () => {
    const pending = deferred<PortfolioActivityPage>();
    stubFetch(() => pending.promise);
    await mount();
    expect(host!.querySelector('[data-state="loading"]')?.textContent).toContain("載入活動");

    pending.resolve(page({ accounts: [], history_started_at_utc: null, items: [], summary: { item_count: 0, unmatched_count: 0, recent_window_days: null } }));
    await flush();
    expect(host!.textContent).toContain("活動歷史尚未開始");
    expect(host!.textContent).toContain("尚無活動紀錄");
  });

  it("renders broker direct facts separately from confirmed intent", async () => {
    stubFetch(() => page());
    await mount();
    await flush();

    const objective = host!.querySelector(".portfolio-activity-objective")!;
    const intent = host!.querySelector(".portfolio-activity-intent")!;
    expect(objective).not.toBe(intent);
    expect(objective.textContent).toContain("已實現獲利");
    expect(objective.textContent).not.toContain("獲利了結");
    expect(intent.textContent).toContain("獲利了結");
    expect(intent.textContent).not.toContain("已實現獲利");
  });

  it("expands immutable fills corrections and commission revisions", async () => {
    stubFetch(() => page());
    await mount();
    await flush();
    await openRowAction("查看明細");

    const detail = host!.querySelector(".portfolio-activity-detail")!;
    expect(detail.textContent).toContain("0001");
    expect(detail.textContent).toContain("0001.01");
    expect(detail.textContent).toContain("修正 0001");
    expect(detail.textContent).toContain("Commission #89");
    expect(detail.textContent).toContain("Commission #90");
    expect(detail.textContent).toContain("最新");
    const execution31 = Array.from(detail.querySelectorAll(".portfolio-activity-revision"))
      .find((row) => row.textContent?.includes("Exec 0001 ·"))!;
    const execution32 = Array.from(detail.querySelectorAll(".portfolio-activity-revision"))
      .find((row) => row.textContent?.includes("Exec 0001.01"))!;
    expect(execution31.textContent).toContain("首次觀察 Run #50");
    expect(execution31.textContent).toContain("07-15 22:32 Asia/Taipei");
    expect(execution32.textContent).toContain("首次觀察 Run #51");
    expect(execution32.textContent).toContain("07-15 22:35 Asia/Taipei");
    const commission89 = Array.from(detail.querySelectorAll("li"))
      .find((row) => row.textContent?.includes("Commission #89"))!;
    const commission90 = Array.from(detail.querySelectorAll("li"))
      .find((row) => row.textContent?.includes("Commission #90"))!;
    expect(commission89.textContent).toContain("已實現損益 124.5 CAD");
    expect(commission89.textContent).not.toContain("已實現損益 124.5 USD");
    expect(commission89.textContent).toContain("首次觀察 Run #51");
    expect(commission89.textContent).toContain("07-15 22:36 Asia/Taipei");
    expect(commission89.textContent).toContain("Yield 未知");
    expect(commission89.textContent).toContain("贖回日 未知");
    expect(commission90.textContent).toContain("首次觀察 Run #52");
    expect(commission90.textContent).toContain("07-15 22:40 Asia/Taipei");
    expect(commission90.textContent).toContain("Yield 2.5");
    expect(commission90.textContent).toContain("贖回日 20270115");
  });

  it("keeps missing-perm execution rows independent", async () => {
    const first = { ...brokerItem, id: "execution:2:41", kind: "execution", symbol: "NO-PERM-ONE", fills: [{ ...brokerItem.fills[0], family_root_id: 41, effective_revision_id: 41 }] } satisfies PortfolioBrokerActivityItem;
    const second = { ...brokerItem, id: "execution:2:42", kind: "execution", symbol: "NO-PERM-TWO", fills: [{ ...brokerItem.fills[0], family_root_id: 42, effective_revision_id: 42 }] } satisfies PortfolioBrokerActivityItem;
    stubFetch(() => page({ items: [first, second], summary: { item_count: 2, unmatched_count: 0, recent_window_days: null } }));
    await mount();
    await flush();

    expect(host!.textContent).toContain("NO-PERM-ONE");
    expect(host!.textContent).toContain("NO-PERM-TWO");
    expect(host!.querySelectorAll("tbody > tr:not(.ui-data-table-expanded)")).toHaveLength(2);
  });

  it("renders pending commission and realized PnL as unknown never zero or outcome", async () => {
    const pending = {
      ...brokerItem,
      id: "execution:2:55",
      state: "outcome_unknown",
      annotation: null,
      objective: {
        ...brokerItem.objective,
        average_price: null,
        gross_notional: null,
        commission: null,
        commission_currency: null,
        realized_pnl: null,
        realized_outcome: "unknown",
        position_direction: "unknown",
        close_scope: "unknown",
        position_context: "unknown",
      },
    } satisfies PortfolioBrokerActivityItem;
    stubFetch(() => page({ items: [pending] }));
    await mount();
    await flush();
    await openRowAction("查看明細");

    const objective = host!.querySelector(".portfolio-activity-objective")!;
    expect(objective.textContent).toContain("結果未知");
    expect(objective.textContent).not.toContain("已實現獲利");
    expect(host!.querySelector(".portfolio-activity-detail")?.textContent).toContain("佣金 未知");
    expect(host!.querySelector(".portfolio-activity-detail")?.textContent).toContain("已實現損益 未知");
    expect(host!.querySelector(".portfolio-activity-detail")?.textContent).not.toContain("佣金 0");
  });

  it("exposes unmatched arithmetic window and coverage", async () => {
    stubFetch(() => page({ items: [unmatchedItem] }));
    await mount();
    await flush();
    await openRowAction("查看明細");

    const detail = host!.querySelector(".portfolio-activity-detail")!;
    for (const expected of ["調整前 20", "調整後 15", "預期 18", "殘差 -3", "Run #52 → #53", "覆蓋不完整", "position_delta_unexplained"]) {
      expect(detail.textContent).toContain(expected);
    }
  });

  it("exposes manual field changes without execution or PnL claims", async () => {
    stubFetch(() => page({ items: [manualItem] }));
    await mount();
    await flush();
    await openRowAction("查看明細");

    const detail = host!.querySelector(".portfolio-activity-detail")!;
    expect(detail.textContent).toContain("quantity");
    expect(detail.textContent).toContain("5 → 8");
    expect(detail.textContent).toContain("notes");
    expect(detail.textContent).not.toContain("成交價");
    expect(detail.textContent).not.toContain("已實現損益");
  });

  it("keeps history-start and coverage-gap markers visible", async () => {
    const openEndedGap = { ...gapItem, from_run_id: null, from_as_of_utc: null } satisfies PortfolioCoverageGapActivityItem;
    stubFetch(() => page({ items: [historyItem, openEndedGap], summary: { item_count: 2, unmatched_count: 0, recent_window_days: null } }));
    await mount();
    await flush();

    expect(host!.textContent).toContain("活動歷史起點");
    expect(host!.textContent).toContain("Broker 日期覆蓋缺口");
    expect(host!.textContent).toContain("系統覆蓋");
    await openRowAction("查看明細", 1);
    expect(host!.querySelector(".portfolio-activity-detail")?.textContent).toContain("開始 未知");
  });

  it("encodes all filters and ET dates in the exact GET query", async () => {
    const calls = stubFetch(() => page({ items: [] }));
    await mount();
    await flush();
    setInput(host!.querySelector('input[aria-label="開始日期（ET）"]')!, "2026-07-01");
    setInput(host!.querySelector('input[aria-label="結束日期（ET）"]')!, "2026-07-15");
    setInput(host!.querySelector('select[aria-label="帳戶篩選"]')!, "2");
    setInput(host!.querySelector('input[aria-label="Symbol 篩選"]')!, "BRK/B & Co");
    setInput(host!.querySelector('select[aria-label="來源篩選"]')!, "broker");
    setInput(host!.querySelector('select[aria-label="狀態篩選"]')!, "realized_gain");
    await clickButton("套用篩選");

    expect(calls.at(-1)?.url.endsWith("/portfolio/activity?date_from_et=2026-07-01&date_to_et=2026-07-15&account_id=2&symbol=BRK%2FB+%26+Co&source=broker&state=realized_gain")).toBe(true);
  });

  it("appends next cursor once without duplicating activity IDs", async () => {
    let reads = 0;
    const calls = stubFetch((url) => {
      reads += 1;
      return reads === 1
        ? page({ next_cursor: "next / opaque", items: [brokerItem] })
        : page({ next_cursor: null, items: [brokerItem, unmatchedItem], summary: { item_count: 2, unmatched_count: 1, recent_window_days: null } });
    });
    await mount();
    await flush();
    await clickButton("載入更多");

    expect(calls.at(-1)?.url.endsWith("/portfolio/activity?cursor=next+%2F+opaque")).toBe(true);
    expect(host!.querySelectorAll("tbody > tr:not(.ui-data-table-expanded)")).toHaveLength(2);
    expect(calls.filter((call) => call.url.includes("cursor="))).toHaveLength(1);
  });

  it("does not let a delayed older filter response clobber newer state", async () => {
    const oldResponse = deferred<PortfolioActivityPage>();
    stubFetch((url) => {
      if (url.includes("symbol=OLD")) return oldResponse.promise;
      if (url.includes("symbol=NEW")) return page({ items: [{ ...brokerItem, symbol: "NEW" }] });
      return page({ items: [] });
    });
    await mount();
    await flush();
    const symbol = host!.querySelector<HTMLInputElement>('input[aria-label="Symbol 篩選"]')!;
    setInput(symbol, "OLD");
    await clickButton("套用篩選");
    setInput(symbol, "NEW");
    await clickButton("套用篩選");
    expect(host!.textContent).toContain("NEW");

    oldResponse.resolve(page({ items: [{ ...brokerItem, symbol: "OLD" }] }));
    await flush();
    expect(host!.textContent).toContain("NEW");
    expect(host!.textContent).not.toContain("OLD");
  });

  it("clears stale append busy state when a full reload supersedes it", async () => {
    const staleAppend = deferred<PortfolioActivityPage>();
    stubFetch((url) => {
      if (url.includes("cursor=old-cursor")) return staleAppend.promise;
      if (url.includes("symbol=NEW")) {
        return page({
          items: [{ ...brokerItem, symbol: "NEW" }],
          next_cursor: "new-cursor",
        });
      }
      return page({ next_cursor: "old-cursor" });
    });
    await mount();
    await flush();
    await clickButton("載入更多");

    const symbol = host!.querySelector<HTMLInputElement>(
      'input[aria-label="Symbol 篩選"]',
    )!;
    setInput(symbol, "NEW");
    await clickButton("套用篩選");

    const loadMore = Array.from(host!.querySelectorAll<HTMLButtonElement>("button"))
      .find((button) => button.textContent?.includes("載入更多"))!;
    expect(loadMore.disabled).toBe(false);

    staleAppend.resolve(page({ items: [unmatchedItem], next_cursor: null }));
    await flush();
    expect(loadMore.disabled).toBe(false);
    expect(host!.textContent).toContain("NEW");
    expect(host!.textContent).not.toContain("MSFT");
  });

  it("keeps failed annotation save authored then updates locally from exact replacement PUT", async () => {
    let puts = 0;
    const calls = stubFetch((url, init) => {
      if (init?.method === "PUT") {
        puts += 1;
        if (puts === 1) return { status: 503, body: { detail: { message: "SECRET DB STACK" } } };
        return { intent_label: "rebalance", note: "target 60/40", updated_at_utc: "2026-07-15T15:10:00+00:00" };
      }
      return page();
    });
    await mount();
    await flush();
    await openRowAction("編輯註記");
    const drawer = document.querySelector<HTMLElement>('.ui-drawer[role="dialog"]')!;
    setInput(drawer.querySelector<HTMLSelectElement>('select[aria-label="確認意圖"]')!, "rebalance");
    setInput(drawer.querySelector<HTMLTextAreaElement>('textarea[aria-label="註記"]')!, "target 60/40");
    await clickButton("儲存註記", document);
    expect(document.body.textContent).toContain("註記未儲存；請重試");
    expect(document.body.textContent).not.toContain("SECRET DB STACK");
    expect(document.querySelector<HTMLTextAreaElement>('textarea[aria-label="註記"]')?.value).toBe("target 60/40");

    await clickButton("儲存註記", document);
    expect(calls.filter((call) => call.method === "PUT").at(-1)).toMatchObject({
      url: expect.stringMatching(/\/portfolio\/activity\/annotations\/order%3A2%3A70001$/),
      body: { intent_label: "rebalance", note: "target 60/40" },
    });
    expect(document.querySelector('.ui-drawer[role="dialog"]')).toBeNull();
    expect(host!.querySelector(".portfolio-activity-intent")?.textContent).toContain("再平衡");
    expect(calls.filter((call) => call.method === "GET")).toHaveLength(1);
  });

  it("clears annotation through ConfirmDialog and retains typed copy after failed DELETE", async () => {
    let deletes = 0;
    const confirm = vi.spyOn(window, "confirm");
    const calls = stubFetch((url, init) => {
      if (init?.method === "DELETE") {
        deletes += 1;
        if (deletes === 1) return { status: 503, body: { detail: "RAW DELETE SECRET" } };
        return { deleted: true, activity_id: brokerItem.id };
      }
      return page();
    });
    await mount();
    await flush();
    await openRowAction("編輯註記");
    const textarea = document.querySelector<HTMLTextAreaElement>('textarea[aria-label="註記"]')!;
    setInput(textarea, "keep this authored copy");
    const clearButton = Array.from(document.querySelectorAll<HTMLButtonElement>("button"))
      .find((button) => button.textContent?.includes("清除註記"))!;
    await clickButton("清除註記", document);
    const cancelDialog = document.querySelector<HTMLElement>('.ui-confirm-dialog[role="dialog"]')!;
    expect(cancelDialog).not.toBeNull();
    expect(confirm).not.toHaveBeenCalled();
    await clickButton("取消", cancelDialog);
    expect(document.activeElement).toBe(clearButton);

    await clickButton("清除註記", document);
    await clickButton("確認清除", document);
    expect(document.body.textContent).toContain("註記未清除；請重試");
    expect(document.body.textContent).not.toContain("RAW DELETE SECRET");
    expect(document.querySelector<HTMLTextAreaElement>('textarea[aria-label="註記"]')?.value).toBe("keep this authored copy");
    expect(document.activeElement).toBe(clearButton);

    await clickButton("清除註記", document);
    await clickButton("確認清除", document);
    expect(calls.filter((call) => call.method === "DELETE")).toHaveLength(2);
    expect(document.querySelector('.ui-drawer[role="dialog"]')).toBeNull();
    expect(host!.querySelector(".portfolio-activity-intent")?.textContent).toContain("未確認");
    expect(calls.filter((call) => call.method === "GET")).toHaveLength(1);
  });

  it("shows market rows in ET first and injected local time second", async () => {
    stubFetch(() => page());
    await mount();
    await flush();

    expect(host!.querySelector("tbody .portfolio-activity-time")?.textContent).toBe("07-15 10:31 ET · 07-15 22:31 Asia/Taipei");
  });

  it("shows authored read cause and next action without raw exception detail", async () => {
    let reads = 0;
    stubFetch(() => {
      reads += 1;
      if (reads === 1) return page({ next_cursor: "stale-cursor" });
      return { status: 503, body: { detail: { message: "sqlite SECRET account DU123 stack" } } };
    });
    await mount();
    await flush();
    expect(host!.textContent).toContain("AAPL");
    expect(host!.textContent).toContain("載入更多");
    setInput(host!.querySelector<HTMLInputElement>('input[aria-label="Symbol 篩選"]')!, "FAIL");
    await clickButton("套用篩選");

    expect(host!.textContent).toContain("活動載入失敗；請重新整理");
    expect(host!.textContent).toContain("重新整理");
    expect(host!.textContent).not.toContain("AAPL");
    expect(host!.textContent).not.toContain("載入更多");
    expect(host!.textContent).not.toContain("sqlite SECRET");
    expect(host!.textContent).not.toContain("DU123");
  });
});
