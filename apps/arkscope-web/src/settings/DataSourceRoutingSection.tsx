import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { ArrowDown, ArrowUp, RefreshCw, Save, Undo2 } from "lucide-react";

import {
  getDataSourceRoutes, putDataSourceRoute, putFinancialDatasetsBudget,
  type DataSourceDataset, type DataSourceRoutesResponse,
  type FinancialDatasetsBudget, type FinancialDatasetsBudgetUpdate,
} from "../api";
import { ConfirmDialog } from "../ui/ConfirmDialog";
import { IconButton } from "../ui/Button";
import { providerName } from "./settingsBackendCopy";
import type { SettingsT } from "./settingsCopy";
import type { SettingsReadCache } from "./settingsReadCache";
import {
  CLEAR_SETTINGS_NAVIGATION_GUARD, type SettingsNavigationGuardReporter,
} from "./settingsNavigationGuard";

function datasetLabel(dataset: DataSourceDataset, t: SettingsT) {
  switch (dataset) {
    case "fundamentals_analysis": return t(($) => $.dataSources.routing.datasets.fundamentals);
    case "detailed_financials": return t(($) => $.dataSources.routing.datasets.detailed);
    case "earnings_supplements": return t(($) => $.dataSources.routing.datasets.earnings);
    case "sa_company_financials": return t(($) => $.dataSources.routing.datasets.saCompany);
  }
}

type BudgetDraft = { enabled: boolean; daily: string; minute: string };

function budgetDraft(value: FinancialDatasetsBudget): BudgetDraft {
  return {
    enabled: value.state === "enabled",
    daily: value.daily_request_limit == null ? "" : String(value.daily_request_limit),
    minute: value.requests_per_minute == null ? "" : String(value.requests_per_minute),
  };
}

function positiveInteger(raw: string): string | null {
  if (!/^[1-9]\d{0,18}$/.test(raw)) return null;
  return BigInt(raw) < 2n ** 63n ? raw : null;
}

