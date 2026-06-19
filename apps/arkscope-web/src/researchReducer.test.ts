import { describe, expect, it } from "vitest";

import {
  initialState,
  MAX_TURNS_SENTINEL,
  reduce,
  selectFooter,
  type Action,
  type Message,
  type State,
} from "./researchReducer";

// Test matrix designed by the c2-reducer-design workflow (grounded line-for-line
// against src/agents/shared/events.py + both run_query_stream). The reducer is
// pure: time enters via the action envelope `ts` (epoch ms), never Date.now.

function run(...actions: Action[]): State {
  return actions.reduce((s, a) => reduce(s, a), initialState);
}
const submit = (o: Partial<Action> & { question: string }): Action =>
  ({ kind: "submit", ts: 0, provider: "anthropic", model: "m", threadId: "t1", ...o } as Action);
const f = (type: string, data: unknown = {}, ts = 0): Action => ({ kind: "frame", frame: { type, data }, ts });
const iso = (ms: number) => new Date(ms).toISOString();
const msgs = (s: State): Message[] => s.messagesByThread[s.activeThreadId!] ?? [];
const assistant = (s: State): Message => msgs(s)[msgs(s).length - 1];

// ---------------------------------------------------------------------------
// GROUP 1 — Anthropic LIVE happy-path build-up
// ---------------------------------------------------------------------------
describe("reducer · anthropic live", () => {
  it("submit commits user msg, opens pending, sets thinkingActive, creates+titles thread", () => {
    const s = run(submit({ question: "NVDA 最新 SA 動態與評論焦點重點整理。", provider: "anthropic", model: "claude-opus-4-8", ticker: "nvda", ts: 1000, threadId: "th-uuid-1" }));
    expect(s.threads).toHaveLength(1);
    expect(s.activeThreadId).toBe("th-uuid-1"); // client-supplied id, not an internal thread-N
    expect(s.threads[0].id).toBe("th-uuid-1");
    const t = s.threads[0];
    expect(t.title).toBe("NVDA 最新 SA 動態與評論焦點重點整理。");
    expect(t.provider).toBe("anthropic");
    expect(t.model).toBe("claude-opus-4-8");
    expect(t.ticker).toBe("NVDA"); // uppercased from the typed field
    expect(t.created_at).toBe(iso(1000));
    expect(msgs(s)).toHaveLength(1);
    expect(msgs(s)[0]).toMatchObject({ role: "user", content: "NVDA 最新 SA 動態與評論焦點重點整理。", tickers: ["NVDA"], created_at: iso(1000) });
    expect(s.pending).not.toBeNull();
    expect(s.pending).toMatchObject({ startedAt: 1000, thinkingActive: true, trace: [], model: "claude-opus-4-8", interimText: "" });
    expect(s.footer).toBeNull();
    expect(s.terminal).toBeNull();
  });

  it("thinking sets the model badge optimistically, keeps indicator on, adds no trace row", () => {
    const s = run(submit({ question: "q", model: "auto" }), f("thinking", { turn: 1, model: "claude-opus-4-8" }));
    expect(s.pending!.thinkingActive).toBe(true);
    expect(s.pending!.model).toBe("claude-opus-4-8"); // overwrote the 'auto' submit guess
    expect(s.pending!.trace).toEqual([]);
    expect(s.pending!.turnCount).toBe(1);
    expect(s.terminal).toBeNull();
    expect(msgs(s)[0].tickers).toEqual([]); // no ticker typed
  });

  it("thinking_content appends one inline trace line; indicator stays on", () => {
    const s = run(submit({ question: "q" }), f("thinking", { turn: 1, model: "m" }), f("thinking_content", { thinking: "I should pull the SA feed first." }));
    expect(s.pending!.thinkingActive).toBe(true);
    expect(s.pending!.trace).toEqual([{ kind: "thinking", text: "I should pull the SA feed first." }]);
    expect(s.pending!.interimText).toBe("");
  });

  it("multiple consecutive thinking_content blocks append in order; none clears the indicator", () => {
    const s = run(submit({ question: "q" }), f("thinking", { turn: 1, model: "m" }), f("thinking_content", { thinking: "first block" }), f("thinking_content", { thinking: "second block" }));
    expect(s.pending!.trace).toEqual([
      { kind: "thinking", text: "first block" },
      { kind: "thinking", text: "second block" },
    ]);
    expect(s.pending!.thinkingActive).toBe(true);
  });

  it("interim text clears the indicator and holds content; adds no trace row", () => {
    const s = run(submit({ question: "q" }), f("thinking", { turn: 1, model: "m" }), f("text", { content: "Let me look at the latest articles." }));
    expect(s.pending!.thinkingActive).toBe(false); // text is first-of clear-set
    expect(s.pending!.interimText).toBe("Let me look at the latest articles.");
    expect(s.pending!.trace).toEqual([]);
  });

  it("text then tool_start — only text (the first) flips the indicator; tool_start just opens the row", () => {
    const s = run(submit({ question: "q" }), f("thinking", { turn: 1, model: "m" }), f("text", { content: "Checking the feed." }), f("tool_start", { tool: "get_sa_feed", input: { ticker: "NVDA" } }));
    expect(s.pending!.thinkingActive).toBe(false);
    expect(s.pending!.interimText).toBe("Checking the feed.");
    expect(s.pending!.trace).toEqual([{ kind: "tool", name: "get_sa_feed", input: { ticker: "NVDA" }, result_preview: undefined, chars: undefined, done: false }]);
  });

  it("tool_start (no prior text) clears the indicator and opens an open trace row", () => {
    const s = run(submit({ question: "q" }), f("thinking", { turn: 1, model: "m" }), f("tool_start", { tool: "get_sa_feed", input: { ticker: "NVDA", limit: 5 } }));
    expect(s.pending!.thinkingActive).toBe(false); // tool_start is first-of clear-set
    expect(s.pending!.trace).toEqual([{ kind: "tool", name: "get_sa_feed", input: { ticker: "NVDA", limit: 5 }, result_preview: undefined, chars: undefined, done: false }]);
  });

  it("tool_end completes exactly that one open row with result_preview+chars", () => {
    const s = run(submit({ question: "q" }), f("thinking", { turn: 1, model: "m" }), f("tool_start", { tool: "get_sa_feed", input: { ticker: "NVDA" } }), f("tool_end", { tool: "get_sa_feed", summary: "5 articles: 3 bullish, AI demand", chars: 842 }));
    expect(s.pending!.trace).toEqual([{ kind: "tool", name: "get_sa_feed", input: { ticker: "NVDA" }, result_preview: "5 articles: 3 bullish, AI demand", chars: 842, done: true }]);
    expect(s.pending!.thinkingActive).toBe(false);
  });

  it("tool_end missing summary/chars still flips the row done (optional fields tolerated)", () => {
    const s = run(submit({ question: "q" }), f("thinking", { turn: 1, model: "m" }), f("tool_start", { tool: "get_sa_feed", input: { ticker: "NVDA" } }), f("tool_end", { tool: "get_sa_feed" }));
    expect(s.pending!.trace).toEqual([{ kind: "tool", name: "get_sa_feed", input: { ticker: "NVDA" }, result_preview: undefined, chars: undefined, done: true }]);
  });

  it("model badge from thinking equals done.model (no reconciliation)", () => {
    const s = run(
      submit({ question: "q", model: "claude-sonnet-4-6" }),
      f("thinking", { turn: 1, model: "claude-opus-4-8" }),
      f("tool_start", { tool: "get_sa_feed", input: {} }),
      f("tool_end", { tool: "get_sa_feed", summary: "s", chars: 1 }),
      f("done", { answer: "a", tools_used: ["get_sa_feed"], provider: "anthropic", model: "claude-opus-4-8", token_usage: { total_tokens: 5, turn_count: 1 } }),
    );
    expect(s.terminal).toBe("done");
    expect(assistant(s).model).toBe("claude-opus-4-8");
  });

  it("full single-turn happy path: interim replaced, footer reads only total_tokens+turn_count, trace chronological", () => {
    const s = run(
      submit({ question: "NVDA 最新 SA 動態？", provider: "anthropic", model: "claude-opus-4-8", ticker: "NVDA", ts: 1000 }),
      f("thinking", { turn: 1, model: "claude-opus-4-8" }),
      f("thinking_content", { thinking: "pull feed" }),
      f("text", { content: "Checking SA…" }),
      f("tool_start", { tool: "get_sa_feed", input: { ticker: "NVDA" } }),
      f("tool_end", { tool: "get_sa_feed", summary: "5 articles…", chars: 842 }),
      f("thinking", { turn: 2, model: "claude-opus-4-8" }),
      f("done", { answer: "NVDA: 3 看多 2 看空，焦點在 AI 需求。", tools_used: ["get_sa_feed"], provider: "anthropic", model: "claude-opus-4-8", token_usage: { total_input_tokens: 1200, total_output_tokens: 300, total_tokens: 1500, turn_count: 2, last_input_tokens: 1200 } }, 4000),
    );
    expect(s.terminal).toBe("done");
    expect(s.pending).toBeNull();
    expect(msgs(s)).toHaveLength(2);
    expect(assistant(s)).toMatchObject({
      role: "assistant",
      content: "NVDA: 3 看多 2 看空，焦點在 AI 需求。",
      provider: "anthropic",
      model: "claude-opus-4-8",
      tools_used: ["get_sa_feed"],
      tool_calls: [{ name: "get_sa_feed", input: { ticker: "NVDA" }, result_preview: "5 articles…" }],
      tickers: ["NVDA"],
      elapsed_seconds: 3, // (4000-1000)/1000
      isError: false,
      maxTurns: false,
    });
    expect(assistant(s).token_usage!.total_tokens).toBe(1500);
    expect(s.footer).toEqual({ total_tokens: 1500, turn_count: 2 });
    expect(s.threads[0].updated_at).toBe(iso(4000));
  });

  it("done with no prior text/tool clears the indicator (done is in the clear-set)", () => {
    const s = run(
      submit({ question: "q", model: "m" }),
      f("thinking", { turn: 1, model: "m" }),
      f("thinking_content", { thinking: "no tools needed" }),
      f("done", { answer: "direct answer", tools_used: [], provider: "anthropic", model: "m", token_usage: { total_tokens: 2, turn_count: 1 } }),
    );
    expect(s.pending).toBeNull();
    expect(s.terminal).toBe("done");
    expect(assistant(s)).toMatchObject({ content: "direct answer", tools_used: [], tool_calls: [], model: "m" });
    expect(s.footer).toEqual({ total_tokens: 2, turn_count: 1 });
  });

  it("empty-answer done finalizes normally (not max-turns, not error)", () => {
    const s = run(
      submit({ question: "q", model: "m" }),
      f("thinking", { turn: 1, model: "m" }),
      f("tool_start", { tool: "get_sa_feed", input: {} }),
      f("tool_end", { tool: "get_sa_feed", summary: "s", chars: 1 }),
      f("done", { answer: "", tools_used: ["get_sa_feed"], provider: "anthropic", model: "m", token_usage: { total_tokens: 3, turn_count: 1 } }),
    );
    expect(s.terminal).toBe("done");
    expect(assistant(s)).toMatchObject({ content: "", tools_used: ["get_sa_feed"], maxTurns: false, isError: false });
    expect(assistant(s).tool_calls).toEqual([{ name: "get_sa_feed", input: {}, result_preview: "s" }]);
    expect(s.pending).toBeNull();
  });

  it("degenerate done with data:{} finalizes gracefully (no throw / no NaN)", () => {
    const s = run(submit({ question: "q", model: "m", ts: 1000 }), f("thinking", { turn: 1, model: "m" }), f("done", {}, 5000));
    expect(s.terminal).toBe("done");
    expect(s.pending).toBeNull();
    expect(assistant(s)).toMatchObject({ content: "", tools_used: [], tool_calls: [], tickers: [] });
    expect(assistant(s).elapsed_seconds).toBe(4); // never NaN
  });
});

