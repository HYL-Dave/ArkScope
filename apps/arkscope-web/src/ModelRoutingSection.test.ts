/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ModelRoutingSection } from "./Settings";
import type { ModelCatalog, ModelOption, TaskRoute } from "./api";

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

afterEach(() => {
  if (root) {
    act(() => root!.unmount());
    root = null;
  }
  host?.remove();
  host = null;
});

const MODELS: ModelOption[] = [
  { id: "gpt-5.4-mini", provider: "openai", label: "GPT-5.4 mini", quality: "balanced", speed: "fast",
    cost_tier: "low", supports_structured_output: true, supports_tool_calling: true, recommended_for: [],
    source_url: "", verified_at: "", notes: "" },
  { id: "claude-opus-4-8", provider: "anthropic", label: "Claude Opus 4.8", quality: "frontier", speed: "slow",
    cost_tier: "high", supports_structured_output: true, supports_tool_calling: true, recommended_for: [],
    source_url: "", verified_at: "", notes: "" },
];

const route = (over: Partial<TaskRoute>): TaskRoute => ({
  task: "ai_research", provider: "openai", model: "gpt-5.4-mini", effort: "low",
  source: "db", custom: false, warning: null, ...over,
});

// ai_research = DB authority (resettable); card_translation = yaml fallback (NOT resettable)
function catalog(): ModelCatalog {
  return {
    providers: ["anthropic", "openai"],
    tasks: [
      { id: "ai_research", label: "AI 研究", description: "", default_provider: "openai", recommended_model: "gpt-5.4-mini" },
      { id: "card_translation", label: "翻譯", description: "", default_provider: "anthropic", recommended_model: "claude-opus-4-8" },
    ],
    models: MODELS,
    effort_options: {
      openai: [{ id: "low", provider: "openai", label: "Low", description: "", applies_to_card_tasks: true }],
      anthropic: [{ id: "default", provider: "anthropic", label: "Provider default", description: "", applies_to_card_tasks: true }],
    },
    routes: {
      ai_research: route({ task: "ai_research", source: "db" }),
      card_translation: route({ task: "card_translation", provider: "anthropic", model: "claude-opus-4-8", effort: "default", source: "profile" }),
      card_synthesis: route({ task: "card_synthesis", source: "default" }),
    },
    credentials: { anthropic: [], openai: [] },
    custom_allowed: true,
  };
}

function render(onReset = vi.fn()) {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  const cat = catalog();
  const modelsByProvider = { anthropic: [MODELS[1]], openai: [MODELS[0]] };
  act(() => {
    root!.render(React.createElement(ModelRoutingSection, {
      catalog: cat,
      draft: {
        ai_research: { provider: "openai", model: "gpt-5.4-mini", effort: "low", custom: false },
        card_translation: { provider: "anthropic", model: "claude-opus-4-8", effort: "default", custom: false },
      },
      modelsByProvider,
      testState: {},
      onDraft: vi.fn(),
      onTest: vi.fn(),
      onReset,
    }));
  });
  return onReset;
}

function resetButtons(): HTMLButtonElement[] {
  return Array.from(host!.querySelectorAll("button")).filter(
    (b) => b.textContent?.trim() === "重設為 fallback") as HTMLButtonElement[];
}

describe("ModelRoutingSection reset affordance", () => {
  it("shows '重設為 fallback' ONLY for a DB-authoritative route", () => {
    render();
    // one DB route (ai_research) → exactly one reset button; the profile/default rows have none
    expect(resetButtons()).toHaveLength(1);
  });

  it("calls onReset with the task when the reset button is clicked", () => {
    const onReset = render();
    act(() => {
      resetButtons()[0].dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    });
    expect(onReset).toHaveBeenCalledWith("ai_research");
  });
});
