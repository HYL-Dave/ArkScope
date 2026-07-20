/** @vitest-environment jsdom */
import React, { type ReactNode } from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import i18n from "i18next";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApiStatus } from "../api";
import type { StatusState } from "../Dashboard";
import { ShellTopBar, type ShellDiagnostics } from "./ShellTopBar";
import {
  DEVELOPER_MODE_STORAGE_KEY,
  readDeveloperMode,
  writeDeveloperMode,
} from "./shellPreferences";
import type { NavigationTarget } from "./navigation";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

const READY_STATUS: ApiStatus = {
  status: "ok",
  timestamp: "2026-07-17T00:00:00Z",
  tools_registered: 19,
  tool_categories: {},
  data_sources: {},
};

const DIAGNOSTICS: ShellDiagnostics = {
  apiBase: "http://127.0.0.1:8420",
  toolsRegistered: 19,
  lastStatusAt: "07:31:12",
  cardModel: "openai/gpt-5.6-luna",
};

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

async function renderTopBar({
  status = { kind: "ready", status: READY_STATUS },
  developerMode = false,
  workControl,
  onNavigate = vi.fn(),
}: {
  status?: StatusState;
  developerMode?: boolean;
  workControl?: ReactNode;
  onNavigate?: (target: NavigationTarget) => void;
} = {}) {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);

  const render = async (next: {
    status?: StatusState;
    developerMode?: boolean;
    workControl?: ReactNode;
  } = {}) => {
    await act(async () => {
      root!.render(
        <ShellTopBar
          contextLabel="持倉"
          status={next.status ?? status}
          developerMode={next.developerMode ?? developerMode}
          diagnostics={DIAGNOSTICS}
          workControl={next.workControl ?? workControl}
          onNavigate={onNavigate}
        />,
      );
    });
  };

  await render();
  return { host, onNavigate, render };
}

async function click(element: Element) {
  await act(async () => {
    element.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  });
}

afterEach(() => {
  if (root) act(() => root!.unmount());
  root = null;
  host?.remove();
  host = null;
  vi.restoreAllMocks();
});

describe("Developer Mode preference", () => {
  it("defaults Developer Mode off when storage is empty or unavailable", () => {
    expect(readDeveloperMode({ getItem: () => null })).toBe(false);
    expect(readDeveloperMode({ getItem: () => { throw new Error("blocked"); } })).toBe(false);
  });

  it("round trips the versioned Developer Mode preference", () => {
    const values = new Map<string, string>();
    const storage = {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => { values.set(key, value); },
    };

    writeDeveloperMode(true, storage);
    expect(values.get(DEVELOPER_MODE_STORAGE_KEY)).toBe("enabled");
    expect(readDeveloperMode(storage)).toBe(true);

    writeDeveloperMode(false, storage);
    expect(values.get(DEVELOPER_MODE_STORAGE_KEY)).toBe("disabled");
    expect(readDeveloperMode(storage)).toBe(false);
  });

  it("treats every value except the literal enabled sentinel as off", () => {
    for (const value of [null, "", "true", "1", "ENABLED", "disabled"]) {
      expect(readDeveloperMode({ getItem: () => value })).toBe(false);
    }
    expect(readDeveloperMode({ getItem: () => "enabled" })).toBe(true);
  });
});

