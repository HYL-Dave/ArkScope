import { expect, it } from "vitest";
import en from "../i18n/resources/en/explore";
import zh from "../i18n/resources/zh-Hant/explore";
import { webCopy, webReason } from "./webPresentation";

it("keeps bilingual historical authentication and reason presentation", () => {
  for (const locale of ["en", "zh-Hant"] as const) {
    const copy = webCopy(locale);
    expect(Object.keys(copy.auth).sort()).toEqual(["api_key", "chatgpt_oauth", "claude_code_oauth"]);
    for (const code of Object.keys(copy.errors)) expect(webReason(code, locale)).not.toBe(copy.unavailable);
    expect(webReason("unknown_internal_id", locale)).toBe(copy.unavailable);
    expect(webReason(null, locale)).toBe("");
  }
});
it("requires complete bilingual Web copy with identical keys in both directions", () => {
  function keys(value: object): string[] {
    return Object.entries(value).flatMap(([key, item]) => typeof item === "string" ? [key] : keys(item).map((path) => `${key}.${path}`)).sort();
  }
  expect(keys(en.lifecycle.web)).toEqual(keys(zh.lifecycle.web));
});
