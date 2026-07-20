import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  getProvidersConfig,
  getProvidersHealth,
  getSAExtensionHealth,
  getSchedule,
  importProviderConfigField,
  putProviderConfig,
  putSchedule,
  runScheduleNow,
  testProvider,
  type ProviderConfigEntry,
  type ProviderConfigField,
  type ProviderConfigSetupState,
  type ProviderHealth,
  type ProviderTestResult,
  type ProvidersHealthResponse,
  type SAExtensionHealthResponse,
  type ScheduleRunResult,
  type ScheduleSourceState,
} from "../api";
import {
  providerHealthStatusLabel,
  schedulerBodyBacklogPresentation,
  schedulerStateLabel,
} from "../marketDataDisplay";
import { displaySAExtensionSegments } from "../saExtensionHealthDisplay";
import { SourceRunProgress } from "../SourceRunProgress";
import {
  durableScheduleCommonState,
  providerCommonState,
  saSegmentCommonState,
} from "../dataSourcesPresentation";
import {
  dataSourceScheduleLifecycleChanged,
  dataSourceSchedulePollMs,
  type DataSourceScheduleMap,
} from "../dataSourceSchedulePolling";
import { formatSystemTimestamp } from "../timeDisplay";
import { ConfirmDialog, StatusBadge } from "../ui";
import { shortTs } from "./DataStorageSection";
import { DeveloperDiagnostics } from "./DeveloperDiagnostics";
import {
  diagnosticValue,
  providerClientDomainLabel,
  providerConfigFieldLabel,
  providerKeySourceLabel,
  providerName,
  providerTestCopy,
  scheduleOutcomeCopy,
  scheduleSourceCopy,
  settingsErrorPresentation,
} from "./settingsBackendCopy";
import type { SettingsT } from "./settingsCopy";
import {
  CLEAR_SETTINGS_NAVIGATION_GUARD,
  type SettingsNavigationGuardReporter,
} from "./settingsNavigationGuard";

function shortDate(iso: string | null | undefined): string {
  return iso ? iso.slice(0, 10) : "—";
}

function formatCount(value: number | null | undefined): string {
  return typeof value === "number" && Number.isFinite(value)
    ? value.toLocaleString("en-US")
    : "—";
}

type FredSnapshotSignal = {
  available: boolean;
  series_count: number | null;
  observation_count: number | null;
  release_dates_count: number | null;
  latest_fetched_at: string | null;
};

function fredSnapshotFromSignals(signals: ProviderHealth["signals"] | undefined): FredSnapshotSignal | null {
  const raw = signals?.local_snapshot;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  const obj = raw as Record<string, unknown>;
  const numberField = (key: string): number | null =>
    typeof obj[key] === "number" && Number.isFinite(obj[key]) ? obj[key] as number : null;
  return {
    available: obj.available === true,
    series_count: numberField("series_count"),
    observation_count: numberField("observation_count"),
    release_dates_count: numberField("release_dates_count"),
    latest_fetched_at: typeof obj.latest_fetched_at === "string" ? obj.latest_fetched_at : null,
  };
}

function boolSignal(signals: ProviderHealth["signals"] | undefined, key: string): boolean | null {
  const value = signals?.[key];
  return typeof value === "boolean" ? value : null;
}

function fredProviderDetail(p: ProviderHealth, t: SettingsT): string | null {
  if (p.id !== "fred") return null;
  const snap = fredSnapshotFromSignals(p.signals);
  const auto = boolSignal(p.signals, "auto_refresh_enabled");
  const parts: string[] = [];
  if (snap?.available) {
    parts.push(
      t(($) => $.dataSources.fred.snapshotAvailable, {
        // i18next reserves `count` as numeric even for this non-plural display key.
        count: formatCount(snap.series_count) as unknown as number,
        value: formatCount(snap.observation_count),
      }),
    );
  } else {
    parts.push(t(($) => $.dataSources.fred.noData));
  }
  if (snap?.latest_fetched_at) {
    parts.push(t(($) => $.dataSources.fred.latestFetched, {
      timestamp: shortDate(snap.latest_fetched_at),
    }));
  }
  parts.push(auto === true
    ? t(($) => $.dataSources.fred.autoEnabled)
    : auto === false
      ? t(($) => $.dataSources.fred.autoDisabled)
      : t(($) => $.dataSources.fred.autoUnknown));
  return parts.join(" · ");
}

