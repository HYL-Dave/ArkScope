/** @vitest-environment jsdom */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { afterEach, describe, expect, it, vi } from "vitest";

import * as api from "./api";

function okResponse(body: unknown = {}): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

function requestBody(fetchMock: ReturnType<typeof vi.fn>, call: number): unknown {
  const init = fetchMock.mock.calls[call][1] as RequestInit;
  return JSON.parse(String(init.body));
}

const apiSource = readFileSync(resolve(import.meta.dirname, "api.ts"), "utf8");

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Investor Profile guided API", () => {
  it("serializes guided start and turn contracts with stable IDs", async () => {
    const fetchMock = vi.fn().mockImplementation(async () => okResponse());
    vi.stubGlobal("fetch", fetchMock);

    await api.startCalibrationSession(true);
    const sendMessage = api.sendCalibrationMessage as (body: {
      turn_id: string;
      session_id?: string;
      content: string;
      provider?: string;
      model?: string;
    }) => Promise<api.CalibrationState>;
    await sendMessage({
      turn_id: "turn-stable-1",
      session_id: "session-1",
      content: "source answer",
      provider: "openai",
      model: "gpt-test",
    });

    expect(String(fetchMock.mock.calls[0][0])).toBe(
      "http://127.0.0.1:8420/profile/investor/calibration/sessions",
    );
    expect(requestBody(fetchMock, 0)).toEqual({ supersede_active: true });
    expect(String(fetchMock.mock.calls[1][0])).toBe(
      "http://127.0.0.1:8420/profile/investor/calibration/messages",
    );
    expect(requestBody(fetchMock, 1)).toEqual({
      turn_id: "turn-stable-1",
      session_id: "session-1",
      content: "source answer",
      provider: "openai",
      model: "gpt-test",
    });
    expect(apiSource).toMatch(/sendCalibrationMessage\(body:\s*\{[\s\S]*?turn_id: string;/);
  });

  it("retries a turn without mutating answer payload", async () => {
    const fetchMock = vi.fn().mockResolvedValue(okResponse());
    vi.stubGlobal("fetch", fetchMock);
    const retryCalibrationTurn = (api as unknown as {
      retryCalibrationTurn: (
        turnId: string,
        body: { provider?: string; model?: string },
      ) => Promise<api.CalibrationState>;
    }).retryCalibrationTurn;

    await retryCalibrationTurn("turn/id", { provider: "anthropic", model: "claude-test" });

    expect(String(fetchMock.mock.calls[0][0])).toBe(
      "http://127.0.0.1:8420/profile/investor/calibration/turns/turn%2Fid/retry",
    );
    expect(requestBody(fetchMock, 0)).toEqual({ provider: "anthropic", model: "claude-test" });
    expect(requestBody(fetchMock, 0)).not.toHaveProperty("content");
    expect(requestBody(fetchMock, 0)).not.toHaveProperty("answer");
    expect(requestBody(fetchMock, 0)).not.toHaveProperty("turn_id");
  });

  it("requests an early proposal on the dedicated route", async () => {
    const fetchMock = vi.fn().mockResolvedValue(okResponse());
    vi.stubGlobal("fetch", fetchMock);
    const requestCalibrationProposal = (api as unknown as {
      requestCalibrationProposal: (body: {
        turn_id: string;
        session_id?: string;
        provider?: string;
        model?: string;
      }) => Promise<api.CalibrationState>;
    }).requestCalibrationProposal;

    await requestCalibrationProposal({
      turn_id: "proposal-turn",
      session_id: "session-1",
      provider: "openai",
      model: "gpt-test",
    });

    expect(String(fetchMock.mock.calls[0][0])).toBe(
      "http://127.0.0.1:8420/profile/investor/calibration/proposals/request",
    );
    expect(requestBody(fetchMock, 0)).toEqual({
      turn_id: "proposal-turn",
      session_id: "session-1",
      provider: "openai",
      model: "gpt-test",
    });
    expect(requestBody(fetchMock, 0)).not.toHaveProperty("content");
    fetchMock.mockResolvedValueOnce(new Response(JSON.stringify({
      detail: { code: "proposal_failed", message: "safe summary", diagnostic: "  sanitized detail  " },
    }), { status: 409 }));
    await expect(requestCalibrationProposal({ turn_id: "error-turn" })).rejects.toMatchObject({
      code: "proposal_failed",
      diagnostic: "sanitized detail",
      message: "/profile/investor/calibration/proposals/request returned 409: safe summary",
    });
  });

  it("approves with an empty body and never sends profile_patch", async () => {
    const fetchMock = vi.fn().mockResolvedValue(okResponse());
    vi.stubGlobal("fetch", fetchMock);
    const approve = api.approveCalibrationProposal as (
      proposalId: string,
      attemptedPatch?: unknown,
    ) => Promise<unknown>;

    await approve("proposal/id", {
      profile_patch: { enabled: false },
      enabled: false,
      freeform_notes: "must not leave the client",
    });

    expect(String(fetchMock.mock.calls[0][0])).toBe(
      "http://127.0.0.1:8420/profile/investor/calibration/proposals/proposal%2Fid/approve",
    );
    expect(requestBody(fetchMock, 0)).toEqual({});
    expect(JSON.stringify(requestBody(fetchMock, 0))).not.toContain("profile_patch");
  });

  it("exposes run personalization snapshot without credential identity", async () => {
    const run = {
      id: "run-1",
      personalization: {
        profile_active: true,
        assistant_stance: "aligned",
        skill_mode: "off",
        suggested_skills: [],
        applied_skills: [],
        context_snapshot: "exact source context",
      },
      auth_mode: "chatgpt_oauth",
      credential_id: "local-secret-identity",
    };
    const fetchMock = vi.fn().mockResolvedValue(okResponse({ run }));
    vi.stubGlobal("fetch", fetchMock);

    const response = await api.getResearchRun("run-1");

    expect(response.run.personalization).toEqual(run.personalization);
    expect(response.run.personalization).not.toHaveProperty("auth_mode");
    expect(response.run.personalization).not.toHaveProperty("credential_id");
    expect(apiSource).toMatch(/interface PersonalizationTrace\s*\{[\s\S]*?context_snapshot\?: string \| null;/);
    expect(apiSource).toMatch(/interface ResearchRunDTO\s*\{[\s\S]*?personalization\?: PersonalizationTrace \| null;/);
  });
});
