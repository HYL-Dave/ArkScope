/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ModelCatalog, ModelTask, TaskRoute } from "./api";
import type { SettingsNavigationRequest } from "./shell/navigation";
import { SETTINGS_ANCHOR_IDS } from "./settings/settingsRegistry";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

const mocks = vi.hoisted(() => ({
  getModelCatalog: vi.fn(),
}));

const emptyCatalog: ModelCatalog = {
  providers: ["anthropic", "openai"],
  tasks: [],
  models: [],
  effort_options: { anthropic: [], openai: [] },
  routes: {} as Record<ModelTask, TaskRoute>,
  credentials: { anthropic: [], openai: [] },
  custom_allowed: true,
};

vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return { ...actual, getModelCatalog: mocks.getModelCatalog };
});

vi.mock("./InvestorProfilePanel", () => ({ InvestorProfilePanel: () => null }));
vi.mock("./settings/DataSourcesSection", () => ({ DataSourcesSection: () => null }));
vi.mock("./settings/DataStorageSection", () => ({ DataStorageSection: () => null }));
vi.mock("./settings/MacroStorageSection", () => ({ MacroStorageSection: () => null }));
vi.mock("./settings/NewsStorageSection", () => ({ NewsStorageSection: () => null }));
vi.mock("./settings/ModelRoutingSection", () => ({
  ModelRoutingSection: () => null,
  TASK_LABELS: {
    card_synthesis: "AI 卡片生成",
    card_translation: "卡片翻譯",
    ai_research: "AI 研究",
  },
}));
vi.mock("./settings/ProviderSection", () => ({
  ProviderSection: () => null,
  CredentialList: () => null,
  DiscoveryResultView: () => null,
  SetupDisclosure: () => null,
}));
vi.mock("./settings/RuntimeLimitSections", () => ({
  FixedTaskRuntimeSection: () => null,
  ResearchRuntimeSection: () => null,
}));

import { SettingsView } from "./Settings";

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;
let overlay = false;
const scrollIntoView = vi.fn();

