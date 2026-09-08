import en from "../i18n/resources/en/explore";
import zh from "../i18n/resources/zh-Hant/explore";
import type { LifecycleLocale } from "./lifecyclePresentation";

export function webCopy(locale: LifecycleLocale) { return (locale === "en" ? en : zh).lifecycle.web; }
export function webReason(code: string | null, locale: LifecycleLocale): string {
  const copy = webCopy(locale);
  if (!code) return "";
  return copy.errors[code as keyof typeof copy.errors] ?? copy.unavailable;
}
