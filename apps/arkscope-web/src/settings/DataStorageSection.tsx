import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  ArrowRightLeft,
  Check,
  ChevronDown,
  ChevronRight,
  RotateCcw,
  X,
} from "lucide-react";
import {
  getMarketDataStatus,
  getSecurityLifecycle,
  getTradingDayCoverage,
  reviewCorporateRelationship,
  reviewSecurityLifecycleEvent,
  type MarketDataStatus,
  type SecurityLifecycleEvent,
  type SecurityLifecycleSnapshot,
  type TradingDayCoverage,
  type TradingDayRow,
} from "../api";
import {
  coverageCalendarHealthLabels,
  coverageDataQualityPresentation,
  coverageDayReasonLabel,
  coverageMarketScopeLabel,
  coverageObservationHealthLabel,
  coverageProviderIssueLabels,
  coverageSessionLabel,
  coverageStatusLabel,
  coverageTickerFactsPresentation,
} from "../marketDataDisplay";
import { formatSystemTimestamp } from "../timeDisplay";
import { Button } from "../ui/Button";
import { DeveloperDiagnostics } from "./DeveloperDiagnostics";
import { settingsErrorPresentation } from "./settingsBackendCopy";
import type { SettingsT } from "./settingsCopy";
import {
  tradingDayCoverageKey,
  type SettingsReadCache,
} from "./settingsReadCache";
import { SettingsSubsectionAnchor } from "./SettingsSectionAnchor";

export function shortTs(iso: string | null | undefined): string {
  return formatSystemTimestamp(iso);
}

function coverageDeveloperDiagnostics(coverage: TradingDayCoverage): string[] {
  return [
    ...coverage.provider_errors.map((issue) => `${issue.ticker}: ${issue.last_error}`),
    ...coverage.days.flatMap((day) => day.unknown_tickers.length > 0
      ? [`${day.date}: ${day.unknown_tickers.join(", ")}`]
      : []),
  ];
}

export function DataStorageSection({
  developerMode = false,
  settingsReadCache,
}: {
  developerMode?: boolean;
  settingsReadCache: SettingsReadCache;
}) {
  const { t } = useTranslation("settings");
  const { t: commonT } = useTranslation("common");
  const [status, setStatus] = useState<MarketDataStatus | null>(() => {
    const inspected = settingsReadCache.inspect<MarketDataStatus>("market_data_status");
    return inspected.status === "missing" ? null : inspected.value;
  });
  const [err, setErr] = useState<Error | null>(null);

  const load = useCallback(async (force = false) => {
    const result = await settingsReadCache.load(
      "market_data_status",
      getMarketDataStatus,
      { force },
    );
    if (result.status === "success") {
      setStatus(result.value);
      setErr(null);
    } else if (result.status === "error") {
      setErr(result.error instanceof Error ? result.error : new Error(String(result.error)));
    }
  }, [settingsReadCache]);
  useEffect(() => {
    void load(false);
  }, [load]);
  useEffect(() => settingsReadCache.subscribeInvalidation(
    "market_data_status",
    () => { void load(false); },
  ), [load, settingsReadCache]);

  const exists = status?.exists ?? false;
  const pr = status?.prices;
  const nw = status?.news;
  const fd = status?.fundamentals;
  const fc = status?.financial_cache;
  const errorPresentation = err ? settingsErrorPresentation(err, t, commonT) : null;

  return (
    <div>
      <div className="settings-section-head">
        <div>
          <h2>{t(($) => $.dataStorage.title)}</h2>
          <p className="muted tiny">{t(($) => $.dataStorage.description)}</p>
        </div>
        <button className="btn-ghost" onClick={() => void load(true)}>
          ↻ {t(($) => $.actions.refreshStatus)}
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
          </dl>
        </div>
      )}

      <SettingsSubsectionAnchor id="security_lifecycle">
        <SecurityLifecyclePanel
          developerMode={developerMode}
          settingsReadCache={settingsReadCache}
        />
      </SettingsSubsectionAnchor>

      <SettingsSubsectionAnchor id="trading_day_coverage">
        <TradingDayCoveragePanel
          developerMode={developerMode}
          settingsReadCache={settingsReadCache}
        />
      </SettingsSubsectionAnchor>
    </div>
  );
}

