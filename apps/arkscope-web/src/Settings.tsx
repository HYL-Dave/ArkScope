import { useEffect, useMemo, useRef, useState, type Dispatch, type SetStateAction } from "react";
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
import { AppRecordsSection } from "./settings/legacy/AppRecordsSection";
import type { SettingsAnchorId } from "./settings/settingsRegistry";

export {
  CredentialList,
  DiscoveryResultView,
  FixedTaskRuntimeSection,
  ModelRoutingSection,
  ProviderSection,
  ResearchRuntimeSection,
  SetupDisclosure,
};

type SettingsSection = SettingsAnchorId | "app_records" | "permissions";

const SETTINGS_SECTIONS: Array<{
  id: SettingsSection;
  title: string;
  description: string;
  enabled: boolean;
}> = [
  {
    id: "models",
    title: "Models",
    description: "任務路由、model id、effort。",
    enabled: true,
  },
  {
    id: "investor_profile",
    title: "投資人設定",
    description: "Investor Profile + 助手立場（opt-in 研究個人化；非投資建議）。",
    enabled: true,
  },
  {
    id: "providers",
    title: "Providers",
    description: "Anthropic / OpenAI key 狀態與可用模型來源。",
    enabled: true,
  },
  {
    id: "data_storage",
    title: "Data Storage",
    description: "價格、新聞、IV、基本面與財務快取狀態。",
    enabled: true,
  },
  {
    id: "news_storage",
    title: "News Data",
    description: "新聞資料量、最新文章、收集狀態與最近錯誤。",
    enabled: true,
  },
  {
    id: "macro_storage",
    title: "Macro / Calendar",
    description: "FRED 總經資料與經濟、財報、IPO 行事曆狀態。",
    enabled: true,
  },
  {
    id: "app_records",
    // One-time PG→local migration tool; migration is done (use_local_records=true) so this is
    // demoted out of the active nav. Component + backend route kept until the final PG-exit step.
    title: "App Records",
    description: "報告／記憶／查詢記錄已本地化（use_local_records=true）。一次性 PG→本地遷移工具，已完成。",
    enabled: false,
  },
  {
    id: "data_sources",
    title: "Data Sources",
    description: "資料源健康狀態 + 每來源獨立排程（app 直接發起，免 cron）。",
    enabled: true,
  },
  {
    id: "permissions",
    title: "Permissions",
    description: "profile_state_write / metered_spend 等權限門檻。",
    enabled: false,
  },
];

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
  const [section, setSection] = useState<SettingsSection>("models");
  const consumedNavigationSequenceRef = useRef(0);
  const [discovery, setDiscovery] = useState<DiscoveryState>({});
  const [testState, setTestState] = useState<TestState>({});

  useEffect(() => {
    if (!navigationRequest || navigationRequest.sequence <= consumedNavigationSequenceRef.current) return;
    consumedNavigationSequenceRef.current = navigationRequest.sequence;
    setSection(navigationRequest.target.section);
  }, [navigationRequest]);

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

  return (
    <main className="main settings-page">
      <div className="page-head">
        <div>
          <p className="eyebrow">Settings</p>
          <h1>模型與任務路由</h1>
          <p className="muted">
            為每個 AI 任務選擇 provider、model id 和 effort。Provider 頁可用目前 active key discovery/test 實際可用模型。
          </p>
        </div>
        <div className="page-head-actions">
          <button
            className="btn-ghost"
            onClick={() => void importRoutes()}
            disabled={saving || loading || !catalog}
            title="把設定檔（user_profile.local.yaml）裡的路由匯入成 DB 權威"
          >
            從設定檔匯入
          </button>
          <button
            className="btn-ghost"
            onClick={() => void exportRoutes()}
            disabled={saving || loading || !catalog}
            title="把 DB 路由寫回設定檔備份（鏡像 DB 狀態：有則寫入、無則清除）"
          >
            匯出到設定檔
          </button>
          <button
            className="btn-ghost"
            onClick={() => void save()}
            disabled={saving || loading || !catalog || routeSaveBlocks.length > 0}
            aria-describedby={routeSaveBlocks.length ? "route-save-blocked" : undefined}
          >
            {saving ? "儲存中…" : "儲存路由"}
          </button>
        </div>
      </div>

      {err && <p className="error-text">{err}</p>}
      {msg && <p className="ok-text">{msg}</p>}
      {routeSaveBlocks.length > 0 && (
        <p id="route-save-blocked" className="warn-text">
          本次變更尚未儲存：請先到 Providers 完成所選 provider 的登入。
        </p>
      )}

      {runtime && (
        <section className="settings-band">
          <div>
            <span className="label">Anthropic key</span>
            <strong>{runtime.anthropic.key_set ? "已設定" : "未設定"}</strong>
          </div>
          <div>
            <span className="label">OpenAI key</span>
            <strong>{runtime.openai.key_set ? "已設定" : "未設定"}</strong>
          </div>
          <div>
            <span className="label">目前合成</span>
            <strong>{runtime.card_synthesis.provider}/{runtime.card_synthesis.model}</strong>
          </div>
          <div>
            <span className="label">目前翻譯</span>
            <strong>{runtime.card_translation.provider}/{runtime.card_translation.model}</strong>
          </div>
        </section>
      )}

      {loading && <p className="muted">Loading model catalog…</p>}

      {catalog && (
        <div className="settings-layout">
          <aside className="settings-nav-card">
            <p className="eyebrow">設定分類</p>
            <div className="settings-section-list">
              {SETTINGS_SECTIONS.filter((item) => item.enabled).map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={`settings-section-button ${section === item.id ? "active" : ""}`}
                  onClick={() => setSection(item.id)}
                  title={item.title}
                >
                  <strong>{item.title}</strong>
                  <span>{item.description}</span>
                </button>
              ))}
            </div>
          </aside>

          <section className="settings-content">
            {section === "models" ? (
              <>
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
                  onOpenProviders={() => setSection("providers")}
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
                {runtime?.fixed_task_runtime && (
                  <FixedTaskRuntimeSection
                    settings={runtime.fixed_task_runtime}
                    saving={saving}
                    onSave={saveFixedTaskLimits}
                    onReset={resetFixedTaskLimits}
                  />
                )}
                {runtime?.research_runtime && (
                  <ResearchRuntimeSection
                    settings={runtime.research_runtime}
                    saving={saving}
                    onSave={saveRuntimeLimits}
                    onReset={resetRuntimeLimits}
                  />
                )}
              </>
            ) : section === "investor_profile" ? (
              <InvestorProfilePanel />
            ) : section === "providers" ? (
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
                  setSection("models");
                }}
              />
            ) : section === "data_storage" ? (
              <DataStorageSection />
            ) : section === "news_storage" ? (
              <NewsStorageSection />
            ) : section === "macro_storage" ? (
              <MacroStorageSection />
            ) : section === "app_records" ? (
              <AppRecordsSection />
            ) : section === "data_sources" ? (
              <DataSourcesSection />
            ) : null}
          </section>
        </div>
      )}
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
