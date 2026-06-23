// AI 研究 — the evidence-first research console (Layer C-2, persisted).
//
// Thin UI over the pure researchReducer (the conversation authority). The
// sidecar owns execution through /research/runs; the UI owns only create +
// attach/replay polling:
//   • submit creates a durable run, then polls replay events;
//   • 新對話 / thread-switch / unmount detach local polling but do NOT cancel the
//     server run;
//   • Stop is the explicit cancellation path;
//   • a superseded poller (a newer run took over abortRef) never commits.
// Persistence (C-2b): the run API persists user/assistant turns to the local
// ResearchThreadStore; on mount this fetches + `hydrate`s the threads/messages
// (merge, so a late hydrate can't clobber a live turn). Threads survive reload;
// follow-ups default to the active thread's persisted provider, while new
// conversations default to the Settings AI 研究 route.
//
// Provider selection is USER-CHOSEN — no global default: 1 provider available →
// auto-select; configured AI 研究 route → auto-select that route; 0 → disable
// input. The model/effort per query is the ai_research route (Settings → Models,
// Slice B2), resolved for the chosen provider — see researchModelFor.
// Per-provider trace behaviour comes from a descriptor map, not an
// OpenAI/Anthropic binary, so compatible providers can slot in later.

import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react";

import {
  cancelResearchRun, createResearchRun, deleteResearchThread, discoverModels,
  getModelCatalog, getQueryProviders, getResearchRunEvents,
  getResearchThreads, getResearchMessages, getRuntimeConfig,
  type CredentialAuthType, type ModelCatalog,
  type ResearchMessageDTO, type ResearchRunDTO, type ResearchThreadDTO, type RuntimeConfig,
} from "./api";
import { MarkdownView } from "./MarkdownView";
import {
  asResearchProviderId,
  chooseResearchProvider,
  RESEARCH_PROVIDER_IDS,
  type ResearchProviderId,
} from "./researchProvider";
import { activeCredential, defaultModel, effortNote, lastAssistantSelection, modelOptions } from "./researchModels";
import { shouldEndResearchReplay } from "./researchRunReplay";
import {
  initialState,
  lastRetryCandidate,
  MAX_TURNS_SENTINEL,
  reduce,
  selectFooter,
  type Message,
  type PendingTurn,
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
  role: m.role, content: m.content, provider: m.provider, model: m.model, effort: m.effort,
  tools_used: m.tools_used ?? [], tool_calls: m.tool_calls ?? [],
  token_usage: m.token_usage, tickers: m.tickers,
  elapsed_seconds: m.elapsed_seconds, created_at: m.created_at,
  isError: m.is_error ?? false, // persisted error turns (MUST-FIX 2) restore as error bubbles
  // store has no maxTurns column — re-derive the badge the same way the reducer does (SF2)
  maxTurns: m.provider === "anthropic" && m.content === MAX_TURNS_SENTINEL,
});

const PROVIDER_IDS = RESEARCH_PROVIDER_IDS;
type ProviderId = ResearchProviderId;

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

const ACTIVE_THREAD_SESSION_KEY = "arkscope.aiResearch.activeThreadId";
const readActiveThreadId = (): string | null => {
  try { return window.sessionStorage.getItem(ACTIVE_THREAD_SESSION_KEY); } catch { return null; }
};
const writeActiveThreadId = (id: string | null) => {
  try {
    if (id) window.sessionStorage.setItem(ACTIVE_THREAD_SESSION_KEY, id);
    else window.sessionStorage.removeItem(ACTIVE_THREAD_SESSION_KEY);
  } catch {
    /* sessionStorage may be unavailable; the reducer state still works in-session */
  }
};

const isTerminalRun = (run: ResearchRunDTO): boolean =>
  ["succeeded", "failed", "cancelled", "interrupted"].includes(run.status);

const runStartedMs = (run: ResearchRunDTO): number => {
  const raw = run.started_at ?? run.created_at;
  const parsed = Date.parse(raw);
  return Number.isFinite(parsed) ? parsed : Date.now();
};

