import { useCallback, useEffect, useMemo, useState } from "react";
import {
  getCockpitWatchlist,
  getProfileLists,
  getUniverse,
  setArchived,
  type CockpitRow,
  type UniverseRow,
  type WatchlistSummary,
} from "./api";

// One normalized row the table renders, regardless of source (cockpit DTO for
// "All Active" vs universe rows for a specific list tab) — avoids two shapes
// leaking into the table. `cockpit` is set only for All-Active rows so a click
// can hand the full cockpit row to the detail page.
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

type State =
  | { kind: "loading" }
  | { kind: "ready"; rows: TabRow[]; asOf: string | null }
  | { kind: "error"; message: string };

type SortKey = "ticker" | "latest_close" | "change_7d_pct" | "news_count_7d" | "sentiment_mean" | "priority";
type SortDir = "asc" | "desc";

const ALL_ACTIVE = "__all_active__";
const PRIORITY_RANK: Record<string, number> = { high: 3, medium: 2, low: 1 };

function cockpitToTab(r: CockpitRow): TabRow {
  return {
    ticker: r.ticker,
    latest_close: r.latest_close,
    change_7d_pct: r.change_7d_pct,
    news_count_7d: r.news_count_7d,
    sentiment_mean: r.sentiment_mean,
    priority: r.priority ?? "",
    archived: r.archived,
    note_count: r.note_count,
    has_summary: true,
    cockpit: r,
  };
}

function universeToTab(r: UniverseRow): TabRow {
  return {
    ticker: r.ticker,
    latest_close: r.latest_close,
    change_7d_pct: r.change_7d_pct,
    news_count_7d: r.news_count_7d,
    sentiment_mean: r.sentiment_mean,
    priority: r.priority ?? "",
    archived: r.archived,
    note_count: r.note_count,
    has_summary: r.has_summary,
  };
}

