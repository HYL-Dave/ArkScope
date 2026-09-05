/** @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import i18n from "i18next";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { AlphaTrackingPanel } from "./AlphaTrackingPanel";
import { parseAlphaTracking, type AlphaTrackingMembership } from "./api";

const api = vi.hoisted(() => ({ getAlphaTracking: vi.fn(), refreshAlphaTracking: vi.fn(), commandAlphaTracking: vi.fn() }));
vi.mock("./api", async (original) => ({ ...await original<typeof import("./api")>(), ...api }));
(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
let host: HTMLDivElement;
let root: ReturnType<typeof createRoot>;
const membership: AlphaTrackingMembership = { membership_id: "m1", ticker: "OLD", picked_date: "2025-01-01", portfolio_status: "closed", state: "tracking", reason: "bootstrap_accepted", accepted_at: "2026-09-05T01:00:00Z", removed_at: null };
beforeEach(async () => {
  await i18n.changeLanguage("en");
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  vi.clearAllMocks();
  api.getAlphaTracking.mockResolvedValue({ available: true, memberships: [membership] });
  api.commandAlphaTracking.mockResolvedValue(undefined);
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); });

it("rejects absent and malformed membership arrays rather than crashing during render", () => {
  for (const memberships of [undefined, null, {}, "OLD"]) expect(() => parseAlphaTracking({ available: true, memberships })).toThrow();
  expect(parseAlphaTracking({ available: true, memberships: [membership] }).memberships).toEqual([membership]);
  expect(() => parseAlphaTracking({ available: true, memberships: [{ ...membership, reason: "made_up" }] })).toThrow();
  expect(parseAlphaTracking({ available: true, memberships: [] }).sync_status).toBe("unavailable");
  for (const sync_status of [null, {}, "success"]) {
    expect(() => parseAlphaTracking({ available: true, memberships: [], sync_status })).toThrow();
  }
});

it("shows pending SA reconciliation without claiming the saved tracking choices were lost", async () => {
  api.getAlphaTracking.mockResolvedValue({ available: true, memberships: [membership], sync_status: "pending" });
  await act(async () => root.render(<AlphaTrackingPanel status="closed" onOpenTicker={vi.fn()} onChanged={vi.fn()} />));
  expect(host.textContent).toContain("Recent SA observations are not yet reflected in local tracking");
  expect(host.querySelector('[aria-label="Stop Former tracking OLD"]')).not.toBeNull();
  expect(api.refreshAlphaTracking).not.toHaveBeenCalled();
});

it("confirms a source-scoped removal and keeps it separate from Restore", async () => {
  const onChanged = vi.fn();
  await act(async () => root.render(<AlphaTrackingPanel status="closed" onOpenTicker={vi.fn()} onChanged={onChanged} />));
  const remove = host.querySelector<HTMLButtonElement>('[aria-label="Stop Former tracking OLD"]')!;
  expect(remove).not.toBeNull();
  await act(async () => remove.click());
  expect(api.commandAlphaTracking).not.toHaveBeenCalled();
  expect(document.querySelector('[role="dialog"]')?.textContent).toContain("Other lists and holdings are unchanged");
  const confirm = Array.from(document.querySelectorAll<HTMLButtonElement>('[role="dialog"] button')).find((button) => button.textContent === "Stop Former tracking")!;
  api.getAlphaTracking.mockResolvedValue({ available: true, memberships: [{ ...membership, state: "removed", reason: "user_removed" }] });
  await act(async () => confirm.click());
  expect(api.commandAlphaTracking).toHaveBeenCalledExactlyOnceWith("m1", "remove");
  expect(onChanged).toHaveBeenCalledOnce();
  const filter = host.querySelector<HTMLSelectElement>("select")!;
  await act(async () => { filter.value = "removed"; filter.dispatchEvent(new Event("change", { bubbles: true })); });
  expect(host.querySelector('[aria-label="Restore tracking OLD"]')).not.toBeNull();
});

it("does not expose ordinary Restore for a terminal-delisting suppression", async () => {
  api.getAlphaTracking.mockResolvedValue({ available: true, memberships: [{ ...membership, state: "removed", reason: "terminal_delisting" }] });
  await act(async () => root.render(<AlphaTrackingPanel status="closed" onOpenTicker={vi.fn()} onChanged={vi.fn()} />));
  const filter = host.querySelector<HTMLSelectElement>("select")!;
  await act(async () => { filter.value = "removed"; filter.dispatchEvent(new Event("change", { bubbles: true })); });
  expect(host.textContent).toContain("reversal belongs to the lifecycle event");
  expect(host.querySelector('[aria-label="Restore tracking OLD"]')).toBeNull();
});

it("does not refresh or notify a departed view when a pending command finishes", async () => {
  const onChanged = vi.fn();
  let finish!: () => void;
  api.commandAlphaTracking.mockReturnValue(new Promise<void>((resolve) => { finish = resolve; }));
  await act(async () => root.render(<AlphaTrackingPanel status="closed" onOpenTicker={vi.fn()} onChanged={onChanged} />));
  await act(async () => host.querySelector<HTMLButtonElement>('[aria-label="Stop Former tracking OLD"]')!.click());
  const confirm = Array.from(document.querySelectorAll<HTMLButtonElement>('[role="dialog"] button')).find((button) => button.textContent === "Stop Former tracking")!;
  await act(async () => confirm.click());
  expect(api.commandAlphaTracking).toHaveBeenCalledOnce();
  await act(async () => root.render(<div />));
  await act(async () => finish());
  expect(api.getAlphaTracking).toHaveBeenCalledOnce();
  expect(onChanged).not.toHaveBeenCalled();
});
