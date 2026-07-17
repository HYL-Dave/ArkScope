import { Fragment, useCallback, useEffect, useMemo, useRef, useState, type Dispatch, type ReactNode, type SetStateAction } from "react";
import {
  addCredential,
  importOAuthCredential,
  probeCredential,
  startOpenAIOAuth,
  openAIOAuthStatus,
  cancelOpenAIOAuth,
  completeOpenAIOAuthManual,
  type ProbeResponse,
  deleteCredential,
  discoverModels,
  getMarketDataStatus,
  deleteModelRoute,
  exportModelRoutes,
  getModelCatalog,
  getProvidersConfig,
  getProvidersHealth,
  getSAExtensionHealth,
  getSchedule,
  importProviderConfigField,
  importModelRoutes,
  deleteFixedTaskRuntime,
  deleteResearchRuntime,
  putProviderConfig,
  putSchedule,
  runScheduleNow,
  saveFixedTaskRuntime,
  saveResearchRuntime,
  saveModelRoutes,
  testProvider,
  getMacroStatus,
  getMacroSnapshot,
  getNewsStatus,
  getTradingDayCoverage,
  previewAppRecordsMigration,
  applyAppRecordsMigration,
  type AppRecordsMigrationPreview,
  type AppRecordsMigrationResult,
  testTaskModelAccess,
  updateCredential,
  type MarketDataStatus,
  type MacroSnapshot,
  type MacroSnapshotItem,
  type MacroStatus,
  type NewsStatus,
  type TradingDayCoverage,
  type TradingDayRow,
  type ProviderConfigEntry,
  type ProviderConfigField,
  type ProviderConfigSetupState,
  type ProviderHealth,
  type ProvidersHealthResponse,
  type SAExtensionHealthResponse,
  type ScheduleSourceState,
  type SyncMeta,
  type ModelCatalog,
  type EffectiveProviderModelEntry,
  type ModelDiscoveryResult,
  type ModelOption,
  type ModelProvider,
  type TaskModelTestResult,
  type ModelTask,
  type ProviderCredential,
  type FixedTaskRuntimeMap,
  type FixedTaskRuntimeSettings,
  type ResearchRuntimeSettings,
  type RuntimeConfig,
  type TaskRoute,
} from "./api";
import { runDiscoveryAndRefreshCatalog } from "./modelSelect";
import { effortOptionsForModel } from "./researchModels";
import {
  blockedRouteSaves,
  isTaskTestSnapshotCurrent,
  MODEL_UX_LABELS,
  providerContexts,
  type DraftRouteValue,
  type TaskTestSnapshot,
} from "./modelRoutingUx";
import {
  activeFirst,
  addApiKeyButtonLabel,
  addApiKeySuccessMessage,
  credentialAvailabilityText,
  credentialPill,
  defaultMakeActiveOnAdd,
  discoverButtonLabel,
  discoveryHeaderTitle,
  discoveryResultCredentialLabel,
  discoverySourceLabel,
  supportsCredentialExpiry,
  isoToDateInput,
  dateInputToIso,
} from "./credentialDisplay";
import { buildManualCompletion, pollOAuthStatus, probeDisplayLabel, probeDisplaySummary, probeRuntimeNote } from "./chatgptOAuth";
import { routeSourceBadge, routeIsOverridable } from "./modelRouteDisplay";
import { formatSystemTimestamp } from "./timeDisplay";
import {
  coverageStatusLabel,
  providerHealthStatusLabel,
  schedulerBodyBacklogPresentation,
  schedulerStateLabel,
} from "./marketDataDisplay";
import { displaySAExtensionSegments } from "./saExtensionHealthDisplay";
import { InvestorProfilePanel } from "./InvestorProfilePanel";
import { SourceRunProgress } from "./SourceRunProgress";
import {
  durableScheduleCommonState,
  providerCommonState,
  saSegmentCommonState,
  scheduleSkipCommonState,
} from "./dataSourcesPresentation";
import {
  dataSourceScheduleLifecycleChanged,
  dataSourceSchedulePollMs,
  type DataSourceScheduleMap,
} from "./dataSourceSchedulePolling";
import { StatusBadge } from "./ui";
import type {
  NavigationRequest,
  NavigationTarget,
} from "./shell/navigation";

const TASK_LABELS: Record<ModelTask, string> = {
  card_synthesis: "AI 卡片生成",
  card_translation: "卡片翻譯",
  ai_research: "AI 研究",
};

type SettingsSection =
  | "models"
  | "investor_profile"
  | "providers"
  | "data_storage"
  | "news_storage"
  | "macro_storage"
  | "app_records"
  | "data_sources"
  | "permissions";

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

interface DraftRoute extends DraftRouteValue {}

type DiscoveryState = Partial<Record<ModelProvider, {
  loading: boolean;
  result: ModelDiscoveryResult | null;
  credentialId: string | null;
}>>;

type TestState = Partial<Record<ModelTask, {
  loading: boolean;
  result: TaskModelTestResult | null;
  snapshot: TaskTestSnapshot | null;
  stale: boolean;
}>>;

