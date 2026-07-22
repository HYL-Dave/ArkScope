/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import i18n from "i18next";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  CalibrationProposal,
  CalibrationSession,
  CalibrationState,
  InvestorProfileResponse,
  ModelCatalog,
  ModelTask,
  TaskRoute,
} from "./api";
import type { SettingsNavigationRequest } from "./shell/navigation";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

const mocks = vi.hoisted(() => ({
  getModelCatalog: vi.fn(),
}));

const emptyCatalog: ModelCatalog = {
  providers: ["anthropic", "openai"],
  tasks: [],
  models: [],
  effort_options: { anthropic: [], openai: [] },
  routes: {} as Record<ModelTask, TaskRoute>,
  credentials: { anthropic: [], openai: [] },
  custom_allowed: true,
};

vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return { ...actual, getModelCatalog: mocks.getModelCatalog };
});

vi.mock("./settings/DataSourcesSection", () => ({
  DataSourcesSection: () => null,
}));
vi.mock("./settings/DataStorageSection", () => ({ DataStorageSection: () => null }));
vi.mock("./settings/MacroStorageSection", () => ({ MacroStorageSection: () => null }));
vi.mock("./settings/NewsStorageSection", () => ({ NewsStorageSection: () => null }));
vi.mock("./settings/ModelRoutingSection", () => ({
  ModelRoutingSection: () => null,
  TASK_LABELS: {},
}));
vi.mock("./settings/ProviderSection", () => ({
  ProviderSection: () => null,
  CredentialList: () => null,
  DiscoveryResultView: () => null,
  SetupDisclosure: () => null,
}));
vi.mock("./settings/RuntimeLimitSections", () => ({
  FixedTaskRuntimeSection: () => null,
  ResearchRuntimeSection: () => null,
}));

import { SettingsView } from "./Settings";

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;
let saveResponse: Promise<Response> | null = null;

function profileResponse(): InvestorProfileResponse {
  return {
    profile: {
      enabled: true,
      primary_preset: "event_driven",
      risk_appetite: 8,
      risk_capacity: 4,
      risk_mismatch: "appetite_above_capacity",
      holding_horizon: "multi_year",
      drawdown_tolerance_pct: 12,
      concentration_limit_pct: 25,
      preferred_edge: ["growth"],
      avoidances: [],
      behavioral_flags: [],
      freeform_notes: "",
      default_stance: "complementary",
      skill_mode: "off",
      last_reviewed_at: null,
      updated_at: null,
    },
    effective_stance: "complementary",
    trace: {
      profile_active: true,
      assistant_stance: "complementary",
      skill_mode: "off",
      suggested_skills: [],
      applied_skills: [],
    },
    context_preview: "SOURCE_CONTEXT",
  };
}

function session(): CalibrationSession {
  return {
    id: "session-1",
    status: "active",
    interview_version: 1,
    covered_topics: [],
    current_topic_id: "loss_response",
    current_question_message_id: "question-1",
    superseded_reason: null,
    created_at: "2026-07-21T01:00:00Z",
    updated_at: "2026-07-21T01:01:00Z",
    closed_at: null,
  };
}

function proposal(): CalibrationProposal {
  return {
    id: "proposal-1",
    session_id: "session-1",
    status: "draft",
    profile_patch: { risk_capacity: 6 },
    proposed_fields: ["risk_capacity"],
    covered_topics: ["financial_capacity"],
    rationales: { risk_capacity: "SOURCE_RATIONALE" },
    conflict_fields: [],
    created_at: "2026-07-21T01:04:00Z",
    approved_at: null,
    rejected_at: null,
    conflicted_at: null,
    superseded_at: null,
    superseded_reason: null,
  };
}

function calibration(): CalibrationState {
  const active = session();
  return {
    active_session: active,
    sessions: [active],
    messages: [{
      id: "question-1",
      session_id: "session-1",
      role: "assistant",
      content: "SOURCE_QUESTION",
      turn_id: null,
      topic_id: "loss_response",
      prompt_id: "loss_response.opening.v1",
      created_at: "2026-07-21T01:00:00Z",
    }],
    pending_turn: null,
    latest_proposal: proposal(),
    topic_catalog: ["loss_response", "financial_capacity"],
  };
}

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

function navigation(sequence: number): SettingsNavigationRequest {
  return {
    sequence,
    target: { kind: "settings_section", section: "investor_profile" },
  };
}

