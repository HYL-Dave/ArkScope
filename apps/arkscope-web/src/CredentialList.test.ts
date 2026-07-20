/** @vitest-environment jsdom */
import React, { useState } from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import i18n from "i18next";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CredentialList } from "./Settings";
import type { ProviderCredential } from "./api";

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

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

function renderCredentialList(
  credentials: ProviderCredential[],
  extra: Record<string, unknown> = {},
) {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  act(() => {
    root!.render(React.createElement(CredentialList, {
      credentials,
      renames: {},
      metadataDrafts: {},
      onRenameDraft: vi.fn(),
      onMetadataDraft: vi.fn(),
      onSaveCredentialDetails: vi.fn(),
      onSetActive: vi.fn(),
      onDelete: vi.fn(),
      onDiscover: vi.fn(),
      discoverLoadingId: null,
      ...extra,
    }));
  });
}

async function settleProbe() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

const plantedProbe = {
  passed: false,
  probes: [{
    name: "P2b: ChatGPT backend returns a function-call output item",
    passed: false,
    expected: "planted-probe-expected",
    observed: "planted-probe-observed",
    error: "planted-probe-error",
  }],
};

describe("CredentialList localization", () => {
  it("renders English credential actions while preserving aliases and masked values", async () => {
    await i18n.changeLanguage("en");
    renderCredentialList([cred({
      label: "planted-alias-value",
      masked: "sk-ant-...MASKED",
      active: false,
      can_discover_models: true,
    })]);

    expect(host!.textContent).toContain("planted-alias-value");
    expect(host!.textContent).toContain("sk-ant-...MASKED");
    expect(host!.textContent).toContain("Set active");
    expect(host!.textContent).toContain("Save display information");
    expect(host!.textContent).toContain("View candidate models");
    expect(host!.textContent).toContain("Delete");
  });

  it("hides probe expected observed and error fields in normal mode", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => plantedProbe,
    }));
    renderCredentialList([cred({})], { developerMode: false });
    await act(async () => { buttonByText("測試 Claude setup-token").click(); });
    await settleProbe();

    expect(host!.textContent).toContain("OAuth 驗證未通過");
    expect(host!.textContent).not.toContain("planted-probe-expected");
    expect(host!.textContent).not.toContain("planted-probe-observed");
    expect(host!.textContent).not.toContain("planted-probe-error");
  });

  it("shows planted probe diagnostics only in Developer Mode", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => plantedProbe,
    }));
    renderCredentialList([cred({})], { developerMode: true });
    await act(async () => { buttonByText("測試 Claude setup-token").click(); });
    await settleProbe();

    expect(host!.textContent).toContain("開發者診斷");
    expect(host!.textContent).toContain("預期");
    expect(host!.textContent).toContain("planted-probe-expected");
    expect(host!.textContent).toContain("觀察結果");
    expect(host!.textContent).toContain("planted-probe-observed");
    expect(host!.textContent).toContain("錯誤");
    expect(host!.textContent).toContain("planted-probe-error");
    expect(host!.querySelector(".developer-diagnostics")?.getAttribute("aria-live")).toBeNull();
  });
});

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
      const alias = inputByLabel("season · 新增 API key alias");
      changeInput(alias, "PRO");

      const account = inputByLabel("season · 帳號／用途標籤（可留空）");
      changeInput(account, "Claude Pro");

      const expires = inputByLabel("season · 到期日（可留空）");
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

  it("marks the alias edit field as required so it is not misread as clearable like the optional metadata", async () => {
    host = document.createElement("div");
    document.body.append(host);
    root = createRoot(host);

    await act(async () => {
      root!.render(
        React.createElement(CredentialList, {
          credentials: [cred({})],
          renames: {},
          metadataDrafts: {},
          onRenameDraft: vi.fn(),
          onMetadataDraft: vi.fn(),
          onSaveCredentialDetails: vi.fn(),
          onSetActive: vi.fn(),
          onDelete: vi.fn(),
          onDiscover: vi.fn(),
          discoverLoadingId: null,
        }),
      );
    });

    // alias is NOT NULL + the row's primary display name → blanking it is a no-op that keeps
    // the original (unlike the neighbouring account-label/expiry fields, which DO clear on save).
    // So the edit field must not borrow the add/import flow's "可留空" framing.
    expect(inputByLabel("season · 新增 API key alias").required).toBe(true);
    expect(inputByLabel("season · 新增 API key alias").placeholder).toBe("新增 API key alias");
  });

  it("opens_credential_delete_confirmation_and_cancel_restores_trigger_focus", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    const onDelete = vi.fn();
    host = document.createElement("div");
    document.body.append(host);
    root = createRoot(host);
    await act(async () => {
      root!.render(React.createElement(CredentialList, {
        credentials: [cred({})],
        renames: {},
        metadataDrafts: {},
        onRenameDraft: vi.fn(),
        onMetadataDraft: vi.fn(),
        onSaveCredentialDetails: vi.fn(),
        onSetActive: vi.fn(),
        onDelete,
        onDiscover: vi.fn(),
        discoverLoadingId: null,
      }));
    });

    const deleteTrigger = buttonByText("刪除");
    deleteTrigger.focus();
    await act(async () => {
      deleteTrigger.click();
    });
    const dialog = document.querySelector<HTMLElement>('[role="dialog"]');
    expect(dialog?.textContent).toContain("刪除 Credential？");
    expect(dialog?.textContent).toContain("season");
    expect(onDelete).not.toHaveBeenCalled();
    const cancelButton = Array.from(dialog?.querySelectorAll("button") ?? [])
      .find((button) => button.textContent?.trim() === "取消") as HTMLButtonElement | undefined;
    if (!cancelButton) throw new Error("missing credential-delete cancel button");
    await act(async () => {
      cancelButton.click();
    });
    expect(onDelete).not.toHaveBeenCalled();
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    expect(document.activeElement).toBe(deleteTrigger);
  });

  it("confirms_only_the_selected_credential_delete", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const onDelete = vi.fn();
    host = document.createElement("div");
    document.body.append(host);
    root = createRoot(host);
    await act(async () => {
      root!.render(React.createElement(CredentialList, {
        credentials: [
          cred({ id: "local:6", label: "season" }),
          cred({ id: "local:8", label: "backup", active: false }),
        ],
        renames: {},
        metadataDrafts: {},
        onRenameDraft: vi.fn(),
        onMetadataDraft: vi.fn(),
        onSaveCredentialDetails: vi.fn(),
        onSetActive: vi.fn(),
        onDelete,
        onDiscover: vi.fn(),
        discoverLoadingId: null,
      }));
    });

    const backupRow = Array.from(host!.querySelectorAll<HTMLElement>(".credential-row"))
      .find((row) => row.querySelector("strong")?.textContent === "backup");
    const deleteTrigger = Array.from(backupRow?.querySelectorAll("button") ?? [])
      .find((button) => button.textContent?.trim() === "刪除") as HTMLButtonElement | undefined;
    if (!deleteTrigger) throw new Error("missing backup credential delete button");
    await act(async () => {
      deleteTrigger.click();
    });
    expect(onDelete).not.toHaveBeenCalled();
    const dialog = document.querySelector<HTMLElement>('[role="dialog"]');
    expect(dialog?.textContent).toContain("backup");
    expect(dialog?.textContent).not.toContain("local:8");
    const confirmButton = Array.from(dialog?.querySelectorAll("button") ?? [])
      .find((button) => button.textContent?.trim() === "刪除") as HTMLButtonElement | undefined;
    if (!confirmButton) throw new Error("missing credential-delete confirm button");
    await act(async () => {
      confirmButton.click();
    });
    expect(onDelete).toHaveBeenCalledTimes(1);
    expect(onDelete).toHaveBeenCalledWith("local:8");
  });

  it("reports_probe_as_navigation_blocking_until_settled", async () => {
    const response = deferred<{ ok: boolean; status: number; json: () => Promise<unknown> }>();
    vi.stubGlobal("fetch", vi.fn(() => response.promise));
    const onNavigationGuardChange = vi.fn();
    host = document.createElement("div");
    document.body.append(host);
    root = createRoot(host);
    await act(async () => {
      root!.render(React.createElement(CredentialList, {
        credentials: [cred({})],
        renames: {},
        metadataDrafts: {},
        onRenameDraft: vi.fn(),
        onMetadataDraft: vi.fn(),
        onSaveCredentialDetails: vi.fn(),
        onSetActive: vi.fn(),
        onDelete: vi.fn(),
        onDiscover: vi.fn(),
        discoverLoadingId: null,
        onNavigationGuardChange,
      }));
    });

    await act(async () => { buttonByText("測試 Claude setup-token").click(); });
    expect(onNavigationGuardChange.mock.calls.at(-1)?.[0]).toEqual({
      dirty: false,
      busy: true,
      reason: "Provider 登入或 Credential 更新正在進行。",
    });
    response.resolve({
      ok: true,
      status: 200,
      json: async () => ({ passed: true, probes: [] }),
    });
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    expect(onNavigationGuardChange.mock.calls.at(-1)?.[0]).toEqual({
      dirty: false,
      busy: false,
      reason: null,
    });
  });
});