const sleep = (ms: number, signal: AbortSignal): Promise<void> => new Promise((resolve, reject) => {
  const timer = window.setTimeout(resolve, ms);
  signal.addEventListener("abort", () => {
    window.clearTimeout(timer);
    reject(new DOMException("aborted", "AbortError"));
  }, { once: true });
});

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
  const [threadMenuId, setThreadMenuId] = useState<string | null>(null);
  // Model/effort picker (Step 3): a per-(provider, active-auth-mode) selection.
  const [catalog, setCatalog] = useState<ModelCatalog | null>(null);
  const [discovered, setDiscovered] = useState<Record<string, string[]>>({}); // credentialId → discovered model ids
  const [selModel, setSelModel] = useState("");
  const [selEffort, setSelEffort] = useState("default");
  const [activeRunsByThread, setActiveRunsByThread] = useState<Record<string, ResearchRunDTO>>({});

  const abortRef = useRef<AbortController | null>(null);
  const pollingRunIdRef = useRef<string | null>(null);

  // --- provider availability = SDK present (/query/providers) AND key set ----
  const availability = useMemo(() => {
    return PROVIDER_IDS.map((id) => {
      const hasKey = runtime ? runtime[id].key_set : false;
      const hasSdk = sdk ? sdk[id] !== false : false; // missing entry → treat as unavailable
      return { id, available: hasKey && hasSdk, model: runtime ? runtime[id].model : "" };
    });
  }, [runtime, sdk]);
  const availableIds = useMemo(() => availability.filter((a) => a.available).map((a) => a.id), [availability]);
  const configuredProvider = runtime?.ai_research?.source !== "default"
    ? (asResearchProviderId(runtime?.ai_research?.provider) ?? undefined)
    : undefined;
  const configuredRouteKey = runtime?.ai_research
    ? `${runtime.ai_research.source}:${runtime.ai_research.provider}:${runtime.ai_research.model}:${runtime.ai_research.effort}`
    : "";
  const activeThread = useMemo(
    () => (state.activeThreadId ? state.threads.find((t) => t.id === state.activeThreadId) ?? null : null),
    [state.activeThreadId, state.threads],
  );
  const activeThreadProvider = asResearchProviderId(activeThread?.provider);

  useEffect(() => {
    let alive = true;
    void (async () => {
      try {
        const [rc, qp, cat] = await Promise.all([getRuntimeConfig(), getQueryProviders(), getModelCatalog()]);
        if (!alive) return;
        setRuntime(rc);
        setSdk(Object.fromEntries(Object.entries(qp.providers).map(([k, v]) => [k, !!v.available])));
        setCatalog(cat);
      } catch {
        if (alive) { setRuntime(null); setSdk(null); }
      } finally {
        if (alive) setBooting(false);
      }
    })();
    return () => { alive = false; };
  }, []);

  // Follow-up turns default to the active thread's provider. If no thread is
  // active, prefer the configured AI 研究 route when available. If the user
  // explicitly clicks "切換", hold at the chooser until they pick another route.
  useEffect(() => {
    const next = chooseResearchProvider({
      currentProvider: provider,
      activeThreadProvider,
      availableIds,
      autoRouteSelection,
      configuredProvider,
    });
    if (next !== provider) setProvider(next);
  }, [provider, activeThreadProvider, availableIds, autoRouteSelection, configuredProvider]);

  // If Settings changes the AI 研究 route, let the page follow the new route.
  useEffect(() => {
    setAutoRouteSelection(true);
    setProvider(null);
  }, [configuredRouteKey]);

  useEffect(() => {
    if (state.pending) setThreadMenuId(null);
  }, [state.pending]);

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
        const savedActive = readActiveThreadId();
        setActiveRunsByThread(Object.fromEntries(
          threads
            .filter((t) => t.active_run && !isTerminalRun(t.active_run))
            .map((t) => [t.id, t.active_run!]),
        ));
        dispatch({
          kind: "hydrate",
          threads: threads.map(toClientThread),
          messagesByThread: Object.fromEntries(entries),
          activeThreadId: savedActive && threads.some((t) => t.id === savedActive) ? savedActive : null,
        });
      } catch {
        /* hydration is best-effort; a clean empty start is fine */
      }
    })();
    return () => { alive = false; };
  }, []);

  // Abort any in-flight stream on unmount.
  useEffect(() => () => abortRef.current?.abort(), []);

  // --- server-owned run attach/replay ---------------------------------------
  // The sidecar owns execution. The UI only creates a durable run and polls its
  // replay buffer. Detaching (thread switch/unmount/settings navigation) aborts
  // local polling, not the server run.
  const pollRun = useCallback(async (run: ResearchRunDTO) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    pollingRunIdRef.current = run.id;
    let after = 0;
    try {
      for (;;) {
        const res = await getResearchRunEvents(run.id, after);
        if (abortRef.current !== controller) return; // detached/superseded
        setActiveRunsByThread((prev) => {
          const next = { ...prev };
          if (isTerminalRun(res.run)) delete next[res.run.thread_id];
          else next[res.run.thread_id] = res.run;
          return next;
        });
        for (const event of res.events) {
          after = Math.max(after, event.seq);
          const parsedTs = Date.parse(event.created_at);
          dispatch({
            kind: "frame",
            frame: { type: event.type, data: event.data },
            ts: Number.isFinite(parsedTs) ? parsedTs : Date.now(),
          });
        }
        if (shouldEndResearchReplay(res.run, res.has_more === true)) {
          dispatch({ kind: "streamEnd", ts: Date.now() });
          return;
        }
        await sleep(1000, controller.signal);
      }
    } catch (e) {
      if (abortRef.current !== controller || controller.signal.aborted) return;
      setThreadError(e instanceof Error ? e.message : String(e));
      dispatch({ kind: "abort", ts: Date.now() });
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null;
        pollingRunIdRef.current = null;
      }
    }
  }, []);

  const runManaged = useCallback(async (body: { question: string; provider: ProviderId; model?: string; effort?: string; thread_id: string; ticker: string | null; retry_last_failed?: boolean }) => {
    try {
      const { run } = await createResearchRun(body);
      setActiveRunsByThread((prev) => ({ ...prev, [run.thread_id]: run }));
      await pollRun(run);
    } catch (e) {
      dispatch({ kind: "streamError", error: e instanceof Error ? e.message : String(e), ts: Date.now() });
    }
  }, [pollRun]);

  useEffect(() => {
    const run = state.activeThreadId ? activeRunsByThread[state.activeThreadId] : null;
    if (!run || isTerminalRun(run)) return;
    if (state.pending?.threadId === run.thread_id || pollingRunIdRef.current === run.id) return;
    dispatch({
      kind: "attachRun",
      threadId: run.thread_id,
      provider: run.provider,
      model: run.model,
      effort: run.effort,
      ticker: run.ticker,
      ts: runStartedMs(run),
    });
    void pollRun(run);
  }, [activeRunsByThread, pollRun, state.activeThreadId, state.pending?.threadId]);

  const submit = useCallback(() => {
    const q = question.trim();
    if (!q || !provider || state.pending) return; // disabled while pending (defensive)
    const ticker = tickerInput.trim().toUpperCase() || null;
    // Client-owned thread id: reuse the active thread to continue, else a fresh
    // uuid for a new conversation (agreed reducer↔store id model).
    const threadId = state.activeThreadId ?? crypto.randomUUID();
    const model = selModel.trim() || null;
    const effort = selEffort && selEffort !== "default" ? selEffort : undefined;
    dispatch({ kind: "submit", question: q, provider, model, effort, ticker, ts: Date.now(), threadId });
    writeActiveThreadId(threadId);
    setQuestion("");
    setThreadError(null);
    // raw question; server frames + persists. model/effort = the picker selection
    // (server falls back to the ai_research route only when model is omitted).
    void runManaged({ question: q, provider, model: model ?? undefined, effort, thread_id: threadId, ticker });
  }, [question, tickerInput, provider, selModel, selEffort, state.pending, state.activeThreadId, runManaged]);

  // Abort the live stream + drop the pending turn (explicit Stop only).
  const stopStream = useCallback(() => {
    const runId = state.activeThreadId ? activeRunsByThread[state.activeThreadId]?.id : null;
    if (runId) void cancelResearchRun(runId).catch((e) => setThreadError(e instanceof Error ? e.message : String(e)));
    abortRef.current?.abort();
    abortRef.current = null;
    pollingRunIdRef.current = null;
    if (state.activeThreadId) {
      setActiveRunsByThread((prev) => {
        const next = { ...prev };
        delete next[state.activeThreadId!];
        return next;
      });
    }
    dispatch({ kind: "abort", ts: Date.now() });
  }, [activeRunsByThread, state.activeThreadId]);
  const newThread = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    pollingRunIdRef.current = null;
    setThreadError(null);
    setThreadMenuId(null);
    setAutoRouteSelection(true);
    setProvider(null);
    writeActiveThreadId(null);
    dispatch({ kind: "newThread" });
  }, []);
  const selectThread = useCallback((id: string) => {
    abortRef.current?.abort();
    abortRef.current = null;
    pollingRunIdRef.current = null;
    setThreadError(null);
    setThreadMenuId(null);
    setAutoRouteSelection(true);
    setProvider(null);
    writeActiveThreadId(id);
    dispatch({ kind: "selectThread", threadId: id });
  }, []);
  const deleteThread = useCallback(async (thread: Thread) => {
    if (activeRunsByThread[thread.id]) {
      setThreadError("這個對話仍有研究執行中，請先停止或等待完成。");
      return;
    }
    const title = thread.title || "（未命名）";
    const ok = window.confirm(`刪除「${title}」？\n\n這會移除此對話的本地訊息與這個 thread 的上下文記憶。`);
    if (!ok) return;
    setThreadError(null);
    try {
      await deleteResearchThread(thread.id);
      const remaining = state.threads.filter((t) => t.id !== thread.id);
      const nextActive = state.activeThreadId === thread.id ? (remaining[0]?.id ?? null) : state.activeThreadId;
      writeActiveThreadId(nextActive);
      dispatch({ kind: "deleteThread", threadId: thread.id });
      setThreadMenuId(null);
    } catch (e) {
      setThreadError(e instanceof Error ? e.message : String(e));
    }
  }, [activeRunsByThread, state.threads, state.activeThreadId]);

  // --- derived view state ----------------------------------------------------
  const msgs = state.activeThreadId ? state.messagesByThread[state.activeThreadId] ?? [] : [];
  const retryCandidate = useMemo(() => lastRetryCandidate(msgs), [msgs]);
  const lastAssistant = [...msgs].reverse().find((m) => m.role === "assistant");
  const lastSelection = useMemo(() => lastAssistantSelection(msgs), [msgs]);
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

  // --- model/effort picker (Step 3): per (provider, ACTIVE auth mode) -----------
  // The active credential decides the model set: api_key → its provider /models;
  // chatgpt_oauth → the ChatGPT backend list; claude_code_oauth → the seed. We
  // discover it via /config/model-discovery (cached per credential id) and fall
  // back to the configured route model until/if discovery returns.
  const activeCred = useMemo(
    () => (provider && runtime ? activeCredential(runtime[provider].credentials) : null),
    [provider, runtime],
  );
  const activeAuthMode: CredentialAuthType | null = activeCred?.auth_type ?? null;
  const routeModel = provider ? researchModelFor(provider) : "";
  const routeEffort = provider ? (researchEffortFor(provider) ?? "default") : "default";

  // discover models for the active credential (once per credential id; silent on
  // failure — the route/seed model stays usable).
  useEffect(() => {
    if (!provider || !activeCred || !activeCred.can_discover_models) return;
    const credId = activeCred.id;
    if (discovered[credId] !== undefined) return; // already attempted/cached
    let alive = true;
    void (async () => {
      try {
        const res = await discoverModels(provider, credId);
        if (alive) setDiscovered((p) => ({ ...p, [credId]: (res.models ?? []).map((m) => m.id) }));
      } catch {
        if (alive) setDiscovered((p) => ({ ...p, [credId]: [] })); // mark attempted → fall back to seed/route
      }
    })();
    return () => { alive = false; };
  }, [provider, activeCred, discovered]);

  const modelOpts = useMemo(() => {
    const disc = activeCred ? (discovered[activeCred.id] ?? []) : [];
    return modelOptions(disc, routeModel, lastSelection.model);
  }, [activeCred, discovered, routeModel, lastSelection.model]);

  // keep the selected model valid as the option set / provider changes
  useEffect(() => { setSelModel((cur) => defaultModel(modelOpts, routeModel, cur)); }, [modelOpts, routeModel]);
  // reset effort to the route's effort when the provider changes
  useEffect(() => { setSelEffort(routeEffort); }, [routeEffort, provider]);
  // When switching to a persisted thread, reflect that thread's latest completed
  // assistant turn rather than the current Settings default. This is display and
  // next-send ergonomics only; each answer bubble remains the historical record.
  useEffect(() => {
    if (!state.activeThreadId) return;
    setSelModel(lastSelection.model && modelOpts.includes(lastSelection.model)
      ? lastSelection.model
      : defaultModel(modelOpts, routeModel, null));
    setSelEffort(lastSelection.effort ?? routeEffort);
  }, [state.activeThreadId, lastSelection.model, lastSelection.effort, modelOpts, routeModel, routeEffort]);

  const effortOpts = provider && catalog ? (catalog.effort_options[provider] ?? []) : [];
  const pickerEffortNote = provider ? effortNote(provider, activeAuthMode, selEffort) : null;

  const retryLastFailed = useCallback(() => {
    if (!retryCandidate || !state.activeThreadId || state.pending) return;
    const retryProvider = retryCandidate.provider as ProviderId;
    const effort = retryProvider === provider && selEffort && selEffort !== "default" ? selEffort : undefined;
    setAutoRouteSelection(false);
    setProvider(retryProvider);
    setThreadError(null);
    dispatch({
      kind: "submit",
      question: retryCandidate.question,
      provider: retryProvider,
      model: retryCandidate.model,
      effort,
      ticker: retryCandidate.ticker,
      ts: Date.now(),
      threadId: state.activeThreadId,
    });
    writeActiveThreadId(state.activeThreadId);
    void runManaged({
      question: retryCandidate.question,
      provider: retryProvider,
      model: retryCandidate.model ?? undefined,
      effort,
      thread_id: state.activeThreadId,
      ticker: retryCandidate.ticker,
      retry_last_failed: true,
    });
  }, [provider, retryCandidate, runManaged, selEffort, state.activeThreadId, state.pending]);

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
            title="新增對話"
          >
            ＋ 新對話
          </button>
          {state.pending && <p className="muted tiny">回應在 sidecar 繼續執行；可切換對話，停止才會取消目前 run。</p>}
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
                      title={t.title}
                    >
                      <span className="research-threadtitle">{t.title || "（未命名）"}</span>
                      {t.ticker && <span className="list-chip tiny">{t.ticker}</span>}
                      {activeRunsByThread[t.id] && <span className="list-chip tiny">執行中</span>}
                    </button>
                    <button
                      className="research-threadmenu-btn"
                      onClick={() => setThreadMenuId((open) => (open === t.id ? null : t.id))}
                      disabled={!!activeRunsByThread[t.id]}
                      title={activeRunsByThread[t.id] ? "這個對話仍有研究執行中" : "更多操作"}
                      aria-label={`開啟對話操作 ${t.title || t.id}`}
                      aria-expanded={threadMenuId === t.id}
                    >
                      …
                    </button>
                    {threadMenuId === t.id && !activeRunsByThread[t.id] && (
                      <div className="research-threadmenu" role="menu">
                        <button
                          className="research-threadmenu-item danger"
                          onClick={() => void deleteThread(t)}
                          role="menuitem"
                        >
                          刪除對話
                        </button>
                      </div>
                    )}
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
              msgs.map((m, i) => (
                <Bubble
                  key={i}
                  m={m}
                  onOpenTicker={onOpenTicker}
                  canRetry={!!retryCandidate && i === msgs.length - 1 && !state.pending}
                  onRetry={retryLastFailed}
                />
              ))
            )}

            {state.pending && (
              <PendingAssistantBubble pending={state.pending} />
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
                {provider && !needChooser && (
                  <div className="research-pickerbar">
                    <label className="research-pick">
                      <span className="muted tiny">模型</span>
                      <select value={selModel} onChange={(e) => setSelModel(e.target.value)} disabled={!!state.pending}>
                        {modelOpts.length === 0 && <option value="">（無可用模型）</option>}
                        {modelOpts.map((m) => (
                          <option key={m} value={m}>{m}</option>
                        ))}
                      </select>
                    </label>
                    <label className="research-pick">
                      <span className="muted tiny">effort</span>
                      <select value={selEffort} onChange={(e) => setSelEffort(e.target.value)} disabled={!!state.pending}>
                        {(effortOpts.length ? effortOpts : [{ id: "default", label: "default" }]).map((o) => (
                          <option key={o.id} value={o.id}>{o.label ?? o.id}</option>
                        ))}
                      </select>
                    </label>
                    {pickerEffortNote && <span className="warn-text tiny">{pickerEffortNote}</span>}
                  </div>
                )}
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
              {typeof footer.cache_read_tokens === "number" && <span> · cache read {footer.cache_read_tokens.toLocaleString()}</span>}
              {typeof footer.cache_creation_tokens === "number" && <span> · cache create {footer.cache_creation_tokens.toLocaleString()}</span>}
            </div>
          )}
        </aside>
      </div>
    </main>
  );
}

