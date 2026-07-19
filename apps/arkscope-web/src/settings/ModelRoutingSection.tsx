import type { Dispatch, SetStateAction } from "react";
import type {
  ModelCatalog,
  ModelOption,
  ModelProvider,
  ModelTask,
  TaskModelTestResult,
} from "../api";
import {
  compatEntries,
  groupedModelEntries,
  modelProviderReason,
  optionReason,
} from "../modelPicker";
import { routeIsOverridable, routeSourceBadge } from "../modelRouteDisplay";
import {
  isTaskTestSnapshotCurrent,
  MODEL_UX_LABELS,
  providerContexts,
  type DraftRouteValue,
  type TaskTestSnapshot,
} from "../modelRoutingUx";
import { effortOptionsForModel } from "../researchModels";
import { formatSystemTimestamp } from "../timeDisplay";

export const TASK_LABELS: Record<ModelTask, string> = {
  card_synthesis: "AI 卡片生成",
  card_translation: "卡片翻譯",
  ai_research: "AI 研究",
};

export interface DraftRoute extends DraftRouteValue {}

export type TestState = Partial<Record<ModelTask, {
  loading: boolean;
  result: TaskModelTestResult | null;
  snapshot: TaskTestSnapshot | null;
  stale: boolean;
}>>;

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
          const providerReason = modelProviderReason(context, providerBlock);
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
