import { useCallback, useEffect, useMemo, useState, type Dispatch, type SetStateAction } from "react";
import {
  addCredential,
  importOAuthCredential,
  probeCredential,
  startOpenAIOAuth,
  openAIOAuthStatus,
  completeOpenAIOAuthManual,
  type ProbeResponse,
  bootstrapMarketData,
  deleteCredential,
  discoverModels,
  getMarketDataJob,
  getMarketDataStatus,
  getModelCatalog,
  getProvidersConfig,
  getProvidersHealth,
  getSchedule,
  putProviderConfig,
  putSchedule,
  runScheduleNow,
  saveModelRoutes,
  testProvider,
  setUseLocalMarket,
  testModelAccess,
  updateCredential,
  updateMarketData,
  validateMarketData,
  type MarketDataJob,
  type MarketDataStatus,
  type MarketDataValidate,
  type ProviderConfigEntry,
  type ProvidersHealthResponse,
  type ScheduleSourceState,
  type SyncMeta,
  type ModelCatalog,
  type ModelDiscoveryResult,
  type ModelOption,
  type ModelProvider,
  type ModelTestResult,
  type ModelTask,
  type ProviderCredential,
  type RuntimeConfig,
  type TaskRoute,
} from "./api";
import { MODEL_OPTION_CUSTOM, decodeModelOption, encodeModelOption, inferProvider } from "./modelSelect";
import { buildManualCompletion, pollOAuthStatus } from "./chatgptOAuth";

const TASK_LABELS: Record<ModelTask, string> = {
  card_synthesis: "AI 卡片生成",
  card_translation: "卡片翻譯",
  ai_research: "AI 研究",
};

type SettingsSection = "models" | "providers" | "data_storage" | "data_sources" | "permissions";

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
    id: "providers",
    title: "Providers",
    description: "Anthropic / OpenAI key 狀態與可用模型來源。",
    enabled: true,
  },
  {
    id: "data_storage",
    title: "Data Storage",
    description: "本地市場庫（價格＋新聞＋IV＋基本面）建立、驗證、啟用；PG 為 fallback。",
    enabled: true,
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
      setMsg("模型路由已儲存到 config/user_profile.local.yaml。");
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
        <button className="btn-ghost" onClick={() => void save()} disabled={saving || loading || !catalog}>
          {saving ? "儲存中…" : "儲存路由"}
        </button>
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
              {SETTINGS_SECTIONS.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={`settings-section-button ${section === item.id ? "active" : ""}`}
                  disabled={!item.enabled}
                  onClick={() => item.enabled && setSection(item.id)}
                  title={item.enabled ? item.title : `${item.title} — 規劃中`}
                >
                  <strong>{item.title}</strong>
                  <span>{item.description}</span>
                </button>
              ))}
            </div>
          </aside>

          <section className="settings-content">
            {section === "models" ? (
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
              />
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
                onUseModel={(provider, model, task) => {
                  onDraftForTask(setDraft, task, provider, model);
                  setSection("models");
                }}
              />
            ) : section === "data_storage" ? (
              <DataStorageSection />
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
    const ts = m.last_success ? m.last_success.slice(0, 16).replace("T", " ") : "—";
    return `+${m.rows_added.toLocaleString()} @ ${ts}`;
  };
  const s = status.sync;
  if (!s.prices && !s.news && !s.iv && !s.fundamentals) return "尚未增量更新";
  return `價格 ${fmt(s.prices)} · 新聞 ${fmt(s.news)} · IV ${fmt(s.iv)} · 基本面 ${fmt(s.fundamentals)}`;
}