async function flush() {
  await act(async () => {
    await Promise.resolve();
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

async function render(request: SettingsNavigationRequest) {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(
      <SettingsView
        runtime={null}
        developerMode={false}
        onRuntimeChanged={vi.fn(async () => undefined)}
        navigationRequest={request}
      />,
    );
  });
  await flush();
}

async function rerender(request: SettingsNavigationRequest) {
  await act(async () => {
    root!.render(
      <SettingsView
        runtime={null}
        developerMode={false}
        onRuntimeChanged={vi.fn(async () => undefined)}
        navigationRequest={request}
      />,
    );
  });
  await flush();
}

function button(text: string, scope: ParentNode = document): HTMLButtonElement {
  const found = Array.from(scope.querySelectorAll("button"))
    .find((candidate) => candidate.textContent?.trim() === text);
  if (!(found instanceof HTMLButtonElement)) throw new Error(`missing button: ${text}`);
  return found;
}

async function click(element: HTMLElement) {
  await act(async () => element.click());
  await flush();
}

async function setValue(control: HTMLTextAreaElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")?.set;
  await act(async () => {
    setter?.call(control, value);
    control.dispatchEvent(new Event("input", { bubbles: true }));
    control.dispatchEvent(new Event("change", { bubbles: true }));
  });
}

function investorAnchor(): HTMLElement {
  return host!.querySelector<HTMLElement>('[data-settings-anchor="investor_profile"]')!;
}

beforeEach(async () => {
  await act(async () => {
    await i18n.changeLanguage("en");
  });
  window.localStorage.clear();
  window.sessionStorage.clear();
  mocks.getModelCatalog.mockReset();
  mocks.getModelCatalog.mockResolvedValue(emptyCatalog);
  saveResponse = null;
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    value: vi.fn(() => ({
      matches: false,
      media: "(max-width: 960px)",
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
  Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
    configurable: true,
    value: vi.fn(),
  });
  vi.stubGlobal("fetch", vi.fn(async (url: unknown, init?: RequestInit) => {
    const path = String(url);
    if (path.endsWith("/profile/investor/calibration")) return jsonResponse(calibration());
    if (path.endsWith("/profile/investor") && init?.method === "PUT") {
      return saveResponse ?? jsonResponse(profileResponse());
    }
    if (path.endsWith("/profile/investor")) return jsonResponse(profileResponse());
    return jsonResponse({});
  }));
});

afterEach(() => {
  if (root) act(() => root!.unmount());
  root = null;
  host?.remove();
  host = null;
  vi.unstubAllGlobals();
});

describe("Settings investor exact-anchor integration", () => {
  it("focuses the investor anchor only after clean real-panel modes commit Summary", async () => {
    await render(navigation(1));
    expect(host!.textContent).toContain("Investor Profile summary");

    for (const [command, sequence] of [
      ["Continue Calibration", 2],
      ["Review proposal", 3],
      ["Edit profile", 4],
    ] as const) {
      await click(button(command));
      expect(host!.textContent).not.toContain("Investor Profile summary");
      await rerender(navigation(sequence));
      expect(host!.textContent).toContain("Investor Profile summary");
      expect(document.activeElement).toBe(investorAnchor());
    }
  });

  it("waits for dirty discard before acknowledging and focusing the investor anchor", async () => {
    await render(navigation(1));
    await click(button("Edit profile"));
    const notes = host!.querySelector<HTMLTextAreaElement>('textarea[name="freeform_notes"]')!;
    await setValue(notes, "SOURCE_DIRTY_VALUE");
    await rerender(navigation(2));

    const dialog = document.querySelector<HTMLElement>('[role="dialog"]')!;
    expect(dialog.textContent).toContain("Discard Investor Profile changes?");
    expect(document.activeElement).not.toBe(investorAnchor());
    await click(button("Discard changes", dialog));

    expect(host!.textContent).toContain("Investor Profile summary");
    expect(document.activeElement).toBe(investorAnchor());
  });

  it("keeps a busy real panel in place and does not transfer exact-anchor focus", async () => {
    let resolveSave!: (response: Response) => void;
    saveResponse = new Promise((resolve) => {
      resolveSave = resolve;
    });
    await render(navigation(1));
    await click(button("Edit profile"));
    await click(button("Save profile"));
    const editHeading = host!.querySelector<HTMLElement>('[data-investor-mode-heading="edit"]')!;
    editHeading.focus();
    await rerender(navigation(2));

    expect(host!.textContent).toContain("Edit Investor Profile");
    expect(host!.textContent).toContain("Wait for the current Investor Profile update to finish.");
    expect(document.activeElement).toBe(editHeading);
    expect(document.activeElement).not.toBe(investorAnchor());

    await act(async () => {
      resolveSave(jsonResponse(profileResponse()));
      await Promise.resolve();
    });
    await flush();
  });
});
