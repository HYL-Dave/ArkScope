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

function render(onReset = vi.fn(), catOverride?: ModelCatalog) {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  const cat = catOverride ?? catalog();
  const modelsByProvider = { anthropic: [MODELS[1]], openai: [MODELS[0]] };
  act(() => {
    root!.render(React.createElement(ModelRoutingSection, {
      catalog: cat,
      draft: {
        ai_research: { provider: "openai", model: "gpt-5.4-mini", effort: "low", custom: false },
        card_translation: { provider: "anthropic", model: "claude-opus-4-8", effort: "default", custom: false },
        card_synthesis: { provider: "openai", model: "gpt-5.4-mini", effort: "default", custom: false },
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

describe("ModelRoutingSection effective picker (P2.7)", () => {
  function catalogWithEffective(): ModelCatalog {
    const cat = catalog();
    // the shared fixture renders only two tasks; the picker tests need all three
    cat.tasks = [
      ...cat.tasks,
      { id: "card_synthesis", label: "卡片合成", description: "", default_provider: "anthropic", recommended_model: "claude-opus-4-8" },
    ];
    cat.effective = {
      tasks: {
        ai_research: {
          verified: [{ id: "gpt-5.4-mini", label: "GPT-5.4 mini", badge: null }],
          advanced: [
            { id: "claude-sonnet-4-6", label: "Sonnet 4.6", badge: "advanced" },
            { id: "mystery-model", label: "mystery-model", badge: "route" },
          ],
          cache_state: "ok",
          discovered_at: "2026-07-10T06:00:00Z",
        },
        card_synthesis: { verified: [], advanced: [], cache_state: "never_discovered", discovered_at: null },
        card_translation: { verified: [], advanced: [], cache_state: "seed_only", discovered_at: null },
      },
    };
    return cat;
  }

  it("defaults to verified models and reveals advanced with badges", () => {
    render(vi.fn(), catalogWithEffective());

    const research = host!.querySelector('[data-testid="route-ai_research"]')!;
    const options = Array.from(research.querySelectorAll("option")).map((o) => (o as HTMLOptionElement).value);
    expect(options.some((v) => v.includes("gpt-5.4-mini"))).toBe(true);
    expect(options.some((v) => v.includes("claude-sonnet-4-6"))).toBe(false);  // advanced hidden by default

    act(() => {
      (research.querySelector('[aria-label="顯示進階模型"]') as HTMLInputElement).click();
    });
    const expanded = Array.from(research.querySelectorAll("option")).map((o) => (o as HTMLOptionElement).value);
    expect(expanded.some((v) => v.includes("claude-sonnet-4-6"))).toBe(true);
    expect(research.textContent).toContain("最後驗證可見");
  });

  it("shows discovery nudge only for never_discovered and badge for seed_only", () => {
    render(vi.fn(), catalogWithEffective());

    const synth = host!.querySelector('[data-testid="route-card_synthesis"]')!;
    expect(synth.textContent).toContain("跑一次模型探索以驗證");
    const trans = host!.querySelector('[data-testid="route-card_translation"]')!;
    expect(trans.textContent).toContain("此通道無法線上列出模型");
    expect(trans.textContent).not.toContain("跑一次模型探索以驗證");
  });

  it("keeps the saved route model selectable from advanced", () => {
    render(vi.fn(), catalogWithEffective());

    const research = host!.querySelector('[data-testid="route-ai_research"]')!;
    act(() => {
      (research.querySelector('[aria-label="顯示進階模型"]') as HTMLInputElement).click();
    });
    const expanded = Array.from(research.querySelectorAll("option")).map((o) => (o as HTMLOptionElement).value);
    expect(expanded.some((v) => v.includes("mystery-model"))).toBe(true);
  });
});
