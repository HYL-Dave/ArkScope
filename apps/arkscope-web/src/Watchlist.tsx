import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  addMember,
  createList,
  deleteList,
  getConsensus,
  getDefaultWatchlist,
  getProfileLists,
  getUniverse,
  removeMember,
  renameList,
  searchSymbols,
  setArchived,
  setDefaultWatchlist,
  setPriority,
  type ConsensusSummary,
  type SymbolHit,
  type TagRef,
  type UniverseRow,
  type WatchlistSummary,
} from "./api";
import { ExploreErrorNotice } from "./explore/ExploreErrorNotice";
import {
  captureExploreError,
  type ExploreErrorState,
  type ExploreT,
} from "./explore/explorePresentation";
import type { NavigationTarget } from "./shell/navigation";
import { TagChips } from "./tags";

// One normalized row the table renders. The single source is the universe
// (profile-state substrate); the aggregate view is the union of active
// memberships across app-created custom lists, not legacy config imports.
interface TabRow {
  ticker: string;
  latest_close: number | null;
  change_7d_pct: number | null;
  news_count_7d: number;
  priority: string;
  archived: boolean;
  note_count: number;
  has_summary: boolean;
  tags: TagRef[];
}

type SortKey = "ticker" | "latest_close" | "change_7d_pct" | "news_count_7d" | "priority";
type SortDir = "asc" | "desc";
type Priority = "high" | "medium" | "low";
type ConsensusCell =
  | { state: "loading" }
  | { state: "err" }
  | { state: "ok"; data: ConsensusSummary };
type UniverseLoadOptions = {
  clearError?: boolean;
  reportError?: boolean;
};

const PRIORITY_RANK: Record<string, number> = { high: 3, medium: 2, low: 1 };

function universeToTab(r: UniverseRow): TabRow {
  return {
    ticker: r.ticker,
    latest_close: r.latest_close,
    change_7d_pct: r.change_7d_pct,
    news_count_7d: r.news_count_7d,
    priority: r.priority ?? "",
    archived: r.archived,
    note_count: r.note_count,
    has_summary: r.has_summary,
    tags: r.tags ?? [],
  };
}

