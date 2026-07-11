/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ModelRoutingSection } from "./Settings";
import type { ModelCatalog, ModelOption, ProviderCredential, TaskRoute, TaskModelTestResult } from "./api";

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

afterEach(() => {
  if (root) {
    act(() => root!.unmount());
    root = null;
  }
  host?.remove();
  host = null;
});

const MODELS: ModelOption[] = [
  { id: "gpt-5.4-mini", provider: "openai", label: "GPT-5.4 mini", quality: "balanced", speed: "fast",
    cost_tier: "low", supports_structured_output: true, supports_tool_calling: true, recommended_for: [],
    source_url: "", verified_at: "", notes: "" },
  { id: "claude-opus-4-8", provider: "anthropic", label: "Claude Opus 4.8", quality: "frontier", speed: "slow",
    cost_tier: "high", supports_structured_output: true, supports_tool_calling: true, recommended_for: [],
    source_url: "", verified_at: "", notes: "" },
];

const route = (over: Partial<TaskRoute>): TaskRoute => ({
  task: "ai_research", provider: "openai", model: "gpt-5.4-mini", effort: "low",
  source: "db", custom: false, warning: null, ...over,
});

// ai_research = DB authority (resettable); card_translation = yaml fallback (NOT resettable)
function catalog(): ModelCatalog {
  return {
    providers: ["anthropic", "openai"],
    tasks: [
      { id: "ai_research", label: "AI 研究", description: "", default_provider: "openai", recommended_model: "gpt-5.4-mini" },
      { id: "card_translation", label: "翻譯", description: "", default_provider: "anthropic", recommended_model: "claude-opus-4-8" },
    ],
    models: MODELS,
    effort_options: {
      openai: [{ id: "low", provider: "openai", label: "Low", description: "", applies_to_card_tasks: true }],
      anthropic: [{ id: "default", provider: "anthropic", label: "Provider default", description: "", applies_to_card_tasks: true }],
    },
    routes: {
      ai_research: route({ task: "ai_research", source: "db" }),
      card_translation: route({ task: "card_translation", provider: "anthropic", model: "claude-opus-4-8", effort: "default", source: "profile" }),
      card_synthesis: route({ task: "card_synthesis", source: "default" }),
    },
    credentials: { anthropic: [], openai: [] },
    custom_allowed: true,
  };
}

type DraftDispatch = Parameters<typeof ModelRoutingSection>[0]["onDraft"];

function render(
  onReset = vi.fn(),
  catOverride?: ModelCatalog,
  onDraftOverride?: DraftDispatch,
  extra: Record<string, unknown> = {},
) {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  const cat = catOverride ?? catalog();
  const modelsByProvider = { anthropic: [MODELS[1]], openai: [MODELS[0]] };
  act(() => {
    root!.render(React.createElement(ModelRoutingSection, {
      catalog: cat,
      draft: {
        ai_research: { provider: "openai", model: "gpt-5.4-mini", effort: "low", custom: false },
        card_translation: { provider: "anthropic", model: "claude-opus-4-8", effort: "default", custom: false },
        card_synthesis: { provider: "openai", model: "gpt-5.4-mini", effort: "default", custom: false },
      },
      modelsByProvider,
      testState: {},
      onDraft: onDraftOverride ?? vi.fn(),
      onTest: vi.fn(),
      onReset,
      onDiscover: vi.fn(),
      onInvalidateTest: vi.fn(),
      ...extra,
    }));
  });
  return onReset;
}

function resetButtons(): HTMLButtonElement[] {
  return Array.from(host!.querySelectorAll("button")).filter(
    (b) => b.textContent?.trim() === "重設為 fallback") as HTMLButtonElement[];
}

describe("ModelRoutingSection reset affordance", () => {
  it("shows '重設為 fallback' ONLY for a DB-authoritative route", () => {
    render();
    // one DB route (ai_research) → exactly one reset button; the profile/default rows have none
    expect(resetButtons()).toHaveLength(1);
  });

  it("calls onReset with the task when the reset button is clicked", () => {
    const onReset = render();
    act(() => {
      resetButtons()[0].dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    });
    expect(onReset).toHaveBeenCalledWith("ai_research");
  });
});

