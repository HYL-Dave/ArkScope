/** @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import i18n from "i18next";
import { InvestigationRuntimeSection } from "./InvestigationRuntimeSection";
const mocks = vi.hoisted(() => ({ getInvestigationRuntime: vi.fn(), saveInvestigationRuntime: vi.fn(), resetInvestigationRuntime: vi.fn() }));
vi.mock("../api", async original => ({ ...await original<typeof import("../api")>(), ...mocks }));
const runtime = { model_submissions: 24, web_actions: 24, source_reads: 32, http_requests: 96, local_queries: 20,
  deadline_seconds: 1800, model_timeout_seconds: 600, api_output_tokens: 8192, retained_source_mib: 512 };
let host: HTMLDivElement, root: Root;
beforeEach(async () => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true); vi.resetAllMocks();
  mocks.getInvestigationRuntime.mockResolvedValue(runtime);
  mocks.saveInvestigationRuntime.mockImplementation(async value => value);
  mocks.resetInvestigationRuntime.mockResolvedValue(runtime);
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  await i18n.changeLanguage("en");
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.unstubAllGlobals(); });
async function open() { await act(async () => { const e = host.querySelector("details")!; e.open = true; e.dispatchEvent(new Event("toggle", { bubbles: true })); }); }
function button(label: string) { return [...host.querySelectorAll<HTMLButtonElement>("button")].find(x => (x.getAttribute("aria-label") || x.textContent) === label)!; }
async function edit(index: number, value: string) { await act(async () => { const input = host.querySelectorAll<HTMLInputElement>('input[type="number"]')[index];
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(input, value);
  input.dispatchEvent(new Event("input", { bubbles: true })); }); }
it("loads only on expansion and reflects the real OAuth output control", async () => {
  await act(async () => root.render(<InvestigationRuntimeSection authMode="claude_code_oauth" />));
  expect(mocks.getInvestigationRuntime).not.toHaveBeenCalled(); await open();
  const fields = host.querySelectorAll<HTMLInputElement>('input[type="number"]');
  expect(fields).toHaveLength(9); expect(fields[7].disabled).toBe(true);
  expect(fields[0].value).toBe("24"); expect(fields[0].disabled).toBe(false);
  expect(mocks.saveInvestigationRuntime).not.toHaveBeenCalled();
});
it("invalid drafts are not clamped or saved and valid changes roundtrip with navigation guards", async () => {
  const guard = vi.fn();
  await act(async () => root.render(<InvestigationRuntimeSection authMode="api_key" onNavigationGuardChange={guard} />)); await open();
  expect(host.querySelectorAll<HTMLInputElement>('input[type="number"]')[7].disabled).toBe(false);
  await edit(0, "129"); expect(button("Save").disabled).toBe(true);
  expect(guard).toHaveBeenLastCalledWith(expect.objectContaining({ dirty: true }));
  await edit(0, "40"); await act(async () => button("Save").click());
  expect(mocks.saveInvestigationRuntime).toHaveBeenCalledExactlyOnceWith({ ...runtime, model_submissions: 40 });
  expect(guard).toHaveBeenLastCalledWith(expect.objectContaining({ busy: false, dirty: false }));
});
it("a failed initial read offers retry without installing or writing defaults", async () => {
  mocks.getInvestigationRuntime.mockRejectedValueOnce(new Error("unavailable"));
  await act(async () => root.render(<InvestigationRuntimeSection />)); await open();
  expect(host.querySelector('[role="alert"]')).not.toBeNull();
  expect(mocks.saveInvestigationRuntime).not.toHaveBeenCalled();
  await act(async () => button("Refresh").click());
  expect(mocks.getInvestigationRuntime).toHaveBeenCalledTimes(2);
  expect(host.querySelector('[role="alert"]')).toBeNull();
  expect(host.querySelector<HTMLInputElement>('input[type="number"]')?.value).toBe("24");
});
