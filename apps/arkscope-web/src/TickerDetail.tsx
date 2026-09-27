// Full-page ticker detail (replaces the cramped right-side panel). Clicking a
// ticker anywhere opens this; the left nav stays visible, the rest of the width
// is the detail. Gives real room for the price/volume chart (reserved area),
// evidence, and the §2 AI card — which the 320px side panel could not.

import { useCallback, useEffect, useRef, useState, type MutableRefObject } from "react";
import { useTranslation } from "react-i18next";
import {
  addNote,
  addTickerTag,
  deleteNote,
  getStoredFundamentals,
  refreshFinancials,
  getSAAcquisitionStatus,
  ApiError,
  type FinancialReadQuery,
  type FinancialPeriod,
  type SAAcquisitionStatus,
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
  type MarketDataCoverage,
  type MarketDataStatus,
  type Note,
  type PriceChange,
  type RuntimeConfig,
  type TagRef,
  type TickerAggregate,
} from "./api";
import { AICardTab, type CardRecoveryDraft } from "./AICard";
import { ExploreErrorNotice } from "./explore/ExploreErrorNotice";
import {
  captureExploreError,
  type ExploreErrorState,
} from "./explore/explorePresentation";
import type { NavigationTarget } from "./shell/navigation";
import { tagClass, tagKey, tagTitle } from "./tags";
import { ArrowLeft, ArrowRight, ExternalLink, RefreshCw, Settings2 } from "lucide-react";
import { Button, IconButton } from "./ui/Button";
import { ConfirmDialog } from "./ui/ConfirmDialog";
import { financialText } from "./settings/FinancialCoverageSection";
import { RecordedTimestamp } from "./settings/RecordedTimestamp";
import type { SettingsReadCache } from "./settings/settingsReadCache";

type Tab = "overview" | "data" | "notes" | "ai";

