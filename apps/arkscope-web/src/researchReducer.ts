// ============================================================================
// C-2a "AI 研究" — PURE event→state reducer (slice 2). NO Date.now / NO I/O.
// Time enters ONLY via the action-envelope `ts` (epoch MILLISECONDS, captured by
// the caller). The SSE wire strips AgentEvent.timestamp (events.py to_sse emits
// only {type,data}), so elapsed cannot be read from the done frame. The slice-1
// parser guarantees only { type:string, data:any } with data defaulting to {}
// (sse.ts) — the reducer must tolerate an under-populated frame.data.
// ============================================================================

import type { SSEFrame } from "./sse";

export type Provider = "anthropic" | "openai" | string; // string: unknown-provider route errors

// ---- Trace rows (THE chronological evidence trace) -------------------------
// Built ONLY from tool_start/tool_end (+ thinking_content), in ARRIVAL order.
// NEVER from done.tools_used (which is list(set(...)) — deduped & unordered).
// Wire keys map IN: tool_start.input->input, tool_end.summary->result_preview,
// tool_end.chars->chars. The wire key `summary` is NEVER a state field.
export interface ToolTraceRow {
  kind: "tool";
  name: string;
  input?: unknown; // tool_start.input (undefined for every OpenAI row)
  result_preview?: string; // tool_end.summary, <=200 chars (undefined for OpenAI)
  chars?: number; // tool_end.chars (undefined for OpenAI)
  done: boolean; // false while open (tool_start seen, tool_end not); true once closed
}
export interface ThinkingTraceRow {
  kind: "thinking";
  text: string; // thinking_content.thinking (Anthropic-only); one row per block
}
export type TraceRow = ToolTraceRow | ThinkingTraceRow;

// ---- Finalized message tool_calls projection (spec §6a; `input`, not `params`)
export interface ToolCall {
  name: string;
  input?: unknown; // Anthropic only; undefined for OpenAI (name-only batch)
  result_preview?: string; // Anthropic only; undefined for OpenAI / still-open rows
}

// ---- DTO: Message (field names == future C-2b columns, spec §6a) ------------
export interface Message {
  role: "user" | "assistant";
  content: string; // user: question; assistant: done.answer | error text | '連線中斷'
  provider?: Provider | null; // assistant: done.provider; user: null
  model?: string | null; // assistant: done.model (== optimistic thinking.model)
  effort?: string | null; // submitted/resolved effort carried outside provider frames
  tools_used: string[]; // VERBATIM done.tools_used (deduped set) — not recomputed
  tool_calls: ToolCall[]; // frozen from the live trace's tool rows on terminal
  token_usage?: Record<string, number> | null; // VERBATIM done.token_usage
  tickers: string[] | null; // from the TYPED ticker field — NEVER parsed from answer
  elapsed_seconds?: number | null; // (terminalTs - startedAt)/1000; assistant-done only
  created_at: string; // ISO from action ts
  isError?: boolean; // error frame / streamError / '連線中斷'
  maxTurns?: boolean; // true IFF provider==='anthropic' AND content === sentinel
  synthesized?: boolean; // true ONLY for the client-fabricated '連線中斷' bubble
}

export interface RetryCandidate {
  question: string;
  provider: Provider;
  model: string | null;
  ticker: string | null;
}

// ---- DTO: Thread (snapshot at first turn, frozen) --------------------------
export interface Thread {
  id: string;
  title: string; // first user message, sliced to ~60 chars; frozen after first submit
  ticker: string | null; // typed ticker (uppercased) of the first turn
  provider: Provider | null;
  model: string | null;
  created_at: string;
  updated_at: string; // advances on done (and other terminals)
}

// ---- In-flight working state (held OUT of messages so abort drops it clean) -
// `pending !== null` is THE discriminator: every terminal/lifecycle no-op
// decision keys on pending===null (NOT on terminal==='done').
export interface PendingTurn {
  threadId: string;
  startedAt: number; // submit.ts (epoch ms) — sole wall-clock source for elapsed
  provider: Provider;
  model: string | null; // optimistic from submit, overwritten by thinking.model
  effort: string | null;
  interimText: string; // text.content (Anthropic interim); replaced by done.answer
  trace: TraceRow[]; // chronological; tool rows + inline thinking lines
  thinkingActive: boolean; // true on submit; cleared on FIRST of text|tool_start|done
  turnCount: number; // advanced by thinking{turn}; footer of record = done.turn_count
  tickers: string[] | null; // typed ticker carried from submit, frozen into the message
}

