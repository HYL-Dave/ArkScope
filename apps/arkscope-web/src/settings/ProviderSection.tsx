import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import {
  addCredential,
  cancelOpenAIOAuth,
  completeOpenAIOAuthManual,
  deleteCredential,
  importOAuthCredential,
  openAIOAuthStatus,
  probeCredential,
  startOpenAIOAuth,
  updateCredential,
  type ModelCatalog,
  type ModelDiscoveryResult,
  type ModelProvider,
  type ModelTask,
  type ProbeResponse,
  type ProviderCredential,
  type RuntimeConfig,
} from "../api";
import {
  activeFirst,
  addApiKeyButtonLabel,
  addApiKeySuccessMessage,
  credentialAvailabilityText,
  credentialPill,
  dateInputToIso,
  defaultMakeActiveOnAdd,
  discoverButtonLabel,
  discoveryHeaderTitle,
  discoveryResultCredentialLabel,
  discoverySourceLabel,
  isoToDateInput,
  supportsCredentialExpiry,
} from "../credentialDisplay";
import {
  buildManualCompletion,
  pollOAuthStatus,
  probeDisplayLabel,
  probeDisplaySummary,
  probeRuntimeNote,
} from "../chatgptOAuth";
import { formatSystemTimestamp } from "../timeDisplay";
import { ConfirmDialog } from "../ui";
import { DeveloperDiagnostics } from "./DeveloperDiagnostics";
import { modelReasonLabel, settingsErrorPresentation } from "./settingsBackendCopy";
import type { SettingsT } from "./settingsCopy";
import {
  CLEAR_SETTINGS_NAVIGATION_GUARD,
  type SettingsNavigationGuardReporter,
} from "./settingsNavigationGuard";

export type DiscoveryState = Partial<Record<ModelProvider, {
  loading: boolean;
  result: ModelDiscoveryResult | null;
  credentialId: string | null;
}>>;

type CredentialMetadataDraft = {
  account_label?: string;
  expires_at?: string;
};

type ProviderNotice =
  | { kind: "api_key_added"; provider: ModelProvider; makeActive: boolean }
  | { kind: "claude_imported" }
  | { kind: "link_copied" }
  | { kind: "oauth_signed_in" }
  | { kind: "oauth_signed_in_manual" }
  | { kind: "active_updated" }
  | { kind: "display_updated" }
  | { kind: "deleted" };

type ProviderFailure =
  | { kind: "empty_key"; provider: ModelProvider }
  | { kind: "empty_claude_token" }
  | { kind: "copy_unsupported" }
  | { kind: "copy_denied" }
  | { kind: "oauth_timeout" }
  | { kind: "oauth_error"; detail: string; manualCompletable: boolean }
  | { kind: "oauth_expired" }
  | { kind: "missing_code" }
  | { kind: "request"; error: unknown };

function providerNoticeText(notice: ProviderNotice, t: SettingsT): string {
  switch (notice.kind) {
    case "api_key_added":
      return addApiKeySuccessMessage(notice.provider, notice.makeActive, t);
    case "claude_imported":
      return t(($) => $.providers.claude.imported);
    case "link_copied":
      return t(($) => $.providers.openAI.copied);
    case "oauth_signed_in":
      return t(($) => $.providers.openAI.signedIn);
    case "oauth_signed_in_manual":
      return t(($) => $.providers.openAI.signedInManual);
    case "active_updated":
      return t(($) => $.providers.credential.activeUpdated);
    case "display_updated":
      return t(($) => $.providers.credential.displayUpdated);
    case "deleted":
      return t(($) => $.providers.credential.deleted);
  }
}

function providerFailureText(failure: ProviderFailure, t: SettingsT): string {
  switch (failure.kind) {
    case "empty_key":
      return t(($) => $.providers.credential.emptyKey, { providerId: failure.provider });
    case "empty_claude_token":
      return t(($) => $.providers.claude.emptyToken);
    case "copy_unsupported":
      return t(($) => $.providers.openAI.copyUnsupported);
    case "copy_denied":
      return t(($) => $.providers.openAI.copyDenied);
    case "oauth_timeout":
      return t(($) => $.providers.openAI.callbackTimeout);
    case "oauth_error":
      return failure.manualCompletable
        ? t(($) => $.providers.openAI.callbackTimeout)
        : t(($) => $.providers.openAI.sessionExpired);
    case "oauth_expired":
      return t(($) => $.providers.openAI.sessionExpired);
    case "missing_code":
      return t(($) => $.providers.openAI.missingCode);
    case "request":
      return settingsErrorPresentation(failure.error, t).message;
  }
}

function providerFailureDiagnostic(failure: ProviderFailure | null, t: SettingsT): string | null {
  if (!failure) return null;
  if (failure.kind === "oauth_error") return failure.detail;
  if (failure.kind === "request") return settingsErrorPresentation(failure.error, t).diagnostic;
  return null;
}

function discoveryStatusLabel(
  status: ModelDiscoveryResult["status"],
  t: SettingsT,
): string {
  switch (status) {
    case "ok":
      return t(($) => $.dataStorage.available);
    case "missing_credential":
      return t(($) => $.models.credentials.missing);
    case "unsupported":
      return t(($) => $.models.test.unsupported);
    case "error":
      return t(($) => $.providers.discovery.failure);
  }
}

