/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { HoldingsView } from "./Holdings";
import type {
  PortfolioAccount,
  PortfolioCaptureReview,
  PortfolioCaptureStart,
  PortfolioCaptureStatus,
  PortfolioActivityPage,
  PortfolioOverview,
  PortfolioPosition,
  PortfolioSnapshot,
  PortfolioSyncPreview,
} from "./api";

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

afterEach(() => {
  if (root) act(() => root!.unmount());
  root = null;
  host?.remove();
  host = null;
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const snapshot = (over: Partial<PortfolioSnapshot> = {}): PortfolioSnapshot => ({
  accounts: [{
    id: 1,
    label: "Manual",
    broker: "manual",
    sync_mode: "manual",
    base_currency: "USD",
    include_in_total: true,
  }],
  positions: [],
  totals: { currency_basis: "per_currency", per_currency: {}, broker_base: null },
  included_account_ids: [1],
  ...over,
});

const overview = (over: Partial<PortfolioOverview> = {}): PortfolioOverview => ({
  accounts: [{
    id: 1,
    label: "Manual",
    broker: "manual",
    broker_account_id_hash: null,
    sync_mode: "manual",
    base_currency: "USD",
    include_in_total: true,
    canonical_last_sync_at: null,
    latest_snapshot: null,
  }],
  manual_subtotal: {
    included_account_ids: [1],
    totals: { currency_basis: "per_currency", per_currency: {}, broker_base: null },
  },
  ...over,
});

type PortfolioApiResponse =
  | PortfolioAccount
  | PortfolioCaptureReview
  | PortfolioCaptureStart
  | PortfolioCaptureStatus
  | PortfolioActivityPage
  | PortfolioOverview
  | PortfolioPosition
  | PortfolioSnapshot
  | PortfolioSyncPreview
  | { ok: true };

const captureStatus = (over: Partial<PortfolioCaptureStatus> = {}): PortfolioCaptureStatus => ({
  settings: {
    enabled: true,
    interval_minutes: 15,
    source: "default",
    provider_configured: true,
  },
  provider_issue: null,
  running: false,
  next_due_at: "2026-07-14T05:15:00+00:00",
  latest_run: null,
  recent_runs: [],
  review: null,
  ...over,
});

const captureRun = (over: Partial<NonNullable<PortfolioCaptureStatus["latest_run"]>> = {}) => ({
  id: 51,
  trigger: "manual" as const,
  state: "succeeded" as const,
  started_at: "2026-07-14T05:00:00+00:00",
  finished_at: "2026-07-14T05:00:02+00:00",
  account_leg_state: "complete",
  execution_leg_state: "complete",
  position_leg_state: "complete",
  discovered_account_count: 2,
  new_account_count: 0,
  archived_activity_count: 0,
  inserted_execution_count: 0,
  inserted_commission_count: 0,
  unmatched_count: 0,
  data_conflict_count: 0,
  error_code: null,
  error_detail: null,
  ...over,
});

const emptyActivityPage = (): PortfolioActivityPage => ({
  accounts: [],
  history_started_at_utc: null,
  items: [],
  summary: { item_count: 0, unmatched_count: 0, recent_window_days: null },
  next_cursor: null,
});

const recentActivityPage = (): PortfolioActivityPage => ({
  accounts: [],
  history_started_at_utc: "2026-07-14T05:00:00+00:00",
  items: [{
    id: "manual:recent:40",
    kind: "manual_adjustment",
    occurred_at_utc: "2026-07-15T13:00:00+00:00",
    account: {
      id: 1,
      label: "Manual",
      broker: "manual",
      broker_account_id_hash: null,
      archived: false,
    },
    symbol: "NVDA",
    source: "manual",
    state: "manual_adjustment",
    annotation: null,
    position_id: 40,
    action: "create",
    changes: [{ field: "quantity", before: null, after: 3 }],
  }],
  summary: { item_count: 1, unmatched_count: 0, recent_window_days: 7 },
  next_cursor: null,
});

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

function stubFetch(
  handler: (url: string, init?: RequestInit) => PortfolioApiResponse | Promise<PortfolioApiResponse>,
  captureHandler?: () => PortfolioCaptureStatus | Promise<PortfolioCaptureStatus>,
  overviewHandler?: () => PortfolioOverview | Promise<PortfolioOverview>,
  recentHandler?: () => PortfolioActivityPage | Promise<PortfolioActivityPage>,
) {
  const calls: Array<{ url: string; method: string; body: unknown }> = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: unknown, init?: RequestInit) => {
      const u = String(url);
      calls.push({
        url: u,
        method: init?.method ?? "GET",
        body: init?.body ? JSON.parse(String(init.body)) : null,
      });
      const method = init?.method ?? "GET";
      const parsed = new URL(u);
      const isActivity = parsed.pathname === "/portfolio/activity" && method === "GET";
      const payload = isActivity
        ? parsed.searchParams.get("recent") === "true"
          ? await (recentHandler?.() ?? emptyActivityPage())
          : emptyActivityPage()
        : u.endsWith("/portfolio/capture") && method === "GET"
        ? await (captureHandler?.() ?? captureStatus())
        : u.endsWith("/portfolio/overview") && method === "GET"
          ? await (overviewHandler?.() ?? overview())
          : await handler(u, init);
      return new Response(JSON.stringify(payload), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }),
  );
  return calls;
}