function DataStorageSection() {
  const [status, setStatus] = useState<MarketDataStatus | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState<"" | "bootstrap" | "update" | "validate" | "toggle">("");
  const [job, setJob] = useState<MarketDataJob | null>(null);
  const [validation, setValidation] = useState<MarketDataValidate | null>(null);

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

  async function runBootstrap() {
    if (busy) return;
    setBusy("bootstrap");
    setValidation(null);
    setErr(null);
    try {
      let j = await bootstrapMarketData();
      setJob(j);
      while (j.status === "running") {
        await new Promise((r) => setTimeout(r, 1000));
        j = await getMarketDataJob(j.id);
        setJob(j);
      }
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy("");
    }
  }

  async function runUpdate() {
    if (busy) return;
    setBusy("update");
    setValidation(null);
    setErr(null);
    try {
      let j = await updateMarketData();
      setJob(j);
      while (j.status === "running") {
        await new Promise((r) => setTimeout(r, 1000));
        j = await getMarketDataJob(j.id);
        setJob(j);
      }
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy("");
    }
  }

  async function runValidate() {
    if (busy) return;
    setBusy("validate");
    setErr(null);
    try {
      setValidation(await validateMarketData());
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy("");
    }
  }

  async function toggle(enabled: boolean) {
    if (busy) return;
    setBusy("toggle");
    setErr(null);
    try {
      await setUseLocalMarket(enabled);
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy("");
    }
  }

  const exists = status?.exists ?? false;
  const pr = status?.prices;
  const nw = status?.news;
  const iv = status?.iv;
  const fd = status?.fundamentals;
  const fc = status?.financial_cache;
  const pct =
    job && job.progress.total > 0
      ? Math.round((job.progress.written / job.progress.total) * 100)
      : 0;

  return (
    <div>
      <div className="settings-section-head">
        <div>
          <h2>本地市場資料庫 · Market Data</h2>
          <p className="muted tiny">
            把市場價格、新聞、IV、基本面從遠端 PostgreSQL 鏡像到本地 SQLite（local-first）。啟用後讀取走本地、
            缺資料自動 fallback 回 PG。財務快取為 local-primary（寫本地、讀本地優先、PG 僅作 legacy fallback）。
            Seeking Alpha capture 已切到本地 SQLite（hard cutover 2026-06-13，無 PG 讀 fallback）；報告與分數仍在 PG。
          </p>
        </div>
        <button className="btn-ghost" onClick={() => void load()} disabled={!!busy}>↻ 重新整理</button>
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
                ? `${fc!.row_count.toLocaleString()} 列（有效 ${fc!.valid_count} · 過期 ${fc!.expired_count}）· 最新抓取 ${fc!.latest_fetched_at ?? "—"}（local-primary，不對 PG 驗證）`
                : "—"}
            </dd>
            <dt>最近增量更新</dt>
            <dd>{syncLine(status)}</dd>
            <dt>本地路由</dt>
            <dd>
              {status.routing_enabled
                ? "啟用中（PG fallback）"
                : status.use_local_market_setting
                  ? "設定已開，待建立資料庫"
                  : "關閉（使用 PG）"}
              {status.env_override && "（env 強制開啟）"}
            </dd>
          </dl>

          <div className="settings-actions" style={{ marginTop: 12 }}>
            <button className="btn-ghost" onClick={() => void runBootstrap()} disabled={!!busy}>
              {busy === "bootstrap" ? "建立中…" : exists ? "重建本地市場庫" : "建立本地市場庫"}
            </button>
            <button className="btn-ghost" onClick={() => void runUpdate()} disabled={!!busy || !exists}>
              {busy === "update" ? "更新中…" : "增量更新"}
            </button>
            <button
              className="btn-ghost"
              onClick={() => void runValidate()}
              disabled={!!busy || !exists}
            >
              {busy === "validate" ? "驗證中…" : "驗證本地資料"}
            </button>
            <label className="ds-toggle">
              <input
                type="checkbox"
                checked={status.use_local_market_setting}
                disabled={!!busy}
                onChange={(e) => void toggle(e.target.checked)}
              />
              使用本地 market data
            </label>
          </div>

          {busy === "bootstrap" && job && (
            <p className="muted tiny" style={{ marginTop: 8 }}>
              建立中… {job.progress.written.toLocaleString()} / {job.progress.total.toLocaleString()} ({pct}%)
              {" "}— 進度在後端執行；建立期間請勿關閉 app（關閉會中斷，需重新建立）。
            </p>
          )}
          {busy === "update" && <p className="muted tiny" style={{ marginTop: 8 }}>增量更新中…（補抓最新資料）</p>}
          {!busy && job && job.status === "done" && job.result && (
            <p className="tiny" style={{ marginTop: 8, color: "var(--ok)" }}>
              {job.kind === "update_market"
                ? `✓ 增量更新完成：價格 +${(job.result.prices?.rows_added ?? 0).toLocaleString()} 列、新聞 +${(job.result.news?.rows_added ?? 0).toLocaleString()} 篇、IV +${(job.result.iv?.rows_added ?? 0).toLocaleString()}、基本面 +${(job.result.fundamentals?.rows_added ?? 0).toLocaleString()}。`
                : `✓ 建立完成：價格 ${(job.result.prices?.rows ?? 0).toLocaleString()} 列、新聞 ${(job.result.news?.rows ?? 0).toLocaleString()} 篇、IV ${(job.result.iv?.rows ?? 0).toLocaleString()}、基本面 ${(job.result.fundamentals?.rows ?? 0).toLocaleString()}，校驗一致；財務快取保留 ${(job.result.financial_cache?.carried_over ?? 0).toLocaleString()} 列。`}
            </p>
          )}
          {!busy && job && job.status === "error" && (
            <p className="tiny refresh-err" style={{ marginTop: 8 }}>
              {job.kind === "update_market" ? "增量更新失敗" : "建立失敗"}：{job.error}（既有資料庫已保留）
            </p>
          )}
          {validation && (
            <p
              className="tiny"
              style={{ marginTop: 8, color: validation.match ? "var(--ok)" : "var(--bad)" }}
            >
              {validation.match ? "✓ 驗證一致" : "✗ 驗證不一致（建議重建）"}：{" "}
              {(
                [
                  ["價格", validation.prices],
                  ["新聞", validation.news],
                  ["IV", validation.iv],
                  ["基本面", validation.fundamentals],
                ] as const
              ).map(([label, dv], i) => (
                <span key={label}>
                  {i > 0 ? " · " : ""}
                  {label} {(dv?.local_rows ?? 0).toLocaleString()}/{(dv?.pg_rows ?? 0).toLocaleString()}
                  {dv?.match ? " ✓" : " ✗"}
                </span>
              ))}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

// ---- Data Sources: provider health + per-source app-owned scheduling (3e) ----

const PROVIDER_STATUS_LABEL: Record<string, string> = {
  connected: "正常",
  stale: "過期",
  maintenance: "維護中",
  no_signal: "無訊號",
  missing_key: "缺金鑰",
  disabled: "已停用",
};

function shortTs(iso: string | null | undefined): string {
  if (!iso) return "—";
  return iso.slice(5, 16).replace("T", " "); // "MM-DD HH:mm"
}

function DataSourcesSection() {
  const [schedule, setSchedule] = useState<Record<string, ScheduleSourceState> | null>(null);
  const [health, setHealth] = useState<ProvidersHealthResponse | null>(null);
  const [cfg, setCfg] = useState<Record<string, ProviderConfigEntry> | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState<string>(""); // source id with an in-flight mutation
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [keyDrafts, setKeyDrafts] = useState<Record<string, string>>({}); // "provider.field"
  const [testResults, setTestResults] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    const [rs, rh, rc] = await Promise.allSettled([
      getSchedule(), getProvidersHealth(), getProvidersConfig()]);
    if (rs.status === "fulfilled") setSchedule(rs.value.sources);
    if (rh.status === "fulfilled") setHealth(rh.value);
    if (rc.status === "fulfilled") setCfg(rc.value.providers);
    const bad = [rs, rh, rc].filter((r): r is PromiseRejectedResult => r.status === "rejected");
    setErr(bad.length
      ? bad.map((r) => (r.reason instanceof Error ? r.reason.message : String(r.reason))).join("；")
      : null);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

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

  async function saveField(provider: string, field: string, value: string | null) {
    if (busy) return;
    setBusy(`${provider}.${field}`);
    try {
      await putProviderConfig(provider, { [field]: value });
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

  return (
    <div>
      <div className="settings-section-head">
        <div>
          <h2>資料來源 · Data Sources</h2>
          <p className="muted tiny">
            App 直接發起資料抓取（免 cron）。每個來源獨立排程：自己的開關與間隔、平行執行
            （IBKR 三項共用 Gateway 鎖序列化）。一次執行 = 抓取 → 同步 PG → 更新本地鏡像。
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
                  <td title={p.detail}>{p.label}</td>
                  <td><span className={`ds-chip ds-${p.status}`}>{PROVIDER_STATUS_LABEL[p.status] ?? p.status}</span></td>
                  <td>{p.key_source === "not_required" ? "免金鑰" : p.key_source}</td>
                  <td>{shortTs(p.last_success_at)}</td>
                  <td className="muted">{p.last_error ? p.last_error.slice(0, 60) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="settings-panel" style={{ marginTop: 16 }}>
        <h4 className="detail-section">連線與金鑰</h4>
        <p className="muted tiny">
          App 管理各 provider 的金鑰與連線設定（存本地、僅顯示遮罩值）。IB Gateway 本體在你啟動的那台機器上
          — 這裡填的是「連去哪」（host / port）。儲存即生效（毋須重啟）；優先序：環境變數 ＞ App 設定 ＞
          config/.env。SEC EDGAR 免金鑰、預設可用。
        </p>
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
                  const rows = c.fields.length > 0 ? c.fields : [null];
                  return rows.map((f, i) => (
                    <tr key={`${pid}.${f?.field ?? "_"}`}>
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
                                <span className="muted tiny">（{f.effective_source}）</span>
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
                                if (e.key === "Enter" && v) void saveField(pid, f.field, v);
                              }}
                            />
                            {keyDrafts[`${pid}.${f.field}`] && (
                              <button className="btn-ghost tiny"
                                onClick={() => void saveField(pid, f.field, keyDrafts[`${pid}.${f.field}`])}>
                                儲存
                              </button>
                            )}
                            {f.app_value_set && (
                              <button className="btn-ghost tiny"
                                onClick={() => void saveField(pid, f.field, null)}>
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
                    {s.ibkr && <span className="muted tiny"> · IBKR</span>}
                    {!s.provider_fetch && <span className="muted tiny"> · 本地</span>}
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
                  <td className="muted tiny">
                    {jobOutcome(s.job_name)}
                    {/* a skip writes no job_runs row — last_result is its only trace */}
                    {s.last_result?.status === "skipped" && (
                      <span className="refresh-err"> · 已跳過：{s.last_result.reason}</span>
                    )}
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

function ModelRoutingSection({
  catalog,
  draft,
  modelsByProvider,
  testState,
  onDraft,
  onTest,
}: {
  catalog: ModelCatalog;
  draft: Partial<Record<ModelTask, DraftRoute>>;
  modelsByProvider: Record<ModelProvider, ModelOption[]>;
  testState: TestState;
  onDraft: Dispatch<SetStateAction<Partial<Record<ModelTask, DraftRoute>>>>;
  onTest: (task: ModelTask) => Promise<void>;
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
          return (
            <div className="settings-panel" key={task.id}>
              <div className="settings-panel-head">
                <div>
                  <h2>{TASK_LABELS[task.id]}</h2>
                  <p className="muted">{task.description}</p>
                </div>
                <span className={`route-source ${effective?.source ?? "default"}`}>
                  {effective?.source ?? "default"}
                </span>
              </div>

              {envLocked && (
                <p className="warn-text">
                  目前由環境變數控制；儲存 profile 會保留設定，但 runtime 仍以 env 為準。
                </p>
              )}
              {effective?.warning && <p className="warn-text">{effective.warning}</p>}

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
                {currentTest?.result && <ModelTestStatus result={currentTest.result} />}
              </div>
            </div>
          );
        })}
      </div>
    </>
  );
}

function ProviderSection({
  catalog,
  runtime,
  discovery,
  onRefresh,
  onDiscover,
  onUseModel,
}: {
  catalog: ModelCatalog;
  runtime: RuntimeConfig | null;
  discovery: DiscoveryState;
  onRefresh: () => Promise<void>;
  onDiscover: (provider: ModelProvider, credentialId: string | null) => Promise<void>;
  onUseModel: (provider: ModelProvider, model: string, task: ModelTask) => void;
}) {
  const [selectedCreds, setSelectedCreds] = useState<Partial<Record<ModelProvider, string>>>({});
  const [newAlias, setNewAlias] = useState<Partial<Record<ModelProvider, string>>>({});
  const [newSecret, setNewSecret] = useState<Partial<Record<ModelProvider, string>>>({});
  const [renames, setRenames] = useState<Record<string, string>>({});
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
  const [oauthBusy, setOauthBusy] = useState(false);
  const [manualValue, setManualValue] = useState("");

  async function addKey(provider: ModelProvider) {
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
        make_active: true,
      });
      setNewAlias((prev) => ({ ...prev, [provider]: "" }));
      setNewSecret((prev) => ({ ...prev, [provider]: "" }));
      setProviderMsg(`${provider} key 已新增並設為 active。`);
      await onRefresh();
    } catch (e) {
      setProviderErr(e instanceof Error ? e.message : String(e));
    }
  }

  async function importClaudeToken() {
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
        make_active: true,
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
    if (oauth?.authUrl && navigator.clipboard) {
      try {
        await navigator.clipboard.writeText(oauth.authUrl);
        setProviderMsg("登入連結已複製。");
      } catch {
        /* clipboard denied — the browser tab already opened the URL */
      }
    }
  }

  async function startChatGPTLogin() {
    setProviderErr(null);
    setProviderMsg(null);
    setOauthBusy(true);
    try {
      const r = await startOpenAIOAuth();
      setOauth({ state: r.state, authUrl: r.auth_url, phase: "waiting" });
      // open the browser login; if a popup blocker eats it, the copy-link button is the fallback
      window.open(r.auth_url, "_blank", "noopener,noreferrer");
      const res = await pollOAuthStatus(r.state, {
        statusFn: openAIOAuthStatus,
        now: () => Date.now(),
        sleep: (ms) => new Promise<void>((resolve) => window.setTimeout(resolve, ms)),
      });
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
      setOauthBusy(false);
    }
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
    setOauthBusy(true);
    try {
      await completeOpenAIOAuthManual(buildManualCompletion(oauth.state, pasted));
      setManualValue("");
      setOauth(null);
      setProviderMsg("ChatGPT 訂閱已登入（手動完成；token 存入 token-store）。");
      await onRefresh();
    } catch (e) {
      // a bad/expired/forged state or a token-exchange error 400s here — show it, no fallback
      setProviderErr(e instanceof Error ? e.message : String(e));
    } finally {
      setOauthBusy(false);
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

  async function saveAlias(credentialId: string) {
    const alias = (renames[credentialId] ?? "").trim();
    if (!alias) return;
    setProviderErr(null);
    setProviderMsg(null);
    try {
      await updateCredential(credentialId, { alias });
      setProviderMsg("Alias 已更新。");
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
            Provider/channel 和 task routing 分開管理。這裡顯示本機 credential 狀態，並可用 API key 做 model discovery / model test。
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
          const keySet = credentials.some((c) => c.available && c.can_test_models);
          const sourceUrls = Array.from(new Set(models.map((m) => m.source_url)));
          const discoveryState = discovery[provider];
          const usable = credentials.filter((c) => c.available && c.can_discover_models);
          const activeUsable = usable.find((c) => c.active);
          const selectedDraft = selectedCreds[provider];
          const selectedCredential = usable.some((c) => c.id === selectedDraft)
            ? selectedDraft ?? null
            : activeUsable?.id ?? usable[0]?.id ?? null;
          return (
            <div className="settings-panel provider-card" key={provider}>
              <div className="settings-panel-head">
                <div>
                  <h2>{provider}</h2>
                  <p className="muted">{models.length} seed models · direct model id input allowed</p>
                </div>
                <span className={`key-pill ${keySet ? "ok" : "missing"}`}>
                  {keySet ? "key set" : "no key"}
                </span>
              </div>
              <div className="provider-model-list">
                {models.map((model) => (
                  <span key={model.id}>{model.id}</span>
                ))}
              </div>
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
                <button type="button" className="btn-ghost small" onClick={() => void addKey(provider)}>
                  新增並設為 active
                </button>
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
                    <span>顯示名稱／帳號標籤（可留空）</span>
                    <input
                      value={claudeLabel}
                      placeholder="例如 Pro / Max"
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
                  <button type="button" className="btn-ghost small" onClick={() => void importClaudeToken()}>
                    匯入 setup-token
                  </button>
                </div>
              )}
              {provider === "openai" && (
                <div className="credential-add-box oauth-import-box">
                  <p className="muted tiny" style={{ marginBottom: 8 }}>
                    登入 ChatGPT 訂閱（OpenAI subscription）。<strong>這不是 OpenAI API key。</strong>
                    這是<strong>實驗性／相容路徑</strong>（走 ChatGPT 後端，非公開 OpenAI API，可能隨時失效）。
                    Token 會存入本機 token-store/keyring，credential DB 只保存 metadata。
                  </p>
                  {!oauth && (
                    <button
                      type="button"
                      className="btn-ghost small"
                      disabled={oauthBusy}
                      onClick={() => void startChatGPTLogin()}
                    >
                      {oauthBusy ? "登入中…" : "登入 ChatGPT"}
                    </button>
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
                        disabled={oauthBusy}
                        onClick={() => void completeChatGPTManual()}
                      >
                        {oauthBusy ? "完成中…" : "完成登入"}
                      </button>
                      <button
                        type="button"
                        className="btn-ghost small"
                        onClick={() => {
                          setOauth(null);
                          setManualValue("");
                        }}
                      >
                        取消
                      </button>
                    </div>
                  )}
                </div>
              )}
              <CredentialList
                credentials={credentials}
                renames={renames}
                onRenameDraft={(id, alias) => setRenames((prev) => ({ ...prev, [id]: alias }))}
                onSaveAlias={(id) => void saveAlias(id)}
                onSetActive={(id) => void setActive(id)}
                onDelete={(id) => void removeKey(id)}
              />
              <div className="settings-actions">
                <label className="field credential-select">
                  <span>Discovery/Test credential</span>
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
                  {discoveryState?.loading ? "讀取模型中…" : "列出此 key 可見模型"}
                </button>
              </div>
              {discoveryState?.result && (
                <DiscoveryResultView
                  result={discoveryState.result}
                  onUse={(model, task) => onUseModel(provider, model, task)}
                />
              )}
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
                  ? " Claude setup-token 可由上方匯入（token 存 token-store/keyring，不進 credential DB）；OpenAI ChatGPT OAuth 匯入規劃中。"
                  : " OpenAI ChatGPT OAuth 匯入規劃中（auth-driver slice）。"}
              </p>
            </div>
          );
        })}
      </div>
    </>
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

function CredentialList({
  credentials,
  renames,
  onRenameDraft,
  onSaveAlias,
  onSetActive,
  onDelete,
}: {
  credentials: ProviderCredential[];
  renames: Record<string, string>;
  onRenameDraft: (id: string, alias: string) => void;
  onSaveAlias: (id: string) => void;
  onSetActive: (id: string) => void;
  onDelete: (id: string) => void;
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
        return (
          <div className="credential-row" key={cred.id}>
            <div>
              <strong>{cred.label}</strong>
              {cred.active && <span className="active-badge">使用中</span>}
              <span>{cred.auth_type}</span>
            </div>
            <span className={`key-pill ${cred.available ? "ok" : "missing"}`}>
              {cred.available ? cred.masked ?? "available" : "missing"}
            </span>
            <p className="muted tiny">
              {cred.id.startsWith("local:")
                ? "本機 Settings credential（profile DB · 可編輯、可設為 active）"
                : ".env／環境變數 fallback（唯讀；DB credential 才是主要選擇面）"}
            </p>
            <p>{cred.notes}</p>
            {cred.editable && (
              <div className="credential-actions">
                <input
                  value={renames[cred.id] ?? cred.label}
                  onChange={(e) => onRenameDraft(cred.id, e.target.value)}
                  aria-label={`${cred.label} alias`}
                />
                <button type="button" className="btn-ghost small" onClick={() => onSaveAlias(cred.id)}>
                  儲存 alias
                </button>
                <button
                  type="button"
                  className="btn-ghost small"
                  disabled={cred.active}
                  onClick={() => onSetActive(cred.id)}
                >
                  設為 active
                </button>
                {isLocalOAuth && (
                  <button
                    type="button"
                    className="btn-ghost small"
                    disabled={probing === cred.id}
                    onClick={() => void runProbe(cred.id)}
                  >
                    {probing === cred.id
                      ? "測試中…（最久約 2 分鐘）"
                      : cred.auth_type === "chatgpt_oauth"
                        ? "測試 ChatGPT OAuth（會打真實請求）"
                        : "測試 setup-token"}
                  </button>
                )}
                <button
                  type="button"
                  className="btn-ghost small danger"
                  onClick={() => {
                    if (window.confirm(`刪除 ${cred.label}？`)) onDelete(cred.id);
                  }}
                >
                  刪除
                </button>
              </div>
            )}
            {probe && <ProbeResultView probe={probe} />}
          </div>
        );
      })}
    </div>
  );
}

