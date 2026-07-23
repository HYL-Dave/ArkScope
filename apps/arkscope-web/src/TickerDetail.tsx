// Full-page ticker detail (replaces the cramped right-side panel). Clicking a
// ticker anywhere opens this; the left nav stays visible, the rest of the width
// is the detail. Gives real room for the price/volume chart (reserved area),
// evidence, and the §2 AI card — which the 320px side panel could not.

import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
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
import { ExploreErrorNotice } from "./explore/ExploreErrorNotice";
import {
  captureExploreError,
  type ExploreErrorState,
  type ExploreT,
} from "./explore/explorePresentation";
import type { NavigationTarget } from "./shell/navigation";
import { tagClass, tagKey, tagTitle } from "./tags";

type Tab = "overview" | "data" | "notes" | "ai";

export function TickerDetailView({
  ticker,
  onBack,
  runtime,
  developerMode,
  onNavigateTarget,
}: {
  ticker: string;
  onBack: () => void;
  runtime?: RuntimeConfig | null;
  developerMode: boolean;
  onNavigateTarget: (target: NavigationTarget) => void;
}) {
  const { t } = useTranslation("explore");
  const [tab, setTab] = useState<Tab>("overview");
  const [state, setState] = useState<TickerAggregate | null>(null);
  const [stateErr, setStateErr] = useState<ExploreErrorState | null>(null);

  const refreshState = useCallback(async () => {
    try {
      const d = await getTickerState(ticker);
      setState(d);
      setStateErr(null);
    } catch (e) {
      setStateErr(captureExploreError("ticker_load_state", e));
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
        <button className="btn-ghost" onClick={onBack}>
          {t(($) => $.tickerDetail.backToWatchlist)}
        </button>
        <span className="mono strong detailpage-ticker">{ticker}</span>
        {state?.priority && <span className={`badge p-${state.priority}`}>{state.priority}</span>}
        {state?.archived && (
          <span className="tag-archived">{t(($) => $.tickerDetail.archived)}</span>
        )}
        {state?.lists && state.lists.length > 0 && (
          <span className="chips">
            {state.lists.map((l) => (
              <span key={l} className="list-chip">{l}</span>
            ))}
          </span>
        )}
      </div>

      {stateErr && (
        <ExploreErrorNotice
          state={stateErr}
          developerMode={developerMode}
          retryLabel={t(($) => $.tickerDetail.retry)}
          onRetry={() => void refreshState()}
          onNavigate={onNavigateTarget}
        />
      )}

      {state && (
        <TagManager
          ticker={ticker}
          tags={state.tags ?? []}
          developerMode={developerMode}
          onNavigateTarget={onNavigateTarget}
          onChanged={() => void refreshState()}
        />
      )}

      <div className="detail-tabs">
        <button type="button" className={`tab ${tab === "overview" ? "active" : ""}`} onClick={() => setTab("overview")}>
          {t(($) => $.tickerDetail.overview)}
        </button>
        <button type="button" className={`tab ${tab === "data" ? "active" : ""}`} onClick={() => setTab("data")}>
          {t(($) => $.tickerDetail.data)}
        </button>
        <button type="button" className={`tab ${tab === "notes" ? "active" : ""}`} onClick={() => setTab("notes")}>
          {t(($) => $.tickerDetail.notes)}
          {state && state.note_count > 0
            ? t(($) => $.tickerDetail.noteCount, { count: state.note_count })
            : ""}
        </button>
        <button type="button" className={`tab ${tab === "ai" ? "active" : ""}`} onClick={() => setTab("ai")}>
          {t(($) => $.tickerDetail.aiCard)}
        </button>
      </div>

      {tab === "overview" ? (
        <OverviewTab
          ticker={ticker}
          developerMode={developerMode}
          onNavigateTarget={onNavigateTarget}
        />
      ) : tab === "data" ? (
        <DataTab
          ticker={ticker}
          developerMode={developerMode}
          onNavigateTarget={onNavigateTarget}
        />
      ) : tab === "notes" ? (
        <NotesTab
          ticker={ticker}
          developerMode={developerMode}
          onNavigateTarget={onNavigateTarget}
          onChanged={refreshState}
        />
      ) : (
        <div className="detail-ai-wrap">
          <AICardTab
            ticker={ticker}
            runtime={runtime}
            developerMode={developerMode}
            onNavigateTarget={onNavigateTarget}
          />
        </div>
      )}
    </main>
  );
}

const PRICE_WINDOWS = [5, 7, 30, 90, 365, 3650] as const;
const PRICE_WINDOW_LABEL: Record<number, string> = {
  5: "5D", 7: "7D", 30: "30D", 90: "90D", 365: "1Y", 3650: "Max",
};

function OverviewTab({
  ticker,
  developerMode,
  onNavigateTarget,
}: {
  ticker: string;
  developerMode: boolean;
  onNavigateTarget: (target: NavigationTarget) => void;
}) {
  const { t } = useTranslation("explore");
  const [pc, setPc] = useState<PriceChange | null>(null);
  const [err, setErr] = useState<ExploreErrorState | null>(null);
  const [days, setDays] = useState<number>(30);
  const [reload, setReload] = useState(0);

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
        if (alive) setErr(captureExploreError("ticker_load_price", e));
      }
    })();
    return () => {
      alive = false;
    };
  }, [ticker, days, reload]);

  return (
    <div className="detail-grid">
      <section className="detail-col">
        <div className="detail-pricehead">
          <h4 className="detail-section">
            {t(($) => $.tickerDetail.pricePrefix)}{PRICE_WINDOW_LABEL[days]})
          </h4>
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
        {err && (
          <ExploreErrorNotice
            state={err}
            developerMode={developerMode}
            retryLabel={t(($) => $.tickerDetail.retry)}
            onRetry={() => setReload((current) => current + 1)}
            onNavigate={onNavigateTarget}
          />
        )}
        {!err && !pc && <p className="muted tiny">{t(($) => $.tickerDetail.loading)}</p>}
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
        <h4 className="detail-section">{t(($) => $.tickerDetail.chartTitle)}</h4>
        <div className="chart-placeholder">
          <span className="muted">{t(($) => $.tickerDetail.chartPlanned)}</span>
          <span className="muted tiny">
            {t(($) => $.tickerDetail.chartDescription)}
          </span>
        </div>
      </section>
    </div>
  );
}

