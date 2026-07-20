/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import i18n from "i18next";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ProviderSection } from "./Settings";
import type { ModelCatalog, ProviderCredential } from "./api";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

beforeEach(async () => {
  await i18n.changeLanguage("zh-Hant");
});

afterEach(() => {
  vi.unstubAllGlobals();
  if (root) {
    act(() => root!.unmount());
    root = null;
  }
  host?.remove();
  host = null;
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
  act(() => {
    root!.render(React.createElement(ProviderSection, {
      catalog: catalog(),
      runtime: null,
      discovery: {},
      onRefresh: vi.fn().mockResolvedValue(undefined),
      onDiscover: vi.fn().mockResolvedValue(undefined),
      onClearDiscovery: vi.fn(),
      onUseModel: vi.fn(),
      ...extra,
    }));
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

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
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
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
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
    expect(host!.querySelector(".developer-diagnostics")?.getAttribute("aria-live")).toBeNull();
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
