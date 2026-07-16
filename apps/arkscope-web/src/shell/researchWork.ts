import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  getResearchRun,
  getResearchThreads,
  type ResearchRunDTO,
  type ResearchThreadDTO,
} from "../api";

export const RESEARCH_WORK_STORAGE_KEY = "arkscope.shell.researchWork.v1";
const MAX_PERSISTED_IDENTITIES = 50;
const FALLBACK_THREAD_TITLE = "AI 研究";

export type ShellResearchWorkStatus = ResearchRunDTO["status"];

export interface ResearchWorkItem {
  runId: string;
  threadId: string;
  threadTitle: string;
  status: ShellResearchWorkStatus;
  createdAt: string;
  startedAt: string | null;
  completedAt: string | null;
}

export interface ResearchWorkState {
  items: ResearchWorkItem[];
  activeCount: number;
  attentionCount: number;
  refresh: () => Promise<void>;
  observeRun: (run: ResearchRunDTO, threadTitle?: string) => void;
  dismiss: (runId: string) => void;
}

export interface ResearchWorkApi {
  getThreads: typeof getResearchThreads;
  getRun: typeof getResearchRun;
}

interface PersistedResearchWorkIdentity {
  runId: string;
  threadId: string;
  observedAt: number;
}

export interface ResearchWorkOptions {
  api?: ResearchWorkApi;
  storage?: Pick<Storage, "getItem" | "setItem">;
  activePollMs?: number;
  discoveryPollMs?: number;
  now?: () => number;
}

const DEFAULT_API: ResearchWorkApi = {
  getThreads: getResearchThreads,
  getRun: getResearchRun,
};

function isActive(status: ShellResearchWorkStatus): boolean {
  return status === "queued" || status === "running";
}

function normalizedTitle(value: string | undefined, previous?: string): string {
  const title = value?.trim();
  return title || previous || FALLBACK_THREAD_TITLE;
}

function projectRun(
  run: ResearchRunDTO,
  threadTitle: string | undefined,
  previous?: ResearchWorkItem,
): ResearchWorkItem {
  return {
    runId: run.id,
    threadId: run.thread_id,
    threadTitle: normalizedTitle(threadTitle, previous?.threadTitle),
    status: run.status,
    createdAt: run.created_at,
    startedAt: run.started_at,
    completedAt: run.completed_at,
  };
}

function normalizeIdentities(value: unknown): PersistedResearchWorkIdentity[] {
  if (!Array.isArray(value)) return [];
  const byRun = new Map<string, PersistedResearchWorkIdentity>();
  for (const candidate of value) {
    if (!candidate || typeof candidate !== "object") continue;
    const record = candidate as Record<string, unknown>;
    const runId = typeof record.runId === "string" ? record.runId.trim() : "";
    const threadId = typeof record.threadId === "string" ? record.threadId.trim() : "";
    const observedAt = record.observedAt;
    if (!runId || !threadId || typeof observedAt !== "number" || !Number.isFinite(observedAt)) continue;
    const prior = byRun.get(runId);
    if (!prior || observedAt >= prior.observedAt) {
      byRun.set(runId, { runId, threadId, observedAt });
    }
  }
  return Array.from(byRun.values())
    .sort((left, right) => left.observedAt - right.observedAt || left.runId.localeCompare(right.runId))
    .slice(-MAX_PERSISTED_IDENTITIES);
}

function readIdentities(storage: Pick<Storage, "getItem"> | null): PersistedResearchWorkIdentity[] {
  if (!storage) return [];
  try {
    const raw = storage.getItem(RESEARCH_WORK_STORAGE_KEY);
    return raw === null ? [] : normalizeIdentities(JSON.parse(raw));
  } catch {
    return [];
  }
}

function writeIdentities(
  storage: Pick<Storage, "setItem"> | null,
  identities: PersistedResearchWorkIdentity[],
): void {
  if (!storage) return;
  try {
    storage.setItem(RESEARCH_WORK_STORAGE_KEY, JSON.stringify(identities));
  } catch {
    // In-memory observation remains available for this session.
  }
}