// 數據 tab: IV + fundamentals, read-only (re-calls the endpoints — no provider
// fetch). All reads go through the DAL, so they hit the local market DB when
// routing is on and fall back to PG otherwise.
const DATA_OPERATIONS = [
  "ticker_load_iv",
  "ticker_load_iv_history",
  "ticker_load_fundamentals",
  "ticker_load_market_status",
  "ticker_load_coverage",
] as const;

function DataTab({
  ticker,
  developerMode,
  onNavigateTarget,
}: {
  ticker: string;
  developerMode: boolean;
  onNavigateTarget: (target: NavigationTarget) => void;
}) {
  const { t } = useTranslation("explore");
  const [iv, setIv] = useState<IVAnalysis | null>(null);
  const [ivHist, setIvHist] = useState<IVHistoryResult | null>(null);
  const [fund, setFund] = useState<FundamentalsResult | null>(null);
  const [status, setStatus] = useState<MarketDataStatus | null>(null);
  const [coverage, setCoverage] = useState<MarketDataCoverage | null>(null);
  const [loading, setLoading] = useState(true);
  const [errs, setErrs] = useState<ExploreErrorState[]>([]);

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
    setErrs(
      results.flatMap((r, i) =>
        r.status === "rejected"
          ? [captureExploreError(DATA_OPERATIONS[i]!, r.reason)]
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
      ? t(($) => $.tickerDetail.localPreferred)
      : status.use_local_market_setting
        ? t(($) => $.tickerDetail.localPending)
        : t(($) => $.tickerDetail.localDisabled);
  const recentHist = ivHist ? ivHist.points.slice(-30).reverse() : []; // newest first, cap 30

  return (
    <div className="detail-data">
      <section className="detail-col">
        <div className="detail-pricehead">
          <h4 className="detail-section">{t(($) => $.tickerDetail.sourceFreshness)}</h4>
          <button className="btn-ghost" onClick={() => void load()} disabled={loading}>
            {loading
              ? t(($) => $.tickerDetail.reading)
              : t(($) => $.tickerDetail.refresh)}
          </button>
        </div>
        <dl className="kv">
          <Kv k={t(($) => $.tickerDetail.localMarketData)} v={routingLabel} />
          <Kv k={t(($) => $.tickerDetail.ivCurrentSource)} v={sourceLabel(iv?.source_path, t)} />
          <Kv
            k={t(($) => $.tickerDetail.ivLocalCoverage)}
            v={coverage ? coverageLabel(coverage.iv, t) : "—"}
          />
          <Kv
            k={t(($) => $.tickerDetail.fundamentalsCurrentSource)}
            v={sourceLabel(fund?.source_path, t)}
          />
          <Kv
            k={t(($) => $.tickerDetail.fundamentalsLocalCoverage)}
            v={coverage ? coverageLabel(coverage.fundamentals, t) : "—"}
          />
        </dl>
        <p className="muted tiny">
          {t(($) => $.tickerDetail.sourceExplanation)}
        </p>
        {errs.map((error) => (
          <ExploreErrorNotice
            key={error.operation}
            state={error}
            developerMode={developerMode}
            retryLabel={t(($) => $.tickerDetail.retry)}
            onRetry={() => void load()}
            onNavigate={onNavigateTarget}
          />
        ))}
      </section>

      <section className="detail-col">
        <h4 className="detail-section">
          {t(($) => $.tickerDetail.impliedVolatility)}
          {iv?.signal ? (
            <span> {t(($) => $.tickerDetail.ivSignalSuffix, { signal: iv.signal })}</span>
          ) : null}
        </h4>
        {loading && !iv && <p className="muted tiny">{t(($) => $.tickerDetail.loading)}</p>}
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
            <summary>
              {t(($) => $.tickerDetail.ivHistorySummary, {
                count: recentHist.length,
                source: sourceLabel(ivHist?.source_path, t),
              })}
            </summary>
            <table className="data-table">
              <thead>
                <tr>
                  <th>{t(($) => $.tickerDetail.date)}</th>
                  <th>{t(($) => $.tickerDetail.atmIv)}</th>
                  <th>{t(($) => $.tickerDetail.hv30)}</th>
                  <th>{t(($) => $.tickerDetail.vrp)}</th>
                  <th>{t(($) => $.tickerDetail.spot)}</th>
                  <th>{t(($) => $.tickerDetail.quotes)}</th>
                </tr>
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
        {!loading && iv && iv.history_days === 0 && (
          <p className="muted tiny">{t(($) => $.tickerDetail.noIv)}</p>
        )}
      </section>

      <section className="detail-col">
        <h4 className="detail-section">
          {t(($) => $.tickerDetail.fundamentals)}
          {fund && fund.data_source !== "none" ? (
            <span> {t(($) => $.tickerDetail.dataSourceSuffix, { source: fund.data_source })}</span>
          ) : null}
        </h4>
        {loading && !fund && <p className="muted tiny">{t(($) => $.tickerDetail.loading)}</p>}
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
            <StatementsBlock
              title={t(($) => $.tickerDetail.incomeStatements)}
              rows={fund.income_statements}
            />
            <StatementsBlock
              title={t(($) => $.tickerDetail.balanceSheet)}
              rows={fund.balance_sheet}
            />
            <StatementsBlock
              title={t(($) => $.tickerDetail.cashFlow)}
              rows={fund.cash_flow_statements}
            />
            {fund.snapshot && Object.keys(fund.snapshot).length > 0 && (
              <details className="detail-raw">
                <summary>{t(($) => $.tickerDetail.rawSnapshot)}</summary>
                <pre className="raw-json">{JSON.stringify(fund.snapshot, null, 2)}</pre>
              </details>
            )}
          </>
        )}
        {!loading && fund && fund.data_source === "none" && (
          <p className="muted tiny">{t(($) => $.tickerDetail.noFundamentals)}</p>
        )}
      </section>
    </div>
  );
}