describe("ShellTopBar", () => {
  it("shows ArkScope current context and healthy sidecar copy in normal mode", async () => {
    const { host } = await renderTopBar();

    expect(host.querySelector("[data-testid='shell-identity']")?.textContent).toBe("ArkScope");
    expect(host.querySelector("[data-testid='shell-context']")?.textContent).toBe("持倉");
    expect(host.querySelector("[data-testid='shell-health']")?.textContent).toContain("Sidecar 已連線");
  });

  it("makes failed sidecar health an actionable System target", async () => {
    const onNavigate = vi.fn<(target: NavigationTarget) => void>();
    const { host } = await renderTopBar({
      status: { kind: "error", message: "recognizable private sidecar exception" },
      onNavigate,
    });
    const health = host.querySelector("[data-testid='shell-health'] button");

    expect(health?.textContent).toContain("Sidecar 無法連線");
    await click(health!);
    expect(onNavigate).toHaveBeenCalledWith({ kind: "view", view: "System" });
  });

  it("does not show apiBase tool count poll time or model diagnostics in normal mode", async () => {
    const { host } = await renderTopBar();

    expect(host.textContent).not.toContain(DIAGNOSTICS.apiBase);
    expect(host.textContent).not.toContain("19 tools");
    expect(host.textContent).not.toContain(DIAGNOSTICS.lastStatusAt);
    expect(host.textContent).not.toContain(DIAGNOSTICS.cardModel);
  });

  it("omits the background-work control when both counts are zero", async () => {
    const { host } = await renderTopBar();

    expect(host.querySelector("[data-testid='shell-work-slot']")).toBeNull();
  });

  it("shows a single work control when active or attention count is nonzero", async () => {
    const { host } = await renderTopBar({
      workControl: <button type="button">執行中 1 · 待查看 2</button>,
    });

    const slot = host.querySelector("[data-testid='shell-work-slot']");
    expect(slot).not.toBeNull();
    expect(slot?.querySelectorAll("button")).toHaveLength(1);
  });

  it("shows the secondary diagnostics row only in Developer Mode", async () => {
    const { host, render } = await renderTopBar();
    expect(host.querySelector("[data-testid='shell-diagnostics']")).toBeNull();

    await render({ developerMode: true });
    expect(host.querySelector("[data-testid='shell-diagnostics']")).not.toBeNull();
  });

  it("keeps developer diagnostics sanitized and labelled as diagnostics", async () => {
    const { host } = await renderTopBar({
      status: { kind: "error", message: "recognizable private sidecar exception" },
      developerMode: true,
    });
    const diagnostics = host.querySelector("[data-testid='shell-diagnostics']");

    expect(diagnostics?.getAttribute("aria-label")).toBe("Developer diagnostics");
    expect(diagnostics?.textContent).toContain(`API ${DIAGNOSTICS.apiBase}`);
    expect(diagnostics?.textContent).toContain("Tools 19");
    expect(diagnostics?.textContent).toContain(`Last status ${DIAGNOSTICS.lastStatusAt}`);
    expect(diagnostics?.textContent).toContain(`Card model ${DIAGNOSTICS.cardModel}`);
    expect(host.textContent).not.toContain("recognizable private sidecar exception");
  });

  it("keeps identity and context in stable named slots when status copy changes", async () => {
    const { host, render } = await renderTopBar();
    const identity = host.querySelector("[data-testid='shell-identity']");
    const context = host.querySelector("[data-testid='shell-context']");
    const health = host.querySelector("[data-testid='shell-health']");

    await render({ status: { kind: "error", message: "offline" } });

    expect(host.querySelector("[data-testid='shell-identity']")).toBe(identity);
    expect(host.querySelector("[data-testid='shell-context']")).toBe(context);
    expect(host.querySelector("[data-testid='shell-health']")).toBe(health);
  });

  it("renders English health and developer diagnostic labels without exposing raw errors", async () => {
    await act(async () => { await i18n.changeLanguage("en"); });
    const { host } = await renderTopBar({
      status: { kind: "error", message: "recognizable private sidecar exception" },
      developerMode: true,
    });
    const diagnostics = host.querySelector("[data-testid='shell-diagnostics']");

    expect(host.querySelector("[data-testid='shell-health']")?.textContent)
      .toContain("Sidecar unavailable");
    expect(diagnostics?.getAttribute("aria-label")).toBe("Developer diagnostics");
    expect(diagnostics?.textContent).toContain(`API ${DIAGNOSTICS.apiBase}`);
    expect(diagnostics?.textContent).toContain("Tools 19");
    expect(diagnostics?.textContent).toContain(`Last status ${DIAGNOSTICS.lastStatusAt}`);
    expect(diagnostics?.textContent).toContain(`Card model ${DIAGNOSTICS.cardModel}`);
    expect(host.textContent).not.toContain("recognizable private sidecar exception");
  });
});
