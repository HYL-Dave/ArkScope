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

import {
  deleteResearchThread,
  queryResearchThreads,
  updateResearchThread,
  type ResearchHistoryArchiveMode,
  type ResearchHistoryRunState,
  type ResearchThreadDTO,
  type ResearchThreadQueryParams,
} from "./api";
import { Button, IconButton } from "./ui/Button";
import { ConfirmDialog } from "./ui/ConfirmDialog";
import { Drawer } from "./ui/Drawer";
import { StatusBadge, type CommonUiState } from "./ui/Status";

const PAGE_LIMIT = 50;

interface HistoryFilters {
  q: string;
  ticker: string;
  updatedFrom: string;
  updatedThrough: string;
  runState: ResearchHistoryRunState;
  archived: ResearchHistoryArchiveMode;
}

const INITIAL_FILTERS: HistoryFilters = {
  q: "",
  ticker: "",
  updatedFrom: "",
  updatedThrough: "",
  runState: "all",
  archived: "current",
};

export interface ResearchHistoryDrawerProps {
  open: boolean;
  onClose: () => void;
  activeThreadId: string | null;
  activeRunIds: ReadonlySet<string>;
  onInitialRowsReady: (rows: readonly ResearchThreadDTO[]) => void;
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

function runStatus(status: ResearchThreadDTO["latest_run_status"]): {
  state: CommonUiState;
  label: string;
} {
  switch (status) {
    case "queued": return { state: "running", label: "排程中" };
    case "running": return { state: "running", label: "執行中" };
    case "succeeded": return { state: "ready", label: "已完成" };
    case "failed": return { state: "failed", label: "失敗" };
    case "cancelled": return { state: "interrupted", label: "已取消" };
    case "interrupted": return { state: "interrupted", label: "已中斷" };
    default: return { state: "empty", label: "尚無執行" };
  }
}

function mutationErrorMessage(error: unknown): string {
  const detail = error instanceof Error ? error.message : String(error);
  if (/returned 409\b/.test(detail)) {
    return "仍有研究執行中，暫時無法封存或永久刪除。";
  }
  return detail || "更新研究歷史時發生錯誤。";
}

export function ResearchHistoryDrawer({
  open,
  onClose,
  activeThreadId,
  activeRunIds,
  onInitialRowsReady,
  onSelect,
  onThreadUpdated,
  onThreadDeleted,
  returnFocusRef,
}: ResearchHistoryDrawerProps) {
  const [filters, setFilters] = useState<HistoryFilters>(INITIAL_FILTERS);
  const [rows, setRows] = useState<ResearchThreadDTO[]>([]);
  const [total, setTotal] = useState(0);
  const [nextOffset, setNextOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [appending, setAppending] = useState(false);
  const [stale, setStale] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [mutationError, setMutationError] = useState<string | null>(null);
  const [mutationId, setMutationId] = useState<string | null>(null);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameDraft, setRenameDraft] = useState("");
  const [renameError, setRenameError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ResearchThreadDTO | null>(null);
  const [deleteReturnFocus, setDeleteReturnFocus] = useState<HTMLButtonElement | null>(null);

  const rowsRef = useRef<ResearchThreadDTO[]>([]);
  const requestSequenceRef = useRef(0);
  const initialRowsNotifiedRef = useRef(false);
  const initialRowsCallbackRef = useRef(onInitialRowsReady);
  initialRowsCallbackRef.current = onInitialRowsReady;
  const deleteReturnFocusRef = useMemo(
    () => ({ current: deleteReturnFocus }),
    [deleteReturnFocus],
  );

  const commitRows = useCallback((next: ResearchThreadDTO[]) => {
    rowsRef.current = next;
    setRows(next);
  }, []);

  const invalidateLoads = useCallback(() => {
    requestSequenceRef.current += 1;
    setLoading(false);
    setAppending(false);
  }, []);

  const loadPage = useCallback(async (
    requestedFilters: HistoryFilters,
    offset: number,
    append: boolean,
  ) => {
    const sequence = ++requestSequenceRef.current;
    if (append) setAppending(true);
    else {
      setAppending(false);
      setLoading(true);
    }
    setLoadError(null);
    try {
      const page = await queryResearchThreads(queryFor(requestedFilters, offset));
      if (sequence !== requestSequenceRef.current) return;
      const nextRows = append
        ? appendUnique(rowsRef.current, page.threads)
        : [...page.threads];
      commitRows(nextRows);
      setTotal(page.total);
      setNextOffset(page.offset + page.limit);
      setStale(false);
      if (!initialRowsNotifiedRef.current && page.offset === 0) {
        initialRowsNotifiedRef.current = true;
        initialRowsCallbackRef.current(page.threads);
      }
    } catch (error) {
      if (sequence !== requestSequenceRef.current) return;
      setLoadError(error instanceof Error ? error.message : String(error));
      setStale(rowsRef.current.length > 0);
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
    setRenamingId(thread.id);
    setRenameDraft(thread.title);
    setRenameError(null);
    setMutationError(null);
  }, []);

  const cancelRename = useCallback(() => {
    setRenamingId(null);
    setRenameDraft("");
    setRenameError(null);
  }, []);

  const saveRename = useCallback(async (thread: ResearchThreadDTO) => {
    const title = renameDraft.trim();
    if (!title) {
      setRenameError("名稱不可空白");
      return;
    }
    setMutationId(thread.id);
    setMutationError(null);
    setRenameError(null);
    try {
      const { thread: updated } = await updateResearchThread(thread.id, { title });
      invalidateLoads();
      replaceRow(updated);
      cancelRename();
      onThreadUpdated(updated);
    } catch (error) {
      setRenameError(mutationErrorMessage(error));
    } finally {
      setMutationId(null);
    }
  }, [cancelRename, invalidateLoads, onThreadUpdated, renameDraft, replaceRow]);

  const changeArchive = useCallback(async (thread: ResearchThreadDTO) => {
    const archived = !thread.archived_at;
    setMutationId(thread.id);
    setMutationError(null);
    try {
      const { thread: updated } = await updateResearchThread(thread.id, { archived });
      invalidateLoads();
      removeRow(thread.id);
      if (deleteTarget?.id === thread.id) setDeleteTarget(null);
      onThreadUpdated(updated);
    } catch (error) {
      setMutationError(mutationErrorMessage(error));
    } finally {
      setMutationId(null);
    }
  }, [deleteTarget?.id, invalidateLoads, onThreadUpdated, removeRow]);

  const confirmDelete = useCallback(async () => {
    if (!deleteTarget) return;
    setMutationId(deleteTarget.id);
    setMutationError(null);
    try {
      await deleteResearchThread(deleteTarget.id);
      const deletedId = deleteTarget.id;
      invalidateLoads();
      removeRow(deletedId);
      setDeleteTarget(null);
      onThreadDeleted(deletedId);
    } catch (error) {
      setMutationError(mutationErrorMessage(error));
    } finally {
      setMutationId(null);
    }
  }, [deleteTarget, invalidateLoads, onThreadDeleted, removeRow]);

  const activeIds = useMemo(() => activeRunIds, [activeRunIds]);
  const isActive = useCallback((thread: ResearchThreadDTO) => {
    const activeRun = thread.active_run;
    if (!activeRun) return false;
    return activeIds.has(activeRun.id)
      || activeRun.status === "queued"
      || activeRun.status === "running";
  }, [activeIds]);

  const hasMore = nextOffset < total;
  const statusLabel = `${rows.length} / ${total}`;

  return (
    <>
      <Drawer
        open={open}
        title="研究歷史"
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
                載入更多
              </Button>
            ) : null}
          </div>
        )}
      >
        <section className="research-history" aria-label="研究歷史清單">
          <div className="research-history-toolbar">
            <div className="research-history-filters">
              <label className="research-history-search">
                <span>搜尋</span>
                <input
                  type="search"
                  aria-label="搜尋歷史"
                  value={filters.q}
                  onChange={(event) => updateFilter("q", event.currentTarget.value)}
                />
              </label>
              <label>
                <span>Ticker</span>
                <input
                  aria-label="Ticker"
                  value={filters.ticker}
                  onChange={(event) => updateFilter("ticker", event.currentTarget.value)}
                />
              </label>
              <label>
                <span>更新日期起日</span>
                <input
                  type="date"
                  aria-label="更新日期起日"
                  value={filters.updatedFrom}
                  onChange={(event) => updateFilter("updatedFrom", event.currentTarget.value)}
                />
              </label>
              <label>
                <span>更新日期迄日</span>
                <input
                  type="date"
                  aria-label="更新日期迄日"
                  value={filters.updatedThrough}
                  onChange={(event) => updateFilter("updatedThrough", event.currentTarget.value)}
                />
              </label>
              <label>
                <span>執行狀態</span>
                <select
                  aria-label="執行狀態"
                  value={filters.runState}
                  onChange={(event) => updateFilter(
                    "runState",
                    event.currentTarget.value as ResearchHistoryRunState,
                  )}
                >
                  <option value="all">全部狀態</option>
                  <option value="active">執行中</option>
                  <option value="succeeded">已完成</option>
                  <option value="failed">失敗</option>
                  <option value="interrupted">已中斷</option>
                  <option value="no_run">尚無執行</option>
                </select>
              </label>
              <label>
                <span>封存狀態</span>
                <select
                  aria-label="封存狀態"
                  value={filters.archived}
                  onChange={(event) => updateFilter(
                    "archived",
                    event.currentTarget.value as ResearchHistoryArchiveMode,
                  )}
                >
                  <option value="current">目前對話</option>
                  <option value="archived">已封存</option>
                </select>
              </label>
            </div>
            <IconButton
              label="重新整理歷史"
              tone="ghost"
              busy={loading}
              icon={<RefreshCw size={17} />}
              onClick={() => void loadPage(filters, 0, false)}
            />
          </div>