function lifecycleEventLabel(event: SecurityLifecycleEvent, t: SettingsT): string {
  switch (event.event_type) {
    case "merger_agreement":
      return t(($) => $.dataStorage.lifecycle.events.mergerAgreement);
    case "merger_proxy":
      return t(($) => $.dataStorage.lifecycle.events.mergerProxy);
    case "acquisition_completed":
      return t(($) => $.dataStorage.lifecycle.events.acquisitionCompleted);
    case "listing_status_review":
      return t(($) => $.dataStorage.lifecycle.events.listingStatusReview);
    case "listing_removal_notice":
      return t(($) => $.dataStorage.lifecycle.events.listingRemovalNotice);
  }
}

function lifecycleStateLabel(
  state: SecurityLifecycleEvent["lifecycle_state"],
  t: SettingsT,
): string {
  switch (state) {
    case "review_required":
      return t(($) => $.dataStorage.lifecycle.states.reviewRequired);
    case "pending_delisting":
      return t(($) => $.dataStorage.lifecycle.states.pendingDelisting);
    case "inactive_confirmed":
      return t(($) => $.dataStorage.lifecycle.states.inactiveConfirmed);
    case "renamed_or_transferred":
      return t(($) => $.dataStorage.lifecycle.states.renamedOrTransferred);
  }
}

