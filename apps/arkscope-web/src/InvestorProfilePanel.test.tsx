/** @vitest-environment jsdom */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import i18n from "i18next";
import { afterEach, describe, expect, it, vi } from "vitest";

import { InvestorProfilePanel } from "./InvestorProfilePanel";
import type { CalibrationProposal, CalibrationState, InvestorProfileResponse } from "./api";

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

const populatedCalibration = (): CalibrationState => ({
  active_session: {
    id: "session-source-1",
    status: "active",
    created_at: "2026-07-21T01:00:00Z",
    updated_at: "2026-07-21T01:01:00Z",
    closed_at: null,
  },
  sessions: [{
    id: "session-source-1",
    status: "active",
    created_at: "2026-07-21T01:00:00Z",
    updated_at: "2026-07-21T01:01:00Z",
    closed_at: null,
  }],
  messages: [
    {
      id: "message-source-user",
      session_id: "session-source-1",
      role: "user",
      content: "SOURCE_USER_MESSAGE",
      created_at: "2026-07-21T01:00:00Z",
    },
    {
      id: "message-source-assistant",
      session_id: "session-source-1",
      role: "assistant",
      content: "SOURCE_ASSISTANT_MESSAGE",
      created_at: "2026-07-21T01:01:00Z",
    },
  ],
  latest_proposal: {
    id: "proposal-source-1",
    session_id: "session-source-1",
    status: "draft",
    profile_patch: {
      risk_appetite: 9,
      risk_capacity: 3,
      risk_mismatch: "appetite_above_capacity",
      default_stance: "valuation_rationalist",
    },
    raw_profile_patch: {
      risk_appetite: 9,
      risk_capacity: 3,
      default_stance: "valuation_rationalist",
    },
    rationales: {
      risk_capacity: "SOURCE_PROPOSAL_RATIONALE",
    },
    changed_fields: ["risk_appetite", "risk_capacity", "default_stance"],
    created_at: "2026-07-21T01:02:00Z",
    approved_at: null,
    rejected_at: null,
  },
});

type PanelApiResponse =
  | InvestorProfileResponse
  | CalibrationState
  | { profile: InvestorProfileResponse["profile"]; proposal: Partial<CalibrationProposal> }
  | { proposal: Partial<CalibrationProposal> };

function stubFetch(handler: (url: string, init?: RequestInit) => PanelApiResponse) {
  const calls: Array<{ url: string; method: string; body: unknown }> = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: unknown, init?: RequestInit) => {
      const u = String(url);
      calls.push({
        url: u,
        method: init?.method ?? "GET",
        body: init?.body ? JSON.parse(String(init.body)) : null,
      });
      return new Response(JSON.stringify(handler(u, init)), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }),
  );
  return calls;
}

async function mount(developerMode = false) {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(<InvestorProfilePanel developerMode={developerMode} />);
  });
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