export function WatchlistView({
  onOpenTicker,
}: {
  onOpenTicker: (ticker: string, row?: CockpitRow) => void;
}) {
  const [state, setState] = useState<State>({ kind: "loading" });
  const [lists, setLists] = useState<WatchlistSummary[]>([]);
  const [tab, setTab] = useState<string>(ALL_ACTIVE); // ALL_ACTIVE or a list name
  const [showArchived, setShowArchived] = useState(false);
  const [sortKey, setSortKey] = useState<SortKey>("change_7d_pct");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [refreshing, setRefreshing] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busyTicker, setBusyTicker] = useState<string | null>(null);

  // List catalog (tab bar) — loaded once; refreshed after an archive toggle.
  const loadLists = useCallback(async () => {
    try {
      setLists((await getProfileLists(false)).lists);
    } catch {
      /* tab bar degrades to just All Active */
    }
  }, []);

  useEffect(() => {
    void loadLists();
  }, [loadLists]);

  // Rows for the current tab: All Active → cockpit DTO; a list → universe rows
  // filtered by membership (active, or active+archived when showing archived).
  const load = useCallback(
    async (currentTab: string, includeArchived: boolean) => {
      setRefreshing(true);
      setActionError(null);
      try {
        if (currentTab === ALL_ACTIVE) {
          const d = await getCockpitWatchlist(includeArchived);
          setState({ kind: "ready", rows: d.rows.map(cockpitToTab), asOf: d.as_of });
        } else {
          const u = await getUniverse(true);
          const rows = u.rows
            .filter((r) =>
              includeArchived ? r.all_lists.includes(currentTab) : r.lists.includes(currentTab),
            )
            .map(universeToTab);
          setState({ kind: "ready", rows, asOf: u.as_of });
        }
      } catch (e) {
        const message = e instanceof Error ? e.message : String(e);
        setState((prev) => (prev.kind === "ready" ? prev : { kind: "error", message }));
        setActionError(message);
      } finally {
        setRefreshing(false);
      }
    },
    [],
  );

  useEffect(() => {
    void load(tab, showArchived);
  }, [load, tab, showArchived]);

  const rows = state.kind === "ready" ? state.rows : [];
  const asOf = state.kind === "ready" ? state.asOf : null;
  const archivedCount = useMemo(() => rows.filter((r) => r.archived).length, [rows]);
  const sorted = useMemo(() => sortRows(rows, sortKey, sortDir), [rows, sortKey, sortDir]);

  function toggleSort(k: SortKey) {
    if (k === sortKey) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortKey(k);
      setSortDir(k === "ticker" || k === "priority" ? "asc" : "desc");
    }
  }

  const onArchiveToggle = useCallback(
    async (row: TabRow) => {
      setBusyTicker(row.ticker);
      setActionError(null);
      try {
        await setArchived(row.ticker, !row.archived); // NOTE: global archive (per-list removal = later slice)
        await load(tab, showArchived);
        void loadLists();
      } catch (e) {
        setActionError(e instanceof Error ? e.message : String(e));
      } finally {
        setBusyTicker(null);
      }
    },
    [load, loadLists, tab, showArchived],
  );

  const thProps = { sortKey, sortDir, toggleSort };
  const tabLabel = tab === ALL_ACTIVE ? "All Active" : tab;

  return (
    <main className="main">
      {state.kind === "error" && (
        <div className="errorbox">
          <p>Could not load the watchlist.</p>
          <p className="muted">{state.message}</p>
        </div>
      )}

      <div className="surface-head">
        <h2 className="surface-title">自選股</h2>
        <span className="muted">
          {tabLabel} · {rows.length} 檔
          {archivedCount > 0 && ` · ${archivedCount} archived`}
          {asOf && ` · as of ${asOf}`}
        </span>
        <span className="spacer" />
        {actionError && <span className="refresh-err" title={actionError}>action failed</span>}
        <button className={`btn-ghost ${showArchived ? "on" : ""}`} onClick={() => setShowArchived((v) => !v)}>
          {showArchived ? "✓ Archived" : "Show archived"}
        </button>
        <button className="btn-ghost" onClick={() => void load(tab, showArchived)} disabled={refreshing}>
          {refreshing ? "↻ …" : "↻ Refresh"}
        </button>
      </div>

      <div className="wl-tabs">
        <button className={`wl-tab ${tab === ALL_ACTIVE ? "active" : ""}`} onClick={() => setTab(ALL_ACTIVE)}>
          All Active
        </button>
        {lists.map((li) => (
          <button
            key={li.id}
            className={`wl-tab ${tab === li.name ? "active" : ""}`}
            onClick={() => setTab(li.name)}
            title={`${li.kind} · ${li.active_count} active / ${li.total_count} total`}
          >
            {li.name} <span className="wl-tab-count">{li.active_count}</span>
          </button>
        ))}
        {lists.length === 0 && (
          <span className="muted tiny">尚無清單分頁 — 到「全部標的」按「匯入清單」。</span>
        )}
      </div>

      {state.kind === "loading" ? (
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
                    <RowActions
                      row={r}
                      busy={busyTicker === r.ticker}
                      onArchiveToggle={() => void onArchiveToggle(r)}
                      onOpen={() => onOpenTicker(r.ticker, r.cockpit)}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {sorted.length === 0 && <p className="muted tiny">這個分頁沒有標的{showArchived ? "" : "（試試 Show archived）"}。</p>}

          <p className="muted tiny">
            點 ticker 開整頁詳情。分頁依清單成員過濾（同一套 profile-state 清單）；封存目前為全域封存
            （「從此清單移除」為後續功能）。
          </p>
        </>
      )}
    </main>
  );
}

function Th({
  k,
  label,
  num,
  sortKey,
  sortDir,
  toggleSort,
}: {
  k: SortKey;
  label: string;
  num?: boolean;
  sortKey: SortKey;
  sortDir: SortDir;
  toggleSort: (k: SortKey) => void;
}) {
  const active = sortKey === k;
  return (
    <th className={`sortable ${num ? "num" : ""} ${active ? "active" : ""}`} onClick={() => toggleSort(k)}>
      {label}
      {active ? (sortDir === "asc" ? " ▲" : " ▼") : ""}
    </th>
  );
}

function RowActions({
  row,
  busy,
  onArchiveToggle,
  onOpen,
}: {
  row: TabRow;
  busy: boolean;
  onArchiveToggle: () => void;
  onOpen: () => void;
}) {
  return (
    <span className="rowactions">
      <button type="button" title="Open detail" onClick={onOpen}>↗</button>
      <button
        type="button"
        title={row.archived ? "Restore (global)" : "Archive (global)"}
        disabled={busy}
        onClick={onArchiveToggle}
      >
        {busy ? "…" : row.archived ? "↩" : "🗄"}
      </button>
    </span>
  );
}

// ---- helpers ----

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

function fmtNum(v: number | null): string {
  return v == null ? "—" : v.toLocaleString(undefined, { maximumFractionDigits: 2 });
}
function fmtPct(v: number | null): string {
  return v == null ? "—" : `${v > 0 ? "+" : ""}${v.toFixed(2)}%`;
}
function fmtSent(v: number | null): string {
  return v == null ? "—" : v.toFixed(2);
}
function changeClass(v: number | null): string {
  return v == null ? "" : v > 0 ? "up" : v < 0 ? "down" : "";
}