const abort = (ts = 0): Action => ({ kind: "abort", ts });
const streamEnd = (ts = 0): Action => ({ kind: "streamEnd", ts });
const streamError = (error: string, ts = 0): Action => ({ kind: "streamError", error, ts });

// ---------------------------------------------------------------------------
// GROUP 2 — trace assembly (chronological from events, NEVER done.tools_used)
// ---------------------------------------------------------------------------
describe("reducer · trace assembly", () => {
  it("multi-turn two tool cycles: ordered trace + ordered tool_calls; tools_used stays deduped/verbatim", () => {
    const s = run(
      submit({ question: "SMCI 新文章和評論焦點？", provider: "anthropic", model: "claude-opus-4-8", ticker: "SMCI" }),
      f("thinking", { turn: 1, model: "claude-opus-4-8" }),
      f("tool_start", { tool: "get_sa_feed", input: { ticker: "SMCI" } }),
      f("tool_end", { tool: "get_sa_feed", summary: "feed A", chars: 100 }),
      f("thinking", { turn: 2, model: "claude-opus-4-8" }),
      f("tool_start", { tool: "get_sa_comment_focus", input: { ticker: "SMCI", days: 14 } }),
      f("tool_end", { tool: "get_sa_comment_focus", summary: "focus B", chars: 200 }),
      f("thinking", { turn: 3, model: "claude-opus-4-8" }),
      f("done", { answer: "整理完成。", tools_used: ["get_sa_comment_focus", "get_sa_feed"], provider: "anthropic", model: "claude-opus-4-8", token_usage: { total_tokens: 5900, turn_count: 3 } }),
    );
    expect(assistant(s).tool_calls).toEqual([
      { name: "get_sa_feed", input: { ticker: "SMCI" }, result_preview: "feed A" },
      { name: "get_sa_comment_focus", input: { ticker: "SMCI", days: 14 }, result_preview: "focus B" },
    ]);
    expect(assistant(s).tools_used).toEqual(["get_sa_comment_focus", "get_sa_feed"]); // verbatim (reversed/deduped)
    expect(s.footer).toEqual({ total_tokens: 5900, turn_count: 3 });
  });

  it("same tool twice → 2 rows matched to own inputs/summaries; tools_used deduped to 1", () => {
    const s = run(
      submit({ question: "q", model: "m" }),
      f("thinking", { turn: 1, model: "m" }),
      f("tool_start", { tool: "get_sa_feed", input: { ticker: "NVDA" } }),
      f("tool_end", { tool: "get_sa_feed", summary: "r1", chars: 10 }),
      f("thinking", { turn: 2, model: "m" }),
      f("tool_start", { tool: "get_sa_feed", input: { ticker: "AMD" } }),
      f("tool_end", { tool: "get_sa_feed", summary: "r2", chars: 20 }),
      f("done", { answer: "done", tools_used: ["get_sa_feed"], provider: "anthropic", model: "m", token_usage: { total_tokens: 90, turn_count: 3 } }),
    );
    expect(assistant(s).tool_calls).toEqual([
      { name: "get_sa_feed", input: { ticker: "NVDA" }, result_preview: "r1" },
      { name: "get_sa_feed", input: { ticker: "AMD" }, result_preview: "r2" },
    ]);
    expect(assistant(s).tools_used).toEqual(["get_sa_feed"]);
  });

  it("tool_calls frozen on done even with a still-open row (no tool_end before done)", () => {
    const s = run(
      submit({ question: "q", model: "m" }),
      f("thinking", { turn: 1, model: "m" }),
      f("tool_start", { tool: "get_sa_feed", input: { ticker: "NVDA" } }),
      f("done", { answer: "partial-but-final", tools_used: ["get_sa_feed"], provider: "anthropic", model: "m", token_usage: { total_tokens: 9, turn_count: 1 } }),
    );
    expect(assistant(s).tool_calls).toEqual([{ name: "get_sa_feed", input: { ticker: "NVDA" }, result_preview: undefined }]);
    expect(assistant(s).tools_used).toEqual(["get_sa_feed"]);
    expect(s.terminal).toBe("done");
    expect(assistant(s).content).toBe("partial-but-final");
  });
});