export function ProviderSection({
  catalog,
  runtime,
  discovery,
  onRefresh,
  onDiscover,
  onClearDiscovery,
  onUseModel,
  onNavigationGuardChange,
  developerMode = false,
}: {
  catalog: ModelCatalog;
  runtime: RuntimeConfig | null;
  discovery: DiscoveryState;
  onRefresh: () => Promise<void>;
  onDiscover: (provider: ModelProvider, credentialId: string | null) => Promise<void>;
  onClearDiscovery: (provider: ModelProvider) => void;
  onUseModel: (provider: ModelProvider, model: string, task: ModelTask) => void;
  onNavigationGuardChange?: SettingsNavigationGuardReporter;
  developerMode?: boolean;
}) {
  const { t } = useTranslation("settings");
  const [selectedCreds, setSelectedCreds] = useState<Partial<Record<ModelProvider, string>>>({});
  const [newAlias, setNewAlias] = useState<Partial<Record<ModelProvider, string>>>({});
  const [newSecret, setNewSecret] = useState<Partial<Record<ModelProvider, string>>>({});
  const [newMakeActive, setNewMakeActive] = useState<Partial<Record<ModelProvider, boolean>>>({});
  // OAuth/setup-token "set active on add?" choice (per provider). Undefined = the
  // unified default (Claude: active iff no local DB credential; ChatGPT: always off —
  // logging in must never silently switch the active credential).
  const [oauthMakeActive, setOauthMakeActive] = useState<Partial<Record<ModelProvider, boolean>>>({});
  const [renames, setRenames] = useState<Record<string, string>>({});
  const [metadataDrafts, setMetadataDrafts] = useState<Record<string, CredentialMetadataDraft>>({});
  // Per-provider disclosure state for the (low-frequency) setup forms. Undefined =
  // use the smart default (collapsed once the provider has any usable credential);
  // a user toggle pins it. Keyed by provider so toggling one card doesn't move others.
  const [setupOpen, setSetupOpen] = useState<Record<string, boolean>>({});
  const [providerMsg, setProviderMsg] = useState<ProviderNotice | null>(null);
  const [providerErr, setProviderErr] = useState<ProviderFailure | null>(null);
  // Claude setup-token import (anthropic only). The token is held in form state
  // only until submit, then cleared — it never persists in React beyond that.
  const [claudeAlias, setClaudeAlias] = useState("");
  const [claudeLabel, setClaudeLabel] = useState("");
  const [claudeToken, setClaudeToken] = useState("");
  // OpenAI ChatGPT in-app OAuth login (openai only). Holds only the public state +
  // auth_url for an in-flight login; no token ever reaches the UI.
  const [oauth, setOauth] = useState<{ state: string; authUrl: string; phase: "waiting" | "manual" } | null>(null);
  // Split busy state: the long (≤180s) loopback poll must NOT disable the manual
  // "完成登入" button — otherwise a stuck popup/callback locks out the fallback.
  const [pollBusy, setPollBusy] = useState(false);
  const [manualBusy, setManualBusy] = useState(false);
  const [manualValue, setManualValue] = useState("");
  const [credentialMutationCount, setCredentialMutationCount] = useState(0);
  const [credentialProbeBusy, setCredentialProbeBusy] = useState(false);
  // ONE ChatGPT login/re-login flow at a time: :1455 is a fixed loopback port, so
  // every trigger (登入 ChatGPT / row 重新登入 / discovery reauth hint) shares this.
  const chatgptLoginBusy = pollBusy || manualBusy || oauth != null;
  // Cooperative abort for the in-flight poll, so a manual completion or a cancel
  // stops it immediately (rather than leaving it to run — and pin pollBusy — for the
  // full timeout). A per-login token object; the poll closure reads token.aborted.
  const pollToken = useRef<{ aborted: boolean }>({ aborted: false });

  const onCredentialNavigationGuardChange = useCallback(
    (guard: { busy: boolean }) => setCredentialProbeBusy(guard.busy),
    [],
  );
  const providerDirty = [
    ...Object.values(newAlias),
    ...Object.values(newSecret),
    claudeAlias,
    claudeLabel,
    claudeToken,
    manualValue,
  ].some((value) => value !== "")
    || Object.keys(renames).length > 0
    || Object.keys(metadataDrafts).length > 0
    || Object.entries(newMakeActive).some(([provider, value]) => {
      const credentials = catalog.credentials?.[provider as ModelProvider] ?? [];
      return value !== defaultMakeActiveOnAdd(credentials);
    })
    || Object.entries(oauthMakeActive).some(([provider, value]) => {
      const credentials = catalog.credentials?.[provider as ModelProvider] ?? [];
      const defaultValue = provider === "anthropic" ? defaultMakeActiveOnAdd(credentials) : false;
      return value !== defaultValue;
    });
  const providerBusy = credentialMutationCount > 0
    || pollBusy
    || manualBusy
    || oauth !== null
    || credentialProbeBusy;

  useEffect(() => {
    onNavigationGuardChange?.({
      dirty: providerDirty,
      busy: providerBusy,
      reason: providerBusy
        ? t(($) => $.providers.guard.busy)
        : providerDirty
          ? t(($) => $.providers.guard.dirty)
          : null,
    });
  }, [onNavigationGuardChange, providerBusy, providerDirty, t]);

  useEffect(() => () => {
    onNavigationGuardChange?.(CLEAR_SETTINGS_NAVIGATION_GUARD);
  }, [onNavigationGuardChange]);

  function beginCredentialMutation() {
    setCredentialMutationCount((count) => count + 1);
  }

  function endCredentialMutation() {
    setCredentialMutationCount((count) => Math.max(0, count - 1));
  }

  async function addKey(provider: ModelProvider, makeActive: boolean) {
    const alias = (newAlias[provider] ?? "").trim();
    const secret = (newSecret[provider] ?? "").trim();
    if (!secret) {
      setProviderErr({ kind: "empty_key", provider });
      return;
    }
    setProviderErr(null);
    setProviderMsg(null);
    beginCredentialMutation();
    try {
      await addCredential({
        provider,
        auth_type: "api_key",
        alias: alias || `${provider} ${t(($) => $.providers.authModes.apiKey)}`,
        secret,
        make_active: makeActive,
      });
      setNewAlias((prev) => ({ ...prev, [provider]: "" }));
      setNewSecret((prev) => ({ ...prev, [provider]: "" }));
      setProviderMsg({ kind: "api_key_added", provider, makeActive });
      await onRefresh();
    } catch (e) {
      setProviderErr({ kind: "request", error: e });
    } finally {
      endCredentialMutation();
    }
  }

  async function importClaudeToken(makeActive: boolean) {
    const token = claudeToken.trim();
    if (!token) {
      setProviderErr({ kind: "empty_claude_token" });
      return;
    }
    setProviderErr(null);
    setProviderMsg(null);
    beginCredentialMutation();
    try {
      await importOAuthCredential({
        provider: "anthropic",
        auth_mode: "claude_code_oauth",
        alias: claudeAlias.trim() || t(($) => $.providers.authModes.claudeCodeOAuth),
        token,
        account_label: claudeLabel.trim() || undefined,
        make_active: makeActive,
      });
      setClaudeToken(""); // clear the token from state immediately on success
      setClaudeAlias("");
      setClaudeLabel("");
      setProviderMsg({ kind: "claude_imported" });
      await onRefresh();
    } catch (e) {
      setClaudeToken(""); // also clear on failure — don't keep the token around
      setProviderErr({ kind: "request", error: e });
    } finally {
      endCredentialMutation();
    }
  }

  async function copyLoginLink() {
    if (!oauth?.authUrl) return;
    if (!navigator.clipboard) {
      setProviderErr({ kind: "copy_unsupported" });
      return;
    }
    try {
      await navigator.clipboard.writeText(oauth.authUrl);
      setProviderMsg({ kind: "link_copied" });
    } catch {
      setProviderErr({ kind: "copy_denied" });
    }
  }

  async function startChatGPTLogin(makeActive: boolean, reloginCredentialId?: string) {
    setProviderErr(null);
    setProviderMsg(null);
    setPollBusy(true);
    const token = { aborted: false }; // this login's abort token; manual/cancel flips it
    pollToken.current = token;
    try {
      const r = await startOpenAIOAuth(makeActive, reloginCredentialId);
      setOauth({ state: r.state, authUrl: r.auth_url, phase: "waiting" });
      // open the browser login; if a popup blocker eats it, the copy-link button is the fallback
      window.open(r.auth_url, "_blank", "noopener,noreferrer");
      const res = await pollOAuthStatus(r.state, {
        statusFn: openAIOAuthStatus,
        now: () => Date.now(),
        sleep: (ms) => new Promise<void>((resolve) => window.setTimeout(resolve, ms)),
        shouldAbort: () => token.aborted,
      });
      if (res.kind === "aborted") return; // a manual completion / cancel superseded this poll
      if (res.kind === "success") {
        setOauth(null);
        setProviderMsg({ kind: "oauth_signed_in" });
        await onRefresh();
      } else if (res.kind === "timeout") {
        setOauth((o) => (o ? { ...o, phase: "manual" } : o));
        setProviderErr({ kind: "oauth_timeout" });
      } else if (res.kind === "error") {
        // surface the backend reason as-is — NO silent fallback to an API key.
        // F4: offer the manual paste ONLY when it can still succeed (the state
        // wasn't consumed by a failed completion) — else reset the flow.
        if (res.manualCompletable) {
          setOauth((o) => (o ? { ...o, phase: "manual" } : o));
          setProviderErr({ kind: "oauth_error", detail: res.detail, manualCompletable: true });
        } else {
          setOauth(null);
          setProviderErr({ kind: "oauth_error", detail: res.detail, manualCompletable: false });
        }
      } else {
        setOauth(null);
        setProviderErr({ kind: "oauth_expired" });
      }
    } catch (e) {
      setProviderErr({ kind: "request", error: e });
    } finally {
      setPollBusy(false);
    }
  }

  // S3 re-login: replace an existing chatgpt_oauth credential's token IN PLACE
  // (no new row; alias/active preserved). First expand the OpenAI setup
  // disclosure — the waiting/manual/cancel controls already live there — then
  // run the SAME login flow with the target id. All triggers share the
  // chatgptLoginBusy guard so two flows can't race for the :1455 callback port.
  function startChatGPTRelogin(credentialId: string) {
    setSetupOpen((prev) => ({ ...prev, openai: true }));
    setSelectedCreds((prev) => ({ ...prev, openai: credentialId }));
    void startChatGPTLogin(false, credentialId);
  }

  function cancelChatGPTLogin() {
    pollToken.current.aborted = true; // stop the background poll (frees the 登入 button)
    const st = oauth?.state;
    // Also cancel server-side: evict the pending login so a late browser callback can't
    // still create a credential, and free the loopback port. Best-effort.
    if (st) void cancelOpenAIOAuth(st).catch(() => {});
    setOauth(null);
    setManualValue("");
  }

  async function completeChatGPTManual() {
    if (!oauth) return;
    const pasted = manualValue.trim();
    if (!pasted) {
      setProviderErr({ kind: "missing_code" });
      return;
    }
    setProviderErr(null);
    setProviderMsg(null);
    setManualBusy(true);
    try {
      await completeOpenAIOAuthManual(buildManualCompletion(oauth.state, pasted));
      pollToken.current.aborted = true; // manual won — stop the still-running loopback poll
      setManualValue("");
      setOauth(null);
      setProviderMsg({ kind: "oauth_signed_in_manual" });
      await onRefresh();
    } catch (e) {
      // a bad/expired/forged state or a token-exchange error 400s here — show it, no fallback
      setProviderErr({ kind: "request", error: e });
    } finally {
      setManualBusy(false);
    }
  }

  async function setActive(credentialId: string) {
    setProviderErr(null);
    setProviderMsg(null);
    beginCredentialMutation();
    try {
      await updateCredential(credentialId, { active: true });
      setProviderMsg({ kind: "active_updated" });
      await onRefresh();
    } catch (e) {
      setProviderErr({ kind: "request", error: e });
    } finally {
      endCredentialMutation();
    }
  }

  async function saveCredentialDetails(
    credentialId: string,
    alias: string,
    accountLabel: string,
    expiresAt?: string,
  ) {
    setProviderErr(null);
    setProviderMsg(null);
    beginCredentialMutation();
    try {
      const cleanAlias = alias.trim();
      const body: { alias?: string; account_label: string; expires_at?: string } = {
        account_label: accountLabel.trim(),
      };
      if (cleanAlias) body.alias = cleanAlias;
      if (expiresAt !== undefined) body.expires_at = expiresAt.trim();
      await updateCredential(credentialId, body);
      setRenames((prev) => {
        const next = { ...prev };
        delete next[credentialId];
        return next;
      });
      setMetadataDrafts((prev) => {
        const next = { ...prev };
        delete next[credentialId];
        return next;
      });
      setProviderMsg({ kind: "display_updated" });
      await onRefresh();
    } catch (e) {
      setProviderErr({ kind: "request", error: e });
    } finally {
      endCredentialMutation();
    }
  }

  async function removeKey(credentialId: string) {
    setProviderErr(null);
    setProviderMsg(null);
    beginCredentialMutation();
    try {
      await deleteCredential(credentialId);
      setProviderMsg({ kind: "deleted" });
      await onRefresh();
    } catch (e) {
      setProviderErr({ kind: "request", error: e });
    } finally {
      endCredentialMutation();
    }
  }

  const providerErrorText = providerErr ? providerFailureText(providerErr, t) : null;
  const providerDiagnostic = providerFailureDiagnostic(providerErr, t);

  return (
    <>
      <div className="settings-section-head">
        <div>
          <h2>{t(($) => $.providers.section.title)}</h2>
          <p className="muted">{t(($) => $.providers.section.description)}</p>
        </div>
      </div>
      {providerErrorText && <p className="error-text">{providerErrorText}</p>}
      {developerMode ? <DeveloperDiagnostics diagnostics={[providerDiagnostic]} t={t} /> : null}
      {providerMsg && <p className="ok-text">{providerNoticeText(providerMsg, t)}</p>}
      <div className="provider-grid">
        {catalog.providers.map((provider) => {
          const models = catalog.models.filter((m) => m.provider === provider);
          const credentials =
            catalog.credentials?.[provider] ??
            (provider === "anthropic" ? runtime?.anthropic.credentials : runtime?.openai.credentials) ??
            [];
          const activeCred = credentials.find((c) => c.active && c.available) ?? null;
          const pill = credentialPill(activeCred, t);
          // Smart-collapse the setup forms: expanded only when the provider has NO
          // usable credential (the empty-state where setup IS the task); a user
          // toggle (setupOpen[provider]) overrides.
          const hasCredential = credentials.some((c) => c.available);
          const setupExpanded = setupOpen[provider] ?? !hasCredential;
          const makeNewKeyActive = newMakeActive[provider] ?? defaultMakeActiveOnAdd(credentials);
          // Claude import default = same empty-state rule; ChatGPT default = OFF (never
          // silently switch the active credential).
          const claudeImportActive = oauthMakeActive.anthropic ?? defaultMakeActiveOnAdd(credentials);
          const chatgptLoginActive = oauthMakeActive.openai ?? false;
          const sourceUrls = Array.from(new Set(models.map((m) => m.source_url)));
          const discoveryState = discovery[provider];
          const usable = credentials.filter((c) => c.available && c.can_discover_models);
          const activeUsable = usable.find((c) => c.active);
          const selectedDraft = selectedCreds[provider];
          const selectedCredential = usable.some((c) => c.id === selectedDraft)
            ? selectedDraft ?? null
            : activeUsable?.id ?? usable[0]?.id ?? null;
          const selectedAuthMode = usable.find((c) => c.id === selectedCredential)?.auth_type ?? null;
          // auth_mode of the credential that produced the current discovery result
          const discoveredAuthMode = discoveryState?.result
            ? credentials.find((c) => c.id === discoveryState.result?.credential_id)?.auth_type ?? null
            : null;
          const discoveredCredential = discoveryState?.result
            ? credentials.find((c) => c.id === discoveryState.result?.credential_id) ?? null
            : null;
          return (
            <div className="settings-panel provider-card" key={provider}>
              <div className="settings-panel-head">
                <div>
                  <h2>{provider}</h2>
                  <p className="muted">
                    {t(($) => $.providers.discovery.modelCount, { count: models.length })}
                    {" · "}
                    {t(($) => $.providers.discovery.directIdAllowed)}
                  </p>
                </div>
                <span className={`key-pill ${pill.ok ? "ok" : "missing"}`}>
                  {pill.label}
                </span>
              </div>
              <div className="provider-model-list">
                {models.map((model) => (
                  <span key={model.id}>{model.id}</span>
                ))}
              </div>
              {/* High-frequency first: your credentials + their row actions (active row first). */}
              <CredentialList
                credentials={activeFirst(credentials)}
                renames={renames}
                metadataDrafts={metadataDrafts}
                onRenameDraft={(id, alias) => setRenames((prev) => ({ ...prev, [id]: alias }))}
                onMetadataDraft={(id, field, value) => setMetadataDrafts((prev) => ({
                  ...prev,
                  [id]: { ...prev[id], [field]: value },
                }))}
                onSaveCredentialDetails={(id, alias, accountLabel, expiresAt) =>
                  void saveCredentialDetails(id, alias, accountLabel, expiresAt)}
                onSetActive={(id) => void setActive(id)}
                onDelete={(id) => void removeKey(id)}
                onDiscover={(id) => void onDiscover(provider, id)}
                discoverLoadingId={discoveryState?.loading ? discoveryState.credentialId ?? null : null}
                onRelogin={provider === "openai" ? startChatGPTRelogin : undefined}
                reloginBusy={chatgptLoginBusy}
                onNavigationGuardChange={onCredentialNavigationGuardChange}
                developerMode={developerMode}
              />
              {discoveryState?.result && (
                <DiscoveryResultView
                  result={discoveryState.result}
                  authMode={discoveredAuthMode}
                  credentialLabel={discoveredCredential?.label ?? null}
                  onClose={() => onClearDiscovery(provider)}
                  onUse={(model, task) => onUseModel(provider, model, task)}
                  onRelogin={
                    provider === "openai" && discoveryState.result.credential_id
                      ? () => startChatGPTRelogin(discoveryState.result!.credential_id!)
                      : undefined
                  }
                  reloginBusy={chatgptLoginBusy}
                  developerMode={developerMode}
                />
              )}
              <div className="settings-actions">
                <p className="muted tiny" style={{ width: "100%" }}>
                  {t(($) => $.providers.discovery.description)}
                </p>
                <label className="field credential-select">
                  <span>{t(($) => $.providers.discovery.credentialLabel)}</span>
                  <select
                    value={selectedCredential ?? ""}
                    onChange={(e) => setSelectedCreds((prev) => ({ ...prev, [provider]: e.target.value }))}
                  >
                    {usable.map((cred) => (
                      <option key={cred.id} value={cred.id}>
                        {cred.active ? "★ " : ""}{cred.label} · {cred.masked ?? cred.source}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  type="button"
                  className="btn-ghost small"
                  disabled={!selectedCredential || discoveryState?.loading}
                  onClick={() => void onDiscover(provider, selectedCredential)}
                >
                  {discoveryState?.loading
                    ? t(($) => $.providers.discovery.listing)
                    : discoverButtonLabel(selectedAuthMode, t)}
                </button>
              </div>
              {/* Low-frequency setup: collapsed once a usable credential exists. */}
              <SetupDisclosure
                provider={provider}
                open={setupExpanded}
                onOpenChange={(p, open) => setSetupOpen((prev) => ({ ...prev, [p]: open }))}
              >
                <div className="credential-add-box">
                  <label className="field">
                    <span>{t(($) => $.providers.credential.alias)}</span>
                    <input
                      value={newAlias[provider] ?? ""}
                      placeholder={`${provider} ${t(($) => $.providers.row.primary)}`}
                      onChange={(e) => setNewAlias((prev) => ({ ...prev, [provider]: e.target.value }))}
                    />
                  </label>
                  <label className="field">
                    <span>{t(($) => $.providers.credential.addApiKey)}</span>
                    <input
                      type="password"
                      value={newSecret[provider] ?? ""}
                      placeholder={provider === "openai" ? "sk-…" : "sk-ant-…"}
                      onChange={(e) => setNewSecret((prev) => ({ ...prev, [provider]: e.target.value }))}
                    />
                  </label>
                  <div className="credential-add-footer">
                    <label className="credential-add-toggle">
                      <input
                        type="checkbox"
                        checked={makeNewKeyActive}
                        onChange={(e) => setNewMakeActive((prev) => ({ ...prev, [provider]: e.target.checked }))}
                      />
                      <span>{t(($) => $.providers.credential.addAsActive)}</span>
                    </label>
                    <button
                      type="button"
                      className="btn-ghost small"
                      onClick={() => void addKey(provider, makeNewKeyActive)}
                    >
                      {addApiKeyButtonLabel(makeNewKeyActive, t)}
                    </button>
                  </div>
                </div>
                {provider === "anthropic" && (
                  <div className="credential-add-box oauth-import-box">
                    <p className="muted tiny" style={{ marginBottom: 8 }}>
                      {t(($) => $.providers.claude.description)}{" "}
                      <strong>{t(($) => $.providers.credential.invalidAnthropicKey)}</strong>
                    </p>
                    <label className="field">
                      <span>{t(($) => $.providers.credential.alias)}</span>
                      <input
                        value={claudeAlias}
                        placeholder={t(($) => $.providers.authModes.claudeCodeOAuth)}
                        onChange={(e) => setClaudeAlias(e.target.value)}
                      />
                    </label>
                    <label className="field">
                      <span>{t(($) => $.providers.credential.accountPurpose)}</span>
                      <input
                        value={claudeLabel}
                        placeholder={t(($) => $.providers.credential.accountPurpose)}
                        onChange={(e) => setClaudeLabel(e.target.value)}
                      />
                    </label>
                    <label className="field">
                      <span>{t(($) => $.providers.claude.tokenLabel)}</span>
                      <input
                        type="password"
                        autoComplete="off"
                        value={claudeToken}
                        placeholder={t(($) => $.providers.claude.tokenPlaceholder)}
                        onChange={(e) => setClaudeToken(e.target.value)}
                      />
                    </label>
                    <div className="credential-add-footer">
                      <label className="credential-add-toggle">
                        <input
                          type="checkbox"
                          checked={claudeImportActive}
                          onChange={(e) => setOauthMakeActive((prev) => ({ ...prev, anthropic: e.target.checked }))}
                        />
                        <span>{t(($) => $.providers.claude.importAsActive)}</span>
                      </label>
                      <button type="button" className="btn-ghost small" onClick={() => void importClaudeToken(claudeImportActive)}>
                        {t(($) => $.providers.claude.import)}
                      </button>
                    </div>
                  </div>
                )}
                {provider === "openai" && (
                  <div className="credential-add-box oauth-import-box">
                    <p className="muted tiny" style={{ marginBottom: 8 }}>
                      {t(($) => $.providers.openAI.description)}{" "}
                      <strong>{t(($) => $.providers.credential.invalidOpenAiKey)}</strong>
                    </p>
                    {!oauth && (
                      <>
                        <label className="credential-add-toggle">
                          <input
                            type="checkbox"
                            checked={chatgptLoginActive}
                            onChange={(e) => setOauthMakeActive((prev) => ({ ...prev, openai: e.target.checked }))}
                          />
                          <span>{t(($) => $.providers.openAI.signInAsActive)}</span>
                        </label>
                        <p className="muted tiny">
                          {t(($) => $.models.test.subscriptionQuota)}
                        </p>
                        <button
                          type="button"
                          className="btn-ghost small"
                          disabled={pollBusy}
                          onClick={() => void startChatGPTLogin(chatgptLoginActive)}
                        >
                          {pollBusy
                            ? t(($) => $.providers.openAI.signingIn)
                            : t(($) => $.providers.openAI.signIn)}
                        </button>
                      </>
                    )}
                    {oauth?.phase === "waiting" && (
                      <div>
                        <p className="muted tiny">{t(($) => $.providers.openAI.waiting)}</p>
                        <button type="button" className="btn-ghost small" onClick={() => void copyLoginLink()}>
                          {t(($) => $.providers.openAI.copyLink)}
                        </button>
                        <button
                          type="button"
                          className="btn-ghost small"
                          onClick={() => setOauth((o) => (o ? { ...o, phase: "manual" } : o))}
                        >
                          {t(($) => $.providers.openAI.manualToggle)}
                        </button>
                      </div>
                    )}
                    {oauth?.phase === "manual" && (
                      <div>
                        <p className="muted tiny">
                          {t(($) => $.providers.openAI.manualDescription)}
                        </p>
                        <label className="field">
                          <span>{t(($) => $.providers.openAI.manualCodeLabel)}</span>
                          <input
                            value={manualValue}
                            autoComplete="off"
                            placeholder={t(($) => $.providers.openAI.manualCodePlaceholder)}
                            onChange={(e) => setManualValue(e.target.value)}
                          />
                        </label>
                        <button
                          type="button"
                          className="btn-ghost small"
                          disabled={manualBusy}
                          onClick={() => void completeChatGPTManual()}
                        >
                          {manualBusy
                            ? t(($) => $.providers.openAI.completing)
                            : t(($) => $.providers.openAI.complete)}
                        </button>
                        <button type="button" className="btn-ghost small" onClick={cancelChatGPTLogin}>
                          {t(($) => $.actions.cancel)}
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </SetupDisclosure>
              <div className="provider-links">
                {sourceUrls.map((url) => (
                  <a key={url} href={url} target="_blank" rel="noreferrer">
                    {t(($) => $.providers.discovery.officialSource)}
                  </a>
                ))}
              </div>
              <p className="muted tiny">
                {t(($) => $.providers.credential.localDescription)}{" "}
                {t(($) => $.providers.credential.environmentFallback)}
              </p>
            </div>
          );
        })}
      </div>
    </>
  );
}

export function SetupDisclosure({
  provider,
  open,
  onOpenChange,
  children,
}: {
  provider: ModelProvider;
  open: boolean;
  onOpenChange: (provider: ModelProvider, open: boolean) => void;
  children?: ReactNode;
}) {
  const { t } = useTranslation("settings");
  return (
    <details
      className="cred-setup"
      open={open}
      onToggle={(e) => {
        const nextOpen = e.currentTarget.open;
        onOpenChange(provider, nextOpen);
      }}
    >
      <summary>＋ {t(($) => $.providers.credential.add)}</summary>
      {children}
    </details>
  );
}

export function CredentialList({
  credentials,
  renames,
  metadataDrafts,
  onRenameDraft,
  onMetadataDraft,
  onSaveCredentialDetails,
  onSetActive,
  onDelete,
  onDiscover,
  discoverLoadingId,
  onRelogin,
  reloginBusy,
  onNavigationGuardChange,
  developerMode = false,
}: {
  credentials: ProviderCredential[];
  renames: Record<string, string>;
  metadataDrafts: Record<string, CredentialMetadataDraft>;
  onRenameDraft: (id: string, alias: string) => void;
  onMetadataDraft: (id: string, field: keyof CredentialMetadataDraft, value: string) => void;
  onSaveCredentialDetails: (id: string, alias: string, accountLabel: string, expiresAt?: string) => void;
  onSetActive: (id: string) => void;
  onDelete: (id: string) => void;
  onDiscover: (id: string) => void;
  discoverLoadingId: string | null;
  // S3 re-login (chatgpt_oauth rows only — scope ruling): replace the row's
  // token in place. Optional so existing render sites stay valid.
  onRelogin?: (id: string) => void;
  reloginBusy?: boolean;
  onNavigationGuardChange?: SettingsNavigationGuardReporter;
  developerMode?: boolean;
}) {
  const { t } = useTranslation("settings");
  // Per-row probe state (claude_code_oauth only). Local — the probe result is
  // ephemeral and never leaves this view.
  const [probing, setProbing] = useState<string | null>(null);
  const [probeResults, setProbeResults] = useState<Record<string, ProbeResponse | { error: string }>>({});
  const [pendingDelete, setPendingDelete] = useState<ProviderCredential | null>(null);
  const deleteTriggerRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    onNavigationGuardChange?.(probing === null
      ? CLEAR_SETTINGS_NAVIGATION_GUARD
      : { dirty: false, busy: true, reason: t(($) => $.providers.guard.busy) });
  }, [onNavigationGuardChange, probing, t]);

  useEffect(() => () => {
    onNavigationGuardChange?.(CLEAR_SETTINGS_NAVIGATION_GUARD);
  }, [onNavigationGuardChange]);

  async function runProbe(id: string) {
    setProbing(id);
    // clear any stale result; the `probing` state drives the loading label
    setProbeResults((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
    try {
      const res = await probeCredential(id);
      setProbeResults((prev) => ({ ...prev, [id]: res }));
    } catch (e) {
      setProbeResults((prev) => ({ ...prev, [id]: { error: e instanceof Error ? e.message : String(e) } }));
    } finally {
      setProbing(null);
    }
  }

  return (
    <div className="credential-list">
      {credentials.map((cred) => {
        const isLocalOAuth =
          cred.id.startsWith("local:") &&
          (cred.auth_type === "claude_code_oauth" || cred.auth_type === "chatgpt_oauth");
        const probe = probeResults[cred.id];
        const metadataDraft = metadataDrafts[cred.id] ?? {};
        const showExpiry = supportsCredentialExpiry(cred.auth_type);
        const aliasDraft = renames[cred.id] ?? cred.label;
        const accountLabelDraft = metadataDraft.account_label ?? cred.account_label ?? "";
        // The expiry draft holds the date-picker's native YYYY-MM-DD form; convert
        // the stored ISO for display, and back to a canonical ISO on save.
        const expiresAtDraft = metadataDraft.expires_at ?? isoToDateInput(cred.expires_at);
        return (
          <div className="credential-row" key={cred.id}>
            <div>
              <strong>{cred.label}</strong>
              {cred.account_label && (
                <span>{t(($) => $.providers.credential.accountLabel, { value: cred.account_label })}</span>
              )}
              {showExpiry && cred.expires_at && (
                <span>{t(($) => $.providers.credential.expiresAt, { timestamp: formatSystemTimestamp(cred.expires_at) })}</span>
              )}
              {cred.active && <span className="active-badge">{t(($) => $.providers.credential.active)}</span>}
              <span>{cred.auth_type}</span>
            </div>
            <span className={`key-pill credential-status-pill ${cred.available ? "ok" : "missing"}`}>
              {credentialAvailabilityText(cred, t)}
            </span>
            <p className="muted tiny">
              {cred.id.startsWith("local:")
                ? t(($) => $.providers.credential.localDescription)
                : t(($) => $.providers.credential.environmentFallback)}
            </p>
            <p>{cred.notes}</p>
            {(cred.editable || cred.can_discover_models) && (
              <div className="credential-actions">
                {cred.editable && (
                  <>
                    <input
                      value={aliasDraft}
                      required
                      onChange={(e) => onRenameDraft(cred.id, e.target.value)}
                      aria-label={`${cred.label} · ${t(($) => $.providers.credential.alias)}`}
                      placeholder={t(($) => $.providers.credential.alias)}
                    />
                    <button
                      type="button"
                      className="btn-ghost small"
                      disabled={cred.active}
                      onClick={() => onSetActive(cred.id)}
                    >
                      {t(($) => $.providers.credential.setActive)}
                    </button>
                  </>
                )}
                {cred.editable && (
                  <div className="credential-actions credential-metadata-actions">
                    <input
                      value={accountLabelDraft}
                      placeholder={t(($) => $.providers.credential.accountPurpose)}
                      aria-label={`${cred.label} · ${t(($) => $.providers.credential.accountPurpose)}`}
                      onChange={(e) => onMetadataDraft(cred.id, "account_label", e.target.value)}
                    />
                    {showExpiry && (
                      <input
                        type="date"
                        value={expiresAtDraft}
                        aria-label={`${cred.label} · ${t(($) => $.providers.credential.expiresOptional)}`}
                        title={t(($) => $.providers.credential.expiresOptional)}
                        onChange={(e) => onMetadataDraft(cred.id, "expires_at", e.target.value)}
                      />
                    )}
                    <button
                      type="button"
                      className="btn-ghost small"
                      onClick={() =>
                        onSaveCredentialDetails(
                          cred.id,
                          aliasDraft,
                          accountLabelDraft,
                          showExpiry ? dateInputToIso(expiresAtDraft) : undefined,
                        )
                      }
                    >
                      {t(($) => $.providers.credential.editDisplay)}
                    </button>
                  </div>
                )}
                {cred.can_discover_models && (
                  <button
                    type="button"
                    className="btn-ghost small"
                    disabled={discoverLoadingId === cred.id}
                    title={
                      cred.auth_type === "claude_code_oauth"
                        ? t(($) => $.providers.discovery.seedNotice)
                        : t(($) => $.providers.discovery.description)
                    }
                    onClick={() => onDiscover(cred.id)}
                  >
                    {discoverLoadingId === cred.id
                      ? t(($) => $.providers.discovery.listing)
                      : discoverButtonLabel(cred.auth_type, t)}
                  </button>
                )}
                {cred.auth_type === "chatgpt_oauth" && onRelogin && (
                  <button
                    type="button"
                    className="btn-ghost small"
                    disabled={reloginBusy}
                    title={t(($) => $.providers.openAI.reloginDescription)}
                    onClick={() => onRelogin(cred.id)}
                  >
                    {t(($) => $.providers.openAI.relogin)}
                  </button>
                )}
                {isLocalOAuth && (
                  <button
                    type="button"
                    className="btn-ghost small"
                    disabled={probing === cred.id}
                    title={
                      cred.auth_type === "chatgpt_oauth"
                        ? t(($) => $.providers.probe.title)
                        : t(($) => $.providers.claude.test)
                    }
                    onClick={() => void runProbe(cred.id)}
                  >
                    {probing === cred.id
                      ? t(($) => $.providers.probe.running)
                      : cred.auth_type === "chatgpt_oauth"
                        ? t(($) => $.providers.probe.run)
                        : t(($) => $.providers.claude.test)}
                  </button>
                )}
                {cred.editable && (
                  <button
                    type="button"
                    className="btn-ghost small danger"
                    onClick={(event) => {
                      deleteTriggerRef.current = event.currentTarget;
                      setPendingDelete(cred);
                    }}
                  >
                    {t(($) => $.actions.delete)}
                  </button>
                )}
              </div>
            )}
            {probe && (
              <ProbeResultView
                probe={probe}
                authType={cred.auth_type}
                developerMode={developerMode}
              />
            )}
          </div>
        );
      })}
      <ConfirmDialog
        open={pendingDelete !== null}
        title={t(($) => $.providers.credential.deleteTitle)}
        consequence={pendingDelete
          ? t(($) => $.providers.credential.deleteConsequence, { value: pendingDelete.label })
          : null}
        confirmLabel={t(($) => $.actions.delete)}
        onConfirm={() => {
          if (!pendingDelete) return;
          const id = pendingDelete.id;
          setPendingDelete(null);
          onDelete(id);
        }}
        onCancel={() => setPendingDelete(null)}
        returnFocusRef={deleteTriggerRef}
      />
    </div>
  );
}

function ProbeResultView({
  probe,
  authType,
  developerMode,
}: {
  probe: ProbeResponse | { error: string };
  authType: ProviderCredential["auth_type"];
  developerMode: boolean;
}) {
  const { t } = useTranslation("settings");
  if ("error" in probe) {
    return (
      <div className="probe-result">
        <p className="error-text tiny">{t(($) => $.errors.testFailed)}</p>
        {developerMode ? <DeveloperDiagnostics diagnostics={[probe.error]} t={t} /> : null}
      </div>
    );
  }
  const note = probeRuntimeNote(authType, t);
  return (
    <div className="probe-result">
      <p className={probe.passed ? "ok-text tiny" : "warn-text tiny"}>
        {probe.passed
          ? `✓ ${t(($) => $.providers.probe.passed)}`
          : `✗ ${t(($) => $.providers.probe.failed)}`}
      </p>
      {note && <p className="probe-note tiny">{note}</p>}
      <ul className="probe-list">
        {probe.probes.map((p) => {
          const summary = probeDisplaySummary(p, t);
          return (
            <li key={p.name} className="tiny">
              <span className={p.passed ? "ok-text" : "warn-text"}>{p.passed ? "✓" : "✗"}</span>
              <span className="probe-label">{probeDisplayLabel(p.name, t)}</span>
              <span className="probe-summary">{summary.text}</span>
              {summary.models.length > 0 && (
                <span className="probe-models">
                  {summary.models.map((model) => (
                    <code key={model}>{model}</code>
                  ))}
                </span>
              )}
              {developerMode ? (
                <DeveloperDiagnostics
                  diagnostics={[
                    p.expected ? `${t(($) => $.providers.probe.expected)}: ${p.expected}` : null,
                    p.observed ? `${t(($) => $.providers.probe.observed)}: ${p.observed}` : null,
                    p.error ? `${t(($) => $.providers.probe.error)}: ${p.error}` : null,
                  ]}
                  t={t}
                />
              ) : null}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function DiscoveryResultView({
  result,
  authMode,
  credentialLabel,
  onClose,
  onUse,
  onRelogin,
  reloginBusy,
  developerMode = false,
}: {
  result: ModelDiscoveryResult;
  authMode: ProviderCredential["auth_type"] | null;
  credentialLabel: string | null;
  onClose: () => void;
  onUse: (model: string, task: ModelTask) => void;
  // S3: when the failure is machine-classified as reauth_required, offer the
  // in-place re-login right where the error is shown. Optional (old sites OK).
  onRelogin?: () => void;
  reloginBusy?: boolean;
  developerMode?: boolean;
}) {
  const { t } = useTranslation("settings");
  const [query, setQuery] = useState("");
  const models = result.models.filter((model) =>
    model.id.toLowerCase().includes(query.trim().toLowerCase()),
  );
  // Source badge: the credential/auth_mode decides whether these are a LIVE backend
  // list (and WHICH backend — OpenAI API vs ChatGPT, both 'provider_api' at the data
  // layer) or seed CANDIDATES — never imply a global catalog (§11).
  const sources = Array.from(new Set(result.models.map((m) => m.source)));
  const sourceBadge =
    sources.length === 1
      ? discoverySourceLabel(result.provider, authMode, sources[0], t)
      : sources.join(" / ");
  const credentialSummary = discoveryResultCredentialLabel(
    authMode
      ? { label: credentialLabel ?? t(($) => $.providers.credential.unnamed), auth_type: authMode }
      : null,
    t,
  );
  const errorMessage = result.error
    ? result.error_code
      ? modelReasonLabel(result.error_code, t)
      : t(($) => $.providers.discovery.failure)
    : null;
  return (
    <div className="discovery-box">
      <div className="discovery-head">
        <div>
          <strong>{discoveryHeaderTitle(authMode, t)} · {discoveryStatusLabel(result.status, t)}</strong>
          <span className="discovery-credential tiny">{credentialSummary}</span>
        </div>
        {result.models.length > 0 && <span className="source-badge tiny">{sourceBadge}</span>}
        {result.source_url && (
          <a href={result.source_url} target="_blank" rel="noreferrer">
            {t(($) => $.providers.discovery.officialSource)}
          </a>
        )}
        <button type="button" className="btn-ghost tiny" onClick={onClose}>
          {t(($) => $.actions.close)}
        </button>
      </div>
      {errorMessage && <p className="warn-text tiny">{errorMessage}</p>}
      {developerMode ? <DeveloperDiagnostics diagnostics={[result.error]} t={t} /> : null}
      {result.error_code === "reauth_required" && onRelogin && (
        <div className="reauth-hint">
          <span className="warn-text tiny">{t(($) => $.providers.openAI.tokenExpired)}</span>
          <button type="button" className="btn-ghost small" disabled={reloginBusy} onClick={onRelogin}>
            {t(($) => $.providers.openAI.relogin)}
          </button>
        </div>
      )}
      <label className="field discovery-filter">
        <span>{t(($) => $.providers.discovery.searchLabel)}</span>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t(($) => $.providers.discovery.searchPlaceholder)}
        />
      </label>
      <div className="discovery-models">
        {models.map((model) => (
          <div className="model-discovery-row" key={model.id}>
            <span>{model.id}</span>
            <button type="button" className="btn-ghost small" onClick={() => onUse(model.id, "card_synthesis")}>
              {t(($) => $.providers.discovery.useForSynthesis)}
            </button>
            <button type="button" className="btn-ghost small" onClick={() => onUse(model.id, "card_translation")}>
              {t(($) => $.providers.discovery.useForTranslation)}
            </button>
          </div>
        ))}
      </div>
      <p className="muted tiny">
        {t(($) => $.providers.discovery.modelCount, { count: models.length })}
        {" / "}{result.models.length}{" · "}
        {t(($) => $.providers.discovery.directIdAllowed)}
      </p>
    </div>
  );
}
