import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  getMarketDataStatus,
  getTradingDayCoverage,
  type MarketDataStatus,
  type SyncMeta,
  type TradingDayCoverage,
  type TradingDayRow,
} from "../api";
import { coverageStatusLabel } from "../marketDataDisplay";
import { formatSystemTimestamp } from "../timeDisplay";
import { DeveloperDiagnostics } from "./DeveloperDiagnostics";
import { settingsErrorPresentation } from "./settingsBackendCopy";
import type { SettingsT } from "./settingsCopy";

export function shortTs(iso: string | null | undefined): string {
  return formatSystemTimestamp(iso);
}
function syncLine(status: MarketDataStatus, t: SettingsT): string {
  const fmt = (m: SyncMeta | null) => {
    if (!m) return "—";
    if (!Number.isFinite(m.rows_added)) return "—";
    const ts = formatSystemTimestamp(m.last_success);
    return `+${m.rows_added.toLocaleString()} @ ${ts}`;
  };
  const s = status.sync;
  if (!s.prices && !s.news && !s.iv && !s.fundamentals) {
    return t(($) => $.dataStorage.update.never);
  }
  if ([s.prices, s.news, s.iv, s.fundamentals].some((value) => value?.last_error)) {
    return t(($) => $.dataStorage.update.failed);
  }
  return t(($) => $.dataStorage.update.succeeded, {
    pricesValue: fmt(s.prices),
    newsValue: fmt(s.news),
    ivValue: fmt(s.iv),
    fundamentalsValue: fmt(s.fundamentals),
  });
}

function syncDiagnostics(status: MarketDataStatus): Array<string | null> {
  const sync = status.sync;
  return [sync.prices, sync.news, sync.iv, sync.fundamentals]
    .map((value) => value?.last_error ?? null);
}