describe("ModelRoutingSection provider-first UX", () => {
  const cred = (
    provider: "openai" | "anthropic",
    id: string,
    authType: ProviderCredential["auth_type"],
    label: string,
  ): ProviderCredential => ({
    id, provider, auth_type: authType, label, account_label: null, expires_at: null,
    source: "profile_state.db", available: true, masked: null, active: true,
    editable: true, can_discover_models: true, can_test_models: authType === "api_key", notes: "",
  });

  const entry = (
    id: string,
    status: "visible" | "advanced" | "route" | "seed",
    eligible: boolean,
    reason: string | null,
    thinking = "none",
    visible: boolean | null = true,
  ) => ({
    id, label: id, status, visible_to_credential: visible, eligible,
    reason_code: reason, thinking_mode: thinking,
  });

  function catalogV2(): ModelCatalog {
    const cat = catalog();
    cat.tasks = [
      ...cat.tasks,
      { id: "card_synthesis", label: "卡片合成", description: "", default_provider: "anthropic", recommended_model: "claude-opus-4-8" },
    ];
    cat.credentials = {
      openai: [cred("openai", "local:7", "chatgpt_oauth", "ChatGPT Plus")],
      anthropic: [cred("anthropic", "local:4", "api_key", "Claude API")],
    };
    cat.effort_options.openai = ["default", "none", "low", "medium", "high", "xhigh", "max"]
      .map((id) => ({
        id: id as "default" | "none" | "low" | "medium" | "high" | "xhigh" | "max",
        provider: "openai",
        label: id,
        description: id,
        applies_to_card_tasks: true,
      }));
    const openai = {
      executable: true, reason_code: null, cache_state: "ok",
      discovered_at: "2026-07-10T06:00:00Z",
      models: [
        entry("gpt-5.4-mini", "visible", true, null),
        entry("gpt-5.6-luna", "visible", false, "task_capability_missing"),
        entry("gpt-5.6-terra", "advanced", true, null),
        entry("mystery-model", "route", true, "model_not_in_registry", "none", false),
      ],
    };
    const anthropic = {
      executable: true, reason_code: null, cache_state: "seed_only",
      discovered_at: null,
      models: [
        entry("claude-sonnet-5", "seed", true, null, "adaptive_default_on", null),
        entry("claude-opus-4-8", "advanced", true, null, "adaptive_opt_in", null),
      ],
    };
    const taskBlock = (current: "openai" | "anthropic") => ({
      verified: [], advanced: [], cache_state: "ok", discovered_at: null,
      current_provider: current,
      providers: { openai, anthropic },
    });
    cat.effective = {
      providers: {
        openai: { credential_id: "local:7", auth_mode: "chatgpt_oauth", label: "ChatGPT Plus" },
        anthropic: { credential_id: "local:4", auth_mode: "api_key", label: "Claude API" },
      },
      tasks: {
        ai_research: taskBlock("openai"),
        card_synthesis: taskBlock("openai"),
        card_translation: taskBlock("anthropic"),
      },
    };
    return cat;
  }

  function researchCard() {
    return host!.querySelector('[data-testid="route-ai_research"]')!;
  }

  function buttonByText(parent: ParentNode, text: string): HTMLButtonElement {
    return Array.from(parent.querySelectorAll("button"))
      .find((button) => button.textContent?.trim() === text) as HTMLButtonElement;
  }

  it("shows provider controls directly and switching clears an incompatible model", () => {
    const drafts: unknown[] = [];
    const onDraft = vi.fn((updater: unknown) => {
      if (typeof updater === "function") {
        drafts.push((updater as (p: Record<string, unknown>) => unknown)({
          ai_research: { provider: "openai", model: "gpt-5.4-mini", effort: "low", custom: false },
        }));
      }
    }) as unknown as DraftDispatch;
    const invalidate = vi.fn();
    render(vi.fn(), catalogV2(), onDraft, { onInvalidateTest: invalidate });

    act(() => buttonByText(researchCard(), "Anthropic").click());
    const updated = drafts.at(-1) as Record<string, { provider: string; model: string; effort: string }>;
    expect(updated.ai_research).toMatchObject({ provider: "anthropic", model: "", effort: "default" });
    expect(invalidate).toHaveBeenCalledWith("ai_research");
  });

  it("renders one selector with four groups and disables ineligible entries with text reasons", () => {
    render(vi.fn(), catalogV2());
    const card = researchCard();
    const select = card.querySelector('[aria-label="模型 ai_research"]') as HTMLSelectElement;
    expect(Array.from(select.querySelectorAll("optgroup")).map((g) => g.label)).toEqual([
      "可供此任務使用", "此登入可見", "進階／未驗證", "目前路由",
    ]);
    const luna = Array.from(select.options).find((option) => option.value === "gpt-5.6-luna")!;
    expect(luna.disabled).toBe(true);
    expect(luna.textContent).toContain("缺少任務能力");
    expect(luna.getAttribute("title")).toBeNull();
    expect(card.textContent).toContain("缺少任務能力");
  });

  it("has no advanced checkbox, manual override details, or duplicate seed selector", () => {
    render(vi.fn(), catalogV2());
    const card = researchCard();
    expect(card.querySelector('[aria-label="顯示進階模型"]')).toBeNull();
    expect(card.querySelector("details")).toBeNull();
    expect(card.querySelectorAll('select[aria-label="模型 ai_research"]')).toHaveLength(1);
  });

  it("reveals a clearly marked custom id input", () => {
    const drafts: unknown[] = [];
    const onDraft = vi.fn((updater: unknown) => {
      if (typeof updater === "function") {
        drafts.push((updater as (p: Record<string, unknown>) => unknown)({
          ai_research: { provider: "openai", model: "gpt-5.4-mini", effort: "low", custom: false },
        }));
      }
    }) as unknown as DraftDispatch;
    render(vi.fn(), catalogV2(), onDraft);
    const card = researchCard();
    act(() => buttonByText(card, "輸入自訂 model id").click());
    const updated = drafts.at(-1) as Record<string, { custom: boolean }>;
    expect(updated.ai_research.custom).toBe(true);

    act(() => root!.unmount());
    root = null;
    host!.remove();
    host = null;
    render(vi.fn(), catalogV2(), undefined, {
      draft: {
        ai_research: { provider: "openai", model: "gpt-5.4-mini", effort: "low", custom: true },
        card_translation: { provider: "anthropic", model: "claude-opus-4-8", effort: "default", custom: false },
        card_synthesis: { provider: "openai", model: "gpt-5.4-mini", effort: "default", custom: false },
      },
    });
    expect(researchCard().querySelector('[aria-label="自訂 model id ai_research"]')).toBeTruthy();
    expect(researchCard().textContent).toContain("未驗證");
  });

  it("shows credential identity/state/time and disables a missing provider", () => {
    const cat = catalogV2();
    render(vi.fn(), cat);
    expect(researchCard().textContent).toContain("ChatGPT Plus");
    expect(researchCard().textContent).toContain("最後驗證可見");

    act(() => root!.unmount());
    root = null;
    host!.remove();
    host = null;
    cat.effective!.providers!.openai = null;
    render(vi.fn(), cat);
    const card = researchCard();
    expect(card.textContent).toContain("尚未設定此 provider 的登入");
    expect((card.querySelector('[aria-label="模型 ai_research"]') as HTMLSelectElement).disabled).toBe(true);
    expect(card.textContent).toContain("前往 Providers");
  });

  it("shows the selected Anthropic credential and its seed-only state", () => {
    render(vi.fn(), catalogV2(), undefined, {
      draft: {
        ai_research: { provider: "anthropic", model: "claude-sonnet-5", effort: "default", custom: false },
        card_translation: { provider: "anthropic", model: "claude-opus-4-8", effort: "default", custom: false },
        card_synthesis: { provider: "openai", model: "gpt-5.4-mini", effort: "default", custom: false },
      },
    });
    const card = researchCard();
    expect(card.textContent).toContain("Claude API");
    expect(card.textContent).toContain("此通道無法線上列出模型");
    expect(card.textContent).not.toContain("重新登入");
    expect(card.textContent).not.toContain("設為 active");
  });

  it("refreshes discovery for the selected provider credential", () => {
    const discover = vi.fn();
    render(vi.fn(), catalogV2(), undefined, { onDiscover: discover });
    act(() => buttonByText(researchCard(), "重新驗證列表").click());
    expect(discover).toHaveBeenCalledWith("openai", "local:7");
  });

  it("renders thinking behavior as read-only", () => {
    render(vi.fn(), catalogV2());
    const translation = host!.querySelector('[data-testid="route-card_translation"]')!;
    expect(translation.textContent).toContain("可選擇 adaptive thinking");
    expect(translation.querySelector('[aria-label="Thinking card_translation"]')).toBeNull();
  });

  it("shows only the selected model's supported effort values", () => {
    const cat = catalogV2();
    const research = cat.effective!.tasks.ai_research!.providers!.openai!;
    const mini = research.models.find((model) => model.id === "gpt-5.4-mini")!;
    const luna = research.models.find((model) => model.id === "gpt-5.6-luna")!;
    (mini as typeof mini & { effort_options: string[] }).effort_options = [
      "none", "low", "medium", "high", "xhigh",
    ];
    (luna as typeof luna & { effort_options: string[] }).effort_options = [
      "none", "low", "medium", "high", "xhigh", "max",
    ];

    render(vi.fn(), cat);
    const miniEffort = researchCard().querySelector('[aria-label="Effort ai_research"]') as HTMLSelectElement;
    expect(Array.from(miniEffort.options).map((option) => option.value)).toEqual([
      "default", "none", "low", "medium", "high", "xhigh",
    ]);

    act(() => root!.unmount());
    root = null;
    host!.remove();
    host = null;
    render(vi.fn(), cat, undefined, {
      draft: {
        ai_research: { provider: "openai", model: "gpt-5.6-luna", effort: "max", custom: false },
        card_translation: { provider: "anthropic", model: "claude-opus-4-8", effort: "default", custom: false },
        card_synthesis: { provider: "openai", model: "gpt-5.4-mini", effort: "default", custom: false },
      },
    });
    const lunaEffort = researchCard().querySelector('[aria-label="Effort ai_research"]') as HTMLSelectElement;
    expect(Array.from(lunaEffort.options).map((option) => option.value)).toEqual([
      "default", "none", "low", "medium", "high", "xhigh", "max",
    ]);
  });

  it("uses the task-scoped test and explains subscription billing", () => {
    const onTest = vi.fn();
    render(vi.fn(), catalogV2(), undefined, { onTest });
    const card = researchCard();
    expect(card.textContent).toContain("消耗訂閱額度，非 API 帳單");
    act(() => buttonByText(card, "實際測試").click());
    expect(onTest).toHaveBeenCalledWith("ai_research");
  });

  it("keeps route-pinned unknown models in the current route group", () => {
    render(vi.fn(), catalogV2());
    const select = researchCard().querySelector('[aria-label="模型 ai_research"]') as HTMLSelectElement;
    const routeGroup = Array.from(select.querySelectorAll("optgroup"))
      .find((group) => group.label === "目前路由")!;
    expect(routeGroup.textContent).toContain("mystery-model");
    expect((routeGroup.querySelector("option") as HTMLOptionElement).disabled).toBe(false);
  });

  it("marks a changed test snapshot stale and does not show the old result", () => {
    const result: TaskModelTestResult = {
      task: "ai_research", provider: "openai", model: "gpt-5.4-mini", effort: "low",
      auth_mode: "chatgpt_oauth", credential_id: "local:7", status: "ok",
      error_code: null, latency_ms: 12, tested_at: "2026-07-11T00:00:00Z",
      fallback_effort: null, warning: null,
    };
    render(vi.fn(), catalogV2(), undefined, {
      testState: {
        ai_research: {
          loading: false, result, stale: true,
          snapshot: { task: "ai_research", provider: "openai", model: "gpt-5.4-mini", effort: "low", credential_id: "local:7" },
        },
      },
    });
    expect(researchCard().textContent).toContain("選擇已變更——重新測試");
    expect(researchCard().textContent).not.toContain("12 ms");
  });

  it("renders an actual-call success only for the current five-field snapshot", () => {
    const result: TaskModelTestResult = {
      task: "ai_research", provider: "openai", model: "gpt-5.4-mini", effort: "low",
      auth_mode: "chatgpt_oauth", credential_id: "local:7", status: "ok",
      error_code: null, latency_ms: 12, tested_at: "2026-07-11T00:00:00Z",
      fallback_effort: null, warning: null,
    };
    render(vi.fn(), catalogV2(), undefined, {
      testState: {
        ai_research: {
          loading: false, result, stale: false,
          snapshot: { task: "ai_research", provider: "openai", model: "gpt-5.4-mini", effort: "low", credential_id: "local:7" },
        },
      },
    });
    expect(researchCard().textContent).toContain("可實際呼叫");
    expect(researchCard().textContent).toContain("12 ms");
  });

  it("maps a reauth result to the credential action without exposing mutation controls", () => {
    const result: TaskModelTestResult = {
      task: "ai_research", provider: "openai", model: "gpt-5.4-mini", effort: "low",
      auth_mode: "chatgpt_oauth", credential_id: "local:7", status: "error",
      error_code: "reauth_required", latency_ms: 8, tested_at: "2026-07-11T00:00:00Z",
      fallback_effort: null, warning: "token expired",
    };
    render(vi.fn(), catalogV2(), undefined, {
      testState: {
        ai_research: {
          loading: false, result, stale: false,
          snapshot: { task: "ai_research", provider: "openai", model: "gpt-5.4-mini", effort: "low", credential_id: "local:7" },
        },
      },
    });
    const card = researchCard();
    expect(card.textContent).toContain("登入已失效，請重新登入");
    expect(card.textContent).not.toContain("刪除 credential");
    expect(card.textContent).not.toContain("設為 active");
  });

  it("degrades honestly against an old sidecar without reviving hidden controls", () => {
    const cat = catalog();
    cat.credentials.openai = [cred("openai", "local:7", "api_key", "OpenAI API")];
    render(vi.fn(), cat);
    const card = researchCard();
    expect(buttonByText(card, "OpenAI")).toBeTruthy();
    expect(card.textContent).toContain("未驗證（舊 sidecar 相容模式）");
    expect(card.textContent).toContain("請重啟／更新 sidecar");
    expect((buttonByText(card, "實際測試")).disabled).toBe(true);
    expect(card.querySelector('[aria-label="顯示進階模型"]')).toBeNull();
    expect(card.querySelector("details")).toBeNull();
  });
});
