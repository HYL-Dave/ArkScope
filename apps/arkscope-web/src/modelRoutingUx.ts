import type {
  EffectiveProviderSummary,
  ModelCatalog,
  ModelProvider,
  ModelTask,
  ProviderCredential,
  TaskRoute,
} from "./api";

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
