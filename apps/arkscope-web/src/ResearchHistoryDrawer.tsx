import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type RefObject,
} from "react";
import {
  Archive,
  ArchiveRestore,
  Check,
  Pencil,
  RefreshCw,
  Trash2,
  X,
} from "lucide-react";
import { useTranslation } from "react-i18next";

import {
  ApiError,
  deleteResearchThread,
  queryResearchThreads,
  updateResearchThread,
  type ResearchHistoryArchiveMode,
  type ResearchHistoryRunState,
  type ResearchThreadDTO,
  type ResearchThreadQueryParams,
} from "./api";
import { researchHistoryStatus } from "./i18n/researchPresentation";
import { Button, IconButton } from "./ui/Button";
import { ConfirmDialog } from "./ui/ConfirmDialog";
import { Drawer } from "./ui/Drawer";
import { StatusBadge } from "./ui/Status";

const PAGE_LIMIT = 50;
const THREAD_MUTATION_PATH = /^\/research\/threads\/[^/?#]+$/;

interface HistoryFilters {
  q: string;
  ticker: string;
  updatedFrom: string;
  updatedThrough: string;
  runState: ResearchHistoryRunState;
  archived: ResearchHistoryArchiveMode;
}

type MutationFailure = "active_run_conflict" | "thread_missing" | "update_failed";
type RenameFailure = MutationFailure | "empty_name";
type LoadPageResult = "committed" | "failed" | "superseded";

const INITIAL_FILTERS: HistoryFilters = {
  q: "",
  ticker: "",
  updatedFrom: "",
  updatedThrough: "",
  runState: "all",
  archived: "current",
};

function isInitialHistoryQuery(filters: HistoryFilters): boolean {
  return filters.q === ""
    && filters.ticker === ""
    && filters.updatedFrom === ""
    && filters.updatedThrough === ""
    && filters.runState === "all"
    && filters.archived === "current";
}

export interface ResearchHistoryDrawerProps {
  open: boolean;
  onClose: () => void;
  activeThreadId: string | null;
  activeRunIds: ReadonlySet<string>;
  onInitialRowsReady: (rows: readonly ResearchThreadDTO[]) => void;
  onInitialLoadFailed?: () => void;
  onSelect: (thread: ResearchThreadDTO) => void;
  onThreadUpdated: (thread: ResearchThreadDTO) => void;
  onThreadDeleted: (id: string) => void;
  returnFocusRef?: RefObject<HTMLElement | null>;
}

function localDateIso(value: string, nextDay: boolean): string | undefined {
  const parts = value.split("-").map(Number);
  if (parts.length !== 3 || parts.some((part) => !Number.isInteger(part))) return undefined;
  const [year, month, day] = parts;
  const date = new Date(year, month - 1, day + (nextDay ? 1 : 0));
  if (!nextDay && (
    date.getFullYear() !== year
    || date.getMonth() !== month - 1
    || date.getDate() !== day
  )) return undefined;
  return date.toISOString();
}

function queryFor(filters: HistoryFilters, offset: number): ResearchThreadQueryParams {
  return {
    ...(filters.q.trim() ? { q: filters.q.trim() } : {}),
    ...(filters.ticker.trim() ? { ticker: filters.ticker.trim().toUpperCase() } : {}),
    ...(filters.updatedFrom
      ? { updated_from: localDateIso(filters.updatedFrom, false) }
      : {}),
    ...(filters.updatedThrough
      ? { updated_before: localDateIso(filters.updatedThrough, true) }
      : {}),
    run_state: filters.runState,
    archived: filters.archived,
    limit: PAGE_LIMIT,
    offset,
  };
}

function queryKeyFor(filters: HistoryFilters): string {
  const query = queryFor(filters, 0);
  return JSON.stringify([
    query.q ?? null,
    query.ticker ?? null,
    query.updated_from ?? null,
    query.updated_before ?? null,
    query.run_state ?? null,
    query.archived ?? null,
  ]);
}

function appendUnique(
  current: readonly ResearchThreadDTO[],
  incoming: readonly ResearchThreadDTO[],
): ResearchThreadDTO[] {
  const next = [...current];
  const seen = new Set(current.map((thread) => thread.id));
  for (const thread of incoming) {
    if (seen.has(thread.id)) continue;
    seen.add(thread.id);
    next.push(thread);
  }
  return next;
}

function formatLocalTime(value: string): string {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
}

function mutationFailure(error: unknown): MutationFailure {
  if (!(error instanceof ApiError) || !THREAD_MUTATION_PATH.test(error.path)) {
    return "update_failed";
  }
  if (error.status === 404 && (error.code === null || error.code === "thread_missing")) {
    return "thread_missing";
  }
  if (error.status === 409 && (error.code === null || error.code === "active_run_conflict")) {
    return "active_run_conflict";
  }
  return "update_failed";
}

export function ResearchHistoryDrawer({
  open,
  onClose,
  activeThreadId,
  activeRunIds,
  onInitialRowsReady,
  onInitialLoadFailed,
  onSelect,
  onThreadUpdated,
  onThreadDeleted,
  returnFocusRef,
}: ResearchHistoryDrawerProps) {
  const { t: researchT } = useTranslation("research");
  const [filters, setFilters] = useState<HistoryFilters>(INITIAL_FILTERS);
  const [rows, setRows] = useState<ResearchThreadDTO[]>([]);
  const [total, setTotal] = useState(0);
  const [nextOffset, setNextOffset] = useState(0);
  const [acceptedQueryKey, setAcceptedQueryKey] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [appending, setAppending] = useState(false);
  const [stale, setStale] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const [mutationError, setMutationError] = useState<MutationFailure | null>(null);
  const [mutationId, setMutationId] = useState<string | null>(null);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameDraft, setRenameDraft] = useState("");
  const [renameError, setRenameError] = useState<RenameFailure | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ResearchThreadDTO | null>(null);
  const [deleteReturnFocus, setDeleteReturnFocus] = useState<HTMLButtonElement | null>(null);
  const [pendingFocusRequest, setPendingFocusRequest] = useState<{
    target: "refresh" | string;
    sequence: number;
  } | null>(null);

  const rowsRef = useRef<ResearchThreadDTO[]>([]);
  const acceptedQueryKeyRef = useRef<string | null>(null);
  const filtersRef = useRef(filters);
  filtersRef.current = filters;
  const requestSequenceRef = useRef(0);
  const initialRowsNotifiedRef = useRef(false);
  const initialRowsCallbackRef = useRef(onInitialRowsReady);
  initialRowsCallbackRef.current = onInitialRowsReady;
  const initialFailureCallbackRef = useRef(onInitialLoadFailed);
  initialFailureCallbackRef.current = onInitialLoadFailed;
  const deleteReturnFocusRef = useMemo(
    () => ({ current: deleteReturnFocus }),
    [deleteReturnFocus],
  );
  const refreshButtonRef = useRef<HTMLButtonElement>(null);
  const rowSelectRefs = useRef(new Map<string, HTMLButtonElement>());
  const focusSequenceRef = useRef(0);
  const mutationOwnerRef = useRef<number | null>(null);
  const mutationSequenceRef = useRef(0);

  const focusAfterRender = useCallback((target: "refresh" | string) => {
    setPendingFocusRequest({ target, sequence: ++focusSequenceRef.current });
  }, []);

  useEffect(() => {
    if (pendingFocusRequest === null) return undefined;
    const timer = window.setTimeout(() => {
      const target = pendingFocusRequest.target === "refresh"
        ? refreshButtonRef.current
        : rowSelectRefs.current.get(pendingFocusRequest.target) ?? refreshButtonRef.current;
      target?.focus();
      setPendingFocusRequest((current) => (
        current?.sequence === pendingFocusRequest.sequence ? null : current
      ));
    }, 0);
    return () => window.clearTimeout(timer);
  }, [pendingFocusRequest, rows]);

  const commitRows = useCallback((next: ResearchThreadDTO[]) => {
    rowsRef.current = next;
    setRows(next);
  }, []);

  const invalidateLoads = useCallback(() => {
    requestSequenceRef.current += 1;
    setLoading(false);
    setAppending(false);
  }, []);

  const beginMutation = useCallback((threadId: string): number | null => {
    if (mutationOwnerRef.current !== null) return null;
    const token = ++mutationSequenceRef.current;
    mutationOwnerRef.current = token;
    setMutationId(threadId);
    return token;
  }, []);

  const finishMutation = useCallback((token: number) => {
    if (mutationOwnerRef.current !== token) return;
    mutationOwnerRef.current = null;
    setMutationId(null);
  }, []);

  const loadPage = useCallback(async (
    requestedFilters: HistoryFilters,
    offset: number,
    append: boolean,
  ): Promise<LoadPageResult> => {
    const requestedQueryKey = queryKeyFor(requestedFilters);
    if (append && acceptedQueryKeyRef.current !== requestedQueryKey) {
      return "failed";
    }
    const sequence = ++requestSequenceRef.current;
    if (append) setAppending(true);
    else {
      setAppending(false);
      setLoading(true);
    }
    setLoadError(false);
    try {
      const page = await queryResearchThreads(queryFor(requestedFilters, offset));
      if (
        sequence !== requestSequenceRef.current
        || requestedQueryKey !== queryKeyFor(filtersRef.current)
      ) return "superseded";
      const nextRows = append
        ? appendUnique(rowsRef.current, page.threads)
        : [...page.threads];
      acceptedQueryKeyRef.current = requestedQueryKey;
      setAcceptedQueryKey(requestedQueryKey);
      commitRows(nextRows);
      setTotal(page.total);
      setNextOffset(page.offset + page.limit);
      setStale(false);
      if (
        !initialRowsNotifiedRef.current
        && page.offset === 0
        && isInitialHistoryQuery(requestedFilters)
      ) {
        initialRowsNotifiedRef.current = true;
        initialRowsCallbackRef.current(page.threads);
      }
      return "committed";
    } catch {
      if (
        sequence !== requestSequenceRef.current
        || requestedQueryKey !== queryKeyFor(filtersRef.current)
      ) return "superseded";
      const retainsAcceptedRows = acceptedQueryKeyRef.current === requestedQueryKey;
      if (!retainsAcceptedRows) {
        acceptedQueryKeyRef.current = null;
        setAcceptedQueryKey(null);
        commitRows([]);
        setTotal(0);
        setNextOffset(0);
      }
      setLoadError(true);
      if (!initialRowsNotifiedRef.current && isInitialHistoryQuery(requestedFilters)) {
        initialFailureCallbackRef.current?.();
      }
      setStale(retainsAcceptedRows && rowsRef.current.length > 0);
      return "failed";
    } finally {
      if (sequence === requestSequenceRef.current) {
        if (append) setAppending(false);
        else setLoading(false);
      }
    }
  }, [commitRows]);

  useEffect(() => {
    setNextOffset(0);
    void loadPage(filters, 0, false);
  }, [filters, loadPage]);

  useEffect(() => () => {
    requestSequenceRef.current += 1;
  }, []);

  const updateFilter = useCallback(<K extends keyof HistoryFilters>(
    key: K,
    value: HistoryFilters[K],
  ) => {
    setNextOffset(0);
    setFilters((current) => ({ ...current, [key]: value }));
  }, []);

  const replaceRow = useCallback((updated: ResearchThreadDTO) => {
    commitRows(rowsRef.current.map((thread) => (
      thread.id === updated.id ? updated : thread
    )));
  }, [commitRows]);

  const removeRow = useCallback((id: string) => {
    const next = rowsRef.current.filter((thread) => thread.id !== id);
    if (next.length === rowsRef.current.length) return;
    commitRows(next);
    setTotal((current) => Math.max(0, current - 1));
    setNextOffset((current) => Math.max(0, current - 1));
  }, [commitRows]);

  const beginRename = useCallback((thread: ResearchThreadDTO) => {
    if (mutationOwnerRef.current !== null) return;
    setRenamingId(thread.id);
    setRenameDraft(thread.title);
    setRenameError(null);
    setMutationError(null);
  }, []);

  const cancelRename = useCallback((focusThreadId?: string) => {
    setRenamingId(null);
    setRenameDraft("");
    setRenameError(null);
    if (focusThreadId) focusAfterRender(focusThreadId);
  }, [focusAfterRender]);

  const reloadAfterMutation = useCallback(async (
    token: number,
    focusTarget: "refresh" | string,
  ) => {
    const result = await loadPage(filtersRef.current, 0, false);
    if (result === "committed" && mutationOwnerRef.current === token) {
      focusAfterRender(focusTarget);
    }
    return result;
  }, [focusAfterRender, loadPage]);

  const reconcileMissingThread = useCallback(async (
    threadId: string,
    token: number,
  ) => {
    if (mutationOwnerRef.current !== token) return;
    invalidateLoads();
    removeRow(threadId);
    onThreadDeleted(threadId);
    setMutationError("thread_missing");
    const result = await reloadAfterMutation(token, "refresh");
    if (result === "committed" && mutationOwnerRef.current === token) {
      removeRow(threadId);
    }
  }, [invalidateLoads, onThreadDeleted, reloadAfterMutation, removeRow]);

  const saveRename = useCallback(async (thread: ResearchThreadDTO) => {
    if (mutationOwnerRef.current !== null) return;
    const title = renameDraft;
    if (!title.trim()) {
      setRenameError("empty_name");
      return;
    }
    const token = beginMutation(thread.id);
    if (token === null) return;
    setMutationError(null);
    setRenameError(null);
    try {
      const { thread: updated } = await updateResearchThread(thread.id, { title });
      if (mutationOwnerRef.current !== token) return;
      invalidateLoads();
      replaceRow(updated);
      cancelRename();
      onThreadUpdated(updated);
      await reloadAfterMutation(token, updated.id);
    } catch (error) {
      if (mutationOwnerRef.current !== token) return;
      const failure = mutationFailure(error);
      if (failure === "thread_missing") {
        cancelRename();
        await reconcileMissingThread(thread.id, token);
      } else {
        setRenameError(failure);
      }
    } finally {
      finishMutation(token);
    }
  }, [beginMutation, cancelRename, finishMutation, invalidateLoads, onThreadUpdated, reconcileMissingThread, reloadAfterMutation, renameDraft, replaceRow]);

  const changeArchive = useCallback(async (thread: ResearchThreadDTO) => {
    const token = beginMutation(thread.id);
    if (token === null) return;
    const archived = !thread.archived_at;
    setMutationError(null);
    try {
      const { thread: updated } = await updateResearchThread(thread.id, { archived });
      if (mutationOwnerRef.current !== token) return;
      invalidateLoads();
      removeRow(thread.id);
      if (deleteTarget?.id === thread.id) setDeleteTarget(null);
      onThreadUpdated(updated);
      await reloadAfterMutation(token, "refresh");
    } catch (error) {
      if (mutationOwnerRef.current !== token) return;
      const failure = mutationFailure(error);
      if (failure === "thread_missing") {
        if (deleteTarget?.id === thread.id) setDeleteTarget(null);
        await reconcileMissingThread(thread.id, token);
      } else {
        setMutationError(failure);
      }
    } finally {
      finishMutation(token);
    }
  }, [beginMutation, deleteTarget?.id, finishMutation, invalidateLoads, onThreadUpdated, reconcileMissingThread, reloadAfterMutation, removeRow]);

  const confirmDelete = useCallback(async () => {
    if (!deleteTarget) return;
    const target = deleteTarget;
    const token = beginMutation(target.id);
    if (token === null) return;
    setMutationError(null);
    try {
      await deleteResearchThread(target.id);
      if (mutationOwnerRef.current !== token) return;
      invalidateLoads();
      removeRow(target.id);
      setDeleteTarget(null);
      onThreadDeleted(target.id);
      await reloadAfterMutation(token, "refresh");
    } catch (error) {
      if (mutationOwnerRef.current !== token) return;
      const failure = mutationFailure(error);
      if (failure === "thread_missing") {
        setDeleteTarget(null);
        await reconcileMissingThread(target.id, token);
      } else {
        setMutationError(failure);
      }
    } finally {
      finishMutation(token);
    }
  }, [beginMutation, deleteTarget, finishMutation, invalidateLoads, onThreadDeleted, reconcileMissingThread, reloadAfterMutation, removeRow]);

  const activeIds = useMemo(() => activeRunIds, [activeRunIds]);
  const isActive = useCallback((thread: ResearchThreadDTO) => {
    const activeRun = thread.active_run;
    if (!activeRun) return false;
    return activeIds.has(activeRun.id)
      || activeRun.status === "queued"
      || activeRun.status === "running";
  }, [activeIds]);

  const mutationBusy = mutationId !== null;
  const currentQueryKey = useMemo(() => queryKeyFor(filters), [filters]);
  const hasMore = acceptedQueryKey === currentQueryKey && nextOffset < total;
  const statusLabel = `${rows.length} / ${total}`;
  const mutationErrorLabel = mutationError === null
    ? null
    : mutationError === "active_run_conflict"
      ? researchT(($) => $.history.activeMutationBlocked)
      : mutationError === "thread_missing"
        ? researchT(($) => $.workspace.threadNotFound)
        : researchT(($) => $.history.updateFailed);
  const renameErrorLabel = renameError === null
    ? null
    : renameError === "empty_name"
      ? researchT(($) => $.history.emptyName)
      : renameError === "active_run_conflict"
        ? researchT(($) => $.history.activeMutationBlocked)
        : renameError === "thread_missing"
          ? researchT(($) => $.workspace.threadNotFound)
          : researchT(($) => $.history.updateFailed);
  const deleteTargetTitle = deleteTarget?.title.trim()
    ? deleteTarget.title
    : researchT(($) => $.history.unnamedFallback);

  return (
    <>
      <Drawer
        open={open}
        title={researchT(($) => $.history.drawerTitle)}
        onClose={onClose}
        returnFocusRef={returnFocusRef}
        footer={(
          <div className="research-history-footer">
            <StatusBadge
              state={stale ? "stale" : rows.length ? "ready" : "empty"}
              label={statusLabel}
            />
            {hasMore ? (
              <Button
                size="compact"
                busy={appending}
                disabled={loading}
                onClick={() => void loadPage(filters, nextOffset, true)}
              >
                {researchT(($) => $.history.loadMore)}
              </Button>
            ) : null}
          </div>
        )}
      >
        <section
          className="research-history"
          aria-label={researchT(($) => $.history.listAria)}
        >
          <div className="research-history-toolbar">
            <div className="research-history-filters">
              <label className="research-history-search">
                <span>{researchT(($) => $.history.searchLabel)}</span>
                <input
                  type="search"
                  aria-label={researchT(($) => $.history.searchAria)}
                  value={filters.q}
                  onChange={(event) => updateFilter("q", event.currentTarget.value)}
                />
              </label>
              <label>
                <span>{researchT(($) => $.history.tickerLabel)}</span>
                <input
                  aria-label={researchT(($) => $.history.tickerFilterAria)}
                  value={filters.ticker}
                  onChange={(event) => updateFilter("ticker", event.currentTarget.value)}
                />
              </label>
              <label>
                <span>{researchT(($) => $.history.updatedFromLabel)}</span>
                <input
                  type="date"
                  aria-label={researchT(($) => $.history.updatedFromAria)}
                  value={filters.updatedFrom}
                  onChange={(event) => updateFilter("updatedFrom", event.currentTarget.value)}
                />
              </label>
              <label>
                <span>{researchT(($) => $.history.updatedToLabel)}</span>
                <input
                  type="date"
                  aria-label={researchT(($) => $.history.updatedToAria)}
                  value={filters.updatedThrough}
                  onChange={(event) => updateFilter("updatedThrough", event.currentTarget.value)}
                />
              </label>
              <label>
                <span>{researchT(($) => $.history.runStatusLabel)}</span>
                <select
                  aria-label={researchT(($) => $.history.runStatusFilterAria)}
                  value={filters.runState}
                  onChange={(event) => updateFilter(
                    "runState",
                    event.currentTarget.value as ResearchHistoryRunState,
                  )}
                >
                  <option value="all">{researchT(($) => $.history.allStatuses)}</option>
                  <option value="active">{researchT(($) => $.history.runningFilter)}</option>
                  <option value="succeeded">{researchT(($) => $.history.completedFilter)}</option>
                  <option value="failed">{researchT(($) => $.history.failedFilter)}</option>
                  <option value="interrupted">{researchT(($) => $.history.interruptedFilter)}</option>
                  <option value="no_run">{researchT(($) => $.history.noRunFilter)}</option>
                </select>
              </label>
              <label>
                <span>{researchT(($) => $.history.archiveStatusLabel)}</span>
                <select
                  aria-label={researchT(($) => $.history.archiveFilterAria)}
                  value={filters.archived}
                  onChange={(event) => updateFilter(
                    "archived",
                    event.currentTarget.value as ResearchHistoryArchiveMode,
                  )}
                >
                  <option value="current">{researchT(($) => $.history.currentThread)}</option>
                  <option value="archived">{researchT(($) => $.history.archivedFilter)}</option>
                </select>
              </label>
            </div>
            <IconButton
              ref={refreshButtonRef}
              label={researchT(($) => $.history.refreshAria)}
              tone="ghost"
              busy={loading}
              icon={<RefreshCw size={17} />}
              onClick={() => void loadPage(filters, 0, false)}
            />
          </div>

          {stale ? (
            <div className="research-history-notice" role="status">
              <StatusBadge
                state="stale"
                label={researchT(($) => $.history.staleDataTitle)}
              />
              <Button size="compact" onClick={() => void loadPage(filters, 0, false)}>
                {researchT(($) => $.history.retry)}
              </Button>
            </div>
          ) : null}
          {loadError && !stale ? (
            <div className="research-history-notice" role="alert">
              <StatusBadge
                state="failed"
                label={researchT(($) => $.history.loadFailedTitle)}
              />
              <Button size="compact" onClick={() => void loadPage(filters, 0, false)}>
                {researchT(($) => $.history.retry)}
              </Button>
            </div>
          ) : null}
          {mutationErrorLabel && !deleteTarget ? (
            <div className="research-history-notice" role="alert">
              <StatusBadge state="blocked" label={mutationErrorLabel} />
            </div>
          ) : null}

          {loading && rows.length === 0 ? (
            <div className="research-history-state">
              <StatusBadge
                state="loading"
                label={researchT(($) => $.history.loadingAria)}
              />
            </div>
          ) : rows.length === 0 && !loadError ? (
            <div className="research-history-state muted">
              {researchT(($) => $.history.emptyFiltered)}
            </div>
          ) : (
            <ul className="research-history-list">
              {rows.map((thread) => {
                const title = thread.title.trim()
                  ? thread.title
                  : researchT(($) => $.history.unnamedFallback);
                const active = isActive(thread);
                const busy = mutationId === thread.id;
                const status = researchHistoryStatus(
                  thread.latest_run_status ?? null,
                  researchT,
                );
                return (
                  <li
                    key={thread.id}
                    className={`research-history-row${thread.id === activeThreadId ? " active" : ""}`}
                    data-research-history-row={thread.id}
                  >
                    {renamingId === thread.id ? (
                      <div className="research-history-rename">
                        <label>
                          <span>{researchT(($) => $.history.conversationNameLabel)}</span>
                          <input
                            autoFocus
                            aria-label={researchT(($) => $.history.titleFilterAria)}
                            value={renameDraft}
                            disabled={mutationBusy}
                            onChange={(event) => {
                              setRenameDraft(event.currentTarget.value);
                              setRenameError(null);
                            }}
                            onKeyDown={(event) => {
                              if (mutationOwnerRef.current !== null) {
                                if (event.key === "Enter" || event.key === "Escape") {
                                  event.preventDefault();
                                  event.stopPropagation();
                                }
                                return;
                              }
                              if (event.key === "Enter") void saveRename(thread);
                              if (event.key === "Escape") {
                                event.preventDefault();
                                event.stopPropagation();
                                cancelRename(thread.id);
                              }
                            }}
                          />
                        </label>
                        <div className="research-history-rename-actions">
                          <Button
                            size="compact"
                            tone="primary"
                            busy={busy}
                            disabled={mutationBusy && !busy}
                            icon={<Check size={15} />}
                            onClick={() => void saveRename(thread)}
                          >
                            {researchT(($) => $.history.saveName)}
                          </Button>
                          <IconButton
                            label={researchT(($) => $.history.cancelRenameAria)}
                            size="compact"
                            tone="ghost"
                            icon={<X size={15} />}
                            disabled={mutationBusy}
                            onClick={() => cancelRename(thread.id)}
                          />
                        </div>
                        {renameErrorLabel
                          ? <p className="error-text tiny">{renameErrorLabel}</p>
                          : null}
                      </div>
                    ) : (
                      <>
                        <Button
                          ref={(node) => {
                            if (node) rowSelectRefs.current.set(thread.id, node);
                            else rowSelectRefs.current.delete(thread.id);
                          }}
                          tone="ghost"
                          className="research-history-select"
                          aria-label={researchT(($) => $.history.openThreadAria, { title })}
                          onClick={() => onSelect(thread)}
                        >
                          <span className="research-history-title">{title}</span>
                          <span className="research-history-summary">
                            {thread.ticker ? <span className="list-chip">{thread.ticker}</span> : null}
                            <StatusBadge state={status.state} label={status.label} />
                          </span>
                          <span className="research-history-times">
                            <time dateTime={thread.created_at}>
                              {researchT(($) => $.history.createdLabel)}{" "}
                              {formatLocalTime(thread.created_at)}
                            </time>
                            <time dateTime={thread.updated_at}>
                              {researchT(($) => $.history.updatedLabel)}{" "}
                              {formatLocalTime(thread.updated_at)}
                            </time>
                          </span>
                        </Button>
                        <div className="research-history-actions">
                          <IconButton
                            label={researchT(($) => $.history.renameThreadAria, { title })}
                            size="compact"
                            tone="ghost"
                            icon={<Pencil size={15} />}
                            disabled={mutationBusy}
                            onClick={() => beginRename(thread)}
                          />
                          <IconButton
                            label={researchT(($) => $.history.archiveToggleAria, {
                              action: thread.archived_at
                                ? researchT(($) => $.history.unarchiveAria)
                                : researchT(($) => $.history.archiveAria),
                              title,
                            })}
                            size="compact"
                            tone="ghost"
                            icon={thread.archived_at
                              ? <ArchiveRestore size={15} />
                              : <Archive size={15} />}
                            disabled={mutationBusy || active}
                            title={active
                              ? researchT(($) => $.history.activeThreadWarning)
                              : undefined}
                            onClick={() => void changeArchive(thread)}
                          />
                          <IconButton
                            label={researchT(($) => $.history.deleteThreadAria, { title })}
                            size="compact"
                            tone="danger"
                            icon={<Trash2 size={15} />}
                            disabled={mutationBusy || active}
                            title={active
                              ? researchT(($) => $.history.activeThreadWarning)
                              : undefined}
                            onClick={(event) => {
                              if (mutationOwnerRef.current !== null) return;
                              setDeleteReturnFocus(event.currentTarget);
                              setMutationError(null);
                              setDeleteTarget(thread);
                            }}
                          />
                        </div>
                      </>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      </Drawer>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title={researchT(($) => $.history.deleteDialogAria)}
        consequence={(
          <div className="research-history-delete-consequence">
            <span>{researchT(($) => $.history.deleteConsequence, {
              title: deleteTargetTitle,
            })}</span>
            {mutationErrorLabel
              ? <StatusBadge state="blocked" label={mutationErrorLabel} />
              : null}
          </div>
        )}
        confirmLabel={researchT(($) => $.history.deleteAction)}
        busy={mutationBusy}
        onConfirm={() => void confirmDelete()}
        onCancel={() => {
          if (mutationOwnerRef.current !== null) return;
          setDeleteTarget(null);
          setMutationError(null);
        }}
        returnFocusRef={deleteReturnFocusRef}
      />
    </>
  );
}
