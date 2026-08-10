/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import i18n from "i18next";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ProviderSection } from "./Settings";
import type { ModelCatalog, ProviderCredential } from "./api";
import {
  createSettingsReadCache,
  oauthAccountUsageKey,
} from "./settings/settingsReadCache";
import { formatSystemTimestamp } from "./timeDisplay";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;
let currentRenderProps: React.ComponentProps<typeof ProviderSection> | null = null;

beforeEach(async () => {
  await i18n.changeLanguage("zh-Hant");
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  if (root) {
    act(() => root!.unmount());
    root = null;
  }
  host?.remove();
  host = null;
  currentRenderProps = null;
});

const chatgptCred: ProviderCredential = {
  id: "local:7", provider: "openai", auth_type: "chatgpt_oauth",
  label: "ChatGPT subscription Plus", account_label: "ChatGPT plus", expires_at: null,
  source: "profile_state.db", available: true, masked: null, active: false, editable: true,
  can_discover_models: true, can_test_models: false, notes: "",
};
const anthropicKey: ProviderCredential = {
  ...chatgptCred, id: "local:5", provider: "anthropic", auth_type: "api_key",
  label: "season_ArkScope", masked: "sk-a…AAAA", can_test_models: true,
};

type LifecycleCredential = ProviderCredential & {
  lifecycle_state: "ready" | "refresh_required" | "refresh_failed_retryable" | "reauth_required" | "unverifiable";
  lifecycle_error_code: string | null;
  last_refresh_attempt_at: string | null;
  last_refresh_success_at: string | null;
  last_refresh_error_at: string | null;
  last_refresh_error_detail: string | null;
};

function oauthCredential(overrides: Partial<LifecycleCredential> = {}): LifecycleCredential {
  return {
    ...chatgptCred,
    lifecycle_state: "ready",
    lifecycle_error_code: null,
    last_refresh_attempt_at: null,
    last_refresh_success_at: null,
    last_refresh_error_at: null,
    last_refresh_error_detail: null,
    ...overrides,
  } as LifecycleCredential;
}

function accountSnapshot({
  credentialId = "local:7",
  observedAt = "2026-08-08T08:00:00+00:00",
  usedPercent = 18,
  resetsAt = 1786190400,
  status = "allowed",
  overageStatus = "rejected",
  overageReason = "out_of_credits",
  provider = "openai",
  authMode = "chatgpt_oauth",
  source = "codex_app_server",
  secondary = null,
}: {
  credentialId?: string;
  observedAt?: string;
  usedPercent?: number | null;
  resetsAt?: number | null;
  status?: "allowed" | "allowed_warning" | "rejected" | null;
  overageStatus?: "allowed" | "allowed_warning" | "rejected" | null;
  overageReason?: string | null;
  provider?: string;
  authMode?: string;
  source?: string;
  secondary?: { used_percent: number | null; window_duration_minutes: number | null; resets_at: number | null } | null;
} = {}) {
  return {
    credential_id: credentialId,
    provider,
    auth_mode: authMode,
    account_fingerprint: "f".repeat(64),
    source,
    schema_version: 1,
    observed_at: observedAt,
    status: "available",
    payload: {
      rate_limits: {
        limit_id: "codex",
        limit_name: "ChatGPT Plus",
        plan_type: "plus",
        primary: {
          used_percent: usedPercent,
          window_duration_minutes: 300,
          resets_at: resetsAt,
        },
        secondary,
        rate_limit_reached_type: null,
        credits: null,
        individual_limit: null,
        spend_control_reached: null,
        status,
        overage_status: overageStatus,
        overage_resets_at: null,
        overage_disabled_reason: overageReason,
      },
      rate_limits_by_limit_id: {},
      reset_credits_available: null,
      usage_summary: {
        lifetime_tokens: 1234,
        peak_daily_tokens: null,
        longest_running_turn_seconds: null,
        current_streak_days: null,
        longest_streak_days: null,
      },
      daily_usage_buckets: [],
    },
    updated_at: observedAt,
  };
}

function accountView(snapshot: ReturnType<typeof accountSnapshot> | null, syncStatus = "not_requested") {
  return {
    credential_id: snapshot?.credential_id ?? "local:7",
    snapshot,
    sync_status: syncStatus,
    sync_error_code: null,
  };
}

function jsonResponse(body: unknown, status = 200) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  });
}

function catalog(): ModelCatalog {
  return {
    providers: ["anthropic", "openai"],
    tasks: [{ id: "ai_research", label: "AI 研究", description: "", default_provider: "openai", recommended_model: "gpt-5.4-mini" }],
    models: [],
    effort_options: { openai: [], anthropic: [] },
    routes: {} as ModelCatalog["routes"],
    credentials: { anthropic: [anthropicKey], openai: [chatgptCred] },
    custom_allowed: true,
  } as ModelCatalog;
}

function renderSection(extra: Record<string, unknown> = {}) {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  currentRenderProps = {
    catalog: catalog(),
    runtime: null,
    discovery: {},
    settingsReadCache: createSettingsReadCache(),
    onRefresh: vi.fn().mockResolvedValue(undefined),
    onDiscover: vi.fn().mockResolvedValue(undefined),
    onClearDiscovery: vi.fn(),
    onUseModel: vi.fn(),
    ...extra,
  } as React.ComponentProps<typeof ProviderSection>;
  act(() => {
    root!.render(React.createElement(ProviderSection, currentRenderProps));
  });
}

function rerenderSection(extra: Record<string, unknown> = {}) {
  if (!root || !currentRenderProps) throw new Error("ProviderSection is not mounted");
  currentRenderProps = {
    ...currentRenderProps,
    ...extra,
  } as React.ComponentProps<typeof ProviderSection>;
  act(() => {
    root!.render(React.createElement(ProviderSection, currentRenderProps!));
  });
}