describe("CredentialList re-login (S3 credential lifecycle)", () => {
  const CHATGPT: Partial<ProviderCredential> = {
    id: "local:7", provider: "openai", auth_type: "chatgpt_oauth", label: "Sub",
  };

  function renderList(over: Partial<ProviderCredential>, extra: Record<string, unknown> = {}) {
    host = document.createElement("div");
    document.body.append(host);
    root = createRoot(host);
    act(() => {
      root!.render(
        React.createElement(CredentialList, {
          credentials: [cred(over)],
          renames: {},
          metadataDrafts: {},
          onRenameDraft: vi.fn(),
          onMetadataDraft: vi.fn(),
          onSaveCredentialDetails: vi.fn(),
          onSetActive: vi.fn(),
          onDelete: vi.fn(),
          onDiscover: vi.fn(),
          discoverLoadingId: null,
          ...extra,
        }),
      );
    });
  }

  it("renders 重新登入 on chatgpt_oauth rows and passes the row id", async () => {
    const onRelogin = vi.fn();
    renderList(CHATGPT, { onRelogin });
    await act(async () => {
      buttonByText("重新登入").dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    });
    expect(onRelogin).toHaveBeenCalledWith("local:7");
  });

  it("does not render 重新登入 for api_key or claude_code_oauth rows (scope ruling)", () => {
    const onRelogin = vi.fn();
    renderList({ id: "local:3", provider: "openai", auth_type: "api_key", label: "K" }, { onRelogin });
    expect(host!.textContent).not.toContain("重新登入");
    act(() => root!.unmount());
    root = null;
    host!.remove();
    renderList({}, { onRelogin }); // default fixture row = anthropic claude_code_oauth
    expect(host!.textContent).not.toContain("重新登入");
  });

  it("disables 重新登入 while a login flow is active", () => {
    renderList(CHATGPT, { onRelogin: vi.fn(), reloginBusy: true });
    expect(buttonByText("重新登入").disabled).toBe(true);
  });

  it("renders no 重新登入 without an onRelogin handler (old render sites stay valid)", () => {
    renderList(CHATGPT);
    expect(host!.textContent).not.toContain("重新登入");
  });
});
