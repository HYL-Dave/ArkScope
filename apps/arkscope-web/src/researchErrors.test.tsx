import { createInstance, type TFunction } from "i18next";
import { describe, expect, it } from "vitest";

import { initializeI18n } from "./i18n/resources";
import { presentResearchError } from "./researchErrors";

function researchT(locale: "zh-Hant" | "en"): TFunction<"research"> {
  const instance = createInstance();
  initializeI18n(instance, locale);
  return instance.getFixedT(locale, "research");
}

describe("research error presentation", () => {
  it("maps reauth_required to a login action without raw primary text", () => {
    const result = presentResearchError({
      code: "reauth_required",
      detail: "raw provider response that must not become the title",
      developerMode: false,
    }, researchT("zh-Hant"));

    expect(result).toMatchObject({
      code: "reauth_required",
      state: "blocked",
      title: "需要重新登入",
      actionLabel: "前往登入設定",
      target: { kind: "settings_section", section: "providers" },
      developerDetail: null,
    });
    expect(result.title).not.toContain("raw provider");
    expect(presentResearchError({ code: "reauth_required" }, researchT("en"))).toMatchObject({
      title: "Sign-in required",
      detail: "The current sign-in has expired. Sign in again before running Research.",
      actionLabel: "Go to sign-in settings",
    });
  });

  it("maps missing_credential to provider setup", () => {
    expect(presentResearchError({ code: "missing_credential" }, researchT("zh-Hant"))).toMatchObject({
      state: "blocked",
      title: "尚未設定登入",
      actionLabel: "設定 Provider",
      target: { kind: "settings_section", section: "providers" },
    });
  });

  it("maps model_timeout to the adjacent runtime-limit settings action", () => {
    expect(presentResearchError({ code: "model_timeout" }, researchT("zh-Hant"))).toMatchObject({
      state: "failed",
      title: "模型執行逾時",
      actionLabel: "檢查 AI 研究執行限制",
      target: { kind: "settings_section", section: "models" },
    });
  });

  it("keeps model_refusal distinct from provider_call_failed", () => {
    const refusal = presentResearchError({ code: "model_refusal" }, researchT("zh-Hant"));
    const providerFailure = presentResearchError({ code: "provider_call_failed" }, researchT("zh-Hant"));

    expect(refusal.title).toBe("模型拒絕回答");
    expect(providerFailure.title).toBe("Provider 呼叫失敗");
    expect(refusal.detail).not.toBe(providerFailure.detail);
  });

  it("keeps maintenance admission distinct from a dispatched provider failure", () => {
    for (const locale of ["en", "zh-Hant"] as const) {
      const result = presentResearchError({ code: "sec_research_operation_busy" }, researchT(locale));
      expect(result).toMatchObject({
        code: "sec_research_operation_busy", state: "blocked", target: null, actionLabel: null,
        preservePartial: false, developerDetail: null,
      });
      expect(result.title).toBe(locale === "en" ? "Research maintenance in progress" : "研究資料維護中");
      expect(result.detail).toBe(locale === "en"
        ? "Research was not started. Try again after maintenance finishes."
        : "研究尚未開始。請等維護完成後重試。");
    }
  });

  it.each([
    ["capture_platform_unsupported", "Research protection unsupported on this platform", "此平台不支援研究保護"],
    ["capture_path_unsafe", "Research storage path is unsafe", "研究儲存路徑不安全"],
    ["sec_research_operation_invalid", "Research protection configuration is invalid", "研究保護設定無效"],
    ["storage_space_insufficient", "Insufficient space for Research protection", "研究保護所需空間不足"],
    ["capture_store_write_failed", "Research protection unavailable", "研究保護無法使用"],
  ])("preserves the closed admission code %s without claiming maintenance or dispatch", (code, english, chinese) => {
    for (const locale of ["en", "zh-Hant"] as const) {
      const result = presentResearchError({ code }, researchT(locale));
      expect(result).toMatchObject({
        code, state: "blocked", target: null, actionLabel: null, preservePartial: false, developerDetail: null,
      });
      expect(result.title).toBe(locale === "en" ? english : chinese);
      expect(result.detail).toContain(locale === "en" ? "Research was not started." : "研究尚未開始。");
      expect(result.detail).not.toMatch(/maintenance|Provider|維護/);
    }
  });

  it("marks tool_limit_reached as partial-preserving and offers simplify or retry", () => {
    expect(presentResearchError({ code: "tool_limit_reached" }, researchT("zh-Hant"))).toMatchObject({
      state: "failed",
      title: "已達工具呼叫上限",
      actionLabel: "簡化問題或重試",
      preservePartial: true,
      target: { kind: "settings_section", section: "models" },
    });
  });

  it("maps cancelled and interrupted run codes to interrupted rather than failed", () => {
    for (const code of ["run_cancelled", "run_interrupted", "cancelled", "interrupted"]) {
      expect(presentResearchError({ code }, researchT("zh-Hant")).state).toBe("interrupted");
    }
  });

  it("shows bounded sanitized detail only in Developer Mode and never exposes credentials", () => {
    const raw = '"credential_id":"local:7" access_token=sekret refresh_token=again Bearer abc123 provider exploded';
    const t = researchT("zh-Hant");
    const normal = presentResearchError({ code: null, detail: raw, developerMode: false }, t);
    const developer = presentResearchError({ code: null, detail: raw, developerMode: true }, t);

    expect(normal.code).toBe("provider_call_failed");
    expect(normal.developerDetail).toBeNull();
    expect(developer.developerDetail).toContain("provider exploded");
    expect(developer.developerDetail).not.toMatch(/local:7|sekret|again|abc123|credential_id|access_token|refresh_token|Bearer/i);
  });
});
