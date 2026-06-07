import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  addMember,
  createList,
  deleteList,
  getConsensus,
  getProfileLists,
  getUniverse,
  removeMember,
  renameList,
  searchSymbols,
  setArchived,
  setPriority,
  type SymbolHit,
  type UniverseRow,
  type WatchlistSummary,
} from "./api";

// One normalized row the table renders. The single source is the universe
// (profile-state substrate); "All Active" is the union of active memberships
// across the user's lists — NOT a separate curated source.
interface TabRow {
  ticker: string;
  latest_close: number | null;
  change_7d_pct: number | null;
  news_count_7d: number;
  priority: string;
  archived: boolean;
  note_count: number;
  has_summary: boolean;
}

type SortKey = "ticker" | "latest_close" | "change_7d_pct" | "news_count_7d" | "priority";
type SortDir = "asc" | "desc";
type Priority = "high" | "medium" | "low";
type ConsensusCell =
  | { state: "loading" }
  | { state: "err" }
  | { state: "ok"; rating: string | null };

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
  };
}

export function WatchlistView({ onOpenTicker }: { onOpenTicker: (ticker: string) => void }) {
  const [lists, setLists] = useState<WatchlistSummary[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null); // null = All Active
  const [showArchived, setShowArchived] = useState(false);
  const [sortKey, setSortKey] = useState<SortKey>("change_7d_pct");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [refreshing, setRefreshing] = useState(false);
  const [err, setErr] = useState<string | null>(null);
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
      setLists((await getProfileLists(false)).lists);
    } catch {
      /* rail degrades to All Active only */
    }
  }, []);

  const loadUniverse = useCallback(async () => {
    const id = ++universeReq.current;
    setRefreshing(true);
    setErr(null);
    try {
      const u = await getUniverse(true);
      if (id === universeReq.current) setUniverse({ rows: u.rows, asOf: u.as_of });
    } catch (e) {
      if (id === universeReq.current) setErr(e instanceof Error ? e.message : String(e));
    } finally {
      if (id === universeReq.current) setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void loadLists();
    void loadUniverse();
  }, [loadLists, loadUniverse]);

  const selectedList = selectedId === null ? null : lists.find((l) => l.id === selectedId) ?? null;
  // If the selected list vanished (deleted/renamed away), fall back to All Active.
  useEffect(() => {
    if (selectedId !== null && lists.length && !lists.some((l) => l.id === selectedId)) {
      setSelectedId(null);
    }
  }, [lists, selectedId]);

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

  // Rows are derived from the universe. All Active = rows with ≥1 active list
  // membership (or any membership when showing archived) — so it auto-populates
  // from your lists and is honestly empty for a new user.
  const { rows, asOf } = useMemo<{ rows: TabRow[]; asOf: string | null }>(() => {
    const src = universe?.rows ?? [];
    const asOfVal = universe?.asOf ?? null;
    if (selectedList === null) {
      return {
        rows: src
          .filter((r) => (showArchived ? r.all_lists.length > 0 : r.lists.length > 0))
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
  }, [selectedList, showArchived, universe]);

  const isLoading = universe === null;
  // Archived-in-this-view count, computed from the universe (not the filtered
  // rows) so "· N archived" shows even while archived rows are hidden — making
  // the Show-archived toggle discoverable.
  const archivedCount = useMemo(() => {
    const src = universe?.rows ?? [];
    if (selectedList === null) return src.filter((r) => r.archived && r.all_lists.length > 0).length;
    return src.filter((r) => r.archived_lists.includes(selectedList.name)).length;
  }, [universe, selectedList]);
  const sorted = useMemo(() => sortRows(rows, sortKey, sortDir), [rows, sortKey, sortDir]);

  // Analyst consensus, lazy per visible row + daily-cached server-side. Fetched
  // with bounded concurrency (Finnhub is throttled); each ticker requested once
  // per session. Replaces the old ArkScope LLM "sentiment" column.
  const [consensus, setConsensus] = useState<Record<string, ConsensusCell>>({});
  const consensusRequested = useRef<Set<string>>(new Set());
  useEffect(() => {
    const todo = sorted.map((r) => r.ticker).filter((t) => !consensusRequested.current.has(t));
    if (todo.length === 0) return;
    let cancelled = false;
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
            if (!cancelled) setConsensus((p) => ({ ...p, [t]: { state: "ok", rating: c.rating } }));
          } catch {
            if (!cancelled) setConsensus((p) => ({ ...p, [t]: { state: "err" } }));
          }
        }
      };
      await Promise.all([worker(), worker(), worker()]); // concurrency 3
    })();
    return () => {
      cancelled = true;
    };
  }, [sorted]);

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
      } catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
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
      } catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
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
        setErr(e instanceof Error ? e.message : String(e));
        void loadUniverse(); // revert to server truth on failure
      }
    },
    [loadUniverse],
  );

  async function submitNewList() {
    const name = newName.trim();
    if (!name) return;
    setErr(null);
    try {
      const li = await createList(name);
      setCreating(false);
      setNewName("");
      await loadLists();
      setSelectedId(li.id);
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
  }

  async function submitRename(id: number) {
    const name = renameName.trim();
    if (!name) { setRenamingId(null); return; }
    setErr(null);
    try {
      await renameList(id, name);
      setRenamingId(null);
      await reloadAfterMutation(); // membership names in cached rows update too
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
  }

  async function onDeleteList(li: WatchlistSummary) {
    const ok = window.confirm(
      `刪除清單「${li.name}」？\n\n只移除這個清單與其成員關係 —— 不會刪除標的本身或任何市場資料，標的仍保留在其他清單中。`,
    );
    if (!ok) return;
    setErr(null);
    try {
      await deleteList(li.id);
      if (selectedId === li.id) setSelectedId(null);
      await reloadAfterMutation();
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
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
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
    finally { setAddBusy(false); }
  }

  const thProps = { sortKey, sortDir, toggleSort };
  const title = selectedList === null ? "All Active" : selectedList.name;
  const normQuery = addQuery.trim().toUpperCase();

  return (
    <main className="main">
      <div className="surface-head">
        <h2 className="surface-title">自選股</h2>
        <span className="muted">
          {title} · {rows.length} 檔
          {archivedCount > 0 && ` · ${archivedCount} archived`}
          {asOf && ` · as of ${asOf}`}
        </span>
        <span className="spacer" />
        {err && <span className="refresh-err" title={err}>error</span>}
        <button className={`btn-ghost ${showArchived ? "on" : ""}`} onClick={() => setShowArchived((v) => !v)}>
          {showArchived ? "✓ Archived" : "Show archived"}
        </button>
        <button className="btn-ghost" onClick={() => void reloadAfterMutation()} disabled={refreshing}>
          {refreshing ? "↻ …" : "↻ Refresh"}
        </button>
      </div>

      <div className="wl-layout">
        <aside className="wl-rail">
          <button
            className={`wl-railitem ${selectedId === null ? "active" : ""}`}
            onClick={() => setSelectedId(null)}
            title="所有清單中 active 的標的聯集"
          >
            All Active
          </button>
          {lists.map((li) =>
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
                <button className="wl-railname" onClick={() => setSelectedId(li.id)} title={`${li.kind} · ${li.active_count} active`}>
                  {li.name} <span className="wl-railcount">{li.active_count}</span>
                </button>
                <button className="wl-railbtn" title="改名" onClick={() => { setRenamingId(li.id); setRenameName(li.name); }}>✎</button>
                <button className="wl-railbtn" title="刪除清單" onClick={() => void onDeleteList(li)}>🗑</button>
              </div>
            ),
          )}
          {creating ? (
            <div className="wl-railedit">
              <input
                className="wl-railinput"
                autoFocus
                placeholder="清單名稱…"
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
            <button className="wl-railadd" onClick={() => setCreating(true)}>＋ 新增清單</button>
          )}
        </aside>

        <div className="wl-content">
          {selectedList && (
            <div className="wl-addbox">
              <input
                className="aicard-q"
                placeholder={`加入標的到「${selectedList.name}」… 輸入代號或公司名（Enter 直接加入）`}
                value={addQuery}
                onChange={(e) => setAddQuery(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && normQuery) void onAddSymbol(normQuery); }}
                disabled={addBusy}
              />
              {addQuery.trim() && (
                <div className="wl-addresults">
                  {addResults === null ? (
                    <div className="muted tiny wl-addhint">搜尋中…</div>
                  ) : (
                    <>
                      {addResults.map((h) => (
                        <button key={h.ticker} className="wl-addrow" disabled={addBusy} onClick={() => void onAddSymbol(h.ticker)}>
                          <span className="mono strong">{h.ticker}</span>
                          <span className="wl-addname">{h.name}</span>
                          {h.tracked && <span className="muted tiny">已追蹤</span>}
                        </button>
                      ))}
                      {addResults.length === 0 && (
                        <div className="muted tiny wl-addhint">目錄無相符（精確/前綴比對，非模糊）。</div>
                      )}
                      <button className="wl-addrow wl-adddirect" disabled={addBusy} onClick={() => void onAddSymbol(normQuery)}>
                        ＋ 直接加入代號 <span className="mono strong">{normQuery}</span>
                      </button>
                    </>
                  )}
                </div>
              )}
            </div>
          )}

          {isLoading ? (
            <p className="muted">Loading…</p>
          ) : sorted.length === 0 ? (
            <EmptyState selectedList={selectedList} hasLists={lists.length > 0} showArchived={showArchived} onCreate={() => setCreating(true)} />
          ) : (
            <>
              <table className="wl">
                <thead>
                  <tr>
                    <Th k="ticker" label="Ticker" {...thProps} />
                    <Th k="latest_close" label="Price" num {...thProps} />
                    <Th k="change_7d_pct" label="Chg 7d" num {...thProps} />
                    <Th k="news_count_7d" label="News" num {...thProps} />
                    <th className="wl-consensus" title="Finnhub analyst consensus (daily-cached)">Consensus</th>
                    <Th k="priority" label="Priority" {...thProps} />
                    <th className="wl-actions">Actions</th>
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
                        {!r.has_summary && <span className="tag-nosum" title="尚無市場摘要">無摘要</span>}
                        {r.archived && <span className="tag-archived">archived</span>}
                        {r.note_count > 0 && <span className="note-dot" title={`${r.note_count} note(s)`}>✎{r.note_count}</span>}
                      </td>
                      <td className="num">{fmtNum(r.latest_close)}</td>
                      <td className={`num ${changeClass(r.change_7d_pct)}`}>{fmtPct(r.change_7d_pct)}</td>
                      <td className="num">{r.news_count_7d}</td>
                      <td className="wl-consensus">{renderConsensus(consensus[r.ticker])}</td>
                      <td onClick={(e) => e.stopPropagation()}>
                        <select
                          className={`prio-select p-${r.priority || "none"}`}
                          value={r.priority}
                          onChange={(e) => void onSetPriority(r.ticker, (e.target.value || null) as Priority | null)}
                          title="設定優先級"
                        >
                          <option value="">—</option>
                          <option value="high">high</option>
                          <option value="medium">medium</option>
                          <option value="low">low</option>
                        </select>
                      </td>
                      <td className="wl-actions" onClick={(e) => e.stopPropagation()}>
                        <span className="rowactions">
                          <button type="button" title="Open detail" onClick={() => onOpenTicker(r.ticker)}>↗</button>
                          {selectedList && (
                            <button type="button" title={`從「${selectedList.name}」移除`} disabled={busyTicker === r.ticker} onClick={() => void onRemoveFromList(r)}>
                              {busyTicker === r.ticker ? "…" : "✕"}
                            </button>
                          )}
                          <button type="button" title={r.archived ? "Restore (global)" : "Archive (global)"} disabled={busyTicker === r.ticker} onClick={() => void onArchiveToggle(r)}>
                            {busyTicker === r.ticker ? "…" : r.archived ? "↩" : "🗄"}
                          </button>
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="muted tiny">
                ↗ 開詳情 · {selectedList ? "✕ 從此清單移除 · " : ""}🗄 全域封存（所有清單）· Priority 下拉可設定。
                {selectedList === null && " 「All Active」= 你所有清單中 active 標的的聯集；新增請到清單裡加。"}
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
}: {
  selectedList: WatchlistSummary | null;
  hasLists: boolean;
  showArchived: boolean;
  onCreate: () => void;
}) {
  if (selectedList) {
    return <p className="muted tiny">這個清單還沒有標的 — 用上方搜尋加入{showArchived ? "" : "（或試試 Show archived）"}。</p>;
  }
  if (!hasLists) {
    return (
      <div className="wl-empty">
        <p className="muted">還沒有任何清單。</p>
        <p className="muted tiny">
          建立你的第一個清單，或到「全部標的」按「匯入清單」帶入現有分類。
        </p>
        <button className="btn-ghost" onClick={onCreate}>＋ 新增清單</button>
      </div>
    );
  }
  return <p className="muted tiny">你的清單目前沒有 active 標的{showArchived ? "" : "（試試 Show archived）"}。</p>;
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
function renderConsensus(c: ConsensusCell | undefined) {
  if (!c || c.state === "loading") return <span className="muted tiny">…</span>;
  if (c.state === "err") return <span className="muted tiny">—</span>;
  if (!c.rating) return <span className="muted tiny" title="無分析師覆蓋">—</span>;
  return <span className={`consensus-tag ${_CONSENSUS_CLASS[c.rating] ?? "muted"}`}>{c.rating}</span>;
}

function fmtNum(v: number | null): string { return v == null ? "—" : v.toLocaleString(undefined, { maximumFractionDigits: 2 }); }
function fmtPct(v: number | null): string { return v == null ? "—" : `${v > 0 ? "+" : ""}${v.toFixed(2)}%`; }
function changeClass(v: number | null): string { return v == null ? "" : v > 0 ? "up" : v < 0 ? "down" : ""; }
