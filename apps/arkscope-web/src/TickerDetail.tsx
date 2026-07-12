// Full-page ticker detail (replaces the cramped right-side panel). Clicking a
// ticker anywhere opens this; the left nav stays visible, the rest of the width
// is the detail. Gives real room for the price/volume chart (reserved area),
// evidence, and the §2 AI card — which the 320px side panel could not.

import { useCallback, useEffect, useState } from "react";
import {
  addNote,
  addTickerTag,
  deleteNote,
  getStoredFundamentals,
  getIvAnalysis,
  getIvHistory,
  getMarketDataCoverage,
  getMarketDataStatus,
  getTagCatalog,
  getTickerState,
  getNotes,
  getPriceChange,
  isEditableTag,
  removeTickerTag,
  type FinancialStatement,
  type FundamentalsResult,
  type IVAnalysis,
  type IVHistoryResult,
  type MarketDataCoverage,
  type MarketDataStatus,
  type Note,
  type SourcePath,
  type PriceChange,
  type RuntimeConfig,
  type TagRef,
  type TickerAggregate,
} from "./api";
import { AICardTab } from "./AICard";
import { tagClass, tagKey, tagTitle } from "./tags";

type Tab = "overview" | "data" | "notes" | "ai";

export function TickerDetailView({
  ticker,
  onBack,
  runtime,
}: {
  ticker: string;
  onBack: () => void;
  runtime?: RuntimeConfig | null;
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

      {state && (
        <TagManager ticker={ticker} tags={state.tags ?? []} onChanged={() => void refreshState()} />
      )}

      <div className="detail-tabs">
        <button type="button" className={`tab ${tab === "overview" ? "active" : ""}`} onClick={() => setTab("overview")}>
          總覽
        </button>
        <button type="button" className={`tab ${tab === "data" ? "active" : ""}`} onClick={() => setTab("data")}>
          數據
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
      ) : tab === "data" ? (
        <DataTab ticker={ticker} />
      ) : tab === "notes" ? (
        <NotesTab ticker={ticker} onChanged={refreshState} />
      ) : (
        <div className="detail-ai-wrap">
          <AICardTab ticker={ticker} runtime={runtime} />
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

// 數據 tab: IV + fundamentals, read-only (re-calls the endpoints — no provider
// fetch). All reads go through the DAL, so they hit the local market DB when
// routing is on and fall back to PG otherwise.
function DataTab({ ticker }: { ticker: string }) {
  const [iv, setIv] = useState<IVAnalysis | null>(null);
  const [ivHist, setIvHist] = useState<IVHistoryResult | null>(null);
  const [fund, setFund] = useState<FundamentalsResult | null>(null);
  const [status, setStatus] = useState<MarketDataStatus | null>(null);
  const [coverage, setCoverage] = useState<MarketDataCoverage | null>(null);
  const [loading, setLoading] = useState(true);
  const [errs, setErrs] = useState<string[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    setErrs([]);
    // Independent reads: one failure (e.g. no IV data) must not blank the others.
    const results = await Promise.allSettled([
      getIvAnalysis(ticker),
      getIvHistory(ticker),
      getStoredFundamentals(ticker),
      getMarketDataStatus(),
      getMarketDataCoverage(ticker),
    ]);
    const [rIv, rHist, rFund, rStatus, rCov] = results;
    setIv(rIv.status === "fulfilled" ? rIv.value : null);
    setIvHist(rHist.status === "fulfilled" ? rHist.value : null);
    setFund(rFund.status === "fulfilled" ? rFund.value : null);
    setStatus(rStatus.status === "fulfilled" ? rStatus.value : null);
    setCoverage(rCov.status === "fulfilled" ? rCov.value : null);
    const labels = ["IV", "IV 歷史", "基本面", "狀態", "覆蓋"];
    setErrs(
      results.flatMap((r, i) =>
        r.status === "rejected"
          ? [`${labels[i]}: ${r.reason instanceof Error ? r.reason.message : String(r.reason)}`]
          : [],
      ),
    );
    setLoading(false);
  }, [ticker]);

  useEffect(() => {
    void load();
  }, [load]);

  const routingLabel = !status
    ? "—"
    : status.routing_enabled
      ? "啟用中（本地優先，缺資料回 PG）"
      : status.use_local_market_setting
        ? "設定已開，待建立本地庫（目前用 PG）"
        : "關閉（使用 PG）";
  const recentHist = ivHist ? ivHist.points.slice(-30).reverse() : []; // newest first, cap 30

  return (
    <div className="detail-data">
      <section className="detail-col">
        <div className="detail-pricehead">
          <h4 className="detail-section">資料來源 / 新鮮度</h4>
          <button className="btn-ghost" onClick={() => void load()} disabled={loading}>
            {loading ? "讀取中…" : "↻ 重新整理"}
          </button>
        </div>
        <dl className="kv">
          <Kv k="本地市場資料" v={routingLabel} />
          <Kv k="IV · 本次來源" v={sourceLabel(iv?.source_path)} />
          <Kv k="IV · 本地覆蓋" v={coverage ? (coverage.iv ? "有" : "無") : "—"} />
          <Kv k="基本面 · 本次來源" v={sourceLabel(fund?.source_path)} />
          <Kv k="基本面 · 本地覆蓋" v={coverage ? (coverage.fundamentals ? "有" : "無") : "—"} />
        </dl>
        <p className="muted tiny">
          「本次來源」= 此次讀取的真實來源（本地命中 / PG 回退 / PG / 無）；「本地覆蓋」= 本地市場庫是否存有此標的的列。
        </p>
        {errs.length > 0 && <p className="muted tiny">部分資料無法載入：{errs.join("；")}</p>}
      </section>

      <section className="detail-col">
        <h4 className="detail-section">隱含波動率 IV{iv?.signal ? ` · ${iv.signal}` : ""}</h4>
        {loading && !iv && <p className="muted tiny">loading…</p>}
        {iv && (
          <dl className="kv">
            <Kv k="Current ATM IV" v={fmtNum(iv.current_iv)} />
            <Kv k="HV 30d" v={fmtNum(iv.hv_30d)} />
            <Kv k="VRP (IV−HV)" v={fmtNum(iv.vrp)} />
            <Kv k="IV rank" v={fmtNum(iv.iv_rank)} />
            <Kv k="IV percentile" v={fmtNum(iv.iv_percentile)} />
            <Kv k="Spot" v={fmtNum(iv.spot_price)} />
            <Kv k="History days" v={String(iv.history_days)} />
          </dl>
        )}
        {recentHist.length > 0 && (
          <details className="detail-raw">
            {/* the history table is its own request → label it with its OWN source */}
            <summary>IV 歷史（最近 {recentHist.length} 筆 · 來源 {sourceLabel(ivHist?.source_path)}）</summary>
            <table className="data-table">
              <thead>
                <tr><th>日期</th><th>ATM IV</th><th>HV30</th><th>VRP</th><th>Spot</th><th>Quotes</th></tr>
              </thead>
              <tbody>
                {recentHist.map((p) => (
                  <tr key={p.date}>
                    <td>{p.date}</td>
                    <td>{fmtNum(p.atm_iv)}</td>
                    <td>{fmtNum(p.hv_30d)}</td>
                    <td>{fmtNum(p.vrp)}</td>
                    <td>{fmtNum(p.spot_price)}</td>
                    <td>{p.num_quotes ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>
        )}
        {!loading && iv && iv.history_days === 0 && <p className="muted tiny">無 IV 資料。</p>}
      </section>

      <section className="detail-col">
        <h4 className="detail-section">
          基本面{fund && fund.data_source !== "none" ? ` · ${fund.data_source}` : ""}
        </h4>
        {loading && !fund && <p className="muted tiny">loading…</p>}
        {fund && (
          <>
            <dl className="kv">
              <Kv k="Snapshot date" v={fund.snapshot_date ?? "—"} />
              <Kv k="Market cap" v={fmtNum(fund.market_cap)} />
              <Kv k="P/E" v={fmtNum(fund.pe_ratio)} />
              <Kv k="Forward P/E" v={fmtNum(fund.forward_pe)} />
              <Kv k="P/S" v={fmtNum(fund.ps_ratio)} />
              <Kv k="P/B" v={fmtNum(fund.pb_ratio)} />
              <Kv k="ROE" v={fmtNum(fund.roe)} />
              <Kv k="ROA" v={fmtNum(fund.roa)} />
              <Kv k="D/E" v={fmtNum(fund.debt_to_equity)} />
              <Kv k="Current ratio" v={fmtNum(fund.current_ratio)} />
              <Kv k="Gross margin" v={fmtNum(fund.gross_margin)} />
              <Kv k="Operating margin" v={fmtNum(fund.operating_margin)} />
              <Kv k="Net margin" v={fmtNum(fund.net_margin)} />
              <Kv k="Revenue growth" v={fmtNum(fund.revenue_growth)} />
              <Kv k="Earnings growth" v={fmtNum(fund.earnings_growth)} />
              <Kv k="Dividend yield" v={fmtNum(fund.dividend_yield)} />
              <Kv k="Beta" v={fmtNum(fund.beta)} />
              <Kv k="Free cash flow" v={fmtNum(fund.free_cash_flow)} />
              <Kv k="Cash & equiv." v={fmtNum(fund.cash_and_equivalents)} />
              <Kv k="Total debt" v={fmtNum(fund.total_debt)} />
            </dl>
            <StatementsBlock title="Income statements" rows={fund.income_statements} />
            <StatementsBlock title="Balance sheet" rows={fund.balance_sheet} />
            <StatementsBlock title="Cash flow" rows={fund.cash_flow_statements} />
            {fund.snapshot && Object.keys(fund.snapshot).length > 0 && (
              <details className="detail-raw">
                <summary>Raw snapshot</summary>
                <pre className="raw-json">{JSON.stringify(fund.snapshot, null, 2)}</pre>
              </details>
            )}
          </>
        )}
        {!loading && fund && fund.data_source === "none" && <p className="muted tiny">無基本面資料。</p>}
      </section>
    </div>
  );
}

// One financial-statement type rendered as metric-rows × period-columns (newest
// first). Collapsed by default; null/empty → nothing.
function StatementsBlock({ title, rows }: { title: string; rows: FinancialStatement[] | null }) {
  if (!rows || rows.length === 0) return null;
  const keys = Array.from(new Set(rows.flatMap((r) => Object.keys(r.data))));
  return (
    <details className="detail-raw">
      <summary>{title}（{rows.length} 期）</summary>
      <table className="data-table">
        <thead>
          <tr>
            <th>指標</th>
            {rows.map((r) => <th key={r.report_period}>{r.fiscal_period ?? r.report_period}</th>)}
          </tr>
        </thead>
        <tbody>
          {keys.map((k) => (
            <tr key={k}>
              <td>{k}</td>
              {rows.map((r) => <td key={r.report_period}>{fmtNum(r.data[k] ?? null)}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </details>
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

// Tag management surface. config:* tags render read-only (owned by import);
// only source="user" tags get a × remove. A small "＋標籤" input adds user tags.
function TagManager({
  ticker,
  tags,
  onChanged,
}: {
  ticker: string;
  tags: TagRef[];
  onChanged: () => void;
}) {
  const [draft, setDraft] = useState("");
  const [facet, setFacet] = useState("theme"); // user tags: theme or category
  const [catalog, setCatalog] = useState<Record<string, string[]>>({});
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const loadCatalog = useCallback(async () => {
    try {
      setCatalog((await getTagCatalog()).catalog);
    } catch {
      /* picker just falls back to free-text */
    }
  }, []);
  useEffect(() => {
    void loadCatalog();
  }, [loadCatalog]);

  async function add() {
    const value = draft.trim();
    if (!value || busy) return;
    setBusy(true);
    setErr(null);
    try {
      await addTickerTag(ticker, value, facet); // user tag on the chosen facet
      setDraft("");
      onChanged();
      void loadCatalog(); // a new value becomes pickable next time
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function remove(t: TagRef) {
    if (busy) return;
    setBusy(true);
    setErr(null);
    try {
      await removeTickerTag(ticker, t.value, t.facet, t.source);
      onChanged();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const listId = `tagvals-${ticker}`;
  return (
    <div className="detail-tags">
      <span className="chips tagchips">
        {tags.map((t) => (
          <span key={tagKey(t)} className={tagClass(t)} title={tagTitle(t)}>
            {t.value}
            {isEditableTag(t) && (
              <button
                type="button"
                className="tagchip-x"
                title="移除標籤"
                disabled={busy}
                onClick={() => void remove(t)}
              >
                ×
              </button>
            )}
          </span>
        ))}
        {tags.length === 0 && <span className="muted tiny">尚無標籤</span>}
      </span>
      <span className="tag-add">
        <select value={facet} disabled={busy} onChange={(e) => setFacet(e.target.value)} title="標籤類型">
          <option value="theme">主題</option>
          <option value="category">板塊/類別</option>
          <option value="provenance">來源</option>
        </select>
        <input
          list={listId}
          placeholder="＋標籤（可挑現有或新建）"
          value={draft}
          disabled={busy}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void add();
          }}
        />
        <datalist id={listId}>
          {(catalog[facet] ?? []).map((v) => (
            <option key={v} value={v} />
          ))}
        </datalist>
        <button className="btn-ghost tiny" disabled={busy || !draft.trim()} onClick={() => void add()}>
          新增
        </button>
      </span>
      {err && <span className="refresh-err tiny">{err}</span>}
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
function sourceLabel(s: SourcePath | undefined): string {
  switch (s) {
    case "local": return "本地";
    case "pg_fallback": return "PG（本地缺→回退）";
    case "pg": return "PG";
    case "file": return "本地檔案";
    case "none": return "無資料";
    default: return "—";
  }
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
