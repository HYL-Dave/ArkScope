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
  deleteResearchRuntime,
  putProviderConfig,
  putSchedule,
  runScheduleNow,
  saveResearchRuntime,
  saveModelRoutes,
  testProvider,
  getMacroStatus,
  getMacroSnapshot,
  setUseLocalNews,
  setNormalizedNewsWrites,
  getNewsStatus,
  getTradingDayCoverage,
  previewAppRecordsMigration,
  applyAppRecordsMigration,
  type AppRecordsMigrationPreview,
  type AppRecordsMigrationResult,
  testModelAccess,
  updateCredential,
  type MarketDataStatus,
  type MacroSnapshot,
  type MacroSnapshotItem,
  type MacroStatus,
  type NewsStatus,
  type TradingDayCoverage,
  type TradingDayRow,
  type ProviderConfigEntry,
  type ProviderEnvFallbackState,
  type ProviderConfigField,
  type ProviderConfigSetupState,
  type ProviderHealth,
  type ProvidersHealthResponse,
  type SAExtensionHealthResponse,
  type ScheduleSourceState,
  type SyncMeta,
  type ModelCatalog,
  type EffectiveTaskModels,
  type ModelDiscoveryResult,
  type ModelOption,
  type ModelProvider,
  type ModelTestResult,
  type ModelTask,
  type ProviderCredential,
  type ResearchRuntimeSettings,
  type RuntimeConfig,
  type TaskRoute,
} from "./api";
import { MODEL_OPTION_CUSTOM, decodeModelOption, encodeModelOption, inferProvider } from "./modelSelect";
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
  macroRoutingLabel,
  marketRoutingLabel,
  newsPostgresRouteLabel,
  newsReadSurfaceLabel,
  newsRoutingLabel,
  newsWriteRouteLabel,
  providerHealthStatusLabel,
  schedulerStateLabel,
} from "./marketDataDisplay";
import { displaySAExtensionSegments } from "./saExtensionHealthDisplay";
import { InvestorProfilePanel } from "./InvestorProfilePanel";

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
    description: "本地市場庫（價格＋新聞＋IV＋基本面）狀態；PG mirror routes 已退役。",
    enabled: true,
  },
  {
    id: "news_storage",
    title: "News Ingestion",
    description: "新聞寫入路由、PostgreSQL exit 狀態與 direct telemetry。",
    enabled: true,
  },
  {
    id: "macro_storage",
    title: "Macro / Calendar",
    description: "本地總經＋行事曆庫（FRED 序列、經濟／財報／IPO 行事曆）；資料由 FRED/Finnhub 抓取。",
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

interface DraftRoute {
  provider: ModelProvider;
  model: string;
  effort: string;
  custom: boolean;
}

type DiscoveryState = Partial<Record<ModelProvider, {
  loading: boolean;
  result: ModelDiscoveryResult | null;
  credentialId: string | null;
}>>;

type TestState = Partial<Record<ModelTask, {
  loading: boolean;
  result: ModelTestResult | null;
}>>;

type CredentialMetadataDraft = {
  account_label?: string;
  expires_at?: string;
};

export function SettingsView({
  runtime,
  onRuntimeChanged,
}: {
  runtime: RuntimeConfig | null;
  onRuntimeChanged: () => Promise<void>;
}) {
  const [catalog, setCatalog] = useState<ModelCatalog | null>(null);
  const [draft, setDraft] = useState<Partial<Record<ModelTask, DraftRoute>>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [section, setSection] = useState<SettingsSection>("models");
  const [discovery, setDiscovery] = useState<DiscoveryState>({});
  const [testState, setTestState] = useState<TestState>({});

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

  async function save() {
    if (!catalog) return;
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
          <button className="btn-ghost" onClick={() => void save()} disabled={saving || loading || !catalog}>
            {saving ? "儲存中…" : "儲存路由"}
          </button>
        </div>
      </div>

      {err && <p className="error-text">{err}</p>}
      {msg && <p className="ok-text">{msg}</p>}

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
                    setTestState((prev) => ({ ...prev, [task]: { loading: true, result: null } }));
                    try {
                      const result = await testModelAccess(row.provider, row.model.trim(), row.effort || "default");
                      setTestState((prev) => ({ ...prev, [task]: { loading: false, result } }));
                    } catch (e) {
                      setTestState((prev) => ({
                        ...prev,
                        [task]: {
                          loading: false,
                          result: {
                            provider: row.provider,
                            credential_id: null,
                            model: row.model,
                            effort: row.effort || "default",
                            status: "error",
                            latency_ms: null,
                            error: e instanceof Error ? e.message : String(e),
                            warning: null,
                            fallback_effort: null,
                          },
                        },
                      }));
                    }
                  }}
                  onReset={async (task) => {
                    setErr(null);
                    setMsg(null);
                    try {
                      await deleteModelRoute(task);
                      const refreshed = await getModelCatalog();
                      setCatalog(refreshed);
                      setDraft(fromRoutes(refreshed.routes));
                      await onRuntimeChanged();
                      setMsg(`${TASK_LABELS[task]} 已重設為設定檔／內建預設。`);
                    } catch (e) {
                      setErr(e instanceof Error ? e.message : String(e));
                    }
                  }}
                />
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
                  await onRuntimeChanged();
                }}
                onDiscover={async (provider, credentialId) => {
                  setDiscovery((prev) => ({
                    ...prev,
                    [provider]: { loading: true, result: null, credentialId },
                  }));
                  try {
                    const result = await discoverModels(provider, credentialId);
                    setDiscovery((prev) => ({
                      ...prev,
                      [provider]: { loading: false, result, credentialId },
                    }));
                    // MF2: the discovery run just updated the entitlement cache —
                    // refetch the catalog so the effective picker leaves
                    // never_discovered without an app reload.
                    try {
                      setCatalog(await getModelCatalog());
                    } catch {
                      // catalog refresh is best-effort; discovery result already shown
                    }
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
                }}
                onClearDiscovery={(provider) => {
                  setDiscovery((prev) => {
                    const next = { ...prev };
                    delete next[provider];
                    return next;
                  });
                }}
                onUseModel={(provider, model, task) => {
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
          <h2>本地市場資料庫 · Market Data</h2>
          <p className="muted tiny">
            市場資料現在以本地 SQLite 為權威。價格與新聞由 Data Sources 的 per-source scheduler 直寫本地；
            PG mirror bootstrap / update / validation route 已退役，缺資料時不會 fallback 回 PG。
            財務快取為 local-primary；Seeking Alpha capture 已切到本地 SQLite。
            最新資料時間沿用來源欄位；同步／抓取時間顯示本機時區 + 美股 ET 對照。
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
            <dt>本地市場庫</dt>
            <dd>{exists ? "已建立" : "尚未建立"}</dd>
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
                ? `${fc!.row_count.toLocaleString()} 列（有效 ${fc!.valid_count} · 過期 ${fc!.expired_count}）· 最新抓取 ${formatSystemTimestamp(fc!.latest_fetched_at)}（local-primary，不對 PG 驗證）`
                : "—"}
            </dd>
            <dt>最近增量更新</dt>
            <dd>{syncLine(status)}</dd>
            <dt>本地路由</dt>
            <dd>
              {marketRoutingLabel(status)}
              {status.env_override && "（env 強制開啟）"}
              {status.strict_enabled && status.strict_env_override && "（strict env 強制開啟）"}
            </dd>
          </dl>

          <div className="settings-actions" style={{ marginTop: 12 }}>
            <span className="ds-chip ds-connected">local authority</span>
            <span className="muted tiny">
              PG mirror bootstrap / update / validation routes are retired. Price and news ingestion now run from Data Sources.
            </span>
          </div>
        </div>
      )}

      <TradingDayCoveragePanel />
    </div>
  );
}

