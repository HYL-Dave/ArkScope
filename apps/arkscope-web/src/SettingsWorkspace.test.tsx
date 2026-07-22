/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import i18n from "i18next";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ModelCatalog, ModelTask, TaskRoute } from "./api";
import type { SettingsNavigationRequest } from "./shell/navigation";
import type { SettingsNavigationGuardReporter } from "./settings/settingsNavigationGuard";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

const mocks = vi.hoisted(() => ({
  getModelCatalog: vi.fn(),
  saveModelRoutes: vi.fn(),
  importModelRoutes: vi.fn(),
  exportModelRoutes: vi.fn(),
  deleteModelRoute: vi.fn(),
  dataMounts: 0,
  dataUnmounts: 0,
  investorDeveloperModes: [] as boolean[],
  investorSummaryRequests: [] as number[],
  investorMounts: 0,
  investorUnmounts: 0,
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
  return {
    ...actual,
    getModelCatalog: mocks.getModelCatalog,
    saveModelRoutes: mocks.saveModelRoutes,
    importModelRoutes: mocks.importModelRoutes,
    exportModelRoutes: mocks.exportModelRoutes,
    deleteModelRoute: mocks.deleteModelRoute,
  };
});

vi.mock("./InvestorProfilePanel", async () => {
  const { useEffect, useState } = await import("react");
  return {
    InvestorProfilePanel: ({
      developerMode,
      onNavigationGuardChange,
      onNavigateToProviders,
      summaryRequestSequence,
    }: {
      developerMode?: boolean;
      onNavigationGuardChange?: SettingsNavigationGuardReporter;
      onNavigateToProviders?: () => void;
      summaryRequestSequence?: number;
    }) => {
      const [busy, setBusy] = useState(false);
      useEffect(() => {
        mocks.investorDeveloperModes.push(Boolean(developerMode));
      }, [developerMode]);
      useEffect(() => {
        mocks.investorSummaryRequests.push(summaryRequestSequence ?? 0);
      }, [summaryRequestSequence]);
      useEffect(() => {
        mocks.investorMounts += 1;
        return () => {
          mocks.investorUnmounts += 1;
        };
      }, []);
      useEffect(() => () => {
        onNavigationGuardChange?.({ dirty: false, busy: false, reason: null });
      }, [onNavigationGuardChange]);
      return (
        <div className="investor-profile-panel" aria-busy={busy}>
          <label>
            投資目標
            <input aria-label="投資目標" defaultValue="長期成長" />
          </label>
          <details>
            <summary>投資人草稿詳細資料</summary>
            <p>草稿內容</p>
          </details>
          <button
            type="button"
            onClick={() => onNavigationGuardChange?.({
              dirty: true,
              busy: false,
              reason: "投資人編輯有尚未儲存的設定。SOURCE_GUARD_SECRET",
            })}
          >標記投資人編輯草稿</button>
          <button
            type="button"
            onClick={() => {
              setBusy(true);
              onNavigationGuardChange?.({
                dirty: false,
                busy: true,
                reason: "請等待目前的投資人設定更新完成。",
              });
            }}
          >開始儲存投資人設定</button>
          <button
            type="button"
            onClick={() => onNavigationGuardChange?.({
              dirty: false,
              busy: false,
              reason: null,
            })}
          >開啟投資人校準</button>
          <button type="button" onClick={onNavigateToProviders}>設定 AI Provider</button>
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
  ModelRoutingSection: ({
    onReset,
  }: {
    onReset: (task: ModelTask) => Promise<void>;
  }) => (
    <div>
      <p>模型路由內容</p>
      <button type="button" onClick={() => void onReset("card_synthesis")}>
        重設卡片生成路由
      </button>
    </div>
  ),
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
  developerMode?: boolean;
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
        developerMode={options.developerMode ?? false}
        onRuntimeChanged={vi.fn(async () => undefined)}
        navigationRequest={options.navigationRequest}
      />,
    );
  });
  await flush();
}

async function rerenderSettings(navigationRequest: SettingsNavigationRequest) {
  await act(async () => {
    root!.render(
      <SettingsView
        runtime={null}
        developerMode={false}
        onRuntimeChanged={vi.fn(async () => undefined)}
        navigationRequest={navigationRequest}
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
  const input = document.querySelector('.settings-directory-search input[type="search"]');
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
  mocks.saveModelRoutes.mockReset();
  mocks.saveModelRoutes.mockResolvedValue(undefined);
  mocks.importModelRoutes.mockReset();
  mocks.importModelRoutes.mockResolvedValue({
    imported: ["card_synthesis", "ai_research"],
    skipped: ["card_translation"],
  });
  mocks.exportModelRoutes.mockReset();
  mocks.exportModelRoutes.mockResolvedValue({
    exported: ["card_synthesis", "card_translation"],
    cleared: ["ai_research"],
  });
  mocks.deleteModelRoute.mockReset();
  mocks.deleteModelRoute.mockResolvedValue(undefined);
  mocks.dataMounts = 0;
  mocks.dataUnmounts = 0;
  mocks.investorDeveloperModes.length = 0;
  mocks.investorSummaryRequests.length = 0;
  mocks.investorMounts = 0;
  mocks.investorUnmounts = 0;
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
  it("renders English Settings workspace tabs directory and section copy", async () => {
    await act(async () => { await i18n.changeLanguage("en"); });
    await renderSettings();

    expect(host!.querySelector("h1")?.textContent).toBe("Settings");
    expect(Array.from(host!.querySelectorAll('[role="tab"]')).map((tab) => tab.textContent)).toEqual([
      "AI and Models",
      "Personalization",
      "Data and Sync",
    ]);
    expect(host!.querySelector('[role="tablist"]')?.getAttribute("aria-label"))
      .toBe("Settings workflows");
    const directory = host!.querySelector('nav[aria-label="Settings Directory"]')!;
    expect(directory.textContent).toContain("AI and Models");
    expect(directory.textContent).toContain("Provider Sign-in and Credentials");
    expect(directory.querySelector('input[type="search"]')?.getAttribute("placeholder"))
      .toBe("Search titles, descriptions, or keywords...");

    const models = host!.querySelector('[data-settings-anchor="models"]')!;
    expect(buttonWithText("Save", models)).not.toBeNull();
    const transfer = models.querySelector("details")!;
    const transferActions = Array.from(transfer.querySelectorAll("button"));
    await click(buttonWithText("Save", models));
    expect.soft(host!.textContent).toContain(
      "Task routes saved to the profile DB (the profile file remains the fallback and import/export mirror).",
    );
    await click(transferActions[0]!);
    expect.soft(host!.textContent).toContain(
      "Imported task routes from the profile file into the profile DB. Imported: 2; skipped as incomplete or inconsistent: 1.",
    );
    await click(transferActions[1]!);
    expect.soft(host!.textContent).toContain(
      "Exported DB task routes to the profile file. Exported: 2; cleared as stale without DB authority: 1.",
    );
    await click(buttonWithText("重設卡片生成路由", models));
    expect.soft(host!.textContent).toContain(
      "AI Card Synthesis was reset to the profile file or built-in fallback.",
    );
    expect.soft(transfer.querySelector("summary")?.textContent)
      .toBe("Import from profile file / Export to profile file");
    expect.soft(transferActions.map((button) => button.textContent?.trim())).toEqual([
      "Import from profile file",
      "Export to profile file",
    ]);
  });

  it("switches locale without losing active group search disclosure draft or focus", async () => {
    await renderSettings();
    const transfer = host!.querySelector('[data-settings-anchor="models"] details')!;
    await click(transfer.querySelector("button")!);
    const routeResult = host!.querySelector(".ok-text")!;
    expect.soft(routeResult.textContent).toBe(
      "已從設定檔匯入任務路由到 profile DB。匯入：2；因不完整或不一致而略過：1。",
    );
    await click(tabWithText("個人化"));
    const search = await setSearch("risk appetite");
    const tab = tabWithText("個人化");
    const anchor = host!.querySelector('[data-settings-anchor="investor_profile"]')!;
    const disclosure = anchor.querySelector("details")!;
    const draft = anchor.querySelector<HTMLInputElement>('input[aria-label="投資目標"]')!;
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
    disclosure.open = true;
    await act(async () => {
      setter?.call(draft, "跨語言保留草稿");
      draft.dispatchEvent(new Event("input", { bubbles: true }));
      tab.focus();
    });
    const catalogCalls = mocks.getModelCatalog.mock.calls.length;

    await act(async () => { await i18n.changeLanguage("en"); });

    expect(host!.querySelector('[data-settings-anchor="investor_profile"]')).toBe(anchor);
    expect(anchor.querySelector("details")).toBe(disclosure);
    expect(disclosure.open).toBe(true);
    expect(anchor.querySelector('input[aria-label="投資目標"]')).toBe(draft);
    expect(draft.value).toBe("跨語言保留草稿");
    expect(document.querySelector('.settings-directory-search input[type="search"]')).toBe(search);
    expect(search.value).toBe("risk appetite");
    expect(tab.textContent).toBe("Personalization");
    expect(tab.getAttribute("aria-selected")).toBe("true");
    expect(document.activeElement).toBe(tab);
    expect(host!.querySelector("h1")?.textContent).toBe("Settings");
    expect(host!.querySelector(".ok-text")).toBe(routeResult);
    expect(routeResult.textContent).toBe(
      "Imported task routes from the profile file into the profile DB. Imported: 2; skipped as incomplete or inconsistent: 1.",
    );
    expect(mocks.getModelCatalog).toHaveBeenCalledTimes(catalogCalls);
  });

  it("searches Chinese and English aliases in either locale", async () => {
    await renderSettings();
    const directory = host!.querySelector('nav[aria-label="設定目錄"]')!;

    await setSearch("subscription credentials");
    expect(directory.textContent).toContain("Provider 登入與憑證");
    await setSearch("trading-day coverage");
    expect(directory.textContent).toContain("市場資料");

    await act(async () => { await i18n.changeLanguage("en"); });
    await setSearch("總體經濟");
    expect(directory.textContent).toContain("Macro Data");
    await setSearch("風險承受能力");
    expect(directory.textContent).toContain("Investor Profile");
  });

  it("keeps busy and dirty navigation guard semantics while labels change", async () => {
    await renderSettings();
    await click(buttonWithText("標記 Provider 草稿", host!));
    await click(tabWithText("資料與同步"));
    const dialog = document.querySelector('[role="dialog"]');
    expect(dialog).not.toBeNull();

    await act(async () => { await i18n.changeLanguage("en"); });
    expect(document.querySelector('[role="dialog"]')).toBe(dialog);
    expect(dialog?.textContent).toContain("Leave this settings section?");
    expect(dialog?.textContent).toContain("There are unsaved changes or work in progress.");
    expect(tabWithText("AI and Models").getAttribute("aria-selected")).toBe("true");
    await click(buttonWithText("Stay here", dialog!));
    expect(document.activeElement).toBe(tabWithText("AI and Models"));

    await click(buttonWithText("開始 Provider 授權", host!));
    await click(tabWithText("Data and Sync"));
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    expect(document.querySelector('[role="alert"]')?.textContent)
      .toContain("Leave this settings section?");
    expect(tabWithText("AI and Models").getAttribute("aria-selected")).toBe("true");
    expect(document.activeElement).toBe(tabWithText("AI and Models"));
  });

  it("renders no locale selector or raw planted diagnostic in Settings PageHeader", async () => {
    let rejectCatalog: ((reason: Error) => void) | null = null;
    mocks.getModelCatalog.mockImplementationOnce(() => new Promise((_, reject) => {
      rejectCatalog = reject;
    }));
    await act(async () => { await i18n.changeLanguage("en"); });
    await renderSettings({ developerMode: false });

    const pageHeader = host!.querySelector(".ui-page-header")!;
    expect(pageHeader.textContent).toContain("Settings");
    expect(pageHeader.querySelector("select, [role='combobox']")).toBeNull();
    expect(pageHeader.textContent).not.toMatch(/English|繁體中文|Language|語言/);
    expect(host!.textContent).toContain("Loading the model catalog...");

    await act(async () => {
      rejectCatalog?.(new Error("PLANTED_SETTINGS_RAW_DIAGNOSTIC"));
      await Promise.resolve();
    });
    await flush();
    expect(host!.textContent).toContain("Could not load AI model settings. Refresh the page, or check the connection under System / Health.");
    expect(host!.textContent).not.toContain("PLANTED_SETTINGS_RAW_DIAGNOSTIC");

    dispose();
    await renderSettings({ developerMode: true });
    await click(tabWithText("Personalization"));
    expect(mocks.investorDeveloperModes).toEqual([true]);
  });

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
    expect(document.querySelectorAll('input[aria-label="搜尋設定"]')).toHaveLength(0);
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

  it("signals same-group investor summary requests from search and external navigation", async () => {
    window.localStorage.setItem("arkscope.settings.activeGroup.v1", "personalization");
    await renderSettings();
    expect(mocks.investorSummaryRequests).toEqual([0]);
    expect(mocks.investorMounts).toBe(1);

    await setSearch("投資人");
    await click(buttonWithText("投資人設定", host!.querySelector('nav[aria-label="設定目錄"]')!));
    expect(mocks.investorSummaryRequests.at(-1)).toBe(1);
    expect(mocks.investorMounts).toBe(1);
    expect(mocks.investorUnmounts).toBe(0);

    await rerenderSettings({
      sequence: 91,
      target: { kind: "settings_section", section: "investor_profile" },
    });
    expect(mocks.investorSummaryRequests.at(-1)).toBe(2);
    expect(mocks.investorMounts).toBe(1);
    expect(mocks.investorUnmounts).toBe(0);
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
    expect(document.querySelector('[role="dialog"]')?.textContent).toContain("要離開這個設定區段嗎");
    expect(tabWithText("AI 與模型").getAttribute("aria-selected")).toBe("true");
    await click(buttonWithText("留在此處", document.querySelector('[role="dialog"]')!));
    expect(document.activeElement).toBe(tabWithText("AI 與模型"));

    await click(tabWithText("資料與同步"));
    await click(buttonWithText("捨棄變更並離開", document.querySelector('[role="dialog"]')!));
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

  it("investor profile guard uses the panel reporter for dirty edit and busy mutation", async () => {
    window.localStorage.setItem("arkscope.settings.activeGroup.v1", "personalization");
    await renderSettings();
    await click(buttonWithText("標記投資人編輯草稿", host!));

    await click(tabWithText("資料與同步"));
    expect(document.querySelector('[role="dialog"]')?.textContent).toContain("要離開這個設定區段嗎");
    expect(document.querySelector('[role="dialog"]')?.textContent).not.toContain("SOURCE_GUARD_SECRET");
    await click(buttonWithText("留在此處", document.querySelector('[role="dialog"]')!));

    await click(buttonWithText("開始儲存投資人設定", host!));
    await click(tabWithText("資料與同步"));
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    expect(document.querySelector('[role="alert"]')?.textContent)
      .toContain("請等待目前的投資人設定更新完成。");
    expect(tabWithText("個人化").getAttribute("aria-selected")).toBe("true");
  });

  it("calibration mode leaves Personalization without discard confirmation", async () => {
    window.localStorage.setItem("arkscope.settings.activeGroup.v1", "personalization");
    await renderSettings();
    await click(buttonWithText("開啟投資人校準", host!));

    await click(tabWithText("資料與同步"));

    expect(document.querySelector('[role="dialog"]')).toBeNull();
    expect(tabWithText("資料與同步").getAttribute("aria-selected")).toBe("true");
  });

  it("investor provider action reveals the Providers anchor and restores focus", async () => {
    window.localStorage.setItem("arkscope.settings.activeGroup.v1", "personalization");
    await renderSettings();

    await click(buttonWithText("設定 AI Provider", host!));

    expect(tabWithText("AI 與模型").getAttribute("aria-selected")).toBe("true");
    const providers = host!.querySelector<HTMLElement>('[data-settings-anchor="providers"]');
    expect(providers).not.toBeNull();
    expect(document.activeElement).toBe(providers);
    expect(scrollIntoView).toHaveBeenCalledTimes(1);
  });
});
