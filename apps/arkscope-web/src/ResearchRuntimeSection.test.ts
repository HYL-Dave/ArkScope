/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import i18n from "i18next";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ResearchRuntimeSection } from "./Settings";
import type { ResearchRuntimeSettings } from "./api";
import type { SettingsNavigationGuardReporter } from "./settings/settingsNavigationGuard";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

beforeEach(async () => {
  await i18n.changeLanguage("zh-Hant");
});

afterEach(() => {
  if (root) {
    act(() => root!.unmount());
    root = null;
  }
  host?.remove();
  host = null;
});

const runtime = (over: Partial<ResearchRuntimeSettings> = {}): ResearchRuntimeSettings => ({
  max_tool_calls: 60,
  session_timeout_s: 900,
  per_tool_timeout_s: 45,
  source: "db",
  db_saved: true,
  warning: null,
  ...over,
});

function render(
  settings: ResearchRuntimeSettings = runtime(),
  onSave = vi.fn(),
  onReset = vi.fn(),
  onNavigationGuardChange?: SettingsNavigationGuardReporter,
  developerMode = false,
) {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  act(() => {
    root!.render(React.createElement(ResearchRuntimeSection, {
      settings,
      saving: false,
      onSave,
      onReset,
      onNavigationGuardChange,
      developerMode,
    }));
  });
  return { onSave, onReset };
}

function input(name: string): HTMLInputElement {
  const el = host!.querySelector(`input[name="${name}"]`);
  if (!(el instanceof HTMLInputElement)) throw new Error(`missing input ${name}`);
  return el;
}

function setInputValue(el: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
  setter?.call(el, value);
  el.dispatchEvent(new Event("input", { bubbles: true }));
}

describe("ResearchRuntimeSection", () => {
  it("renders current DB-backed runtime limits and the scope note", () => {
    render(runtime({ max_tool_calls: 96, session_timeout_s: 1800, per_tool_timeout_s: 75 }));
    expect(input("max_tool_calls").value).toBe("96");
    expect(input("session_timeout_s").value).toBe("1800");
    expect(input("per_tool_timeout_s").value).toBe("75");
    expect(host!.textContent).toContain("DB（已儲存）");
    expect(host!.textContent).toContain("設定 AI 研究 session 與單次工具執行限制。");
  });

  it("saves numeric values", () => {
    const { onSave } = render();
    act(() => {
      setInputValue(input("max_tool_calls"), "120");
      setInputValue(input("session_timeout_s"), "3600");
      setInputValue(input("per_tool_timeout_s"), "90");
    });
    const save = Array.from(host!.querySelectorAll("button")).find((b) => b.textContent?.includes("儲存"));
    act(() => {
      save!.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    });
    expect(onSave).toHaveBeenCalledWith({
      max_tool_calls: 120,
      session_timeout_s: 3600,
      per_tool_timeout_s: 90,
    });
  });

  it("offers reset only when DB-authoritative", () => {
    const { onReset } = render(runtime({ source: "db" }));
    const reset = Array.from(host!.querySelectorAll("button")).find((b) => b.textContent?.includes("重設"));
    expect(reset).toBeTruthy();
    act(() => {
      reset!.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    });
    expect(onReset).toHaveBeenCalledOnce();
  });

  it("reports_runtime_draft_dirty_and_clears_when_settings_catch_up", () => {
    const onNavigationGuardChange = vi.fn();
    const onSave = vi.fn();
    const onReset = vi.fn();
    render(runtime(), onSave, onReset, onNavigationGuardChange);

    act(() => {
      setInputValue(input("session_timeout_s"), "1200");
    });
    expect(onNavigationGuardChange.mock.calls.at(-1)?.[0]).toEqual({
      dirty: true,
      busy: false,
      reason: "AI 研究執行限制有未儲存的變更。",
    });

    act(() => {
      root!.render(React.createElement(ResearchRuntimeSection, {
        settings: runtime({ session_timeout_s: 1200 }),
        saving: false,
        onSave,
        onReset,
        onNavigationGuardChange,
        developerMode: false,
      }));
    });
    expect(onNavigationGuardChange.mock.calls.at(-1)?.[0]).toEqual({
      dirty: false,
      busy: false,
      reason: null,
    });
  });

  it("renders English Research limits without changing values or dirty state", async () => {
    const current = runtime({ warning: "PLANTED RESEARCH RUNTIME WARNING" });
    const onSave = vi.fn();
    const onReset = vi.fn();
    const onNavigationGuardChange = vi.fn();
    render(current, onSave, onReset, onNavigationGuardChange);
    const session = input("session_timeout_s");
    act(() => setInputValue(session, "1200"));
    expect(onNavigationGuardChange.mock.calls.at(-1)?.[0].dirty).toBe(true);
    expect(host!.textContent).not.toContain("PLANTED RESEARCH RUNTIME WARNING");

    await act(async () => { await i18n.changeLanguage("en"); });

    expect(host!.textContent).toContain("AI Research Runtime Limits");
    expect(host!.textContent).toContain("Maximum tool calls");
    expect(host!.textContent).toContain("Session timeout");
    expect(host!.textContent).toContain("Per-tool timeout");
    expect(input("session_timeout_s")).toBe(session);
    expect(input("max_tool_calls").value).toBe("60");
    expect(session.value).toBe("1200");
    expect(input("per_tool_timeout_s").value).toBe("45");
    expect(onNavigationGuardChange.mock.calls.at(-1)?.[0]).toEqual({
      dirty: true,
      busy: false,
      reason: "AI Research runtime limits have unsaved changes.",
    });

    act(() => {
      root!.render(React.createElement(ResearchRuntimeSection, {
        settings: current,
        saving: false,
        onSave,
        onReset,
        onNavigationGuardChange,
        developerMode: true,
      }));
    });
    expect(host!.textContent).toContain("Developer diagnostics");
    expect(host!.textContent).toContain("PLANTED RESEARCH RUNTIME WARNING");
  });
});
