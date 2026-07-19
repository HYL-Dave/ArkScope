import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
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

export function ProviderSection({
  catalog,
  runtime,
  discovery,
  onRefresh,
  onDiscover,
  onClearDiscovery,
  onUseModel,
  onNavigationGuardChange,
}: {
  catalog: ModelCatalog;
  runtime: RuntimeConfig | null;
  discovery: DiscoveryState;
  onRefresh: () => Promise<void>;
  onDiscover: (provider: ModelProvider, credentialId: string | null) => Promise<void>;
  onClearDiscovery: (provider: ModelProvider) => void;
  onUseModel: (provider: ModelProvider, model: string, task: ModelTask) => void;
  onNavigationGuardChange?: SettingsNavigationGuardReporter;
}) {
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
  const [providerMsg, setProviderMsg] = useState<string | null>(null);
  const [providerErr, setProviderErr] = useState<string | null>(null);
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
        ? "Provider 登入或 Credential 更新正在進行。"
        : providerDirty
          ? "Provider 登入與憑證有未儲存的變更。"
          : null,
    });
  }, [onNavigationGuardChange, providerBusy, providerDirty]);

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
      setProviderErr(`${provider}: API key 不可為空`);
      return;
    }
    setProviderErr(null);
    setProviderMsg(null);
    beginCredentialMutation();
    try {
      await addCredential({
        provider,
        auth_type: "api_key",
        alias: alias || `${provider} key`,
        secret,
        make_active: makeActive,
      });
      setNewAlias((prev) => ({ ...prev, [provider]: "" }));
      setNewSecret((prev) => ({ ...prev, [provider]: "" }));
      setProviderMsg(addApiKeySuccessMessage(provider, makeActive));
      await onRefresh();
    } catch (e) {
      setProviderErr(e instanceof Error ? e.message : String(e));
    } finally {
      endCredentialMutation();
    }
  }

  async function importClaudeToken(makeActive: boolean) {
    const token = claudeToken.trim();
    if (!token) {
      setProviderErr("Claude setup-token 不可為空");
      return;
    }
    setProviderErr(null);
    setProviderMsg(null);
    beginCredentialMutation();
    try {
      await importOAuthCredential({
        provider: "anthropic",
        auth_mode: "claude_code_oauth",
        alias: claudeAlias.trim() || "Claude subscription",
        token,
        account_label: claudeLabel.trim() || undefined,
        make_active: makeActive,
      });
      setClaudeToken(""); // clear the token from state immediately on success
      setClaudeAlias("");
      setClaudeLabel("");
      setProviderMsg("Claude setup-token 已匯入（存入 token-store，未存入 credential DB）。");
      await onRefresh();
    } catch (e) {
      setClaudeToken(""); // also clear on failure — don't keep the token around
      setProviderErr(e instanceof Error ? e.message : String(e));
    } finally {
      endCredentialMutation();
    }
  }

  async function copyLoginLink() {
    if (!oauth?.authUrl) return;
    if (!navigator.clipboard) {
      setProviderErr("此瀏覽器不支援自動複製，請從新分頁的網址列手動複製登入連結。");
      return;
    }
    try {
      await navigator.clipboard.writeText(oauth.authUrl);
      setProviderMsg("登入連結已複製。");
    } catch {
      setProviderErr("無法複製連結（瀏覽器剪貼簿權限被拒）。請從新分頁完成登入，或重新點「登入 ChatGPT」。");
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
        setProviderMsg("ChatGPT 訂閱已登入（token 存入 token-store，未存入 credential DB）。");
        await onRefresh();
      } else if (res.kind === "timeout") {
        setOauth((o) => (o ? { ...o, phase: "manual" } : o));
        setProviderErr("等不到瀏覽器回呼（可能 popup 被擋，或本機 :1455 沒收到）。請改用下方手動貼上授權碼。");
      } else if (res.kind === "error") {
        // surface the backend reason as-is — NO silent fallback to an API key.
        // F4: offer the manual paste ONLY when it can still succeed (the state
        // wasn't consumed by a failed completion) — else reset the flow.
        if (res.manualCompletable) {
          setOauth((o) => (o ? { ...o, phase: "manual" } : o));
          setProviderErr(`登入失敗：${res.detail}`);
        } else {
          setOauth(null);
          setProviderErr(`登入失敗：${res.detail}（此登入工作階段已失效，請重新點「登入 ChatGPT」）`);
        }
      } else {
        setOauth(null);
        setProviderErr("登入工作階段不存在或已過期，請重新點「登入 ChatGPT」。");
      }
    } catch (e) {
      setProviderErr(e instanceof Error ? e.message : String(e));
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
      setProviderErr("請貼上授權碼或回呼網址");
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
      setProviderMsg("ChatGPT 訂閱已登入（手動完成；token 存入 token-store）。");
      await onRefresh();
    } catch (e) {
      // a bad/expired/forged state or a token-exchange error 400s here — show it, no fallback
      setProviderErr(e instanceof Error ? e.message : String(e));
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
      setProviderMsg("Active key 已更新。");
      await onRefresh();
    } catch (e) {
      setProviderErr(e instanceof Error ? e.message : String(e));
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
      setProviderMsg("Credential 顯示資訊已更新。");
      await onRefresh();
    } catch (e) {
      setProviderErr(e instanceof Error ? e.message : String(e));
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
      setProviderMsg("Credential 已刪除。");
      await onRefresh();
    } catch (e) {
      setProviderErr(e instanceof Error ? e.message : String(e));
    } finally {
      endCredentialMutation();
    }
  }

  return (
    <>
      <div className="settings-section-head">
        <div>
          <h2>Provider 狀態</h2>
          <p className="muted">
            Provider/channel 和 task routing 分開管理。這裡顯示本機 credential 狀態；每個 credential 可依其類型做 model discovery / capability test（API key 與 OAuth 方式各自不同）。
          </p>
        </div>
      </div>
      {providerErr && <p className="error-text">{providerErr}</p>}
      {providerMsg && <p className="ok-text">{providerMsg}</p>}
      <div className="provider-grid">
        {catalog.providers.map((provider) => {
          const models = catalog.models.filter((m) => m.provider === provider);
          const credentials =
            catalog.credentials?.[provider] ??
            (provider === "anthropic" ? runtime?.anthropic.credentials : runtime?.openai.credentials) ??
            [];
          const activeCred = credentials.find((c) => c.active && c.available) ?? null;
          const pill = credentialPill(activeCred);
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
                  <p className="muted">{models.length} seed models · direct model id input allowed</p>
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
                />
              )}
              <div className="settings-actions">
                <p className="muted tiny" style={{ width: "100%" }}>
                  進階：指定某個 credential 做 discovery（一般用上方各列的「列模型／查看候選模型」即可）。
                </p>
                <label className="field credential-select">
                  <span>credential</span>
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
                  {discoveryState?.loading ? "讀取中…" : `${discoverButtonLabel(selectedAuthMode)}（此 credential）`}
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
                    <span>新增 API key alias</span>
                    <input
                      value={newAlias[provider] ?? ""}
                      placeholder={`${provider} primary`}
                      onChange={(e) => setNewAlias((prev) => ({ ...prev, [provider]: e.target.value }))}
                    />
                  </label>
                  <label className="field">
                    <span>新增 API key</span>
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
                      <span>新增後設為 active</span>
                    </label>
                    <button
                      type="button"
                      className="btn-ghost small"
                      onClick={() => void addKey(provider, makeNewKeyActive)}
                    >
                      {addApiKeyButtonLabel(makeNewKeyActive)}
                    </button>
                  </div>
                </div>
                {provider === "anthropic" && (
                  <div className="credential-add-box oauth-import-box">
                    <p className="muted tiny" style={{ marginBottom: 8 }}>
                      匯入 Claude setup-token（訂閱登入）。<strong>這不是 Anthropic API key。</strong>
                      Token 會存入本機 token-store/keyring，credential DB 只保存 metadata。
                      用終端機 <code className="mono">claude setup-token</code> 產生後貼上。
                    </p>
                    <label className="field">
                      <span>顯示名稱（可留空）</span>
                      <input
                        value={claudeAlias}
                        placeholder="Claude subscription"
                        onChange={(e) => setClaudeAlias(e.target.value)}
                      />
                    </label>
                    <label className="field">
                      <span>帳號／方案標籤（可留空）</span>
                      <input
                        value={claudeLabel}
                        placeholder="例如 Claude Pro / Max"
                        onChange={(e) => setClaudeLabel(e.target.value)}
                      />
                    </label>
                    <label className="field">
                      <span>Claude setup-token</span>
                      <input
                        type="password"
                        autoComplete="off"
                        value={claudeToken}
                        placeholder="貼上 claude setup-token 產生的 token"
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
                        <span>匯入後設為 active</span>
                      </label>
                      <button type="button" className="btn-ghost small" onClick={() => void importClaudeToken(claudeImportActive)}>
                        匯入 setup-token
                      </button>
                    </div>
                  </div>
                )}
                {provider === "openai" && (
                  <div className="credential-add-box oauth-import-box">
                    <p className="muted tiny" style={{ marginBottom: 8 }}>
                      登入 ChatGPT 訂閱（OpenAI subscription）。<strong>這不是 OpenAI API key。</strong>
                      這是<strong>ChatGPT backend 相容路徑</strong>（非公開 OpenAI API host；Research 啟用前會用實測確認 backend 行為）。
                      Token 會存入本機 token-store/keyring，credential DB 只保存 metadata。
                    </p>
                    {!oauth && (
                      <>
                        <label className="credential-add-toggle">
                          <input
                            type="checkbox"
                            checked={chatgptLoginActive}
                            onChange={(e) => setOauthMakeActive((prev) => ({ ...prev, openai: e.target.checked }))}
                          />
                          <span>登入後設為 active</span>
                        </label>
                        <p className="muted tiny">
                          AI 研究、卡片合成與翻譯會依 active credential 使用 ChatGPT 訂閱後端；
                          可見模型仍須用任務內的實際測試確認。預設不設為 active——登入不應悄悄切換使用中的 credential。
                        </p>
                        <button
                          type="button"
                          className="btn-ghost small"
                          disabled={pollBusy}
                          onClick={() => void startChatGPTLogin(chatgptLoginActive)}
                        >
                          {pollBusy ? "登入中…" : "登入 ChatGPT"}
                        </button>
                      </>
                    )}
                    {oauth?.phase === "waiting" && (
                      <div>
                        <p className="muted tiny">等待瀏覽器登入完成…（已開新分頁）</p>
                        <button type="button" className="btn-ghost small" onClick={() => void copyLoginLink()}>
                          複製登入連結
                        </button>
                        <button
                          type="button"
                          className="btn-ghost small"
                          onClick={() => setOauth((o) => (o ? { ...o, phase: "manual" } : o))}
                        >
                          沒有自動返回？手動貼上授權碼
                        </button>
                      </div>
                    )}
                    {oauth?.phase === "manual" && (
                      <div>
                        <p className="muted tiny">
                          只在瀏覽器已完成登入、但本機 callback 沒收到時使用。貼上授權碼或整個回呼網址：
                        </p>
                        <label className="field">
                          <span>授權碼／回呼網址</span>
                          <input
                            value={manualValue}
                            autoComplete="off"
                            placeholder="code 或 http://localhost:1455/auth/callback?code=…"
                            onChange={(e) => setManualValue(e.target.value)}
                          />
                        </label>
                        <button
                          type="button"
                          className="btn-ghost small"
                          disabled={manualBusy}
                          onClick={() => void completeChatGPTManual()}
                        >
                          {manualBusy ? "完成中…" : "完成登入"}
                        </button>
                        <button type="button" className="btn-ghost small" onClick={cancelChatGPTLogin}>
                          取消
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </SetupDisclosure>
              <div className="provider-links">
                {sourceUrls.map((url) => (
                  <a key={url} href={url} target="_blank" rel="noreferrer">
                    official source
                  </a>
                ))}
              </div>
              <p className="muted tiny">
                可在此新增本機 API key credential（存於本機 profile DB）；env/config/.env 與 key pool 為唯讀來源。
                {provider === "anthropic"
                  ? " Claude setup-token 可由上方匯入（token 存 token-store/keyring，不進 credential DB）。"
                  : " OpenAI ChatGPT 訂閱可由上方「登入 ChatGPT」（token 存 token-store/keyring，不進 credential DB）。"}
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
  return (
    <details
      className="cred-setup"
      open={open}
      onToggle={(e) => {
        const nextOpen = e.currentTarget.open;
        onOpenChange(provider, nextOpen);
      }}
    >
      <summary>＋ 新增 API key 或登入訂閱</summary>
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
}) {
  // Per-row probe state (claude_code_oauth only). Local — the probe result is
  // ephemeral and never leaves this view.
  const [probing, setProbing] = useState<string | null>(null);
  const [probeResults, setProbeResults] = useState<Record<string, ProbeResponse | { error: string }>>({});
  const [pendingDelete, setPendingDelete] = useState<ProviderCredential | null>(null);
  const deleteTriggerRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    onNavigationGuardChange?.(probing === null
      ? CLEAR_SETTINGS_NAVIGATION_GUARD
      : { dirty: false, busy: true, reason: "Credential 驗證正在進行。" });
  }, [onNavigationGuardChange, probing]);

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
              {cred.account_label && <span>帳號／方案：{cred.account_label}</span>}
              {showExpiry && cred.expires_at && <span>到期：{formatSystemTimestamp(cred.expires_at)}</span>}
              {cred.active && <span className="active-badge">使用中</span>}
              <span>{cred.auth_type}</span>
            </div>
            <span className={`key-pill credential-status-pill ${cred.available ? "ok" : "missing"}`}>
              {credentialAvailabilityText(cred)}
            </span>
            <p className="muted tiny">
              {cred.id.startsWith("local:")
                ? "本機 Settings credential（profile DB · 可編輯、可設為 active）"
                : ".env／環境變數 fallback（唯讀；DB credential 才是主要選擇面）"}
            </p>
            <p>{cred.notes}</p>
            {(cred.editable || cred.can_discover_models) && (
              <div className="credential-actions">
                {cred.editable && (
                  <>
                    <input
                      value={aliasDraft}
                      onChange={(e) => onRenameDraft(cred.id, e.target.value)}
                      aria-label={`${cred.label} alias`}
                      placeholder="必填；留空則保留原名稱"
                    />
                    <button
                      type="button"
                      className="btn-ghost small"
                      disabled={cred.active}
                      onClick={() => onSetActive(cred.id)}
                    >
                      設為 active
                    </button>
                  </>
                )}
                {cred.editable && (
                  <div className="credential-actions credential-metadata-actions">
                    <input
                      value={accountLabelDraft}
                      placeholder={showExpiry ? "帳號／方案標籤（可留空）" : "帳號／用途標籤（可留空）"}
                      aria-label={`${cred.label} account label`}
                      onChange={(e) => onMetadataDraft(cred.id, "account_label", e.target.value)}
                    />
                    {showExpiry && (
                      <input
                        type="date"
                        value={expiresAtDraft}
                        aria-label={`${cred.label} expires at`}
                        title="到期日（可留空）"
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
                      儲存顯示資訊
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
                        ? "查看候選模型（seed，非即時 discovery）"
                        : "列出此 credential 後端可見的模型"
                    }
                    onClick={() => onDiscover(cred.id)}
                  >
                    {discoverLoadingId === cred.id ? "讀取中…" : discoverButtonLabel(cred.auth_type)}
                  </button>
                )}
                {cred.auth_type === "chatgpt_oauth" && onRelogin && (
                  <button
                    type="button"
                    className="btn-ghost small"
                    disabled={reloginBusy}
                    title="以此列身分重新登入 ChatGPT，原地更換 token（不新增 credential；alias／active 保留）"
                    onClick={() => onRelogin(cred.id)}
                  >
                    重新登入
                  </button>
                )}
                {isLocalOAuth && (
                  <button
                    type="button"
                    className="btn-ghost small"
                    disabled={probing === cred.id}
                    title={
                      cred.auth_type === "chatgpt_oauth"
                        ? "實測 ChatGPT OAuth backend"
                        : "測試 Claude setup-token"
                    }
                    onClick={() => void runProbe(cred.id)}
                  >
                    {probing === cred.id
                      ? "測試中…"
                      : cred.auth_type === "chatgpt_oauth"
                        ? "實測 OAuth"
                        : "測試 token"}
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
                    刪除
                  </button>
                )}
              </div>
            )}
            {probe && <ProbeResultView probe={probe} authType={cred.auth_type} />}
          </div>
        );
      })}
      <ConfirmDialog
        open={pendingDelete !== null}
        title="刪除 Credential？"
        consequence={pendingDelete
          ? <>將移除已儲存的登入項目「<strong>{pendingDelete.label}</strong>」。</>
          : null}
        confirmLabel="刪除 Credential"
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
}: {
  probe: ProbeResponse | { error: string };
  authType: ProviderCredential["auth_type"];
}) {
  if ("error" in probe) {
    return <p className="error-text tiny">probe 失敗：{probe.error}</p>;
  }
  const note = probeRuntimeNote(authType);
  return (
    <div className="probe-result">
      <p className={probe.passed ? "ok-text tiny" : "warn-text tiny"}>
        {probe.passed ? "✓ OAuth 驗證通過" : "✗ OAuth 驗證未通過"}
      </p>
      {note && <p className="probe-note tiny">{note}</p>}
      <ul className="probe-list">
        {probe.probes.map((p) => {
          const summary = probeDisplaySummary(p);
          return (
            <li key={p.name} className="tiny">
              <span className={p.passed ? "ok-text" : "warn-text"}>{p.passed ? "✓" : "✗"}</span>
              <span className="probe-label">{probeDisplayLabel(p.name)}</span>
              <span className="probe-summary">{summary.text}</span>
              {summary.models.length > 0 && (
                <span className="probe-models">
                  {summary.models.map((model) => (
                    <code key={model}>{model}</code>
                  ))}
                </span>
              )}
              <details className="probe-detail">
                <summary>細節</summary>
                <div>expected: {p.expected}</div>
                <div>observed: {p.observed}</div>
                {p.error && <div>error: {p.error}</div>}
              </details>
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
}) {
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
      ? discoverySourceLabel(result.provider, authMode, sources[0])
      : sources.join(" / ");
  const credentialSummary = discoveryResultCredentialLabel(
    authMode ? { label: credentialLabel ?? "未命名 credential", auth_type: authMode } : null,
  );
  return (
    <div className="discovery-box">
      <div className="discovery-head">
        <div>
          <strong>{discoveryHeaderTitle(authMode)} · {result.status}</strong>
          <span className="discovery-credential tiny">{credentialSummary}</span>
        </div>
        {result.models.length > 0 && <span className="source-badge tiny">{sourceBadge}</span>}
        {result.source_url && (
          <a href={result.source_url} target="_blank" rel="noreferrer">
            source
          </a>
        )}
        <button type="button" className="btn-ghost tiny" onClick={onClose}>
          關閉
        </button>
      </div>
      {result.error && <p className="warn-text tiny">{result.error}</p>}
      {result.error_code === "reauth_required" && onRelogin && (
        <div className="reauth-hint">
          <span className="warn-text tiny">token 已失效——需要重新登入。</span>
          <button type="button" className="btn-ghost small" disabled={reloginBusy} onClick={onRelogin}>
            重新登入
          </button>
        </div>
      )}
      <label className="field discovery-filter">
        <span>搜尋模型</span>
        <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="gpt / claude / mini…" />
      </label>
      <div className="discovery-models">
        {models.map((model) => (
          <div className="model-discovery-row" key={model.id}>
            <span>{model.id}</span>
            <button type="button" className="btn-ghost small" onClick={() => onUse(model.id, "card_synthesis")}>
              用於生成
            </button>
            <button type="button" className="btn-ghost small" onClick={() => onUse(model.id, "card_translation")}>
              用於翻譯
            </button>
          </div>
        ))}
      </div>
      <p className="muted tiny">
        顯示 {models.length} / {result.models.length} 個 provider 回傳模型；任務頁仍可直接輸入任何 model id。
      </p>
    </div>
  );
}
