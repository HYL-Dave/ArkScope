/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import i18n from "i18next";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ModelRoutingSection } from "./Settings";
import type { ModelCatalog, ModelOption, ProviderCredential, TaskRoute, TaskModelTestResult } from "./api";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

beforeEach(async () => {
  await i18n.changeLanguage("zh-Hant");
});

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
      developerMode: false,
      ...extra,
    }));
  });
  return onReset;
}

function disposeRender() {
  act(() => root!.unmount());
  root = null;
  host!.remove();
  host = null;
}

function resetButtons(): HTMLButtonElement[] {
  return Array.from(host!.querySelectorAll("button")).filter(
    (b) => b.textContent?.trim() === "重設為 fallback") as HTMLButtonElement[];
}

type RouteFieldLabel = "provider" | "model" | "custom-model" | "effort";

function labelledControl(card: Element, field: RouteFieldLabel): HTMLElement {
  const testId = card.getAttribute("data-testid");
  if (!testId?.startsWith("route-")) throw new Error("missing route test id");
  const task = testId.slice("route-".length);
  const taskLabelId = `model-route-${task}-task-label`;
  const fieldLabelId = `model-route-${task}-${field}-label`;
  const control = card.querySelector(
    `[aria-labelledby="${taskLabelId} ${fieldLabelId}"]`,
  );
  if (!(control instanceof HTMLElement)) throw new Error(`missing labelled ${field} control`);
  return control;
}

function resolvedLabelledByText(element: Element): string {
  const labelledBy = element.getAttribute("aria-labelledby");
  if (!labelledBy) throw new Error("missing aria-labelledby");
  return labelledBy.split(/\s+/).map((id) => {
    const label = document.getElementById(id);
    if (!label) throw new Error(`missing label node ${id}`);
    return label.textContent?.trim() ?? "";
  }).join(" ");
}

function expectLocalizedControlName(
  card: Element,
  field: RouteFieldLabel,
  expected: string,
): HTMLElement {
  const control = labelledControl(card, field);
  const name = resolvedLabelledByText(control);
  expect(name).toBe(expected);
  expect(name).not.toMatch(/ai_research|card_synthesis|card_translation/);
  return control;
}

function expectNoKnownTaskId(value: string | null | undefined) {
  expect(value ?? "").not.toMatch(/ai_research|card_synthesis|card_translation/);
}

