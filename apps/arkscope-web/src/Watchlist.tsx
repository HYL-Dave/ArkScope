import { useCallback, useEffect, useMemo, useState } from "react";
import { getCockpitWatchlist, setArchived, type CockpitRow } from "./api";

interface CockpitData {
  rows: CockpitRow[];
  asOf: string | null;
  total: number;
  shown: number;
  archivedCount: number;
}

type State =
  | { kind: "loading" }
  | { kind: "ready"; data: CockpitData }
  | { kind: "error"; message: string };

type SortKey =
  | "ticker"
  | "latest_close"
  | "change_7d_pct"
  | "news_count_7d"
  | "sentiment_mean"
  | "priority";
type SortDir = "asc" | "desc";

const PRIORITY_RANK: Record<string, number> = { high: 3, medium: 2, low: 1 };

export function WatchlistView({
  onOpenTicker,
}: {
  onOpenTicker: (ticker: string, row?: CockpitRow) => void;
}) {
  const [state, setState] = useState<State>({ kind: "loading" });
  const [showArchived, setShowArchived] = useState(false);
  const [sortKey, setSortKey] = useState<SortKey>("change_7d_pct");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [refreshing, setRefreshing] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busyTicker, setBusyTicker] = useState<string | null>(null);

  const load = useCallback(async (includeArchived: boolean) => {
    setRefreshing(true);
    setActionError(null);
    try {
      const d = await getCockpitWatchlist(includeArchived);
      setState({
        kind: "ready",
        data: {
          rows: d.rows,
          asOf: d.as_of,
          total: d.total,
          shown: d.shown,
          archivedCount: d.archived_count,
        },
      });
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      // Keep an already-loaded table on a transient failure; full error screen
      // only on the initial load.
      setState((prev) => (prev.kind === "ready" ? prev : { kind: "error", message }));
      setActionError(message);
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void load(showArchived);
  }, [load, showArchived]);

  const data = state.kind === "ready" ? state.data : null;
  const rows = data?.rows ?? [];
  const sorted = useMemo(() => sortRows(rows, sortKey, sortDir), [rows, sortKey, sortDir]);

  function toggleSort(k: SortKey) {
    if (k === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(k);
      setSortDir(k === "ticker" || k === "priority" ? "asc" : "desc");
    }
  }

  const onArchiveToggle = useCallback(
    async (row: CockpitRow) => {
      setBusyTicker(row.ticker);
      setActionError(null);
      try {
        await setArchived(row.ticker, !row.archived);
        await load(showArchived);
      } catch (e) {
        setActionError(e instanceof Error ? e.message : String(e));
      } finally {
        setBusyTicker(null);
      }
    },
    [load, showArchived],
  );

  const thProps = { sortKey, sortDir, toggleSort };

  return (
    <main className="main">
      {state.kind === "loading" && <p className="muted">Loading watchlist…</p>}
      {state.kind === "error" && (
        <div className="errorbox">
          <p>Could not load the watchlist (/cockpit/watchlist).</p>
          <p className="muted">{state.message}</p>
        </div>
      )}
      {data && (
        <>
          <div className="surface-head">
            <h2 className="surface-title">Watchlist</h2>
            <span className="muted">
              {data.shown} of {data.total}
              {data.archivedCount > 0 && ` · ${data.archivedCount} archived`}
              {data.asOf && ` · as of ${data.asOf}`}
            </span>
            <span className="spacer" />
            {actionError && (
              <span className="refresh-err" title={actionError}>
                action failed
              </span>
            )}
            <button
              className={`btn-ghost ${showArchived ? "on" : ""}`}
              onClick={() => setShowArchived((v) => !v)}
            >
              {showArchived ? "✓ Archived" : "Show archived"}
            </button>
            <button className="btn-ghost" onClick={() => void load(showArchived)} disabled={refreshing}>
              {refreshing ? "↻ …" : "↻ Refresh"}
            </button>
          </div>

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
                  className={r.archived ? "archived" : ""}
                  onClick={() => onOpenTicker(r.ticker, r)}
                >
                  <td className="mono strong">
                    {r.ticker}
                    {r.archived && <span className="tag-archived">archived</span>}
                    {r.note_count > 0 && <span className="note-dot" title={`${r.note_count} note(s)`}>✎{r.note_count}</span>}
                  </td>
                  <td className="num">{fmtNum(r.latest_close)}</td>
                  <td className={`num ${changeClass(r.change_7d_pct)}`}>{fmtPct(r.change_7d_pct)}</td>
                  <td className="num">{r.news_count_7d}</td>
                  <td className="num">{fmtSent(r.sentiment_mean)}</td>
                  <td>
                    <span className={`badge p-${r.priority}`}>{r.priority}</span>
                  </td>
                  <td className="wl-actions" onClick={(e) => e.stopPropagation()}>
                    <RowActions
                      row={r}
                      busy={busyTicker === r.ticker}
                      onArchiveToggle={() => void onArchiveToggle(r)}
                      onOpen={() => onOpenTicker(r.ticker, r)}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <p className="muted tiny">
            Click a ticker to open its full detail page. Archive is a soft hide (restorable).
            Lists, tags and multi-tab views come with the profile surface — this v0 shows the
            aggregate "All Active" set.
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
    <th
      className={`sortable ${num ? "num" : ""} ${active ? "active" : ""}`}
      onClick={() => toggleSort(k)}
    >
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
  row: CockpitRow;
  busy: boolean;
  onArchiveToggle: () => void;
  onOpen: () => void;
}) {
  return (
    <span className="rowactions">
      <button type="button" title="Open detail" onClick={onOpen}>
        ↗
      </button>
      <button
        type="button"
        title={row.archived ? "Restore" : "Archive"}
        disabled={busy}
        onClick={onArchiveToggle}
      >
        {busy ? "…" : row.archived ? "↩" : "🗄"}
      </button>
    </span>
  );
}

// ---- helpers ----

function sortRows(rows: CockpitRow[], key: SortKey, dir: SortDir): CockpitRow[] {
  const mul = dir === "asc" ? 1 : -1;
  return [...rows].sort((a, b) => {
    if (key === "ticker") return a.ticker.localeCompare(b.ticker) * mul;
    if (key === "priority") {
      return ((PRIORITY_RANK[a.priority] ?? 0) - (PRIORITY_RANK[b.priority] ?? 0)) * mul;
    }
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
