import { useCallback, useEffect, useMemo, useRef, useState, type Dispatch, type SetStateAction } from "react";
import { Download, Menu, Save, Upload } from "lucide-react";
import { useTranslation } from "react-i18next";
import {
  discoverModels,
  deleteModelRoute,
  exportModelRoutes,
  getModelCatalog,
  importModelRoutes,
  deleteFixedTaskRuntime,
  deleteResearchRuntime,
  saveFixedTaskRuntime,
  saveResearchRuntime,
  saveModelRoutes,
  testTaskModelAccess,
  type ModelCatalog,
  type ModelOption,
  type ModelProvider,
  type ModelTask,
  type ResearchRuntimeSettings,
  type RuntimeConfig,
  type TaskRoute,
} from "./api";
import { runDiscoveryAndRefreshCatalog } from "./modelSelect";
import {
  blockedRouteSaves,
  providerContexts,
  type TaskTestSnapshot,
} from "./modelRoutingUx";
import { InvestorProfilePanel } from "./InvestorProfilePanel";
import type {
  NavigationRequest,
  NavigationTarget,
} from "./shell/navigation";
import { DataSourcesSection } from "./settings/DataSourcesSection";
import { DataStorageSection } from "./settings/DataStorageSection";
import { DeveloperDiagnostics } from "./settings/DeveloperDiagnostics";
import { MacroStorageSection } from "./settings/MacroStorageSection";
import {
  ModelRoutingSection,
  type DraftRoute,
  type TestState,
} from "./settings/ModelRoutingSection";
import { NewsStorageSection } from "./settings/NewsStorageSection";
import {
  CredentialList,
  DiscoveryResultView,
  ProviderSection,
  SetupDisclosure,
  type DiscoveryState,
} from "./settings/ProviderSection";
import {
  FixedTaskRuntimeSection,
  ResearchRuntimeSection,
} from "./settings/RuntimeLimitSections";
import { SettingsDirectory } from "./settings/SettingsDirectory";
import { SettingsSectionAnchor } from "./settings/SettingsSectionAnchor";
import {
  CLEAR_SETTINGS_NAVIGATION_GUARD,
  type SettingsNavigationGuard,
} from "./settings/settingsNavigationGuard";
import {
  SETTINGS_GROUPS,
  firstSettingsAnchor,
  settingsGroupFor,
  type SettingsAnchorId,
  type SettingsGroupId,
} from "./settings/settingsRegistry";
import {
  readActiveSettingsGroup,
  writeActiveSettingsGroup,
} from "./settings/settingsPreferences";
import { settingsTaskLabel, type SettingsT } from "./settings/settingsCopy";
import {
  Button,
  ConfirmDialog,
  Drawer,
  InlineAlert,
  PageHeader,
  Tabs,
  useShellOverlay,
  type TabItem,
} from "./ui";

export {
  CredentialList,
  DiscoveryResultView,
  FixedTaskRuntimeSection,
  ModelRoutingSection,
  ProviderSection,
  ResearchRuntimeSection,
  SetupDisclosure,
};

export interface SettingsViewProps {
  runtime: RuntimeConfig | null;
  developerMode: boolean;
  onRuntimeChanged: () => Promise<void>;
  navigationRequest?: NavigationRequest<Extract<NavigationTarget, { kind: "settings_section" }>> | null;
}

type SettingsNavigationIntent = {
  group: SettingsGroupId;
  anchor: SettingsAnchorId;
  kind: "manual_group" | "exact_anchor";
};

type SettingsRouteOutcome =
  | { kind: "save_succeeded" }
  | { kind: "missing_model"; task: ModelTask }
  | { kind: "save_failed" }
  | { kind: "import_succeeded"; imported: number; skipped: number }
  | { kind: "import_failed" }
  | { kind: "export_succeeded"; exported: number; cleared: number }
  | { kind: "export_failed" }
  | { kind: "reset_succeeded"; task: ModelTask }
  | { kind: "reset_failed" };

type SettingsRouteOutcomePresentation = {
  tone: "ok" | "error";
  message: string;
};

