import { describe, expect, it } from "vitest";

import type { ModelCatalog, ProviderCredential } from "./api";
import {
  activeCredential,
  defaultModel,
  effortNote,
  effortOptionsForModel,
  lastAssistantSelection,
  modelOptions,
} from "./researchModels";

const cred = (over: Partial<ProviderCredential>): ProviderCredential => ({
  id: "local:1", provider: "openai", auth_type: "api_key", label: "k", source: "db",
  account_label: null, expires_at: null, available: true, masked: null, active: false, editable: true,
  can_discover_models: true, can_test_models: true, notes: "", ...over,
});

describe("activeCredential", () => {
  it("returns the active credential", () => {
    const a = cred({ id: "local:2", active: true, auth_type: "chatgpt_oauth" });
    expect(activeCredential([cred({}), a])?.id).toBe("local:2");
  });
  it("returns null when none active or list empty", () => {
    expect(activeCredential([cred({})])).toBeNull();
    expect(activeCredential(undefined)).toBeNull();
  });
});

describe("modelOptions", () => {
  it("prefers discovered models and always includes the route model", () => {
    expect(modelOptions(["gpt-5.4-mini", "gpt-5.5"], "gpt-5.4")).toEqual(["gpt-5.4-mini", "gpt-5.5", "gpt-5.4"]);
  });
  it("de-dupes and trims, keeping order", () => {
    expect(modelOptions(["a", "a", " b "], "a")).toEqual(["a", "b"]);
  });
  it("falls back to just the route model when nothing discovered", () => {
    expect(modelOptions([], "gpt-5.4")).toEqual(["gpt-5.4"]);
  });
  it("is empty when there is neither discovery nor a route model", () => {
    expect(modelOptions([], "")).toEqual([]);
  });
  it("includes a historical model so old threads can show what was used", () => {
    expect(modelOptions(["gpt-5.4-mini"], "gpt-5.4", "gpt-5.5")).toEqual(["gpt-5.4-mini", "gpt-5.4", "gpt-5.5"]);
  });
});

describe("defaultModel", () => {
  it("keeps the current selection when still valid", () => {
    expect(defaultModel(["a", "b"], "b", "a")).toBe("a");
  });
  it("falls back to the route model when current is gone", () => {
    expect(defaultModel(["a", "b"], "b", "zzz")).toBe("b");
  });
  it("falls back to the first option when the route model isn't an option", () => {
    expect(defaultModel(["a", "b"], "zzz", null)).toBe("a");
  });
  it("returns empty when there are no options", () => {
    expect(defaultModel([], "", null)).toBe("");
  });
});

describe("effortNote", () => {
  it("does not warn for Claude subscription effort because the SDK driver applies it", () => {
    const n = effortNote("anthropic", "claude_code_oauth", "high");
    expect(n).toBeNull();
  });
  it("is silent for default/no effort on the subscription", () => {
    expect(effortNote("anthropic", "claude_code_oauth", "default")).toBeNull();
    expect(effortNote("anthropic", "claude_code_oauth", "")).toBeNull();
  });
  it("is silent for api_key and other auth modes", () => {
    expect(effortNote("openai", "api_key", "high")).toBeNull();
    expect(effortNote("anthropic", null, "high")).toBeNull();
  });
});

describe("effortOptionsForModel", () => {
  const options = ["default", "none", "low", "medium", "high", "xhigh", "max"]
    .map((id) => ({
      id,
      provider: "openai" as const,
      label: id,
      description: id,
      applies_to_card_tasks: true,
    }));
  const catalog = {
    effort_options: { openai: options, anthropic: [] },
    models: [
      { id: "gpt-5.4-mini", provider: "openai", effort_options: ["none", "low", "medium", "high", "xhigh"] },
      { id: "gpt-5.6-luna", provider: "openai", effort_options: ["none", "low", "medium", "high", "xhigh", "max"] },
    ],
  } as unknown as ModelCatalog;

  it("uses the selected model contract rather than the provider union", () => {
    expect(effortOptionsForModel(catalog, "openai", "gpt-5.4-mini").map((item) => item.id))
      .toEqual(["default", "none", "low", "medium", "high", "xhigh"]);
    expect(effortOptionsForModel(catalog, "openai", "gpt-5.6-luna").map((item) => item.id))
      .toEqual(["default", "none", "low", "medium", "high", "xhigh", "max"]);
  });

  it("limits a new-sidecar custom model to provider default", () => {
    expect(effortOptionsForModel(catalog, "openai", "gpt-future-custom").map((item) => item.id))
      .toEqual(["default"]);
  });
});

describe("lastAssistantSelection", () => {
  it("returns the newest assistant model and effort", () => {
    const sel = lastAssistantSelection([
      { role: "assistant", model: "gpt-5.4-mini", effort: "low" },
      { role: "user", model: null, effort: null },
      { role: "assistant", model: "gpt-5.5", effort: "xhigh" },
    ]);
    expect(sel).toEqual({ model: "gpt-5.5", effort: "xhigh" });
  });

  it("returns nulls when no assistant has model metadata", () => {
    expect(lastAssistantSelection([{ role: "user", model: null, effort: null }])).toEqual({ model: null, effort: null });
    expect(lastAssistantSelection([{ role: "assistant", model: " ", effort: "default" }])).toEqual({ model: null, effort: null });
  });
});
