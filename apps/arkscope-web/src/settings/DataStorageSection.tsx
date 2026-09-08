import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  ChevronDown,
  ChevronRight,
  ExternalLink,
  Play,
  RefreshCw,
} from "lucide-react";
import {
  DEFAULT_PRICE_LOOKBACK_DAYS,
  getSecurityLifecycleAutomationStatus,
  getMarketDataStatus,
  listSecurityLifecycleCases,
  getTradingDayCoverage,
  runDueSecurityLifecycleAutomation,
  updateSecurityLifecycleAutomationConfig,
  type MarketDataStatus,
  type SecurityLifecycleAutomationConfig,
  type SecurityLifecycleAutomationSchedulerStatus,
  type SecurityLifecycleAutomationStage,
  type SecurityLifecycleAutomationStatusResponse,
  type SecurityLifecycleCaseListResponse,
  type TradingDayCoverage,
  type TradingDayRow,
} from "../api";
import type { NavigationTarget } from "../shell/navigation";
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
import { Button, IconButton } from "../ui/Button";
import { DeveloperDiagnostics } from "./DeveloperDiagnostics";
import { settingsErrorPresentation } from "./settingsBackendCopy";
import type { SettingsT } from "./settingsCopy";
import {
  tradingDayCoverageKey,
  type SettingsReadCache,
} from "./settingsReadCache";
import { SettingsSubsectionAnchor } from "./SettingsSectionAnchor";
import { PriceCoverageRepair } from "./PriceCoverageRepair";

export function shortTs(iso: string | null | undefined): string {
  return formatSystemTimestamp(iso);
}

function lifecycleAutomationStageLabel(
  stage: SecurityLifecycleAutomationStage,
  t: SettingsT,
): string {
  switch (stage) {
    case "preparing": return t(($) => $.dataStorage.lifecycle.automation.stages.preparing);
    case "sec": return t(($) => $.dataStorage.lifecycle.automation.stages.sec);
    case "listing": return t(($) => $.dataStorage.lifecycle.automation.stages.listing);
    case "ibkr": return t(($) => $.dataStorage.lifecycle.automation.stages.ibkr);
    case "evaluate": return t(($) => $.dataStorage.lifecycle.automation.stages.evaluate);
    case "persist": return t(($) => $.dataStorage.lifecycle.automation.stages.persist);
    case "approve": return t(($) => $.dataStorage.lifecycle.automation.stages.approve);
    case "finalize": return t(($) => $.dataStorage.lifecycle.automation.stages.finalize);
  }
}

