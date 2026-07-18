// Shared model metadata helpers that remain independent of selection precedence.
import type {
  CredentialAuthType,
  EffortOption,
  ModelCatalog,
  ModelProvider,
  ProviderCredential,
} from "./api";

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
  if (supported === undefined) {
    const hasModelContracts = catalog.models.some((item) => item.effort_options !== undefined);
    return hasModelContracts
      ? providerOptions.filter((item) => item.id === "default")
      : providerOptions;
  }
  const allowed = new Set(["default", ...supported]);
  return providerOptions.filter((item) => allowed.has(item.id));
}
