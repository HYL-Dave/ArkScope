export const RESEARCH_PROVIDER_IDS = ["anthropic", "openai"] as const;
export type ResearchProviderId = (typeof RESEARCH_PROVIDER_IDS)[number];

export function asResearchProviderId(value: string | null | undefined): ResearchProviderId | null {
  return value === "anthropic" || value === "openai" ? value : null;
}

export function chooseResearchProvider({
  currentProvider,
  activeThreadProvider,
  availableIds,
  autoRouteSelection,
  configuredProvider,
}: {
  currentProvider: ResearchProviderId | null;
  activeThreadProvider: ResearchProviderId | null;
  availableIds: ResearchProviderId[];
  autoRouteSelection: boolean;
  configuredProvider?: ResearchProviderId | null;
}): ResearchProviderId | null {
  const available = new Set(availableIds);
  if (activeThreadProvider && autoRouteSelection) {
    return available.has(activeThreadProvider) ? activeThreadProvider : null;
  }
  if (currentProvider && available.has(currentProvider)) return currentProvider;
  if (autoRouteSelection && configuredProvider && available.has(configuredProvider)) return configuredProvider;
  if (autoRouteSelection && availableIds.length === 1) return availableIds[0];
  return null;
}
