import { describe, expect, it } from "vitest";

import { chooseResearchProvider } from "./researchProvider";

describe("chooseResearchProvider", () => {
  it("prefers the active thread provider over the Settings route for follow-ups", () => {
    expect(chooseResearchProvider({
      currentProvider: "openai",
      activeThreadProvider: "anthropic",
      availableIds: ["anthropic", "openai"],
      autoRouteSelection: true,
      configuredProvider: "openai",
    })).toBe("anthropic");
  });

  it("lets a manual in-thread switch override the thread default", () => {
    expect(chooseResearchProvider({
      currentProvider: "openai",
      activeThreadProvider: "anthropic",
      availableIds: ["anthropic", "openai"],
      autoRouteSelection: false,
      configuredProvider: "anthropic",
    })).toBe("openai");
  });

  it("uses the Settings route when no thread is active", () => {
    expect(chooseResearchProvider({
      currentProvider: null,
      activeThreadProvider: null,
      availableIds: ["anthropic", "openai"],
      autoRouteSelection: true,
      configuredProvider: "openai",
    })).toBe("openai");
  });

  it("does not silently switch an active thread to another provider when its provider is unavailable", () => {
    expect(chooseResearchProvider({
      currentProvider: "openai",
      activeThreadProvider: "anthropic",
      availableIds: ["openai"],
      autoRouteSelection: true,
      configuredProvider: "openai",
    })).toBeNull();
  });
});
