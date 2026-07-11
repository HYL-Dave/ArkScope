import { describe, expect, it } from "vitest";

import type { ModelCatalog, TaskRoute } from "./api";
import {
  blockedRouteSaves,
  isTaskTestSnapshotCurrent,
  providerContexts,
  routesSemanticallyEqual,
  type DraftRouteValue,
  type ProviderContextMap,
  type TaskTestSnapshot,
} from "./modelRoutingUx";

const route = (provider: "openai" | "anthropic", model: string): TaskRoute => ({
  task: "ai_research",
  provider,
  model,
  effort: "default",
  source: "db",
  custom: false,
  warning: null,
});

const credential = (provider: "openai" | "anthropic", id: string, active = true) => ({
  id,
  provider,
  auth_type: provider === "openai" ? "chatgpt_oauth" as const : "api_key" as const,
  label: `${provider} primary`,
  account_label: null,
  expires_at: null,
  source: "profile_state.db",
  available: true,
  masked: null,
  active,
  editable: true,
  can_discover_models: true,
  can_test_models: provider === "anthropic",
  notes: "",
});

describe("providerContexts", () => {
  it("uses the v2 provider summary as authority", () => {
    const contexts = providerContexts(
      {
        openai: { credential_id: "local:7", auth_mode: "chatgpt_oauth", label: "ChatGPT Plus" },
        anthropic: null,
      },
      { openai: [credential("openai", "local:9")], anthropic: [credential("anthropic", "local:4")] },
    );
    expect(contexts.openai).toEqual({
      credential_id: "local:7", auth_mode: "chatgpt_oauth", label: "ChatGPT Plus",
    });
    expect(contexts.anthropic).toBeNull();
  });

  it("falls back to the active credential on an old sidecar", () => {
    const contexts = providerContexts(undefined, {
      openai: [credential("openai", "local:7", false), credential("openai", "local:8")],
      anthropic: [],
    });
    expect(contexts.openai).toEqual({
      credential_id: "local:8", auth_mode: "chatgpt_oauth", label: "openai primary",
    });
    expect(contexts.anthropic).toBeNull();
  });
});

describe("blockedRouteSaves", () => {
  const baseline = {
    ai_research: route("anthropic", "claude-sonnet-5"),
  } as ModelCatalog["routes"];
  const contexts = {
    openai: { credential_id: "local:7", auth_mode: "chatgpt_oauth", label: "ChatGPT" },
    anthropic: null,
  } satisfies ProviderContextMap;

  it("does not block a pre-existing missing-credential route", () => {
    const draft = {
      ai_research: { provider: "anthropic", model: "claude-sonnet-5", effort: "default", custom: false },
    } satisfies Partial<Record<string, DraftRouteValue>>;
    expect(blockedRouteSaves(draft, baseline, contexts)).toEqual([]);
  });

  it("blocks only a task freshly drafted onto that provider", () => {
    const draft = {
      ai_research: { provider: "anthropic", model: "claude-opus-4-8", effort: "default", custom: false },
    } satisfies Partial<Record<string, DraftRouteValue>>;
    expect(blockedRouteSaves(draft, baseline, contexts)).toEqual([
      { task: "ai_research", reason: "missing_active_credential" },
    ]);
  });

  it("compares semantic fields, not object identity", () => {
    expect(routesSemanticallyEqual(
      { provider: "openai", model: "gpt-5.4-mini", effort: "low" },
      { ...route("openai", "gpt-5.4-mini"), effort: "low" },
    )).toBe(true);
  });
});

describe("task test snapshots", () => {
  const snapshot: TaskTestSnapshot = {
    task: "ai_research",
    provider: "openai",
    model: "gpt-5.4-mini",
    effort: "low",
    credential_id: "local:7",
  };

  it("requires all five fields and never accepts an explicitly stale result", () => {
    expect(isTaskTestSnapshotCurrent(snapshot, {
      task: "ai_research",
      route: { provider: "openai", model: "gpt-5.4-mini", effort: "low", custom: false },
      credentialId: "local:7",
      stale: false,
    })).toBe(true);
    expect(isTaskTestSnapshotCurrent(snapshot, {
      task: "ai_research",
      route: { provider: "openai", model: "gpt-5.6-luna", effort: "low", custom: false },
      credentialId: "local:7",
      stale: false,
    })).toBe(false);
    expect(isTaskTestSnapshotCurrent(snapshot, {
      task: "ai_research",
      route: { provider: "openai", model: "gpt-5.4-mini", effort: "low", custom: false },
      credentialId: "local:7",
      stale: true,
    })).toBe(false);
  });
});