// ---- Reducer State ----------------------------------------------------------
export interface State {
  threads: Thread[];
  activeThreadId: string | null;
  messagesByThread: Record<string, Message[]>;
  pending: PendingTurn | null;
  footer: { total_tokens?: number; turn_count?: number } | null;
  terminal: null | "done" | "maxTurns" | "error" | "disconnect" | "aborted";
}

// ---- Action union (ts is epoch MS; submit + frame carry ts so elapsed is pure)
export type Action =
  // threadId is CLIENT-OWNED (UI generates a stable uuid at 新對話, reuses the
  // active thread's id to continue). New thread iff no thread with that id exists.
  | { kind: "submit"; question: string; provider: Provider; model: string | null; effort?: string | null; ticker?: string | null; ts: number; threadId: string }
  | { kind: "attachRun"; threadId: string; provider: Provider; model: string | null; effort?: string | null; ticker?: string | null; ts: number }
  | { kind: "frame"; frame: SSEFrame; ts: number }
  | { kind: "abort"; ts?: number }
  | { kind: "streamEnd"; ts?: number }
  | { kind: "streamError"; error: string; ts?: number }
  | { kind: "newThread" } // + 新對話: next submit starts a fresh thread (UI blocks while pending)
  | { kind: "selectThread"; threadId: string } // left-pane switch (UI blocks while pending)
  | { kind: "deleteThread"; threadId: string } // persisted delete succeeded; remove local copy
  | { kind: "hydrate"; threads: Thread[]; messagesByThread: Record<string, Message[]>; activeThreadId?: string | null }; // reload restore (C-2b)

// The exact max-turns sentinel (Anthropic-only; agent.py:516). EXACT equality.
export const MAX_TURNS_SENTINEL = "Maximum tool calls reached. Please try a simpler query.";

export const initialState: State = {
  threads: [],
  activeThreadId: null,
  messagesByThread: {},
  pending: null,
  footer: null,
  terminal: null,
};

const TITLE_MAX = 60;
const iso = (ms: number) => new Date(ms).toISOString();

/** Typed ticker field → [] when blank/absent, else a single uppercased symbol. */
function normTickers(ticker?: string | null): string[] {
  const t = (ticker ?? "").trim().toUpperCase();
  return t ? [t] : [];
}

/** Freeze the live trace's tool rows into the message tool_calls projection. */
function toolCalls(trace: TraceRow[]): ToolCall[] {
  return trace
    .filter((r): r is ToolTraceRow => r.kind === "tool")
    .map((r) => ({ name: r.name, input: r.input, result_preview: r.result_preview }));
}

/** Commit a terminal assistant message: append, drop pending, advance the thread. */
function commit(state: State, p: PendingTurn, msg: Message, terminal: State["terminal"], ts: number): State {
  const prev = state.messagesByThread[p.threadId] ?? [];
  return {
    ...state,
    threads: state.threads.map((t) => (t.id === p.threadId ? { ...t, updated_at: iso(ts) } : t)),
    messagesByThread: { ...state.messagesByThread, [p.threadId]: [...prev, msg] },
    pending: null,
    terminal,
  };
}

function onSubmit(state: State, a: Extract<Action, { kind: "submit" }>): State {
  const threadId = a.threadId; // client-owned; new iff not already present
  const isNew = !state.threads.some((t) => t.id === threadId);
  const createdIso = iso(a.ts);
  const tickers = normTickers(a.ticker);
  const userMsg: Message = {
    role: "user", content: a.question, provider: null, model: null,
    tools_used: [], tool_calls: [], token_usage: null, tickers, created_at: createdIso,
  };
  const threads = isNew
    ? [...state.threads, {
        id: threadId, title: a.question.slice(0, TITLE_MAX),
        ticker: tickers.length ? tickers[0] : null,
        provider: a.provider, model: a.model, created_at: createdIso, updated_at: createdIso,
      }]
    : state.threads;
  const prev = state.messagesByThread[threadId] ?? [];
  const pending: PendingTurn = {
    threadId, startedAt: a.ts, provider: a.provider, model: a.model, effort: a.effort ?? null,
    interimText: "", trace: [], thinkingActive: true, turnCount: 0, tickers,
  };
  return {
    ...state, threads, activeThreadId: threadId,
    messagesByThread: { ...state.messagesByThread, [threadId]: [...prev, userMsg] },
    pending, footer: null, terminal: null,
  };
}

