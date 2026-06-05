import { useCallback, useEffect, useMemo, useState } from "react";
import { getOverview, getPriceChange, type PriceChange, type WatchlistRow } from "./api";

type State =
  | { kind: "loading" }
  | { kind: "ready"; rows: WatchlistRow[]; date: string }
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

export function WatchlistView() {
  const [state, setState] = useState<State>({ kind: "loading" });
  const [selected, setSelected] = useState<WatchlistRow | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("change_7d_pct");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [refreshing, setRefreshing] = useState(false);
  const [refreshError, setRefreshError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setRefreshing(true);
    setRefreshError(null);
    try {
      const o = await getOverview();
      setState({ kind: "ready", rows: o.tickers, date: o.date });
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      // Keep an already-loaded table visible on a transient refresh failure;
      // only fall back to the full error screen on the initial load.
      setState((prev) => (prev.kind === "ready" ? prev : { kind: "error", message }));
      setRefreshError(message);
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const rows = state.kind === "ready" ? state.rows : [];
  const sorted = useMemo(() => sortRows(rows, sortKey, sortDir), [rows, sortKey, sortDir]);

  function toggleSort(k: SortKey) {
    if (k === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(k);
      setSortDir(k === "ticker" || k === "priority" ? "asc" : "desc");
    }
  }

  const thProps = { sortKey, sortDir, toggleSort };

  return (
    <>
      <main className="main">
        {state.kind === "loading" && <p className="muted">Loading watchlist…</p>}
        {state.kind === "error" && (
          <div className="errorbox">
            <p>Could not load the watchlist (/overview).</p>
            <p className="muted">{state.message}</p>
          </div>
        )}
        {state.kind === "ready" && (
          <>
            <div className="surface-head">
              <h2 className="surface-title">Watchlist</h2>
              <span className="muted">
                {state.rows.length} tickers · as of {state.date}
              </span>
              <span className="spacer" />
              {refreshError && (
                <span className="refresh-err" title={refreshError}>
                  refresh failed
                </span>
              )}
              <button className="btn-ghost" onClick={() => void load()} disabled={refreshing}>
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
                    className={selected?.ticker === r.ticker ? "sel" : ""}
                    onClick={() => setSelected(r)}
                  >
                    <td className="mono strong">{r.ticker}</td>
                    <td className="num">{fmtNum(r.latest_close)}</td>
                    <td className={`num ${changeClass(r.change_7d_pct)}`}>{fmtPct(r.change_7d_pct)}</td>
                    <td className="num">{r.news_count_7d}</td>
                    <td className="num">{fmtSent(r.sentiment_mean)}</td>
                    <td>
                      <span className={`badge p-${r.priority}`}>{r.priority}</span>
                    </td>
                    <td className="wl-actions" onClick={(e) => e.stopPropagation()}>
                      <RowActions />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <p className="muted tiny">
              Row actions (star / note / tag / archive) are placeholders — lifecycle persistence
              (profile_state_write) lands with the profile/Settings surface.
            </p>
          </>
        )}
      </main>

      <aside className="rightpanel detail">
        {selected ? (
          <TickerDetail row={selected} />
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

function RowActions() {
  // Placeholder affordances; the parent <td> stops row-selection propagation.
  return (
    <span className="rowactions" title="lifecycle actions — coming with the profile surface">
      <button type="button" aria-label="star">☆</button>
      <button type="button" aria-label="note">📝</button>
      <button type="button" aria-label="tag">🏷</button>
      <button type="button" aria-label="archive">🗄</button>
    </span>
  );
}

function TickerDetail({ row }: { row: WatchlistRow }) {
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
    <div className="detailpane">
      <div className="detail-head">
        <span className="mono strong big">{row.ticker}</span>
        <span className={`badge p-${row.priority}`}>{row.priority}</span>
      </div>
      <div className="muted tiny">{row.group}</div>

      <div className="detail-tabs">
        {["Overview", "Notes", "Related news", "AI summary"].map((t, i) => (
          <span key={t} className={`tab ${i === 0 ? "active" : "disabled"}`}>
            {t}
          </span>
        ))}
      </div>

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

      <h4 className="detail-section">Actions</h4>
      <p className="muted tiny">
        analyze · summarize · add to thesis · generate note — agent wiring deferred.
      </p>
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

function sortRows(rows: WatchlistRow[], key: SortKey, dir: SortDir): WatchlistRow[] {
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
