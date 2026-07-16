/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ShellNavigation } from "./ShellNavigation";
import type { NavigationTarget, ShellView } from "./navigation";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

async function renderNavigation({
  currentView = "Home",
  onNavigate = vi.fn(),
  onAfterNavigate = vi.fn(),
}: {
  currentView?: ShellView;
  onNavigate?: (target: NavigationTarget) => void;
  onAfterNavigate?: () => void;
} = {}) {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(
      <ShellNavigation
        currentView={currentView}
        onNavigate={onNavigate}
        onAfterNavigate={onAfterNavigate}
      />,
    );
  });
  return { host, onNavigate, onAfterNavigate };
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

describe("ShellNavigation", () => {
  it("renders four noninteractive workflow group labels", async () => {
    const { host } = await renderNavigation();
    const groups = Array.from(host.querySelectorAll("[data-shell-nav-group]"));

    expect(groups.map((group) => group.textContent)).toEqual(["探索", "研究", "追蹤", "系統"]);
    expect(groups.every((group) => !["BUTTON", "A"].includes(group.tagName))).toBe(true);
    expect(groups.every((group) => group.getAttribute("tabindex") === null)).toBe(true);
  });

  it("renders eight shipped destinations in canonical order", async () => {
    const { host } = await renderNavigation();

    expect(Array.from(host.querySelectorAll("button"), (button) => button.textContent?.trim())).toEqual([
      "工作台",
      "自選股",
      "全部標的",
      "新聞·事件",
      "AI 研究",
      "持倉",
      "System / Health",
      "設定",
    ]);
  });

  it("marks only the current view with aria-current page", async () => {
    const { host } = await renderNavigation({ currentView: "Holdings" });
    const current = Array.from(host.querySelectorAll("[aria-current='page']"));

    expect(current).toHaveLength(1);
    expect(current[0]?.textContent).toContain("持倉");
  });

  it("dispatches an exact view target and closes an overlay copy", async () => {
    const onNavigate = vi.fn<(target: NavigationTarget) => void>();
    const onAfterNavigate = vi.fn<() => void>();
    const { host } = await renderNavigation({ onNavigate, onAfterNavigate });
    const settings = Array.from(host.querySelectorAll("button"))
      .find((button) => button.textContent?.includes("設定"));

    expect(settings).toBeDefined();
    await click(settings!);
    expect(onNavigate).toHaveBeenCalledWith({ kind: "view", view: "Settings" });
    expect(onAfterNavigate).toHaveBeenCalledOnce();
  });

  it("renders one aria-hidden Lucide icon per destination with no literal svg source", async () => {
    const { host } = await renderNavigation();
    const source = readFileSync(
      resolve(process.cwd(), "src/shell/ShellNavigation.tsx"),
      "utf8",
    );

    expect(host.querySelectorAll("button svg[aria-hidden='true']")).toHaveLength(8);
    expect(source).not.toMatch(/<svg\b/i);
  });

  it("contains no disabled Notes or Alerts controls", async () => {
    const { host } = await renderNavigation();

    expect(host.textContent).not.toMatch(/研究筆記|告警|Notes|Alerts/);
    expect(host.querySelectorAll("button:disabled")).toHaveLength(0);
  });
});
