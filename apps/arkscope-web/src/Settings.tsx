import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Download, Menu, RefreshCw, Save, Upload } from "lucide-react";
import { useTranslation } from "react-i18next";
import { InvestigationRuntimeSection } from "./settings/InvestigationRuntimeSection";
import {
  ApiError,
  discoverModels,
  deleteModelRoute,
  exportModelRoutes,
  getMacroSnapshot,
  getMacroStatus,
  getMarketDataStatus,
  getModelCatalog,
  getNewsStatus,
  getProvidersConfig,
  getProvidersHealth,
  getSchedule,
  listSecurityLifecycleCases,
  getTradingDayCoverage,
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
  modelReasonLabel,
  providerContexts,
  routesSemanticallyEqual,
  type ModelCommonT,
  type TaskTestSnapshot,
} from "./modelRoutingUx";
import { taskRouteBlocker } from "./researchModels";
import { InvestorProfilePanel } from "./InvestorProfilePanel";
import type {
  NavigationRequest,
  NavigationTarget,
} from "./shell/navigation";
import { DataSourcesSection } from "./settings/DataSourcesSection";
import { DataStorageSection } from "./settings/DataStorageSection";
import { DeveloperDiagnostics } from "./settings/DeveloperDiagnostics";
import { MacroStorageSection } from "./settings/MacroStorageSection";
import { DataScheduleControlsProvider } from "./settings/dataScheduleControls";
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
import { LocaleSelector } from "./settings/LocaleSelector";
import { SettingsSectionAnchor } from "./settings/SettingsSectionAnchor";
import {
  CLEAR_SETTINGS_NAVIGATION_GUARD,
  type SettingsNavigationGuard,
} from "./settings/settingsNavigationGuard";
import {
  SETTINGS_GROUPS,
  firstSettingsAnchor,
  settingsGroup,
  settingsGroupForLocation,
  settingsParentAnchor,
  settingsSubsectionsFor,
  type SettingsAnchorId,
  type SettingsGroupId,
  type SettingsLocationId,
} from "./settings/settingsRegistry";
import {
  readActiveSettingsGroup,
  writeActiveSettingsGroup,
} from "./settings/settingsPreferences";
import {
  createSettingsReadCache,
  scheduleSettingsIdleWarmup,
  type SettingsReadCache,
} from "./settings/settingsReadCache";
import { loadValidatedOAuthAccountSnapshot } from "./settings/useOAuthAccountUsage";
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
  settingsReadCache?: SettingsReadCache;
  onNavigateTarget?: (target: NavigationTarget) => void;
}

type SettingsNavigationIntent = {
  group: SettingsGroupId;
  anchor: SettingsAnchorId;
  location?: SettingsLocationId;
  kind: "manual_group" | "exact_anchor";
};

type RouteSaveRequest = Partial<Record<ModelTask, Pick<TaskRoute, "provider" | "model" | "effort">>>;

function confirmedSavedRoutes(value: unknown, requested: RouteSaveRequest): Partial<Record<ModelTask, TaskRoute>> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const candidates = value as Record<string, unknown>;
  const confirmed: Partial<Record<ModelTask, TaskRoute>> = {};
  for (const task of Object.keys(requested) as ModelTask[]) {
    const candidate = candidates[task];
    if (!candidate || typeof candidate !== "object" || Array.isArray(candidate)) return null;
    const row = candidate as Record<string, unknown>;
    const expected = requested[task]!;
    if (row.task !== task || row.source !== "db"
      || row.provider !== expected.provider || row.model !== expected.model || row.effort !== expected.effort
      || typeof row.custom !== "boolean" || (row.warning !== null && typeof row.warning !== "string")) return null;
    confirmed[task] = {
      task, ...expected, source: "db", custom: row.custom, warning: row.warning,
    };
  }
  return Object.keys(confirmed).length ? confirmed : null;
}

