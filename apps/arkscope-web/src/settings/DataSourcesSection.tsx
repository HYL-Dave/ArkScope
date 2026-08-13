import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  getProvidersConfig,
  getProvidersHealth,
  getSAExtensionHealth,
  importProviderConfigField,
  putProviderConfig,
  testProvider,
  type ProviderConfigEntry,
  type ProviderConfigField,
  type ProviderConfigSetupState,
  type ProviderHealth,
  type ProviderTestResult,
  type ProvidersConfigResponse,
  type ProvidersHealthResponse,
  type SAExtensionHealthResponse,
} from "../api";
import {
  providerHealthStatusLabel,
} from "../marketDataDisplay";
import { displaySAExtensionSegments } from "../saExtensionHealthDisplay";
import {
  providerCommonState,
  saSegmentCommonState,
} from "../dataSourcesPresentation";
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
  settingsErrorPresentation,
} from "./settingsBackendCopy";
import type { SettingsT } from "./settingsCopy";
import { SettingsSubsectionAnchor } from "./SettingsSectionAnchor";
import {
  CLEAR_SETTINGS_NAVIGATION_GUARD,
  type SettingsNavigationGuardReporter,
} from "./settingsNavigationGuard";
import {
  DataScheduleTable,
  useDataScheduleControls,
} from "./dataScheduleControls";
import type { SettingsReadCache, SettingsReadKey } from "./settingsReadCache";

function retainedCacheValue<T>(
  settingsReadCache: SettingsReadCache,
  key: SettingsReadKey,
): T | null {
  const inspected = settingsReadCache.inspect<T>(key);
  return inspected.status === "missing" ? null : inspected.value;
}

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
        seriesCount: formatCount(snap.series_count),
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
    .map((d) => `${providerClientDomainLabel(d.domain, t)}=${base !== null ? base + d.offset : d.effective_id ?? "—"}`)
    .join(t(($) => $.dataSources.providers.config.clientIdSeparator));
  return { preview: base !== null, text };
}

function ProviderHealthState({ provider, t }: { provider: ProviderHealth; t: SettingsT }) {
  const state = providerCommonState(provider.status);
  return state === null
    ? <span className="muted tiny">{providerHealthStatusLabel(provider, t)}</span>
    : <StatusBadge state={state} label={providerHealthStatusLabel(provider, t)} />;
}

type DataSourcesOutcome = { kind: "error"; error: unknown };

type ProviderTestState =
  | { kind: "running" }
  | { kind: "result"; result: ProviderTestResult }
  | { kind: "error"; error: unknown };