function Bubble({
  m,
  onOpenTicker,
  canRetry,
  onRetry,
}: {
  m: Message;
  onOpenTicker: (t: string) => void;
  canRetry?: boolean;
  onRetry?: () => void;
}) {
  const cls = `research-bubble ${m.role}${m.isError ? " error" : ""}`;
  return (
    <div className={cls}>
      {m.role === "assistant" && (m.model || m.maxTurns) && (
        <div className="research-bubble-meta muted tiny">
          {m.model && <span className="research-model">{m.provider}/{m.model}{m.effort && m.effort !== "default" ? ` · ${m.effort}` : ""}</span>}
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
      {canRetry && (
        <div className="research-bubble-actions">
          <button
            className="btn-ghost tiny"
            onClick={onRetry}
            title="保留同一對話上下文，排除最後失敗回合後重試"
          >
            重試
          </button>
        </div>
      )}
    </div>
  );
}

export function PendingAssistantBubble({ pending }: { pending: PendingTurn }) {
  const provider = pending.provider as ProviderId;
  const presentation = PRESENTATION[provider];
  const providerLabel = presentation?.label ?? pending.provider;
  const hasInterimText = pending.interimText.length > 0;
  const status = hasInterimText
    ? "生成中…"
    : presentation?.trace_mode === "post_run"
      ? `${providerLabel} 執行中，完成後一次顯示工具追蹤…`
      : "思考中…";

  return (
    <div className="research-bubble assistant pending">
      {hasInterimText && <div className="research-interim research-bubble-body">{pending.interimText}</div>}
      {(pending.thinkingActive || hasInterimText) && (
        <div className="research-thinking muted tiny">
          <span className="research-spinner" />
          {status}
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