// Only localized, reviewed reason codes may reach product copy, never raw API diagnostics.
const ROUTE_SAVE_REASONS = new Set([
  "missing_active_credential", "task_auth_mode_unsupported", "model_auth_unverified",
  "model_entitlement_unverified", "task_capability_missing", "model_not_visible",
  "model_not_in_registry", "discovery_unavailable", "reauth_required", "model_task_unsupported",
  "model_output_limit_unknown", "version_incompatible", "model_retired",
  "subscription_plan_required", "subscription_plan_unverified",
]);

type SettingsRouteOutcome =
  | { kind: "save_succeeded" }
  | { kind: "save_refresh_failed" }
  | { kind: "save_unknown" }
  | { kind: "save_superseded" }
  | { kind: "missing_model"; task: ModelTask }
  | { kind: "save_failed"; reason?: string }
  | { kind: "import_succeeded"; imported: number; skipped: number }
  | { kind: "import_failed" }
  | { kind: "export_succeeded"; exported: number; cleared: number }
  | { kind: "export_failed" }
  | { kind: "reset_succeeded"; task: ModelTask }
  | { kind: "reset_failed" };

type SettingsRouteOutcomePresentation = {
  tone: "ok" | "error" | "warning";
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
  commonT: ModelCommonT,
): SettingsRouteOutcomePresentation {
  switch (outcome.kind) {
    case "save_succeeded":
      return { tone: "ok", message: t(($) => $.workspace.routes.saved) };
    case "save_refresh_failed":
      return { tone: "warning", message: t(($) => $.workspace.routes.savedRefreshFailed) };
    case "save_unknown":
      return { tone: "warning", message: t(($) => $.workspace.routes.saveUnknown) };
    case "save_superseded":
      return { tone: "warning", message: t(($) => $.workspace.routes.saveSuperseded) };
    case "missing_model":
      return {
        tone: "error",
        message: t(($) => $.workspace.routes.missingModel, {
          taskLabel: settingsTaskLabel(outcome.task, t),
        }),
      };
    case "save_failed":
      return {
        tone: "error",
        message: outcome.reason
          ? t(($) => $.workspace.routes.saveRejected, { reason: modelReasonLabel(outcome.reason, commonT) })
          : t(($) => $.workspace.routes.saveFailed),
      };
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

function activeOAuthLocalCredentialIds(value: unknown): string[] {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return [];
  const credentials = (value as { credentials?: unknown }).credentials;
  if (typeof credentials !== "object" || credentials === null || Array.isArray(credentials)) return [];
  const ids: string[] = [];
  for (const providerCredentials of Object.values(credentials)) {
    if (!Array.isArray(providerCredentials)) return [];
    for (const credential of providerCredentials) {
      if (typeof credential !== "object" || credential === null || Array.isArray(credential)) return [];
      const candidate = credential as Record<string, unknown>;
      if (
        candidate.active === true
        && (candidate.auth_type === "chatgpt_oauth" || candidate.auth_type === "claude_code_oauth")
        && typeof candidate.id === "string"
      ) {
        ids.push(candidate.id);
      }
    }
  }
  return ids;
}

export function SettingsView({
  runtime,
  developerMode,
  onRuntimeChanged,
  navigationRequest,
  settingsReadCache,
  onNavigateTarget = () => {},
}: SettingsViewProps) {
  const { t } = useTranslation("settings");
  const { t: commonT } = useTranslation("common");
  const cacheRef = useRef<SettingsReadCache | null>(null);
  if (cacheRef.current === null) {
    cacheRef.current = settingsReadCache ?? createSettingsReadCache();
  }
  const readCache = cacheRef.current;
  const initialCatalogRef = useRef<ReturnType<SettingsReadCache["inspect"]> | null>(null);
  if (initialCatalogRef.current === null) {
    initialCatalogRef.current = readCache.inspect<ModelCatalog>("model_catalog");
  }
  const initialCatalog = initialCatalogRef.current.status === "missing"
    ? null
    : initialCatalogRef.current.value as ModelCatalog;
  const [catalog, setCatalog] = useState<ModelCatalog | null>(initialCatalog);
  const [draft, setDraft] = useState<Partial<Record<ModelTask, DraftRoute>>>(() => (
    initialCatalog ? fromRoutes(initialCatalog.routes) : {}
  ));
  const [catalogLoading, setCatalogLoading] = useState(
    initialCatalogRef.current.status !== "fresh",
  );
  const [catalogFailed, setCatalogFailed] = useState(false);
  const [saving, setSaving] = useState(false);
  const [routeOutcome, setRouteOutcome] = useState<SettingsRouteOutcome | null>(null);
  const routeOutcomePresentation = routeOutcome
    ? settingsRouteOutcomePresentation(routeOutcome, t, commonT)
    : null;
  const pendingRouteSave = useRef<{
    routes: RouteSaveRequest;
    baseline: ModelCatalog["routes"];
    editedTasks: Set<ModelTask>;
    acknowledged: boolean;
  } | null>(null);
  const [runtimeOutcome, setRuntimeOutcome] = useState<SettingsRuntimeOutcome | null>(null);
  const [activeGroup, setActiveGroup] = useState<SettingsGroupId>(() => readActiveSettingsGroup());
  const [section, setSection] = useState<SettingsLocationId>(() => firstSettingsAnchor(activeGroup));
  const [directoryQuery, setDirectoryQuery] = useState("");
  const [directoryOpen, setDirectoryOpen] = useState(false);
  const [pendingReveal, setPendingReveal] = useState<SettingsLocationId | null>(null);
  const [pendingGroupTop, setPendingGroupTop] = useState<SettingsGroupId | null>(null);
  const [pendingIntent, setPendingIntent] = useState<SettingsNavigationIntent | null>(null);
  const [blockedNotice, setBlockedNotice] = useState<string | null>(null);
  const [providerGuard, setProviderGuard] = useState<SettingsNavigationGuard>(CLEAR_SETTINGS_NAVIGATION_GUARD);
  const [fixedRuntimeGuard, setFixedRuntimeGuard] = useState<SettingsNavigationGuard>(CLEAR_SETTINGS_NAVIGATION_GUARD);
  const [investigationGuard, setInvestigationGuard] = useState<SettingsNavigationGuard>(CLEAR_SETTINGS_NAVIGATION_GUARD);
  const [researchRuntimeGuard, setResearchRuntimeGuard] = useState<SettingsNavigationGuard>(CLEAR_SETTINGS_NAVIGATION_GUARD);
  const [dataSourcesGuard, setDataSourcesGuard] = useState<SettingsNavigationGuard>(CLEAR_SETTINGS_NAVIGATION_GUARD);
  const [investorGuard, setInvestorGuard] = useState<SettingsNavigationGuard>(CLEAR_SETTINGS_NAVIGATION_GUARD);
  const [investorSummaryRequestSequence, setInvestorSummaryRequestSequence] = useState(0);
  const [investorPendingRevealSequence, setInvestorPendingRevealSequence] = useState<number | null>(null);
  const consumedNavigationSequenceRef = useRef(0);
  const investorSummarySequenceRef = useRef(0);
  const investorPendingRevealSequenceRef = useRef<number | null>(null);
  const settingsScrollOwnerRef = useRef<HTMLElement>(null);
  const directoryTriggerRef = useRef<HTMLButtonElement>(null);
  const aiModelsTabRef = useRef<HTMLButtonElement>(null);
  const personalizationTabRef = useRef<HTMLButtonElement>(null);
  const dataSyncTabRef = useRef<HTMLButtonElement>(null);
  const dialogReturnFocusRef = useRef<HTMLElement | null>(null);
  const discoveryReturnFocusRef = useRef<HTMLElement | null>(null);
  const [discovery, setDiscovery] = useState<DiscoveryState>({});
  const [discoveryPanelProvider, setDiscoveryPanelProvider] = useState<ModelProvider | null>(null);
  const [discoveryPanelOpen, setDiscoveryPanelOpen] = useState(false);
  const [testState, setTestState] = useState<TestState>({});
  const shellOverlay = useShellOverlay();

  const tabRefFor = useCallback((group: SettingsGroupId) => {
    if (group === "ai_models") return aiModelsTabRef;
    if (group === "personalization") return personalizationTabRef;
    return dataSyncTabRef;
  }, []);

  const applySettingsIntent = useCallback((intent: SettingsNavigationIntent) => {
    if (intent.kind === "exact_anchor" && intent.anchor === "investor_profile") {
      const sequence = investorSummarySequenceRef.current + 1;
      investorSummarySequenceRef.current = sequence;
      investorPendingRevealSequenceRef.current = sequence;
      setInvestorSummaryRequestSequence(sequence);
      setInvestorPendingRevealSequence(sequence);
    } else {
      investorPendingRevealSequenceRef.current = null;
      setInvestorPendingRevealSequence(null);
    }
    setActiveGroup(intent.group);
    writeActiveSettingsGroup(intent.group);
    const location = intent.location ?? intent.anchor;
    setSection(location);
    setDirectoryOpen(false);
    if (intent.kind === "exact_anchor") {
      setPendingGroupTop(null);
      setPendingReveal(location);
    } else {
      setPendingReveal(null);
      setPendingGroupTop(intent.group);
    }
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
        investigationGuard,
        researchRuntimeGuard,
      ]);
    }
    if (activeGroup === "personalization") {
      return investorGuard;
    }
    return dataSourcesGuard;
  }, [
    activeGroup,
    dataSourcesGuard,
    fixedRuntimeGuard,
    investigationGuard,
    investorGuard,
    providerGuard,
    researchRuntimeGuard,
    saving,
    t,
  ]);

  const requestSettingsNavigation = useCallback((intent: SettingsNavigationIntent): boolean => {
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

  const revealLocation = useCallback((id: SettingsLocationId) => {
    const anchor = settingsParentAnchor(id);
    return requestSettingsNavigation({
      group: settingsGroupForLocation(id).id,
      anchor,
      location: id,
      kind: "exact_anchor",
    });
  }, [requestSettingsNavigation]);

  const revealSection = useCallback((id: SettingsAnchorId) => revealLocation(id), [revealLocation]);

  const handleInvestorSummaryRequest = useCallback((
    sequence: number,
    committed: boolean,
  ) => {
    if (investorPendingRevealSequenceRef.current !== sequence) return;
    investorPendingRevealSequenceRef.current = null;
    setInvestorPendingRevealSequence(null);
    if (!committed) {
      setPendingReveal((current) => current === "investor_profile" ? null : current);
    }
  }, []);

  useEffect(() => {
    if (!pendingGroupTop || pendingGroupTop !== activeGroup) return;
    const scrollOwner = settingsScrollOwnerRef.current;
    const selectedTab = tabRefFor(pendingGroupTop).current;
    if (!scrollOwner || !selectedTab) return;
    scrollOwner.scrollTop = 0;
    selectedTab.focus({ preventScroll: true });
    setPendingGroupTop((current) => (current === pendingGroupTop ? null : current));
  }, [activeGroup, pendingGroupTop, tabRefFor]);

  useEffect(() => {
    if (!pendingReveal) return undefined;
    if (pendingReveal === "investor_profile" && investorPendingRevealSequence !== null) {
      return undefined;
    }
    if (settingsGroupForLocation(pendingReveal).id !== activeGroup) return;
    const anchor = document.querySelector<HTMLElement>(
      `[data-settings-location="${pendingReveal}"]`,
    );
    if (!anchor) return;
    anchor.scrollIntoView({ block: "start" });
    anchor.focus({ preventScroll: true });
    setPendingReveal((current) => (current === pendingReveal ? null : current));
  }, [activeGroup, investorPendingRevealSequence, pendingReveal]);

  useEffect(() => {
    if (activeGroup !== "ai_models") setDiscoveryPanelOpen(false);
  }, [activeGroup]);

  useEffect(() => {
    const scrollOwner = settingsScrollOwnerRef.current;
    if (!scrollOwner) return undefined;
    const activeLocations = new Set<SettingsLocationId>(
      settingsGroup(activeGroup).sections.flatMap((definition) => [
        definition.id,
        ...settingsSubsectionsFor(definition.id).map((subsection) => subsection.id),
      ]),
    );

    const updateCurrentLocation = () => {
      const anchors = Array.from(
        scrollOwner.querySelectorAll<HTMLElement>("[data-settings-location]"),
      ).filter((anchor) => activeLocations.has(anchor.dataset.settingsLocation as SettingsLocationId));
      if (anchors.length === 0) return;

      const measurements = anchors.map((anchor) => ({
        anchor,
        top: anchor.getBoundingClientRect().top,
      }));
      if (
        scrollOwner.scrollHeight === 0
        && scrollOwner.clientHeight === 0
        && measurements.every((measurement) => measurement.top === 0)
      ) {
        return;
      }

      const ownerTop = scrollOwner.getBoundingClientRect().top;
      const tabBottom = scrollOwner
        .querySelector<HTMLElement>(".settings-workflow-tabs > .ui-tab-list")
        ?.getBoundingClientRect().bottom ?? ownerTop;
      const threshold = Math.max(ownerTop, tabBottom) + 1;
      let current = measurements[0].anchor.dataset.settingsLocation as SettingsLocationId;
      for (const measurement of measurements) {
        if (measurement.top > threshold) break;
        current = measurement.anchor.dataset.settingsLocation as SettingsLocationId;
      }
      if (
        scrollOwner.scrollHeight > scrollOwner.clientHeight
        && scrollOwner.scrollTop + scrollOwner.clientHeight >= scrollOwner.scrollHeight - 1
      ) {
        current = measurements.at(-1)!.anchor.dataset.settingsLocation as SettingsLocationId;
      }
      setSection((value) => (value === current ? value : current));
    };

    updateCurrentLocation();
    scrollOwner.addEventListener("scroll", updateCurrentLocation, { passive: true });
    window.addEventListener("resize", updateCurrentLocation);
    return () => {
      scrollOwner.removeEventListener("scroll", updateCurrentLocation);
      window.removeEventListener("resize", updateCurrentLocation);
    };
  }, [activeGroup]);

  useEffect(() => {
    if (!navigationRequest || navigationRequest.sequence <= consumedNavigationSequenceRef.current) return;
    consumedNavigationSequenceRef.current = navigationRequest.sequence;
    revealSection(navigationRequest.target.section);
  }, [navigationRequest, revealSection]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const retained = readCache.inspect<ModelCatalog>("model_catalog");
      setCatalogLoading(retained.status !== "fresh");
      setCatalogFailed(false);
      const outcome = await readCache.load("model_catalog", getModelCatalog);
      if (cancelled) return;
      if (outcome.status === "success") {
        setCatalog(outcome.value);
        setDraft(fromRoutes(outcome.value.routes));
      } else if (outcome.status === "error") {
        setCatalogFailed(true);
      }
      setCatalogLoading(false);
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [readCache]);

  useEffect(() => {
    if (settingsReadCache === undefined) return undefined;
    return scheduleSettingsIdleWarmup({
      cache: readCache,
      loaders: {
        model_catalog: getModelCatalog,
        data_schedule: getSchedule,
        provider_health: getProvidersHealth,
        provider_config: getProvidersConfig,
        market_data_status: getMarketDataStatus,
        security_lifecycle: () => listSecurityLifecycleCases({ limit: 1 }),
        "trading_day_coverage:15min:10": () => getTradingDayCoverage(10, "15min"),
        news_status: getNewsStatus,
        macro_status: getMacroStatus,
        macro_snapshot: getMacroSnapshot,
      },
      selectActiveOAuthLocalIds: activeOAuthLocalCredentialIds,
      loadOAuthAccountUsage: loadValidatedOAuthAccountSnapshot,
    });
  }, [readCache, settingsReadCache]);

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
    () => catalog ? blockedRouteSaves(draft, catalog.routes, modelProviderContexts, catalog) : [],
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

  async function fetchCatalogAfterMutation(): Promise<ModelCatalog> {
    readCache.invalidate("model_catalog");
    const outcome = await readCache.load("model_catalog", getModelCatalog, { force: true });
    if (outcome.status !== "success") throw new Error("model catalog refresh failed");
    return outcome.value;
  }

  async function save() {
    if (!catalog) return;
    if (routeSaveBlocks.length) return;
    setSaving(true);
    setRouteOutcome(null);
    setRuntimeOutcome(null);
    try {
      const routes: RouteSaveRequest = {};
      const changedTasks = catalog.tasks.filter((task) => !routesSemanticallyEqual(draft[task.id], catalog.routes[task.id]));
      // An explicit save of unchanged defaults still persists them; edits touch only their own tasks.
      for (const task of changedTasks.length ? changedTasks : catalog.tasks) {
        const row = draft[task.id];
        if (!row || !row.model.trim()) {
          setRouteOutcome({ kind: "missing_model", task: task.id });
          return;
        }
        if (taskRouteBlocker(catalog, row, task.id)) return;
        routes[task.id] = { provider: row.provider, model: row.model.trim(), effort: row.effort.trim() };
      }
      pendingRouteSave.current = { routes, baseline: { ...catalog.routes }, editedTasks: new Set(), acknowledged: false };
      try {
        const result = await saveModelRoutes(routes);
        const confirmed = confirmedSavedRoutes(result?.routes, routes);
        if (confirmed) {
          pendingRouteSave.current.acknowledged = true;
          applyRouteReceipt(confirmed, routes);
        }
      } catch (error) {
        if (error instanceof ApiError && [400, 401, 403, 404, 409, 422].includes(error.status)) {
          pendingRouteSave.current = null;
          setRouteOutcome({ kind: "save_failed", reason: error.code && ROUTE_SAVE_REASONS.has(error.code) ? error.code : undefined });
          return;
        }
        // A missing response does not prove that the write failed. Read back; never retry the PUT.
      }
      await checkRouteSave();
    } finally {
      setSaving(false);
    }
  }

  function applyRouteReceipt(routes: Partial<Record<ModelTask, TaskRoute>>, requested: RouteSaveRequest) {
    setCatalog((current) => current ? { ...current, routes: { ...current.routes, ...routes } } : current);
    setDraft((current) => {
      const next = { ...current };
      for (const task of Object.keys(routes) as ModelTask[]) {
        if (!pendingRouteSave.current?.editedTasks.has(task) && routesSemanticallyEqual(current[task], requested[task])) {
          next[task] = fromRoutes(routes)[task];
        }
      }
      return next;
    });
    setTestState({});
  }

  async function checkRouteSave() {
    const pending = pendingRouteSave.current;
    if (!pending) return;
    setSaving(true);
    try {
      const refreshed = await fetchCatalogAfterMutation();
      const confirmed = confirmedSavedRoutes(refreshed.routes, pending.routes);
      if (confirmed) pending.acknowledged = true;
      const baseline = pending.baseline;
      const acknowledged = pending.acknowledged;
      const currentRoutes = fromRoutes(refreshed.routes);
      setCatalog(refreshed);
      setDraft((current) => {
        const next = { ...current };
        for (const task of Object.keys(currentRoutes) as ModelTask[]) {
          if (pending.routes[task] && !acknowledged) continue;
          if (!pending.editedTasks.has(task) && (
            routesSemanticallyEqual(current[task], baseline[task])
            || (acknowledged && routesSemanticallyEqual(current[task], pending.routes[task]))
          )) next[task] = currentRoutes[task];
        }
        return next;
      });
      pending.baseline = { ...refreshed.routes };
      setTestState({});
      await onRuntimeChanged();
      setRouteOutcome({ kind: confirmed ? "save_succeeded" : acknowledged ? "save_superseded" : "save_unknown" });
      if (acknowledged) pendingRouteSave.current = null;
    } catch {
      setRouteOutcome({ kind: pending.acknowledged ? "save_refresh_failed" : "save_unknown" });
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
      const refreshed = await fetchCatalogAfterMutation();
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
      const refreshed = await fetchCatalogAfterMutation();
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

  function openDiscoveryPanel(provider: ModelProvider) {
    discoveryReturnFocusRef.current = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;
    setDiscoveryPanelProvider(provider);
    setDiscoveryPanelOpen(true);
  }

  async function discoverAndRefresh(provider: ModelProvider, credentialId: string | null) {
    openDiscoveryPanel(provider);
    setDiscovery((prev) => ({
      ...prev,
      [provider]: { loading: true, result: null, credentialId },
    }));
    try {
      await runDiscoveryAndRefreshCatalog({
        discover: () => discoverModels(provider, credentialId),
        fetchCatalog: fetchCatalogAfterMutation,
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
          discoveryPanelProvider={discoveryPanelProvider}
          discoveryPanelOpen={discoveryPanelOpen}
          discoveryReturnFocusRef={discoveryReturnFocusRef}
          settingsReadCache={readCache}
          developerMode={developerMode}
          onRefresh={async () => {
            const refreshed = await fetchCatalogAfterMutation();
            setCatalog(refreshed);
            invalidateAllTaskTests();
            await onRuntimeChanged();
          }}
          onDiscover={async (provider, credentialId) => {
            await discoverAndRefresh(provider, credentialId);
          }}
          onOpenDiscovery={openDiscoveryPanel}
          onCloseDiscovery={() => setDiscoveryPanelOpen(false)}
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
            {routeOutcomePresentation ? (
              <div role={routeOutcomePresentation.tone === "error" ? "alert" : "status"}>
                <p className={routeOutcomePresentation.tone === "error" ? "error-text"
                  : routeOutcomePresentation.tone === "warning" ? "warn-text" : "ok-text"}>
                  {routeOutcomePresentation.message}
                </p>
                {routeOutcomePresentation.tone === "warning" && pendingRouteSave.current ? (
                  <Button size="compact" tone="secondary" icon={<RefreshCw size={15} />}
                    disabled={saving} onClick={() => void checkRouteSave()}>
                    {t(($) => $.workspace.routes.readSavedState)}
                  </Button>
                ) : null}
              </div>
            ) : null}
            {routeSaveBlocks.length > 0 ? (
              <div id="route-save-blocked">
                {(["missing_active_credential", "effort_required", "model_retired"] as const)
                  .map((reason) => {
                    const tasks = routeSaveBlocks
                      .filter((block) => block.reason === reason)
                      .map(({ task }) => settingsTaskLabel(task, t))
                      .join(", ");
                    if (!tasks) return null;
                    const message = reason === "missing_active_credential"
                      ? t(($) => $.workspace.routes.saveBlocked, { value: tasks })
                      : reason === "effort_required"
                        ? t(($) => $.workspace.routes.effortRequired, { value: tasks })
                        : t(($) => $.workspace.routes.modelRetired, { value: tasks });
                    return <p className="warn-text" key={reason}>{message}</p>;
                  })}
              </div>
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
            onDraft={(update) => {
              const pending = pendingRouteSave.current;
              setDraft((current) => {
                const next = typeof update === "function" ? update(current) : update;
                for (const task of Object.keys(next) as ModelTask[]) {
                  if (!routesSemanticallyEqual(next[task], current[task])) pending?.editedTasks.add(task);
                }
                return next;
              });
            }}
            onTest={async (task) => {
            const row = draft[task];
            if (!row || !row.model.trim() || taskRouteBlocker(catalog, row, task)) return;
            const context = modelProviderContexts[row.provider];
            if (!context) return;
            const snapshot: TaskTestSnapshot = {
              task,
              provider: row.provider,
              model: row.model.trim(),
              effort: row.effort.trim(),
              credential_id: context.credential_id,
            };
            setTestState((prev) => ({
              ...prev,
              [task]: { loading: true, result: null, snapshot, stale: false },
            }));
            try {
              const result = await testTaskModelAccess(
                task, row.provider, row.model.trim(), row.effort.trim(),
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
                    effort: row.effort.trim(),
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
            discoveryAvailable={{
              anthropic: !!discovery.anthropic,
              openai: !!discovery.openai,
            }}
            onOpenDiscovery={openDiscoveryPanel}
            onOpenProviders={() => revealSection("providers")}
            onReset={async (task) => {
            setRouteOutcome(null);
            setRuntimeOutcome(null);
            try {
              await deleteModelRoute(task);
              const refreshed = await fetchCatalogAfterMutation();
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
        <><FixedTaskRuntimeSection
          settings={runtime.fixed_task_runtime}
          saving={saving}
          onSave={saveFixedTaskLimits}
          onReset={resetFixedTaskLimits}
          onNavigationGuardChange={setFixedRuntimeGuard}
          developerMode={developerMode}
        /><InvestigationRuntimeSection authMode={modelProviderContexts[draft.lifecycle_investigation?.provider ?? "anthropic"]?.auth_mode}
          onNavigationGuardChange={setInvestigationGuard} /></>
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
      return (
        <InvestorProfilePanel
          developerMode={developerMode}
          onNavigationGuardChange={setInvestorGuard}
          onNavigateToProviders={() => revealSection("providers")}
          summaryRequestSequence={investorSummaryRequestSequence}
          onSummaryRequestHandled={handleInvestorSummaryRequest}
        />
      );
    }
    if (id === "data_sources") {
      return (
        <DataSourcesSection
          onNavigationGuardChange={setDataSourcesGuard}
          developerMode={developerMode}
          settingsReadCache={readCache}
        />
      );
    }
    if (id === "data_storage") {
      return (
        <DataStorageSection
          developerMode={developerMode}
          settingsReadCache={readCache}
          onNavigateTarget={onNavigateTarget}
        />
      );
    }
    if (id === "news_storage") {
      return <NewsStorageSection developerMode={developerMode} settingsReadCache={readCache} />;
    }
    return <MacroStorageSection settingsReadCache={readCache} />;
  }

  const directory = (
    <SettingsDirectory
      query={directoryQuery}
      activeGroup={activeGroup}
      currentTarget={section}
      onQueryChange={setDirectoryQuery}
      onSelect={revealLocation}
    />
  );

  const tabItems: readonly TabItem<SettingsGroupId>[] = SETTINGS_GROUPS.map((group) => {
    const sections = group.sections.map((definition) => (
      <SettingsSectionAnchor id={definition.id} key={definition.id}>
        {renderSection(definition.id)}
      </SettingsSectionAnchor>
    ));
    return {
      value: group.id,
      label: settingsWorkspaceTabLabel(group.id, t),
      tabRef: tabRefFor(group.id),
      panel: (
        <div className="settings-workspace-layout">
          {!shellOverlay ? <aside className="settings-directory-rail">{directory}</aside> : null}
          <div className="settings-workspace-groups">
            {group.id === "data_sync" ? (
              <DataScheduleControlsProvider settingsReadCache={readCache}>
                {sections}
              </DataScheduleControlsProvider>
            ) : sections}
          </div>
        </div>
      ),
    };
  });
  const runtimeOutcomePresentation = runtimeOutcome
    ? settingsRuntimeOutcomePresentation(runtimeOutcome, t)
    : null;
  const runtimeDiagnostic = runtimeOutcomeDiagnostic(runtimeOutcome);

  return (
    <main
      ref={settingsScrollOwnerRef}
      className="main settings-workspace"
      data-settings-overlay={String(shellOverlay)}
    >
      <div className="settings-page-lede">
        <PageHeader
          title={t(($) => $.workspace.title)}
          actions={<LocaleSelector />}
        />
      </div>

      {runtimeOutcomePresentation?.tone === "error" ? (
        <p className="error-text">{runtimeOutcomePresentation.message}</p>
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
          setPendingIntent(null);
          applySettingsIntent(intent);
        }}
      />
    </main>
  );
}

// ---- Data Sources: provider health + per-source app-owned scheduling (3e) ----

function fromRoutes(routes: Partial<Record<ModelTask, TaskRoute>>): Partial<Record<ModelTask, DraftRoute>> {
  const out: Partial<Record<ModelTask, DraftRoute>> = {};
  for (const [key, route] of Object.entries(routes)) {
    const task = key as ModelTask;
    out[task] = {
      provider: route.provider,
      model: route.model,
      effort: route.effort,
      custom: route.custom,
    };
  }
  return out;
}