// One financial-statement type rendered as metric-rows × period-columns (newest
// first). Collapsed by default; null/empty → nothing.
function StatementsBlock({ title, rows }: { title: string; rows: FinancialStatement[] | null }) {
  const { t } = useTranslation("explore");
  if (!rows || rows.length === 0) return null;
  const keys = Array.from(new Set(rows.flatMap((r) => Object.keys(r.data))));
  return (
    <details className="detail-raw">
      <summary>{t(($) => $.tickerDetail.statementSummary, { title, count: rows.length })}</summary>
      <table className="data-table">
        <thead>
          <tr>
            <th>{t(($) => $.tickerDetail.indicator)}</th>
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

function NotesTab({
  ticker,
  developerMode,
  onNavigateTarget,
  onChanged,
}: {
  ticker: string;
  developerMode: boolean;
  onNavigateTarget: (target: NavigationTarget) => void;
  onChanged?: () => void;
}) {
  const { t } = useTranslation("explore");
  const [notes, setNotes] = useState<Note[] | null>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<ExploreErrorState | null>(null);
  const [failedDeleteId, setFailedDeleteId] = useState<number | null>(null);

  const refresh = useCallback(async () => {
    try {
      const d = await getNotes(ticker);
      setNotes(d.notes);
      setErr(null);
    } catch (e) {
      setErr(captureExploreError("ticker_load_notes", e));
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
      setErr(captureExploreError("ticker_add_note", e));
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: number) {
    setBusy(true);
    setErr(null);
    setFailedDeleteId(id);
    try {
      await deleteNote(ticker, id);
      await refresh();
      onChanged?.();
    } catch (e) {
      setErr(captureExploreError("ticker_delete_note", e));
    } finally {
      setBusy(false);
    }
  }

  function retry() {
    if (!err) return;
    if (err.operation === "ticker_add_note") {
      void submit();
    } else if (err.operation === "ticker_delete_note" && failedDeleteId !== null) {
      void remove(failedDeleteId);
    } else {
      void refresh();
    }
  }

  return (
    <div className="notes detail-notes">
      <textarea
        className="note-input"
        placeholder={t(($) => $.tickerDetail.notePlaceholder, { ticker })}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if ((e.metaKey || e.ctrlKey) && e.key === "Enter") void submit();
        }}
        rows={3}
      />
      <div className="note-actions">
        <span className="muted tiny">{t(($) => $.tickerDetail.saveShortcut)}</span>
        <button type="button" disabled={busy || !draft.trim()} onClick={() => void submit()}>
          {t(($) => $.tickerDetail.addNote)}
        </button>
      </div>
      {err && (
        <ExploreErrorNotice
          state={err}
          developerMode={developerMode}
          retryLabel={t(($) => $.tickerDetail.retry)}
          onRetry={retry}
          onNavigate={onNavigateTarget}
        />
      )}

      {notes === null && !err && <p className="muted tiny">{t(($) => $.tickerDetail.loading)}</p>}
      {notes && notes.length === 0 && (
        <p className="muted tiny">{t(($) => $.tickerDetail.noNotes)}</p>
      )}
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
                  title={t(($) => $.tickerDetail.deleteNote)}
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
  developerMode,
  onNavigateTarget,
  onChanged,
}: {
  ticker: string;
  tags: TagRef[];
  developerMode: boolean;
  onNavigateTarget: (target: NavigationTarget) => void;
  onChanged: () => void;
}) {
  const { t } = useTranslation("explore");
  const [draft, setDraft] = useState("");
  const [facet, setFacet] = useState("theme"); // user tags: theme or category
  const [catalog, setCatalog] = useState<Record<string, string[]>>({});
  const [busy, setBusy] = useState(false);
  const [catalogErr, setCatalogErr] = useState<ExploreErrorState | null>(null);
  const [err, setErr] = useState<ExploreErrorState | null>(null);
  const [failedTag, setFailedTag] = useState<TagRef | null>(null);

  const loadCatalog = useCallback(async () => {
    try {
      setCatalog((await getTagCatalog()).catalog);
      setCatalogErr(null);
    } catch (e) {
      setCatalogErr(captureExploreError("ticker_load_tag_catalog", e));
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
      setErr(captureExploreError("ticker_add_tag", e));
    } finally {
      setBusy(false);
    }
  }

  async function remove(t: TagRef) {
    if (busy) return;
    setBusy(true);
    setErr(null);
    setFailedTag(t);
    try {
      await removeTickerTag(ticker, t.value, t.facet, t.source);
      onChanged();
    } catch (e) {
      setErr(captureExploreError("ticker_remove_tag", e));
    } finally {
      setBusy(false);
    }
  }

  function retryMutation() {
    if (err?.operation === "ticker_remove_tag" && failedTag) {
      void remove(failedTag);
    } else {
      void add();
    }
  }

  const listId = `tagvals-${ticker}`;
  return (
    <div className="detail-tags">
      <span className="chips tagchips">
        {tags.map((tag) => (
          <span key={tagKey(tag)} className={tagClass(tag)} title={tagTitle(tag, t)}>
            {tag.value}
            {isEditableTag(tag) && (
              <button
                type="button"
                className="tagchip-x"
                title={t(($) => $.tickerDetail.removeTag)}
                disabled={busy}
                onClick={() => void remove(tag)}
              >
                ×
              </button>
            )}
          </span>
        ))}
        {tags.length === 0 && (
          <span className="muted tiny">{t(($) => $.tickerDetail.noTags)}</span>
        )}
      </span>
      <span className="tag-add">
        <select
          value={facet}
          disabled={busy}
          onChange={(e) => setFacet(e.target.value)}
          title={t(($) => $.tickerDetail.tagTypeLabel)}
        >
          <option value="theme">{t(($) => $.tickerDetail.theme)}</option>
          <option value="category">{t(($) => $.tickerDetail.sectorCategory)}</option>
          <option value="provenance">{t(($) => $.tickerDetail.source)}</option>
        </select>
        <input
          list={listId}
          placeholder={t(($) => $.tickerDetail.tagInputPlaceholder)}
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
          {t(($) => $.tickerDetail.add)}
        </button>
      </span>
      {catalogErr && (
        <ExploreErrorNotice
          state={catalogErr}
          developerMode={developerMode}
          retryLabel={t(($) => $.tickerDetail.retry)}
          onRetry={() => void loadCatalog()}
          onNavigate={onNavigateTarget}
        />
      )}
      {err && (
        <ExploreErrorNotice
          state={err}
          developerMode={developerMode}
          retryLabel={t(($) => $.tickerDetail.retry)}
          onRetry={retryMutation}
          onNavigate={onNavigateTarget}
        />
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
function sourceLabel(s: SourcePath | string | undefined, t: ExploreT): string {
  switch (s) {
    case "local": return t(($) => $.tickerDetail.sourceLocal);
    case "pg_fallback": return t(($) => $.tickerDetail.sourcePgFallback);
    case "pg": return t(($) => $.tickerDetail.sourcePg);
    case "file": return t(($) => $.tickerDetail.sourceLocalFile);
    case "none": return t(($) => $.tickerDetail.sourceNone);
    default: return s === undefined ? "—" : String(s);
  }
}
function coverageLabel(covered: boolean, t: ExploreT): string {
  return covered
    ? t(($) => $.tickerDetail.yes)
    : t(($) => $.tickerDetail.no);
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
