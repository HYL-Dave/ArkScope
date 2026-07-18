import { describe, expect, it, vi } from "vitest";

import type { ModelCatalog, ModelProvider, TaskRoute } from "./api";
import {
  RESEARCH_SELECTION_STORAGE_KEY,
  readExplicitResearchSelection,
  resolveResearchSelection,
  writeExplicitResearchSelection,
  type ResearchTuple,
} from "./researchSelection";

const route = (
  provider: ModelProvider = "openai",
  model = "gpt-5.4-mini",
  effort = "low",
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
    card_translation: { ...route("anthropic", "claude-sonnet-5", "default"), task: "card_translation" as const },
  };
  const openai = {
    executable: true,
    reason_code: null,
    cache_state: "ok" as const,
    discovered_at: "2026-07-18T00:00:00Z",
    models: [
      model("gpt-5.4-mini", ["low", "high"]),
      model("gpt-5.6-luna", ["low", "high", "max"]),
      model("gpt-route-custom", ["low"], {
        status: "route",
        visible_to_credential: false,
        reason_code: "model_not_in_registry",
      }),
    ],
  };
  const anthropic = {
    executable: true,
    reason_code: null,
    cache_state: "seed_only" as const,
    discovered_at: null,
    models: [model("claude-sonnet-5", ["low", "high"])],
  };
  return {
    providers: ["openai", "anthropic"],
    tasks: [{
      id: "ai_research",
      label: "AI 研究",
      description: "",
      default_provider: "openai",
      recommended_model: "gpt-5.4-mini",
    }],
    models: [],
    effort_options: {
      openai: ["default", "low", "high", "max"].map((id) => ({
        id, provider: "openai" as const, label: id, description: "", applies_to_card_tasks: false,
      })),
      anthropic: ["default", "low", "high"].map((id) => ({
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

describe("research selection precedence and validation", () => {
  it("uses the latest successful tuple for an existing thread", () => {
    const storage = new MemoryStorage();
    writeExplicitResearchSelection({ provider: "openai", model: "gpt-5.6-luna", effort: "max" }, storage);
    expect(resolveResearchSelection({
      catalog: catalog(), hasActiveThread: true, threadSelection: threadTuple, preferenceStorage: storage,
    })).toMatchObject({ state: "ready", provenance: "thread", tuple: threadTuple });
  });

  it("uses the last explicit tuple for a new thread", () => {
    const storage = new MemoryStorage();
    const explicit = { provider: "openai" as const, model: "gpt-5.6-luna", effort: "max" };
    writeExplicitResearchSelection(explicit, storage);
    expect(resolveResearchSelection({
      catalog: catalog(), hasActiveThread: false, threadSelection: null, preferenceStorage: storage,
    })).toMatchObject({ state: "ready", provenance: "explicit", tuple: explicit });
  });

  it("uses the Settings route when there is no prior choice", () => {
    expect(resolveResearchSelection({
      catalog: catalog(), hasActiveThread: false, threadSelection: null, preferenceStorage: new MemoryStorage(),
    })).toMatchObject({
      state: "ready",
      provenance: "settings",
      tuple: { provider: "openai", model: "gpt-5.4-mini", effort: "low" },
    });
  });

  it("blocks an invalid thread tuple without falling through", () => {
    const storage = new MemoryStorage();
    writeExplicitResearchSelection({ provider: "openai", model: "gpt-5.4-mini", effort: "low" }, storage);
    expect(resolveResearchSelection({
      catalog: catalog(),
      hasActiveThread: true,
      threadSelection: { ...threadTuple, model: "claude-removed" },
      preferenceStorage: storage,
    })).toMatchObject({ state: "blocked", provenance: "thread", reasonCode: "model_not_visible" });
  });

  it("blocks an invalid explicit tuple without falling through", () => {
    const storage = new MemoryStorage();
    writeExplicitResearchSelection({ provider: "openai", model: "gpt-removed", effort: "low" }, storage);
    expect(resolveResearchSelection({
      catalog: catalog(), hasActiveThread: false, threadSelection: null, preferenceStorage: storage,
    })).toMatchObject({ state: "blocked", provenance: "explicit", reasonCode: "model_not_visible" });
  });

  it("blocks an invalid Settings route", () => {
    const cat = catalog();
    cat.routes.ai_research = route("openai", "gpt-removed", "low");
    expect(resolveResearchSelection({
      catalog: cat, hasActiveThread: false, threadSelection: null, preferenceStorage: new MemoryStorage(),
    })).toMatchObject({ state: "blocked", provenance: "settings", reasonCode: "model_not_visible" });
  });

  it("blocks an unsupported saved effort instead of resetting it", () => {
    expect(resolveResearchSelection({
      catalog: catalog(),
      hasActiveThread: true,
      threadSelection: { provider: "openai", model: "gpt-5.4-mini", effort: "max" },
      preferenceStorage: new MemoryStorage(),
    })).toMatchObject({ state: "blocked", provenance: "thread", reasonCode: "effort_not_supported" });
  });

  it("accepts semantic default as a complete effort", () => {
    expect(resolveResearchSelection({
      catalog: catalog(),
      hasActiveThread: true,
      threadSelection: { provider: "anthropic", model: "claude-sonnet-5", effort: "default" },
      preferenceStorage: new MemoryStorage(),
    })).toMatchObject({ state: "ready", tuple: { effort: "default" } });
  });

  it("writes a versioned preference for an explicit user action", () => {
    const storage = new MemoryStorage();
    const tuple = { provider: "openai" as const, model: "gpt-5.6-luna", effort: "high" };
    writeExplicitResearchSelection(tuple, storage);
    expect(JSON.parse(storage.values.get(RESEARCH_SELECTION_STORAGE_KEY)!)).toEqual({ version: 1, tuple });
    expect(readExplicitResearchSelection(storage)).toEqual(tuple);
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
    const subscription = resolveResearchSelection({
      catalog: catalog(), hasActiveThread: false, threadSelection: null, preferenceStorage: new MemoryStorage(),
    });
    const apiKey = resolveResearchSelection({
      catalog: catalog(), hasActiveThread: true, threadSelection: threadTuple, preferenceStorage: new MemoryStorage(),
    });
    expect(subscription).toMatchObject({ authLabel: "ChatGPT 訂閱登入" });
    expect(subscription.billingCopy).toContain("訂閱額度");
    expect(apiKey).toMatchObject({ authLabel: "API key" });
    expect(apiKey.billingCopy).toContain("API 帳單");
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

    const invalid = catalog();
    invalid.routes.ai_research = route("openai", "gpt-removed", "low");
    expect(resolveResearchSelection({
      catalog: invalid, hasActiveThread: false, threadSelection: null, preferenceStorage: new MemoryStorage(),
      sdkAvailability: { openai: false },
    })).toMatchObject({ state: "blocked", reasonCode: "model_not_visible" });
  });
});