function changeInput(input: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
  setter?.call(input, value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

function providerCard(provider: string): HTMLElement {
  const card = Array.from(host!.querySelectorAll<HTMLElement>(".provider-card"))
    .find((item) => item.querySelector("h2")?.textContent === provider);
  if (!card) throw new Error(`missing provider card ${provider}`);
  return card;
}

function credentialRow(label: string): HTMLElement {
  const row = Array.from(host!.querySelectorAll<HTMLElement>(".credential-row"))
    .find((item) => item.querySelector("strong")?.textContent === label);
  if (!row) throw new Error(`missing credential row ${label}`);
  return row;
}

function callsFor(fetchMock: ReturnType<typeof vi.fn>, needle: string, method?: string) {
  return fetchMock.mock.calls.filter(([url, init]) => (
    String(url).includes(needle)
      && (method === undefined || ((init as RequestInit | undefined)?.method ?? "GET") === method)
  ));
}

async function flushPromises(rounds = 4) {
  await act(async () => {
    for (let index = 0; index < rounds; index += 1) await Promise.resolve();
  });
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((done, fail) => {
    resolve = done;
    reject = fail;
  });
  return { promise, resolve, reject };
}

function latestReport(callback: ReturnType<typeof vi.fn>) {
  return callback.mock.calls.at(-1)?.[0] as { dirty: boolean; busy: boolean; reason: string | null };
}

function reloginButtons(): HTMLButtonElement[] {
  return Array.from(host!.querySelectorAll("button")).filter(
    (b) => b.textContent?.trim() === "重新登入",
  ) as HTMLButtonElement[];
}

function disposeRender() {
  act(() => root!.unmount());
  root = null;
  host!.remove();
  host = null;
}

async function waitFor(pred: () => boolean, timeoutMs = 3000) {
  const deadline = performance.now() + timeoutMs;
  while (performance.now() < deadline) {
    if (pred()) return;
    await act(async () => {
      await new Promise((r) => setTimeout(r, 40));
    });
  }
  expect(pred()).toBe(true);
}

describe("ProviderSection localization", () => {
  it("renders English Provider OAuth and credential setup without changing active work", async () => {
    renderSection();
    const anthropic = providerCard("anthropic");
    const disclosure = anthropic.querySelector<HTMLDetailsElement>("details.cred-setup")!;
    const alias = anthropic.querySelector<HTMLInputElement>(
      ".credential-add-box:not(.oauth-import-box) input:not([type='password'])",
    )!;

    await act(async () => {
      disclosure.open = true;
      disclosure.dispatchEvent(new Event("toggle", { bubbles: false }));
      changeInput(alias, "planted-provider-draft");
      await i18n.changeLanguage("en");
    });

    const currentAnthropic = providerCard("anthropic");
    const currentDisclosure = currentAnthropic.querySelector<HTMLDetailsElement>("details.cred-setup")!;
    const currentAlias = currentAnthropic.querySelector<HTMLInputElement>(
      ".credential-add-box:not(.oauth-import-box) input:not([type='password'])",
    )!;
    expect(currentDisclosure).toBe(disclosure);
    expect(currentAlias).toBe(alias);
    expect(host!.textContent).toContain("Provider Status");
    expect(host!.textContent).toContain("Add an API key or subscription sign-in");
    expect(host!.textContent).toContain("Sign in to ChatGPT");
    expect(currentDisclosure.open).toBe(true);
    expect(currentAlias.value).toBe("planted-provider-draft");
    expect(host!.querySelector('[data-testid="locale-selector"]')).toBeNull();
  });

  it("hides OAuth backend detail in normal mode and reveals it only in Developer Mode", async () => {
    const rawDetail = "planted-oauth-detail";
    const fetchMock = vi.fn().mockImplementation(async (url: unknown) => ({
      ok: true,
      status: 200,
      json: async () => String(url).includes("/oauth/start")
        ? { auth_url: "https://auth.openai.com/x", state: "S", expires_at: "t", manual_code_supported: true }
        : { status: "error", credential: null, detail: rawDetail, manual_completable: false },
    }));
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("open", vi.fn());

    renderSection({ developerMode: false });
    await act(async () => { reloginButtons()[0].click(); });
    await waitFor(() => !reloginButtons()[0].disabled);
    expect(host!.textContent).toContain("登入工作階段不存在或已過期");
    expect(host!.textContent).not.toContain(rawDetail);

    disposeRender();
    renderSection({ developerMode: true });
    await act(async () => { reloginButtons()[0].click(); });
    await waitFor(() => (host!.textContent ?? "").includes(rawDetail));
    expect(host!.textContent).toContain("開發者診斷");
    expect(host!.querySelector('[data-testid="developer-diagnostics"]')?.getAttribute("aria-live")).toBeNull();
  });

  it("switches locale during OAuth without cancelling or duplicating the flow", async () => {
    const statusResponse = deferred<{ ok: boolean; status: number; json: () => Promise<unknown> }>();
    const onRefresh = vi.fn().mockResolvedValue(undefined);
    const openaiKey: ProviderCredential = {
      ...chatgptCred,
      id: "local:2",
      auth_type: "api_key",
      label: "OpenAI primary",
      masked: "sk-p...MASKED",
      active: true,
    };
    const oauthCatalog = catalog();
    oauthCatalog.credentials.openai = [openaiKey, chatgptCred];
    const fetchMock = vi.fn().mockImplementation((url: unknown) => {
      if (String(url).includes("/oauth/start")) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({ auth_url: "https://auth.openai.com/x", state: "S", expires_at: "t", manual_code_supported: true }),
        });
      }
      if (String(url).includes("/oauth/status")) return statusResponse.promise;
      return Promise.resolve({ ok: true, status: 200, json: async () => ({}) });
    });
    const openWindow = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("open", openWindow);
    renderSection({ catalog: oauthCatalog, onRefresh });

    await act(async () => { reloginButtons()[0].click(); });
    await waitFor(() => fetchMock.mock.calls.some(([url]) => String(url).includes("/oauth/status")));
    const openai = providerCard("openai");
    const disclosure = openai.querySelector<HTMLDetailsElement>("details.cred-setup")!;
    const select = openai.querySelector<HTMLSelectElement>("select")!;
    expect(select.value).toBe("local:7");

    await act(async () => { await i18n.changeLanguage("en"); });
    const currentOpenai = providerCard("openai");
    const currentDisclosure = currentOpenai.querySelector<HTMLDetailsElement>("details.cred-setup")!;
    const currentSelect = currentOpenai.querySelector<HTMLSelectElement>("select")!;
    expect(currentDisclosure).toBe(disclosure);
    expect(currentSelect).toBe(select);
    expect(currentDisclosure.open).toBe(true);
    expect(currentSelect.value).toBe("local:7");
    expect(host!.textContent).toContain("Waiting for browser sign-in...");

    await act(async () => {
      statusResponse.resolve({
        ok: true,
        status: 200,
        json: async () => ({ status: "success", credential: chatgptCred, detail: null }),
      });
      await Promise.resolve();
    });
    await waitFor(() => onRefresh.mock.calls.length === 1);
    const completedOpenai = providerCard("openai");
    const completedDisclosure = completedOpenai.querySelector<HTMLDetailsElement>("details.cred-setup")!;
    const completedSelect = completedOpenai.querySelector<HTMLSelectElement>("select")!;
    expect(completedDisclosure).toBe(disclosure);
    expect(completedSelect).toBe(select);
    expect(completedDisclosure.open).toBe(true);
    expect(completedSelect.value).toBe("local:7");
    expect(fetchMock.mock.calls.filter(([url]) => String(url).includes("/oauth/start"))).toHaveLength(1);
    expect(fetchMock.mock.calls.filter(([url]) => String(url).includes("/oauth/status"))).toHaveLength(1);
    expect(fetchMock.mock.calls.filter(([url]) => String(url).includes("/oauth/cancel"))).toHaveLength(0);
    expect(openWindow).toHaveBeenCalledTimes(1);
    expect(onRefresh).toHaveBeenCalledTimes(1);
  });
});