export function DataStorageSection({
  developerMode = false,
}: {
  developerMode?: boolean;
}) {
  const { t } = useTranslation("settings");
  const [status, setStatus] = useState<MarketDataStatus | null>(null);
  const [err, setErr] = useState<Error | null>(null);

  const load = useCallback(async () => {
    try {
      setStatus(await getMarketDataStatus());
      setErr(null);
    } catch (e) {
      setErr(e instanceof Error ? e : new Error(String(e)));
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);

  const exists = status?.exists ?? false;
  const pr = status?.prices;
  const nw = status?.news;
  const iv = status?.iv;
  const fd = status?.fundamentals;
  const fc = status?.financial_cache;
  const errorPresentation = err ? settingsErrorPresentation(err, t) : null;

  return (
    <div>
      <div className="settings-section-head">
        <div>
          <h2>{t(($) => $.dataStorage.title)}</h2>
          <p className="muted tiny">{t(($) => $.dataStorage.description)}</p>
        </div>
        <button className="btn-ghost" onClick={() => void load()}>
          ↻ {t(($) => $.actions.refresh)}
        </button>
      </div>

      {errorPresentation ? (
        <div className="errorbox"><p className="muted">{errorPresentation.message}</p></div>
      ) : null}
      {developerMode ? (
        <DeveloperDiagnostics diagnostics={[errorPresentation?.diagnostic]} t={t} />
      ) : null}

      {!status ? (
        <p className="muted">{t(($) => $.dataStorage.loading)}</p>
      ) : (
        <div className="settings-panel">
          <dl className="ds-kv">
            <dt>{t(($) => $.dataStorage.title)}</dt>
            <dd>{exists
              ? t(($) => $.dataStorage.available)
              : t(($) => $.dataStorage.empty)}</dd>
            <dt>{t(($) => $.dataStorage.labels.prices)}</dt>
            <dd>{exists ? t(($) => $.dataStorage.summary.prices, {
              value: pr!.row_count.toLocaleString(),
              count: pr!.ticker_count,
              timestamp: pr!.latest_datetime ?? "—",
            }) : "—"}</dd>
            <dt>{t(($) => $.dataStorage.labels.news)}</dt>
            <dd>{exists ? t(($) => $.dataStorage.summary.news, {
              value: nw!.row_count.toLocaleString(),
              count: nw!.source_count,
              timestamp: nw!.latest_published ?? "—",
            }) : "—"}</dd>
            <dt>{t(($) => $.dataStorage.labels.iv)}</dt>
            <dd>{exists ? t(($) => $.dataStorage.summary.iv, {
              value: iv!.row_count.toLocaleString(),
              count: iv!.ticker_count,
              timestamp: iv!.latest_date ?? "—",
            }) : "—"}</dd>
            <dt>{t(($) => $.dataStorage.labels.fundamentals)}</dt>
            <dd>{exists ? t(($) => $.dataStorage.summary.fundamentals, {
              value: fd!.row_count.toLocaleString(),
              count: fd!.ticker_count,
              timestamp: fd!.latest_date ?? "—",
            }) : "—"}</dd>
            <dt>{t(($) => $.dataStorage.labels.financialCache)}</dt>
            <dd>
              {exists
                ? t(($) => $.dataStorage.summary.financialCache, {
                    value: fc!.row_count.toLocaleString(),
                    count: fc!.valid_count,
                    expiredCount: fc!.expired_count,
                    timestamp: formatSystemTimestamp(fc!.latest_fetched_at),
                  })
                : "—"}
            </dd>
            <dt>{t(($) => $.dataStorage.update.title)}</dt>
            <dd>{syncLine(status, t)}</dd>
          </dl>
          {developerMode ? (
            <DeveloperDiagnostics diagnostics={syncDiagnostics(status)} t={t} />
          ) : null}
        </div>
      )}

      <TradingDayCoveragePanel developerMode={developerMode} />
    </div>
  );
}

// ---- 交易日 / 價格覆蓋唯讀診斷 (Slice B) — read-only; renders backend coverage_status ----

function coverageToneColor(tone: "ok" | "warn" | "muted" | "bad"): string {
  return tone === "ok" ? "var(--ok)" : tone === "bad" ? "var(--bad)"
    : tone === "warn" ? "var(--warn, #b8860b)" : "var(--muted, #888)";
}

function TradingDayCoveragePanel({ developerMode }: { developerMode: boolean }) {
  const { t } = useTranslation("settings");
  const [cov, setCov] = useState<TradingDayCoverage | null>(null);
  const [err, setErr] = useState<Error | null>(null);
  const [busy, setBusy] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [lookback, setLookback] = useState(10);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      setCov(await getTradingDayCoverage(lookback, "15min"));
      setErr(null);
    } catch (e) {
      setErr(e instanceof Error ? e : new Error(String(e)));
    } finally {
      setBusy(false);
    }
  }, [lookback]);
  useEffect(() => {
    void load();
  }, [load]);
  const errorPresentation = err ? settingsErrorPresentation(err, t) : null;

  return (
    <div style={{ marginTop: 24, borderTop: "1px solid var(--border, #333)", paddingTop: 16 }}>
      <div className="settings-section-head">
        <div>
          <h2>{t(($) => $.dataStorage.coverage.title)}</h2>
          <p className="muted tiny">
            {t(($) => $.dataStorage.coverage.lookback, { count: lookback })}{" "}
            {t(($) => $.dataStorage.coverage.description)}{" "}
            <strong>{t(($) => $.dataStorage.coverage.readOnly)}</strong>
          </p>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <label className="muted tiny">
            {t(($) => $.dataStorage.coverage.lookbackLabel)}{" "}
            <select
              value={lookback}
              disabled={busy}
              onChange={(e) => setLookback(Number(e.target.value))}
            >
              {[10, 15, 30, 60].map((n) => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>
          </label>
          <button className="btn-ghost" onClick={() => void load()} disabled={busy}>
            ↻ {t(($) => $.actions.refresh)}
          </button>
        </div>
      </div>

      {errorPresentation ? (
        <div className="errorbox"><p className="muted">{errorPresentation.message}</p></div>
      ) : null}
      {developerMode ? (
        <DeveloperDiagnostics diagnostics={[errorPresentation?.diagnostic]} t={t} />
      ) : null}

      {!cov ? (
        <p className="muted">{t(($) => $.dataStorage.loading)}</p>
      ) : (
        <div className="settings-panel">
          <p className="muted tiny">
            {t(($) => $.dataStorage.coverage.drilldown.universe, {
              count: cov.universe_count,
            })} ·{" "}
            {t(($) => $.dataStorage.coverage.drilldown.interval)} {cov.interval} ·{" "}
            {t(($) => $.dataStorage.update.generatedAt, {
              timestamp: shortTs(cov.generated_at_et),
            })}
          </p>
          <table className="ds-table" style={{ width: "100%", marginTop: 8 }}>
            <thead>
              <tr>
                <th style={{ textAlign: "left" }}>{t(($) => $.dataStorage.coverage.headings.date)}</th>
                <th style={{ textAlign: "left" }}>{t(($) => $.dataStorage.coverage.headings.status)}</th>
                <th style={{ textAlign: "right" }}>{t(($) => $.dataStorage.coverage.headings.maxBars)}</th>
                <th style={{ textAlign: "right" }}>{t(($) => $.dataStorage.coverage.headings.covered)}</th>
                <th style={{ textAlign: "right" }}>{t(($) => $.dataStorage.coverage.headings.missing)}</th>
                <th style={{ textAlign: "right" }}>{t(($) => $.dataStorage.coverage.drilldown.partial)}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {cov.days.map((d) => {
                const cs = coverageStatusLabel(d, t);
                const open = expanded === d.date;
                // in_progress: the session is open, so "missing/partial" is just not-fetched-yet,
                // not a gap — don't offer an alarming drill-down. Only completed days drill.
                const drillable =
                  d.coverage_status !== "in_progress" &&
                  d.is_trading_day &&
                  ((d.missing ?? 0) > 0 || (d.partial ?? 0) > 0);
                return (
                  <CoverageRow
                    key={d.date}
                    row={d}
                    label={cs.label}
                    tone={cs.tone}
                    open={open}
                    drillable={drillable}
                    onToggle={() => setExpanded(open ? null : d.date)}
                    providerErrors={cov.provider_errors}
                    developerMode={developerMode}
                    t={t}
                  />
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function CoverageRow({
  row, label, tone, open, drillable, onToggle, providerErrors, developerMode, t,
}: {
  row: TradingDayRow;
  label: string;
  tone: "ok" | "warn" | "muted" | "bad";
  open: boolean;
  drillable: boolean;
  onToggle: () => void;
  providerErrors: TradingDayCoverage["provider_errors"];
  developerMode: boolean;
  t: SettingsT;
}) {
  // Show numeric coverage only for COMPLETED trading days. Non-trading → "—"; in_progress →
  // "—" too (mid-session counts aren't a gap; the status cell already says 盤中).
  const showCounts = row.is_trading_day && row.coverage_status !== "in_progress";
  const dash = (n: number | null) => (showCounts && n != null ? n.toLocaleString() : "—");
  // provider errors are universe-wide (not per-day); show them only under a day that has misses.
  const relErrors = drillable
    ? providerErrors.filter((e) => row.missing_tickers.includes(e.ticker))
    : [];
  return (
    <>
      <tr
        onClick={drillable ? onToggle : undefined}
        style={{ cursor: drillable ? "pointer" : "default" }}
      >
        <td>{row.date}{drillable ? (open ? " ▾" : " ▸") : ""}</td>
        <td style={{ color: coverageToneColor(tone) }}>{label}</td>
        <td style={{ textAlign: "right" }}>{dash(row.max_observed_bar_count)}</td>
        <td style={{ textAlign: "right" }}>{dash(row.covered)}</td>
        <td style={{ textAlign: "right" }}>{dash(row.missing)}</td>
        <td style={{ textAlign: "right" }}>{dash(row.partial)}</td>
        <td />
      </tr>
      {open && drillable && (
        <tr>
          <td colSpan={7} style={{ background: "var(--panel-2, #1a1a1a)", padding: "8px 12px" }}>
            {row.missing_tickers.length > 0 && (
              <p className="tiny" style={{ margin: "0 0 4px" }}>
                {t(($) => $.dataStorage.coverage.drilldown.missingDetail, {
                  count: row.missing_tickers.length,
                  value: row.missing_tickers.join(", "),
                })}
              </p>
            )}
            {row.partial_tickers.length > 0 && (
              <p className="tiny" style={{ margin: "0 0 4px" }}>
                {t(($) => $.dataStorage.coverage.drilldown.partialDetail, {
                  value: row.partial_tickers.map((p) => `${p.ticker}(${p.bars})`).join(", "),
                })}
              </p>
            )}
            {relErrors.length > 0 && (
              <p className="tiny refresh-err" style={{ margin: 0 }}>
                {t(($) => $.dataStorage.coverage.drilldown.providerError)}
              </p>
            )}
            {developerMode ? (
              <DeveloperDiagnostics
                diagnostics={relErrors.map((error) => error.last_error
                  ? `${error.ticker}: ${error.last_error}`
                  : null)}
                t={t}
              />
            ) : null}
          </td>
        </tr>
      )}
    </>
  );
}
