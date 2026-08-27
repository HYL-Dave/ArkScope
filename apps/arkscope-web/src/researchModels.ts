// Shared model metadata helpers that remain independent of selection precedence.
import type {
  CredentialAuthType,
  EffortOption,
  ModelCatalog,
  ModelProvider,
  ProviderCredential,
} from "./api";

const TASK_ROUTE_EFFORT_IDS = ["low", "medium", "high", "xhigh", "max"] as const;

export type TaskRouteBlockerReason = "model_retired" | "effort_required";

export function taskRouteModelStatus(
  catalog: ModelCatalog,
  model: string,
): "current" | "retired" | "unknown" {
  const id = model.trim();
  if ((catalog.retired_model_ids ?? []).includes(id)) return "retired";
  if ((catalog.current_model_ids ?? []).includes(id)) return "current";
  return "unknown";
}

export function activeCredential(creds: ProviderCredential[] | undefined): ProviderCredential | null {
  return creds?.find((c) => c.active) ?? null;
}

// A live note when a selected effort will NOT actually apply. null = fine.
export function effortNote(
  provider: ModelProvider,
  authMode: CredentialAuthType | null,
  effort: string,
): string | null {
  void provider;
  void authMode;
  void effort;
  return null;
}

export function effortOptionsForModel(
  catalog: ModelCatalog,
  provider: ModelProvider,
  model: string,
  effectiveEffortIds?: string[],
): EffortOption[] {
  const providerOptions = catalog.effort_options[provider] ?? [];
  const modelOption = catalog.models
    .filter((item) => item.provider === provider && (
      item.id === model || model.startsWith(`${item.id}-`)
    ))
    .sort((left, right) => right.id.length - left.id.length)[0];
  const supported = effectiveEffortIds ?? modelOption?.effort_options;
  const providerIds = new Set(providerOptions.map((item) => item.id));
  const allowed = supported === undefined
    ? providerIds
    : new Set(supported);
  return TASK_ROUTE_EFFORT_IDS
    .filter((id) => providerIds.has(id) && allowed.has(id))
    .map((id) => providerOptions.find((item) => item.id === id)!)
    .filter(Boolean);
}

export function taskRouteBlocker(
  catalog: ModelCatalog,
  route: Pick<{ provider: ModelProvider; model: string; effort: string }, "provider" | "model" | "effort">,
): TaskRouteBlockerReason | null {
  if (taskRouteModelStatus(catalog, route.model) === "retired") return "model_retired";
  const effort = route.effort.trim();
  const supported = effortOptionsForModel(catalog, route.provider, route.model)
    .some((option) => option.id === effort);
  return supported ? null : "effort_required";
}
