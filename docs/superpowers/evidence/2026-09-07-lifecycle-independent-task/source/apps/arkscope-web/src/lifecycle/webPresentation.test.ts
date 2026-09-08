import { expect, it } from "vitest";
import en from "../i18n/resources/en/explore";
import zh from "../i18n/resources/zh-Hant/explore";
import { WEB_PHASES, WEB_RUN_STATES, WEB_USAGE_BASES, WEB_USAGE_COVERAGE } from "./webContract";
import { webCopy, webReason } from "./webPresentation";

it("covers every Web state in both languages without inventing a state label", () => {
  for (const locale of ["en", "zh-Hant"] as const) {
    const copy = webCopy(locale);
    expect(Object.keys(copy.status).sort()).toEqual([...WEB_RUN_STATES].sort());
    expect(WEB_PHASES.every((phase) => copy.status[phase])).toBe(true);
    expect(Object.keys(copy.auth).sort()).toEqual(["api_key", "chatgpt_oauth", "claude_code_oauth"]);
    expect(Object.keys(copy.usageBasis).sort()).toEqual([...WEB_USAGE_BASES].sort());
    expect(Object.keys(copy.usageCoverage).sort()).toEqual([...WEB_USAGE_COVERAGE].sort());
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
  expect(keys(en.lifecycle.web)).toHaveLength(148);
});
