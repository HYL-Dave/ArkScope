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
  const taskEfforts = ["low", "medium", "high", "xhigh", "max"];
  const options = (provider: "openai" | "anthropic") => taskEfforts.map((id) => ({
    id,
    provider,
    label: id,
    description: id,
    applies_to_card_tasks: true,
  }));
  const catalog = {
    effort_options: { openai: options("openai"), anthropic: options("anthropic") },
    current_model_ids: [
      "gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol",
      "claude-fable-5", "claude-opus-5", "claude-sonnet-5",
    ],
    retired_model_ids: ["gpt-5.4-mini", "claude-opus-4-8"],
    models: [
      ...["gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol"].map((id) => ({
        id, provider: "openai" as const, effort_options: taskEfforts,
      })),
      ...["claude-fable-5", "claude-opus-5", "claude-sonnet-5"].map((id) => ({
        id, provider: "anthropic" as const, effort_options: taskEfforts,
      })),
    ],
  } as unknown as ModelCatalog;

  it("projects the closed current roster into the product effort order", () => {
    expect(effortOptionsForModel(catalog, "openai", "gpt-5.6-luna").map((item) => item.id))
      .toEqual(["low", "medium", "high", "xhigh", "max"]);
    expect(effortOptionsForModel(catalog, "anthropic", "claude-opus-5").map((item) => item.id))
      .toEqual(["low", "medium", "high", "xhigh", "max"]);
  });

  it("gives a genuinely unknown custom model the explicit provider union", () => {
    expect(effortOptionsForModel(catalog, "openai", "gpt-future-custom").map((item) => item.id))
      .toEqual(["low", "medium", "high", "xhigh", "max"]);
  });
});