type SettingsRuntimeOutcome =
  | { kind: "fixed_save_succeeded" }
  | { kind: "fixed_save_failed"; diagnostic: string }
  | { kind: "fixed_reset_succeeded" }
  | { kind: "fixed_reset_failed"; diagnostic: string }
  | { kind: "research_save_succeeded" }
  | { kind: "research_save_failed"; diagnostic: string }
  | { kind: "research_reset_succeeded" }
  | { kind: "research_reset_failed"; diagnostic: string };

function unreachableRouteOutcome(outcome: never): never {
  throw new Error(`unknown Settings route outcome: ${String(outcome)}`);
}

function settingsRouteOutcomePresentation(
  outcome: SettingsRouteOutcome,
  t: SettingsT,
): SettingsRouteOutcomePresentation {
  switch (outcome.kind) {
    case "save_succeeded":
      return { tone: "ok", message: t(($) => $.workspace.routes.saved) };
    case "missing_model":
      return {
        tone: "error",
        message: t(($) => $.workspace.routes.missingModel, {
          taskLabel: settingsTaskLabel(outcome.task, t),
        }),
      };
    case "save_failed":
      return { tone: "error", message: t(($) => $.workspace.routes.saveFailed) };
    case "import_succeeded":
      return {
        tone: "ok",
        message: t(($) => $.workspace.routes.imported, {
          count: outcome.imported,
          value: outcome.skipped,
        }),
      };
    case "import_failed":
      return { tone: "error", message: t(($) => $.workspace.routes.importFailed) };
    case "export_succeeded":
      return {
        tone: "ok",
        message: t(($) => $.workspace.routes.exported, {
          count: outcome.exported,
          value: outcome.cleared,
        }),
      };
    case "export_failed":
      return { tone: "error", message: t(($) => $.workspace.routes.exportFailed) };
    case "reset_succeeded":
      return {
        tone: "ok",
        message: t(($) => $.workspace.routes.reset, {
          taskLabel: settingsTaskLabel(outcome.task, t),
        }),
      };
    case "reset_failed":
      return { tone: "error", message: t(($) => $.errors.mutationFailed) };
    default:
      return unreachableRouteOutcome(outcome);
  }
}

function settingsRuntimeOutcomePresentation(
  outcome: SettingsRuntimeOutcome,
  t: SettingsT,
): SettingsRouteOutcomePresentation {
  switch (outcome.kind) {
    case "fixed_save_succeeded":
      return { tone: "ok", message: t(($) => $.runtime.fixed.saved) };
    case "fixed_reset_succeeded":
      return { tone: "ok", message: t(($) => $.runtime.fixed.reset) };
    case "research_save_succeeded":
      return { tone: "ok", message: t(($) => $.runtime.research.saved) };
    case "research_reset_succeeded":
      return { tone: "ok", message: t(($) => $.runtime.research.reset) };
    case "fixed_save_failed":
    case "research_save_failed":
      return { tone: "error", message: t(($) => $.errors.saveFailed) };
    case "fixed_reset_failed":
    case "research_reset_failed":
      return { tone: "error", message: t(($) => $.errors.mutationFailed) };
  }
}

function runtimeOutcomeDiagnostic(outcome: SettingsRuntimeOutcome | null): string | null {
  return outcome && "diagnostic" in outcome ? outcome.diagnostic : null;
}

function firstBusyOrDirtyGuard(
  guards: readonly SettingsNavigationGuard[],
): SettingsNavigationGuard {
  const busy = guards.find((guard) => guard.busy);
  if (busy) return busy;
  return guards.find((guard) => guard.dirty) ?? CLEAR_SETTINGS_NAVIGATION_GUARD;
}

function settingsWorkspaceTabLabel(id: SettingsGroupId, t: SettingsT): string {
  switch (id) {
    case "ai_models":
      return t(($) => $.workspace.tabs.aiModels);
    case "personalization":
      return t(($) => $.workspace.tabs.personalization);
    case "data_sync":
      return t(($) => $.workspace.tabs.dataSync);
  }
}