export function DataSourceRoutingSection({ settingsReadCache, onNavigationGuardChange, disabled = false }: {
  settingsReadCache: SettingsReadCache;
  onNavigationGuardChange?: SettingsNavigationGuardReporter;
  disabled?: boolean;
}) {
  const { t } = useTranslation("settings");
  const [data, setData] = useState<DataSourceRoutesResponse | null>(() => {
    const current = settingsReadCache.inspect<DataSourceRoutesResponse>("data_source_routes");
    return current.status === "missing" ? null : current.value;
  });
  const [drafts, setDrafts] = useState<Partial<Record<DataSourceDataset, string[]>>>({});
  const [budgetEdit, setBudgetEdit] = useState<BudgetDraft | null>(null);
  const [pendingBudget, setPendingBudget] = useState<FinancialDatasetsBudgetUpdate | null>(null);
  const [busy, setBusy] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);
  const [saveFailed, setSaveFailed] = useState(false);
  const [invalidBudget, setInvalidBudget] = useState(false);
  const mounted = useRef(false);
  const sequence = useRef(0);
  const budgetSaveRef = useRef<HTMLButtonElement>(null);
  const currentBudget = data ? budgetEdit ?? budgetDraft(data.financial_datasets_budget) : null;
  const budgetDirty = Boolean(data && budgetEdit && JSON.stringify(budgetEdit) !== JSON.stringify(budgetDraft(data.financial_datasets_budget)));
  const dirty = budgetDirty || Boolean(data?.routes.some((row) =>
    drafts[row.dataset] != null && JSON.stringify(drafts[row.dataset]) !== JSON.stringify(row.providers)));
  const blocked = disabled || busy !== "" || pendingBudget !== null;

  useEffect(() => {
    onNavigationGuardChange?.({
      dirty, busy: busy !== "" || pendingBudget !== null,
      reason: busy || pendingBudget ? t(($) => $.dataSources.guard.busy)
        : dirty ? t(($) => $.dataSources.guard.dirty) : null,
    });
  }, [dirty, busy, pendingBudget, onNavigationGuardChange, t]);
  useEffect(() => () => {
    onNavigationGuardChange?.(CLEAR_SETTINGS_NAVIGATION_GUARD);
  }, [onNavigationGuardChange]);

  const load = useCallback(async (force = false) => {
    const request = ++sequence.current;
    setLoading(true);
    const result = await settingsReadCache.load("data_source_routes", getDataSourceRoutes, { force });
    if (!mounted.current || request !== sequence.current) return;
    if (result.status === "success") {
      setData(result.value);
      setLoadFailed(false);
    } else if (result.status === "error") setLoadFailed(true);
    setLoading(false);
  }, [settingsReadCache]);

  useEffect(() => {
    mounted.current = true;
    void load();
    const unsubscribe = settingsReadCache.subscribeInvalidation("data_source_routes", () => { void load(); });
    return () => { mounted.current = false; unsubscribe(); };
  }, [load, settingsReadCache]);

  async function saveRoute(dataset: DataSourceDataset) {
    if (blocked || !drafts[dataset]) return;
    setBusy(dataset);
    setSaveFailed(false);
    try {
      const saved = await putDataSourceRoute(dataset, drafts[dataset]);
      settingsReadCache.invalidate("data_source_routes");
      if (!mounted.current) return;
      setData((value) => value && { ...value, routes: value.routes.map((row) => row.dataset === dataset ? saved : row) });
      setDrafts((value) => { const copy = { ...value }; delete copy[dataset]; return copy; });
    } catch {
      if (mounted.current) setSaveFailed(true);
    } finally {
      if (mounted.current) setBusy("");
    }
  }

  async function saveBudget(value: FinancialDatasetsBudgetUpdate) {
    setBusy("budget");
    setSaveFailed(false);
    try {
      const saved = await putFinancialDatasetsBudget(value);
      settingsReadCache.invalidate("data_source_routes");
      if (!mounted.current) return;
      setData((current) => current && { ...current, financial_datasets_budget: saved });
      setBudgetEdit(null);
      setPendingBudget(null);
    } catch {
      if (mounted.current) setSaveFailed(true);
    } finally {
      if (mounted.current) setBusy("");
    }
  }

  function prepareBudget() {
    if (blocked || !currentBudget) return;
    const daily = positiveInteger(currentBudget.daily), minute = positiveInteger(currentBudget.minute);
    if (currentBudget.enabled && (daily == null || minute == null)) {
      setInvalidBudget(true);
      return;
    }
    setInvalidBudget(false);
    const value = { enabled: currentBudget.enabled, daily_request_limit: daily,
      requests_per_minute: minute, confirm_paid: currentBudget.enabled };
    if (value.enabled) setPendingBudget(value);
    else void saveBudget(value);
  }

  function editBudget(change: Partial<BudgetDraft>) {
    if (currentBudget) setBudgetEdit({ ...currentBudget, ...change });
    setInvalidBudget(false);
  }

  const budgetState = data?.financial_datasets_budget.state;
  const canSaveBudget = budgetDirty || Boolean(currentBudget && !currentBudget.enabled
    && (budgetState === "invalid" || budgetState === "unconfigured"));
  const budgetStateLabel = budgetState === "enabled" ? t(($) => $.dataSources.routing.budget.enabled)
    : budgetState === "disabled" ? t(($) => $.dataSources.routing.budget.disabled)
      : budgetState === "unconfigured" ? t(($) => $.dataSources.routing.budget.unconfigured)
        : t(($) => $.dataSources.routing.invalid);

  return (
    <section className="data-source-routing" aria-label={t(($) => $.dataSources.routing.title)}>
      <div className="settings-section-head">
        <h3>{t(($) => $.dataSources.routing.title)}</h3>
        <IconButton label={t(($) => $.actions.refreshStatus)} icon={<RefreshCw size={16} />}
          disabled={blocked || dirty || loading} onClick={() => void load(true)} />
      </div>
      {loadFailed ? <p role="alert" className="refresh-err">{t(($) => $.dataSources.routing.loadFailed)}</p> : null}
      {saveFailed ? <p role="alert" className="refresh-err">{t(($) => $.dataSources.routing.saveFailed)}</p> : null}
      {!data && loading ? <p className="muted tiny">{t(($) => $.dataSources.loading)}</p> : null}
      {data ? <>
        <div className="data-route-head muted tiny" aria-hidden="true">
          <span>{t(($) => $.dataSources.routing.dataset)}</span>
          <span>{t(($) => $.dataSources.routing.selectionOrder)}</span>
        </div>
        {data.routes.map((row) => {
          const selected = drafts[row.dataset] ?? row.providers ?? [];
          const changed = drafts[row.dataset] != null && JSON.stringify(selected) !== JSON.stringify(row.providers);
          const label = datasetLabel(row.dataset, t);
          const ordered = [...selected, ...row.options.map((option) => option.provider).filter((provider) => !selected.includes(provider))];
          return <div className="data-route-row" key={row.dataset}>
            <div className="data-route-label">
              <strong>{label}</strong>
              <span className={row.error_code ? "refresh-err tiny" : "muted tiny"}>
                {row.error_code ? t(($) => $.dataSources.routing.invalid)
                  : row.providers?.length === 0 ? t(($) => $.dataSources.routing.noSources)
                    : row.setting_source === "default" ? t(($) => $.dataSources.routing.defaultSelection)
                      : t(($) => $.dataSources.routing.savedSelection)}
              </span>
            </div>
            <fieldset className="data-route-options" aria-label={label} disabled={blocked}>
              {ordered.map((provider) => {
                const index = selected.indexOf(provider);
                const access = row.options.find((item) => item.provider === provider)?.access;
                const name = provider === "seeking_alpha" ? t(($) => $.dataSources.catalog.seekingAlpha) : providerName(provider, t);
                const move = (offset: number) => {
                  const next = [...selected];
                  [next[index], next[index + offset]] = [next[index + offset], next[index]];
                  setDrafts((value) => ({ ...value, [row.dataset]: next }));
                };
                return <div className="data-route-option" key={provider}>
                  <label>
                    <input type="checkbox" checked={index >= 0}
                      aria-label={t(($) => $.dataSources.routing.choose, { dataset: label, provider: name })}
                      onChange={(event) => setDrafts((value) => ({ ...value, [row.dataset]: event.target.checked
                        ? [...selected, provider] : selected.filter((item) => item !== provider) }))} />
                    <span>{name}</span>
                  </label>
                  <span className="muted tiny data-route-access">
                    {access === "metered_requests" ? t(($) => $.dataSources.routing.metered)
                      : access === "endpoint_entitlement_unverified" ? t(($) => $.dataSources.routing.entitlementUnknown)
                        : access === "signed_in_browser_subscription" ? t(($) => $.dataSources.catalog.requirements.signed_in_browser_subscription)
                        : t(($) => $.dataSources.routing.publicSource)}
                  </span>
                  {row.options.length > 1 ? <div className="data-route-actions">
                    <IconButton size="compact" label={t(($) => $.dataSources.routing.moveUp, { provider: name })}
                      icon={<ArrowUp size={14} />} disabled={blocked || index <= 0} onClick={() => move(-1)} />
                    <IconButton size="compact" label={t(($) => $.dataSources.routing.moveDown, { provider: name })}
                      icon={<ArrowDown size={14} />} disabled={blocked || index < 0 || index === selected.length - 1} onClick={() => move(1)} />
                  </div> : null}
                </div>;
              })}
              {row.unimplemented.map((provider) => <div className="data-route-unimplemented muted tiny" key={provider}>
                <span>{provider === "seeking_alpha" ? t(($) => $.dataSources.catalog.seekingAlpha) : providerName(provider, t)}</span><span>{t(($) => $.dataSources.routing.notImplemented)}</span>
              </div>)}
            </fieldset>
            <div className="data-route-actions">
              <IconButton label={t(($) => $.dataSources.routing.save, { dataset: label })}
                icon={<Save size={16} />} busy={busy === row.dataset} disabled={blocked || !changed}
                onClick={() => void saveRoute(row.dataset)} />
              <IconButton label={t(($) => $.dataSources.routing.undo, { dataset: label })}
                icon={<Undo2 size={16} />} disabled={blocked || !changed}
                onClick={() => setDrafts((value) => { const copy = { ...value }; delete copy[row.dataset]; return copy; })} />
            </div>
          </div>;
        })}
        {currentBudget ? <div className="data-route-budget">
          <div className="settings-section-head">
            <h4>{t(($) => $.dataSources.routing.budget.title)}</h4>
            <span className="muted tiny">{budgetStateLabel}</span>
          </div>
          <label className="data-route-budget-toggle">
            <input type="checkbox" checked={currentBudget.enabled} disabled={blocked}
              onChange={(event) => editBudget({ enabled: event.target.checked })} />
            {t(($) => $.dataSources.routing.budget.allowPaid)}
          </label>
          <div className="ui-inline-form data-route-budget-fields">
            <label>{t(($) => $.dataSources.routing.budget.daily)}
              <input type="number" min={1} step={1} inputMode="numeric" value={currentBudget.daily}
                disabled={blocked || !currentBudget.enabled} onChange={(event) => editBudget({ daily: event.target.value })} />
            </label>
            <label>{t(($) => $.dataSources.routing.budget.minute)}
              <input type="number" min={1} step={1} inputMode="numeric" value={currentBudget.minute}
                disabled={blocked || !currentBudget.enabled} onChange={(event) => editBudget({ minute: event.target.value })} />
            </label>
            <div className="data-route-actions">
              <IconButton ref={budgetSaveRef} label={t(($) => $.dataSources.routing.budget.save)}
                icon={<Save size={16} />} busy={busy === "budget"} disabled={blocked || !canSaveBudget} onClick={prepareBudget} />
              <IconButton label={t(($) => $.dataSources.routing.budget.undo)} icon={<Undo2 size={16} />}
                disabled={blocked || !budgetDirty} onClick={() => { setBudgetEdit(null); setInvalidBudget(false); }} />
            </div>
          </div>
          {invalidBudget ? <p role="alert" className="refresh-err tiny">{t(($) => $.dataSources.routing.budget.invalidLimits)}</p> : null}
        </div> : null}
      </> : null}
      <ConfirmDialog open={pendingBudget !== null} title={t(($) => $.dataSources.routing.budget.confirmTitle)}
        consequence={<>
          <p>{t(($) => $.dataSources.routing.budget.confirmLimits, {
            daily: pendingBudget?.daily_request_limit ?? "", minute: pendingBudget?.requests_per_minute ?? "",
          })}</p>
          <p>{t(($) => $.dataSources.routing.budget.notDollarCap)}</p>
          {saveFailed ? <p role="alert">{t(($) => $.dataSources.routing.saveFailed)}</p> : null}
        </>}
        confirmLabel={t(($) => $.dataSources.routing.budget.confirm)} tone="primary" busy={busy === "budget"}
        onConfirm={() => { if (pendingBudget && !busy) void saveBudget(pendingBudget); }}
        onCancel={() => setPendingBudget(null)} returnFocusRef={budgetSaveRef} />
    </section>
  );
}
