import type { Dispatch, SetStateAction } from "react";
import { useTranslation } from "react-i18next";
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
  type ModelEntryWithReason,
} from "../modelPicker";
import { routeIsOverridable, routeSourceBadge } from "../modelRouteDisplay";
import {
  isTaskTestSnapshotCurrent,
  modelAuthModeLabel,
  modelCompatibilityLabel,
  modelReasonLabel,
  officialModelPricingUrl,
  providerContexts,
  type DraftRouteValue,
  type ModelCommonT,
  type TaskTestSnapshot,
} from "../modelRoutingUx";
import {
  effortOptionsForModel,
  taskRouteBlocker,
  taskRouteModelStatus,
} from "../researchModels";
import { formatSystemTimestamp } from "../timeDisplay";
import { DeveloperDiagnostics } from "./DeveloperDiagnostics";
import {
  settingsEffortLabel,
  settingsTaskLabel,
  settingsThinkingLabel,
  type SettingsT,
} from "./settingsCopy";

function taskDescription(task: ModelTask, t: SettingsT): string {
  switch (task) {
    case "card_synthesis":
      return t(($) => $.models.tasks.cardSynthesis.description);
    case "card_translation":
      return t(($) => $.models.tasks.cardTranslation.description);
    case "ai_research":
      return t(($) => $.models.tasks.aiResearch.description);
  }
}

function providerLabel(provider: ModelProvider, t: SettingsT): string {
  if (provider === "openai") return t(($) => $.models.providers.openai);
  return t(($) => $.models.providers.anthropic);
}

function modelEntrySuffix(
  entry: ModelEntryWithReason,
  t: SettingsT,
  commonT: ModelCommonT,
): string | null {
  if (entry.disabledReason) return modelReasonLabel(entry.disabledReason, commonT);
  if (entry.compatibility === "legacy_unverified") {
    return t(($) => $.models.compatibility.unverified);
  }
  if (entry.status === "advanced") return t(($) => $.models.compatibility.advanced);
  if (entry.status === "seed") return t(($) => $.models.compatibility.unverified);
  if (entry.status === "route" && entry.reason_code) {
    return modelReasonLabel(entry.reason_code, commonT);
  }
  return null;
}

