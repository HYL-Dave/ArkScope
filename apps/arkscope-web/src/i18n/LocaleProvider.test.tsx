/** @vitest-environment jsdom */
import React, { StrictMode, useState } from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LocaleProvider, useUiLocale } from "./LocaleProvider";
import {
  createUiLocaleController,
  type UiLocaleResponse,
} from "./localeController";

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

async function mount(node: React.ReactNode) {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => root!.render(node));
}

afterEach(() => {
  if (root) act(() => root!.unmount());
  host?.remove();
  root = null;
  host = null;
});

function Probe() {
  const { locale, busy, errorCode, setLocale } = useUiLocale();
  return (
    <div>
      <output data-locale={locale} data-busy={String(busy)} data-error={errorCode ?? ""} />
      <button type="button" onClick={() => void setLocale("en")}>change</button>
    </div>
  );
}

function controllerWith({
  get,
  put,
}: {
  get: () => Promise<UiLocaleResponse>;
  put: (locale: "zh-Hant" | "en") => Promise<UiLocaleResponse>;
}) {
  return createUiLocaleController({
    initialLocale: "zh-Hant",
    authority: { get, put },
    applyLocale: vi.fn(),
    writeCache: vi.fn(() => true),
  });
}

describe("LocaleProvider", () => {
  it("subscribes to controller state and reconciles once under StrictMode", async () => {
    const pendingGet = deferred<UiLocaleResponse>();
    const get = vi.fn(() => pendingGet.promise);
    const controller = controllerWith({ get, put: vi.fn() });

    await mount(
      <StrictMode>
        <LocaleProvider controller={controller}>
          <Probe />
        </LocaleProvider>
      </StrictMode>,
    );
    expect(get).toHaveBeenCalledOnce();

    await act(async () => pendingGet.resolve({ locale: "en", source: "stored" }));
    expect(host!.querySelector("output")?.getAttribute("data-locale")).toBe("en");
  });

  it("exposes locale busy and stable error state without raw detail", async () => {
    const pendingPut = deferred<UiLocaleResponse>();
    const controller = controllerWith({
      get: vi.fn().mockResolvedValue({ locale: "zh-Hant", source: "default" }),
      put: vi.fn(() => pendingPut.promise),
    });
    await mount(
      <LocaleProvider controller={controller}>
        <Probe />
      </LocaleProvider>,
    );

    await act(async () => host!.querySelector("button")!.click());
    expect(host!.querySelector("output")?.getAttribute("data-locale")).toBe("en");
    expect(host!.querySelector("output")?.getAttribute("data-busy")).toBe("true");

    await act(async () => pendingPut.reject(new Error("raw secret failure")));
    const output = host!.querySelector("output")!;
    expect(output.getAttribute("data-locale")).toBe("zh-Hant");
    expect(output.getAttribute("data-busy")).toBe("false");
    expect(output.getAttribute("data-error")).toBe("write_failed");
    expect(host!.textContent).not.toContain("raw secret failure");
  });

  it("locale changes rerender labels without remounting child state", async () => {
    const pendingPut = deferred<UiLocaleResponse>();
    const controller = controllerWith({
      get: vi.fn().mockResolvedValue({ locale: "zh-Hant", source: "default" }),
      put: vi.fn(() => pendingPut.promise),
    });
    const mounts = vi.fn();

    function StatefulChild() {
      const { locale, setLocale } = useUiLocale();
      const [value, setValue] = useState("draft");
      useState(() => mounts());
      return (
        <div>
          <span>{locale}</span>
          <input value={value} onChange={(event) => setValue(event.target.value)} />
          <button type="button" onClick={() => void setLocale("en")}>change</button>
        </div>
      );
    }

    await mount(
      <LocaleProvider controller={controller}>
        <StatefulChild />
      </LocaleProvider>,
    );
    const input = host!.querySelector("input")!;
    await act(async () => {
      const setter = Object.getOwnPropertyDescriptor(
        HTMLInputElement.prototype,
        "value",
      )!.set!;
      setter.call(input, "kept value");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await act(async () => host!.querySelector("button")!.click());
    await act(async () => pendingPut.resolve({ locale: "en", source: "stored" }));

    expect(host!.querySelector("span")?.textContent).toBe("en");
    expect(host!.querySelector("input")?.value).toBe("kept value");
    expect(mounts).toHaveBeenCalledOnce();
  });
});
