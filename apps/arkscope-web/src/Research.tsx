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
// ResearchThreadStore; on mount this fetches + `hydrate`s the threads/messages.
// Complete provider/model/effort selection is resolved from the latest successful
// thread tuple, the last explicit user tuple, or the Settings route, in that order.
// Every candidate is validated against the shared Models-UX effective catalog;
// invalid saved choices block instead of silently falling through.
// Per-provider trace behaviour comes from a descriptor map, not an
// OpenAI/Anthropic binary, so compatible providers can slot in later.

import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react";

import {
  cancelResearchRun, createResearchRun, deleteResearchThread,
  getModelCatalog, getQueryProviders, getResearchRunEvents,
  getResearchThreads, getResearchMessages, getResearchSelection,
  type ModelCatalog,
  type ResearchMessageDTO, type ResearchRunDTO, type ResearchThreadDTO,
} from "./api";
import { MarkdownView } from "./MarkdownView";
import {
  asResearchProviderId,
  RESEARCH_PROVIDER_IDS,
  type ResearchProviderId,
} from "./researchProvider";
import {
  effortNote,
  effortOptionsForModel,
} from "./researchModels";
import {
  groupedModelEntries,
  modelProviderReason,
  optionReason,
} from "./modelPicker";
import { MODEL_UX_LABELS } from "./modelRoutingUx";
import {
  loadResearchThreadSelection,
  resolveResearchSelection,
  writeExplicitResearchSelection,
  type ResearchTuple,
} from "./researchSelection";
import { getInvestorProfile, type AssistantStance, type InvestorProfileResponse } from "./api";
import { stanceLabel, traceSummary } from "./personalizationDisplay";
import { shouldEndResearchReplay } from "./researchRunReplay";
import type { NavigationRequest, NavigationTarget } from "./shell/navigation";
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
  personalization: m.personalization ?? null,
  isError: m.is_error ?? false, // persisted error turns (MUST-FIX 2) restore as error bubbles
  // store has no maxTurns column — re-derive the badge the same way the reducer does (SF2)
  maxTurns: m.provider === "anthropic" && m.content === MAX_TURNS_SENTINEL,
});

const PROVIDER_IDS = RESEARCH_PROVIDER_IDS;
type ProviderId = ResearchProviderId;

// trace_mode drives the live-trace vs silent-until-done affordance; copy stays
// neutral. A new OpenAI-compatible provider is a row here, not a render rewrite.
const PRESENTATION: Record<ProviderId, { label: string; trace_mode: "live" | "post_run"; trace_note: string }> = {
  anthropic: { label: "Anthropic", trace_mode: "live", trace_note: "即時工具追蹤" },
  openai: { label: "OpenAI", trace_mode: "post_run", trace_note: "完成後一次顯示工具追蹤" },
};

const modelReasonLabel = (reason: string): string =>
  MODEL_UX_LABELS.reasons[reason] ?? reason;

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

export interface ResearchViewProps {
  onOpenTicker: (ticker: string) => void;
  navigationRequest?: NavigationRequest<Extract<NavigationTarget, { kind: "research_thread" }>> | null;
  onObserveRun?: (run: ResearchRunDTO, threadTitle?: string) => void;
}

