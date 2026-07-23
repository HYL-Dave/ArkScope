import { readFileSync } from "node:fs";

import { createInstance, type TFunction } from "i18next";
import { describe, expect, it } from "vitest";

import type { AssistantStance } from "../../api";
import { initializeI18n } from "../../i18n/resources";

type SettingsT = TFunction<"settings">;
type CommonT = TFunction<"common">;

interface TopicDisplay {
  id: string;
  label: string;
  description: string | null;
  developerDiagnostic: string | null;
}

interface FieldDisplay {
  field: string;
  label: string;
}

interface DisplayModule {
  CALIBRATION_TOPIC_IDS: readonly string[];
  CALIBRATION_PROMPT_IDS: readonly string[];
  PROPOSABLE_INVESTOR_PROFILE_FIELDS: readonly string[];
  calibrationTopicDisplay: (id: string, t: SettingsT) => TopicDisplay;
  calibrationPromptText: (
    promptId: string | null,
    canonicalContent: string,
    t: SettingsT,
  ) => string;
  investorProfileFieldLabel: (field: string, t: SettingsT) => string;
  investorProfileFieldValue: (
    field: string,
    value: unknown,
    settingsT: SettingsT,
    commonT: CommonT,
  ) => string;
  assistantStanceEffect: (stance: AssistantStance, t: SettingsT) => string;
  orderedCalibrationTopicDisplays: (
    topicIds: readonly string[],
    t: SettingsT,
  ) => TopicDisplay[];
  orderedInvestorProfileFieldDisplays: (
    fields: readonly string[],
    t: SettingsT,
  ) => FieldDisplay[];
}

const moduleUrl = new URL("./investorProfileDisplay.ts", import.meta.url).href;

async function loadDisplay(): Promise<DisplayModule> {
  return import(/* @vite-ignore */ moduleUrl) as Promise<DisplayModule>;
}

function settingsT(locale: "zh-Hant" | "en"): SettingsT {
  const instance = createInstance();
  initializeI18n(instance, locale);
  return instance.getFixedT(locale, "settings");
}

function commonT(locale: "zh-Hant" | "en"): CommonT {
  const instance = createInstance();
  initializeI18n(instance, locale);
  return instance.getFixedT(locale, "common");
}

