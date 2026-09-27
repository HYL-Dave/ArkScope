/** @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import i18n from "i18next";
import { getSAAcquisitionStatus } from "../api";
import { SAAcquisitionNotice } from "./SAAcquisitionNotice";

vi.mock("../api", () => ({ getSAAcquisitionStatus: vi.fn() }));
(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot>;
let host: HTMLDivElement;
const onNavigate = vi.fn();
const clear = { status: "ok" as const, configured: true, paused_reason: null, capability_pauses: {}, rate_limited: false, rate_limit_until: null };
beforeEach(async () => {
  vi.useFakeTimers();
  await i18n.changeLanguage("en");
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  vi.mocked(getSAAcquisitionStatus).mockResolvedValue(clear);
});
afterEach(async () => { act(() => root.unmount()); host.remove(); vi.useRealTimers(); vi.resetAllMocks(); await i18n.changeLanguage("zh-Hant"); });
async function mount() { await act(async () => root.render(<SAAcquisitionNotice onNavigate={onNavigate} />)); }

it("shows an actionable login pause without claiming subscription entitlement", async () => {
  vi.mocked(getSAAcquisitionStatus).mockResolvedValue({ ...clear, paused_reason: "login_required" });
  await mount();
  expect(host.querySelector('[role="alert"]')?.textContent).toContain("Sign-in expired");
  expect(host.textContent).not.toContain("entitled");
  act(() => host.querySelector("button")!.click());
  expect(onNavigate).toHaveBeenCalledWith({ kind: "settings_section", section: "data_sources" });
});
it("distinguishes subscription restriction and only names affected capabilities", async () => {
  vi.mocked(getSAAcquisitionStatus).mockResolvedValue({ ...clear, capability_pauses: { financials: "access_restricted" } });
  await mount();
  expect(host.textContent).toContain("Subscription access unavailable");
  expect(host.textContent).toContain("Financial statements");
  expect(host.textContent).toContain("separate");
  expect(host.textContent).not.toContain("Sign-in expired");
});
it("hides a clear state and removes polling on unmount", async () => {
  await mount(); expect(host.childElementCount).toBe(0);
  await act(async () => vi.advanceTimersByTimeAsync(60_000));
  expect(getSAAcquisitionStatus).toHaveBeenCalledTimes(2);
  act(() => root.unmount());
  await act(async () => vi.advanceTimersByTimeAsync(60_000));
  expect(getSAAcquisitionStatus).toHaveBeenCalledTimes(2);
});
it("reports unavailable status without clearing it as healthy", async () => {
  vi.mocked(getSAAcquisitionStatus).mockRejectedValue(new Error("offline"));
  await mount(); expect(host.textContent).toContain("Status unavailable");
});
it("shows an unfinished record without claiming that the browser is running or failed", async () => {
  vi.mocked(getSAAcquisitionStatus).mockResolvedValue({ ...clear, unfinished_task: {
    operation: "alpha_picks_sync", started_at: "2026-09-27T11:42:15Z", navigation_attempt_count: 2,
  } });
  await mount();
  expect(host.textContent).toContain("Unfinished capture record");
  expect(host.textContent).toContain("Alpha Picks");
  expect(host.textContent).toContain("2");
  expect(host.textContent).not.toContain("Acquisition running");
  expect(host.querySelector('[role="alert"]')).toBeNull();
});
it("never overlaps an unfinished status read and ignores its result after unmount", async () => {
  let resolve!: (value: typeof clear) => void;
  vi.mocked(getSAAcquisitionStatus).mockReturnValue(new Promise(done => { resolve = done; }));
  await mount(); await act(async () => vi.advanceTimersByTimeAsync(120_000));
  expect(getSAAcquisitionStatus).toHaveBeenCalledTimes(1);
  act(() => root.unmount()); await act(async () => resolve(clear));
  expect(host.childElementCount).toBe(0);
});