function installViewport() {
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    value: vi.fn(() => ({
      matches: overlay,
      media: "(max-width: 960px)",
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

async function flush() {
  await act(async () => {
    await Promise.resolve();
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

async function renderSettings(options: {
  narrow?: boolean;
  navigationRequest?: SettingsNavigationRequest | null;
} = {}) {
  overlay = options.narrow ?? false;
  installViewport();
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(
      <SettingsView
        runtime={null}
        onRuntimeChanged={vi.fn(async () => undefined)}
        navigationRequest={options.navigationRequest}
      />,
    );
  });
  await flush();
}

function dispose() {
  if (root) act(() => root!.unmount());
  root = null;
  host?.remove();
  host = null;
}

function buttonWithText(text: string, scope: ParentNode = document): HTMLButtonElement {
  const button = Array.from(scope.querySelectorAll("button"))
    .find((candidate) => candidate.textContent?.trim() === text);
  if (!(button instanceof HTMLButtonElement)) throw new Error(`missing button: ${text}`);
  return button;
}

async function click(element: HTMLElement) {
  await act(async () => {
    element.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
  });
  await flush();
}

async function setSearch(value: string) {
  const input = document.querySelector('input[aria-label="搜尋設定"]');
  if (!(input instanceof HTMLInputElement)) throw new Error("missing settings search");
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
  await act(async () => {
    setter?.call(input, value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
  return input;
}

beforeEach(() => {
  mocks.getModelCatalog.mockReset();
  mocks.getModelCatalog.mockResolvedValue(emptyCatalog);
  window.localStorage.clear();
  scrollIntoView.mockReset();
  Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
    configurable: true,
    value: scrollIntoView,
  });
  Object.defineProperty(window, "requestAnimationFrame", {
    configurable: true,
    value: (callback: FrameRequestCallback) => window.setTimeout(() => callback(0), 0),
  });
  Object.defineProperty(window, "cancelAnimationFrame", {
    configurable: true,
    value: (handle: number) => window.clearTimeout(handle),
  });
});

afterEach(() => {
  dispose();
  document.body.replaceChildren();
  vi.restoreAllMocks();
});

describe("Settings workspace", () => {
  it("renders_generic_page_header_and_all_shipped_groups_and_anchors", async () => {
    await renderSettings();

    expect(host!.querySelector("h1")?.textContent).toBe("設定");
    expect(Array.from(host!.querySelectorAll(".settings-workspace-group > header h2"))
      .map((heading) => heading.textContent)).toEqual(["AI 與模型", "個人化", "資料與同步"]);
    expect(Array.from(host!.querySelectorAll("[data-settings-anchor]"))
      .map((anchor) => anchor.getAttribute("data-settings-anchor"))).toEqual(SETTINGS_ANCHOR_IDS);
  });

  it("omits_legacy_model_header_runtime_band_and_global_route_actions", async () => {
    await renderSettings();

    expect(host!.querySelectorAll("h1")).toHaveLength(1);
    expect(host!.querySelector(".settings-band")).toBeNull();
    expect(host!.querySelector(".ui-page-header-actions")).toBeNull();
    const models = host!.querySelector('[data-settings-anchor="models"]')!;
    const transfer = models.querySelector("details");
    expect(transfer?.open).toBe(false);
    expect(buttonWithText("從設定檔匯入", transfer!)).not.toBeNull();
    expect(buttonWithText("匯出到設定檔", transfer!)).not.toBeNull();
    expect(host!.querySelectorAll('[data-settings-anchor]:not([data-settings-anchor="models"]) details button'))
      .toHaveLength(0);
  });

  it("renders_one_persistent_searchable_directory_on_wide_screens", async () => {
    await renderSettings();

    expect(host!.querySelectorAll('nav[aria-label="設定目錄"]')).toHaveLength(1);
    expect(host!.querySelectorAll('input[aria-label="搜尋設定"]')).toHaveLength(1);
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    expect(Array.from(host!.querySelectorAll("button")).some((node) => node.textContent === "設定目錄")).toBe(false);
  });

  it("renders_one_directory_trigger_and_transient_drawer_on_narrow_screens", async () => {
    await renderSettings({ narrow: true });

    expect(host!.querySelector('nav[aria-label="設定目錄"]')).toBeNull();
    const trigger = buttonWithText("設定目錄", host!);
    await click(trigger);
    expect(document.querySelectorAll('[role="dialog"][aria-modal="true"]')).toHaveLength(1);
    expect(document.querySelectorAll('input[aria-label="搜尋設定"]')).toHaveLength(1);
  });

  it("collapses_persists_and_unmounts_a_group_body", async () => {
    await renderSettings();

    await click(document.querySelector('button[aria-label="收合 AI 與模型"]') as HTMLElement);
    expect(host!.querySelector('[data-settings-anchor="providers"]')).toBeNull();
    expect(host!.querySelector('[data-settings-anchor="models"]')).toBeNull();
    expect(window.localStorage.getItem("arkscope.settings.collapsedGroups.v1")).toBe('["ai_models"]');
  });

  it("restores_remembered_collapse_while_first_use_stays_expanded", async () => {
    await renderSettings();
    expect(host!.querySelectorAll("[data-settings-anchor]")).toHaveLength(9);

    dispose();
    window.localStorage.setItem("arkscope.settings.collapsedGroups.v1", '["data_sync"]');
    await renderSettings();
    expect(host!.querySelector('[data-settings-anchor="investor_profile"]')).not.toBeNull();
    expect(host!.querySelector('[data-settings-anchor="data_sources"]')).toBeNull();
  });

  it("searches_chinese_and_english_aliases_without_filtering_page_content", async () => {
    await renderSettings();

    await setSearch("FRED");
    const directory = host!.querySelector('nav[aria-label="設定目錄"]')!;
    expect(Array.from(directory.querySelectorAll("button")).map((node) => node.textContent?.trim()))
      .toContain("總體經濟與行事曆");
    expect(directory.textContent).not.toContain("Provider 登入與憑證");
    expect(host!.querySelectorAll("[data-settings-anchor]")).toHaveLength(9);

    await setSearch("OAuth");
    expect(directory.textContent).toContain("Provider 登入與憑證");
  });

  it("selecting_a_result_expands_scrolls_and_focuses_the_exact_anchor", async () => {
    window.localStorage.setItem("arkscope.settings.collapsedGroups.v1", '["data_sync"]');
    await renderSettings();
    await setSearch("FRED");

    await click(buttonWithText("總體經濟與行事曆", host!.querySelector('nav[aria-label="設定目錄"]')!));
    const anchor = host!.querySelector('[data-settings-anchor="macro_storage"]');
    expect(anchor).not.toBeNull();
    expect(document.activeElement).toBe(anchor);
    expect(scrollIntoView).toHaveBeenCalledWith({ block: "start" });
    expect(window.localStorage.getItem("arkscope.settings.collapsedGroups.v1")).toBe("[]");
  });

  it("enter_selects_the_first_deterministic_search_result", async () => {
    await renderSettings();
    const input = await setSearch("timeout");

    await act(async () => {
      input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    });
    await flush();
    expect(document.activeElement).toBe(host!.querySelector('[data-settings-anchor="fixed_task_runtime"]'));
  });

  it("shows_neutral_no_match_copy_without_a_disabled_control", async () => {
    await renderSettings();
    await setSearch("no-such-setting-value");
    const directory = host!.querySelector('nav[aria-label="設定目錄"]')!;

    expect(directory.textContent).toContain("找不到符合的設定");
    expect(directory.querySelector("button[disabled]")).toBeNull();
  });

  it("directory_selection_closes_the_narrow_drawer_and_restores_one_focus_path", async () => {
    await renderSettings({ narrow: true });
    await click(buttonWithText("設定目錄", host!));
    await setSearch("投資人");
    await click(buttonWithText("投資人設定", document.querySelector('[role="dialog"]')!));

    const anchor = host!.querySelector('[data-settings-anchor="investor_profile"]');
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    expect(document.activeElement).toBe(anchor);
    expect(document.querySelectorAll('input[aria-label="搜尋設定"]')).toHaveLength(0);
  });

  it("renders_no_empty_advanced_group_or_historical_disabled_section", async () => {
    await renderSettings();

    expect(host!.textContent).not.toMatch(/App and Advanced|App Records|Permissions/);
    expect(host!.querySelector('[data-settings-anchor="app_records"]')).toBeNull();
    expect(host!.querySelector('[data-settings-anchor="permissions"]')).toBeNull();
  });

  it("exposes_compact_accessible_group_toggles_with_aria_expanded", async () => {
    await renderSettings();
    const toggles = Array.from(host!.querySelectorAll<HTMLButtonElement>(".settings-workspace-group > header button"));

    expect(toggles.map((button) => [button.getAttribute("aria-label"), button.getAttribute("aria-expanded")]))
      .toEqual([
        ["收合 AI 與模型", "true"],
        ["收合 個人化", "true"],
        ["收合 資料與同步", "true"],
      ]);
    await click(toggles[1]);
    expect(toggles[1].getAttribute("aria-expanded")).toBe("false");
    expect(toggles[1].getAttribute("aria-label")).toBe("展開 個人化");
  });
});