function onAttachRun(state: State, a: Extract<Action, { kind: "attachRun" }>): State {
  const tickers = normTickers(a.ticker);
  const pending: PendingTurn = {
    threadId: a.threadId,
    startedAt: a.ts,
    provider: a.provider,
    model: a.model,
    effort: a.effort ?? null,
    interimText: "",
    trace: [],
    thinkingActive: true,
    turnCount: 0,
    tickers,
  };
  return { ...state, activeThreadId: a.threadId, pending, footer: null, terminal: null };
}

/** Build a terminal isError/synthesized assistant message, preserving the partial trace. */
function terminalMsg(p: PendingTurn, content: string, ts: number, synthesized?: boolean): Message {
  return {
    role: "assistant", content, provider: p.provider, model: p.model, effort: p.effort,
    tools_used: [], tool_calls: toolCalls(p.trace), token_usage: null,
    tickers: p.tickers, elapsed_seconds: (ts - p.startedAt) / 1000, created_at: iso(ts),
    isError: true, maxTurns: false, synthesized,
  };
}

function onDone(state: State, p: PendingTurn, data: Record<string, unknown>, ts: number): State {
  const content = typeof data.answer === "string" ? data.answer : "";
  const provider = (data.provider as Provider) ?? p.provider;
  const model = (data.model as string) ?? p.model;
  const tools_used = Array.isArray(data.tools_used) ? (data.tools_used as string[]) : [];
  const token_usage = (data.token_usage as Record<string, number>) ?? null;
  const maxTurns = provider === "anthropic" && content === MAX_TURNS_SENTINEL;
  const msg: Message = {
    role: "assistant", content, provider, model, effort: p.effort, tools_used,
    tool_calls: toolCalls(p.trace), token_usage, tickers: p.tickers,
    elapsed_seconds: (ts - p.startedAt) / 1000, created_at: iso(ts),
    isError: false, maxTurns,
  };
  return {
    ...commit(state, p, msg, maxTurns ? "maxTurns" : "done", ts),
    footer: { total_tokens: token_usage?.total_tokens, turn_count: token_usage?.turn_count },
  };
}

function onFrame(state: State, a: Extract<Action, { kind: "frame" }>): State {
  const p = state.pending;
  if (p === null) return state; // exactly-once: post-terminal stray frame is a no-op
  const { type } = a.frame;
  const data = (a.frame.data ?? {}) as Record<string, any>;
  switch (type) {
    case "thinking":
      return { ...state, pending: { ...p, model: data.model ?? p.model, turnCount: typeof data.turn === "number" ? data.turn : p.turnCount } };
    case "thinking_content":
      return { ...state, pending: { ...p, trace: [...p.trace, { kind: "thinking", text: data.thinking }] } };
    case "text":
      return { ...state, pending: { ...p, thinkingActive: false, interimText: data.content ?? "" } };
    case "tool_start":
      return { ...state, pending: { ...p, thinkingActive: false, trace: [...p.trace, { kind: "tool", name: data.tool, input: data.input, result_preview: undefined, chars: undefined, done: false }] } };
    case "tool_end": {
      const trace = [...p.trace];
      let idx = -1;
      for (let i = trace.length - 1; i >= 0; i--) {
        const r = trace[i];
        if (r.kind === "tool" && !r.done) { idx = i; break; }
      }
      if (idx >= 0) {
        trace[idx] = { ...(trace[idx] as ToolTraceRow), result_preview: data.summary, chars: data.chars, done: true };
      } else {
        // OpenAI name-only batch: no open row → append an already-closed row.
        trace.push({ kind: "tool", name: data.tool, input: undefined, result_preview: data.summary, chars: data.chars, done: true });
      }
      return { ...state, pending: { ...p, trace } };
    }
    case "done":
      return onDone(state, p, data, a.ts);
    case "error": {
      // Agent error {error,...} or route-layer {message}; data.error wins.
      const content = (data.error ?? data.message ?? "") as string;
      return commit(state, p, terminalMsg(p, content, a.ts), "error", a.ts);
    }
    default:
      return state; // unknown frame type
  }
}

function onAbort(state: State): State {
  if (state.pending === null) return state; // no-op: abort after a terminal
  // Drop the in-flight assistant turn; the user message was committed at submit.
  return { ...state, pending: null, terminal: "aborted" };
}