// ---------------------------------------------------------------------------
// GROUP 3 — OpenAI SPARSE trace (silent gap; name-only batch; indicator holds)
// ---------------------------------------------------------------------------
describe("reducer · openai sparse", () => {
  it("lone thinking{turn:1} holds indicator true, leaves trace empty", () => {
    const s = run(submit({ question: "NVDA 最新 SA 動態", provider: "openai", model: "gpt-5.4", ticker: "NVDA" }), f("thinking", { turn: 1, model: "gpt-5.4" }));
    expect(s.pending).not.toBeNull();
    expect(s.pending).toMatchObject({ model: "gpt-5.4", thinkingActive: true, trace: [] });
    expect(msgs(s)).toHaveLength(1); // user only
    expect(s.terminal).toBeNull();
  });

  it("batched tool_end (name only, no tool_start) builds closed name-only rows; indicator stays on", () => {
    const s = run(submit({ question: "q", provider: "openai", model: "gpt-5.4" }), f("thinking", { turn: 1, model: "gpt-5.4" }), f("tool_end", { tool: "get_sa_feed" }), f("tool_end", { tool: "get_sa_comment_focus" }));
    expect(s.pending!.trace).toEqual([
      { kind: "tool", name: "get_sa_feed", input: undefined, result_preview: undefined, chars: undefined, done: true },
      { kind: "tool", name: "get_sa_comment_focus", input: undefined, result_preview: undefined, chars: undefined, done: true },
    ]);
    expect(s.pending!.thinkingActive).toBe(true);
    expect(msgs(s)).toHaveLength(1);
  });

  it("done finalizes normally with provider:openai, clears indicator, maxTurns false", () => {
    const s = run(
      submit({ question: "q", provider: "openai", model: "gpt-5.4", ticker: "NVDA", ts: 1000 }),
      f("thinking", { turn: 1, model: "gpt-5.4" }),
      f("tool_end", { tool: "get_sa_feed" }),
      f("tool_end", { tool: "get_sa_comment_focus" }),
      f("done", { answer: "NVDA summary...", tools_used: ["get_sa_feed", "get_sa_comment_focus"], provider: "openai", model: "gpt-5.4", token_usage: { total_tokens: 1500, turn_count: 1 } }, 91000),
    );
    expect(s.pending).toBeNull();
    expect(s.terminal).toBe("done");
    expect(assistant(s)).toMatchObject({ content: "NVDA summary...", provider: "openai", model: "gpt-5.4", tools_used: ["get_sa_feed", "get_sa_comment_focus"], tickers: ["NVDA"], elapsed_seconds: 90, isError: false, maxTurns: false });
    expect(assistant(s).tool_calls).toEqual([
      { name: "get_sa_feed", input: undefined, result_preview: undefined },
      { name: "get_sa_comment_focus", input: undefined, result_preview: undefined },
    ]);
  });

  it("duplicate tool calls → trace longer than deduped done.tools_used (3 rows vs 2 used)", () => {
    const s = run(
      submit({ question: "q", provider: "openai", model: "gpt-5.4" }),
      f("thinking", { turn: 1, model: "gpt-5.4" }),
      f("tool_end", { tool: "get_sa_feed" }),
      f("tool_end", { tool: "get_sa_comment_focus" }),
      f("tool_end", { tool: "get_sa_feed" }),
      f("done", { answer: "a", tools_used: ["get_sa_feed", "get_sa_comment_focus"], provider: "openai", model: "gpt-5.4", token_usage: { total_tokens: 9, turn_count: 1 } }),
    );
    expect(assistant(s).tool_calls.map((c) => c.name)).toEqual(["get_sa_feed", "get_sa_comment_focus", "get_sa_feed"]);
    expect(assistant(s).tools_used).toEqual(["get_sa_feed", "get_sa_comment_focus"]);
    expect(assistant(s).tool_calls.length).toBeGreaterThan(assistant(s).tools_used.length);
  });

  it("thinkingActive stays TRUE across the whole tool_end batch, flips false only on done", () => {
    let s = run(submit({ question: "q", provider: "openai", model: "gpt-5.4" }), f("thinking", { turn: 1, model: "gpt-5.4" }), f("tool_end", { tool: "get_sa_feed" }));
    expect(s.pending!.thinkingActive).toBe(true);
    s = reduce(s, f("tool_end", { tool: "get_sa_comment_focus" }));
    expect(s.pending!.thinkingActive).toBe(true);
    s = reduce(s, f("done", { answer: "done.", tools_used: ["get_sa_feed", "get_sa_comment_focus"], provider: "openai", model: "gpt-5.4", token_usage: { total_tokens: 7, turn_count: 1 } }));
    expect(s.pending).toBeNull();
    expect(s.terminal).toBe("done");
  });

  it("zero-tool turn: empty trace is a valid terminal state", () => {
    const s = run(submit({ question: "q", provider: "openai", model: "gpt-5.4" }), f("thinking", { turn: 1, model: "gpt-5.4" }), f("done", { answer: "No tools needed.", tools_used: [], provider: "openai", model: "gpt-5.4", token_usage: { total_tokens: 42, turn_count: 1 } }));
    expect(assistant(s).tool_calls).toEqual([]);
    expect(assistant(s)).toMatchObject({ content: "No tools needed.", provider: "openai", tools_used: [], isError: false, maxTurns: false });
    expect(s.terminal).toBe("done");
  });

  it("empty-answer done is a normal completion (final_output falsy → '')", () => {
    const s = run(submit({ question: "q", provider: "openai", model: "gpt-5.4" }), f("thinking", { turn: 1, model: "gpt-5.4" }), f("done", { answer: "", tools_used: [], provider: "openai", model: "gpt-5.4", token_usage: { total_tokens: 5, turn_count: 1 } }));
    expect(s.terminal).toBe("done");
    expect(assistant(s)).toMatchObject({ content: "", isError: false, maxTurns: false, tools_used: [] });
    expect(assistant(s).tool_calls).toEqual([]);
  });

  it("identical sentinel string from openai is NOT flagged maxTurns (provider gate)", () => {
    const s = run(submit({ question: "q", provider: "openai", model: "gpt-5.4" }), f("thinking", { turn: 1, model: "gpt-5.4" }), f("tool_end", { tool: "get_sa_feed" }), f("done", { answer: MAX_TURNS_SENTINEL, tools_used: ["get_sa_feed"], provider: "openai", model: "gpt-5.4", token_usage: { total_tokens: 5, turn_count: 1 } }));
    expect(assistant(s)).toMatchObject({ provider: "openai", maxTurns: false, isError: false, content: MAX_TURNS_SENTINEL });
    expect(s.terminal).toBe("done");
  });

  it("agent error frame ({error,scratchpad}, no turn/tools_used) renders error bubble via data.error, clears spinner", () => {
    const s = run(submit({ question: "q", provider: "openai", model: "gpt-5.4" }), f("thinking", { turn: 1, model: "gpt-5.4" }), f("error", { error: "RuntimeError: boom", scratchpad: "/tmp/x.md" }));
    expect(s.pending).toBeNull();
    expect(s.terminal).toBe("error");
    expect(msgs(s)).toHaveLength(2);
    expect(assistant(s)).toMatchObject({ isError: true, content: "RuntimeError: boom", maxTurns: false, tool_calls: [] });
    expect(assistant(s).synthesized).toBeFalsy();
  });

  it("streamEnd after lone thinking synthesizes 連線中斷", () => {
    const s = run(submit({ question: "q", provider: "openai", model: "gpt-5.4" }), f("thinking", { turn: 1, model: "gpt-5.4" }), streamEnd());
    expect(s.pending).toBeNull();
    expect(s.terminal).toBe("disconnect");
    expect(assistant(s)).toMatchObject({ isError: true, synthesized: true, content: "連線中斷", maxTurns: false, tool_calls: [] });
  });

  it("abort during the silent gap drops pending, keeps user message, clears indicator", () => {
    const s = run(submit({ question: "q", provider: "openai", model: "gpt-5.4", ticker: "TSLA" }), f("thinking", { turn: 1, model: "gpt-5.4" }), abort());
    expect(s.pending).toBeNull();
    expect(msgs(s)).toHaveLength(1);
    expect(msgs(s)[0]).toMatchObject({ role: "user", tickers: ["TSLA"] });
    expect(s.terminal).toBe("aborted");
  });

  it("late frames after abort are no-ops (pending===null discriminator)", () => {
    const s = run(submit({ question: "q", provider: "openai", model: "gpt-5.4" }), f("thinking", { turn: 1, model: "gpt-5.4" }), abort(), f("tool_end", { tool: "get_sa_feed" }), f("done", { answer: "a", tools_used: ["get_sa_feed"], provider: "openai", model: "gpt-5.4", token_usage: { total_tokens: 1, turn_count: 1 } }));
    expect(msgs(s)).toHaveLength(1); // user only
    expect(s.pending).toBeNull();
    expect(s.terminal).toBe("aborted");
  });
});

