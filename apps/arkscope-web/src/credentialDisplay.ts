// Pure display helpers for the Settings → Providers credential UX (§11). Extracted
// so the auth-mode-aware labels are unit-testable without a DOM. The core rule:
// a model id is NOT split, but its SOURCE/capability is shown per credential's
// (provider, auth_mode) — never as one global catalog.
import type { CredentialAuthType, ModelProvider } from "./api";
import type { SettingsT } from "./settings/settingsCopy";

// Discovery-result badge. `provider_api` is ambiguous at the data layer (OpenAI API
// AND the ChatGPT backend both report it), so disambiguate by auth_mode; `seed` is
// the non-live candidate list (claude_code_oauth).
function discoveryApiProviderLabel(provider: ModelProvider, t: SettingsT): string {
  return provider === "anthropic"
    ? t(($) => $.models.providers.anthropic)
    : t(($) => $.models.providers.openai);
}

export function discoverySourceLabel(
  provider: ModelProvider,
  authMode: CredentialAuthType | null,
  modelSource: "provider_api" | "seed",
  t: SettingsT,
): string {
  if (modelSource === "seed") return t(($) => $.providers.discovery.seedNotice);
  const source = authMode === "chatgpt_oauth"
    ? t(($) => $.providers.authModes.chatgptOAuth)
    : `${discoveryApiProviderLabel(provider, t)} API`;
  return [source, " · ", t(($) => $.models.catalog.visibleListLoaded)].join("");
}

// Provider-card pill: reflect the ACTIVE credential's mode, not "key set/no key"
// (which misreads an OAuth-only provider as having no credential).
export function credentialPill(
  active: { auth_type: CredentialAuthType } | null,
  t: SettingsT,
): { label: string; ok: boolean } {
  if (!active) return { label: t(($) => $.models.credentials.missing), ok: false };
  switch (active.auth_type) {
    case "api_key":
      return { label: t(($) => $.providers.authModes.apiKey), ok: true };
    case "api_key_pool":
      return { label: t(($) => $.providers.authModes.apiKeyPool), ok: true };
    case "chatgpt_oauth":
      return { label: t(($) => $.providers.authModes.chatgptOAuth), ok: true };
    case "claude_code_oauth":
      return { label: t(($) => $.providers.authModes.claudeCodeOAuth), ok: true };
    default:
      return { label: active.auth_type, ok: true };
  }
}

export function credentialAvailabilityText(
  cred: { available: boolean; masked: string | null },
  t: SettingsT,
): string {
  if (!cred.available) return t(($) => $.providers.credential.unavailable);
  return cred.masked ?? t(($) => $.dataStorage.available);
}

// Only claude_code_oauth exposes a user-set expiry. chatgpt_oauth's access token is
// short-lived (~240h JWT) but AUTO-REFRESHES (refresh_if_needed → refresh_token grant),
// so a manual expiry would be meaningless + overwritten — don't show/edit it. api_key
// has no expiry. (See chatgpt_oauth_login.refresh_if_needed.)
export function supportsCredentialExpiry(authMode: CredentialAuthType): boolean {
  return authMode === "claude_code_oauth";
}

// Date-picker conversions for the claude_code_oauth expiry (a <input type="date">
// speaks YYYY-MM-DD; the store keeps a canonical ISO). Empty round-trips to empty so
// the field can be cleared (留空).
export function isoToDateInput(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toISOString().slice(0, 10); // YYYY-MM-DD (UTC)
}

export function dateInputToIso(dateInput: string): string {
  const v = (dateInput || "").trim();
  return v ? `${v}T00:00:00+00:00` : "";
}

// Discover-button label: claude_code_oauth has no live discovery API (seed only) →
// 查看候選模型; everything else does live 列模型.
export function discoverButtonLabel(authMode: CredentialAuthType | null, t: SettingsT): string {
  return authMode === "claude_code_oauth"
    ? t(($) => $.providers.discovery.candidates)
    : t(($) => $.providers.discovery.listModels);
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
// (ChatGPT OAuth opts out of this default — logging in must never silently switch
// the active credential, so it defaults to NOT active regardless; see the start route.)
export function defaultMakeActiveOnAdd(creds: { id: string }[]): boolean {
  return !creds.some((c) => c.id.startsWith("local:"));
}

export function addApiKeyButtonLabel(makeActive: boolean, t: SettingsT): string {
  return makeActive
    ? t(($) => $.providers.credential.addAsActive)
    : t(($) => $.providers.credential.addApiKey);
}

export function addApiKeySuccessMessage(
  provider: ModelProvider | string,
  makeActive: boolean,
  t: SettingsT,
): string {
  const state = makeActive
    ? t(($) => $.providers.credential.active)
    : t(($) => $.providers.credential.inactive);
  return [provider, ": ", state].join("");
}

export function discoveryHeaderTitle(authMode: CredentialAuthType | null, t: SettingsT): string {
  return authMode === "claude_code_oauth"
    ? t(($) => $.providers.discovery.candidates)
    : t(($) => $.providers.discovery.listModels);
}

export function discoveryResultCredentialLabel(
  credential: { label: string; auth_type: CredentialAuthType } | null,
  t: SettingsT,
): string {
  const value = credential
    ? `${credential.label} / ${credential.auth_type}`
    : t(($) => $.providers.credential.unnamed);
  return [t(($) => $.providers.credential.source), ": ", value].join("");
}
