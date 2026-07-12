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

type PortfolioApiResponse =
  | PortfolioAccount
  | PortfolioPosition
  | PortfolioSnapshot
  | PortfolioSyncPreview
  | { ok: true };

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

function stubFetch(
  handler: (url: string, init?: RequestInit) => PortfolioApiResponse | Promise<PortfolioApiResponse>,
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
      return new Response(JSON.stringify(await handler(u, init)), {
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
    const found = Array.from(document.querySelectorAll("button")).find((b) =>
      b.textContent?.includes(text),
    );
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

    expect(host!.querySelectorAll("h1")).toHaveLength(1);
    expect(host!.querySelector('[data-state="ready"]')?.textContent).toContain("1 筆持倉");
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
    const previewResponse = deferred<PortfolioSyncPreview>();
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    stubFetch((url) => {
      if (url.endsWith("/portfolio/ibkr/preview")) {
        return previewResponse.promise;
      }
      return snapshot();
    });
    await mount();
    await flush();

    await act(async () => {
      (await buttonByText("預覽 IBKR 同步")).click();
    });
    expect(host!.querySelector('[data-state="running"]')?.textContent).toContain("更新中");

    await act(async () => {
      previewResponse.resolve({
          changes: [{
            kind: "update",
            account_id: 1,
            broker_account_id: "DU111",
            broker_con_id: "1001",
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
          }, {
            kind: "update",
            account_id: 2,
            broker_account_id: "DU222",
            broker_con_id: "1001",
            symbol: "MSFT",
            quantity: 2,
            before: {
              avg_cost: 200,
              market_value: 2200,
              unrealized_pnl: 50,
            },
            after: {
              avg_cost: 210.5,
              market_value: 2250,
              unrealized_pnl: 75,
            },
          }],
          applies: false,
      });
      await previewResponse.promise;
    });
    await flush();

    expect(host!.querySelector('[data-state="partial"]')?.textContent).toContain("待套用變更");
    const previewTable = host!.querySelector('table[aria-label="IBKR 同步預覽"]')!;
    expect(previewTable.querySelectorAll("tbody tr")).toHaveLength(2);
    expect(Array.from(previewTable.querySelectorAll("tbody tr")).map((row) => row.textContent))
      .toEqual([
        expect.stringContaining("90 → 100.25"),
        expect.stringContaining("200 → 210.5"),
      ]);
    expect(consoleError.mock.calls.flat().join(" ")).not.toContain("same key");
    expect(host!.textContent).not.toContain("DU111");
    expect(host!.textContent).not.toContain("DU222");
    expect(host!.textContent).toContain("MSFT");
    expect(host!.textContent).toContain("套用同步");
    expect(host!.textContent).toContain("尚未寫入本地持倉");
    expect(host!.textContent).toContain("Avg Cost");
    expect(host!.textContent).toContain("90 → 100.25");
    expect(host!.textContent).toContain("1,200 → 1,250");
    expect(host!.textContent).toContain("-50 → -25.5");
    expect(host!.textContent).toContain("2,200 → 2,250");
    expect(host!.textContent).toContain("50 → 75");
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