export function WatchlistView({
  onOpenTicker,
  developerMode,
  onNavigateTarget,
}: {
  onOpenTicker: (ticker: string) => void;
  developerMode: boolean;
  onNavigateTarget: (target: NavigationTarget) => void;
}) {
  const { t } = useTranslation("explore");
  const [lists, setLists] = useState<WatchlistSummary[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null); // null = all custom lists
  const [defaultListId, setDefaultListId] = useState<number | null>(null);
  const initialized = useRef(false); // landing-list selection happens once
  const [showArchived, setShowArchived] = useState(false);
  const [sortKey, setSortKey] = useState<SortKey>("change_7d_pct");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [refreshing, setRefreshing] = useState(false);
  const [err, setErr] = useState<ExploreErrorState | null>(null);
  const [busyTicker, setBusyTicker] = useState<string | null>(null);

  // Single cached source: the universe (all imported tickers + their membership
  // & market summary). Tab + showArchived + sort are pure client-side derivation.
  const [universe, setUniverse] = useState<{ rows: UniverseRow[]; asOf: string | null } | null>(null);
  const universeReq = useRef(0);

  // Rail editing + add-ticker state
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [renamingId, setRenamingId] = useState<number | null>(null);
  const [renameName, setRenameName] = useState("");
  const [addQuery, setAddQuery] = useState("");
  const [addResults, setAddResults] = useState<SymbolHit[] | null>(null);
  const [addBusy, setAddBusy] = useState(false);
  const searchReq = useRef(0);

  const loadLists = useCallback(async () => {
    try {
      const [listsRes, def] = await Promise.all([getProfileLists(false), getDefaultWatchlist()]);
      setLists(listsRes.lists);
      setDefaultListId(def.default_watchlist_id);
      // First load only: land on the default list (else the first custom list,
      // else the All-Active view). Later reloads must NOT override the user's
      // current selection (e.g. when they click All Active).
      if (!initialized.current) {
        initialized.current = true;
        const custom = listsRes.lists.filter((l) => l.kind === "custom");
        const def_id = def.default_watchlist_id;
        const target =
          def_id != null && custom.some((l) => l.id === def_id)
            ? def_id
            : custom[0]?.id ?? null;
        setSelectedId(target);
      }
    } catch {
      /* rail degrades to the aggregate custom-list view only */
    }
  }, []);

  const onSetDefault = useCallback(async (listId: number) => {
    // Toggle: pin this list as default, or clear if it already is.
    const next = defaultListId === listId ? null : listId;
    setDefaultListId(next); // optimistic
    try {
      await setDefaultWatchlist(next);
    } catch {
      setDefaultListId(defaultListId); // revert on failure
    }
  }, [defaultListId]);

  const loadUniverse = useCallback(async ({
    clearError = true,
    reportError = true,
  }: UniverseLoadOptions = {}) => {
    const id = ++universeReq.current;
    setRefreshing(true);
    if (clearError) setErr(null);
    try {
      const u = await getUniverse(true);
      if (id === universeReq.current) setUniverse({ rows: u.rows, asOf: u.as_of });
    } catch (e) {
      if (id === universeReq.current && reportError) {
        setErr(captureExploreError("watchlist_load_universe", e));
      }
    } finally {
      if (id === universeReq.current) setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void loadLists();
    void loadUniverse();
  }, [loadLists, loadUniverse]);

  // 自選股 = app-created custom lists only. Imported legacy groups from
  // user_profile.yaml and tickers_core tier inventory belong to 全部標的 as seed
  // material; otherwise old visual/reference config keeps polluting the app UI.
  const railLists = useMemo(() => lists.filter((l) => l.kind === "custom"), [lists]);
  const watchlistNames = useMemo(() => new Set(railLists.map((l) => l.name)), [railLists]);
  const selectedList = selectedId === null ? null : railLists.find((l) => l.id === selectedId) ?? null;
  // If the selected list vanished, was deleted, or is a hidden tier inventory
  // list, fall back to the visible aggregate.
  useEffect(() => {
    if (selectedId !== null && lists.length && !railLists.some((l) => l.id === selectedId)) {
      setSelectedId(null);
    }
  }, [lists.length, railLists, selectedId]);

  // Debounced symbol search for the add-ticker box (stale responses dropped).
  useEffect(() => {
    const q = addQuery.trim();
    if (!q) { setAddResults(null); return; }
    const id = ++searchReq.current;
    const t = window.setTimeout(async () => {
      try {
        const r = await searchSymbols(q, 8);
        if (id === searchReq.current) setAddResults(r.results);
      } catch {
        if (id === searchReq.current) setAddResults([]);
      }
    }, 200);
    return () => window.clearTimeout(t);
  }, [addQuery]);

  // Rows are derived from the universe. 全部清單 = rows with >=1 active custom
  // list membership (or any custom membership when showing archived). Legacy
  // imported inventory stays visible in 全部標的, not in this daily work list.
  const { rows, asOf } = useMemo<{ rows: TabRow[]; asOf: string | null }>(() => {
    const src = universe?.rows ?? [];
    const asOfVal = universe?.asOf ?? null;
    if (selectedList === null) {
      // union of active members across app-created custom lists only
      return {
        rows: src
          .filter((r) => (showArchived ? r.all_lists : r.lists).some((n) => watchlistNames.has(n)))
          .map(universeToTab),
        asOf: asOfVal,
      };
    }
    return {
      rows: src
        .filter((r) => (showArchived ? r.all_lists : r.lists).includes(selectedList.name))
        .map(universeToTab),
      asOf: asOfVal,
    };
  }, [selectedList, showArchived, universe, watchlistNames]);

  const isLoading = universe === null;
  // Archived-in-this-view count, computed from the universe (not the filtered
  // rows) so "· N archived" shows even while archived rows are hidden — making
  // the Show-archived toggle discoverable.
  const archivedCount = useMemo(() => {
    const src = universe?.rows ?? [];
    if (selectedList === null)
      return src.filter((r) => r.archived && r.all_lists.some((n) => watchlistNames.has(n))).length;
    return src.filter((r) => r.archived_lists.includes(selectedList.name)).length;
  }, [universe, selectedList, watchlistNames]);
  const sorted = useMemo(() => sortRows(rows, sortKey, sortDir), [rows, sortKey, sortDir]);

  // Analyst consensus, lazy per visible row + daily-cached server-side. Fetched
  // with bounded concurrency (Finnhub is throttled); each ticker requested once
  // per session. Replaces the old ArkScope LLM "sentiment" column.
  const [consensus, setConsensus] = useState<Record<string, ConsensusCell>>({});
  const consensusRequested = useRef<Set<string>>(new Set());
  // Membership-stable key: a pure re-sort or an optimistic priority patch must
  // NOT tear down in-flight consensus fetches (that orphaned cells on "…"
  // forever). The key changes only when the SET of visible tickers changes.
  const visibleKey = useMemo(
    () => Array.from(new Set(sorted.map((r) => r.ticker))).sort().join(","),
    [sorted],
  );
  useEffect(() => {
    const visible = visibleKey ? visibleKey.split(",") : [];
    const todo = visible.filter((t) => !consensusRequested.current.has(t));
    if (todo.length === 0) return;
    let cancelled = false;
    const completed = new Set<string>();
    todo.forEach((t) => consensusRequested.current.add(t));
    setConsensus((prev) => {
      const next = { ...prev };
      todo.forEach((t) => (next[t] = { state: "loading" }));
      return next;
    });
    (async () => {
      let i = 0;
      const worker = async () => {
        while (i < todo.length && !cancelled) {
          const t = todo[i++];
          try {
            const c = await getConsensus(t);
            completed.add(t);
            if (!cancelled) setConsensus((p) => ({ ...p, [t]: { state: "ok", data: c } }));
          } catch {
            completed.add(t);
            if (!cancelled) setConsensus((p) => ({ ...p, [t]: { state: "err" } }));
          }
        }
      };
      await Promise.all([worker(), worker(), worker()]); // concurrency 3
    })();
    return () => {
      cancelled = true;
      // Roll back tickers that never resolved so a genuine membership change
      // re-fetches them instead of stranding them on "…".
      todo.forEach((t) => {
        if (!completed.has(t)) consensusRequested.current.delete(t);
      });
    };
  }, [visibleKey]);

  function toggleSort(k: SortKey) {
    if (k === sortKey) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setSortKey(k); setSortDir(k === "ticker" || k === "priority" ? "asc" : "desc"); }
  }

  const reloadAfterMutation = useCallback(async () => {
    // Errored consensus cells can be re-fetched (the server never caches a
    // failure) — drop them so the lazy effect retries on this reload.
    setConsensus((prev) => {
      let changed = false;
      const next = { ...prev };
      for (const t of Object.keys(next)) {
        if (next[t].state === "err") {
          delete next[t];
          consensusRequested.current.delete(t);
          changed = true;
        }
      }
      return changed ? next : prev;
    });
    await loadUniverse();
    void loadLists();
  }, [loadUniverse, loadLists]);

  const onArchiveToggle = useCallback(
    async (row: TabRow) => {
      setBusyTicker(row.ticker);
      setErr(null);
      try {
        await setArchived(row.ticker, !row.archived); // GLOBAL archive (all lists)
        await reloadAfterMutation();
      } catch (e) {
        setErr(captureExploreError("watchlist_set_archived", e));
      }
      finally { setBusyTicker(null); }
    },
    [reloadAfterMutation],
  );

  const onRemoveFromList = useCallback(
    async (row: TabRow) => {
      if (!selectedList) return;
      setBusyTicker(row.ticker);
      setErr(null);
      try {
        await removeMember(selectedList.id, row.ticker); // THIS list only
        await reloadAfterMutation();
      } catch (e) {
        setErr(captureExploreError("watchlist_remove_member", e));
      }
      finally { setBusyTicker(null); }
    },
    [selectedList, reloadAfterMutation],
  );

  const onSetPriority = useCallback(
    async (ticker: string, priority: Priority | null) => {
      // optimistic: patch the cached universe row so sort/display update at once
      setUniverse((prev) =>
        prev ? { ...prev, rows: prev.rows.map((r) => (r.ticker === ticker ? { ...r, priority } : r)) } : prev,
      );
      try {
        await setPriority(ticker, priority);
        // Clearing reverts to the profile-derived priority (user ?? profile), so
        // the optimistic null would otherwise flip back on a later refresh —
        // reconcile now to the server's effective value.
        if (priority === null) void loadUniverse();
      } catch (e) {
        setErr(captureExploreError("watchlist_set_priority", e));
        void loadUniverse({ clearError: false, reportError: false });
      }
    },
    [loadUniverse],
  );

  async function submitNewList() {
    const name = newName.trim();
    if (!name) return;
    setErr(null);
    try {
      // Force kind="custom" — else the backend infers kind from the name
      // (_infer_kind: "holdings"/"interest"/"theme"/colon) and a reserved-name
      // list would land non-custom and vanish from this custom-only rail.
      const li = await createList(name, "custom");
      setCreating(false);
      setNewName("");
      await loadLists();
      setSelectedId(li.id);
    } catch (e) {
      setErr(captureExploreError("watchlist_create_list", e));
    }
  }

  async function submitRename(id: number) {
    const name = renameName.trim();
    if (!name) { setRenamingId(null); return; }
    setErr(null);
    try {
      await renameList(id, name);
      setRenamingId(null);
      await reloadAfterMutation(); // membership names in cached rows update too
    } catch (e) {
      setErr(captureExploreError("watchlist_rename_list", e));
    }
  }

  async function onDeleteList(li: WatchlistSummary) {
    const ok = window.confirm(t(($) => $.watchlist.deleteConfirmation, { listName: li.name }));
    if (!ok) return;
    setErr(null);
    try {
      await deleteList(li.id);
      if (selectedId === li.id) setSelectedId(null);
      await reloadAfterMutation();
    } catch (e) {
      setErr(captureExploreError("watchlist_delete_list", e));
    }
  }

  async function onAddSymbol(ticker: string) {
    if (!selectedList || addBusy) return;
    setAddBusy(true);
    setErr(null);
    try {
      await addMember(selectedList.id, ticker); // idempotent server-side
      setAddQuery("");
      setAddResults(null);
      await reloadAfterMutation();
    } catch (e) {
      setErr(captureExploreError("watchlist_add_member", e));
    }
    finally { setAddBusy(false); }
  }

  const thProps = { sortKey, sortDir, toggleSort };
  const title = selectedList === null
    ? t(($) => $.watchlist.allListsRuntime)
    : selectedList.name;
  const universeCount = universe?.rows.length ?? null;
  const normQuery = addQuery.trim().toUpperCase();

  return (
    <main className="main">
      <div className="surface-head">
        <h2 className="surface-title">{t(($) => $.watchlist.title)}</h2>
        <span className="muted">
          {title} · {rows.length === 1
            ? t(($) => $.watchlist.renderedTickerCount.one, { count: rows.length })
            : t(($) => $.watchlist.renderedTickerCount.other, { count: rows.length })}
          {selectedList === null && (
            <> {railLists.length === 1
              ? t(($) => $.watchlist.customListCount.one, { count: railLists.length })
              : t(($) => $.watchlist.customListCount.other, { count: railLists.length })}</>
          )}
          {selectedList === null && universeCount !== null && (
            <> {t(($) => $.watchlist.universeCount, { count: universeCount })}</>
          )}
          {archivedCount > 0 && (
            <> {t(($) => $.watchlist.archivedCount, { count: archivedCount })}</>
          )}
          {asOf && <> {t(($) => $.watchlist.asOf, { value: asOf })}</>}
        </span>
        <span className="spacer" />
        {err && <span className="refresh-err">{t(($) => $.watchlist.error)}</span>}
        <button className={`btn-ghost ${showArchived ? "on" : ""}`} onClick={() => setShowArchived((v) => !v)}>
          {showArchived
            ? t(($) => $.watchlist.archivedBadge)
            : t(($) => $.watchlist.showArchived)}
        </button>
        <button className="btn-ghost" onClick={() => void reloadAfterMutation()} disabled={refreshing}>
          {refreshing ? "↻ …" : t(($) => $.watchlist.refresh)}
        </button>
      </div>

      {err && (
        <ExploreErrorNotice
          state={err}
          developerMode={developerMode}
          retryLabel={t(($) => $.watchlist.refresh)}
          onRetry={() => void reloadAfterMutation()}
          onNavigate={err.code === "active_universe_unavailable"
            ? onNavigateTarget
            : undefined}
        />
      )}

      <div className="wl-layout">
        <aside className="wl-rail">
          <button
            className={`wl-railitem ${selectedId === null ? "active" : ""}`}
            onClick={() => setSelectedId(null)}
            title={t(($) => $.watchlist.allListsDescription)}
          >
            {t(($) => $.watchlist.allLists)}
          </button>
          {railLists.map((li) =>
            renamingId === li.id ? (
              <div key={li.id} className="wl-railedit">
                <input
                  className="wl-railinput"
                  autoFocus
                  value={renameName}
                  onChange={(e) => setRenameName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") void submitRename(li.id);
                    if (e.key === "Escape") setRenamingId(null);
                  }}
                />
                <button className="wl-railbtn" onClick={() => void submitRename(li.id)}>✓</button>
                <button className="wl-railbtn" onClick={() => setRenamingId(null)}>✕</button>
              </div>
            ) : (
              <div key={li.id} className={`wl-railitem ${selectedId === li.id ? "active" : ""}`}>
                <button
                  className="wl-railname"
                  onClick={() => setSelectedId(li.id)}
                  title={t(($) => $.watchlist.listSummary, {
                    kind: li.kind,
                    count: li.active_count,
                  })}
                >
                  {li.name} <span className="wl-railcount">{li.active_count}</span>
                </button>
                <button
                  className={`wl-railbtn wl-raildefault ${defaultListId === li.id ? "on" : ""}`}
                  title={defaultListId === li.id
                    ? t(($) => $.watchlist.currentDefaultList)
                    : t(($) => $.watchlist.setDefaultList)}
                  onClick={() => void onSetDefault(li.id)}
                >
                  {defaultListId === li.id ? "★" : "☆"}
                </button>
                <button className="wl-railbtn" title={t(($) => $.watchlist.rename)} onClick={() => { setRenamingId(li.id); setRenameName(li.name); }}>✎</button>
                <button className="wl-railbtn" title={t(($) => $.watchlist.deleteList)} onClick={() => void onDeleteList(li)}>🗑</button>
              </div>
            ),
          )}
          {creating ? (
            <div className="wl-railedit">
              <input
                className="wl-railinput"
                autoFocus
                placeholder={t(($) => $.watchlist.listNamePlaceholder)}
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") void submitNewList();
                  if (e.key === "Escape") { setCreating(false); setNewName(""); }
                }}
              />
              <button className="wl-railbtn" onClick={() => void submitNewList()}>✓</button>
              <button className="wl-railbtn" onClick={() => { setCreating(false); setNewName(""); }}>✕</button>
            </div>
          ) : (
            <button className="wl-railadd" onClick={() => setCreating(true)}>
              {t(($) => $.watchlist.addList)}
            </button>
          )}
        </aside>

        <div className="wl-content">
          {selectedList && (
            <div className="wl-addbox">
              <input
                className="aicard-q"
                placeholder={t(($) => $.watchlist.addMemberPlaceholder, {
                  listName: selectedList.name,
                })}
                value={addQuery}
                onChange={(e) => setAddQuery(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && normQuery) void onAddSymbol(normQuery); }}
                disabled={addBusy}
              />
              {addQuery.trim() && (
                <div className="wl-addresults">
                  {addResults === null ? (
                    <div className="muted tiny wl-addhint">
                      {t(($) => $.watchlist.searching)}
                    </div>
                  ) : (
                    <>
                      {addResults.map((h) => (
                        <button key={h.ticker} className="wl-addrow" disabled={addBusy} onClick={() => void onAddSymbol(h.ticker)}>
                          <span className="mono strong">{h.ticker}</span>
                          <span className="wl-addname">{h.name}</span>
                          {h.tracked && (
                            <span className="muted tiny">{t(($) => $.watchlist.tracked)}</span>
                          )}
                        </button>
                      ))}
                      {addResults.length === 0 && (
                        <div className="muted tiny wl-addhint">
                          {t(($) => $.watchlist.noMatches)}
                        </div>
                      )}
                      <button className="wl-addrow wl-adddirect" disabled={addBusy} onClick={() => void onAddSymbol(normQuery)}>
                        {t(($) => $.watchlist.directAddTicker)}{" "}
                        <span className="mono strong">{normQuery}</span>
                      </button>
                    </>
                  )}
                </div>
              )}
            </div>
          )}

          {isLoading ? (
            <p className="muted">{t(($) => $.watchlist.loading)}</p>
          ) : sorted.length === 0 ? (
            <EmptyState
              selectedList={selectedList}
              hasLists={railLists.length > 0}
              showArchived={showArchived}
              onCreate={() => setCreating(true)}
              t={t}
            />
          ) : (
            <>
              <table className="wl">
                <thead>
                  <tr>
                    <Th k="ticker" label={t(($) => $.watchlist.ticker)} {...thProps} />
                    <Th k="latest_close" label={t(($) => $.watchlist.price)} num {...thProps} />
                    <Th k="change_7d_pct" label={t(($) => $.watchlist.change7d)} num {...thProps} />
                    <Th k="news_count_7d" label={t(($) => $.watchlist.news)} num {...thProps} />
                    <th className="wl-consensus" title={t(($) => $.watchlist.consensusTitle)}>
                      {t(($) => $.watchlist.consensus)}
                    </th>
                    <Th k="priority" label={t(($) => $.watchlist.priority)} {...thProps} />
                    <th>{t(($) => $.watchlist.tags)}</th>
                    <th className="wl-actions">{t(($) => $.watchlist.actions)}</th>
                  </tr>
                </thead>
                <tbody>
                  {sorted.map((r) => (
                    <tr
                      key={r.ticker}
                      className={`${r.archived ? "archived" : ""} ${r.has_summary ? "" : "no-summary"}`}
                      onClick={() => onOpenTicker(r.ticker)}
                    >
                      <td className="mono strong">
                        {r.ticker}
                        {!r.has_summary && (
                          <span className="tag-nosum" title={t(($) => $.watchlist.noMarketSummary)}>
                            {t(($) => $.watchlist.noSummary)}
                          </span>
                        )}
                        {r.archived && (
                          <span className="tag-archived">{t(($) => $.watchlist.archived)}</span>
                        )}
                        {r.note_count > 0 && (
                          <span
                            className="note-dot"
                            title={r.note_count === 1
                              ? t(($) => $.watchlist.noteCount.one, { count: r.note_count })
                              : t(($) => $.watchlist.noteCount.other, { count: r.note_count })}
                          >
                            ✎{r.note_count}
                          </span>
                        )}
                      </td>
                      <td className="num">{fmtNum(r.latest_close)}</td>
                      <td className={`num ${changeClass(r.change_7d_pct)}`}>{fmtPct(r.change_7d_pct)}</td>
                      <td className="num">{r.news_count_7d}</td>
                      <td className="wl-consensus">{renderConsensus(consensus[r.ticker], t)}</td>
                      <td onClick={(e) => e.stopPropagation()}>
                        <select
                          className={`prio-select p-${r.priority || "none"}`}
                          value={r.priority}
                          onChange={(e) => void onSetPriority(r.ticker, (e.target.value || null) as Priority | null)}
                          title={t(($) => $.watchlist.setPriority)}
                        >
                          <option value="">—</option>
                          <option value="high">{t(($) => $.watchlist.high)}</option>
                          <option value="medium">{t(($) => $.watchlist.medium)}</option>
                          <option value="low">{t(($) => $.watchlist.low)}</option>
                        </select>
                      </td>
                      <td><TagChips tags={r.tags} t={t} max={4} /></td>
                      <td className="wl-actions" onClick={(e) => e.stopPropagation()}>
                        <span className="rowactions">
                          <button type="button" title={t(($) => $.watchlist.openDetail)} onClick={() => onOpenTicker(r.ticker)}>↗</button>
                          {selectedList && (
                            <button
                              type="button"
                              title={t(($) => $.watchlist.removeFromList, {
                                listName: selectedList.name,
                              })}
                              disabled={busyTicker === r.ticker}
                              onClick={() => void onRemoveFromList(r)}
                            >
                              {busyTicker === r.ticker ? "…" : "✕"}
                            </button>
                          )}
                          <button
                            type="button"
                            title={r.archived
                              ? t(($) => $.watchlist.restoreGlobal)
                              : t(($) => $.watchlist.archiveGlobal)}
                            disabled={busyTicker === r.ticker}
                            onClick={() => void onArchiveToggle(r)}
                          >
                            {busyTicker === r.ticker ? "…" : r.archived ? "↩" : "🗄"}
                          </button>
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="muted tiny">
                {t(($) => $.watchlist.openDetailAction)}{" "}
                {selectedList ? <>{t(($) => $.watchlist.removeFromListAction)} </> : ""}
                {t(($) => $.watchlist.globalArchiveHint)}
                {selectedList === null && <> {t(($) => $.watchlist.allListsExplanation)}</>}
              </p>
            </>
          )}
        </div>
      </div>
    </main>
  );
}

function EmptyState({
  selectedList,
  hasLists,
  showArchived,
  onCreate,
  t,
}: {
  selectedList: WatchlistSummary | null;
  hasLists: boolean;
  showArchived: boolean;
  onCreate: () => void;
  t: ExploreT;
}) {
  if (selectedList) {
    return (
      <p className="muted tiny">
        {showArchived
          ? t(($) => $.watchlist.emptyListWithoutArchivedHint)
          : t(($) => $.watchlist.emptyListWithArchivedHint)}
      </p>
    );
  }
  if (!hasLists) {
    return (
      <div className="wl-empty">
        <p className="muted">{t(($) => $.watchlist.noLists)}</p>
        <p className="muted tiny">
          {t(($) => $.watchlist.firstList)}
        </p>
        <button className="btn-ghost" onClick={onCreate}>
          {t(($) => $.watchlist.addList)}
        </button>
      </div>
    );
  }
  return (
    <p className="muted tiny">
      {showArchived
        ? t(($) => $.watchlist.emptyActiveListWithoutArchivedHint)
        : t(($) => $.watchlist.emptyActiveListWithArchivedHint)}
    </p>
  );
}

function Th({ k, label, num, sortKey, sortDir, toggleSort }: {
  k: SortKey; label: string; num?: boolean; sortKey: SortKey; sortDir: SortDir; toggleSort: (k: SortKey) => void;
}) {
  const active = sortKey === k;
  return (
    <th className={`sortable ${num ? "num" : ""} ${active ? "active" : ""}`} onClick={() => toggleSort(k)}>
      {label}{active ? (sortDir === "asc" ? " ▲" : " ▼") : ""}
    </th>
  );
}

function sortRows(rows: TabRow[], key: SortKey, dir: SortDir): TabRow[] {
  const mul = dir === "asc" ? 1 : -1;
  return [...rows].sort((a, b) => {
    if (key === "ticker") return a.ticker.localeCompare(b.ticker) * mul;
    if (key === "priority") return ((PRIORITY_RANK[a.priority] ?? 0) - (PRIORITY_RANK[b.priority] ?? 0)) * mul;
    const av = a[key] ?? -Infinity;
    const bv = b[key] ?? -Infinity;
    return (av - bv) * mul;
  });
}
const _CONSENSUS_CLASS: Record<string, string> = {
  "Strong Buy": "up", "Buy": "up", "Hold": "muted", "Sell": "down", "Strong Sell": "down",
};
function renderConsensus(c: ConsensusCell | undefined, t: ExploreT) {
  if (!c || c.state === "loading") return <span className="muted tiny">…</span>;
  if (c.state === "err") {
    return <span className="muted tiny" title={t(($) => $.watchlist.loadFailed)}>⚠</span>;
  }
  const d = c.data;
  // Distinguish missing-key / provider-error / no-coverage (gpt-5.5) — not all "—".
  if (d.status === "missing_key")
    return <span className="muted tiny" title={t(($) => $.watchlist.missingFinnhubKey)}>🔑</span>;
  if (d.status === "rate_limited")
    return <span className="muted tiny" title={t(($) => $.watchlist.finnhubRateLimit)}>⏳</span>;
  if (d.status === "provider_error")
    return <span className="muted tiny" title={t(($) => $.watchlist.analystSourceError)}>⚠</span>;
  if (d.status === "no_data")
    return <span className="muted tiny" title={t(($) => $.watchlist.temporaryNoData)}>—</span>;
  if (!d.rating)
    return <span className="muted tiny" title={t(($) => $.watchlist.noAnalystCoverage)}>—</span>;
  const cn = d.counts || {};
  const when = d.fetched_at ? d.fetched_at.slice(0, 10) : "—";
  const votes = `${cn.strongBuy ?? 0}/${cn.buy ?? 0}/${cn.hold ?? 0}/${cn.sell ?? 0}/${cn.strongSell ?? 0}`;
  const analystSummary = d.total === 1
    ? t(($) => $.watchlist.consensusAnalystSummary.one, { total: d.total, when })
    : t(($) => $.watchlist.consensusAnalystSummary.other, { total: d.total, when });
  const tip = `${t(($) => $.watchlist.consensusRatingsSummary, {
    strongBuy: cn.strongBuy ?? 0,
    buy: cn.buy ?? 0,
    hold: cn.hold ?? 0,
    sell: cn.sell ?? 0,
    strongSell: cn.strongSell ?? 0,
  })}\n${analystSummary}${d.status === "cached" ? t(($) => $.watchlist.cached) : ""}`;
  return (
    <span className={`consensus-tag ${_CONSENSUS_CLASS[d.rating] ?? "muted"}`} title={tip}>
      <span>{d.rating}</span>
      <span className="consensus-votes">{votes}</span>
    </span>
  );
}

function fmtNum(v: number | null): string { return v == null ? "—" : v.toLocaleString(undefined, { maximumFractionDigits: 2 }); }
function fmtPct(v: number | null): string { return v == null ? "—" : `${v > 0 ? "+" : ""}${v.toFixed(2)}%`; }
function changeClass(v: number | null): string { return v == null ? "" : v > 0 ? "up" : v < 0 ? "down" : ""; }