// ---------------------------------------------------------------------------
// GROUP 4 — terminal / error / abort / no-done / frame races
// ---------------------------------------------------------------------------
describe("reducer · terminal & races", () => {
  it("anthropic error frame mid-stream commits isError bubble via data.error, preserves partial trace", () => {
    const s = run(
      submit({ question: "q", provider: "anthropic", model: "m", ticker: "AMD" }),
      f("thinking", { turn: 1, model: "m" }),
      f("tool_start", { tool: "get_sa_feed", input: { ticker: "AMD" } }),
      f("tool_end", { tool: "get_sa_feed", summary: "ok", chars: 10 }),
      f("error", { error: "RuntimeError: db down", turn: 2, tools_used: ["get_sa_feed"], scratchpad: "/tmp/x.md" }),
    );
    expect(s.pending).toBeNull();
    expect(s.terminal).toBe("error");
    expect(msgs(s)).toHaveLength(2);
    expect(assistant(s)).toMatchObject({ isError: true, content: "RuntimeError: db down", maxTurns: false });
    expect(assistant(s).synthesized).toBeFalsy();
    expect(assistant(s).tool_calls).toEqual([{ name: "get_sa_feed", input: { ticker: "AMD" }, result_preview: "ok" }]);
  });

  it("route-layer error {message} with no error key falls through to data.message", () => {
    const s = run(submit({ question: "q", provider: "foo", model: null }), f("error", { message: "Unknown provider: foo" }));
    expect(s.pending).toBeNull();
    expect(s.terminal).toBe("error");
    expect(assistant(s)).toMatchObject({ isError: true, content: "Unknown provider: foo", maxTurns: false, tool_calls: [] });
  });

  it("error precedence: data.error wins when both error and message present", () => {
    const s = run(submit({ question: "q", provider: "anthropic", model: "m" }), f("thinking", { turn: 1, model: "m" }), f("error", { error: "AgentErr: boom", message: "should be ignored", turn: 1, tools_used: [], scratchpad: null }));
    expect(assistant(s)).toMatchObject({ isError: true, content: "AgentErr: boom" });
    expect(s.terminal).toBe("error");
  });

  it("route {message} error AFTER partial agent frames preserves the completed trace", () => {
    const s = run(
      submit({ question: "q", provider: "anthropic", model: "m", ticker: "NVDA" }),
      f("thinking", { turn: 1, model: "m" }),
      f("tool_start", { tool: "get_sa_feed", input: { ticker: "NVDA" } }),
      f("tool_end", { tool: "get_sa_feed", summary: "ok", chars: 2 }),
      f("error", { message: "asyncio.CancelledError" }),
    );
    expect(msgs(s)).toHaveLength(2);
    expect(assistant(s)).toMatchObject({ isError: true, content: "asyncio.CancelledError" });
    expect(assistant(s).tool_calls).toEqual([{ name: "get_sa_feed", input: { ticker: "NVDA" }, result_preview: "ok" }]);
    expect(s.terminal).toBe("error");
  });

  it("done with exact sentinel flags maxTurns, content preserved, isError false", () => {
    const s = run(
      submit({ question: "big query", provider: "anthropic", model: "claude-opus-4-6" }),
      f("thinking", { turn: 1, model: "claude-opus-4-6" }),
      f("tool_start", { tool: "get_sa_feed", input: {} }),
      f("tool_end", { tool: "get_sa_feed", summary: "...", chars: 40 }),
      f("done", { answer: MAX_TURNS_SENTINEL, tools_used: ["get_sa_feed"], provider: "anthropic", model: "claude-opus-4-6", token_usage: { total_tokens: 9000, turn_count: 20 } }),
    );
    expect(s.terminal).toBe("maxTurns");
    expect(assistant(s)).toMatchObject({ maxTurns: true, isError: false, content: MAX_TURNS_SENTINEL, provider: "anthropic" });
    expect(assistant(s).tool_calls).toEqual([{ name: "get_sa_feed", input: {}, result_preview: "..." }]);
  });

  it("near-miss sentinel is a NORMAL done (strict exact-string, not substring)", () => {
    const s = run(submit({ question: "q", provider: "anthropic", model: "m" }), f("thinking", { turn: 1, model: "m" }), f("done", { answer: "Maximum tool calls reached.", tools_used: [], provider: "anthropic", model: "m", token_usage: { total_tokens: 50, turn_count: 1 } }));
    expect(assistant(s)).toMatchObject({ maxTurns: false, isError: false, content: "Maximum tool calls reached." });
    expect(s.terminal).toBe("done");
  });

  it("abort right after submit drops the empty pending, keeps user message", () => {
    const s = run(submit({ question: "q", provider: "openai", model: "gpt-5.4", ticker: "TSLA" }), abort());
    expect(msgs(s)).toHaveLength(1);
    expect(msgs(s)[0]).toMatchObject({ role: "user", content: "q", tickers: ["TSLA"] });
    expect(s.pending).toBeNull();
    expect(s.terminal).toBe("aborted");
  });

  it("abort after some tool_ends drops the completed-so-far trace too", () => {
    const s = run(
      submit({ question: "q", provider: "anthropic", model: "m" }),
      f("thinking", { turn: 1, model: "m" }),
      f("tool_start", { tool: "a", input: {} }), f("tool_end", { tool: "a", summary: "s", chars: 1 }),
      f("tool_start", { tool: "b", input: {} }), f("tool_end", { tool: "b", summary: "s", chars: 1 }),
      abort(),
    );
    expect(msgs(s)).toHaveLength(1);
    expect(s.pending).toBeNull();
    expect(s.terminal).toBe("aborted");
  });

  it("abort after done is a no-op (idempotent; does not corrupt the finalized bubble)", () => {
    const s = run(submit({ question: "q", provider: "anthropic", model: "m" }), f("done", { answer: "ans", tools_used: [], provider: "anthropic", model: "m", token_usage: { total_tokens: 5, turn_count: 1 } }), abort());
    expect(msgs(s)).toHaveLength(2);
    expect(assistant(s)).toMatchObject({ content: "ans", isError: false });
    expect(s.pending).toBeNull();
    expect(s.terminal).toBe("done"); // NOT 'aborted'
  });

  it("streamEnd with partial trace synthesizes 連線中斷 and preserves the trace", () => {
    const s = run(
      submit({ question: "q", provider: "anthropic", model: "m" }),
      f("thinking", { turn: 1, model: "m" }),
      f("tool_start", { tool: "get_sa_feed", input: {} }),
      f("tool_end", { tool: "get_sa_feed", summary: "s", chars: 3 }),
      streamEnd(),
    );
    expect(msgs(s)).toHaveLength(2);
    expect(assistant(s)).toMatchObject({ isError: true, synthesized: true, content: "連線中斷", maxTurns: false });
    expect(assistant(s).tool_calls).toEqual([{ name: "get_sa_feed", input: {}, result_preview: "s" }]);
    expect(s.terminal).toBe("disconnect");
  });

  it("TRUE empty stream — streamEnd before any frame synthesizes 連線中斷", () => {
    const s = run(submit({ question: "q", provider: "openai", model: "gpt-5.4" }), streamEnd());
    expect(msgs(s)).toHaveLength(2);
    expect(assistant(s)).toMatchObject({ isError: true, synthesized: true, content: "連線中斷", maxTurns: false, tool_calls: [] });
    expect(s.pending).toBeNull();
    expect(s.terminal).toBe("disconnect");
  });

  it("streamEnd after done is a no-op (the normal happy-path close)", () => {
    const s = run(submit({ question: "q", provider: "anthropic", model: "m" }), f("done", { answer: "ans", tools_used: [], provider: "anthropic", model: "m", token_usage: { total_tokens: 5, turn_count: 1 } }), streamEnd());
    expect(msgs(s)).toHaveLength(2);
    expect(assistant(s)).toMatchObject({ content: "ans", isError: false });
    expect(assistant(s).synthesized).toBeFalsy();
    expect(s.terminal).toBe("done");
  });

  it("streamEnd after error is a no-op (one terminal bubble per turn)", () => {
    const s = run(submit({ question: "q", provider: "anthropic", model: "m" }), f("error", { error: "boom", turn: 1, tools_used: [], scratchpad: null }), streamEnd());
    expect(msgs(s)).toHaveLength(2);
    expect(assistant(s)).toMatchObject({ isError: true, content: "boom" });
    expect(assistant(s).synthesized).toBeFalsy();
    expect(s.terminal).toBe("error");
  });

  it("frame race: done AFTER error is a no-op (stray done must not overwrite error)", () => {
    const s = run(
      submit({ question: "q", provider: "anthropic", model: "m" }),
      f("thinking", { turn: 1, model: "m" }),
      f("tool_start", { tool: "get_sa_feed", input: {} }),
      f("error", { error: "boom", turn: 2, tools_used: ["get_sa_feed"], scratchpad: null }),
      f("done", { answer: "too late", tools_used: ["get_sa_feed"], provider: "anthropic", model: "m", token_usage: { total_tokens: 5, turn_count: 2 } }),
    );
    expect(msgs(s)).toHaveLength(2);
    expect(assistant(s)).toMatchObject({ isError: true, content: "boom" });
    expect(assistant(s).tool_calls).toEqual([{ name: "get_sa_feed", input: {}, result_preview: undefined }]);
    expect(s.terminal).toBe("error");
  });

  it("frame race: error AFTER done is a no-op (done already finalized)", () => {
    const s = run(submit({ question: "q", provider: "anthropic", model: "m" }), f("done", { answer: "ans", tools_used: [], provider: "anthropic", model: "m", token_usage: { total_tokens: 5, turn_count: 1 } }), f("error", { error: "late boom", turn: 1, tools_used: [], scratchpad: null }));
    expect(msgs(s)).toHaveLength(2);
    expect(assistant(s)).toMatchObject({ content: "ans", isError: false });
    expect(s.terminal).toBe("done");
  });

  it("streamError before any frame commits an error bubble (thrown text, not 連線中斷)", () => {
    const s = run(submit({ question: "q", provider: "openai", model: "gpt-5.4" }), streamError("HTTP 401 Unauthorized"));
    expect(msgs(s)).toHaveLength(2);
    expect(assistant(s)).toMatchObject({ isError: true, content: "HTTP 401 Unauthorized", maxTurns: false });
    expect(assistant(s).synthesized).toBeFalsy();
    expect(s.pending).toBeNull();
    expect(s.terminal).toBe("error");
  });

  it("streamError after done is a no-op (reader-close exception after success)", () => {
    const s = run(submit({ question: "q", provider: "anthropic", model: "m" }), f("done", { answer: "ans", tools_used: [], provider: "anthropic", model: "m", token_usage: { total_tokens: 5, turn_count: 1 } }), streamError("reader aborted"));
    expect(msgs(s)).toHaveLength(2);
    expect(assistant(s)).toMatchObject({ content: "ans", isError: false });
    expect(s.terminal).toBe("done");
  });

  it("submit with empty ticker yields empty tickers[] (never ['']), no NL-parse from answer", () => {
    const s = run(submit({ question: "general market view?", provider: "anthropic", model: "m", ticker: "" }), f("done", { answer: "NVDA and TSLA look strong", tools_used: [], provider: "anthropic", model: "m", token_usage: { total_tokens: 5, turn_count: 1 } }));
    expect(msgs(s)[0]).toMatchObject({ role: "user", content: "general market view?", tickers: [] });
    expect(assistant(s).tickers).toEqual([]); // NOT ['NVDA','TSLA']
    expect(s.threads[0].ticker).toBeNull();
    expect(s.terminal).toBe("done");
  });

  it("thread title derived from first user message (~60), FROZEN after second submit", () => {
    const longQ = "請針對 SMCI 分析最近的 Seeking Alpha 文章、評論焦點以及整體的情緒走向變化趨勢如何";
    const s = run(
      submit({ question: longQ, provider: "anthropic", model: "m", ticker: "SMCI" }),
      f("done", { answer: "a", tools_used: [], provider: "anthropic", model: "m", token_usage: { total_tokens: 5, turn_count: 1 } }, 1000),
      submit({ question: "second question much shorter", provider: "anthropic", model: "m", ts: 2000 }),
    );
    expect(s.threads).toHaveLength(1);
    expect(s.threads[0].title.length).toBeLessThanOrEqual(60);
    expect(s.threads[0].title).toBe(longQ.slice(0, 60));
    expect(msgs(s)).toHaveLength(3); // user, assistant, user(2nd)
  });
});