function stubShellOverlay(initialMatches: boolean) {
  let matches = initialMatches;
  let media = "";
  const listeners = new Set<EventListener>();
  const mediaQueryList = {
    get matches() { return matches; },
    get media() { return media; },
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn((_type: string, listener: EventListener) => {
      listeners.add(listener);
    }),
    removeEventListener: vi.fn((_type: string, listener: EventListener) => {
      listeners.delete(listener);
    }),
    dispatchEvent: vi.fn(() => true),
  } as unknown as MediaQueryList;
  const matchMedia = vi.fn((query: string) => {
    media = query;
    return mediaQueryList;
  });
  vi.stubGlobal("matchMedia", matchMedia);
  return {
    matchMedia,
    setMatches(next: boolean) {
      matches = next;
      const event = new Event("change");
      listeners.forEach((listener) => listener.call(mediaQueryList, event));
    },
  };
}

function activityCalls(
  calls: Array<{ url: string; method: string; body: unknown }>,
  recent: boolean,
) {
  return calls.filter((call) => {
    const parsed = new URL(call.url);
    return call.method === "GET"
      && parsed.pathname === "/portfolio/activity"
      && (parsed.searchParams.get("recent") === "true") === recent;
  });
}

async function mount() {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(<HoldingsView />);
  });
}

