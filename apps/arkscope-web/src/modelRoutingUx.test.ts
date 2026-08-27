import { createInstance } from "i18next";
import { describe, expect, it } from "vitest";

import { initializeI18n } from "./i18n/resources";
import type { ModelCatalog, TaskRoute } from "./api";
import * as modelRoutingUx from "./modelRoutingUx";
import {
  blockedRouteSaves,
  isTaskTestSnapshotCurrent,
  officialModelPricingUrl,
  providerContexts,
  routesSemanticallyEqual,
  type DraftRouteValue,
  type ProviderContextMap,
  type TaskTestSnapshot,
} from "./modelRoutingUx";

describe("official model pricing links", () => {
  it("separates metered API pricing from subscription plan pricing", () => {
    expect(officialModelPricingUrl("openai", "api_key"))
      .toBe("https://developers.openai.com/api/docs/pricing");
    expect(officialModelPricingUrl("openai", "api_key_pool"))
      .toBe("https://developers.openai.com/api/docs/pricing");
    expect(officialModelPricingUrl("openai", "chatgpt_oauth"))
      .toBe("https://chatgpt.com/pricing/");
    expect(officialModelPricingUrl("anthropic", "api_key"))
      .toBe("https://platform.claude.com/docs/en/about-claude/pricing");
    expect(officialModelPricingUrl("anthropic", "claude_code_oauth"))
      .toBe("https://claude.com/pricing");
    expect(officialModelPricingUrl("anthropic", null)).toBeNull();
  });
});

describe("Models terminology", () => {
  it("keeps status, auth, thinking, and group copy in one canonical table", () => {
    expect(modelRoutingUx).not.toHaveProperty("MODEL_UX_LABELS");
    const instance = createInstance();
    initializeI18n(instance, "zh-Hant");
    const t = instance.getFixedT("zh-Hant", "common");
    expect([
      modelRoutingUx.modelGroupLabel("available", t),
      modelRoutingUx.modelReasonLabel("reauth_required", t),
      modelRoutingUx.modelAuthModeLabel("chatgpt_oauth", t),
      modelRoutingUx.modelThinkingModeLabel("adaptive_default_on", t),
    ]).toEqual([
      "可供此任務使用",
      "登入已失效，請重新登入",
      "ChatGPT 訂閱登入",
      "預設開啟 adaptive thinking",
    ]);
  });

  it("resolves every shared model group reason auth mode thinking mode and compatibility context in both locales", () => {
    type ModelRoutingPresenters = {
      modelGroupLabel: (id: string, t: ReturnType<ReturnType<typeof createInstance>["getFixedT"]>) => string;
      modelReasonLabel: (id: string, t: ReturnType<ReturnType<typeof createInstance>["getFixedT"]>) => string;
      modelAuthModeLabel: (id: string, t: ReturnType<ReturnType<typeof createInstance>["getFixedT"]>) => string;
      modelThinkingModeLabel: (id: string, t: ReturnType<ReturnType<typeof createInstance>["getFixedT"]>) => string;
      modelCompatibilityLabel: (id: string, t: ReturnType<ReturnType<typeof createInstance>["getFixedT"]>) => string;
    };
    const presenters = modelRoutingUx as typeof modelRoutingUx & Partial<ModelRoutingPresenters>;
    expect(presenters.modelGroupLabel).toBeTypeOf("function");
    expect(presenters.modelReasonLabel).toBeTypeOf("function");
    expect(presenters.modelAuthModeLabel).toBeTypeOf("function");
    expect(presenters.modelThinkingModeLabel).toBeTypeOf("function");
    expect(presenters.modelCompatibilityLabel).toBeTypeOf("function");
    if (
      !presenters.modelGroupLabel ||
      !presenters.modelReasonLabel ||
      !presenters.modelAuthModeLabel ||
      !presenters.modelThinkingModeLabel ||
      !presenters.modelCompatibilityLabel
    ) return;

    const expected = {
      "zh-Hant": {
        groups: ["可供此任務使用", "此登入可見", "進階／未驗證", "目前路由"],
        reasons: [
          "尚未設定此 provider 的登入",
          "此登入方式不支援這個任務",
          "此登入方式尚不支援實際測試",
          "缺少任務能力",
          "此登入的探索清單未顯示此模型",
          "自訂／未知模型，尚未驗證能力",
          "暫時無法讀取模型探索狀態",
          "provider 實際呼叫失敗",
          "登入已失效，請重新登入",
        ],
        authModes: ["API key", "API key pool", "ChatGPT 訂閱登入", "Claude 訂閱登入"],
        thinkingModes: [
          "無特殊 thinking 行為",
          "使用手動 thinking budget",
          "可選擇 adaptive thinking",
          "預設開啟 adaptive thinking",
          "固定開啟 adaptive thinking",
        ],
        compatibility: ["未驗證（舊 sidecar 相容模式）", "未驗證（舊 sidecar 相容模式）。"],
      },
      en: {
        groups: ["Available for this task", "Visible to this sign-in", "Advanced / unverified", "Current route"],
        reasons: [
          "No sign-in is configured for this provider",
          "This sign-in method does not support the task",
          "This sign-in method does not yet support live testing",
          "Task capability is missing",
          "This model does not appear in the discovery list for this sign-in",
          "Custom or unknown model; capabilities are unverified",
          "Model discovery status is temporarily unavailable",
          "The live provider call failed",
          "The sign-in has expired. Sign in again",
        ],
        authModes: ["API key", "API key pool", "ChatGPT subscription sign-in", "Claude subscription sign-in"],
        thinkingModes: [
          "No special thinking behavior",
          "Uses a manual thinking budget",
          "Adaptive thinking available",
          "Adaptive thinking on by default",
          "Adaptive thinking always on",
        ],
        compatibility: [
          "Unverified (legacy sidecar compatibility mode)",
          "Unverified (legacy sidecar compatibility mode).",
        ],
      },
    } as const;
    const groupIds = ["available", "visible_disabled", "advanced", "current"];
    const reasonIds = [
      "missing_active_credential",
      "task_auth_mode_unsupported",
      "task_test_unsupported",
      "task_capability_missing",
      "model_not_visible",
      "model_not_in_registry",
      "discovery_unavailable",
      "provider_call_failed",
      "reauth_required",
    ];
    const authModeIds = ["api_key", "api_key_pool", "chatgpt_oauth", "claude_code_oauth"];
    const thinkingModeIds = [
      "none",
      "manual_budget",
      "adaptive_opt_in",
      "adaptive_default_on",
      "adaptive_always_on",
    ];
    const compatibilityIds = ["decorated_suffix", "settings_notice"];

    for (const locale of ["zh-Hant", "en"] as const) {
      const instance = createInstance();
      initializeI18n(instance, locale);
      const t = instance.getFixedT(locale, "common");
      expect(groupIds.map((id) => presenters.modelGroupLabel!(id, t))).toEqual(expected[locale].groups);
      expect(reasonIds.map((id) => presenters.modelReasonLabel!(id, t))).toEqual(expected[locale].reasons);
      expect(authModeIds.map((id) => presenters.modelAuthModeLabel!(id, t))).toEqual(expected[locale].authModes);
      expect(thinkingModeIds.map((id) => presenters.modelThinkingModeLabel!(id, t))).toEqual(expected[locale].thinkingModes);
      expect(compatibilityIds.map((id) => presenters.modelCompatibilityLabel!(id, t)))
        .toEqual(expected[locale].compatibility);
    }
    expect(presenters.modelReasonLabel("future_reason", createInstance().t)).toBe("future_reason");
  });
});