function onStreamEnd(state: State, a: Extract<Action, { kind: "streamEnd" }>): State {
  const p = state.pending;
  if (p === null) return state; // no-op: clean close after done/error
  const ts = a.ts ?? p.startedAt; // ts optional → avoid Invalid Date in commit
  return commit(state, p, terminalMsg(p, "連線中斷", ts, true), "disconnect", ts);
}

function onStreamError(state: State, a: Extract<Action, { kind: "streamError" }>): State {
  const p = state.pending;
  if (p === null) return state; // no-op: reader-close throw after a terminal
  const ts = a.ts ?? p.startedAt;
  return commit(state, p, terminalMsg(p, a.error, ts), "error", ts);
}

/**
 * Trace-pane footer (total_tokens · turn_count) for display. Derived from the
 * ACTIVE thread's last assistant message rather than `state.footer`, so that
 * switching threads restores that thread's footer (state.footer is the live
 * current-turn value and is cleared on selectThread/newThread). null while a
 * turn is pending or the active thread has no completed assistant turn yet.
 */
export function selectFooter(state: State): { total_tokens?: number; turn_count?: number } | null {
  if (state.pending) return null;
  const msgs = state.activeThreadId ? state.messagesByThread[state.activeThreadId] ?? [] : [];
  for (let i = msgs.length - 1; i >= 0; i--) {
    if (msgs[i].role === "assistant") {
      const u = msgs[i].token_usage;
      return u ? { total_tokens: u.total_tokens, turn_count: u.turn_count } : null;
    }
  }
  return null;
}

export function lastRetryCandidate(messages: Message[]): RetryCandidate | null {
  if (messages.length < 2) return null;
  const last = messages[messages.length - 1];
  const prev = messages[messages.length - 2];
  if (last.role !== "assistant" || prev.role !== "user") return null;
  if (!last.isError && !last.maxTurns) return null;
  if (!prev.content.trim()) return null;
  const provider = last.provider ?? null;
  if (provider !== "anthropic" && provider !== "openai") return null;
  return {
    question: prev.content,
    provider,
    model: last.model ?? null,
    ticker: prev.tickers?.[0] ?? null,
  };
}

export function reduce(state: State, action: Action): State {
  switch (action.kind) {
    case "submit":
      return onSubmit(state, action);
    case "attachRun":
      return onAttachRun(state, action);
    case "frame":
      return onFrame(state, action);
    case "abort":
      return onAbort(state);
    case "streamEnd":
      return onStreamEnd(state, action);
    case "streamError":
      return onStreamError(state, action);
    case "newThread":
      // Drop active thread + any in-flight pending; threads/messages preserved.
      return { ...state, activeThreadId: null, pending: null, footer: null, terminal: null };
    case "selectThread":
      return { ...state, activeThreadId: action.threadId, pending: null, footer: null, terminal: null };
    case "deleteThread": {
      const threads = state.threads.filter((t) => t.id !== action.threadId);
      const { [action.threadId]: _deleted, ...messagesByThread } = state.messagesByThread;
      const activeThreadId = state.activeThreadId === action.threadId
        ? (threads[0]?.id ?? null)
        : state.activeThreadId;
      return { ...state, threads, activeThreadId, messagesByThread, footer: null, terminal: null };
    }
    case "hydrate": {
      // Reload restore. MERGE (not replace) so a slow mount-fetch landing after
      // the user already started a turn can't clobber the in-flight pending /
      // active selection (the mount-fetch race). Union threads by id, newest
      // activity first; in-session messages win over persisted for the same id.
      const seen = new Set(state.threads.map((t) => t.id));
      const threads = [...state.threads, ...action.threads.filter((t) => !seen.has(t.id))].sort(
        (a, b) => (a.updated_at < b.updated_at ? 1 : a.updated_at > b.updated_at ? -1 : 0),
      );
      const restoredActive = action.activeThreadId && threads.some((t) => t.id === action.activeThreadId)
        ? action.activeThreadId
        : null;
      return {
        ...state, // preserves activeThreadId / pending / footer / terminal
        activeThreadId: state.activeThreadId ?? restoredActive,
        threads,
        messagesByThread: { ...action.messagesByThread, ...state.messagesByThread },
      };
    }
    default:
      return state; // unreachable for known kinds; guards against a silent undefined
  }
}
