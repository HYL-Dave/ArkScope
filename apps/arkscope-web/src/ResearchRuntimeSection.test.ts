/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ResearchRuntimeSection } from "./Settings";
import type { ResearchRuntimeSettings } from "./api";

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
    expect(host!.textContent).toContain("DB 已儲存");
    expect(host!.textContent).toContain("API-key 路徑目前只套用 max turns");
  });

  it("saves numeric values", () => {
    const { onSave } = render();
    act(() => {
      setInputValue(input("max_tool_calls"), "120");
      setInputValue(input("session_timeout_s"), "3600");
      setInputValue(input("per_tool_timeout_s"), "90");
    });
    const save = Array.from(host!.querySelectorAll("button")).find((b) => b.textContent?.includes("儲存限制"));
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
    const reset = Array.from(host!.querySelectorAll("button")).find((b) => b.textContent?.includes("重設限制"));
    expect(reset).toBeTruthy();
    act(() => {
      reset!.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    });
    expect(onReset).toHaveBeenCalledOnce();
  });
});
