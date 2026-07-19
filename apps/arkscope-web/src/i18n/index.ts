export { defaultNamespace, initializeI18n, resourceNamespaces, resources } from "./resources";
export { bootstrapUiLocale } from "./bootstrap";
export {
  DEFAULT_UI_LOCALE,
  SUPPORTED_UI_LOCALES,
  UI_LOCALE_CACHE_KEY,
  browserUiLocaleCache,
  createUiLocaleCache,
  isUiLocale,
} from "./locale";
export type { UiLocale, UiLocaleCache } from "./locale";
export { LocaleProvider, useUiLocale } from "./LocaleProvider";
export { createUiLocaleController } from "./localeController";
export type {
  UiLocaleAuthority,
  UiLocaleController,
  UiLocaleState,
} from "./localeController";
