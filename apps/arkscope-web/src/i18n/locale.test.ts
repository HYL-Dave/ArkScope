import { describe, expect, it, vi } from "vitest";

import {
  DEFAULT_UI_LOCALE,
  SUPPORTED_UI_LOCALES,
  UI_LOCALE_CACHE_KEY,
  createUiLocaleCache,
  isUiLocale,
} from "./locale";

describe("UI locale cache", () => {
  it("allowlists exactly zh-Hant and en", () => {
    expect(SUPPORTED_UI_LOCALES).toEqual(["zh-Hant", "en"]);
    expect(DEFAULT_UI_LOCALE).toBe("zh-Hant");
    expect(isUiLocale("zh-Hant")).toBe(true);
    expect(isUiLocale("en")).toBe(true);
    expect(isUiLocale("fr")).toBe(false);
    expect(isUiLocale(null)).toBe(false);
  });

  it("treats a missing cache entry as absent", () => {
    const getItem = vi.fn(() => null);
    const cache = createUiLocaleCache(() => ({ getItem, setItem: vi.fn() }));

    expect(cache.read()).toBeNull();
    expect(getItem).toHaveBeenCalledOnce();
    expect(getItem).toHaveBeenCalledWith(UI_LOCALE_CACHE_KEY);
  });

  it("ignores malformed and unknown cache values", () => {
    for (const value of ["", "  ", "fr", '"en"', "ZH-hant", "null"]) {
      const cache = createUiLocaleCache(() => ({
        getItem: () => value,
        setItem: vi.fn(),
      }));
      expect(cache.read()).toBeNull();
    }
  });

  it("ignores storage read exceptions", () => {
    const resolverFailure = createUiLocaleCache(() => {
      throw new Error("storage property blocked");
    });
    const methodFailure = createUiLocaleCache(() => ({
      getItem: () => {
        throw new Error("storage read blocked");
      },
      setItem: vi.fn(),
    }));

    expect(resolverFailure.read()).toBeNull();
    expect(methodFailure.read()).toBeNull();
  });

  it("writes only valid locale values and tolerates cache write failure", () => {
    const setItem = vi.fn();
    const cache = createUiLocaleCache(() => ({ getItem: vi.fn(), setItem }));

    expect(cache.write("en")).toBe(true);
    expect(cache.write("zh-Hant")).toBe(true);
    expect(cache.write("fr")).toBe(false);
    expect(setItem.mock.calls).toEqual([
      [UI_LOCALE_CACHE_KEY, "en"],
      [UI_LOCALE_CACHE_KEY, "zh-Hant"],
    ]);

    const resolverFailure = createUiLocaleCache(() => {
      throw new Error("storage property blocked");
    });
    const methodFailure = createUiLocaleCache(() => ({
      getItem: vi.fn(),
      setItem: () => {
        throw new Error("storage write blocked");
      },
    }));
    expect(resolverFailure.write("en")).toBe(false);
    expect(methodFailure.write("en")).toBe(false);
  });
});