const route = (provider: "openai" | "anthropic", model: string): TaskRoute => ({
  task: "ai_research",
  provider,
  model,
  effort: "low",
  source: "db",
  custom: false,
  warning: null,
});

const taskCatalog = {
  current_model_ids: [
    "gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol",
    "claude-fable-5", "claude-opus-5", "claude-sonnet-5",
  ],
  retired_model_ids: ["gpt-5.4-mini", "claude-opus-4-8"],
  effort_options: {
    openai: ["low", "medium", "high", "xhigh", "max"].map((id) => ({
      id, provider: "openai" as const, label: id, description: id, applies_to_card_tasks: true,
    })),
    anthropic: ["low", "medium", "high", "xhigh", "max"].map((id) => ({
      id, provider: "anthropic" as const, label: id, description: id, applies_to_card_tasks: true,
    })),
  },
  models: [
    ...["gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol"].map((id) => ({
      id, provider: "openai" as const, effort_options: ["low", "medium", "high", "xhigh", "max"],
    })),
    ...["claude-fable-5", "claude-opus-5", "claude-sonnet-5"].map((id) => ({
      id, provider: "anthropic" as const, effort_options: ["low", "medium", "high", "xhigh", "max"],
    })),
  ],
} as unknown as ModelCatalog;

const credential = (provider: "openai" | "anthropic", id: string, active = true) => ({
  id,
  provider,
  auth_type: provider === "openai" ? "chatgpt_oauth" as const : "api_key" as const,
  label: `${provider} primary`,
  account_label: null,
  expires_at: null,
  source: "profile_state.db",
  available: true,
  masked: null,
  active,
  editable: true,
  can_discover_models: true,
  can_test_models: provider === "anthropic",
  notes: "",
});

