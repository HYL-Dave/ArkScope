import { describe, expect, it, vi } from "vitest";

import type { ModelCatalog, ModelProvider, TaskRoute } from "./api";
import {
  quotaKindForAuthMode,
  loadResearchThreadSelection,
  RESEARCH_SELECTION_STORAGE_KEY,
  readExplicitResearchSelection,
  resolveResearchSelection,
  writeExplicitResearchSelection,
  type ExplicitResearchTuple,
  type ResearchTuple,
} from "./researchSelection";

const route = (
  provider: ModelProvider = "openai",
  model = "gpt-5.6-luna",
  effort = "xhigh",
): TaskRoute => ({
  task: "ai_research",
  provider,
  model,
  effort,
  source: "db",
  custom: false,
  warning: null,
});

const model = (
  id: string,
  effortOptions: string[],
  over: Record<string, unknown> = {},
) => ({
  id,
  label: id,
  status: "visible" as const,
  visible_to_credential: true,
  eligible: true,
  reason_code: null,
  thinking_mode: "none",
  effort_options: effortOptions,
  ...over,
});

function catalog(): ModelCatalog {
  const routes = {
    ai_research: route(),
    card_synthesis: { ...route(), task: "card_synthesis" as const },
    card_translation: { ...route("anthropic", "claude-sonnet-5", "medium"), task: "card_translation" as const },
  };
  const openai = {
    executable: true,
    reason_code: null,
    cache_state: "ok" as const,
    discovered_at: "2026-07-18T00:00:00Z",
    models: [
      ...["gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol"].map((id) => model(id, ["low", "medium", "high", "xhigh", "max"])),
    ],
  };
  const anthropic = {
    executable: true,
    reason_code: null,
    cache_state: "seed_only" as const,
    discovered_at: null,
    models: ["claude-fable-5-1", "claude-opus-5", "claude-sonnet-5"].map((id) => model(id, ["low", "medium", "high", "xhigh", "max"])),
  };
  return {
    providers: ["openai", "anthropic"],
    tasks: [{
      id: "ai_research",
      label: "AI 研究",
      description: "",
      default_provider: "openai",
      recommended_model: "gpt-5.6-luna",
    }],
    current_model_ids: [
      "gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol",
      "claude-fable-5-1", "claude-opus-5", "claude-sonnet-5",
    ],
    retired_model_ids: ["gpt-5.4-mini", "claude-fable-5", "claude-opus-4-8"],
    model_lifecycle: [
      { id: "gpt-5.6-sol", provider: "openai", task_route_status: "current", aliases: ["gpt-5.6"] },
      { id: "gpt-5.6-terra", provider: "openai", task_route_status: "current", aliases: [] },
      { id: "gpt-5.6-luna", provider: "openai", task_route_status: "current", aliases: [] },
      { id: "gpt-5.4-mini", provider: "openai", task_route_status: "retired", aliases: [] },
      { id: "claude-fable-5-1", provider: "anthropic", task_route_status: "current", aliases: [] },
      { id: "claude-fable-5", provider: "anthropic", task_route_status: "retired", aliases: [] },
      { id: "claude-opus-5", provider: "anthropic", task_route_status: "current", aliases: [] },
      { id: "claude-sonnet-5", provider: "anthropic", task_route_status: "current", aliases: [] },
      { id: "claude-opus-4-8", provider: "anthropic", task_route_status: "retired", aliases: [] },
    ],
    models: [
      ...["gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol"].map((id) => ({
        id, provider: "openai" as const, effort_options: ["low", "medium", "high", "xhigh", "max"],
      })),
      ...["claude-fable-5-1", "claude-opus-5", "claude-sonnet-5"].map((id) => ({
        id, provider: "anthropic" as const, effort_options: ["low", "medium", "high", "xhigh", "max"],
      })),
    ] as unknown as ModelCatalog["models"],
    effort_options: {
      openai: ["low", "medium", "high", "xhigh", "max"].map((id) => ({
        id, provider: "openai" as const, label: id, description: "", applies_to_card_tasks: false,
      })),
      anthropic: ["low", "medium", "high", "xhigh", "max"].map((id) => ({
        id, provider: "anthropic" as const, label: id, description: "", applies_to_card_tasks: false,
      })),
    },
    routes,
    credentials: { openai: [], anthropic: [] },
    custom_allowed: true,
    effective: {
      providers: {
        openai: { credential_id: "local:7", auth_mode: "chatgpt_oauth", label: "ChatGPT Plus" },
        anthropic: { credential_id: "local:4", auth_mode: "api_key", label: "Claude API" },
      },
      tasks: {
        ai_research: {
          verified: [], advanced: [], cache_state: "ok", discovered_at: null,
          current_provider: "openai", providers: { openai, anthropic },
        },
      },
    },
  };
}