          {stale ? (
            <div className="research-history-notice" role="status">
              <StatusBadge state="stale" label="資料可能已過期" />
              <Button size="compact" onClick={() => void loadPage(filters, 0, false)}>
                重試
              </Button>
            </div>
          ) : null}
          {loadError && !stale ? (
            <div className="research-history-notice" role="alert">
              <StatusBadge state="failed" label="無法載入研究歷史" />
              <Button size="compact" onClick={() => void loadPage(filters, 0, false)}>
                重試
              </Button>
            </div>
          ) : null}
          {mutationError && !deleteTarget ? (
            <div className="research-history-notice" role="alert">
              <StatusBadge state="blocked" label={mutationError} />
            </div>
          ) : null}

          {loading && rows.length === 0 ? (
            <div className="research-history-state">
              <StatusBadge state="loading" label="載入研究歷史" />
            </div>
          ) : rows.length === 0 && !loadError ? (
            <div className="research-history-state muted">找不到符合條件的對話</div>
          ) : (
            <ul className="research-history-list">
              {rows.map((thread) => {
                const title = thread.title.trim() || "（未命名）";
                const active = isActive(thread);
                const busy = mutationId === thread.id;
                const status = runStatus(thread.latest_run_status);
                return (
                  <li
                    key={thread.id}
                    className={`research-history-row${thread.id === activeThreadId ? " active" : ""}`}
                    data-research-history-row={thread.id}
                  >
                    {renamingId === thread.id ? (
                      <div className="research-history-rename">
                        <label>
                          <span>對話名稱</span>
                          <input
                            autoFocus
                            aria-label="對話名稱"
                            value={renameDraft}
                            onChange={(event) => {
                              setRenameDraft(event.currentTarget.value);
                              setRenameError(null);
                            }}
                            onKeyDown={(event) => {
                              if (event.key === "Enter") void saveRename(thread);
                              if (event.key === "Escape") cancelRename();
                            }}
                          />
                        </label>
                        <div className="research-history-rename-actions">
                          <Button
                            size="compact"
                            tone="primary"
                            busy={busy}
                            icon={<Check size={15} />}
                            onClick={() => void saveRename(thread)}
                          >
                            儲存名稱
                          </Button>
                          <IconButton
                            label="取消重新命名"
                            size="compact"
                            tone="ghost"
                            icon={<X size={15} />}
                            disabled={busy}
                            onClick={cancelRename}
                          />
                        </div>
                        {renameError ? <p className="error-text tiny">{renameError}</p> : null}
                      </div>
                    ) : (
                      <>
                        <Button
                          tone="ghost"
                          className="research-history-select"
                          aria-label={`開啟對話 ${title}`}
                          onClick={() => onSelect(thread)}
                        >
                          <span className="research-history-title">{title}</span>
                          <span className="research-history-summary">
                            {thread.ticker ? <span className="list-chip">{thread.ticker}</span> : null}
                            <StatusBadge state={status.state} label={status.label} />
                          </span>
                          <span className="research-history-times">
                            <time dateTime={thread.created_at}>
                              建立 {formatLocalTime(thread.created_at)}
                            </time>
                            <time dateTime={thread.updated_at}>
                              更新 {formatLocalTime(thread.updated_at)}
                            </time>
                          </span>
                        </Button>
                        <div className="research-history-actions">
                          <IconButton
                            label={`重新命名 ${title}`}
                            size="compact"
                            tone="ghost"
                            icon={<Pencil size={15} />}
                            disabled={busy}
                            onClick={() => beginRename(thread)}
                          />
                          <IconButton
                            label={`${thread.archived_at ? "取消封存" : "封存"} ${title}`}
                            size="compact"
                            tone="ghost"
                            icon={thread.archived_at
                              ? <ArchiveRestore size={15} />
                              : <Archive size={15} />}
                            disabled={busy || active}
                            title={active ? "這個對話仍在執行中" : undefined}
                            onClick={() => void changeArchive(thread)}
                          />
                          <IconButton
                            label={`永久刪除 ${title}`}
                            size="compact"
                            tone="danger"
                            icon={<Trash2 size={15} />}
                            disabled={busy || active}
                            title={active ? "這個對話仍在執行中" : undefined}
                            onClick={(event) => {
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
        title="永久刪除對話"
        consequence={(
          <div className="research-history-delete-consequence">
            <span>
              「{deleteTarget?.title || "（未命名）"}」的訊息與研究執行紀錄將永久刪除。
            </span>
            {mutationError ? <StatusBadge state="blocked" label={mutationError} /> : null}
          </div>
        )}
        confirmLabel="永久刪除"
        busy={Boolean(deleteTarget && mutationId === deleteTarget.id)}
        onConfirm={() => void confirmDelete()}
        onCancel={() => {
          if (mutationId) return;
          setDeleteTarget(null);
          setMutationError(null);
        }}
        returnFocusRef={deleteReturnFocusRef}
      />
    </>
  );
}