function lifecycleAutomationStateLabel(
  status: SecurityLifecycleAutomationSchedulerStatus | "absent" | "invalid",
  t: SettingsT,
): string {
  switch (status) {
    case "running": return t(($) => $.dataStorage.lifecycle.automation.stateLabels.running);
    case "failed": return t(($) => $.dataStorage.lifecycle.automation.stateLabels.failed);
    case "succeeded": return t(($) => $.dataStorage.lifecycle.automation.stateLabels.succeeded);
    case "partial": return t(($) => $.dataStorage.lifecycle.automation.stateLabels.partial);
    case "unavailable": return t(($) => $.dataStorage.lifecycle.automation.stateLabels.unavailable);
    case "not_installed": return t(($) => $.dataStorage.lifecycle.automation.stateLabels.not_installed);
    case "skipped": return t(($) => $.dataStorage.lifecycle.automation.stateLabels.skipped);
    case "absent": return t(($) => $.dataStorage.lifecycle.automation.stateLabels.absent);
    case "invalid": return t(($) => $.dataStorage.lifecycle.automation.stateLabels.invalid);
  }
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
  onNavigateTarget,
}: {
  developerMode?: boolean;
  settingsReadCache: SettingsReadCache;
  onNavigateTarget: (target: NavigationTarget) => void;
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
          onNavigateTarget={onNavigateTarget}
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

function SecurityLifecyclePanel({
  developerMode,
  settingsReadCache,
  onNavigateTarget,
}: {
  developerMode: boolean;
  settingsReadCache: SettingsReadCache;
  onNavigateTarget: (target: NavigationTarget) => void;
}) {
  const { t } = useTranslation("settings");
  const { t: commonT } = useTranslation("common");
  const [snapshot, setSnapshot] = useState<SecurityLifecycleCaseListResponse | null>(() => {
    const inspected = settingsReadCache.inspect<SecurityLifecycleCaseListResponse>(
      "security_lifecycle",
    );
    if (inspected.status === "missing") return null;
    return typeof inspected.value?.count === "number"
      && typeof inspected.value?.data_integrity?.source_missing_count === "number"
      ? inspected.value
      : null;
  });
  const [err, setErr] = useState<Error | null>(null);
  const [busy, setBusy] = useState(false);
  const [automation, setAutomation] = useState<SecurityLifecycleAutomationStatusResponse | null>(null);
  const [automationErr, setAutomationErr] = useState<Error | null>(null);
  const [automationBusy, setAutomationBusy] = useState<"config" | "run" | null>(null);
  const [automationPollRevision, setAutomationPollRevision] = useState(0);
  const automationRequestRef = useRef(0);
  const load = useCallback(async (force = false) => {
    setBusy(true);
    const result = await settingsReadCache.load(
      "security_lifecycle",
      () => listSecurityLifecycleCases({ limit: 1 }),
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
  const loadAutomation = useCallback(async () => {
    const request = ++automationRequestRef.current;
    try {
      const value = await getSecurityLifecycleAutomationStatus();
      if (request !== automationRequestRef.current) return null;
      setAutomation(value);
      setAutomationErr(null);
      return value;
    } catch (error) {
      if (request !== automationRequestRef.current) return null;
      setAutomationErr(error instanceof Error ? error : new Error(String(error)));
      return null;
    } finally {
      if (request === automationRequestRef.current) {
        setAutomationPollRevision((current) => current + 1);
      }
    }
  }, []);
  useEffect(() => {
    void loadAutomation();
  }, [loadAutomation]);
  const automationRunning = automation?.last_status === "running"
    || Boolean(automation?.current_progress.length);
  useEffect(() => {
    if (!automationRunning) return undefined;
    const timer = window.setTimeout(() => { void loadAutomation(); }, 1_000);
    return () => window.clearTimeout(timer);
  }, [automationRunning, automation, automationPollRevision, loadAutomation]);

  const saveAutomationConfig = async (next: SecurityLifecycleAutomationConfig) => {
    if (automationBusy || automationRunning || automation?.config_status !== "valid") return;
    setAutomationBusy("config");
    setAutomationErr(null);
    try {
      const response = await updateSecurityLifecycleAutomationConfig(next);
      setAutomation((current) => current ? { ...current, ...response } : current);
      await loadAutomation();
    } catch (error) {
      setAutomationErr(error instanceof Error ? error : new Error(String(error)));
    } finally {
      setAutomationBusy(null);
    }
  };
  const runDueAutomation = async () => {
    if (automationBusy || automationRunning || automation?.config_status !== "valid") return;
    setAutomationBusy("run");
    setAutomationErr(null);
    try {
      await runDueSecurityLifecycleAutomation();
      await loadAutomation();
    } catch (error) {
      setAutomationErr(error instanceof Error ? error : new Error(String(error)));
    } finally {
      setAutomationBusy(null);
    }
  };
  const errorPresentation = err ? settingsErrorPresentation(err, t, commonT) : null;
  const automationErrorPresentation = automationErr
    ? settingsErrorPresentation(automationErr, t, commonT)
    : null;
  const config = automation?.config_status === "valid" ? automation.config : null;
  const automationDisabled = !config || automationBusy !== null || automationRunning;
  const currentProgress = automation?.current_progress[0] ?? null;
  const incidentCaseCount = automation
    ? Object.keys(automation.active_incident?.case_failures ?? {}).length
    : 0;
  const schedulerIncident = Boolean(automation?.active_incident?.scheduler_failure);
  const telemetryInvalid = automation?.telemetry_status === "invalid";
  const lastAttemptProblem = automation?.last_status === "failed"
    || automation?.last_status === "unavailable"
    || automation?.last_status === "not_installed"
    || automation?.last_status === "skipped"
    ? automation.last_status
    : null;
  const showRuntimeStatus = schedulerIncident || incidentCaseCount > 0
    || automationRunning || telemetryInvalid || lastAttemptProblem;
  const scheduleState = automation?.schedule.status ?? "invalid";
  const scheduleLabel = scheduleState === "scheduled"
    ? t(($) => $.dataStorage.lifecycle.automation.scheduleLabels.scheduled)
    : scheduleState === "due"
      ? t(($) => $.dataStorage.lifecycle.automation.scheduleLabels.due)
      : scheduleState === "disabled"
        ? t(($) => $.dataStorage.lifecycle.automation.scheduleLabels.disabled)
        : t(($) => $.dataStorage.lifecycle.automation.scheduleLabels.invalid);

  return (
    <div className="lifecycle-settings">
      <div className="lifecycle-settings-header">
        <h2>{t(($) => $.dataStorage.lifecycle.title)}</h2>
        <div className="lifecycle-settings-actions">
          <Button
            size="compact"
            tone="primary"
            icon={<ExternalLink size={15} />}
            onClick={() => onNavigateTarget({ kind: "universe_lifecycle" })}
          >
            {t(($) => $.dataStorage.lifecycle.openWorkflow)}
          </Button>
          <IconButton
            size="compact"
            tone="ghost"
            label={t(($) => $.actions.refreshStatus)}
            icon={<RefreshCw size={15} />}
            onClick={() => void Promise.all([load(true), loadAutomation()])}
            disabled={busy}
          />
          <Button
            className="lifecycle-automation-run"
            size="compact"
            tone="secondary"
            icon={<Play size={15} />}
            busy={automationBusy === "run"}
            disabled={automationDisabled}
            onClick={() => void runDueAutomation()}
          >
            {automationBusy === "run"
              ? t(($) => $.dataStorage.lifecycle.automation.runningCommand)
              : t(($) => $.dataStorage.lifecycle.automation.runDue)}
          </Button>
        </div>
      </div>
      {errorPresentation ? (
        <div className="errorbox"><p className="muted">{errorPresentation.message}</p></div>
      ) : null}
      {automationErrorPresentation ? (
        <div className="errorbox"><p className="muted">{automationErrorPresentation.message}</p></div>
      ) : null}
      {developerMode ? (
        <DeveloperDiagnostics diagnostics={[errorPresentation?.diagnostic]} t={t} />
      ) : null}
      <section className="lifecycle-automation-settings" aria-labelledby="lifecycle-automation-title">
        <h3 id="lifecycle-automation-title">
          {t(($) => $.dataStorage.lifecycle.automation.title)}
        </h3>
        {!automation ? (
          <p className="muted tiny">{t(($) => $.dataStorage.loading)}</p>
        ) : (
          <>
            <dl className="ds-kv lifecycle-automation-status">
              <dt>{t(($) => $.dataStorage.lifecycle.automation.schedule)}</dt>
              <dd>
                <strong data-automation-schedule={scheduleState}>{scheduleLabel}</strong>
              </dd>
              <dt>{t(($) => $.dataStorage.lifecycle.automation.nextScheduled)}</dt>
              <dd>{automation.schedule.next_scheduled_at
                ? shortTs(automation.schedule.next_scheduled_at)
                : t(($) => $.dataStorage.lifecycle.automation.notScheduled)}</dd>
              {showRuntimeStatus ? (
                <>
                  <dt>{t(($) => $.dataStorage.lifecycle.automation.state)}</dt>
                  <dd className="lifecycle-automation-notices">
                    {schedulerIncident ? (
                      <strong data-automation-state="incident">
                        {t(($) => $.dataStorage.lifecycle.automation.incidentScheduler)}
                      </strong>
                    ) : null}
                    {incidentCaseCount > 0 ? (
                      <strong data-automation-state="incident">
                        {incidentCaseCount === 1
                          ? t(($) => $.dataStorage.lifecycle.automation.incidentCases_one, {
                            count: incidentCaseCount,
                          })
                          : t(($) => $.dataStorage.lifecycle.automation.incidentCases_other, {
                            count: incidentCaseCount,
                          })}
                      </strong>
                    ) : null}
                    {automationRunning ? (
                      <strong data-automation-state="running">
                        {lifecycleAutomationStateLabel("running", t)}
                      </strong>
                    ) : null}
                    {telemetryInvalid ? (
                      <strong data-automation-state="invalid">
                        {lifecycleAutomationStateLabel("invalid", t)}
                      </strong>
                    ) : null}
                    {lastAttemptProblem && !automationRunning && !schedulerIncident
                      && incidentCaseCount === 0 && !telemetryInvalid ? (
                        <strong data-automation-state={lastAttemptProblem}>
                          {lifecycleAutomationStateLabel(lastAttemptProblem, t)}
                        </strong>
                      ) : null}
                  </dd>
                </>
              ) : null}
              {currentProgress?.current_stage ? (
                <>
                  <dt>{t(($) => $.dataStorage.lifecycle.automation.currentStage)}</dt>
                  <dd>{lifecycleAutomationStageLabel(currentProgress.current_stage, t)}</dd>
                </>
              ) : null}
              <dt>{t(($) => $.dataStorage.lifecycle.automation.lastResult)}</dt>
              <dd>{automation.last_result
                ? t(($) => $.dataStorage.lifecycle.automation.resultSummary, {
                  processed: automation.last_result.processed,
                  accepted: automation.last_result.accepted,
                  drafted: automation.last_result.drafted,
                  blocked: automation.last_result.blocked,
                  failed: automation.last_result.failed,
                })
                : t(($) => $.dataStorage.lifecycle.automation.noResult)}</dd>
              <dt>{t(($) => $.dataStorage.lifecycle.automation.lastAttempt)}</dt>
              <dd>{automation.schedule.last_attempt_at
                ? shortTs(automation.schedule.last_attempt_at)
                : t(($) => $.dataStorage.lifecycle.automation.notScheduled)}</dd>
            </dl>

            <div
              className="lifecycle-automation-controls"
              data-testid="lifecycle-automation-controls"
            >
              {config ? (
                <>
                  <label className="ds-toggle lifecycle-automation-toggle">
                    <input
                      type="checkbox"
                      aria-label={t(($) => $.dataStorage.lifecycle.automation.backgroundEnabled)}
                      checked={config.enabled}
                      disabled={automationDisabled}
                      onChange={(event) => void saveAutomationConfig({
                        ...config,
                        enabled: event.target.checked,
                      })}
                    />
                    <span>{t(($) => $.dataStorage.lifecycle.automation.backgroundEnabled)}</span>
                  </label>
                  <details className="lifecycle-automation-advanced">
                    <summary>{t(($) => $.dataStorage.lifecycle.automation.advancedSettings)}</summary>
                    <div className="lifecycle-automation-fields">
                      <label className="lifecycle-automation-field">
                        <span>{t(($) => $.dataStorage.lifecycle.automation.interval)}</span>
                        <select
                          aria-label={t(($) => $.dataStorage.lifecycle.automation.interval)}
                          value={config.interval_minutes}
                          disabled={automationDisabled}
                          onChange={(event) => void saveAutomationConfig({
                            ...config,
                            interval_minutes: Number(event.target.value),
                          })}
                        >
                          {[5, 15, 30, 60, 360, 1440].map((minutes) => (
                            <option value={minutes} key={minutes}>
                              {t(($) => $.dataStorage.lifecycle.automation.intervalMinutes, {
                                count: minutes,
                              })}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="lifecycle-automation-field">
                        <span>{t(($) => $.dataStorage.lifecycle.automation.batchSize)}</span>
                        <select
                          aria-label={t(($) => $.dataStorage.lifecycle.automation.batchSize)}
                          value={config.batch_limit}
                          disabled={automationDisabled}
                          onChange={(event) => void saveAutomationConfig({
                            ...config,
                            batch_limit: event.target.value === "1" ? 1 : 2,
                          })}
                        >
                          {([1, 2] as const).map((limit) => (
                            <option value={limit} key={limit}>
                              {t(($) => $.dataStorage.lifecycle.automation.batchOption, {
                                count: limit,
                              })}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="ds-toggle lifecycle-automation-toggle">
                        <input
                          type="checkbox"
                          aria-label={t(($) => $.dataStorage.lifecycle.automation.applyTransitions)}
                          checked={config.apply_profile_transitions}
                          disabled={automationDisabled}
                          onChange={(event) => void saveAutomationConfig({
                            ...config,
                            apply_profile_transitions: event.target.checked,
                          })}
                        />
                        <span>{t(($) => $.dataStorage.lifecycle.automation.applyTransitions)}</span>
                      </label>
                    </div>
                  </details>
                </>
              ) : (
                <p className="errorbox lifecycle-automation-invalid">
                  {t(($) => $.dataStorage.lifecycle.automation.invalidConfig)}
                </p>
              )}
            </div>
          </>
        )}
      </section>
      <details className="lifecycle-settings-diagnostics">
        <summary>{t(($) => $.dataStorage.lifecycle.summary.diagnostics)}</summary>
        {!snapshot ? (
          <p className="muted tiny">{t(($) => $.dataStorage.loading)}</p>
        ) : (
          <dl className="ds-kv lifecycle-automation-status">
            <dt>{t(($) => $.dataStorage.lifecycle.summary.activeCases)}</dt>
            <dd>{snapshot.count.toLocaleString()}</dd>
            <dt>{t(($) => $.dataStorage.lifecycle.summary.sourceMissing)}</dt>
            <dd>{snapshot.data_integrity.source_missing_count.toLocaleString()}</dd>
          </dl>
        )}
      </details>
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
    const inspected = settingsReadCache.inspect<TradingDayCoverage>(tradingDayCoverageKey(DEFAULT_PRICE_LOOKBACK_DAYS));
    return inspected.status === "missing" ? null : inspected.value;
  });
  const [err, setErr] = useState<Error | null>(null);
  const [busy, setBusy] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [lookback, setLookback] = useState(DEFAULT_PRICE_LOOKBACK_DAYS);
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
          <PriceCoverageRepair coverage={cov} t={t} onCompleted={() => void load(true)} />
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
