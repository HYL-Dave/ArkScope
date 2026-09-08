import en from "../i18n/resources/en/investigation";
import zh from "../i18n/resources/zh-Hant/investigation";
import { webReason } from "./webPresentation";
export const investigationCopy = (locale: "en" | "zh-Hant") => locale === "en" ? en : zh;
export function investigationReason(code: string | null, locale: "en" | "zh-Hant") {
  const copy = investigationCopy(locale);
  return code && code in copy.errors ? copy.errors[code as keyof typeof copy.errors] : webReason(code, locale);
}
