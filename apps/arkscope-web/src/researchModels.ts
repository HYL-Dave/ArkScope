// Shared model metadata helpers that remain independent of selection precedence.
import type {
  CredentialAuthType,
  EffortOption,
  ExplicitResearchEffort,
  ModelCatalog,
  ModelLifecycleFact,
  ModelProvider,
  ProviderCredential,
} from "./api";

const TASK_ROUTE_EFFORT_IDS = ["low", "medium", "high", "xhigh", "max"] as const;

export type TaskRouteBlockerReason = "model_retired" | "effort_required";

export function isTaskRouteEffort(value: string): value is ExplicitResearchEffort {
  return (TASK_ROUTE_EFFORT_IDS as readonly string[]).includes(value);
}

export function taskRouteModelStatus(
  catalog: ModelCatalog,
  provider: ModelProvider,
  model: string,
): "current" | "retired" | "unknown" {
  const match = matchModelLifecycle(catalog, model);
  return match?.provider === provider ? match.task_route_status : "unknown";
}

function inferredProvider(model: string): ModelProvider | null {
  const normalized = model.trim().toLowerCase();
  if (normalized.startsWith("claude-")) return "anthropic";
  if (normalized.startsWith("gpt-") || normalized.startsWith("o")) return "openai";
  return null;
}

function lifecycleFacts(catalog: ModelCatalog): ModelLifecycleFact[] {
  if (catalog.model_lifecycle?.length) return catalog.model_lifecycle;

  const models = new Map(catalog.models.map((model) => [model.id.toLowerCase(), model]));
  const facts = new Map<string, ModelLifecycleFact>();
  const append = (id: string, status: "current" | "retired") => {
    const option = models.get(id.toLowerCase());
    const provider = option?.provider ?? inferredProvider(id);
    if (!provider) return;
    facts.set(id.toLowerCase(), {
      id,
      provider,
      task_route_status: option?.task_route_status ?? status,
      aliases: option?.aliases ?? [],
    });
  };
  for (const id of catalog.current_model_ids ?? []) append(id, "current");
  for (const id of catalog.retired_model_ids ?? []) append(id, "retired");
  for (const option of catalog.models) {
    if (option.task_route_status) append(option.id, option.task_route_status);
  }
  return [...facts.values()];
}

export function matchModelLifecycle(
  catalog: ModelCatalog,
  model: string,
): ModelLifecycleFact | null {
  const query = model.trim().toLowerCase();
  if (!query) return null;
  const facts = lifecycleFacts(catalog);
  const exact = facts.find((fact) => (
    fact.id.toLowerCase() === query
    || (fact.aliases ?? []).some((alias) => alias.toLowerCase() === query)
  ));
  if (exact) return exact;
  return [...facts]
    .sort((left, right) => right.id.length - left.id.length)
    .find((fact) => query.startsWith(fact.id.toLowerCase())) ?? null;
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
  const lifecycle = matchModelLifecycle(catalog, model);
  if (lifecycle && lifecycle.provider !== provider) return [];
  const modelOption = lifecycle
    ? catalog.models.find((item) => item.id.toLowerCase() === lifecycle.id.toLowerCase())
    : undefined;
  const supported = effectiveEffortIds !== undefined
    ? effectiveEffortIds
    : lifecycle
      ? modelOption?.effort_options ?? []
      : undefined;
  const providerIds = new Set(providerOptions.map((item) => item.id));
  const allowed = supported === undefined
    ? providerIds
    : new Set(supported);
  const taskRouteOrder = catalog.task_route_effort_order === undefined
    ? TASK_ROUTE_EFFORT_IDS
    : catalog.task_route_effort_order.filter(isTaskRouteEffort);
  return taskRouteOrder
    .filter((id) => providerIds.has(id) && allowed.has(id))
    .map((id) => providerOptions.find((item) => item.id === id)!)
    .filter(Boolean);
}

export function taskRouteBlocker(
  catalog: ModelCatalog,
  route: Pick<{ provider: ModelProvider; model: string; effort: string }, "provider" | "model" | "effort">,
): TaskRouteBlockerReason | null {
  if (taskRouteModelStatus(catalog, route.provider, route.model) === "retired") return "model_retired";
  const effort = route.effort.trim();
  const supported = effortOptionsForModel(catalog, route.provider, route.model)
    .some((option) => option.id === effort);
  return supported ? null : "effort_required";
}
