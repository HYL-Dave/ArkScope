/** @vitest-environment jsdom */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import i18n from "i18next";
import { afterEach, describe, expect, it, vi } from "vitest";

import { InvestorProfilePanel } from "./InvestorProfilePanel";
import type {
  CalibrationMessage,
  CalibrationProposal,
  CalibrationSession,
  CalibrationState,
  CalibrationTurn,
  InvestorProfileResponse,
} from "./api";
import type { SettingsNavigationGuard } from "./settings/settingsNavigationGuard";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

function dispose() {
  if (root) act(() => root!.unmount());
  root = null;
  host?.remove();
  host = null;
}

afterEach(() => {
  dispose();
  vi.unstubAllGlobals();
});

const disabledResponse = (): InvestorProfileResponse => ({
  profile: {
    enabled: false,
    primary_preset: "growth",
    risk_appetite: null,
    risk_capacity: null,
    risk_mismatch: "unclear",
    holding_horizon: "mixed",
    drawdown_tolerance_pct: null,
    concentration_limit_pct: null,
    preferred_edge: [],
    avoidances: [],
    behavioral_flags: [],
    freeform_notes: "",
    default_stance: "complementary",
    skill_mode: "off",
    last_reviewed_at: null,
    updated_at: null,
  },
  effective_stance: "off",
  trace: {
    profile_active: false,
    assistant_stance: "off",
    skill_mode: "off",
    suggested_skills: [],
    applied_skills: [],
  },
  context_preview: "",
});

const populatedResponse = (): InvestorProfileResponse => {
  const response = disabledResponse();
  response.profile = {
    ...response.profile,
    enabled: true,
    primary_preset: "event_driven",
    risk_appetite: 8,
    risk_capacity: 4,
    risk_mismatch: "appetite_above_capacity",
    holding_horizon: "multi_year",
    drawdown_tolerance_pct: 12,
    concentration_limit_pct: 25,
    preferred_edge: ["growth", "SOURCE_CUSTOM_EDGE"],
    avoidances: ["SOURCE_AVOID_LEVERAGE", "SOURCE_AVOID_HYPE"],
    behavioral_flags: ["FOMO", "SOURCE_CUSTOM_FLAG"],
    freeform_notes: "SOURCE_PROFILE_NOTES",
    default_stance: "complementary",
  };
  response.effective_stance = "complementary";
  response.trace = {
    profile_active: true,
    assistant_stance: "complementary",
    skill_mode: "off",
    suggested_skills: [],
    applied_skills: [],
  };
  response.context_preview = "SOURCE_CONTEXT_PREVIEW";
  return response;
};

async function mount(
  developerMode = false,
  options: {
    onNavigationGuardChange?: (guard: SettingsNavigationGuard) => void;
    onNavigateToProviders?: () => void;
    turnIdFactory?: () => string;
    strictMode?: boolean;
    summaryRequestSequence?: number;
    onSummaryRequestHandled?: (sequence: number, committed: boolean) => void;
  } = {},
) {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  const panel = (
    <InvestorProfilePanel
      developerMode={developerMode}
      onNavigationGuardChange={options.onNavigationGuardChange}
      onNavigateToProviders={options.onNavigateToProviders}
      turnIdFactory={options.turnIdFactory}
      summaryRequestSequence={options.summaryRequestSequence}
      onSummaryRequestHandled={options.onSummaryRequestHandled}
    />
  );
  await act(async () => {
    root!.render(options.strictMode ? <React.StrictMode>{panel}</React.StrictMode> : panel);
  });
}

async function rerenderPanel(
  summaryRequestSequence: number,
  onSummaryRequestHandled?: (sequence: number, committed: boolean) => void,
) {
  await act(async () => {
    root!.render(
      <InvestorProfilePanel
        summaryRequestSequence={summaryRequestSequence}
        onSummaryRequestHandled={onSummaryRequestHandled}
      />,
    );
  });
  await flush();
}

async function flush() {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

async function buttonByText(text: string): Promise<HTMLButtonElement> {
  for (let i = 0; i < 6; i += 1) {
    const found = Array.from(host!.querySelectorAll("button")).find((b) =>
      b.textContent?.includes(text),
    );
    if (found) return found;
    await flush();
  }
  throw new Error(`button not found: ${text}; text=${host?.textContent ?? ""}`);
}

function calibrationSession(
  overrides: Partial<CalibrationSession> = {},
): CalibrationSession {
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
    ...overrides,
  };
}

function calibrationMessage(
  overrides: Partial<CalibrationMessage> = {},
): CalibrationMessage {
  return {
    id: "question-1",
    session_id: "session-1",
    role: "assistant",
    content: "CANONICAL_OPENING_SOURCE",
    turn_id: null,
    topic_id: "loss_response",
    prompt_id: "loss_response.opening.v1",
    created_at: "2026-07-21T01:00:00Z",
    ...overrides,
  };
}

function calibrationTurn(overrides: Partial<CalibrationTurn> = {}): CalibrationTurn {
  return {
    id: "turn-source-1",
    session_id: "session-1",
    kind: "answer",
    status: "interrupted",
    question_message_id: "question-1",
    addressed_topic_id: "loss_response",
    next_topic_id: null,
    error_code: null,
    diagnostic: null,
    attempt_count: 1,
    created_at: "2026-07-21T01:02:00Z",
    updated_at: "2026-07-21T01:03:00Z",
    completed_at: null,
    ...overrides,
  };
}

function calibrationProposal(
  overrides: Partial<CalibrationProposal> = {},
): CalibrationProposal {
  return {
    id: "proposal-1",
    session_id: "session-1",
    status: "draft",
    profile_patch: {
      risk_capacity: 6,
      concentration_limit_pct: 18,
    },
    proposed_fields: ["risk_capacity", "concentration_limit_pct"],
    covered_topics: ["financial_capacity", "single_position_limit"],
    rationales: {
      risk_capacity: "SOURCE_RISK_CAPACITY_RATIONALE",
      concentration_limit_pct: "SOURCE_CONCENTRATION_RATIONALE",
    },
    conflict_fields: [],
    created_at: "2026-07-21T01:04:00Z",
    approved_at: null,
    rejected_at: null,
    conflicted_at: null,
    superseded_at: null,
    superseded_reason: null,
    ...overrides,
  };
}

function emptyCalibration(overrides: Partial<CalibrationState> = {}): CalibrationState {
  return {
    active_session: null,
    sessions: [],
    messages: [],
    pending_turn: null,
    latest_proposal: null,
    topic_catalog: [
      "loss_response",
      "financial_capacity",
      "time_horizon",
      "single_position_limit",
      "risk_avoidances",
      "behavioral_patterns",
      "investment_approach",
      "assistant_style",
    ],
    ...overrides,
  };
}

function activeCalibration(overrides: Partial<CalibrationState> = {}): CalibrationState {
  const active = calibrationSession();
  return emptyCalibration({
    active_session: active,
    sessions: [active],
    messages: [calibrationMessage()],
    ...overrides,
  });
}

type ApiCall = { url: string; method: string; body: unknown };
type ApiResult = unknown | Response | undefined;