export function DataSourcesSection({
  onNavigationGuardChange,
  developerMode = false,
  settingsReadCache,
}: {
  onNavigationGuardChange?: SettingsNavigationGuardReporter;
  developerMode?: boolean;
  settingsReadCache: SettingsReadCache;
}) {
  const { t } = useTranslation("settings");
  const { t: commonT } = useTranslation("common");
  const scheduleController = useDataScheduleControls(settingsReadCache);
  const schedule = scheduleController.schedule;
  const [initialHealth] = useState(() =>
    retainedCacheValue<ProvidersHealthResponse>(settingsReadCache, "provider_health"));
  const [initialConfig] = useState(() =>
    retainedCacheValue<ProvidersConfigResponse>(settingsReadCache, "provider_config"));
  const [health, setHealth] = useState<ProvidersHealthResponse | null>(initialHealth);
  const [saExtensionHealth, setSaExtensionHealth] = useState<SAExtensionHealthResponse | null>(
    () => retainedCacheValue<SAExtensionHealthResponse>(settingsReadCache, "sa_extension_health"),
  );
  const [cfg, setCfg] = useState<Record<string, ProviderConfigEntry> | null>(
    initialConfig?.providers ?? null,
  );
  const [cfgSetup, setCfgSetup] = useState<ProviderConfigSetupState | null>(
    initialConfig?.setup ?? null,
  );
  const [outcome, setOutcome] = useState<DataSourcesOutcome | null>(null);
  const [busy, setBusy] = useState<string>("");
  const [keyDrafts, setKeyDrafts] = useState<Record<string, string>>({}); // "provider.field"
  const [testResults, setTestResults] = useState<Record<string, ProviderTestState>>({});
  const [pendingGuardedEdit, setPendingGuardedEdit] = useState<{
    provider: string;
    field: string;
    value: string;
    fieldMeta: ProviderConfigField;
  } | null>(null);
  const guardedEditTriggerRef = useRef<HTMLButtonElement>(null);
  const dataSourcesMountedRef = useRef(true);
  const combinedBusy = scheduleController.busy || busy;
  const dirty = scheduleController.hasDrafts
    || Object.values(keyDrafts).some((value) => value !== "")
    || pendingGuardedEdit !== null;
  const navigationBusy = combinedBusy !== "";

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

  const load = useCallback(async (force = false) => {
    const [rh, rc] = await Promise.all([
      settingsReadCache.load("provider_health", getProvidersHealth, { force }),
      settingsReadCache.load("provider_config", getProvidersConfig, { force }),
    ]);
    if (!dataSourcesMountedRef.current) return;
    if (rh.status === "success") setHealth(rh.value);
    if (rc.status === "success") {
      setCfg(rc.value.providers);
      setCfgSetup(rc.value.setup);
    }
    const bad = [rh, rc].filter((result) => result.status === "error");
    setOutcome(bad.length
      ? {
          kind: "error",
          error: new Error(
            bad.map((result) => result.status === "error"
              ? result.error instanceof Error
                ? result.error.message
                : String(result.error)
              : "")
              .join("; "),
          ),
        }
      : null);
  }, [settingsReadCache]);

  useEffect(() => {
    void load(false);
  }, [load]);

  useEffect(() => {
    if (scheduleController.lifecycleVersion > 0) void load(true);
  }, [load, scheduleController.lifecycleVersion]);

  // Extension health spawns a native-host subprocess server-side — fetch once
  // on mount and via the manual 重新檢查 button only, NEVER on the 5s
  // scheduler-status poll.
  useEffect(() => {
    let cancelled = false;
    settingsReadCache.load("sa_extension_health", getSAExtensionHealth)
      .then((result) => {
        if (!cancelled && result.status === "success") setSaExtensionHealth(result.value);
      })
      .catch(() => {
        // Keep the retained visible truth when the optional health read fails.
      });
    return () => {
      cancelled = true;
    };
  }, [settingsReadCache]);

  async function importField(provider: string, field: string, sourceEnvVar: string | null) {
    if (combinedBusy) return;
    setBusy(`import.${provider}.${field}`);
    try {
      await importProviderConfigField(provider, field, sourceEnvVar);
      settingsReadCache.invalidate("provider_config");
      settingsReadCache.invalidate("provider_health");
      await load(true);
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
    if (combinedBusy) return false;
    setBusy(`${provider}.${field}`);
    try {
      await putProviderConfig(
        provider,
        { [field]: value },
        fieldMeta?.guarded ? { [field]: true } : undefined,
      );
      setKeyDrafts((d) => ({ ...d, [`${provider}.${field}`]: "" }));
      settingsReadCache.invalidate("provider_config");
      settingsReadCache.invalidate("provider_health");
      await load(true);
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
    if (combinedBusy) return;
    if (fieldMeta?.guarded && value !== null) {
      setPendingGuardedEdit({ provider, field, value, fieldMeta });
      return;
    }
    await commitField(provider, field, value, fieldMeta);
  }

  async function confirmGuardedEdit() {
    if (!pendingGuardedEdit || combinedBusy) return;
    const saved = await commitField(
      pendingGuardedEdit.provider,
      pendingGuardedEdit.field,
      pendingGuardedEdit.value,
      pendingGuardedEdit.fieldMeta,
    );
    if (saved) setPendingGuardedEdit(null);
  }

  async function runTest(provider: string) {
    if (combinedBusy) return;
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
    if (combinedBusy) return;
    setBusy("sa.extension-health");
    try {
      const result = await settingsReadCache.load(
        "sa_extension_health",
        getSAExtensionHealth,
        { force: true },
      );
      if (result.status === "success") {
        setSaExtensionHealth(result.value);
      } else if (result.status === "error") {
        throw result.error;
      }
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
                    : t(($) => $.dataSources.labels.external)}
                </span>
                {f.defaulted && (
                  <span className="muted tiny">
                    {" · "}{t(($) => $.dataSources.labels.defaultValue)}
                  </span>
                )}
                <span className="muted tiny">
                  {t(($) => $.dataSources.providers.config.sourceValue, {
                    value: providerKeySourceLabel(f.effective_source, t),
                  })}
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
    ? settingsErrorPresentation(outcome.error, t, commonT)
    : null;
  const scheduleOutcomePresentation = scheduleController.outcome?.kind === "error"
    ? settingsErrorPresentation(scheduleController.outcome.error, t, commonT)
    : null;
  const outcomeMessage = scheduleController.outcome?.kind === "schedule"
    ? scheduleOutcomeCopy(
        scheduleController.outcome.source,
        scheduleController.outcome.result,
        t,
      )
    : scheduleOutcomePresentation?.message ?? outcomePresentation?.message ?? null;
  const jobDiagnostics = Object.values(health?.jobs ?? {}).map((row) => row.error);
  const providerDiagnostics = (health?.providers ?? []).flatMap((provider) => [
    provider.detail,
    provider.last_error,
    provider.disabled_reason,
  ]);
  const configDiagnostics = Object.values(cfg ?? {}).flatMap((entry) =>
    entry.fields.map((field) => field.guard_reason));
  const scheduleDiagnostics = Object.values(schedule ?? {}).flatMap((source) => [
    source.last_result?.reason,
    source.durable_state?.last_error,
    source.durable_state?.running_stale_reason,
  ]);
  const providerTestDiagnostics = Object.values(testResults).map((state) => {
    if (state.kind === "result") return state.result.detail;
    if (state.kind === "error") return state.error;
    return null;
  });
  const saExtensionRows = displaySAExtensionSegments(
    saExtensionHealth?.segments ?? [],
    t,
    developerMode,
  );
  const diagnostics = [
    outcomePresentation?.diagnostic,
    scheduleOutcomePresentation?.diagnostic,
    scheduleController.outcome?.kind === "schedule"
      ? scheduleController.outcome.result.reason
      : null,
    ...(health?.notes ?? []),
    ...jobDiagnostics,
    ...providerDiagnostics,
    ...saExtensionRows.map((row) => row.diagnostic),
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
        <button
          className="btn-ghost"
          onClick={() => void Promise.all([load(true), scheduleController.reloadSchedule()])}
          disabled={Boolean(combinedBusy)}
        >
          ↻ {t(($) => $.actions.refreshStatus)}
          {scheduleController.anyRunning
            ? t(($) => $.dataSources.schedule.autoRefreshing)
            : null}
        </button>
      </div>

      {outcomeMessage && (
        <div className="errorbox"><p className="muted">{outcomeMessage}</p></div>
      )}
      {developerMode ? <DeveloperDiagnostics diagnostics={diagnostics} t={t} /> : null}

      <SettingsSubsectionAnchor id="provider_health">
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
                      <td className="settings-wrap-text">
                        {p.last_error ? (
                          <>
                            <span className="refresh-err">{t(($) => $.dataSources.states.failed)}</span>
                            {p.last_attempt_at ? (
                              <div className="muted tiny">{shortTs(p.last_attempt_at)}</div>
                            ) : null}
                          </>
                        ) : <span className="muted">—</span>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        </div>
      </SettingsSubsectionAnchor>

      <SettingsSubsectionAnchor id="sa_extension_health">
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
                  {saExtensionRows.map((row) => (
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
                      <td className="muted settings-wrap-text">
                        {row.showDetail ? row.copy : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
        </div>
      </SettingsSubsectionAnchor>

      <SettingsSubsectionAnchor id="provider_connections">
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
                                  <button className="btn-ghost" disabled={Boolean(combinedBusy)}
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
                                    : t(($) => $.dataSources.labels.external)}
                                </span>
                                {f.defaulted && (
                                  <span className="muted tiny">
                                    {" · "}{t(($) => $.dataSources.labels.defaultValue)}
                                  </span>
                                )}
                                <span className="muted tiny">
                                  {t(($) => $.dataSources.providers.config.sourceValue, {
                                    value: providerKeySourceLabel(f.effective_source, t),
                                  })}
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
                              <button className="btn-ghost" disabled={Boolean(combinedBusy)}
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
      </SettingsSubsectionAnchor>

      <SettingsSubsectionAnchor id="source_schedules">
        <div className="settings-panel" style={{ marginTop: 16 }}>
        <h4 className="detail-section">{t(($) => $.dataSources.schedule.title)}</h4>
        <DataScheduleTable
          controller={scheduleController}
          jobs={health?.jobs}
          externalBusy={busy !== ""}
        />
        <p className="muted tiny ds-schedule-protection-note" style={{ marginTop: 8 }}>
          {t(($) => $.dataSources.schedule.guardTitle)}
          {t(($) => $.dataSources.schedule.protection)}
        </p>
        </div>
      </SettingsSubsectionAnchor>
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
