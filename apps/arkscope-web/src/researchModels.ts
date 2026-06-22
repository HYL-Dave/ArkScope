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
// selectable even when discovery is empty/stale. A historical model from the
// active thread is also included so old conversations can show what was used even
// after Settings defaults or discovery results change.
export function modelOptions(discovered: string[], routeModel: string, historicalModel?: string | null): string[] {
  const out: string[] = [];
  const seen = new Set<string>();
  for (const m of [...discovered, routeModel, historicalModel ?? ""]) {
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

export interface MinimalResearchMessage {
  role: string;
  model?: string | null;
  effort?: string | null;
}

export function lastAssistantSelection(messages: MinimalResearchMessage[]): { model: string | null; effort: string | null } {
  for (let i = messages.length - 1; i >= 0; i--) {
    const m = messages[i];
    if (m.role !== "assistant") continue;
    const model = (m.model ?? "").trim() || null;
    const effort = (m.effort ?? "").trim();
    return { model, effort: effort && effort !== "default" ? effort : null };
  }
  return { model: null, effort: null };
}
