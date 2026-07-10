/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { HoldingsView } from "./Holdings";
import type {
  PortfolioAccount,
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

type PortfolioApiResponse =
  | PortfolioAccount
  | PortfolioSnapshot
  | PortfolioSyncPreview
  | { ok: true };

function stubFetch(handler: (url: string, init?: RequestInit) => PortfolioApiResponse) {
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
      return new Response(JSON.stringify(handler(u, init)), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }),
  );
  return calls;
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
    const found = Array.from(host!.querySelectorAll("button")).find((b) =>
      b.textContent?.includes(text),
    );
    if (found) return found;
    await flush();
  }
  throw new Error(`button not found: ${text}; text=${host?.textContent ?? ""}`);
}

describe("HoldingsView", () => {
  it("renders accounts, positions, and currency basis", async () => {
    stubFetch(() => snapshot({
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
      ],
      totals: {
        currency_basis: "per_currency",
        per_currency: { USD: { market_value: null, position_count: 1 } },
        broker_base: null,
      },
    }));

    await mount();
    await flush();

    expect(host!.textContent).toContain("Manual");
    expect(host!.textContent).toContain("NVDA");
    expect(host!.textContent).toContain("per-currency");
    expect(host!.textContent).toContain("Avg Cost");
    expect(host!.textContent).toContain("212.84");
    expect(host!.textContent).toContain("61,086");
    expect(host!.textContent).toContain("-2,765");
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

  it("shows ibkr preview as review before applying", async () => {
    stubFetch((url) => {
      if (url.endsWith("/portfolio/ibkr/preview")) {
        return {
          changes: [{
            kind: "update",
            symbol: "MSFT",
            quantity: 1,
            before: {
              avg_cost: 90,
              market_value: 1200,
              unrealized_pnl: -50,
            },
            after: {
              avg_cost: 100.25,
              market_value: 1250,
              unrealized_pnl: -25.5,
            },
          }],
          applies: false,
        };
      }
      return snapshot();
    });
    await mount();

    await act(async () => {
      (await buttonByText("預覽 IBKR 同步")).click();
    });
    await flush();

    expect(host!.textContent).toContain("MSFT");
    expect(host!.textContent).toContain("套用同步");
    expect(host!.textContent).toContain("尚未寫入本地持倉");
    expect(host!.textContent).toContain("Avg Cost");
    expect(host!.textContent).toContain("90 → 100.25");
    expect(host!.textContent).toContain("1,200 → 1,250");
    expect(host!.textContent).toContain("-50 → -25.5");
  });

  it("clears preview and shows persisted positions after applying", async () => {
    let applied = false;
    const calls = stubFetch((url, init) => {
      if (url.endsWith("/portfolio/ibkr/preview")) {
        return {
          changes: [{
            kind: "add",
            symbol: "AMD",
            quantity: 400,
            after: { avg_cost: 92.26, market_value: 206704, unrealized_pnl: 169800 },
          }],
          applies: false,
        };
      }
      if (url.endsWith("/portfolio/ibkr/apply") && init?.method === "POST") {
        applied = true;
        return { changes: [], applies: true };
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
    });
    await mount();

    await act(async () => {
      (await buttonByText("預覽 IBKR 同步")).click();
    });
    await flush();
    await act(async () => {
      (await buttonByText("套用同步")).click();
    });
    await flush();

    expect(calls.some((call) => call.url.endsWith("/portfolio/ibkr/apply"))).toBe(true);
    expect(
      calls.filter((call) => call.url.endsWith("/portfolio")).length,
    ).toBeGreaterThanOrEqual(2);
    expect(host!.textContent).toContain("AMD");
    expect(host!.textContent).toContain("92.26");
    expect(host!.textContent).not.toContain("尚未寫入本地持倉");
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
    const toggle = host!.querySelector<HTMLInputElement>(
      'input[aria-label="Manual 納入總計"]',
    )!;

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

    expect(host!.textContent).toContain("唯讀同步");
    expect(host!.textContent).toContain("不會下單");
    expect(host!.textContent).toContain("Options");
    expect(host!.textContent).toContain("進階選擇權風險尚未建模");
  });
});
