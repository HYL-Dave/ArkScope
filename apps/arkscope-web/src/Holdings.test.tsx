/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { HoldingsView } from "./Holdings";
import type {
  PortfolioAccount,
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
  | PortfolioPosition
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

    await act(async () => {
      (await buttonByText("編輯")).click();
    });
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

  it("soft closes a manual row after confirmation", async () => {
    const confirmFn = vi.fn(() => false);
    vi.stubGlobal("confirm", confirmFn);
    const calls = stubFetch((url, init) => {
      if (init?.method === "DELETE") {
        return manualPosition({ closed_at: "2026-07-10T00:00:00Z" });
      }
      return snapshot({ positions: [manualPosition()] });
    });
    await mount();
    await flush();

    await act(async () => {
      (await buttonByText("關閉")).click();
    });
    expect(confirmFn).toHaveBeenCalled();
    expect(calls.some((c) => c.method === "DELETE")).toBe(false);

    confirmFn.mockReturnValue(true);
    await act(async () => {
      (await buttonByText("關閉")).click();
    });

    const del = calls.find((c) => c.method === "DELETE");
    expect(del?.url.endsWith("/portfolio/positions/40")).toBe(true);
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

  it("does not render a close action for ibkr rows", async () => {
    stubFetch(() => snapshot({ positions: [ibkrPosition()] }));
    await mount();
    await flush();

    expect(host!.textContent).toContain("AAPL");
    const closeButtons = Array.from(host!.querySelectorAll("button")).filter((b) =>
      b.textContent?.includes("關閉"),
    );
    expect(closeButtons).toEqual([]);
  });
});
