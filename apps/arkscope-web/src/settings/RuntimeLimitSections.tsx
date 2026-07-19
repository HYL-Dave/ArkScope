import { useEffect, useState } from "react";
import type {
  FixedTaskRuntimeMap,
  FixedTaskRuntimeSettings,
  ResearchRuntimeSettings,
} from "../api";

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
