import { describe, expect, it } from "vitest";

import type { ProviderCredential } from "./api";
import { activeCredential, defaultModel, effortNote, modelOptions } from "./researchModels";

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
  it("warns that effort is dropped on the Claude subscription", () => {
    const n = effortNote("anthropic", "claude_code_oauth", "high");
    expect(n).not.toBeNull();
    expect(n!).toContain("high");
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
