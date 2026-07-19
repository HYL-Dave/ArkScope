import type { i18n } from "i18next";

import { DEFAULT_UI_LOCALE, type UiLocale, type UiLocaleCache } from "./locale";
import { initializeI18n } from "./resources";

export interface UiLocaleRoot {
  lang: string;
}

export interface BootstrapUiLocaleOptions {
  instance: i18n;
  cache: UiLocaleCache;
  root: UiLocaleRoot;
}

export function bootstrapUiLocale({
  instance,
  cache,
  root,
}: BootstrapUiLocaleOptions): UiLocale {
  const locale = cache.read() ?? DEFAULT_UI_LOCALE;
  initializeI18n(instance, locale);
  root.lang = locale;
  return locale;
}
