/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DiscoveryResultView } from "./Settings";

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

afterEach(() => {
  if (root) {
    act(() => root!.unmount());
    root = null;
  }
  host?.remove();
  host = null;
});

describe("DiscoveryResultView", () => {
  it("shows the producing credential and can be closed", async () => {
    const onClose = vi.fn();

    host = document.createElement("div");
    document.body.append(host);
    root = createRoot(host);

    await act(async () => {
      root!.render(
        React.createElement(DiscoveryResultView, {
          result: {
            provider: "openai",
            credential_id: "local:7",
            status: "ok",
            models: [{ id: "gpt-5.4-mini", provider: "openai", label: "gpt-5.4-mini", source: "provider_api" }],
            error: null,
            source_url: null,
          },
          authMode: "chatgpt_oauth",
          credentialLabel: "TS_Codex",
          onClose,
          onUse: vi.fn(),
        }),
      );
    });

    expect(host.textContent).toContain("列模型結果");
    expect(host.textContent).toContain("ChatGPT backend · live");
    expect(host.textContent).toContain("來源：TS_Codex / chatgpt_oauth");

    const closeButton = Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "關閉");
    expect(closeButton).toBeTruthy();

    await act(async () => {
      closeButton!.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    });

    expect(onClose).toHaveBeenCalledTimes(1);
  });
});

describe("DiscoveryResultView reauth affordance (S3 credential lifecycle)", () => {
  function renderView(resultOver: Record<string, unknown>, extra: Record<string, unknown> = {}) {
    host = document.createElement("div");
    document.body.append(host);
    root = createRoot(host);
    act(() => {
      root!.render(
        React.createElement(DiscoveryResultView, {
          result: {
            provider: "openai",
            credential_id: "local:7",
            status: "error",
            models: [],
            error: "re-login needed (token refresh failed): [REDACTED]",
            source_url: null,
            ...resultOver,
          },
          authMode: "chatgpt_oauth",
          credentialLabel: "Sub",
          onClose: vi.fn(),
          onUse: vi.fn(),
          ...extra,
        }),
      );
    });
  }

  it("renders the re-login affordance for reauth_required and invokes it", async () => {
    const onRelogin = vi.fn();
    renderView({ error_code: "reauth_required" }, { onRelogin });
    const btn = Array.from(host!.querySelectorAll("button")).find((b) => b.textContent?.trim() === "重新登入");
    expect(btn).toBeTruthy();
    await act(async () => {
      btn!.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    });
    expect(onRelogin).toHaveBeenCalled();
  });

  it("does not render the affordance for a plain error", () => {
    renderView({ error_code: null }, { onRelogin: vi.fn() });
    expect(host!.textContent).not.toContain("重新登入");
  });

  it("disables the affordance while a login flow is active", () => {
    renderView({ error_code: "reauth_required" }, { onRelogin: vi.fn(), reloginBusy: true });
    const btn = Array.from(host!.querySelectorAll("button")).find((b) => b.textContent?.trim() === "重新登入");
    expect(btn!.disabled).toBe(true);
  });
});