function defaultSessionStorage(): Pick<Storage, "getItem" | "setItem"> | null {
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

export function useResearchWorkRegistry(options: ResearchWorkOptions = {}): ResearchWorkState {
  const api = options.api ?? DEFAULT_API;
  const activePollMs = options.activePollMs ?? 5_000;
  const discoveryPollMs = options.discoveryPollMs ?? 30_000;
  const nowRef = useRef(options.now ?? Date.now);
  nowRef.current = options.now ?? Date.now;

  // Deliberately session-scoped: closing the browser must not resurrect old
  // attention notifications. The injected storage exists only for tests.
  const [storage] = useState<Pick<Storage, "getItem" | "setItem"> | null>(
    () => options.storage ?? defaultSessionStorage(),
  );
  const [identities, setIdentities] = useState<PersistedResearchWorkIdentity[]>(
    () => readIdentities(storage),
  );
  const identitiesRef = useRef(identities);
  const [itemsById, setItemsById] = useState<Record<string, ResearchWorkItem>>({});
  const itemsRef = useRef(itemsById);
  const discoveryInFlightRef = useRef<Promise<void> | null>(null);
  const activeInFlightRef = useRef<Promise<void> | null>(null);
  const mountedRef = useRef(true);

  const replaceIdentities = useCallback((
    update: (current: PersistedResearchWorkIdentity[]) => PersistedResearchWorkIdentity[],
  ) => {
    setIdentities((current) => {
      const next = normalizeIdentities(update(current));
      identitiesRef.current = next;
      writeIdentities(storage, next);
      return next;
    });
  }, [storage]);

  const rememberIdentity = useCallback((run: ResearchRunDTO) => {
    const identity = {
      runId: run.id,
      threadId: run.thread_id,
      observedAt: nowRef.current(),
    };
    replaceIdentities((current) => [
      ...current.filter((entry) => entry.runId !== identity.runId),
      identity,
    ]);
  }, [replaceIdentities]);

  const observeRun = useCallback((run: ResearchRunDTO, threadTitle?: string) => {
    if (!run.id.trim() || !run.thread_id.trim()) return;
    setItemsById((current) => {
      const next = {
        ...current,
        [run.id]: projectRun(run, threadTitle, current[run.id]),
      };
      itemsRef.current = next;
      return next;
    });
    rememberIdentity(run);
  }, [rememberIdentity]);

  const refresh = useCallback((): Promise<void> => {
    if (discoveryInFlightRef.current) return discoveryInFlightRef.current;
    const request = (async () => {
      let threads: ResearchThreadDTO[] = [];
      try {
        ({ threads } = await api.getThreads(50));
      } catch {
        // Preserve prior truth and still reconcile session-observed identities.
      }
      if (!mountedRef.current) return;

      const titleByThread = new Map(threads.map((thread) => [thread.id, thread.title]));
      const activeRunIds = new Set<string>();
      for (const thread of threads) {
        if (!thread.active_run || !isActive(thread.active_run.status)) continue;
        activeRunIds.add(thread.active_run.id);
        observeRun(thread.active_run, thread.title);
      }

      const missing = identitiesRef.current.filter((identity) => (
        !activeRunIds.has(identity.runId) && !itemsRef.current[identity.runId]
      ));
      const settled = await Promise.allSettled(missing.map((identity) => api.getRun(identity.runId)));
      if (!mountedRef.current) return;
      settled.forEach((result) => {
        if (result.status !== "fulfilled") return;
        observeRun(result.value.run, titleByThread.get(result.value.run.thread_id));
      });
    })().finally(() => {
      discoveryInFlightRef.current = null;
    });
    discoveryInFlightRef.current = request;
    return request;
  }, [api, observeRun]);

  const reconcileActive = useCallback((): Promise<void> => {
    if (activeInFlightRef.current) return activeInFlightRef.current;
    const activeItems = Object.values(itemsRef.current).filter((item) => isActive(item.status));
    const request = (async () => {
      const settled = await Promise.allSettled(activeItems.map((item) => api.getRun(item.runId)));
      if (!mountedRef.current) return;
      settled.forEach((result, index) => {
        if (result.status !== "fulfilled") return;
        observeRun(result.value.run, activeItems[index]?.threadTitle);
      });
    })().finally(() => {
      activeInFlightRef.current = null;
    });
    activeInFlightRef.current = request;
    return request;
  }, [api, observeRun]);

  const dismiss = useCallback((runId: string) => {
    const item = itemsRef.current[runId];
    if (!item || isActive(item.status)) return;
    setItemsById((current) => {
      const next = { ...current };
      delete next[runId];
      itemsRef.current = next;
      return next;
    });
    replaceIdentities((current) => current.filter((identity) => identity.runId !== runId));
  }, [replaceIdentities]);

  useEffect(() => {
    mountedRef.current = true;
    void refresh();
    const activeTimer = window.setInterval(() => { void reconcileActive(); }, activePollMs);
    const discoveryTimer = window.setInterval(() => { void refresh(); }, discoveryPollMs);
    const onFocus = () => { void refresh(); };
    window.addEventListener("focus", onFocus);
    return () => {
      mountedRef.current = false;
      window.clearInterval(activeTimer);
      window.clearInterval(discoveryTimer);
      window.removeEventListener("focus", onFocus);
    };
  }, [activePollMs, discoveryPollMs, reconcileActive, refresh]);

  const items = useMemo(
    () => Object.values(itemsById).sort((left, right) => (
      Date.parse(right.createdAt) - Date.parse(left.createdAt) || left.runId.localeCompare(right.runId)
    )),
    [itemsById],
  );

  return {
    items,
    activeCount: items.filter((item) => isActive(item.status)).length,
    attentionCount: items.filter((item) => !isActive(item.status)).length,
    refresh,
    observeRun,
    dismiss,
  };
}
