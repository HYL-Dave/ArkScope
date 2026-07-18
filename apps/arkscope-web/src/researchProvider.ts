export const RESEARCH_PROVIDER_IDS = ["anthropic", "openai"] as const;
export type ResearchProviderId = (typeof RESEARCH_PROVIDER_IDS)[number];

export function asResearchProviderId(value: string | null | undefined): ResearchProviderId | null {
  return value === "anthropic" || value === "openai" ? value : null;
}