describe("ProviderSection re-login integration (S3 credential lifecycle)", () => {
  it("row re-login opens the OpenAI setup disclosure, starts the flow with the target, and blocks a second trigger", async () => {
    const fetchMock = vi.fn().mockImplementation(async (url: unknown) => {
      const u = String(url);
      if (u.includes("/oauth/start")) {
        return { ok: true, status: 200, json: async () => ({ auth_url: "https://auth.openai.com/x", state: "S", expires_at: "t", manual_code_supported: true }) };
      }
      if (u.includes("/oauth/status")) {
        return { ok: true, status: 200, json: async () => ({ status: "error", credential: null, detail: "boom" }) };
      }
      return { ok: true, status: 200, json: async () => ({}) };
    });
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("open", vi.fn());
    renderSection();
    expect(host!.querySelectorAll("details.cred-setup[open]").length).toBe(0); // both collapsed initially
    const btn = reloginButtons()[0];
    expect(btn).toBeTruthy();
    await act(async () => {
      btn.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    });
    const startCall = fetchMock.mock.calls.find(([u]) => String(u).includes("/oauth/start"));
    expect(startCall).toBeTruthy();
    expect(JSON.parse((startCall![1] as RequestInit).body as string)).toEqual({
      make_active: false,
      relogin_credential_id: "local:7",
    });
    // the OpenAI setup disclosure (waiting/manual/cancel home) is expanded
    expect(host!.querySelectorAll("details.cred-setup[open]").length).toBe(1);
    // the poll settles on the backend error → manual fallback surfaces in the SAME region
    await waitFor(() => (host!.textContent ?? "").includes("等不到瀏覽器回呼"));
    expect(host!.textContent).toContain("完成登入");
    // a second trigger cannot start while this flow is active
    expect(reloginButtons().every((b) => b.disabled)).toBe(true);
  });

  it("openai setup copy explains subscription task billing without changing active", () => {
    vi.stubGlobal("fetch", vi.fn());
    renderSection();
    expect(host!.textContent).not.toContain("尚未接上");
    expect(host!.textContent).toContain("使用 ChatGPT 訂閱後端");
    expect(host!.textContent).toContain("消耗訂閱額度，非 API 帳單");
    const activeToggle = Array.from(providerCard("openai").querySelectorAll("label"))
      .find((label) => label.textContent?.includes("登入後設為 active"))
      ?.querySelector<HTMLInputElement>('input[type="checkbox"]');
    expect(activeToggle?.checked).toBe(false);
  });
});

describe("ProviderSection manual fallback gating (F4)", () => {
  it("does not offer the dead-end manual paste when the state was consumed", async () => {
    const fetchMock = vi.fn().mockImplementation(async (url: unknown) => {
      const u = String(url);
      if (u.includes("/oauth/start")) {
        return { ok: true, status: 200, json: async () => ({ auth_url: "https://auth.openai.com/x", state: "S", expires_at: "t", manual_code_supported: true }) };
      }
      if (u.includes("/oauth/status")) {
        return { ok: true, status: 200, json: async () => ({ status: "error", credential: null, detail: "cache clear failed", manual_completable: false }) };
      }
      return { ok: true, status: 200, json: async () => ({}) };
    });
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("open", vi.fn());
    renderSection();
    const btn = reloginButtons()[0];
    await act(async () => {
      btn.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    });
    await waitFor(() => (host!.textContent ?? "").includes("登入工作階段不存在或已過期"));
    expect(host!.textContent).not.toContain("完成登入");   // no dead-end manual form
    expect(reloginButtons().every((b) => !b.disabled)).toBe(true); // flow reset, retry allowed
  });
});

