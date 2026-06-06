import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  addMember,
  createList,
  deleteList,
  getCockpitWatchlist,
  getProfileLists,
  getUniverse,
  removeMember,
  renameList,
  searchSymbols,
  setArchived,
  type CockpitRow,
  type SymbolHit,
  type UniverseRow,
  type WatchlistSummary,
} from "./api";

// One normalized row the table renders, regardless of source (cockpit DTO for
// "All Active" vs universe rows for a specific list). `cockpit` is set only for
// All-Active rows so a click can hand the full cockpit row to the detail page.
interface TabRow {
  ticker: string;
  latest_close: number | null;
  change_7d_pct: number | null;
  news_count_7d: number;
  sentiment_mean: number | null;
  priority: string;
  archived: boolean;
  note_count: number;
  has_summary: boolean;
  cockpit?: CockpitRow;
}

interface Snapshot<T> {
  rows: T[];
  asOf: string | null;
}

type SortKey = "ticker" | "latest_close" | "change_7d_pct" | "news_count_7d" | "sentiment_mean" | "priority";
type SortDir = "asc" | "desc";

const PRIORITY_RANK: Record<string, number> = { high: 3, medium: 2, low: 1 };

function cockpitToTab(r: CockpitRow): TabRow {
  return { ticker: r.ticker, latest_close: r.latest_close, change_7d_pct: r.change_7d_pct,
    news_count_7d: r.news_count_7d, sentiment_mean: r.sentiment_mean, priority: r.priority ?? "",
    archived: r.archived, note_count: r.note_count, has_summary: true, cockpit: r };
}
function universeToTab(r: UniverseRow): TabRow {
  return { ticker: r.ticker, latest_close: r.latest_close, change_7d_pct: r.change_7d_pct,
    news_count_7d: r.news_count_7d, sentiment_mean: r.sentiment_mean, priority: r.priority ?? "",
    archived: r.archived, note_count: r.note_count, has_summary: r.has_summary };
}

