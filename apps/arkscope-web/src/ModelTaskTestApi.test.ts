/** @vitest-environment jsdom */
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("testTaskModelAccess", () => {
  it("posts the task route and uses a 60 second UI timeout", async () => {
    const setTimeoutSpy = vi.spyOn(window, "setTimeout");
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => new Response(JSON.stringify({
      task: "ai_research",
      provider: "openai",
      model: "gpt-5.4-mini",
      effort: "low",
      auth_mode: "chatgpt_oauth",
      credential_id: "local:7",
      status: "ok",
      error_code: null,
      latency_ms: 12,
      tested_at: "2026-07-11T00:00:00Z",
      fallback_effort: null,
      warning: null,
    }), { status: 200, headers: { "content-type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);

    const { testTaskModelAccess } = await import("./api");
    await testTaskModelAccess("ai_research", "openai", "gpt-5.4-mini", "low");

    expect(setTimeoutSpy).toHaveBeenCalledWith(expect.any(Function), 60_000);
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(JSON.parse(String(init.body))).toEqual({
      task: "ai_research", provider: "openai", model: "gpt-5.4-mini", effort: "low",
    });
  });
});
