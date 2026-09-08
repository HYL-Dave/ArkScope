import { useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, Play, RefreshCw } from "lucide-react";
import { getPriceRepairOperations, getSchedule, resumePriceRepair, type PriceRepairOperation, type PriceRepairOperations } from "../api";
import { Button, IconButton } from "../ui/Button";
import { ConfirmDialog } from "../ui/ConfirmDialog";
import type { SettingsT } from "./settingsCopy";

export function PriceRepairHistory({ t, pending, refreshKey, onAccepted, onCompleted, onRunningChange }: {
  t: SettingsT; pending: boolean; refreshKey: string;
  onAccepted: (repairId: string) => void; onCompleted: () => void; onRunningChange: (running: boolean | null) => void;
}) {
  const [page, setPage] = useState<PriceRepairOperations | null>(null);
  const [offset, setOffset] = useState(0);
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(true);
  const [readError, setReadError] = useState(false);
  const [writeError, setWriteError] = useState(false);
  const [running, setRunning] = useState<boolean | null>(null);
  const [selection, setSelection] = useState<PriceRepairOperation | null>(null);
  const [busy, setBusy] = useState(false);
  const trigger = useRef<HTMLButtonElement | null>(null);
  const callbacks = useRef({ onAccepted, onCompleted, onRunningChange });
  callbacks.current = { onAccepted, onCompleted, onRunningChange };
  const mounted = useRef(true);
  const priorStates = useRef(new Map<string, string>());
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  useEffect(() => {
    let cancelled = false;
    let wasActive = false;
    let timer: ReturnType<typeof setTimeout>;
    setLoading(true);
    async function read() {
      let active = false;
      try {
        const result = await getPriceRepairOperations(offset);
        if (cancelled) return;
        setPage(result); setReadError(false);
        const changed = result.operations.some((row) => row.state === "complete" && priorStates.current.get(row.repair_id) === "incomplete");
        result.operations.forEach((row) => priorStates.current.set(row.repair_id, row.state));
        if (changed) callbacks.current.onCompleted();
      } catch { if (!cancelled) setReadError(true); }
      try {
        const activity = (await getSchedule()).sources.ibkr_prices?.running;
        if (typeof activity !== "boolean") throw new Error("price_collection_activity_unavailable");
        active = activity;
        if (cancelled) return;
        wasActive = active;
        setRunning(active); callbacks.current.onRunningChange(active);
      } catch {
        if (cancelled) return;
        setRunning(null); callbacks.current.onRunningChange(null);
        active = wasActive;
      }
      if (cancelled) return;
      setLoading(false);
      if (active || pending) timer = setTimeout(() => { void read(); }, 2000);
    }
    void read();
    return () => { cancelled = true; clearTimeout(timer); };
  }, [offset, refresh, refreshKey, pending]);

  async function confirm() {
    if (!selection) return;
    setBusy(true); setWriteError(false);
    try {
      const result = await resumePriceRepair(selection.repair_id);
      if (!mounted.current) return;
      setSelection(null); setOffset(0); setRefresh((value) => value + 1);
      if (result.repair_id) callbacks.current.onAccepted(result.repair_id);
      else callbacks.current.onCompleted();
    } catch {
      if (mounted.current) { setWriteError(true); setSelection(null); setRefresh((value) => value + 1); }
    } finally { if (mounted.current) setBusy(false); }
  }

  function stateText(row: PriceRepairOperation) {
    switch (row.state) {
      case "complete": return t(($) => $.dataStorage.coverage.repair.historyComplete);
      case "incomplete": return t(($) => $.dataStorage.coverage.repair.historyIncomplete);
      case "blocked": return t(($) => $.dataStorage.coverage.repair.historyBlocked);
      case "unavailable": return t(($) => $.dataStorage.coverage.repair.historyUnavailable);
    }
  }
  function reasonText(row: PriceRepairOperation) {
    switch (row.reason) {
      case null: return null;
      case "unconfirmed_requests": return t(($) => $.dataStorage.coverage.repair.unconfirmedRequests);
      case "response_incomplete": return t(($) => $.dataStorage.coverage.repair.responseIncomplete);
      case "scope_changed": return t(($) => $.dataStorage.coverage.repair.scopeChanged);
      case "coverage_unavailable": return t(($) => $.dataStorage.coverage.repair.coverageUnavailable);
      case "journal_unavailable": return t(($) => $.dataStorage.coverage.repair.journalUnavailable);
    }
  }
  return <section aria-label={t(($) => $.dataStorage.coverage.repair.historyTitle)} style={{ borderTop: "1px solid var(--border)", paddingTop: 12, marginTop: 16 }}>
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
      <strong>{t(($) => $.dataStorage.coverage.repair.historyTitle)}</strong>
      <IconButton tone="ghost" icon={<RefreshCw size={16} />} label={t(($) => $.dataStorage.coverage.repair.refreshHistory)}
        busy={loading} onClick={() => setRefresh((value) => value + 1)} />
    </div>
    {running && <p className="tiny muted" role="status">{t(($) => $.dataStorage.coverage.repair.collectionRunning)}</p>}
    {running === null && !loading && <p className="tiny muted" role="status">{t(($) => $.dataStorage.coverage.repair.collectionUnknown)}</p>}
    {readError && <p className="tiny refresh-err" role="alert">{t(($) => $.dataStorage.coverage.repair.historyReadError)}</p>}
    {writeError && <p className="tiny refresh-err" role="alert">{t(($) => $.dataStorage.coverage.repair.error)}</p>}
    {!readError && page?.total === 0 && <p className="tiny muted">{t(($) => $.dataStorage.coverage.repair.historyEmpty)}</p>}
    {page?.operations.map((row) => <div key={row.repair_id} style={{ borderBottom: "1px solid var(--border)", paddingBlock: 12, display: "grid", gap: 8 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
        <strong className={row.state === "complete" ? "tiny" : "tiny refresh-err"}>{stateText(row)}</strong>
        {row.resume.available && <Button tone="ghost" icon={<Play size={16} />} disabled={readError || loading || running !== false || pending || busy}
          onClick={(event) => { trigger.current = event.currentTarget; setSelection(row); }}>{t(($) => $.dataStorage.coverage.repair.resume)}</Button>}
      </div>
      {row.scope && <div className="tiny muted">{t(($) => $.dataStorage.coverage.repair.historyWindow, { days: row.scope.lookback_days, date: row.scope.as_of_date, count: row.scope.tickers.length })}</div>}
      {row.requests && <div className="tiny" style={{ display: "flex", flexWrap: "wrap", gap: "4px 16px" }}>
        <span>{t(($) => $.dataStorage.coverage.repair.requestsSent, { count: row.requests.dispatched, total: row.requests.planned })}</span>
        <span>{t(($) => $.dataStorage.coverage.repair.responsesReceived, { count: row.requests.received, total: row.requests.planned })}</span>
        {row.requests.unanswered > 0 && <span>{t(($) => $.dataStorage.coverage.repair.requestsUnanswered, { count: row.requests.unanswered })}</span>}
      </div>}
      {row.coverage && row.coverage.remaining_tickers.length > 0 && <div className="tiny">
        {t(($) => $.dataStorage.coverage.repair.remainingDays, { missing: row.coverage.missing_ticker_days, partial: row.coverage.partial_ticker_days })}
        <div style={{ overflowWrap: "anywhere" }}>{row.coverage.remaining_tickers.join(", ")}</div>
      </div>}
      {row.reason && <div className="tiny muted">{reasonText(row)}</div>}
    </div>)}
    {page && (page.total > 5 || offset > 0) && <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", flexWrap: "wrap", gap: 8, marginTop: 8 }}>
      <span className="tiny muted">{t(($) => $.dataStorage.coverage.repair.historyPage, { start: page.operations.length ? offset + 1 : 0, end: offset + page.operations.length, total: page.total })}</span>
      <IconButton tone="ghost" icon={<ChevronLeft size={16} />} disabled={loading || offset === 0} onClick={() => setOffset(Math.max(0, offset - 5))}
        label={t(($) => $.dataStorage.coverage.repair.previousPage)} />
      <IconButton tone="ghost" icon={<ChevronRight size={16} />} disabled={loading || !page.has_more} onClick={() => setOffset(offset + 5)}
        label={t(($) => $.dataStorage.coverage.repair.nextPage)} />
    </div>}
    <ConfirmDialog open={selection !== null} title={t(($) => $.dataStorage.coverage.repair.resumeTitle)} tone="primary" busy={busy}
      returnFocusRef={trigger} confirmLabel={t(($) => $.dataStorage.coverage.repair.confirmResume)} onConfirm={() => void confirm()} onCancel={() => setSelection(null)}
      consequence={selection?.scope && <>
        <p>{t(($) => $.dataStorage.coverage.repair.resumeScope, { count: selection.scope.tickers.length, days: selection.scope.lookback_days, date: selection.scope.as_of_date })}</p>
        <p>{selection.resume.request_limit === 0 ? t(($) => $.dataStorage.coverage.repair.cacheOnlyResume)
          : t(($) => $.dataStorage.coverage.repair.resumeBudget, { count: selection.resume.request_limit })}</p>
        <p style={{ maxHeight: 160, overflow: "auto", overflowWrap: "anywhere" }}>{selection.scope.tickers.join(", ")}</p>
      </>} />
  </section>;
}
