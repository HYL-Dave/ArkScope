/** @vitest-environment jsdom */
import { afterEach, describe, expect, it, vi } from "vitest";

import { completeOpenAIOAuthManual, openAIOAuthStatus, startOpenAIOAuth } from "./api";
import type { OAuthStatusResult } from "./api";
import { buildManualCompletion, pollOAuthStatus } from "./chatgptOAuth";

afterEach(() => vi.unstubAllGlobals());

const okJson = (body: unknown) =>
  vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => body });

// --- api clients (request shape) ----------------------------------------------
describe("OpenAI OAuth api clients", () => {
  it("startOpenAIOAuth POSTs to the start route with no body", async () => {
    const fetchMock = okJson({ auth_url: "https://auth.openai.com/x", state: "S", expires_at: "t", manual_code_supported: true });
    vi.stubGlobal("fetch", fetchMock);

    const out = await startOpenAIOAuth();

    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/config\/credentials\/openai\/oauth\/start$/);
    expect(init.method).toBe("POST");
    expect(init.body).toBeUndefined();
    expect(out.state).toBe("S");
    expect(out.manual_code_supported).toBe(true);
  });

  it("openAIOAuthStatus GETs the status route with the state url-encoded", async () => {
    const fetchMock = okJson({ status: "pending", credential: null, detail: null });
    vi.stubGlobal("fetch", fetchMock);

    await openAIOAuthStatus("a b/c+d");

    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toContain("/config/credentials/openai/oauth/status?state=a%20b%2Fc%2Bd");
    // GET: fetchWithTimeout is called without an explicit method (defaults to GET)
    expect(init?.method).toBeUndefined();
  });

  it("completeOpenAIOAuthManual POSTs the state + code", async () => {
    const fetchMock = okJson({ credential: { id: "local:1" } });
    vi.stubGlobal("fetch", fetchMock);

    await completeOpenAIOAuthManual({ state: "S", code: "CODE" });

    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/config\/credentials\/openai\/oauth\/complete-manual$/);
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ state: "S", code: "CODE" });
  });

  it("completeOpenAIOAuthManual forwards a redirect_url instead of a code", async () => {
    const fetchMock = okJson({ credential: { id: "local:1" } });
    vi.stubGlobal("fetch", fetchMock);

    await completeOpenAIOAuthManual({ state: "S", redirect_url: "http://localhost:1455/auth/callback?code=C&state=S" });

    const [, init] = fetchMock.mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({ state: "S", redirect_url: "http://localhost:1455/auth/callback?code=C&state=S" });
  });

  it("throws on a non-ok status response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 400, json: async () => ({}) }));
    await expect(openAIOAuthStatus("S")).rejects.toThrow();
  });
});

// --- pollOAuthStatus state machine (pure; injected statusFn + fake clock) ------
function fakeClock() {
  let t = 0;
  return { now: () => t, sleep: async (ms: number) => { t += ms; } };
}

const PENDING: OAuthStatusResult = { status: "pending", credential: null, detail: null };

describe("pollOAuthStatus", () => {
  it("returns success with the masked credential", async () => {
    const cred = { id: "local:1", auth_type: "chatgpt_oauth" } as OAuthStatusResult["credential"];
    const statusFn = vi.fn().mockResolvedValue({ status: "success", credential: cred, detail: null });
    const clk = fakeClock();

    const res = await pollOAuthStatus("S", { statusFn, ...clk, timeoutMs: 5000, intervalMs: 100 });

    expect(res).toEqual({ kind: "success", credential: cred });
  });

  it("returns an error kind carrying the backend detail (no fallback)", async () => {
    const statusFn = vi.fn().mockResolvedValue({ status: "error", credential: null, detail: "loopback callback port 1455 is unavailable" });
    const res = await pollOAuthStatus("S", { statusFn, ...fakeClock(), timeoutMs: 5000, intervalMs: 100 });
    expect(res.kind).toBe("error");
    if (res.kind === "error") expect(res.detail).toContain("1455");
  });

  it("returns unknown and stops (does not spin) when the login is not tracked", async () => {
    const statusFn = vi.fn().mockResolvedValue({ status: "unknown", credential: null, detail: null });
    const res = await pollOAuthStatus("S", { statusFn, ...fakeClock(), timeoutMs: 5000, intervalMs: 100 });
    expect(res.kind).toBe("unknown");
    expect(statusFn).toHaveBeenCalledTimes(1);
  });

  it("polls through pendings until success, sleeping between", async () => {
    const cred = { id: "local:9" } as OAuthStatusResult["credential"];
    const statusFn = vi.fn()
      .mockResolvedValueOnce(PENDING)
      .mockResolvedValueOnce(PENDING)
      .mockResolvedValueOnce({ status: "success", credential: cred, detail: null });
    const res = await pollOAuthStatus("S", { statusFn, ...fakeClock(), timeoutMs: 5000, intervalMs: 100 });
    expect(res.kind).toBe("success");
    expect(statusFn).toHaveBeenCalledTimes(3);
  });

  it("returns a timeout kind when pending persists past the budget", async () => {
    const statusFn = vi.fn().mockResolvedValue(PENDING);
    const res = await pollOAuthStatus("S", { statusFn, ...fakeClock(), timeoutMs: 1000, intervalMs: 300 });
    expect(res.kind).toBe("timeout");
    expect(statusFn.mock.calls.length).toBeGreaterThanOrEqual(2);
  });
});

describe("buildManualCompletion", () => {
  it("sends a bare authorization code as `code`", () => {
    expect(buildManualCompletion("S", "AUTHCODE123")).toEqual({ state: "S", code: "AUTHCODE123" });
  });

  it("sends a full redirect URL as `redirect_url`", () => {
    const url = "http://localhost:1455/auth/callback?code=C&state=S";
    expect(buildManualCompletion("S", url)).toEqual({ state: "S", redirect_url: url });
  });

  it("treats a value containing ?code= as a redirect URL even without a scheme", () => {
    const v = "localhost:1455/auth/callback?code=C&state=S";
    expect(buildManualCompletion("S", v)).toEqual({ state: "S", redirect_url: v });
  });

  it("trims surrounding whitespace", () => {
    expect(buildManualCompletion("S", "  AUTHCODE  ")).toEqual({ state: "S", code: "AUTHCODE" });
  });
});
