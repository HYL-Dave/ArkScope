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
