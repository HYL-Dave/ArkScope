import { useEffect, useMemo, useState, type Dispatch, type SetStateAction } from "react";
import {
  getModelCatalog,
  saveModelRoutes,
  type ModelCatalog,
  type ModelOption,
  type ModelProvider,
  type ModelTask,
  type RuntimeConfig,
  type TaskRoute,
} from "./api";

const TASK_LABELS: Record<ModelTask, string> = {
  card_synthesis: "AI 卡片生成",
  card_translation: "卡片翻譯",
};

type SettingsSection = "models" | "providers" | "data_sources" | "permissions";

const SETTINGS_SECTIONS: Array<{
  id: SettingsSection;
  title: string;
  description: string;
  enabled: boolean;
}> = [
  {
    id: "models",
    title: "Models",
    description: "任務路由、模型選擇、custom model id。",
    enabled: true,
  },
  {
    id: "providers",
    title: "Providers",
    description: "Anthropic / OpenAI key 狀態與可用模型來源。",
    enabled: true,
  },
  {
    id: "data_sources",
    title: "Data Sources",
    description: "IBKR、SA、Polygon、Finnhub 等資料源設定。",
    enabled: false,
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
  custom: boolean;
}

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
      const routes: Partial<Record<ModelTask, { provider: ModelProvider; model: string }>> = {};
      for (const task of catalog.tasks) {
        const row = draft[task.id];
        if (!row || !row.model.trim()) throw new Error(`${TASK_LABELS[task.id]} 缺少 model id`);
        routes[task.id] = { provider: row.provider, model: row.model.trim() };
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
            為每個 AI 任務選擇 provider 和 model。Seed catalog 來自官方文件；帳號權限不同時可用 custom model id。
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
                onDraft={setDraft}
              />
            ) : section === "providers" ? (
              <ProviderSection catalog={catalog} runtime={runtime} />
            ) : null}
          </section>
        </div>
      )}
    </main>
  );
}

function ModelRoutingSection({
  catalog,
  draft,
  modelsByProvider,
  onDraft,
}: {
  catalog: ModelCatalog;
  draft: Partial<Record<ModelTask, DraftRoute>>;
  modelsByProvider: Record<ModelProvider, ModelOption[]>;
  onDraft: Dispatch<SetStateAction<Partial<Record<ModelTask, DraftRoute>>>>;
}) {
  return (
    <>
      <div className="settings-section-head">
        <div>
          <h2>任務模型路由</h2>
          <p className="muted">
            這裡控制實際會被 AI card / 翻譯呼叫的模型。Seed list 只是快速入口；任何 provider 都可以填 custom model id。
          </p>
        </div>
      </div>
      <div className="settings-grid">
        {catalog.tasks.map((task) => {
          const row = draft[task.id];
          if (!row) return null;
          const options = modelsByProvider[row.provider];
          const effective = catalog.routes[task.id];
          const envLocked = effective?.source === "env";
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

              <label className="field">
                <span>Provider</span>
                <select
                  value={row.provider}
                  onChange={(e) => {
                    const provider = e.target.value as ModelProvider;
                    const first = catalog.models.find((m) => m.provider === provider && m.recommended_for.includes(task.id))
                      ?? catalog.models.find((m) => m.provider === provider);
                    onDraft((prev) => ({
                      ...prev,
                      [task.id]: {
                        provider,
                        model: first?.id ?? "",
                        custom: false,
                      },
                    }));
                  }}
                >
                  {catalog.providers.map((p) => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                </select>
              </label>

              <label className="field">
                <span>Model</span>
                <select
                  value={row.custom ? "__custom" : row.model}
                  onChange={(e) => {
                    const value = e.target.value;
                    onDraft((prev) => ({
                      ...prev,
                      [task.id]: {
                        ...row,
                        custom: value === "__custom",
                        model: value === "__custom" ? "" : value,
                      },
                    }));
                  }}
                >
                  {options.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.label} · {m.quality}/{m.cost_tier}
                    </option>
                  ))}
                  <option value="__custom">Custom model id…</option>
                </select>
              </label>

              <label className="field custom-field">
                <span>Custom model id</span>
                <div className="custom-row">
                  <input
                    value={row.custom ? row.model : ""}
                    placeholder={row.provider === "anthropic" ? "claude-…" : "gpt-…"}
                    onFocus={() => {
                      if (!row.custom) {
                        onDraft((prev) => ({
                          ...prev,
                          [task.id]: { ...row, custom: true, model: "" },
                        }));
                      }
                    }}
                    onChange={(e) => {
                      onDraft((prev) => ({
                        ...prev,
                        [task.id]: { ...row, custom: true, model: e.target.value },
                      }));
                    }}
                  />
                  <button
                    type="button"
                    className="btn-ghost small"
                    onClick={() => {
                      onDraft((prev) => ({
                        ...prev,
                        [task.id]: { ...row, custom: true, model: "" },
                      }));
                    }}
                  >
                    使用自訂
                  </button>
                </div>
              </label>

              <ModelNotes models={options} selected={row.model} custom={row.custom} />
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
}: {
  catalog: ModelCatalog;
  runtime: RuntimeConfig | null;
}) {
  return (
    <>
      <div className="settings-section-head">
        <div>
          <h2>Provider 狀態</h2>
          <p className="muted">
            Provider/channel 和 task routing 分開管理。這一版先顯示 key 狀態與 seed catalog；連線測試和 model discovery 是下一步。
          </p>
        </div>
      </div>
      <div className="provider-grid">
        {catalog.providers.map((provider) => {
          const models = catalog.models.filter((m) => m.provider === provider);
          const keySet = provider === "anthropic" ? runtime?.anthropic.key_set : runtime?.openai.key_set;
          const sourceUrls = Array.from(new Set(models.map((m) => m.source_url)));
          return (
            <div className="settings-panel provider-card" key={provider}>
              <div className="settings-panel-head">
                <div>
                  <h2>{provider}</h2>
                  <p className="muted">{models.length} seed models · custom model id allowed</p>
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
              <div className="provider-links">
                {sourceUrls.map((url) => (
                  <a key={url} href={url} target="_blank" rel="noreferrer">
                    official source
                  </a>
                ))}
              </div>
              <p className="muted tiny">
                下一步：加入「測試連線」與可支援 provider 的 model discovery；目前不在 UI 寫入 API key，只讀取本機 env/key 狀態。
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
      custom: routes[task].custom,
    };
  }
  return out;
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
        Custom model ids are accepted so new or account-specific models can be used before the seed catalog is updated.
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
