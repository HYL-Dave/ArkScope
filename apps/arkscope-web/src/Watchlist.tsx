import { useCallback, useEffect, useMemo, useState } from "react";
import {
  addNote,
  deleteNote,
  getCockpitWatchlist,
  getNotes,
  getPriceChange,
  setArchived,
  type CockpitRow,
  type Note,
  type PriceChange,
} from "./api";

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
type DetailTab = "overview" | "notes";

const PRIORITY_RANK: Record<string, number> = { high: 3, medium: 2, low: 1 };

export function WatchlistView() {
  const [state, setState] = useState<State>({ kind: "loading" });
  const [showArchived, setShowArchived] = useState(false);
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [detailTab, setDetailTab] = useState<DetailTab>("overview");
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
  const selected = selectedTicker ? rows.find((r) => r.ticker === selectedTicker) ?? null : null;

  function toggleSort(k: SortKey) {
    if (k === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(k);
      setSortDir(k === "ticker" || k === "priority" ? "asc" : "desc");
    }
  }

  const patchNoteCount = useCallback((ticker: string, noteCount: number) => {
    setState((prev) =>
      prev.kind === "ready"
        ? {
            ...prev,
            data: {
              ...prev.data,
              rows: prev.data.rows.map((r) =>
                r.ticker === ticker ? { ...r, note_count: noteCount } : r,
              ),
            },
          }
        : prev,
    );
  }, []);

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

  function openRow(ticker: string) {
    setSelectedTicker(ticker);
    setDetailTab("overview");
  }
  function openNotes(ticker: string) {
    setSelectedTicker(ticker);
    setDetailTab("notes");
  }

  const thProps = { sortKey, sortDir, toggleSort };

  return (
    <>
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
                    className={[
                      selectedTicker === r.ticker ? "sel" : "",
                      r.archived ? "archived" : "",
                    ]
                      .filter(Boolean)
                      .join(" ")}
                    onClick={() => openRow(r.ticker)}
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
                        onNote={() => openNotes(r.ticker)}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <p className="muted tiny">
              Archive is a soft hide (restorable). Lists, tags and multi-tab views come with the
              profile surface — this v0 shows the aggregate "All Active" set.
            </p>
          </>
        )}
      </main>

      <aside className="rightpanel detail">
        {selected ? (
          <TickerDetail
            key={selected.ticker}
            row={selected}
            tab={detailTab}
            onTab={setDetailTab}
            onNoteCount={(n) => patchNoteCount(selected.ticker, n)}
          />
        ) : (
          <p className="muted">Select a ticker to see its detail.</p>
        )}
      </aside>
    </>
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
  onNote,
}: {
  row: CockpitRow;
  busy: boolean;
  onArchiveToggle: () => void;
  onNote: () => void;
}) {
  return (
    <span className="rowactions">
      <button type="button" title="Notes" onClick={onNote}>
        📝
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

function TickerDetail({
  row,
  tab,
  onTab,
  onNoteCount,
}: {
  row: CockpitRow;
  tab: DetailTab;
  onTab: (t: DetailTab) => void;
  onNoteCount: (n: number) => void;
}) {
  return (
    <div className="detailpane">
      <div className="detail-head">
        <span className="mono strong big">{row.ticker}</span>
        <span className={`badge p-${row.priority}`}>{row.priority}</span>
        {row.archived && <span className="tag-archived">archived</span>}
      </div>
      <div className="muted tiny">{row.group ?? "—"}</div>
      {row.lists.length > 0 && (
        <div className="chips">
          {row.lists.map((l) => (
            <span key={l} className="list-chip">
              {l}
            </span>
          ))}
        </div>
      )}

      <div className="detail-tabs">
        <button
          type="button"
          className={`tab ${tab === "overview" ? "active" : ""}`}
          onClick={() => onTab("overview")}
        >
          Overview
        </button>
        <button
          type="button"
          className={`tab ${tab === "notes" ? "active" : ""}`}
          onClick={() => onTab("notes")}
        >
          Notes {row.note_count > 0 ? `(${row.note_count})` : ""}
        </button>
        <span className="tab disabled" title="agent wiring deferred">
          AI summary
        </span>
      </div>

      {tab === "overview" ? (
        <OverviewTab row={row} />
      ) : (
        <NotesTab ticker={row.ticker} onNoteCount={onNoteCount} />
      )}
    </div>
  );
}

function OverviewTab({ row }: { row: CockpitRow }) {
  const [pc, setPc] = useState<PriceChange | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setPc(null);
    setErr(null);
    (async () => {
      try {
        const d = await getPriceChange(row.ticker, 30);
        if (alive) setPc(d);
      } catch (e) {
        if (alive) setErr(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      alive = false;
    };
  }, [row.ticker]);

  return (
    <>
      <dl className="kv">
        <Kv k="Last close" v={fmtNum(row.latest_close)} />
        <Kv k="Change 7d" v={fmtPct(row.change_7d_pct)} cls={changeClass(row.change_7d_pct)} />
        <Kv k="News 7d" v={String(row.news_count_7d)} />
        <Kv k="Sentiment" v={fmtSent(row.sentiment_mean)} />
        <Kv k="Bullish %" v={fmtRatioPct(row.bullish_ratio)} />
      </dl>

      <h4 className="detail-section">Price (30d)</h4>
      {err && <p className="muted tiny">price detail unavailable: {err}</p>}
      {!err && !pc && <p className="muted tiny">loading…</p>}
      {pc && (
        <dl className="kv">
          <Kv k="Latest close" v={fmtNum(pc.latest_close)} />
          <Kv k="Change %" v={fmtPct(pc.change_pct)} cls={changeClass(pc.change_pct)} />
          <Kv k="Period high" v={fmtNum(pc.period_high)} />
          <Kv k="Period low" v={fmtNum(pc.period_low)} />
          <Kv k="Range %" v={fmtRangePct(pc.high_low_range_pct)} />
          <Kv k="Volume" v={fmtNum(pc.total_volume)} />
          <Kv k="Bars" v={String(pc.bar_count)} />
          <Kv k="Dates" v={pc.date_range} />
        </dl>
      )}
    </>
  );
}

function NotesTab({
  ticker,
  onNoteCount,
}: {
  ticker: string;
  onNoteCount: (n: number) => void;
}) {
  const [notes, setNotes] = useState<Note[] | null>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const d = await getNotes(ticker);
      setNotes(d.notes);
      onNoteCount(d.notes.length);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }, [ticker, onNoteCount]);

  useEffect(() => {
    setNotes(null);
    setErr(null);
    void refresh();
  }, [refresh]);

  async function submit() {
    const body = draft.trim();
    if (!body || busy) return;
    setBusy(true);
    setErr(null);
    try {
      await addNote(ticker, body);
      setDraft("");
      await refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: number) {
    setBusy(true);
    setErr(null);
    try {
      await deleteNote(ticker, id);
      await refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="notes">
      <textarea
        className="note-input"
        placeholder={`Add a note on ${ticker}…`}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if ((e.metaKey || e.ctrlKey) && e.key === "Enter") void submit();
        }}
        rows={3}
      />
      <div className="note-actions">
        <span className="muted tiny">⌘/Ctrl+Enter to save</span>
        <button type="button" disabled={busy || !draft.trim()} onClick={() => void submit()}>
          Add note
        </button>
      </div>
      {err && <p className="refresh-err tiny">{err}</p>}

      {notes === null && !err && <p className="muted tiny">loading…</p>}
      {notes && notes.length === 0 && <p className="muted tiny">No notes yet.</p>}
      {notes && notes.length > 0 && (
        <ul className="note-list">
          {notes.map((n) => (
            <li key={n.id} className="note-item">
              <div className="note-body">{n.body}</div>
              <div className="note-meta">
                <span className="muted tiny">{n.created_at.replace("T", " ").replace("+00:00", "Z")}</span>
                <button
                  type="button"
                  className="note-del"
                  disabled={busy}
                  title="Delete note"
                  onClick={() => void remove(n.id)}
                >
                  ✕
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Kv({ k, v, cls }: { k: string; v: string; cls?: string }) {
  return (
    <>
      <dt>{k}</dt>
      <dd className={cls}>{v}</dd>
    </>
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

// Bullish ratio is a 0..1 fraction — render it as a whole percent (0.32 -> 32%).
function fmtRatioPct(v: number | null): string {
  return v == null ? "—" : `${Math.round(v * 100)}%`;
}

// Range is a magnitude (never negative), so append "%" without a +/- sign.
function fmtRangePct(v: number | null): string {
  return v == null ? "—" : `${v.toFixed(2)}%`;
}