describe("ProviderSection Settings navigation guard", () => {
  it("reports_credential_and_oauth_form_drafts_without_exposing_secret_values", async () => {
    const onNavigationGuardChange = vi.fn();
    renderSection({ onNavigationGuardChange });
    const anthropic = providerCard("anthropic");
    const apiKey = anthropic.querySelector<HTMLInputElement>('input[type="password"]')!;
    const alias = anthropic.querySelector<HTMLInputElement>(
      ".credential-add-box:not(.oauth-import-box) input:not([type='password'])",
    )!;

    await act(async () => {
      changeInput(alias, "planted-alias-value");
      changeInput(apiKey, "sk-planted-secret-value");
    });
    expect(latestReport(onNavigationGuardChange)).toEqual({
      dirty: true,
      busy: false,
      reason: "Provider 登入與憑證有未儲存的變更。",
    });
    expect(JSON.stringify(onNavigationGuardChange.mock.calls)).not.toContain("planted-alias-value");
    expect(JSON.stringify(onNavigationGuardChange.mock.calls)).not.toContain("sk-planted-secret-value");

    await act(async () => {
      changeInput(alias, "");
      changeInput(apiKey, "");
      const openaiToggle = Array.from(providerCard("openai").querySelectorAll("label"))
        .find((label) => label.textContent?.includes("登入後設為 active"))
        ?.querySelector<HTMLInputElement>('input[type="checkbox"]');
      openaiToggle?.click();
    });
    expect(latestReport(onNavigationGuardChange).dirty).toBe(true);
  });

  it("reports_oauth_and_credential_mutations_as_navigation_blocking_until_settled", async () => {
    const credentialResponse = deferred<{ ok: boolean; status: number; json: () => Promise<unknown> }>();
    const fetchMock = vi.fn(() => credentialResponse.promise);
    vi.stubGlobal("fetch", fetchMock);
    const onCredentialGuard = vi.fn();
    renderSection({ onNavigationGuardChange: onCredentialGuard });
    const anthropic = providerCard("anthropic");
    const apiKey = anthropic.querySelector<HTMLInputElement>('input[type="password"]')!;
    await act(async () => { changeInput(apiKey, "sk-planted-mutation-secret"); });
    const addButton = Array.from(anthropic.querySelectorAll<HTMLButtonElement>("button"))
      .find((button) => button.textContent?.includes("新增"));
    if (!addButton) throw new Error("missing add credential button");
    await act(async () => { addButton.click(); });
    expect(latestReport(onCredentialGuard)).toEqual({
      dirty: true,
      busy: true,
      reason: "Provider 登入或 Credential 更新正在進行。",
    });
    credentialResponse.resolve({
      ok: true,
      status: 200,
      json: async () => ({ credential: anthropicKey }),
    });
    await waitFor(() => latestReport(onCredentialGuard)?.busy === false);
    expect(JSON.stringify(onCredentialGuard.mock.calls)).not.toContain("sk-planted-mutation-secret");

    act(() => root!.unmount());
    root = null;
    host!.remove();
    host = null;

    const oauthStart = deferred<{ ok: boolean; status: number; json: () => Promise<unknown> }>();
    vi.stubGlobal("open", vi.fn());
    vi.stubGlobal("fetch", vi.fn((url: unknown) => {
      if (String(url).includes("/oauth/start")) return oauthStart.promise;
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => ({ status: "error", credential: null, detail: "closed", manual_completable: false }),
      });
    }));
    const onOauthGuard = vi.fn();
    renderSection({ onNavigationGuardChange: onOauthGuard });
    const login = Array.from(providerCard("openai").querySelectorAll<HTMLButtonElement>("button"))
      .find((button) => button.textContent?.trim() === "登入 ChatGPT");
    if (!login) throw new Error("missing ChatGPT login button");
    await act(async () => { login.click(); });
    expect(latestReport(onOauthGuard).busy).toBe(true);
    oauthStart.resolve({
      ok: true,
      status: 200,
      json: async () => ({
        auth_url: "https://auth.openai.com/planted-public-state",
        state: "planted-public-state",
        expires_at: "2026-07-20T00:00:00Z",
        manual_code_supported: true,
      }),
    });
    await waitFor(() => latestReport(onOauthGuard)?.busy === false);
    expect(JSON.stringify(onOauthGuard.mock.calls)).not.toContain("planted-public-state");
  });
});

