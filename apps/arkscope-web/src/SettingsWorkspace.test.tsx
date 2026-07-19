/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ModelCatalog, ModelTask, TaskRoute } from "./api";
import type { SettingsNavigationRequest } from "./shell/navigation";
import type { SettingsNavigationGuardReporter } from "./settings/settingsNavigationGuard";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

const mocks = vi.hoisted(() => ({
  getModelCatalog: vi.fn(),
  dataMounts: 0,
  dataUnmounts: 0,
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

vi.mock("./InvestorProfilePanel", async () => {
  const { useState } = await import("react");
  return {
    InvestorProfilePanel: () => {
      const [busy, setBusy] = useState(false);
      return (
        <div className="investor-profile-panel" aria-busy={busy}>
          <label>
            投資目標
            <input aria-label="投資目標" defaultValue="長期成長" />
          </label>
          <button type="button" onClick={() => setBusy(true)}>開始儲存投資人設定</button>
        </div>
      );
    },
  };
});

vi.mock("./settings/DataSourcesSection", async () => {
  const { useEffect } = await import("react");
  return {
    DataSourcesSection: ({
      onNavigationGuardChange,
    }: {
      onNavigationGuardChange?: SettingsNavigationGuardReporter;
    }) => {
      useEffect(() => {
        mocks.dataMounts += 1;
        return () => {
          mocks.dataUnmounts += 1;
          onNavigationGuardChange?.({ dirty: false, busy: false, reason: null });
        };
      }, [onNavigationGuardChange]);
      return (
        <div>
          <button
            type="button"
            onClick={() => onNavigationGuardChange?.({
              dirty: true,
              busy: false,
              reason: "資料來源有尚未儲存的設定。",
            })}
          >標記資料草稿</button>
          <button
            type="button"
            onClick={() => onNavigationGuardChange?.({
              dirty: false,
              busy: true,
              reason: "資料來源設定正在儲存。",
            })}
          >開始資料變更</button>
        </div>
      );
    },
  };
});
vi.mock("./settings/DataStorageSection", () => ({
  DataStorageSection: () => <p>市場資料內容</p>,
}));
vi.mock("./settings/MacroStorageSection", () => ({
  MacroStorageSection: () => <p>總經資料內容</p>,
}));
vi.mock("./settings/NewsStorageSection", () => ({
  NewsStorageSection: () => <p>新聞資料內容</p>,
}));
vi.mock("./settings/ModelRoutingSection", () => ({
  ModelRoutingSection: () => <p>模型路由內容</p>,
  TASK_LABELS: {
    card_synthesis: "AI 卡片生成",
    card_translation: "卡片翻譯",
    ai_research: "AI 研究",
  },
}));
vi.mock("./settings/ProviderSection", () => ({
  ProviderSection: ({
    onNavigationGuardChange,
  }: {
    onNavigationGuardChange?: SettingsNavigationGuardReporter;
  }) => (
    <div>
      <button
        type="button"
        onClick={() => onNavigationGuardChange?.({
          dirty: true,
          busy: false,
          reason: "Provider 有尚未儲存的設定。",
        })}
      >標記 Provider 草稿</button>
      <button
        type="button"
        onClick={() => onNavigationGuardChange?.({
          dirty: false,
          busy: true,
          reason: "Provider 授權正在進行。",
        })}
      >開始 Provider 授權</button>
    </div>
  ),
  CredentialList: () => null,
  DiscoveryResultView: () => null,
  SetupDisclosure: () => null,
}));
vi.mock("./settings/RuntimeLimitSections", () => ({
  FixedTaskRuntimeSection: () => <p>固定任務內容</p>,
  ResearchRuntimeSection: () => <p>研究限制內容</p>,
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

function tabWithText(text: string): HTMLButtonElement {
  const tab = Array.from(host!.querySelectorAll<HTMLButtonElement>('[role="tab"]'))
    .find((candidate) => candidate.textContent?.trim() === text);
  if (!tab) throw new Error(`missing tab: ${text}`);
  return tab;
}

async function click(element: HTMLElement) {
  await act(async () => {
    element.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
  });
  await flush();
}

async function setSearch(value: string) {
  const input = document.querySelector('input[aria-label="搜尋所有設定"]');
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
  mocks.dataMounts = 0;
  mocks.dataUnmounts = 0;
  window.localStorage.clear();
  scrollIntoView.mockReset();
  Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
    configurable: true,
    value: scrollIntoView,
  });
});

afterEach(() => {
  dispose();
  document.body.replaceChildren();
  vi.restoreAllMocks();
});

describe("Settings workspace", () => {
  it("renders_page_header_tabs_and_only_default_group_anchors", async () => {
    await renderSettings();

    expect(host!.querySelector("h1")?.textContent).toBe("設定");
    expect(Array.from(host!.querySelectorAll('[role="tab"]')).map((tab) => tab.textContent)).toEqual([
      "AI 與模型",
      "個人化",
      "資料與同步",
    ]);
    expect(Array.from(host!.querySelectorAll("[data-settings-anchor]"))
      .map((anchor) => anchor.getAttribute("data-settings-anchor"))).toEqual([
        "providers",
        "models",
        "fixed_task_runtime",
        "research_runtime",
      ]);
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
    expect(host!.querySelectorAll('input[aria-label="搜尋所有設定"]')).toHaveLength(1);
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    expect(Array.from(host!.querySelectorAll("button")).some((node) => node.textContent === "設定目錄")).toBe(false);
  });

  it("renders_one_directory_trigger_and_transient_drawer_on_narrow_screens", async () => {
    await renderSettings({ narrow: true });

    expect(host!.querySelector('nav[aria-label="設定目錄"]')).toBeNull();
    const trigger = buttonWithText("設定目錄", host!);
    await click(trigger);
    expect(document.querySelectorAll('[role="dialog"][aria-modal="true"]')).toHaveLength(1);
    expect(document.querySelectorAll('input[aria-label="搜尋所有設定"]')).toHaveLength(1);
  });

  it("manual_tab_switch_unmounts_prior_group_and_targets_first_anchor", async () => {
    await renderSettings();

    await click(tabWithText("個人化"));
    expect(host!.querySelector('[data-settings-anchor="providers"]')).toBeNull();
    expect(host!.querySelector('[data-settings-anchor="investor_profile"]')).not.toBeNull();
    expect(window.localStorage.getItem("arkscope.settings.activeGroup.v1")).toBe("personalization");
    expect(buttonWithText("投資人設定", host!.querySelector('nav[aria-label="設定目錄"]')!)
      .getAttribute("aria-current")).toBe("location");
    expect(document.activeElement).toBe(tabWithText("個人化"));
  });

  it("restores_valid_active_group_and_ignores_retired_collapse_key", async () => {
    window.localStorage.setItem("arkscope.settings.activeGroup.v1", "data_sync");
    window.localStorage.setItem("arkscope.settings.collapsedGroups.v1", '["data_sync"]');
    await renderSettings();

    expect(tabWithText("資料與同步").getAttribute("aria-selected")).toBe("true");
    expect(host!.querySelector('[data-settings-anchor="data_sources"]')).not.toBeNull();
    expect(host!.querySelector('[data-settings-anchor="providers"]')).toBeNull();
  });

  it("searches_all_groups_while_empty_directory_stays_in_active_group", async () => {
    await renderSettings();
    const directory = host!.querySelector('nav[aria-label="設定目錄"]')!;

    expect(directory.textContent).toContain("Provider 登入與憑證");
    expect(directory.textContent).not.toContain("總經資料");
    await setSearch("FRED");
    expect(Array.from(directory.querySelectorAll("button")).map((node) => node.textContent?.trim()))
      .toEqual(["總經資料"]);
    expect(host!.querySelector('[data-settings-anchor="macro_storage"]')).toBeNull();

    await setSearch("OAuth");
    expect(directory.textContent).toContain("Provider 登入與憑證");
  });

  it("selecting_cross_group_result_mounts_group_then_focuses_exact_anchor", async () => {
    await renderSettings();
    await setSearch("FRED");

    await click(buttonWithText("總經資料", host!.querySelector('nav[aria-label="設定目錄"]')!));
    const anchor = host!.querySelector('[data-settings-anchor="macro_storage"]');
    expect(anchor).not.toBeNull();
    expect(document.activeElement).toBe(anchor);
    expect(scrollIntoView).toHaveBeenCalledWith({ block: "start" });
    expect(window.localStorage.getItem("arkscope.settings.activeGroup.v1")).toBe("data_sync");
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
    expect(document.querySelectorAll('input[aria-label="搜尋所有設定"]')).toHaveLength(0);
  });

  it("renders_no_empty_advanced_group_or_historical_disabled_section", async () => {
    await renderSettings();

    expect(host!.textContent).not.toMatch(/App and Advanced|App Records|Permissions/);
    expect(host!.querySelector('[data-settings-anchor="app_records"]')).toBeNull();
    expect(host!.querySelector('[data-settings-anchor="permissions"]')).toBeNull();
  });

  it("renders_three_workflow_tabs_with_one_selected_panel", async () => {
    await renderSettings();
    const tabs = Array.from(host!.querySelectorAll<HTMLButtonElement>('[role="tab"]'));

    expect(tabs.map((tab) => [tab.textContent, tab.getAttribute("aria-selected"), tab.tabIndex]))
      .toEqual([
        ["AI 與模型", "true", 0],
        ["個人化", "false", -1],
        ["資料與同步", "false", -1],
      ]);
    expect(host!.querySelectorAll('[role="tabpanel"]')).toHaveLength(1);
    expect(tabs[0].getAttribute("aria-controls")).toBe(host!.querySelector('[role="tabpanel"]')?.id);
  });

  it("manual_tab_change_clears_stale_pending_anchor", async () => {
    await renderSettings();
    await setSearch("FRED");
    await click(buttonWithText("總經資料", host!.querySelector('nav[aria-label="設定目錄"]')!));
    expect(scrollIntoView).toHaveBeenCalledTimes(1);

    await click(tabWithText("AI 與模型"));
    await click(tabWithText("資料與同步"));
    expect(document.activeElement).toBe(tabWithText("資料與同步"));
    expect(scrollIntoView).toHaveBeenCalledTimes(1);
  });

  it("navigation_target_overrides_persisted_active_group", async () => {
    window.localStorage.setItem("arkscope.settings.activeGroup.v1", "personalization");
    await renderSettings({
      navigationRequest: {
        sequence: 1,
        target: { kind: "settings_section", section: "data_storage" },
      },
    });

    expect(tabWithText("資料與同步").getAttribute("aria-selected")).toBe("true");
    expect(document.activeElement).toBe(host!.querySelector('[data-settings-anchor="data_storage"]'));
  });

  it("unmounts_data_sources_polling_when_leaving_data_sync", async () => {
    window.localStorage.setItem("arkscope.settings.activeGroup.v1", "data_sync");
    await renderSettings();
    expect(mocks.dataMounts).toBe(1);
    expect(mocks.dataUnmounts).toBe(0);

    await click(tabWithText("AI 與模型"));
    expect(mocks.dataUnmounts).toBe(1);
    expect(host!.querySelector('[data-settings-anchor="data_sources"]')).toBeNull();
  });

  it("dirty_section_requires_explicit_discard_before_group_change", async () => {
    await renderSettings();
    await click(buttonWithText("標記 Provider 草稿", host!));

    await click(tabWithText("資料與同步"));
    expect(document.querySelector('[role="dialog"]')?.textContent).toContain("捨棄未儲存的變更");
    expect(tabWithText("AI 與模型").getAttribute("aria-selected")).toBe("true");
    await click(buttonWithText("取消", document.querySelector('[role="dialog"]')!));
    expect(document.activeElement).toBe(tabWithText("AI 與模型"));

    await click(tabWithText("資料與同步"));
    await click(buttonWithText("捨棄並切換", document.querySelector('[role="dialog"]')!));
    expect(tabWithText("資料與同步").getAttribute("aria-selected")).toBe("true");
    expect(document.activeElement).toBe(tabWithText("資料與同步"));
  });

  it("busy_section_blocks_group_change_with_visible_reason", async () => {
    await renderSettings();
    await click(buttonWithText("開始 Provider 授權", host!));

    await click(tabWithText("資料與同步"));
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    expect(document.querySelector('[role="alert"]')?.textContent).toContain("Provider 授權正在進行。");
    expect(tabWithText("AI 與模型").getAttribute("aria-selected")).toBe("true");
    expect(document.activeElement).toBe(tabWithText("AI 與模型"));
  });

  it("investor_profile_guard_blocks_busy_and_confirms_potential_draft_without_modifying_panel", async () => {
    window.localStorage.setItem("arkscope.settings.activeGroup.v1", "personalization");
    await renderSettings();
    const input = host!.querySelector<HTMLInputElement>('input[aria-label="投資目標"]')!;
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
    await act(async () => {
      setter?.call(input, "保守成長");
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.dispatchEvent(new Event("change", { bubbles: true }));
    });

    await click(tabWithText("資料與同步"));
    expect(document.querySelector('[role="dialog"]')?.textContent).toContain("捨棄未儲存的變更");
    await click(buttonWithText("取消", document.querySelector('[role="dialog"]')!));

    await click(buttonWithText("開始儲存投資人設定", host!));
    await click(tabWithText("資料與同步"));
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    expect(document.querySelector('[role="alert"]')?.textContent).toContain("投資人設定正在儲存");
    expect(tabWithText("個人化").getAttribute("aria-selected")).toBe("true");
  });
});
