import { readFileSync } from "node:fs";

import { createInstance, type TFunction } from "i18next";
import { describe, expect, it } from "vitest";

import { initializeI18n } from "./resources";

type Locale = "zh-Hant" | "en";
type ResearchT = TFunction<"research">;
type CommonT = TFunction<"common">;

interface ResearchPresentationModule {
  RESEARCH_DISCONNECT_ERROR_CODE: "run_interrupted";
  presentResearchSelection: (
    input: {
      provenance: string | null;
      authMode: string | null;
      quotaKind: "subscription" | "api" | null;
      reasonCode: string | null;
    },
    researchT: ResearchT,
    commonT: CommonT,
  ) => {
    provenanceLabel: string | null;
    authLabel: string | null;
    billingCopy: string | null;
    reasonLabel: string | null;
  };
  researchHistoryStatus: (
    status: string | null,
    t: ResearchT,
  ) => { state: string; label: string };
  researchEvidenceStatusLabel: (status: string, t: ResearchT) => string;
  researchEvidenceTokenRows: (
    usage: Record<string, number> | null,
    t: ResearchT,
  ) => Array<{ key: string; label: string; value: number }>;
  researchEvidenceTimingLabel: (field: string, t: ResearchT) => string;
  researchEmptyResponseLabel: (t: ResearchT) => string;
  researchConnectionLabel: (outcome: string, t: ResearchT) => string;
  researchProgressCopy: (
    stage: string,
    t: ResearchT,
  ) => { stageLabel: string; resultLabel: string };
  researchSuggestedPrompts: (
    t: ResearchT,
  ) => Array<{ id: string; ticker: string; text: string }>;
  presentResearchRoute: (
    input: {
      provider?: string | null;
      model?: string | null;
      effort?: string | null;
      runId?: string | null;
      errorCode?: string | null;
    },
    t: ResearchT,
  ) => {
    provider: string | null;
    providerLabel: string;
    model: string | null;
    modelLabel: string;
    effort: string | null;
    effortLabel: string;
    runId: string | null;
    errorCode: string | null;
  };
}

const modulePath = "./researchPresentation";

function loadPresentation(): Promise<ResearchPresentationModule> {
  return import(/* @vite-ignore */ modulePath) as Promise<ResearchPresentationModule>;
}

function translators(locale: Locale): { researchT: ResearchT; commonT: CommonT } {
  const instance = createInstance();
  initializeI18n(instance, locale);
  return {
    researchT: instance.getFixedT(locale, "research"),
    commonT: instance.getFixedT(locale, "common"),
  };
}

function flattenStrings(value: unknown): string[] {
  if (typeof value === "string") return [value];
  if (Array.isArray(value)) return value.flatMap(flattenStrings);
  if (value && typeof value === "object") {
    return Object.values(value as Record<string, unknown>).flatMap(flattenStrings);
  }
  return [];
}

