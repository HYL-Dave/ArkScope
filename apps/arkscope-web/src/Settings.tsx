import { useCallback, useEffect, useMemo, useRef, useState, type Dispatch, type SetStateAction } from "react";
import { ChevronDown, ChevronRight, Menu } from "lucide-react";
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
import { MacroStorageSection } from "./settings/MacroStorageSection";
import {
  ModelRoutingSection,
  TASK_LABELS,
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
  SETTINGS_GROUPS,
  settingsGroupFor,
  type SettingsAnchorId,
  type SettingsGroupId,
} from "./settings/settingsRegistry";
import {
  readCollapsedSettingsGroups,
  writeCollapsedSettingsGroups,
} from "./settings/settingsPreferences";
import { Button, Drawer, IconButton, PageHeader, useShellOverlay } from "./ui";

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
  onRuntimeChanged: () => Promise<void>;
  navigationRequest?: NavigationRequest<Extract<NavigationTarget, { kind: "settings_section" }>> | null;
}

export function SettingsView({
  runtime,
  onRuntimeChanged,
  navigationRequest,
}: SettingsViewProps) {
  const [catalog, setCatalog] = useState<ModelCatalog | null>(null);
  const [draft, setDraft] = useState<Partial<Record<ModelTask, DraftRoute>>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [section, setSection] = useState<SettingsAnchorId>("models");
  const [collapsedGroups, setCollapsedGroups] = useState<ReadonlySet<SettingsGroupId>>(
    () => readCollapsedSettingsGroups(),
  );
  const [directoryQuery, setDirectoryQuery] = useState("");
  const [directoryOpen, setDirectoryOpen] = useState(false);
  const consumedNavigationSequenceRef = useRef(0);
  const directoryTriggerRef = useRef<HTMLButtonElement>(null);
  const revealFrameRef = useRef<number | null>(null);
  const [discovery, setDiscovery] = useState<DiscoveryState>({});
  const [testState, setTestState] = useState<TestState>({});
  const shellOverlay = useShellOverlay();

  const revealSection = useCallback((id: SettingsAnchorId) => {
    const groupId = settingsGroupFor(id).id;
    setCollapsedGroups((current) => {
      if (!current.has(groupId)) return current;
      const next = new Set(current);
      next.delete(groupId);
      writeCollapsedSettingsGroups(next);
      return next;
    });
    setSection(id);
    setDirectoryOpen(false);
    if (revealFrameRef.current != null) cancelAnimationFrame(revealFrameRef.current);
    revealFrameRef.current = requestAnimationFrame(() => {
      revealFrameRef.current = null;
      const anchor = document.querySelector<HTMLElement>(`[data-settings-anchor="${id}"]`);
      if (!anchor) return;
      anchor.scrollIntoView({ block: "start" });
      anchor.focus({ preventScroll: true });
    });
  }, []);

  const toggleGroup = useCallback((id: SettingsGroupId) => {
    setCollapsedGroups((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      writeCollapsedSettingsGroups(next);
      return next;
    });
  }, []);

  useEffect(() => () => {
    if (revealFrameRef.current != null) cancelAnimationFrame(revealFrameRef.current);
  }, []);

  useEffect(() => {
    if (!navigationRequest || navigationRequest.sequence <= consumedNavigationSequenceRef.current) return;
    consumedNavigationSequenceRef.current = navigationRequest.sequence;
    revealSection(navigationRequest.target.section);
  }, [navigationRequest, revealSection]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setErr(null);
      try {
        const data = await getModelCatalog();
        if (cancelled) return;
        setCatalog(data);
        setDraft(fromRoutes(data.routes));
      } catch (e) {
        if (!cancelled) setErr(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
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
    if (routeSaveBlocks.length) {
      setErr(
        routeSaveBlocks
          .map(({ task }) => `${TASK_LABELS[task]}：所選 provider 尚未設定登入`)
          .join("；"),
      );
      return;
    }
    setSaving(true);
    setErr(null);
    setMsg(null);
    try {
      const routes: Partial<Record<ModelTask, { provider: ModelProvider; model: string; effort: string }>> = {};
      for (const task of catalog.tasks) {
        const row = draft[task.id];
        if (!row || !row.model.trim()) throw new Error(`${TASK_LABELS[task.id]} 缺少 model id`);
        routes[task.id] = { provider: row.provider, model: row.model.trim(), effort: row.effort || "default" };
      }
      await saveModelRoutes(routes);
      const refreshed = await getModelCatalog();
      setCatalog(refreshed);
      setDraft(fromRoutes(refreshed.routes));
      setTestState({});
      await onRuntimeChanged();
      setMsg("模型路由已儲存到 profile DB（設定檔僅作 fallback／匯入匯出）。");
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  async function importRoutes() {
    setSaving(true);
    setErr(null);
    setMsg(null);
    try {
      const res = await importModelRoutes();
      const refreshed = await getModelCatalog();
      setCatalog(refreshed);
      setDraft(fromRoutes(refreshed.routes));
      setTestState({});
      await onRuntimeChanged();
      const imp = res.imported.length ? `匯入 ${res.imported.length}` : "無可匯入";
      const skip = res.skipped.length ? `，略過 ${res.skipped.length}（不完整／不一致）` : "";
      setMsg(`已從設定檔匯入路由到 DB：${imp}${skip}。`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  async function exportRoutes() {
    setSaving(true);
    setErr(null);
    setMsg(null);
    try {
      const res = await exportModelRoutes();
      // the clear branch can drop a task from profile→default, so refresh the badge/draft
      const refreshed = await getModelCatalog();
      setCatalog(refreshed);
      setDraft(fromRoutes(refreshed.routes));
      setTestState({});
      await onRuntimeChanged();
      const cleared = res.cleared.length ? `，清除 ${res.cleared.length} 個無 DB 路由的舊鍵` : "";
      setMsg(`已將 DB 路由寫回設定檔（${res.exported.length} 筆${cleared}）。`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  async function saveRuntimeLimits(
    body: Pick<ResearchRuntimeSettings, "max_tool_calls" | "session_timeout_s" | "per_tool_timeout_s">,
  ) {
    setSaving(true);
    setErr(null);
    setMsg(null);
    try {
      await saveResearchRuntime(body);
      await onRuntimeChanged();
      setMsg("AI 研究執行限制已儲存到 profile DB。");
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  async function resetRuntimeLimits() {
    setSaving(true);
    setErr(null);
    setMsg(null);
    try {
      await deleteResearchRuntime();
      await onRuntimeChanged();
      setMsg("AI 研究執行限制已重設為設定檔／內建預設。");
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
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
    setErr(null);
    setMsg(null);
    try {
      await saveFixedTaskRuntime(body);
      await onRuntimeChanged();
      setMsg("固定 AI 任務執行限制已儲存到 profile DB。");
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  async function resetFixedTaskLimits() {
    setSaving(true);
    setErr(null);
    setMsg(null);
    try {
      await deleteFixedTaskRuntime();
      await onRuntimeChanged();
      setMsg("固定 AI 任務執行限制已重設為環境變數／內建預設。");
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
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
      if (!catalog) return loading ? <p className="muted">Loading model catalog…</p> : null;
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
        />
      );
    }

    if (id === "models") {
      if (!catalog) return null;
      return (
        <>
          <div className="ui-action-row">
            <Button
              tone="primary"
              onClick={() => void save()}
              disabled={saving || loading || routeSaveBlocks.length > 0}
              aria-describedby={routeSaveBlocks.length ? "route-save-blocked" : undefined}
            >
              {saving ? "儲存中…" : "儲存路由"}
            </Button>
          </div>
          <ModelRoutingSection
            catalog={catalog}
            draft={draft}
            modelsByProvider={modelsByProvider}
            testState={testState}
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
            setErr(null);
            setMsg(null);
            try {
              await deleteModelRoute(task);
              const refreshed = await getModelCatalog();
              setCatalog(refreshed);
              setDraft(fromRoutes(refreshed.routes));
              invalidateTaskTest(task);
              await onRuntimeChanged();
              setMsg(`${TASK_LABELS[task]} 已重設為設定檔／內建預設。`);
            } catch (e) {
              setErr(e instanceof Error ? e.message : String(e));
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
        />
      ) : null;
    }

    if (id === "investor_profile") return <InvestorProfilePanel />;
    if (id === "data_sources") return <DataSourcesSection />;
    if (id === "data_storage") return <DataStorageSection />;
    if (id === "news_storage") return <NewsStorageSection />;
    return <MacroStorageSection />;
  }

  const directory = (
    <SettingsDirectory
      query={directoryQuery}
      currentTarget={section}
      onQueryChange={setDirectoryQuery}
      onSelect={revealSection}
    />
  );

  return (
    <main className="main settings-workspace" data-settings-overlay={String(shellOverlay)}>
      <PageHeader title="設定" />

      {err && <p className="error-text">{err}</p>}
      {msg && <p className="ok-text">{msg}</p>}
      {routeSaveBlocks.length > 0 && (
        <p id="route-save-blocked" className="warn-text">
          本次變更尚未儲存：請先到 Providers 完成所選 provider 的登入。
        </p>
      )}

      {shellOverlay ? (
        <Button
          ref={directoryTriggerRef}
          className="settings-directory-trigger"
          tone="secondary"
          size="compact"
          icon={<Menu size={16} />}
          onClick={() => setDirectoryOpen(true)}
        >
          設定目錄
        </Button>
      ) : null}

      <div className="settings-workspace-layout">
        {!shellOverlay ? <aside className="settings-directory-rail">{directory}</aside> : null}
        <div className="settings-workspace-groups">
          {SETTINGS_GROUPS.map((group) => {
            const expanded = !collapsedGroups.has(group.id);
            return (
              <section className="settings-workspace-group" key={group.id}>
                <header>
                  <h2>{group.title}</h2>
                  <IconButton
                    label={`${expanded ? "收合" : "展開"} ${group.title}`}
                    tone="ghost"
                    size="compact"
                    icon={expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                    aria-expanded={expanded}
                    onClick={() => toggleGroup(group.id)}
                  />
                </header>
                {expanded ? (
                  <div className="settings-workspace-group-body">
                    {group.sections.map((definition) => (
                      <SettingsSectionAnchor id={definition.id} key={definition.id}>
                        {renderSection(definition.id)}
                      </SettingsSectionAnchor>
                    ))}
                  </div>
                ) : null}
              </section>
            );
          })}
        </div>
      </div>

      <Drawer
        open={shellOverlay && directoryOpen}
        title="設定目錄"
        onClose={() => setDirectoryOpen(false)}
        returnFocusRef={directoryTriggerRef}
      >
        {directory}
      </Drawer>
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