export function SettingsView({
  runtime,
  developerMode,
  onRuntimeChanged,
  navigationRequest,
}: SettingsViewProps) {
  const { t } = useTranslation("settings");
  const [catalog, setCatalog] = useState<ModelCatalog | null>(null);
  const [draft, setDraft] = useState<Partial<Record<ModelTask, DraftRoute>>>({});
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [catalogFailed, setCatalogFailed] = useState(false);
  const [saving, setSaving] = useState(false);
  const [routeOutcome, setRouteOutcome] = useState<SettingsRouteOutcome | null>(null);
  const [runtimeOutcome, setRuntimeOutcome] = useState<SettingsRuntimeOutcome | null>(null);
  const [activeGroup, setActiveGroup] = useState<SettingsGroupId>(() => readActiveSettingsGroup());
  const [section, setSection] = useState<SettingsAnchorId>(() => firstSettingsAnchor(activeGroup));
  const [directoryQuery, setDirectoryQuery] = useState("");
  const [directoryOpen, setDirectoryOpen] = useState(false);
  const [pendingReveal, setPendingReveal] = useState<SettingsAnchorId | null>(null);
  const [pendingIntent, setPendingIntent] = useState<SettingsNavigationIntent | null>(null);
  const [blockedNotice, setBlockedNotice] = useState<string | null>(null);
  const [providerGuard, setProviderGuard] = useState<SettingsNavigationGuard>(CLEAR_SETTINGS_NAVIGATION_GUARD);
  const [fixedRuntimeGuard, setFixedRuntimeGuard] = useState<SettingsNavigationGuard>(CLEAR_SETTINGS_NAVIGATION_GUARD);
  const [researchRuntimeGuard, setResearchRuntimeGuard] = useState<SettingsNavigationGuard>(CLEAR_SETTINGS_NAVIGATION_GUARD);
  const [dataSourcesGuard, setDataSourcesGuard] = useState<SettingsNavigationGuard>(CLEAR_SETTINGS_NAVIGATION_GUARD);
  const [investorPotentialDirty, setInvestorPotentialDirty] = useState(false);
  const consumedNavigationSequenceRef = useRef(0);
  const directoryTriggerRef = useRef<HTMLButtonElement>(null);
  const aiModelsTabRef = useRef<HTMLButtonElement>(null);
  const personalizationTabRef = useRef<HTMLButtonElement>(null);
  const dataSyncTabRef = useRef<HTMLButtonElement>(null);
  const dialogReturnFocusRef = useRef<HTMLElement | null>(null);
  const [discovery, setDiscovery] = useState<DiscoveryState>({});
  const [testState, setTestState] = useState<TestState>({});
  const shellOverlay = useShellOverlay();

  const tabRefFor = useCallback((group: SettingsGroupId) => {
    if (group === "ai_models") return aiModelsTabRef;
    if (group === "personalization") return personalizationTabRef;
    return dataSyncTabRef;
  }, []);

  const applySettingsIntent = useCallback((intent: SettingsNavigationIntent) => {
    setActiveGroup(intent.group);
    writeActiveSettingsGroup(intent.group);
    setSection(intent.anchor);
    setDirectoryOpen(false);
    setPendingReveal(intent.kind === "exact_anchor" ? intent.anchor : null);
    setBlockedNotice(null);
  }, []);

  const currentNavigationGuard = useCallback((): SettingsNavigationGuard => {
    if (activeGroup === "ai_models") {
      return firstBusyOrDirtyGuard([
        saving
          ? {
              dirty: false,
              busy: true,
              reason: t(($) => $.workspace.guard.busyModels),
            }
          : CLEAR_SETTINGS_NAVIGATION_GUARD,
        providerGuard,
        fixedRuntimeGuard,
        researchRuntimeGuard,
      ]);
    }
    if (activeGroup === "personalization") {
      const investorBusy = !!document.querySelector(
        '[data-settings-anchor="investor_profile"] .investor-profile-panel[aria-busy="true"]',
      );
      if (investorBusy) {
        return {
          dirty: investorPotentialDirty,
          busy: true,
          reason: t(($) => $.workspace.blocked.description),
        };
      }
      return investorPotentialDirty
        ? {
            dirty: true,
            busy: false,
            reason: t(($) => $.workspace.blocked.description),
          }
        : CLEAR_SETTINGS_NAVIGATION_GUARD;
    }
    return dataSourcesGuard;
  }, [
    activeGroup,
    dataSourcesGuard,
    fixedRuntimeGuard,
    investorPotentialDirty,
    providerGuard,
    researchRuntimeGuard,
    saving,
    t,
  ]);

  const requestSettingsNavigation = useCallback((intent: SettingsNavigationIntent): boolean => {
    if (intent.kind === "manual_group") setPendingReveal(null);
    if (intent.group === activeGroup) {
      applySettingsIntent(intent);
      return true;
    }

    const guard = currentNavigationGuard();
    if (guard.busy) {
      setPendingIntent(null);
      setBlockedNotice(guard.reason ?? t(($) => $.workspace.blocked.description));
      return false;
    }
    if (guard.dirty) {
      dialogReturnFocusRef.current = tabRefFor(activeGroup).current;
      setBlockedNotice(null);
      setPendingIntent(intent);
      return false;
    }
    applySettingsIntent(intent);
    return true;
  }, [activeGroup, applySettingsIntent, currentNavigationGuard, t, tabRefFor]);

  const revealSection = useCallback((id: SettingsAnchorId) => requestSettingsNavigation({
    group: settingsGroupFor(id).id,
    anchor: id,
    kind: "exact_anchor",
  }), [requestSettingsNavigation]);

  useEffect(() => {
    if (!pendingReveal) return undefined;
    if (settingsGroupFor(pendingReveal).id !== activeGroup) return;
    const anchor = document.querySelector<HTMLElement>(
      `[data-settings-anchor="${pendingReveal}"]`,
    );
    if (!anchor) return;
    anchor.scrollIntoView({ block: "start" });
    anchor.focus({ preventScroll: true });
    setPendingReveal((current) => (current === pendingReveal ? null : current));
  }, [activeGroup, pendingReveal]);

  useEffect(() => {
    if (!navigationRequest || navigationRequest.sequence <= consumedNavigationSequenceRef.current) return;
    consumedNavigationSequenceRef.current = navigationRequest.sequence;
    revealSection(navigationRequest.target.section);
  }, [navigationRequest, revealSection]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setCatalogLoading(true);
      setCatalogFailed(false);
      try {
        const data = await getModelCatalog();
        if (cancelled) return;
        setCatalog(data);
        setDraft(fromRoutes(data.routes));
      } catch {
        if (!cancelled) setCatalogFailed(true);
      } finally {
        if (!cancelled) setCatalogLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const modelsByProvider = useMemo(() => {
    const grouped: Record<ModelProvider, ModelOption[]> = { anthropic: [], openai: [] };
    for (const m of catalog?.models ?? []) grouped[m.provider].push(m);
    return grouped;
  }, [catalog]);

  const modelProviderContexts = useMemo(
    () => catalog
      ? providerContexts(catalog.effective?.providers, catalog.credentials)
      : { anthropic: null, openai: null },
    [catalog],
  );
  const routeSaveBlocks = useMemo(
    () => catalog ? blockedRouteSaves(draft, catalog.routes, modelProviderContexts) : [],
    [catalog, draft, modelProviderContexts],
  );

  function invalidateTaskTest(task: ModelTask) {
    setTestState((prev) => {
      const state = prev[task];
      if (!state) return prev;
      return { ...prev, [task]: { ...state, loading: false, stale: true } };
    });
  }

  function invalidateAllTaskTests() {
    setTestState((prev) => Object.fromEntries(
      Object.entries(prev).map(([task, state]) => [
        task,
        state ? { ...state, loading: false, stale: true } : state,
      ]),
    ) as TestState);
  }

  async function save() {
    if (!catalog) return;
    if (routeSaveBlocks.length) return;
    setSaving(true);
    setRouteOutcome(null);
    setRuntimeOutcome(null);
    try {
      const routes: Partial<Record<ModelTask, { provider: ModelProvider; model: string; effort: string }>> = {};
      for (const task of catalog.tasks) {
        const row = draft[task.id];
        if (!row || !row.model.trim()) {
          setRouteOutcome({ kind: "missing_model", task: task.id });
          return;
        }
        routes[task.id] = { provider: row.provider, model: row.model.trim(), effort: row.effort || "default" };
      }
      await saveModelRoutes(routes);
      const refreshed = await getModelCatalog();
      setCatalog(refreshed);
      setDraft(fromRoutes(refreshed.routes));
      setTestState({});
      await onRuntimeChanged();
      setRouteOutcome({ kind: "save_succeeded" });
    } catch {
      setRouteOutcome({ kind: "save_failed" });
    } finally {
      setSaving(false);
    }
  }

  async function importRoutes() {
    setSaving(true);
    setRouteOutcome(null);
    setRuntimeOutcome(null);
    try {
      const result = await importModelRoutes();
      const refreshed = await getModelCatalog();
      setCatalog(refreshed);
      setDraft(fromRoutes(refreshed.routes));
      setTestState({});
      await onRuntimeChanged();
      setRouteOutcome({
        kind: "import_succeeded",
        imported: result.imported.length,
        skipped: result.skipped.length,
      });
    } catch {
      setRouteOutcome({ kind: "import_failed" });
    } finally {
      setSaving(false);
    }
  }

  async function exportRoutes() {
    setSaving(true);
    setRouteOutcome(null);
    setRuntimeOutcome(null);
    try {
      const result = await exportModelRoutes();
      // the clear branch can drop a task from profile→default, so refresh the badge/draft
      const refreshed = await getModelCatalog();
      setCatalog(refreshed);
      setDraft(fromRoutes(refreshed.routes));
      setTestState({});
      await onRuntimeChanged();
      setRouteOutcome({
        kind: "export_succeeded",
        exported: result.exported.length,
        cleared: result.cleared.length,
      });
    } catch {
      setRouteOutcome({ kind: "export_failed" });
    } finally {
      setSaving(false);
    }
  }

  async function saveRuntimeLimits(
    body: Pick<ResearchRuntimeSettings, "max_tool_calls" | "session_timeout_s" | "per_tool_timeout_s">,
  ) {
    setSaving(true);
    setRouteOutcome(null);
    setRuntimeOutcome(null);
    try {
      await saveResearchRuntime(body);
      await onRuntimeChanged();
      setRuntimeOutcome({ kind: "research_save_succeeded" });
    } catch (e) {
      setRuntimeOutcome({
        kind: "research_save_failed",
        diagnostic: e instanceof Error ? e.message : String(e),
      });
    } finally {
      setSaving(false);
    }
  }

  async function resetRuntimeLimits() {
    setSaving(true);
    setRouteOutcome(null);
    setRuntimeOutcome(null);
    try {
      await deleteResearchRuntime();
      await onRuntimeChanged();
      setRuntimeOutcome({ kind: "research_reset_succeeded" });
    } catch (e) {
      setRuntimeOutcome({
        kind: "research_reset_failed",
        diagnostic: e instanceof Error ? e.message : String(e),
      });
    } finally {
      setSaving(false);
    }
  }

  async function saveFixedTaskLimits(body: {
    tasks: {
      card_synthesis: { model_timeout_s: number };
      card_translation: { model_timeout_s: number };
    };
  }) {
    setSaving(true);
    setRouteOutcome(null);
    setRuntimeOutcome(null);
    try {
      await saveFixedTaskRuntime(body);
      await onRuntimeChanged();
      setRuntimeOutcome({ kind: "fixed_save_succeeded" });
    } catch (e) {
      setRuntimeOutcome({
        kind: "fixed_save_failed",
        diagnostic: e instanceof Error ? e.message : String(e),
      });
    } finally {
      setSaving(false);
    }
  }

  async function resetFixedTaskLimits() {
    setSaving(true);
    setRouteOutcome(null);
    setRuntimeOutcome(null);
    try {
      await deleteFixedTaskRuntime();
      await onRuntimeChanged();
      setRuntimeOutcome({ kind: "fixed_reset_succeeded" });
    } catch (e) {
      setRuntimeOutcome({
        kind: "fixed_reset_failed",
        diagnostic: e instanceof Error ? e.message : String(e),
      });
    } finally {
      setSaving(false);
    }
  }

  async function discoverAndRefresh(provider: ModelProvider, credentialId: string | null) {
    setDiscovery((prev) => ({
      ...prev,
      [provider]: { loading: true, result: null, credentialId },
    }));
    try {
      await runDiscoveryAndRefreshCatalog({
        discover: () => discoverModels(provider, credentialId),
        fetchCatalog: getModelCatalog,
        onResult: (result) =>
          setDiscovery((prev) => ({
            ...prev,
            [provider]: { loading: false, result, credentialId },
          })),
        onCatalog: (next) => {
          setCatalog(next);
          invalidateAllTaskTests();
        },
      });
    } catch (e) {
      setDiscovery((prev) => ({
        ...prev,
        [provider]: {
          loading: false,
          credentialId,
          result: {
            provider,
            credential_id: credentialId,
            status: "error",
            models: [],
            error: e instanceof Error ? e.message : String(e),
            source_url: null,
          },
        },
      }));
    }
  }

  function renderSection(id: SettingsAnchorId) {
    if (id === "providers") {
      if (!catalog) {
        if (catalogLoading) {
          return <p className="muted">{t(($) => $.workspace.catalog.loading)}</p>;
        }
        if (catalogFailed) {
          return (
            <p className="error-text">
              {t(($) => $.workspace.catalog.failure)}
            </p>
          );
        }
        return null;
      }
      return (
        <ProviderSection
          catalog={catalog}
          runtime={runtime}
          discovery={discovery}
          onRefresh={async () => {
            const refreshed = await getModelCatalog();
            setCatalog(refreshed);
            invalidateAllTaskTests();
            await onRuntimeChanged();
          }}
          onDiscover={async (provider, credentialId) => {
            await discoverAndRefresh(provider, credentialId);
          }}
          onClearDiscovery={(provider) => {
            setDiscovery((prev) => {
              const next = { ...prev };
              delete next[provider];
              return next;
            });
          }}
          onUseModel={(provider, model, task) => {
            invalidateTaskTest(task);
            onDraftForTask(setDraft, task, provider, model);
            revealSection("models");
          }}
          onNavigationGuardChange={setProviderGuard}
        />
      );
    }

    if (id === "models") {
      if (!catalog) return null;
      return (
        <>
          <div className="settings-model-actions">
            <div className="ui-action-row">
              <Button
                tone="primary"
                icon={<Save size={16} />}
                onClick={() => void save()}
                disabled={saving || catalogLoading || routeSaveBlocks.length > 0}
                aria-describedby={routeSaveBlocks.length ? "route-save-blocked" : undefined}
              >
                {saving
                  ? t(($) => $.actions.saving)
                  : t(($) => $.actions.save)}
              </Button>
            </div>
            {routeSaveBlocks.length > 0 ? (
              <p id="route-save-blocked" className="warn-text">
                {t(($) => $.workspace.routes.saveBlocked, {
                  value: routeSaveBlocks
                    .map(({ task }) => settingsTaskLabel(task, t))
                    .join(", "),
                })}
              </p>
            ) : null}
            <details className="settings-model-transfer">
              <summary>
                {t(($) => $.actions.import)} / {t(($) => $.actions.export)}
              </summary>
              <div className="ui-action-row">
                <Button
                  tone="secondary"
                  size="compact"
                  icon={<Upload size={15} />}
                  onClick={() => void importRoutes()}
                  disabled={saving || catalogLoading}
                  title={t(($) => $.actions.import)}
                >
                  {t(($) => $.actions.import)}
                </Button>
                <Button
                  tone="secondary"
                  size="compact"
                  icon={<Download size={15} />}
                  onClick={() => void exportRoutes()}
                  disabled={saving || catalogLoading}
                  title={t(($) => $.actions.export)}
                >
                  {t(($) => $.actions.export)}
                </Button>
              </div>
            </details>
          </div>
          <ModelRoutingSection
            catalog={catalog}
            draft={draft}
            modelsByProvider={modelsByProvider}
            testState={testState}
            developerMode={developerMode}
            onDraft={setDraft}
            onTest={async (task) => {
            const row = draft[task];
            if (!row || !row.model.trim()) return;
            const context = modelProviderContexts[row.provider];
            if (!context) return;
            const snapshot: TaskTestSnapshot = {
              task,
              provider: row.provider,
              model: row.model.trim(),
              effort: row.effort || "default",
              credential_id: context.credential_id,
            };
            setTestState((prev) => ({
              ...prev,
              [task]: { loading: true, result: null, snapshot, stale: false },
            }));
            try {
              const result = await testTaskModelAccess(
                task, row.provider, row.model.trim(), row.effort || "default",
              );
              setTestState((prev) => ({
                ...prev,
                [task]: {
                  loading: false,
                  result,
                  snapshot,
                  stale: prev[task]?.stale ?? false,
                },
              }));
            } catch (e) {
              setTestState((prev) => ({
                ...prev,
                [task]: {
                  loading: false,
                  snapshot,
                  stale: prev[task]?.stale ?? false,
                  result: {
                    task,
                    provider: row.provider,
                    auth_mode: context.auth_mode,
                    credential_id: null,
                    model: row.model,
                    effort: row.effort || "default",
                    status: "error",
                    error_code: "provider_call_failed",
                    latency_ms: null,
                    tested_at: new Date().toISOString(),
                    warning: e instanceof Error ? e.message : String(e),
                    fallback_effort: null,
                  },
                },
              }));
            }
            }}
            onInvalidateTest={invalidateTaskTest}
            onDiscover={discoverAndRefresh}
            onOpenProviders={() => revealSection("providers")}
            onReset={async (task) => {
            setRouteOutcome(null);
            setRuntimeOutcome(null);
            try {
              await deleteModelRoute(task);
              const refreshed = await getModelCatalog();
              setCatalog(refreshed);
              setDraft(fromRoutes(refreshed.routes));
              invalidateTaskTest(task);
              await onRuntimeChanged();
              setRouteOutcome({ kind: "reset_succeeded", task });
            } catch {
              setRouteOutcome({ kind: "reset_failed" });
            }
            }}
          />
        </>
      );
    }

    if (id === "fixed_task_runtime") {
      return runtime?.fixed_task_runtime ? (
        <FixedTaskRuntimeSection
          settings={runtime.fixed_task_runtime}
          saving={saving}
          onSave={saveFixedTaskLimits}
          onReset={resetFixedTaskLimits}
          onNavigationGuardChange={setFixedRuntimeGuard}
          developerMode={developerMode}
        />
      ) : null;
    }

    if (id === "research_runtime") {
      return runtime?.research_runtime ? (
        <ResearchRuntimeSection
          settings={runtime.research_runtime}
          saving={saving}
          onSave={saveRuntimeLimits}
          onReset={resetRuntimeLimits}
          onNavigationGuardChange={setResearchRuntimeGuard}
          developerMode={developerMode}
        />
      ) : null;
    }

    if (id === "investor_profile") {
      const markPotentialDirty = () => setInvestorPotentialDirty(true);
      return (
        <div onInputCapture={markPotentialDirty} onChangeCapture={markPotentialDirty}>
          <InvestorProfilePanel />
        </div>
      );
    }
    if (id === "data_sources") {
      return <DataSourcesSection onNavigationGuardChange={setDataSourcesGuard} />;
    }
    if (id === "data_storage") return <DataStorageSection />;
    if (id === "news_storage") return <NewsStorageSection />;
    return <MacroStorageSection />;
  }

  const directory = (
    <SettingsDirectory
      query={directoryQuery}
      currentTarget={section}
      activeGroup={activeGroup}
      onQueryChange={setDirectoryQuery}
      onSelect={revealSection}
    />
  );

  const tabItems: readonly TabItem<SettingsGroupId>[] = SETTINGS_GROUPS.map((group) => ({
    value: group.id,
    label: settingsWorkspaceTabLabel(group.id, t),
    tabRef: tabRefFor(group.id),
    panel: (
      <div className="settings-workspace-layout">
        {!shellOverlay ? <aside className="settings-directory-rail">{directory}</aside> : null}
        <div className="settings-workspace-groups">
          {group.sections.map((definition) => (
            <SettingsSectionAnchor id={definition.id} key={definition.id}>
              {renderSection(definition.id)}
            </SettingsSectionAnchor>
          ))}
        </div>
      </div>
    ),
  }));
  const routeOutcomePresentation = routeOutcome
    ? settingsRouteOutcomePresentation(routeOutcome, t)
    : null;
  const runtimeOutcomePresentation = runtimeOutcome
    ? settingsRuntimeOutcomePresentation(runtimeOutcome, t)
    : null;
  const runtimeDiagnostic = runtimeOutcomeDiagnostic(runtimeOutcome);

  return (
    <main className="main settings-workspace" data-settings-overlay={String(shellOverlay)}>
      <PageHeader title={t(($) => $.workspace.title)} />

      {routeOutcomePresentation?.tone === "error" ? (
        <p className="error-text">{routeOutcomePresentation.message}</p>
      ) : null}
      {runtimeOutcomePresentation?.tone === "error" ? (
        <p className="error-text">{runtimeOutcomePresentation.message}</p>
      ) : null}
      {routeOutcomePresentation?.tone === "ok" ? (
        <p className="ok-text">{routeOutcomePresentation.message}</p>
      ) : null}
      {runtimeOutcomePresentation?.tone === "ok" ? (
        <p className="ok-text">{runtimeOutcomePresentation.message}</p>
      ) : null}
      {developerMode ? (
        <DeveloperDiagnostics diagnostics={[runtimeDiagnostic]} t={t} />
      ) : null}
      {blockedNotice ? (
        <InlineAlert state="blocked" title={t(($) => $.workspace.blocked.title)}>
          {blockedNotice}
        </InlineAlert>
      ) : null}
      {shellOverlay ? (
        <Button
          ref={directoryTriggerRef}
          className="settings-directory-trigger"
          tone="secondary"
          size="compact"
          icon={<Menu size={16} />}
          onClick={() => setDirectoryOpen(true)}
        >
          {t(($) => $.workspace.directory.title)}
        </Button>
      ) : null}

      <Tabs
        className="settings-workflow-tabs"
        ariaLabel={t(($) => $.workspace.tabs.label)}
        value={activeGroup}
        items={tabItems}
        onValueChange={(group) => requestSettingsNavigation({
          group,
          anchor: firstSettingsAnchor(group),
          kind: "manual_group",
        })}
      />

      <Drawer
        open={shellOverlay && directoryOpen}
        title={t(($) => $.workspace.directory.title)}
        onClose={() => setDirectoryOpen(false)}
        returnFocusRef={directoryTriggerRef}
      >
        {directory}
      </Drawer>

      <ConfirmDialog
        open={pendingIntent !== null}
        title={t(($) => $.workspace.blocked.title)}
        consequence={t(($) => $.workspace.blocked.description)}
        confirmLabel={t(($) => $.workspace.blocked.discard)}
        cancelLabel={t(($) => $.workspace.blocked.stay)}
        returnFocusRef={dialogReturnFocusRef}
        onCancel={() => {
          dialogReturnFocusRef.current = tabRefFor(activeGroup).current;
          setPendingIntent(null);
        }}
        onConfirm={() => {
          if (!pendingIntent) return;
          const intent = pendingIntent;
          dialogReturnFocusRef.current = tabRefFor(intent.group).current;
          if (activeGroup === "personalization") setInvestorPotentialDirty(false);
          setPendingIntent(null);
          applySettingsIntent(intent);
        }}
      />
    </main>
  );
}

// ---- Data Sources: provider health + per-source app-owned scheduling (3e) ----

function fromRoutes(routes: Record<ModelTask, TaskRoute>): Partial<Record<ModelTask, DraftRoute>> {
  const out: Partial<Record<ModelTask, DraftRoute>> = {};
  for (const task of Object.keys(routes) as ModelTask[]) {
    out[task] = {
      provider: routes[task].provider,
      model: routes[task].model,
      effort: routes[task].effort || "default",
      custom: routes[task].custom,
    };
  }
  return out;
}

function onDraftForTask(
  setDraft: Dispatch<SetStateAction<Partial<Record<ModelTask, DraftRoute>>>>,
  task: ModelTask,
  provider: ModelProvider,
  model: string,
) {
  setDraft((prev) => ({
    ...prev,
    [task]: {
      provider,
      model,
      effort: prev[task]?.effort ?? "default",
      custom: true,
    },
  }));
}