// ---------------------------------------------------------------------------
// GROUP 5 — thread navigation (left pane: + 新對話 / switch thread)
// ---------------------------------------------------------------------------
describe("reducer · thread navigation", () => {
  const done1 = f("done", { answer: "a1", tools_used: [], provider: "anthropic", model: "m", token_usage: { total_tokens: 5, turn_count: 1 } });

  it("newThread resets active to null + clears pending/terminal/footer, preserving threads & messages", () => {
    const s = run(submit({ question: "first", threadId: "t1" }), done1, { kind: "newThread" });
    expect(s.activeThreadId).toBeNull();
    expect(s.pending).toBeNull();
    expect(s.terminal).toBeNull();
    expect(s.footer).toBeNull();
    expect(s.threads).toHaveLength(1); // preserved
    expect(s.messagesByThread["t1"]).toHaveLength(2); // user + assistant preserved
  });

  it("submit after newThread creates a fresh thread under the new client id (no append to the first)", () => {
    const s = run(submit({ question: "first", threadId: "t1" }), done1, { kind: "newThread" }, submit({ question: "second", threadId: "t2" }));
    expect(s.threads).toHaveLength(2);
    expect(s.activeThreadId).toBe("t2");
    expect(s.threads.find((t) => t.id === "t2")!.title).toBe("second");
    expect(s.messagesByThread["t2"]).toHaveLength(1); // only the new user msg
    expect(s.messagesByThread["t1"]).toHaveLength(2); // untouched
  });

  it("re-submitting the active thread's id appends (multi-turn), does not create a new thread", () => {
    const s = run(submit({ question: "first", threadId: "t1" }), done1, submit({ question: "follow-up", threadId: "t1" }));
    expect(s.threads).toHaveLength(1);
    expect(s.messagesByThread["t1"]).toHaveLength(3); // user, assistant, user
  });

  it("selectThread switches the active thread, preserving both threads' messages", () => {
    const s0 = run(submit({ question: "first", threadId: "t1" }), done1, { kind: "newThread" }, submit({ question: "second", threadId: "t2" }), f("done", { answer: "a2", tools_used: [], provider: "anthropic", model: "m", token_usage: { total_tokens: 5, turn_count: 1 } }));
    const s = reduce(s0, { kind: "selectThread", threadId: "t1" });
    expect(s.activeThreadId).toBe("t1");
    expect(s.pending).toBeNull();
    expect(msgs(s)).toHaveLength(2); // t1's user+assistant
    expect(s.messagesByThread["t2"]).toHaveLength(2); // t2 preserved
  });

  it("newThread/selectThread clear an in-flight pending (defensive; UI blocks first)", () => {
    const mid = run(submit({ question: "q", threadId: "t1" }), f("thinking", { turn: 1, model: "m" }), f("tool_start", { tool: "get_sa_feed", input: {} }));
    expect(mid.pending).not.toBeNull();
    const a = reduce(mid, { kind: "newThread" });
    expect(a.pending).toBeNull();
    expect(a.activeThreadId).toBeNull();
    // no assistant bubble fabricated from the dropped pending
    expect(a.messagesByThread["t1"]).toHaveLength(1); // user only
  });

  it("deleteThread removes an inactive thread and its messages without changing active", () => {
    const s0 = run(
      submit({ question: "first", threadId: "t1" }),
      done1,
      { kind: "newThread" },
      submit({ question: "second", threadId: "t2" }),
      f("done", { answer: "a2", tools_used: [], provider: "anthropic", model: "m", token_usage: { total_tokens: 5, turn_count: 1 } }),
    );
    const s = reduce(s0, { kind: "deleteThread", threadId: "t1" });
    expect(s.activeThreadId).toBe("t2");
    expect(s.threads.map((t) => t.id)).toEqual(["t2"]);
    expect(s.messagesByThread["t1"]).toBeUndefined();
    expect(s.messagesByThread["t2"]).toHaveLength(2);
  });

  it("deleteThread removes the active thread and selects the next remaining thread", () => {
    const s0 = run(
      submit({ question: "first", threadId: "t1" }),
      done1,
      { kind: "newThread" },
      submit({ question: "second", threadId: "t2" }),
      f("done", { answer: "a2", tools_used: [], provider: "anthropic", model: "m", token_usage: { total_tokens: 5, turn_count: 1 } }),
    );
    const s = reduce(s0, { kind: "deleteThread", threadId: "t2" });
    expect(s.activeThreadId).toBe("t1");
    expect(s.threads.map((t) => t.id)).toEqual(["t1"]);
    expect(s.messagesByThread["t2"]).toBeUndefined();
    expect(msgs(s)).toHaveLength(2);
  });

  it("deleteThread on the last thread clears active selection and footer", () => {
    const s0 = run(submit({ question: "first", threadId: "t1" }), done1);
    const s = reduce(s0, { kind: "deleteThread", threadId: "t1" });
    expect(s.activeThreadId).toBeNull();
    expect(s.threads).toEqual([]);
    expect(s.messagesByThread).toEqual({});
    expect(s.footer).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// GROUP 7 — hydrate (reload restores persisted threads + messages, C-2b)
// ---------------------------------------------------------------------------
describe("reducer · hydrate", () => {
  const mkThread = (id: string, title: string): import("./researchReducer").Thread => ({
    id, title, ticker: null, provider: "anthropic", model: "m", created_at: "x", updated_at: "y",
  });
  const mkMsg = (role: "user" | "assistant", content: string): Message => ({
    role, content, tools_used: [], tool_calls: [], tickers: null, created_at: "x",
  });

  it("on a pristine state, hydrate loads persisted threads (active stays null)", () => {
    const s = reduce(initialState, {
      kind: "hydrate",
      threads: [mkThread("ta", "alpha"), mkThread("tb", "beta")],
      messagesByThread: { ta: [mkMsg("user", "qa"), mkMsg("assistant", "aa")], tb: [mkMsg("user", "qb")] },
    });
    expect(s.threads.map((t) => t.id).sort()).toEqual(["ta", "tb"]);
    expect(s.messagesByThread["ta"]).toHaveLength(2);
    expect(s.activeThreadId).toBeNull(); // user picks from the list
    expect(s.pending).toBeNull();
  });

  it("on navigation remount, hydrate can restore a previously active persisted thread", () => {
    const s = reduce(initialState, {
      kind: "hydrate",
      threads: [mkThread("ta", "alpha"), mkThread("tb", "beta")],
      messagesByThread: { ta: [mkMsg("user", "qa")], tb: [mkMsg("user", "qb"), mkMsg("assistant", "ab")] },
      activeThreadId: "tb",
    });
    expect(s.activeThreadId).toBe("tb");
    expect(msgs(s)).toHaveLength(2);
  });

  it("MERGES persisted threads WITHOUT clobbering an in-flight turn (mount-fetch race guard)", () => {
    // A slow mount hydrate must not wipe a turn the user already started.
    const seeded = run(submit({ question: "in-flight", threadId: "t9" }), f("thinking", { turn: 1, model: "m" }));
    expect(seeded.pending).not.toBeNull();
    const s = reduce(seeded, {
      kind: "hydrate",
      threads: [mkThread("ta", "alpha"), mkThread("tb", "beta")],
      messagesByThread: { ta: [mkMsg("user", "qa"), mkMsg("assistant", "aa")], tb: [mkMsg("user", "qb")] },
    });
    expect(s.activeThreadId).toBe("t9"); // in-flight selection preserved
    expect(s.pending).not.toBeNull(); // live turn preserved (NOT wiped)
    expect(s.threads.map((t) => t.id).sort()).toEqual(["t9", "ta", "tb"]); // union by id
    expect(s.messagesByThread["t9"]).toHaveLength(1); // in-session user msg kept
    expect(s.messagesByThread["ta"]).toHaveLength(2); // persisted merged in
  });

  it("after hydrate, selectThread opens a restored thread and submit appends to it", () => {
    const h = reduce(initialState, {
      kind: "hydrate",
      threads: [mkThread("ta", "alpha")],
      messagesByThread: { ta: [mkMsg("user", "qa"), mkMsg("assistant", "aa")] },
    });
    const sel = reduce(h, { kind: "selectThread", threadId: "ta" });
    expect(msgs(sel)).toHaveLength(2);
    const cont = reduce(sel, submit({ question: "follow-up in restored thread", threadId: "ta" }));
    expect(cont.threads).toHaveLength(1); // appended, not a new thread
    expect(cont.messagesByThread["ta"]).toHaveLength(3);
  });
});

// ---------------------------------------------------------------------------
// GROUP 6 — selectFooter (footer derives from the ACTIVE thread's last
// assistant turn, so switching threads restores its footer; fixes gpt-5.5 #1)
// ---------------------------------------------------------------------------
describe("selectFooter", () => {
  const turn = (q: string, total: number, turns: number, ts = 0, threadId = "t1"): Action[] => [
    submit({ question: q, provider: "anthropic", model: "m", ts, threadId }),
    f("done", { answer: "a", tools_used: [], provider: "anthropic", model: "m", token_usage: { total_tokens: total, turn_count: turns } }, ts),
  ];

  it("returns null while a turn is pending", () => {
    const s = run(submit({ question: "q", provider: "anthropic", model: "m" }), f("thinking", { turn: 1, model: "m" }));
    expect(selectFooter(s)).toBeNull();
  });

  it("returns null when there is no active thread", () => {
    expect(selectFooter(initialState)).toBeNull();
  });

  it("derives total_tokens+turn_count from the active thread's last assistant message", () => {
    const s = run(...turn("first", 1500, 2));
    expect(selectFooter(s)).toEqual({ total_tokens: 1500, turn_count: 2 });
  });

  it("returns null when the active thread has no assistant message yet (user-only)", () => {
    const s = run(submit({ question: "q", provider: "anthropic", model: "m" }), { kind: "abort" });
    expect(selectFooter(s)).toBeNull(); // aborted → pending cleared, only the user message remains
  });

  it("restores the SWITCHED-to thread's footer (the bug: footer was cleared on selectThread)", () => {
    const s0 = run(
      ...turn("first thread", 1500, 2, 0, "t1"),
      { kind: "newThread" },
      ...turn("second thread", 9000, 5, 0, "t2"),
    );
    expect(selectFooter(s0)).toEqual({ total_tokens: 9000, turn_count: 5 }); // active = t2
    const s1 = reduce(s0, { kind: "selectThread", threadId: "t1" });
    expect(s1.footer).toBeNull(); // reducer still clears its live footer on switch…
    expect(selectFooter(s1)).toEqual({ total_tokens: 1500, turn_count: 2 }); // …but the selector restores it
  });
});

// Smoke: the sentinel constant is exported for the max-turns group.
it("exports the exact max-turns sentinel", () => {
  expect(MAX_TURNS_SENTINEL).toBe("Maximum tool calls reached. Please try a simpler query.");
});
