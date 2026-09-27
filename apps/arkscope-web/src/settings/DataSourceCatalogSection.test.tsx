/** @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { readFileSync } from "node:fs";
import i18n from "i18next";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { DataSourceCapability, DataSourceCatalog, DataSourceRoutesResponse, ProvidersConfigResponse } from "../api";
import { createSettingsReadCache, type SettingsReadCache } from "./settingsReadCache";
import { settingsParentAnchor } from "./settingsRegistry";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

vi.mock("../api", async (importOriginal) => ({
  ...await importOriginal<typeof import("../api")>(),
  getDataSourceCatalog: vi.fn(),
  getProvidersConfig: vi.fn(),
  putDataSourceRoute: vi.fn(),
  runScheduleNow: vi.fn(),
  testProvider: vi.fn(),
}));

import { getDataSourceCatalog, getProvidersConfig, putDataSourceRoute, runScheduleNow, testProvider } from "../api";
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
          financial_routes: ["sa_company_financials"],
        }),
        source("massive", { integration: "candidate", acquisition: "not_implemented", controls: [], access_requirement: "endpoint_entitlement_unverified" }),
      ] },
      { id: "valuation_ratings", sources: [source("seeking_alpha", {
        acquisition: "browser_page_capture", controls: ["financial_sources", "sa_extension"],
        access_requirement: "signed_in_browser_subscription",
      })] },
      { id: "earnings_estimates", sources: [source("seeking_alpha", {
        acquisition: "browser_page_capture", controls: ["financial_sources", "sa_extension"],
        access_requirement: "signed_in_browser_subscription",
      })] },
      { id: "news", sources: [
        source("massive", { acquisition: "app_job", access_requirement: "endpoint_entitlement_unverified", controls: ["source_schedules"] }),
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
let config: ProvidersConfigResponse;
let root: ReturnType<typeof createRoot> | null;
let host: HTMLDivElement;
const navigate = vi.fn();

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((accept, decline) => {
    resolve = accept;
    reject = decline;
  });
  return { promise, resolve, reject };
}

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
  config = {
    providers: {
      massive: { testable: true, default_available: false, fields: [{
        field: "api_key", label: "API key", secret: true, env_var: "MASSIVE_API_KEY",
        app_value_set: true, app_value_masked: "MASKED_SECRET_SENTINEL", effective_source: "app",
        needs_import: false, import_source: null, importable_env_vars: [], defaulted: false,
        guarded: false, guard_reason: null,
      }] },
    },
    setup: { required: false, code: null, reason: null },
    env_fallback: { enabled: false, source: "default" },
  };
  vi.mocked(getDataSourceCatalog).mockImplementation(async () => structuredClone(state));
  vi.mocked(getProvidersConfig).mockImplementation(async () => structuredClone(config));
});

afterEach(() => {
  if (root) act(() => root!.unmount());
  root = null;
  document.body.replaceChildren();
  vi.useRealTimers();
});

describe("DataSourceCatalogSection", () => {
  it("shows integration and access requirements without activating sources", async () => {
    await render();
    expect(provider("sec_edgar").textContent).toContain("Category adapter present");
    expect(provider("financial_datasets").textContent).toContain("authorized request budget required");
    expect(provider("seeking_alpha").textContent).toContain("Category adapter present");
    expect(provider("massive").textContent).toContain("Category adapter missing");
    expect(provider("massive").textContent).toContain("Provider integrated elsewhere");
    expect(provider("massive").textContent).toContain("A subscription upgrade alone cannot enable financial acquisition");
    expect(provider("seeking_alpha").querySelector('.data-catalog-provider')?.textContent).toBe("Seeking Alpha");
    expect(host.querySelectorAll('input[type="checkbox"]')).toHaveLength(0);
    expect(putDataSourceRoute).not.toHaveBeenCalled();
    expect(runScheduleNow).not.toHaveBeenCalled();
    expect(testProvider).not.toHaveBeenCalled();
  });

  it("separates explicit company research capture from extension news alarms", async () => {
    await render();
    expect(provider("seeking_alpha").textContent).toContain("Company-page capture: manual / scheduled");
    expect(provider("seeking_alpha").textContent).toContain("Captured SA financial tables");
    expect(provider("seeking_alpha").textContent).toContain("support the common financial read and reviewed ratios");
    await select("valuation_ratings");
    expect(provider("seeking_alpha").textContent).toContain("Company-page capture: manual / scheduled");
    await select("earnings_estimates");
    expect(provider("seeking_alpha").textContent).toContain("Company-page capture: manual / scheduled");
    await select("news");
    expect(provider("seeking_alpha").textContent).toContain("Browser extension capture / auto-sync");
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
    cache.replace("provider_config", config);
    await render(cache);
    expect(getDataSourceCatalog).not.toHaveBeenCalled();
    expect(getProvidersConfig).not.toHaveBeenCalled();
    await select("news");
    expect(provider("finnhub").textContent).toContain("endpoint access unverified");
    expect(testProvider).not.toHaveBeenCalled();
  });

  it.each(["app", "env", "config/.env"])("shows configured keys from %s without claiming entitlement or disclosing values", async (effectiveSource) => {
    config.providers.massive.fields[0].effective_source = effectiveSource;
    await render();
    expect(provider("massive").textContent).toContain("API key configured");
    expect(provider("massive").textContent).toContain("endpoint access unverified");
    expect(provider("massive").textContent).toContain("Category adapter missing");
    expect(host.textContent).not.toContain("MASKED_SECRET_SENTINEL");
    expect(testProvider).not.toHaveBeenCalled();
  });

  it("treats stored/importable but ineffective keys as missing and reloads after a config change", async () => {
    config.providers.massive.fields[0].effective_source = "missing";
    config.providers.massive.fields[0].needs_import = true;
    const cache = createSettingsReadCache();
    await render(cache);
    expect(provider("massive").textContent).toContain("API key not configured");
    config.providers.massive.fields[0].effective_source = "env";
    await act(async () => { cache.invalidate("provider_config"); });
    await flush();
    expect(provider("massive").textContent).toContain("API key configured");
    expect(provider("massive").querySelector("button")).toBeNull();
  });

  it("does not present stale credential state as current after a failed refresh", async () => {
    await render();
    vi.mocked(getProvidersConfig).mockRejectedValueOnce(new Error("PRIVATE_CONFIG_ERROR"));
    await click(reload());
    expect(provider("massive").textContent).toContain("API key status unavailable");
    expect(provider("massive").textContent).not.toContain("API key configured");
    expect(host.textContent).not.toContain("PRIVATE_CONFIG_ERROR");
    await click(reload());
    expect(provider("massive").textContent).toContain("API key configured");
  });

  it("keeps an unset credential read unknown until the first response arrives", async () => {
    const pending = deferred<ProvidersConfigResponse>();
    vi.mocked(getProvidersConfig).mockReturnValueOnce(pending.promise);
    await render();
    expect(provider("massive").textContent).toContain("API key status unavailable");
    expect(provider("massive").textContent).not.toContain("API key configured");
    expect(provider("seeking_alpha").textContent).toContain("No API key used for this source");

    await act(async () => { pending.resolve(config); });
    expect(provider("massive").textContent).toContain("API key configured");
  });

  it("does not treat stale cached credentials as current while mount revalidation is pending", async () => {
    vi.useFakeTimers();
    const cache = createSettingsReadCache();
    cache.replace("data_source_catalog", state);
    cache.replace("provider_config", structuredClone(config));
    vi.advanceTimersByTime(61_000);
    const pending = deferred<ProvidersConfigResponse>();
    vi.mocked(getProvidersConfig).mockReturnValueOnce(pending.promise);

    await render(cache);

    expect(provider("massive").textContent).toContain("API key status unavailable");
    expect(provider("massive").textContent).not.toContain("API key configured");
    expect(getDataSourceCatalog).not.toHaveBeenCalled();
    config.providers.massive.fields[0].effective_source = "missing";
    await act(async () => { pending.resolve(config); });
    expect(provider("massive").textContent).toContain("API key not configured");
  });

  it.each(["catalog reload", "invalidation", "parent refresh"])(
    "withdraws the previous credential claim during a pending %s",
    async (trigger) => {
      const cache = createSettingsReadCache();
      await render(cache);
      expect(provider("massive").textContent).toContain("API key configured");
      const pending = deferred<ProvidersConfigResponse>();
      vi.mocked(getProvidersConfig).mockReturnValueOnce(pending.promise);

      if (trigger === "catalog reload") await click(reload());
      else await act(async () => {
        if (trigger === "invalidation") cache.invalidate("provider_config");
        else void cache.load("provider_config", getProvidersConfig, { force: true });
      });

      expect(provider("massive").textContent).toContain("API key status unavailable");
      expect(provider("massive").textContent).not.toContain("API key configured");
      config.providers.massive.fields[0].effective_source = "missing";
      await act(async () => { pending.resolve(config); });
      expect(provider("massive").textContent).toContain("API key not configured");
    },
  );

  it.each(["refresh", "replace"])("observes a parent config %s without reloading the catalog", async (update) => {
    const cache = createSettingsReadCache();
    await render(cache);
    config.providers.massive.fields[0].effective_source = "missing";

    await act(async () => {
      if (update === "refresh") await cache.load("provider_config", getProvidersConfig, { force: true });
      else cache.replace("provider_config", structuredClone(config));
    });

    expect(provider("massive").textContent).toContain("API key not configured");
    expect(provider("massive").textContent).not.toContain("API key configured");
    expect(getDataSourceCatalog).toHaveBeenCalledTimes(1);
    expect(getProvidersConfig).toHaveBeenCalledTimes(update === "refresh" ? 2 : 1);
  });

  it.each(["catalog", "parent"])("does not resurrect configured credentials on remount after a failed %s refresh", async (owner) => {
    const cache = createSettingsReadCache();
    await render(cache);
    vi.mocked(getProvidersConfig).mockRejectedValueOnce(new Error("PRIVATE_CONFIG_ERROR"));
    if (owner === "catalog") await click(reload());
    else await act(async () => { await cache.load("provider_config", getProvidersConfig, { force: true }); });

    expect(provider("massive").textContent).toContain("API key status unavailable");
    await act(async () => { root!.unmount(); root = null; });
    const pending = deferred<ProvidersConfigResponse>();
    vi.mocked(getProvidersConfig).mockReturnValueOnce(pending.promise);
    await render(cache);

    expect(provider("massive").textContent).toContain("API key status unavailable");
    expect(provider("massive").textContent).not.toContain("API key configured");
    expect(host.textContent).not.toContain("PRIVATE_CONFIG_ERROR");
    expect(getProvidersConfig).toHaveBeenCalledTimes(3);
    await act(async () => { pending.resolve(config); });
    expect(provider("massive").textContent).toContain("API key configured");
  });

  it("does not adopt a fresh-looking credential snapshot when mounting during a parent refresh", async () => {
    const cache = createSettingsReadCache();
    cache.replace("provider_config", config);
    const pending = deferred<ProvidersConfigResponse>();
    vi.mocked(getProvidersConfig).mockReturnValueOnce(pending.promise);
    const loading = cache.load("provider_config", getProvidersConfig, { force: true });

    await render(cache);

    expect(provider("massive").textContent).toContain("API key status unavailable");
    expect(getProvidersConfig).toHaveBeenCalledOnce();
    config.providers.massive.fields[0].effective_source = "missing";
    await act(async () => { pending.resolve(config); await loading; });
    expect(provider("massive").textContent).toContain("API key not configured");
  });

  it("expires the credential claim while mounted without probing a provider", async () => {
    vi.useFakeTimers();
    await render();
    expect(provider("massive").textContent).toContain("API key configured");

    await act(async () => { vi.advanceTimersByTime(60_001); });

    expect(provider("massive").textContent).toContain("API key status unavailable");
    expect(provider("massive").textContent).not.toContain("API key configured");
    expect(getProvidersConfig).toHaveBeenCalledOnce();
    expect(testProvider).not.toHaveBeenCalled();
  });

  it("does not let an invalidated config request replace a newer missing-key response", async () => {
    const cache = createSettingsReadCache();
    const pending = deferred<ProvidersConfigResponse>();
    vi.mocked(getProvidersConfig).mockReturnValueOnce(pending.promise);
    await render(cache);
    const oldConfig = structuredClone(config);
    config.providers.massive.fields[0].effective_source = "missing";
    await act(async () => { cache.invalidate("provider_config"); });
    expect(provider("massive").textContent).toContain("API key not configured");

    await act(async () => { pending.resolve(oldConfig); });

    expect(provider("massive").textContent).toContain("API key not configured");
    expect(provider("massive").textContent).not.toContain("API key configured");
  });

  it("does not interpret a configured Financial Datasets key as enabling paid requests", async () => {
    config.providers.financial_datasets = structuredClone(config.providers.massive);
    const cache = createSettingsReadCache();
    const routes: DataSourceRoutesResponse = {
      routes: [],
      financial_datasets_budget: {
        enabled: false, daily_request_limit: null, requests_per_minute: null,
        setting_source: "default", state: "disabled", error_code: null,
      },
    };
    cache.replace("data_source_routes", routes);
    await render(cache);

    expect(provider("financial_datasets").textContent).toContain("API key configured");
    expect(provider("financial_datasets").textContent).toContain("authorized request budget required");
    expect(provider("financial_datasets").textContent).not.toContain("Paid requests allowed");
    expect(cache.inspect("data_source_routes")).toMatchObject({ status: "fresh", value: routes });
    expect(putDataSourceRoute).not.toHaveBeenCalled();
    expect(runScheduleNow).not.toHaveBeenCalled();
    expect(testProvider).not.toHaveBeenCalled();
  });

  it("treats an incomplete config store as unknown, not as a verified missing key", async () => {
    config.setup.required = true;
    config.providers.massive.fields[0].effective_source = "missing";
    await render();
    expect(provider("massive").textContent).toContain("API key status unavailable");
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
    expect(provider("seeking_alpha").textContent).toContain(locale === "en" ? "Browser extension capture" : "瀏覽器擴充套件擷取");
  });

  it("stacks rows by container width while keeping text wrap-capable", () => {
    const css = readFileSync("src/settings/settings.css", "utf8");
    expect(css).toContain("container: data-source-catalog / inline-size");
    expect(css).toContain("@container data-source-catalog (max-width: 720px)");
    expect(css).toMatch(/\.data-catalog-row > \*\s*\{[^}]*min-width:\s*0;[^}]*overflow-wrap:\s*anywhere;/);
  });
});