type CredentialMetadataDraft = {
  account_label?: string;
  expires_at?: string;
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

function syncLine(status: MarketDataStatus): string {
  const fmt = (m: SyncMeta | null) => {
    if (!m) return "—";
    if (m.last_error) return `錯誤（${m.last_error.slice(0, 40)}）`;
    const ts = formatSystemTimestamp(m.last_success);
    return `+${m.rows_added.toLocaleString()} @ ${ts}`;
  };
  const s = status.sync;
  if (!s.prices && !s.news && !s.iv && !s.fundamentals) return "尚未增量更新";
  return `價格 ${fmt(s.prices)} · 新聞 ${fmt(s.news)} · IV ${fmt(s.iv)} · 基本面 ${fmt(s.fundamentals)}`;
}

function DataStorageSection() {
  const [status, setStatus] = useState<MarketDataStatus | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setStatus(await getMarketDataStatus());
      setErr(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
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

  return (
    <div>
      <div className="settings-section-head">
        <div>
          <h2>市場資料 · Market Data</h2>
          <p className="muted tiny">
            顯示價格、新聞、隱含波動率、基本面與財務快取的資料量、最新時間及最近更新。
            資料抓取由 Data Sources 管理。
          </p>
        </div>
        <button className="btn-ghost" onClick={() => void load()}>↻ 重新整理</button>
      </div>

      {err && <div className="errorbox"><p className="muted">{err}</p></div>}

      {!status ? (
        <p className="muted">載入中…</p>
      ) : (
        <div className="settings-panel">
          <dl className="ds-kv">
            <dt>市場資料</dt>
            <dd>{exists ? "可用" : "尚無資料"}</dd>
            <dt>價格</dt>
            <dd>{exists ? `${pr!.row_count.toLocaleString()} 列 · ${pr!.ticker_count} 檔 · 最新 ${pr!.latest_datetime ?? "—"}` : "—"}</dd>
            <dt>新聞</dt>
            <dd>{exists ? `${nw!.row_count.toLocaleString()} 篇 · ${nw!.source_count} 來源 · 最新 ${nw!.latest_published ?? "—"}` : "—"}</dd>
            <dt>IV</dt>
            <dd>{exists ? `${iv!.row_count.toLocaleString()} 列 · ${iv!.ticker_count} 檔 · 最新 ${iv!.latest_date ?? "—"}` : "—"}</dd>
            <dt>基本面</dt>
            <dd>{exists ? `${fd!.row_count.toLocaleString()} 列 · ${fd!.ticker_count} 檔 · 最新 ${fd!.latest_date ?? "—"}` : "—"}</dd>
            <dt>財務快取</dt>
            <dd>
              {exists
                ? `${fc!.row_count.toLocaleString()} 列（有效 ${fc!.valid_count} · 過期 ${fc!.expired_count}）· 最新抓取 ${formatSystemTimestamp(fc!.latest_fetched_at)}`
                : "—"}
            </dd>
            <dt>最近增量更新</dt>
            <dd>{syncLine(status)}</dd>
          </dl>
        </div>
      )}

      <TradingDayCoveragePanel />
    </div>
  );
}

function NewsStorageSection() {
  const [status, setStatus] = useState<NewsStatus | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setStatus(await getNewsStatus());
      setErr(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const sync = status?.sync;
  const providerErrors = sync
    ? Object.entries(sync.providers)
        .filter(([, provider]) => provider.last_error)
        .map(([provider, state]) => `${provider}: ${state.last_error}`)
        .join("；")
    : "";

  return (
    <div>
      <div className="settings-section-head">
        <div>
          <h2>新聞資料狀態 · News Data</h2>
          <p className="muted tiny">
            顯示新聞資料量、最新文章、最近收集時間與錯誤。各來源排程與手動執行由 Data Sources 管理。
          </p>
        </div>
        <button className="btn-ghost" onClick={() => void load()}>↻ 重新整理</button>
      </div>

      {err && <div className="errorbox"><p className="muted">{err}</p></div>}

      {!status ? (
        <p className="muted">載入中…</p>
      ) : (
        <div className="settings-panel">
          <dl className="ds-kv">
            <dt>新聞資料</dt>
            <dd>
              {status.exists
                ? `${status.news.row_count.toLocaleString()} 篇 · ${status.news.source_count} 來源 · 最新 ${status.news.latest_published ?? "—"}`
                : "尚無資料"}
            </dd>
            <dt>最近收集成功</dt>
            <dd>{formatSystemTimestamp(sync?.last_success)}</dd>
            <dt>最近收集嘗試</dt>
            <dd>{formatSystemTimestamp(sync?.last_attempt)}</dd>
            <dt>收集狀態</dt>
            <dd>{sync?.status ?? "尚未執行"}</dd>
            <dt>最近錯誤</dt>
            <dd className={providerErrors ? "refresh-err" : undefined}>{providerErrors || sync?.last_error || "—"}</dd>
          </dl>

        </div>
      )}
    </div>
  );
}

// ---- 交易日 / 價格覆蓋唯讀診斷 (Slice B) — read-only; renders backend coverage_status ----

function coverageToneColor(tone: "ok" | "warn" | "muted" | "bad"): string {
  return tone === "ok" ? "var(--ok)" : tone === "bad" ? "var(--bad)"
    : tone === "warn" ? "var(--warn, #b8860b)" : "var(--muted, #888)";
}

function TradingDayCoveragePanel() {
  const [cov, setCov] = useState<TradingDayCoverage | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [lookback, setLookback] = useState(10);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      setCov(await getTradingDayCoverage(lookback, "15min"));
      setErr(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, [lookback]);
  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div style={{ marginTop: 24, borderTop: "1px solid var(--border, #333)", paddingTop: 16 }}>
      <div className="settings-section-head">
        <div>
          <h2>交易日 / 價格覆蓋 · Trading-day coverage</h2>
          <p className="muted tiny">
            最近 {lookback} 天的 15min 價格覆蓋。每列以 coverage_status 為準：
            覆蓋完整 / 部分覆蓋 / 疑似不足 / 缺資料 / 盤中 / 週末假日。點開可看缺漏與 partial 標的、以及 provider 錯誤。
            <strong>唯讀診斷，不會自動補抓</strong>；full/partial/missing 僅作為「相對當天覆蓋最佳標的」的 drill-down。
          </p>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <label className="muted tiny">
            天數{" "}
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
          <button className="btn-ghost" onClick={() => void load()} disabled={busy}>↻ 重新整理</button>
        </div>
      </div>

      {err && <div className="errorbox"><p className="muted">{err}</p></div>}

      {!cov ? (
        <p className="muted">載入中…</p>
      ) : (
        <div className="settings-panel">
          <p className="muted tiny">
            universe {cov.universe_count} 檔 · interval {cov.interval} · 產生於 {shortTs(cov.generated_at_et)}
          </p>
          <table className="ds-table" style={{ width: "100%", marginTop: 8 }}>
            <thead>
              <tr>
                <th style={{ textAlign: "left" }}>日期</th>
                <th style={{ textAlign: "left" }}>狀態</th>
                <th style={{ textAlign: "right" }}>最多 bars</th>
                <th style={{ textAlign: "right" }}>覆蓋</th>
                <th style={{ textAlign: "right" }}>缺</th>
                <th style={{ textAlign: "right" }}>partial</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {cov.days.map((d) => {
                const cs = coverageStatusLabel(d);
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
  row, label, tone, open, drillable, onToggle, providerErrors,
}: {
  row: TradingDayRow;
  label: string;
  tone: "ok" | "warn" | "muted" | "bad";
  open: boolean;
  drillable: boolean;
  onToggle: () => void;
  providerErrors: TradingDayCoverage["provider_errors"];
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
                缺（{row.missing_tickers.length}）：{row.missing_tickers.join(", ")}
              </p>
            )}
            {row.partial_tickers.length > 0 && (
              <p className="tiny" style={{ margin: "0 0 4px" }}>
                partial：{row.partial_tickers.map((p) => `${p.ticker}(${p.bars})`).join(", ")}
              </p>
            )}
            {relErrors.length > 0 && (
              <p className="tiny refresh-err" style={{ margin: 0 }}>
                provider 錯誤：{relErrors.map((e) => `${e.ticker}: ${e.last_error}`).join("；")}
              </p>
            )}
          </td>
        </tr>
      )}
    </>
  );
}

const MACRO_TABLE_LABELS: Array<[string, string]> = [
  ["macro_series", "FRED 序列"],
  ["macro_observations", "FRED 觀測值"],
  ["macro_release_dates", "發布排程"],
  ["cal_economic_events", "經濟行事曆"],
  ["cal_earnings_events", "財報行事曆"],
  ["cal_ipo_events", "IPO 行事曆"],
];

function MacroStorageSection() {
  const [status, setStatus] = useState<MacroStatus | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setStatus(await getMacroStatus());
      setErr(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);

  const exists = status?.exists ?? false;
  const tables = status?.tables ?? {};
  const totalObs = (tables.macro_observations?.row_count ?? 0).toLocaleString();
  const seriesCount = (tables.macro_series?.row_count ?? 0).toLocaleString();

  return (
    <div>
      <div className="settings-section-head">
        <div>
          <h2>總經與行事曆 · Macro / Calendar</h2>
          <p className="muted tiny">
            顯示 FRED 序列與觀測值，以及經濟、財報與 IPO 行事曆資料。
            經濟行事曆需要 Finnhub 付費方案；未取得授權時會維持不可用。
          </p>
        </div>
        <button className="btn-ghost" onClick={() => void load()}>↻ 重新整理</button>
      </div>

      {err && <div className="errorbox"><p className="muted">{err}</p></div>}

      {!status ? (
        <p className="muted">載入中…</p>
      ) : (
        <div className="settings-panel">
          <dl className="ds-kv">
            <dt>總經資料</dt>
            <dd>{exists ? `可用 · ${seriesCount} 序列 · ${totalObs} 觀測值` : "尚無資料"}</dd>
            {MACRO_TABLE_LABELS.map(([key, label]) => {
              const t = tables[key];
              return (
                <FragmentKV
                  key={key}
                  label={label}
                  value={
                    exists && t
                      ? `${t.row_count.toLocaleString()} 列 · 最新抓取 ${formatSystemTimestamp(t.last_fetched_at)}`
                      : "—"
                  }
                />
              );
            })}
          </dl>
        </div>
      )}
    </div>
  );
}

// A <dt>/<dd> pair (a fragment can't carry a key cleanly inside .map for the dl).
function FragmentKV({ label, value }: { label: string; value: string }) {
  return (
    <>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </>
  );
}

// ---- App Records: PG→local migration (PG-exit 1c) — dry-run preview then explicit apply ----

const APP_RECORD_LABELS: Array<[string, string]> = [
  ["research_reports", "報告"],
  ["agent_memories", "記憶"],
  ["agent_queries", "查詢記錄"],
];

function AppRecordsSection() {
  const [preview, setPreview] = useState<AppRecordsMigrationPreview | null>(null);
  const [applied, setApplied] = useState<AppRecordsMigrationResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState<"" | "preview" | "apply">("");

  async function runPreview() {
    if (busy) return;
    setBusy("preview"); setErr(null); setApplied(null);
    try {
      setPreview(await previewAppRecordsMigration());
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy("");
    }
  }

  async function runApply() {
    if (busy || !preview?.would_apply) return;
    setBusy("apply"); setErr(null);
    try {
      setApplied(await applyAppRecordsMigration());
      setPreview(await previewAppRecordsMigration());  // refresh (now all idempotent)
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy("");
    }
  }

  const totalConflicts = preview
    ? Object.values(preview.tables).reduce((n, t) => n + t.conflicts.length, 0) : 0;
  const totalMissing = preview
    ? Object.values(preview.tables).reduce((n, t) => n + t.missing_files.length, 0) : 0;
  const totalToInsert = preview
    ? Object.values(preview.tables).reduce((n, t) => n + t.to_insert.length, 0) : 0;
  const alreadyLocalized = !!preview && preview.would_apply && totalToInsert === 0;

  return (
    <div>
      <div className="settings-section-head">
        <div>
          <h2>App Records 遷移 · reports / memories / queries</h2>
          <p className="muted tiny">
            把報告、記憶、查詢記錄從 PostgreSQL 一次性遷移到本地 profile_state.db。這些是不可再生的使用者/agent 資料。
            遷移<strong>保留原始 id</strong>（卡片→報告連結不會斷）、<strong>先備份本地 DB</strong>、衝突（同 id 不同內容）會拒絕不寫。
            先按「預覽」(dry-run，不寫入)，確認沒有衝突再「執行遷移」。遷移成功後才在他處啟用 use_local_records（本面板不提供切換）。
            需要 PG 可連線。
          </p>
        </div>
        <button className="btn-ghost" onClick={() => void runPreview()} disabled={!!busy}>
          {busy === "preview" ? "預覽中…" : "↻ 預覽 (dry-run)"}
        </button>
      </div>

      {err && <div className="errorbox"><p className="muted">{err}</p></div>}

      {!preview ? (
        <p className="muted">按「預覽」檢視 PG 與本地的差異（不會寫入）。</p>
      ) : (
        <div className="settings-panel">
          <table className="ds-table" style={{ width: "100%" }}>
            <thead>
              <tr>
                <th style={{ textAlign: "left" }}>表</th>
                <th style={{ textAlign: "right" }}>PG</th>
                <th style={{ textAlign: "right" }}>本地</th>
                <th style={{ textAlign: "right" }}>待遷移</th>
                <th style={{ textAlign: "right" }}>已存在</th>
                <th style={{ textAlign: "right" }}>衝突</th>
                <th style={{ textAlign: "right" }}>缺檔</th>
              </tr>
            </thead>
            <tbody>
              {APP_RECORD_LABELS.map(([key, label]) => {
                const t = preview.tables[key];
                if (!t) return null;
                return (
                  <tr key={key}>
                    <td>{label}</td>
                    <td style={{ textAlign: "right" }}>{t.pg_count}</td>
                    <td style={{ textAlign: "right" }}>{t.local_count}</td>
                    <td style={{ textAlign: "right" }}>{t.to_insert.length}</td>
                    <td style={{ textAlign: "right" }}>{t.idempotent_skip.length}</td>
                    <td style={{ textAlign: "right", color: t.conflicts.length ? "var(--bad)" : undefined }}>
                      {t.conflicts.length}
                    </td>
                    <td style={{ textAlign: "right", color: t.missing_files.length ? "var(--warn, #b8860b)" : undefined }}>
                      {t.missing_files.length}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {alreadyLocalized && (
            <p className="tiny" style={{ marginTop: 8, color: "var(--ok)" }}>
              ✓ 已本地化：PG 與本地一致，無待遷移項目（reports/memories/queries 走 profile_state.db）。
            </p>
          )}
          {totalConflicts > 0 && (
            <p className="tiny refresh-err" style={{ marginTop: 8 }}>
              ✗ 有 {totalConflicts} 筆同 id 不同內容的衝突 — 遷移會被拒絕（不寫入）。請先排查再重試。
            </p>
          )}
          {totalMissing > 0 && (
            <p className="muted tiny" style={{ marginTop: 8 }}>
              ⚠ {totalMissing} 筆 file_path 找不到對應檔案（metadata 仍會遷移）。
            </p>
          )}

          <div className="settings-actions" style={{ marginTop: 12 }}>
            <button
              className="btn-ghost"
              onClick={() => void runApply()}
              disabled={!!busy || !preview.would_apply || totalToInsert === 0}
            >
              {busy === "apply" ? "遷移中…"
                : alreadyLocalized ? "已全部遷移"
                : `執行遷移 (apply) · ${totalToInsert} 筆`}
            </button>
            {!preview.would_apply && <span className="muted tiny">（有衝突，無法遷移）</span>}
          </div>

          {applied && (
            <p className="tiny" style={{ marginTop: 8, color: "var(--ok)" }}>
              ✓ 遷移完成：{APP_RECORD_LABELS.map(([k, l]) => {
                const r = applied.tables[k];
                return r ? `${l} +${r.inserted}（略過 ${r.skipped}）` : null;
              }).filter(Boolean).join("、")}。備份：{applied.backup ?? "—"}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

// ---- Data Sources: provider health + per-source app-owned scheduling (3e) ----

function providerConfigSourceLabel(source: string): string {
  if (source === "app") return "App";
  if (source === "env") return "環境變數";
  if (source === "config/.env") return "config/.env";
  if (source === "missing") return "未設定";
  return source;
}

function shortTs(iso: string | null | undefined): string {
  return formatSystemTimestamp(iso);
}

function compactMessage(value: string, max = 88): string {
  const text = value.replace(/\s+/g, " ").trim();
  if (text.length <= max) return text;
  return `${text.slice(0, max - 1)}…`;
}

function shortDate(iso: string | null | undefined): string {
  return iso ? iso.slice(0, 10) : "—";
}

function formatCount(value: number | null | undefined): string {
  return typeof value === "number" && Number.isFinite(value)
    ? value.toLocaleString("en-US")
    : "—";
}

function formatMacroValue(item: MacroSnapshotItem): string {
  if (item.value == null || !Number.isFinite(item.value)) return "—";
  const value = item.value.toLocaleString("en-US", { maximumFractionDigits: 4 });
  return item.units ? `${value} ${item.units}` : value;
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

function fredProviderDetail(p: ProviderHealth): string | null {
  if (p.id !== "fred") return null;
  const snap = fredSnapshotFromSignals(p.signals);
  const auto = boolSignal(p.signals, "auto_refresh_enabled");
  const parts: string[] = [];
  if (snap?.available) {
    parts.push(
      `資料快照可用：${formatCount(snap.series_count)} 序列 · ${formatCount(snap.observation_count)} 觀測值`,
    );
  } else {
    parts.push("尚無資料");
  }
  if (snap?.latest_fetched_at) parts.push(`最後抓取 ${shortDate(snap.latest_fetched_at)}`);
  parts.push(auto ? "自動刷新已啟用" : "自動刷新未啟用");
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
): { preview: boolean; text: string } {
  const s = draft.trim();
  const base = /^\d+$/.test(s) ? Number(s) : null;
  const text = domains
    .map((d) => `${d.label}=${base !== null ? base + d.offset : d.effective_id ?? "？"}`)
    .join("、");
  return { preview: base !== null, text };
}

function ProviderHealthState({ provider }: { provider: ProviderHealth }) {
  const state = providerCommonState(provider.status);
  return state === null
    ? <span className="muted tiny">{providerHealthStatusLabel(provider)}</span>
    : <StatusBadge state={state} label={providerHealthStatusLabel(provider)} />;
}

function DataSourcesSection() {
  const [schedule, setSchedule] = useState<Record<string, ScheduleSourceState> | null>(null);
  const [health, setHealth] = useState<ProvidersHealthResponse | null>(null);
  const [macroSnapshot, setMacroSnapshot] = useState<MacroSnapshot | null>(null);
  const [saExtensionHealth, setSaExtensionHealth] = useState<SAExtensionHealthResponse | null>(null);
  const [cfg, setCfg] = useState<Record<string, ProviderConfigEntry> | null>(null);
  const [cfgSetup, setCfgSetup] = useState<ProviderConfigSetupState | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState<string>(""); // source id with an in-flight mutation
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [keyDrafts, setKeyDrafts] = useState<Record<string, string>>({}); // "provider.field"
  const [testResults, setTestResults] = useState<Record<string, string>>({});
  const scheduleRef = useRef<DataSourceScheduleMap | null>(null);
  const scheduleRequestSequenceRef = useRef(0);
  const acceptedScheduleSequenceRef = useRef(0);
  const schedulePollInFlightRef = useRef<Promise<void> | null>(null);
  const dataSourcesMountedRef = useRef(true);

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
    const [rs, rh, rc, rm] = await Promise.allSettled([
      getSchedule(), getProvidersHealth(), getProvidersConfig(), getMacroSnapshot()]);
    if (!dataSourcesMountedRef.current) return;
    if (rs.status === "fulfilled") acceptSchedule(rs.value.sources, scheduleSequence);
    if (rh.status === "fulfilled") setHealth(rh.value);
    if (rc.status === "fulfilled") {
      setCfg(rc.value.providers);
      setCfgSetup(rc.value.setup);
    }
    if (rm.status === "fulfilled") setMacroSnapshot(rm.value);
    const bad = [rs, rh, rc, rm].filter((r): r is PromiseRejectedResult => r.status === "rejected");
    setErr(bad.length
      ? bad.map((r) => (r.reason instanceof Error ? r.reason.message : String(r.reason))).join("；")
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
      setErr(e instanceof Error ? e.message : String(e));
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
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy("");
    }
  }

  async function runNow(source: string) {
    if (busy) return;
    setBusy(source);
    try {
      const r = await runScheduleNow(source);
      if (r.status === "skipped") setErr(`${source}: ${r.reason ?? "已在執行"}`);
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
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
      setErr(e instanceof Error ? e.message : String(e));
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
    const confirmGuarded =
      fieldMeta?.guarded && value !== null
        ? window.confirm(fieldMeta.guard_reason ?? "此設定需要確認後才會變更。")
        : true;
    if (!confirmGuarded) return;
    setBusy(`${provider}.${field}`);
    try {
      await putProviderConfig(
        provider,
        { [field]: value },
        fieldMeta?.guarded ? { [field]: true } : undefined,
      );
      setKeyDrafts((d) => ({ ...d, [`${provider}.${field}`]: "" }));
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy("");
    }
  }

  async function runTest(provider: string) {
    if (busy) return;
    setBusy(`test.${provider}`);
    setTestResults((t) => ({ ...t, [provider]: "測試中…" }));
    try {
      const r = await testProvider(provider);
      setTestResults((t) => ({
        ...t,
        [provider]:
          r.ok === true
            ? `✓ ${r.detail}${r.latency_ms != null ? ` · ${r.latency_ms}ms` : ""}`
            : r.ok === false
              ? `✗ ${r.detail}`
              : `— ${r.detail}`,
      }));
    } catch (e) {
      setTestResults((t) => ({ ...t, [provider]: `✗ ${e instanceof Error ? e.message : String(e)}` }));
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
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy("");
    }
  }

  function renderProviderConfigField(pid: string, f: ProviderConfigField) {
    const draftKey = `${pid}.${f.field}`;
    const draft = keyDrafts[draftKey] ?? "";
    const envControlled = f.env_var === "IBKR_CLIENT_ID" && f.effective_source === "env";
    const chips = f.env_var === "IBKR_CLIENT_ID" && (f.client_id_domains?.length ?? 0) > 0
      ? ibkrClientIdChips(f.client_id_domains!, envControlled ? "" : draft)
      : null;
    const caption = envControlled
      ? "各域用戶端 ID（環境變數控制中）："
      : chips?.preview
        ? "存檔後 ID："
        : "各域用戶端 ID：";

    return (
      <div className="provider-config-field" key={draftKey}>
        <div className="provider-config-field-label">{f.label}</div>
        <div className="provider-config-field-current">
          {f.effective_source === "missing"
            ? <span className="ds-chip ds-missing_key">未設定</span>
            : <>
                <span className="mono">{f.app_value_set ? f.app_value_masked : "（外部）"}</span>
                {f.defaulted && <span className="muted tiny"> · 預設</span>}
                <span className="muted tiny">（{providerConfigSourceLabel(f.effective_source)}）</span>
                {f.needs_import && (
                  <button className="btn-ghost tiny"
                    disabled={busy === `import.${pid}.${f.field}`}
                    onClick={() => void importField(pid, f.field, f.import_source)}>
                    匯入
                  </button>
                )}
                {f.needs_import && <span className="muted tiny">建議匯入</span>}
              </>}
        </div>
        <div className="provider-config-field-edit">
          <input
            className="ds-interval ds-keyinput"
            type={f.secret ? "password" : "text"}
            placeholder={f.secret ? "貼上金鑰…" : f.label}
            value={draft}
            disabled={busy === draftKey}
            onChange={(e) => setKeyDrafts((d) => ({ ...d, [draftKey]: e.target.value }))}
            onKeyDown={(e) => {
              if (e.key === "Enter" && draft) void saveField(pid, f.field, draft, f);
            }}
          />
          {draft && (
            <button className="btn-ghost tiny" onClick={() => void saveField(pid, f.field, draft, f)}>
              儲存
            </button>
          )}
          {f.app_value_set && (
            <button className="btn-ghost tiny" onClick={() => void saveField(pid, f.field, null, f)}>
              清除
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
    if (row.status === "failed") return `✗ ${ts}${row.error ? `（${String(row.error).slice(0, 60)}）` : ""}`;
    if (row.status === "running") return "執行中…";
    return row.status ?? "—";
  }

  function renderLastRun(source: string, s: ScheduleSourceState) {
    const details: Array<{ label: string; value: string; tone?: "bad" | "warn" }> = [];
    const skippedReason = s.last_result?.status === "skipped" ? s.last_result.reason ?? "已在執行" : null;
    const alreadyRunningSkip = skippedReason?.includes("already running") ?? false;
    const skippedSummary = alreadyRunningSkip ? "已有執行中" : compactMessage(skippedReason ?? "");
    const skipState = scheduleSkipCommonState(skippedReason);
    const historyState = durableScheduleCommonState(s);
    const durableSkipped = s.durable_state?.last_status === "skipped";
    if (skippedReason) {
      details.push({
        label: alreadyRunningSkip ? "新觸發略過" : "跳過原因",
        value: skippedReason,
        tone: "warn",
      });
    }
    const ss = schedulerStateLabel(s.durable_state ?? null);
    const bodyBacklog = schedulerBodyBacklogPresentation(s.durable_state ?? null);
    const durableError = s.durable_state?.last_status === "failed" ? s.durable_state.last_error : null;
    if (durableError) details.push({ label: "失敗訊息", value: durableError, tone: "bad" });

    return (
      <div className="ds-last-run">
        <div className="ds-last-run-summary">
          <span>{jobOutcome(s.job_name)}</span>
          {skippedReason && (
            skipState === null ? (
              <span className="muted tiny" title={skippedReason}>
                已跳過：{skippedSummary}
              </span>
            ) : (
              <StatusBadge state={skipState} label="新觸發已略過" />
            )
          )}
          {historyState !== null ? (
            <StatusBadge
              state={historyState}
              label={`${ss.label}${durableError ? `：${compactMessage(durableError)}` : ""}`}
            />
          ) : durableSkipped && !skippedReason ? (
            <span className="muted tiny">{ss.label}</span>
          ) : null}
          {ss.needsContinue && (
            <button
              className="btn-ghost"
              disabled={!!busy || s.running}
              onClick={() => void runNow(source)}
              title="手動補抓上次部分完成剩餘的標的"
            >
              補抓
            </button>
          )}
        </div>
        {bodyBacklog && (
          <div className={`tiny ${bodyBacklog.tone === "warn" ? "refresh-err" : "muted"}`}>
            {bodyBacklog.label}
            {bodyBacklog.earliestNextRetryAt
              ? ` · 最早 ${formatSystemTimestamp(bodyBacklog.earliestNextRetryAt)}`
              : ""}
          </div>
        )}
        {details.length > 0 && (
          <details className="ds-last-run-details">
            <summary>完整訊息</summary>
            {details.map((d) => (
              <div className={`ds-last-run-detail ${d.tone === "bad" ? "refresh-err" : ""}`} key={d.label}>
                <span className="muted tiny">{d.label}</span>
                <pre>{d.value}</pre>
              </div>
            ))}
          </details>
        )}
      </div>
    );
  }

  return (
    <div>
      <div className="settings-section-head">
        <div>
          <h2>資料來源 · Data Sources</h2>
          <p className="muted tiny">
            集中檢視各資料來源的健康狀態、連線設定、排程與手動執行。
            每個來源可獨立設定；IBKR 工作會共用 Gateway 鎖以避免重疊。
          </p>
        </div>
        <button className="btn-ghost" onClick={() => void load()} disabled={!!busy}>
          ↻ 重新整理{anyRunning ? "（執行中，自動更新）" : ""}
        </button>
      </div>

      {err && <div className="errorbox"><p className="muted">{err}</p></div>}

      <div className="settings-panel">
        <h4 className="detail-section">Provider 健康</h4>
        {!health ? (
          <p className="muted tiny">loading…</p>
        ) : (
          <div className="settings-table-scroll" data-testid="provider-health-scroll">
            <table className="data-table settings-provider-health-table">
              <thead>
                <tr><th>Provider</th><th>狀態</th><th>金鑰</th><th>最近成功</th><th>最近錯誤</th></tr>
              </thead>
              <tbody>
                {health.providers.map((p) => (
                  <tr key={p.id}>
                    <td className="settings-wrap-text">
                      {p.label}
                      {fredProviderDetail(p) && (
                        <div className="muted tiny">{fredProviderDetail(p)}</div>
                      )}
                    </td>
                    <td><ProviderHealthState provider={p} /></td>
                    <td>
                      {p.key_source === "not_required" ? "免金鑰" : p.key_source}
                      {p.key_import_suggested && <span className="muted tiny"> · 建議匯入</span>}
                    </td>
                    <td>{shortTs(p.last_success_at)}</td>
                    <td className="muted settings-wrap-text">{p.last_error ? p.last_error.slice(0, 60) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="settings-panel" style={{ marginTop: 16 }}>
        <div className="settings-panel-head">
          <div>
            <h4 className="detail-section">SA Extension 健康</h4>
            <p className="muted tiny">
              檢查瀏覽器 extension、native host、sidecar 回報與資料接收狀態。
            </p>
          </div>
          <button
            className="btn-ghost"
            disabled={busy === "sa.extension-health"}
            onClick={() => void reloadSAExtensionHealth()}
          >
            重新檢查
          </button>
        </div>
        {!saExtensionHealth ? (
          <p className="muted tiny">loading…</p>
        ) : (
          <>
            <p className="muted tiny">
              {saExtensionHealth.ok ? "鏈路可用" : "鏈路有中斷"} · {shortTs(saExtensionHealth.generated_at)}
            </p>
            <div className="settings-table-scroll" data-testid="sa-health-scroll">
              <table className="data-table settings-sa-health-table">
                <thead>
                  <tr><th>段落</th><th>狀態</th><th>細節</th></tr>
                </thead>
                <tbody>
                  {displaySAExtensionSegments(saExtensionHealth.segments).map((row) => (
                    <tr key={row.key}>
                      <td>{row.label}</td>
                      <td>
                        <StatusBadge
                          state={saSegmentCommonState(row.tone)}
                          label={row.tone === "ok" ? "正常" : row.tone === "warn" ? "注意" : "失敗"}
                        />
                      </td>
                      <td className="muted settings-wrap-text">{row.detail}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>

      <div className="settings-panel" style={{ marginTop: 16 }}>
        <h4 className="detail-section">FRED 資料快照</h4>
        {!macroSnapshot ? (
          <p className="muted tiny">loading…</p>
        ) : (
          <>
            <p className="muted tiny">
              {macroSnapshot.available
                ? `${formatCount(macroSnapshot.series_count)} 序列 · ${formatCount(macroSnapshot.observation_count)} 觀測值 · 最後抓取 ${shortDate(macroSnapshot.latest_fetched_at)} · 自動刷新${macroSnapshot.auto_refresh_enabled ? "開啟" : "關閉"}`
                : `尚無資料 · 自動刷新${macroSnapshot.auto_refresh_enabled ? "開啟" : "關閉"}`}
            </p>
            {macroSnapshot.items.length > 0 ? (
              <div className="settings-table-scroll" data-testid="fred-snapshot-scroll">
                <table className="data-table settings-fred-table">
                  <thead>
                    <tr><th>指標</th><th>值</th><th>觀測日</th><th>抓取時間</th></tr>
                  </thead>
                  <tbody>
                    {macroSnapshot.items.slice(0, 11).map((item) => (
                      <tr key={item.series_id}>
                        <td className="settings-wrap-text">
                          {item.label}
                          <div className="muted tiny">{item.series_id}{item.title ? ` · ${item.title}` : ""}</div>
                        </td>
                        <td>{formatMacroValue(item)}</td>
                        <td>{shortDate(item.observation_date)}</td>
                        <td>{shortDate(item.fetched_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="muted tiny">尚無可顯示的 FRED 觀測值。</p>
            )}
          </>
        )}
      </div>

      <div className="settings-panel" style={{ marginTop: 16 }}>
        <h4 className="detail-section">連線與金鑰</h4>
        <p className="muted tiny">
          來源標示會說明每個值由 App、環境變數或 config/.env 管理。
          App 內儲存的設定會立即生效；敏感值只顯示遮罩內容。
        </p>
        {cfgSetup?.required && (
          <div className="errorbox">
            <p className="muted">
              Provider 設定需要修復：{cfgSetup.reason ?? cfgSetup.code ?? "profile DB unavailable"}
            </p>
          </div>
        )}
        {!cfg ? (
          <p className="muted tiny">loading…</p>
        ) : (
          <div className="settings-table-scroll" data-testid="provider-config-scroll">
          <table className="data-table ds-config settings-provider-config-table">
            <thead>
              <tr><th>Provider</th><th>欄位</th><th>目前值（來源）</th><th>設定</th><th>連線測試</th></tr>
            </thead>
            <tbody>
              {Object.entries(cfg)
                .filter(([, c]) => c.fields.length > 0 || c.testable)
                .map(([pid, c]) => {
                  const label = health?.providers.find((p) => p.id === pid)?.label ?? pid;
                  if (pid === "ibkr" && c.fields.length > 0) {
                    return (
                      <tr key="ibkr.group">
                        <td>
                          {label}
                          {c.default_available && <div className="muted tiny">免金鑰 · 預設可用</div>}
                        </td>
                        <td colSpan={4}>
                          <div data-testid="ibkr-config-group" className="provider-config-group">
                            {c.fields.map((f) => renderProviderConfigField(pid, f))}
                            <div className="provider-config-actions">
                              {c.testable ? (
                                <>
                                  <button className="btn-ghost" disabled={!!busy}
                                    onClick={() => void runTest(pid)}>
                                    測試
                                  </button>
                                  {testResults[pid] && (
                                    <div className="muted tiny">{testResults[pid]}</div>
                                  )}
                                </>
                              ) : (
                                <span className="muted tiny">不提供（按次計費）</span>
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
                          {c.default_available && <div className="muted tiny">免金鑰 · 預設可用</div>}
                        </td>
                      )}
                      <td>{f ? f.label : "—"}</td>
                      <td>
                        {f
                          ? f.effective_source === "missing"
                            ? <span className="ds-chip ds-missing_key">未設定</span>
                            : <>
                                <span className="mono">{f.app_value_set ? f.app_value_masked : "（外部）"}</span>
                                {f.defaulted && <span className="muted tiny"> · 預設</span>}
                                <span className="muted tiny">（{providerConfigSourceLabel(f.effective_source)}）</span>
                                {f.needs_import && (
                                  <button className="btn-ghost tiny"
                                    disabled={busy === `import.${pid}.${f.field}`}
                                    onClick={() => void importField(pid, f.field, f.import_source)}>
                                    匯入
                                  </button>
                                )}
                                {f.needs_import && <span className="muted tiny">建議匯入</span>}
                              </>
                          : "—"}
                      </td>
                      <td>
                        {f && (
                          <>
                            <input
                              className="ds-interval ds-keyinput"
                              type={f.secret ? "password" : "text"}
                              placeholder={f.secret ? "貼上金鑰…" : f.label}
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
                                儲存
                              </button>
                            )}
                            {f.app_value_set && (
                              <button className="btn-ghost tiny"
                                onClick={() => void saveField(pid, f.field, null, f)}>
                                清除
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
                                測試
                              </button>
                              {testResults[pid] && (
                                <div className="muted tiny">{testResults[pid]}</div>
                              )}
                            </>
                          ) : (
                            <span className="muted tiny">不提供（按次計費）</span>
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
        <h4 className="detail-section">排程（每來源獨立）</h4>
        {!schedule ? (
          <p className="muted tiny">loading…</p>
        ) : (
          <div className="settings-table-scroll" data-testid="schedule-scroll">
          <table className="data-table settings-schedule-table">
            <thead>
              <tr>
                <th>來源</th><th>排程</th><th>間隔（分）</th><th>立即執行</th><th>最近一次</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(schedule).map(([id, s]) => (
                <tr key={id}>
                  <td>
                    {s.label}
                    {s.retired && <span className="ds-chip ds-disabled">已退役</span>}
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
                        {s.enabled ? "排程開啟" : "排程關閉"}
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
                        套用
                      </button>
                    )}
                  </td>
                  <td>
                    {s.running ? (
                      <SourceRunProgress
                        sourceLabel={s.label}
                        running={s.running}
                        progress={s.progress}
                      />
                    ) : (
                      <button
                        className="btn-ghost"
                        disabled={!!busy}
                        onClick={() => void runNow(id)}
                      >
                        ▶ Run
                      </button>
                    )}
                  </td>
                  <td className="muted tiny ds-last-run-cell settings-wrap-text">
                    {renderLastRun(id, s)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )}
        <p className="muted tiny ds-schedule-protection-note" style={{ marginTop: 8 }}>
          執行保護：同一資料來源與 IBKR 工作同時間只執行一次；若已有工作進行中，
          新觸發會顯示為已跳過，不會重複抓取。
        </p>
      </div>
    </div>
  );
}

type ModelEntryGroup = {
  label: string;
  entries: Array<EffectiveProviderModelEntry & { disabledReason: string | null }>;
};

function optionReason(
  entry: EffectiveProviderModelEntry,
  providerReason: string | null,
): string | null {
  if (providerReason) return providerReason;
  if (!entry.eligible) return entry.reason_code ?? "task_capability_missing";
  if (entry.visible_to_credential === false && entry.status !== "route") {
    return "model_not_visible";
  }
  return null;
}

function groupedModelEntries(
  entries: EffectiveProviderModelEntry[],
  providerReason: string | null,
): ModelEntryGroup[] {
  const withReason = entries.map((entry) => ({
    ...entry,
    disabledReason: optionReason(entry, providerReason),
  }));
  return [
    {
      label: MODEL_UX_LABELS.groups[0],
      entries: withReason.filter((entry) => entry.status === "visible" && !entry.disabledReason),
    },
    {
      label: MODEL_UX_LABELS.groups[1],
      entries: withReason.filter((entry) => entry.status === "visible" && !!entry.disabledReason),
    },
    {
      label: MODEL_UX_LABELS.groups[2],
      entries: withReason.filter((entry) => entry.status === "advanced" || entry.status === "seed"),
    },
    {
      label: MODEL_UX_LABELS.groups[3],
      entries: withReason.filter((entry) => entry.status === "route"),
    },
  ];
}

function compatEntries(
  provider: ModelProvider,
  row: DraftRoute,
  modelsByProvider: Record<ModelProvider, ModelOption[]>,
): EffectiveProviderModelEntry[] {
  const entries: EffectiveProviderModelEntry[] = (modelsByProvider[provider] ?? []).map((model) => ({
    id: model.id,
    label: `${model.label} · 未驗證（舊 sidecar 相容模式）`,
    status: "advanced",
    visible_to_credential: null,
    eligible: true,
    reason_code: null,
    thinking_mode: "none",
    effort_options: model.effort_options,
  }));
  if (row.model && !entries.some((entry) => entry.id === row.model)) {
    entries.push({
      id: row.model,
      label: `${row.model} · 未驗證（舊 sidecar 相容模式）`,
      status: "route",
      visible_to_credential: null,
      eligible: true,
      reason_code: "model_not_in_registry",
      thinking_mode: "none",
      effort_options: undefined,
    });
  }
  return entries;
}

export function ModelRoutingSection({
  catalog,
  draft,
  modelsByProvider,
  testState,
  onDraft,
  onTest,
  onReset,
  onDiscover = async () => {},
  onInvalidateTest = () => {},
  onOpenProviders = () => {},
}: {
  catalog: ModelCatalog;
  draft: Partial<Record<ModelTask, DraftRoute>>;
  modelsByProvider: Record<ModelProvider, ModelOption[]>;
  testState: TestState;
  onDraft: Dispatch<SetStateAction<Partial<Record<ModelTask, DraftRoute>>>>;
  onTest: (task: ModelTask) => Promise<void>;
  onReset: (task: ModelTask) => Promise<void>;
  onDiscover?: (provider: ModelProvider, credentialId: string) => Promise<void> | void;
  onInvalidateTest?: (task: ModelTask) => void;
  onOpenProviders?: () => void;
}) {
  const contexts = providerContexts(catalog.effective?.providers, catalog.credentials);
  const compatMode = !catalog.effective?.providers;

  const updateTask = (task: ModelTask, next: DraftRoute) => {
    onInvalidateTest(task);
    onDraft((prev) => ({ ...prev, [task]: next }));
  };

  return (
    <>
      <div className="settings-section-head">
        <div>
          <h2>任務模型路由</h2>
          <p className="muted">
            登入在 Providers 管理；這裡只決定每個任務使用哪個 provider、模型與 effort。
          </p>
        </div>
      </div>
      <div className="settings-grid">
        {catalog.tasks.map((task) => {
          const row = draft[task.id];
          if (!row) return null;
          const effectiveRoute = catalog.routes[task.id];
          const envLocked = effectiveRoute?.source === "env";
          const context = contexts[row.provider];
          const taskEffective = catalog.effective?.tasks?.[task.id];
          const providerBlock = taskEffective?.providers?.[row.provider];
          const rawEntries = providerBlock?.models
            ?? compatEntries(row.provider, row, modelsByProvider);
          const entries = rawEntries.some((entry) => entry.id === row.model) || !row.model
            ? rawEntries
            : [
                ...rawEntries,
                {
                  id: row.model,
                  label: row.model,
                  status: "route" as const,
                  visible_to_credential: null,
                  eligible: true,
                  reason_code: "model_not_in_registry",
                  thinking_mode: "none",
                  effort_options: [],
                },
              ];
          const providerReason = context
            ? (providerBlock?.reason_code ?? null)
            : "missing_active_credential";
          const groups = groupedModelEntries(entries, providerReason);
          const selectedEntry = entries.find((entry) => entry.id === row.model) ?? null;
          const selectedReason = selectedEntry ? optionReason(selectedEntry, providerReason) : null;
          const disabledReasons = Array.from(new Set(
            groups.flatMap((group) => group.entries)
              .map((entry) => entry.disabledReason)
              .filter((reason): reason is string => !!reason),
          ));
          const effortOptions = effortOptionsForModel(
            catalog,
            row.provider,
            row.model,
            selectedEntry?.effort_options,
          );
          const currentTest = testState[task.id];
          const testIsCurrent = !!(
            currentTest?.snapshot
            && isTaskTestSnapshotCurrent(currentTest.snapshot, {
              task: task.id,
              route: row,
              credentialId: context?.credential_id ?? null,
              stale: currentTest.stale,
            })
          );
          const modelSelectDisabled = !context || (!!providerBlock && !providerBlock.executable);
          const testDisabled = (
            compatMode
            || modelSelectDisabled
            || !row.model.trim()
            || !!selectedReason
            || !!currentTest?.loading
          );
          return (
            <div className="settings-panel" key={task.id} data-testid={`route-${task.id}`}>
              <div className="settings-panel-head">
                <div>
                  <h2>{TASK_LABELS[task.id]}</h2>
                  <p className="muted">{task.description}</p>
                </div>
                <span
                  className={`route-source ${routeSourceBadge(effectiveRoute?.source ?? "default").tone}`}
                  aria-label={`路由權威 ${routeSourceBadge(effectiveRoute?.source ?? "default").label}`}
                >
                  {routeSourceBadge(effectiveRoute?.source ?? "default").label}
                </span>
              </div>

              {envLocked && (
                <p className="warn-text">
                  目前由環境變數控制；可以儲存到 DB，但 runtime 仍以 env 為準。
                </p>
              )}
              {effectiveRoute?.warning && <p className="warn-text">{effectiveRoute.warning}</p>}

              <div className="field">
                <span>Provider</span>
                <div className="model-provider-toggle" role="group" aria-label={`Provider ${task.id}`}>
                  {(["openai", "anthropic"] as ModelProvider[]).map((provider) => (
                    <button
                      key={provider}
                      type="button"
                      className={row.provider === provider ? "active" : ""}
                      aria-pressed={row.provider === provider}
                      onClick={() => {
                        if (provider === row.provider) return;
                        const nextBlock = taskEffective?.providers?.[provider];
                        const nextModels = nextBlock?.models
                          ?? compatEntries(provider, row, modelsByProvider);
                        const keepModel = nextModels.some((entry) => entry.id === row.model);
                        updateTask(task.id, {
                          provider,
                          model: keepModel ? row.model : "",
                          effort: "default",
                          custom: false,
                        });
                      }}
                    >
                      {provider === "openai" ? "OpenAI" : "Anthropic"}
                    </button>
                  ))}
                </div>
              </div>

              <div className={`model-credential-summary ${context ? "ok" : "missing"}`}>
                {context ? (
                  <>
                    <strong>{context.label}</strong>
                    <span>{MODEL_UX_LABELS.authModes[context.auth_mode] ?? context.auth_mode}</span>
                    <span>
                      {providerBlock?.cache_state === "ok"
                        ? "已取得可見模型清單"
                        : providerBlock?.cache_state === "seed_only"
                          ? "此通道無法線上列出模型"
                          : "尚未探索此登入的模型"}
                    </span>
                    {providerBlock?.discovered_at && (
                      <span>最後驗證可見 {formatSystemTimestamp(providerBlock.discovered_at)}</span>
                    )}
                    <button
                      type="button"
                      className="btn-ghost small"
                      onClick={() => void onDiscover(row.provider, context.credential_id)}
                    >
                      重新驗證列表
                    </button>
                  </>
                ) : (
                  <>
                    <strong>尚未設定此 provider 的登入</strong>
                    <button type="button" className="btn-ghost small" onClick={onOpenProviders}>
                      前往 Providers
                    </button>
                  </>
                )}
              </div>

              {compatMode && (
                <p className="warn-text">
                  未驗證（舊 sidecar 相容模式）。請重啟／更新 sidecar 後再執行模型測試。
                </p>
              )}

              {!row.custom ? (
                <div className="field">
                  <span>Model</span>
                  <select
                    aria-label={`模型 ${task.id}`}
                    value={entries.some((entry) => entry.id === row.model) ? row.model : ""}
                    disabled={modelSelectDisabled}
                    onChange={(event) => {
                      const model = event.currentTarget.value;
                      if (!model) return;
                      const nextEntry = entries.find((entry) => entry.id === model);
                      const nextEfforts = effortOptionsForModel(
                        catalog, row.provider, model, nextEntry?.effort_options,
                      );
                      const effort = nextEfforts.some((item) => item.id === row.effort)
                        ? row.effort
                        : "default";
                      updateTask(task.id, { ...row, model, effort, custom: false });
                    }}
                  >
                    <option value="">選擇模型…</option>
                    {groups.map((group) => (
                      <optgroup key={group.label} label={group.label}>
                        {group.entries.map((entry) => (
                          <option
                            key={`${group.label}:${entry.id}`}
                            value={entry.id}
                            disabled={!!entry.disabledReason}
                          >
                            {entry.label}
                            {entry.disabledReason
                              ? ` · ${MODEL_UX_LABELS.reasons[entry.disabledReason] ?? entry.disabledReason}`
                              : entry.status === "advanced"
                                ? " · 進階"
                                : entry.status === "seed"
                                  ? " · 未驗證"
                                  : entry.status === "route" && entry.reason_code
                                    ? ` · ${MODEL_UX_LABELS.reasons[entry.reason_code] ?? entry.reason_code}`
                                    : ""}
                          </option>
                        ))}
                      </optgroup>
                    ))}
                  </select>
                  {disabledReasons.length > 0 && (
                    <p className="field-help" aria-label={`模型限制 ${task.id}`}>
                      不可選：{disabledReasons.map((reason) => MODEL_UX_LABELS.reasons[reason] ?? reason).join("；")}
                    </p>
                  )}
                  <button
                    type="button"
                    className="btn-ghost small model-custom-toggle"
                    disabled={!context}
                    onClick={() => updateTask(task.id, { ...row, effort: "default", custom: true })}
                  >
                    輸入自訂 model id
                  </button>
                </div>
              ) : (
                <div className="field">
                  <span>自訂 model id · 未驗證</span>
                  <input
                    aria-label={`自訂 model id ${task.id}`}
                    value={row.model}
                    placeholder={row.provider === "anthropic" ? "claude-…" : "gpt-…"}
                    onChange={(event) => updateTask(task.id, {
                      ...row,
                      model: event.currentTarget.value.trim(),
                      custom: true,
                    })}
                  />
                  <span className="field-help">自訂 id 仍會經過「實際測試」；不會被當成已驗證模型。</span>
                  <button
                    type="button"
                    className="btn-ghost small model-custom-toggle"
                    onClick={() => updateTask(task.id, { ...row, custom: false })}
                  >
                    返回模型列表
                  </button>
                </div>
              )}

              <label className="field">
                <span>Effort</span>
                <select
                  aria-label={`Effort ${task.id}`}
                  value={effortOptions.some((item) => item.id === (row.effort || "default"))
                    ? (row.effort || "default")
                    : "default"}
                  onChange={(event) => updateTask(task.id, {
                    ...row,
                    effort: event.currentTarget.value,
                  })}
                >
                  {effortOptions.map((effort) => (
                    <option key={effort.id} value={effort.id}>{effort.label}</option>
                  ))}
                </select>
                <span className="field-help">
                  {effortOptions.find((item) => item.id === (row.effort || "default"))?.description
                    ?? "Provider default."}
                </span>
              </label>

              <div className="model-thinking-line">
                <span>Thinking</span>
                <strong>
                  {MODEL_UX_LABELS.thinking[selectedEntry?.thinking_mode ?? "none"]
                    ?? selectedEntry?.thinking_mode
                    ?? MODEL_UX_LABELS.thinking.none}
                </strong>
              </div>

              <ModelNotes
                models={modelsByProvider[row.provider] ?? []}
                selected={row.model}
                custom={row.custom}
              />

              <div className="settings-actions">
                <button
                  type="button"
                  className="btn-ghost small"
                  disabled={testDisabled}
                  onClick={() => void onTest(task.id)}
                >
                  {currentTest?.loading && testIsCurrent ? "測試中…" : "實際測試"}
                </button>
                {context?.auth_mode.includes("oauth") && (
                  <span className="muted tiny">消耗訂閱額度，非 API 帳單</span>
                )}
                {routeIsOverridable(effectiveRoute?.source ?? "default") && (
                  <button
                    type="button"
                    className="btn-ghost small"
                    aria-label={`重設 ${task.id}`}
                    onClick={() => void onReset(task.id)}
                  >
                    重設為 fallback
                  </button>
                )}
              </div>

              {currentTest && !testIsCurrent && (
                <p className="muted tiny">選擇已變更——重新測試</p>
              )}
              {currentTest?.result && testIsCurrent && (
                <TaskModelTestStatus result={currentTest.result} />
              )}
            </div>
          );
        })}
      </div>
    </>
  );
}

function TaskModelTestStatus({ result }: { result: TaskModelTestResult }) {
  const ok = result.status === "ok";
  const action = result.error_code ? MODEL_UX_LABELS.reasons[result.error_code] : null;
  return (
    <div className={`test-status ${ok ? "ok" : "bad"}`}>
      <strong>{ok ? "可實際呼叫" : action ?? "測試失敗"}</strong>
      {result.latency_ms != null && <span>{result.latency_ms} ms</span>}
      {result.warning && <p className="warn-text">{result.warning}</p>}
      {result.fallback_effort && (
        <p className="muted tiny">fallback effort: {result.fallback_effort}</p>
      )}
    </div>
  );
}
function runtimeSourceBadge(
  source: ResearchRuntimeSettings["source"] | FixedTaskRuntimeSettings["source"],
) {
  if (source === "db") return { label: "DB 已儲存", tone: "active" };
  if (source === "env") return { label: "env override", tone: "override" };
  if (source === "profile") return { label: "設定檔 fallback", tone: "fallback" };
  return { label: "內建預設", tone: "default" };
}

function parseFixedTaskTimeout(raw: string): number | null {
  const trimmed = raw.trim();
  if (!trimmed) return null;
  const value = Number(trimmed);
  if (!Number.isFinite(value) || value < 60 || value > 3600) return null;
  return value;
}

export function FixedTaskRuntimeSection({
  settings,
  saving,
  onSave,
  onReset,
}: {
  settings: FixedTaskRuntimeMap;
  saving: boolean;
  onSave: (body: {
    tasks: {
      card_synthesis: { model_timeout_s: number };
      card_translation: { model_timeout_s: number };
    };
  }) => void | Promise<void>;
  onReset: () => void | Promise<void>;
}) {
  const [draft, setDraft] = useState({
    card_synthesis: String(settings.card_synthesis.model_timeout_s),
    card_translation: String(settings.card_translation.model_timeout_s),
  });

  useEffect(() => {
    setDraft({
      card_synthesis: String(settings.card_synthesis.model_timeout_s),
      card_translation: String(settings.card_translation.model_timeout_s),
    });
  }, [
    settings.card_synthesis.model_timeout_s,
    settings.card_translation.model_timeout_s,
  ]);

  const synthesis = parseFixedTaskTimeout(draft.card_synthesis);
  const translation = parseFixedTaskTimeout(draft.card_translation);
  const disabled = saving || synthesis == null || translation == null;
  const canReset = settings.card_synthesis.db_saved || settings.card_translation.db_saved;
  const rows: Array<{
    key: "card_synthesis" | "card_translation";
    label: string;
    settings: FixedTaskRuntimeSettings;
  }> = [
    {
      key: "card_synthesis",
      label: "AI 卡片生成 - 模型執行上限（秒）",
      settings: settings.card_synthesis,
    },
    {
      key: "card_translation",
      label: "卡片翻譯 - 模型執行上限（秒）",
      settings: settings.card_translation,
    },
  ];

  return (
    <section className="settings-panel research-runtime-panel">
      <div className="settings-panel-head">
        <div>
          <h2>固定 AI 任務執行限制</h2>
          <p className="muted">
            較高 effort 的模型可能需要更久；這裡只控制最長等待時間，不會變更模型或 effort。
          </p>
        </div>
      </div>

      <div className="runtime-limit-grid">
        {rows.map((row) => {
          const badge = runtimeSourceBadge(row.settings.source);
          return (
            <label className="field" key={row.key}>
              <span>{row.label}</span>
              <input
                name={`${row.key}_model_timeout_s`}
                type="number"
                min={60}
                max={3600}
                step={30}
                value={draft[row.key]}
                onChange={(e) => setDraft((prev) => ({
                  ...prev,
                  [row.key]: e.target.value,
                }))}
              />
              <span className={`route-source ${badge.tone}`}>{badge.label}</span>
              {row.settings.warning && (
                <span className="warn-text">{row.settings.warning}</span>
              )}
            </label>
          );
        })}
      </div>

      <div className="settings-actions">
        <button
          type="button"
          className="btn-ghost small"
          disabled={disabled}
          onClick={() => {
            if (synthesis == null || translation == null) return;
            void onSave({
              tasks: {
                card_synthesis: { model_timeout_s: synthesis },
                card_translation: { model_timeout_s: translation },
              },
            });
          }}
        >
          {saving ? "儲存中…" : "儲存固定任務限制"}
        </button>
        {canReset && (
          <button
            type="button"
            className="btn-ghost small"
            disabled={saving}
            onClick={() => void onReset()}
          >
            重設固定任務限制
          </button>
        )}
      </div>
    </section>
  );
}

export function ResearchRuntimeSection({
  settings,
  saving,
  onSave,
  onReset,
}: {
  settings: ResearchRuntimeSettings;
  saving: boolean;
  onSave: (body: Pick<ResearchRuntimeSettings, "max_tool_calls" | "session_timeout_s" | "per_tool_timeout_s">) => void | Promise<void>;
  onReset: () => void | Promise<void>;
}) {
  const [draft, setDraft] = useState({
    max_tool_calls: String(settings.max_tool_calls),
    session_timeout_s: String(settings.session_timeout_s),
    per_tool_timeout_s: String(settings.per_tool_timeout_s),
  });

  useEffect(() => {
    setDraft({
      max_tool_calls: String(settings.max_tool_calls),
      session_timeout_s: String(settings.session_timeout_s),
      per_tool_timeout_s: String(settings.per_tool_timeout_s),
    });
  }, [settings.max_tool_calls, settings.session_timeout_s, settings.per_tool_timeout_s]);

  const badge = runtimeSourceBadge(settings.source);
  const disabled = saving || !draft.max_tool_calls || !draft.session_timeout_s || !draft.per_tool_timeout_s;

  return (
    <section className="settings-panel research-runtime-panel">
      <div className="settings-panel-head">
        <div>
          <h2>AI 研究執行限制</h2>
          <p className="muted">
            控制單次 AI 研究的工具輪數與 subscription driver timeout。API-key 路徑目前只套用 max turns；切頁不中斷與並行會由 server-owned run manager 解決。
          </p>
        </div>
        <span className={`route-source ${badge.tone}`}>{badge.label}</span>
      </div>

      {settings.warning && <p className="warn-text">{settings.warning}</p>}

      <div className="runtime-limit-grid">
        <label className="field">
          <span>Max turns</span>
          <input
            name="max_tool_calls"
            type="number"
            min={1}
            max={500}
            step={1}
            value={draft.max_tool_calls}
            onChange={(e) => setDraft((prev) => ({ ...prev, max_tool_calls: e.target.value }))}
          />
          <span className="field-help">模型可連續呼叫工具的最大輪數；API-key 與 subscription Research 都會套用。</span>
        </label>
        <label className="field">
          <span>Session timeout 秒</span>
          <input
            name="session_timeout_s"
            type="number"
            min={0}
            max={86400}
            step={30}
            value={draft.session_timeout_s}
            onChange={(e) => setDraft((prev) => ({ ...prev, session_timeout_s: e.target.value }))}
          />
          <span className="field-help">subscription driver 的整體牆鐘時間；0 代表不設整體 timeout。</span>
        </label>
        <label className="field">
          <span>每工具 timeout 秒</span>
          <input
            name="per_tool_timeout_s"
            type="number"
            min={1}
            max={3600}
            step={5}
            value={draft.per_tool_timeout_s}
            onChange={(e) => setDraft((prev) => ({ ...prev, per_tool_timeout_s: e.target.value }))}
          />
          <span className="field-help">subscription driver 裡單一 ArkScope 工具呼叫的 timeout。</span>
        </label>
      </div>

      <div className="settings-actions">
        <button
          type="button"
          className="btn-ghost small"
          disabled={disabled}
          onClick={() => onSave({
            max_tool_calls: Number(draft.max_tool_calls),
            session_timeout_s: Number(draft.session_timeout_s),
            per_tool_timeout_s: Number(draft.per_tool_timeout_s),
          })}
        >
          {saving ? "儲存中…" : "儲存限制"}
        </button>
        {settings.db_saved && (
          <button type="button" className="btn-ghost small" disabled={saving} onClick={() => onReset()}>
            重設限制
          </button>
        )}
      </div>
    </section>
  );
}

export function ProviderSection({
  catalog,
  runtime,
  discovery,
  onRefresh,
  onDiscover,
  onClearDiscovery,
  onUseModel,
}: {
  catalog: ModelCatalog;
  runtime: RuntimeConfig | null;
  discovery: DiscoveryState;
  onRefresh: () => Promise<void>;
  onDiscover: (provider: ModelProvider, credentialId: string | null) => Promise<void>;
  onClearDiscovery: (provider: ModelProvider) => void;
  onUseModel: (provider: ModelProvider, model: string, task: ModelTask) => void;
}) {
  const [selectedCreds, setSelectedCreds] = useState<Partial<Record<ModelProvider, string>>>({});
  const [newAlias, setNewAlias] = useState<Partial<Record<ModelProvider, string>>>({});
  const [newSecret, setNewSecret] = useState<Partial<Record<ModelProvider, string>>>({});
  const [newMakeActive, setNewMakeActive] = useState<Partial<Record<ModelProvider, boolean>>>({});
  // OAuth/setup-token "set active on add?" choice (per provider). Undefined = the
  // unified default (Claude: active iff no local DB credential; ChatGPT: always off —
  // logging in must never silently switch the active credential).
  const [oauthMakeActive, setOauthMakeActive] = useState<Partial<Record<ModelProvider, boolean>>>({});
  const [renames, setRenames] = useState<Record<string, string>>({});
  const [metadataDrafts, setMetadataDrafts] = useState<Record<string, CredentialMetadataDraft>>({});
  // Per-provider disclosure state for the (low-frequency) setup forms. Undefined =
  // use the smart default (collapsed once the provider has any usable credential);
  // a user toggle pins it. Keyed by provider so toggling one card doesn't move others.
  const [setupOpen, setSetupOpen] = useState<Record<string, boolean>>({});
  const [providerMsg, setProviderMsg] = useState<string | null>(null);
  const [providerErr, setProviderErr] = useState<string | null>(null);
  // Claude setup-token import (anthropic only). The token is held in form state
  // only until submit, then cleared — it never persists in React beyond that.
  const [claudeAlias, setClaudeAlias] = useState("");
  const [claudeLabel, setClaudeLabel] = useState("");
  const [claudeToken, setClaudeToken] = useState("");
  // OpenAI ChatGPT in-app OAuth login (openai only). Holds only the public state +
  // auth_url for an in-flight login; no token ever reaches the UI.
  const [oauth, setOauth] = useState<{ state: string; authUrl: string; phase: "waiting" | "manual" } | null>(null);
  // Split busy state: the long (≤180s) loopback poll must NOT disable the manual
  // "完成登入" button — otherwise a stuck popup/callback locks out the fallback.
  const [pollBusy, setPollBusy] = useState(false);
  const [manualBusy, setManualBusy] = useState(false);
  const [manualValue, setManualValue] = useState("");
  // ONE ChatGPT login/re-login flow at a time: :1455 is a fixed loopback port, so
  // every trigger (登入 ChatGPT / row 重新登入 / discovery reauth hint) shares this.
  const chatgptLoginBusy = pollBusy || manualBusy || oauth != null;
  // Cooperative abort for the in-flight poll, so a manual completion or a cancel
  // stops it immediately (rather than leaving it to run — and pin pollBusy — for the
  // full timeout). A per-login token object; the poll closure reads token.aborted.
  const pollToken = useRef<{ aborted: boolean }>({ aborted: false });

  async function addKey(provider: ModelProvider, makeActive: boolean) {
    const alias = (newAlias[provider] ?? "").trim();
    const secret = (newSecret[provider] ?? "").trim();
    if (!secret) {
      setProviderErr(`${provider}: API key 不可為空`);
      return;
    }
    setProviderErr(null);
    setProviderMsg(null);
    try {
      await addCredential({
        provider,
        auth_type: "api_key",
        alias: alias || `${provider} key`,
        secret,
        make_active: makeActive,
      });
      setNewAlias((prev) => ({ ...prev, [provider]: "" }));
      setNewSecret((prev) => ({ ...prev, [provider]: "" }));
      setProviderMsg(addApiKeySuccessMessage(provider, makeActive));
      await onRefresh();
    } catch (e) {
      setProviderErr(e instanceof Error ? e.message : String(e));
    }
  }

  async function importClaudeToken(makeActive: boolean) {
    const token = claudeToken.trim();
    if (!token) {
      setProviderErr("Claude setup-token 不可為空");
      return;
    }
    setProviderErr(null);
    setProviderMsg(null);
    try {
      await importOAuthCredential({
        provider: "anthropic",
        auth_mode: "claude_code_oauth",
        alias: claudeAlias.trim() || "Claude subscription",
        token,
        account_label: claudeLabel.trim() || undefined,
        make_active: makeActive,
      });
      setClaudeToken(""); // clear the token from state immediately on success
      setClaudeAlias("");
      setClaudeLabel("");
      setProviderMsg("Claude setup-token 已匯入（存入 token-store，未存入 credential DB）。");
      await onRefresh();
    } catch (e) {
      setClaudeToken(""); // also clear on failure — don't keep the token around
      setProviderErr(e instanceof Error ? e.message : String(e));
    }
  }

  async function copyLoginLink() {
    if (!oauth?.authUrl) return;
    if (!navigator.clipboard) {
      setProviderErr("此瀏覽器不支援自動複製，請從新分頁的網址列手動複製登入連結。");
      return;
    }
    try {
      await navigator.clipboard.writeText(oauth.authUrl);
      setProviderMsg("登入連結已複製。");
    } catch {
      setProviderErr("無法複製連結（瀏覽器剪貼簿權限被拒）。請從新分頁完成登入，或重新點「登入 ChatGPT」。");
    }
  }

  async function startChatGPTLogin(makeActive: boolean, reloginCredentialId?: string) {
    setProviderErr(null);
    setProviderMsg(null);
    setPollBusy(true);
    const token = { aborted: false }; // this login's abort token; manual/cancel flips it
    pollToken.current = token;
    try {
      const r = await startOpenAIOAuth(makeActive, reloginCredentialId);
      setOauth({ state: r.state, authUrl: r.auth_url, phase: "waiting" });
      // open the browser login; if a popup blocker eats it, the copy-link button is the fallback
      window.open(r.auth_url, "_blank", "noopener,noreferrer");
      const res = await pollOAuthStatus(r.state, {
        statusFn: openAIOAuthStatus,
        now: () => Date.now(),
        sleep: (ms) => new Promise<void>((resolve) => window.setTimeout(resolve, ms)),
        shouldAbort: () => token.aborted,
      });
      if (res.kind === "aborted") return; // a manual completion / cancel superseded this poll
      if (res.kind === "success") {
        setOauth(null);
        setProviderMsg("ChatGPT 訂閱已登入（token 存入 token-store，未存入 credential DB）。");
        await onRefresh();
      } else if (res.kind === "timeout") {
        setOauth((o) => (o ? { ...o, phase: "manual" } : o));
        setProviderErr("等不到瀏覽器回呼（可能 popup 被擋，或本機 :1455 沒收到）。請改用下方手動貼上授權碼。");
      } else if (res.kind === "error") {
        // surface the backend reason as-is — NO silent fallback to an API key.
        // F4: offer the manual paste ONLY when it can still succeed (the state
        // wasn't consumed by a failed completion) — else reset the flow.
        if (res.manualCompletable) {
          setOauth((o) => (o ? { ...o, phase: "manual" } : o));
          setProviderErr(`登入失敗：${res.detail}`);
        } else {
          setOauth(null);
          setProviderErr(`登入失敗：${res.detail}（此登入工作階段已失效，請重新點「登入 ChatGPT」）`);
        }
      } else {
        setOauth(null);
        setProviderErr("登入工作階段不存在或已過期，請重新點「登入 ChatGPT」。");
      }
    } catch (e) {
      setProviderErr(e instanceof Error ? e.message : String(e));
    } finally {
      setPollBusy(false);
    }
  }

  // S3 re-login: replace an existing chatgpt_oauth credential's token IN PLACE
  // (no new row; alias/active preserved). First expand the OpenAI setup
  // disclosure — the waiting/manual/cancel controls already live there — then
  // run the SAME login flow with the target id. All triggers share the
  // chatgptLoginBusy guard so two flows can't race for the :1455 callback port.
  function startChatGPTRelogin(credentialId: string) {
    setSetupOpen((prev) => ({ ...prev, openai: true }));
    void startChatGPTLogin(false, credentialId);
  }

  function cancelChatGPTLogin() {
    pollToken.current.aborted = true; // stop the background poll (frees the 登入 button)
    const st = oauth?.state;
    // Also cancel server-side: evict the pending login so a late browser callback can't
    // still create a credential, and free the loopback port. Best-effort.
    if (st) void cancelOpenAIOAuth(st).catch(() => {});
    setOauth(null);
    setManualValue("");
  }

  async function completeChatGPTManual() {
    if (!oauth) return;
    const pasted = manualValue.trim();
    if (!pasted) {
      setProviderErr("請貼上授權碼或回呼網址");
      return;
    }
    setProviderErr(null);
    setProviderMsg(null);
    setManualBusy(true);
    try {
      await completeOpenAIOAuthManual(buildManualCompletion(oauth.state, pasted));
      pollToken.current.aborted = true; // manual won — stop the still-running loopback poll
      setManualValue("");
      setOauth(null);
      setProviderMsg("ChatGPT 訂閱已登入（手動完成；token 存入 token-store）。");
      await onRefresh();
    } catch (e) {
      // a bad/expired/forged state or a token-exchange error 400s here — show it, no fallback
      setProviderErr(e instanceof Error ? e.message : String(e));
    } finally {
      setManualBusy(false);
    }
  }

  async function setActive(credentialId: string) {
    setProviderErr(null);
    setProviderMsg(null);
    try {
      await updateCredential(credentialId, { active: true });
      setProviderMsg("Active key 已更新。");
      await onRefresh();
    } catch (e) {
      setProviderErr(e instanceof Error ? e.message : String(e));
    }
  }

  async function saveCredentialDetails(
    credentialId: string,
    alias: string,
    accountLabel: string,
    expiresAt?: string,
  ) {
    setProviderErr(null);
    setProviderMsg(null);
    try {
      const cleanAlias = alias.trim();
      const body: { alias?: string; account_label: string; expires_at?: string } = {
        account_label: accountLabel.trim(),
      };
      if (cleanAlias) body.alias = cleanAlias;
      if (expiresAt !== undefined) body.expires_at = expiresAt.trim();
      await updateCredential(credentialId, body);
      setRenames((prev) => {
        const next = { ...prev };
        delete next[credentialId];
        return next;
      });
      setMetadataDrafts((prev) => {
        const next = { ...prev };
        delete next[credentialId];
        return next;
      });
      setProviderMsg("Credential 顯示資訊已更新。");
      await onRefresh();
    } catch (e) {
      setProviderErr(e instanceof Error ? e.message : String(e));
    }
  }

  async function removeKey(credentialId: string) {
    setProviderErr(null);
    setProviderMsg(null);
    try {
      await deleteCredential(credentialId);
      setProviderMsg("Credential 已刪除。");
      await onRefresh();
    } catch (e) {
      setProviderErr(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <>
      <div className="settings-section-head">
        <div>
          <h2>Provider 狀態</h2>
          <p className="muted">
            Provider/channel 和 task routing 分開管理。這裡顯示本機 credential 狀態；每個 credential 可依其類型做 model discovery / capability test（API key 與 OAuth 方式各自不同）。
          </p>
        </div>
      </div>
      {providerErr && <p className="error-text">{providerErr}</p>}
      {providerMsg && <p className="ok-text">{providerMsg}</p>}
      <div className="provider-grid">
        {catalog.providers.map((provider) => {
          const models = catalog.models.filter((m) => m.provider === provider);
          const credentials =
            catalog.credentials?.[provider] ??
            (provider === "anthropic" ? runtime?.anthropic.credentials : runtime?.openai.credentials) ??
            [];
          const activeCred = credentials.find((c) => c.active && c.available) ?? null;
          const pill = credentialPill(activeCred);
          // Smart-collapse the setup forms: expanded only when the provider has NO
          // usable credential (the empty-state where setup IS the task); a user
          // toggle (setupOpen[provider]) overrides.
          const hasCredential = credentials.some((c) => c.available);
          const setupExpanded = setupOpen[provider] ?? !hasCredential;
          const makeNewKeyActive = newMakeActive[provider] ?? defaultMakeActiveOnAdd(credentials);
          // Claude import default = same empty-state rule; ChatGPT default = OFF (never
          // silently switch the active credential).
          const claudeImportActive = oauthMakeActive.anthropic ?? defaultMakeActiveOnAdd(credentials);
          const chatgptLoginActive = oauthMakeActive.openai ?? false;
          const sourceUrls = Array.from(new Set(models.map((m) => m.source_url)));
          const discoveryState = discovery[provider];
          const usable = credentials.filter((c) => c.available && c.can_discover_models);
          const activeUsable = usable.find((c) => c.active);
          const selectedDraft = selectedCreds[provider];
          const selectedCredential = usable.some((c) => c.id === selectedDraft)
            ? selectedDraft ?? null
            : activeUsable?.id ?? usable[0]?.id ?? null;
          const selectedAuthMode = usable.find((c) => c.id === selectedCredential)?.auth_type ?? null;
          // auth_mode of the credential that produced the current discovery result
          const discoveredAuthMode = discoveryState?.result
            ? credentials.find((c) => c.id === discoveryState.result?.credential_id)?.auth_type ?? null
            : null;
          const discoveredCredential = discoveryState?.result
            ? credentials.find((c) => c.id === discoveryState.result?.credential_id) ?? null
            : null;
          return (
            <div className="settings-panel provider-card" key={provider}>
              <div className="settings-panel-head">
                <div>
                  <h2>{provider}</h2>
                  <p className="muted">{models.length} seed models · direct model id input allowed</p>
                </div>
                <span className={`key-pill ${pill.ok ? "ok" : "missing"}`}>
                  {pill.label}
                </span>
              </div>
              <div className="provider-model-list">
                {models.map((model) => (
                  <span key={model.id}>{model.id}</span>
                ))}
              </div>
              {/* High-frequency first: your credentials + their row actions (active row first). */}
              <CredentialList
                credentials={activeFirst(credentials)}
                renames={renames}
                metadataDrafts={metadataDrafts}
                onRenameDraft={(id, alias) => setRenames((prev) => ({ ...prev, [id]: alias }))}
                onMetadataDraft={(id, field, value) => setMetadataDrafts((prev) => ({
                  ...prev,
                  [id]: { ...prev[id], [field]: value },
                }))}
                onSaveCredentialDetails={(id, alias, accountLabel, expiresAt) =>
                  void saveCredentialDetails(id, alias, accountLabel, expiresAt)}
                onSetActive={(id) => void setActive(id)}
                onDelete={(id) => void removeKey(id)}
                onDiscover={(id) => void onDiscover(provider, id)}
                discoverLoadingId={discoveryState?.loading ? discoveryState.credentialId ?? null : null}
                onRelogin={provider === "openai" ? startChatGPTRelogin : undefined}
                reloginBusy={chatgptLoginBusy}
              />
              {discoveryState?.result && (
                <DiscoveryResultView
                  result={discoveryState.result}
                  authMode={discoveredAuthMode}
                  credentialLabel={discoveredCredential?.label ?? null}
                  onClose={() => onClearDiscovery(provider)}
                  onUse={(model, task) => onUseModel(provider, model, task)}
                  onRelogin={
                    provider === "openai" && discoveryState.result.credential_id
                      ? () => startChatGPTRelogin(discoveryState.result!.credential_id!)
                      : undefined
                  }
                  reloginBusy={chatgptLoginBusy}
                />
              )}
              <div className="settings-actions">
                <p className="muted tiny" style={{ width: "100%" }}>
                  進階：指定某個 credential 做 discovery（一般用上方各列的「列模型／查看候選模型」即可）。
                </p>
                <label className="field credential-select">
                  <span>credential</span>
                  <select
                    value={selectedCredential ?? ""}
                    onChange={(e) => setSelectedCreds((prev) => ({ ...prev, [provider]: e.target.value }))}
                  >
                    {usable.map((cred) => (
                      <option key={cred.id} value={cred.id}>
                        {cred.active ? "★ " : ""}{cred.label} · {cred.masked ?? cred.source}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  type="button"
                  className="btn-ghost small"
                  disabled={!selectedCredential || discoveryState?.loading}
                  onClick={() => void onDiscover(provider, selectedCredential)}
                >
                  {discoveryState?.loading ? "讀取中…" : `${discoverButtonLabel(selectedAuthMode)}（此 credential）`}
                </button>
              </div>
              {/* Low-frequency setup: collapsed once a usable credential exists. */}
              <SetupDisclosure
                provider={provider}
                open={setupExpanded}
                onOpenChange={(p, open) => setSetupOpen((prev) => ({ ...prev, [p]: open }))}
              >
                <div className="credential-add-box">
                  <label className="field">
                    <span>新增 API key alias</span>
                    <input
                      value={newAlias[provider] ?? ""}
                      placeholder={`${provider} primary`}
                      onChange={(e) => setNewAlias((prev) => ({ ...prev, [provider]: e.target.value }))}
                    />
                  </label>
                  <label className="field">
                    <span>新增 API key</span>
                    <input
                      type="password"
                      value={newSecret[provider] ?? ""}
                      placeholder={provider === "openai" ? "sk-…" : "sk-ant-…"}
                      onChange={(e) => setNewSecret((prev) => ({ ...prev, [provider]: e.target.value }))}
                    />
                  </label>
                  <div className="credential-add-footer">
                    <label className="credential-add-toggle">
                      <input
                        type="checkbox"
                        checked={makeNewKeyActive}
                        onChange={(e) => setNewMakeActive((prev) => ({ ...prev, [provider]: e.target.checked }))}
                      />
                      <span>新增後設為 active</span>
                    </label>
                    <button
                      type="button"
                      className="btn-ghost small"
                      onClick={() => void addKey(provider, makeNewKeyActive)}
                    >
                      {addApiKeyButtonLabel(makeNewKeyActive)}
                    </button>
                  </div>
                </div>
                {provider === "anthropic" && (
                  <div className="credential-add-box oauth-import-box">
                    <p className="muted tiny" style={{ marginBottom: 8 }}>
                      匯入 Claude setup-token（訂閱登入）。<strong>這不是 Anthropic API key。</strong>
                      Token 會存入本機 token-store/keyring，credential DB 只保存 metadata。
                      用終端機 <code className="mono">claude setup-token</code> 產生後貼上。
                    </p>
                    <label className="field">
                      <span>顯示名稱（可留空）</span>
                      <input
                        value={claudeAlias}
                        placeholder="Claude subscription"
                        onChange={(e) => setClaudeAlias(e.target.value)}
                      />
                    </label>
                    <label className="field">
                      <span>帳號／方案標籤（可留空）</span>
                      <input
                        value={claudeLabel}
                        placeholder="例如 Claude Pro / Max"
                        onChange={(e) => setClaudeLabel(e.target.value)}
                      />
                    </label>
                    <label className="field">
                      <span>Claude setup-token</span>
                      <input
                        type="password"
                        autoComplete="off"
                        value={claudeToken}
                        placeholder="貼上 claude setup-token 產生的 token"
                        onChange={(e) => setClaudeToken(e.target.value)}
                      />
                    </label>
                    <div className="credential-add-footer">
                      <label className="credential-add-toggle">
                        <input
                          type="checkbox"
                          checked={claudeImportActive}
                          onChange={(e) => setOauthMakeActive((prev) => ({ ...prev, anthropic: e.target.checked }))}
                        />
                        <span>匯入後設為 active</span>
                      </label>
                      <button type="button" className="btn-ghost small" onClick={() => void importClaudeToken(claudeImportActive)}>
                        匯入 setup-token
                      </button>
                    </div>
                  </div>
                )}
                {provider === "openai" && (
                  <div className="credential-add-box oauth-import-box">
                    <p className="muted tiny" style={{ marginBottom: 8 }}>
                      登入 ChatGPT 訂閱（OpenAI subscription）。<strong>這不是 OpenAI API key。</strong>
                      這是<strong>ChatGPT backend 相容路徑</strong>（非公開 OpenAI API host；Research 啟用前會用實測確認 backend 行為）。
                      Token 會存入本機 token-store/keyring，credential DB 只保存 metadata。
                    </p>
                    {!oauth && (
                      <>
                        <label className="credential-add-toggle">
                          <input
                            type="checkbox"
                            checked={chatgptLoginActive}
                            onChange={(e) => setOauthMakeActive((prev) => ({ ...prev, openai: e.target.checked }))}
                          />
                          <span>登入後設為 active</span>
                        </label>
                        <p className="muted tiny">
                          AI 研究、卡片合成與翻譯會依 active credential 使用 ChatGPT 訂閱後端；
                          可見模型仍須用任務內的實際測試確認。預設不設為 active——登入不應悄悄切換使用中的 credential。
                        </p>
                        <button
                          type="button"
                          className="btn-ghost small"
                          disabled={pollBusy}
                          onClick={() => void startChatGPTLogin(chatgptLoginActive)}
                        >
                          {pollBusy ? "登入中…" : "登入 ChatGPT"}
                        </button>
                      </>
                    )}
                    {oauth?.phase === "waiting" && (
                      <div>
                        <p className="muted tiny">等待瀏覽器登入完成…（已開新分頁）</p>
                        <button type="button" className="btn-ghost small" onClick={() => void copyLoginLink()}>
                          複製登入連結
                        </button>
                        <button
                          type="button"
                          className="btn-ghost small"
                          onClick={() => setOauth((o) => (o ? { ...o, phase: "manual" } : o))}
                        >
                          沒有自動返回？手動貼上授權碼
                        </button>
                      </div>
                    )}
                    {oauth?.phase === "manual" && (
                      <div>
                        <p className="muted tiny">
                          只在瀏覽器已完成登入、但本機 callback 沒收到時使用。貼上授權碼或整個回呼網址：
                        </p>
                        <label className="field">
                          <span>授權碼／回呼網址</span>
                          <input
                            value={manualValue}
                            autoComplete="off"
                            placeholder="code 或 http://localhost:1455/auth/callback?code=…"
                            onChange={(e) => setManualValue(e.target.value)}
                          />
                        </label>
                        <button
                          type="button"
                          className="btn-ghost small"
                          disabled={manualBusy}
                          onClick={() => void completeChatGPTManual()}
                        >
                          {manualBusy ? "完成中…" : "完成登入"}
                        </button>
                        <button type="button" className="btn-ghost small" onClick={cancelChatGPTLogin}>
                          取消
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </SetupDisclosure>
              <div className="provider-links">
                {sourceUrls.map((url) => (
                  <a key={url} href={url} target="_blank" rel="noreferrer">
                    official source
                  </a>
                ))}
              </div>
              <p className="muted tiny">
                可在此新增本機 API key credential（存於本機 profile DB）；env/config/.env 與 key pool 為唯讀來源。
                {provider === "anthropic"
                  ? " Claude setup-token 可由上方匯入（token 存 token-store/keyring，不進 credential DB）。"
                  : " OpenAI ChatGPT 訂閱可由上方「登入 ChatGPT」（token 存 token-store/keyring，不進 credential DB）。"}
              </p>
            </div>
          );
        })}
      </div>
    </>
  );
}

export function SetupDisclosure({
  provider,
  open,
  onOpenChange,
  children,
}: {
  provider: ModelProvider;
  open: boolean;
  onOpenChange: (provider: ModelProvider, open: boolean) => void;
  children?: ReactNode;
}) {
  return (
    <details
      className="cred-setup"
      open={open}
      onToggle={(e) => {
        const nextOpen = e.currentTarget.open;
        onOpenChange(provider, nextOpen);
      }}
    >
      <summary>＋ 新增 API key 或登入訂閱</summary>
      {children}
    </details>
  );
}

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

function ModelNotes({
  models,
  selected,
  custom,
}: {
  models: ModelOption[];
  selected: string;
  custom: boolean;
}) {
  if (custom) {
    return (
      <p className="muted tiny">
        這個 model id 不在 seed catalog；請用 Providers 的 discovery/test 確認此 credential 是否可用。
      </p>
    );
  }
  const model = models.find((m) => m.id === selected);
  if (!model) return null;
  return (
    <div className="model-note">
      <span>{model.speed} speed</span>
      <span>{model.cost_tier} cost</span>
      <span>verified {model.verified_at}</span>
      <p>{model.notes}</p>
    </div>
  );
}

export function CredentialList({
  credentials,
  renames,
  metadataDrafts,
  onRenameDraft,
  onMetadataDraft,
  onSaveCredentialDetails,
  onSetActive,
  onDelete,
  onDiscover,
  discoverLoadingId,
  onRelogin,
  reloginBusy,
}: {
  credentials: ProviderCredential[];
  renames: Record<string, string>;
  metadataDrafts: Record<string, CredentialMetadataDraft>;
  onRenameDraft: (id: string, alias: string) => void;
  onMetadataDraft: (id: string, field: keyof CredentialMetadataDraft, value: string) => void;
  onSaveCredentialDetails: (id: string, alias: string, accountLabel: string, expiresAt?: string) => void;
  onSetActive: (id: string) => void;
  onDelete: (id: string) => void;
  onDiscover: (id: string) => void;
  discoverLoadingId: string | null;
  // S3 re-login (chatgpt_oauth rows only — scope ruling): replace the row's
  // token in place. Optional so existing render sites stay valid.
  onRelogin?: (id: string) => void;
  reloginBusy?: boolean;
}) {
  // Per-row probe state (claude_code_oauth only). Local — the probe result is
  // ephemeral and never leaves this view.
  const [probing, setProbing] = useState<string | null>(null);
  const [probeResults, setProbeResults] = useState<Record<string, ProbeResponse | { error: string }>>({});

  async function runProbe(id: string) {
    setProbing(id);
    // clear any stale result; the `probing` state drives the loading label
    setProbeResults((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
    try {
      const res = await probeCredential(id);
      setProbeResults((prev) => ({ ...prev, [id]: res }));
    } catch (e) {
      setProbeResults((prev) => ({ ...prev, [id]: { error: e instanceof Error ? e.message : String(e) } }));
    } finally {
      setProbing(null);
    }
  }

  return (
    <div className="credential-list">
      {credentials.map((cred) => {
        const isLocalOAuth =
          cred.id.startsWith("local:") &&
          (cred.auth_type === "claude_code_oauth" || cred.auth_type === "chatgpt_oauth");
        const probe = probeResults[cred.id];
        const metadataDraft = metadataDrafts[cred.id] ?? {};
        const showExpiry = supportsCredentialExpiry(cred.auth_type);
        const aliasDraft = renames[cred.id] ?? cred.label;
        const accountLabelDraft = metadataDraft.account_label ?? cred.account_label ?? "";
        // The expiry draft holds the date-picker's native YYYY-MM-DD form; convert
        // the stored ISO for display, and back to a canonical ISO on save.
        const expiresAtDraft = metadataDraft.expires_at ?? isoToDateInput(cred.expires_at);
        return (
          <div className="credential-row" key={cred.id}>
            <div>
              <strong>{cred.label}</strong>
              {cred.account_label && <span>帳號／方案：{cred.account_label}</span>}
              {showExpiry && cred.expires_at && <span>到期：{formatSystemTimestamp(cred.expires_at)}</span>}
              {cred.active && <span className="active-badge">使用中</span>}
              <span>{cred.auth_type}</span>
            </div>
            <span className={`key-pill credential-status-pill ${cred.available ? "ok" : "missing"}`}>
              {credentialAvailabilityText(cred)}
            </span>
            <p className="muted tiny">
              {cred.id.startsWith("local:")
                ? "本機 Settings credential（profile DB · 可編輯、可設為 active）"
                : ".env／環境變數 fallback（唯讀；DB credential 才是主要選擇面）"}
            </p>
            <p>{cred.notes}</p>
            {(cred.editable || cred.can_discover_models) && (
              <div className="credential-actions">
                {cred.editable && (
                  <>
                    <input
                      value={aliasDraft}
                      onChange={(e) => onRenameDraft(cred.id, e.target.value)}
                      aria-label={`${cred.label} alias`}
                      placeholder="必填；留空則保留原名稱"
                    />
                    <button
                      type="button"
                      className="btn-ghost small"
                      disabled={cred.active}
                      onClick={() => onSetActive(cred.id)}
                    >
                      設為 active
                    </button>
                  </>
                )}
                {cred.editable && (
                  <div className="credential-actions credential-metadata-actions">
                    <input
                      value={accountLabelDraft}
                      placeholder={showExpiry ? "帳號／方案標籤（可留空）" : "帳號／用途標籤（可留空）"}
                      aria-label={`${cred.label} account label`}
                      onChange={(e) => onMetadataDraft(cred.id, "account_label", e.target.value)}
                    />
                    {showExpiry && (
                      <input
                        type="date"
                        value={expiresAtDraft}
                        aria-label={`${cred.label} expires at`}
                        title="到期日（可留空）"
                        onChange={(e) => onMetadataDraft(cred.id, "expires_at", e.target.value)}
                      />
                    )}
                    <button
                      type="button"
                      className="btn-ghost small"
                      onClick={() =>
                        onSaveCredentialDetails(
                          cred.id,
                          aliasDraft,
                          accountLabelDraft,
                          showExpiry ? dateInputToIso(expiresAtDraft) : undefined,
                        )
                      }
                    >
                      儲存顯示資訊
                    </button>
                  </div>
                )}
                {cred.can_discover_models && (
                  <button
                    type="button"
                    className="btn-ghost small"
                    disabled={discoverLoadingId === cred.id}
                    title={
                      cred.auth_type === "claude_code_oauth"
                        ? "查看候選模型（seed，非即時 discovery）"
                        : "列出此 credential 後端可見的模型"
                    }
                    onClick={() => onDiscover(cred.id)}
                  >
                    {discoverLoadingId === cred.id ? "讀取中…" : discoverButtonLabel(cred.auth_type)}
                  </button>
                )}
                {cred.auth_type === "chatgpt_oauth" && onRelogin && (
                  <button
                    type="button"
                    className="btn-ghost small"
                    disabled={reloginBusy}
                    title="以此列身分重新登入 ChatGPT，原地更換 token（不新增 credential；alias／active 保留）"
                    onClick={() => onRelogin(cred.id)}
                  >
                    重新登入
                  </button>
                )}
                {isLocalOAuth && (
                  <button
                    type="button"
                    className="btn-ghost small"
                    disabled={probing === cred.id}
                    title={
                      cred.auth_type === "chatgpt_oauth"
                        ? "實測 ChatGPT OAuth backend"
                        : "測試 Claude setup-token"
                    }
                    onClick={() => void runProbe(cred.id)}
                  >
                    {probing === cred.id
                      ? "測試中…"
                      : cred.auth_type === "chatgpt_oauth"
                        ? "實測 OAuth"
                        : "測試 token"}
                  </button>
                )}
                {cred.editable && (
                  <button
                    type="button"
                    className="btn-ghost small danger"
                    onClick={() => {
                      if (window.confirm(`刪除 ${cred.label}？`)) onDelete(cred.id);
                    }}
                  >
                    刪除
                  </button>
                )}
              </div>
            )}
            {probe && <ProbeResultView probe={probe} authType={cred.auth_type} />}
          </div>
        );
      })}
    </div>
  );
}

function ProbeResultView({
  probe,
  authType,
}: {
  probe: ProbeResponse | { error: string };
  authType: ProviderCredential["auth_type"];
}) {
  if ("error" in probe) {
    return <p className="error-text tiny">probe 失敗：{probe.error}</p>;
  }
  const note = probeRuntimeNote(authType);
  return (
    <div className="probe-result">
      <p className={probe.passed ? "ok-text tiny" : "warn-text tiny"}>
        {probe.passed ? "✓ OAuth 驗證通過" : "✗ OAuth 驗證未通過"}
      </p>
      {note && <p className="probe-note tiny">{note}</p>}
      <ul className="probe-list">
        {probe.probes.map((p) => {
          const summary = probeDisplaySummary(p);
          return (
            <li key={p.name} className="tiny">
              <span className={p.passed ? "ok-text" : "warn-text"}>{p.passed ? "✓" : "✗"}</span>
              <span className="probe-label">{probeDisplayLabel(p.name)}</span>
              <span className="probe-summary">{summary.text}</span>
              {summary.models.length > 0 && (
                <span className="probe-models">
                  {summary.models.map((model) => (
                    <code key={model}>{model}</code>
                  ))}
                </span>
              )}
              <details className="probe-detail">
                <summary>細節</summary>
                <div>expected: {p.expected}</div>
                <div>observed: {p.observed}</div>
                {p.error && <div>error: {p.error}</div>}
              </details>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function DiscoveryResultView({
  result,
  authMode,
  credentialLabel,
  onClose,
  onUse,
  onRelogin,
  reloginBusy,
}: {
  result: ModelDiscoveryResult;
  authMode: ProviderCredential["auth_type"] | null;
  credentialLabel: string | null;
  onClose: () => void;
  onUse: (model: string, task: ModelTask) => void;
  // S3: when the failure is machine-classified as reauth_required, offer the
  // in-place re-login right where the error is shown. Optional (old sites OK).
  onRelogin?: () => void;
  reloginBusy?: boolean;
}) {
  const [query, setQuery] = useState("");
  const models = result.models.filter((model) =>
    model.id.toLowerCase().includes(query.trim().toLowerCase()),
  );
  // Source badge: the credential/auth_mode decides whether these are a LIVE backend
  // list (and WHICH backend — OpenAI API vs ChatGPT, both 'provider_api' at the data
  // layer) or seed CANDIDATES — never imply a global catalog (§11).
  const sources = Array.from(new Set(result.models.map((m) => m.source)));
  const sourceBadge =
    sources.length === 1
      ? discoverySourceLabel(result.provider, authMode, sources[0])
      : sources.join(" / ");
  const credentialSummary = discoveryResultCredentialLabel(
    authMode ? { label: credentialLabel ?? "未命名 credential", auth_type: authMode } : null,
  );
  return (
    <div className="discovery-box">
      <div className="discovery-head">
        <div>
          <strong>{discoveryHeaderTitle(authMode)} · {result.status}</strong>
          <span className="discovery-credential tiny">{credentialSummary}</span>
        </div>
        {result.models.length > 0 && <span className="source-badge tiny">{sourceBadge}</span>}
        {result.source_url && (
          <a href={result.source_url} target="_blank" rel="noreferrer">
            source
          </a>
        )}
        <button type="button" className="btn-ghost tiny" onClick={onClose}>
          關閉
        </button>
      </div>
      {result.error && <p className="warn-text tiny">{result.error}</p>}
      {result.error_code === "reauth_required" && onRelogin && (
        <div className="reauth-hint">
          <span className="warn-text tiny">token 已失效——需要重新登入。</span>
          <button type="button" className="btn-ghost small" disabled={reloginBusy} onClick={onRelogin}>
            重新登入
          </button>
        </div>
      )}
      <label className="field discovery-filter">
        <span>搜尋模型</span>
        <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="gpt / claude / mini…" />
      </label>
      <div className="discovery-models">
        {models.map((model) => (
          <div className="model-discovery-row" key={model.id}>
            <span>{model.id}</span>
            <button type="button" className="btn-ghost small" onClick={() => onUse(model.id, "card_synthesis")}>
              用於生成
            </button>
            <button type="button" className="btn-ghost small" onClick={() => onUse(model.id, "card_translation")}>
              用於翻譯
            </button>
          </div>
        ))}
      </div>
      <p className="muted tiny">
        顯示 {models.length} / {result.models.length} 個 provider 回傳模型；任務頁仍可直接輸入任何 model id。
      </p>
    </div>
  );
}
