/** @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import i18n from "i18next";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { SAFinancialAcquisitionSection } from "./SAFinancialAcquisitionSection";

const api = vi.hoisted(() => ({ getSAFinancialAcquisitionSettings: vi.fn(), putSAFinancialAcquisitionSettings: vi.fn() }));
vi.mock("../api", async original => ({ ...await original<typeof import("../api")>(), ...api }));
(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
const defaults = { parser_failure_ticker_threshold: 3 };
const view = () => ({ values: { ...defaults }, defaults, error_code: null, setting_source: "default" });
let host: HTMLDivElement, root: Root;
const guard = vi.fn();
beforeEach(async () => {
  await i18n.changeLanguage("en"); vi.clearAllMocks();
  api.getSAFinancialAcquisitionSettings.mockReset().mockResolvedValue(view());
  api.putSAFinancialAcquisitionSettings.mockReset().mockImplementation(async values => ({ ...view(), values, setting_source: "profile" }));
});
afterEach(async () => { if (root) await act(async () => root.unmount()); host?.remove(); });
async function render() {
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  await act(async () => root.render(<SAFinancialAcquisitionSection onNavigationGuardChange={guard} />));
}
const button = (name: string) => host.querySelector<HTMLButtonElement>(`button[aria-label="${name}"]`)!;
async function input(value: string) {
  const node = host.querySelector<HTMLInputElement>('input[type="number"]')!;
  await act(async () => { Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(node, value); node.dispatchEvent(new Event("input", { bubbles: true })); });
}
it("retains the default until explicitly saving zero and guards the draft", async () => {
  await render();
  expect(host.querySelector<HTMLInputElement>('input[type="number"]')?.value).toBe("3");
  expect(api.putSAFinancialAcquisitionSettings).not.toHaveBeenCalled();
  await input("0");
  expect(guard).toHaveBeenLastCalledWith(expect.objectContaining({ dirty: true }));
  await act(async () => button("Save financial capture settings").click());
  expect(api.putSAFinancialAcquisitionSettings).toHaveBeenLastCalledWith({ parser_failure_ticker_threshold: 0 });
  expect(host.querySelector<HTMLInputElement>('input[type="number"]')?.value).toBe("0");
  expect(guard).toHaveBeenLastCalledWith(expect.objectContaining({ dirty: false }));
});
it("rejects fractional limits and preserves the draft after a save failure", async () => {
  await render(); await input("1.5");
  expect(button("Save financial capture settings").disabled).toBe(true);
  await input("5");
  api.putSAFinancialAcquisitionSettings.mockRejectedValue(new Error("private internals"));
  await act(async () => button("Save financial capture settings").click());
  expect(host.textContent).toContain("Financial capture settings could not be saved");
  expect(host.textContent).not.toContain("private internals");
  expect(host.querySelector<HTMLInputElement>('input[type="number"]')?.value).toBe("5");
  await act(async () => button("Undo financial capture settings").click());
  expect(host.querySelector<HTMLInputElement>('input[type="number"]')?.value).toBe("3");
});
it("requires an explicit reset when the saved policy is invalid", async () => {
  api.getSAFinancialAcquisitionSettings.mockResolvedValue({ ...view(), values: null, error_code: "sa_financial_settings_invalid" });
  await render();
  expect(host.querySelector("fieldset")?.disabled).toBe(true);
  await act(async () => button("Use default financial capture settings").click());
  await act(async () => button("Save financial capture settings").click());
  expect(api.putSAFinancialAcquisitionSettings).toHaveBeenCalledWith(defaults);
});
it("does not substitute defaults for an unavailable profile", async () => {
  api.getSAFinancialAcquisitionSettings.mockRejectedValue(new Error("unavailable"));
  await render();
  expect(host.textContent).toContain("Financial capture settings unavailable");
  expect(host.querySelectorAll("input")).toHaveLength(0);
  expect(api.putSAFinancialAcquisitionSettings).not.toHaveBeenCalled();
});