describe("ProviderSection OAuth lifecycle and account usage truth", () => {
  it("renders_retained_account_usage_immediately_and_revalidates_with_cached_GET_only", async () => {
    const now = Date.now();
    const cache = createSettingsReadCache({ clock: () => now });
    const credential = oauthCredential({ active: true });
    const retained = accountView(accountSnapshot({
      observedAt: new Date(now - 6 * 60_000).toISOString(),
      usedPercent: 11,
    }));
    const refreshed = accountView(accountSnapshot({
      observedAt: new Date(now).toISOString(),
      usedPercent: 12,
    }));
    cache.replace(oauthAccountUsageKey(credential.id), retained, now - 6 * 60_000);
    const response = deferred<Awaited<ReturnType<typeof jsonResponse>>>();
    const fetchMock = vi.fn(() => response.promise);
    vi.stubGlobal("fetch", fetchMock);
    vi.spyOn(document, "visibilityState", "get").mockReturnValue("hidden");
    const value = catalog();
    value.credentials.openai = [credential];

    renderSection({ catalog: value, settingsReadCache: cache });

    expect(credentialRow("ChatGPT subscription Plus").textContent).toContain("已用：11%");
    expect(callsFor(fetchMock, "local%3A7/account-usage", "GET")).toHaveLength(1);
    expect(callsFor(fetchMock, "/account-usage/sync", "POST")).toHaveLength(0);

    response.resolve(await jsonResponse(refreshed));
    await waitFor(() => (credentialRow("ChatGPT subscription Plus").textContent ?? "").includes("已用：12%"));
    expect(callsFor(fetchMock, "/account-usage/sync", "POST")).toHaveLength(0);
  });

  it("preserves_retained_account_truth_when_cached_revalidation_fails_without_sync_POST", async () => {
    const now = Date.now();
    const cache = createSettingsReadCache({ clock: () => now });
    const credential = oauthCredential({ active: true });
    const retained = accountView(accountSnapshot({
      observedAt: new Date(now - 6 * 60_000).toISOString(),
      usedPercent: 31,
    }));
    cache.replace(oauthAccountUsageKey(credential.id), retained, now - 6 * 60_000);
    const fetchMock = vi.fn().mockRejectedValue(new Error("offline"));
    vi.stubGlobal("fetch", fetchMock);
    vi.spyOn(document, "visibilityState", "get").mockReturnValue("hidden");
    const value = catalog();
    value.credentials.openai = [credential];

    renderSection({ catalog: value, settingsReadCache: cache });
    await flushPromises();

    expect(credentialRow("ChatGPT subscription Plus").textContent).toContain("已用：31%");
    expect(callsFor(fetchMock, "local%3A7/account-usage", "GET")).toHaveLength(1);
    expect(callsFor(fetchMock, "/account-usage/sync", "POST")).toHaveLength(0);
    expect(cache.inspect(oauthAccountUsageKey(credential.id)).status).toBe("stale");
  });

  it("manual_sync_replaces_only_the_affected_account_cache_entry", async () => {
    const now = Date.now();
    const cache = createSettingsReadCache({ clock: () => now });
    const first = oauthCredential({ id: "local:7", label: "Account A", active: true });
    const second = oauthCredential({ id: "local:8", label: "Account B", active: true });
    const firstBefore = accountView(accountSnapshot({
      credentialId: first.id,
      observedAt: new Date(now).toISOString(),
      usedPercent: 41,
    }));
    const secondBefore = accountView(accountSnapshot({
      credentialId: second.id,
      observedAt: new Date(now).toISOString(),
      usedPercent: 52,
    }));
    const firstAfter = accountView(accountSnapshot({
      credentialId: first.id,
      observedAt: new Date(now + 1_000).toISOString(),
      usedPercent: 42,
    }), "succeeded");
    cache.replace(oauthAccountUsageKey(first.id), firstBefore, now);
    cache.replace(oauthAccountUsageKey(second.id), secondBefore, now);
    const loadSpy = vi.spyOn(cache, "load");
    const replaceSpy = vi.spyOn(cache, "replace");
    const fetchMock = vi.fn((url: unknown, init?: RequestInit) => {
      if (String(url).includes("local%3A7/account-usage/sync") && init?.method === "POST") {
        return jsonResponse(firstAfter);
      }
      return jsonResponse({});
    });
    vi.stubGlobal("fetch", fetchMock);
    const value = catalog();
    value.credentials.openai = [first, second];

    renderSection({ catalog: value, settingsReadCache: cache });
    await flushPromises();
    const sync = Array.from(credentialRow("Account A").querySelectorAll("button"))
      .find((button) => button.textContent?.trim() === "同步使用量") as HTMLButtonElement;
    await act(async () => { sync.click(); });
    await waitFor(() => (credentialRow("Account A").textContent ?? "").includes("已用：42%"));

    const firstCached = cache.inspect<ReturnType<typeof accountView>>(oauthAccountUsageKey(first.id));
    const secondCached = cache.inspect<ReturnType<typeof accountView>>(oauthAccountUsageKey(second.id));
    expect(firstCached.status).toBe("fresh");
    expect(firstCached.status === "missing" ? null : firstCached.value).toEqual(firstAfter);
    expect(secondCached.status).toBe("fresh");
    expect(secondCached.status === "missing" ? null : secondCached.value).toEqual(secondBefore);
    expect(callsFor(fetchMock, "/account-usage/sync", "POST")).toHaveLength(1);
    expect(JSON.stringify([...loadSpy.mock.calls, ...replaceSpy.mock.calls])).not.toContain("raw-account");
  });

  it("renders retryable refresh failure separately from re-login required", () => {
    const value = catalog();
    value.credentials.openai = [
      oauthCredential({
        id: "local:7",
        label: "Temporary refresh failure",
        available: false,
        lifecycle_state: "refresh_failed_retryable",
        lifecycle_error_code: "transport_error",
      }),
      oauthCredential({
        id: "local:8",
        label: "Terminal refresh failure",
        available: false,
        lifecycle_state: "reauth_required",
        lifecycle_error_code: "invalid_grant",
      }),
    ];

    renderSection({ catalog: value });

    const retryable = credentialRow("Temporary refresh failure");
    const terminal = credentialRow("Terminal refresh failure");
    expect(retryable.textContent).toContain("登入更新暫時失敗");
    expect(retryable.textContent).not.toContain("需要重新登入");
    expect(terminal.textContent).toContain("需要重新登入");
    expect(retryable.querySelector(".credential-status-pill.ok")).toBeNull();
    expect(terminal.querySelector(".credential-status-pill.ok")).toBeNull();
  });

  it("does not treat an expired OAuth credential as active or collapse setup", async () => {
    const value = catalog();
    value.credentials.openai = [oauthCredential({
      active: true,
      available: false,
      lifecycle_state: "refresh_required",
      expires_at: "2026-08-08T00:00:00+00:00",
    })];
    const fetchMock = vi.fn(() => jsonResponse(accountView(null)));
    vi.stubGlobal("fetch", fetchMock);

    renderSection({ catalog: value });
    await flushPromises();

    const openai = providerCard("openai");
    const providerStatus = openai.querySelector<HTMLElement>(".settings-panel-head .key-pill")!;
    expect(providerStatus.textContent).toBe("需要更新登入權杖");
    expect(providerStatus.classList.contains("ok")).toBe(false);
    expect(openai.querySelector<HTMLDetailsElement>("details.cred-setup")?.open).toBe(true);
    expect(credentialRow("ChatGPT subscription Plus").textContent).toContain("需要更新登入權杖");
  });

  it("renders direct used percentage and reset time with inferred remaining labeled", async () => {
    const observedAt = new Date(Date.now() - 60_000).toISOString();
    const value = catalog();
    value.credentials.openai = [oauthCredential({ active: true })];
    const snapshot = accountSnapshot({
      observedAt,
      usedPercent: 18,
      resetsAt: 1786190400,
      overageStatus: "rejected",
      overageReason: "out_of_credits",
    });
    const fetchMock = vi.fn(() => jsonResponse(accountView(snapshot)));
    vi.stubGlobal("fetch", fetchMock);

    renderSection({ catalog: value });
    await waitFor(() => (host!.textContent ?? "").includes("已用：18%"));

    const row = credentialRow("ChatGPT subscription Plus");
    expect(row.textContent).toContain("推算剩餘：82%");
    expect(row.textContent).toContain(
      `重置：${formatSystemTimestamp(new Date(1786190400 * 1000).toISOString())}`,
    );
    expect(row.textContent).toContain("超額使用：拒絕");
    expect(row.textContent).toContain("out_of_credits");
    expect(row.textContent).toContain("來源：codex_app_server");
    expect(row.textContent).toContain(
      `觀察時間：${formatSystemTimestamp(observedAt)}`,
    );
    expect(callsFor(fetchMock, "/account-usage/sync", "POST")).toHaveLength(0);
  });

  it("renders missing account fields as unknown instead of zero", async () => {
    const observedAt = new Date(Date.now() - 60_000).toISOString();
    const value = catalog();
    value.credentials.openai = [oauthCredential({ active: true })];
    const snapshot = accountSnapshot({
      observedAt,
      usedPercent: null,
      resetsAt: null,
      status: null,
      overageStatus: null,
      overageReason: null,
    });
    vi.stubGlobal("fetch", vi.fn(() => jsonResponse(accountView(snapshot))));

    renderSection({ catalog: value });
    await waitFor(() => (host!.textContent ?? "").includes("已用：未知"));

    const row = credentialRow("ChatGPT subscription Plus");
    expect(row.textContent).toContain("推算剩餘：未知");
    expect(row.textContent).toContain("重置：未知");
    expect(row.textContent).toContain("超額使用：未知");
    expect(row.textContent).not.toContain("已用：0%");
    expect(row.textContent).not.toContain("推算剩餘：100%");
  });

  it("does not sync stale ChatGPT usage without an explicit manual click", async () => {
    let visibility: DocumentVisibilityState = "visible";
    vi.spyOn(document, "visibilityState", "get").mockImplementation(() => visibility);
    const intervalSpy = vi.spyOn(window, "setInterval");
    const value = catalog();
    value.credentials.openai = [oauthCredential({ active: true })];
    const stale = accountSnapshot({ observedAt: new Date(Date.now() - 6 * 60_000).toISOString() });
    const fresh = accountSnapshot({ observedAt: new Date().toISOString(), usedPercent: 19 });
    const realDateNow = Date.now.bind(Date);
    let nowOffset = 0;
    vi.spyOn(Date, "now").mockImplementation(() => realDateNow() + nowOffset);
    const cache = createSettingsReadCache({ clock: () => Date.now() });
    const fetchMock = vi.fn((url: unknown, init?: RequestInit) => {
      if ((init?.method ?? "GET") === "POST") return jsonResponse(accountView(fresh, "succeeded"));
      return jsonResponse(accountView(stale));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderSection({ catalog: value, settingsReadCache: cache });
    await waitFor(() => (host!.textContent ?? "").includes("已用：18%"));
    await act(async () => {
      window.dispatchEvent(new Event("focus"));
      document.dispatchEvent(new Event("visibilitychange"));
      await new Promise((resolve) => setTimeout(resolve, 80));
    });
    expect(callsFor(fetchMock, "/account-usage/sync", "POST")).toHaveLength(0);
    expect(intervalSpy).not.toHaveBeenCalled();

    const sync = Array.from(credentialRow("ChatGPT subscription Plus").querySelectorAll("button"))
      .find((button) => button.textContent?.trim() === "同步使用量") as HTMLButtonElement;
    await act(async () => {
      sync.click();
      await new Promise((resolve) => setTimeout(resolve, 20));
    });
    expect(callsFor(fetchMock, "/account-usage/sync", "POST")).toHaveLength(1);
    await waitFor(() => (host!.textContent ?? "").includes("已用：19%"));

    // Deferred-GET race: an older in-flight cached GET resolving AFTER the
    // manual sync must not roll the display back (the sync invalidates the
    // cache generation before replacing).
    let releaseOldGet: (() => void) | null = null;
    fetchMock.mockImplementation((url: unknown, init?: RequestInit) => {
      if ((init?.method ?? "GET") === "POST") return jsonResponse(accountView(fresh, "succeeded"));
      return new Promise((resolveGet) => {
        releaseOldGet = () => resolveGet({
          ok: true,
          status: 200,
          json: async () => accountView(stale),
        });
      });
    });
    nowOffset += 6 * 60_000;
    await act(async () => {
      window.dispatchEvent(new Event("focus"));
      await new Promise((resolve) => setTimeout(resolve, 20));
    });
    nowOffset += 11_000;
    await act(async () => {
      sync.click();
      await new Promise((resolve) => setTimeout(resolve, 20));
    });
    await waitFor(() => (host!.textContent ?? "").includes("已用：19%"));
    await act(async () => {
      releaseOldGet?.();
      await new Promise((resolve) => setTimeout(resolve, 30));
    });
    expect(host!.textContent).toContain("已用：19%");
    expect(host!.textContent).not.toContain("已用：18%");
  });

  it("manual sync bypasses the TTL and observes the ten-second cooldown", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-08T08:01:00+00:00"));
    const value = catalog();
    value.credentials.openai = [oauthCredential({ active: true })];
    const fresh = accountSnapshot({ observedAt: "2026-08-08T08:00:00+00:00" });
    const fetchMock = vi.fn(() => jsonResponse(accountView(fresh, "succeeded")));
    vi.stubGlobal("fetch", fetchMock);

    renderSection({ catalog: value });
    await flushPromises(8);
    const sync = Array.from(credentialRow("ChatGPT subscription Plus").querySelectorAll("button"))
      .find((button) => button.textContent?.trim() === "同步使用量") as HTMLButtonElement;
    expect(sync).toBeTruthy();

    await act(async () => { sync.click(); await Promise.resolve(); });
    await flushPromises();
    expect(callsFor(fetchMock, "/account-usage/sync", "POST")).toHaveLength(1);
    expect(sync.disabled).toBe(true);
    sync.click();
    expect(callsFor(fetchMock, "/account-usage/sync", "POST")).toHaveLength(1);

    await act(async () => { await vi.advanceTimersByTimeAsync(9_999); });
    expect(sync.disabled).toBe(true);
    await act(async () => { await vi.advanceTimersByTimeAsync(1); });
    expect(sync.disabled).toBe(false);
    await act(async () => { sync.click(); await Promise.resolve(); });
    await flushPromises();
    expect(callsFor(fetchMock, "/account-usage/sync", "POST")).toHaveLength(2);
  });

  it("credential mutation invalidates only the affected account snapshot", async () => {
    const observedAt = new Date(Date.now() - 60_000).toISOString();
    const first = oauthCredential({ id: "local:7", label: "Account A", active: true });
    const second = oauthCredential({ id: "local:8", label: "Account B", active: false });
    const firstSnapshot = accountSnapshot({ credentialId: "local:7", observedAt, usedPercent: 11 });
    const secondSnapshot = accountSnapshot({ credentialId: "local:8", observedAt, usedPercent: 22 });
    const onRefresh = vi.fn().mockResolvedValue(undefined);
    const fetchMock = vi.fn((url: unknown, init?: RequestInit) => {
      const path = String(url);
      if ((init?.method ?? "GET") === "PUT") {
        return jsonResponse({ credential: { ...second, active: true } });
      }
      if (path.includes("local%3A8/account-usage")) return jsonResponse(accountView(secondSnapshot));
      if (path.includes("local%3A7/account-usage")) return jsonResponse(accountView(firstSnapshot));
      return jsonResponse({});
    });
    vi.stubGlobal("fetch", fetchMock);
    const firstCatalog = catalog();
    firstCatalog.credentials.openai = [first, second];

    renderSection({ catalog: firstCatalog, onRefresh });
    await waitFor(() => callsFor(fetchMock, "local%3A7/account-usage", "GET").length === 1);
    await waitFor(() => (credentialRow("Account A").textContent ?? "").includes("已用：11%"));

    const secondCatalog = catalog();
    secondCatalog.credentials.openai = [
      { ...first, active: false },
      { ...second, active: true },
    ];
    rerenderSection({ catalog: secondCatalog });
    await waitFor(() => callsFor(fetchMock, "local%3A8/account-usage", "GET").length === 1);
    const save = Array.from(credentialRow("Account B").querySelectorAll("button"))
      .find((button) => button.textContent?.trim() === "儲存顯示資訊") as HTMLButtonElement;
    await act(async () => { save.click(); });
    await waitFor(() => callsFor(fetchMock, "local%3A8/account-usage", "GET").length === 2);
    expect(onRefresh).toHaveBeenCalledTimes(1);

    rerenderSection({ catalog: firstCatalog });
    await flushPromises();
    expect(callsFor(fetchMock, "local%3A7/account-usage", "GET")).toHaveLength(1);
    expect(credentialRow("Account A").textContent).toContain("已用：11%");
  });
});


describe("ProviderSection read and sync recovery states", () => {
  function claudeCredential(overrides: Partial<LifecycleCredential> = {}): LifecycleCredential {
    return oauthCredential({
      id: "local:1",
      provider: "anthropic",
      auth_type: "claude_code_oauth",
      label: "Claude subscription",
      active: true,
      ...overrides,
    } as Partial<LifecycleCredential>);
  }

  function claudeSnapshot(overrides: Parameters<typeof accountSnapshot>[0] = {}) {
    return accountSnapshot({
      credentialId: "local:1",
      provider: "anthropic",
      authMode: "claude_code_oauth",
      source: "anthropic_oauth_probe",
      usedPercent: 5,
      secondary: { used_percent: 14, window_duration_minutes: 10080, resets_at: 1786687200 },
      ...overrides,
    });
  }

  it("cached read failure without snapshot says no confirmed observation", async () => {
    const value = catalog();
    value.credentials.openai = [oauthCredential({ active: true })];
    const fetchMock = vi.fn(() => jsonResponse({ detail: "boom" }, 500));
    vi.stubGlobal("fetch", fetchMock);

    renderSection({ catalog: value });
    await waitFor(() => (host!.textContent ?? "").includes("無法讀取本地觀察"));
    expect(host!.textContent).toContain("目前沒有已確認的觀察");
    expect(host!.textContent).not.toContain("仍顯示");
    expect(callsFor(fetchMock, "/account-usage/sync", "POST")).toHaveLength(0);
  });

  it("cached read failure with snapshot keeps observation and its observed_at", async () => {
    const value = catalog();
    value.credentials.openai = [oauthCredential({ active: true })];
    const retained = accountSnapshot({ observedAt: "2026-08-10T01:00:00+00:00" });
    let clockNow = Date.now();
    const cache = createSettingsReadCache({ clock: () => clockNow });
    let reads = 0;
    const fetchMock = vi.fn((url: unknown, init?: RequestInit) => {
      if ((init?.method ?? "GET") === "GET" && String(url).includes("/account-usage")) {
        reads += 1;
        if (reads === 1) return jsonResponse(accountView(retained));
        return jsonResponse({ detail: "boom" }, 500);
      }
      return jsonResponse({ detail: "unexpected" }, 500);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderSection({ catalog: value, settingsReadCache: cache });
    await waitFor(() => (host!.textContent ?? "").includes("已用：18%"));

    // Push the retained view past the five-minute freshness; the focus
    // revalidation is now a real GET that fails, and truth must be kept.
    clockNow += 6 * 60_000;
    await act(async () => {
      window.dispatchEvent(new Event("focus"));
      await new Promise((resolve) => setTimeout(resolve, 40));
    });
    await waitFor(() => reads >= 2);
    await flushPromises(6);
    expect(host!.textContent).toContain("已用：18%");
    expect(host!.textContent).toContain("無法讀取本地觀察");
    expect(host!.textContent).toContain(formatSystemTimestamp("2026-08-10T01:00:00+00:00"));
    expect(callsFor(fetchMock, "/account-usage/sync", "POST")).toHaveLength(0);
  });

  it("sync transport failure is never labeled cached_read_failed", async () => {
    const value = catalog();
    value.credentials.openai = [oauthCredential({ active: true })];
    const fetchMock = vi.fn((url: unknown, init?: RequestInit) => {
      if ((init?.method ?? "GET") === "POST") return Promise.reject(new Error("socket down"));
      return jsonResponse(accountView(accountSnapshot()));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderSection({ catalog: value });
    await waitFor(() => (host!.textContent ?? "").includes("已用：18%"));
    const sync = Array.from(credentialRow("ChatGPT subscription Plus").querySelectorAll("button"))
      .find((button) => button.textContent?.trim() === "同步使用量") as HTMLButtonElement;
    await act(async () => {
      sync.click();
      await new Promise((resolve) => setTimeout(resolve, 30));
    });
    expect(host!.textContent).toContain("provider 結果未知");
    expect(host!.textContent).not.toContain("cached_read_failed");
    expect(host!.textContent).toContain("已用：18%");
  });

  it("decoded backend sync failure shows its stable backend code", async () => {
    const value = catalog();
    value.credentials.openai = [oauthCredential({ active: true })];
    const retained = accountSnapshot();
    const realDateNow = Date.now.bind(Date);
    let nowOffset = 0;
    vi.spyOn(Date, "now").mockImplementation(() => realDateNow() + nowOffset);
    const cache = createSettingsReadCache({ clock: () => Date.now() });
    let postCode: string | null = null;
    let postSnapshot: ReturnType<typeof accountSnapshot> | null = null;
    let serverView: ReturnType<typeof accountView> | null = null;
    const fetchMock = vi.fn((url: unknown, init?: RequestInit) => {
      if ((init?.method ?? "GET") === "POST") {
        return jsonResponse({ credential_id: "local:7", snapshot: postSnapshot, sync_status: "failed", sync_error_code: postCode });
      }
      return jsonResponse(serverView ?? accountView(retained));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderSection({ catalog: value, settingsReadCache: cache });
    await waitFor(() => (host!.textContent ?? "").includes("已用：18%"));
    const syncButton = () => Array.from(credentialRow("ChatGPT subscription Plus").querySelectorAll("button"))
      .find((button) => button.textContent?.trim() === "同步使用量") as HTMLButtonElement;

    // Phase A: decoded failure with a retained snapshot keeps BOTH the
    // observation and the stable backend code (LD 3/9).
    postCode = "version_incompatible";
    await act(async () => {
      syncButton().click();
      await new Promise((resolve) => setTimeout(resolve, 30));
    });
    expect(host!.textContent).toContain("version_incompatible");
    expect(host!.textContent).toContain("已用：18%");
    expect(host!.textContent).not.toContain("provider 結果未知");

    // Phase B: a later successful cached GET must not clear the backend
    // sync error channel.
    nowOffset += 6 * 60_000;
    await act(async () => {
      window.dispatchEvent(new Event("focus"));
      await new Promise((resolve) => setTimeout(resolve, 40));
    });
    expect(host!.textContent).toContain("已用：18%");
    expect(host!.textContent).toContain("version_incompatible");

    // Phase C: the one typed exception — the credential changed during the
    // sync, so the stale observation is cleared instead of retained, and
    // the cache entry is invalidated so focus cannot resurrect it.
    nowOffset += 11_000;
    postCode = "credential_changed_during_sync";
    serverView = { credential_id: "local:7", snapshot: null, sync_status: "not_requested", sync_error_code: null };
    await act(async () => {
      syncButton().click();
      await new Promise((resolve) => setTimeout(resolve, 30));
    });
    expect(host!.textContent).toContain("credential_changed_during_sync");
    expect(host!.textContent).not.toContain("已用：18%");
    expect(host!.textContent).toContain("帳戶用量：未知");
    expect(host!.textContent).not.toContain("仍顯示");

    // Resurrection guard: focus revalidation must MISS the invalidated
    // cache (a real GET fires, returning the server's post-change truth)
    // instead of reviving the dead 18% observation from a fresh cache hit.
    const getsBefore = callsFor(fetchMock, "/account-usage", "GET").length;
    await act(async () => {
      window.dispatchEvent(new Event("focus"));
      await new Promise((resolve) => setTimeout(resolve, 40));
    });
    expect(callsFor(fetchMock, "/account-usage", "GET").length).toBeGreaterThan(getsBefore);
    expect(host!.textContent).not.toContain("已用：18%");
    expect(host!.textContent).toContain("帳戶用量：未知");

    // Phase D: a non-credential-changed failure whose view CARRIES an
    // authoritative snapshot must display that snapshot, not stay unknown.
    nowOffset += 11_000;
    // re-render so the button recomputes its cooldown state at the new time
    await act(async () => {
      window.dispatchEvent(new Event("focus"));
      await new Promise((resolve) => setTimeout(resolve, 30));
    });
    postCode = "version_incompatible";
    postSnapshot = accountSnapshot({ usedPercent: 21, observedAt: "2026-08-10T03:00:00+00:00" });
    await act(async () => {
      syncButton().click();
      await new Promise((resolve) => setTimeout(resolve, 30));
    });
    expect(host!.textContent).toContain("version_incompatible");
    expect(host!.textContent).toContain("已用：21%");
    expect(host!.textContent).not.toContain("帳戶用量：未知");
  });

  it("first cached read failure schedules exactly one bounded retry and unmount cancels it", async () => {
    const value = catalog();
    value.credentials.openai = [oauthCredential({ active: true })];
    const fetchMock = vi.fn(() => jsonResponse({ detail: "boom" }, 500));
    vi.stubGlobal("fetch", fetchMock);

    renderSection({ catalog: value });
    await flushPromises(6);
    const before = callsFor(fetchMock, "/account-usage", "GET").length;
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 1100));
    });
    const afterOne = callsFor(fetchMock, "/account-usage", "GET").length;
    expect(afterOne).toBe(before + 1);
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 1200));
    });
    expect(callsFor(fetchMock, "/account-usage", "GET").length).toBe(afterOne);

    const priorCalls = fetchMock.mock.calls.length;
    renderSection({ catalog: value });
    await flushPromises(4);
    await act(async () => {
      root!.unmount();
      root = null;
      await new Promise((resolve) => setTimeout(resolve, 1200));
    });
    const tail = (fetchMock.mock.calls as unknown as [unknown, RequestInit | undefined][])
      .slice(priorCalls)
      .filter((call) => String(call[0]).includes("/account-usage")
        && (call[1]?.method ?? "GET") === "GET");
    expect(tail.length).toBe(1);
  });

  it("manual retry local read performs one GET and zero sync POSTs", async () => {
    const value = catalog();
    value.credentials.openai = [oauthCredential({ active: true })];
    const fetchMock = vi.fn(() => jsonResponse({ detail: "boom" }, 500));
    vi.stubGlobal("fetch", fetchMock);

    renderSection({ catalog: value });
    await waitFor(() => (host!.textContent ?? "").includes("無法讀取本地觀察"));
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 1100));
    });
    const before = callsFor(fetchMock, "/account-usage", "GET").length;
    const retry = Array.from(credentialRow("ChatGPT subscription Plus").querySelectorAll("button"))
      .find((button) => button.textContent?.trim() === "重試本地讀取") as HTMLButtonElement;
    expect(retry).toBeTruthy();
    await act(async () => {
      retry.click();
      await new Promise((resolve) => setTimeout(resolve, 30));
    });
    expect(callsFor(fetchMock, "/account-usage", "GET").length).toBe(before + 1);
    expect(callsFor(fetchMock, "/account-usage/sync", "POST")).toHaveLength(0);
  });

  it("claude row shows cost labeled manual sync and one click sends one POST", async () => {
    const value = catalog();
    value.credentials.anthropic = [claudeCredential()];
    const probe = claudeSnapshot({ observedAt: "2026-08-10T02:00:00+00:00" });
    const fetchMock = vi.fn((url: unknown, init?: RequestInit) => {
      if ((init?.method ?? "GET") === "POST") return jsonResponse({ credential_id: "local:1", snapshot: probe, sync_status: "succeeded", sync_error_code: null });
      return jsonResponse({ credential_id: "local:1", snapshot: null, sync_status: "not_requested", sync_error_code: null });
    });
    vi.stubGlobal("fetch", fetchMock);

    renderSection({ catalog: value });
    await flushPromises(6);
    const row = credentialRow("Claude subscription");
    const sync = Array.from(row.querySelectorAll("button"))
      .find((button) => (button.textContent ?? "").includes("同步用量")) as HTMLButtonElement;
    expect(sync).toBeTruthy();
    expect(sync.textContent).toContain("消耗少量訂閱用量");
    await act(async () => {
      sync.click();
      await new Promise((resolve) => setTimeout(resolve, 30));
    });
    expect(callsFor(fetchMock, "/account-usage/sync", "POST")).toHaveLength(1);
    await waitFor(() => (host!.textContent ?? "").includes("已用：5%"));
    expect(host!.textContent).toContain("5 小時視窗");
    expect(host!.textContent).toContain("7 天視窗");
    expect(host!.textContent).toContain("來源：anthropic_oauth_probe");
  });

  it("claude page load focus and idle send zero anthropic requests", async () => {
    const value = catalog();
    value.credentials.anthropic = [claudeCredential()];
    const fetchMock = vi.fn(() => jsonResponse({ credential_id: "local:1", snapshot: null, sync_status: "not_requested", sync_error_code: null }));
    vi.stubGlobal("fetch", fetchMock);

    renderSection({ catalog: value });
    await flushPromises(6);
    await act(async () => {
      window.dispatchEvent(new Event("focus"));
      document.dispatchEvent(new Event("visibilitychange"));
      await new Promise((resolve) => setTimeout(resolve, 120));
    });
    expect(callsFor(fetchMock, "/account-usage/sync", "POST")).toHaveLength(0);
    const posts = (fetchMock.mock.calls as unknown as [unknown, RequestInit | undefined][])
      .filter((call) => (call[1]?.method ?? "GET") === "POST");
    expect(posts).toHaveLength(0);
  });
});