class MemoryStorage implements Pick<Storage, "getItem" | "setItem" | "removeItem"> {
  values = new Map<string, string>();
  getItem = vi.fn((key: string) => this.values.get(key) ?? null);
  setItem = vi.fn((key: string, value: string) => { this.values.set(key, value); });
  removeItem = vi.fn((key: string) => { this.values.delete(key); });
}

const threadTuple: ResearchTuple = {
  provider: "anthropic",
  model: "claude-sonnet-5",
  effort: "high",
};

function routeCatalog(tuple: ResearchTuple, cat = catalog()): ModelCatalog {
  cat.routes.ai_research = { ...route(), ...tuple, effort: tuple.effort ?? "" };
  return cat;
}

describe("research selection precedence and validation", () => {
  it("uses Settings for the next turn of an existing thread", () => {
    const storage = new MemoryStorage();
    writeExplicitResearchSelection({ provider: "openai", model: "gpt-5.6-luna", effort: "max" }, storage);
    expect(resolveResearchSelection({
      catalog: catalog(), hasActiveThread: true, threadSelection: threadTuple, preferenceStorage: storage,
    })).toMatchObject({ state: "ready", provenance: "settings", tuple: { provider: "openai", model: "gpt-5.6-luna", effort: "xhigh" } });
  });

  it("ignores stale global preferences for a new thread", () => {
    const storage = new MemoryStorage();
    const explicit: ExplicitResearchTuple = { provider: "openai", model: "gpt-5.6-luna", effort: "max" };
    writeExplicitResearchSelection(explicit, storage);
    expect(resolveResearchSelection({
      catalog: catalog(), hasActiveThread: false, threadSelection: null, preferenceStorage: storage,
    })).toMatchObject({ state: "ready", provenance: "settings", tuple: { provider: "openai", model: "gpt-5.6-luna", effort: "xhigh" } });
  });

  it("initializes from the configured Research task route", () => {
    expect(resolveResearchSelection({
      catalog: catalog(), hasActiveThread: false, threadSelection: null, preferenceStorage: new MemoryStorage(),
    })).toMatchObject({
      state: "ready",
      provenance: "settings",
      tuple: { provider: "openai", model: "gpt-5.6-luna", effort: "xhigh" },
    });
  });

  it.each([
    { provider: "openai" as const, model: "gpt-5.6-sol", effort: "low" },
    { provider: "anthropic" as const, model: "claude-sonnet-5", effort: "medium" },
  ])("uses $provider Settings even while historical selection is unavailable", tuple => {
    const cat = catalog();
    cat.routes.ai_research = { ...route(), ...tuple };
    expect(resolveResearchSelection({ catalog: cat, hasActiveThread: true, threadSelection: undefined }))
      .toMatchObject({ state: "ready", provenance: "settings", tuple });
  });

  it("keeps a current conversation override ahead of Settings and history", () => {
    const tuple = { provider: "openai" as const, model: "gpt-5.6-sol", effort: "low" as const };
    expect(resolveResearchSelection({ catalog: catalog(), hasActiveThread: true, threadSelection: threadTuple, userSelection: tuple }))
      .toMatchObject({ state: "ready", provenance: "user", tuple });
  });

  it("does not invent a tuple if Settings has no Research route", () => {
    const cat = catalog();
    delete (cat.routes as Partial<ModelCatalog["routes"]>).ai_research;
    expect(resolveResearchSelection({ catalog: cat, hasActiveThread: false, threadSelection: null }))
      .toMatchObject({ state: "needs_selection", tuple: null });
  });

  it("does not substitute Settings for a malformed explicit current-conversation choice", () => {
    expect(resolveResearchSelection({ catalog: catalog(), userSelection: { provider: "openai", model: "", effort: "low" } }))
      .toMatchObject({ state: "needs_selection", tuple: null });
  });

  it.each([
    { provider: "openai" as const, modelId: "gpt-5.3-codex-spark", auth: "chatgpt_oauth" as const, reason: "model_task_unsupported" },
    { provider: "openai" as const, modelId: "gpt-5.6-luna", auth: "chatgpt_oauth" as const, reason: "subscription_plan_required" },
    { provider: "anthropic" as const, modelId: "claude-fable-5-1", auth: "claude_code_oauth" as const, reason: "model_auth_unverified" },
  ])("retains the effective $reason gate for Settings and an explicit override", ({ provider, modelId, auth, reason }) => {
    const tuple = { provider, model: modelId, effort: "high" as const };
    const cat = routeCatalog(tuple);
    cat.effective!.providers![provider]!.auth_mode = auth;
    const block = cat.effective!.tasks.ai_research!.providers![provider]!;
    block.models = [model(modelId, ["high"], { eligible: false, reason_code: reason })];
    for (const userSelection of [null, tuple]) {
      expect(resolveResearchSelection({ catalog: cat, userSelection }))
        .toMatchObject({ state: "blocked", reasonCode: reason, authMode: auth, tuple });
    }
  });

  it("blocks an invalid Settings tuple without falling through", () => {
    const storage = new MemoryStorage();
    writeExplicitResearchSelection({ provider: "openai", model: "gpt-5.6-luna", effort: "low" }, storage);
    expect(resolveResearchSelection({
      catalog: routeCatalog({ ...threadTuple, model: "claude-removed" }),
      hasActiveThread: true,
      threadSelection: { ...threadTuple, model: "claude-removed" },
      preferenceStorage: storage,
    })).toMatchObject({ state: "blocked", provenance: "settings", reasonCode: "model_not_visible" });
  });

  it("blocks an invalid explicit tuple without falling through", () => {
    const storage = new MemoryStorage();
    writeExplicitResearchSelection({ provider: "openai", model: "gpt-removed", effort: "low" }, storage);
    expect(resolveResearchSelection({
      catalog: catalog(), hasActiveThread: false, threadSelection: null, preferenceStorage: storage,
      userSelection: { provider: "openai", model: "gpt-removed", effort: "low" },
    })).toMatchObject({ state: "blocked", provenance: "user", reasonCode: "model_not_visible" });
  });

  it("blocks an unsupported saved effort instead of resetting it", () => {
    expect(resolveResearchSelection({
      catalog: routeCatalog({ provider: "openai", model: "gpt-5.6-luna", effort: "experimental" }),
      hasActiveThread: true,
      threadSelection: { provider: "openai", model: "gpt-5.6-luna", effort: "experimental" },
      preferenceStorage: new MemoryStorage(),
    })).toMatchObject({ state: "blocked", provenance: "settings", reasonCode: "effort_not_supported" });
  });

  it("admits a discovered unknown custom model when its explicit effort is real", () => {
    const custom = catalog();
    custom.effective!.tasks.ai_research!.providers!.openai!.models.push(model(
      "gpt-7-custom",
      [],
      { effort_options: undefined, reason_code: "model_not_in_registry" },
    ));

    expect(resolveResearchSelection({
      catalog: routeCatalog({ provider: "openai", model: "gpt-7-custom", effort: "high" }, custom),
      hasActiveThread: true,
      threadSelection: { provider: "openai", model: "gpt-7-custom", effort: "high" },
      preferenceStorage: new MemoryStorage(),
    })).toMatchObject({
      state: "ready", provenance: "settings",
      tuple: { provider: "openai", model: "gpt-7-custom", effort: "high" },
    });
  });

  it("keeps an invalid discovered custom-model effort blocked", () => {
    const custom = catalog();
    custom.effective!.tasks.ai_research!.providers!.openai!.models.push(model(
      "gpt-7-custom",
      [],
      { effort_options: undefined, reason_code: "model_not_in_registry" },
    ));

    expect(resolveResearchSelection({
      catalog: routeCatalog({ provider: "openai", model: "gpt-7-custom", effort: "experimental" }, custom),
      hasActiveThread: true,
      threadSelection: { provider: "openai", model: "gpt-7-custom", effort: "experimental" },
      preferenceStorage: new MemoryStorage(),
    })).toMatchObject({
      state: "blocked", provenance: "settings", reasonCode: "effort_not_supported",
    });
  });

  it.each(["default", "none"])("blocks %s as an incomplete current-model effort", (effort) => {
    expect(resolveResearchSelection({
      catalog: routeCatalog({ provider: "openai", model: "gpt-5.6-luna", effort }),
      hasActiveThread: true,
      threadSelection: { provider: "openai", model: "gpt-5.6-luna", effort },
      preferenceStorage: new MemoryStorage(),
    })).toMatchObject({ state: "blocked", provenance: "settings", reasonCode: "effort_required" });
  });

  it("blocks a retired Settings tuple even with a syntactically valid effort", () => {
    expect(resolveResearchSelection({
      catalog: routeCatalog({ provider: "openai", model: "gpt-5.4-mini", effort: "low" }),
      hasActiveThread: true,
      threadSelection: { provider: "openai", model: "gpt-5.4-mini", effort: "low" },
      preferenceStorage: new MemoryStorage(),
    })).toMatchObject({ state: "blocked", provenance: "settings", reasonCode: "model_retired" });
  });

  it("blocks a blank Settings effort instead of falling through", () => {
    const storage = new MemoryStorage();
    writeExplicitResearchSelection({ provider: "openai", model: "gpt-5.6-luna", effort: "low" }, storage);
    expect(resolveResearchSelection({
      catalog: routeCatalog({ provider: "anthropic", model: "claude-sonnet-5", effort: "  " }), hasActiveThread: true,
      threadSelection: { provider: "anthropic", model: "claude-sonnet-5", effort: "  " },
      preferenceStorage: storage,
    })).toMatchObject({
      state: "blocked", provenance: "settings", reasonCode: "effort_required",
      tuple: { provider: "anthropic", model: "claude-sonnet-5", effort: null },
    });
  });

  it("reads a nullable server effort as historical provenance", async () => {
    await expect(loadResearchThreadSelection("thread-legacy", async () => ({
      provider: "openai", model: "gpt-5.6-luna", effort: null,
    }))).resolves.toEqual({
      provider: "openai", model: "gpt-5.6-luna", effort: null,
    });
  });

  it("writes a versioned preference for an explicit user action", () => {
    const storage = new MemoryStorage();
    const tuple: ExplicitResearchTuple = { provider: "openai", model: "gpt-5.6-luna", effort: "high" };
    writeExplicitResearchSelection(tuple, storage);
    expect(JSON.parse(storage.values.get(RESEARCH_SELECTION_STORAGE_KEY)!)).toEqual({ version: 1, tuple });
    expect(readExplicitResearchSelection(storage)).toEqual(tuple);
  });

  it("does not read an arbitrary non-empty effort as a writable preference", () => {
    const storage = new MemoryStorage();
    storage.values.set(RESEARCH_SELECTION_STORAGE_KEY, JSON.stringify({
      version: 1,
      tuple: { provider: "openai", model: "gpt-5.6-luna", effort: "experimental" },
    }));
    expect(readExplicitResearchSelection(storage)).toBeNull();
  });

  it("does not write an arbitrary non-empty effort as a writable preference", () => {
    const storage = new MemoryStorage();
    writeExplicitResearchSelection({
      provider: "openai", model: "gpt-5.6-luna", effort: "experimental",
    } as unknown as ExplicitResearchTuple, storage);
    expect(storage.values.get(RESEARCH_SELECTION_STORAGE_KEY)).toBeUndefined();
  });

  it("never writes a preference during automatic resolution", () => {
    const storage = new MemoryStorage();
    resolveResearchSelection({
      catalog: catalog(), hasActiveThread: false, threadSelection: null, preferenceStorage: storage,
    });
    expect(storage.setItem).not.toHaveBeenCalled();
    expect(storage.removeItem).not.toHaveBeenCalled();
  });

  it("distinguishes subscription quota from API-key billing", () => {
    expect(quotaKindForAuthMode("chatgpt_oauth")).toBe("subscription");
    expect(quotaKindForAuthMode("claude_code_oauth")).toBe("subscription");
    expect(quotaKindForAuthMode("api_key")).toBe("api");
    expect(quotaKindForAuthMode("api_key_pool")).toBe("api");
    expect(quotaKindForAuthMode("future_auth_mode")).toBeNull();
    expect(quotaKindForAuthMode(null)).toBeNull();

    const subscription = resolveResearchSelection({
      catalog: catalog(), hasActiveThread: false, threadSelection: null, preferenceStorage: new MemoryStorage(),
    });
    const apiKey = resolveResearchSelection({
      catalog: routeCatalog(threadTuple), hasActiveThread: true, threadSelection: threadTuple, preferenceStorage: new MemoryStorage(),
    });
    expect(subscription).toMatchObject({
      authMode: "chatgpt_oauth",
      quotaKind: "subscription",
    });
    expect(apiKey).toMatchObject({
      authMode: "api_key",
      quotaKind: "api",
    });
    for (const result of [subscription, apiKey]) {
      expect(result).not.toHaveProperty("authLabel");
      expect(result).not.toHaveProperty("billingCopy");
      expect(result).not.toHaveProperty("reasonLabel");
    }
  });

  it("fails closed for absent effective truth and applies SDK veto only afterward", () => {
    const absent = catalog();
    delete absent.effective;
    expect(resolveResearchSelection({
      catalog: absent, hasActiveThread: false, threadSelection: null, preferenceStorage: new MemoryStorage(),
      sdkAvailability: { openai: true },
    })).toMatchObject({ state: "blocked", reasonCode: "missing_active_credential" });

    expect(resolveResearchSelection({
      catalog: catalog(), hasActiveThread: false, threadSelection: null, preferenceStorage: new MemoryStorage(),
      sdkAvailability: { openai: false },
    })).toMatchObject({ state: "blocked", reasonCode: "runtime_unavailable" });
    expect(resolveResearchSelection({
      catalog: catalog(), hasActiveThread: false, threadSelection: null, preferenceStorage: new MemoryStorage(),
      sdkAvailability: { anthropic: true },
    })).toMatchObject({ state: "blocked", reasonCode: "runtime_unavailable" });

    expect(resolveResearchSelection({
      catalog: routeCatalog({ provider: "openai", model: "gpt-5.6-luna", effort: "default" }), hasActiveThread: true,
      threadSelection: { provider: "openai", model: "gpt-5.6-luna", effort: "default" },
      preferenceStorage: new MemoryStorage(), sdkAvailability: { openai: false },
    })).toMatchObject({ state: "blocked", reasonCode: "effort_required" });
  });
});
