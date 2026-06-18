// AI 研究 — the evidence-first research console (Layer C-2, persisted).
//
// Thin UI over the pure researchReducer (the conversation authority). The UI
// owns ONLY the AbortController + lifecycle discipline:
//   • submit is disabled while a turn is pending;
//   • 新對話 / thread-switch / delete are disabled while pending so a live
//     stream cannot be accidentally interrupted by navigation;
//   • on normal close → streamEnd (reducer no-ops if done already finalized);
//   • on a thrown read → abort if it was deliberate, else streamError;
//   • a superseded stream (a newer turn took over abortRef) never commits.
// Persistence (C-2b): /query/stream best-effort-persists each turn to the local
// ResearchThreadStore; on mount this fetches + `hydrate`s the threads/messages
// (merge, so a late hydrate can't clobber a live turn). Threads survive reload;
// the provider pick is per-session (re-chosen after reload), not persisted.
//
// Provider selection is USER-CHOSEN — no global default: 1 provider available →
// auto-select; configured AI 研究 route → auto-select that route; 0 → disable
// input. The model/effort per query is the ai_research route (Settings → Models,
// Slice B2), resolved for the chosen provider — see researchModelFor.
// Per-provider trace behaviour comes from a descriptor map, not an
// OpenAI/Anthropic binary, so compatible providers can slot in later.

import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react";

import {
  deleteResearchThread, getQueryProviders, getResearchThreads, getResearchMessages,
  getRuntimeConfig, streamQuery,
  type ResearchMessageDTO, type ResearchThreadDTO, type RuntimeConfig,
} from "./api";
import { MarkdownView } from "./MarkdownView";
import {
  initialState,
  MAX_TURNS_SENTINEL,
  reduce,
  selectFooter,
  type Message,
  type Thread,
  type ToolTraceRow,
  type TraceRow,
} from "./researchReducer";

// Map persisted DTOs → the in-memory reducer shapes (field names already align,
// spec §6a). Persisted turns are completed/non-error by construction (we only
// persist on `done`), so isError/maxTurns default false.
const toClientThread = (t: ResearchThreadDTO): Thread => ({
  id: t.id, title: t.title, ticker: t.ticker, provider: t.provider, model: t.model,
  created_at: t.created_at, updated_at: t.updated_at,
});
const toClientMessage = (m: ResearchMessageDTO): Message => ({
  role: m.role, content: m.content, provider: m.provider, model: m.model,
  tools_used: m.tools_used ?? [], tool_calls: m.tool_calls ?? [],
  token_usage: m.token_usage, tickers: m.tickers,
  elapsed_seconds: m.elapsed_seconds, created_at: m.created_at,
  isError: m.is_error ?? false, // persisted error turns (MUST-FIX 2) restore as error bubbles
  // store has no maxTurns column — re-derive the badge the same way the reducer does (SF2)
  maxTurns: m.provider === "anthropic" && m.content === MAX_TURNS_SENTINEL,
});

const PROVIDER_IDS = ["anthropic", "openai"] as const;
type ProviderId = (typeof PROVIDER_IDS)[number];

// trace_mode drives the live-trace vs silent-until-done affordance; copy stays
// neutral. A new OpenAI-compatible provider is a row here, not a render rewrite.
const PRESENTATION: Record<ProviderId, { label: string; trace_mode: "live" | "post_run"; trace_note: string; auth_mode_label: string }> = {
  // auth_mode_label reflects what's WIRED today (API key). setup-token / OAuth
  // are planned auth modes (auth-driver slices S3/S4), not yet usable here.
  anthropic: { label: "Anthropic", trace_mode: "live", trace_note: "即時工具追蹤", auth_mode_label: "API key（setup-token 計畫中）" },
  openai: { label: "OpenAI", trace_mode: "post_run", trace_note: "完成後一次顯示工具追蹤", auth_mode_label: "API key（OAuth 計畫中）" },
};

// Suggested prompts scoped to the C-1 SA primitives (get_sa_feed / get_sa_comment_focus).
const SUGGESTED = [
  { ticker: "SMCI", text: "最近 SA 對 SMCI 有什麼新文章和評論焦點？" },
  { ticker: "CLS", text: "CLS 過去 14 天的 SA 評論焦點與情緒變化？" },
  { ticker: "MXL", text: "MXL 的高價值留言在吵什麼？焦點是什麼？" },
  { ticker: "NVDA", text: "NVDA 最新 SA 動態與評論焦點重點整理。" },
];

