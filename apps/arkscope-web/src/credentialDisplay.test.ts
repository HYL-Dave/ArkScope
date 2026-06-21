import { describe, expect, it } from "vitest";

import {
  activeFirst,
  addApiKeyButtonLabel,
  addApiKeySuccessMessage,
  credentialPill,
  credentialAvailabilityText,
  defaultMakeActiveOnAdd,
  discoverButtonLabel,
  discoveryHeaderTitle,
  discoveryResultCredentialLabel,
  discoverySourceLabel,
  supportsCredentialExpiry,
} from "./credentialDisplay";

describe("activeFirst", () => {
  it("moves the active credential to the front, preserving the rest's order", () => {
    const rows = [{ id: "a", active: false }, { id: "b", active: true }, { id: "c", active: false }];
    expect(activeFirst(rows).map((r) => r.id)).toEqual(["b", "a", "c"]);
  });
  it("is a no-op when the first is already active or none is active", () => {
    expect(activeFirst([{ id: "x", active: true }, { id: "y", active: false }]).map((r) => r.id)).toEqual(["x", "y"]);
    expect(activeFirst([{ id: "x", active: false }, { id: "y", active: false }]).map((r) => r.id)).toEqual(["x", "y"]);
  });
  it("does not mutate the input + handles empty", () => {
    const rows = [{ id: "a", active: false }, { id: "b", active: true }];
    activeFirst(rows);
    expect(rows.map((r) => r.id)).toEqual(["a", "b"]);  // original order intact
    expect(activeFirst([])).toEqual([]);
  });
});

describe("discoverySourceLabel", () => {
  it("distinguishes OpenAI API vs ChatGPT backend (both provider_api at the data layer)", () => {
    expect(discoverySourceLabel("openai", "api_key", "provider_api")).toBe("OpenAI API · live");
    expect(discoverySourceLabel("openai", "chatgpt_oauth", "provider_api")).toBe("ChatGPT backend · live");
  });
  it("labels Anthropic API", () => {
    expect(discoverySourceLabel("anthropic", "api_key", "provider_api")).toBe("Anthropic API · live");
  });
  it("labels seed candidates as non-live regardless of provider/mode", () => {
    expect(discoverySourceLabel("anthropic", "claude_code_oauth", "seed")).toBe("seed · 非即時 discovery");
    expect(discoverySourceLabel("openai", "api_key", "seed")).toBe("seed · 非即時 discovery");
  });
});

describe("credentialPill", () => {
  it("reflects the active credential's auth mode (not just key set/no key)", () => {
    expect(credentialPill({ auth_type: "api_key" })).toEqual({ label: "API key", ok: true });
    expect(credentialPill({ auth_type: "chatgpt_oauth" })).toEqual({ label: "ChatGPT OAuth", ok: true });
    expect(credentialPill({ auth_type: "claude_code_oauth" })).toEqual({ label: "Claude OAuth", ok: true });
  });
  it("says no credential when none active", () => {
    expect(credentialPill(null)).toEqual({ label: "無 credential", ok: false });
  });
});

describe("credential row metadata display", () => {
  it("uses short availability copy so rows don't stretch on non-secret OAuth credentials", () => {
    expect(credentialAvailabilityText({ available: true, masked: null })).toBe("可用");
    expect(credentialAvailabilityText({ available: true, masked: "sk-p...Q2wA" })).toBe("sk-p...Q2wA");
    expect(credentialAvailabilityText({ available: false, masked: null })).toBe("缺少");
  });

  it("only shows an expiry editor for OAuth-style credentials", () => {
    expect(supportsCredentialExpiry("api_key")).toBe(false);
    expect(supportsCredentialExpiry("api_key_pool")).toBe(false);
    expect(supportsCredentialExpiry("chatgpt_oauth")).toBe(true);
    expect(supportsCredentialExpiry("claude_code_oauth")).toBe(true);
  });
});

describe("discoverButtonLabel", () => {
  it("is 查看候選模型 for the seed-only Claude OAuth, else 列模型", () => {
    expect(discoverButtonLabel("claude_code_oauth")).toBe("查看候選模型");
    expect(discoverButtonLabel("chatgpt_oauth")).toBe("列模型");
    expect(discoverButtonLabel("api_key")).toBe("列模型");
    expect(discoverButtonLabel(null)).toBe("列模型");
  });
});

describe("add API key activation copy", () => {
  it("defaults to active only when there is no LOCAL DB credential (env fallback rows don't count)", () => {
    expect(defaultMakeActiveOnAdd([])).toBe(true);
    expect(defaultMakeActiveOnAdd([{ id: "openai:OPENAI_API_KEY" }])).toBe(true); // env-only → still empty
    expect(defaultMakeActiveOnAdd([{ id: "local:1" }])).toBe(false); // a DB credential exists
    expect(defaultMakeActiveOnAdd([{ id: "openai:OPENAI_API_KEY" }, { id: "local:2" }])).toBe(false);
  });

  it("labels the submit action by whether the new key will become active", () => {
    expect(addApiKeyButtonLabel(true)).toBe("新增並設為 active");
    expect(addApiKeyButtonLabel(false)).toBe("新增 API key");
  });

  it("reports whether the add switched the active credential", () => {
    expect(addApiKeySuccessMessage("openai", true)).toBe("openai key 已新增並設為 active。");
    expect(addApiKeySuccessMessage("openai", false)).toBe("openai key 已新增（未切換 active）。");
  });
});

describe("discovery result header copy", () => {
  it("labels live vs seed discovery by auth mode", () => {
    expect(discoveryHeaderTitle("api_key")).toBe("列模型結果");
    expect(discoveryHeaderTitle("chatgpt_oauth")).toBe("列模型結果");
    expect(discoveryHeaderTitle("claude_code_oauth")).toBe("查看候選模型");
  });

  it("shows which credential produced the result", () => {
    expect(discoveryResultCredentialLabel({ label: "TS_Codex", auth_type: "chatgpt_oauth" })).toBe("來源：TS_Codex / chatgpt_oauth");
    expect(discoveryResultCredentialLabel({ label: "OpenAI primary", auth_type: "api_key" })).toBe("來源：OpenAI primary / api_key");
    expect(discoveryResultCredentialLabel(null)).toBe("來源：未指定 credential");
  });
});