describe("research presentation", () => {
  it("maps selection provenance and provider quota chrome in both locales", async () => {
    const presentation = await loadPresentation();
    const expected = {
      "zh-Hant": {
        provenanceLabel: "此對話上次成功路線",
        authLabel: "ChatGPT 訂閱登入",
        billingCopy: "使用訂閱額度，非 API 帳單",
        reasonLabel: "此模型不支援已選 effort",
      },
      en: {
        provenanceLabel: "Last successful route for this conversation",
        authLabel: "ChatGPT subscription sign-in",
        billingCopy: "Uses subscription quota, not API billing",
        reasonLabel: "This model does not support the selected effort",
      },
    } as const;

    for (const locale of ["zh-Hant", "en"] as const) {
      const { researchT, commonT } = translators(locale);
      expect(presentation.presentResearchSelection({
        provenance: "thread",
        authMode: "chatgpt_oauth",
        quotaKind: "subscription",
        reasonCode: "effort_not_supported",
      }, researchT, commonT)).toEqual(expected[locale]);
      expect(presentation.presentResearchSelection({
        provenance: "user",
        authMode: "api_key",
        quotaKind: "api",
        reasonCode: null,
      }, researchT, commonT)).toMatchObject({
        provenanceLabel: locale === "zh-Hant" ? "上次明確選擇" : "Last explicit selection",
        authLabel: "API key",
        billingCopy: locale === "zh-Hant"
          ? "使用 API 額度，會計入 API 帳單"
          : "Uses API quota and counts toward API billing",
      });
      expect(presentation.presentResearchSelection({
        provenance: null,
        authMode: "chatgpt_oauth",
        quotaKind: "api",
        reasonCode: null,
      }, researchT, commonT).billingCopy).toBe(
        locale === "zh-Hant"
          ? "使用 API 額度，會計入 API 帳單"
          : "Uses API quota and counts toward API billing",
      );
    }
  });

  it("maps run and history statuses without translating stable IDs", async () => {
    const presentation = await loadPresentation();
    const zh = translators("zh-Hant").researchT;
    const en = translators("en").researchT;
    expect([
      "queued", "running", "succeeded", "failed", "cancelled", "interrupted", null,
    ].map((status) => presentation.researchHistoryStatus(status, zh).label)).toEqual([
      "排程中", "執行中", "已完成", "失敗", "已取消", "已中斷", "尚無執行",
    ]);
    expect(presentation.researchHistoryStatus("succeeded", en)).toEqual({
      state: "ready",
      label: "Completed",
    });
    expect([
      "running", "complete", "recorded",
    ].map((status) => presentation.researchEvidenceStatusLabel(status, en))).toEqual([
      "Running", "Complete", "Recorded",
    ]);
  });

  it("maps Evidence token and timing labels without changing values", async () => {
    const presentation = await loadPresentation();
    const zh = translators("zh-Hant").researchT;
    const en = translators("en").researchT;
    const usage = {
      input_tokens: 101,
      cache_creation_input_tokens: 17,
      total_tokens: 303,
      provider_counter: 999,
    };
    expect(presentation.researchEvidenceTokenRows(usage, zh)).toEqual([
      { key: "input_tokens", label: "輸入 tokens", value: 101 },
      { key: "cache_creation_input_tokens", label: "快取寫入 tokens", value: 17 },
      { key: "total_tokens", label: "總 tokens", value: 303 },
    ]);
    expect(presentation.researchEvidenceTokenRows(usage, en).map((row) => row.value)).toEqual([
      101, 17, 303,
    ]);
    expect([
      "created", "started", "completed", "turn_saved", "model_elapsed",
    ].map((field) => presentation.researchEvidenceTimingLabel(field, en))).toEqual([
      "Created", "Started", "Completed", "Turn saved", "Model elapsed time",
    ]);
  });

  it("maps empty response disconnect and progress outcomes from semantic IDs", async () => {
    const presentation = await loadPresentation();
    const zh = translators("zh-Hant").researchT;
    const en = translators("en").researchT;
    expect(presentation.researchEmptyResponseLabel(zh)).toBe("（空回應）");
    expect(presentation.RESEARCH_DISCONNECT_ERROR_CODE).toBe("run_interrupted");
    expect(presentation.researchConnectionLabel(
      presentation.RESEARCH_DISCONNECT_ERROR_CODE,
      en,
    )).toBe("Connection interrupted");
    expect([
      "creating", "queued", "running", "succeeded", "failed", "interrupted", "cancelled",
    ].map((stage) => presentation.researchProgressCopy(stage, en))).toEqual([
      { stageLabel: "Creating run", resultLabel: "Shown in this conversation after creation" },
      { stageLabel: "Waiting to run", resultLabel: "Shown in this conversation after completion" },
      { stageLabel: "Running model and tools", resultLabel: "Shown in this conversation after completion" },
      { stageLabel: "Research completed", resultLabel: "Saved in this conversation" },
      { stageLabel: "Research failed", resultLabel: "Content already received remains in this conversation" },
      { stageLabel: "Research interrupted", resultLabel: "Content already received remains in this conversation" },
      { stageLabel: "Research cancelled", resultLabel: "Content already received remains in this conversation" },
    ]);
  });

  it("maps suggested prompts in both locales before they become drafts", async () => {
    const presentation = await loadPresentation();
    const zh = presentation.researchSuggestedPrompts(translators("zh-Hant").researchT);
    const en = presentation.researchSuggestedPrompts(translators("en").researchT);
    expect(zh.map(({ id, ticker }) => ({ id, ticker }))).toEqual([
      { id: "smci", ticker: "SMCI" },
      { id: "cls", ticker: "CLS" },
      { id: "mxl", ticker: "MXL" },
      { id: "nvda", ticker: "NVDA" },
    ]);
    expect(zh[0].text).toBe("最近 SA 對 SMCI 有什麼新文章和評論焦點？");
    expect(en[0].text).toBe("What new Seeking Alpha articles and comment themes are there for SMCI?");
    expect(en.map((row) => row.text)).not.toEqual(zh.map((row) => row.text));
  });

  it("keeps Provider model effort run and error identifiers original", async () => {
    const presentation = await loadPresentation();
    const facts = {
      provider: "provider-X",
      model: "model/原值-v7",
      effort: "xhigh",
      runId: "run:abc-123",
      errorCode: "future_error_code",
    };
    expect(presentation.presentResearchRoute(facts, translators("en").researchT)).toEqual({
      ...facts,
      providerLabel: "provider-X",
      modelLabel: "model/原值-v7",
      effortLabel: "xhigh",
    });
  });

  it("shows the historical default effort identifier literally", async () => {
    const presentation = await loadPresentation();

    expect(presentation.presentResearchRoute({
      provider: "openai",
      model: "gpt-5.6-luna",
      effort: "default",
    }, translators("en").researchT).effortLabel).toBe("default");
  });

  it("preserves unknown stable values instead of collapsing them", async () => {
    const presentation = await loadPresentation();
    const { researchT, commonT } = translators("en");
    expect(presentation.researchHistoryStatus("future_status", researchT).label).toBe("future_status");
    expect(presentation.researchEvidenceStatusLabel("future_completion", researchT))
      .toBe("future_completion");
    expect(presentation.researchConnectionLabel("future_connection", researchT))
      .toBe("future_connection");
    expect(presentation.presentResearchSelection({
      provenance: "future_provenance",
      authMode: "future_auth",
      quotaKind: null,
      reasonCode: "future_reason",
    }, researchT, commonT)).toEqual({
      provenanceLabel: "future_provenance",
      authLabel: "future_auth",
      billingCopy: null,
      reasonLabel: "future_reason",
    });
  });

  it("uses only static Research resource selectors", () => {
    const source = readFileSync(new URL("./researchPresentation.ts", import.meta.url), "utf8");
    expect(source).not.toMatch(/\bt\s*\(\s*["'`]/u);
    expect(source).not.toMatch(/\bt\s*\(\s*\([^)]*\)\s*=>\s*\$\s*\[/u);
    expect(source).not.toMatch(/\bt\s*\(\s*`/u);
  });

  it("renders no raw resource key for every closed presenter branch", async () => {
    const presentation = await loadPresentation();
    for (const locale of ["zh-Hant", "en"] as const) {
      const { researchT, commonT } = translators(locale);
      const outputs: unknown[] = [
        ...[null, "thread", "settings", "explicit", "user"].map((provenance) =>
          presentation.presentResearchSelection({
            provenance,
            authMode: null,
            quotaKind: null,
            reasonCode: null,
          }, researchT, commonT)),
        ...[null, "chatgpt_oauth", "claude_code_oauth", "api_key", "api_key_pool"]
          .map((authMode) => presentation.presentResearchSelection({
            provenance: null,
            authMode,
            quotaKind: authMode === null
              ? null
              : authMode === "chatgpt_oauth" || authMode === "claude_code_oauth"
                ? "subscription"
                : "api",
            reasonCode: null,
          }, researchT, commonT)),
        ...[
          null,
          "effort_not_supported",
          "runtime_unavailable",
          "missing_active_credential",
          "task_auth_mode_unsupported",
          "task_test_unsupported",
          "task_capability_missing",
          "model_not_visible",
          "model_not_in_registry",
          "discovery_unavailable",
          "provider_call_failed",
          "reauth_required",
        ].map((reasonCode) => presentation.presentResearchSelection({
          provenance: null,
          authMode: null,
          quotaKind: null,
          reasonCode,
        }, researchT, commonT)),
        ...["queued", "running", "succeeded", "failed", "cancelled", "interrupted", null]
          .map((status) => presentation.researchHistoryStatus(status, researchT)),
        ...["running", "complete", "recorded"]
          .map((status) => presentation.researchEvidenceStatusLabel(status, researchT)),
        presentation.researchEvidenceTokenRows({
          cache_creation_input_tokens: 1,
          cache_read_input_tokens: 2,
          total_input_tokens: 3,
          total_output_tokens: 4,
          last_input_tokens: 5,
          total_tokens: 6,
          input_tokens: 7,
          output_tokens: 8,
        }, researchT),
        ...["created", "started", "completed", "turn_saved", "model_elapsed"]
          .map((field) => presentation.researchEvidenceTimingLabel(field, researchT)),
        presentation.researchEmptyResponseLabel(researchT),
        presentation.researchConnectionLabel(
          presentation.RESEARCH_DISCONNECT_ERROR_CODE,
          researchT,
        ),
        ...["creating", "queued", "running", "succeeded", "failed", "interrupted", "cancelled"]
          .map((stage) => presentation.researchProgressCopy(stage, researchT)),
        presentation.researchSuggestedPrompts(researchT),
        presentation.presentResearchRoute({
          provider: "openai",
          model: "gpt-stable",
          effort: "default",
          runId: "run-stable",
          errorCode: "provider_call_failed",
        }, researchT),
      ];
      expect(flattenStrings(outputs).filter((value) => (
        /^(?:(?:research|common):)?(?:workspace|history|evidence|errors|progress|selection|connection|models)\./u
          .test(value)
      )))
        .toEqual([]);
    }
  });

  it("keeps source work and generated content outside the presenter", () => {
    const source = readFileSync(new URL("./researchPresentation.ts", import.meta.url), "utf8");
    expect(source).not.toMatch(/\b(?:question|answer|threadTitle|toolInput|toolOutput|resultPreview|contextSnapshot)\b/u);
    expect(source).not.toContain("MarkdownView");
    expect(source).not.toContain("translateGenerated");
  });
});
