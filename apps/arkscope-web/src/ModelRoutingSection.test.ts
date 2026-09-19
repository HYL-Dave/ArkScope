/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import i18n from "i18next";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ModelRoutingSection } from "./Settings";
import type {
  EffectiveProviderModelEntry,
  ModelCatalog,
  ModelOption,
  ModelReasonCode,
  ProviderCredential,
  TaskModelTestResult,
  TaskRoute,
} from "./api";

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

const CURRENT_MODEL_IDS = [
  "gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol",
  "claude-fable-5-1", "claude-opus-5", "claude-sonnet-5",
] as const;
const TASK_EFFORT_IDS = ["low", "medium", "high", "xhigh", "max"];
const MODELS: ModelOption[] = CURRENT_MODEL_IDS.map((id) => ({
  id,
  provider: id.startsWith("gpt-") ? "openai" : "anthropic",
  label: id,
  quality: "frontier",
  speed: "medium",
  cost_tier: "medium",
  supports_structured_output: true,
  supports_tool_calling: true,
  effort_options: TASK_EFFORT_IDS,
  recommended_for: [],
  source_url: "",
  verified_at: "",
  notes: "",
}));

const route = (over: Partial<TaskRoute>): TaskRoute => ({
  task: "ai_research", provider: "openai", model: "gpt-5.6-luna", effort: "low",
  source: "db", custom: false, warning: null, ...over,
});

