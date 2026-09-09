/** @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import i18n from "i18next";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { withTestUiLocale } from "./test/testUiLocale";
import type { NavigationTarget } from "./shell/navigation";

const api = vi.hoisted(() => ({ generateCard: vi.fn(), getInvestorProfile: vi.fn() }));
vi.mock("./api", async (original) => ({
  ...await original<typeof import("./api")>(), ...api,
  getStatus: vi.fn(async () => ({ status: "ok", timestamp: "2026-09-10", tools_registered: 0, tool_categories: {}, data_sources: {} })),
  getRuntimeConfig: vi.fn(async () => null),
  getCards: vi.fn(async () => ({ cards: [] })),
  getTickerState: vi.fn(async () => null),
  getPriceChange: vi.fn(async () => null),
}));
vi.mock("./shell/researchWork", () => ({
  useResearchWorkRegistry: () => ({ items: [], activeCount: 0, attentionCount: 0 }),
}));
vi.mock("./Home", () => ({ HomeView: ({ onOpenTicker }: { onOpenTicker: (ticker: string) => void }) => (
  <button onClick={() => onOpenTicker("AMD")}>Open AMD</button>
) }));
vi.mock("./Settings", () => ({ SettingsView: ({ onNavigateTarget, navigationRequest }: {
  onNavigateTarget: (target: NavigationTarget) => void;
  navigationRequest: { target: NavigationTarget };
}) => <main data-testid="settings">
  <output>{JSON.stringify(navigationRequest.target)}</output>
  <button onClick={() => onNavigateTarget({ kind: "ticker", ticker: "AMD" })}>Return AMD</button>
  <button onClick={() => onNavigateTarget({ kind: "ticker", ticker: "INTC" })}>Visit INTC</button>
</main> }));

import { App } from "./App";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let host: HTMLDivElement;
let root: ReturnType<typeof createRoot>;

beforeEach(async () => {
  vi.clearAllMocks();
  localStorage.clear();
  sessionStorage.clear();
  await i18n.changeLanguage("en");
  api.getInvestorProfile.mockResolvedValue({ profile: { enabled: true, default_stance: "aligned" } });
  api.generateCard.mockRejectedValue(Object.assign(new Error("synthetic login failure"), {
    status: 502, code: "reauth_required", path: "/analysis/card/AMD",
  }));
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
});

afterEach(() => {
  act(() => root.unmount());
  host.remove();
});

async function click(text: string) {
  const button = Array.from(host.querySelectorAll("button")).find(b => b.textContent?.includes(text));
  expect(button, `missing ${text}: ${host.textContent}`).toBeDefined();
  await act(async () => { button!.click(); });
}

async function setValue(control: HTMLInputElement | HTMLSelectElement, value: string) {
  const select = control instanceof HTMLSelectElement;
  await act(async () => {
    Object.getOwnPropertyDescriptor(select ? HTMLSelectElement.prototype : HTMLInputElement.prototype, "value")!.set!.call(control, value);
    control.dispatchEvent(new Event(select ? "change" : "input", { bubbles: true }));
  });
}

async function back() {
  await act(async () => { host.querySelector<HTMLButtonElement>(".detailpage-head button")!.click(); });
}

function question() { return host.querySelector<HTMLInputElement>(".aicard-q")!; }
function numbers() { return host.querySelectorAll<HTMLInputElement>('.aicard-adv input[type="number"]'); }
function stance() { return host.querySelector<HTMLSelectElement>(".aicard-adv select")!; }

async function startRecovery(strict: boolean) {
    await act(async () => { root.render(withTestUiLocale(strict ? <React.StrictMode><App /></React.StrictMode> : <App />)); });
    await click("Open AMD");
    await click("AI Card");
    await setValue(question(), "Keep this failed card question.");
    await click("Advanced");
    await setValue(numbers()[0]!, "33");
    await setValue(numbers()[1]!, "23");
    await setValue(stance(), "valuation_rationalist");
    await click("Generate Card");
    expect(api.generateCard).toHaveBeenCalledTimes(1);
    await click("Go to Provider Sign-in and Credentials");
    expect(host.querySelector(".aicard")).toBeNull();
    expect(host.querySelector('[data-testid="settings"]')?.textContent).toContain('"section":"providers"');
}

it.each([[false, false], [false, true], [true, false], [true, true]])(
  "retains failed inputs through actual shell unmount/return, strict=%s otherTicker=%s",
  async (strict, detour) => {
    await startRecovery(strict);
    api.getInvestorProfile.mockResolvedValue({ profile: { enabled: true, default_stance: "neutral" } });
    if (detour) {
      await click("Visit INTC");
      await click("AI Card");
      expect(question().value).toBe("");
      await back();
    }
    await click("Return AMD");
    await click("AI Card");
    expect(question().value).toBe("Keep this failed card question.");
    expect(numbers()[0]?.value).toBe("33");
    expect(numbers()[1]?.value).toBe("23");
    expect(stance()?.value).toBe("valuation_rationalist");
    expect(api.generateCard).toHaveBeenCalledTimes(1);
    expect(JSON.stringify({ localStorage, sessionStorage })).not.toContain("Keep this failed card question.");
    await click("Generate Card");
    expect(api.generateCard).toHaveBeenCalledTimes(2);
    expect(api.generateCard.mock.calls[1]?.[1]).toEqual({
      question: "Keep this failed card question.", news_days: 33, max_news: 23, assistant_stance: "valuation_rationalist",
    });
    // A consumed recovery draft must not overwrite a later independent visit.
    await back();
    await click("Return AMD");
    await click("AI Card");
    expect(question().value).toBe("");
  },
);

it.each([false, true])("blocks click and Enter until recovered profile resolves, readFailure=%s", async (failRead) => {
  await startRecovery(true);
  let resolve!: (value: unknown) => void;
  let reject!: (error: Error) => void;
  const pending = new Promise((yes, no) => { resolve = yes; reject = no; });
  api.getInvestorProfile.mockReturnValue(pending);
  await click("Return AMD");
  await click("AI Card");
  expect(question().value).toBe("Keep this failed card question.");
  const generate = host.querySelector<HTMLButtonElement>(".aicard-actions button")!;
  expect(generate.disabled).toBe(true);
  await act(async () => {
    generate.click();
    question().dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
  });
  expect(api.generateCard).toHaveBeenCalledTimes(1);
  const profile = { profile: { enabled: true, default_stance: "neutral" } };
  if (failRead) {
    await act(async () => { reject(new Error("synthetic profile read failure")); });
    expect(generate.disabled).toBe(true);
    expect(question().value).toBe("Keep this failed card question.");
    expect(api.generateCard).toHaveBeenCalledTimes(1);
    api.getInvestorProfile.mockResolvedValue(profile);
    await click("Retry");
  } else {
    await act(async () => { resolve(profile); });
  }
  expect(generate.disabled).toBe(false);
  expect(stance().value).toBe("valuation_rationalist");
  await click("Generate Card");
  expect(api.generateCard).toHaveBeenCalledTimes(2);
  expect(api.generateCard.mock.calls[1]?.[1]).toMatchObject({ assistant_stance: "valuation_rationalist" });
});