async function flush() {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

async function buttonByText(text: string): Promise<HTMLButtonElement> {
  for (let i = 0; i < 6; i += 1) {
    const buttons = Array.from(document.querySelectorAll("button"));
    const found = buttons.find((button) => button.textContent?.trim() === text)
      ?? buttons.find((button) => button.textContent?.includes(text));
    if (found) return found;
    await flush();
  }
  throw new Error(`button not found: ${text}; text=${host?.textContent ?? ""}`);
}

async function openRowActions(label: string): Promise<HTMLButtonElement> {
  const trigger = host!.querySelector<HTMLButtonElement>(`button[aria-label="${label} 操作"]`);
  if (!trigger) throw new Error(`row action trigger not found: ${label}`);
  await act(async () => {
    trigger.click();
  });
  return trigger;
}

describe("HoldingsView", () => {
  it("shows_loading_before_the_first_portfolio_response", async () => {
    const firstPortfolio = deferred<PortfolioSnapshot>();
    stubFetch(() => firstPortfolio.promise);

    await mount();

    expect(host!.querySelector('[data-state="loading"]')?.textContent).toContain("載入持倉");

    await act(async () => {
      firstPortfolio.resolve(snapshot());
      await firstPortfolio.promise;
    });
  });

  it("renders account-labelled positions and filters by account", async () => {
    const accounts: PortfolioAccount[] = [{
      id: 1,
      label: "Manual",
      broker: "manual",
      sync_mode: "manual",
      base_currency: "USD",
      include_in_total: true,
    }, {
      id: 2,
      label: "IBKR DU123",
      broker: "ibkr",
      sync_mode: "ibkr_review",
      base_currency: "USD",
      include_in_total: true,
    }];
    stubFetch(() => snapshot({
      accounts,
      positions: [
        {
          id: 10,
          account_id: 1,
          symbol: "NVDA",
          asset_class: "stock",
          quantity: 3,
          avg_cost: 212.84,
          currency: "USD",
          market_value: 61086,
          unrealized_pnl: -2765,
          notes: "core",
        },
        {
          id: 11,
          account_id: 2,
          broker: "ibkr",
          symbol: "AAPL",
          asset_class: "stock",
          quantity: 1,
          avg_cost: 190,
          currency: "USD",
          market_value: 200,
          unrealized_pnl: 10,
        },
      ],
    }), undefined, () => overview({
      accounts: [{
        ...overview().accounts[0],
      }, {
        id: 2,
        label: "IBKR · safe-hash",
        broker: "ibkr",
        broker_account_id_hash: "safe-hash",
        sync_mode: "ibkr_review",
        base_currency: "USD",
        include_in_total: true,
        canonical_last_sync_at: null,
        latest_snapshot: null,
      }],
    }));

    await mount();
    await flush();

    expect(host!.querySelectorAll("h1")).toHaveLength(1);
    expect(host!.querySelector('[data-state="ready"]')?.textContent).toContain("2 筆持倉");
    expect(host!.textContent).toContain("Manual");
    expect(host!.textContent).toContain("IBKR · safe-hash");
    expect(host!.textContent).toContain("NVDA");
    expect(host!.textContent).toContain("AAPL");
    expect(host!.textContent).not.toContain("IBKR DU123");
    expect(host!.textContent).not.toContain("Currency basis");
    expect(host!.textContent).toContain("Avg Cost");
    expect(host!.textContent).toContain("212.84");
    expect(host!.textContent).toContain("61,086");
    expect(host!.textContent).toContain("-2,765");

    const filter = host!.querySelector<HTMLSelectElement>(
      'select[aria-label="持倉帳戶篩選"]',
    )!;
    await act(async () => {
      filter.value = "2";
      filter.dispatchEvent(new Event("change", { bubbles: true }));
    });

    expect(host!.textContent).not.toContain("NVDA");
    expect(host!.textContent).toContain("AAPL");
  });

  it("keeps_canonical_positions_usable_when_the_additive_overview_fails", async () => {
    const calls = stubFetch(
      () => snapshot({
        positions: [{
          id: 10,
          account_id: 1,
          broker: "manual",
          symbol: "NVDA",
          asset_class: "stock",
          quantity: 3,
          currency: "USD",
        }],
      }),
      undefined,
      () => Promise.reject(new Error("stale sidecar")),
    );

    await mount();
    await flush();

    expect(calls.some((call) => call.url.endsWith("/portfolio"))).toBe(true);
    expect(calls.some((call) => call.url.endsWith("/portfolio/overview"))).toBe(true);
    expect(host!.textContent).toContain("帳戶總覽無法載入；持倉仍可使用");
    expect(host!.textContent).not.toContain("stale sidecar");
    expect(host!.textContent).toContain("NVDA");
    expect(host!.querySelector('button[aria-label="NVDA 操作"]')).not.toBeNull();
  });

  it("keeps_account_summary_visible_above_every_completed_tab", async () => {
    stubFetch(() => snapshot());
    await mount();
    await flush();

    for (const label of ["持倉", "活動", "帳戶明細", "同步紀錄"]) {
      await act(async () => {
        (await buttonByText(label)).click();
      });
      const summary = host!.querySelector('[aria-label="帳戶總覽"]')!;
      const tablist = host!.querySelector('[role="tablist"]')!;
      expect(summary).not.toBeNull();
      expect(summary.compareDocumentPosition(tablist) & Node.DOCUMENT_POSITION_FOLLOWING)
        .toBeTruthy();
    }
  });

  it("switches_between_holdings_activity_account_details_and_sync_records", async () => {
    stubFetch(() => snapshot());
    await mount();
    await flush();

    expect(host!.querySelector('[role="tabpanel"]')?.id)
      .toBe("portfolio-panel-holdings");
    expect(host!.querySelector('[data-portfolio-capture-controls]')).toBeNull();

    await act(async () => {
      (await buttonByText("活動")).click();
    });
    await flush();
    expect(host!.querySelector('[role="tabpanel"]')?.id)
      .toBe("portfolio-panel-activity");
    expect(host!.querySelector('table[aria-label="持倉"]')).toBeNull();

    await act(async () => {
      (await buttonByText("帳戶明細")).click();
    });
    expect(host!.querySelector('table[aria-label="帳戶最新快照明細"]')).not.toBeNull();
    expect(host!.querySelector('table[aria-label="持倉"]')).toBeNull();

    await act(async () => {
      (await buttonByText("同步紀錄")).click();
    });
    await flush();
    expect(host!.querySelector('[data-portfolio-capture-controls]')).not.toBeNull();
    expect(host!.querySelector('table[aria-label="帳戶最新快照明細"]')).toBeNull();
  });

  it("renders_the_exact_completed_portfolio_tabs_without_a_placeholder", async () => {
    stubFetch(() => snapshot());
    await mount();
    await flush();

    const labels = Array.from(
      host!.querySelectorAll<HTMLButtonElement>('[role="tab"]'),
      (tab) => tab.textContent,
    );
    expect(labels).toEqual(["持倉", "活動", "帳戶明細", "同步紀錄"]);
  });

  it("mounts_capture_polling_only_while_sync_records_is_active", async () => {
    const calls = stubFetch(() => snapshot());
    await mount();
    await flush();

    expect(calls.filter((call) => call.url.endsWith("/portfolio/capture")))
      .toHaveLength(0);

    await act(async () => {
      (await buttonByText("同步紀錄")).click();
    });
    await flush();
    expect(calls.filter((call) => call.url.endsWith("/portfolio/capture")))
      .toHaveLength(1);

    await act(async () => {
      (await buttonByText("持倉")).click();
    });
    expect(host!.querySelector('[data-portfolio-capture-controls]')).toBeNull();
  });

  it("supports_arrow_home_and_end_keyboard_navigation_between_tabs", async () => {
    stubFetch(() => snapshot());
    await mount();
    await flush();

    const selected = () => host!.querySelector<HTMLButtonElement>(
      '[role="tab"][aria-selected="true"]',
    )!;
    const key = (target: HTMLButtonElement, value: string) => {
      act(() => {
        target.dispatchEvent(new KeyboardEvent("keydown", { key: value, bubbles: true }));
      });
    };

    selected().focus();
    key(selected(), "ArrowRight");
    expect(selected().textContent).toBe("活動");
    expect(document.activeElement).toBe(selected());

    key(selected(), "ArrowRight");
    expect(selected().textContent).toBe("帳戶明細");
    expect(document.activeElement).toBe(selected());

    key(selected(), "End");
    expect(selected().textContent).toBe("同步紀錄");
    key(selected(), "Home");
    expect(selected().textContent).toBe("持倉");
    key(selected(), "ArrowLeft");
    expect(selected().textContent).toBe("同步紀錄");
  });

  it("mounts and fetches PortfolioActivity only while the activity tab is selected", async () => {
    const { matchMedia } = stubShellOverlay(false);
    const calls = stubFetch(() => snapshot());
    await mount();
    await flush();

    expect(activityCalls(calls, false)).toHaveLength(0);
    expect(host!.querySelector(".portfolio-activity")).toBeNull();

    await act(async () => {
      (await buttonByText("活動")).click();
    });
    await flush();

    expect(activityCalls(calls, false)).toHaveLength(1);
    expect(host!.querySelector(".portfolio-activity")).not.toBeNull();

    await act(async () => {
      (await buttonByText("帳戶明細")).click();
    });
    expect(host!.querySelector(".portfolio-activity")).toBeNull();
    expect(activityCalls(calls, false)).toHaveLength(1);
    expect(matchMedia).toHaveBeenCalledWith("(max-width: 960px)");
  });

  it("at 959px skips the recent request and renders no panel or reserved width", async () => {
    const { matchMedia, setMatches } = stubShellOverlay(true);
    const delayedRecent = deferred<PortfolioActivityPage>();
    const recentHandler = vi.fn(() => delayedRecent.promise);
    const calls = stubFetch(() => snapshot(), undefined, undefined, recentHandler);
    await mount();
    await flush();

    expect(recentHandler).not.toHaveBeenCalled();
    expect(activityCalls(calls, true)).toHaveLength(0);
    expect(host!.querySelector(".portfolio-recent-activity")).toBeNull();
    expect(host!.querySelector('[data-has-recent="true"]')).toBeNull();
    expect(matchMedia).toHaveBeenCalledWith("(max-width: 960px)");

    await act(async () => setMatches(false));
    await flush();
    expect(recentHandler).toHaveBeenCalledTimes(1);

    await act(async () => setMatches(true));
    await act(async () => delayedRecent.resolve(recentActivityPage()));
    await flush();

    expect(host!.querySelector(".portfolio-recent-activity")).toBeNull();
    expect(host!.querySelector('[data-has-recent="true"]')).toBeNull();
  });

  it("at 961px renders a non-empty recent response beside positions", async () => {
    const { matchMedia } = stubShellOverlay(false);
    const calls = stubFetch(
      () => snapshot(),
      undefined,
      undefined,
      recentActivityPage,
    );
    await mount();
    await flush();

    const recentCalls = activityCalls(calls, true);
    expect(recentCalls).toHaveLength(1);
    const recentUrl = new URL(recentCalls[0].url);
    expect(recentUrl.searchParams.get("recent")).toBe("true");
    expect(recentUrl.searchParams.get("limit")).toBe("5");
    const layout = host!.querySelector('[data-has-recent="true"]')!;
    expect(layout.classList.contains("portfolio-holdings-layout")).toBe(true);
    expect(layout.children).toHaveLength(2);
    expect(layout.querySelector(".portfolio-holdings-primary table[aria-label=\"持倉\"]"))
      .not.toBeNull();
    expect(layout.querySelector(".portfolio-recent-activity")).not.toBeNull();
    expect(matchMedia).toHaveBeenCalledWith("(max-width: 960px)");
  });

  it("opens the activity tab from recent activity and removes the side panel", async () => {
    stubShellOverlay(false);
    const calls = stubFetch(
      () => snapshot(),
      undefined,
      undefined,
      recentActivityPage,
    );
    await mount();
    await flush();

    await act(async () => {
      host!.querySelector<HTMLButtonElement>('button[aria-label="開啟完整活動"]')!.click();
    });
    await flush();

    expect(host!.querySelector('[role="tab"][aria-selected="true"]')?.textContent)
      .toBe("活動");
    expect(host!.querySelector(".portfolio-recent-activity")).toBeNull();
    expect(host!.querySelector('[data-has-recent="true"]')).toBeNull();
    expect(activityCalls(calls, false)).toHaveLength(1);
  });

  it("invalidates recent synchronously and only for persisted manual financial changes", async () => {
    stubShellOverlay(false);
    let persisted = manualPosition();
    let patchCount = 0;
    let publishPreFinancialRecent: (() => void) | null = null;
    const financialPatch = deferred<PortfolioPosition>();
    const recentRequests: Array<ReturnType<typeof deferred<PortfolioActivityPage>>> = [];
    const recentHandler = vi.fn(() => {
      const request = deferred<PortfolioActivityPage>();
      recentRequests.push(request);
      return request.promise;
    });
    const calls = stubFetch((url, init) => {
      if (init?.method === "PATCH") {
        patchCount += 1;
        if (patchCount === 1) {
          persisted = manualPosition({ notes: "note only" });
          return persisted;
        }
        return financialPatch.promise.then((position) => {
          persisted = position;
          return position;
        });
      }
      if (
        init?.method === undefined
        && new URL(url).pathname === "/portfolio"
        && patchCount === 2
      ) {
        const publish = publishPreFinancialRecent;
        publishPreFinancialRecent = null;
        publish?.();
      }
      return snapshot({ positions: [persisted] });
    }, undefined, undefined, recentHandler);
    await mount();
    await flush();
    expect(recentHandler).toHaveBeenCalledTimes(1);

    await openRowActions("NVDA");
    await act(async () => {
      (await buttonByText("編輯")).click();
    });
    await act(async () => {
      setInput("Edit Notes", "note only");
      (await buttonByText("儲存")).click();
    });
    await flush();
    await flush();
    const recentRequestCountAfterNote = activityCalls(calls, true).length;

    await openRowActions("NVDA");
    await act(async () => {
      (await buttonByText("編輯")).click();
    });
    await act(async () => {
      setInput("Edit Quantity", "5");
      (await buttonByText("儲存")).click();
    });

    let stalePanelPublished = false;
    const observer = new MutationObserver((records) => {
      for (const record of records) {
        for (const node of record.addedNodes) {
          if (
            node instanceof Element
            && (node.matches(".portfolio-recent-activity")
              || node.querySelector(".portfolio-recent-activity"))
          ) {
            stalePanelPublished = true;
          }
        }
      }
    });
    observer.observe(host!, { childList: true, subtree: true });

    const preFinancialRecent = recentRequests[recentRequests.length - 1];
    publishPreFinancialRecent = () => preFinancialRecent.resolve(recentActivityPage());
    await act(async () => {
      financialPatch.resolve(manualPosition({ quantity: 5, notes: "note only" }));
      await Promise.resolve();
      await Promise.resolve();
    });
    await flush();
    observer.disconnect();

    expect(stalePanelPublished).toBe(false);
    expect(recentRequestCountAfterNote).toBe(1);
    expect(activityCalls(calls, true)).toHaveLength(2);
    expect(activityCalls(calls, true).length - recentRequestCountAfterNote).toBe(1);

    await act(async () => {
      for (const request of recentRequests) request.resolve(emptyActivityPage());
    });
  });

  it("can add a manual holding", async () => {
    const calls = stubFetch((url, init) => {
      if (init?.method === "POST") return { ok: true };
      return snapshot();
    });
    await mount();
    const ticker = host!.querySelector<HTMLInputElement>('input[aria-label="Ticker"]')!;
    const quantity = host!.querySelector<HTMLInputElement>('input[aria-label="Quantity"]')!;

    await act(async () => {
      ticker.value = "AAPL";
      ticker.dispatchEvent(new Event("input", { bubbles: true }));
      quantity.value = "2";
      quantity.dispatchEvent(new Event("input", { bubbles: true }));
      (await buttonByText("新增持倉")).click();
    });

    expect(calls.some((c) => c.method === "POST" && (c.body as any)?.symbol === "AAPL")).toBe(true);
  });

  it("shows captured review as review before applying", async () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    const review: PortfolioCaptureReview = {
      run_id: 51,
      changes: [{
        kind: "update",
        account_id: 1,
        account_label: "IBKR 主帳戶",
        broker_account_id_hash: "hash-one",
        broker_con_id: "1001",
        symbol: "MSFT",
        quantity: 1,
        before: { avg_cost: 90, market_value: 1200, unrealized_pnl: -50 },
        after: { avg_cost: 100.25, market_value: 1250, unrealized_pnl: -25.5 },
      }, {
        kind: "update",
        account_id: 2,
        account_label: "IBKR 子帳戶",
        broker_account_id_hash: "hash-two",
        broker_con_id: "1001",
        symbol: "MSFT",
        quantity: 2,
        before: { avg_cost: 200, market_value: 2200, unrealized_pnl: 50 },
        after: { avg_cost: 210.5, market_value: 2250, unrealized_pnl: 75 },
      }],
      applies: false,
    };
    stubFetch(
      () => snapshot(),
      () => captureStatus({ latest_run: captureRun(), recent_runs: [captureRun()], review }),
    );
    await mount();
    await flush();
    await act(async () => {
      (await buttonByText("同步紀錄")).click();
    });
    await flush();

    expect(host!.querySelector('[data-state="partial"]')?.textContent).toContain("2 項變更");
    const reviewTable = host!.querySelector('table[aria-label="持倉同步待檢視差異"]')!;
    expect(reviewTable.querySelectorAll("tbody tr")).toHaveLength(2);
    expect(Array.from(reviewTable.querySelectorAll("tbody tr")).map((row) => row.textContent))
      .toEqual([
        expect.stringContaining("90 → 100.25"),
        expect.stringContaining("200 → 210.5"),
      ]);
    expect(consoleError.mock.calls.flat().join(" ")).not.toContain("same key");
    expect(host!.textContent).not.toContain("DU111");
    expect(host!.textContent).not.toContain("DU222");
    expect(host!.textContent).toContain("MSFT");
    expect(host!.textContent).toContain("套用同步");
    expect(host!.textContent).toContain("Avg Cost");
    expect(host!.textContent).toContain("1,200 → 1,250");
    expect(host!.textContent).toContain("-50 → -25.5");
    expect(host!.textContent).toContain("2,200 → 2,250");
    expect(host!.textContent).toContain("50 → 75");
  });

  it("clears captured review and shows persisted positions after applying", async () => {
    let applied = false;
    const review: PortfolioCaptureReview = {
      run_id: 52,
      changes: [{
        kind: "add",
        account_id: 1,
        account_label: "IBKR 主帳戶",
        broker_account_id_hash: "hash-one",
        broker_con_id: "2002",
        symbol: "AMD",
        quantity: 400,
        before: null,
        after: { avg_cost: 92.26, market_value: 206704, unrealized_pnl: 169800 },
      }],
      applies: false,
    };
    const calls = stubFetch((url, init) => {
      if (url.endsWith("/portfolio/capture/runs/52/apply") && init?.method === "POST") {
        applied = true;
        return { run_id: 52, changes: [], applies: true };
      }
      if (applied && url.endsWith("/portfolio")) {
        return snapshot({
          positions: [{
            id: 20,
            account_id: 1,
            symbol: "AMD",
            asset_class: "stock",
            quantity: 400,
            avg_cost: 92.26,
            currency: "USD",
            market_value: 206704,
            unrealized_pnl: 169800,
          }],
        });
      }
      return snapshot();
    }, () => captureStatus({
      latest_run: captureRun({ id: 52 }),
      recent_runs: [captureRun({ id: 52 })],
      review: applied ? null : review,
    }));
    await mount();
    await act(async () => {
      (await buttonByText("同步紀錄")).click();
    });
    await flush();
    await act(async () => {
      (await buttonByText("套用同步")).click();
    });
    await flush();

    expect(calls.some((call) => call.url.endsWith("/portfolio/capture/runs/52/apply"))).toBe(true);
    expect(calls.filter((call) => call.url.endsWith("/portfolio")).length).toBeGreaterThanOrEqual(2);
    expect(calls.filter((call) => call.url.endsWith("/portfolio/overview")).length)
      .toBeGreaterThanOrEqual(2);
    await act(async () => {
      (await buttonByText("持倉")).click();
    });
    expect(host!.textContent).toContain("AMD");
    expect(host!.textContent).toContain("92.26");
    expect(host!.textContent).not.toContain("待套用差異");
  });

  it("holdings_renders_one_capture_control_surface_and_no_legacy_live_sync_buttons", async () => {
    stubFetch(() => snapshot());
    await mount();
    await flush();
    await act(async () => {
      (await buttonByText("同步紀錄")).click();
    });
    await flush();

    expect(host!.querySelectorAll("[data-portfolio-capture-controls]")).toHaveLength(1);
    expect(host!.textContent).toContain("同步紀錄");
    expect(host!.textContent).not.toContain("預覽 IBKR 同步");
    expect(host!.textContent).not.toContain("IBKR 同步預覽");
  });

  it("updates whether an account participates in aggregate totals", async () => {
    const calls = stubFetch((url, init) => {
      if (init?.method === "PATCH") {
        return {
          id: 1,
          label: "Manual",
          broker: "manual",
          sync_mode: "manual",
          include_in_total: false,
        };
      }
      return snapshot();
    });
    await mount();
    await flush();
    const toggle = host!.querySelector<HTMLInputElement>(
      'input[aria-label="Manual 納入總計"]',
    )!;

    expect(host!.textContent).not.toContain("Currency basis");
    expect(host!.querySelectorAll('input[aria-label="Manual 納入總計"]'))
      .toHaveLength(1);

    await act(async () => {
      toggle.click();
    });

    expect(
      calls.some(
        (call) =>
          call.url.endsWith("/portfolio/accounts/1") &&
          call.method === "PATCH" &&
          (call.body as any)?.include_in_total === false,
      ),
    ).toBe(true);
  });

  it("states read-only sync and separates options with a risk warning", async () => {
    stubFetch(() => snapshot({
      positions: [
        {
          id: 11,
          account_id: 1,
          symbol: "NVDA",
          asset_class: "stock",
          quantity: 1,
          currency: "USD",
        },
        {
          id: 12,
          account_id: 1,
          symbol: "NVDA 260116C00150000",
          asset_class: "option",
          quantity: 1,
          currency: "USD",
        },
      ],
    }));

    await mount();
    await flush();

    await act(async () => {
      (await buttonByText("同步紀錄")).click();
    });
    await flush();

    expect(host!.textContent).toContain("唯讀同步");
    expect(host!.textContent).toContain("不會下單");
    await act(async () => {
      (await buttonByText("持倉")).click();
    });
    expect(host!.textContent).toContain("Options");
    expect(host!.textContent).toContain("進階選擇權風險尚未建模");
  });

  const manualPosition = (over: Partial<PortfolioPosition> = {}): PortfolioPosition => ({
    id: 40,
    account_id: 1,
    broker: "manual",
    symbol: "NVDA",
    asset_class: "stock",
    quantity: 3,
    avg_cost: 100,
    currency: "USD",
    notes: "start",
    thesis: "",
    tags: [],
    ...over,
  });

  const ibkrPosition = (over: Partial<PortfolioPosition> = {}): PortfolioPosition => ({
    id: 30,
    account_id: 2,
    broker: "ibkr",
    broker_con_id: "1001",
    symbol: "AAPL",
    asset_class: "stock",
    quantity: 1,
    currency: "USD",
    notes: "",
    thesis: "",
    tags: [],
    ...over,
  });

  function setInput(label: string, value: string) {
    const input = host!.querySelector<HTMLInputElement>(`input[aria-label="${label}"]`);
    if (!input) throw new Error(`input not found: ${label}`);
    input.value = value;
    input.dispatchEvent(new Event("input", { bubbles: true }));
  }

  it("edits notes thesis and tags on an ibkr position without broker fields", async () => {
    const calls = stubFetch((url, init) => {
      if (init?.method === "PATCH") return ibkrPosition({ notes: "keep" });
      return snapshot({ positions: [ibkrPosition()] });
    });
    await mount();
    await flush();

    await openRowActions("AAPL");
    await act(async () => {
      (await buttonByText("編輯")).click();
    });

    expect(host!.querySelector('input[aria-label="Edit Symbol"]')).toBeNull();
    expect(host!.querySelector('input[aria-label="Edit Quantity"]')).toBeNull();

    await act(async () => {
      setInput("Edit Notes", "keep");
      setInput("Edit Thesis", "moat");
      setInput("Edit Tags", "core, long");
      (await buttonByText("儲存")).click();
    });

    const patch = calls.find((c) => c.method === "PATCH");
    expect(patch?.url.endsWith("/portfolio/positions/30")).toBe(true);
    expect(patch?.body).toEqual({ notes: "keep", thesis: "moat", tags: ["core", "long"] });
  });

  it("edits manual financial and user fields in one patch", async () => {
    const calls = stubFetch((url, init) => {
      if (init?.method === "PATCH") return manualPosition({ quantity: 5 });
      return snapshot({ positions: [manualPosition()] });
    });
    await mount();
    await flush();

    const trigger = await openRowActions("NVDA");
    await act(async () => {
      (await buttonByText("編輯")).click();
    });
    const ownerRow = trigger.closest("tr");
    expect(ownerRow?.nextElementSibling?.classList.contains("ui-data-table-expanded")).toBe(true);
    expect(ownerRow?.nextElementSibling?.querySelector('input[aria-label="Edit Quantity"]')).not.toBeNull();
    await act(async () => {
      setInput("Edit Quantity", "5");
      setInput("Edit Avg Cost", "110.5");
      setInput("Edit Currency", "twd");
      setInput("Edit Notes", "updated");
      (await buttonByText("儲存")).click();
    });

    const patch = calls.find((c) => c.method === "PATCH");
    expect(patch?.body).toEqual({
      notes: "updated",
      thesis: "",
      tags: [],
      symbol: "NVDA",
      asset_class: "stock",
      quantity: 5,
      avg_cost: 110.5,
      currency: "twd",
    });
  });

  it("clears manual average cost with explicit null", async () => {
    const calls = stubFetch((url, init) => {
      if (init?.method === "PATCH") return manualPosition({ avg_cost: null });
      return snapshot({ positions: [manualPosition()] });
    });
    await mount();
    await flush();

    await openRowActions("NVDA");
    await act(async () => {
      (await buttonByText("編輯")).click();
    });
    await act(async () => {
      setInput("Edit Avg Cost", "");
      (await buttonByText("儲存")).click();
    });

    const patch = calls.find((c) => c.method === "PATCH");
    expect(patch && "avg_cost" in (patch.body as Record<string, unknown>)).toBe(true);
    expect((patch?.body as Record<string, unknown>).avg_cost).toBeNull();
  });

  it("soft closes a manual row only after ConfirmDialog approval", async () => {
    const legacyConfirm = vi.fn(() => { throw new Error("legacy confirmation must not run"); });
    vi.stubGlobal("confirm", legacyConfirm);
    const calls = stubFetch((url, init) => {
      if (init?.method === "DELETE") {
        return manualPosition({ closed_at: "2026-07-10T00:00:00Z" });
      }
      return snapshot({ positions: [manualPosition()] });
    });
    await mount();
    await flush();

    const trigger = host!.querySelector<HTMLButtonElement>('button[aria-label="NVDA 操作"]')!;
    await act(async () => {
      trigger.click();
    });
    await act(async () => {
      (await buttonByText("關閉")).click();
    });

    expect(document.querySelector('[role="dialog"]')?.textContent).toContain("顯示已關閉");
    expect(calls.some((call) => call.method === "DELETE")).toBe(false);
    expect(legacyConfirm).not.toHaveBeenCalled();

    await act(async () => { (await buttonByText("取消")).click(); });
    expect(calls.some((call) => call.method === "DELETE")).toBe(false);
    expect(document.activeElement).toBe(trigger);

    await act(async () => {
      trigger.click();
    });
    await act(async () => { (await buttonByText("關閉")).click(); });
    await act(async () => { (await buttonByText("確認關閉")).click(); });

    expect(calls.find((call) => call.method === "DELETE")?.url)
      .toMatch(/\/portfolio\/positions\/40$/);
  });

  it("shows closed rows when include closed is enabled", async () => {
    const calls = stubFetch((url) => {
      if (url.includes("include_closed=true")) {
        return snapshot({
          positions: [manualPosition({ closed_at: "2026-07-10T00:00:00Z" })],
        });
      }
      return snapshot();
    });
    await mount();
    await flush();
    expect(host!.textContent).not.toContain("NVDA");

    const toggle = host!.querySelector<HTMLInputElement>(
      'input[aria-label="顯示已關閉持倉"]',
    )!;
    await act(async () => {
      toggle.click();
    });
    await flush();

    expect(calls.some((c) => c.url.includes("/portfolio?include_closed=true"))).toBe(true);
    expect(host!.textContent).toContain("NVDA");
    expect(host!.textContent).toContain("已關閉");
  });

  it("rejects invalid manual numbers without sending a patch", async () => {
    const calls = stubFetch((url, init) => {
      if (init?.method === "PATCH") return manualPosition();
      return snapshot({ positions: [manualPosition()] });
    });
    await mount();
    await flush();

    await openRowActions("NVDA");
    await act(async () => {
      (await buttonByText("編輯")).click();
    });
    await act(async () => {
      setInput("Edit Avg Cost", "abc");
      (await buttonByText("儲存")).click();
    });

    expect(calls.some((c) => c.method === "PATCH")).toBe(false);
    expect(host!.textContent).toContain("均價");

    await act(async () => {
      setInput("Edit Avg Cost", "110");
      setInput("Edit Quantity", "not-a-number");
      (await buttonByText("儲存")).click();
    });

    expect(calls.some((c) => c.method === "PATCH")).toBe(false);
    expect(host!.textContent).toContain("數量");
  });

  it("does not render a close action for ibkr rows", async () => {
    stubFetch(() => snapshot({ positions: [ibkrPosition()] }));
    await mount();
    await flush();

    expect(host!.textContent).toContain("AAPL");
    await openRowActions("AAPL");
    const menu = document.querySelector('[role="menu"]');
    expect(menu?.textContent).toContain("編輯");
    expect(menu?.textContent).not.toContain("關閉");
  });
});
