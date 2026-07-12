/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { InvestorProfilePanel } from "./InvestorProfilePanel";
import type { CalibrationProposal, CalibrationState, InvestorProfileResponse } from "./api";

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

afterEach(() => {
  if (root) act(() => root!.unmount());
  root = null;
  host?.remove();
  host = null;
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

type PanelApiResponse =
  | InvestorProfileResponse
  | CalibrationState
  | { profile: InvestorProfileResponse["profile"]; proposal: Partial<CalibrationProposal> };

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

async function mount() {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(<InvestorProfilePanel />);
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
    expect(host!.querySelector('[role="alert"]')?.textContent).toContain("投資人設定失敗");
  });

  it("loads_default_disabled_profile", async () => {
    const calls = stubFetch(() => disabledResponse());
    await mount();
    expect(calls[0].url).toContain("/profile/investor");
    expect(calls[0].method).toBe("GET");
    const checkbox = host!.querySelector<HTMLInputElement>("input[type=checkbox]");
    expect(checkbox?.checked).toBe(false);
    expect(host!.textContent).toContain("投資人設定");
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
    expect(host!.textContent).toContain("風險胃納高於承受能力");
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
    const saveBtn = Array.from(host!.querySelectorAll("button")).find((b) =>
      b.textContent?.includes("儲存設定"),
    )!;
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
    expect(host!.querySelector('[data-state="running"]')?.textContent).toContain("正在更新投資人設定");

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
    stubFetch((url) => {
      if (url.endsWith("/profile/investor")) return disabledResponse();
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
      }
      return {
        active_session: null,
        sessions: [],
        messages: [],
        latest_proposal: null,
      };
    });
    await mount();
    await flush();
    await flush();

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

    expect(host!.textContent).toContain("Draft ready.");
    expect(host!.textContent).toContain("User said 10% drawdown");
    expect(host!.textContent).toContain("風險承受能力");
    expect(host!.querySelector('[data-state="partial"]')?.textContent).toContain("校準提案");
  });

  it("approves_calibration_proposal_through_dedicated_endpoint", async () => {
    const calls = stubFetch((url) => {
      if (url.includes("/profile/investor/calibration/proposals/p1/approve")) {
        const resp = disabledResponse();
        resp.profile.enabled = true;
        resp.profile.risk_appetite = 8;
        return { profile: resp.profile, proposal: { id: "p1", status: "approved", approved_at: "t" } };
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
        return {
          active_session: null,
          sessions: [],
          messages: [],
          latest_proposal: null,
        };
      }
      if (url.endsWith("/profile/investor")) return disabledResponse();
      return disabledResponse();
    });
    await mount();
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
    const approveBtn = await buttonByText("套用校準提案");
    await act(async () => {
      approveBtn.click();
    });

    const approve = calls.find((c) => c.url.includes("/proposals/p1/approve"));
    expect(approve).toBeTruthy();
  });
});
