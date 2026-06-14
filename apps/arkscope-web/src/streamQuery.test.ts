/** @vitest-environment jsdom */
import { afterEach, describe, expect, it, vi } from "vitest";

import { streamQuery } from "./api";
import type { SSEFrame } from "./sse";

// streamQuery is the thin transport wrapping the (separately unit-tested)
// SSEFrameParser around fetch + a ReadableStream reader. These tests stub the
// network boundary (the only unavoidable mock) to pin: ordered frame delivery
// across chunk boundaries, the request shape + abort-signal forwarding, and
// throw-on-non-ok so the consumer can surface an error bubble.

const wire = (t: string, d: unknown) => `data: ${JSON.stringify({ type: t, data: d })}\n\n`;

function streamFromChunks(chunks: string[]): ReadableStream<Uint8Array> {
  const enc = new TextEncoder();
  let i = 0;
  return new ReadableStream({
    pull(controller) {
      if (i < chunks.length) controller.enqueue(enc.encode(chunks[i++]));
      else controller.close();
    },
  });
}

async function collect(gen: AsyncGenerator<SSEFrame>): Promise<SSEFrame[]> {
  const out: SSEFrame[] = [];
  for await (const f of gen) out.push(f);
  return out;
}

afterEach(() => vi.unstubAllGlobals());

describe("streamQuery", () => {
  it("yields parsed frames in order across awkward chunk boundaries", async () => {
    const full =
      wire("thinking", { turn: 1, model: "m" }) +
      wire("tool_end", { tool: "get_sa_feed" }) +
      wire("done", { answer: "hi", tools_used: ["get_sa_feed"], provider: "anthropic", model: "m", token_usage: {} });
    const chunks = [full.slice(0, 10), full.slice(10, 40), full.slice(40)]; // mid-frame splits
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, status: 200, body: streamFromChunks(chunks) }));

    const frames = await collect(streamQuery({ question: "q", provider: "anthropic" }));

    expect(frames.map((f) => f.type)).toEqual(["thinking", "tool_end", "done"]);
    expect(frames[2].data.answer).toBe("hi");
  });

  it("POSTs JSON to /query/stream and forwards the abort signal", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, body: streamFromChunks([]) });
    vi.stubGlobal("fetch", fetchMock);
    const ctrl = new AbortController();

    await collect(streamQuery({ question: "hello", provider: "openai", model: "gpt-5.4" }, ctrl.signal));

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/query\/stream$/);
    expect(init.method).toBe("POST");
    expect(init.headers["content-type"]).toBe("application/json");
    expect(JSON.parse(init.body)).toEqual({ question: "hello", provider: "openai", model: "gpt-5.4" });
    expect(init.signal).toBe(ctrl.signal);
  });

  it("throws on a non-ok response so the consumer can surface an error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 401, body: null }));
    await expect(collect(streamQuery({ question: "q", provider: "anthropic" }))).rejects.toThrow();
  });
});