function SecurityLifecyclePanel({
  developerMode,
  settingsReadCache,
}: {
  developerMode: boolean;
  settingsReadCache: SettingsReadCache;
}) {
  const { t } = useTranslation("settings");
  const { t: commonT } = useTranslation("common");
  const [snapshot, setSnapshot] = useState<SecurityLifecycleSnapshot | null>(() => {
    const inspected = settingsReadCache.inspect<SecurityLifecycleSnapshot>(
      "security_lifecycle",
    );
    return inspected.status === "missing" ? null : inspected.value;
  });
  const [err, setErr] = useState<Error | null>(null);
  const [busy, setBusy] = useState(false);
  const [reviewingRelationshipId, setReviewingRelationshipId] = useState<number | null>(null);
  const [reviewingEventId, setReviewingEventId] = useState<number | null>(null);
  const load = useCallback(async (force = false) => {
    setBusy(true);
    const result = await settingsReadCache.load(
      "security_lifecycle",
      () => getSecurityLifecycle(200),
      { force },
    );
    if (result.status === "success") {
      setSnapshot(result.value);
      setErr(null);
    } else if (result.status === "error") {
      setErr(result.error instanceof Error ? result.error : new Error(String(result.error)));
    }
    setBusy(false);
  }, [settingsReadCache]);
  useEffect(() => {
    void load(false);
  }, [load]);
  useEffect(() => settingsReadCache.subscribeInvalidation(
    "security_lifecycle",
    () => { void load(false); },
  ), [load, settingsReadCache]);
  const reviewRelationship = useCallback(async (
    relationshipId: number,
    status: "confirmed" | "rejected",
  ) => {
    setReviewingRelationshipId(relationshipId);
    try {
      await reviewCorporateRelationship(relationshipId, status);
      settingsReadCache.invalidate("security_lifecycle");
      await load(false);
    } catch (error) {
      setErr(error instanceof Error ? error : new Error(String(error)));
    } finally {
      setReviewingRelationshipId(null);
    }
  }, [load, settingsReadCache]);
  const reviewEvent = useCallback(async (
    eventId: number,
    status: "inactive_confirmed" | "renamed_or_transferred" | "unreviewed",
  ) => {
    setReviewingEventId(eventId);
    try {
      await reviewSecurityLifecycleEvent(eventId, status);
      settingsReadCache.invalidate("security_lifecycle");
      await load(false);
    } catch (error) {
      setErr(error instanceof Error ? error : new Error(String(error)));
    } finally {
      setReviewingEventId(null);
    }
  }, [load, settingsReadCache]);
  const errorPresentation = err ? settingsErrorPresentation(err, t, commonT) : null;

  return (
    <div style={{ marginTop: 24, borderTop: "1px solid var(--border, #333)", paddingTop: 16 }}>
      <div className="settings-section-head">
        <div>
          <h2>{t(($) => $.dataStorage.lifecycle.title)}</h2>
          <p className="muted tiny">{t(($) => $.dataStorage.lifecycle.description)}</p>
        </div>
        <button className="btn-ghost" onClick={() => void load(true)} disabled={busy}>
          ↻ {t(($) => $.actions.refreshStatus)}
        </button>
      </div>
      {errorPresentation ? (
        <div className="errorbox"><p className="muted">{errorPresentation.message}</p></div>
      ) : null}
      {developerMode ? (
        <DeveloperDiagnostics diagnostics={[errorPresentation?.diagnostic]} t={t} />
      ) : null}
      {!snapshot ? (
        <p className="muted">{t(($) => $.dataStorage.loading)}</p>
      ) : snapshot.events.length === 0 && snapshot.relationships.length === 0 ? (
        <p className="muted">{t(($) => $.dataStorage.lifecycle.empty)}</p>
      ) : (
        <div className="settings-panel">
          <dl className="ds-kv">
            <dt>{t(($) => $.dataStorage.lifecycle.summary.events)}</dt>
            <dd>{snapshot.summary.event_count.toLocaleString()}</dd>
            <dt>{t(($) => $.dataStorage.lifecycle.summary.reviewRequired)}</dt>
            <dd>{snapshot.summary.review_required.toLocaleString()}</dd>
            <dt>{t(($) => $.dataStorage.lifecycle.summary.pendingDelisting)}</dt>
            <dd>{snapshot.summary.pending_delisting.toLocaleString()}</dd>
            <dt>{t(($) => $.dataStorage.lifecycle.summary.confirmedInactive)}</dt>
            <dd>{snapshot.summary.confirmed_inactive.toLocaleString()}</dd>
            <dt>{t(($) => $.dataStorage.lifecycle.summary.renamedOrTransferred)}</dt>
            <dd>{snapshot.summary.renamed_or_transferred.toLocaleString()}</dd>
            <dt>{t(($) => $.dataStorage.lifecycle.summary.relationshipCandidates)}</dt>
            <dd>{snapshot.summary.relationship_candidates.toLocaleString()}</dd>
          </dl>
          <p className="muted tiny">
            {t(($) => $.dataStorage.lifecycle.reviewBoundary)}
          </p>

          {snapshot.relationships.length > 0 ? (
            <div style={{ marginTop: 16 }}>
              <h3>{t(($) => $.dataStorage.lifecycle.relationships.title)}</h3>
              <div className="settings-table-scroll">
                <table className="ds-table">
                  <thead><tr>
                    <th>{t(($) => $.dataStorage.lifecycle.headings.target)}</th>
                    <th>{t(($) => $.dataStorage.lifecycle.headings.acquirer)}</th>
                    <th>{t(($) => $.dataStorage.lifecycle.headings.status)}</th>
                    <th>{t(($) => $.dataStorage.lifecycle.headings.date)}</th>
                    <th>{t(($) => $.dataStorage.lifecycle.headings.evidence)}</th>
                    <th>{t(($) => $.dataStorage.lifecycle.headings.actions)}</th>
                  </tr></thead>
                  <tbody>
                    {snapshot.relationships.map((relationship) => (
                      <tr key={relationship.id}>
                        <td>{relationship.target_ticker ?? relationship.target_name}</td>
                        <td>{relationship.acquirer_ticker ?? relationship.acquirer_name}</td>
                        <td>{relationship.status === "candidate"
                          ? t(($) => $.dataStorage.lifecycle.relationships.candidate)
                          : relationship.status === "confirmed"
                            ? t(($) => $.dataStorage.lifecycle.relationships.confirmed)
                            : t(($) => $.dataStorage.lifecycle.relationships.rejected)}</td>
                        <td>{relationship.effective_date ?? "—"}</td>
                        <td><a href={relationship.evidence_url} target="_blank" rel="noreferrer">
                          {t(($) => $.dataStorage.lifecycle.openEvidence)}
                        </a></td>
                        <td>
                          <div style={{ display: "flex", gap: 6, whiteSpace: "nowrap" }}>
                            <Button
                              size="compact"
                              tone="secondary"
                              icon={<Check size={14} />}
                              busy={reviewingRelationshipId === relationship.id}
                              disabled={relationship.status === "confirmed"}
                              onClick={() => void reviewRelationship(relationship.id, "confirmed")}
                            >
                              {t(($) => $.dataStorage.lifecycle.relationships.confirmAction)}
                            </Button>
                            <Button
                              size="compact"
                              tone="ghost"
                              icon={<X size={14} />}
                              busy={reviewingRelationshipId === relationship.id}
                              disabled={relationship.status === "rejected"}
                              onClick={() => void reviewRelationship(relationship.id, "rejected")}
                            >
                              {t(($) => $.dataStorage.lifecycle.relationships.rejectAction)}
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : null}

          {snapshot.events.length > 0 ? (
            <div style={{ marginTop: 16 }}>
              <h3>{t(($) => $.dataStorage.lifecycle.events.title)}</h3>
              <div className="settings-table-scroll">
                <table className="ds-table">
                  <thead><tr>
                    <th>{t(($) => $.dataStorage.lifecycle.headings.ticker)}</th>
                    <th>{t(($) => $.dataStorage.lifecycle.headings.event)}</th>
                    <th>{t(($) => $.dataStorage.lifecycle.headings.status)}</th>
                    <th>{t(($) => $.dataStorage.lifecycle.headings.date)}</th>
                    <th>{t(($) => $.dataStorage.lifecycle.headings.evidence)}</th>
                    <th>{t(($) => $.dataStorage.lifecycle.headings.actions)}</th>
                  </tr></thead>
                  <tbody>
                    {snapshot.events.slice(0, 50).map((event) => (
                      <tr key={event.id}>
                        <td>{event.ticker}</td>
                        <td>{lifecycleEventLabel(event, t)}</td>
                        <td>{lifecycleStateLabel(event.lifecycle_state, t)}</td>
                        <td>{event.filing_date}</td>
                        <td><a href={event.evidence_url} target="_blank" rel="noreferrer">
                          {t(($) => $.dataStorage.lifecycle.openEvidence)}
                        </a></td>
                        <td>
                          {event.event_type === "listing_status_review"
                            || event.event_type === "listing_removal_notice" ? (
                              <div style={{ display: "flex", gap: 6, whiteSpace: "nowrap" }}>
                                <Button
                                  size="compact"
                                  tone="secondary"
                                  icon={<Check size={14} />}
                                  busy={reviewingEventId === event.id}
                                  disabled={event.reviewed_state === "inactive_confirmed"}
                                  onClick={() => void reviewEvent(event.id, "inactive_confirmed")}
                                >
                                  {t(($) => $.dataStorage.lifecycle.events.confirmInactiveAction)}
                                </Button>
                                <Button
                                  size="compact"
                                  tone="ghost"
                                  icon={<ArrowRightLeft size={14} />}
                                  busy={reviewingEventId === event.id}
                                  disabled={event.reviewed_state === "renamed_or_transferred"}
                                  onClick={() => void reviewEvent(event.id, "renamed_or_transferred")}
                                >
                                  {t(($) => $.dataStorage.lifecycle.events.markTransferredAction)}
                                </Button>
                                {event.reviewed_state ? (
                                  <Button
                                    size="compact"
                                    tone="ghost"
                                    icon={<RotateCcw size={14} />}
                                    busy={reviewingEventId === event.id}
                                    onClick={() => void reviewEvent(event.id, "unreviewed")}
                                  >
                                    {t(($) => $.dataStorage.lifecycle.events.clearReviewAction)}
                                  </Button>
                                ) : null}
                              </div>
                            ) : null}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}

function coverageToneColor(tone: "ok" | "warn" | "muted" | "bad"): string {
  return tone === "ok" ? "var(--ok)" : tone === "bad" ? "var(--bad)"
    : tone === "warn" ? "var(--warn, #b8860b)" : "var(--muted, #888)";
}

function TradingDayCoveragePanel({
  developerMode,
  settingsReadCache,
}: {
  developerMode: boolean;
  settingsReadCache: SettingsReadCache;
}) {
  const { t } = useTranslation("settings");
  const { t: commonT } = useTranslation("common");
  const [cov, setCov] = useState<TradingDayCoverage | null>(() => {
    const inspected = settingsReadCache.inspect<TradingDayCoverage>(tradingDayCoverageKey(10));
    return inspected.status === "missing" ? null : inspected.value;
  });
  const [err, setErr] = useState<Error | null>(null);
  const [busy, setBusy] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [lookback, setLookback] = useState(10);
  const requestSequenceRef = useRef(0);

  const load = useCallback(async (force = false) => {
    const sequence = ++requestSequenceRef.current;
    const requestedLookback = lookback;
    setBusy(true);
    const result = await settingsReadCache.load(
      tradingDayCoverageKey(requestedLookback),
      () => getTradingDayCoverage(requestedLookback, "15min"),
      { force },
    );
    if (sequence !== requestSequenceRef.current) return;
    if (result.status === "success") {
      setCov(result.value);
      setErr(null);
    } else if (result.status === "error") {
      setErr(result.error instanceof Error ? result.error : new Error(String(result.error)));
    }
    setBusy(false);
  }, [lookback, settingsReadCache]);
  useEffect(() => {
    void load(false);
  }, [load]);
  useEffect(() => settingsReadCache.subscribeInvalidation(
    tradingDayCoverageKey(lookback),
    () => { void load(false); },
  ), [load, lookback, settingsReadCache]);
  const errorPresentation = err ? settingsErrorPresentation(err, t, commonT) : null;
  const calendarHealthLabels = cov
    ? coverageCalendarHealthLabels(cov.calendar_health, t)
    : [];
  const observationHealthLabel = cov
    ? coverageObservationHealthLabel(cov.observation_health, t)
    : null;
  const providerIssueLabels = cov
    ? coverageProviderIssueLabels(cov.provider_errors, t)
    : [];

  return (
    <div style={{ marginTop: 24, borderTop: "1px solid var(--border, #333)", paddingTop: 16 }}>
      <div className="settings-section-head settings-coverage-head">
        <div>
          <h2>{t(($) => $.dataStorage.coverage.title)}</h2>
          <p className="muted tiny">
            {t(($) => $.dataStorage.coverage.lookback, { count: lookback })}{" "}
            {t(($) => $.dataStorage.coverage.description)}{" "}
            <strong>{t(($) => $.dataStorage.coverage.readOnly)}</strong>
          </p>
        </div>
        <div className="settings-coverage-controls">
          <label className="muted tiny">
            {t(($) => $.dataStorage.coverage.lookbackLabel)}{" "}
            <select
              value={lookback}
              disabled={busy}
              onChange={(e) => {
                const nextLookback = Number(e.target.value);
                const inspected = settingsReadCache.inspect<TradingDayCoverage>(
                  tradingDayCoverageKey(nextLookback),
                );
                requestSequenceRef.current += 1;
                setLookback(nextLookback);
                setCov(inspected.status === "missing" ? null : inspected.value);
                setErr(null);
                setBusy(false);
                setExpanded(null);
              }}
            >
              {[10, 15, 30, 60].map((n) => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>
          </label>
          <button className="btn-ghost" onClick={() => void load(true)} disabled={busy}>
            ↻ {t(($) => $.actions.refreshStatus)}
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
          <dl className="ds-kv">
            <dt>{t(($) => $.dataStorage.coverage.facts.universe)}</dt>
            <dd>{" "}{cov.universe_count.toLocaleString()}</dd>
            <dt>{t(($) => $.dataStorage.coverage.facts.interval)}</dt>
            <dd>{" "}{cov.interval}</dd>
            <dt>{t(($) => $.dataStorage.coverage.facts.marketScope)}</dt>
            <dd>{" "}{coverageMarketScopeLabel(cov.market_scope, t)}</dd>
            <dt>{t(($) => $.dataStorage.coverage.facts.session)}</dt>
            <dd>{" "}{coverageSessionLabel(cov.coverage_session, t)}</dd>
            <dt>{t(($) => $.dataStorage.coverage.facts.reviewedThrough)}</dt>
            <dd>{" "}{cov.calendar_health.reviewed_through}</dd>
            <dt>{t(($) => $.dataStorage.coverage.facts.horizonMonths)}</dt>
            <dd>{" "}{cov.calendar_health.forward_horizon_months.toLocaleString()}</dd>
          </dl>
          <p className="muted tiny">
            {t(($) => $.dataStorage.coverage.generatedAt, {
              timestamp: shortTs(cov.generated_at_et),
            })}
          </p>
          {calendarHealthLabels.map((label, index) => (
            <p
              className="tiny"
              data-testid="coverage-calendar-health"
              key={`${index}-${cov.calendar_health.reason_codes[index] ?? "unavailable"}`}
              style={{ color: "var(--warn, #b8860b)" }}
            >
              {label}
            </p>
          ))}
          {observationHealthLabel ? (
            <p
              className="tiny"
              data-testid="coverage-observation-health"
              style={{ color: "var(--warn, #b8860b)" }}
            >
              {observationHealthLabel}
            </p>
          ) : null}
          {providerIssueLabels.map((label) => (
            <p className="tiny refresh-err" data-testid="coverage-provider-issues" key={label}>
              {label}
            </p>
          ))}
          {developerMode ? (
            <DeveloperDiagnostics
              diagnostics={coverageDeveloperDiagnostics(cov)}
              t={t}
            />
          ) : null}
          <div style={{ overflowX: "auto" }}>
            <table className="ds-table" style={{ minWidth: 640, marginTop: 8 }}>
              <thead>
                <tr>
                  <th style={{ textAlign: "left" }}>{t(($) => $.dataStorage.coverage.headings.date)}</th>
                  <th style={{ textAlign: "left" }}>{t(($) => $.dataStorage.coverage.headings.status)}</th>
                  <th style={{ textAlign: "right" }}>{t(($) => $.dataStorage.coverage.headings.expectedSlots)}</th>
                  <th style={{ textAlign: "right" }}>{t(($) => $.dataStorage.coverage.headings.complete)}</th>
                  <th style={{ textAlign: "right" }}>{t(($) => $.dataStorage.coverage.headings.partial)}</th>
                  <th style={{ textAlign: "right" }}>{t(($) => $.dataStorage.coverage.headings.unknown)}</th>
                </tr>
              </thead>
              <tbody>
                {cov.days.map((day) => {
                  const status = coverageStatusLabel(day, t);
                  const open = expanded === day.date;
                  const drillable = day.partial_tickers.length > 0
                    || day.unknown_tickers.length > 0
                    || (day.unmatched_rth_row_count ?? 0) > 0
                    || (developerMode && (
                      day.session_open_at_utc !== null && day.session_close_at_utc !== null
                    ));
                  return (
                    <CoverageRow
                      key={day.date}
                      row={day}
                      label={status.label}
                      tone={status.tone}
                      open={open}
                      drillable={drillable}
                      onToggle={() => setExpanded(open ? null : day.date)}
                      developerMode={developerMode}
                      t={t}
                    />
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function CoverageRow({
  row, label, tone, open, drillable, onToggle, developerMode, t,
}: {
  row: TradingDayRow;
  label: string;
  tone: "ok" | "warn" | "muted" | "bad";
  open: boolean;
  drillable: boolean;
  onToggle: () => void;
  developerMode: boolean;
  t: SettingsT;
}) {
  const dash = (value: number | null) => value === null ? "—" : value.toLocaleString();
  const reasonLabel = coverageDayReasonLabel(row.status_reason_code, t);
  const tickerFacts = coverageTickerFactsPresentation(row, t);
  const quality = coverageDataQualityPresentation(row, 0, t);
  const detailId = `coverage-details-${row.date}`;
  const sessionWindow = developerMode
    && row.session_open_at_utc !== null
    && row.session_close_at_utc !== null
    ? t(($) => $.dataStorage.coverage.drilldown.sessionWindow, {
      open: row.session_open_at_utc,
      close: row.session_close_at_utc,
    })
    : null;
  return (
    <>
      <tr>
        <td>
          {drillable ? (
            <Button
              tone="ghost"
              size="compact"
              icon={open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              aria-expanded={open}
              aria-controls={detailId}
              onClick={onToggle}
            >
              {row.date}
            </Button>
          ) : row.date}
        </td>
        <td>
          <span style={{ color: coverageToneColor(tone) }}>{label}</span>
          {reasonLabel ? <div className="muted tiny">{reasonLabel}</div> : null}
        </td>
        <td style={{ textAlign: "right" }}>{dash(row.expected_slot_count)}</td>
        <td style={{ textAlign: "right" }}>{dash(row.complete_ticker_count)}</td>
        <td style={{ textAlign: "right" }}>{dash(row.partial_ticker_count)}</td>
        <td style={{ textAlign: "right" }}>{dash(row.unknown_ticker_count)}</td>
      </tr>
      {open && drillable && (
        <tr>
          <td
            id={detailId}
            colSpan={6}
            style={{ background: "var(--panel-2, #1a1a1a)", padding: "8px 12px" }}
          >
            {tickerFacts.partialTitle ? (
              <div style={{ marginBottom: 8 }}>
                <p className="tiny" style={{ margin: "0 0 4px" }}>
                  <strong>{tickerFacts.partialTitle}</strong>
                </p>
                {tickerFacts.partialDetails.map((detail, index) => (
                  <p
                    className="tiny"
                    key={`${index}-${row.partial_tickers[index]?.ticker ?? "partial"}`}
                    style={{ margin: "0 0 4px" }}
                  >
                    {detail}
                  </p>
                ))}
              </div>
            ) : null}
            {tickerFacts.unknownTitle ? (
              <div style={{ marginBottom: 8 }}>
                <p className="tiny" style={{ margin: "0 0 4px" }}>
                  <strong>{tickerFacts.unknownTitle}</strong>
                </p>
                <p className="tiny" style={{ margin: "0 0 4px" }}>
                  {tickerFacts.unknownDetail}
                </p>
              </div>
            ) : null}
            {quality.unmatched ? (
              <p className="tiny refresh-err" style={{ margin: "0 0 4px" }}>
                {quality.unmatched}
              </p>
            ) : null}
            {sessionWindow ? (
              <p className="muted tiny" style={{ margin: 0 }}>{sessionWindow}</p>
            ) : null}
          </td>
        </tr>
      )}
    </>
  );
}
