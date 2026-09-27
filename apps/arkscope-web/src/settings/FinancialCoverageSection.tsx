import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { ArrowLeft, ArrowRight, RefreshCw, Settings2 } from "lucide-react";
import { getFinancialCoverage, type FinancialCoveragePage, type FinancialPeriod } from "../api";
import type { NavigationTarget } from "../shell/navigation";
import { IconButton } from "../ui/Button";
import { RecordedTimestamp } from "./RecordedTimestamp";
import type { SettingsT } from "./settingsCopy";
import { createSettingsReadCache, financialCoverageKey, type SettingsReadCache } from "./settingsReadCache";

export function financialText(t: SettingsT, group: "gaps" | "kinds" | "metrics" | "precision" | "sources" | "states", value: string): string {
  const groups = {
    gaps: t(($) => $.financialCoverage.gaps, { returnObjects: true }),
    kinds: t(($) => $.financialCoverage.kinds, { returnObjects: true }),
    metrics: t(($) => $.financialCoverage.metrics, { returnObjects: true }),
    precision: t(($) => $.financialCoverage.precision, { returnObjects: true }),
    sources: t(($) => $.financialCoverage.sources, { returnObjects: true }),
    states: t(($) => $.financialCoverage.states, { returnObjects: true }),
  };
  const labels = groups[group] as Record<string, string>;
  return Object.hasOwn(labels, value) ? labels[value]! : value;
}

export function FinancialCoverageSection({ settingsReadCache: suppliedCache, onNavigateTarget }: {
  settingsReadCache?: SettingsReadCache; onNavigateTarget?: (target: NavigationTarget) => void;
}) {
  const { t } = useTranslation("settings");
  const [ownCache] = useState(createSettingsReadCache);
  const cache = suppliedCache ?? ownCache;
  const [period, setPeriod] = useState<FinancialPeriod>("annual");
  const [source, setSource] = useState("auto");
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<FinancialCoveragePage | null>(null);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const sequence = useRef(0);
  const key = financialCoverageKey(period, source, "USD", offset, 25);
  const load = useCallback(async (force = false) => {
    const request = ++sequence.current;
    setBusy(true); setFailed(false);
    const response = await cache.load(key, () => getFinancialCoverage({ period, source, currency: "USD", offset, limit: 25 }), { force });
    if (request !== sequence.current) return;
    if (response.status === "success") setPage(response.value);
    else if (response.status === "error") setFailed(true);
    setBusy(false);
  }, [cache, key, offset, period, source]);
  useEffect(() => {
    setPage(null); void load();
    const unsubscribe = cache.subscribeInvalidation(key, () => { void load(); });
    return () => { sequence.current += 1; unsubscribe(); };
  }, [cache, key, load]);

  return <section className="financial-coverage" aria-label={t(($) => $.financialCoverage.title)}>
    <div className="settings-section-head">
      <h3>{t(($) => $.financialCoverage.title)}</h3>
      <div className="financial-actions">
        {onNavigateTarget ? <IconButton label={t(($) => $.financialCoverage.settings)} icon={<Settings2 size={16} />}
          onClick={() => onNavigateTarget({ kind: "settings_section", section: "data_sources" })} /> : null}
        <IconButton label={t(($) => $.financialCoverage.reread)} icon={<RefreshCw size={16} />} disabled={busy}
          onClick={() => void load(true)} />
      </div>
    </div>
    <div className="financial-controls">
      <label>{t(($) => $.financialCoverage.source)}<select aria-label={t(($) => $.financialCoverage.source)} value={source}
        onChange={(e) => { setSource(e.target.value); setOffset(0); }}>
        {["auto", "seeking_alpha", "financial_datasets"].map((value) => <option key={value} value={value}>{financialText(t, "sources", value)}</option>)}
      </select></label>
      <label>{t(($) => $.financialCoverage.period)}<select aria-label={t(($) => $.financialCoverage.period)} value={period}
        onChange={(e) => { setPeriod(e.target.value as FinancialPeriod); setOffset(0); }}>
        <option value="annual">{t(($) => $.financialCoverage.annual)}</option>
        <option value="quarterly">{t(($) => $.financialCoverage.quarterly)}</option>
      </select></label>
    </div>
    {busy ? <p role="status">{t(($) => $.financialCoverage.loading)}</p> : null}
    {failed ? <p role="alert">{t(($) => $.financialCoverage.loadFailed)}</p> : null}
    {page ? <>
      <p className="muted tiny">{t(($) => $.financialCoverage.inventory, { count: page.candidate_count, inspected: page.items.length })}</p>
      {page.gaps.map((gap, index) => <p key={index} className="refresh-err">{financialText(t, "gaps", gap.code)}</p>)}
      {page.items.length === 0 && page.status !== "unavailable" ? <p>{t(($) => $.financialCoverage.empty)}</p> : null}
      <div className="financial-coverage-list">
        {page.items.map((item) => <article key={item.ticker} className="financial-coverage-row">
          <div className="financial-record-head"><strong>{item.ticker}</strong>
            <span>{financialText(t, "sources", item.selected_source ?? "none")}</span>
            <span>{financialText(t, "states", item.status)}</span></div>
          {Object.entries(item.statements).map(([kind, rows]) => <div key={kind} className="financial-periods">
            <strong>{financialText(t, "kinds", kind)}</strong>
            {rows.map((row, index) => <div key={index} className="financial-period">
              <span>{row.report_period ?? row.end_month ?? t(($) => $.financialCoverage.unknown)}</span>
              <span>{row.currency ?? t(($) => $.financialCoverage.unknown)}</span>
              <RecordedTimestamp value={row.fetched_at} />
              <span className="muted tiny">{row.unit_note ?? ""} {row.value_precision.map((p) => financialText(t, "precision", p)).join(" / ")}</span>
            </div>)}
          </div>)}
          {item.missing_statements.length ? <p className="muted tiny">{t(($) => $.financialCoverage.missing, {
            value: item.missing_statements.map((kind) => financialText(t, "kinds", kind)).join(", "),
          })}</p> : null}
          {item.supported_metrics.length ? <p className="tiny">{t(($) => $.financialCoverage.supported, {
            value: item.supported_metrics.map((name) => financialText(t, "metrics", name)).join(", "),
          })}</p> : null}
          <details><summary>{t(($) => $.financialCoverage.inputGaps)}</summary>
            <dl className="financial-gaps">{Object.entries(item.metric_gaps).map(([name, code]) => <div key={name}>
              <dt>{financialText(t, "metrics", name)}</dt><dd>{financialText(t, "gaps", code)}</dd>
            </div>)}</dl>
            {item.gaps.filter((g) => !g.metric).map((g, i) => <p key={i}>{financialText(t, "gaps", g.code)}</p>)}
            {item.read_id ? <code className="financial-id">{item.read_id}</code> : null}
          </details>
        </article>)}
      </div>
      <div className="financial-actions">
        <IconButton label={t(($) => $.financialCoverage.previous)} icon={<ArrowLeft size={16} />}
          disabled={busy || offset === 0} onClick={() => setOffset(Math.max(0, offset - 25))} />
        <span>{t(($) => $.financialCoverage.page, { start: page.items.length ? offset + 1 : 0, end: offset + page.items.length })}</span>
        <IconButton label={t(($) => $.financialCoverage.next)} icon={<ArrowRight size={16} />}
          disabled={busy || page.next_offset == null} onClick={() => setOffset(page.next_offset ?? offset)} />
      </div>
    </> : null}
  </section>;
}
