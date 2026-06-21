// Pure display helpers for the Settings → Providers credential UX (§11). Extracted
// so the auth-mode-aware labels are unit-testable without a DOM. The core rule:
// a model id is NOT split, but its SOURCE/capability is shown per credential's
// (provider, auth_mode) — never as one global catalog.
import type { CredentialAuthType, ModelProvider } from "./api";

// Discovery-result badge. `provider_api` is ambiguous at the data layer (OpenAI API
// AND the ChatGPT backend both report it), so disambiguate by auth_mode; `seed` is
// the non-live candidate list (claude_code_oauth).
export function discoverySourceLabel(
  provider: ModelProvider,
  authMode: CredentialAuthType | null,
  modelSource: "provider_api" | "seed",
): string {
  if (modelSource === "seed") return "seed · 非即時 discovery";
  if (authMode === "chatgpt_oauth") return "ChatGPT backend · live";
  return provider === "anthropic" ? "Anthropic API · live" : "OpenAI API · live";
}

// Provider-card pill: reflect the ACTIVE credential's mode, not "key set/no key"
// (which misreads an OAuth-only provider as having no credential).
export function credentialPill(
  active: { auth_type: CredentialAuthType } | null,
): { label: string; ok: boolean } {
  if (!active) return { label: "無 credential", ok: false };
  switch (active.auth_type) {
    case "api_key":
    case "api_key_pool":
      return { label: "API key", ok: true };
    case "chatgpt_oauth":
      return { label: "ChatGPT OAuth", ok: true };
    case "claude_code_oauth":
      return { label: "Claude OAuth", ok: true };
    default:
      return { label: active.auth_type, ok: true };
  }
}

export function credentialAvailabilityText(cred: { available: boolean; masked: string | null }): string {
  if (!cred.available) return "缺少";
  return cred.masked ?? "可用";
}

export function supportsCredentialExpiry(authMode: CredentialAuthType): boolean {
  return authMode === "chatgpt_oauth" || authMode === "claude_code_oauth";
}

// Discover-button label: claude_code_oauth has no live discovery API (seed only) →
// 查看候選模型; everything else does live 列模型.
export function discoverButtonLabel(authMode: CredentialAuthType | null): string {
  return authMode === "claude_code_oauth" ? "查看候選模型" : "列模型";
}

// Active credential first (then the rest in their existing order) so the credential
// you're using — and its row actions — sit at the top of the card without scrolling.
// Stable + non-mutating; at most one row is active (single-active per provider).
export function activeFirst<T extends { active: boolean }>(creds: T[]): T[] {
  return [...creds].sort((a, b) => Number(b.active) - Number(a.active));
}

// Unified credential-activation default (API key add AND OAuth/setup-token import):
// take over automatically ONLY in the empty-state — when this provider has no LOCAL DB
// credential yet. A .env fallback row does NOT count (adding your first DB credential
// should take over from the env fallback). Once a DB credential exists, adding/importing
// another is staging/rotation and must not silently switch the active row.
// (ChatGPT OAuth opts out of this default — its execution is unwired, so it defaults
// to NOT active regardless; see the start route.)
export function defaultMakeActiveOnAdd(creds: { id: string }[]): boolean {
  return !creds.some((c) => c.id.startsWith("local:"));
}

export function addApiKeyButtonLabel(makeActive: boolean): string {
  return makeActive ? "新增並設為 active" : "新增 API key";
}

export function addApiKeySuccessMessage(provider: ModelProvider, makeActive: boolean): string {
  return makeActive ? `${provider} key 已新增並設為 active。` : `${provider} key 已新增（未切換 active）。`;
}

export function discoveryHeaderTitle(authMode: CredentialAuthType | null): string {
  return authMode === "claude_code_oauth" ? "查看候選模型" : "列模型結果";
}

export function discoveryResultCredentialLabel(
  credential: { label: string; auth_type: CredentialAuthType } | null,
): string {
  return credential ? `來源：${credential.label} / ${credential.auth_type}` : "來源：未指定 credential";
}
