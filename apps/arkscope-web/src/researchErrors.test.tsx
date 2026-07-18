import { describe, expect, it } from "vitest";

import { presentResearchError } from "./researchErrors";

describe("research error presentation", () => {
  it("maps reauth_required to a login action without raw primary text", () => {
    const result = presentResearchError({
      code: "reauth_required",
      detail: "raw provider response that must not become the title",
      developerMode: false,
    });

    expect(result).toMatchObject({
      code: "reauth_required",
      state: "blocked",
      title: "需要重新登入",
      actionLabel: "前往登入設定",
      target: { kind: "settings_section", section: "providers" },
      developerDetail: null,
    });
    expect(result.title).not.toContain("raw provider");
  });

  it("maps missing_credential to provider setup", () => {
    expect(presentResearchError({ code: "missing_credential" })).toMatchObject({
      state: "blocked",
      title: "尚未設定登入",
      actionLabel: "設定 Provider",
      target: { kind: "settings_section", section: "providers" },
    });
  });

  it("maps model_timeout to the adjacent runtime-limit settings action", () => {
    expect(presentResearchError({ code: "model_timeout" })).toMatchObject({
      state: "failed",
      title: "模型執行逾時",
      actionLabel: "檢查 AI 研究執行限制",
      target: { kind: "settings_section", section: "models" },
    });
  });

  it("keeps model_refusal distinct from provider_call_failed", () => {
    const refusal = presentResearchError({ code: "model_refusal" });
    const providerFailure = presentResearchError({ code: "provider_call_failed" });

    expect(refusal.title).toBe("模型拒絕回答");
    expect(providerFailure.title).toBe("Provider 呼叫失敗");
    expect(refusal.detail).not.toBe(providerFailure.detail);
  });

  it("marks tool_limit_reached as partial-preserving and offers simplify or retry", () => {
    expect(presentResearchError({ code: "tool_limit_reached" })).toMatchObject({
      state: "failed",
      title: "已達工具呼叫上限",
      actionLabel: "簡化問題或重試",
      preservePartial: true,
      target: { kind: "settings_section", section: "models" },
    });
  });

  it("maps cancelled and interrupted run codes to interrupted rather than failed", () => {
    for (const code of ["run_cancelled", "run_interrupted", "cancelled", "interrupted"]) {
      expect(presentResearchError({ code }).state).toBe("interrupted");
    }
  });

  it("shows bounded sanitized detail only in Developer Mode and never exposes credentials", () => {
    const raw = '"credential_id":"local:7" access_token=sekret refresh_token=again Bearer abc123 provider exploded';
    const normal = presentResearchError({ code: null, detail: raw, developerMode: false });
    const developer = presentResearchError({ code: null, detail: raw, developerMode: true });

    expect(normal.code).toBe("provider_call_failed");
    expect(normal.developerDetail).toBeNull();
    expect(developer.developerDetail).toContain("provider exploded");
    expect(developer.developerDetail).not.toMatch(/local:7|sekret|again|abc123|credential_id|access_token|refresh_token|Bearer/i);
  });
});
