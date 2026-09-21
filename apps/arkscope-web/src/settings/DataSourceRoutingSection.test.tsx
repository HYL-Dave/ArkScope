/** @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import i18n from "i18next";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { DataSourceRoutesResponse } from "../api";
import { createSettingsReadCache, type SettingsReadCache } from "./settingsReadCache";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

vi.mock("../api", async (importOriginal) => ({
  ...await importOriginal<typeof import("../api")>(),
  getDataSourceRoutes: vi.fn(),
  putDataSourceRoute: vi.fn(),
  putFinancialDatasetsBudget: vi.fn(),
}));

import { getDataSourceRoutes, putDataSourceRoute, putFinancialDatasetsBudget } from "../api";
import { DataSourceRoutingSection } from "./DataSourceRoutingSection";

const FD = "Financial Datasets (paid)";
const FUNDAMENTALS = "Fundamental analysis";
const SAVE_BUDGET = "Save Financial Datasets request budget";
let state: DataSourceRoutesResponse;
let root: ReturnType<typeof createRoot> | null;
let host: HTMLDivElement;
const guard = vi.fn();

function fixture(): DataSourceRoutesResponse {
  return {
    routes: [
      {
        dataset: "fundamentals_analysis", providers: ["sec_edgar", "financial_datasets"],
        options: [{ provider: "sec_edgar", access: "public_identity" },
          { provider: "financial_datasets", access: "metered_requests" }],
        setting_source: "default", consumers: ["get_fundamentals_analysis"],
        unimplemented: ["massive", "seeking_alpha"], error_code: null,
      },
      {
        dataset: "detailed_financials", providers: ["sec_edgar"],
        options: [{ provider: "sec_edgar", access: "public_identity" }],
        setting_source: "default", consumers: ["get_detailed_financials"], unimplemented: [], error_code: null,
      },
      {
        dataset: "earnings_supplements", providers: ["finnhub"],
        options: [{ provider: "finnhub", access: "endpoint_entitlement_unverified" }],
        setting_source: "default", consumers: ["get_detailed_financials"], unimplemented: [], error_code: null,
      },
      {
        dataset: "sa_company_financials", providers: ["seeking_alpha"],
        options: [{ provider: "seeking_alpha", access: "signed_in_browser_subscription" }],
        setting_source: "default", consumers: ["get_sa_company_data"], unimplemented: [], error_code: null,
      },
      ...(["sa_company_valuation", "sa_company_estimates"] as const).map((dataset) => ({
        dataset, providers: ["seeking_alpha"],
        options: [{ provider: "seeking_alpha", access: "signed_in_browser_subscription" as const }],
        setting_source: "default" as const, consumers: ["get_sa_company_data"], unimplemented: [], error_code: null,
      })),
    ],
    financial_datasets_budget: {
      enabled: true, daily_request_limit: null, requests_per_minute: null,
      state: "unconfigured", setting_source: "default", error_code: "financial_datasets_policy_unconfigured",
    },
  };
}

async function flush() {
  await act(async () => { await Promise.resolve(); await Promise.resolve(); });
}

async function render(cache: SettingsReadCache = createSettingsReadCache()) {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  await act(async () => { root!.render(<DataSourceRoutingSection settingsReadCache={cache} onNavigationGuardChange={guard} />); });
  await flush();
}

function button(label: string): HTMLButtonElement {
  const result = Array.from(document.querySelectorAll<HTMLButtonElement>("button"))
    .find((item) => item.getAttribute("aria-label") === label || item.textContent?.trim() === label);
  if (!result) throw new Error(`missing button: ${label}`);
  return result;
}

function source(label: string): HTMLInputElement {
  const result = Array.from(host.querySelectorAll<HTMLInputElement>('input[type="checkbox"]'))
    .find((item) => item.getAttribute("aria-label") === label);
  if (!result) throw new Error(`missing source: ${label}`);
  return result;
}

function paid(): HTMLInputElement { return host.querySelector(".data-route-budget-toggle input")!; }

async function click(element: HTMLElement) {
  await act(async () => { element.click(); });
  await flush();
}

async function limit(index: number, value: string) {
  const input = host.querySelectorAll<HTMLInputElement>('.data-route-budget-fields input')[index];
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(input, value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

beforeEach(async () => {
  await i18n.changeLanguage("en");
  vi.resetAllMocks();
  state = fixture();
  vi.mocked(getDataSourceRoutes).mockImplementation(async () => structuredClone(state));
  vi.mocked(putDataSourceRoute).mockImplementation(async (dataset, providers) => {
    const row = state.routes.find((item) => item.dataset === dataset)!;
    Object.assign(row, { providers, setting_source: "profile", error_code: null });
    return structuredClone(row);
  });
  vi.mocked(putFinancialDatasetsBudget).mockImplementation(async (value) => {
    const { confirm_paid: _, ...budget } = value;
    state.financial_datasets_budget = {
      ...budget, state: value.enabled ? "enabled" : "disabled", setting_source: "profile", error_code: null,
    };
    return structuredClone(state.financial_datasets_budget);
  });
});

afterEach(() => {
  if (root) act(() => root!.unmount());
  root = null;
  document.body.replaceChildren();
});

describe("DataSourceRoutingSection", () => {
  it("shows actual adapter scope and unverified Finnhub access without activating paid requests", async () => {
    await render();
    expect(host.textContent).toContain("Endpoint access unverified");
    expect(host.textContent).toContain("Not connected to this analysis tool");
    expect(host.textContent).toContain("Request limits not configured");
    expect(Array.from(host.querySelectorAll("input[aria-label]")).some((item) =>
      item.getAttribute("aria-label")?.startsWith(FUNDAMENTALS) && /Massive|Seeking Alpha/.test(item.getAttribute("aria-label")!))).toBe(false);
    expect(paid().checked).toBe(false);
    expect(putDataSourceRoute).not.toHaveBeenCalled();
    expect(putFinancialDatasetsBudget).not.toHaveBeenCalled();
  });

  it("saves selected sources only, separately from billing permission", async () => {
    await render();
    await click(source(`${FUNDAMENTALS}: SEC EDGAR`));
    expect(guard).toHaveBeenLastCalledWith(expect.objectContaining({ dirty: true, busy: false }));
    await click(button(`Save sources: ${FUNDAMENTALS}`));
    expect(putDataSourceRoute).toHaveBeenCalledExactlyOnceWith("fundamentals_analysis", ["financial_datasets"]);
    expect(putFinancialDatasetsBudget).not.toHaveBeenCalled();
    expect(guard).toHaveBeenLastCalledWith({ dirty: false, busy: false, reason: null });
  });

  it.each([
    ["sa_company_financials", "Captured SA financial tables"],
    ["sa_company_valuation", "Captured SA valuations and peers"],
    ["sa_company_estimates", "Captured SA estimates and revisions"],
  ] as const)("controls %s independently without enabling paid fallback", async (dataset, label) => {
    await render();
    await click(source(`${label}: Seeking Alpha`));
    await click(button(`Save sources: ${label}`));
    expect(putDataSourceRoute).toHaveBeenCalledExactlyOnceWith(dataset, []);
    expect(putFinancialDatasetsBudget).not.toHaveBeenCalled();
    expect(source(`${FUNDAMENTALS}: SEC EDGAR`).checked).toBe(true);
  });

  it("changes the ordered fallback route with stable move controls", async () => {
    await render();
    await click(button(`Higher priority: ${FD}`));
    await click(button(`Save sources: ${FUNDAMENTALS}`));
    expect(putDataSourceRoute).toHaveBeenCalledWith("fundamentals_analysis", ["financial_datasets", "sec_edgar"]);
    expect(button(`Higher priority: ${FD}`).disabled).toBe(true);
  });

  it("persists an empty route instead of silently restoring defaults", async () => {
    await render();
    await click(source(`${FUNDAMENTALS}: SEC EDGAR`));
    await click(source(`${FUNDAMENTALS}: ${FD}`));
    await click(button(`Save sources: ${FUNDAMENTALS}`));
    expect(putDataSourceRoute).toHaveBeenCalledWith("fundamentals_analysis", []);
    expect(host.textContent).toContain("No source selected");
  });

  it("keeps the draft on a rejected save and supports explicit discard", async () => {
    vi.mocked(putDataSourceRoute).mockRejectedValue(new Error("PRIVATE_BACKEND_DETAIL"));
    await render();
    await click(source(`${FUNDAMENTALS}: SEC EDGAR`));
    await click(button(`Save sources: ${FUNDAMENTALS}`));
    expect(source(`${FUNDAMENTALS}: SEC EDGAR`).checked).toBe(false);
    expect(host.textContent).toContain("Changes were not saved");
    expect(host.textContent).not.toContain("PRIVATE_BACKEND_DETAIL");
    expect(guard).toHaveBeenLastCalledWith(expect.objectContaining({ dirty: true, busy: false }));
    await click(button(`Discard source changes: ${FUNDAMENTALS}`));
    expect(source(`${FUNDAMENTALS}: SEC EDGAR`).checked).toBe(true);
    expect(guard).toHaveBeenLastCalledWith({ dirty: false, busy: false, reason: null });
  });

  it("retains another row's unsaved draft when a save invalidates the shared read cache", async () => {
    await render();
    await click(source(`${FUNDAMENTALS}: SEC EDGAR`));
    await click(source("Detailed financials: earnings supplement: Finnhub"));
    await click(button("Save sources: Detailed financials: earnings supplement"));
    expect(source(`${FUNDAMENTALS}: SEC EDGAR`).checked).toBe(false);
    expect(button(`Save sources: ${FUNDAMENTALS}`).disabled).toBe(false);
    expect(guard).toHaveBeenLastCalledWith(expect.objectContaining({ dirty: true }));
  });

  it("never presents a failed refresh as successfully verified settings", async () => {
    const cache = createSettingsReadCache();
    cache.replace("data_source_routes", structuredClone(state));
    await render(cache);
    vi.mocked(getDataSourceRoutes).mockRejectedValue(new Error("offline"));
    await click(button("Reload status"));
    expect(host.textContent).toContain("Retained values may be outdated");
    expect(source(`${FUNDAMENTALS}: SEC EDGAR`).checked).toBe(true);
    expect(putDataSourceRoute).not.toHaveBeenCalled();
  });

  it("requires limits and an explicit billing confirmation before enabling paid requests", async () => {
    await render();
    await click(paid());
    await click(button(SAVE_BUDGET));
    expect(host.textContent).toContain("Both request limits must be positive whole numbers");
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    await limit(0, "10");
    await limit(1, "2");
    await click(button(SAVE_BUDGET));
    expect(document.querySelector('[role="dialog"]')?.textContent).toContain("not a dollar cap");
    expect(putFinancialDatasetsBudget).not.toHaveBeenCalled();
    expect(guard).toHaveBeenLastCalledWith(expect.objectContaining({ dirty: true, busy: true }));
    await click(button("Cancel"));
    expect(putFinancialDatasetsBudget).not.toHaveBeenCalled();
    await click(button(SAVE_BUDGET));
    await click(button("Authorize and save"));
    expect(putFinancialDatasetsBudget).toHaveBeenCalledExactlyOnceWith({
      enabled: true, daily_request_limit: "10", requests_per_minute: "2", confirm_paid: true,
    });
    expect(host.textContent).toContain("Paid requests allowed within limits");
    expect(guard).toHaveBeenLastCalledWith({ dirty: false, busy: false, reason: null });
  });

  it("keeps int64 limits exact through the confirmation and save", async () => {
    await render();
    await click(paid());
    await limit(0, "9223372036854775807");
    await limit(1, "1");
    await click(button(SAVE_BUDGET));
    expect(document.querySelector('[role="dialog"]')?.textContent).toContain("9223372036854775807");
    await click(button("Authorize and save"));
    expect(putFinancialDatasetsBudget).toHaveBeenCalledWith(expect.objectContaining({ daily_request_limit: "9223372036854775807" }));
    expect(host.querySelector<HTMLInputElement>('.data-route-budget-fields input')!.value).toBe("9223372036854775807");
  });

  it("can disable paid acquisition without an enablement confirmation", async () => {
    state.financial_datasets_budget = {
      enabled: true, daily_request_limit: "10", requests_per_minute: "2",
      setting_source: "profile", state: "enabled", error_code: null,
    };
    await render();
    await click(paid());
    await click(button(SAVE_BUDGET));
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    expect(putFinancialDatasetsBudget).toHaveBeenCalledExactlyOnceWith({
      enabled: false, daily_request_limit: "10", requests_per_minute: "2", confirm_paid: false,
    });
    expect(host.textContent).toContain("Paid requests disabled");
  });

  it.each(["unconfigured", "invalid"] as const)("can explicitly disable an %s policy without inventing limits", async (stateName) => {
    state.financial_datasets_budget.state = stateName;
    if (stateName === "invalid") state.financial_datasets_budget.enabled = null;
    await render();
    expect(guard).toHaveBeenLastCalledWith({ dirty: false, busy: false, reason: null });
    expect(paid().checked).toBe(false);
    expect(button(SAVE_BUDGET).disabled).toBe(false);
    await click(button(SAVE_BUDGET));
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    expect(putFinancialDatasetsBudget).toHaveBeenCalledExactlyOnceWith({
      enabled: false, daily_request_limit: null, requests_per_minute: null, confirm_paid: false,
    });
    expect(host.textContent).toContain("Paid requests disabled");
    expect(button(SAVE_BUDGET).disabled).toBe(true);
  });

  it.each(["0", "-1", "1.5", "9223372036854775808"])("rejects invalid request limit %s before confirmation", async (value) => {
    await render();
    await click(paid());
    await limit(0, value);
    await limit(1, "1");
    await click(button(SAVE_BUDGET));
    expect(host.textContent).toContain("Both request limits must be positive whole numbers");
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    expect(putFinancialDatasetsBudget).not.toHaveBeenCalled();
  });

  it("does not claim enablement when the confirmed save fails", async () => {
    vi.mocked(putFinancialDatasetsBudget).mockRejectedValue(new Error("failed"));
    await render();
    await click(paid());
    await limit(0, "10");
    await limit(1, "2");
    await click(button(SAVE_BUDGET));
    await click(button("Authorize and save"));
    expect(document.querySelector('[role="dialog"]')?.textContent).toContain("Changes were not saved");
    expect(host.textContent).toContain("Request limits not configured");
    expect(host.textContent).not.toContain("Paid requests allowed within limits");
    await click(button("Cancel"));
    expect(guard).toHaveBeenLastCalledWith(expect.objectContaining({ dirty: true, busy: false }));
  });

  it("keeps a malformed stored route visible until explicitly repaired", async () => {
    Object.assign(state.routes[0], { providers: null, setting_source: "profile", error_code: "data_source_policy_invalid" });
    await render();
    expect(host.textContent).toContain("Invalid configuration");
    expect(source(`${FUNDAMENTALS}: SEC EDGAR`).checked).toBe(false);
    await click(source(`${FUNDAMENTALS}: SEC EDGAR`));
    await click(button(`Save sources: ${FUNDAMENTALS}`));
    expect(host.textContent).not.toContain("Invalid configuration");
    expect(putDataSourceRoute).toHaveBeenCalledWith("fundamentals_analysis", ["sec_edgar"]);
  });
});