describe("investor profile display mappings", () => {
  it("pins exact known topic and prompt ID sets", async () => {
    const display = await loadDisplay();

    expect(display.CALIBRATION_TOPIC_IDS).toEqual([
      "loss_response",
      "financial_capacity",
      "time_horizon",
      "single_position_limit",
      "risk_avoidances",
      "behavioral_patterns",
      "investment_approach",
      "assistant_style",
    ]);
    expect(display.CALIBRATION_PROMPT_IDS).toEqual(["loss_response.opening.v1"]);

    const source = readFileSync(new URL("./investorProfileDisplay.ts", import.meta.url), "utf8");
    const translationCalls = source.match(/\bt\(/g) ?? [];
    const selectorCalls = source.match(/\bt\(\(\$\) => \$\./g) ?? [];
    expect(selectorCalls).toHaveLength(translationCalls.length);
    expect(source).not.toMatch(/\bt\([^)]*(?:\+|`|\[)/);
  });

  it("maps all topic labels and descriptions in both locales", async () => {
    const display = await loadDisplay();
    const expected = {
      en: [
        ["How you respond to losses", "How you typically react when an important holding falls."],
        ["What your finances allow", "The investment risk your finances can absorb."],
        ["How long you invest", "The time periods your investments are intended to span."],
        ["Single-position limit", "How much of the portfolio one position may represent."],
        ["Risks you avoid", "Risk types and situations you prefer not to take."],
        ["Behavioral patterns to watch", "Patterns that may affect decisions under pressure."],
        ["Research approaches you prefer", "The research styles and signals you prefer."],
        ["How you want AI to work with you", "The stance the assistant should take when helping you."],
      ],
      "zh-Hant": [
        ["遇到虧損時怎麼做", "了解重要持股下跌時，你通常如何應對。"],
        ["資金能承受多少", "了解你的財務狀況能承受多少投資風險。"],
        ["預計持有多久", "了解投資預計涵蓋的持有期間。"],
        ["單一持股上限", "了解單一持股最多可占投資組合多少。"],
        ["不碰哪些風險", "了解你偏好避開的風險類型與情境。"],
        ["容易受哪些行為影響", "了解壓力下可能影響決策的行為模式。"],
        ["偏好的研究方法", "了解你偏好的研究方法與訊號。"],
        ["希望 AI 如何配合", "了解你希望助手用什麼立場協助你。"],
      ],
    } as const;

    for (const locale of ["zh-Hant", "en"] as const) {
      const t = settingsT(locale);
      expect(display.CALIBRATION_TOPIC_IDS.map((id) => {
        const topic = display.calibrationTopicDisplay(id, t);
        return [topic.label, topic.description];
      })).toEqual(expected[locale]);
    }
  });

  it("uses generic topic copy while keeping an unknown raw ID diagnostic-only", async () => {
    const display = await loadDisplay();

    for (const [locale, label] of [["en", "Other topic"], ["zh-Hant", "其他主題"]] as const) {
      const topic = display.calibrationTopicDisplay("future_private_topic", settingsT(locale));
      expect({ label: topic.label, description: topic.description }).toEqual({
        label,
        description: null,
      });
      expect(`${topic.label}${topic.description ?? ""}`).not.toContain("future_private_topic");
      expect(topic.developerDiagnostic).toBe("future_private_topic");
    }
  });

  it("relocalizes a known opening prompt and falls back to canonical unknown copy", async () => {
    const display = await loadDisplay();
    const canonical = "Suppose an important holding falls 18% over a short period while its long-term thesis is not clearly broken. What would you usually do?";

    expect(display.calibrationPromptText("loss_response.opening.v1", canonical, settingsT("en")))
      .toBe(canonical);
    expect(display.calibrationPromptText("loss_response.opening.v1", canonical, settingsT("zh-Hant")))
      .toBe("假設一個重要持股在短期內下跌 18%，但長期 thesis 尚未明確失效，你通常會怎麼處理？");
    expect(display.calibrationPromptText("future.opening.v2", "Canonical source copy", settingsT("zh-Hant")))
      .toBe("Canonical source copy");
  });

  it("maps all proposable field labels without owning topic field policy", async () => {
    const display = await loadDisplay();
    expect(display.PROPOSABLE_INVESTOR_PROFILE_FIELDS).toEqual([
      "risk_appetite",
      "drawdown_tolerance_pct",
      "risk_capacity",
      "holding_horizon",
      "concentration_limit_pct",
      "avoidances",
      "behavioral_flags",
      "primary_preset",
      "preferred_edge",
      "default_stance",
    ]);

    const expected = {
      en: [
        "Risk appetite (1-10)",
        "Tolerable drawdown %",
        "Risk capacity (1-10)",
        "Holding horizon",
        "Single-position limit %",
        "Avoidances (comma-separated)",
        "Behavioral tendencies (for calibration, not diagnosis)",
        "Investment style",
        "Preferred edges",
        "Default assistant stance",
      ],
      "zh-Hant": [
        "風險意願(1-10)",
        "可承受回撤 %",
        "風險承受能力(1-10)",
        "持有週期",
        "單一部位上限 %",
        "想避開的(逗號分隔)",
        "行為傾向(供助手校準,非診斷)",
        "投資風格",
        "偏好優勢",
        "預設助手立場",
      ],
    } as const;

    for (const locale of ["zh-Hant", "en"] as const) {
      expect(display.PROPOSABLE_INVESTOR_PROFILE_FIELDS.map(
        (field) => display.investorProfileFieldLabel(field, settingsT(locale)),
      )).toEqual(expected[locale]);
    }

    const source = readFileSync(new URL("./investorProfileDisplay.ts", import.meta.url), "utf8");
    expect(source).not.toMatch(/TOPIC_FIELDS|FIELDS_BY_TOPIC|topicFields|fieldsForTopic/);
  });

  it("preserves source list and numeric values while localizing semantic IDs", async () => {
    const display = await loadDisplay();

    for (const locale of ["zh-Hant", "en"] as const) {
      const t = settingsT(locale);
      const sharedT = commonT(locale);
      expect(display.investorProfileFieldValue("risk_appetite", 7, t, sharedT)).toBe("7");
      expect(display.investorProfileFieldValue("preferred_edge", ["quality", "cash flow"], t, sharedT))
        .toBe("quality, cash flow");
      expect(display.investorProfileFieldValue("avoidances", ["leverage", "binary events"], t, sharedT))
        .toBe("leverage, binary events");
    }

    expect(display.investorProfileFieldValue(
      "primary_preset", "growth", settingsT("en"), commonT("zh-Hant"),
    ))
      .toBe("Growth investor (default)");
    expect(display.investorProfileFieldValue(
      "holding_horizon", "months", settingsT("zh-Hant"), commonT("en"),
    ))
      .toBe("數月");
    expect(display.investorProfileFieldValue(
      "default_stance", "complementary", settingsT("zh-Hant"), commonT("en"),
    ))
      .toBe("Complementary");
  });

  it("maps all seven stance effects in both locales", async () => {
    const display = await loadDisplay();
    const stances: AssistantStance[] = [
      "off",
      "neutral",
      "aligned",
      "complementary",
      "strict_risk_control",
      "valuation_rationalist",
      "growth_opportunity",
    ];
    const expected = {
      en: [
        "Personalization is off, so the assistant uses no Investor Profile emphasis.",
        "Keeps the analysis balanced without favoring your existing view.",
        "Emphasizes evidence and trade-offs that fit your stated investor profile.",
        "Adds perspectives and risks that complement your usual approach.",
        "Prioritizes downside, position sizing, and risk limit discipline.",
        "Prioritizes valuation, assumptions, and price-versus-value discipline.",
        "Prioritizes growth durability, upside drivers, and opportunity cost.",
      ],
      "zh-Hant": [
        "個人化已關閉，助手不會套用投資人設定重點。",
        "維持平衡分析，不偏向你目前的看法。",
        "強調符合你投資人設定的證據與取捨。",
        "補充與你慣用方法互補的觀點與風險。",
        "優先檢視下行風險、部位大小與風控紀律。",
        "優先檢視估值、假設與價格相對價值。",
        "優先檢視成長持續性、上行驅動因素與機會成本。",
      ],
    } as const;

    for (const locale of ["zh-Hant", "en"] as const) {
      expect(stances.map((stance) => display.assistantStanceEffect(stance, settingsT(locale))))
        .toEqual(expected[locale]);
    }
  });

  it("preserves backend topic and proposed-field order without sorting", async () => {
    const display = await loadDisplay();
    const topicOrder = ["assistant_style", "loss_response", "future_topic"];
    const fieldOrder = ["default_stance", "risk_appetite", "preferred_edge"];

    expect(display.orderedCalibrationTopicDisplays(topicOrder, settingsT("en")).map(({ id }) => id))
      .toEqual(topicOrder);
    expect(display.orderedInvestorProfileFieldDisplays(fieldOrder, settingsT("en")).map(({ field }) => field))
      .toEqual(fieldOrder);
  });
});