describe("providerContexts", () => {
  it("uses the v2 provider summary as authority", () => {
    const contexts = providerContexts(
      {
        openai: { credential_id: "local:7", auth_mode: "chatgpt_oauth", label: "ChatGPT Plus" },
        anthropic: null,
      },
      { openai: [credential("openai", "local:9")], anthropic: [credential("anthropic", "local:4")] },
    );
    expect(contexts.openai).toEqual({
      credential_id: "local:7", auth_mode: "chatgpt_oauth", label: "ChatGPT Plus",
    });
    expect(contexts.anthropic).toBeNull();
  });

  it("falls back to the active credential on an old sidecar", () => {
    const contexts = providerContexts(undefined, {
      openai: [credential("openai", "local:7", false), credential("openai", "local:8")],
      anthropic: [],
    });
    expect(contexts.openai).toEqual({
      credential_id: "local:8", auth_mode: "chatgpt_oauth", label: "openai primary",
    });
    expect(contexts.anthropic).toBeNull();
  });
});

describe("blockedRouteSaves", () => {
  const baseline = {
    ai_research: route("anthropic", "claude-sonnet-5"),
  } as ModelCatalog["routes"];
  const contexts = {
    openai: { credential_id: "local:7", auth_mode: "chatgpt_oauth", label: "ChatGPT" },
    anthropic: null,
  } satisfies ProviderContextMap;

  it("does not block a pre-existing missing-credential route", () => {
    const draft = {
      ai_research: { provider: "anthropic", model: "claude-sonnet-5", effort: "low", custom: false },
    } satisfies Partial<Record<string, DraftRouteValue>>;
    expect(blockedRouteSaves(draft, baseline, contexts, taskCatalog)).toEqual([]);
  });

  it("blocks only a task freshly drafted onto that provider", () => {
    const draft = {
      ai_research: { provider: "anthropic", model: "claude-opus-5", effort: "low", custom: false },
    } satisfies Partial<Record<string, DraftRouteValue>>;
    expect(blockedRouteSaves(draft, baseline, contexts, taskCatalog)).toEqual([
      { task: "ai_research", reason: "missing_active_credential" },
    ]);
  });

  it("compares semantic fields, not object identity", () => {
    expect(routesSemanticallyEqual(
      { provider: "openai", model: "gpt-5.6-luna", effort: "low" },
      { ...route("openai", "gpt-5.6-luna"), effort: "low" },
    )).toBe(true);
  });

  it("blocks unchanged incomplete and retired rows before semantic equality", () => {
    const currentContexts = {
      openai: { credential_id: "local:7", auth_mode: "chatgpt_oauth", label: "ChatGPT" },
      anthropic: { credential_id: "local:4", auth_mode: "api_key", label: "Claude" },
    } satisfies ProviderContextMap;
    for (const effort of ["default", "none", ""] as const) {
      const legacy = { provider: "openai" as const, model: "gpt-5.6-luna", effort, custom: false };
      expect(blockedRouteSaves({ ai_research: legacy }, { ai_research: { ...route("openai", "gpt-5.6-luna"), effort } }, currentContexts, taskCatalog))
        .toEqual([{ task: "ai_research", reason: "effort_required" }]);
    }
    const retired = { provider: "openai" as const, model: "gpt-5.4-mini", effort: "low", custom: false };
    expect(blockedRouteSaves({ ai_research: retired }, { ai_research: { ...route("openai", "gpt-5.4-mini"), effort: "low" } }, currentContexts, taskCatalog))
      .toEqual([{ task: "ai_research", reason: "model_retired" }]);
    expect(routesSemanticallyEqual(
      { provider: "openai", model: "gpt-5.6-luna", effort: "" },
      { ...route("openai", "gpt-5.6-luna"), effort: "default" },
    )).toBe(false);
  });
});

describe("task test snapshots", () => {
  const snapshot: TaskTestSnapshot = {
    task: "ai_research",
    provider: "openai",
    model: "gpt-5.6-luna",
    effort: "low",
    credential_id: "local:7",
  };

  it("requires all five fields and never accepts an explicitly stale result", () => {
    expect(isTaskTestSnapshotCurrent(snapshot, {
      task: "ai_research",
      route: { provider: "openai", model: "gpt-5.6-luna", effort: "low", custom: false },
      credentialId: "local:7",
      stale: false,
    })).toBe(true);
    expect(isTaskTestSnapshotCurrent(snapshot, {
      task: "ai_research",
      route: { provider: "openai", model: "gpt-5.6-terra", effort: "low", custom: false },
      credentialId: "local:7",
      stale: false,
    })).toBe(false);
    expect(isTaskTestSnapshotCurrent(snapshot, {
      task: "ai_research",
      route: { provider: "openai", model: "gpt-5.6-luna", effort: "low", custom: false },
      credentialId: "local:7",
      stale: true,
    })).toBe(false);
  });
});
