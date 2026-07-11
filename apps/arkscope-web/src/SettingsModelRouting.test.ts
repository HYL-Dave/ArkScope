/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ModelCatalog, ModelTask, TaskRoute } from "./api";

const taskRoute = (
  task: ModelTask,
  provider: "openai" | "anthropic",
  model: string,
): TaskRoute => ({
  task, provider, model, effort: "default", source: "db", custom: false, warning: null,
});

const providerBlock = (provider: "openai" | "anthropic", model: string) => ({
  executable: true,
  reason_code: null,
  cache_state: "ok",
  discovered_at: "2026-07-11T00:00:00Z",
  models: [{
    id: model,
    label: model,
    status: "visible" as const,
    visible_to_credential: true,
    eligible: true,
    reason_code: null,
    thinking_mode: "none",
  }],
});

const routes = {
  card_synthesis: taskRoute("card_synthesis", "openai", "gpt-5.4-mini"),
  card_translation: taskRoute("card_translation", "anthropic", "claude-sonnet-5"),
  ai_research: taskRoute("ai_research", "openai", "gpt-5.4-mini"),
};

const catalog: ModelCatalog = {
  providers: ["anthropic", "openai"],
  tasks: [
    { id: "card_synthesis", label: "生成", description: "", default_provider: "openai", recommended_model: "gpt-5.4-mini" },
    { id: "card_translation", label: "翻譯", description: "", default_provider: "anthropic", recommended_model: "claude-sonnet-5" },
    { id: "ai_research", label: "研究", description: "", default_provider: "openai", recommended_model: "gpt-5.4-mini" },
  ],
  models: [],
  effort_options: {
    openai: [{ id: "default", provider: "openai", label: "Default", description: "", applies_to_card_tasks: true }],
    anthropic: [{ id: "default", provider: "anthropic", label: "Default", description: "", applies_to_card_tasks: true }],
  },
  routes,
  credentials: { openai: [], anthropic: [] },
  custom_allowed: true,
  effective: {
    providers: {
      openai: { credential_id: "local:7", auth_mode: "api_key", label: "OpenAI API" },
      anthropic: null,
    },
    tasks: Object.fromEntries((Object.keys(routes) as ModelTask[]).map((task) => [task, {
      verified: [], advanced: [], cache_state: "ok", discovered_at: null,
      current_provider: routes[task].provider,
      providers: {
        openai: providerBlock("openai", "gpt-5.4-mini"),
        anthropic: providerBlock("anthropic", "claude-sonnet-5"),
      },
    }])) as ModelCatalog["effective"] extends { tasks: infer T } ? T : never,
  },
};

vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return { ...actual, getModelCatalog: vi.fn(async () => catalog) };
});

import { SettingsView } from "./Settings";

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

afterEach(() => {
  if (root) act(() => root!.unmount());
  root = null;
  host?.remove();
  host = null;
});

async function flush() {
  await act(async () => { await Promise.resolve(); });
}

describe("Settings model route save gate", () => {
  it("allows an unchanged missing route but blocks a new draft onto that provider", async () => {
    host = document.createElement("div");
    document.body.append(host);
    root = createRoot(host);
    await act(async () => {
      root!.render(React.createElement(SettingsView, { runtime: null, onRuntimeChanged: vi.fn() }));
    });
    await flush();

    const save = Array.from(host.querySelectorAll("button"))
      .find((button) => button.textContent?.trim() === "儲存路由") as HTMLButtonElement;
    expect(save.disabled).toBe(false);

    const research = host.querySelector('[data-testid="route-ai_research"]')!;
    const anthropic = Array.from(research.querySelectorAll("button"))
      .find((button) => button.textContent?.trim() === "Anthropic") as HTMLButtonElement;
    await act(async () => anthropic.click());
    await flush();

    expect(save.disabled).toBe(true);
    expect(host.textContent).toContain("本次變更尚未儲存");
  });
});
