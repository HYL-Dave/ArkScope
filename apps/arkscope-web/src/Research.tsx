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
import { FileSearch, History, Plus } from "lucide-react";
import { useTranslation } from "react-i18next";

import {
  cancelResearchRun, createResearchRun,
  getModelCatalog, getQueryProviders, getResearchRunEvents,
  getResearchThread, getResearchMessages, getResearchSelection,
  type ModelCatalog, type RuntimeConfig,
  type ResearchMessageDTO, type ResearchRunDTO, type ResearchThreadDTO,
} from "./api";
import { MarkdownView } from "./MarkdownView";
import { ResearchHistoryDrawer } from "./ResearchHistoryDrawer";
import { ResearchEvidenceDrawer, researchEvidenceRows } from "./ResearchEvidenceDrawer";
import { ResearchRunProgress } from "./ResearchRunProgress";
import { presentResearchError } from "./researchErrors";
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
import { Button, PageHeader, useShellOverlay } from "./ui";
import {
  initialState,
  lastRetryCandidate,
  MAX_TURNS_SENTINEL,
  reduce,
  type Message,
  type PendingTurn,
  type Thread,
  type TraceRow,
} from "./researchReducer";

// Map persisted DTOs → the in-memory reducer shapes (field names already align,
// spec §6a). Persisted turns are completed/non-error by construction (we only
// persist on `done`), so isError/maxTurns default false.
const toClientThread = (t: ResearchThreadDTO): Thread => ({
  id: t.id, title: t.title, ticker: t.ticker, provider: t.provider, model: t.model,
  created_at: t.created_at, updated_at: t.updated_at, archived_at: t.archived_at ?? null,
});
const toClientMessage = (m: ResearchMessageDTO): Message => ({
  role: m.role, content: m.content, provider: m.provider, model: m.model, effort: m.effort,
  tools_used: m.tools_used ?? [], tool_calls: m.tool_calls ?? [],
  token_usage: m.token_usage, tickers: m.tickers,
  elapsed_seconds: m.elapsed_seconds, created_at: m.created_at,
  personalization: m.personalization ?? null,
  isError: m.is_error ?? false, // persisted error turns (MUST-FIX 2) restore as error bubbles
  runId: m.run_id ?? null,
  errorCode: m.error_code ?? null,
  errorDetail: m.error ?? null,
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

const selectionProvenanceLabel = (value: string | null | undefined): string => {
  if (value === "thread") return "此對話上次成功路線";
  if (value === "settings") return "設定路線";
  if (value === "explicit" || value === "user") return "上次明確選擇";
  return "";
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

const isMissingResearchThreadError = (error: unknown): boolean => (
  error instanceof Error
  && /^\/research\/threads\/\S+ returned 404$/.test(error.message)
);

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
  onNavigationConsumed?: (sequence: number) => void;
  onObserveRun?: (run: ResearchRunDTO, threadTitle?: string) => void;
  runtime?: RuntimeConfig | null;
  developerMode?: boolean;
  onNavigate?: (target: NavigationTarget) => void;
}

export function ResearchView({
  onOpenTicker,
  navigationRequest,
  onNavigationConsumed,
  onObserveRun,
  runtime = null,
  developerMode = false,
  onNavigate,
}: ResearchViewProps) {
  const { t: commonT } = useTranslation("common");
  const [state, dispatch] = useReducer(reduce, initialState);
  const [question, setQuestion] = useState("");
  const [tickerInput, setTickerInput] = useState("");
  const [sdk, setSdk] = useState<Record<string, boolean> | null>(null);
  const [booting, setBooting] = useState(true);
  const [threadError, setThreadError] = useState<string | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [evidencePinned, setEvidencePinned] = useState(false);
  const [evidenceMessageIndex, setEvidenceMessageIndex] = useState<number | null>(null);
  const [transcriptPendingThreadId, setTranscriptPendingThreadId] = useState<string | null>(null);
  const [catalog, setCatalog] = useState<ModelCatalog | null>(null);
  const [userSelection, setUserSelection] = useState<ResearchTuple | null>(null);
  const [incompleteSelection, setIncompleteSelection] = useState<{
    provider: ProviderId;
    model: string;
  } | null>(null);
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
  const [latestRunsByThread, setLatestRunsByThread] = useState<Record<string, ResearchRunDTO>>({});

  const abortRef = useRef<AbortController | null>(null);
  const pollingRunIdRef = useRef<string | null>(null);
  const submissionSequenceRef = useRef(0);
  const stopRequestRunIdRef = useRef<string | null>(null);
  const hydrationSequenceRef = useRef(0);
  const lifecycleGenerationRef = useRef(0);
  const initialAutoSelectAllowedRef = useRef(true);
  const consumedNavigationSequenceRef = useRef(0);
  const historyTriggerRef = useRef<HTMLButtonElement>(null);
  const evidenceTriggerRef = useRef<HTMLButtonElement>(null);
  const evidenceReturnFocusRef = useRef<HTMLElement | null>(null);
  const shellOverlay = useShellOverlay();
  const onObserveRunRef = useRef(onObserveRun);
  onObserveRunRef.current = onObserveRun;
  const onNavigationConsumedRef = useRef(onNavigationConsumed);
  onNavigationConsumedRef.current = onNavigationConsumed;

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
  const provider = incompleteSelection?.provider ?? selection?.tuple?.provider ?? null;
  const selModel = incompleteSelection?.model ?? selection?.tuple?.model ?? "";
  const selEffort = incompleteSelection ? "" : selection?.tuple?.effort ?? "default";
  const selectionReady = !incompleteSelection && selection?.state === "ready";
  const currentThread = state.activeThreadId
    ? state.threads.find((thread) => thread.id === state.activeThreadId) ?? null
    : null;

  const rememberUserSelection = useCallback((tuple: ResearchTuple) => {
    setIncompleteSelection(null);
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

  const detachLocalPolling = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    pollingRunIdRef.current = null;
  }, []);

  const observeThreadRun = useCallback((thread: ResearchThreadDTO) => {
    const activeRun = thread.active_run;
    setActiveRunsByThread((current) => {
      const next = { ...current };
      if (!activeRun || isTerminalRun(activeRun)) delete next[thread.id];
      else next[thread.id] = activeRun;
      return next;
    });
    if (!activeRun) return;
    setLatestRunsByThread((current) => ({ ...current, [thread.id]: activeRun }));
    onObserveRunRef.current?.(activeRun, thread.title);
  }, []);

  const hydrateThread = useCallback(async (thread: ResearchThreadDTO) => {
    const sequence = ++hydrationSequenceRef.current;
    submissionSequenceRef.current += 1;
    setTranscriptPendingThreadId(thread.id);
    detachLocalPolling();
    setThreadError(null);
    setUserSelection(null);
    setIncompleteSelection(null);
    setEvidenceMessageIndex(null);
    writeActiveThreadId(thread.id);
    observeThreadRun(thread);
    dispatch({
      kind: "hydrate",
      threads: [toClientThread(thread)],
      messagesByThread: {},
      activeThreadId: thread.id,
    });
    dispatch({ kind: "selectThread", threadId: thread.id });
    try {
      const response = await getResearchMessages(thread.id);
      if (sequence !== hydrationSequenceRef.current) return;
      dispatch({
        kind: "hydrateThread",
        thread: toClientThread(thread),
        messages: response.messages.map(toClientMessage),
      });
      setTranscriptPendingThreadId((current) => current === thread.id ? null : current);
    } catch {
      if (sequence === hydrationSequenceRef.current) {
        setThreadError("無法載入這個研究對話，請從歷史重新選取。");
      }
    }
  }, [detachLocalPolling, observeThreadRun]);

  const hydrateThreadById = useCallback(async (threadId: string) => {
    const requestSequence = ++hydrationSequenceRef.current;
    try {
      const { thread } = await getResearchThread(threadId);
      if (requestSequence !== hydrationSequenceRef.current) return "unavailable" as const;
      await hydrateThread(thread);
      return "loaded" as const;
    } catch (error) {
      const missing = isMissingResearchThreadError(error);
      if (requestSequence === hydrationSequenceRef.current) {
        setThreadError(missing
          ? "找不到指定的研究對話，可能已被刪除。"
          : "暫時無法載入指定的研究對話，請稍後再試。");
      }
      return missing ? "missing" as const : "unavailable" as const;
    }
  }, [hydrateThread]);

  const handleInitialHistoryRows = useCallback(async (
    rows: readonly ResearchThreadDTO[],
  ) => {
    for (const thread of rows) observeThreadRun(thread);
    if (navigationRequest || !initialAutoSelectAllowedRef.current) return;
    const savedActive = readActiveThreadId();
    if (savedActive) {
      const target = rows.find((thread) => thread.id === savedActive) ?? null;
      if (target) {
        await hydrateThread(target);
      } else {
        const result = await hydrateThreadById(savedActive);
        if (result === "missing" && initialAutoSelectAllowedRef.current && rows[0]) {
          await hydrateThread(rows[0]);
        }
      }
    } else if (rows[0]) {
      await hydrateThread(rows[0]);
    }
    initialAutoSelectAllowedRef.current = false;
  }, [hydrateThread, hydrateThreadById, navigationRequest, observeThreadRun]);

  // Ignore transcript responses and detach local replay after unmount.
  useEffect(() => {
    const generation = ++lifecycleGenerationRef.current;
    return () => {
      // React StrictMode synchronously replays setup after this cleanup. Defer
      // invalidation one microtask so only a real unmount remains current.
      queueMicrotask(() => {
        if (lifecycleGenerationRef.current !== generation) return;
        hydrationSequenceRef.current += 1;
        submissionSequenceRef.current += 1;
        detachLocalPolling();
      });
    };
  }, [detachLocalPolling]);

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
        setLatestRunsByThread((prev) => ({ ...prev, [res.run.thread_id]: res.run }));
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
    } catch {
      if (abortRef.current !== controller || controller.signal.aborted) return;
      setThreadError("暫時無法更新研究執行狀態，請稍後重新開啟此對話。");
      dispatch({ kind: "abort", runId: run.id, ts: Date.now() });
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null;
        pollingRunIdRef.current = null;
      }
    }
  }, []);

  const runManaged = useCallback(async (
    body: { question: string; provider: ProviderId; model: string; effort: string; thread_id: string; ticker: string | null; retry_last_failed?: boolean; assistant_stance?: AssistantStance },
    submissionSequence: number,
  ) => {
    try {
      const { run } = await createResearchRun(body);
      if (submissionSequenceRef.current !== submissionSequence) return;
      dispatch({ kind: "linkRun", runId: run.id, threadId: run.thread_id });
      onObserveRunRef.current?.(run);
      setActiveRunsByThread((prev) => ({ ...prev, [run.thread_id]: run }));
      setLatestRunsByThread((prev) => ({ ...prev, [run.thread_id]: run }));
      await pollRun(run);
    } catch (e) {
      if (submissionSequenceRef.current !== submissionSequence) return;
      dispatch({ kind: "streamError", error: e instanceof Error ? e.message : String(e), ts: Date.now() });
    }
  }, [pollRun]);

  useEffect(() => {
    const run = state.activeThreadId ? activeRunsByThread[state.activeThreadId] : null;
    if (!run || isTerminalRun(run)) return;
    if (transcriptPendingThreadId === run.thread_id) return;
    if (state.pending?.threadId === run.thread_id || pollingRunIdRef.current === run.id) return;
    dispatch({
      kind: "attachRun",
      runId: run.id,
      threadId: run.thread_id,
      provider: run.provider,
      model: run.model,
      effort: run.effort,
      ticker: run.ticker,
      ts: runStartedMs(run),
    });
    void pollRun(run);
  }, [activeRunsByThread, pollRun, state.activeThreadId, state.pending?.threadId, transcriptPendingThreadId]);

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
    if (
      !q
      || selection?.state !== "ready"
      || incompleteSelection !== null
      || state.pending
      || currentThread?.archived_at
      || (!!state.activeThreadId && transcriptPendingThreadId === state.activeThreadId)
    ) return;
    const ticker = tickerInput.trim().toUpperCase() || null;
    // Client-owned thread id: reuse the active thread to continue, else a fresh
    // uuid for a new conversation (agreed reducer↔store id model).
    const threadId = state.activeThreadId ?? crypto.randomUUID();
    const { provider: runProvider, model, effort } = selection.tuple;
    const submissionSequence = ++submissionSequenceRef.current;
    dispatch({ kind: "submit", question: q, provider: runProvider, model, effort, ticker, ts: Date.now(), threadId });
    writeActiveThreadId(threadId);
    setQuestion("");
    setThreadError(null);
    setEvidenceMessageIndex(null);
    void runManaged({
      question: q,
      provider: runProvider,
      model,
      effort,
      thread_id: threadId,
      ticker,
      assistant_stance: stanceForRun,
    }, submissionSequence);
  }, [question, tickerInput, selection, incompleteSelection, state.pending, state.activeThreadId, currentThread?.archived_at, runManaged, stanceForRun, transcriptPendingThreadId]);

  // Cancel server work first; keep the pending turn locked until cancellation succeeds.
  const stopStream = useCallback(() => {
    const runId = state.pending?.runId
      ?? (state.activeThreadId ? activeRunsByThread[state.activeThreadId]?.id : null);
    if (!runId || stopRequestRunIdRef.current) return;
    stopRequestRunIdRef.current = runId;
    void cancelResearchRun(runId)
      .then(({ run }) => {
        setLatestRunsByThread((current) => ({ ...current, [run.thread_id]: run }));
        setActiveRunsByThread((current) => {
          if (current[run.thread_id]?.id !== runId) return current;
          const next = { ...current };
          delete next[run.thread_id];
          return next;
        });
        onObserveRunRef.current?.(run);
        if (pollingRunIdRef.current === runId) {
          abortRef.current?.abort();
          abortRef.current = null;
          pollingRunIdRef.current = null;
        }
        dispatch({ kind: "abort", runId, ts: Date.now() });
      })
      .catch(() => setThreadError("無法停止目前研究，請稍後再試。"))
      .finally(() => {
        if (stopRequestRunIdRef.current === runId) stopRequestRunIdRef.current = null;
      });
  }, [activeRunsByThread, state.activeThreadId, state.pending?.runId]);
  const newThread = useCallback(() => {
    initialAutoSelectAllowedRef.current = false;
    hydrationSequenceRef.current += 1;
    submissionSequenceRef.current += 1;
    detachLocalPolling();
    setThreadError(null);
    setHistoryOpen(false);
    setEvidenceOpen(false);
    setEvidencePinned(false);
    setEvidenceMessageIndex(null);
    setTranscriptPendingThreadId(null);
    setUserSelection(null);
    setIncompleteSelection(null);
    writeActiveThreadId(null);
    dispatch({ kind: "newThread" });
  }, [detachLocalPolling]);

  useEffect(() => {
    if (!navigationRequest || navigationRequest.sequence <= consumedNavigationSequenceRef.current) return;
    initialAutoSelectAllowedRef.current = false;
    consumedNavigationSequenceRef.current = navigationRequest.sequence;
    onNavigationConsumedRef.current?.(navigationRequest.sequence);
    void hydrateThreadById(navigationRequest.target.threadId);
  }, [hydrateThreadById, navigationRequest]);

  const handleThreadUpdated = useCallback((updated: ResearchThreadDTO) => {
    dispatch({ kind: "updateThread", thread: toClientThread(updated) });
    observeThreadRun(updated);
  }, [observeThreadRun]);

  const handleThreadDeleted = useCallback((threadId: string) => {
    setActiveRunsByThread((current) => {
      const next = { ...current };
      delete next[threadId];
      return next;
    });
    setLatestRunsByThread((current) => {
      const next = { ...current };
      delete next[threadId];
      return next;
    });
    if (state.activeThreadId === threadId) {
      hydrationSequenceRef.current += 1;
      detachLocalPolling();
      setTranscriptPendingThreadId(null);
      setUserSelection(null);
      writeActiveThreadId(null);
    }
    dispatch({ kind: "deleteThread", threadId });
  }, [detachLocalPolling, state.activeThreadId]);

  // --- derived view state ----------------------------------------------------
  const msgs = state.activeThreadId ? state.messagesByThread[state.activeThreadId] ?? [] : [];
  const retryCandidate = useMemo(() => lastRetryCandidate(msgs), [msgs]);
  let lastAssistantIndex: number | null = null;
  for (let index = msgs.length - 1; index >= 0; index -= 1) {
    if (msgs[index].role === "assistant") {
      lastAssistantIndex = index;
      break;
    }
  }
  const explicitEvidenceIndex = evidenceMessageIndex != null
    && msgs[evidenceMessageIndex]?.role === "assistant"
    ? evidenceMessageIndex
    : null;
  const selectedEvidenceIndex = explicitEvidenceIndex ?? lastAssistantIndex;
  const evidenceMessage = (state.pending && explicitEvidenceIndex == null)
    || selectedEvidenceIndex == null
    ? null
    : msgs[selectedEvidenceIndex];
  const evidenceTrace: TraceRow[] = explicitEvidenceIndex == null
    ? state.pending?.trace ?? []
    : [];
  const evidenceHasContent = researchEvidenceRows(evidenceMessage, evidenceTrace).length > 0;
  const evidenceVisible = evidenceOpen && !(shellOverlay && historyOpen);
  const threadActiveRun = state.activeThreadId ? activeRunsByThread[state.activeThreadId] ?? null : null;
  const threadLatestRun = state.activeThreadId ? latestRunsByThread[state.activeThreadId] ?? null : null;
  const pendingRunId = state.pending?.runId ?? null;
  const currentRun = state.pending
    ? pendingRunId
      ? [threadActiveRun, threadLatestRun].find((run) => run?.id === pendingRunId) ?? null
      : null
    : threadActiveRun ?? threadLatestRun;
  useEffect(() => {
    if (!evidencePinned || evidenceHasContent) return;
    setEvidencePinned(false);
    setEvidenceOpen(false);
  }, [evidenceHasContent, evidencePinned]);
  useEffect(() => {
    if (!shellOverlay || !historyOpen || !evidenceOpen) return;
    setEvidenceOpen(false);
  }, [evidenceOpen, historyOpen, shellOverlay]);
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
  const effortChoices = !selEffort || supportedEffortChoices.some((option) => option.id === selEffort)
    ? supportedEffortChoices
    : [...supportedEffortChoices, {
        id: selEffort,
        provider: provider ?? "openai",
        label: `${selEffort} · 此模型不支援`,
        description: "此儲存值不再受目前模型支援",
        applies_to_card_tasks: false,
        disabled: true,
      }];
  const pickerEffortNote = provider && selEffort
    ? effortNote(provider, selection?.authMode ?? null, selEffort)
    : null;

  const chooseModel = useCallback((nextModel: string) => {
    if (!provider || !catalog) return;
    const entry = catalog.effective?.tasks.ai_research?.providers?.[provider]
      ?.models.find((candidate) => candidate.id === nextModel);
    if (!entry) return;
    const supported = selEffort === "default" || effortOptionsForModel(
      catalog,
      provider,
      nextModel,
      entry.effort_options,
    ).some((option) => option.id === selEffort);
    if (!supported) {
      setIncompleteSelection({ provider, model: nextModel });
      return;
    }
    rememberUserSelection({ provider, model: nextModel, effort: selEffort });
  }, [catalog, provider, rememberUserSelection, selEffort]);

  const chooseEffort = useCallback((nextEffort: string) => {
    if (!provider || !selModel || !nextEffort) return;
    rememberUserSelection({ provider, model: selModel, effort: nextEffort });
  }, [provider, rememberUserSelection, selModel]);

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
    if (
      !retryCandidate
      || !state.activeThreadId
      || state.pending
      || selection?.state !== "ready"
      || incompleteSelection !== null
      || currentThread?.archived_at
    ) return;
    const retryTuple = selection.tuple;
    const submissionSequence = ++submissionSequenceRef.current;
    setThreadError(null);
    setEvidenceMessageIndex(null);
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
    }, submissionSequence);
  }, [currentThread?.archived_at, incompleteSelection, retryCandidate, runManaged, selection, state.activeThreadId, state.pending, stanceForRun]);
  const activeRunIds = useMemo(
    () => new Set(Object.values(activeRunsByThread).map((run) => run.id)),
    [activeRunsByThread],
  );

  return (
    <main className="main research">
      <PageHeader
        title="AI 研究"
        context={(
          <div className="research-page-context">
            <span className="muted tiny">對話與研究執行保存於本地；離開頁面後，研究仍會繼續執行。</span>
            {incompleteSelection ? (
              <span className="warn-text tiny">
                研究模型：{incompleteSelection.provider} · {incompleteSelection.model} · 尚未選擇 effort（未套用）
              </span>
            ) : selection?.tuple ? (
              <span className="muted tiny">
                研究模型：{selection.tuple.provider} · {selection.tuple.model} · {selection.tuple.effort === "default" ? "Provider 預設" : selection.tuple.effort}
                {selection.provenance ? `（${selectionProvenanceLabel(selection.provenance)}）` : ""}
              </span>
            ) : null}
          </div>
        )}
        actions={(
          <>
            <Button
              ref={historyTriggerRef}
              size="compact"
              tone="secondary"
              icon={<History size={16} />}
              onClick={() => {
                if (shellOverlay || !evidencePinned) setEvidenceOpen(false);
                setHistoryOpen(true);
              }}
            >
              歷史
            </Button>
            <Button
              ref={evidenceTriggerRef}
              size="compact"
              tone="secondary"
              icon={<FileSearch size={16} />}
              onClick={() => {
                evidenceReturnFocusRef.current = evidenceTriggerRef.current;
                setHistoryOpen(false);
                setEvidenceOpen(true);
              }}
            >
              證據
            </Button>
            <Button
              size="compact"
              tone="primary"
              icon={<Plus size={16} />}
              onClick={newThread}
            >
              新研究
            </Button>
          </>
        )}
      />

      <div className={`research-workspace${evidenceVisible && evidencePinned && evidenceHasContent && !shellOverlay ? " has-pinned-evidence" : ""}`}>
        {/* ── Conversation workspace ──────────────────────────────────── */}
        <section className="research-convo">
          <div className="research-conversation-head">
            <h2 className="research-conversation-title">
              {currentThread?.title?.trim() || "新對話"}
            </h2>
            {currentThread?.archived_at ? (
              <span className="warn-text tiny">此對話已封存；取消封存後才能繼續提問。</span>
            ) : null}
            {state.pending ? (
              <span className="muted tiny">回應由背景服務繼續執行；只有「停止」會取消目前執行。</span>
            ) : null}
          </div>
          {threadError ? <p className="error-text tiny">{threadError}</p> : null}
          <div className="research-messages">
            {msgs.length === 0 && !state.pending ? (
              <div className="research-empty">
                <p className="muted">問一個開放式問題，看 agent 如何用工具調查並整理證據。</p>
                <div className="research-suggest">
                  {SUGGESTED.map((s) => (
                    <Button
                      key={s.text}
                      size="compact"
                      tone="ghost"
                      onClick={() => { setQuestion(s.text); setTickerInput(s.ticker); }}
                    >
                      {s.text}
                    </Button>
                  ))}
                </div>
              </div>
            ) : (
              msgs.map((m, i) => (
                <Bubble
                  key={i}
                  m={m}
                  onOpenTicker={onOpenTicker}
                  developerMode={developerMode}
                  onNavigate={onNavigate}
                  onInspect={(trigger) => {
                    evidenceReturnFocusRef.current = trigger;
                    setEvidenceMessageIndex(i);
                    setHistoryOpen(false);
                    setEvidenceOpen(true);
                  }}
                  canRetry={!!retryCandidate && i === msgs.length - 1 && !state.pending && !currentThread?.archived_at && selectionReady}
                  onRetry={retryLastFailed}
                />
              ))
            )}

            {state.pending && (
              <PendingAssistantBubble pending={state.pending} />
            )}
          </div>

          <ResearchRunProgress
            pending={state.pending}
            run={currentRun}
            runtime={runtime}
            developerMode={developerMode}
            onStop={stopStream}
            onNavigate={onNavigate}
          />

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
                    <Button
                      key={choice.id}
                      size="compact"
                      tone={provider === choice.id ? "primary" : "secondary"}
                      onClick={() => chooseProvider(choice.id)}
                      disabled={choice.disabled || !!state.pending}
                      title={choice.providerReason
                        ? modelReasonLabel(choice.providerReason)
                        : `${choice.context?.label ?? choice.id}；${PRESENTATION[choice.id].trace_note}`}
                    >
                      {PRESENTATION[choice.id].label} / {choice.suggestedModel || "無可用模型"}
                      {choice.providerReason
                        ? ` · ${modelReasonLabel(choice.providerReason)}`
                        : choice.context?.auth_mode
                          ? ` · ${MODEL_UX_LABELS.authModes[choice.context.auth_mode] ?? choice.context.auth_mode}`
                          : ""}
                    </Button>
                  ))}
                </div>
                {selection?.state === "needs_selection" && state.activeThreadId && (
                  <div className="research-providerbar">
                    {threadSelectionLoadError ? (
                      <>
                        <span className="warn-text tiny">無法確認此對話上次使用的模型；目前不會自動 fallback。</span>
                        <Button
                          size="compact"
                          tone="ghost"
                          onClick={() => setThreadSelectionRequestVersion((version) => version + 1)}
                        >
                          重新確認模型
                        </Button>
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
                        aria-label="模型"
                        onChange={(event) => chooseModel(event.target.value)}
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
                        aria-label="effort"
                        aria-invalid={incompleteSelection ? "true" : undefined}
                        onChange={(event) => chooseEffort(event.target.value)}
                        disabled={!!state.pending}
                      >
                        {incompleteSelection ? (
                          <option value="" disabled>請選擇此模型支援的 effort</option>
                        ) : null}
                        {effortChoices.map((o) => (
                          <option key={o.id} value={o.id} disabled={"disabled" in o && o.disabled}>
                            {o.id === "default" ? "Provider 預設" : o.label ?? o.id}
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
                    {incompleteSelection ? (
                      <span className="warn-text tiny">此模型不支援已選 effort，請明確選擇新的 effort。</span>
                    ) : null}
                    {(selection?.state === "blocked" || incompleteSelection) && onNavigate ? (
                      <Button
                        size="compact"
                        tone="secondary"
                        onClick={() => onNavigate({ kind: "settings_section", section: "models" })}
                      >
                        前往模型設定
                      </Button>
                    ) : null}
                    {stanceEnabled && (
                      <label className="tiny">
                        立場
                        <select value={runStance} onChange={(e) => setRunStance(e.target.value as AssistantStance)} disabled={!!state.pending}>
                          {(["off", "neutral", "aligned", "complementary", "strict_risk_control", "valuation_rationalist", "growth_opportunity"] as AssistantStance[]).map((s) => (
                            <option key={s} value={s}>{stanceLabel(s, commonT)}</option>
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
                    disabled={Boolean(currentThread?.archived_at)}
                  />
                  <textarea
                    className="research-textarea"
                    placeholder="輸入問題…（Enter 送出，Shift+Enter 換行）"
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } }}
                    rows={2}
                    disabled={Boolean(currentThread?.archived_at)}
                  />
                  <Button
                    tone="primary"
                    onClick={submit}
                    disabled={
                      !selectionReady
                      || !!state.pending
                      || !question.trim()
                      || Boolean(currentThread?.archived_at)
                      || (!!state.activeThreadId && transcriptPendingThreadId === state.activeThreadId)
                    }
                  >
                    送出
                  </Button>
                </div>
              </>
            )}
          </div>
        </section>

        <ResearchEvidenceDrawer
          open={evidenceVisible}
          pinned={evidencePinned}
          onClose={() => setEvidenceOpen(false)}
          onPinnedChange={setEvidencePinned}
          returnFocusRef={evidenceReturnFocusRef}
          message={evidenceMessage}
          activeTrace={evidenceTrace}
          activeRun={currentRun}
          developerMode={developerMode}
        />
      </div>
      <ResearchHistoryDrawer
        open={historyOpen}
        onClose={() => setHistoryOpen(false)}
        activeThreadId={state.activeThreadId}
        activeRunIds={activeRunIds}
        onInitialRowsReady={(rows) => void handleInitialHistoryRows(rows)}
        onSelect={(thread) => {
          initialAutoSelectAllowedRef.current = false;
          setHistoryOpen(false);
          void hydrateThread(thread);
        }}
        onThreadUpdated={handleThreadUpdated}
        onThreadDeleted={handleThreadDeleted}
        returnFocusRef={historyTriggerRef}
      />
    </main>
  );
}

function Bubble({
  m,
  onOpenTicker,
  developerMode,
  onNavigate,
  onInspect,
  canRetry,
  onRetry,
}: {
  m: Message;
  onOpenTicker: (t: string) => void;
  developerMode: boolean;
  onNavigate?: (target: NavigationTarget) => void;
  onInspect: (trigger: HTMLButtonElement) => void;
  canRetry?: boolean;
  onRetry?: () => void;
}) {
  const { t: commonT } = useTranslation("common");
  const error = m.role === "assistant" && (m.isError || m.maxTurns)
    ? presentResearchError({
        code: m.errorCode ?? (m.maxTurns ? "tool_limit_reached" : null),
        detail: m.errorDetail ?? m.content,
        developerMode,
      })
    : null;
  const personalizationSummary = traceSummary(m.personalization, commonT);
  const cls = `research-bubble ${m.role}${error ? ` ${error.state}` : ""}`;
  return (
    <div className={cls} data-state={error?.state}>
      {m.role === "assistant" && (m.model || m.maxTurns) && (
        <div className="research-bubble-meta muted tiny">
          {m.model && <span className="research-model">{m.provider}/{m.model}{m.effort && m.effort !== "default" ? ` · ${m.effort}` : ""}</span>}
          {m.maxTurns && <span className="research-maxturns"> · 已達工具呼叫上限</span>}
          {typeof m.elapsed_seconds === "number" && <span> · {m.elapsed_seconds.toFixed(1)}s</span>}
          {personalizationSummary && <span> · {personalizationSummary}</span>}
        </div>
      )}
      <div className="research-bubble-body">
        {error ? (
          <>
            <strong className="research-error-title">{error.title}</strong>
            <div>{error.detail}</div>
          </>
        ) : m.role === "assistant" && m.content ? (
          // assistant answers are Markdown (safe renderer); user/error/maxTurns
          // stay literal text (don't reinterpret a raw question or error string).
          <MarkdownView source={m.content} />
        ) : (
          m.content || (m.role === "assistant" ? "（空回應）" : "")
        )}
      </div>
      {error?.developerDetail ? (
        <details className="research-diagnostic">
          <summary>診斷細節</summary>
          <pre>{error.developerDetail}</pre>
        </details>
      ) : null}
      {m.tickers && m.tickers.length > 0 && (
        <div className="research-bubble-tickers">
          {m.tickers.map((t) => (
            <button key={t} className="news-ticker-chip" onClick={() => onOpenTicker(t)} title={`開啟 ${t}`}>{t}</button>
          ))}
        </div>
      )}
      {m.role === "assistant" ? (
        <div className="research-bubble-actions">
          <Button
            size="compact"
            tone="ghost"
            onClick={(event) => onInspect(event.currentTarget)}
          >
            查看證據
          </Button>
          {error?.actionLabel && error.target && onNavigate ? (
            <Button size="compact" tone="secondary" onClick={() => onNavigate(error.target!)}>
              {error.actionLabel}
            </Button>
          ) : null}
          {canRetry ? (
            <Button
              size="compact"
              tone="secondary"
              onClick={onRetry}
              title="保留同一對話上下文，排除最後失敗回合後重試"
            >
              重試
            </Button>
          ) : null}
        </div>
      ) : null}
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
