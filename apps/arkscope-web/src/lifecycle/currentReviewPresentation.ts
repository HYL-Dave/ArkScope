import enExplore from "../i18n/resources/en/explore";
import zhExplore from "../i18n/resources/zh-Hant/explore";
import type { LifecycleLocale } from "./lifecyclePresentation";

export function currentReviewCopy(locale: LifecycleLocale) {
  return (locale === "en" ? enExplore : zhExplore).lifecycle.current;
}

export function currentSourceCheckLabel(value: string, locale: LifecycleLocale): string {
  const copy = currentReviewCopy(locale).checks;
  return copy[value as keyof typeof copy] ?? currentReviewCopy(locale).unconfirmed;
}