export function ResearchView({ onOpenTicker }: { onOpenTicker: (ticker: string) => void }) {
  const [state, dispatch] = useReducer(reduce, initialState);
  const [question, setQuestion] = useState("");
  const [tickerInput, setTickerInput] = useState("");
  const [provider, setProvider] = useState<ProviderId | null>(null); // user-chosen, session-scoped
  const [runtime, setRuntime] = useState<RuntimeConfig | null>(null);
  const [sdk, setSdk] = useState<Record<string, boolean> | null>(null);
  const [booting, setBooting] = useState(true);
  const [autoRouteSelection, setAutoRouteSelection] = useState(true);
  const [threadError, setThreadError] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);

  // --- provider availability = SDK present (/query/providers) AND key set ----
  const availability = useMemo(() => {
    return PROVIDER_IDS.map((id) => {
      const hasKey = runtime ? runtime[id].key_set : false;
      const hasSdk = sdk ? sdk[id] !== false : false; // missing entry → treat as unavailable
      return { id, available: hasKey && hasSdk, model: runtime ? runtime[id].model : "" };
    });
  }, [runtime, sdk]);
  const availableIds = availability.filter((a) => a.available).map((a) => a.id);
  const configuredProvider = runtime?.ai_research?.source !== "default"
    ? (runtime?.ai_research?.provider as ProviderId | undefined)
    : undefined;
  const configuredRouteKey = runtime?.ai_research
    ? `${runtime.ai_research.source}:${runtime.ai_research.provider}:${runtime.ai_research.model}:${runtime.ai_research.effort}`
    : "";

  useEffect(() => {
    let alive = true;
    void (async () => {
      try {
        const [rc, qp] = await Promise.all([getRuntimeConfig(), getQueryProviders()]);
        if (!alive) return;
        setRuntime(rc);
        setSdk(Object.fromEntries(Object.entries(qp.providers).map(([k, v]) => [k, !!v.available])));
      } catch {
        if (alive) { setRuntime(null); setSdk(null); }
      } finally {
        if (alive) setBooting(false);
      }
    })();
    return () => { alive = false; };
  }, []);

  // Prefer the configured AI 研究 route when available. If the user explicitly
  // clicks "切換", hold at the chooser until they pick another route.
  useEffect(() => {
    if (provider !== null) return;
    if (autoRouteSelection && configuredProvider && availableIds.includes(configuredProvider)) {
      setProvider(configuredProvider);
      return;
    }
    if (availableIds.length === 1) setProvider(availableIds[0] as ProviderId);
  }, [provider, availableIds, autoRouteSelection, configuredProvider]);

  // If Settings changes the AI 研究 route, let the page follow the new route.
  useEffect(() => {
    setAutoRouteSelection(true);
    setProvider(null);
  }, [configuredRouteKey]);

  // Reload hydration (C-2b): on mount, restore persisted threads + their
  // messages from the store into the reducer. Best-effort — an empty/failed
  // fetch just starts clean. (v1 eager-loads each thread's messages; fine for a
  // local single-user store, revisit with lazy-per-thread if thread counts grow.)
  useEffect(() => {
    let alive = true;
    void (async () => {
      try {
        const { threads } = await getResearchThreads();
        const entries = await Promise.all(
          threads.map(async (t) => [t.id, (await getResearchMessages(t.id)).messages.map(toClientMessage)] as const),
        );
        if (!alive || threads.length === 0) return;
        dispatch({ kind: "hydrate", threads: threads.map(toClientThread), messagesByThread: Object.fromEntries(entries) });
      } catch {
        /* hydration is best-effort; a clean empty start is fine */
      }
    })();
    return () => { alive = false; };
  }, []);

  // Abort any in-flight stream on unmount.
  useEffect(() => () => abortRef.current?.abort(), []);

  // --- streaming runner: reducer is the authority; UI owns the controller ----
  // Sends the RAW question + ticker + thread_id; the server frames the agent
  // prompt and persists the raw question (criterion #2).
  const runStream = useCallback(async (body: { question: string; provider: ProviderId; thread_id: string; ticker: string | null }) => {
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      for await (const frame of streamQuery(body, controller.signal)) {
        if (abortRef.current !== controller) return; // superseded by a newer turn
        dispatch({ kind: "frame", frame, ts: Date.now() });
      }
      if (abortRef.current === controller) dispatch({ kind: "streamEnd", ts: Date.now() });
    } catch (e) {
      if (abortRef.current !== controller) return; // superseded — its terminal already ran
      if (controller.signal.aborted) dispatch({ kind: "abort", ts: Date.now() });
      else dispatch({ kind: "streamError", error: e instanceof Error ? e.message : String(e), ts: Date.now() });
    } finally {
      if (abortRef.current === controller) abortRef.current = null;
    }
  }, []);

  const submit = useCallback(() => {
    const q = question.trim();
    if (!q || !provider || state.pending) return; // disabled while pending (defensive)
    const ticker = tickerInput.trim().toUpperCase() || null;
    // Client-owned thread id: reuse the active thread to continue, else a fresh
    // uuid for a new conversation (agreed reducer↔store id model).
    const threadId = state.activeThreadId ?? crypto.randomUUID();
    dispatch({ kind: "submit", question: q, provider, model: null, ticker, ts: Date.now(), threadId });
    setQuestion("");
    setThreadError(null);
    void runStream({ question: q, provider, thread_id: threadId, ticker }); // raw question; server frames + persists
  }, [question, tickerInput, provider, state.pending, state.activeThreadId, runStream]);

  // Abort the live stream + drop the pending turn (explicit Stop only).
  const stopStream = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    dispatch({ kind: "abort", ts: Date.now() });
  }, []);
  const newThread = useCallback(() => {
    if (state.pending) return;
    setThreadError(null);
    dispatch({ kind: "newThread" });
  }, [state.pending]);
  const selectThread = useCallback((id: string) => {
    if (state.pending) return;
    setThreadError(null);
    dispatch({ kind: "selectThread", threadId: id });
  }, [state.pending]);
  const deleteThread = useCallback(async (id: string) => {
    if (state.pending) return;
    setThreadError(null);
    try {
      await deleteResearchThread(id);
      dispatch({ kind: "deleteThread", threadId: id });
    } catch (e) {
      setThreadError(e instanceof Error ? e.message : String(e));
    }
  }, [state.pending]);

  // --- derived view state ----------------------------------------------------
  const msgs = state.activeThreadId ? state.messagesByThread[state.activeThreadId] ?? [] : [];
  const lastAssistant = [...msgs].reverse().find((m) => m.role === "assistant");
  const traceRows: TraceRow[] = state.pending
    ? state.pending.trace
    : (lastAssistant?.tool_calls ?? []).map((c) => ({ kind: "tool", name: c.name, input: c.input, result_preview: c.result_preview, chars: undefined, done: true } as ToolTraceRow));
  const pendingPresentation = state.pending ? PRESENTATION[state.pending.provider as ProviderId] : null;
  const footer = selectFooter(state); // derived from the active thread, survives thread-switch
  const noProvider = !booting && availableIds.length === 0;
  const needChooser = !provider && availableIds.length > 1;
  // The model/effort a query will ACTUALLY use for a provider: the configured
  // ai_research route when its provider matches, else the provider's default-tier
  // model (= resolve_research_route's fallback). Keeps the send-area chip honest
  // vs the header (don't show the default tier when a cheaper route is set).
  const researchModelFor = (pid: string): string => {
    const r = runtime?.ai_research;
    if (r && r.provider === pid && r.source !== "default") return r.model;
    return availability.find((a) => a.id === pid)?.model || "?";
  };
  const researchEffortFor = (pid: string): string | null => {
    const r = runtime?.ai_research;
    if (r && r.provider === pid && r.source !== "default" && r.effort && r.effort !== "default") return r.effort;
    return null;
  };

  return (
    <main className="main research">
      <div className="surface-head">
        <h1 className="surface-title">AI 研究</h1>
        <span className="muted tiny">工具追蹤與證據整理，支援即時或完成後顯示，依 provider 而定；對話保存於本地（reload 後保留），即時工具追蹤為 ephemeral</span>
        {runtime?.ai_research && (
          runtime.ai_research.source !== "default" ? (
            <span className="muted tiny">
              研究模型：{runtime.ai_research.provider} · {runtime.ai_research.model}
              {runtime.ai_research.effort && runtime.ai_research.effort !== "default" ? ` · ${runtime.ai_research.effort}` : ""}
              {`（套用於 ${runtime.ai_research.provider} 查詢；其他 provider 用預設層）`}
            </span>
          ) : (
            <span className="muted tiny">研究模型：未設定 — 各 provider 用預設層（設定 → 模型可指定，例如 OpenAI · gpt-5.4-mini · low）</span>
          )
        )}
      </div>

      <div className="research-grid">
        {/* ── Left: thread list ───────────────────────────────────────── */}
        <aside className="research-threads">
          <button
            className="btn-ghost small"
            onClick={newThread}
            disabled={!!state.pending}
            title={state.pending ? "目前回應執行中，請先停止或等待完成" : "新增對話"}
          >
            ＋ 新對話
          </button>
          {state.pending && <p className="muted tiny">回應執行中，完成或停止後可切換／刪除對話。</p>}
          {threadError && <p className="error-text tiny">{threadError}</p>}
          {state.threads.length === 0 ? (
            <p className="muted tiny" style={{ marginTop: 10 }}>尚無對話。</p>
          ) : (
            <ul className="research-threadlist">
              {state.threads.map((t) => (
                <li key={t.id}>
                  <div className={`research-threadrow ${t.id === state.activeThreadId ? "active" : ""}`}>
                    <button
                      className="research-threaditem"
                      onClick={() => selectThread(t.id)}
                      disabled={!!state.pending}
                      title={state.pending ? "目前回應執行中，請先停止或等待完成" : t.title}
                    >
                      <span className="research-threadtitle">{t.title || "（未命名）"}</span>
                      {t.ticker && <span className="list-chip tiny">{t.ticker}</span>}
                    </button>
                    <button
                      className="research-threaddelete"
                      onClick={() => void deleteThread(t.id)}
                      disabled={!!state.pending}
                      title={state.pending ? "目前回應執行中，請先停止或等待完成" : "刪除對話"}
                      aria-label={`刪除對話 ${t.title || t.id}`}
                    >
                      ×
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </aside>

        {/* ── Center: conversation ────────────────────────────────────── */}
        <section className="research-convo">
          <div className="research-messages">
            {msgs.length === 0 && !state.pending ? (
              <div className="research-empty">
                <p className="muted">問一個開放式問題，看 agent 如何用工具調查並整理證據。</p>
                <div className="research-suggest">
                  {SUGGESTED.map((s) => (
                    <button key={s.text} className="btn-ghost small" onClick={() => { setQuestion(s.text); setTickerInput(s.ticker); }}>
                      {s.text}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              msgs.map((m, i) => <Bubble key={i} m={m} onOpenTicker={onOpenTicker} />)
            )}

            {state.pending && (
              <div className="research-bubble assistant pending">
                {state.pending.interimText && <div className="research-interim muted">{state.pending.interimText}</div>}
                {state.pending.thinkingActive && (
                  <div className="research-thinking muted tiny">
                    <span className="research-spinner" />
                    {pendingPresentation?.trace_mode === "post_run"
                      ? `${PRESENTATION[state.pending.provider as ProviderId]?.label ?? state.pending.provider} 執行中，完成後一次顯示工具追蹤…`
                      : "思考中…"}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* input + provider control */}
          <div className="research-input">
            {booting ? (
              <p className="muted tiny">載入 provider…</p>
            ) : noProvider ? (
              <p className="muted">尚未設定可用的 AI provider（API key）。請到「設定」頁設定後再使用。</p>
            ) : (
              <>
                <div className="research-providerbar">
                  {needChooser ? (
                    <>
                      <span className="muted tiny">選擇研究路線：</span>
                      {availability.filter((a) => a.available).map((a) => (
                        <button
                          key={a.id}
                          className="btn-ghost small"
                          onClick={() => { setAutoRouteSelection(false); setProvider(a.id as ProviderId); }}
                          title={`${PRESENTATION[a.id as ProviderId].auth_mode_label}；${PRESENTATION[a.id as ProviderId].trace_note}`}
                        >
                          {PRESENTATION[a.id as ProviderId].label} / {researchModelFor(a.id)}
                          {researchEffortFor(a.id) ? ` · ${researchEffortFor(a.id)}` : ""}
                        </button>
                      ))}
                    </>
                  ) : provider ? (
                    <>
                      <span className="list-chip prov">{PRESENTATION[provider].label} / {researchModelFor(provider)}{researchEffortFor(provider) ? ` · ${researchEffortFor(provider)}` : ""}</span>
                      <span className="muted tiny">{PRESENTATION[provider].trace_note}</span>
                      {availableIds.length > 1 && (
                        <button
                          className="btn-ghost tiny"
                          onClick={() => { setAutoRouteSelection(false); setProvider(null); }}
                          title="切換研究路線"
                        >
                          切換
                        </button>
                      )}
                    </>
                  ) : null}
                </div>
                <div className="research-inputrow">
                  <input
                    className="news-ticker"
                    placeholder="Ticker（選填）"
                    value={tickerInput}
                    onChange={(e) => setTickerInput(e.target.value)}
                  />
                  <textarea
                    className="research-textarea"
                    placeholder="輸入問題…（Enter 送出，Shift+Enter 換行）"
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } }}
                    rows={2}
                  />
                  {state.pending ? (
                    <button className="btn-ghost danger" onClick={stopStream}>停止</button>
                  ) : (
                    <button className="btn-ghost" onClick={submit} disabled={!provider || !question.trim()}>送出</button>
                  )}
                </div>
              </>
            )}
          </div>
        </section>

        {/* ── Right: evidence / tool trace ────────────────────────────── */}
        <aside className="research-trace">
          <div className="research-trace-head">
            <h3 className="surface-title tiny">證據·工具追蹤</h3>
          </div>
          {traceRows.length === 0 ? (
            <p className="muted tiny">
              {state.pending?.thinkingActive && pendingPresentation?.trace_mode === "post_run"
                ? `${PRESENTATION[state.pending!.provider as ProviderId]?.label} 完成後一次顯示。`
                : "尚無工具呼叫。"}
            </p>
          ) : (
            <ul className="research-tracelist">
              {traceRows.map((r, i) => <TraceRowView key={i} row={r} />)}
            </ul>
          )}
          {footer && (
            <div className="research-trace-footer muted tiny">
              {typeof footer.total_tokens === "number" && <span>tokens {footer.total_tokens.toLocaleString()}</span>}
              {typeof footer.turn_count === "number" && <span> · turns {footer.turn_count}</span>}
            </div>
          )}
        </aside>
      </div>
    </main>
  );
}

function Bubble({ m, onOpenTicker }: { m: Message; onOpenTicker: (t: string) => void }) {
  const cls = `research-bubble ${m.role}${m.isError ? " error" : ""}`;
  return (
    <div className={cls}>
      {m.role === "assistant" && (m.model || m.maxTurns) && (
        <div className="research-bubble-meta muted tiny">
          {m.model && <span className="research-model">{m.provider}/{m.model}</span>}
          {m.maxTurns && <span className="research-maxturns"> · 已達工具呼叫上限</span>}
          {typeof m.elapsed_seconds === "number" && <span> · {m.elapsed_seconds.toFixed(1)}s</span>}
        </div>
      )}
      <div className="research-bubble-body">
        {m.role === "assistant" && !m.isError && !m.maxTurns && m.content ? (
          // assistant answers are Markdown (safe renderer); user/error/maxTurns
          // stay literal text (don't reinterpret a raw question or error string).
          <MarkdownView source={m.content} />
        ) : (
          m.content || (m.role === "assistant" ? "（空回應）" : "")
        )}
      </div>
      {m.tickers && m.tickers.length > 0 && (
        <div className="research-bubble-tickers">
          {m.tickers.map((t) => (
            <button key={t} className="news-ticker-chip" onClick={() => onOpenTicker(t)} title={`開啟 ${t}`}>{t}</button>
          ))}
        </div>
      )}
    </div>
  );
}

function TraceRowView({ row }: { row: TraceRow }) {
  if (row.kind === "thinking") {
    return <li className="research-trace-think muted tiny">💭 {row.text}</li>;
  }
  return (
    <li className={`research-trace-tool ${row.done ? "done" : "open"}`}>
      <div className="research-trace-tool-head">
        <span className="mono">{row.name}</span>
        {!row.done && <span className="muted tiny"> …執行中</span>}
        {typeof row.chars === "number" && <span className="muted tiny"> · {row.chars}c</span>}
      </div>
      {row.input !== undefined && <div className="research-trace-input mono tiny muted">{JSON.stringify(row.input)}</div>}
      {row.result_preview && <div className="research-trace-preview tiny muted">{row.result_preview}</div>}
    </li>
  );
}
