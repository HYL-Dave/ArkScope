/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  ModelCatalog,
  ModelDiscoveryResult,
  ModelTask,
  ProviderCredential,
  RuntimeConfig,
  TaskRoute,
} from "./api";
import type {
  EnabledSettingsSection,
  SettingsNavigationRequest,
} from "./shell/navigation";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

const controls = vi.hoisted(() => ({
  saveFixedTaskRuntime: vi.fn(async () => ({ fixed_task_runtime: {} })),
  discoverModels: vi.fn(),
  catalogPending: null as Promise<ModelCatalog> | null,
  catalogError: null as Error | null,
  catalogOverride: null as ModelCatalog | null,
}));

const taskRoute = (
  task: ModelTask,
  provider: "openai" | "anthropic",
  model: string,
): TaskRoute => ({
  task, provider, model, effort: "default", source: "db", custom: false, warning: null,
});

const providerBlock = (provider: "openai" | "anthropic", model: string) => ({
  executable: true,
  reason_code: null,
  cache_state: "ok",
  discovered_at: "2026-07-11T00:00:00Z",
  models: [{
    id: model,
    label: model,
    status: "visible" as const,
    visible_to_credential: true,
    eligible: true,
    reason_code: null,
    thinking_mode: "none",
  }],
});

const routes = {
  card_synthesis: taskRoute("card_synthesis", "openai", "gpt-5.4-mini"),
  card_translation: taskRoute("card_translation", "anthropic", "claude-sonnet-5"),
  ai_research: taskRoute("ai_research", "openai", "gpt-5.4-mini"),
};

const catalog: ModelCatalog = {
  providers: ["anthropic", "openai"],
  tasks: [
    { id: "card_synthesis", label: "生成", description: "", default_provider: "openai", recommended_model: "gpt-5.4-mini" },
    { id: "card_translation", label: "翻譯", description: "", default_provider: "anthropic", recommended_model: "claude-sonnet-5" },
    { id: "ai_research", label: "研究", description: "", default_provider: "openai", recommended_model: "gpt-5.4-mini" },
  ],
  models: [],
  effort_options: {
    openai: [{ id: "default", provider: "openai", label: "Default", description: "", applies_to_card_tasks: true }],
    anthropic: [{ id: "default", provider: "anthropic", label: "Default", description: "", applies_to_card_tasks: true }],
  },
  routes,
  credentials: { openai: [], anthropic: [] },
  custom_allowed: true,
  effective: {
    providers: {
      openai: { credential_id: "local:7", auth_mode: "api_key", label: "OpenAI API" },
      anthropic: null,
    },
    tasks: Object.fromEntries((Object.keys(routes) as ModelTask[]).map((task) => [task, {
      verified: [], advanced: [], cache_state: "ok", discovered_at: null,
      current_provider: routes[task].provider,
      providers: {
        openai: providerBlock("openai", "gpt-5.4-mini"),
        anthropic: providerBlock("anthropic", "claude-sonnet-5"),
      },
    }])) as ModelCatalog["effective"] extends { tasks: infer T } ? T : never,
  },
};

vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return {
    ...actual,
    getModelCatalog: vi.fn(async () => {
      if (controls.catalogPending) return controls.catalogPending;
      if (controls.catalogError) throw controls.catalogError;
      return controls.catalogOverride ?? catalog;
    }),
    discoverModels: controls.discoverModels,
    saveFixedTaskRuntime: controls.saveFixedTaskRuntime,
  };
});

import { SettingsView } from "./Settings";

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

beforeEach(() => {
  controls.catalogPending = null;
  controls.catalogError = null;
  controls.catalogOverride = null;
  controls.discoverModels.mockReset();
  window.localStorage.clear();
  Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
    configurable: true,
    value: vi.fn(),
  });
  Object.defineProperty(window, "requestAnimationFrame", {
    configurable: true,
    value: (callback: FrameRequestCallback) => {
      callback(0);
      return 1;
    },
  });
  Object.defineProperty(window, "cancelAnimationFrame", {
    configurable: true,
    value: vi.fn(),
  });
});

afterEach(() => {
  if (root) act(() => root!.unmount());
  root = null;
  host?.remove();
  host = null;
});

async function flush() {
  await act(async () => { await Promise.resolve(); });
}

