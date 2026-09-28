/** @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import i18n from "i18next";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { SAArticleAcquisitionSection } from "./SAArticleAcquisitionSection";

const api = vi.hoisted(() => ({ getSAArticleAcquisitionSettings: vi.fn(), putSAArticleAcquisitionSettings: vi.fn(), getSABodyRecoveryStatus: vi.fn() }));
vi.mock("../api", async (original) => ({ ...await original<typeof import("../api")>(), ...api }));
(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
const defaults = { max_articles_per_job: 0, body_lookback_days: 0, body_scope: "all_retained", comment_scope: "current" };
const view = () => ({ values: { ...defaults }, defaults, error_code: null, setting_source: "default" });
let host: HTMLDivElement, root: Root;
const guard = vi.fn();
beforeEach(async () => {
  await i18n.changeLanguage("en"); vi.clearAllMocks();
  api.getSAArticleAcquisitionSettings.mockReset().mockResolvedValue(view());
  api.getSABodyRecoveryStatus.mockReset().mockResolvedValue({ status: "ok", state: "not_started" });
  api.putSAArticleAcquisitionSettings.mockReset().mockImplementation(async (values) => ({ ...view(), values, setting_source: "profile" }));
});
afterEach(async () => { if (root) await act(async () => root.unmount()); host?.remove(); });
async function render() {
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  await act(async () => root.render(<SAArticleAcquisitionSection onNavigationGuardChange={guard} />));
}
const button = (name: string) => host.querySelector<HTMLButtonElement>(`button[aria-label="${name}"]`)!;
async function input(label: string, value: string) {
  const node = host.querySelector<HTMLInputElement>(`input[aria-label="${label}"]`)!;
  await act(async () => { Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(node, value); node.dispatchEvent(new Event("input", { bubbles: true })); });
}
it("loads without starting collection, preserves zero, saves and undoes a draft", async () => {
  await render();
  expect(host.textContent).toContain("Article acquisition");
  expect(host.querySelector<HTMLInputElement>('input[aria-label="Articles per job (0 = unlimited)"]')?.value).toBe("0");
  expect(api.putSAArticleAcquisitionSettings).not.toHaveBeenCalled();
  await input("Articles per job (0 = unlimited)", "128");
  expect(guard).toHaveBeenLastCalledWith(expect.objectContaining({ dirty: true }));
  await act(async () => button("Undo article settings").click());
  expect(host.querySelector<HTMLInputElement>('input[type="number"]')?.value).toBe("0");
  await input("Article age in days (0 = unlimited)", "3650");
  await act(async () => button("Save article settings").click());
  expect(api.putSAArticleAcquisitionSettings).toHaveBeenLastCalledWith({ ...defaults, body_lookback_days: 3650 });
  expect(guard).toHaveBeenLastCalledWith(expect.objectContaining({ dirty: false }));
});
it("invalid saved values are blocked until defaults are explicitly chosen", async () => {
  api.getSAArticleAcquisitionSettings.mockResolvedValue({ ...view(), values: null, error_code: "sa_article_settings_invalid" });
  await render();
  expect(host.textContent).toContain("Saved article settings are invalid");
  expect(host.querySelector("fieldset")?.disabled).toBe(true);
  expect(button("Save article settings").disabled).toBe(true);
  await act(async () => button("Use default article settings").click());
  await act(async () => button("Save article settings").click());
  expect(api.putSAArticleAcquisitionSettings).toHaveBeenCalledWith(defaults);
});
it("failed saves keep the draft and do not falsely report success", async () => {
  api.putSAArticleAcquisitionSettings.mockRejectedValue(new Error("private server internals"));
  await render(); await input("Articles per job (0 = unlimited)", "9");
  await act(async () => button("Save article settings").click());
  expect(host.textContent).toContain("Article settings could not be saved");
  expect(host.textContent).not.toContain("private server internals");
  expect(host.querySelector<HTMLInputElement>('input[type="number"]')?.value).toBe("9");
  expect(button("Save article settings").disabled).toBe(false);
});
it("blocked reads are unavailable and never replaced with default values", async () => {
  api.getSAArticleAcquisitionSettings.mockRejectedValue(new Error("unavailable"));
  await render(); expect(host.textContent).toContain("Article settings unavailable");
  expect(host.querySelectorAll("input")).toHaveLength(0);
  expect(api.putSAArticleAcquisitionSettings).not.toHaveBeenCalled();
});
it("shows durable counts and pacing without inventing a completion estimate", async () => {
  api.getSABodyRecoveryStatus.mockResolvedValue({ status: "ok", state: "waiting", counts: { selected: 128, saved: 8, failed: 2, skipped: 3, pending: 115 },
    reason_code: "site_pacing", next_eligible_at: "2026-09-29T05:01:00+00:00" });
  await render(); expect(host.textContent).toContain("128 selected"); expect(host.textContent).toContain("115 pending");
  expect(host.textContent).toContain("Next eligible"); expect(host.querySelector("progress")?.max).toBe(128);
  expect(host.textContent).not.toMatch(/estimated|\bETA\b/i);
});
it("does not allow fractional or unsafe limits", async () => {
  await render(); await input("Articles per job (0 = unlimited)", "1.5");
  expect(button("Save article settings").disabled).toBe(true);
  expect(api.putSAArticleAcquisitionSettings).not.toHaveBeenCalled();
});
