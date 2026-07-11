/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProviderSection } from "./Settings";
import type { ModelCatalog, ProviderCredential } from "./api";

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

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

function renderSection() {
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
    }));
  });
}

function reloginButtons(): HTMLButtonElement[] {
  return Array.from(host!.querySelectorAll("button")).filter(
    (b) => b.textContent?.trim() === "重新登入",
  ) as HTMLButtonElement[];
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
    await waitFor(() => (host!.textContent ?? "").includes("登入失敗"));
    expect(host!.textContent).toContain("完成登入");
    // a second trigger cannot start while this flow is active
    expect(reloginButtons().every((b) => b.disabled)).toBe(true);
  });

  it("openai setup copy is three-axis honest (research wired; cards api-key-only)", () => {
    vi.stubGlobal("fetch", vi.fn());
    renderSection();
    expect(host!.textContent).not.toContain("尚未接上");
    expect(host!.textContent).toContain("卡片合成／翻譯仍需 API key");
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
    await waitFor(() => (host!.textContent ?? "").includes("登入失敗"));
    expect(host!.textContent).toContain("已失效");
    expect(host!.textContent).not.toContain("完成登入");   // no dead-end manual form
    expect(reloginButtons().every((b) => !b.disabled)).toBe(true); // flow reset, retry allowed
  });
});
