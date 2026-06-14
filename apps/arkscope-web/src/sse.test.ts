import { describe, expect, it } from "vitest";

import { SSEFrameParser, type SSEFrame } from "./sse";

// The wire format the sidecar emits (src/agents/shared/events.py to_sse):
//   `data: {json}\n\n`  with ensure_ascii=False (Chinese stays literal).
// The parser is the #1 load-bearing risk in C-2: a slow agent turn delivers
// frames across arbitrary chunk boundaries, so this must buffer correctly and
// never crash the stream on a stray/keep-alive line.

const wire = (type: string, data: unknown) =>
  `data: ${JSON.stringify({ type, data })}\n\n`;

function pushAll(p: SSEFrameParser, ...chunks: string[]): SSEFrame[] {
  return chunks.flatMap((c) => p.push(c));
}

describe("SSEFrameParser", () => {
  it("parses one complete frame from a single push", () => {
    const p = new SSEFrameParser();
    const frames = p.push(wire("thinking", { turn: 1, model: "claude-opus-4-8" }));
    expect(frames).toEqual([{ type: "thinking", data: { turn: 1, model: "claude-opus-4-8" } }]);
  });

  it("parses two frames delivered in one push", () => {
    const p = new SSEFrameParser();
    const frames = p.push(wire("tool_start", { tool: "get_sa_feed" }) + wire("tool_end", { tool: "get_sa_feed", chars: 42 }));
    expect(frames.map((f) => f.type)).toEqual(["tool_start", "tool_end"]);
    expect(frames[1].data.chars).toBe(42);
  });

  it("buffers a frame split mid-JSON across two chunks", () => {
    const p = new SSEFrameParser();
    const full = wire("text", { content: "hello world" });
    const cut = 14; // somewhere inside the JSON
    expect(p.push(full.slice(0, cut))).toEqual([]); // incomplete → nothing yet
    const frames = p.push(full.slice(cut));
    expect(frames).toEqual([{ type: "text", data: { content: "hello world" } }]);
  });

  it("buffers a frame split inside the \\n\\n delimiter across chunks", () => {
    const p = new SSEFrameParser();
    const f1 = wire("text", { content: "a" });
    const f2 = wire("done", { answer: "b", tools_used: [], provider: "anthropic", model: "m", token_usage: {} });
    // break exactly between the two newlines of f1's terminator
    const joined = f1 + f2;
    const at = f1.length - 1; // f1 = `...}\n\n`; cut leaves one trailing \n in chunk A
    expect(p.push(joined.slice(0, at))).toEqual([]); // f1 not yet terminated
    const frames = p.push(joined.slice(at));
    expect(frames.map((f) => f.type)).toEqual(["text", "done"]);
  });

  it("preserves unicode in data (ensure_ascii=False round-trip)", () => {
    const p = new SSEFrameParser();
    const frames = p.push(wire("done", { answer: "最近 SA 對 MXL 的評論焦點", tools_used: ["get_sa_comment_focus"] }));
    expect(frames[0].data.answer).toBe("最近 SA 對 MXL 的評論焦點");
  });

  it("ignores blank and comment/keep-alive segments (no frames)", () => {
    const p = new SSEFrameParser();
    expect(p.push("\n\n")).toEqual([]); // blank segment
    expect(p.push(": keep-alive\n\n")).toEqual([]); // SSE comment line
    // and a real frame still parses afterwards
    expect(p.push(wire("thinking", { turn: 2, model: "m" }))).toEqual([
      { type: "thinking", data: { turn: 2, model: "m" } },
    ]);
  });

  it("tolerates a 'data:' line with no space after the colon", () => {
    const p = new SSEFrameParser();
    const frames = p.push(`data:${JSON.stringify({ type: "text", data: { content: "x" } })}\n\n`);
    expect(frames).toEqual([{ type: "text", data: { content: "x" } }]);
  });

  it("skips a malformed-JSON frame without throwing and keeps parsing", () => {
    const p = new SSEFrameParser();
    const frames = pushAll(
      p,
      "data: {not valid json\n\n",
      wire("done", { answer: "ok", tools_used: [], provider: "openai", model: "m", token_usage: {} }),
    );
    expect(frames.map((f) => f.type)).toEqual(["done"]); // malformed dropped, valid survives
  });

  it("flush() emits a trailing frame whose \\n\\n terminator never arrived", () => {
    const p = new SSEFrameParser();
    expect(p.push(`data: ${JSON.stringify({ type: "text", data: { content: "tail" } })}`)).toEqual([]);
    expect(p.flush()).toEqual([{ type: "text", data: { content: "tail" } }]);
  });

  it("flush() returns [] when the buffer holds only whitespace", () => {
    const p = new SSEFrameParser();
    p.push("\n");
    expect(p.flush()).toEqual([]);
  });
});