export function TickerDetailView({
  ticker,
  onBack,
  runtime,
  developerMode,
  onNavigateTarget,
  cardRecoveryDraftRef,
  settingsReadCache,
}: {
  ticker: string;
  onBack: () => void;
  runtime?: RuntimeConfig | null;
  developerMode: boolean;
  onNavigateTarget: (target: NavigationTarget) => void;
  cardRecoveryDraftRef?: MutableRefObject<CardRecoveryDraft | null>;
  settingsReadCache?: SettingsReadCache;
}) {
  const { t } = useTranslation("explore");
  const [tab, setTab] = useState<Tab>("overview");
  const [state, setState] = useState<TickerAggregate | null>(null);
  const [stateErr, setStateErr] = useState<ExploreErrorState | null>(null);
  const stateRequestSeqRef = useRef(0);

  const refreshState = useCallback(async () => {
    const requestSeq = ++stateRequestSeqRef.current;
    try {
      const d = await getTickerState(ticker);
      if (requestSeq !== stateRequestSeqRef.current) return;
      setState(d);
      setStateErr(null);
    } catch (e) {
      if (requestSeq === stateRequestSeqRef.current) {
        setStateErr(captureExploreError("ticker_load_state", e));
      }
    }
  }, [ticker]);

  useEffect(() => {
    setState(null);
    setStateErr(null);
    void refreshState();
    return () => {
      stateRequestSeqRef.current += 1;
    };
  }, [refreshState]);

  return (
    <main className="main detail-full">
      <div className="detailpage-head">
        <button className="btn-ghost" onClick={onBack}>
          {t(($) => $.tickerDetail.backToWatchlist)}
        </button>
        <span className="mono strong detailpage-ticker">{ticker}</span>
        <button className="btn-ghost" onClick={() => onNavigateTarget({ kind: "universe_lifecycle", ticker })}>
          {t(($) => $.investigation.title)}
        </button>
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

      {state && (state.lineage.predecessors.length > 0 || state.lineage.successors.length > 0) ? (
        <div className="lifecycle-assessment-facts" aria-label={t(($) => $.tickerDetail.lineage)}>
          {state.lineage.predecessors.length > 0 ? (
            <div>
              <strong>{t(($) => $.tickerDetail.predecessors)}</strong>
              <span className="chips">
                {state.lineage.predecessors.map((item) => (
                  <button
                    className="btn-ghost mono"
                    key={item.transition_id}
                    type="button"
                    onClick={() => onNavigateTarget({ kind: "ticker", ticker: item.ticker })}
                  >
                    {item.ticker}
                  </button>
                ))}
              </span>
            </div>
          ) : null}
          {state.lineage.successors.length > 0 ? (
            <div>
              <strong>{t(($) => $.tickerDetail.successors)}</strong>
              <span className="chips">
                {state.lineage.successors.map((item) => (
                  <button
                    className="btn-ghost mono"
                    key={item.transition_id}
                    type="button"
                    onClick={() => onNavigateTarget({ kind: "ticker", ticker: item.ticker })}
                  >
                    {item.ticker}
                  </button>
                ))}
              </span>
            </div>
          ) : null}
        </div>
      ) : null}

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
          settingsReadCache={settingsReadCache}
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
            recoveryDraftRef={cardRecoveryDraftRef}
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
            <Kv k={t(($) => $.tickerDetail.kvLabels.latestClose)} v={fmtNum(pc.latest_close)} />
            <Kv
              k={t(($) => $.tickerDetail.kvLabels.changePercent)}
              v={fmtPct(pc.change_pct)}
              cls={changeClass(pc.change_pct)}
            />
            <Kv k={t(($) => $.tickerDetail.kvLabels.periodHigh)} v={fmtNum(pc.period_high)} />
            <Kv k={t(($) => $.tickerDetail.kvLabels.periodLow)} v={fmtNum(pc.period_low)} />
            <Kv
              k={t(($) => $.tickerDetail.kvLabels.rangePercent)}
              v={fmtRangePct(pc.high_low_range_pct)}
            />
            <Kv k={t(($) => $.tickerDetail.kvLabels.volume)} v={fmtNum(pc.total_volume)} />
            <Kv k={t(($) => $.tickerDetail.kvLabels.bars)} v={String(pc.bar_count)} />
            <Kv k={t(($) => $.tickerDetail.kvLabels.dates)} v={pc.date_range} />
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

// Data tab: stored fundamentals and local coverage, read-only. Opening or
// refreshing this surface never triggers a provider fetch.
const DATA_OPERATIONS = [
  "ticker_load_fundamentals",
  "ticker_load_market_status",
  "ticker_load_coverage",
] as const;

function DataTab({
  ticker, developerMode, onNavigateTarget, settingsReadCache,
}: {
  ticker: string; developerMode: boolean;
  onNavigateTarget: (target: NavigationTarget) => void;
  settingsReadCache?: SettingsReadCache;
}) {
  const { t } = useTranslation("explore");
  const { t: ft } = useTranslation("settings");
  const [source, setSource] = useState<FinancialReadQuery["source"]>("auto");
  const [period, setPeriod] = useState<FinancialPeriod>("annual");
  const [fund, setFund] = useState<FundamentalsResult | null>(null);
  const [status, setStatus] = useState<MarketDataStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [errs, setErrs] = useState<ExploreErrorState[]>([]);
  const [changed, setChanged] = useState(false);
  const [confirmUpdate, setConfirmUpdate] = useState(false);
  const [updating, setUpdating] = useState(false);
  const [updateResult, setUpdateResult] = useState<FundamentalsResult | "error" | null>(null);
  const [collector, setCollector] = useState<SAAcquisitionStatus | null>(null);
  const sequence = useRef(0);
  const updateRunning = useRef(false);
  const updateButton = useRef<HTMLButtonElement>(null);

  const load = useCallback(async (offset = 0, readId?: string) => {
    const request = ++sequence.current;
    setLoading(true); setErrs([]); setChanged(false);
    const results = await Promise.allSettled([
      getStoredFundamentals(ticker, { source, period, currency: "USD", period_offset: offset, read_id: readId }),
      getMarketDataStatus(), getMarketDataCoverage(ticker),
    ]);
    if (request !== sequence.current) return;
    const [financial, market] = results;
    if (financial.status === "fulfilled") setFund(financial.value);
    else if (financial.reason instanceof ApiError && financial.reason.status === 409) setChanged(true);
    setStatus(market.status === "fulfilled" ? market.value : null);
    setErrs(results.flatMap((r, i) => r.status === "rejected"
      ? [captureExploreError(DATA_OPERATIONS[i]!, r.reason)] : []));
    setLoading(false);
  }, [ticker, source, period]);

  useEffect(() => {
    setFund(null); setUpdateResult(null); setCollector(null); setConfirmUpdate(false);
    void load();
    return () => { sequence.current += 1; };
  }, [load]);

  async function update() {
    if (source !== "financial_datasets" || updateRunning.current) return;
    updateRunning.current = true;
    const request = ++sequence.current;
    setUpdating(true); setUpdateResult(null); setLoading(false);
    try {
      const result = await refreshFinancials(ticker, { source: "financial_datasets", period, currency: "USD" });
      if (result.read_id) settingsReadCache?.invalidateFinancialReads();
      if (request !== sequence.current) return;
      setUpdateResult(result);
      if (result.status !== "unavailable" && result.read_id) setFund(result);
    } catch {
      if (request === sequence.current) setUpdateResult("error");
    } finally {
      updateRunning.current = false;
      setUpdating(false); setConfirmUpdate(false);
    }
  }

  async function inspectCollector() {
    const request = sequence.current;
    try {
      const result = await getSAAcquisitionStatus();
      if (request === sequence.current) setCollector(result);
    } catch {
      if (request === sequence.current) setCollector({ status: "error" });
    }
  }

  const routingLabel = !status ? "—" : status.routing_enabled
    ? t(($) => $.tickerDetail.localPreferred) : status.use_local_market_setting
      ? t(($) => $.tickerDetail.localPending) : t(($) => $.tickerDetail.localDisabled);
  const metric = (name: string) => {
    const value = fund?.[name as keyof FundamentalsResult];
    if (typeof value !== "number") return financialText(ft, "gaps", fund?.metric_gaps?.[name] ?? "inputs_unavailable");
    const basis = fund?.metric_basis[name];
    const context = basis ? [basis.report_period ?? basis.end_month, basis.currency,
      typeof basis.precision === "string" ? financialText(ft, "precision", basis.precision) : null]
      .filter((item): item is string => typeof item === "string").join(" / ") : "";
    return context ? `${fmtNum(value)} (${context})` : fmtNum(value);
  };
  const sa = fund?.update_choices?.find((choice) => choice.provider === "seeking_alpha");
  const fd = fund?.update_choices?.find((choice) => choice.provider === "financial_datasets");
  const previous = updateResult === "error" || updateResult?.status === "unavailable";
  const financialPause = collector?.capability_pauses?.financials;
  const pauseReason = collector?.paused_reason
    || (typeof financialPause === "string" ? financialPause : null);
  return <div className="detail-data financial-reader">
    <section className="detail-col">
      <div className="detail-pricehead">
        <h4 className="detail-section">{t(($) => $.tickerDetail.sourceFreshness)}</h4>
        <IconButton label={t(($) => $.tickerDetail.refresh)} icon={<RefreshCw size={16} />}
          disabled={loading || updating} onClick={() => void load()} />
      </div>
      <div className="financial-controls">
        <label>{ft(($) => $.financialCoverage.source)}
          <select aria-label={ft(($) => $.financialCoverage.source)} value={source}
            onChange={(e) => setSource(e.target.value as FinancialReadQuery["source"])}>
            {["auto", "seeking_alpha", "financial_datasets"].map((value) =>
              <option key={value} value={value}>{financialText(ft, "sources", value)}</option>)}
          </select>
        </label>
        <label>{ft(($) => $.financialCoverage.period)}
          <select aria-label={ft(($) => $.financialCoverage.period)} value={period}
            onChange={(e) => setPeriod(e.target.value as FinancialPeriod)}>
            <option value="annual">{ft(($) => $.financialCoverage.annual)}</option>
            <option value="quarterly">{ft(($) => $.financialCoverage.quarterly)}</option>
          </select>
        </label>
      </div>
      <dl className="kv">
        <Kv k={t(($) => $.tickerDetail.localMarketData)} v={routingLabel} />
        <Kv k={t(($) => $.tickerDetail.fundamentalsCurrentSource)} v={financialText(ft, "sources", fund?.data_source ?? "none")} />
        <Kv k={t(($) => $.tickerDetail.fundamentalsLocalCoverage)} v={financialText(ft, "states", fund?.status ?? "unavailable")} />
      </dl>
      {fund?.source_routes?.map((route, index) => <p key={index} className="muted tiny">
        {ft(($) => $.financialCoverage.configuredSources, { value: route.configured_sources.map((p) => financialText(ft, "sources", p)).join(", ") })}
      </p>)}
      {fund?.read_gaps?.filter((g) => !g.metric).map((gap, index) =>
        <p key={index} className="refresh-err">{financialText(ft, "gaps", gap.code)}</p>)}
      <div className="financial-actions">
        <IconButton label={ft(($) => $.financialCoverage.settings)} icon={<Settings2 size={16} />}
          onClick={() => onNavigateTarget({ kind: "settings_section", section: "data_sources" })} />
        {source === "financial_datasets" && fd ? <Button ref={updateButton} icon={<RefreshCw size={14} />}
          disabled={loading || updating} onClick={() => setConfirmUpdate(true)}>{ft(($) => $.financialCoverage.fdUpdate)}</Button> : null}
        {sa ? <Button icon={<ExternalLink size={14} />} onClick={() => void inspectCollector()}>
          {ft(($) => $.financialCoverage.browser)}</Button> : null}
      </div>
      {collector ? <div data-financial-collector>
        <p>{collector.status === "error" ? ft(($) => $.financialCoverage.collectorUnavailable)
          : !collector.configured ? ft(($) => $.financialCoverage.collectorUnconfigured)
            : pauseReason ? ft(($) => $.financialCoverage.collectorPaused, { reason: pauseReason })
              : collector.rate_limited ? ft(($) => $.financialCoverage.collectorRateLimited, { until: collector.rate_limit_until ?? ft(($) => $.financialCoverage.unknown) })
                : ft(($) => $.financialCoverage.collectorConfigured)}</p>
        <p className="muted tiny">{ft(($) => $.financialCoverage.collectorUnknown)}</p>
        {sa?.capture_urls?.filter((url) => /^https:\/\/seekingalpha\.com\/symbol\/[A-Za-z0-9.%_-]+\/[a-z-]+$/.test(url)).map((url) =>
          <p key={url}><a href={url} target="_blank" rel="noreferrer">{ft(($) => $.financialCoverage.capture)}: {url}</a></p>)}
      </div> : null}
      {updating ? <p role="status">{ft(($) => $.financialCoverage.updating)}</p> : null}
      {updateResult ? <div role="status">
        <p>{previous ? ft(($) => $.financialCoverage.updateFailed) : ft(($) => $.financialCoverage.updated)}</p>
        {updateResult !== "error" ? updateResult.read_gaps.filter((g) => !g.metric).map((g, index) =>
          <p key={index}>{financialText(ft, "gaps", g.code)}</p>) : null}
      </div> : null}
      {changed ? <p role="alert">{ft(($) => $.financialCoverage.readChanged)}</p> : null}
      {errs.map((error) => <ExploreErrorNotice key={error.operation} state={error} developerMode={developerMode}
        retryLabel={t(($) => $.tickerDetail.retry)} onRetry={() => void load()} onNavigate={onNavigateTarget} />)}
      <ConfirmDialog open={confirmUpdate} title={ft(($) => $.financialCoverage.confirmTitle)}
        consequence={ft(($) => $.financialCoverage.confirmConsequence, { ticker, period, currency: "USD" })}
        confirmLabel={ft(($) => $.financialCoverage.confirm)} tone="primary" busy={updating}
        onConfirm={() => void update()} onCancel={() => setConfirmUpdate(false)} returnFocusRef={updateButton} />
    </section>
    <section className="detail-col">
      <h4 className="detail-section">{previous ? ft(($) => $.financialCoverage.previousRead) : t(($) => $.tickerDetail.fundamentals)}
        {fund && fund.data_source !== "none" ? <span> {t(($) => $.tickerDetail.dataSourceSuffix, { source: fund.data_source })}</span> : null}
      </h4>
      {loading ? <p className="muted tiny">{t(($) => $.tickerDetail.loading)}</p> : null}
      {fund ? <>
        {fund.source_observations?.map((o) => <div key={o.observation_id} className="financial-period">
          <span>{ft(($) => $.financialCoverage.captured)} / {financialText(ft, "kinds", o.dataset)}</span>
          <RecordedTimestamp value={o.fetched_at} />
        </div>)}
            <dl className="kv">
              <Kv
                k={t(($) => $.tickerDetail.kvLabels.snapshotDate)}
                v={fund.snapshot_date ?? "—"}
              />
              <Kv k={t(($) => $.tickerDetail.kvLabels.marketCap)} v={metric("market_cap")} />
              <Kv k={t(($) => $.tickerDetail.kvLabels.pe)} v={metric("pe_ratio")} />
              <Kv k={t(($) => $.tickerDetail.kvLabels.forwardPe)} v={metric("forward_pe")} />
              <Kv k={t(($) => $.tickerDetail.kvLabels.ps)} v={metric("ps_ratio")} />
              <Kv k={t(($) => $.tickerDetail.kvLabels.pb)} v={metric("pb_ratio")} />
              <Kv k={t(($) => $.tickerDetail.kvLabels.roe)} v={metric("roe")} />
              <Kv k={t(($) => $.tickerDetail.kvLabels.roa)} v={metric("roa")} />
              <Kv
                k={t(($) => $.tickerDetail.kvLabels.debtToEquity)}
                v={metric("debt_to_equity")}
              />
              <Kv
                k={t(($) => $.tickerDetail.kvLabels.currentRatio)}
                v={metric("current_ratio")}
              />
              <Kv
                k={t(($) => $.tickerDetail.kvLabels.grossMargin)}
                v={metric("gross_margin")}
              />
              <Kv
                k={t(($) => $.tickerDetail.kvLabels.operatingMargin)}
                v={metric("operating_margin")}
              />
              <Kv k={t(($) => $.tickerDetail.kvLabels.netMargin)} v={metric("net_margin")} />
              <Kv
                k={t(($) => $.tickerDetail.kvLabels.revenueGrowth)}
                v={metric("revenue_growth")}
              />
              <Kv
                k={t(($) => $.tickerDetail.kvLabels.earningsGrowth)}
                v={metric("earnings_growth")}
              />
              <Kv
                k={t(($) => $.tickerDetail.kvLabels.dividendYield)}
                v={metric("dividend_yield")}
              />
              <Kv k={t(($) => $.tickerDetail.kvLabels.beta)} v={metric("beta")} />
              <Kv
                k={t(($) => $.tickerDetail.kvLabels.freeCashFlow)}
                v={metric("free_cash_flow")}
              />
              <Kv
                k={t(($) => $.tickerDetail.kvLabels.cashAndEquivalents)}
                v={metric("cash_and_equivalents")}
              />
              <Kv k={t(($) => $.tickerDetail.kvLabels.totalDebt)} v={metric("total_debt")} />
            </dl>

        <StatementsBlock title={t(($) => $.tickerDetail.incomeStatements)} rows={fund.income_statements} />
        <StatementsBlock title={t(($) => $.tickerDetail.balanceSheet)} rows={fund.balance_sheet} />
        <StatementsBlock title={t(($) => $.tickerDetail.cashFlow)} rows={fund.cash_flow_statements} />
        {fund.coverage?.missing_statements?.length ? <p className="muted tiny">{ft(($) => $.financialCoverage.missing, {
          value: fund.coverage.missing_statements.map((kind) => financialText(ft, "kinds", kind)).join(", "),
        })}</p> : null}
        {fund.read_id ? <details><summary>{ft(($) => $.financialCoverage.readIdentity)}</summary><code>{fund.read_id}</code></details> : null}
        {fund.pagination && fund.read_id ? <div className="financial-actions">
          <IconButton label={ft(($) => $.financialCoverage.previous)} icon={<ArrowLeft size={14} />}
            disabled={loading || updating || fund.pagination.offset === 0}
            onClick={() => void load(Math.max(0, fund.pagination!.offset - fund.pagination!.limit), fund.read_id!)} />
          <span>{ft(($) => $.financialCoverage.page, { start: fund.pagination.offset + 1,
            end: Math.min(fund.pagination.offset + fund.pagination.limit, fund.pagination.total_periods) })}</span>
          <IconButton label={ft(($) => $.financialCoverage.next)} icon={<ArrowRight size={14} />}
            disabled={loading || updating || !fund.pagination.has_more}
            onClick={() => void load(fund.pagination!.offset + fund.pagination!.limit, fund.read_id!)} />
        </div> : null}
        {fund.snapshot && Object.keys(fund.snapshot).length > 0 ? <details className="detail-raw">
          <summary>{t(($) => $.tickerDetail.rawSnapshot)}</summary><pre className="raw-json">{JSON.stringify(fund.snapshot, null, 2)}</pre>
        </details> : null}
      </> : null}
      {!loading && fund?.data_source === "none" ? <p className="muted tiny">{t(($) => $.tickerDetail.noFundamentals)}</p> : null}
    </section>
  </div>;
}

function StatementsBlock({ title, rows }: { title: string; rows: FinancialStatement[] | null }) {
  const { t } = useTranslation("explore");
  const { t: ft } = useTranslation("settings");
  if (!rows?.length) return null;
  const keys = Array.from(new Set(rows.flatMap((r) => Object.keys(r.data))));
  return <details className="detail-raw" open>
    <summary>{rows.length === 1 ? t(($) => $.tickerDetail.statementSummary.one, { title, count: rows.length })
      : t(($) => $.tickerDetail.statementSummary.other, { title, count: rows.length })}</summary>
    <div className="financial-table-scroll" tabIndex={0}>
      <table className="data-table"><thead><tr>
        <th>{t(($) => $.tickerDetail.indicator)}</th>
        {rows.map((row, index) => <th key={index}>{row.report_period ?? row.end_month ?? row.fiscal_period ?? "—"}
          <div className="muted tiny">{financialText(ft, "precision", row.period_precision ?? "unknown")}</div>
          <div className="muted tiny">{row.currency}</div>
        </th>)}
      </tr></thead><tbody>
        {keys.map((key) => <tr key={key}><td>{key}</td>
          {rows.map((row, index) => <td key={index}>
            {typeof row.data[key] === "string" ? row.data[key] : fmtNum(row.data[key] as number | null)}
            <span className="muted tiny"> {row.value_metadata?.[key]?.unit ?? row.currency}</span>
            {row.value_metadata?.[key]?.precision ? <div className="muted tiny">
              {financialText(ft, "precision", row.value_metadata[key]!.precision!)}
            </div> : null}
          </td>)}
        </tr>)}
      </tbody></table>
    </div>
    {[...new Set(rows.map((row) => row.unit_note).filter((note): note is string => typeof note === "string"))].map((note) =>
      <p key={note} className="muted tiny">{ft(($) => $.financialCoverage.originalUnits, { value: note })}</p>)}
  </details>;
}

type NoteAddPayload = {
  ticker: string;
  body: string;
};

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
  const [failedAddPayload, setFailedAddPayload] = useState<NoteAddPayload | null>(null);
  const [failedDeleteId, setFailedDeleteId] = useState<number | null>(null);
  const notesRequestSeqRef = useRef(0);

  const refresh = useCallback(async () => {
    const requestSeq = ++notesRequestSeqRef.current;
    try {
      const d = await getNotes(ticker);
      if (requestSeq !== notesRequestSeqRef.current) return;
      setNotes(d.notes);
      setErr(null);
    } catch (e) {
      if (requestSeq === notesRequestSeqRef.current) {
        setErr(captureExploreError("ticker_load_notes", e));
      }
    }
  }, [ticker]);

  useEffect(() => {
    setNotes(null);
    setErr(null);
    setFailedAddPayload(null);
    void refresh();
    return () => {
      notesRequestSeqRef.current += 1;
    };
  }, [refresh]);

  async function submit(retryPayload?: NoteAddPayload) {
    const payload = retryPayload ?? { ticker, body: draft.trim() };
    if (!payload.body || busy) return;
    setBusy(true);
    setErr(null);
    setFailedAddPayload(null);
    try {
      await addNote(payload.ticker, payload.body);
      setDraft((current) => current.trim() === payload.body ? "" : current);
      await refresh();
      onChanged?.();
    } catch (e) {
      setFailedAddPayload(payload);
      setErr(captureExploreError("ticker_add_note", e));
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: number) {
    setBusy(true);
    setErr(null);
    setFailedAddPayload(null);
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
    if (err.operation === "ticker_add_note" && failedAddPayload) {
      void submit(failedAddPayload);
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
type TagAddPayload = {
  ticker: string;
  value: string;
  facet: string;
};

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
  const [failedAddPayload, setFailedAddPayload] = useState<TagAddPayload | null>(null);
  const [failedTag, setFailedTag] = useState<TagRef | null>(null);
  const catalogRequestSeqRef = useRef(0);

  const loadCatalog = useCallback(async () => {
    const requestSeq = ++catalogRequestSeqRef.current;
    try {
      const response = await getTagCatalog();
      if (requestSeq !== catalogRequestSeqRef.current) return;
      setCatalog(response.catalog);
      setCatalogErr(null);
    } catch (e) {
      if (requestSeq === catalogRequestSeqRef.current) {
        setCatalogErr(captureExploreError("ticker_load_tag_catalog", e));
      }
    }
  }, []);
  useEffect(() => {
    void loadCatalog();
    return () => {
      catalogRequestSeqRef.current += 1;
    };
  }, [loadCatalog, ticker]);

  async function add(retryPayload?: TagAddPayload) {
    const payload = retryPayload ?? { ticker, value: draft.trim(), facet };
    if (!payload.value || busy) return;
    setBusy(true);
    setErr(null);
    setFailedAddPayload(null);
    try {
      await addTickerTag(payload.ticker, payload.value, payload.facet);
      setDraft((current) => (
        current.trim() === payload.value && facet === payload.facet ? "" : current
      ));
      onChanged();
      void loadCatalog(); // a new value becomes pickable next time
    } catch (e) {
      setFailedAddPayload(payload);
      setErr(captureExploreError("ticker_add_tag", e));
    } finally {
      setBusy(false);
    }
  }

  async function remove(t: TagRef) {
    if (busy) return;
    setBusy(true);
    setErr(null);
    setFailedAddPayload(null);
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
    } else if (err?.operation === "ticker_add_tag" && failedAddPayload) {
      void add(failedAddPayload);
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
function fmtPct(v: number | null): string {
  return v == null ? "—" : `${v > 0 ? "+" : ""}${v.toFixed(2)}%`;
}
function changeClass(v: number | null): string {
  return v == null ? "" : v > 0 ? "up" : v < 0 ? "down" : "";
}
function fmtRangePct(v: number | null): string {
  return v == null ? "—" : `${v.toFixed(2)}%`;
}