function NewsStorageSection() {
  const [status, setStatus] = useState<NewsStatus | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

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

  async function toggleLocalNews(enabled: boolean) {
    if (busy || status?.env_override || status?.news_hard_local) return;
    setBusy(true);
    setErr(null);
    try {
      await setUseLocalNews(enabled);
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function toggleNormalizedWrites(enabled: boolean) {
    if (busy || status?.normalized_writes_env_override || status?.news_hard_local) return;
    setBusy(true);
    setErr(null);
    try {
      await setNormalizedNewsWrites(enabled);
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

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
          <h2>新聞本地狀態 · News Ingestion</h2>
          <p className="muted tiny">
            Polygon／Finnhub／IBKR 新聞由 Data Sources 排程直寫 normalized SQLite，並投影到 legacy local
            讀取面直到 N8b 完成。不再經 news PG sync／mirror；此頁只顯示本地新聞庫與 PG exit 狀態。
          </p>
        </div>
        <button className="btn-ghost" onClick={() => void load()} disabled={busy}>↻ 重新整理</button>
      </div>

      {err && <div className="errorbox"><p className="muted">{err}</p></div>}

      {!status ? (
        <p className="muted">載入中…</p>
      ) : (
        <div className="settings-panel">
          <dl className="ds-kv">
            <dt>本地新聞庫</dt>
            <dd>
              {status.exists
                ? `${status.news.row_count.toLocaleString()} 篇 · ${status.news.source_count} 來源 · 最新 ${status.news.latest_published ?? "—"}`
                : "尚未建立"}
            </dd>
            {status.news_hard_local ? (
              <>
                <dt>新聞寫入</dt>
                <dd>{newsWriteRouteLabel(status)}</dd>
                <dt>PostgreSQL</dt>
                <dd>{newsPostgresRouteLabel(status)}</dd>
                <dt>新聞讀取</dt>
                <dd>{newsReadSurfaceLabel(status)}</dd>
              </>
            ) : (
              <>
                <dt>Legacy local 直寫</dt>
                <dd>{newsRoutingLabel(status)}</dd>
                <dt>Normalized 寫入測試</dt>
                <dd>
                  {status.normalized_writes_env_override
                    ? status.normalized_writes_env_value
                      ? "開啟（env 強制）"
                      : "關閉（env 強制）"
                    : status.normalized_writes_setting
                      ? "開啟（pre-exit test）"
                      : "關閉"}
                </dd>
                <dt>目前新聞寫入</dt>
                <dd>{newsWriteRouteLabel(status)}</dd>
                <dt>PostgreSQL</dt>
                <dd>{newsPostgresRouteLabel(status)}</dd>
              </>
            )}
            <dt>最近 direct 成功</dt>
            <dd>{formatSystemTimestamp(sync?.last_success)}</dd>
            <dt>最近 direct 嘗試</dt>
            <dd>{formatSystemTimestamp(sync?.last_attempt)}</dd>
            <dt>Direct 狀態</dt>
            <dd>{sync?.status ?? "尚未執行"}</dd>
            <dt>最近錯誤</dt>
            <dd className={providerErrors ? "refresh-err" : undefined}>{providerErrors || sync?.last_error || "—"}</dd>
          </dl>

          {!status.news_hard_local && (
            <div className="settings-actions" style={{ marginTop: 12 }}>
              <label className="ds-toggle">
                <input
                  type="checkbox"
                  checked={status.env_override ? status.direct_active : status.use_local_news_setting}
                  disabled={busy || status.env_override}
                  onChange={(e) => void toggleLocalNews(e.target.checked)}
                />
                Legacy local writer（pre-exit）
              </label>
              <label className="ds-toggle">
                <input
                  type="checkbox"
                  checked={
                    status.normalized_writes_env_override
                      ? !!status.normalized_writes_env_value
                      : status.normalized_writes_setting
                  }
                  disabled={busy || status.normalized_writes_env_override}
                  onChange={(e) => void toggleNormalizedWrites(e.target.checked)}
                />
                Normalized news writes（測試）
              </label>
            </div>
          )}

          {status.env_override && !status.news_hard_local && (
            <p className="muted tiny" style={{ marginTop: 8 }}>
              目前由 ARKSCOPE_USE_LOCAL_NEWS 環境變數強制控制；移除 env override 後才能由此開關變更。
            </p>
          )}
          {status.normalized_writes_env_override && !status.news_hard_local && (
            <p className="muted tiny" style={{ marginTop: 8 }}>
              目前由 ARKSCOPE_USE_NORMALIZED_NEWS_WRITES 環境變數強制控制；移除 env override 後才能由此開關變更。
            </p>
          )}
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
            最近 {lookback} 天本地 15min 價格覆蓋（讀 market_data.db）。每列以 coverage_status 為準：
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
          <h2>本地總經／行事曆庫 · Macro / Calendar</h2>
          <p className="muted tiny">
            把 FRED 總經序列（含 ALFRED vintage 還原時點）與經濟／財報／IPO 行事曆存到本地 SQLite（macro_calendar.db）。
            Macro / Calendar is local-only in the app；資料由 FRED／Finnhub 抓取的 job 填入，非 PG 鏡像。
            觀測值的 realtime_start 取 FRED 首次發布日（output_type=4），lookahead-safe。
            注意：經濟行事曆需 Finnhub 付費方案（目前 403）；財報行事曆待節流批次抓取。
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
            <dt>本地總經庫</dt>
            <dd>{exists ? `已建立 · ${seriesCount} 序列 · ${totalObs} 觀測值` : "尚未建立"}</dd>
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
            <dt>本地路由</dt>
            <dd>
              {macroRoutingLabel(status)}
            </dd>
          </dl>

          <p className="muted tiny" style={{ marginTop: 12 }}>
            Macro / Calendar is local-only in the app. FRED/Finnhub jobs populate macro_calendar.db;
            when disabled or empty, reads return honest empty results rather than PG fallback.
          </p>

          {status.local_first_active && !exists && (
            <p className="muted tiny" style={{ marginTop: 8 }}>
              讀寫即走本地，macro_calendar.db 會在首次使用時自動建立；未經 FRED／Finnhub
              ingestion 填入前本地查詢回空（不會 fallback 回 PG）。
            </p>
          )}
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
      `本地快照可用：${formatCount(snap.series_count)} 序列 · ${formatCount(snap.observation_count)} 觀測值`,
    );
  } else {
    parts.push("本地快照尚無資料");
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

function DataSourcesSection() {
  const [schedule, setSchedule] = useState<Record<string, ScheduleSourceState> | null>(null);
  const [health, setHealth] = useState<ProvidersHealthResponse | null>(null);
  const [macroSnapshot, setMacroSnapshot] = useState<MacroSnapshot | null>(null);
  const [saExtensionHealth, setSaExtensionHealth] = useState<SAExtensionHealthResponse | null>(null);
  const [cfg, setCfg] = useState<Record<string, ProviderConfigEntry> | null>(null);
  const [cfgSetup, setCfgSetup] = useState<ProviderConfigSetupState | null>(null);
  const [cfgEnvFallback, setCfgEnvFallback] = useState<ProviderEnvFallbackState | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState<string>(""); // source id with an in-flight mutation
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [keyDrafts, setKeyDrafts] = useState<Record<string, string>>({}); // "provider.field"
  const [testResults, setTestResults] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    const [rs, rh, rc, rm] = await Promise.allSettled([
      getSchedule(), getProvidersHealth(), getProvidersConfig(), getMacroSnapshot()]);
    if (rs.status === "fulfilled") setSchedule(rs.value.sources);
    if (rh.status === "fulfilled") setHealth(rh.value);
    if (rc.status === "fulfilled") {
      setCfg(rc.value.providers);
      setCfgSetup(rc.value.setup);
      setCfgEnvFallback(rc.value.env_fallback);
    }
    if (rm.status === "fulfilled") setMacroSnapshot(rm.value);
    const bad = [rs, rh, rc, rm].filter((r): r is PromiseRejectedResult => r.status === "rejected");
    setErr(bad.length
      ? bad.map((r) => (r.reason instanceof Error ? r.reason.message : String(r.reason))).join("；")
      : null);
  }, []);

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

  // Run-now / scheduled runs flip `running` server-side — poll while any is active.
  const anyRunning = !!schedule && Object.values(schedule).some((s) => s.running);
  useEffect(() => {
    if (!anyRunning) return;
    const t = window.setInterval(() => void load(), 5_000);
    return () => window.clearInterval(t);
  }, [anyRunning, load]);

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
    if (skippedReason) {
      details.push({
        label: alreadyRunningSkip ? "新觸發略過" : "跳過原因",
        value: skippedReason,
        tone: "warn",
      });
    }
    const ss = schedulerStateLabel(s.durable_state ?? null);
    const durableError = s.durable_state?.last_status === "failed" ? s.durable_state.last_error : null;
    if (durableError) details.push({ label: "失敗訊息", value: durableError, tone: "bad" });

    return (
      <div className="ds-last-run">
        <div className="ds-last-run-summary">
          <span>{jobOutcome(s.job_name)}</span>
          {skippedReason && (
            <span className="refresh-err" title={skippedReason}>
              {alreadyRunningSkip ? "新觸發已略過" : "已跳過"}：{skippedSummary}
            </span>
          )}
          {s.durable_state?.last_status && (
            <span style={{ color: coverageToneColor(ss.tone) }} title={durableError ?? ss.label}>
              {ss.label}{durableError ? `：${compactMessage(durableError)}` : ""}
            </span>
          )}
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
            App 直接發起資料抓取（免 cron）。每個來源獨立排程：自己的開關與間隔、平行執行
            （IBKR 項目共用 Gateway 鎖序列化；同一輪最多啟動一個本地市場 DB 寫入者）。
            一次執行＝抓取並直寫本地 SQLite（股價與新聞皆為 direct-local，已無 PG 同步／鏡像）。
            預設全部停用。
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
          <table className="data-table">
            <thead>
              <tr><th>Provider</th><th>狀態</th><th>金鑰</th><th>最近成功</th><th>最近錯誤</th></tr>
            </thead>
            <tbody>
              {health.providers.map((p) => (
                <tr key={p.id}>
                  <td title={p.detail}>
                    {p.label}
                    {fredProviderDetail(p) && (
                      <div className="muted tiny">{fredProviderDetail(p)}</div>
                    )}
                  </td>
                  <td><span className={`ds-chip ds-${p.status}`}>{providerHealthStatusLabel(p)}</span></td>
                  <td>
                    {p.key_source === "not_required" ? "免金鑰" : p.key_source}
                    {p.key_import_suggested && <span className="muted tiny"> · 建議匯入</span>}
                  </td>
                  <td>{shortTs(p.last_success_at)}</td>
                  <td className="muted">{p.last_error ? p.last_error.slice(0, 60) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="settings-panel" style={{ marginTop: 16 }}>
        <div className="settings-panel-head">
          <div>
            <h4 className="detail-section">SA Extension 健康</h4>
            <p className="muted tiny">
              Firefox/Chrome extension → native host → sidecar telemetry → 本地 SA DB 的分段檢查。
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
            <table className="data-table" style={{ tableLayout: "fixed", width: "100%" }}>
              <thead>
                <tr><th>段落</th><th>狀態</th><th>細節</th></tr>
              </thead>
              <tbody>
                {displaySAExtensionSegments(saExtensionHealth.segments).map((row) => (
                  <tr key={row.key}>
                    <td>{row.label}</td>
                    <td>
                      <span className={`ds-chip ds-${row.tone === "ok" ? "connected" : row.tone === "warn" ? "stale" : "disabled"}`}>
                        {row.mark}
                      </span>
                    </td>
                    <td className="muted" style={{ overflowWrap: "anywhere" }}>{row.detail}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </div>

      <div className="settings-panel" style={{ marginTop: 16 }}>
        <h4 className="detail-section">FRED 本地快照</h4>
        {!macroSnapshot ? (
          <p className="muted tiny">loading…</p>
        ) : (
          <>
            <p className="muted tiny">
              {macroSnapshot.available
                ? `${formatCount(macroSnapshot.series_count)} 序列 · ${formatCount(macroSnapshot.observation_count)} 觀測值 · 最後抓取 ${shortDate(macroSnapshot.latest_fetched_at)} · 自動刷新${macroSnapshot.auto_refresh_enabled ? "開啟" : "關閉"}`
                : `尚無本地快照 · 自動刷新${macroSnapshot.auto_refresh_enabled ? "開啟" : "關閉"}`}
            </p>
            {macroSnapshot.items.length > 0 ? (
              <table className="data-table" style={{ tableLayout: "fixed", width: "100%" }}>
                <thead>
                  <tr><th>指標</th><th>值</th><th>觀測日</th><th>抓取時間</th></tr>
                </thead>
                <tbody>
                  {macroSnapshot.items.slice(0, 11).map((item) => (
                    <tr key={item.series_id}>
                      <td style={{ overflowWrap: "anywhere" }}>
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
            ) : (
              <p className="muted tiny">本地 macro_calendar.db 尚無可顯示的 FRED 觀測值。</p>
            )}
          </>
        )}
      </div>

      <div className="settings-panel" style={{ marginTop: 16 }}>
        <h4 className="detail-section">連線與金鑰</h4>
        <p className="muted tiny">
          App 管理各 provider 的金鑰與連線設定（存本地、僅顯示遮罩值）。真實環境變數仍可作為 operator escape hatch；
          config/.env 只作為逐欄匯入來源。儲存即生效（毋須重啟）。
        </p>
        {cfgEnvFallback && (
          <p className="muted tiny">
            Provider runtime policy：
            {cfgEnvFallback.enabled
              ? ` legacy config/.env fallback enabled（${cfgEnvFallback.source}）`
              : ` strict DB-first（${cfgEnvFallback.source}）`}
          </p>
        )}
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
          <table className="data-table ds-config">
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
        )}
      </div>

      <div className="settings-panel" style={{ marginTop: 16 }}>
        <h4 className="detail-section">排程（每來源獨立）</h4>
        {!schedule ? (
          <p className="muted tiny">loading…</p>
        ) : (
          <table className="data-table ds-schedule">
            <thead>
              <tr>
                <th>來源</th><th>排程</th><th>間隔（分）</th><th>立即執行</th><th>最近一次</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(schedule).map(([id, s]) => (
                <tr key={id}>
                  <td title={s.description}>
                    {s.label}
                    {(s.source_badges ?? []).map((badge) => (
                      <span className="muted tiny" key={badge}> · {badge}</span>
                    ))}
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
                      {s.enabled ? "開" : "關"}
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
                      <span className="ds-chip ds-running">
                        執行中…
                        {s.progress
                          ? ` ${s.progress.done}/${s.progress.total}（${s.progress.current}，${Math.round((s.progress.done / Math.max(1, s.progress.total)) * 100)}%）`
                          : ""}
                      </span>
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
                  <td className="muted tiny ds-last-run-cell">
                    {renderLastRun(id, s)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <p className="muted tiny" style={{ marginTop: 8 }}>
          保護機制：同來源不重疊、IBKR Gateway 序列化、啟動時讀 job_runs 接續（手動剛跑過
          不會立即重抓）— 且鎖為<strong>跨進程</strong>（data/locks/）：app 與 CLI 重疊跑
          同一來源會被跳過（顯示於「最近一次」），不會雙抓。
        </p>
      </div>
    </div>
  );
}

const EFFECTIVE_BADGE_LABELS: Record<string, string> = {
  advanced: "舊版",
  seed: "未驗證 seed",
  custom: "自訂",
  route: "目前路由",
};

// P2.7 verified-first picker: default list = 已驗證可用 (registry ∩ discovery ∩
// executability);其餘 (舊版/seed/自訂/目前路由) 收進「顯示進階模型」。
function EffectiveModelPicker({
  task,
  effective,
  row,
  onDraft,
}: {
  task: ModelTask;
  effective: EffectiveTaskModels;
  row: DraftRoute;
  onDraft: Dispatch<SetStateAction<Partial<Record<ModelTask, DraftRoute>>>>;
}) {
  const [showAdvanced, setShowAdvanced] = useState(false);
  const entries = showAdvanced
    ? [...effective.verified, ...effective.advanced]
    : effective.verified;
  return (
    <div className="field">
      <span>已驗證可用模型</span>
      {effective.cache_state === "never_discovered" && (
        <p className="muted tiny">尚未探索——跑一次模型探索以驗證此 credential 可見的模型。</p>
      )}
      {effective.cache_state === "seed_only" && (
        <p className="muted tiny">此通道無法線上列出模型；以下為 seed 候選（未驗證）。</p>
      )}
      {effective.discovered_at && (
        <p className="muted tiny">最後驗證可見 {effective.discovered_at}</p>
      )}
      <select
        aria-label={`已驗證模型 ${task}`}
        value={entries.some((m) => m.id === row.model) ? row.model : ""}
        onChange={(e) => {
          const id = e.target.value;
          if (!id) return;
          const inferred = inferProvider(id);
          onDraft((prev) => ({
            ...prev,
            [task]: {
              provider: inferred ?? row.provider,
              model: id,
              effort: (inferred ?? row.provider) === row.provider ? row.effort : "default",
              custom: false,
            },
          }));
        }}
      >
        <option value="">選擇模型…</option>
        {entries.map((m) => (
          <option key={m.id} value={m.id}>
            {m.label}
            {m.badge ? ` · ${EFFECTIVE_BADGE_LABELS[m.badge] ?? m.badge}` : ""}
          </option>
        ))}
      </select>
      <label className="muted tiny">
        <input
          type="checkbox"
          aria-label="顯示進階模型"
          checked={showAdvanced}
          onChange={(e) => setShowAdvanced(e.currentTarget.checked)}
        />
        顯示進階模型（舊版 / 未驗證 / 自訂 / 目前路由）
      </label>
    </div>
  );
}


export function ModelRoutingSection({
  catalog,
  draft,
  modelsByProvider,
  testState,
  onDraft,
  onTest,
  onReset,
}: {
  catalog: ModelCatalog;
  draft: Partial<Record<ModelTask, DraftRoute>>;
  modelsByProvider: Record<ModelProvider, ModelOption[]>;
  testState: TestState;
  onDraft: Dispatch<SetStateAction<Partial<Record<ModelTask, DraftRoute>>>>;
  onTest: (task: ModelTask) => Promise<void>;
  onReset: (task: ModelTask) => Promise<void>;
}) {
  return (
    <>
      <div className="settings-section-head">
        <div>
          <h2>任務模型路由</h2>
          <p className="muted">
            這裡控制實際會被 AI card / 翻譯呼叫的模型。可以從 seed/discovery 套用，也可以直接輸入 provider model id。
          </p>
        </div>
      </div>
      <div className="settings-grid">
        {catalog.tasks.map((task) => {
          const row = draft[task.id];
          if (!row) return null;
          const options = modelsByProvider[row.provider];
          const effortOptions = catalog.effort_options[row.provider] ?? [];
          const effective = catalog.routes[task.id];
          const envLocked = effective?.source === "env";
          const currentTest = testState[task.id];
          const taskEffective = catalog.effective?.tasks?.[task.id];
          return (
            <div className="settings-panel" key={task.id} data-testid={`route-${task.id}`}>
              <div className="settings-panel-head">
                <div>
                  <h2>{TASK_LABELS[task.id]}</h2>
                  <p className="muted">{task.description}</p>
                </div>
                <span
                  className={`route-source ${routeSourceBadge(effective?.source ?? "default").tone}`}
                  title={`此路由目前的權威來源：${routeSourceBadge(effective?.source ?? "default").label}`}
                >
                  {routeSourceBadge(effective?.source ?? "default").label}
                </span>
              </div>

              {envLocked && (
                <p className="warn-text">
                  目前由環境變數控制；可以儲存到 DB，但 runtime 仍以 env 為準（不會被 DB 覆蓋）。
                </p>
              )}
              {effective?.warning && <p className="warn-text">{effective.warning}</p>}
              {taskEffective && (
                <EffectiveModelPicker
                  task={task.id}
                  effective={taskEffective}
                  row={row}
                  onDraft={onDraft}
                />
              )}

              {/* MF1: with the effective picker present, the full-seed
                  selector + custom-id input become a collapsed manual override —
                  no default path around verified-first. Without `effective`
                  (older sidecar) they render as before. */}
              {taskEffective ? (
                <details className="field" data-testid={`manual-override-${task.id}`}>
                  <summary className="muted tiny">手動覆寫（全部 seed 模型 / 自訂 id）</summary>
              <label className="field">
                <span>Model</span>
                <select
                  value={row.custom ? MODEL_OPTION_CUSTOM : encodeModelOption(row.provider, row.model)}
                  onChange={(e) => {
                    const v = e.target.value;
                    if (v === MODEL_OPTION_CUSTOM) {
                      // switch to custom-id mode; keep the current provider/model as the starting point
                      onDraft((prev) => ({ ...prev, [task.id]: { ...row, custom: true } }));
                      return;
                    }
                    const dec = decodeModelOption(v);
                    if (!dec) return;
                    onDraft((prev) => ({
                      ...prev,
                      [task.id]: {
                        provider: dec.provider,
                        model: dec.model,
                        // reset effort only when the provider changed (effort sets differ)
                        effort: dec.provider === row.provider ? row.effort : "default",
                        custom: false,
                      },
                    }));
                  }}
                >
                  {catalog.providers.map((p) => (
                    <optgroup key={p} label={p}>
                      {(modelsByProvider[p] ?? []).map((m) => (
                        <option key={`${p}:${m.id}`} value={encodeModelOption(p, m.id)}>
                          {p} · {m.label}
                        </option>
                      ))}
                    </optgroup>
                  ))}
                  <option value={MODEL_OPTION_CUSTOM}>自訂 model id…</option>
                </select>
                <span className="field-help">直接選模型即可，provider 會自動設定；或選「自訂 model id」手動輸入。</span>
              </label>

              {row.custom && (
                <label className="field">
                  <span>自訂 model id</span>
                  <input
                    value={row.model}
                    placeholder={row.provider === "anthropic" ? "claude-…" : "gpt-…"}
                    onChange={(e) => {
                      const value = e.target.value.trim();
                      const inferred = inferProvider(value);
                      onDraft((prev) => ({
                        ...prev,
                        [task.id]: { ...row, provider: inferred ?? row.provider, model: value, custom: true },
                      }));
                    }}
                  />
                  <span className="field-help">
                    由 prefix 自動判斷 provider（gpt-… → openai，claude-… → anthropic）；判斷不出時沿用目前 provider（{row.provider}）。
                  </span>
                </label>
              )}

                </details>
              ) : (
                <>
              <label className="field">
                <span>Model</span>
                <select
                  value={row.custom ? MODEL_OPTION_CUSTOM : encodeModelOption(row.provider, row.model)}
                  onChange={(e) => {
                    const v = e.target.value;
                    if (v === MODEL_OPTION_CUSTOM) {
                      // switch to custom-id mode; keep the current provider/model as the starting point
                      onDraft((prev) => ({ ...prev, [task.id]: { ...row, custom: true } }));
                      return;
                    }
                    const dec = decodeModelOption(v);
                    if (!dec) return;
                    onDraft((prev) => ({
                      ...prev,
                      [task.id]: {
                        provider: dec.provider,
                        model: dec.model,
                        // reset effort only when the provider changed (effort sets differ)
                        effort: dec.provider === row.provider ? row.effort : "default",
                        custom: false,
                      },
                    }));
                  }}
                >
                  {catalog.providers.map((p) => (
                    <optgroup key={p} label={p}>
                      {(modelsByProvider[p] ?? []).map((m) => (
                        <option key={`${p}:${m.id}`} value={encodeModelOption(p, m.id)}>
                          {p} · {m.label}
                        </option>
                      ))}
                    </optgroup>
                  ))}
                  <option value={MODEL_OPTION_CUSTOM}>自訂 model id…</option>
                </select>
                <span className="field-help">直接選模型即可，provider 會自動設定；或選「自訂 model id」手動輸入。</span>
              </label>

              {row.custom && (
                <label className="field">
                  <span>自訂 model id</span>
                  <input
                    value={row.model}
                    placeholder={row.provider === "anthropic" ? "claude-…" : "gpt-…"}
                    onChange={(e) => {
                      const value = e.target.value.trim();
                      const inferred = inferProvider(value);
                      onDraft((prev) => ({
                        ...prev,
                        [task.id]: { ...row, provider: inferred ?? row.provider, model: value, custom: true },
                      }));
                    }}
                  />
                  <span className="field-help">
                    由 prefix 自動判斷 provider（gpt-… → openai，claude-… → anthropic）；判斷不出時沿用目前 provider（{row.provider}）。
                  </span>
                </label>
              )}

                </>
              )}

              <label className="field">
                <span>Effort / thinking</span>
                <select
                  value={row.effort || "default"}
                  onChange={(e) => {
                    onDraft((prev) => ({
                      ...prev,
                      [task.id]: { ...row, effort: e.target.value },
                    }));
                  }}
                >
                  {effortOptions.map((effort) => (
                    <option key={effort.id} value={effort.id}>
                      {effort.label}
                    </option>
                  ))}
                </select>
                <span className="field-help">
                  {effortOptions.find((x) => x.id === (row.effort || "default"))?.description ??
                    "Provider default."}
                </span>
              </label>

              <ModelNotes models={options} selected={row.model} custom={row.custom} />

              <div className="settings-actions">
                <button
                  type="button"
                  className="btn-ghost small"
                  disabled={!row.model.trim() || currentTest?.loading}
                  onClick={() => void onTest(task.id)}
                >
                  {currentTest?.loading ? "測試中…" : "測試此模型"}
                </button>
                {routeIsOverridable(effective?.source ?? "default") && (
                  <button
                    type="button"
                    className="btn-ghost small"
                    title="移除此任務的 DB 路由，改回設定檔／內建預設"
                    onClick={() => void onReset(task.id)}
                  >
                    重設為 fallback
                  </button>
                )}
                {currentTest?.result && <ModelTestStatus result={currentTest.result} />}
              </div>
            </div>
          );
        })}
      </div>
    </>
  );
}

function runtimeSourceBadge(source: ResearchRuntimeSettings["source"]) {
  if (source === "db") return { label: "DB 已儲存", tone: "active" };
  if (source === "env") return { label: "env override", tone: "override" };
  if (source === "profile") return { label: "設定檔 fallback", tone: "fallback" };
  return { label: "內建預設", tone: "default" };
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

function ProviderSection({
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
  // unified default (Claude: active iff no local DB credential; ChatGPT: always off,
  // since its execution is unwired and active = fail-closed Research).
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

  async function startChatGPTLogin(makeActive: boolean) {
    setProviderErr(null);
    setProviderMsg(null);
    setPollBusy(true);
    const token = { aborted: false }; // this login's abort token; manual/cancel flips it
    pollToken.current = token;
    try {
      const r = await startOpenAIOAuth(makeActive);
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
        // surface the backend reason as-is — NO silent fallback to an API key
        setOauth((o) => (o ? { ...o, phase: "manual" } : o));
        setProviderErr(`登入失敗：${res.detail}`);
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
          // Claude import default = same empty-state rule; ChatGPT default = OFF (unwired).
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
              />
              {discoveryState?.result && (
                <DiscoveryResultView
                  result={discoveryState.result}
                  authMode={discoveredAuthMode}
                  credentialLabel={discoveredCredential?.label ?? null}
                  onClose={() => onClearDiscovery(provider)}
                  onUse={(model, task) => onUseModel(provider, model, task)}
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
                          目前可做 discovery / probe；AI 研究「執行」尚未接上，設為 active 會讓 OpenAI 研究 fail-closed。
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
}: {
  result: ModelDiscoveryResult;
  authMode: ProviderCredential["auth_type"] | null;
  credentialLabel: string | null;
  onClose: () => void;
  onUse: (model: string, task: ModelTask) => void;
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

function ModelTestStatus({ result }: { result: ModelTestResult }) {
  const ok = result.status === "ok";
  return (
    <div className={`test-status ${ok ? "ok" : "bad"}`}>
      <strong>{ok ? "可用" : result.status}</strong>
      {result.latency_ms != null && <span>{result.latency_ms} ms</span>}
      {result.warning && <p className="warn-text">{result.warning}</p>}
      {result.fallback_effort && <p className="muted tiny">fallback effort: {result.fallback_effort}</p>}
      {result.error && <p>{result.error}</p>}
    </div>
  );
}
