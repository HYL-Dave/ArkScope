/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import i18n from "i18next";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { FixedTaskRuntimeSection } from "./Settings";
import type {
  FixedTaskRuntimeSettings,
  FixedTaskRuntimeTask,
} from "./api";
import type { SettingsNavigationGuardReporter } from "./settings/settingsNavigationGuard";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

beforeEach(async () => {
  await i18n.changeLanguage("zh-Hant");
});

afterEach(() => {
  if (root) act(() => root!.unmount());
  root = null;
  host?.remove();
  host = null;
});

function row(
  task: FixedTaskRuntimeTask,
  over: Partial<FixedTaskRuntimeSettings> = {},
): FixedTaskRuntimeSettings {
  return {
    task,
    model_timeout_s: 900,
    source: "db",
    db_saved: true,
    warning: null,
    ...over,
  };
}

function settings(
  synthesis: Partial<FixedTaskRuntimeSettings> = {},
  translation: Partial<FixedTaskRuntimeSettings> = {},
) {
  return {
    card_synthesis: row("card_synthesis", synthesis),
    card_translation: row("card_translation", translation),
  };
}

function render(
  current = settings(),
  onSave = vi.fn(),
  onReset = vi.fn(),
  onNavigationGuardChange?: SettingsNavigationGuardReporter,
  developerMode = false,
) {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  act(() => {
    root!.render(React.createElement(FixedTaskRuntimeSection, {
      settings: current,
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
  const element = host!.querySelector(`input[name="${name}"]`);
  if (!(element instanceof HTMLInputElement)) throw new Error(`missing ${name}`);
  return element;
}

function setInputValue(element: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
  setter?.call(element, value);
  element.dispatchEvent(new Event("input", { bubbles: true }));
}

function button(text: string): HTMLButtonElement | undefined {
  return Array.from(host!.querySelectorAll("button"))
    .find((item) => item.textContent?.includes(text));
}

describe("FixedTaskRuntimeSection", () => {
  it("renders independent values and source badges", () => {
    render(settings(
      { model_timeout_s: 1200, source: "env", db_saved: true },
      { model_timeout_s: 600, source: "default", db_saved: false },
    ));

    expect(input("card_synthesis_model_timeout_s").value).toBe("1200");
    expect(input("card_translation_model_timeout_s").value).toBe("600");
    expect(host!.textContent).toContain("AI 卡片生成 - 模型執行上限（秒）");
    expect(host!.textContent).toContain("卡片翻譯 - 模型執行上限（秒）");
    expect(host!.textContent).toContain("env 覆蓋");
    expect(host!.textContent).toContain("內建預設");
    expect(button("重設")).toBeTruthy();
  });

  it("saves both task values atomically", () => {
    const { onSave } = render();
    act(() => {
      setInputValue(input("card_synthesis_model_timeout_s"), "1500");
      setInputValue(input("card_translation_model_timeout_s"), "750");
    });
    act(() => button("儲存")!.click());

    expect(onSave).toHaveBeenCalledWith({
      tasks: {
        card_synthesis: { model_timeout_s: 1500 },
        card_translation: { model_timeout_s: 750 },
      },
    });
  });

  it.each(["59", "3601", "", "NaN", "Infinity"])(
    "disables save for invalid value %s",
    (value) => {
      render();
      act(() => {
        setInputValue(input("card_synthesis_model_timeout_s"), value);
      });
      expect(button("儲存")!.disabled).toBe(true);
    },
  );

  it("hides reset only when neither task has a saved DB row", () => {
    render(settings({ source: "default", db_saved: false }, { source: "default", db_saved: false }));
    expect(button("重設")).toBeUndefined();
  });

  it("explains effort sensitivity without changing route quality", () => {
    render();
    expect(host!.textContent).toContain("較高 effort 的模型可能需要更久");
    expect(host!.textContent).toContain("不會變更模型或 effort");
    expect(host!.textContent).toContain("以秒為單位。");
  });

  it("reports_runtime_draft_dirty_and_clears_when_settings_catch_up", () => {
    const onNavigationGuardChange = vi.fn();
    const onSave = vi.fn();
    const onReset = vi.fn();
    render(settings(), onSave, onReset, onNavigationGuardChange);

    act(() => {
      setInputValue(input("card_synthesis_model_timeout_s"), "1200");
    });
    expect(onNavigationGuardChange.mock.calls.at(-1)?.[0]).toEqual({
      dirty: true,
      busy: false,
      reason: "固定任務執行限制有未儲存的變更。",
    });

    act(() => {
      root!.render(React.createElement(FixedTaskRuntimeSection, {
        settings: settings({ model_timeout_s: 1200 }),
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

  it("renders English fixed-task limits without changing values or dirty state", async () => {
    const current = settings(
      { warning: "PLANTED SYNTHESIS RUNTIME WARNING" },
      { warning: "PLANTED TRANSLATION RUNTIME WARNING" },
    );
    const onSave = vi.fn();
    const onReset = vi.fn();
    const onNavigationGuardChange = vi.fn();
    render(current, onSave, onReset, onNavigationGuardChange);
    const synthesis = input("card_synthesis_model_timeout_s");
    const translation = input("card_translation_model_timeout_s");
    act(() => setInputValue(synthesis, "1200"));
    expect(onNavigationGuardChange.mock.calls.at(-1)?.[0].dirty).toBe(true);
    expect(host!.textContent).not.toContain("PLANTED SYNTHESIS RUNTIME WARNING");

    await act(async () => { await i18n.changeLanguage("en"); });

    expect(host!.textContent).toContain("Fixed AI Task Runtime Limits");
    expect(host!.textContent).toContain("AI Card Synthesis - model runtime limit (seconds)");
    expect(host!.textContent).toContain("Card Translation - model runtime limit (seconds)");
    expect(host!.textContent).toContain(
      "Higher-effort models may need more time. These limits only control the maximum wait; they do not change the model or effort.",
    );
    expect(input("card_synthesis_model_timeout_s")).toBe(synthesis);
    expect(input("card_translation_model_timeout_s")).toBe(translation);
    expect(synthesis.value).toBe("1200");
    expect(translation.value).toBe("900");
    expect(onNavigationGuardChange.mock.calls.at(-1)?.[0]).toEqual({
      dirty: true,
      busy: false,
      reason: "Fixed task runtime limits have unsaved changes.",
    });

    act(() => {
      root!.render(React.createElement(FixedTaskRuntimeSection, {
        settings: current,
        saving: false,
        onSave,
        onReset,
        onNavigationGuardChange,
        developerMode: true,
      }));
    });
    expect(host!.textContent).toContain("Developer diagnostics");
    expect(host!.textContent).toContain("PLANTED SYNTHESIS RUNTIME WARNING");
    expect(host!.textContent).toContain("PLANTED TRANSLATION RUNTIME WARNING");
  });
});