// Derived client-id chips for the IBKR base field. Offsets/labels come from the
// BACKEND (single authority: data_sources/ibkr_client_id.py via the config view) —
// adding a domain there shows up here with no frontend change. A valid numeric
// draft previews post-save ids; otherwise the backend's effective ids are shown
// (parseInt would mis-preview "1abc"; the backend rejects such bases on save).
function ibkrClientIdChips(
  domains: NonNullable<ProviderConfigField["client_id_domains"]>,
  draft: string,
  t: SettingsT,
): { preview: boolean; text: string } {
  const s = draft.trim();
  const base = /^\d+$/.test(s) ? Number(s) : null;
  const text = domains
    .map((d) => `${providerClientDomainLabel(d.domain, t)}=${base !== null ? base + d.offset : d.effective_id ?? "？"}`)
    .join("、");
  return { preview: base !== null, text };
}

function ProviderHealthState({ provider, t }: { provider: ProviderHealth; t: SettingsT }) {
  const state = providerCommonState(provider.status);
  return state === null
    ? <span className="muted tiny">{providerHealthStatusLabel(provider, t)}</span>
    : <StatusBadge state={state} label={providerHealthStatusLabel(provider, t)} />;
}

type DataSourcesOutcome =
  | { kind: "error"; error: unknown }
  | { kind: "schedule"; source: string; result: ScheduleRunResult };

type ProviderTestState =
  | { kind: "running" }
  | { kind: "result"; result: ProviderTestResult }
  | { kind: "error"; error: unknown };