export function WatchlistView({
  onOpenTicker,
}: {
  onOpenTicker: (ticker: string, row?: CockpitRow) => void;
}) {
  const [lists, setLists] = useState<WatchlistSummary[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null); // null = All Active
  const [showArchived, setShowArchived] = useState(false);
  const [sortKey, setSortKey] = useState<SortKey>("change_7d_pct");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [refreshing, setRefreshing] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [busyTicker, setBusyTicker] = useState<string | null>(null);

  // Cached, tab-independent sources (see B-slice-3 fix); rows are derived.
  const [cockpit, setCockpit] = useState<Snapshot<CockpitRow> | null>(null);
  const [universe, setUniverse] = useState<Snapshot<UniverseRow> | null>(null);
  const cockpitReq = useRef(0);
  const universeReq = useRef(0);
  const inflight = useRef(0);
  const beginLoad = useCallback(() => { inflight.current += 1; setRefreshing(true); }, []);
  const endLoad = useCallback(() => {
    inflight.current = Math.max(0, inflight.current - 1);
    if (inflight.current === 0) setRefreshing(false);
  }, []);

  // Rail editing + add-ticker state
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [renamingId, setRenamingId] = useState<number | null>(null);
  const [renameName, setRenameName] = useState("");
  const [addQuery, setAddQuery] = useState("");
  const [addResults, setAddResults] = useState<SymbolHit[] | null>(null);
  const [addBusy, setAddBusy] = useState(false);

  const loadLists = useCallback(async () => {
    try {
      setLists((await getProfileLists(false)).lists);
    } catch {
      /* rail degrades to All Active only */
    }
  }, []);

  const loadCockpit = useCallback(async () => {
    const id = ++cockpitReq.current;
    beginLoad();
    setErr(null);
    try {
      const d = await getCockpitWatchlist(true);
      if (id === cockpitReq.current) setCockpit({ rows: d.rows, asOf: d.as_of });
    } catch (e) {
      if (id === cockpitReq.current) setErr(e instanceof Error ? e.message : String(e));
    } finally {
      endLoad();
    }
  }, [beginLoad, endLoad]);

  const loadUniverse = useCallback(async () => {
    const id = ++universeReq.current;
    beginLoad();
    setErr(null);
    try {
      const u = await getUniverse(true);
      if (id === universeReq.current) setUniverse({ rows: u.rows, asOf: u.as_of });
    } catch (e) {
      if (id === universeReq.current) setErr(e instanceof Error ? e.message : String(e));
    } finally {
      endLoad();
    }
  }, [beginLoad, endLoad]);

  useEffect(() => {
    void loadLists();
    void loadCockpit();
  }, [loadLists, loadCockpit]);

  useEffect(() => {
    if (selectedId !== null && universe === null) void loadUniverse();
  }, [selectedId, universe, loadUniverse]);

  const selectedList = selectedId === null ? null : lists.find((l) => l.id === selectedId) ?? null;
  // If the selected list vanished (deleted), fall back to All Active.
  useEffect(() => {
    if (selectedId !== null && lists.length && !lists.some((l) => l.id === selectedId)) {
      setSelectedId(null);
    }
  }, [lists, selectedId]);

  // Debounced symbol search for the add-ticker box.
  useEffect(() => {
    const q = addQuery.trim();
    if (!q) { setAddResults(null); return; }
    const t = window.setTimeout(async () => {
      try {
        setAddResults((await searchSymbols(q, 8)).results);
      } catch {
        setAddResults([]);
      }
    }, 200);
    return () => window.clearTimeout(t);
  }, [addQuery]);

  const { rows, asOf } = useMemo<{ rows: TabRow[]; asOf: string | null }>(() => {
    if (selectedList === null) {
      const src = cockpit?.rows ?? [];
      return { rows: src.filter((r) => showArchived || !r.archived).map(cockpitToTab), asOf: cockpit?.asOf ?? null };
    }
    const src = universe?.rows ?? [];
    return {
      rows: src.filter((r) => (showArchived ? r.all_lists : r.lists).includes(selectedList.name)).map(universeToTab),
      asOf: universe?.asOf ?? null,
    };
  }, [selectedList, showArchived, cockpit, universe]);

  const isLoading = selectedList === null ? cockpit === null : universe === null;
  const archivedCount = useMemo(() => rows.filter((r) => r.archived).length, [rows]);
  const sorted = useMemo(() => sortRows(rows, sortKey, sortDir), [rows, sortKey, sortDir]);

  function toggleSort(k: SortKey) {
    if (k === sortKey) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setSortKey(k); setSortDir(k === "ticker" || k === "priority" ? "asc" : "desc"); }
  }

  const reloadAfterMutation = useCallback(async () => {
    await Promise.all([loadUniverse(), loadCockpit()]);
    void loadLists();
  }, [loadUniverse, loadCockpit, loadLists]);

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
      await loadLists();
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
  }

  async function onDeleteList(li: WatchlistSummary) {
    // window.confirm is supported in Electron (window.prompt is not).
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
  const hasData = selectedList === null ? cockpit !== null : universe !== null;
  const title = selectedList === null ? "All Active" : selectedList.name;

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
                <button
                  className="wl-railbtn"
                  title="改名"
                  onClick={() => { setRenamingId(li.id); setRenameName(li.name); }}
                >✎</button>
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
                placeholder={`加入標的到「${selectedList.name}」… 輸入代號或公司名`}
                value={addQuery}
                onChange={(e) => setAddQuery(e.target.value)}
                disabled={addBusy}
              />
              {addQuery.trim() && (
                <div className="wl-addresults">
                  {addResults === null ? (
                    <div className="muted tiny wl-addhint">搜尋中…</div>
                  ) : addResults.length === 0 ? (
                    <div className="muted tiny wl-addhint">找不到符合的標的（目錄為精確/前綴比對，非模糊）。可直接輸入完整代號。</div>
                  ) : (
                    addResults.map((h) => (
                      <button key={h.ticker} className="wl-addrow" disabled={addBusy} onClick={() => void onAddSymbol(h.ticker)}>
                        <span className="mono strong">{h.ticker}</span>
                        <span className="wl-addname">{h.name}</span>
                        {h.tracked && <span className="muted tiny">已追蹤</span>}
                      </button>
                    ))
                  )}
                </div>
              )}
            </div>
          )}

          {isLoading ? (
            <p className="muted">Loading…</p>
          ) : (
            <>
              <table className="wl">
                <thead>
                  <tr>
                    <Th k="ticker" label="Ticker" {...thProps} />
                    <Th k="latest_close" label="Price" num {...thProps} />
                    <Th k="change_7d_pct" label="Chg 7d" num {...thProps} />
                    <Th k="news_count_7d" label="News" num {...thProps} />
                    <Th k="sentiment_mean" label="Sentiment" num {...thProps} />
                    <Th k="priority" label="Priority" {...thProps} />
                    <th className="wl-actions">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {sorted.map((r) => (
                    <tr
                      key={r.ticker}
                      className={`${r.archived ? "archived" : ""} ${r.has_summary ? "" : "no-summary"}`}
                      onClick={() => onOpenTicker(r.ticker, r.cockpit)}
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
                      <td className="num">{fmtSent(r.sentiment_mean)}</td>
                      <td>{r.priority ? <span className={`badge p-${r.priority}`}>{r.priority}</span> : <span className="muted">—</span>}</td>
                      <td className="wl-actions" onClick={(e) => e.stopPropagation()}>
                        <span className="rowactions">
                          <button type="button" title="Open detail" onClick={() => onOpenTicker(r.ticker, r.cockpit)}>↗</button>
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
              {sorted.length === 0 && (
                <p className="muted tiny">
                  {selectedList ? "這個清單還沒有標的 — 用上方搜尋加入。" : "沒有標的。"}
                  {!showArchived && rows.length === 0 && archivedCount === 0 ? "" : ""}
                </p>
              )}
              <p className="muted tiny">
                ↗ 開詳情 · {selectedList ? "✕ 從此清單移除 · " : ""}🗄 全域封存（所有清單）。
                {selectedList ? " 刪除清單只移除清單關係，不刪標的或市場資料。" : ""}
              </p>
            </>
          )}
        </div>
      </div>
    </main>
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
function fmtNum(v: number | null): string { return v == null ? "—" : v.toLocaleString(undefined, { maximumFractionDigits: 2 }); }
function fmtPct(v: number | null): string { return v == null ? "—" : `${v > 0 ? "+" : ""}${v.toFixed(2)}%`; }
function fmtSent(v: number | null): string { return v == null ? "—" : v.toFixed(2); }
function changeClass(v: number | null): string { return v == null ? "" : v > 0 ? "up" : v < 0 ? "down" : ""; }
