import { createInstance } from "i18next";
import { describe, expect, it, vi } from "vitest";

import { bootstrapUiLocale } from "./bootstrap";
import { createUiLocaleCache } from "./locale";

describe("synchronous locale bootstrap", () => {
  it("applies a valid cached locale synchronously before returning", () => {
    const instance = createInstance();
    const root = { lang: "" };
    const cache = createUiLocaleCache(() => ({
      getItem: () => "en",
      setItem: vi.fn(),
    }));

    const locale = bootstrapUiLocale({ instance, cache, root });

    expect(locale).toBe("en");
    expect(instance.isInitialized).toBe(true);
    expect(instance.language).toBe("en");
    expect(instance.t(($) => $.i18n.missingTranslation)).toBe(
      "This text is temporarily unavailable.",
    );
    expect(root.lang).toBe("en");
  });

  it("defaults synchronously to zh-Hant without a valid cache", () => {
    const instance = createInstance();
    const root = { lang: "en" };
    const cache = createUiLocaleCache(() => ({
      getItem: () => "not-supported",
      setItem: vi.fn(),
    }));

    expect(bootstrapUiLocale({ instance, cache, root })).toBe("zh-Hant");
    expect(instance.language).toBe("zh-Hant");
    expect(instance.t(($) => $.i18n.missingTranslation)).toBe(
      "此文字暫時無法顯示。",
    );
    expect(root.lang).toBe("zh-Hant");
  });

  it("never writes cache or fetches resources during bootstrap", () => {
    const instance = createInstance();
    const root = { lang: "" };
    const read = vi.fn(() => "en" as const);
    const write = vi.fn(() => true);
    const fetchSpy = vi.spyOn(globalThis, "fetch");

    bootstrapUiLocale({ instance, cache: { read, write }, root });

    expect(read).toHaveBeenCalledOnce();
    expect(write).not.toHaveBeenCalled();
    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });
});