export function ResearchView({ onOpenTicker, navigationRequest, onObserveRun }: ResearchViewProps) {
  const [state, dispatch] = useReducer(reduce, initialState);
  const [question, setQuestion] = useState("");
  const [tickerInput, setTickerInput] = useState("");
  const [sdk, setSdk] = useState<Record<string, boolean> | null>(null);
  const [booting, setBooting] = useState(true);
  const [threadError, setThreadError] = useState<string | null>(null);
  const [threadMenuId, setThreadMenuId] = useState<string | null>(null);
  const [catalog, setCatalog] = useState<ModelCatalog | null>(null);
  const [userSelection, setUserSelection] = useState<ResearchTuple | null>(null);
  const [threadSelection, setThreadSelection] = useState<{
    threadId: string;
    tuple: ResearchTuple | null;
    loaded: boolean;
  } | null>(null);
  const [threadSelectionLoadError, setThreadSelectionLoadError] = useState(false);
  const [threadSelectionRequestVersion, setThreadSelectionRequestVersion] = useState(0);
  // Track A: opt-in investor profile → per-run assistant stance override.
  const [investorProfile, setInvestorProfile] = useState<InvestorProfileResponse | null>(null);
  const [runStance, setRunStance] = useState<AssistantStance>("off");
  const [activeRunsByThread, setActiveRunsByThread] = useState<Record<string, ResearchRunDTO>>({});

  const abortRef = useRef<AbortController | null>(null);
  const pollingRunIdRef = useRef<string | null>(null);
  const consumedNavigationSequenceRef = useRef(0);
  const onObserveRunRef = useRef(onObserveRun);
  onObserveRunRef.current = onObserveRun;

  const currentThreadSelection = state.activeThreadId
    ? (threadSelection?.threadId === state.activeThreadId && threadSelection.loaded
        ? threadSelection.tuple
        : undefined)
    : null;
  const selection = useMemo(
    () => catalog
      ? resolveResearchSelection({
          catalog,
          hasActiveThread: !!state.activeThreadId,
          threadSelection: currentThreadSelection,
          userSelection,
          sdkAvailability: sdk ?? undefined,
        })
      : null,
    [catalog, currentThreadSelection, sdk, state.activeThreadId, userSelection],
  );
  const provider = selection?.tuple?.provider ?? null;
  const selModel = selection?.tuple?.model ?? "";
  const selEffort = selection?.tuple?.effort ?? "default";

  const rememberUserSelection = useCallback((tuple: ResearchTuple) => {
    setUserSelection(tuple);
    writeExplicitResearchSelection(tuple);
  }, []);

  useEffect(() => {
    let alive = true;
    void (async () => {
      try {
        const [qp, cat] = await Promise.all([getQueryProviders(), getModelCatalog()]);
        if (!alive) return;
        setSdk(Object.fromEntries(Object.entries(qp.providers).map(([k, v]) => [k, !!v.available])));
        setCatalog(cat);
      } catch {
        if (alive) { setCatalog(null); setSdk(null); }
      } finally {
        if (alive) setBooting(false);
      }
    })();
    return () => { alive = false; };
  }, []);

  useEffect(() => {
    const threadId = state.activeThreadId;
    if (!threadId) {
      setThreadSelection(null);
      setThreadSelectionLoadError(false);
      return;
    }
    let alive = true;
    setThreadSelectionLoadError(false);
    setThreadSelection({ threadId, tuple: null, loaded: false });
    void loadResearchThreadSelection(threadId, getResearchSelection)
      .then((tuple) => {
        if (alive) {
          setThreadSelectionLoadError(false);
          setThreadSelection((current) => (
            current?.threadId === threadId && current.loaded
              ? current
              : { threadId, tuple, loaded: true }
          ));
        }
      })
      .catch(() => {
        if (alive) {
          setThreadSelectionLoadError(true);
          setThreadSelection((current) => (
            current?.threadId === threadId && current.loaded
              ? current
              : { threadId, tuple: null, loaded: false }
          ));
        }
      });
    return () => { alive = false; };
  }, [state.activeThreadId, threadSelectionRequestVersion]);

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
        for (const thread of threads) {
          if (thread.active_run) onObserveRunRef.current?.(thread.active_run, thread.title);
        }
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
        onObserveRunRef.current?.(res.run);
        if (abortRef.current !== controller) return; // detached/superseded
        if (res.run.status === "succeeded") {
          const successfulProvider = asResearchProviderId(res.run.provider);
          if (successfulProvider && res.run.model.trim()) {
            setThreadSelection({
              threadId: res.run.thread_id,
              tuple: {
                provider: successfulProvider,
                model: res.run.model.trim(),
                effort: res.run.effort?.trim() || "default",
              },
              loaded: true,
            });
          }
        }
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

  const runManaged = useCallback(async (body: { question: string; provider: ProviderId; model?: string; effort?: string; thread_id: string; ticker: string | null; retry_last_failed?: boolean; assistant_stance?: AssistantStance }) => {
    try {
      const { run } = await createResearchRun(body);
      onObserveRunRef.current?.(run);
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

  useEffect(() => {
    let cancelled = false;
    getInvestorProfile()
      .then((r) => {
        if (cancelled) return;
        setInvestorProfile(r);
        if (r.profile.enabled) setRunStance(r.profile.default_stance);
      })
      .catch(() => {
        /* personalization is optional — a failed load = feature off */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const stanceEnabled = investorProfile?.profile.enabled ?? false;
  const stanceForRun = stanceEnabled ? runStance : undefined;

  const submit = useCallback(() => {
    const q = question.trim();
    if (!q || selection?.state !== "ready" || state.pending) return;
    const ticker = tickerInput.trim().toUpperCase() || null;
    // Client-owned thread id: reuse the active thread to continue, else a fresh
    // uuid for a new conversation (agreed reducer↔store id model).
    const threadId = state.activeThreadId ?? crypto.randomUUID();
    const { provider: runProvider, model, effort } = selection.tuple;
    dispatch({ kind: "submit", question: q, provider: runProvider, model, effort, ticker, ts: Date.now(), threadId });
    writeActiveThreadId(threadId);
    setQuestion("");
    setThreadError(null);
    void runManaged({
      question: q,
      provider: runProvider,
      model,
      effort,
      thread_id: threadId,
      ticker,
      assistant_stance: stanceForRun,
    });
  }, [question, tickerInput, selection, state.pending, state.activeThreadId, runManaged, stanceForRun]);

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
    setUserSelection(null);
    writeActiveThreadId(null);
    dispatch({ kind: "newThread" });
  }, []);
  const selectThread = useCallback((id: string) => {
    abortRef.current?.abort();
    abortRef.current = null;
    pollingRunIdRef.current = null;
    setThreadError(null);
    setThreadMenuId(null);
    setUserSelection(null);
    writeActiveThreadId(id);
    dispatch({ kind: "selectThread", threadId: id });
  }, []);
  useEffect(() => {
    if (!navigationRequest || navigationRequest.sequence <= consumedNavigationSequenceRef.current) return;
    if (!state.threads.some((thread) => thread.id === navigationRequest.target.threadId)) return;
    consumedNavigationSequenceRef.current = navigationRequest.sequence;
    selectThread(navigationRequest.target.threadId);
  }, [navigationRequest, selectThread, state.threads]);
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
      if (state.activeThreadId === thread.id) setUserSelection(null);
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
  const traceRows: TraceRow[] = state.pending
    ? state.pending.trace
    : (lastAssistant?.tool_calls ?? []).map((c) => ({ kind: "tool", name: c.name, input: c.input, result_preview: c.result_preview, chars: undefined, done: true } as ToolTraceRow));
  const pendingPresentation = state.pending ? PRESENTATION[state.pending.provider as ProviderId] : null;
  const footer = selectFooter(state); // derived from the active thread, survives thread-switch
  const taskProviders = catalog?.effective?.tasks.ai_research?.providers;
  const noProvider = !booting && !PROVIDER_IDS.some((id) => !!catalog?.effective?.providers?.[id]);
  const providerChoices = PROVIDER_IDS.map((id) => {
    const context = catalog?.effective?.providers?.[id] ?? null;
    const block = taskProviders?.[id];
    const providerReason = modelProviderReason(context, block);
    const preferred = block?.models.find((entry) => (
      entry.id === catalog?.routes.ai_research.model && !optionReason(entry, providerReason)
    ));
    const firstReady = block?.models.find((entry) => !optionReason(entry, providerReason));
    return {
      id,
      context,
      block,
      providerReason,
      suggestedModel: preferred?.id ?? firstReady?.id ?? "",
      disabled: !context || !block || !firstReady,
    };
  });
  const selectedProviderChoice = providerChoices.find((choice) => choice.id === provider) ?? null;
  const selectedProviderReason = selectedProviderChoice?.providerReason ?? null;
  const modelGroups = groupedModelEntries(
    selectedProviderChoice?.block?.models ?? [],
    selectedProviderReason,
  );
  const selectedEffectiveModel = selectedProviderChoice?.block?.models
    .find((item) => item.id === selModel);
  const selectedModelMissing = !!provider && !!selModel && !selectedEffectiveModel;
  const effortOpts = useMemo(
    () => provider && catalog
      ? effortOptionsForModel(catalog, provider, selModel ?? "", selectedEffectiveModel?.effort_options)
      : [],
    [catalog, provider, selModel, selectedEffectiveModel?.effort_options],
  );
  const supportedEffortChoices = effortOpts.some((option) => option.id === "default")
    ? effortOpts
    : [{
        id: "default",
        provider: provider ?? "openai",
        label: "default",
        description: "使用 provider 預設 effort",
        applies_to_card_tasks: false,
      }, ...effortOpts];
  const effortChoices = supportedEffortChoices.some((option) => option.id === selEffort)
    ? supportedEffortChoices
    : [...supportedEffortChoices, {
        id: selEffort,
        provider: provider ?? "openai",
        label: `${selEffort} · 此模型不支援`,
        description: "此儲存值不再受目前模型支援",
        applies_to_card_tasks: false,
        disabled: true,
      }];
  const pickerEffortNote = provider ? effortNote(provider, selection?.authMode ?? null, selEffort) : null;

  const chooseProvider = useCallback((nextProvider: ProviderId) => {
    if (!catalog) return;
    const context = catalog.effective?.providers?.[nextProvider] ?? null;
    const block = catalog.effective?.tasks.ai_research?.providers?.[nextProvider];
    const providerReason = modelProviderReason(context, block);
    const route = catalog.routes.ai_research;
    const selected = block?.models.find((entry) => (
      entry.id === route.model && !optionReason(entry, providerReason)
    )) ?? block?.models.find((entry) => !optionReason(entry, providerReason));
    if (!selected) return;
    rememberUserSelection({ provider: nextProvider, model: selected.id, effort: "default" });
  }, [catalog, rememberUserSelection]);

  const retryLastFailed = useCallback(() => {
    if (!retryCandidate || !state.activeThreadId || state.pending || selection?.state !== "ready") return;
    const retryTuple = selection.tuple;
    setThreadError(null);
    dispatch({
      kind: "submit",
      question: retryCandidate.question,
      provider: retryTuple.provider,
      model: retryTuple.model,
      effort: retryTuple.effort,
      ticker: retryCandidate.ticker,
      ts: Date.now(),
      threadId: state.activeThreadId,
    });
    writeActiveThreadId(state.activeThreadId);
    void runManaged({
      question: retryCandidate.question,
      provider: retryTuple.provider,
      model: retryTuple.model,
      effort: retryTuple.effort,
      thread_id: state.activeThreadId,
      ticker: retryCandidate.ticker,
      retry_last_failed: true,
      assistant_stance: stanceForRun,
    });
  }, [retryCandidate, runManaged, selection, state.activeThreadId, state.pending, stanceForRun]);

  return (
    <main className="main research">
      <div className="surface-head">
        <h1 className="surface-title">AI 研究</h1>
        <span className="muted tiny">工具追蹤與證據整理，支援即時或完成後顯示，依 provider 而定；對話保存於本地（reload 後保留），即時工具追蹤為 ephemeral</span>
        {selection?.tuple && (
          <span className="muted tiny">
            研究模型：{selection.tuple.provider} · {selection.tuple.model} · {selection.tuple.effort}
            {selection.provenance ? `（${selection.provenance}）` : ""}
          </span>
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
              <p className="muted">尚未設定可執行 AI 研究的登入。請到「設定」→ Providers 完成登入。</p>
            ) : (
              <>
                <div className="research-providerbar">
                  <span className="muted tiny">研究路線：</span>
                  {providerChoices.map((choice) => (
                    <button
                      key={choice.id}
                      className={`btn-ghost small ${provider === choice.id ? "active" : ""}`}
                      onClick={() => chooseProvider(choice.id)}
                      disabled={choice.disabled || !!state.pending}
                      title={choice.providerReason
                        ? modelReasonLabel(choice.providerReason)
                        : `${choice.context?.label ?? choice.id}；${PRESENTATION[choice.id].trace_note}`}
                    >
                      {PRESENTATION[choice.id].label} / {choice.suggestedModel || "無可用模型"}
                    </button>
                  ))}
                </div>
                {selection?.state === "needs_selection" && state.activeThreadId && (
                  <div className="research-providerbar">
                    {threadSelectionLoadError ? (
                      <>
                        <span className="warn-text tiny">無法確認此對話上次使用的模型；目前不會自動 fallback。</span>
                        <button
                          className="btn-ghost tiny"
                          onClick={() => setThreadSelectionRequestVersion((version) => version + 1)}
                        >
                          重新確認模型
                        </button>
                      </>
                    ) : (
                      <span className="muted tiny">正在確認此對話上次成功使用的模型…</span>
                    )}
                  </div>
                )}
                {provider && (
                  <div className="research-pickerbar">
                    <label className="research-pick">
                      <span className="muted tiny">模型</span>
                      <select
                        value={selModel}
                        onChange={(event) => rememberUserSelection({
                          provider,
                          model: event.target.value,
                          effort: selEffort,
                        })}
                        disabled={!!state.pending}
                      >
                        {selectedModelMissing && (
                          <option value={selModel} disabled>
                            {selModel} · 此登入未顯示
                          </option>
                        )}
                        {modelGroups.map((group) => (
                          <optgroup key={group.label} label={group.label}>
                            {group.entries.map((entry) => (
                              <option
                                key={entry.id}
                                value={entry.id}
                                disabled={!!entry.disabledReason}
                              >
                                {entry.label}
                                {entry.disabledReason || entry.reason_code
                                  ? ` · ${modelReasonLabel(entry.disabledReason ?? entry.reason_code ?? "")}`
                                  : ""}
                              </option>
                            ))}
                          </optgroup>
                        ))}
                      </select>
                    </label>
                    <label className="research-pick">
                      <span className="muted tiny">effort</span>
                      <select
                        value={selEffort}
                        onChange={(event) => rememberUserSelection({
                          provider,
                          model: selModel,
                          effort: event.target.value,
                        })}
                        disabled={!!state.pending}
                      >
                        {effortChoices.map((o) => (
                          <option key={o.id} value={o.id} disabled={"disabled" in o && o.disabled}>
                            {o.label ?? o.id}
                          </option>
                        ))}
                      </select>
                    </label>
                    {pickerEffortNote && <span className="warn-text tiny">{pickerEffortNote}</span>}
                    {selection?.authLabel && <span className="muted tiny">{selection.authLabel}</span>}
                    {selection?.billingCopy && <span className="muted tiny">{selection.billingCopy}</span>}
                    {selection?.state === "blocked" && (
                      <span className="warn-text tiny">{selection.reasonLabel}</span>
                    )}
                    {stanceEnabled && (
                      <label className="tiny">
                        立場
                        <select value={runStance} onChange={(e) => setRunStance(e.target.value as AssistantStance)} disabled={!!state.pending}>
                          {(["off", "neutral", "aligned", "complementary", "strict_risk_control", "valuation_rationalist", "growth_opportunity"] as AssistantStance[]).map((s) => (
                            <option key={s} value={s}>{stanceLabel(s)}</option>
                          ))}
                        </select>
                      </label>
                    )}
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
                    <button
                      className="btn-ghost"
                      onClick={submit}
                      disabled={selection?.state !== "ready" || !question.trim()}
                    >
                      送出
                    </button>
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
          {traceSummary(m.personalization) && <span> · {traceSummary(m.personalization)}</span>}
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
