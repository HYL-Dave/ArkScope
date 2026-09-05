import { useEffect, useRef, useState } from "react";
import { Download } from "lucide-react";
import { getPriceRepairPreview, getSchedule, startPriceRepair, type TradingDayCoverage, type PriceRepairPreview } from "../api";
import { Button } from "../ui/Button";
import { ConfirmDialog } from "../ui/ConfirmDialog";
import type { SettingsT } from "./settingsCopy";

type Outcome = "accepted" | "succeeded" | "partial" | "failed" | "skipped" | "unconfirmed" | "nothing_to_repair";

export function PriceCoverageRepair({ coverage, t, onCompleted }: { coverage: TradingDayCoverage; t: SettingsT; onCompleted: () => void }) {
  const [preview, setPreview] = useState<PriceRepairPreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const [requestId, setRequestId] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const mounted = useRef(true);
  const completed = useRef(onCompleted);
  completed.current = onCompleted;
  const trigger = useRef<HTMLButtonElement>(null);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  useEffect(() => {
    if (!requestId) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const started = Date.now();
    async function poll() {
      try {
        const source = (await getSchedule()).sources.ibkr_prices;
        if (cancelled) return;
        const result = [source?.last_result, source?.durable_state?.last_result].find((row) => row?.price_repair_id === requestId);
        if (result && ["succeeded", "partial", "failed", "skipped"].includes(result.status)) {
          setOutcome(result.status as Outcome); setRequestId(null); completed.current(); return;
        }
        if (!source?.running && Date.now() - started > 60_000) {
          setOutcome("unconfirmed"); setRequestId(null); completed.current(); return;
        }
      } catch {
        if (cancelled) return;
        setOutcome("unconfirmed"); setRequestId(null); return;
      }
      timer = setTimeout(() => { void poll(); }, 2000);
    }
    void poll();
    return () => { cancelled = true; clearTimeout(timer); };
  }, [requestId]);

  async function inspect() {
    setBusy(true); setError(false);
    try { const plan = await getPriceRepairPreview(coverage.lookback_days); if (mounted.current) setPreview(plan); }
    catch { if (mounted.current) setError(true); }
    finally { if (mounted.current) setBusy(false); }
  }
  async function confirm() {
    if (!preview) return;
    if (preview.tickers.length === 0) { setPreview(null); setOutcome("nothing_to_repair"); return; }
    setBusy(true); setError(false);
    try {
      const result = await startPriceRepair(preview);
      if (!mounted.current) return;
      setPreview(null);
      setOutcome(result.status);
      setRequestId(result.repair_id);
      if (!result.repair_id) completed.current();
    } catch { if (mounted.current) { setError(true); setPreview(null); } }
    finally { if (mounted.current) setBusy(false); }
  }
  const gaps = coverage.history_gaps ?? [];
  const reason = (value: typeof gaps[number]["reason"]) => {
    switch (value) {
      case "before_first_local_bar": return t(($) => $.dataStorage.coverage.repair.beforeFirst);
      case "no_local_history": return t(($) => $.dataStorage.coverage.repair.noHistory);
      case "missing_observations": return t(($) => $.dataStorage.coverage.repair.missing);
      case "partial_observations": return t(($) => $.dataStorage.coverage.repair.partialBars);
    }
  };
  const status = outcome ? ({
    accepted: t(($) => $.dataStorage.coverage.repair.accepted), succeeded: t(($) => $.dataStorage.coverage.repair.succeeded),
    partial: t(($) => $.dataStorage.coverage.repair.partial), failed: t(($) => $.dataStorage.coverage.repair.failed),
    skipped: t(($) => $.dataStorage.coverage.repair.skipped), unconfirmed: t(($) => $.dataStorage.coverage.repair.unconfirmed),
    nothing_to_repair: t(($) => $.dataStorage.coverage.repair.nothingToRepair),
  })[outcome] : null;
  return <section style={{ marginBlock: 12 }}>
    <p className="muted tiny">{t(($) => $.dataStorage.coverage.repair.scope)}</p>
    {gaps.length > 0 && <>
      <Button ref={trigger} tone="ghost" icon={<Download size={16} />} busy={busy} disabled={Boolean(requestId) || coverage.observation_health.status !== "ok"} onClick={() => void inspect()}>
        {t(($) => $.dataStorage.coverage.repair.preview)}
      </Button>
      <details style={{ marginBlock: 8 }}><summary>{t(($) => $.dataStorage.coverage.repair.gaps, { count: gaps.length })}</summary>
        <div style={{ overflowX: "auto" }}><table className="ds-table" style={{ minWidth: 550 }}><thead><tr>
          <th>{t(($) => $.dataStorage.coverage.repair.ticker)}</th><th>{t(($) => $.dataStorage.coverage.repair.reason)}</th>
          <th>{t(($) => $.dataStorage.coverage.repair.firstBar)}</th><th>{t(($) => $.dataStorage.coverage.repair.missingDates)}</th>
        </tr></thead><tbody>{gaps.map((gap) => <tr key={gap.ticker}><td>{gap.ticker}</td><td>{reason(gap.reason)}</td>
          <td>{gap.first_local_bar_at?.slice(0, 10) ?? t(($) => $.dataStorage.coverage.repair.none)}</td>
          <td><details><summary>{gap.missing_dates.length + gap.partial_dates.length}</summary>
            <div style={{ maxWidth: 360, whiteSpace: "normal", overflowWrap: "anywhere" }}>{[...gap.missing_dates, ...gap.partial_dates].sort().join(", ")}</div>
          </details></td></tr>)}</tbody></table></div>
      </details>
    </>}
    {status && <p className="tiny" role="status">{status}</p>}
    {error && <p className="tiny refresh-err" role="alert">{t(($) => $.dataStorage.coverage.repair.error)}</p>}
    <ConfirmDialog open={preview !== null} title={t(($) => $.dataStorage.coverage.repair.confirmTitle)} tone="primary" busy={busy}
      confirmLabel={preview?.tickers.length === 0 ? t(($) => $.dataStorage.coverage.repair.close) : t(($) => $.dataStorage.coverage.repair.confirm)} returnFocusRef={trigger}
      onConfirm={() => void confirm()} onCancel={() => setPreview(null)}
      consequence={preview && <>
        <p>{t(($) => $.dataStorage.coverage.repair.consequence, { count: preview.tickers.length, days: preview.lookback_days, date: preview.as_of_date })}</p>
        <p style={{ maxHeight: 160, overflow: "auto", overflowWrap: "anywhere" }}>{preview.tickers.join(", ")}</p>
        {preview.blocked_tickers.length > 0 && <p>{t(($) => $.dataStorage.coverage.repair.blocked, { tickers: preview.blocked_tickers.join(", ") })}</p>}
      </>} />
  </section>;
}