function apiRoutes(options: {
  profile?: InvestorProfileResponse;
  calibration?: CalibrationState;
  handle?: (call: ApiCall) => ApiResult | Promise<ApiResult>;
} = {}) {
  const calls: ApiCall[] = [];
  const profile = options.profile ?? populatedResponse();
  const calibration = options.calibration ?? emptyCalibration();
  vi.stubGlobal("fetch", vi.fn(async (url: unknown, init?: RequestInit) => {
    const call: ApiCall = {
      url: String(url),
      method: init?.method ?? "GET",
      body: init?.body ? JSON.parse(String(init.body)) : null,
    };
    calls.push(call);
    const handled = await options.handle?.(call);
    if (handled instanceof Response) return handled;
    const body = handled ?? (
      call.url.endsWith("/profile/investor/calibration")
        ? calibration
        : profile
    );
    return new Response(JSON.stringify(body), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  }));
  return calls;
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

async function clickButton(text: string) {
  const button = await buttonByText(text);
  await act(async () => {
    button.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
  });
  await flush();
  return button;
}

async function setControlValue(control: HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement, value: string) {
  const prototype = control instanceof HTMLTextAreaElement
    ? HTMLTextAreaElement.prototype
    : control instanceof HTMLSelectElement
      ? HTMLSelectElement.prototype
      : HTMLInputElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set;
  await act(async () => {
    setter?.call(control, value);
    control.dispatchEvent(new Event("input", { bubbles: true }));
    control.dispatchEvent(new Event("change", { bubbles: true }));
  });
}

async function useEnglish() {
  await act(async () => {
    await i18n.changeLanguage("en");
  });
}

describe("InvestorProfilePanel", () => {
  it("pending_profile_request_uses_loading_state_not_bare_text", async () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(() => {})));
    await mount();
    expect(host!.querySelector('[data-state="loading"]')?.textContent).toContain("載入投資人設定");
  });


  it("request_failure_uses_alert_semantics", async () => {
    const calibrationLeg = deferred<Response>();
    let profileGets = 0;
    apiRoutes({
      profile: populatedResponse(),
      calibration: emptyCalibration(),
      handle: (call) => {
        if (call.url.endsWith("/profile/investor/calibration") && call.method === "GET") {
          return calibrationLeg.promise;
        }
        if (call.url.endsWith("/profile/investor") && call.method === "GET") {
          profileGets += 1;
          if (profileGets === 1) {
            return new Response(JSON.stringify({ detail: "SOURCE_PROFILE_LOAD_SECRET" }), {
              status: 503,
              headers: { "content-type": "application/json" },
            });
          }
        }
        return undefined;
      },
    });
    await mount();
    await flush();
    expect(host!.querySelector('[role="alert"]')?.textContent).toContain("無法載入投資人設定。");
    expect(host!.textContent).not.toContain("SOURCE_PROFILE_LOAD_SECRET");

    await clickButton("重試");
    expect(profileGets).toBe(2);
    expect(host!.textContent).toContain("投資人設定摘要");
    await act(async () => {
      calibrationLeg.resolve(new Response(JSON.stringify(emptyCalibration()), {
        status: 200,
        headers: { "content-type": "application/json" },
      }));
      await Promise.resolve();
    });
    await flush();
    expect(host!.textContent).toContain("目前沒有進行中的引導式校準");
  });

  it("loads_default_disabled_profile", async () => {
    apiRoutes({ profile: disabledResponse(), calibration: emptyCalibration() });
    await mount();
    await flush();

    expect(host!.textContent).toContain("投資人設定摘要");
    expect(host!.textContent).toContain("個人化已關閉");
    expect(host!.textContent).toContain("目前沒有進行中的引導式校準");
    expect(host!.textContent).toContain("目前未啟用個人化");
    expect(host!.querySelector(".ip-grid")).toBeNull();
    expect(await buttonByText("編輯設定")).not.toBeNull();
    expect(await buttonByText("開始校準")).not.toBeNull();
  });

  it("disabled_profile_shows_effective_off", async () => {
    apiRoutes({ profile: disabledResponse(), calibration: emptyCalibration() });
    await mount();
    await flush();

    expect(host!.textContent).toContain("目前生效的助手立場");
    expect(host!.textContent).toContain("關閉");
    expect(host!.textContent).toContain("助手不會套用投資人設定重點");
  });

  it("draft_button_posts_profile_without_saving", async () => {
    await useEnglish();
    const drafted = populatedResponse();
    drafted.profile.risk_appetite = 9;
    drafted.profile.risk_capacity = 3;
    const calls = apiRoutes({
      profile: populatedResponse(),
      calibration: emptyCalibration(),
      handle: (call) => call.url.endsWith("/profile/investor/draft") ? drafted : undefined,
    });
    await mount();
    await flush();
    await clickButton("Edit profile");
    await setControlValue(
      host!.querySelector<HTMLTextAreaElement>('textarea[name="freeform_notes"]')!,
      "SOURCE_DRAFT_INPUT",
    );
    await clickButton("Generate draft");

    expect(calls.find((call) => call.url.endsWith("/profile/investor/draft"))).toMatchObject({
      method: "POST",
      body: {
        concentration_limit_pct: 25,
        preferred_edge: ["growth", "SOURCE_CUSTOM_EDGE"],
        avoidances: ["SOURCE_AVOID_LEVERAGE", "SOURCE_AVOID_HYPE"],
        behavioral_flags: ["FOMO", "SOURCE_CUSTOM_FLAG"],
        freeform_notes: "SOURCE_DRAFT_INPUT",
      },
    });
    expect(calls.some((call) => call.method === "PUT")).toBe(false);
    expect(host!.textContent).toContain("Edit Investor Profile");
    expect(host!.querySelector('[data-state="ready"]')?.textContent)
      .toContain("Draft generated (not saved)");
  });

  it("save_button_puts_profile", async () => {
    await useEnglish();
    const initial = populatedResponse();
    const refreshed = populatedResponse();
    refreshed.effective_stance = "valuation_rationalist";
    let profileGets = 0;
    const calls = apiRoutes({
      profile: initial,
      calibration: emptyCalibration(),
      handle: (call) => {
        if (call.url.endsWith("/profile/investor") && call.method === "GET") {
          profileGets += 1;
          return profileGets === 1 ? initial : refreshed;
        }
        if (call.url.endsWith("/profile/investor") && call.method === "PUT") return initial;
        return undefined;
      },
    });
    await mount();
    await flush();
    await clickButton("Edit profile");
    await clickButton("Save profile");

    expect(calls.find((call) => call.method === "PUT")?.url).toContain("/profile/investor");
    expect(profileGets).toBe(2);
    expect(host!.textContent).toContain("Investor Profile summary");
    expect(host!.textContent).toContain("Valuation rationalist");
    expect(Array.from(host!.querySelectorAll('[data-state="ready"]'))
      .some((node) => node.textContent?.includes("Saved"))).toBe(true);
  });

  it("shows_a_running_state_while_a_profile_mutation_is_pending", async () => {
    await useEnglish();
    const pendingSave = deferred<Response>();
    const guards: SettingsNavigationGuard[] = [];
    apiRoutes({
      profile: populatedResponse(),
      calibration: emptyCalibration(),
      handle: (call) => call.method === "PUT" ? pendingSave.promise : undefined,
    });
    await mount(false, { onNavigationGuardChange: (guard) => guards.push(guard) });
    await flush();
    await clickButton("Edit profile");
    await clickButton("Save profile");

    expect(host!.querySelector(".investor-profile-panel")?.getAttribute("aria-busy")).toBe("true");
    expect(host!.querySelector('[data-state="running"]')?.textContent)
      .toBe("Updating Investor Profile");
    expect(guards.at(-1)).toEqual({
      dirty: false,
      busy: true,
      reason: "Wait for the current Investor Profile update to finish.",
    });

    await act(async () => {
      pendingSave.resolve(new Response(JSON.stringify(populatedResponse()), {
        status: 200,
        headers: { "content-type": "application/json" },
      }));
      await Promise.resolve();
    });
    await flush();
  });

  it("starts_calibration_sends_message_and_shows_proposal_rationale", async () => {
    await useEnglish();
    const started = activeCalibration();
    const proposal = calibrationProposal({
      rationales: {
        risk_capacity: "SOURCE_PROPOSAL_RATIONALE",
        concentration_limit_pct: "SOURCE_CONCENTRATION_RATIONALE",
      },
    });
    const completed = activeCalibration({
      messages: [
        calibrationMessage(),
        calibrationMessage({
          id: "source-user",
          role: "user",
          content: "SOURCE_CALIBRATION_ANSWER",
          turn_id: "turn-guided-1",
          prompt_id: null,
        }),
        calibrationMessage({
          id: "source-assistant",
          content: "SOURCE_ASSISTANT_FOLLOWUP",
          turn_id: "turn-guided-1",
          topic_id: "financial_capacity",
          prompt_id: null,
        }),
      ],
      latest_proposal: proposal,
    });
    const calls = apiRoutes({
      profile: populatedResponse(),
      calibration: emptyCalibration(),
      handle: (call) => {
        if (call.url.endsWith("/calibration/sessions")) return started;
        if (call.url.endsWith("/calibration/messages")) return completed;
        return undefined;
      },
    });
    await mount(false, { turnIdFactory: () => "turn-guided-1" });
    await flush();
    await clickButton("Start Calibration");
    await setControlValue(
      host!.querySelector<HTMLTextAreaElement>('textarea[name="calibration_answer"]')!,
      "SOURCE_CALIBRATION_ANSWER",
    );
    await clickButton("Send answer");

    expect(calls.find((call) => call.url.endsWith("/calibration/messages"))?.body).toEqual({
      turn_id: "turn-guided-1",
      session_id: "session-1",
      content: "SOURCE_CALIBRATION_ANSWER",
    });
    expect(host!.textContent).toContain("Investor Profile summary");
    expect(host!.textContent).toContain("A calibration proposal is ready for review");
    expect(host!.textContent).not.toContain("SOURCE_PROPOSAL_RATIONALE");
    await clickButton("Review proposal");
    expect(host!.textContent).toContain("Proposal review");
    expect(host!.textContent).toContain("SOURCE_PROPOSAL_RATIONALE");

    dispose();
    const pendingTurns: Array<ReturnType<typeof deferred<Response>>> = [];
    apiRoutes({
      profile: populatedResponse(),
      calibration: activeCalibration(),
      handle: (call) => {
        if (!call.url.endsWith("/calibration/messages")) return undefined;
        const pending = deferred<Response>();
        pendingTurns.push(pending);
        return pending.promise;
      },
    });
    let turnSequence = 0;
    await mount(false, { turnIdFactory: () => `turn-race-${++turnSequence}` });
    await flush();
    await clickButton("Continue Calibration");
    const answer = host!.querySelector<HTMLTextAreaElement>('textarea[name="calibration_answer"]')!;
    await setControlValue(answer, "SOURCE_GENERATION_DRAFT");
    const send = await buttonByText("Send answer");
    await act(async () => {
      send.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
      send.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
      await Promise.resolve();
    });
    expect(pendingTurns).toHaveLength(1);

    await act(async () => {
      pendingTurns[0].resolve(new Response(JSON.stringify(activeCalibration({
        messages: [calibrationMessage({
          id: "single-generation",
          content: "SINGLE_GENERATION_MESSAGE",
          prompt_id: null,
        })],
      })), {
        status: 200,
        headers: { "content-type": "application/json" },
      }));
      await Promise.resolve();
    });
    await flush();
    expect(host!.querySelector(".investor-profile-panel")?.getAttribute("aria-busy")).toBeNull();
    expect(answer.value).toBe("");
    expect(host!.textContent).toContain("SINGLE_GENERATION_MESSAGE");
  });

  it("approves_calibration_proposal_through_dedicated_endpoint", async () => {
    await useEnglish();
    const proposal = calibrationProposal();
    const approvedProfile = populatedResponse().profile;
    approvedProfile.primary_preset = "income";
    approvedProfile.risk_capacity = 6;
    let calibrationGets = 0;
    let profileGets = 0;
    const calls = apiRoutes({
      profile: populatedResponse(),
      calibration: activeCalibration({ latest_proposal: proposal }),
      handle: (call) => {
        if (call.url.includes("/approve")) {
          return {
            profile: approvedProfile,
            proposal: { ...proposal, status: "approved" },
          };
        }
        if (call.url.endsWith("/profile/investor") && call.method === "GET") {
          profileGets += 1;
          if (profileGets > 1) {
            return new Response(JSON.stringify({ detail: "SOURCE_APPROVE_REFRESH_SECRET" }), {
              status: 503,
              headers: { "content-type": "application/json" },
            });
          }
        }
        if (call.url.endsWith("/profile/investor/calibration")) {
          calibrationGets += 1;
          return calibrationGets === 1
            ? activeCalibration({ latest_proposal: proposal })
            : emptyCalibration();
        }
        return undefined;
      },
    });
    await mount();
    await flush();
    await clickButton("Review proposal");
    await clickButton("Approve proposal");

    const approve = calls.find((call) => call.url.includes("/approve"));
    expect(approve).toMatchObject({ method: "POST", body: {} });
    expect(approve?.body).not.toHaveProperty("profile_patch");
    expect(host!.textContent).toContain("Investor Profile summary");
    expect(host!.textContent).toContain("Income");
    expect(host!.textContent).toContain("The profile was saved, but the refreshed summary could not be loaded.");
    expect(host!.textContent).not.toContain("SOURCE_APPROVE_REFRESH_SECRET");
    expect(host!.textContent).not.toContain("SOURCE_CONTEXT_PREVIEW");
    expect(host!.textContent).not.toContain("Complementary");
    expect(document.activeElement).toBe(
      host!.querySelector('[data-investor-mode-heading="summary"]'),
    );

    dispose();
    apiRoutes({
      profile: populatedResponse(),
      calibration: activeCalibration({ latest_proposal: proposal }),
      handle: (call) => call.url.includes("/approve")
        ? new Response(JSON.stringify({ detail: { code: "provider_call_failed" } }), {
          status: 502,
          headers: { "content-type": "application/json" },
        })
        : undefined,
    });
    await mount();
    await flush();
    await clickButton("Review proposal");
    await clickButton("Approve proposal");
    expect(host!.textContent).toContain("Proposal review");
    expect(host!.querySelector('[role="alert"]')?.textContent)
      .toContain("Could not update the calibration proposal.");
    expect(host!.textContent).not.toContain(
      "The profile was saved, but the refreshed summary could not be loaded.",
    );
  });

  it("renders every current Investor Profile field in English", async () => {
    await useEnglish();
    apiRoutes({ profile: populatedResponse(), calibration: emptyCalibration() });
    await mount();
    await flush();
    await clickButton("Edit profile");

    const text = host!.textContent ?? "";
    for (const expected of [
      "Personalization enabled",
      "Investment style",
      "Risk appetite (1-10)",
      "Risk capacity (1-10)",
      "Holding horizon",
      "Tolerable drawdown %",
      "Single-position limit %",
      "Default assistant stance",
      "Preferred edges",
      "Behavioral tendencies (for calibration, not diagnosis)",
      "Avoidances (comma-separated)",
      "Free-form notes (goals, observations, and preferred assistance)",
      "Notes are stored for your reference and currently do not affect AI analysis.",
      "Skill mode: off",
      "Generate draft",
      "Save profile",
    ]) expect.soft(text).toContain(expected);

    expect(host!.querySelector<HTMLInputElement>('input[name="concentration_limit_pct"]')?.value)
      .toBe("25");
    expect(host!.querySelector<HTMLTextAreaElement>('textarea[name="freeform_notes"]')?.value)
      .toBe("SOURCE_PROFILE_NOTES");
    expect(host!.querySelectorAll('[data-testid="investor-profile-edit"] fieldset')).toHaveLength(2);
  });

  it("switches locale without changing draft calibration or proposal state", async () => {
    await useEnglish();
    const state = activeCalibration({ latest_proposal: calibrationProposal() });
    const calls = apiRoutes({ profile: populatedResponse(), calibration: state });
    await mount();
    await flush();
    await clickButton("Continue Calibration");
    const answer = host!.querySelector<HTMLTextAreaElement>('textarea[name="calibration_answer"]')!;
    await setControlValue(answer, "SOURCE_PENDING_CALIBRATION_DRAFT");
    const disclosure = host!.querySelector<HTMLDetailsElement>(
      '[data-testid="calibration-topics-disclosure"]',
    )!;
    disclosure.open = true;
    answer.focus();
    const getCount = calls.filter((call) => call.method === "GET").length;

    await act(async () => {
      await i18n.changeLanguage("zh-Hant");
    });
    await flush();

    expect(host!.querySelector('textarea[name="calibration_answer"]')).toBe(answer);
    expect(answer.value).toBe("SOURCE_PENDING_CALIBRATION_DRAFT");
    expect(host!.querySelector('[data-testid="calibration-topics-disclosure"]')).toBe(disclosure);
    expect(disclosure.open).toBe(true);
    expect(document.activeElement).toBe(answer);
    expect(host!.textContent).toContain("假設一個重要持股在短期內下跌 18%");
    expect(calls.filter((call) => call.method === "GET").length).toBe(getCount);
  });

  it("preserves calibration messages rationales and custom values as source content", async () => {
    await useEnglish();
    const proposal = calibrationProposal({
      profile_patch: { preferred_edge: ["SOURCE_CUSTOM_EDGE", "growth"] },
      proposed_fields: ["preferred_edge"],
      covered_topics: ["investment_approach"],
      rationales: { preferred_edge: "SOURCE_PROPOSAL_RATIONALE" },
    });
    const state = activeCalibration({
      messages: [
        calibrationMessage(),
        calibrationMessage({
          id: "source-user-message",
          role: "user",
          content: "SOURCE_USER_MESSAGE",
          turn_id: "turn-source",
          prompt_id: null,
        }),
        calibrationMessage({
          id: "source-assistant-message",
          content: "SOURCE_ASSISTANT_MESSAGE",
          turn_id: "turn-source",
          prompt_id: null,
        }),
      ],
      latest_proposal: proposal,
    });
    apiRoutes({ profile: populatedResponse(), calibration: state });
    await mount();
    await flush();
    await clickButton("Continue Calibration");
    expect(host!.textContent).toContain("SOURCE_USER_MESSAGE");
    expect(host!.textContent).toContain("SOURCE_ASSISTANT_MESSAGE");
    await clickButton("Back to summary");
    await clickButton("Review proposal");

    expect(host!.textContent).toContain("SOURCE_CUSTOM_EDGE, growth");
    expect(host!.textContent).toContain("SOURCE_PROPOSAL_RATIONALE");
    expect(host!.textContent).not.toContain("session-1");
    expect(host!.textContent).not.toContain("proposal-1");
  });

  it("hides request diagnostics outside Developer Mode and reveals them inside it", async () => {
    await useEnglish();
    const diagnostic = "SOURCE_DIAGNOSTIC_" + "x".repeat(700) + "_TAIL_SECRET";
    vi.stubGlobal("fetch", vi.fn(async () => {
      throw new Error(diagnostic);
    }));
    await mount(false);
    await flush();

    expect(host!.querySelector('[role="alert"]')?.textContent)
      .toContain("Could not load the Investor Profile.");
    expect(host!.textContent).not.toContain("SOURCE_DIAGNOSTIC");
    expect(host!.querySelector('[data-testid="developer-diagnostics"]')).toBeNull();

    dispose();
    await mount(true);
    await flush();

    const developer = host!.querySelector('[data-testid="developer-diagnostics"]')!;
    expect(developer.textContent).toContain("SOURCE_DIAGNOSTIC");
    expect(developer.textContent).not.toContain("TAIL_SECRET");
  });
  it("renders summary first with effective stance mismatch and current context", async () => {
    await useEnglish();
    apiRoutes({ profile: populatedResponse(), calibration: emptyCalibration() });
    await mount();
    await flush();

    const text = host!.textContent ?? "";
    expect(text).toContain("Investor Profile summary");
    expect(text).toContain("Personalization enabled");
    expect(text).toContain("Complementary");
    expect(text).toContain("Investment style");
    expect(text).toContain("Event-driven");
    expect(text).toContain("Holding horizon");
    expect(text).toContain("Multi-year");
    expect(text).toContain("Risk appetite (1-10)");
    expect(text).toContain("8");
    expect(text).toContain("Risk capacity (1-10)");
    expect(text).toContain("4");
    expect(text).toContain("Risk appetite above capacity");
    expect(text).toContain("No active guided calibration");
    expect(text).toContain("SOURCE_CONTEXT_PREVIEW");
    expect(host!.querySelector(".ip-grid")).toBeNull();
  });

  it("loads profile and calibration independently without inventing empty state", async () => {
    await useEnglish();
    const staleProfile = disabledResponse();
    staleProfile.context_preview = "STALE_PROFILE_CONTEXT";
    const latestProfile = populatedResponse();
    latestProfile.context_preview = "LATEST_PROFILE_CONTEXT";
    const latestCalibration = activeCalibration({
      pending_turn: calibrationTurn({ id: "turn-running", status: "pending" }),
    });
    const profileLegs = [deferred<Response>(), deferred<Response>()];
    const calibrationLegs = [deferred<Response>(), deferred<Response>()];
    let profileCalls = 0;
    let calibrationCalls = 0;
    const guards: SettingsNavigationGuard[] = [];
    vi.stubGlobal("fetch", vi.fn((url: unknown) => {
      if (String(url).endsWith("/profile/investor/calibration")) {
        return calibrationLegs[calibrationCalls++].promise;
      }
      return profileLegs[profileCalls++].promise;
    }));
    await mount(false, {
      strictMode: true,
      onNavigationGuardChange: (guard) => guards.push(guard),
    });
    expect(profileCalls).toBe(2);
    expect(calibrationCalls).toBe(2);

    await act(async () => {
      profileLegs[1].resolve(new Response(JSON.stringify(latestProfile), {
        status: 200,
        headers: { "content-type": "application/json" },
      }));
      calibrationLegs[1].resolve(new Response(JSON.stringify(latestCalibration), {
        status: 200,
        headers: { "content-type": "application/json" },
      }));
      await Promise.resolve();
    });
    await flush();
    expect(host!.textContent).toContain("Investor Profile summary");
    expect(host!.textContent).toContain("LATEST_PROFILE_CONTEXT");
    expect(host!.textContent).not.toContain("STALE_PROFILE_CONTEXT");
    expect(host!.textContent).toContain("Sending");
    expect(host!.querySelector(".investor-profile-panel")?.getAttribute("aria-busy")).toBe("true");
    expect(guards.at(-1)).toEqual({
      dirty: false,
      busy: true,
      reason: "Wait for the current Investor Profile update to finish.",
    });
    expect((await buttonByText("Continue Calibration")).disabled).toBe(true);

    await act(async () => {
      profileLegs[0].resolve(new Response(JSON.stringify(staleProfile), {
        status: 200,
        headers: { "content-type": "application/json" },
      }));
      calibrationLegs[0].resolve(new Response(JSON.stringify(emptyCalibration()), {
        status: 200,
        headers: { "content-type": "application/json" },
      }));
      await Promise.resolve();
    });
    await flush();
    expect(host!.textContent).toContain("LATEST_PROFILE_CONTEXT");
    expect(host!.textContent).not.toContain("STALE_PROFILE_CONTEXT");
    expect(host!.textContent).not.toContain("No active guided calibration");
    expect(host!.querySelector(".investor-profile-panel")?.getAttribute("aria-busy")).toBe("true");

    dispose();
    const calibrationAfterSave = deferred<Response>();
    let savedProfileGets = 0;
    apiRoutes({
      profile: populatedResponse(),
      calibration: emptyCalibration(),
      handle: (call) => {
        if (call.url.endsWith("/profile/investor/calibration") && call.method === "GET") {
          return calibrationAfterSave.promise;
        }
        if (call.url.endsWith("/profile/investor") && call.method === "GET") {
          savedProfileGets += 1;
          const response = populatedResponse();
          if (savedProfileGets > 1) response.context_preview = "SOURCE_PROFILE_AFTER_SAVE";
          return response;
        }
        return undefined;
      },
    });
    await mount();
    await flush();
    await clickButton("Edit profile");
    await clickButton("Save profile");
    expect(host!.textContent).toContain("SOURCE_PROFILE_AFTER_SAVE");

    await act(async () => {
      calibrationAfterSave.resolve(new Response(JSON.stringify(emptyCalibration()), {
        status: 200,
        headers: { "content-type": "application/json" },
      }));
      await Promise.resolve();
    });
    await flush();
    expect(host!.textContent).toContain("No active guided calibration");
  });

  it("defaults and reloads to summary while keeping one registry anchor", async () => {
    await useEnglish();
    const calls = apiRoutes({ profile: populatedResponse(), calibration: emptyCalibration() });
    await mount();
    await flush();
    expect(host!.querySelectorAll(".investor-profile-panel")).toHaveLength(1);
    expect(host!.textContent).toContain("Investor Profile summary");

    await clickButton("Edit profile");
    expect(host!.textContent).toContain("Edit Investor Profile");
    dispose();
    await mount();
    await flush();

    expect(host!.querySelectorAll(".investor-profile-panel")).toHaveLength(1);
    expect(host!.textContent).toContain("Investor Profile summary");
    expect(calls.filter((call) => call.method === "GET").length).toBe(4);
  });

  it("resets exact-anchor requests to summary while honoring dirty and busy guards", async () => {
    await useEnglish();
    const handled = vi.fn();
    const pendingSave = deferred<Response>();
    const calls = apiRoutes({
      profile: populatedResponse(),
      calibration: activeCalibration({ latest_proposal: calibrationProposal() }),
      handle: (call) => call.method === "PUT" ? pendingSave.promise : undefined,
    });
    await mount(false, { summaryRequestSequence: 0, onSummaryRequestHandled: handled });
    await flush();
    const initialGetCount = calls.filter((call) => call.method === "GET").length;

    await clickButton("Continue Calibration");
    await rerenderPanel(1, handled);
    expect(host!.textContent).toContain("Investor Profile summary");
    expect(handled).toHaveBeenCalledWith(1, true);
    expect(calls.filter((call) => call.method === "GET")).toHaveLength(initialGetCount);

    await clickButton("Edit profile");
    await setControlValue(
      host!.querySelector<HTMLTextAreaElement>('textarea[name="freeform_notes"]')!,
      "SOURCE_EXTERNAL_DIRTY_VALUE",
    );
    await rerenderPanel(2, handled);
    const dialog = document.querySelector<HTMLElement>('[role="dialog"]')!;
    expect(dialog.textContent).toContain("Discard Investor Profile changes?");
    expect(dialog.textContent).not.toContain("SOURCE_EXTERNAL_DIRTY_VALUE");
    expect(handled).not.toHaveBeenCalledWith(2, expect.anything());
    const discard = Array.from(dialog.querySelectorAll("button"))
      .find((button) => button.textContent === "Discard changes")!;
    await act(async () => discard.click());
    await flush();
    expect(host!.textContent).toContain("Investor Profile summary");
    expect(handled).toHaveBeenCalledWith(2, true);

    await clickButton("Review proposal");
    await rerenderPanel(3, handled);
    expect(host!.textContent).toContain("Investor Profile summary");
    expect(handled).toHaveBeenCalledWith(3, true);

    await clickButton("Edit profile");
    await clickButton("Save profile");
    await rerenderPanel(4, handled);
    expect(host!.textContent).toContain("Edit Investor Profile");
    expect(host!.querySelector('[role="alert"]')?.textContent)
      .toContain("Wait for the current Investor Profile update to finish.");
    expect(handled).toHaveBeenCalledWith(4, false);

    await act(async () => {
      pendingSave.resolve(new Response(JSON.stringify(populatedResponse()), {
        status: 200,
        headers: { "content-type": "application/json" },
      }));
      await Promise.resolve();
    });
    await flush();
  });

  it("enters edit with focus and preserves every profile field", async () => {
    await useEnglish();
    apiRoutes({ profile: populatedResponse(), calibration: emptyCalibration() });
    await mount();
    await flush();
    await clickButton("Edit profile");

    const heading = host!.querySelector<HTMLElement>('[data-investor-mode-heading="edit"]');
    expect(document.activeElement).toBe(heading);
    for (const label of [
      "Investment style",
      "Risk appetite (1-10)",
      "Risk capacity (1-10)",
      "Holding horizon",
      "Tolerable drawdown %",
      "Single-position limit %",
      "Preferred edges",
      "Avoidances (comma-separated)",
      "Behavioral tendencies (for calibration, not diagnosis)",
      "Free-form notes (goals, observations, and preferred assistance)",
      "Default assistant stance",
      "Skill mode: off",
    ]) expect.soft(host!.textContent).toContain(label);
    expect(host!.querySelector<HTMLInputElement>('input[name="concentration_limit_pct"]')?.value)
      .toBe("25");
    expect(host!.querySelector<HTMLTextAreaElement>('textarea[name="freeform_notes"]')?.value)
      .toBe("SOURCE_PROFILE_NOTES");
  });

  it("dirty edit exit uses value-free confirm and cancel restores focus", async () => {
    await useEnglish();
    const guards: SettingsNavigationGuard[] = [];
    apiRoutes({ profile: populatedResponse(), calibration: emptyCalibration() });
    await mount(false, { onNavigationGuardChange: (guard) => guards.push(guard) });
    await flush();
    await clickButton("Edit profile");
    const notes = host!.querySelector<HTMLTextAreaElement>('textarea[name="freeform_notes"]')!;
    await setControlValue(notes, "sk-secret-SOURCE_DIRTY_VALUE");
    expect(guards.at(-1)).toEqual({
      dirty: true,
      busy: false,
      reason: "Your unsaved profile edits will be discarded.",
    });
    const back = await buttonByText("Back to summary");
    await act(async () => back.click());
    await flush();

    const dialog = document.querySelector<HTMLElement>('[role="dialog"]')!;
    expect(dialog.textContent).toContain("Discard Investor Profile changes?");
    expect(dialog.textContent).not.toContain("sk-secret-SOURCE_DIRTY_VALUE");
    const stay = Array.from(dialog.querySelectorAll("button"))
      .find((button) => button.textContent === "Keep editing")!;
    await act(async () => stay.click());
    await flush();
    expect(document.activeElement).toBe(back);
    expect(notes.value).toBe("sk-secret-SOURCE_DIRTY_VALUE");
  });

  it("confirmed edit discard returns to a fresh summary", async () => {
    await useEnglish();
    apiRoutes({ profile: populatedResponse(), calibration: emptyCalibration() });
    await mount();
    await flush();
    await clickButton("Edit profile");
    await setControlValue(
      host!.querySelector<HTMLTextAreaElement>('textarea[name="freeform_notes"]')!,
      "SOURCE_DISCARDED_NOTES",
    );
    await clickButton("Back to summary");
    const dialog = document.querySelector<HTMLElement>('[role="dialog"]')!;
    const discard = Array.from(dialog.querySelectorAll("button"))
      .find((button) => button.textContent === "Discard changes")!;
    await act(async () => discard.click());
    await flush();

    expect(host!.textContent).toContain("Investor Profile summary");
    expect(host!.textContent).not.toContain("SOURCE_DISCARDED_NOTES");
    expect(document.activeElement).toBe(await buttonByText("Edit profile"));
  });

  it("draft save stays in edit without writing or clearing fields", async () => {
    await useEnglish();
    const profile = populatedResponse();
    const calls = apiRoutes({
      profile,
      calibration: emptyCalibration(),
      handle: (call) => call.url.endsWith("/profile/investor/draft") ? profile : undefined,
    });
    await mount();
    await flush();
    await clickButton("Edit profile");
    const notes = host!.querySelector<HTMLTextAreaElement>('textarea[name="freeform_notes"]')!;
    await setControlValue(notes, "SOURCE_DRAFT_NOTES");
    await clickButton("Generate draft");

    expect(host!.textContent).toContain("Edit Investor Profile");
    expect(host!.querySelector<HTMLTextAreaElement>('textarea[name="freeform_notes"]')?.value)
      .toBe("SOURCE_PROFILE_NOTES");
    expect(calls.find((call) => call.url.endsWith("/draft"))?.body).toMatchObject({
      concentration_limit_pct: 25,
      freeform_notes: "SOURCE_DRAFT_NOTES",
    });
    expect(calls.some((call) => call.method === "PUT")).toBe(false);
  });

  it("full save refetches effective profile before summary", async () => {
    await useEnglish();
    const initial = populatedResponse();
    const refreshed = populatedResponse();
    refreshed.effective_stance = "strict_risk_control";
    let profileGets = 0;
    const calls = apiRoutes({
      profile: initial,
      calibration: emptyCalibration(),
      handle: (call) => {
        if (call.url.endsWith("/profile/investor") && call.method === "GET") {
          profileGets += 1;
          return profileGets === 1 ? initial : refreshed;
        }
        if (call.url.endsWith("/profile/investor") && call.method === "PUT") return initial;
        return undefined;
      },
    });
    await mount();
    await flush();
    await clickButton("Edit profile");
    await clickButton("Save profile");

    expect(calls.some((call) => call.method === "PUT")).toBe(true);
    expect(profileGets).toBe(2);
    expect(host!.textContent).toContain("Investor Profile summary");
    expect(host!.textContent).toContain("Strict risk control");
  });

  it("failed post-save refresh stays in edit with an honest error", async () => {
    await useEnglish();
    let profileGets = 0;
    apiRoutes({
      profile: populatedResponse(),
      calibration: emptyCalibration(),
      handle: (call) => {
        if (call.url.endsWith("/profile/investor") && call.method === "GET") {
          profileGets += 1;
          if (profileGets > 1) {
            return new Response(JSON.stringify({ detail: "SOURCE_REFRESH_SECRET" }), {
              status: 503,
              headers: { "content-type": "application/json" },
            });
          }
        }
        return undefined;
      },
    });
    await mount();
    await flush();
    await clickButton("Edit profile");
    await clickButton("Save profile");

    expect(host!.textContent).toContain("Edit Investor Profile");
    expect(host!.querySelector('[role="alert"]')?.textContent)
      .toContain("The profile was saved, but the refreshed summary could not be loaded.");
    expect(host!.textContent).not.toContain("SOURCE_REFRESH_SECRET");
  });

  it("busy save or approve blocks mode change", async () => {
    await useEnglish();
    const pendingSave = deferred<Response>();
    apiRoutes({
      profile: populatedResponse(),
      calibration: emptyCalibration(),
      handle: (call) => call.method === "PUT" ? pendingSave.promise : undefined,
    });
    await mount();
    await flush();
    await clickButton("Edit profile");
    await clickButton("Save profile");
    await clickButton("Back to summary");
    expect(host!.textContent).toContain("Edit Investor Profile");
    expect(host!.querySelector('[role="alert"]')?.textContent)
      .toContain("Wait for the current Investor Profile update to finish.");
    await act(async () => {
      pendingSave.resolve(new Response(JSON.stringify(populatedResponse()), {
        status: 200,
        headers: { "content-type": "application/json" },
      }));
      await Promise.resolve();
    });
    await flush();

    dispose();
    const pendingApprove = deferred<Response>();
    apiRoutes({
      profile: populatedResponse(),
      calibration: activeCalibration({ latest_proposal: calibrationProposal() }),
      handle: (call) => call.url.includes("/approve") ? pendingApprove.promise : undefined,
    });
    await mount();
    await flush();
    await clickButton("Review proposal");
    await clickButton("Approve proposal");
    await clickButton("Back to summary");
    expect(host!.textContent).toContain("Proposal review");
    expect(host!.querySelector('[role="alert"]')?.textContent)
      .toContain("Wait for the current Investor Profile update to finish.");
    await act(async () => {
      pendingApprove.resolve(new Response(JSON.stringify({
        profile: populatedResponse().profile,
        proposal: calibrationProposal({ status: "approved" }),
      }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }));
      await Promise.resolve();
    });
    await flush();
  });

  it("calibration exit is free and restores command focus", async () => {
    await useEnglish();
    const guards: SettingsNavigationGuard[] = [];
    apiRoutes({ profile: populatedResponse(), calibration: activeCalibration() });
    await mount(false, { onNavigationGuardChange: (guard) => guards.push(guard) });
    await flush();
    const command = await buttonByText("Continue Calibration");
    await act(async () => command.click());
    await flush();
    expect(guards.at(-1)).toEqual({ dirty: false, busy: false, reason: null });
    expect(document.activeElement).toBe(
      host!.querySelector('[data-investor-mode-heading="calibration"]'),
    );
    const answer = host!.querySelector<HTMLTextAreaElement>('textarea[name="calibration_answer"]')!;
    await setControlValue(answer, "SOURCE_UNSENT_CALIBRATION_ANSWER");
    await clickButton("Back to summary");

    expect(document.querySelector('[role="dialog"]')).toBeNull();
    expect(host!.textContent).toContain("Investor Profile summary");
    expect(command.isConnected).toBe(false);
    expect(document.activeElement).toBe(await buttonByText("Continue Calibration"));
    dispose();
    expect(guards.at(-1)).toEqual({ dirty: false, busy: false, reason: null });
  });

  it("starts with a localizable fixed question without a provider call", async () => {
    await useEnglish();
    const started = activeCalibration();
    const calls = apiRoutes({
      profile: populatedResponse(),
      calibration: emptyCalibration(),
      handle: (call) => call.url.endsWith("/calibration/sessions") ? started : undefined,
    });
    await mount();
    await flush();
    await clickButton("Start Calibration");

    expect(host!.textContent).toContain(
      "Suppose an important holding falls 18% over a short period while its long-term thesis is not clearly broken. What would you usually do?",
    );
    expect(calls.filter((call) => call.url.endsWith("/calibration/sessions"))).toHaveLength(1);
    expect(calls.some((call) => call.url.endsWith("/calibration/messages"))).toBe(false);
  });

  it("submits source answer with stable turn ID and preserves journal", async () => {
    await useEnglish();
    const answered = activeCalibration({
      messages: [
        calibrationMessage(),
        calibrationMessage({
          id: "answer-1",
          role: "user",
          content: "SOURCE_ANSWER_KEEP_BYTES",
          turn_id: "turn-stable-1",
          prompt_id: null,
        }),
        calibrationMessage({
          id: "question-2",
          content: "SOURCE_NEXT_QUESTION",
          turn_id: "turn-stable-1",
          topic_id: "financial_capacity",
          prompt_id: null,
        }),
      ],
    });
    const calls = apiRoutes({
      profile: populatedResponse(),
      calibration: activeCalibration(),
      handle: (call) => call.url.endsWith("/calibration/messages") ? answered : undefined,
    });
    await mount(false, { turnIdFactory: () => "turn-stable-1" });
    await flush();
    await clickButton("Continue Calibration");
    await setControlValue(
      host!.querySelector<HTMLTextAreaElement>('textarea[name="calibration_answer"]')!,
      "SOURCE_ANSWER_KEEP_BYTES",
    );
    await clickButton("Send answer");

    expect(calls.find((call) => call.url.endsWith("/calibration/messages"))?.body).toEqual({
      turn_id: "turn-stable-1",
      session_id: "session-1",
      content: "SOURCE_ANSWER_KEEP_BYTES",
    });
    expect(host!.textContent).toContain("SOURCE_ANSWER_KEEP_BYTES");
    expect(host!.textContent).toContain("SOURCE_NEXT_QUESTION");
  });

  it("reconciles lost turn responses only from matching assistant evidence", async () => {
    await useEnglish();
    const userOnly = activeCalibration({
      messages: [
        calibrationMessage(),
        calibrationMessage({
          id: "answer-before-provider",
          role: "user",
          content: "SOURCE_USER_ONLY_ANSWER",
          turn_id: "turn-user-only",
          prompt_id: null,
        }),
      ],
    });
    let userOnlyGets = 0;
    apiRoutes({
      profile: populatedResponse(),
      calibration: activeCalibration(),
      handle: (call) => {
        if (call.url.endsWith("/profile/investor/calibration") && call.method === "GET") {
          userOnlyGets += 1;
          return userOnlyGets === 1 ? activeCalibration() : userOnly;
        }
        if (call.url.endsWith("/calibration/messages")) {
          return new Response(JSON.stringify({ detail: { code: "calibration_responder_failed" } }), {
            status: 502,
            headers: { "content-type": "application/json" },
          });
        }
        return undefined;
      },
    });
    await mount(false, { turnIdFactory: () => "turn-user-only" });
    await flush();
    await clickButton("Continue Calibration");
    const userOnlyAnswer = host!.querySelector<HTMLTextAreaElement>(
      'textarea[name="calibration_answer"]',
    )!;
    await setControlValue(userOnlyAnswer, "SOURCE_USER_ONLY_ANSWER");
    await clickButton("Send answer");

    expect(userOnlyAnswer.value).toBe("SOURCE_USER_ONLY_ANSWER");
    expect((await buttonByText("Send answer")).disabled).toBe(false);

    dispose();
    const completed = activeCalibration({
      messages: [
        calibrationMessage(),
        calibrationMessage({
          id: "answer-after-lost-response",
          role: "user",
          content: "SOURCE_RESPONSE_LOST_ANSWER",
          turn_id: "turn-response-lost",
          prompt_id: null,
        }),
        calibrationMessage({
          id: "question-after-lost-response",
          content: "SOURCE_RESPONSE_LOST_COMPLETED",
          turn_id: "turn-response-lost",
          prompt_id: null,
        }),
      ],
    });
    let completedGets = 0;
    apiRoutes({
      profile: populatedResponse(),
      calibration: activeCalibration(),
      handle: (call) => {
        if (call.url.endsWith("/profile/investor/calibration") && call.method === "GET") {
          completedGets += 1;
          return completedGets === 1 ? activeCalibration() : completed;
        }
        if (call.url.endsWith("/calibration/messages")) {
          return new Response(JSON.stringify({ detail: { code: "calibration_responder_failed" } }), {
            status: 502,
            headers: { "content-type": "application/json" },
          });
        }
        return undefined;
      },
    });
    await mount(false, { turnIdFactory: () => "turn-response-lost" });
    await flush();
    await clickButton("Continue Calibration");
    const completedAnswer = host!.querySelector<HTMLTextAreaElement>(
      'textarea[name="calibration_answer"]',
    )!;
    await setControlValue(completedAnswer, "SOURCE_RESPONSE_LOST_ANSWER");
    await clickButton("Send answer");

    expect(completedAnswer.value).toBe("");
    expect(host!.textContent).toContain("SOURCE_RESPONSE_LOST_COMPLETED");
  });

  it("blocks ambiguous turns until manual status refresh resolves authority", async () => {
    await useEnglish();
    const pending = activeCalibration({
      pending_turn: calibrationTurn({ id: "turn-ambiguous", status: "pending" }),
    });
    const failed = activeCalibration({
      pending_turn: calibrationTurn({ id: "turn-ambiguous", status: "failed" }),
    });
    const completed = activeCalibration({
      messages: [
        calibrationMessage(),
        calibrationMessage({
          id: "question-after-ambiguous-retry",
          content: "SOURCE_AMBIGUOUS_RETRY_COMPLETED",
          turn_id: "turn-ambiguous",
          prompt_id: null,
        }),
      ],
    });
    let calibrationGets = 0;
    const calls = apiRoutes({
      profile: populatedResponse(),
      calibration: activeCalibration(),
      handle: (call) => {
        if (call.url.endsWith("/profile/investor/calibration") && call.method === "GET") {
          calibrationGets += 1;
          if (calibrationGets === 2) {
            return new Response(JSON.stringify({ detail: "SOURCE_UNCONFIRMED_TURN" }), {
              status: 503,
              headers: { "content-type": "application/json" },
            });
          }
          if (calibrationGets === 3) return pending;
          if (calibrationGets === 4) return failed;
        }
        if (call.url.endsWith("/calibration/messages")) {
          return new Response(JSON.stringify({ detail: { code: "calibration_responder_failed" } }), {
            status: 502,
            headers: { "content-type": "application/json" },
          });
        }
        if (call.url.includes("/turns/turn-ambiguous/retry")) return completed;
        return undefined;
      },
    });
    await mount(false, { turnIdFactory: () => "turn-ambiguous" });
    await flush();
    await clickButton("Continue Calibration");
    await setControlValue(
      host!.querySelector<HTMLTextAreaElement>('textarea[name="calibration_answer"]')!,
      "SOURCE_AMBIGUOUS_ANSWER",
    );
    await clickButton("Send answer");

    expect(host!.textContent).toContain("Could not load guided calibration.");
    expect(host!.textContent).not.toContain("SOURCE_UNCONFIRMED_TURN");
    expect((await buttonByText("Send answer")).disabled).toBe(true);
    expect((await buttonByText("Propose Now")).disabled).toBe(true);
    await clickButton("Retry");

    expect(calibrationGets).toBe(3);
    expect(host!.textContent).toContain("Sending");
    expect(host!.querySelector<HTMLTextAreaElement>('textarea[name="calibration_answer"]')?.disabled)
      .toBe(true);
    expect((await buttonByText("Propose Now")).disabled).toBe(true);
    await clickButton("Refresh");

    expect(calibrationGets).toBe(4);
    await clickButton("Retry turn");
    expect(calls.filter((call) => call.url.includes("/turns/turn-ambiguous/retry")))
      .toHaveLength(1);
    expect(calls.filter((call) => call.url.endsWith("/calibration/messages"))).toHaveLength(1);
    expect(host!.textContent).toContain("SOURCE_AMBIGUOUS_RETRY_COMPLETED");
  });

  it("refreshes an initially persisted pending turn before retrying the same ID", async () => {
    await useEnglish();
    const pending = activeCalibration({
      pending_turn: calibrationTurn({
        id: "turn-initial-pending",
        status: "pending",
      }),
    });
    const failed = activeCalibration({
      pending_turn: calibrationTurn({
        id: "turn-initial-pending",
        status: "failed",
      }),
    });
    const completed = activeCalibration({
      messages: [
        calibrationMessage(),
        calibrationMessage({
          id: "question-after-initial-pending",
          content: "SOURCE_INITIAL_PENDING_COMPLETED",
          turn_id: "turn-initial-pending",
          prompt_id: null,
        }),
      ],
    });
    let calibrationGets = 0;
    const calls = apiRoutes({
      profile: populatedResponse(),
      calibration: pending,
      handle: (call) => {
        if (call.url.endsWith("/profile/investor/calibration") && call.method === "GET") {
          calibrationGets += 1;
          if (calibrationGets === 1) return pending;
          if (calibrationGets === 2) {
            return new Response(JSON.stringify({ detail: "SOURCE_INITIAL_PENDING_REFRESH" }), {
              status: 503,
              headers: { "content-type": "application/json" },
            });
          }
          return failed;
        }
        if (call.url.includes("/turns/turn-initial-pending/retry")) return completed;
        return undefined;
      },
    });
    await mount();
    await flush();

    expect(host!.textContent).toContain("Sending");
    expect((await buttonByText("Edit profile")).disabled).toBe(true);
    await clickButton("Refresh");

    expect(calibrationGets).toBe(2);
    expect(calls.filter((call) => call.method === "POST")).toHaveLength(0);
    expect(host!.textContent).toContain("Could not load guided calibration.");
    expect(host!.textContent).toContain("Sending");
    expect(host!.textContent).not.toContain("SOURCE_INITIAL_PENDING_REFRESH");
    await clickButton("Retry");

    expect(calibrationGets).toBe(3);
    expect(host!.textContent).toContain("This turn was interrupted. Your answer is saved.");
    await clickButton("Continue Calibration");
    await clickButton("Retry turn");

    expect(calls.filter((call) => call.url.includes("/turns/turn-initial-pending/retry")))
      .toHaveLength(1);
    expect(calls.filter((call) => call.url.endsWith("/calibration/messages"))).toHaveLength(0);
    expect(host!.textContent).toContain("SOURCE_INITIAL_PENDING_COMPLETED");
  });

  it("retries interrupted turn with the same ID without duplicate answer", async () => {
    await useEnglish();
    const interrupted = activeCalibration({
      pending_turn: calibrationTurn({ id: "turn-durable-retry" }),
      messages: [
        calibrationMessage(),
        calibrationMessage({
          id: "answer-retry",
          role: "user",
          content: "SOURCE_SAVED_ANSWER",
          turn_id: "turn-durable-retry",
          prompt_id: null,
        }),
      ],
    });
    const failed = activeCalibration({
      pending_turn: calibrationTurn({
        id: "turn-durable-retry",
        status: "failed",
        attempt_count: 2,
        diagnostic: "SOURCE_FAILED_TURN_DIAGNOSTIC",
      }),
      messages: interrupted.messages,
    });
    const completed = activeCalibration({
      messages: [
        ...interrupted.messages,
        calibrationMessage({
          id: "question-after-retry",
          content: "SOURCE_RETRY_QUESTION",
          turn_id: "turn-durable-retry",
          prompt_id: null,
        }),
      ],
    });
    let calibrationGets = 0;
    let retryAttempts = 0;
    const calls = apiRoutes({
      profile: populatedResponse(),
      calibration: interrupted,
      handle: (call) => {
        if (call.url.endsWith("/profile/investor/calibration") && call.method === "GET") {
          calibrationGets += 1;
          if (calibrationGets === 1) return interrupted;
          if (calibrationGets === 2) return failed;
          return completed;
        }
        if (call.url.includes("/turns/turn-durable-retry/retry")) {
          retryAttempts += 1;
          return new Response(JSON.stringify({ detail: { code: "calibration_responder_failed" } }), {
            status: 502,
            headers: { "content-type": "application/json" },
          });
        }
        return undefined;
      },
    });
    await mount();
    await flush();
    expect(host!.textContent).toContain("This turn was interrupted. Your answer is saved.");
    await clickButton("Continue Calibration");
    expect((await buttonByText("Send answer")).disabled).toBe(true);
    expect((await buttonByText("Propose Now")).disabled).toBe(true);
    await clickButton("Retry turn");

    expect(calibrationGets).toBe(2);
    expect(calls.filter((call) => call.url.includes("/turns/turn-durable-retry/retry")))
      .toHaveLength(1);
    expect(calls.filter((call) => call.url.endsWith("/calibration/messages"))).toHaveLength(0);
    expect((await buttonByText("Send answer")).disabled).toBe(true);
    expect((await buttonByText("Propose Now")).disabled).toBe(true);
    await clickButton("Retry turn");

    const retries = calls.filter((call) => call.url.includes("/turns/turn-durable-retry/retry"));
    expect(retries).toHaveLength(2);
    expect(retries.every((call) => call.body && Object.keys(call.body as object).length === 0))
      .toBe(true);
    expect(calibrationGets).toBe(3);
    expect((host!.textContent?.match(/SOURCE_SAVED_ANSWER/g) ?? [])).toHaveLength(1);
    expect(host!.textContent).toContain("SOURCE_RETRY_QUESTION");
    expect(host!.textContent).not.toContain("Could not complete this calibration turn.");
  });

  it("requests early proposal without synthetic user content", async () => {
    await useEnglish();
    const failed = activeCalibration({
      pending_turn: calibrationTurn({
        id: "turn-propose-now",
        kind: "proposal_request",
        status: "failed",
      }),
    });
    const proposed = activeCalibration({ latest_proposal: calibrationProposal() });
    let calibrationGets = 0;
    const calls = apiRoutes({
      profile: populatedResponse(),
      calibration: activeCalibration(),
      handle: (call) => {
        if (call.url.endsWith("/profile/investor/calibration") && call.method === "GET") {
          calibrationGets += 1;
          return calibrationGets === 1 ? activeCalibration() : failed;
        }
        if (call.url.endsWith("/calibration/proposals/request")) {
          return new Response(JSON.stringify({ detail: { code: "calibration_responder_failed" } }), {
            status: 502,
            headers: { "content-type": "application/json" },
          });
        }
        if (call.url.includes("/turns/turn-propose-now/retry")) return proposed;
        return undefined;
      },
    });
    await mount(false, { turnIdFactory: () => "turn-propose-now" });
    await flush();
    await clickButton("Continue Calibration");
    await clickButton("Propose Now");

    const request = calls.find((call) => call.url.endsWith("/calibration/proposals/request"));
    expect(request?.body).toEqual({ turn_id: "turn-propose-now", session_id: "session-1" });
    expect(request?.body).not.toHaveProperty("content");
    expect(calibrationGets).toBe(2);
    expect((await buttonByText("Send answer")).disabled).toBe(true);
    expect((await buttonByText("Propose Now")).disabled).toBe(true);
    await clickButton("Retry turn");
    expect(calls.some((call) => call.url.includes("/turns/turn-propose-now/retry"))).toBe(true);
    expect(host!.textContent).toContain("Investor Profile summary");
    expect(host!.textContent).toContain("A calibration proposal is ready for review");
    expect(host!.textContent).not.toContain("Proposal review");
    await clickButton("Review proposal");
    expect(host!.textContent).toContain("Proposal review");
  });

  it("returns response-lost draft proposals to summary without replaying the mutation", async () => {
    await useEnglish();
    const proposed = activeCalibration({
      messages: [
        calibrationMessage(),
        calibrationMessage({
          id: "proposal-response-lost-assistant",
          turn_id: "turn-proposal-response-lost",
          prompt_id: null,
        }),
      ],
      latest_proposal: calibrationProposal(),
    });
    let calibrationGets = 0;
    const calls = apiRoutes({
      profile: populatedResponse(),
      calibration: activeCalibration(),
      handle: (call) => {
        if (call.url.endsWith("/profile/investor/calibration") && call.method === "GET") {
          calibrationGets += 1;
          return calibrationGets === 1 ? activeCalibration() : proposed;
        }
        if (call.url.endsWith("/calibration/proposals/request")) {
          return new Response(JSON.stringify({ detail: "SOURCE_PROPOSAL_RESPONSE_LOST" }), {
            status: 504,
            headers: { "content-type": "application/json" },
          });
        }
        return undefined;
      },
    });
    await mount(false, { turnIdFactory: () => "turn-proposal-response-lost" });
    await flush();
    await clickButton("Continue Calibration");
    await clickButton("Propose Now");

    expect(host!.textContent).toContain("Investor Profile summary");
    expect(host!.textContent).toContain("A calibration proposal is ready for review");
    expect(host!.textContent).not.toContain("Could not update the calibration proposal.");
    expect(host!.textContent).not.toContain("SOURCE_PROPOSAL_RESPONSE_LOST");
    expect(calls.filter((call) => call.url.endsWith("/calibration/proposals/request")))
      .toHaveLength(1);
  });

  it("does not correlate an unrelated draft to a failed proposal request", async () => {
    await useEnglish();
    const unrelated = activeCalibration({
      messages: [
        calibrationMessage(),
        calibrationMessage({
          id: "unrelated-draft-assistant",
          turn_id: "turn-unrelated",
          prompt_id: null,
        }),
      ],
      latest_proposal: calibrationProposal({ id: "proposal-unrelated" }),
    });
    let calibrationGets = 0;
    const calls = apiRoutes({
      profile: populatedResponse(),
      calibration: activeCalibration(),
      handle: (call) => {
        if (call.url.endsWith("/profile/investor/calibration") && call.method === "GET") {
          calibrationGets += 1;
          return calibrationGets === 1 ? activeCalibration() : unrelated;
        }
        if (call.url.endsWith("/calibration/proposals/request")) {
          return new Response(JSON.stringify({ detail: "SOURCE_UNRELATED_DRAFT_FAILURE" }), {
            status: 504,
            headers: { "content-type": "application/json" },
          });
        }
        return undefined;
      },
    });
    await mount(false, { turnIdFactory: () => "turn-current-request" });
    await flush();
    await clickButton("Continue Calibration");
    await clickButton("Propose Now");

    expect(host!.textContent).toContain("Guided calibration");
    expect(host!.textContent).toContain("Could not update the calibration proposal.");
    expect(host!.textContent).not.toContain("Investor Profile summary");
    expect(host!.textContent).not.toContain("SOURCE_UNRELATED_DRAFT_FAILURE");
    expect(calls.filter((call) => call.url.endsWith("/calibration/proposals/request")))
      .toHaveLength(1);
  });

  it("does not treat an existing draft as a new proposal or erase same-session evidence", async () => {
    await useEnglish();
    const existingProposal = calibrationProposal({ id: "proposal-existing" });
    const richSession = calibrationSession({ covered_topics: ["time_horizon"] });
    const richState = activeCalibration({
      active_session: richSession,
      sessions: [richSession],
      messages: [
        calibrationMessage(),
        calibrationMessage({
          id: "existing-journal-answer",
          role: "user",
          content: "SOURCE_EXISTING_JOURNAL",
          turn_id: "turn-existing",
          prompt_id: null,
        }),
      ],
      latest_proposal: existingProposal,
    });
    const staleState = activeCalibration({ latest_proposal: existingProposal });
    let calibrationGets = 0;
    const calls = apiRoutes({
      profile: populatedResponse(),
      calibration: richState,
      handle: (call) => {
        if (call.url.endsWith("/profile/investor/calibration") && call.method === "GET") {
          calibrationGets += 1;
          return calibrationGets === 1 ? richState : staleState;
        }
        if (call.url.endsWith("/calibration/proposals/request")) {
          return new Response(JSON.stringify({ detail: "SOURCE_NEW_PROPOSAL_FAILED" }), {
            status: 504,
            headers: { "content-type": "application/json" },
          });
        }
        return undefined;
      },
    });
    await mount(false, { turnIdFactory: () => "turn-new-proposal" });
    await flush();
    await clickButton("Continue Calibration");
    await clickButton("Propose Now");

    expect(host!.textContent).toContain("Guided calibration");
    expect(host!.textContent).toContain("SOURCE_EXISTING_JOURNAL");
    expect(host!.textContent).toContain("How long you invest");
    expect(host!.textContent).toContain("Could not update the calibration proposal.");
    expect(host!.textContent).not.toContain("Investor Profile summary");
    expect(calls.filter((call) => call.url.endsWith("/calibration/proposals/request")))
      .toHaveLength(1);
  });

  it("renders backend-ordered coverage and unknown topic without raw ID", async () => {
    await useEnglish();
    const session = calibrationSession({
      covered_topics: ["time_horizon", "SOURCE_UNKNOWN_TOPIC", "loss_response"],
      current_topic_id: "SOURCE_UNKNOWN_CURRENT",
    });
    apiRoutes({
      profile: populatedResponse(),
      calibration: activeCalibration({ active_session: session, sessions: [session] }),
    });
    await mount();
    await flush();
    await clickButton("Continue Calibration");

    const text = host!.textContent ?? "";
    const covered = host!.querySelector('[data-testid="calibration-covered-topics"]')?.textContent ?? "";
    expect(text).toContain("3 of 8 topics covered");
    expect(covered.indexOf("How long you invest")).toBeLessThan(covered.indexOf("Other topic"));
    expect(covered.indexOf("Other topic")).toBeLessThan(covered.indexOf("How you respond to losses"));
    expect(text).not.toContain("SOURCE_UNKNOWN_TOPIC");
    expect(text).not.toContain("SOURCE_UNKNOWN_CURRENT");
  });

  it("preserves edit draft disclosure and focus across locale switch", async () => {
    await useEnglish();
    const calls = apiRoutes({
      profile: populatedResponse(),
      calibration: activeCalibration({ latest_proposal: calibrationProposal() }),
    });
    await mount();
    await flush();
    await clickButton("Edit profile");
    const notes = host!.querySelector<HTMLTextAreaElement>('textarea[name="freeform_notes"]')!;
    await setControlValue(notes, "SOURCE_LOCALE_DRAFT");
    const disclosure = host!.querySelector<HTMLDetailsElement>('[data-testid="risk-disclosure"]')!;
    disclosure.open = true;
    notes.focus();
    const getCount = calls.filter((call) => call.method === "GET").length;

    await act(async () => {
      await i18n.changeLanguage("zh-Hant");
    });
    await flush();

    expect(host!.querySelector<HTMLTextAreaElement>('textarea[name="freeform_notes"]')).toBe(notes);
    expect(notes.value).toBe("SOURCE_LOCALE_DRAFT");
    expect(host!.querySelector('[data-testid="risk-disclosure"]')).toBe(disclosure);
    expect(disclosure.open).toBe(true);
    expect(document.activeElement).toBe(notes);
    expect(calls.filter((call) => call.method === "GET").length).toBe(getCount);
  });

  it("preserves calibration source content disclosure answer and focus across locale switch", async () => {
    await useEnglish();
    const calls = apiRoutes({
      profile: populatedResponse(),
      calibration: activeCalibration(),
    });
    await mount();
    await flush();
    await clickButton("Continue Calibration");
    const answer = host!.querySelector<HTMLTextAreaElement>('textarea[name="calibration_answer"]')!;
    await setControlValue(answer, "SOURCE_LOCALE_CALIBRATION_ANSWER");
    const disclosure = host!.querySelector<HTMLDetailsElement>(
      '[data-testid="calibration-topics-disclosure"]',
    )!;
    disclosure.open = true;
    answer.focus();
    const getCount = calls.filter((call) => call.method === "GET").length;

    await act(async () => {
      await i18n.changeLanguage("zh-Hant");
    });
    await flush();

    expect(host!.querySelector<HTMLTextAreaElement>('textarea[name="calibration_answer"]'))
      .toBe(answer);
    expect(answer.value).toBe("SOURCE_LOCALE_CALIBRATION_ANSWER");
    expect(host!.querySelector('[data-testid="calibration-topics-disclosure"]')).toBe(disclosure);
    expect(disclosure.open).toBe(true);
    expect(host!.textContent).toContain("SOURCE_LOCALE_CALIBRATION_ANSWER");
    expect(document.activeElement).toBe(answer);
    expect(calls.filter((call) => call.method === "GET").length).toBe(getCount);
  });

  it("preserves proposal source rationale and focus across locale switch", async () => {
    await useEnglish();
    const calls = apiRoutes({
      profile: populatedResponse(),
      calibration: activeCalibration({ latest_proposal: calibrationProposal() }),
    });
    await mount();
    await flush();
    await clickButton("Review proposal");
    const review = host!.querySelector<HTMLElement>(
      '[data-testid="investor-profile-proposal-review"]',
    )!;
    const reject = await buttonByText("Reject proposal");
    reject.focus();
    const getCount = calls.filter((call) => call.method === "GET").length;

    await act(async () => {
      await i18n.changeLanguage("zh-Hant");
    });
    await flush();

    expect(host!.querySelector('[data-testid="investor-profile-proposal-review"]')).toBe(review);
    expect(host!.textContent).toContain("SOURCE_RISK_CAPACITY_RATIONALE");
    expect(host!.textContent).toContain("SOURCE_CONCENTRATION_RATIONALE");
    expect(document.activeElement).toBe(reject);
    expect(calls.filter((call) => call.method === "GET").length).toBe(getCount);
  });

  it("proposal mode requires a pending proposal and separates coverage from actions", async () => {
    await useEnglish();
    const initialProfile = populatedResponse();
    const refreshedProfile = populatedResponse();
    refreshedProfile.effective_stance = "strict_risk_control";
    refreshedProfile.context_preview = "SOURCE_REJECT_REFRESHED_CONTEXT";
    const proposal = calibrationProposal();
    const rejectedProposal = {
      ...proposal,
      status: "rejected" as const,
      rejected_at: "2026-07-21T01:06:00Z",
    };
    let profileGets = 0;
    let calibrationGets = 0;
    const calls = apiRoutes({
      profile: initialProfile,
      calibration: activeCalibration({ latest_proposal: proposal }),
      handle: (call) => {
        if (call.url.endsWith("/profile/investor") && call.method === "GET") {
          profileGets += 1;
          if (profileGets === 1) return initialProfile;
          if (profileGets === 2) {
            return new Response(JSON.stringify({ detail: "SOURCE_REJECT_REFRESH_SECRET" }), {
              status: 503,
              headers: { "content-type": "application/json" },
            });
          }
          return refreshedProfile;
        }
        if (call.url.endsWith("/profile/investor/calibration") && call.method === "GET") {
          calibrationGets += 1;
          return calibrationGets === 1
            ? activeCalibration({ latest_proposal: proposal })
            : emptyCalibration({ latest_proposal: rejectedProposal });
        }
        if (call.url.endsWith(`/proposals/${proposal.id}/reject`)) {
          return { proposal: rejectedProposal };
        }
        return undefined;
      },
    });
    await mount();
    await flush();
    await clickButton("Review proposal");

    const coverage = host!.querySelector('[data-testid="proposal-coverage"]')!;
    const changes = host!.querySelector('[data-testid="proposal-changes"]')!;
    const actions = host!.querySelector('[data-testid="proposal-actions"]')!;
    expect(coverage).not.toBeNull();
    expect(changes).not.toBeNull();
    expect(actions).not.toBeNull();
    expect(coverage.contains(actions)).toBe(false);
    expect(changes.contains(actions)).toBe(false);
    expect(coverage.textContent).toContain("What your finances allow");

    await clickButton("Reject proposal");
    expect(calls.filter((call) => call.url.endsWith("/profile/investor") && call.method === "GET"))
      .toHaveLength(2);
    expect(calibrationGets).toBe(2);
    expect(host!.querySelector('[role="alert"]')?.textContent)
      .toContain("Could not refresh status.");
    expect(host!.textContent).not.toContain(
      "The profile was saved, but the refreshed summary could not be loaded.",
    );
    expect(host!.textContent).toContain("Investor Profile summary");
    expect(host!.textContent).toContain("Event-driven");
    expect(host!.textContent).not.toContain("Effective AI stance");
    expect(host!.textContent).not.toContain("SOURCE_REJECT_REFRESH_SECRET");

    await clickButton("Retry");
    expect(calls.filter((call) => call.url.endsWith("/profile/investor") && call.method === "GET"))
      .toHaveLength(3);
    expect(host!.textContent).toContain("Investor Profile summary");
    expect(host!.textContent).toContain("Event-driven");
    expect(host!.textContent).toContain("Strict risk control");
    expect(host!.textContent).toContain("SOURCE_REJECT_REFRESHED_CONTEXT");

    dispose();
    apiRoutes({ profile: populatedResponse(), calibration: activeCalibration() });
    await mount();
    await flush();
    expect(Array.from(host!.querySelectorAll("button")).some(
      (button) => button.textContent === "Review proposal",
    )).toBe(false);
  });

  it("reconciles ambiguous approve and reject outcomes from read-only authority", async () => {
    await useEnglish();
    const proposal = calibrationProposal();
    const approvedProposal = calibrationProposal({
      status: "approved",
      approved_at: "2026-07-21T01:07:00Z",
    });
    const approvedProfile = populatedResponse();
    approvedProfile.profile.primary_preset = "income";
    approvedProfile.profile.risk_capacity = 6;
    approvedProfile.profile.concentration_limit_pct = 18;
    approvedProfile.effective_stance = "strict_risk_control";
    let approveProfileGets = 0;
    let approveCalibrationGets = 0;
    const approveCalls = apiRoutes({
      profile: populatedResponse(),
      calibration: activeCalibration({ latest_proposal: proposal }),
      handle: (call) => {
        if (call.url.endsWith("/profile/investor") && call.method === "GET") {
          approveProfileGets += 1;
          return approveProfileGets === 1 ? populatedResponse() : approvedProfile;
        }
        if (call.url.endsWith("/profile/investor/calibration") && call.method === "GET") {
          approveCalibrationGets += 1;
          return approveCalibrationGets === 1
            ? activeCalibration({ latest_proposal: proposal })
            : activeCalibration({ latest_proposal: approvedProposal });
        }
        if (call.url.includes("/approve")) {
          return new Response(JSON.stringify({ detail: "SOURCE_APPROVE_RESPONSE_LOST" }), {
            status: 504,
            headers: { "content-type": "application/json" },
          });
        }
        return undefined;
      },
    });
    await mount();
    await flush();
    await clickButton("Review proposal");
    await clickButton("Approve proposal");

    expect(host!.textContent).toContain("Investor Profile summary");
    expect(host!.textContent).toContain("Calibration proposal approved");
    expect(host!.textContent).toContain("Income");
    expect(host!.textContent).toContain("Strict risk control");
    expect(host!.textContent).not.toContain("SOURCE_APPROVE_RESPONSE_LOST");
    expect(approveCalls.filter((call) => call.url.includes("/approve"))).toHaveLength(1);

    dispose();
    let rejectProfileGets = 0;
    let rejectCalibrationGets = 0;
    const rejectCalls = apiRoutes({
      profile: populatedResponse(),
      calibration: activeCalibration({ latest_proposal: proposal }),
      handle: (call) => {
        if (call.url.endsWith("/profile/investor") && call.method === "GET") {
          rejectProfileGets += 1;
          return populatedResponse();
        }
        if (call.url.endsWith("/profile/investor/calibration") && call.method === "GET") {
          rejectCalibrationGets += 1;
          if (rejectCalibrationGets === 1) {
            return activeCalibration({ latest_proposal: proposal });
          }
          if (rejectCalibrationGets === 2) {
            return new Response(JSON.stringify({ detail: "SOURCE_REJECT_AUTHORITY_UNKNOWN" }), {
              status: 503,
              headers: { "content-type": "application/json" },
            });
          }
          return activeCalibration({ latest_proposal: proposal });
        }
        if (call.url.includes("/reject")) {
          return new Response(JSON.stringify({ detail: "SOURCE_REJECT_RESPONSE_LOST" }), {
            status: 504,
            headers: { "content-type": "application/json" },
          });
        }
        return undefined;
      },
    });
    await mount();
    await flush();
    await clickButton("Review proposal");
    await clickButton("Reject proposal");

    expect(rejectProfileGets).toBe(2);
    expect(rejectCalibrationGets).toBe(2);
    expect(host!.textContent).not.toContain("Proposal review");
    expect(host!.textContent).toContain("Could not load guided calibration.");
    expect(host!.textContent).not.toContain("SOURCE_REJECT_AUTHORITY_UNKNOWN");
    await rerenderPanel(1);
    expect(host!.textContent).toContain("Investor Profile summary");
    expect(host!.querySelector('[data-testid="summary-pending-proposal"]')).toBeNull();
    await clickButton("Retry turn");

    expect(rejectCalibrationGets).toBe(3);
    expect(host!.textContent).toContain("A calibration proposal is ready for review");
    await clickButton("Review proposal");
    expect(host!.textContent).toContain("Proposal review");
    expect((await buttonByText("Reject proposal")).disabled).toBe(false);
    expect(rejectCalls.filter((call) => call.url.includes("/reject"))).toHaveLength(1);
  });

  it("keeps the approved proposal patch when ambiguous reconciliation reads a stale profile", async () => {
    await useEnglish();
    const proposal = calibrationProposal({
      profile_patch: { risk_capacity: 6 },
      proposed_fields: ["risk_capacity"],
    });
    const approvedProposal = calibrationProposal({
      ...proposal,
      status: "approved",
      approved_at: "2026-07-21T01:07:00Z",
    });
    let profileGets = 0;
    let calibrationGets = 0;
    const calls = apiRoutes({
      profile: populatedResponse(),
      calibration: activeCalibration({ latest_proposal: proposal }),
      handle: (call) => {
        if (call.url.endsWith("/profile/investor") && call.method === "GET") {
          profileGets += 1;
          return populatedResponse();
        }
        if (call.url.endsWith("/profile/investor/calibration") && call.method === "GET") {
          calibrationGets += 1;
          return calibrationGets === 1
            ? activeCalibration({ latest_proposal: proposal })
            : activeCalibration({ latest_proposal: approvedProposal });
        }
        if (call.url.includes("/approve")) {
          return new Response(JSON.stringify({ detail: "SOURCE_APPROVE_RESPONSE_LOST" }), {
            status: 504,
            headers: { "content-type": "application/json" },
          });
        }
        return undefined;
      },
    });
    await mount();
    await flush();
    await clickButton("Review proposal");
    await clickButton("Approve proposal");

    expect(profileGets).toBe(2);
    expect(calibrationGets).toBe(2);
    expect(host!.textContent).toContain("Investor Profile summary");
    expect(host!.textContent).toContain("Calibration proposal approved");
    expect(host!.textContent).toContain("Risk capacity (1-10)6");
    expect(host!.textContent).not.toContain("Risk capacity (1-10)4");
    expect(host!.textContent).not.toContain("Effective AI stance");
    expect(host!.textContent).not.toContain("SOURCE_APPROVE_RESPONSE_LOST");
    expect(calls.filter((call) => call.url.includes("/approve"))).toHaveLength(1);
  });

  it("withholds derived mismatch until an approved patch is corroborated", async () => {
    await useEnglish();
    const proposal = calibrationProposal({
      profile_patch: { risk_appetite: 2, risk_capacity: 8 },
      proposed_fields: ["risk_appetite", "risk_capacity"],
    });
    const approvedProposal = calibrationProposal({
      ...proposal,
      status: "approved",
      approved_at: "2026-07-21T01:07:00Z",
    });
    const corroborated = populatedResponse();
    corroborated.profile.risk_appetite = 2;
    corroborated.profile.risk_capacity = 8;
    corroborated.profile.risk_mismatch = "capacity_above_appetite";
    corroborated.effective_stance = "strict_risk_control";
    let profileGets = 0;
    let calibrationGets = 0;
    apiRoutes({
      profile: populatedResponse(),
      calibration: activeCalibration({ latest_proposal: proposal }),
      handle: (call) => {
        if (call.url.endsWith("/profile/investor") && call.method === "GET") {
          profileGets += 1;
          return profileGets < 3 ? populatedResponse() : corroborated;
        }
        if (call.url.endsWith("/profile/investor/calibration") && call.method === "GET") {
          calibrationGets += 1;
          return calibrationGets === 1
            ? activeCalibration({ latest_proposal: proposal })
            : activeCalibration({ latest_proposal: approvedProposal });
        }
        if (call.url.includes("/approve")) {
          return new Response(JSON.stringify({ detail: "SOURCE_APPROVE_RESPONSE_LOST" }), {
            status: 504,
            headers: { "content-type": "application/json" },
          });
        }
        return undefined;
      },
    });
    await mount();
    await flush();
    await clickButton("Review proposal");
    await clickButton("Approve proposal");

    expect(host!.textContent).toContain("Risk appetite (1-10)2");
    expect(host!.textContent).toContain("Risk capacity (1-10)8");
    expect(host!.textContent).toContain("Not assessed");
    expect(host!.textContent).not.toContain("Risk appetite above capacity");
    expect(host!.textContent).not.toContain("Risk capacity above appetite");
    await clickButton("Retry");

    expect(profileGets).toBe(3);
    expect(host!.textContent).toContain("Risk capacity above appetite");
    expect(host!.textContent).not.toContain("Not assessed");
    expect(host!.textContent).toContain("Strict risk control");
  });

  it("keeps successful approve authority across stale advisory GET responses", async () => {
    await useEnglish();
    const proposal = calibrationProposal();
    const approvedProposal = calibrationProposal({
      status: "approved",
      approved_at: "2026-07-21T01:08:00Z",
    });
    const approvedProfile = populatedResponse().profile;
    approvedProfile.primary_preset = "income";
    approvedProfile.risk_capacity = 6;
    let profileGets = 0;
    let calibrationGets = 0;
    const calls = apiRoutes({
      profile: populatedResponse(),
      calibration: activeCalibration({ latest_proposal: proposal }),
      handle: (call) => {
        if (call.url.includes("/approve")) {
          return { profile: approvedProfile, proposal: approvedProposal };
        }
        if (call.url.endsWith("/profile/investor") && call.method === "GET") {
          profileGets += 1;
          return populatedResponse();
        }
        if (call.url.endsWith("/profile/investor/calibration") && call.method === "GET") {
          calibrationGets += 1;
          return activeCalibration({ latest_proposal: proposal });
        }
        return undefined;
      },
    });
    await mount();
    await flush();
    await clickButton("Review proposal");
    await clickButton("Approve proposal");

    expect(profileGets).toBe(2);
    expect(calibrationGets).toBe(2);
    expect(host!.textContent).toContain("Investor Profile summary");
    expect(host!.textContent).toContain("Calibration proposal approved");
    expect(host!.textContent).toContain("Income");
    expect(host!.textContent).not.toContain("Event-driven");
    expect(host!.textContent).not.toContain("Complementary");
    expect(host!.querySelector('[data-testid="summary-pending-proposal"]')).toBeNull();
    expect(calls.filter((call) => call.url.includes("/approve"))).toHaveLength(1);
  });

  it("keeps a later full save authoritative after approved stale reconciliation", async () => {
    await useEnglish();
    const proposal = calibrationProposal();
    const approvedProposal = calibrationProposal({
      status: "approved",
      approved_at: "2026-07-21T01:08:00Z",
    });
    const initial = populatedResponse();
    const approved = populatedResponse();
    approved.profile.primary_preset = "income";
    const saved = populatedResponse();
    saved.profile.primary_preset = "growth";
    let profileGets = 0;
    const calls = apiRoutes({
      profile: initial,
      calibration: activeCalibration({ latest_proposal: proposal }),
      handle: (call) => {
        if (call.url.includes("/approve")) {
          return { profile: approved.profile, proposal: approvedProposal };
        }
        if (call.url.endsWith("/profile/investor") && call.method === "PUT") {
          return saved;
        }
        if (call.url.endsWith("/profile/investor") && call.method === "GET") {
          profileGets += 1;
          if (profileGets <= 2) return initial;
          return approved;
        }
        return undefined;
      },
    });
    await mount();
    await flush();
    await clickButton("Review proposal");
    await clickButton("Approve proposal");

    expect(host!.textContent).toContain("Income");
    await clickButton("Edit profile");
    await setControlValue(
      host!.querySelector<HTMLSelectElement>('select[name="primary_preset"]')!,
      "growth",
    );
    await clickButton("Save profile");

    expect(profileGets).toBe(3);
    expect(calls.find((call) => call.method === "PUT")?.body).toMatchObject({
      primary_preset: "growth",
    });
    expect(host!.textContent).toContain("Investor Profile summary");
    expect(host!.textContent).toContain("Growth");
    expect(host!.textContent).not.toContain("Income");
  });

  it("keeps successful reject authority across stale advisory GET responses", async () => {
    await useEnglish();
    const proposal = calibrationProposal();
    const rejectedProposal = calibrationProposal({
      status: "rejected",
      rejected_at: "2026-07-21T01:09:00Z",
    });
    const staleProfile = disabledResponse();
    let profileGets = 0;
    let calibrationGets = 0;
    const calls = apiRoutes({
      profile: populatedResponse(),
      calibration: activeCalibration({ latest_proposal: proposal }),
      handle: (call) => {
        if (call.url.includes("/reject")) return { proposal: rejectedProposal };
        if (call.url.endsWith("/profile/investor") && call.method === "GET") {
          profileGets += 1;
          return profileGets === 1 ? populatedResponse() : staleProfile;
        }
        if (call.url.endsWith("/profile/investor/calibration") && call.method === "GET") {
          calibrationGets += 1;
          return activeCalibration({ latest_proposal: proposal });
        }
        return undefined;
      },
    });
    await mount();
    await flush();
    await clickButton("Review proposal");
    await clickButton("Reject proposal");

    expect(profileGets).toBe(2);
    expect(calibrationGets).toBe(2);
    expect(host!.textContent).toContain("Investor Profile summary");
    expect(host!.textContent).toContain("Calibration proposal rejected");
    expect(host!.textContent).toContain("Event-driven");
    expect(host!.textContent).not.toContain("Personalization disabled");
    expect(host!.querySelector('[data-testid="summary-pending-proposal"]')).toBeNull();
    expect(calls.filter((call) => call.url.includes("/reject"))).toHaveLength(1);
  });

  it("keeps reject profile authority through failed and stale refreshes until corroborated", async () => {
    await useEnglish();
    const proposal = calibrationProposal();
    const rejectedProposal = calibrationProposal({
      status: "rejected",
      rejected_at: "2026-07-21T01:09:00Z",
    });
    const staleProfile = disabledResponse();
    const corroborated = populatedResponse();
    corroborated.effective_stance = "strict_risk_control";
    corroborated.context_preview = "SOURCE_REJECT_CORROBORATED_CONTEXT";
    let profileGets = 0;
    let calibrationGets = 0;
    const calls = apiRoutes({
      profile: populatedResponse(),
      calibration: activeCalibration({ latest_proposal: proposal }),
      handle: (call) => {
        if (call.url.includes("/reject")) return { proposal: rejectedProposal };
        if (call.url.endsWith("/profile/investor") && call.method === "GET") {
          profileGets += 1;
          if (profileGets === 1) return populatedResponse();
          if (profileGets === 2) {
            return new Response(JSON.stringify({ detail: "SOURCE_REJECT_REFRESH_FAILED" }), {
              status: 503,
              headers: { "content-type": "application/json" },
            });
          }
          if (profileGets === 3) return staleProfile;
          return corroborated;
        }
        if (call.url.endsWith("/profile/investor/calibration") && call.method === "GET") {
          calibrationGets += 1;
          return calibrationGets === 1
            ? activeCalibration({ latest_proposal: proposal })
            : activeCalibration({ latest_proposal: rejectedProposal });
        }
        return undefined;
      },
    });
    await mount();
    await flush();
    await clickButton("Review proposal");
    await clickButton("Reject proposal");

    expect(host!.textContent).toContain("Investor Profile summary");
    expect(host!.textContent).toContain("Event-driven");
    expect(host!.textContent).not.toContain("Effective AI stance");
    expect(host!.textContent).not.toContain(
      "The profile was saved, but the refreshed summary could not be loaded.",
    );
    expect(host!.querySelector('[role="alert"]')?.textContent)
      .toContain("Could not refresh status.");
    expect(host!.textContent).not.toContain("SOURCE_REJECT_REFRESH_FAILED");
    await clickButton("Retry");

    expect(profileGets).toBe(3);
    expect(host!.textContent).toContain("Event-driven");
    expect(host!.textContent).not.toContain("Personalization disabled");
    expect(host!.textContent).not.toContain("Effective AI stance");
    await clickButton("Retry");

    expect(profileGets).toBe(4);
    expect(host!.textContent).toContain("Event-driven");
    expect(host!.textContent).toContain("Strict risk control");
    expect(host!.textContent).toContain("SOURCE_REJECT_CORROBORATED_CONTEXT");
    expect(calls.filter((call) => call.url.includes("/reject"))).toHaveLength(1);
  });

  it("renders localized field diffs and source rationales then approves without patch", async () => {
    await useEnglish();
    const proposal = calibrationProposal({
      proposed_fields: ["concentration_limit_pct", "risk_capacity"],
    });
    const approvedProfile = populatedResponse().profile;
    approvedProfile.primary_preset = "income";
    approvedProfile.risk_capacity = 6;
    const refreshedProfile = populatedResponse();
    refreshedProfile.profile = { ...approvedProfile };
    refreshedProfile.effective_stance = "strict_risk_control";
    refreshedProfile.context_preview = "SOURCE_REFRESHED_CONTEXT";
    let calibrationGets = 0;
    let profileGets = 0;
    const calls = apiRoutes({
      profile: populatedResponse(),
      calibration: activeCalibration({ latest_proposal: proposal }),
      handle: (call) => {
        if (call.url.endsWith("/profile/investor/calibration") && call.method === "GET") {
          calibrationGets += 1;
          return calibrationGets === 1
            ? activeCalibration({ latest_proposal: proposal })
            : emptyCalibration();
        }
        if (call.url.includes("/approve")) {
          return { profile: approvedProfile, proposal: { ...proposal, status: "approved" } };
        }
        if (call.url.endsWith("/profile/investor") && call.method === "GET") {
          profileGets += 1;
          return profileGets === 1 ? populatedResponse() : refreshedProfile;
        }
        return undefined;
      },
    });
    await mount();
    await flush();
    await clickButton("Review proposal");
    const text = host!.textContent ?? "";
    expect(text.indexOf("Single-position limit %")).toBeLessThan(text.indexOf("Risk capacity (1-10)"));
    expect(text).toContain("Current25");
    expect(text).toContain("Proposed18");
    expect(text).toContain("SOURCE_CONCENTRATION_RATIONALE");
    await clickButton("Approve proposal");

    const approve = calls.find((call) => call.url.includes("/approve"));
    expect(approve?.body).toEqual({});
    expect(approve?.body).not.toHaveProperty("profile_patch");
    expect(host!.textContent).toContain("Investor Profile summary");
    expect(host!.textContent).toContain("Income");
    expect(host!.textContent).toContain("Strict risk control");
    expect(host!.textContent).toContain("SOURCE_REFRESHED_CONTEXT");
    expect(calls.filter((call) => call.url.endsWith("/profile/investor") && call.method === "GET"))
      .toHaveLength(2);
  });

  it("keeps conflicted proposal pending with approval disabled", async () => {
    await useEnglish();
    const conflictProposal = calibrationProposal({
      conflict_fields: ["risk_capacity"],
      conflicted_at: "2026-07-21T01:05:00Z",
    });
    let calibrationGets = 0;
    let profileGets = 0;
    const refreshedProfile = populatedResponse();
    refreshedProfile.profile.risk_capacity = 9;
    apiRoutes({
      profile: populatedResponse(),
      calibration: activeCalibration({ latest_proposal: calibrationProposal() }),
      handle: (call) => {
        if (call.url.includes("/approve")) {
          return new Response(JSON.stringify({
            detail: { code: "proposal_conflict", diagnostic: "SOURCE_CONFLICT_SECRET" },
          }), {
            status: 409,
            headers: { "content-type": "application/json" },
          });
        }
        if (call.url.endsWith("/profile/investor/calibration") && call.method === "GET") {
          calibrationGets += 1;
          return calibrationGets === 1
            ? activeCalibration({ latest_proposal: calibrationProposal() })
            : activeCalibration({ latest_proposal: conflictProposal });
        }
        if (call.url.endsWith("/profile/investor") && call.method === "GET") {
          profileGets += 1;
          return profileGets === 1 ? populatedResponse() : refreshedProfile;
        }
        return undefined;
      },
    });
    await mount();
    await flush();
    await clickButton("Review proposal");
    await clickButton("Approve proposal");
    expect(host!.textContent).toContain("Proposal review");
    expect(host!.textContent).toContain("Profile changed since this proposal was created");
    expect(host!.textContent).toContain("Current9");
    expect(host!.textContent).not.toContain("Current4");
    expect(host!.textContent).not.toContain("SOURCE_CONFLICT_SECRET");
    expect((await buttonByText("Approve proposal")).disabled).toBe(true);
    expect((await buttonByText("Reject proposal")).disabled).toBe(false);

    dispose();
    let failedRefreshProfileGets = 0;
    let failedRefreshCalibrationGets = 0;
    apiRoutes({
      profile: populatedResponse(),
      calibration: activeCalibration({ latest_proposal: calibrationProposal() }),
      handle: (call) => {
        if (call.url.includes("/approve")) {
          return new Response(JSON.stringify({ detail: { code: "proposal_conflict" } }), {
            status: 409,
            headers: { "content-type": "application/json" },
          });
        }
        if (call.url.endsWith("/profile/investor") && call.method === "GET") {
          failedRefreshProfileGets += 1;
          if (failedRefreshProfileGets > 1) {
            return new Response(JSON.stringify({ detail: "SOURCE_CONFLICT_REFRESH_SECRET" }), {
              status: 503,
              headers: { "content-type": "application/json" },
            });
          }
        }
        if (call.url.endsWith("/profile/investor/calibration") && call.method === "GET") {
          failedRefreshCalibrationGets += 1;
          return failedRefreshCalibrationGets === 1
            ? activeCalibration({ latest_proposal: calibrationProposal() })
            : activeCalibration({ latest_proposal: conflictProposal });
        }
        return undefined;
      },
    });
    await mount();
    await flush();
    await clickButton("Review proposal");
    await clickButton("Approve proposal");
    expect(host!.textContent).toContain(
      "Could not load the Investor Profile.",
    );
    expect(host!.textContent).not.toContain("Profile changed since this proposal was created");
    expect(host!.querySelectorAll('[data-testid="proposal-current-value"]')).toHaveLength(0);
    expect(host!.textContent).not.toContain("SOURCE_CONFLICT_REFRESH_SECRET");
  });

  it("preserves confirmed conflict across a stale non-conflicted draft", async () => {
    await useEnglish();
    const proposal = calibrationProposal();
    let calibrationGets = 0;
    apiRoutes({
      profile: populatedResponse(),
      calibration: activeCalibration({ latest_proposal: proposal }),
      handle: (call) => {
        if (call.url.includes("/approve")) {
          return new Response(JSON.stringify({
            detail: { code: "proposal_conflict", diagnostic: "SOURCE_CONFIRMED_CONFLICT" },
          }), {
            status: 409,
            headers: { "content-type": "application/json" },
          });
        }
        if (call.url.endsWith("/profile/investor/calibration") && call.method === "GET") {
          calibrationGets += 1;
          return activeCalibration({ latest_proposal: proposal });
        }
        return undefined;
      },
    });
    await mount();
    await flush();
    await clickButton("Review proposal");
    await clickButton("Approve proposal");

    expect(calibrationGets).toBe(2);
    expect(host!.textContent).toContain("Proposal review");
    expect(host!.textContent).toContain("Profile changed since this proposal was created");
    expect(host!.textContent).not.toContain("SOURCE_CONFIRMED_CONFLICT");
    expect((await buttonByText("Approve proposal")).disabled).toBe(true);
    expect((await buttonByText("Reject proposal")).disabled).toBe(false);
  });

  it("routes calibration provider recovery to the Providers anchor", async () => {
    await useEnglish();
    const navigate = vi.fn();
    const failedTurn = activeCalibration({
      pending_turn: calibrationTurn({
        id: "turn-provider-missing",
        status: "failed",
        error_code: "provider_config_missing",
      }),
    });
    let providerCalibrationGets = 0;
    const providerCalls = apiRoutes({
      profile: populatedResponse(),
      calibration: activeCalibration(),
      handle: (call) => {
        if (call.url.endsWith("/profile/investor/calibration") && call.method === "GET") {
          providerCalibrationGets += 1;
          return providerCalibrationGets === 1 ? activeCalibration() : failedTurn;
        }
        if (call.url.endsWith("/calibration/messages")) {
          return new Response(JSON.stringify({
            detail: {
              code: "provider_config_missing",
              diagnostic: "sk-proj-SOURCE_PROVIDER_SECRET",
            },
          }), {
            status: 400,
            headers: { "content-type": "application/json" },
          });
        }
        if (call.url.includes("/turns/turn-provider-missing/retry")) {
          return activeCalibration();
        }
        return undefined;
      },
    });
    await mount(false, {
      onNavigateToProviders: navigate,
      turnIdFactory: () => "turn-provider-missing",
    });
    await flush();
    await clickButton("Continue Calibration");
    await setControlValue(
      host!.querySelector<HTMLTextAreaElement>('textarea[name="calibration_answer"]')!,
      "SOURCE_PROVIDER_ANSWER",
    );
    await clickButton("Send answer");
    expect(providerCalibrationGets).toBe(2);
    expect(host!.textContent).toContain("Configure an AI provider before continuing calibration.");
    expect(host!.textContent).not.toContain("sk-proj-SOURCE_PROVIDER_SECRET");
    expect((await buttonByText("Send answer")).disabled).toBe(true);
    expect((await buttonByText("Propose Now")).disabled).toBe(true);
    await clickButton("Provider Sign-in and Credentials");
    expect(navigate).toHaveBeenCalledTimes(1);
    await clickButton("Retry turn");
    expect(providerCalls.filter((call) =>
      call.url.includes("/turns/turn-provider-missing/retry"))).toHaveLength(1);
    expect(providerCalls.filter((call) => call.url.endsWith("/calibration/messages")))
      .toHaveLength(1);
  });
});
