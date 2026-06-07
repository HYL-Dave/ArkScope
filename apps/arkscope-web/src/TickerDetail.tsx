// Full-page ticker detail (replaces the cramped right-side panel). Clicking a
// ticker anywhere opens this; the left nav stays visible, the rest of the width
// is the detail. Gives real room for the price/volume chart (reserved area),
// evidence, and the §2 AI card — which the 320px side panel could not.

import { useCallback, useEffect, useState } from "react";
import {
  addNote,
  deleteNote,
  getTickerState,
  getNotes,
  getPriceChange,
  type Note,
  type PriceChange,
  type TickerAggregate,
} from "./api";
import { AICardTab } from "./AICard";

type Tab = "overview" | "notes" | "ai";

export function TickerDetailView({
  ticker,
  onBack,
}: {
  ticker: string;
  onBack: () => void;
}) {
  const [tab, setTab] = useState<Tab>("overview");
  const [state, setState] = useState<TickerAggregate | null>(null);
  const [stateErr, setStateErr] = useState<string | null>(null);

  const refreshState = useCallback(async () => {
    try {
      const d = await getTickerState(ticker);
      setState(d);
      setStateErr(null);
    } catch (e) {
      setStateErr(e instanceof Error ? e.message : String(e));
    }
  }, [ticker]);

  useEffect(() => {
    setState(null);
    setStateErr(null);
    void refreshState();
  }, [refreshState]);

  return (
    <main className="main detail-full">
      <div className="detailpage-head">
        <button className="btn-ghost" onClick={onBack}>← 自選股</button>
        <span className="mono strong detailpage-ticker">{ticker}</span>
        {state?.priority && <span className={`badge p-${state.priority}`}>{state.priority}</span>}
        {state?.archived && <span className="tag-archived">archived</span>}
        {state?.lists && state.lists.length > 0 && (
          <span className="chips">
            {state.lists.map((l) => (
              <span key={l} className="list-chip">{l}</span>
            ))}
          </span>
        )}
        {stateErr && <span className="refresh-err tiny">{stateErr}</span>}
      </div>

      <div className="detail-tabs">
        <button type="button" className={`tab ${tab === "overview" ? "active" : ""}`} onClick={() => setTab("overview")}>
          總覽
        </button>
        <button type="button" className={`tab ${tab === "notes" ? "active" : ""}`} onClick={() => setTab("notes")}>
          筆記{state && state.note_count > 0 ? `（${state.note_count}）` : ""}
        </button>
        <button type="button" className={`tab ${tab === "ai" ? "active" : ""}`} onClick={() => setTab("ai")}>
          AI 卡片
        </button>
      </div>

      {tab === "overview" ? (
        <OverviewTab ticker={ticker} />
      ) : tab === "notes" ? (
        <NotesTab ticker={ticker} onChanged={refreshState} />
      ) : (
        <div className="detail-ai-wrap">
          <AICardTab ticker={ticker} />
        </div>
      )}
    </main>
  );
}

const PRICE_WINDOWS = [5, 7, 30, 90, 365, 3650] as const;
const PRICE_WINDOW_LABEL: Record<number, string> = {
  5: "5D", 7: "7D", 30: "30D", 90: "90D", 365: "1Y", 3650: "Max",
};

function OverviewTab({ ticker }: { ticker: string }) {
  const [pc, setPc] = useState<PriceChange | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [days, setDays] = useState<number>(30);

  // Refetch when ticker OR the selected window changes; drop stale responses.
  useEffect(() => {
    let alive = true;
    setPc(null);
    setErr(null);
    (async () => {
      try {
        const d = await getPriceChange(ticker, days);
        if (alive) setPc(d);
      } catch (e) {
        if (alive) setErr(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      alive = false;
    };
  }, [ticker, days]);

  return (
    <div className="detail-grid">
      <section className="detail-col">
        <div className="detail-pricehead">
          <h4 className="detail-section">Price ({PRICE_WINDOW_LABEL[days]})</h4>
          <span className="price-windows">
            {PRICE_WINDOWS.map((d) => (
              <button
                key={d}
                className={`price-win ${days === d ? "active" : ""}`}
                onClick={() => setDays(d)}
              >
                {PRICE_WINDOW_LABEL[d]}
              </button>
            ))}
          </span>
        </div>
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
      </section>

      <section className="detail-col">
        <h4 className="detail-section">圖表（price / volume）</h4>
        <div className="chart-placeholder">
          <span className="muted">圖表元件規劃中</span>
          <span className="muted tiny">
            price / volume / range / 多窗報酬 — 之後接 IBKR 即時與歷史 OHLCV
          </span>
        </div>
      </section>
    </div>
  );
}

function NotesTab({ ticker, onChanged }: { ticker: string; onChanged?: () => void }) {
  const [notes, setNotes] = useState<Note[] | null>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const d = await getNotes(ticker);
      setNotes(d.notes);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }, [ticker]);

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
      onChanged?.();
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
      onChanged?.();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="notes detail-notes">
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

// ---- local formatters (kept self-contained; Watchlist has its own copies) ----

function fmtNum(v: number | null): string {
  return v == null ? "—" : v.toLocaleString(undefined, { maximumFractionDigits: 2 });
}
function fmtPct(v: number | null): string {
  return v == null ? "—" : `${v > 0 ? "+" : ""}${v.toFixed(2)}%`;
}
function changeClass(v: number | null): string {
  return v == null ? "" : v > 0 ? "up" : v < 0 ? "down" : "";
}
function fmtRangePct(v: number | null): string {
  return v == null ? "—" : `${v.toFixed(2)}%`;
}
