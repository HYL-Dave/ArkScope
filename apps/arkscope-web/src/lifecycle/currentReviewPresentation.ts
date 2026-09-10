import enExplore from "../i18n/resources/en/explore";
import zhExplore from "../i18n/resources/zh-Hant/explore";
import type { LifecycleLocale } from "./lifecyclePresentation";

export function currentReviewCopy(locale: LifecycleLocale) {
  return (locale === "en" ? enExplore : zhExplore).lifecycle.current;
}
