/** @vitest-environment jsdom */
import React, { useState } from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CredentialList } from "./Settings";
import type { ProviderCredential } from "./api";

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

const cred = (over: Partial<ProviderCredential>): ProviderCredential => ({
  id: "local:6",
  provider: "anthropic",
  auth_type: "claude_code_oauth",
  label: "season",
  account_label: "season_PRO",
  expires_at: null,
  source: "local",
  available: true,
  masked: null,
  active: true,
  editable: true,
  can_discover_models: false,
  can_test_models: false,
  notes: "Claude subscription",
  ...over,
});

function inputByLabel(label: string): HTMLInputElement {
  const input = Array.from(host!.querySelectorAll("input")).find((el) => el.getAttribute("aria-label") === label);
  if (!input) throw new Error(`missing input ${label}`);
  return input as HTMLInputElement;
}

function buttonByText(text: string): HTMLButtonElement {
  const button = Array.from(host!.querySelectorAll("button")).find((el) => el.textContent?.trim() === text);
  if (!button) throw new Error(`missing button ${text}`);
  return button as HTMLButtonElement;
}

function changeInput(input: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
  setter?.call(input, value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

describe("CredentialList", () => {
  it("saves alias, account label, and OAuth expiry together from one display-info action", async () => {
    const onSaveCredentialDetails = vi.fn();

    function Harness() {
      const [renames, setRenames] = useState<Record<string, string>>({});
      const [metadataDrafts, setMetadataDrafts] = useState<Record<string, { account_label?: string; expires_at?: string }>>({});
      return React.createElement(CredentialList, {
        credentials: [cred({})],
        renames,
        metadataDrafts,
        onRenameDraft: (id: string, alias: string) => setRenames((prev) => ({ ...prev, [id]: alias })),
        onMetadataDraft: (id: string, field: "account_label" | "expires_at", value: string) =>
            setMetadataDrafts((prev) => ({ ...prev, [id]: { ...prev[id], [field]: value } }))
        ,
        onSaveCredentialDetails,
        onSetActive: vi.fn(),
        onDelete: vi.fn(),
        onDiscover: vi.fn(),
        discoverLoadingId: null,
      });
    }

    host = document.createElement("div");
    document.body.append(host);
    root = createRoot(host);

    await act(async () => {
      root!.render(React.createElement(Harness));
    });

    await act(async () => {
      const alias = inputByLabel("season alias");
      changeInput(alias, "PRO");

      const account = inputByLabel("season account label");
      changeInput(account, "Claude Pro");

      const expires = inputByLabel("season expires at");
      changeInput(expires, "2027-06-22");
    });

    await act(async () => {
      buttonByText("儲存顯示資訊").dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    });

    expect(onSaveCredentialDetails).toHaveBeenCalledWith(
      "local:6",
      "PRO",
      "Claude Pro",
      "2027-06-22T00:00:00+00:00",
    );
  });
});
