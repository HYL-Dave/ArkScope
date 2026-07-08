/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { HoldingsView } from "./Holdings";
import type { PortfolioSnapshot, PortfolioSyncPreview } from "./api";

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
  accounts: [{ id: 1, label: "Manual", broker: "manual", sync_mode: "manual", base_currency: "USD" }],
  positions: [],
  totals: { currency_basis: "per_currency", per_currency: {}, broker_base: null },
  ...over,
});

type PortfolioApiResponse = PortfolioSnapshot | PortfolioSyncPreview | { ok: true };

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
          currency: "USD",
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
        return { changes: [{ kind: "add", symbol: "MSFT", quantity: 1 }], applies: false };
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
  });
});