function modelCatalogStateLabel(
  cacheState: string | undefined,
  t: SettingsT,
  commonT: ModelCommonT,
): string {
  switch (cacheState) {
    case "ok":
      return t(($) => $.models.catalog.visibleListLoaded);
    case "seed_only":
      return t(($) => $.models.catalog.seedOnly);
    case "never_discovered":
      return t(($) => $.models.catalog.neverDiscovered);
    default: {
      const label = modelReasonLabel("discovery_unavailable", commonT);
      return label;
    }
  }
}

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
  developerMode,
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
  developerMode: boolean;
}) {
  const { t } = useTranslation("settings");
  const { t: commonT } = useTranslation("common");
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
          <h2>{t(($) => $.models.section.title)}</h2>
          <p className="muted">{t(($) => $.models.section.description)}</p>
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
            ?? compatEntries(row.provider, row, modelsByProvider, commonT);
          const currentEntries = rawEntries.filter((entry) => (
            taskRouteModelStatus(catalog, row.provider, entry.id) === "current"
          ));
          const entries = currentEntries.some((entry) => entry.id === row.model) || !row.model
            ? currentEntries
            : [
                ...currentEntries,
                {
                  id: row.model,
                  label: row.model,
                  status: "route" as const,
                  visible_to_credential: null,
                  eligible: taskRouteModelStatus(catalog, row.provider, row.model) !== "retired",
                  reason_code: taskRouteModelStatus(catalog, row.provider, row.model) === "retired"
                    ? "model_retired"
                    : "model_not_in_registry",
                  thinking_mode: "none",
                  effort_options: undefined,
                },
              ];
          const providerReason = modelProviderReason(context, providerBlock);
          const groups = groupedModelEntries(entries, providerReason, commonT);
          const selectedEntry = entries.find((entry) => entry.id === row.model) ?? null;
          const selectedModelStatus = taskRouteModelStatus(catalog, row.provider, row.model);
          const selectedReason = selectedModelStatus === "retired"
            ? "model_retired"
            : selectedEntry ? optionReason(selectedEntry, providerReason) : null;
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
          const selectedEffort = effortOptions.some(
            (item) => item.id === row.effort.trim(),
          ) ? row.effort.trim() : "";
          const routeBlocker = taskRouteBlocker(catalog, row);
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
          const modelSelectDisabled = !context
            || (!!providerBlock && !providerBlock.executable);
          const testDisabled = (
            compatMode
            || modelSelectDisabled
            || !row.model.trim()
            || !!selectedReason
            || !!routeBlocker
            || !!currentTest?.loading
          );
          const routeBadge = routeSourceBadge(effectiveRoute?.source ?? "default", t);
          const taskLabelId = `model-route-${task.id}-task-label`;
          const providerLabelId = `model-route-${task.id}-provider-label`;
          const modelLabelId = `model-route-${task.id}-model-label`;
          const customModelLabelId = `model-route-${task.id}-custom-model-label`;
          const effortLabelId = `model-route-${task.id}-effort-label`;
          return (
            <div className="settings-panel" key={task.id} data-testid={`route-${task.id}`}>
              <div className="settings-panel-head">
                <div>
                  <h2 id={taskLabelId}>{settingsTaskLabel(task.id, t)}</h2>
                  <p className="muted">{taskDescription(task.id, t)}</p>
                </div>
                <span
                  className={`route-source ${routeBadge.tone}`}
                  aria-label={[
                    t(($) => $.models.route.authority),
                    " ",
                    routeSourceBadge(effectiveRoute?.source ?? "default", t).label,
                  ].join("")}
                >
                  {routeBadge.label}
                </span>
              </div>

              {envLocked ? (
                <p className="warn-text">
                  {t(($) => $.models.route.envOverrideDetail)}
                </p>
              ) : null}
              {developerMode ? (
                <DeveloperDiagnostics diagnostics={[effectiveRoute?.warning]} t={t} />
              ) : null}

              <div className="field">
                <span id={providerLabelId}>{t(($) => $.models.fields.provider)}</span>
                <div
                  className="model-provider-toggle"
                  role="group"
                  aria-labelledby={`${taskLabelId} ${providerLabelId}`}
                >
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
                          ?? compatEntries(provider, row, modelsByProvider, commonT);
                        const keepModel = nextModels.some((entry) => entry.id === row.model);
                        const nextModel = keepModel ? row.model : "";
                        const nextEffort = effortOptionsForModel(catalog, provider, nextModel)
                          .some((item) => item.id === row.effort.trim())
                          ? row.effort.trim()
                          : "";
                        updateTask(task.id, {
                          provider,
                          model: nextModel,
                          effort: nextEffort,
                          custom: false,
                        });
                      }}
                    >
                      {providerLabel(provider, t)}
                    </button>
                  ))}
                </div>
              </div>

              <div className={`model-credential-summary ${context ? "ok" : "missing"}`}>
                {context ? (
                  <>
                    <strong>{context.label}</strong>
                    <span>{modelAuthModeLabel(context.auth_mode, commonT)}</span>
                    <span>{modelCatalogStateLabel(providerBlock?.cache_state, t, commonT)}</span>
                    {providerBlock?.discovered_at && (
                      <span>
                        {t(($) => $.models.metrics.verifiedAt, {
                          timestamp: formatSystemTimestamp(providerBlock.discovered_at),
                        })}
                      </span>
                    )}
                    <button
                      type="button"
                      className="btn-ghost small"
                      onClick={() => void onDiscover(row.provider, context.credential_id)}
                    >
                      {t(($) => $.models.catalog.verifyAgain)}
                    </button>
                  </>
                ) : (
                  <>
                    <strong>{modelReasonLabel("missing_active_credential", commonT)}</strong>
                    <button type="button" className="btn-ghost small" onClick={onOpenProviders}>
                      {t(($) => $.models.credentials.openProviders)}
                    </button>
                  </>
                )}
              </div>

              {compatMode ? (
                <p className="warn-text">
                  {modelCompatibilityLabel("settings_notice", commonT)}{" "}
                  {t(($) => $.models.compatibility.restartSidecar)}
                </p>
              ) : null}

              {!row.custom ? (
                <div className="field">
                  <span id={modelLabelId}>{t(($) => $.models.fields.model)}</span>
                  <select
                    aria-labelledby={`${taskLabelId} ${modelLabelId}`}
                    value={entries.some((entry) => entry.id === row.model) ? row.model : ""}
                    disabled={modelSelectDisabled}
                    onChange={(event) => {
                      const model = event.currentTarget.value;
                      if (!model) return;
                      const nextEntry = entries.find((entry) => entry.id === model);
                      const nextEfforts = effortOptionsForModel(
                        catalog, row.provider, model, nextEntry?.effort_options,
                      );
                      const effort = nextEfforts.some((item) => item.id === row.effort.trim())
                        ? row.effort.trim()
                        : "";
                      updateTask(task.id, { ...row, model, effort, custom: false });
                    }}
                  >
                    <option value="">{t(($) => $.models.catalog.select)}</option>
                    {groups.map((group) => (
                      <optgroup key={group.id} label={group.label}>
                        {group.entries.map((entry) => {
                          const suffix = modelEntrySuffix(entry, t, commonT);
                          return (
                            <option
                              key={`${group.id}:${entry.id}`}
                              value={entry.id}
                              disabled={!!entry.disabledReason}
                            >
                              {[entry.baseLabel, suffix ? " · " : "", suffix ?? ""].join("")}
                            </option>
                          );
                        })}
                      </optgroup>
                    ))}
                  </select>
                  {disabledReasons.length > 0 && (
                    <p className="field-help">
                      {t(($) => $.models.compatibility.unavailableReasons, {
                        value: disabledReasons
                          .map((reason) => modelReasonLabel(reason, commonT))
                          .join("; "),
                      })}
                    </p>
                  )}
                  <button
                    type="button"
                    className="btn-ghost small model-custom-toggle"
                    disabled={!context}
                    onClick={() => updateTask(task.id, {
                      ...row,
                      effort: effortOptionsForModel(catalog, row.provider, row.model)
                        .some((item) => item.id === row.effort.trim()) ? row.effort.trim() : "",
                      custom: true,
                    })}
                  >
                    {t(($) => $.models.custom.use)}
                  </button>
                </div>
              ) : (
                <div className="field">
                  <span id={customModelLabelId}>{t(($) => $.models.custom.label)}</span>
                  <input
                    aria-labelledby={`${taskLabelId} ${customModelLabelId}`}
                    value={row.model}
                    placeholder={row.provider === "anthropic" ? "claude-…" : "gpt-…"}
                    onChange={(event) => updateTask(task.id, {
                      ...row,
                      model: event.currentTarget.value.trim(),
                      effort: effortOptionsForModel(
                        catalog,
                        row.provider,
                        event.currentTarget.value.trim(),
                      ).some((item) => item.id === row.effort.trim()) ? row.effort.trim() : "",
                      custom: true,
                    })}
                  />
                  <span className="field-help">
                    {modelReasonLabel("model_not_in_registry", commonT)}
                  </span>
                  <button
                    type="button"
                    className="btn-ghost small model-custom-toggle"
                    onClick={() => updateTask(task.id, { ...row, custom: false })}
                  >
                    {t(($) => $.models.custom.returnToList)}
                  </button>
                </div>
              )}

              <label className="field">
                <span id={effortLabelId}>{t(($) => $.models.fields.effort)}</span>
                <select
                  aria-labelledby={`${taskLabelId} ${effortLabelId}`}
                  value={selectedEffort}
                  onChange={(event) => updateTask(task.id, {
                    ...row,
                    effort: event.currentTarget.value,
                  })}
                >
                  <option value="">{t(($) => $.models.catalog.selectEffort)}</option>
                  {effortOptions.map((effort) => (
                    <option key={effort.id} value={effort.id}>
                      {settingsEffortLabel(effort.id, t)}
                    </option>
                  ))}
                </select>
              </label>

              {routeBlocker === "effort_required" ? (
                <p className="warn-text">{t(($) => $.models.route.effortRequired)}</p>
              ) : null}
              {routeBlocker === "model_retired" ? (
                <p className="warn-text">{t(($) => $.models.route.modelRetired)}</p>
              ) : null}

              <div className="model-thinking-line">
                <span>{t(($) => $.models.fields.thinking)}</span>
                <strong>
                  {settingsThinkingLabel(selectedEntry?.thinking_mode ?? "none", commonT)}
                </strong>
              </div>

              <ModelNotes
                models={modelsByProvider[row.provider] ?? []}
                selected={row.model}
                custom={row.custom}
                provider={row.provider}
                authMode={context?.auth_mode ?? null}
                t={t}
              />

              <div className="settings-actions">
                <button
                  type="button"
                  className="btn-ghost small"
                  disabled={testDisabled}
                  onClick={() => void onTest(task.id)}
                >
                  {currentTest?.loading && testIsCurrent
                    ? t(($) => $.models.test.running)
                    : t(($) => $.models.test.run)}
                </button>
                {context?.auth_mode.includes("oauth") ? (
                  <span className="muted tiny">{t(($) => $.models.test.subscriptionQuota)}</span>
                ) : null}
                {routeIsOverridable(effectiveRoute?.source ?? "default") && (
                  <button
                    type="button"
                    className="btn-ghost small"
                    onClick={() => void onReset(task.id)}
                  >
                    {t(($) => $.models.route.resetToFallback)}
                  </button>
                )}
              </div>

              {currentTest && !testIsCurrent ? (
                <p className="muted tiny">{t(($) => $.models.test.stale)}</p>
              ) : null}
              {currentTest?.result && testIsCurrent && (
                <TaskModelTestStatus
                  result={currentTest.result}
                  developerMode={developerMode}
                  t={t}
                  commonT={commonT}
                />
              )}
            </div>
          );
        })}
      </div>
    </>
  );
}
function TaskModelTestStatus({
  result,
  developerMode,
  t,
  commonT,
}: {
  result: TaskModelTestResult;
  developerMode: boolean;
  t: SettingsT;
  commonT: ModelCommonT;
}) {
  const ok = result.status === "ok";
  const action = result.error_code ? modelReasonLabel(result.error_code, commonT) : null;
  return (
    <div className={`test-status ${ok ? "ok" : "bad"}`}>
      <strong>
        {ok ? t(($) => $.models.test.succeeded) : action ?? modelReasonLabel("provider_call_failed", commonT)}
      </strong>
      {result.latency_ms != null ? (
        <span>{t(($) => $.models.metrics.latency, { value: result.latency_ms })}</span>
      ) : null}
      <span>{t(($) => $.models.metrics.testedAt, { timestamp: formatSystemTimestamp(result.tested_at) })}</span>
      {result.fallback_effort && (
        <p className="muted tiny">
          {t(($) => $.models.test.fallbackEffort, {
            value: settingsEffortLabel(result.fallback_effort, t),
          })}
        </p>
      )}
      {developerMode ? <DeveloperDiagnostics diagnostics={[result.warning]} t={t} /> : null}
    </div>
  );
}
function ModelNotes({
  models,
  selected,
  custom,
  provider,
  authMode,
  t,
}: {
  models: ModelOption[];
  selected: string;
  custom: boolean;
  provider: ModelProvider;
  authMode: Parameters<typeof officialModelPricingUrl>[1];
  t: SettingsT;
}) {
  if (custom) {
    return <p className="muted tiny">{t(($) => $.models.custom.guidance)}</p>;
  }
  const model = models.find((m) => m.id === selected);
  if (!model) return null;
  const pricingUrl = officialModelPricingUrl(provider, authMode);
  return (
    <div className="model-note">
      {model.verified_at ? (
        <span>{t(($) => $.models.metrics.verifiedAt, { timestamp: model.verified_at })}</span>
      ) : null}
      {pricingUrl ? (
        <a
          className="model-pricing-link"
          href={pricingUrl}
          target="_blank"
          rel="noreferrer"
        >
          {t(($) => $.models.metrics.officialPricing)}
        </a>
      ) : null}
    </div>
  );
}