// ai_research = DB authority (resettable); card_translation = yaml fallback (NOT resettable)
function catalog(): ModelCatalog {
  return {
    providers: ["anthropic", "openai"],
    tasks: [
      { id: "ai_research", label: "AI 研究", description: "", default_provider: "openai", recommended_model: "gpt-5.6-luna" },
      { id: "card_translation", label: "翻譯", description: "", default_provider: "anthropic", recommended_model: "claude-opus-5" },
    ],
    models: MODELS,
    effort_options: {
      openai: TASK_EFFORT_IDS.map((id) => ({ id, provider: "openai" as const, label: id, description: "", applies_to_card_tasks: true })),
      anthropic: TASK_EFFORT_IDS.map((id) => ({ id, provider: "anthropic" as const, label: id, description: "", applies_to_card_tasks: true })),
    },
    current_model_ids: [...CURRENT_MODEL_IDS],
    retired_model_ids: ["gpt-5.4-mini", "claude-opus-4-8"],
    routes: {
      ai_research: route({ task: "ai_research", source: "db" }),
      card_translation: route({ task: "card_translation", provider: "anthropic", model: "claude-opus-5", effort: "low", source: "profile" }),
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
  const modelsByProvider = {
    anthropic: MODELS.filter((model) => model.provider === "anthropic"),
    openai: MODELS.filter((model) => model.provider === "openai"),
  };
  act(() => {
    root!.render(React.createElement(ModelRoutingSection, {
      catalog: cat,
      draft: {
        ai_research: { provider: "openai", model: "gpt-5.6-luna", effort: "low", custom: false },
        card_translation: { provider: "anthropic", model: "claude-opus-5", effort: "low", custom: false },
        card_synthesis: { provider: "openai", model: "gpt-5.6-luna", effort: "low", custom: false },
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

function investigationCatalog(): ModelCatalog {
  const cat = catalog();
  cat.tasks.push({ id: "lifecycle_investigation", label: "DO NOT RENDER BACKEND LABEL",
    description: "", default_provider: "anthropic", recommended_model: "claude-sonnet-5", supports_custom_models: false });
  cat.routes.lifecycle_investigation = route({ task: "lifecycle_investigation",
    provider: "anthropic", model: "claude-sonnet-5", effort: "high" });
  cat.effective = {
    providers: { anthropic: { credential_id: "local:9", auth_mode: "claude_code_oauth", label: "Selected subscription" } },
    tasks: { lifecycle_investigation: {
      verified: [], advanced: [], cache_state: "seed_only", discovered_at: null,
      providers: { anthropic: { executable: true, reason_code: null, cache_state: "seed_only",
        discovered_at: null, models: [{ id: "claude-sonnet-5", label: "Claude Sonnet 5",
          status: "seed", eligible: true, reason_code: null, visible_to_credential: null,
          thinking_mode: "adaptive_default_on" }] } },
    } },
  };
  return cat;
}

describe("independent lifecycle investigation routing", () => {
  it.each([
    ["zh-Hant", "標的事件調查", "連線與格式測試"],
    ["en", "Lifecycle Investigation", "Test connection and format"],
  ])("has its own localized route and bounded test in %s", async (locale, label, testLabel) => {
    await i18n.changeLanguage(locale);
    const cat = investigationCatalog();
    const onTest = vi.fn(async () => {});
    const onDraft = vi.fn();
    const draft = {
      ai_research: { provider: "openai", model: "gpt-5.6-luna", effort: "low", custom: false },
      lifecycle_investigation: { provider: "anthropic", model: "claude-sonnet-5", effort: "high", custom: false },
    };
    render(vi.fn(), cat, onDraft, { draft, onTest });
    const card = host!.querySelector('[data-testid="route-lifecycle_investigation"]')!;
    expect(card.querySelector("h2")!.textContent).toBe(label);
    expect(card.textContent).not.toContain("DO NOT RENDER");
    expect(card.textContent).not.toContain("lifecycle_investigation");
    expect(card.querySelector(".model-custom-toggle")).toBeNull();
    expect(onTest).not.toHaveBeenCalled();
    const effort = labelledControl(card, "effort") as HTMLSelectElement;
    act(() => {
      effort.value = "max";
      effort.dispatchEvent(new Event("change", { bubbles: true }));
    });
    const update = onDraft.mock.calls[0][0](draft);
    expect(update.ai_research).toEqual(draft.ai_research);
    expect(update.lifecycle_investigation.effort).toBe("max");
    const test = Array.from(card.querySelectorAll("button")).find((button) => button.textContent === testLabel)!;
    expect(test).toBeDefined();
    expect(test.disabled).toBe(false);
    await act(async () => { test.click(); });
    expect(onTest).toHaveBeenCalledExactlyOnceWith("lifecycle_investigation");
  });

  it.each(["absent", "explicitly_rejected"])("does not promote an %s retained investigation model", (shape) => {
    const cat = investigationCatalog();
    const model = "claude-unknown-custom";
    cat.routes.lifecycle_investigation = route({ task: "lifecycle_investigation", provider: "anthropic",
      model, effort: "high", custom: true });
    if (shape === "explicitly_rejected") {
      cat.effective!.tasks.lifecycle_investigation!.providers!.anthropic!.models.push({
        id: model, label: model, status: "route", visible_to_credential: false,
        eligible: false, reason_code: "model_not_in_registry", thinking_mode: "none",
      });
    }
    const onTest = vi.fn();
    render(vi.fn(), cat, undefined, { onTest, draft: {
      lifecycle_investigation: { provider: "anthropic", model, effort: "high", custom: true },
    } });
    const card = host!.querySelector('[data-testid="route-lifecycle_investigation"]')!;
    const select = labelledControl(card, "model") as HTMLSelectElement;
    expect(select.value).toBe(model);
    expect(select.selectedOptions[0].disabled).toBe(true);
    expect(card.querySelector(".model-custom-toggle")).toBeNull();
    const test = Array.from(card.querySelectorAll("button")).find((button) => button.textContent === "連線與格式測試")!;
    expect(test.disabled).toBe(true);
    act(() => test.click());
    expect(onTest).not.toHaveBeenCalled();
  });

  it.each([
    ["zh-Hant", "連線與格式檢查通過"],
    ["en", "Connection and format check passed"],
  ])("does not call a schema check a full investigation success in %s", async (locale, label) => {
    await i18n.changeLanguage(locale);
    const cat = investigationCatalog();
    const snapshot = { task: "lifecycle_investigation", provider: "anthropic", model: "claude-sonnet-5",
      effort: "high", credential_id: "local:9" };
    render(vi.fn(), cat, undefined, {
      draft: { lifecycle_investigation: { ...snapshot, custom: false } },
      testState: { lifecycle_investigation: { loading: false, snapshot, stale: false,
        result: { ...snapshot, auth_mode: "claude_code_oauth", status: "ok", error_code: null,
          latency_ms: 12, tested_at: "2026-09-07T00:00:00Z", fallback_effort: null, warning: null } } },
    });
    expect(host!.querySelector('[data-testid="route-lifecycle_investigation"] .test-status strong')!.textContent).toBe(label);
  });
});

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
    reason: ModelReasonCode | null,
    thinking = "none",
    visible: boolean | null = true,
  ): EffectiveProviderModelEntry => ({
    id, label: id, status, visible_to_credential: visible, eligible,
    reason_code: reason, thinking_mode: thinking,
  });

  function catalogV2(): ModelCatalog {
    const cat = catalog();
    cat.tasks = [
      ...cat.tasks,
      { id: "card_synthesis", label: "卡片合成", description: "", default_provider: "anthropic", recommended_model: "claude-opus-5" },
    ];
    cat.credentials = {
      openai: [cred("openai", "local:7", "chatgpt_oauth", "ChatGPT subscription")],
      anthropic: [cred("anthropic", "local:4", "claude_code_oauth", "Claude subscription")],
    };
    cat.effort_options.openai = TASK_EFFORT_IDS
      .map((id) => ({
        id,
        provider: "openai",
        label: id,
        description: id,
        applies_to_card_tasks: true,
      }));
    const openai = {
      executable: true, reason_code: null, cache_state: "ok",
      discovered_at: "2026-07-10T06:00:00Z",
      models: [
        entry("gpt-5.6-luna", "visible", true, null),
        entry("gpt-5.6-terra", "visible", false, "task_capability_missing"),
        entry("gpt-5.6-sol", "advanced", true, null),
        entry("mystery-model", "route", true, "model_not_in_registry", "none", false),
      ],
    };
    const anthropic = {
      executable: true, reason_code: null, cache_state: "seed_only",
      discovered_at: null,
      models: [
        entry("claude-sonnet-5", "seed", true, null, "adaptive_default_on", null),
        entry("claude-opus-5", "advanced", true, null, "adaptive_opt_in", null),
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
        anthropic: { credential_id: "local:4", auth_mode: "claude_code_oauth", label: "Claude subscription" },
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

  function translationCard() {
    return host!.querySelector('[data-testid="route-card_translation"]')!;
  }

  function retiredSparkCatalog(planType: string, savedRoute = true): ModelCatalog {
    const cat = catalogV2();
    const sparkId = "gpt-5.3-codex-spark";
    cat.retired_model_ids = [...(cat.retired_model_ids ?? []), sparkId];
    cat.model_lifecycle = [
      ...(cat.model_lifecycle ?? []),
      { id: sparkId, provider: "openai", task_route_status: "retired", aliases: [] },
    ];
    cat.effective!.providers!.openai = {
      ...cat.effective!.providers!.openai!,
      plan_type: planType,
    };
    if (!savedRoute) return cat;
    const task = cat.effective!.tasks.card_translation!;
    const openai = task.providers!.openai!;
    cat.effective!.tasks.card_translation = {
      ...task,
      providers: {
        ...task.providers,
        openai: {
          ...openai,
          models: [
            ...openai.models,
            {
              ...entry(
                sparkId,
                "route",
                false,
                "model_retired",
                "none",
                true,
              ),
              effort_options: [],
            },
          ],
        },
      },
    };
    return cat;
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
          ai_research: { provider: "openai", model: "gpt-5.6-luna", effort: "low", custom: false },
        }));
      }
    }) as unknown as DraftDispatch;
    const invalidate = vi.fn();
    render(vi.fn(), catalogV2(), onDraft, { onInvalidateTest: invalidate });
    expectLocalizedControlName(researchCard(), "provider", "AI 研究 Provider");

    act(() => buttonByText(researchCard(), "Anthropic").click());
    const updated = drafts.at(-1) as Record<string, { provider: string; model: string; effort: string }>;
    expect(updated.ai_research).toMatchObject({ provider: "anthropic", model: "", effort: "low" });
    expect(invalidate).toHaveBeenCalledWith("ai_research");
  });

  it("retains a supported real effort across current-model changes", () => {
    const drafts: unknown[] = [];
    const onDraft = vi.fn((updater: unknown) => {
      if (typeof updater === "function") {
        drafts.push((updater as (p: Record<string, unknown>) => unknown)({
          ai_research: { provider: "openai", model: "gpt-5.6-luna", effort: "high", custom: false },
        }));
      }
    }) as unknown as DraftDispatch;
    render(vi.fn(), catalogV2(), onDraft, {
      draft: {
        ai_research: { provider: "openai", model: "gpt-5.6-luna", effort: "high", custom: false },
        card_translation: { provider: "anthropic", model: "claude-opus-5", effort: "low", custom: false },
        card_synthesis: { provider: "openai", model: "gpt-5.6-luna", effort: "low", custom: false },
      },
    });
    const model = labelledControl(researchCard(), "model") as HTMLSelectElement;
    const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value")?.set;
    act(() => {
      setter?.call(model, "gpt-5.6-sol");
      model.dispatchEvent(new Event("change", { bubbles: true }));
    });
    expect(drafts.at(-1)).toMatchObject({
      ai_research: { model: "gpt-5.6-sol", effort: "high" },
    });
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
      "可供此任務使用", "此登入可見", "其他模型", "目前路由",
    ]);
    const terra = Array.from(select.options).find((option) => option.value === "gpt-5.6-terra")!;
    expect(terra.disabled).toBe(true);
    expect(terra.textContent).toContain("缺少任務能力");
    expect(terra.getAttribute("title")).toBeNull();
    // Another model's rejection must not describe the selected, eligible Luna.
    expect(card.querySelector(".field > p.field-help")).toBeNull();
    expect(Array.from(select.options).find((option) => option.value === "gpt-5.6-sol")?.textContent)
      .toContain("進階");
    const translation = host!.querySelector('[data-testid="route-card_translation"]')!;
    const translationSelect = expectLocalizedControlName(
      translation,
      "model",
      "內容翻譯 Model",
    ) as HTMLSelectElement;
    expect(Array.from(translationSelect.options)
      .find((option) => option.value === "claude-sonnet-5")?.textContent)
      .not.toContain("未驗證");
    expect(Array.from(translationSelect.options)
      .find((option) => option.value === "claude-opus-5")?.textContent)
      .toContain("進階");
  });

  it.each(["pro", "prolite", "plus"])(
    "keeps an old Spark route blocked regardless of discovered visibility or plan %s",
    (plan) => {
      const cat = retiredSparkCatalog(plan);
      render(vi.fn(), cat, undefined, {
        draft: {
          ai_research: { provider: "openai", model: "gpt-5.6-luna", effort: "low", custom: false },
          card_translation: { provider: "openai", model: "gpt-5.3-codex-spark", effort: "low", custom: false },
          card_synthesis: { provider: "openai", model: "gpt-5.6-luna", effort: "low", custom: false },
        },
      });

      const translation = translationCard();
      const model = labelledControl(translation, "model") as HTMLSelectElement;
      const spark = Array.from(model.options)
        .find((option) => option.value === "gpt-5.3-codex-spark")!;
      expect(spark.disabled).toBe(true);
      expect(spark.textContent).toContain("此模型已退出新執行");
      expect(translation.textContent?.toLowerCase()).toContain(`方案：${plan}`);
      expect(translation.textContent)
        .not.toContain("已偵測到 Spark 額度");
      expect(translation.textContent).toContain("不可選：");
      expect(buttonByText(translation, "重新驗證列表")).toBeTruthy();
    },
  );

  it("does not offer Spark in any task without a saved historical route", () => {
    const cat = retiredSparkCatalog("prolite", false);
    render(vi.fn(), cat, undefined, {
      draft: {
        ai_research: { provider: "openai", model: "gpt-5.6-luna", effort: "low", custom: false },
        card_translation: { provider: "openai", model: "gpt-5.6-luna", effort: "high", custom: false },
        card_synthesis: { provider: "openai", model: "gpt-5.6-luna", effort: "low", custom: false },
      },
    });

    const translation = translationCard();
    const model = labelledControl(translation, "model") as HTMLSelectElement;
    expect(Array.from(model.options)
      .map((option) => option.value)).not.toContain("gpt-5.3-codex-spark");
    expect(translation.textContent).toContain("方案：prolite");
    expect(Array.from((labelledControl(researchCard(), "model") as HTMLSelectElement).options)
      .map((option) => option.value)).not.toContain("gpt-5.3-codex-spark");
    const synthesis = host!.querySelector('[data-testid="route-card_synthesis"]')!;
    expect(Array.from((labelledControl(synthesis, "model") as HTMLSelectElement).options)
      .map((option) => option.value)).not.toContain("gpt-5.3-codex-spark");
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
          ai_research: { provider: "openai", model: "gpt-5.6-luna", effort: "low", custom: false },
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
        ai_research: { provider: "openai", model: "gpt-5.6-luna", effort: "low", custom: true },
        card_translation: { provider: "anthropic", model: "claude-opus-5", effort: "low", custom: false },
        card_synthesis: { provider: "openai", model: "gpt-5.6-luna", effort: "low", custom: false },
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
        ai_research: { provider: "anthropic", model: "claude-custom", effort: "low", custom: true },
        card_translation: { provider: "anthropic", model: "claude-opus-5", effort: "low", custom: false },
        card_synthesis: { provider: "openai", model: "gpt-5.6-luna", effort: "low", custom: false },
      },
    });
    expect((researchCard().querySelector("input") as HTMLInputElement).placeholder).toBe("claude-…");
  });

  it("shows credential identity/state/time and disables a missing provider", () => {
    const cat = catalogV2();
    render(vi.fn(), cat);
    expect(researchCard().textContent).toContain("ChatGPT Plus");
    expect(researchCard().textContent).toContain("已取得可見模型清單");
    expect(researchCard().textContent).toContain("上次列出模型");
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
    const cat = catalogV2();
    for (const task of Object.values(cat.effective!.tasks)) {
      task!.providers!.anthropic!.discovered_at = "2026-09-03T01:02:03Z";
    }
    render(vi.fn(), cat, undefined, {
      draft: {
        ai_research: { provider: "anthropic", model: "claude-sonnet-5", effort: "low", custom: false },
        card_translation: { provider: "anthropic", model: "claude-opus-5", effort: "low", custom: false },
        card_synthesis: { provider: "openai", model: "gpt-5.6-luna", effort: "low", custom: false },
      },
    });
    const card = researchCard();
    expect(card.textContent).toContain("Claude subscription");
    expect(card.textContent).toContain("此通道無法線上列出模型");
    const model = labelledControl(card, "model") as HTMLSelectElement;
    expect(Array.from(model.options)
      .find((option) => option.value === "claude-sonnet-5")?.textContent)
      .not.toContain("未驗證");
    expect(card.textContent).not.toContain("上次列出模型");
    expect(card.textContent).not.toContain("重新登入");
    expect(card.textContent).not.toContain("設為 active");
  });

  it("describes an API-key seed as absent from the last model list", () => {
    const cat = catalogV2();
    cat.effective!.providers!.anthropic = {
      ...cat.effective!.providers!.anthropic!,
      auth_mode: "api_key",
      label: "Claude API",
    };
    const block = cat.effective!.tasks.card_translation!.providers!.anthropic!;
    block.cache_state = "ok";
    block.discovered_at = "2026-07-25T00:00:00Z";
    block.models = [
      entry("claude-fable-5-1", "seed", true, null, "adaptive_always_on", null),
    ];
    render(vi.fn(), cat, undefined, {
      draft: {
        ai_research: { provider: "openai", model: "gpt-5.6-luna", effort: "low", custom: false },
        card_translation: { provider: "anthropic", model: "claude-fable-5-1", effort: "high", custom: false },
        card_synthesis: { provider: "openai", model: "gpt-5.6-luna", effort: "low", custom: false },
      },
    });

    const option = Array.from((labelledControl(translationCard(), "model") as HTMLSelectElement).options)
      .find((candidate) => candidate.value === "claude-fable-5-1")!;
    expect(option.disabled).toBe(false);
    expect(option.textContent).toContain("上次模型清單未包含");
    expect(option.textContent).not.toContain("未驗證");
  });

  it("states that Fable 5.1 OAuth is a controlled release policy", () => {
    const cat = catalogV2();
    const block = cat.effective!.tasks.card_translation!.providers!.anthropic!;
    block.models = [
      entry(
        "claude-fable-5-1",
        "seed",
        false,
        "model_auth_unverified",
        "adaptive_always_on",
        null,
      ),
    ];
    render(vi.fn(), cat, undefined, {
      draft: {
        ai_research: { provider: "openai", model: "gpt-5.6-luna", effort: "low", custom: false },
        card_translation: { provider: "anthropic", model: "claude-fable-5-1", effort: "high", custom: false },
        card_synthesis: { provider: "openai", model: "gpt-5.6-luna", effort: "low", custom: false },
      },
    });

    const option = Array.from((labelledControl(translationCard(), "model") as HTMLSelectElement).options)
      .find((candidate) => candidate.value === "claude-fable-5-1")!;
    expect(option.disabled).toBe(true);
    expect(option.textContent).toContain("Claude OAuth 尚未開放");
    expect(translationCard().textContent).toContain("需經受控 live 驗證與版本更新");
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

  it("projects a legacy effort as empty, without default or none task options", () => {
    const cat = catalogV2();
    render(vi.fn(), cat, undefined, {
      draft: {
        ai_research: { provider: "openai", model: "gpt-5.6-luna", effort: "default", custom: false },
        card_translation: { provider: "anthropic", model: "claude-opus-5", effort: "low", custom: false },
        card_synthesis: { provider: "openai", model: "gpt-5.6-luna", effort: "low", custom: false },
      },
    });
    const effort = labelledControl(researchCard(), "effort") as HTMLSelectElement;
    expect(Array.from(effort.options).map((option) => option.value)).toEqual([
      "", "low", "medium", "high", "xhigh", "max",
    ]);
    expect(effort.value).toBe("");
    expect(researchCard().textContent).not.toContain("不送 effort；實際檔位由目前模型與後端決定。");
    expect(buttonByText(researchCard(), "實際測試").disabled).toBe(true);
  });

  it("retains a retired model as read-only provenance while excluding it from discovered choices", () => {
    const cat = catalogV2();
    cat.effective!.tasks.ai_research!.providers!.openai!.models.push(
      entry("gpt-5.4-mini", "visible", true, null),
    );
    render(vi.fn(), cat, undefined, {
      draft: {
        ai_research: { provider: "openai", model: "gpt-5.4-mini", effort: "low", custom: false },
        card_translation: { provider: "anthropic", model: "claude-opus-5", effort: "low", custom: false },
        card_synthesis: { provider: "openai", model: "gpt-5.6-luna", effort: "low", custom: false },
      },
    });
    const model = labelledControl(researchCard(), "model") as HTMLSelectElement;
    expect(model.value).toBe("gpt-5.4-mini");
    expect(model.disabled).toBe(false);
    expect(model.selectedOptions[0].disabled).toBe(true);
    expect(researchCard().textContent).toContain("已淘汰");
    expect(buttonByText(researchCard(), "實際測試").disabled).toBe(true);

    disposeRender();
    render(vi.fn(), cat);
    const currentModelSelect = labelledControl(researchCard(), "model") as HTMLSelectElement;
    expect(Array.from(currentModelSelect.options).map((option) => option.value))
      .not.toContain("gpt-5.4-mini");
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

  it("does not promote a discovered unknown model into a task choice", () => {
    render(vi.fn(), catalogV2());
    const select = labelledControl(researchCard(), "model") as HTMLSelectElement;
    expect(Array.from(select.options).map((option) => option.value)).not.toContain("mystery-model");
  });

  it("marks a changed test snapshot stale and does not show the old result", () => {
    const result: TaskModelTestResult = {
      task: "ai_research", provider: "openai", model: "gpt-5.6-luna", effort: "low",
      auth_mode: "chatgpt_oauth", credential_id: "local:7", status: "ok",
      error_code: null, latency_ms: 12, tested_at: "2026-07-11T00:00:00Z",
      fallback_effort: null, warning: null,
    };
    render(vi.fn(), catalogV2(), undefined, {
      testState: {
        ai_research: {
          loading: false, result, stale: true,
          snapshot: { task: "ai_research", provider: "openai", model: "gpt-5.6-luna", effort: "low", credential_id: "local:7" },
        },
      },
    });
    expect(researchCard().querySelector(".test-status")).toBeNull();
    expect(researchCard().textContent).toContain("選擇已變更——重新測試");
    expect(researchCard().textContent).not.toContain("12 ms");
  });

  it("renders an actual-call success only for the current five-field snapshot", () => {
    const result: TaskModelTestResult = {
      task: "ai_research", provider: "openai", model: "gpt-5.6-luna", effort: "low",
      auth_mode: "chatgpt_oauth", credential_id: "local:7", status: "ok",
      error_code: null, latency_ms: 12, tested_at: "2026-07-11T00:00:00Z",
      fallback_effort: "high", warning: null,
    };
    render(vi.fn(), catalogV2(), undefined, {
      testState: {
        ai_research: {
          loading: false, result, stale: false,
          snapshot: { task: "ai_research", provider: "openai", model: "gpt-5.6-luna", effort: "low", credential_id: "local:7" },
        },
      },
    });
    expect(researchCard().textContent).toContain("實際測試通過");
    expect(researchCard().textContent).toContain("12 ms");
    expect(researchCard().textContent).toContain("使用的 fallback effort：high。");
  });

  it("maps a reauth result to the credential action without exposing mutation controls", () => {
    const result: TaskModelTestResult = {
      task: "ai_research", provider: "openai", model: "gpt-5.6-luna", effort: "low",
      auth_mode: "chatgpt_oauth", credential_id: "local:7", status: "error",
      error_code: "reauth_required", latency_ms: 8, tested_at: "2026-07-11T00:00:00Z",
      fallback_effort: null, warning: "token expired",
    };
    render(vi.fn(), catalogV2(), undefined, {
      testState: {
        ai_research: {
          loading: false, result, stale: false,
          snapshot: { task: "ai_research", provider: "openai", model: "gpt-5.6-luna", effort: "low", credential_id: "local:7" },
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
    expect(host!.textContent).not.toContain("gpt-5.3-codex-spark");
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
        "Other models",
        "Current route",
      ]);
    expectLocalizedControlName(research, "provider", "AI Research Provider");
    expectLocalizedControlName(research, "model", "AI Research Model");
    const effort = expectLocalizedControlName(
      research,
      "effort",
      "AI Research Effort",
    ) as HTMLSelectElement;
    expect(research.querySelector(".field > p.field-help")).toBeNull();
    expect(Array.from(effort.options).map((option) => option.textContent)).toContain("low");
    expect(research.textContent).not.toContain("Low reasoning effort.");
    expect(research.textContent).toContain(
      "The environment currently controls this route. You can save a DB value, but runtime continues to follow the environment override.",
    );
    expect(research.textContent).toContain("Uses subscription quota, not API billing.");
    const translation = host!.querySelector('[data-testid="route-card_translation"]')!;
    expect(translation.textContent).toContain("Adaptive thinking available");
    const defaultRouteBadge = host!.querySelector(
      '[data-testid="route-card_synthesis"] .route-source',
    )!;
    expect(defaultRouteBadge.getAttribute("aria-label")).toBe(
      "Route authority Built-in default",
    );
    expect(defaultRouteBadge.getAttribute("title")).toBeNull();
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
    expect(model.value).toBe("gpt-5.6-luna");
    expect(effort.value).toBe("low");
    expect(research.textContent).toContain("Desk credential alias");
    expect(research.textContent).not.toContain("速度：fast");
    expect(research.textContent).not.toContain("成本級別：low");
    expect(research.textContent).toContain("驗證時間：SOURCE_VERIFIED_2026-07-10T06:00:00Z");
    expect(research.textContent).not.toContain("SOURCE MODEL NOTE: keep byte-identical");
    const pricingLink = research.querySelector<HTMLAnchorElement>(".model-pricing-link");
    expect(pricingLink?.textContent).toBe("查看官方價格");
    expect(pricingLink?.href).toBe("https://chatgpt.com/pricing/");
    expect(pricingLink?.target).toBe("_blank");
    expect(pricingLink?.rel).toContain("noreferrer");
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
    expect(model.value).toBe("gpt-5.6-luna");
    expect(effort.value).toBe("low");
    expect(buttonByText(translatedResearch, "OpenAI")).toBe(openai);
    expect(openai.getAttribute("aria-pressed")).toBe("true");
    expect(translatedResearch.textContent).toContain("Desk credential alias");
    expect(translatedResearch.textContent).toContain("gpt-5.6-luna");
    expect(translatedResearch.querySelector(".model-note")).toBe(modelNote);
    expect(modelNote.textContent).not.toBe(sourceContent);
    expect(modelNote.textContent).not.toContain("Speed: fast");
    expect(modelNote.textContent).not.toContain("Cost tier: low");
    expect(modelNote.textContent).toContain("Verified: SOURCE_VERIFIED_2026-07-10T06:00:00Z");
    expect(modelNote.textContent).not.toContain("SOURCE MODEL NOTE: keep byte-identical");
    expect(modelNote.textContent).toContain("Official pricing");
  });

  it("links API-key routes to the provider API pricing page", () => {
    const cat = catalogV2();
    cat.effective!.providers!.openai = {
      credential_id: "local:api",
      auth_mode: "api_key",
      label: "OpenAI API",
    };
    render(vi.fn(), cat);

    const pricingLink = researchCard().querySelector<HTMLAnchorElement>(".model-pricing-link");
    expect(pricingLink?.href).toBe("https://developers.openai.com/api/docs/pricing");
  });

  it("shows route and test diagnostics only in Developer Mode and never renders model notes", () => {
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
      model: "gpt-5.6-luna",
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
          model: "gpt-5.6-luna",
          effort: "low",
          credential_id: "local:7",
        },
      },
    };
    const modelsByProvider = { anthropic: [MODELS[1]], openai: [warnedModel] };

    render(vi.fn(), cat, undefined, { testState, modelsByProvider });
    expect(host!.textContent).not.toContain("PLANTED ROUTE WARNING");
    expect(host!.textContent).not.toContain("PLANTED MODEL NOTE");
    expect(host!.textContent).not.toContain("PLANTED TEST WARNING");

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
    expect(host!.textContent).not.toContain("PLANTED MODEL NOTE");
    expect(host!.textContent).toContain("PLANTED TEST WARNING");
    const diagnostics = Array.from(host!.querySelectorAll('[data-testid="developer-diagnostics"]'))
      .map((node) => node.textContent)
      .join("\n");
    expect(diagnostics).toContain("PLANTED ROUTE WARNING");
    expect(diagnostics).toContain("PLANTED TEST WARNING");
    expect(diagnostics).not.toContain("PLANTED MODEL NOTE");
  });
});