describe("InvestorProfilePanel", () => {
  it("pending_profile_request_uses_loading_state_not_bare_text", async () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(() => {})));
    await mount();
    expect(host!.querySelector('[data-state="loading"]')?.textContent).toContain("載入投資人設定");
  });

  it("request_failure_uses_alert_semantics", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => {
      throw new Error("profile request failed");
    }));
    await mount();
    await flush();
    expect(host!.querySelector('[role="alert"]')?.textContent).toBe("要求失敗，請稍後再試。");
  });

  it("loads_default_disabled_profile", async () => {
    const calls = stubFetch(() => disabledResponse());
    await mount();
    expect(calls[0].url).toContain("/profile/investor");
    expect(calls[0].method).toBe("GET");
    const checkbox = host!.querySelector<HTMLInputElement>("input[type=checkbox]");
    expect(checkbox?.checked).toBe(false);
    expect(host!.textContent).toContain("投資人設定");
    expect(host!.textContent).toContain(
      "啟用後,助手依你的風險輪廓與所選立場調整分析重點;證據蒐集與反方論點完全不受影響。",
    );
    expect(host!.textContent).toContain("技能模式:off(技能建議屬後續階段,尚未啟用)");
    expect(Array.from(host!.querySelectorAll('option[value=""]'), (option) => option.textContent))
      .toEqual(["未設定", "未設定"]);
    for (const expected of [
      "啟用個人化(目前生效立場:關閉)",
      "風險承受能力(1-10)",
      "想避開的(逗號分隔)",
      "行為傾向(供助手校準,非診斷)",
      "自由描述(目標、自我觀察、想被怎麼協助)",
    ]) {
      expect.soft(host!.textContent).toContain(expected);
    }
  });

  it("disabled_profile_shows_effective_off", async () => {
    stubFetch(() => disabledResponse());
    await mount();
    expect(host!.textContent).toContain("關閉"); // effective stance off label
  });

  it("draft_button_posts_profile_without_saving", async () => {
    const calls = stubFetch((url) => {
      const resp = disabledResponse();
      if (url.endsWith("/draft")) {
        resp.profile.enabled = true;
        resp.profile.risk_appetite = 8;
        resp.profile.risk_capacity = 4;
        resp.profile.risk_mismatch = "appetite_above_capacity";
      }
      return resp;
    });
    await mount();
    const draftBtn = Array.from(host!.querySelectorAll("button")).find((b) =>
      b.textContent?.includes("產生設定草稿"),
    )!;
    await act(async () => {
      draftBtn.click();
    });
    const draftCall = calls.find((c) => c.url.endsWith("/profile/investor/draft"));
    expect(draftCall?.method).toBe("POST");
    expect(calls.some((c) => c.method === "PUT")).toBe(false);
    expect(host!.textContent).toContain("風險意願高於承受能力");
    expect(host!.textContent).toContain("風險意願(1-10)");
    expect(host!.textContent).toContain("風險意願與風險承受能力:");
    expect(host!.textContent).not.toContain("風險胃納");
    expect(host!.querySelector('[data-state="ready"]')?.textContent)
      .toBe("草稿已產生(未儲存)");
  });

  it("save_button_puts_profile", async () => {
    const calls = stubFetch((url, init) => {
      const resp = disabledResponse();
      if (init?.method === "PUT") {
        resp.profile.enabled = true;
        resp.effective_stance = "complementary";
        resp.trace.profile_active = true;
        resp.trace.assistant_stance = "complementary";
      }
      return resp;
    });
    await mount();
    const saveBtn = await buttonByText("儲存設定");
    await act(async () => {
      saveBtn.click();
    });
    const putCall = calls.find((c) => c.method === "PUT");
    expect(putCall?.url).toContain("/profile/investor");
    expect(host!.textContent).toContain("互補投資人");
    expect(host!.querySelector('[data-state="ready"]')?.textContent).toContain("已儲存");
  });

  it("shows_a_running_state_while_a_profile_mutation_is_pending", async () => {
    let finishSave: ((response: Response) => void) | null = null;
    vi.stubGlobal(
      "fetch",
      vi.fn((url: unknown, init?: RequestInit) => {
        const target = String(url);
        if (target.endsWith("/profile/investor") && init?.method === "PUT") {
          return new Promise<Response>((resolve) => {
            finishSave = resolve;
          });
        }
        const body = target.endsWith("/profile/investor/calibration")
          ? { active_session: null, sessions: [], messages: [], latest_proposal: null }
          : disabledResponse();
        return Promise.resolve(new Response(JSON.stringify(body), {
          status: 200,
          headers: { "content-type": "application/json" },
        }));
      }),
    );
    await mount();
    await flush();

    const saveBtn = await buttonByText("儲存設定");
    await act(async () => saveBtn.click());

    expect(host!.querySelector(".investor-profile-panel")?.getAttribute("aria-busy")).toBe("true");
    expect(host!.querySelector('[data-state="running"]')?.textContent)
      .toBe("正在更新投資人設定");

    await act(async () => {
      finishSave?.(new Response(JSON.stringify(disabledResponse()), {
        status: 200,
        headers: { "content-type": "application/json" },
      }));
      await Promise.resolve();
    });
    await flush();
  });

  it("starts_calibration_sends_message_and_shows_proposal_rationale", async () => {
    let finishInitialCalibration: ((response: Response) => void) | null = null;
    const session: CalibrationState["active_session"] = {
      id: "s1",
      status: "active",
      created_at: "t",
      updated_at: "t",
      closed_at: null,
    };
    const actionState: CalibrationState = {
      active_session: session,
      sessions: [session!],
      messages: [],
      latest_proposal: null,
    };
    const proposalState: CalibrationState = {
      active_session: session,
      sessions: [session!],
      messages: [
        { id: "m1", session_id: "s1", role: "user", content: "I chase AI stocks.", created_at: "t" },
        { id: "m2", session_id: "s1", role: "assistant", content: "Draft ready.", created_at: "t" },
      ],
      latest_proposal: {
        id: "p1",
        session_id: "s1",
        status: "draft",
        profile_patch: {
          enabled: true,
          risk_appetite: 8,
          risk_capacity: 4,
          risk_mismatch: "appetite_above_capacity",
          default_stance: "complementary",
        },
        raw_profile_patch: { enabled: true, risk_appetite: 8, risk_capacity: 4, default_stance: "complementary" },
        rationales: { risk_capacity: "User said 10% drawdown would likely trigger selling." },
        changed_fields: [],
        created_at: "t",
        approved_at: null,
        rejected_at: null,
      },
    };
    vi.stubGlobal("fetch", vi.fn((url: unknown, init?: RequestInit) => {
      const target = String(url);
      const method = init?.method ?? "GET";
      if (target.endsWith("/profile/investor") && method === "GET") {
        return Promise.resolve(new Response(JSON.stringify(disabledResponse()), {
          status: 200,
          headers: { "content-type": "application/json" },
        }));
      }
      if (target.endsWith("/profile/investor/calibration") && method === "GET") {
        return new Promise<Response>((resolveRequest) => {
          finishInitialCalibration = resolveRequest;
        });
      }
      const body = target.endsWith("/profile/investor/calibration/messages")
        ? proposalState
        : actionState;
      return Promise.resolve(new Response(JSON.stringify(body), {
        status: 200,
        headers: { "content-type": "application/json" },
      }));
    }));
    await mount();
    await flush();

    const startBtn = await buttonByText("開始校準對話");
    await act(async () => {
      startBtn.click();
    });
    const startOutcome = Array.from(host!.querySelectorAll('[data-state="ready"]'))
      .map((node) => node.textContent ?? "")
      .find((text) => text.includes("校準"));
    const textarea = host!.querySelector<HTMLTextAreaElement>('textarea[aria-label="校準訊息"]')!;
    await act(async () => {
      const setter = Object.getOwnPropertyDescriptor(
        window.HTMLTextAreaElement.prototype,
        "value",
      )!.set!;
      setter.call(textarea, "I chase AI stocks.");
      textarea.dispatchEvent(new Event("input", { bubbles: true }));
    });
    const sendBtn = await buttonByText("送出校準訊息");
    await act(async () => {
      sendBtn.click();
    });
    const updatedOutcome = Array.from(host!.querySelectorAll('[data-state="ready"]'))
      .map((node) => node.textContent ?? "")
      .find((text) => text.includes("校準"));

    const staleInitial: CalibrationState = {
      active_session: null,
      sessions: [],
      messages: [{
        id: "stale-initial",
        session_id: "stale-session",
        role: "assistant",
        content: "STALE_INITIAL_CALIBRATION",
        created_at: "t0",
      }],
      latest_proposal: null,
    };
    await act(async () => {
      finishInitialCalibration?.(new Response(JSON.stringify(staleInitial), {
        status: 200,
        headers: { "content-type": "application/json" },
      }));
      await Promise.resolve();
    });
    await flush();

    expect(startOutcome).toContain("校準對話已開始");
    expect(updatedOutcome).toContain("校準回覆已更新");
    expect(host!.textContent).toContain("Draft ready.");
    expect(host!.textContent).toContain("User said 10% drawdown");
    expect(host!.textContent).toContain("風險承受能力");
    expect(host!.textContent).not.toContain("STALE_INITIAL_CALIBRATION");
    expect(host!.textContent).toContain(
      "校準對話只用來整理投資人輪廓,不是投資建議或個股推薦。只有你核准的結構化設定會影響研究;原始對話不會進入研究 prompt。",
    );
    expect(host!.querySelector('[data-state="partial"]')?.textContent).toBe("待核准校準提案");
    expect(await buttonByText("套用校準提案")).toBeTruthy();

    dispose();
    const sendFailure = "PLANTED_CURRENT_SEND_FAILURE";
    vi.stubGlobal("fetch", vi.fn(async (url: unknown, init?: RequestInit) => {
      const target = String(url);
      const method = init?.method ?? "GET";
      if (target.endsWith("/profile/investor") && method === "GET") {
        return new Response(JSON.stringify(disabledResponse()), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      if (target.endsWith("/profile/investor/calibration") && method === "GET") {
        return new Response(JSON.stringify(actionState), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      if (target.endsWith("/profile/investor/calibration/messages")) {
        throw new Error(sendFailure);
      }
      throw new Error(`unexpected request: ${method} ${target}`);
    }));
    await mount(true);
    await flush();
    await flush();

    const failedDraft = host!.querySelector<HTMLTextAreaElement>(
      'textarea[aria-label="校準訊息"]',
    )!;
    await act(async () => {
      const setter = Object.getOwnPropertyDescriptor(
        window.HTMLTextAreaElement.prototype,
        "value",
      )!.set!;
      setter.call(failedDraft, "SOURCE_FAILED_SEND_DRAFT");
      failedDraft.dispatchEvent(new Event("input", { bubbles: true }));
    });
    const failedSend = await buttonByText("送出校準訊息");
    await act(async () => { failedSend.click(); });
    await flush();

    expect.soft(failedDraft.value).toBe("");
    expect(host!.querySelector('[role="alert"]')?.textContent).toBe("要求失敗，請稍後再試。");
    expect(host!.querySelector('[data-testid="developer-diagnostics"]')?.textContent).toContain(sendFailure);

    dispose();
    const deferredMessages: Array<{
      resolve: (response: Response) => void;
      reject: (error: Error) => void;
    }> = [];
    vi.stubGlobal("fetch", vi.fn((url: unknown, init?: RequestInit) => {
      const target = String(url);
      const method = init?.method ?? "GET";
      if (target.endsWith("/profile/investor") && method === "GET") {
        return Promise.resolve(new Response(JSON.stringify(disabledResponse()), {
          status: 200,
          headers: { "content-type": "application/json" },
        }));
      }
      if (target.endsWith("/profile/investor/calibration") && method === "GET") {
        return Promise.resolve(new Response(JSON.stringify(actionState), {
          status: 200,
          headers: { "content-type": "application/json" },
        }));
      }
      if (target.endsWith("/profile/investor/calibration/messages")) {
        return new Promise<Response>((resolveRequest, rejectRequest) => {
          deferredMessages.push({ resolve: resolveRequest, reject: rejectRequest });
        });
      }
      return Promise.reject(new Error(`unexpected request: ${method} ${target}`));
    }));
    await mount(true);
    await flush();
    await flush();

    const doubleDraft = host!.querySelector<HTMLTextAreaElement>(
      'textarea[aria-label="校準訊息"]',
    )!;
    const setDoubleDraft = async (value: string) => {
      await act(async () => {
        const setter = Object.getOwnPropertyDescriptor(
          window.HTMLTextAreaElement.prototype,
          "value",
        )!.set!;
        setter.call(doubleDraft, value);
        doubleDraft.dispatchEvent(new Event("input", { bubbles: true }));
      });
    };
    await setDoubleDraft("SOURCE_DOUBLE_SEND_SUCCESS");
    const doubleSend = await buttonByText("送出校準訊息");
    await act(async () => {
      doubleSend.click();
      doubleSend.click();
    });
    expect(deferredMessages).toHaveLength(2);

    const staleSuccess: CalibrationState = {
      ...actionState,
      messages: [{
        id: "stale-double-success",
        session_id: "s1",
        role: "assistant",
        content: "STALE_DOUBLE_SUCCESS",
        created_at: "t",
      }],
    };
    await act(async () => {
      deferredMessages[0]!.resolve(new Response(JSON.stringify(staleSuccess), {
        status: 200,
        headers: { "content-type": "application/json" },
      }));
      await Promise.resolve();
    });
    await flush();
    expect(host!.querySelector(".investor-profile-panel")?.getAttribute("aria-busy")).toBe("true");
    expect(doubleDraft.value).toBe("SOURCE_DOUBLE_SEND_SUCCESS");
    expect(host!.textContent).not.toContain("STALE_DOUBLE_SUCCESS");
    expect(host!.querySelector('[role="alert"]')).toBeNull();

    const latestSuccess: CalibrationState = {
      ...actionState,
      messages: [{
        id: "latest-double-success",
        session_id: "s1",
        role: "assistant",
        content: "LATEST_DOUBLE_SUCCESS",
        created_at: "t",
      }],
    };
    await act(async () => {
      deferredMessages[1]!.resolve(new Response(JSON.stringify(latestSuccess), {
        status: 200,
        headers: { "content-type": "application/json" },
      }));
      await Promise.resolve();
    });
    await flush();
    expect(host!.querySelector(".investor-profile-panel")?.getAttribute("aria-busy")).toBe("false");
    expect(doubleDraft.value).toBe("");
    expect(host!.textContent).toContain("LATEST_DOUBLE_SUCCESS");
    expect(host!.querySelector('[data-state="ready"]')?.textContent).toBe("校準回覆已更新");

    await setDoubleDraft("SOURCE_DOUBLE_SEND_ERROR");
    await act(async () => {
      doubleSend.click();
      doubleSend.click();
    });
    expect(deferredMessages).toHaveLength(4);
    await act(async () => {
      deferredMessages[2]!.reject(new Error("STALE_DOUBLE_ERROR"));
      await Promise.resolve();
    });
    await flush();
    expect(host!.querySelector(".investor-profile-panel")?.getAttribute("aria-busy")).toBe("true");
    expect(doubleDraft.value).toBe("SOURCE_DOUBLE_SEND_ERROR");
    expect(host!.querySelector('[role="alert"]')).toBeNull();
    expect(host!.textContent).not.toContain("STALE_DOUBLE_ERROR");

    const latestAfterStaleError: CalibrationState = {
      ...actionState,
      messages: [{
        id: "latest-after-stale-error",
        session_id: "s1",
        role: "assistant",
        content: "LATEST_AFTER_STALE_ERROR",
        created_at: "t",
      }],
    };
    await act(async () => {
      deferredMessages[3]!.resolve(new Response(JSON.stringify(latestAfterStaleError), {
        status: 200,
        headers: { "content-type": "application/json" },
      }));
      await Promise.resolve();
    });
    await flush();
    expect(host!.querySelector(".investor-profile-panel")?.getAttribute("aria-busy")).toBe("false");
    expect(doubleDraft.value).toBe("");
    expect(host!.textContent).toContain("LATEST_AFTER_STALE_ERROR");
    expect(host!.textContent).not.toContain("STALE_DOUBLE_ERROR");
    expect(host!.querySelector('[data-state="ready"]')?.textContent).toBe("校準回覆已更新");
  });

  it("approves_calibration_proposal_through_dedicated_endpoint", async () => {
    const approvedResponse = disabledResponse();
    approvedResponse.profile = {
      ...approvedResponse.profile,
      enabled: true,
      primary_preset: "income",
      risk_appetite: 6,
      risk_capacity: 5,
      freeform_notes: "SOURCE_APPROVED_PROFILE",
    };
    approvedResponse.effective_stance = "complementary";
    approvedResponse.trace.profile_active = true;
    approvedResponse.trace.assistant_stance = "complementary";
    const refreshFailure = "PLANTED_APPROVED_REFRESH_FAILURE";
    let approved = false;
    let failedApprovedRefresh = false;
    const calls = stubFetch((url) => {
      if (url.includes("/profile/investor/calibration/proposals/p1/approve")) {
        approved = true;
        return {
          profile: approvedResponse.profile,
          proposal: { id: "p1", status: "approved", approved_at: "t" },
        };
      }
      if (url.includes("/profile/investor/calibration/proposals/p1/reject")) {
        return { proposal: { id: "p1", status: "rejected", rejected_at: "t" } };
      }
      if (url.endsWith("/profile/investor/calibration/sessions")) {
        return {
          active_session: { id: "s1", status: "active", created_at: "t", updated_at: "t", closed_at: null },
          sessions: [{ id: "s1", status: "active", created_at: "t", updated_at: "t", closed_at: null }],
          messages: [],
          latest_proposal: null,
        };
      }
      if (url.endsWith("/profile/investor/calibration/messages")) {
        return {
          active_session: { id: "s1", status: "active", created_at: "t", updated_at: "t", closed_at: null },
          sessions: [{ id: "s1", status: "active", created_at: "t", updated_at: "t", closed_at: null }],
          messages: [
            { id: "m1", session_id: "s1", role: "user", content: "I chase AI stocks.", created_at: "t" },
            { id: "m2", session_id: "s1", role: "assistant", content: "Draft ready.", created_at: "t" },
          ],
          latest_proposal: {
            id: "p1",
            session_id: "s1",
            status: "draft",
            profile_patch: { enabled: true, risk_appetite: 8, risk_capacity: 4, default_stance: "complementary" },
            raw_profile_patch: {},
            rationales: {},
            changed_fields: [],
            created_at: "t",
            approved_at: null,
            rejected_at: null,
          },
        };
      }
      if (url.endsWith("/profile/investor/calibration")) {
        if (approved && !failedApprovedRefresh) {
          failedApprovedRefresh = true;
          throw new Error(refreshFailure);
        }
        return {
          active_session: null,
          sessions: [],
          messages: [],
          latest_proposal: null,
        };
      }
      if (url.endsWith("/profile/investor")) {
        return approved ? approvedResponse : disabledResponse();
      }
      return disabledResponse();
    });
    await mount(true);
    await flush();
    await flush();
    expect(calls.some((c) => c.url.endsWith("/profile/investor/calibration"))).toBe(true);
    const startBtn = await buttonByText("開始校準對話");
    await act(async () => {
      startBtn.click();
    });
    const textarea = host!.querySelector<HTMLTextAreaElement>('textarea[aria-label="校準訊息"]')!;
    await act(async () => {
      const setter = Object.getOwnPropertyDescriptor(
        window.HTMLTextAreaElement.prototype,
        "value",
      )!.set!;
      setter.call(textarea, "I chase AI stocks.");
      textarea.dispatchEvent(new Event("input", { bubbles: true }));
    });
    const sendBtn = await buttonByText("送出校準訊息");
    await act(async () => {
      sendBtn.click();
    });
    const approveBtn = await buttonByText("套用");
    await act(async () => {
      approveBtn.click();
    });
    await flush();

    const approve = calls.find((c) => c.url.includes("/proposals/p1/approve"));
    expect(approve).toBeTruthy();
    expect(approve?.method).toBe("POST");
    const approvedSelects = host!.querySelectorAll<HTMLSelectElement>(".ip-grid select");
    expect.soft(approvedSelects[0]?.value).toBe("income");
    expect.soft(approvedSelects[1]?.value).toBe("6");
    expect.soft(approvedSelects[2]?.value).toBe("5");
    expect.soft(host!.querySelectorAll<HTMLTextAreaElement>("textarea")[0]?.value)
      .toBe("SOURCE_APPROVED_PROFILE");
    expect.soft(host!.textContent).toContain("互補投資人");
    expect(host!.querySelector('[role="alert"]')?.textContent).toBe("要求失敗，請稍後再試。");
    expect(host!.querySelector('[data-testid="developer-diagnostics"]')?.textContent).toContain(refreshFailure);

    const rejectBtn = await buttonByText("拒絕提案");
    await act(async () => { rejectBtn.click(); });
    await flush();

    const reject = calls.find((c) => c.url.includes("/proposals/p1/reject"));
    expect(reject?.method).toBe("POST");
    expect(host!.querySelector('[data-state="ready"]')?.textContent).toBe("校準提案已拒絕");
    expect(host!.querySelectorAll<HTMLTextAreaElement>("textarea")[0]?.value)
      .toBe("SOURCE_APPROVED_PROFILE");
  });

  it("renders every current Investor Profile field in English", async () => {
    const response = populatedResponse();
    const calibration = populatedCalibration();
    stubFetch((url) => url.endsWith("/profile/investor/calibration") ? calibration : response);
    await act(async () => { await i18n.changeLanguage("en"); });
    await mount();
    await flush();
    await flush();

    const text = host!.textContent ?? "";
    for (const expected of [
      "Investor Profile",
      "Research personalization aid, not investment advice or a suitability assessment. When enabled, the assistant adjusts its analytical focus based on your risk profile and selected stance; evidence gathering and counterarguments remain completely unaffected.",
      "Enable personalization (current effective stance: Complementary)",
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
      "Skill mode: off (skill recommendations are a later phase and are not yet enabled)",
      "Calibration Conversation",
      "Calibration conversations only organize your investor profile; they are not investment advice or individual-stock recommendations. Only structured settings you approve affect research; raw conversation transcripts are not included in research prompts.",
      "Start calibration conversation",
      "Calibration message",
      "Send calibration message",
      "Calibration Proposal",
      "Calibration proposal awaiting approval",
      "Apply calibration proposal",
      "Reject proposal",
      "Generate settings draft",
      "Save settings",
      "Risk appetite and risk capacity:",
      "Risk appetite above capacity",
    ]) {
      expect.soft(text).toContain(expected);
    }

    const optionLabels = Array.from(host!.querySelectorAll("option"), (option) => option.textContent);
    for (const expected of [
      "Growth investor (default)",
      "Value",
      "Momentum",
      "Income",
      "Event-driven",
      "Balanced",
      "Custom",
      "Intraday",
      "Days to weeks",
      "Months",
      "Multi-year",
      "Mixed",
      "Neutral",
      "Investor-aligned",
      "Complementary",
      "Strict risk control",
      "Valuation rationalist",
      "Growth opportunity",
    ]) {
      expect.soft(optionLabels).toContain(expected);
    }
    expect.soft(optionLabels.filter((label) => label === "Not set")).toHaveLength(2);

    const proposalHeading = host!.querySelector(".ip-calibration .ip-guardrail strong");
    expect.soft(proposalHeading?.querySelector('[data-state="partial"]')?.textContent)
      .toBe("Calibration proposal awaiting approval");
    expect.soft(proposalHeading?.textContent?.match(/Calibration Proposal/g) ?? []).toHaveLength(1);

    const source = readFileSync(resolve(import.meta.dirname, "InvestorProfilePanel.tsx"), "utf8");
    for (const helper of [
      "settingsInvestorPresetLabel",
      "settingsInvestorHorizonLabel",
      "settingsStanceLabel",
      "settingsMismatchLabel",
    ]) {
      expect.soft(source).toContain(helper);
    }
    expect.soft(source).not.toContain("personalizationDisplay");
  });

  it("switches locale without changing draft calibration or proposal state", async () => {
    const response = populatedResponse();
    const calibration = populatedCalibration();
    const calls: Array<{ url: string; method: string; body: unknown }> = [];
    let finishInitialCalibration: ((value: Response) => void) | null = null;
    let finishDraft: ((value: Response) => void) | null = null;
    vi.stubGlobal("fetch", vi.fn((url: unknown, init?: RequestInit) => {
      const target = String(url);
      calls.push({
        url: target,
        method: init?.method ?? "GET",
        body: init?.body ? JSON.parse(String(init.body)) : null,
      });
      if (target.endsWith("/profile/investor/draft")) {
        return new Promise<Response>((resolveRequest) => {
          finishDraft = resolveRequest;
        });
      }
      if (target.endsWith("/profile/investor/calibration")) {
        return new Promise<Response>((resolveRequest) => {
          finishInitialCalibration = resolveRequest;
        });
      }
      return Promise.resolve(new Response(JSON.stringify(response), {
        status: 200,
        headers: { "content-type": "application/json" },
      }));
    }));

    await mount();
    await flush();

    const queryControls = () => {
      const selects = Array.from(host!.querySelectorAll<HTMLSelectElement>(".ip-grid select"));
      const numbers = Array.from(
        host!.querySelectorAll<HTMLInputElement>('.ip-grid input[type="number"]'),
      );
      const fieldsets = host!.querySelectorAll("fieldset");
      return {
        enabled: host!.querySelector<HTMLInputElement>('.ip-toggle input[type="checkbox"]')!,
        selects,
        numbers,
        edges: Array.from(
          fieldsets[0]!.querySelectorAll<HTMLInputElement>('input[type="checkbox"]'),
        ),
        flags: Array.from(
          fieldsets[1]!.querySelectorAll<HTMLInputElement>('input[type="checkbox"]'),
        ),
        avoidances: host!.querySelector<HTMLInputElement>('input[type="text"]')!,
        notes: Array.from(host!.querySelectorAll<HTMLTextAreaElement>("textarea"))
          .find((node) => !node.closest(".ip-calibration"))!,
        calibrationDraft: host!.querySelector<HTMLTextAreaElement>(".ip-calibration textarea")!,
      };
    };
    const editValue = async (
      node: HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement,
      value: string,
    ) => {
      const prototype = node instanceof window.HTMLSelectElement
        ? window.HTMLSelectElement.prototype
        : node instanceof window.HTMLTextAreaElement
          ? window.HTMLTextAreaElement.prototype
          : window.HTMLInputElement.prototype;
      await act(async () => {
        Object.getOwnPropertyDescriptor(prototype, "value")!.set!.call(node, value);
        node.dispatchEvent(new Event(
          node instanceof window.HTMLSelectElement ? "change" : "input",
          { bubbles: true },
        ));
      });
    };
    const assertEditedControls = (controls: ReturnType<typeof queryControls>) => {
      expect.soft(controls.enabled.checked).toBe(false);
      expect.soft(controls.selects.map((node) => node.value)).toEqual([
        "custom",
        "6",
        "7",
        "days_weeks",
        "strict_risk_control",
      ]);
      expect.soft(controls.numbers.map((node) => node.value)).toEqual(["31", "41"]);
      expect.soft(controls.edges.map((node) => node.checked)).toEqual([
        false,
        true,
        true,
        true,
        true,
        true,
        true,
        true,
      ]);
      expect.soft(controls.flags.map((node) => node.checked)).toEqual([
        false,
        true,
        true,
        true,
        true,
        true,
        true,
        true,
        true,
      ]);
      expect.soft(controls.avoidances.value)
        .toBe("SOURCE_DRAFT_AVOIDANCE, SOURCE_SECOND_AVOIDANCE");
      expect.soft(controls.notes.value).toBe("SOURCE_DRAFT_NOTES");
      expect.soft(controls.calibrationDraft.value).toBe("SOURCE_PENDING_CALIBRATION_DRAFT");
    };

    const editedControls = queryControls();
    await act(async () => { editedControls.enabled.click(); });
    await editValue(editedControls.selects[0]!, "custom");
    await editValue(editedControls.selects[1]!, "6");
    await editValue(editedControls.selects[2]!, "7");
    await editValue(editedControls.selects[3]!, "days_weeks");
    await editValue(editedControls.numbers[0]!, "31");
    await editValue(editedControls.numbers[1]!, "41");
    await editValue(editedControls.selects[4]!, "strict_risk_control");
    for (const checkbox of editedControls.edges) {
      await act(async () => { checkbox.click(); });
    }
    for (const checkbox of editedControls.flags) {
      await act(async () => { checkbox.click(); });
    }
    await editValue(
      editedControls.avoidances,
      "SOURCE_DRAFT_AVOIDANCE, SOURCE_SECOND_AVOIDANCE",
    );
    await editValue(editedControls.notes, "SOURCE_DRAFT_NOTES");
    await editValue(editedControls.calibrationDraft, "SOURCE_PENDING_CALIBRATION_DRAFT");
    assertEditedControls(queryControls());

    await act(async () => {
      finishInitialCalibration?.(new Response(JSON.stringify(calibration), {
        status: 200,
        headers: { "content-type": "application/json" },
      }));
      await Promise.resolve();
    });
    await flush();

    const afterCalibration = queryControls();
    assertEditedControls(afterCalibration);
    expect(host!.textContent).toContain("SOURCE_USER_MESSAGE");
    expect(host!.textContent).toContain("SOURCE_ASSISTANT_MESSAGE");
    expect(host!.textContent).toContain("SOURCE_PROPOSAL_RATIONALE");

    const draftButton = await buttonByText("產生設定草稿");
    await act(async () => { draftButton.click(); });
    await flush();
    const requestCount = calls.length;
    const draftCall = calls.find((call) => call.url.endsWith("/profile/investor/draft"));
    expect.soft(draftCall?.body).toEqual({
      enabled: false,
      primary_preset: "custom",
      risk_appetite: 6,
      risk_capacity: 7,
      holding_horizon: "days_weeks",
      drawdown_tolerance_pct: 31,
      concentration_limit_pct: 41,
      preferred_edge: [
        "SOURCE_CUSTOM_EDGE",
        "valuation",
        "catalyst",
        "quality",
        "momentum",
        "macro",
        "options",
        "sentiment",
      ],
      avoidances: ["SOURCE_DRAFT_AVOIDANCE", "SOURCE_SECOND_AVOIDANCE"],
      behavioral_flags: [
        "SOURCE_CUSTOM_FLAG",
        "greed",
        "overconfidence",
        "panic selling",
        "loss aversion",
        "anchoring",
        "narrative susceptibility",
        "revenge trading",
        "under-diversification",
      ],
      freeform_notes: "SOURCE_DRAFT_NOTES",
      default_stance: "strict_risk_control",
    });
    expect.soft(draftCall?.body).not.toHaveProperty("context_preview");
    const panel = host!.querySelector(".investor-profile-panel")!;
    const beforeSwitch = queryControls();
    const proposal = host!.querySelector(".ip-calibration .ip-guardrail")!;
    const messages = Array.from(host!.querySelectorAll(".ip-calibration-log > div"));
    const rationale = proposal.querySelector("li")!;
    const running = host!.querySelector('[data-state="running"]')!;
    expect(panel.getAttribute("aria-busy")).toBe("true");

    await act(async () => { await i18n.changeLanguage("en"); });

    const afterSwitch = queryControls();
    expect(host!.querySelector(".investor-profile-panel")).toBe(panel);
    expect(afterSwitch.enabled).toBe(beforeSwitch.enabled);
    for (const [index, node] of afterSwitch.selects.entries()) {
      expect(node).toBe(beforeSwitch.selects[index]);
    }
    for (const [index, node] of afterSwitch.numbers.entries()) {
      expect(node).toBe(beforeSwitch.numbers[index]);
    }
    for (const [index, node] of afterSwitch.edges.entries()) {
      expect(node).toBe(beforeSwitch.edges[index]);
    }
    for (const [index, node] of afterSwitch.flags.entries()) {
      expect(node).toBe(beforeSwitch.flags[index]);
    }
    expect(afterSwitch.notes).toBe(beforeSwitch.notes);
    expect(afterSwitch.avoidances).toBe(beforeSwitch.avoidances);
    expect(afterSwitch.calibrationDraft).toBe(beforeSwitch.calibrationDraft);
    assertEditedControls(afterSwitch);
    expect(host!.querySelector('textarea[aria-label="Calibration message"]'))
      .toBe(beforeSwitch.calibrationDraft);
    expect(host!.querySelector(".ip-calibration .ip-guardrail")).toBe(proposal);
    const switchedMessages = Array.from(host!.querySelectorAll(".ip-calibration-log > div"));
    expect(switchedMessages).toHaveLength(messages.length);
    for (const [index, node] of switchedMessages.entries()) {
      expect(node).toBe(messages[index]);
    }
    expect(proposal.querySelector("li")).toBe(rationale);
    expect(switchedMessages.map((node) => node.textContent)).toEqual([
      "You:SOURCE_USER_MESSAGE",
      "Assistant:SOURCE_ASSISTANT_MESSAGE",
    ]);
    expect(rationale.textContent).toContain("SOURCE_PROPOSAL_RATIONALE");
    expect(panel.getAttribute("aria-busy")).toBe("true");
    expect(host!.querySelector('[data-state="running"]')).toBe(running);
    expect(running.textContent).toBe("Updating Investor Profile");
    const switchedDraftButton = await buttonByText("Generate settings draft");
    expect(switchedDraftButton).toBe(draftButton);
    expect(switchedDraftButton.disabled).toBe(true);
    expect(calls).toHaveLength(requestCount);
    expect(host!.textContent).toContain("Investor Profile");
    expect(host!.textContent).toContain("Calibration Proposal");
    expect(host!.textContent).toContain("SOURCE_USER_MESSAGE");
    expect(host!.textContent).toContain("SOURCE_ASSISTANT_MESSAGE");
    expect(host!.textContent).toContain("SOURCE_PROPOSAL_RATIONALE");

    await act(async () => {
      finishDraft?.(new Response(JSON.stringify(response), {
        status: 200,
        headers: { "content-type": "application/json" },
      }));
      await Promise.resolve();
    });
    await flush();
  });

  it("preserves calibration messages rationales and custom values as source content", async () => {
    const response = populatedResponse();
    const calibration = populatedCalibration();
    const calls = stubFetch((url) =>
      url.endsWith("/profile/investor/calibration") ? calibration : response);
    await act(async () => { await i18n.changeLanguage("en"); });
    await mount();
    await flush();
    await flush();

    expect(host!.textContent).toContain("You:SOURCE_USER_MESSAGE");
    expect(host!.textContent).toContain("Assistant:SOURCE_ASSISTANT_MESSAGE");
    expect(host!.textContent).toContain("SOURCE_PROPOSAL_RATIONALE");
    expect(host!.querySelector<HTMLInputElement>('input[type="text"]')?.value)
      .toBe("SOURCE_AVOID_LEVERAGE, SOURCE_AVOID_HYPE");
    expect(host!.querySelectorAll<HTMLTextAreaElement>("textarea")[0]?.value)
      .toBe("SOURCE_PROFILE_NOTES");
    const patchedSelects = host!.querySelectorAll<HTMLSelectElement>(".ip-grid select");
    expect(patchedSelects[1]?.value).toBe("9");
    expect(patchedSelects[2]?.value).toBe("3");
    expect(patchedSelects[4]?.value).toBe("valuation_rationalist");

    const draftButton = await buttonByText("Generate settings draft");
    await act(async () => { draftButton.click(); });
    await flush();
    const draftCall = calls.find((call) => call.url.endsWith("/profile/investor/draft"));
    expect(draftCall?.body).toMatchObject({
      preferred_edge: ["growth", "SOURCE_CUSTOM_EDGE"],
      avoidances: ["SOURCE_AVOID_LEVERAGE", "SOURCE_AVOID_HYPE"],
      behavioral_flags: ["FOMO", "SOURCE_CUSTOM_FLAG"],
      freeform_notes: "SOURCE_PROFILE_NOTES",
      risk_appetite: 9,
      risk_capacity: 3,
      default_stance: "valuation_rationalist",
    });
    expect(draftCall?.body).not.toHaveProperty("context_preview");
    expect(host!.textContent).toContain("SOURCE_USER_MESSAGE");
    expect(host!.textContent).toContain("SOURCE_ASSISTANT_MESSAGE");
    expect(host!.textContent).toContain("SOURCE_PROPOSAL_RATIONALE");
  });

  it("hides request diagnostics outside Developer Mode and reveals them inside it", async () => {
    const diagnostic = "PLANTED_INVESTOR_REQUEST_DIAGNOSTIC";
    await act(async () => { await i18n.changeLanguage("en"); });
    vi.stubGlobal("fetch", vi.fn(async () => {
      throw new Error(diagnostic);
    }));
    await mount(false);
    await flush();

    expect(host!.querySelector('[role="alert"]')?.textContent)
      .toContain("The request failed. Try again later.");
    expect(host!.textContent).not.toContain(diagnostic);
    expect(host!.querySelector('[data-testid="developer-diagnostics"]')).toBeNull();

    dispose();
    await mount(true);
    await flush();

    expect(host!.querySelector('[role="alert"]')?.textContent)
      .toContain("The request failed. Try again later.");
    expect(host!.querySelector('[data-testid="developer-diagnostics"]')?.textContent)
      .toContain("Developer diagnostics");
    expect(host!.querySelector('[data-testid="developer-diagnostics"]')?.textContent).toContain(diagnostic);
  });
});