export function DataSourcesSection({
  onNavigationGuardChange,
  developerMode = false,
}: {
  onNavigationGuardChange?: SettingsNavigationGuardReporter;
  developerMode?: boolean;
}) {
  const { t } = useTranslation("settings");
  const [schedule, setSchedule] = useState<Record<string, ScheduleSourceState> | null>(null);
  const [health, setHealth] = useState<ProvidersHealthResponse | null>(null);
  const [saExtensionHealth, setSaExtensionHealth] = useState<SAExtensionHealthResponse | null>(null);
  const [cfg, setCfg] = useState<Record<string, ProviderConfigEntry> | null>(null);
  const [cfgSetup, setCfgSetup] = useState<ProviderConfigSetupState | null>(null);
  const [outcome, setOutcome] = useState<DataSourcesOutcome | null>(null);
  const [busy, setBusy] = useState<string>(""); // source id with an in-flight mutation
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [keyDrafts, setKeyDrafts] = useState<Record<string, string>>({}); // "provider.field"
  const [testResults, setTestResults] = useState<Record<string, ProviderTestState>>({});
  const [pendingGuardedEdit, setPendingGuardedEdit] = useState<{
    provider: string;
    field: string;
    value: string;
    fieldMeta: ProviderConfigField;
  } | null>(null);
  const guardedEditTriggerRef = useRef<HTMLButtonElement>(null);
  const scheduleRef = useRef<DataSourceScheduleMap | null>(null);
  const scheduleRequestSequenceRef = useRef(0);
  const acceptedScheduleSequenceRef = useRef(0);
  const schedulePollInFlightRef = useRef<Promise<void> | null>(null);
  const dataSourcesMountedRef = useRef(true);
  const dirty = Object.values(drafts).some((value) => value !== "")
    || Object.values(keyDrafts).some((value) => value !== "")
    || pendingGuardedEdit !== null;
  const navigationBusy = busy !== "";

  useEffect(() => {
    onNavigationGuardChange?.({
      dirty,
      busy: navigationBusy,
      reason: navigationBusy
        ? t(($) => $.dataSources.guard.busy)
        : dirty
          ? t(($) => $.dataSources.guard.dirty)
          : null,
    });
  }, [dirty, navigationBusy, onNavigationGuardChange, t]);

  useEffect(() => () => {
    onNavigationGuardChange?.(CLEAR_SETTINGS_NAVIGATION_GUARD);
  }, [onNavigationGuardChange]);

  useEffect(() => {
    dataSourcesMountedRef.current = true;
    return () => {
      dataSourcesMountedRef.current = false;
    };
  }, []);

  const acceptSchedule = useCallback((
    next: DataSourceScheduleMap,
    sequence: number,
  ): { accepted: boolean; lifecycleChanged: boolean } => {
    if (sequence < acceptedScheduleSequenceRef.current) {
      return { accepted: false, lifecycleChanged: false };
    }
    acceptedScheduleSequenceRef.current = sequence;
    const previous = scheduleRef.current;
    scheduleRef.current = next;
    setSchedule(next);
    return {
      accepted: true,
      lifecycleChanged: dataSourceScheduleLifecycleChanged(previous, next),
    };
  }, []);

  const load = useCallback(async () => {
    const scheduleSequence = ++scheduleRequestSequenceRef.current;
    const [rs, rh, rc] = await Promise.allSettled([
      getSchedule(), getProvidersHealth(), getProvidersConfig()]);
    if (!dataSourcesMountedRef.current) return;
    if (rs.status === "fulfilled") acceptSchedule(rs.value.sources, scheduleSequence);
    if (rh.status === "fulfilled") setHealth(rh.value);
    if (rc.status === "fulfilled") {
      setCfg(rc.value.providers);
      setCfgSetup(rc.value.setup);
    }
    const bad = [rs, rh, rc].filter((r): r is PromiseRejectedResult => r.status === "rejected");
    setOutcome(bad.length
      ? {
          kind: "error",
          error: new Error(
            bad.map((r) => (r.reason instanceof Error ? r.reason.message : String(r.reason)))
              .join("; "),
          ),
        }
      : null);
  }, [acceptSchedule]);

  const pollSchedule = useCallback((): Promise<void> => {
    if (schedulePollInFlightRef.current) return schedulePollInFlightRef.current;
    const sequence = ++scheduleRequestSequenceRef.current;
    const request = (async () => {
      try {
        const next = await getSchedule();
        if (!dataSourcesMountedRef.current) return;
        const accepted = acceptSchedule(next.sources, sequence);
        if (accepted.accepted && accepted.lifecycleChanged) {
          await load();
        }
      } catch {
        // Passive polling preserves the last accepted schedule truth.
      }
    })().finally(() => {
      if (schedulePollInFlightRef.current === request) {
        schedulePollInFlightRef.current = null;
      }
    });
    schedulePollInFlightRef.current = request;
    return request;
  }, [acceptSchedule, load]);

  useEffect(() => {
    void load();
  }, [load]);

  // Extension health spawns a native-host subprocess server-side — fetch once
  // on mount and via the manual 重新檢查 button only, NEVER on the 5s
  // scheduler-status poll.
  useEffect(() => {
    let cancelled = false;
    getSAExtensionHealth()
      .then((v) => {
        if (!cancelled) setSaExtensionHealth(v);
      })
      .catch(() => {
        if (!cancelled) setSaExtensionHealth(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Discover background starts while idle, then observe active runs more closely.
  const anyRunning = !!schedule && Object.values(schedule).some((s) => s.running);
  const schedulePollIntervalMs = dataSourceSchedulePollMs(schedule);
  useEffect(() => {
    const timer = window.setInterval(
      () => { void pollSchedule(); },
      schedulePollIntervalMs,
    );
    const onFocus = () => { void pollSchedule(); };
    window.addEventListener("focus", onFocus);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", onFocus);
    };
  }, [pollSchedule, schedulePollIntervalMs]);

  async function setEnabled(source: string, enabled: boolean) {
    if (busy) return;
    setBusy(source);
    try {
      await putSchedule(source, { enabled });
      await load();
    } catch (e) {
      setOutcome({ kind: "error", error: e });
    } finally {
      setBusy("");
    }
  }

  async function applyInterval(source: string) {
    const raw = drafts[source];
    const n = Number(raw);
    if (!raw || !Number.isFinite(n)) return;
    if (busy) return;
    setBusy(source);
    try {
      await putSchedule(source, { interval_minutes: Math.round(n) });
      setDrafts((d) => ({ ...d, [source]: "" }));
      await load();
    } catch (e) {
      setOutcome({ kind: "error", error: e });
    } finally {
      setBusy("");
    }
  }

  async function runNow(source: string) {
    if (busy) return;
    setBusy(source);
    try {
      const r = await runScheduleNow(source);
      if (r.status === "skipped") {
        setOutcome({ kind: "schedule", source, result: r });
      }
      await load();
    } catch (e) {
      setOutcome({ kind: "error", error: e });
    } finally {
      setBusy("");
    }
  }

  async function importField(provider: string, field: string, sourceEnvVar: string | null) {
    if (busy) return;
    setBusy(`import.${provider}.${field}`);
    try {
      await importProviderConfigField(provider, field, sourceEnvVar);
      await load();
    } catch (e) {
      setOutcome({ kind: "error", error: e });
    } finally {
      setBusy("");
    }
  }

  async function commitField(
    provider: string,
    field: string,
    value: string | null,
    fieldMeta?: ProviderConfigField,
  ): Promise<boolean> {
    if (busy) return false;
    setBusy(`${provider}.${field}`);
    try {
      await putProviderConfig(
        provider,
        { [field]: value },
        fieldMeta?.guarded ? { [field]: true } : undefined,
      );
      setKeyDrafts((d) => ({ ...d, [`${provider}.${field}`]: "" }));
      await load();
      return true;
    } catch (e) {
      setOutcome({ kind: "error", error: e });
      return false;
    } finally {
      setBusy("");
    }
  }

  async function saveField(
    provider: string,
    field: string,
    value: string | null,
    fieldMeta?: ProviderConfigField,
  ) {
    if (busy) return;
    if (fieldMeta?.guarded && value !== null) {
      setPendingGuardedEdit({ provider, field, value, fieldMeta });
      return;
    }
    await commitField(provider, field, value, fieldMeta);
  }

  async function confirmGuardedEdit() {
    if (!pendingGuardedEdit || busy) return;
    const saved = await commitField(
      pendingGuardedEdit.provider,
      pendingGuardedEdit.field,
      pendingGuardedEdit.value,
      pendingGuardedEdit.fieldMeta,
    );
    if (saved) setPendingGuardedEdit(null);
  }

  async function runTest(provider: string) {
    if (busy) return;
    setBusy(`test.${provider}`);
    setTestResults((results) => ({ ...results, [provider]: { kind: "running" } }));
    try {
      const r = await testProvider(provider);
      setTestResults((results) => ({
        ...results,
        [provider]: { kind: "result", result: r },
      }));
    } catch (e) {
      setTestResults((results) => ({
        ...results,
        [provider]: { kind: "error", error: e },
      }));
    } finally {
      setBusy("");
    }
  }

  async function reloadSAExtensionHealth() {
    if (busy) return;
    setBusy("sa.extension-health");
    try {
      setSaExtensionHealth(await getSAExtensionHealth());
    } catch (e) {
      setOutcome({ kind: "error", error: e });
    } finally {
      setBusy("");
    }
  }

  function renderProviderConfigField(pid: string, f: ProviderConfigField) {
    const draftKey = `${pid}.${f.field}`;
    const draft = keyDrafts[draftKey] ?? "";
    const fieldLabel = providerConfigFieldLabel(pid, f.field, t);
    const envControlled = f.env_var === "IBKR_CLIENT_ID" && f.effective_source === "env";
    const chips = f.env_var === "IBKR_CLIENT_ID" && (f.client_id_domains?.length ?? 0) > 0
      ? ibkrClientIdChips(f.client_id_domains!, envControlled ? "" : draft, t)
      : null;
    const caption = envControlled
      ? t(($) => $.dataSources.providers.config.clientIdsEnvironmentControlled)
      : chips?.preview
        ? t(($) => $.dataSources.providers.config.clientIdsAfterSave)
        : t(($) => $.dataSources.providers.config.clientIdsCurrent);

    return (
      <div className="provider-config-field" key={draftKey}>
        <div className="provider-config-field-label">{fieldLabel}</div>
        <div className="provider-config-field-current">
          {f.effective_source === "missing"
            ? <span className="ds-chip ds-missing_key">
                {providerKeySourceLabel(f.effective_source, t)}
              </span>
            : <>
                <span className="mono">
                  {f.app_value_set
                    ? f.app_value_masked
                    : <>（{t(($) => $.dataSources.labels.external)}）</>}
                </span>
                {f.defaulted && (
                  <span className="muted tiny">
                    {" · "}{t(($) => $.dataSources.labels.defaultValue)}
                  </span>
                )}
                <span className="muted tiny">
                  （{providerKeySourceLabel(f.effective_source, t)}）
                </span>
                {f.needs_import && (
                  <button className="btn-ghost tiny"
                    disabled={busy === `import.${pid}.${f.field}`}
                    onClick={() => void importField(pid, f.field, f.import_source)}>
                    {t(($) => $.dataSources.providers.config.importValue)}
                  </button>
                )}
                {f.needs_import && (
                  <span className="muted tiny">
                    {t(($) => $.dataSources.labels.recommendedImport)}
                  </span>
                )}
              </>}
        </div>
        <div className="provider-config-field-edit">
          <input
            className="ds-interval ds-keyinput"
            type={f.secret ? "password" : "text"}
            placeholder={f.secret
              ? t(($) => $.dataSources.providers.config.pasteKey)
              : fieldLabel}
            value={draft}
            disabled={busy === draftKey}
            onChange={(e) => setKeyDrafts((d) => ({ ...d, [draftKey]: e.target.value }))}
            onKeyDown={(e) => {
              if (e.key === "Enter" && draft) void saveField(pid, f.field, draft, f);
            }}
          />
          {draft && (
            <button
              ref={f.guarded ? guardedEditTriggerRef : undefined}
              className="btn-ghost tiny"
              onClick={() => void saveField(pid, f.field, draft, f)}
            >
              {t(($) => $.actions.save)}
            </button>
          )}
          {f.app_value_set && (
            <button className="btn-ghost tiny" onClick={() => void saveField(pid, f.field, null, f)}>
              {t(($) => $.actions.clear)}
            </button>
          )}
        </div>
        {chips && (
          <div className="provider-config-field-hint muted tiny">
            {caption}{chips.text}
          </div>
        )}
      </div>
    );
  }

  function jobOutcome(jobName: string): string {
    const row = health?.jobs?.[jobName] as
      | { status?: string; finished_at?: string; error?: string }
      | undefined;
    if (!row) return "—";
    const ts = shortTs(row.finished_at ?? null);
    if (row.status === "succeeded") return `✓ ${ts}`;
    if (row.status === "failed") return `✗ ${ts}`;
    if (row.status === "running") return t(($) => $.actions.running);
    return row.status ?? "—";
  }

  function renderLastRun(source: string, s: ScheduleSourceState) {
    const skipped = s.last_result?.status === "skipped";
    const historyState = durableScheduleCommonState(s);
    const durableSkipped = s.durable_state?.last_status === "skipped";
    const ss = schedulerStateLabel(s.durable_state ?? null, t);
    const bodyBacklog = schedulerBodyBacklogPresentation(s.durable_state ?? null, t);

    return (
      <div className="ds-last-run">
        <div className="ds-last-run-summary">
          <span>{jobOutcome(s.job_name)}</span>
          {skipped && (
            <StatusBadge
              state="blocked"
              label={t(($) => $.dataSources.schedule.triggerSkipped)}
            />
          )}
          {historyState !== null ? (
            <StatusBadge
              state={historyState}
              label={ss.label}
            />
          ) : durableSkipped && !skipped ? (
            <span className="muted tiny">{ss.label}</span>
          ) : null}
          {ss.needsContinue && (
            <button
              className="btn-ghost"
              disabled={!!busy || s.running}
              onClick={() => void runNow(source)}
              title={t(($) => $.dataSources.schedule.continue.title)}
            >
              {t(($) => $.dataSources.schedule.continue.label)}
            </button>
          )}
        </div>
        {bodyBacklog && (
          <div className={`tiny ${bodyBacklog.tone === "warn" ? "refresh-err" : "muted"}`}>
            {bodyBacklog.label}
            {bodyBacklog.earliestNextRetryAt
              ? <>
                  {" · "}
                  {t(($) => $.dataSources.schedule.backlog.earliest, {
                    timestamp: formatSystemTimestamp(bodyBacklog.earliestNextRetryAt),
                  })}
                </>
              : ""}
          </div>
        )}
      </div>
    );
  }

  function providerTestPresentation(provider: string): string | null {
    const state = testResults[provider];
    if (!state) return null;
    if (state.kind === "running") return t(($) => $.actions.testing);
    if (state.kind === "error") return t(($) => $.errors.testFailed);
    const mark = state.result.ok === true ? "✓" : state.result.ok === false ? "✗" : "—";
    const latency = state.result.latency_ms == null ? null : `${state.result.latency_ms}ms`;
    return [mark, providerTestCopy(provider, state.result.ok, t), latency]
      .filter((value): value is string => value !== null)
      .join(" · ");
  }

  const outcomePresentation = outcome?.kind === "error"
    ? settingsErrorPresentation(outcome.error, t)
    : null;
  const outcomeMessage = outcome?.kind === "schedule"
    ? scheduleOutcomeCopy(outcome.source, outcome.result, t)
    : outcomePresentation?.message ?? null;
  const jobDiagnostics = Object.values(health?.jobs ?? {}).map((row) => row.error);
  const providerDiagnostics = (health?.providers ?? []).flatMap((provider) => [
    provider.detail,
    provider.last_error,
    provider.disabled_reason,
  ]);
  const configDiagnostics = Object.values(cfg ?? {}).flatMap((entry) =>
    entry.fields.map((field) => field.guard_reason));
  const scheduleDiagnostics = Object.values(schedule ?? {}).flatMap((source) => [
    source.retired_reason,
    source.last_result?.reason,
    source.durable_state?.last_error,
    source.durable_state?.running_stale_reason,
  ]);
  const providerTestDiagnostics = Object.values(testResults).map((state) => {
    if (state.kind === "result") return state.result.detail;
    if (state.kind === "error") return state.error;
    return null;
  });
  const diagnostics = [
    outcomePresentation?.diagnostic,
    outcome?.kind === "schedule" ? outcome.result.reason : null,
    ...(health?.notes ?? []),
    ...jobDiagnostics,
    ...providerDiagnostics,
    ...(saExtensionHealth?.segments.map((segment) => segment.detail) ?? []),
    cfgSetup?.reason,
    ...configDiagnostics,
    ...scheduleDiagnostics,
    ...providerTestDiagnostics,
  ].map((value) => diagnosticValue(developerMode, value));

  return (
    <div>
      <div className="settings-section-head">
        <div>
          <h2>{t(($) => $.dataSources.section.title)}</h2>
          <p className="muted tiny">
            {t(($) => $.dataSources.section.description)}
          </p>
        </div>
        <button className="btn-ghost" onClick={() => void load()} disabled={!!busy}>
          ↻ {t(($) => $.actions.refresh)}
          {anyRunning
            ? <>（{t(($) => $.dataSources.schedule.autoRefreshing)}）</>
            : null}
        </button>
      </div>

      {outcomeMessage && (
        <div className="errorbox"><p className="muted">{outcomeMessage}</p></div>
      )}
      {developerMode ? <DeveloperDiagnostics diagnostics={diagnostics} t={t} /> : null}

      <div className="settings-panel">
        <h4 className="detail-section">{t(($) => $.dataSources.providers.health.title)}</h4>
        {!health ? (
          <p className="muted tiny">{t(($) => $.dataSources.loading)}</p>
        ) : (
          <div className="settings-table-scroll" data-testid="provider-health-scroll">
            <table className="data-table settings-provider-health-table">
              <thead>
                <tr>
                  <th>{t(($) => $.dataSources.headings.provider)}</th>
                  <th>{t(($) => $.dataSources.headings.status)}</th>
                  <th>{t(($) => $.dataSources.headings.key)}</th>
                  <th>{t(($) => $.dataSources.headings.lastSuccess)}</th>
                  <th>{t(($) => $.dataSources.headings.lastError)}</th>
                </tr>
              </thead>
              <tbody>
                {health.providers.map((p) => {
                  const fredDetail = fredProviderDetail(p, t);
                  return (
                    <tr key={p.id}>
                      <td className="settings-wrap-text">
                        {providerName(p.id, t)}
                        {fredDetail && <div className="muted tiny">{fredDetail}</div>}
                      </td>
                      <td><ProviderHealthState provider={p} t={t} /></td>
                      <td>
                        {providerKeySourceLabel(p.key_source, t)}
                        {p.key_import_suggested && (
                          <span className="muted tiny">
                            {" · "}{t(($) => $.dataSources.labels.recommendedImport)}
                          </span>
                        )}
                      </td>
                      <td>{shortTs(p.last_success_at)}</td>
                      <td className="muted settings-wrap-text">—</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="settings-panel" style={{ marginTop: 16 }}>
        <div className="settings-panel-head">
          <div>
            <h4 className="detail-section">{t(($) => $.dataSources.extension.title)}</h4>
            <p className="muted tiny">
              {t(($) => $.dataSources.extension.description)}
            </p>
          </div>
          <button
            className="btn-ghost"
            disabled={busy === "sa.extension-health"}
            onClick={() => void reloadSAExtensionHealth()}
          >
            {t(($) => $.dataSources.extension.recheck)}
          </button>
        </div>
        {!saExtensionHealth ? (
          <p className="muted tiny">{t(($) => $.dataSources.loading)}</p>
        ) : (
          <>
            <p className="muted tiny">
              {saExtensionHealth.ok
                ? t(($) => $.dataSources.extension.available)
                : t(($) => $.dataSources.extension.interrupted)}
              {" · "}{shortTs(saExtensionHealth.generated_at)}
            </p>
            <div className="settings-table-scroll" data-testid="sa-health-scroll">
              <table className="data-table settings-sa-health-table">
                <thead>
                  <tr>
                    <th>{t(($) => $.dataSources.headings.segment)}</th>
                    <th>{t(($) => $.dataSources.headings.status)}</th>
                    <th>{t(($) => $.dataSources.headings.detail)}</th>
                  </tr>
                </thead>
                <tbody>
                  {displaySAExtensionSegments(saExtensionHealth.segments, t).map((row) => (
                    <tr key={row.key}>
                      <td>{row.label}</td>
                      <td>
                        <StatusBadge
                          state={saSegmentCommonState(row.tone)}
                          label={row.tone === "ok"
                            ? t(($) => $.dataSources.states.ok)
                            : row.tone === "warn"
                              ? t(($) => $.dataSources.states.warn)
                              : t(($) => $.dataSources.states.failed)}
                        />
                      </td>
                      <td className="muted settings-wrap-text">—</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>

      <div className="settings-panel" style={{ marginTop: 16 }}>
        <h4 className="detail-section">{t(($) => $.dataSources.providers.config.title)}</h4>
        <p className="muted tiny">
          {t(($) => $.dataSources.providers.config.description)}
        </p>
        {cfgSetup?.required && (
          <div className="errorbox">
            <p className="muted">
              {t(($) => $.dataSources.providers.config.setupRequired)}
            </p>
          </div>
        )}
        {!cfg ? (
          <p className="muted tiny">{t(($) => $.dataSources.loading)}</p>
        ) : (
          <div className="settings-table-scroll" data-testid="provider-config-scroll">
          <table className="data-table ds-config settings-provider-config-table">
            <thead>
              <tr>
                <th>{t(($) => $.dataSources.headings.provider)}</th>
                <th>{t(($) => $.dataSources.headings.field)}</th>
                <th>{t(($) => $.dataSources.headings.currentValueSource)}</th>
                <th>{t(($) => $.dataSources.headings.setting)}</th>
                <th>{t(($) => $.dataSources.headings.connectionTest)}</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(cfg)
                .filter(([, c]) => c.fields.length > 0 || c.testable)
                .map(([pid, c]) => {
                  const label = providerName(pid, t);
                  const testPresentation = providerTestPresentation(pid);
                  if (pid === "ibkr" && c.fields.length > 0) {
                    return (
                      <tr key="ibkr.group">
                        <td>
                          {label}
                          {c.default_available && (
                            <div className="muted tiny">
                              {t(($) => $.dataSources.providers.config.defaultAvailable)}
                            </div>
                          )}
                        </td>
                        <td colSpan={4}>
                          <div data-testid="ibkr-config-group" className="provider-config-group">
                            {c.fields.map((f) => renderProviderConfigField(pid, f))}
                            <div className="provider-config-actions">
                              {c.testable ? (
                                <>
                                  <button className="btn-ghost" disabled={!!busy}
                                    onClick={() => void runTest(pid)}>
                                    {t(($) => $.actions.test)}
                                  </button>
                                  {testPresentation && (
                                    <div className="muted tiny">{testPresentation}</div>
                                  )}
                                </>
                              ) : (
                                <span className="muted tiny">
                                  {t(($) => $.dataSources.providers.config.testUnavailable)}
                                </span>
                              )}
                            </div>
                          </div>
                        </td>
                      </tr>
                    );
                  }
                  const rows = c.fields.length > 0 ? c.fields : [null];
                  return rows.map((f, i) => (
                    <Fragment key={`${pid}.${f?.field ?? "_"}`}>
                    <tr>
                      {i === 0 && (
                        <td rowSpan={rows.length}>
                          {label}
                          {c.default_available && (
                            <div className="muted tiny">
                              {t(($) => $.dataSources.providers.config.defaultAvailable)}
                            </div>
                          )}
                        </td>
                      )}
                      <td>{f ? providerConfigFieldLabel(pid, f.field, t) : "—"}</td>
                      <td>
                        {f
                          ? f.effective_source === "missing"
                            ? <span className="ds-chip ds-missing_key">
                                {providerKeySourceLabel(f.effective_source, t)}
                              </span>
                            : <>
                                <span className="mono">
                                  {f.app_value_set
                                    ? f.app_value_masked
                                    : <>（{t(($) => $.dataSources.labels.external)}）</>}
                                </span>
                                {f.defaulted && (
                                  <span className="muted tiny">
                                    {" · "}{t(($) => $.dataSources.labels.defaultValue)}
                                  </span>
                                )}
                                <span className="muted tiny">
                                  （{providerKeySourceLabel(f.effective_source, t)}）
                                </span>
                                {f.needs_import && (
                                  <button className="btn-ghost tiny"
                                    disabled={busy === `import.${pid}.${f.field}`}
                                    onClick={() => void importField(pid, f.field, f.import_source)}>
                                    {t(($) => $.dataSources.providers.config.importValue)}
                                  </button>
                                )}
                                {f.needs_import && (
                                  <span className="muted tiny">
                                    {t(($) => $.dataSources.labels.recommendedImport)}
                                  </span>
                                )}
                              </>
                          : "—"}
                      </td>
                      <td>
                        {f && (
                          <>
                            <input
                              className="ds-interval ds-keyinput"
                              type={f.secret ? "password" : "text"}
                              placeholder={f.secret
                                ? t(($) => $.dataSources.providers.config.pasteKey)
                                : providerConfigFieldLabel(pid, f.field, t)}
                              value={keyDrafts[`${pid}.${f.field}`] ?? ""}
                              disabled={busy === `${pid}.${f.field}`}
                              onChange={(e) =>
                                setKeyDrafts((d) => ({ ...d, [`${pid}.${f.field}`]: e.target.value }))}
                              onKeyDown={(e) => {
                                const v = keyDrafts[`${pid}.${f.field}`];
                                if (e.key === "Enter" && v) void saveField(pid, f.field, v, f);
                              }}
                            />
                            {keyDrafts[`${pid}.${f.field}`] && (
                              <button className="btn-ghost tiny"
                                onClick={() => void saveField(pid, f.field, keyDrafts[`${pid}.${f.field}`], f)}>
                                {t(($) => $.actions.save)}
                              </button>
                            )}
                            {f.app_value_set && (
                              <button className="btn-ghost tiny"
                                onClick={() => void saveField(pid, f.field, null, f)}>
                                {t(($) => $.actions.clear)}
                              </button>
                            )}
                          </>
                        )}
                      </td>
                      {i === 0 && (
                        <td rowSpan={rows.length}>
                          {c.testable ? (
                            <>
                              <button className="btn-ghost" disabled={!!busy}
                                onClick={() => void runTest(pid)}>
                                {t(($) => $.actions.test)}
                              </button>
                              {testPresentation && (
                                <div className="muted tiny">{testPresentation}</div>
                              )}
                            </>
                          ) : (
                            <span className="muted tiny">
                              {t(($) => $.dataSources.providers.config.testUnavailable)}
                            </span>
                          )}
                        </td>
                      )}
                    </tr>
                    </Fragment>
                  ));
                })}
            </tbody>
          </table>
          </div>
        )}
      </div>

      <div className="settings-panel" style={{ marginTop: 16 }}>
        <h4 className="detail-section">{t(($) => $.dataSources.schedule.title)}</h4>
        {!schedule ? (
          <p className="muted tiny">{t(($) => $.dataSources.loading)}</p>
        ) : (
          <div className="settings-table-scroll" data-testid="schedule-scroll">
          <table className="data-table settings-schedule-table">
            <thead>
              <tr>
                <th>{t(($) => $.dataSources.headings.source)}</th>
                <th>{t(($) => $.dataSources.headings.schedule)}</th>
                <th>{t(($) => $.dataSources.headings.intervalMinutes)}</th>
                <th>{t(($) => $.dataSources.headings.runNow)}</th>
                <th>{t(($) => $.dataSources.headings.lastRun)}</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(schedule).map(([id, s]) => {
                const sourceCopy = scheduleSourceCopy(id, t);
                return (
                  <tr key={id}>
                  <td>
                    {sourceCopy.label}
                    <div className="muted tiny">{sourceCopy.description}</div>
                    {s.retired && (
                      <span className="ds-chip ds-disabled">
                        {t(($) => $.dataSources.labels.retired)}
                      </span>
                    )}
                  </td>
                  <td>
                    <label className="ds-toggle">
                      <input
                        type="checkbox"
                        checked={s.enabled}
                        disabled={busy === id}
                        onChange={(e) => void setEnabled(id, e.target.checked)}
                      />
                      <span className={s.enabled ? "tiny" : "muted tiny ds-schedule-disabled"}>
                        {s.enabled
                          ? t(($) => $.dataSources.labels.scheduleEnabled)
                          : t(($) => $.dataSources.labels.scheduleDisabled)}
                      </span>
                    </label>
                  </td>
                  <td>
                    <input
                      className="ds-interval"
                      type="number"
                      min={5}
                      placeholder={String(s.interval_minutes)}
                      value={drafts[id] ?? ""}
                      disabled={busy === id}
                      onChange={(e) => setDrafts((d) => ({ ...d, [id]: e.target.value }))}
                      onKeyDown={(e) => { if (e.key === "Enter") void applyInterval(id); }}
                    />
                    {drafts[id] && (
                      <button className="btn-ghost tiny" onClick={() => void applyInterval(id)}>
                        {t(($) => $.actions.apply)}
                      </button>
                    )}
                  </td>
                  <td>
                    {s.running ? (
                      <SourceRunProgress
                        sourceLabel={sourceCopy.label}
                        running={s.running}
                        progress={s.progress}
                      />
                    ) : (
                      <button
                        className="btn-ghost"
                        disabled={!!busy}
                        onClick={() => void runNow(id)}
                      >
                        ▶ {t(($) => $.actions.run)}
                      </button>
                    )}
                  </td>
                  <td className="muted tiny ds-last-run-cell settings-wrap-text">
                    {renderLastRun(id, s)}
                  </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          </div>
        )}
        <p className="muted tiny ds-schedule-protection-note" style={{ marginTop: 8 }}>
          {t(($) => $.dataSources.schedule.guardTitle)}：
          {t(($) => $.dataSources.schedule.protection)}
        </p>
      </div>
      <ConfirmDialog
        open={pendingGuardedEdit !== null}
        title={t(($) => $.dataSources.providers.config.guardTitle)}
        consequence={t(($) => $.dataSources.providers.config.guardConsequence)}
        confirmLabel={t(($) => $.dataSources.providers.config.guardConfirm)}
        tone="primary"
        busy={pendingGuardedEdit !== null && busy === `${pendingGuardedEdit.provider}.${pendingGuardedEdit.field}`}
        onConfirm={() => void confirmGuardedEdit()}
        onCancel={() => setPendingGuardedEdit(null)}
        returnFocusRef={guardedEditTriggerRef}
      />
    </div>
  );
}
