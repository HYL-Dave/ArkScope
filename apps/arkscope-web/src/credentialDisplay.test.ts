import { describe, expect, it } from "vitest";

import { activeFirst, credentialPill, discoverButtonLabel, discoverySourceLabel } from "./credentialDisplay";

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

describe("discoverButtonLabel", () => {
  it("is 查看候選模型 for the seed-only Claude OAuth, else 列模型", () => {
    expect(discoverButtonLabel("claude_code_oauth")).toBe("查看候選模型");
    expect(discoverButtonLabel("chatgpt_oauth")).toBe("列模型");
    expect(discoverButtonLabel("api_key")).toBe("列模型");
    expect(discoverButtonLabel(null)).toBe("列模型");
  });
});
