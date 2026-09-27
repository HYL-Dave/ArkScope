/** @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import i18n from "i18next";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { coverageFixture } from "../financialReadFixtures";
import { createSettingsReadCache } from "./settingsReadCache";
import { FinancialCoverageSection } from "./FinancialCoverageSection";

const mocks = vi.hoisted(() => ({ getFinancialCoverage: vi.fn(), refreshFinancials: vi.fn(), putDataSourceRoute: vi.fn() }));
vi.mock("../api", async (original) => ({ ...await original<typeof import("../api")>(), ...mocks }));
(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
let host: HTMLDivElement, root: Root;
beforeEach(async () => { await i18n.changeLanguage("en"); mocks.getFinancialCoverage.mockReset().mockResolvedValue(coverageFixture()); });
afterEach(async () => { if (root) await act(async () => root.unmount()); host?.remove(); });
async function render() {
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  await act(async () => { root.render(<FinancialCoverageSection settingsReadCache={createSettingsReadCache()} onNavigateTarget={vi.fn()} />); });
}
it("shows inspected financial coverage and original period independently of market status", async () => {
  await render();
  expect(host.textContent).toContain("Seeking Alpha");
  expect(host.textContent).toContain("2025-12");
  expect(host.textContent).not.toContain("2025-12-31");
  expect(host.textContent).toContain("40");
  expect(host.textContent).toContain("1");
  expect(host.textContent).toContain("Mapping not reviewed");
  expect(host.textContent).not.toMatch(/SEC|TTL|expired/i);
  expect(mocks.refreshFinancials).not.toHaveBeenCalled();
  expect(mocks.putDataSourceRoute).not.toHaveBeenCalled();
  const next = host.querySelector<HTMLButtonElement>('button[aria-label="Next financial page"]')!;
  await act(async () => next.click());
  expect(mocks.getFinancialCoverage).toHaveBeenLastCalledWith(expect.objectContaining({ offset: 25 }));
});
it("keeps disabled route distinct from an empty inventory", async () => {
  mocks.getFinancialCoverage.mockResolvedValue({ ...coverageFixture(), status: "unavailable", items: [],
    gaps: [{ provider: "financials", code: "data_source_route_disabled" }] });
  await render();
  expect(host.textContent).toContain("No financial source selected");
});