describe("ModelRoutingSection reset affordance", () => {
  it("shows '重設為 fallback' ONLY for a DB-authoritative route", async () => {
    render();
    // one DB route (ai_research) → exactly one reset button; the profile/default rows have none
    expect(resetButtons()).toHaveLength(1);
    const reset = resetButtons()[0];
    expect(reset.getAttribute("aria-label")).toBeNull();
    expect(reset.textContent?.trim()).toBe("重設為 fallback");
    expectNoKnownTaskId(reset.textContent);

    await act(async () => { await i18n.changeLanguage("en"); });
    expect(reset.textContent?.trim()).toBe("Reset to fallback");
    expect(reset.getAttribute("aria-label")).toBeNull();
    expectNoKnownTaskId(reset.textContent);
    await act(async () => { await i18n.changeLanguage("zh-Hant"); });

    disposeRender();
    const envCatalog = catalog();
    envCatalog.routes.ai_research = route({ source: "env" });
    render(vi.fn(), envCatalog);
    expect(resetButtons()).toHaveLength(0);
    expect(host!.textContent).toContain(
      "目前由環境變數控制；可以儲存到 DB，但 runtime 仍以 env 為準。",
    );
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
    expectLocalizedControlName(researchCard(), "provider", "AI 研究 Provider");

    act(() => buttonByText(researchCard(), "Anthropic").click());
    const updated = drafts.at(-1) as Record<string, { provider: string; model: string; effort: string }>;
    expect(updated.ai_research).toMatchObject({ provider: "anthropic", model: "", effort: "default" });
    expect(invalidate).toHaveBeenCalledWith("ai_research");
  });

  it("renders one selector with four groups and disables ineligible entries with text reasons", () => {
    render(vi.fn(), catalogV2());
    const card = researchCard();
    const select = expectLocalizedControlName(
      card,
      "model",
      "AI 研究 Model",
    ) as HTMLSelectElement;
    expectLocalizedControlName(card, "effort", "AI 研究 Effort");
    expect(Array.from(select.querySelectorAll("optgroup")).map((g) => g.label)).toEqual([
      "可供此任務使用", "此登入可見", "進階／未驗證", "目前路由",
    ]);
    const luna = Array.from(select.options).find((option) => option.value === "gpt-5.6-luna")!;
    expect(luna.disabled).toBe(true);
    expect(luna.textContent).toContain("缺少任務能力");
    expect(luna.getAttribute("title")).toBeNull();
    expect(card.textContent).toContain("不可選：缺少任務能力");
    const modelLimitHelp = card.querySelector("p.field-help")!;
    expect(modelLimitHelp.getAttribute("aria-label")).toBeNull();
    expect(modelLimitHelp.getAttribute("aria-labelledby")).toBeNull();
    expectNoKnownTaskId(modelLimitHelp.textContent);
    expect(Array.from(select.options).find((option) => option.value === "gpt-5.6-terra")?.textContent)
      .toContain("進階");
    const translation = host!.querySelector('[data-testid="route-card_translation"]')!;
    const translationSelect = expectLocalizedControlName(
      translation,
      "model",
      "卡片翻譯 Model",
    ) as HTMLSelectElement;
    expect(Array.from(translationSelect.options)
      .find((option) => option.value === "claude-sonnet-5")?.textContent)
      .toContain("未驗證");
    expect(Array.from(translationSelect.options)
      .find((option) => option.value === "claude-opus-4-8")?.textContent)
      .toContain("進階");
  });

  it("has no advanced checkbox, manual override details, or duplicate seed selector", () => {
    render(vi.fn(), catalogV2());
    const card = researchCard();
    expect(card.querySelector('[aria-label="顯示進階模型"]')).toBeNull();
    expect(card.querySelector("details")).toBeNull();
    expect(card.querySelectorAll('[aria-labelledby$="-model-label"]')).toHaveLength(1);
  });

  it("reveals a clearly marked custom id input", async () => {
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
    act(() => buttonByText(card, "使用自訂模型").click());
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
    const openAiCustom = researchCard();
    const customInput = expectLocalizedControlName(
      openAiCustom,
      "custom-model",
      "AI 研究 自訂 model ID",
    ) as HTMLInputElement;
    expect(customInput.placeholder).toBe("gpt-…");
    expect(openAiCustom.textContent).toContain(
      "這個 model id 不在 seed catalog；請用 Providers 的 discovery/test 確認此 credential 是否可用。",
    );
    expect(buttonByText(openAiCustom, "返回模型列表")).toBeTruthy();

    await act(async () => { await i18n.changeLanguage("en"); });
    expect(expectLocalizedControlName(
      openAiCustom,
      "custom-model",
      "AI Research Custom model ID",
    )).toBe(customInput);

    disposeRender();
    render(vi.fn(), catalogV2(), undefined, {
      draft: {
        ai_research: { provider: "anthropic", model: "claude-custom", effort: "default", custom: true },
        card_translation: { provider: "anthropic", model: "claude-opus-4-8", effort: "default", custom: false },
        card_synthesis: { provider: "openai", model: "gpt-5.4-mini", effort: "default", custom: false },
      },
    });
    expect((researchCard().querySelector("input") as HTMLInputElement).placeholder).toBe("claude-…");
  });

  it("shows credential identity/state/time and disables a missing provider", () => {
    const cat = catalogV2();
    render(vi.fn(), cat);
    expect(researchCard().textContent).toContain("ChatGPT Plus");
    expect(researchCard().textContent).toContain("已取得可見模型清單");
    expect(researchCard().textContent).toContain("驗證時間");
    expect(researchCard().textContent).not.toContain("測試時間");

    disposeRender();
    cat.effective!.tasks.ai_research!.providers!.openai!.cache_state = "never_discovered";
    cat.effective!.tasks.ai_research!.providers!.openai!.discovered_at = null;
    render(vi.fn(), cat);
    expect(researchCard().textContent).toContain("尚未探索此登入的模型");

    disposeRender();
    cat.effective!.tasks.ai_research!.providers!.openai!.cache_state = "temporary_failure";
    render(vi.fn(), cat);
    expect(researchCard().textContent).toContain("暫時無法讀取模型探索狀態");

    disposeRender();
    cat.effective!.providers!.openai = null;
    render(vi.fn(), cat);
    const card = researchCard();
    expect(card.textContent).toContain("尚未設定此 provider 的登入");
    expect((labelledControl(card, "model") as HTMLSelectElement).disabled).toBe(true);
    expect(card.textContent).toContain("前往 Provider 登入與憑證");
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

    render(vi.fn(), cat, undefined, {
      draft: {
        ai_research: { provider: "openai", model: "gpt-5.4-mini", effort: "max", custom: false },
        card_translation: { provider: "anthropic", model: "claude-opus-4-8", effort: "default", custom: false },
        card_synthesis: { provider: "openai", model: "gpt-5.4-mini", effort: "default", custom: false },
      },
    });
    const miniEffort = labelledControl(researchCard(), "effort") as HTMLSelectElement;
    expect(Array.from(miniEffort.options).map((option) => option.value)).toEqual([
      "default", "none", "low", "medium", "high", "xhigh",
    ]);
    expect(miniEffort.value).toBe("default");
    expect(researchCard().textContent).toContain(
      "不送 effort；實際檔位由目前模型與後端決定。",
    );

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
    const lunaEffort = labelledControl(researchCard(), "effort") as HTMLSelectElement;
    expect(Array.from(lunaEffort.options).map((option) => option.value)).toEqual([
      "default", "none", "low", "medium", "high", "xhigh", "max",
    ]);
  });

  it("uses the task-scoped test and explains subscription billing", () => {
    const onTest = vi.fn();
    render(vi.fn(), catalogV2(), undefined, { onTest });
    const card = researchCard();
    expect(card.textContent).toContain("ChatGPT 訂閱登入");
    expect(card.textContent).toContain("消耗訂閱額度，非 API 帳單");
    act(() => buttonByText(card, "實際測試").click());
    expect(onTest).toHaveBeenCalledWith("ai_research");
  });

  it("keeps route-pinned unknown models in the current route group", () => {
    render(vi.fn(), catalogV2());
    const select = labelledControl(researchCard(), "model") as HTMLSelectElement;
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
    expect(researchCard().querySelector(".test-status")).toBeNull();
    expect(researchCard().textContent).toContain("選擇已變更——重新測試");
    expect(researchCard().textContent).not.toContain("12 ms");
  });

  it("renders an actual-call success only for the current five-field snapshot", () => {
    const result: TaskModelTestResult = {
      task: "ai_research", provider: "openai", model: "gpt-5.4-mini", effort: "low",
      auth_mode: "chatgpt_oauth", credential_id: "local:7", status: "ok",
      error_code: null, latency_ms: 12, tested_at: "2026-07-11T00:00:00Z",
      fallback_effort: "high", warning: null,
    };
    render(vi.fn(), catalogV2(), undefined, {
      testState: {
        ai_research: {
          loading: false, result, stale: false,
          snapshot: { task: "ai_research", provider: "openai", model: "gpt-5.4-mini", effort: "low", credential_id: "local:7" },
        },
      },
    });
    expect(researchCard().textContent).toContain("實際測試通過");
    expect(researchCard().textContent).toContain("12 ms");
    expect(researchCard().textContent).toContain("使用的 fallback effort：高。");
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
    expect(card.textContent).toContain("請重啟／更新 sidecar 後再執行模型測試");
    expect((buttonByText(card, "實際測試")).disabled).toBe(true);
    expect(card.querySelector('[aria-label="顯示進階模型"]')).toBeNull();
    expect(card.querySelector("details")).toBeNull();
  });

  it("renders English task model effort and thinking copy from semantic ids", async () => {
    const cat = catalogV2();
    cat.routes.ai_research = route({ source: "env" });
    cat.tasks = cat.tasks.map((task) => ({
      ...task,
      label: `BACKEND TASK LABEL ${task.id}`,
      description: `BACKEND TASK DESCRIPTION ${task.id}`,
    }));
    cat.effort_options.openai = cat.effort_options.openai.map((effort) => ({
      ...effort,
      label: `BACKEND EFFORT LABEL ${effort.id}`,
      description: `BACKEND EFFORT DESCRIPTION ${effort.id}`,
    }));
    await act(async () => { await i18n.changeLanguage("en"); });

    render(vi.fn(), cat);

    const research = researchCard();
    expect(host!.textContent).toContain("Task Model Routing");
    expect(research.textContent).toContain("AI Research");
    expect(research.textContent).toContain("Run multi-step AI research work.");
    expect(Array.from(research.querySelectorAll("optgroup")).map((group) => group.label))
      .toEqual([
        "Available for this task",
        "Visible to this sign-in",
        "Advanced / unverified",
        "Current route",
      ]);
    expectLocalizedControlName(research, "provider", "AI Research Provider");
    expectLocalizedControlName(research, "model", "AI Research Model");
    const effort = expectLocalizedControlName(
      research,
      "effort",
      "AI Research Effort",
    ) as HTMLSelectElement;
    const modelLimitHelp = research.querySelector("p.field-help")!;
    expect(modelLimitHelp.getAttribute("aria-label")).toBeNull();
    expect(modelLimitHelp.getAttribute("aria-labelledby")).toBeNull();
    expectNoKnownTaskId(modelLimitHelp.textContent);
    expect(Array.from(effort.options).map((option) => option.textContent)).toContain("Low");
    expect(research.textContent).toContain("Low reasoning effort.");
    expect(research.textContent).toContain(
      "The environment currently controls this route. You can save a DB value, but runtime continues to follow the environment override.",
    );
    expect(research.textContent).toContain("Uses subscription quota, not API billing.");
    const translation = host!.querySelector('[data-testid="route-card_translation"]')!;
    expect(translation.textContent).toContain("Adaptive thinking available");
    expect(host!.textContent).not.toContain("BACKEND TASK");
    expect(host!.textContent).not.toContain("BACKEND EFFORT");
  });

  it("preserves model ids credential labels and selected values across locale change", async () => {
    const cat = catalogV2();
    cat.effective!.providers!.openai = {
      ...cat.effective!.providers!.openai!,
      label: "Desk credential alias",
    };
    const selectedModel = {
      ...MODELS[0],
      speed: "fast" as const,
      cost_tier: "low" as const,
      verified_at: "SOURCE_VERIFIED_2026-07-10T06:00:00Z",
      notes: "SOURCE MODEL NOTE: keep byte-identical",
    };
    render(vi.fn(), cat, undefined, {
      modelsByProvider: { anthropic: [MODELS[1]], openai: [selectedModel] },
    });
    const research = researchCard();
    const model = expectLocalizedControlName(
      research,
      "model",
      "AI 研究 Model",
    ) as HTMLSelectElement;
    const effort = expectLocalizedControlName(
      research,
      "effort",
      "AI 研究 Effort",
    ) as HTMLSelectElement;
    const openai = buttonByText(research, "OpenAI");
    expect(model.value).toBe("gpt-5.4-mini");
    expect(effort.value).toBe("low");
    expect(research.textContent).toContain("Desk credential alias");
    expect(research.textContent).toContain("速度：fast");
    expect(research.textContent).toContain("成本級別：low");
    expect(research.textContent).toContain("驗證時間：SOURCE_VERIFIED_2026-07-10T06:00:00Z");
    expect(research.textContent).toContain("SOURCE MODEL NOTE: keep byte-identical");
    const modelNote = research.querySelector(".model-note")!;
    const sourceContent = modelNote.textContent;

    await act(async () => { await i18n.changeLanguage("en"); });

    const translatedResearch = researchCard();
    expect(expectLocalizedControlName(
      translatedResearch,
      "model",
      "AI Research Model",
    )).toBe(model);
    expect(expectLocalizedControlName(
      translatedResearch,
      "effort",
      "AI Research Effort",
    )).toBe(effort);
    expect(model.value).toBe("gpt-5.4-mini");
    expect(effort.value).toBe("low");
    expect(buttonByText(translatedResearch, "OpenAI")).toBe(openai);
    expect(openai.getAttribute("aria-pressed")).toBe("true");
    expect(translatedResearch.textContent).toContain("Desk credential alias");
    expect(translatedResearch.textContent).toContain("gpt-5.4-mini");
    expect(translatedResearch.querySelector(".model-note")).toBe(modelNote);
    expect(modelNote.textContent).not.toBe(sourceContent);
    expect(modelNote.textContent).toContain("Speed: fast");
    expect(modelNote.textContent).toContain("Cost tier: low");
    expect(modelNote.textContent).toContain("Verified: SOURCE_VERIFIED_2026-07-10T06:00:00Z");
    expect(modelNote.textContent).toContain("SOURCE MODEL NOTE: keep byte-identical");
  });

  it("shows raw model warnings only in Developer Mode", () => {
    const cat = catalogV2();
    cat.routes.ai_research = {
      ...cat.routes.ai_research,
      warning: "PLANTED ROUTE WARNING",
    };
    const warnedModel = {
      ...MODELS[0],
      notes: "PLANTED MODEL NOTE",
    };
    const result: TaskModelTestResult = {
      task: "ai_research",
      provider: "openai",
      model: "gpt-5.4-mini",
      effort: "low",
      auth_mode: "chatgpt_oauth",
      credential_id: "local:7",
      status: "error",
      error_code: "provider_call_failed",
      latency_ms: null,
      tested_at: "2026-07-11T00:00:00Z",
      fallback_effort: null,
      warning: "PLANTED TEST WARNING",
    };
    const testState = {
      ai_research: {
        loading: false,
        result,
        stale: false,
        snapshot: {
          task: "ai_research",
          provider: "openai",
          model: "gpt-5.4-mini",
          effort: "low",
          credential_id: "local:7",
        },
      },
    };
    const modelsByProvider = { anthropic: [MODELS[1]], openai: [warnedModel] };

    render(vi.fn(), cat, undefined, { testState, modelsByProvider });
    expect(host!.textContent).not.toContain("PLANTED ROUTE WARNING");
    expect(host!.textContent).toContain("PLANTED MODEL NOTE");
    expect(host!.textContent).not.toContain("PLANTED TEST WARNING");
    expect(host!.querySelector(".model-note")?.textContent).toContain("PLANTED MODEL NOTE");

    act(() => root!.unmount());
    root = null;
    host!.remove();
    host = null;
    render(vi.fn(), cat, undefined, {
      developerMode: true,
      testState,
      modelsByProvider,
    });
    expect(host!.textContent).toContain("開發者診斷");
    expect(host!.textContent).toContain("PLANTED ROUTE WARNING");
    expect(host!.textContent).toContain("PLANTED MODEL NOTE");
    expect(host!.textContent).toContain("PLANTED TEST WARNING");
    const diagnostics = Array.from(host!.querySelectorAll(".developer-diagnostics"))
      .map((node) => node.textContent)
      .join("\n");
    expect(diagnostics).toContain("PLANTED ROUTE WARNING");
    expect(diagnostics).toContain("PLANTED TEST WARNING");
    expect(diagnostics).not.toContain("PLANTED MODEL NOTE");
  });
});
