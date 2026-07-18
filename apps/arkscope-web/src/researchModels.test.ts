import { describe, expect, it } from "vitest";

import type { ModelCatalog, ProviderCredential } from "./api";
import {
  activeCredential,
  effortNote,
  effortOptionsForModel,
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
