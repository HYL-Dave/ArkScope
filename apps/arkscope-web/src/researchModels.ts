// Pure helpers for the AI 研究 model/effort picker — extracted so the option/default
// logic is unit-testable without a DOM or network (mirrors researchProvider.ts /
// chatgptOAuth.ts). The component owns the discovery FETCH; these decide what the
// dropdown shows and what's selected.
import type { CredentialAuthType, ProviderCredential, ModelProvider } from "./api";

export function activeCredential(creds: ProviderCredential[] | undefined): ProviderCredential | null {
  return creds?.find((c) => c.active) ?? null;
}

// Ordered, de-duped, trimmed model options. Discovered (per-auth-mode) models come
// first; the current route model is ALWAYS included so a saved choice stays
// selectable even when discovery is empty/stale.
export function modelOptions(discovered: string[], routeModel: string): string[] {
  const out: string[] = [];
  const seen = new Set<string>();
  for (const m of [...discovered, routeModel]) {
    const v = (m || "").trim();
    if (v && !seen.has(v)) {
      seen.add(v);
      out.push(v);
    }
  }
  return out;
}

// Keep the current selection if still valid; else the route model if present; else
// the first option (else empty).
export function defaultModel(options: string[], routeModel: string, current?: string | null): string {
  if (current && options.includes(current)) return current;
  if (routeModel && options.includes(routeModel)) return routeModel;
  return options[0] ?? routeModel ?? "";
}

// A live note when a selected effort will NOT actually apply: the Claude-subscription
// (claude_code_oauth) path derives its own effort. Mirrors the backend save-time
// warning (route_capability_warnings) so the user sees it at pick time too. null = fine.
export function effortNote(
  provider: ModelProvider,
  authMode: CredentialAuthType | null,
  effort: string,
): string | null {
  const hasEffort = (effort || "").trim() !== "" && effort !== "default";
  if (provider === "anthropic" && authMode === "claude_code_oauth" && hasEffort) {
    return `Claude 訂閱（claude_code_oauth）會自行決定 reasoning effort — 所選的「${effort}」不會套用。`;
  }
  return null;
}