function tabWithText(text: string): HTMLButtonElement {
  const tab = Array.from(host!.querySelectorAll<HTMLButtonElement>('[role="tab"]'))
    .find((candidate) => candidate.textContent?.trim() === text);
  if (!tab) throw new Error(`missing tab: ${text}`);
  return tab;
}

async function click(element: HTMLElement) {
  await act(async () => element.click());
  await flush();
}

describe("Settings model route save gate", () => {
  it("allows an unchanged missing route but blocks a new draft onto that provider", async () => {
    host = document.createElement("div");
    document.body.append(host);
    root = createRoot(host);
    await act(async () => {
      root!.render(React.createElement(SettingsView, { runtime: null, onRuntimeChanged: vi.fn() }));
    });
    await flush();

    const save = Array.from(host.querySelectorAll("button"))
      .find((button) => button.textContent?.trim() === "儲存路由") as HTMLButtonElement;
    expect(save.disabled).toBe(false);

    const research = host.querySelector('[data-testid="route-ai_research"]')!;
    const anthropic = Array.from(research.querySelectorAll("button"))
      .find((button) => button.textContent?.trim() === "Anthropic") as HTMLButtonElement;
    await act(async () => anthropic.click());
    await flush();

    expect(save.disabled).toBe(true);
    expect(host.textContent).toContain("本次變更尚未儲存");
  });

  it("wires the fixed-task panel to one atomic settings request", async () => {
    controls.saveFixedTaskRuntime.mockClear();
    const runtime = {
      anthropic: {
        model: "claude-sonnet-5",
        model_advanced: "claude-opus-4-8",
        effort: null,
        thinking: false,
        key_set: true,
        credentials: [],
      },
      openai: {
        model: "gpt-5.4-mini",
        model_advanced: "gpt-5.6-luna",
        reasoning_effort: "default",
        key_set: true,
        credentials: [],
      },
      card_synthesis: routes.card_synthesis,
      card_translation: routes.card_translation,
      ai_research: routes.ai_research,
      research_runtime: {
        max_tool_calls: 60,
        session_timeout_s: 900,
        per_tool_timeout_s: 45,
        source: "default",
        db_saved: false,
        warning: null,
      },
      fixed_task_runtime: {
        card_synthesis: {
          task: "card_synthesis",
          model_timeout_s: 900,
          source: "db",
          db_saved: true,
          warning: null,
        },
        card_translation: {
          task: "card_translation",
          model_timeout_s: 900,
          source: "db",
          db_saved: true,
          warning: null,
        },
      },
      data_keys: {},
    } satisfies RuntimeConfig;
    const onRuntimeChanged = vi.fn(async () => undefined);

    host = document.createElement("div");
    document.body.append(host);
    root = createRoot(host);
    await act(async () => {
      root!.render(React.createElement(SettingsView, { runtime, onRuntimeChanged }));
    });
    await flush();

    const synthesis = host.querySelector(
      'input[name="card_synthesis_model_timeout_s"]',
    ) as HTMLInputElement;
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
    await act(async () => {
      setter?.call(synthesis, "1200");
      synthesis.dispatchEvent(new Event("input", { bubbles: true }));
    });
    const save = Array.from(host.querySelectorAll("button"))
      .find((item) => item.textContent?.includes("儲存固定任務限制")) as HTMLButtonElement;
    await act(async () => save.click());
    await flush();

    expect(controls.saveFixedTaskRuntime).toHaveBeenCalledWith({
      tasks: {
        card_synthesis: { model_timeout_s: 1200 },
        card_translation: { model_timeout_s: 900 },
      },
    });
    expect(onRuntimeChanged).toHaveBeenCalledOnce();
  });

  it("opens an enabled section from a sequenced shell request", async () => {
    window.localStorage.setItem("arkscope.settings.activeGroup.v1", "personalization");
    window.localStorage.setItem("arkscope.settings.collapsedGroups.v1", '["data_sync"]');
    const dataSources = "data_sources" satisfies EnabledSettingsSection;
    const navigationRequest: SettingsNavigationRequest = {
      sequence: 1,
      target: { kind: "settings_section", section: dataSources },
    };
    host = document.createElement("div");
    document.body.append(host);
    root = createRoot(host);
    await act(async () => {
      root!.render(React.createElement(SettingsView, {
        runtime: null,
        onRuntimeChanged: vi.fn(),
        navigationRequest,
      }));
    });
    await flush();

    expect(document.activeElement).toBe(host.querySelector('[data-settings-anchor="data_sources"]'));
    expect(window.localStorage.getItem("arkscope.settings.activeGroup.v1")).toBe("data_sync");
  });

  it("reapplies the same section only when its request sequence advances", async () => {
    const models = "models" satisfies EnabledSettingsSection;
    const request = (sequence: number): SettingsNavigationRequest => ({
      sequence,
      target: { kind: "settings_section", section: models },
    });
    const render = async (navigationRequest: SettingsNavigationRequest) => {
      await act(async () => {
        root!.render(React.createElement(SettingsView, {
          runtime: null,
          onRuntimeChanged: vi.fn(),
          navigationRequest,
        }));
      });
      await flush();
    };

    host = document.createElement("div");
    document.body.append(host);
    root = createRoot(host);
    await render(request(1));
    const providers = Array.from(host.querySelectorAll("button"))
      .find((button) => button.textContent?.trim() === "Provider 登入與憑證") as HTMLButtonElement;
    await act(async () => providers.click());
    expect(document.activeElement).toBe(host.querySelector('[data-settings-anchor="providers"]'));

    await render(request(1));
    expect(document.activeElement).toBe(host.querySelector('[data-settings-anchor="providers"]'));

    await render(request(2));
    expect(document.activeElement).toBe(host.querySelector('[data-settings-anchor="models"]'));
  });

  it("catalog_loading_does_not_hide_personalization_or_data_groups", async () => {
    controls.catalogPending = new Promise<ModelCatalog>(() => undefined);
    host = document.createElement("div");
    document.body.append(host);
    root = createRoot(host);
    await act(async () => {
      root!.render(React.createElement(SettingsView, { runtime: null, onRuntimeChanged: vi.fn() }));
    });
    await flush();

    expect(host.querySelector('[data-settings-anchor="providers"]')?.textContent)
      .toContain("Loading model catalog");
    await click(tabWithText("個人化"));
    expect(host.querySelector('[data-settings-anchor="investor_profile"]')).not.toBeNull();
    await click(tabWithText("資料與同步"));
    expect(host.querySelector('[data-settings-anchor="data_sources"]')).not.toBeNull();
  });

  it("catalog_failure_stays_inside_ai_group_and_preserves_other_sections", async () => {
    controls.catalogError = new Error("private catalog transport detail");
    host = document.createElement("div");
    document.body.append(host);
    root = createRoot(host);
    await act(async () => {
      root!.render(React.createElement(SettingsView, { runtime: null, onRuntimeChanged: vi.fn() }));
    });
    await flush();

    const providers = host.querySelector('[data-settings-anchor="providers"]');
    expect(providers?.textContent).toContain("無法載入 AI 模型設定。請重新整理，或到 System / Health 檢查連線。");
    expect(host.textContent).not.toContain("private catalog transport detail");
    await click(tabWithText("個人化"));
    expect(host.querySelector('[data-settings-anchor="investor_profile"]')).not.toBeNull();
    await click(tabWithText("資料與同步"));
    expect(host.querySelector('[data-settings-anchor="macro_storage"]')).not.toBeNull();
  });

  it("owns_save_in_models_and_import_export_in_a_closed_advanced_disclosure", async () => {
    host = document.createElement("div");
    document.body.append(host);
    root = createRoot(host);
    await act(async () => {
      root!.render(React.createElement(SettingsView, { runtime: null, onRuntimeChanged: vi.fn() }));
    });
    await flush();

    const models = host.querySelector('[data-settings-anchor="models"]')!;
    expect(Array.from(models.querySelectorAll("button")).some((button) => button.textContent?.trim() === "儲存路由"))
      .toBe(true);
    const transfer = Array.from(models.querySelectorAll("details"))
      .find((details) => details.querySelector("summary")?.textContent === "匯入與匯出");
    expect(transfer?.open).toBe(false);
    expect(Array.from(transfer?.querySelectorAll("button") ?? []).map((button) => button.textContent?.trim()))
      .toEqual(["從設定檔匯入", "匯出到設定檔"]);
    expect(host.querySelector(".ui-page-header-actions")).toBeNull();
  });

  it("opens_fixed_task_runtime_from_a_sequenced_exact_target", async () => {
    const navigationRequest: SettingsNavigationRequest = {
      sequence: 1,
      target: { kind: "settings_section", section: "fixed_task_runtime" },
    };
    host = document.createElement("div");
    document.body.append(host);
    root = createRoot(host);
    await act(async () => {
      root!.render(React.createElement(SettingsView, {
        runtime: null,
        onRuntimeChanged: vi.fn(),
        navigationRequest,
      }));
    });
    await flush();

    expect(document.activeElement).toBe(host.querySelector('[data-settings-anchor="fixed_task_runtime"]'));
  });

  it("opens_research_runtime_only_when_the_request_sequence_advances", async () => {
    const request = (sequence: number): SettingsNavigationRequest => ({
      sequence,
      target: { kind: "settings_section", section: "research_runtime" },
    });
    const render = async (navigationRequest: SettingsNavigationRequest) => {
      await act(async () => {
        root!.render(React.createElement(SettingsView, {
          runtime: null,
          onRuntimeChanged: vi.fn(),
          navigationRequest,
        }));
      });
      await flush();
    };

    host = document.createElement("div");
    document.body.append(host);
    root = createRoot(host);
    await render(request(1));
    expect(document.activeElement).toBe(host.querySelector('[data-settings-anchor="research_runtime"]'));

    const providers = Array.from(host.querySelectorAll("button"))
      .find((button) => button.textContent?.trim() === "Provider 登入與憑證") as HTMLButtonElement;
    await act(async () => providers.click());
    expect(document.activeElement).toBe(host.querySelector('[data-settings-anchor="providers"]'));

    await render(request(1));
    expect(document.activeElement).toBe(host.querySelector('[data-settings-anchor="providers"]'));
    await render(request(2));
    expect(document.activeElement).toBe(host.querySelector('[data-settings-anchor="research_runtime"]'));
  });

  it("preserves_model_route_drafts_across_workflow_tab_unmounts", async () => {
    host = document.createElement("div");
    document.body.append(host);
    root = createRoot(host);
    await act(async () => {
      root!.render(React.createElement(SettingsView, { runtime: null, onRuntimeChanged: vi.fn() }));
    });
    await flush();

    const research = host.querySelector('[data-testid="route-ai_research"]')!;
    const anthropic = Array.from(research.querySelectorAll<HTMLButtonElement>("button"))
      .find((button) => button.textContent?.trim() === "Anthropic")!;
    await click(anthropic);
    expect(anthropic.getAttribute("aria-pressed")).toBe("true");

    await click(tabWithText("資料與同步"));
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    expect(host.querySelector('[data-testid="route-ai_research"]')).toBeNull();
    await click(tabWithText("AI 與模型"));

    const restored = host.querySelector('[data-testid="route-ai_research"]')!;
    const restoredAnthropic = Array.from(restored.querySelectorAll<HTMLButtonElement>("button"))
      .find((button) => button.textContent?.trim() === "Anthropic")!;
    expect(restoredAnthropic.getAttribute("aria-pressed")).toBe("true");
    expect(host.textContent).toContain("本次變更尚未儲存");
  });

  it("preserves_discovery_state_across_workflow_tab_unmounts", async () => {
    const credential: ProviderCredential = {
      id: "local:7",
      provider: "openai",
      auth_type: "api_key",
      label: "OpenAI API",
      account_label: null,
      expires_at: null,
      source: "profile_state.db",
      available: true,
      masked: "sk-a…AAAA",
      active: true,
      editable: true,
      can_discover_models: true,
      can_test_models: true,
      notes: "",
    };
    controls.catalogOverride = {
      ...catalog,
      credentials: { ...catalog.credentials, openai: [credential] },
    };
    const discovery: ModelDiscoveryResult = {
      provider: "openai",
      credential_id: credential.id,
      status: "ok",
      models: [{ id: "gpt-discovered", provider: "openai", label: "gpt-discovered", source: "provider_api" }],
      error: null,
      source_url: null,
    };
    controls.discoverModels.mockResolvedValue(discovery);

    host = document.createElement("div");
    document.body.append(host);
    root = createRoot(host);
    await act(async () => {
      root!.render(React.createElement(SettingsView, { runtime: null, onRuntimeChanged: vi.fn() }));
    });
    await flush();
    const discover = Array.from(host.querySelectorAll<HTMLButtonElement>("button"))
      .find((button) => button.textContent?.trim() === "列模型")!;
    await click(discover);
    expect(host.textContent).toContain("gpt-discovered");

    await click(tabWithText("資料與同步"));
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    await click(tabWithText("AI 與模型"));
    expect(host.textContent).toContain("gpt-discovered");
  });
});
