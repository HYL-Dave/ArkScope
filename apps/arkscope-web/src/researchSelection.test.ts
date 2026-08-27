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
    models: ["claude-fable-5", "claude-opus-5", "claude-sonnet-5"].map((id) => model(id, ["low", "medium", "high", "xhigh", "max"])),
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
      "claude-fable-5", "claude-opus-5", "claude-sonnet-5",
    ],
    retired_model_ids: ["gpt-5.4-mini", "claude-opus-4-8"],
    models: [
      ...["gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol"].map((id) => ({
        id, provider: "openai" as const, effort_options: ["low", "medium", "high", "xhigh", "max"],
      })),
      ...["claude-fable-5", "claude-opus-5", "claude-sonnet-5"].map((id) => ({
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
    const explicit: ExplicitResearchTuple = { provider: "openai", model: "gpt-5.6-luna", effort: "max" };
    writeExplicitResearchSelection(explicit, storage);
    expect(resolveResearchSelection({
      catalog: catalog(), hasActiveThread: false, threadSelection: null, preferenceStorage: storage,
    })).toMatchObject({ state: "ready", provenance: "explicit", tuple: explicit });
  });

  it("initializes a new preference with the current Luna xhigh tuple", () => {
    expect(resolveResearchSelection({
      catalog: catalog(), hasActiveThread: false, threadSelection: null, preferenceStorage: new MemoryStorage(),
    })).toMatchObject({
      state: "ready",
      provenance: "explicit",
      tuple: { provider: "openai", model: "gpt-5.6-luna", effort: "xhigh" },
    });
  });

  it("blocks an invalid thread tuple without falling through", () => {
    const storage = new MemoryStorage();
    writeExplicitResearchSelection({ provider: "openai", model: "gpt-5.6-luna", effort: "low" }, storage);
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

  it("blocks an unsupported saved effort instead of resetting it", () => {
    expect(resolveResearchSelection({
      catalog: catalog(),
      hasActiveThread: true,
      threadSelection: { provider: "openai", model: "gpt-5.6-luna", effort: "experimental" },
      preferenceStorage: new MemoryStorage(),
    })).toMatchObject({ state: "blocked", provenance: "thread", reasonCode: "effort_not_supported" });
  });

  it.each(["default", "none"])("blocks %s as an incomplete current-model effort", (effort) => {
    expect(resolveResearchSelection({
      catalog: catalog(),
      hasActiveThread: true,
      threadSelection: { provider: "openai", model: "gpt-5.6-luna", effort },
      preferenceStorage: new MemoryStorage(),
    })).toMatchObject({ state: "blocked", provenance: "thread", reasonCode: "effort_required" });
  });

  it("blocks a retired historical tuple even with a syntactically valid effort", () => {
    expect(resolveResearchSelection({
      catalog: catalog(),
      hasActiveThread: true,
      threadSelection: { provider: "openai", model: "gpt-5.4-mini", effort: "low" },
      preferenceStorage: new MemoryStorage(),
    })).toMatchObject({ state: "blocked", provenance: "thread", reasonCode: "model_retired" });
  });

  it("retains blank historical effort as thread provenance instead of falling through", () => {
    const storage = new MemoryStorage();
    writeExplicitResearchSelection({ provider: "openai", model: "gpt-5.6-luna", effort: "low" }, storage);
    expect(resolveResearchSelection({
      catalog: catalog(), hasActiveThread: true,
      threadSelection: { provider: "anthropic", model: "claude-sonnet-5", effort: "  " },
      preferenceStorage: storage,
    })).toMatchObject({
      state: "blocked", provenance: "thread", reasonCode: "effort_required",
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
      catalog: catalog(), hasActiveThread: true, threadSelection: threadTuple, preferenceStorage: new MemoryStorage(),
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
      catalog: catalog(), hasActiveThread: true,
      threadSelection: { provider: "openai", model: "gpt-5.6-luna", effort: "default" },
      preferenceStorage: new MemoryStorage(), sdkAvailability: { openai: false },
    })).toMatchObject({ state: "blocked", reasonCode: "effort_required" });
  });
});
