import type { TFunction } from "i18next";

import type {
  CredentialAuthType,
  EffectiveProviderSummary,
  ModelCatalog,
  ModelProvider,
  ModelTask,
  ProviderCredential,
  TaskRoute,
} from "./api";

export type ModelCommonT = TFunction<"common">;

const DECORATED_COMPATIBILITY_ID = "decorated_suffix";

export function officialModelPricingUrl(
  provider: ModelProvider,
  authMode: CredentialAuthType | null,
): string | null {
  if (authMode === "api_key" || authMode === "api_key_pool") {
    return provider === "openai"
      ? "https://developers.openai.com/api/docs/pricing"
      : "https://platform.claude.com/docs/en/about-claude/pricing";
  }
  if (provider === "openai" && authMode === "chatgpt_oauth") {
    return "https://chatgpt.com/pricing/";
  }
  if (provider === "anthropic" && authMode === "claude_code_oauth") {
    return "https://claude.com/pricing";
  }
  return null;
}

export function modelGroupLabel(id: string, t: ModelCommonT): string {
  switch (id) {
    case "available": return t(($) => $.models.groups.available);
    case "visible_disabled": return t(($) => $.models.groups.visibleDisabled);
    case "advanced": return t(($) => $.models.groups.advanced);
    case "current": return t(($) => $.models.groups.current);
    default: return id;
  }
}

export function modelReasonLabel(id: string, t: ModelCommonT): string {
  switch (id) {
    case "missing_active_credential": return t(($) => $.models.reasons.missingActiveCredential);
    case "task_auth_mode_unsupported": return t(($) => $.models.reasons.taskAuthModeUnsupported);
    case "task_test_unsupported": return t(($) => $.models.reasons.taskTestUnsupported);
    case "task_capability_missing": return t(($) => $.models.reasons.taskCapabilityMissing);
    case "model_not_visible": return t(($) => $.models.reasons.modelNotVisible);
    case "model_not_in_registry": return t(($) => $.models.reasons.modelNotInRegistry);
    case "discovery_unavailable": return t(($) => $.models.reasons.discoveryUnavailable);
    case "provider_call_failed": return t(($) => $.models.reasons.providerCallFailed);
    case "reauth_required": return t(($) => $.models.reasons.reauthRequired);
    default: return id;
  }
}

export function modelAuthModeLabel(id: string, t: ModelCommonT): string {
  switch (id) {
    case "api_key": return t(($) => $.models.authModes.apiKey);
    case "api_key_pool": return t(($) => $.models.authModes.apiKeyPool);
    case "chatgpt_oauth": return t(($) => $.models.authModes.chatgptOauth);
    case "claude_code_oauth": return t(($) => $.models.authModes.claudeCodeOauth);
    default: return id;
  }
}

export function modelThinkingModeLabel(id: string, t: ModelCommonT): string {
  switch (id) {
    case "none": return t(($) => $.models.thinkingModes.none);
    case "manual_budget": return t(($) => $.models.thinkingModes.manualBudget);
    case "adaptive_opt_in": return t(($) => $.models.thinkingModes.adaptiveOptIn);
    case "adaptive_default_on": return t(($) => $.models.thinkingModes.adaptiveDefaultOn);
    case "adaptive_always_on": return t(($) => $.models.thinkingModes.adaptiveAlwaysOn);
    default: return id;
  }
}

export function modelCompatibilityLabel(id: string, t: ModelCommonT): string {
  switch (id) {
    case "decorated_suffix": return t(($) => $.models.compatibility.decoratedSuffix);
    case "settings_notice": return t(($) => $.models.compatibility.settingsNotice);
    default: return id;
  }
}

export function modelDecoratedLabel(baseLabel: string, t: ModelCommonT): string {
  return [baseLabel, modelCompatibilityLabel(DECORATED_COMPATIBILITY_ID, t)].join(" · ");
}

export function modelEntryLabel(
  baseLabel: string,
  compatibility: "legacy_unverified" | null,
  t: ModelCommonT,
): string {
  switch (compatibility) {
    case "legacy_unverified": return modelDecoratedLabel(baseLabel, t);
    case null: return baseLabel;
  }
}

export interface DraftRouteValue {
  provider: ModelProvider;
  model: string;
  effort: string;
  custom: boolean;
}

export interface TaskTestSnapshot {
  task: ModelTask;
  provider: ModelProvider;
  model: string;
  effort: string;
  credential_id: string;
}

export type ProviderContextMap = Record<ModelProvider, EffectiveProviderSummary | null>;

export function providerContexts(
  effective: Partial<Record<ModelProvider, EffectiveProviderSummary | null>> | undefined,
  credentials: Record<ModelProvider, ProviderCredential[]>,
): ProviderContextMap {
  if (effective) {
    return {
      openai: effective.openai ?? null,
      anthropic: effective.anthropic ?? null,
    };
  }
  const fromInventory = (provider: ModelProvider): EffectiveProviderSummary | null => {
    const active = (credentials[provider] ?? []).find((row) => row.active && row.available);
    if (!active) return null;
    return {
      credential_id: active.id,
      auth_mode: active.auth_type,
      label: active.label,
    };
  };
  return { openai: fromInventory("openai"), anthropic: fromInventory("anthropic") };
}

export function routesSemanticallyEqual(
  draft: Pick<DraftRouteValue, "provider" | "model" | "effort"> | undefined,
  baseline: Pick<TaskRoute, "provider" | "model" | "effort"> | undefined,
): boolean {
  if (!draft || !baseline) return draft === baseline;
  return (
    draft.provider === baseline.provider
    && draft.model.trim() === baseline.model.trim()
    && (draft.effort || "default") === (baseline.effort || "default")
  );
}

export function blockedRouteSaves(
  draft: Partial<Record<ModelTask, DraftRouteValue>>,
  baseline: ModelCatalog["routes"],
  contexts: ProviderContextMap,
): Array<{ task: ModelTask; reason: "missing_active_credential" }> {
  const blocked: Array<{ task: ModelTask; reason: "missing_active_credential" }> = [];
  for (const task of Object.keys(draft) as ModelTask[]) {
    const row = draft[task];
    if (!row || routesSemanticallyEqual(row, baseline[task])) continue;
    if (!contexts[row.provider]) blocked.push({ task, reason: "missing_active_credential" });
  }
  return blocked;
}

export function isTaskTestSnapshotCurrent(
  snapshot: TaskTestSnapshot,
  current: {
    task: ModelTask;
    route: DraftRouteValue;
    credentialId: string | null;
    stale: boolean;
  },
): boolean {
  return !current.stale
    && snapshot.task === current.task
    && snapshot.provider === current.route.provider
    && snapshot.model === current.route.model
    && snapshot.effort === (current.route.effort || "default")
    && snapshot.credential_id === current.credentialId;
}