function ProbeResultView({ probe }: { probe: ProbeResponse | { error: string } }) {
  if ("error" in probe) {
    return <p className="error-text tiny">probe 失敗：{probe.error}</p>;
  }
  return (
    <div className="probe-result">
      <p className={probe.passed ? "ok-text tiny" : "warn-text tiny"}>
        {probe.passed ? "✓ OAuth 驗證通過" : "✗ OAuth 驗證未通過"}
      </p>
      <ul className="probe-list">
        {probe.probes.map((p) => (
          <li key={p.name} className="tiny">
            <span className={p.passed ? "ok-text" : "warn-text"}>{p.passed ? "✓" : "✗"}</span>{" "}
            {p.name} — {p.error ? p.error : p.observed}
          </li>
        ))}
      </ul>
    </div>
  );
}

function DiscoveryResultView({
  result,
  onUse,
}: {
  result: ModelDiscoveryResult;
  onUse: (model: string, task: ModelTask) => void;
}) {
  const [query, setQuery] = useState("");
  const models = result.models.filter((model) =>
    model.id.toLowerCase().includes(query.trim().toLowerCase()),
  );
  return (
    <div className="discovery-box">
      <div className="discovery-head">
        <strong>Discovery: {result.status}</strong>
        {result.source_url && (
          <a href={result.source_url} target="_blank" rel="noreferrer">
            source
          </a>
        )}
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
