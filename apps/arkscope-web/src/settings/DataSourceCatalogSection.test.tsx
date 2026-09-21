/** @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { readFileSync } from "node:fs";
import i18n from "i18next";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { DataSourceCapability, DataSourceCatalog } from "../api";
import { createSettingsReadCache, type SettingsReadCache } from "./settingsReadCache";
import { settingsParentAnchor } from "./settingsRegistry";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

vi.mock("../api", async (importOriginal) => ({
  ...await importOriginal<typeof import("../api")>(),
  getDataSourceCatalog: vi.fn(),
  putDataSourceRoute: vi.fn(),
  runScheduleNow: vi.fn(),
  testProvider: vi.fn(),
}));

import { getDataSourceCatalog, putDataSourceRoute, runScheduleNow, testProvider } from "../api";
import { DataSourceCatalogSection } from "./DataSourceCatalogSection";

function source(provider: string, overrides: Partial<DataSourceCapability> = {}): DataSourceCapability {
  return {
    provider, integration: "implemented", acquisition: "on_demand_api", access_requirement: "public_identity",
    controls: ["financial_sources"], schedule_sources: [], financial_routes: [], ...overrides,
  };
}

function fixture(): DataSourceCatalog {
  return {
    scope: "current_integrations_and_candidates",
    categories: [
      { id: "financial_statements", sources: [
        source("sec_edgar"), source("financial_datasets", { access_requirement: "metered_requests" }),
        source("seeking_alpha", {
          acquisition: "browser_page_capture", controls: ["financial_sources", "sa_extension"],
          access_requirement: "signed_in_browser_subscription",
        }),
        source("massive", { integration: "candidate", acquisition: "not_implemented", controls: [] }),
      ] },
      { id: "valuation_ratings", sources: [source("seeking_alpha", {
        integration: "candidate", acquisition: "not_implemented", controls: [],
        access_requirement: "signed_in_browser_subscription",
      })] },
      { id: "news", sources: [
        source("finnhub", { acquisition: "app_job", access_requirement: "endpoint_entitlement_unverified", controls: ["source_schedules"] }),
        source("seeking_alpha", {
          acquisition: "browser_extension", access_requirement: "signed_in_browser_subscription", controls: ["sa_extension"],
        }),
      ] },
      { id: "macro", sources: [source("fred", { acquisition: "app_job", access_requirement: "api_key", controls: ["macro_schedules"] })] },
    ],
  };
}

let state: DataSourceCatalog;
let root: ReturnType<typeof createRoot> | null;
let host: HTMLDivElement;
const navigate = vi.fn();

async function flush() {
  await act(async () => { await Promise.resolve(); await Promise.resolve(); });
}

async function render(cache: SettingsReadCache = createSettingsReadCache(), withNavigation = true) {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(<DataSourceCatalogSection settingsReadCache={cache} onNavigate={withNavigation ? navigate : undefined} />);
  });
  await flush();
}

function provider(name: string): HTMLElement {
  return host.querySelector(`[data-catalog-provider="${name}"]`)!;
}

async function select(value: string) {
  await act(async () => {
    const control = host.querySelector("select")!;
    control.value = value;
    control.dispatchEvent(new Event("change", { bubbles: true }));
  });
}

async function click(element: HTMLElement) {
  await act(async () => { element.click(); });
  await flush();
}

function reload(): HTMLButtonElement { return host.querySelector(".data-catalog-toolbar button")!; }

beforeEach(async () => {
  await i18n.changeLanguage("en");
  vi.resetAllMocks();
  state = fixture();
  vi.mocked(getDataSourceCatalog).mockImplementation(async () => structuredClone(state));
});

afterEach(() => {
  if (root) act(() => root!.unmount());
  root = null;
  document.body.replaceChildren();
});

describe("DataSourceCatalogSection", () => {
  it("shows integration and access requirements without activating sources", async () => {
    await render();
    expect(provider("sec_edgar").textContent).toContain("Integrated");
    expect(provider("financial_datasets").textContent).toContain("authorized request budget required");
    expect(provider("seeking_alpha").textContent).toContain("Integrated");
    expect(provider("massive").textContent).toContain("Not integrated");
    expect(provider("seeking_alpha").querySelector('.data-catalog-provider')?.textContent).toBe("Seeking Alpha");
    expect(host.querySelectorAll('input[type="checkbox"]')).toHaveLength(0);
    expect(putDataSourceRoute).not.toHaveBeenCalled();
    expect(runScheduleNow).not.toHaveBeenCalled();
    expect(testProvider).not.toHaveBeenCalled();
  });

  it("separates manual financial capture, extension news alarms and unimplemented valuation", async () => {
    await render();
    expect(provider("seeking_alpha").textContent).toContain("Explicit capture of the displayed financial table");
    await select("valuation_ratings");
    expect(provider("seeking_alpha").textContent).toContain("Not integrated");
    expect(provider("seeking_alpha").querySelector("button")).toBeNull();
    await select("news");
    expect(provider("seeking_alpha").textContent).toContain("Chrome capture / extension auto-sync");
    expect(provider("finnhub").textContent).toContain("endpoint access unverified");
    await click(provider("seeking_alpha").querySelector("button")!);
    expect(navigate).toHaveBeenCalledExactlyOnceWith("sa_extension_health");
    expect(getDataSourceCatalog).toHaveBeenCalledTimes(1);
    expect(runScheduleNow).not.toHaveBeenCalled();
    expect(testProvider).not.toHaveBeenCalled();
  });

  it.each([
    ["financial_sources", "data_source_routes"],
    ["source_schedules", "source_schedules"],
    ["macro_schedules", "macro_storage"],
    ["sa_extension", "sa_extension_health"],
    ["connections", "provider_connections"],
    ["price_coverage", "trading_day_coverage"],
    ["sec_research", "sec_structured_storage"],
  ] as const)("navigates %s to the existing %s owner", async (control, destination) => {
    state.categories[0].sources = [source("sec_edgar", { controls: [control] })];
    await render();
    await click(provider("sec_edgar").querySelector("button")!);
    expect(navigate).toHaveBeenCalledExactlyOnceWith(destination);
    expect(settingsParentAnchor(destination)).toBeTruthy();
  });

  it("never exposes controls for a candidate even if a response includes them", async () => {
    state.categories[0].sources = [source("seeking_alpha", { integration: "candidate", controls: ["financial_sources"] })];
    await render();
    expect(provider("seeking_alpha").querySelector("button")).toBeNull();
    expect(navigate).not.toHaveBeenCalled();
  });

  it("reuses the retained metadata without probing accounts", async () => {
    const cache = createSettingsReadCache();
    cache.replace("data_source_catalog", state);
    await render(cache);
    expect(getDataSourceCatalog).not.toHaveBeenCalled();
    await select("news");
    expect(provider("finnhub").textContent).toContain("endpoint access unverified");
    expect(testProvider).not.toHaveBeenCalled();
  });

  it("keeps the selected category and old definitions on failed reload without displaying diagnostics", async () => {
    await render();
    await select("news");
    vi.mocked(getDataSourceCatalog).mockRejectedValueOnce(new Error("PRIVATE_DIAGNOSTIC"));
    await click(reload());
    expect(host.querySelector("[role=alert]")?.textContent).toContain("Catalog unavailable");
    expect(host.textContent).not.toContain("PRIVATE_DIAGNOSTIC");
    expect(host.querySelector("select")?.value).toBe("news");
    expect(provider("seeking_alpha")).toBeTruthy();
    await click(reload());
    expect(host.querySelector("[role=alert]")).toBeNull();
    expect(host.querySelector("select")?.value).toBe("news");
  });

  it("offers a working retry after first-load failure", async () => {
    vi.mocked(getDataSourceCatalog).mockRejectedValueOnce(new Error("offline"));
    await render();
    expect(host.querySelector("[role=alert]")).not.toBeNull();
    expect(host.querySelector("select")).toBeNull();
    expect(reload().disabled).toBe(false);
    await click(reload());
    expect(host.querySelector("[role=alert]")).toBeNull();
    expect(provider("sec_edgar")).toBeTruthy();
  });

  it("falls back to an existing category when the catalog changes", async () => {
    await render();
    await select("news");
    state.categories = state.categories.filter((item) => item.id === "macro");
    await click(reload());
    expect(host.querySelector("select")?.value).toBe("macro");
    expect(provider("fred")).toBeTruthy();
  });

  it("handles an empty catalog without inventing providers", async () => {
    state.categories = [];
    await render();
    expect(host.textContent).toContain("No data categories available");
    expect(host.querySelector("select")).toBeNull();
    expect(host.querySelector("[role=table]")).toBeNull();
  });

  it("does not leave an actionable navigation button without its Settings owner", async () => {
    await render(createSettingsReadCache(), false);
    const button = provider("sec_edgar").querySelector("button")!;
    expect(button.disabled).toBe(true);
    await click(button);
    expect(navigate).not.toHaveBeenCalled();
  });

  it("handles a pending metadata load and safely ignores completion after unmount", async () => {
    let done!: (value: DataSourceCatalog) => void;
    vi.mocked(getDataSourceCatalog).mockImplementationOnce(() => new Promise((resolve) => { done = resolve; }));
    await render();
    expect(host.querySelector("[role=status]")).not.toBeNull();
    expect(reload().disabled).toBe(true);
    await act(async () => { root!.unmount(); root = null; done(state); });
    await flush();
    expect(getDataSourceCatalog).toHaveBeenCalledTimes(1);
    expect(host.textContent).toBe("");
  });

  it.each(["en", "zh-Hant"])("localizes the catalog in %s", async (locale) => {
    await i18n.changeLanguage(locale);
    await render();
    expect(host.textContent).toContain(locale === "en" ? "Data Types and Sources" : "資料種類與來源");
    expect(host.textContent).not.toMatch(/dataSources\.catalog|financial_statements|public_identity/);
    await select("news");
    expect(provider("seeking_alpha").textContent).toContain(locale === "en" ? "Chrome capture" : "Chrome 擷取");
  });

  it("stacks rows by container width while keeping text wrap-capable", () => {
    const css = readFileSync("src/settings/settings.css", "utf8");
    expect(css).toContain("container: data-source-catalog / inline-size");
    expect(css).toContain("@container data-source-catalog (max-width: 720px)");
    expect(css).toMatch(/\.data-catalog-row > \*\s*\{[^}]*min-width:\s*0;[^}]*overflow-wrap:\s*anywhere;/);
  });
});
