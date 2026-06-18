import { describe, expect, it } from "vitest";

import {
  MODEL_OPTION_CUSTOM,
  decodeModelOption,
  encodeModelOption,
  inferProvider,
} from "./modelSelect";

describe("model select encode/decode", () => {
  it("round-trips a catalog option", () => {
    const v = encodeModelOption("openai", "gpt-5.4-mini");
    expect(v).toBe("openai:gpt-5.4-mini");
    expect(decodeModelOption(v)).toEqual({ provider: "openai", model: "gpt-5.4-mini" });
  });

  it("decodes anthropic models (handles colons only at the split point)", () => {
    expect(decodeModelOption("anthropic:claude-opus-4-8")).toEqual({
      provider: "anthropic",
      model: "claude-opus-4-8",
    });
  });

  it("rejects the custom sentinel + malformed values", () => {
    expect(decodeModelOption(MODEL_OPTION_CUSTOM)).toBeNull();
    expect(decodeModelOption("")).toBeNull();
    expect(decodeModelOption("noprovider")).toBeNull();
    expect(decodeModelOption("grok:foo")).toBeNull(); // unknown provider
  });
});

describe("inferProvider (custom model id)", () => {
  it("maps claude-* → anthropic", () => {
    expect(inferProvider("claude-opus-4-8")).toBe("anthropic");
    expect(inferProvider("CLAUDE-sonnet-4-6")).toBe("anthropic");
  });
  it("maps gpt-*/o-series → openai", () => {
    expect(inferProvider("gpt-5.4-mini")).toBe("openai");
    expect(inferProvider("o3")).toBe("openai");
    expect(inferProvider("o4-mini")).toBe("openai");
  });
  it("returns null when ambiguous (keep current provider)", () => {
    expect(inferProvider("grok-2")).toBeNull();
    expect(inferProvider("")).toBeNull();
    expect(inferProvider("   ")).toBeNull();
  });
});
