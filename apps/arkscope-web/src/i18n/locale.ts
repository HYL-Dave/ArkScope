export const SUPPORTED_UI_LOCALES = ["zh-Hant", "en"] as const;
export type UiLocale = (typeof SUPPORTED_UI_LOCALES)[number];

export const DEFAULT_UI_LOCALE: UiLocale = "zh-Hant";
export const UI_LOCALE_CACHE_KEY = "arkscope.ui.locale.v1";

export type UiLocaleStorage = Pick<Storage, "getItem" | "setItem">;
export type UiLocaleStorageResolver = () => UiLocaleStorage | null;

export interface UiLocaleCache {
  read(): UiLocale | null;
  write(value: unknown): boolean;
}

export function isUiLocale(value: unknown): value is UiLocale {
  return value === "zh-Hant" || value === "en";
}

export function createUiLocaleCache(
  resolveStorage: UiLocaleStorageResolver,
): UiLocaleCache {
  return {
    read() {
      try {
        const value = resolveStorage()?.getItem(UI_LOCALE_CACHE_KEY);
        return isUiLocale(value) ? value : null;
      } catch {
        return null;
      }
    },
    write(value) {
      if (!isUiLocale(value)) return false;
      try {
        const storage = resolveStorage();
        if (!storage) return false;
        storage.setItem(UI_LOCALE_CACHE_KEY, value);
        return true;
      } catch {
        return false;
      }
    },
  };
}

export const browserUiLocaleCache = createUiLocaleCache(() => {
  if (typeof window === "undefined") return null;
  return window.localStorage;
});
