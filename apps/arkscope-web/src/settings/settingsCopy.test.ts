import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { createInstance } from "i18next";
import { describe, expect, it } from "vitest";

import type {
  AssistantStance,
  InvestorPreset,
  InvestorProfile,
  ModelProvider,
  ModelTask,
  TaskRoute,
} from "../api";
import { initializeI18n, resources } from "../i18n/resources";
import { mismatchLabel, stanceLabel } from "../personalizationDisplay";
import type { SettingsAnchorId, SettingsGroupId } from "./settingsRegistry";
import {
  settingsEffortDescription,
  settingsEffortLabel,
  settingsGroupLabel,
  settingsInvestorHorizonLabel,
  settingsInvestorPresetLabel,
  settingsRouteSourceLabel,
  settingsSearchValues,
  settingsSectionCopy,
  settingsTaskLabel,
  settingsThinkingLabel,
} from "./settingsCopy";

type Locale = "zh-Hant" | "en";

function settingsT(locale: Locale) {
  const instance = createInstance();
  initializeI18n(instance, locale);
  return instance.getFixedT(locale, "settings");
}

function commonT(locale: Locale) {
  const instance = createInstance();
  initializeI18n(instance, locale);
  return instance.getFixedT(locale, "common");
}

// Frozen from settingsRegistry.ts at the reviewed pre-I18N-2 baseline 707a5705.
// Do not derive this fixture from localized resources or the live registry.
const BASELINE_SECTIONS: ReadonlyArray<{
  id: SettingsAnchorId;
  title: string;
  description: string;
  keywords: readonly string[];
}> = [
  {
    id: "providers",
    title: "Provider 登入與憑證",
    description: "管理 AI provider 登入、訂閱與 API 憑證。",
    keywords: ["provider", "oauth", "api key", "credential", "憑證", "登入", "anthropic", "openai", "chatgpt", "claude"],
  },
  {
    id: "models",
    title: "模型與任務路由",
    description: "依任務選擇模型、provider 與推理強度。",
    keywords: ["model", "models", "模型", "任務", "路由", "routing", "effort"],
  },
  {
    id: "fixed_task_runtime",
    title: "固定 AI 任務執行限制",
    description: "設定 AI 卡片生成與翻譯的模型執行上界。",
    keywords: ["timeout", "runtime", "卡片生成", "卡片翻譯", "fixed task"],
  },
  {
    id: "research_runtime",
    title: "AI 研究執行限制",
    description: "設定 AI 研究 session 與單次執行限制。",
    keywords: ["ai 研究", "research", "timeout", "runtime", "session"],
  },
  {
    id: "investor_profile",
    title: "投資人設定",
    description: "管理投資人輪廓、風險意願與研究個人化。",
    keywords: ["投資人", "個人化", "investor profile", "risk appetite", "風險意願", "風險承受能力"],
  },
  {
    id: "data_sources",
    title: "資料來源與排程",
    description: "查看資料來源健康度、排程與瀏覽器擴充同步狀態。",
    keywords: [
      "data sources", "schedule", "資料來源", "排程", "health",
      "provider health", "credential", "seeking alpha", "sa extension",
      "ibkr client id", "IBKR 用戶端 ID",
    ],
  },
  {
    id: "data_storage",
    title: "市場資料",
    description: "查看價格、IV、基本面與交易日資料覆蓋。",
    keywords: ["market data", "市場資料", "price", "價格", "iv", "基本面", "coverage", "sqlite"],
  },
  {
    id: "news_storage",
    title: "新聞資料",
    description: "查看新聞資料量、攝入狀態與最近更新。",
    keywords: ["news", "新聞", "ingestion", "文章", "polygon", "finnhub", "ibkr"],
  },
  {
    id: "macro_storage",
    title: "總經資料",
    description: "查看 FRED series、資料快照與總經資料覆蓋。",
    keywords: [
      "macro", "總經", "總體經濟", "fred", "fred snapshot", "snapshot",
      "series", "observation", "資料快照",
    ],
  },
];

function normalize(value: string): string {
  return value.normalize("NFKC").trim().toLowerCase();
}

function searchIds(query: string): SettingsAnchorId[] {
  const normalized = normalize(query);
  if (!normalized) return BASELINE_SECTIONS.map(({ id }) => id);
  return BASELINE_SECTIONS
    .map(({ id }) => id)
    .filter((id) => settingsSearchValues(id).some((value) => normalize(value).includes(normalized)));
}

describe("Settings static copy authority", () => {
  it("maps every workflow group in both locales", () => {
    const ids: SettingsGroupId[] = ["ai_models", "personalization", "data_sync"];
    const cases = [
      { locale: "zh-Hant" as const, labels: ["AI 與模型", "個人化", "資料與同步"] },
      { locale: "en" as const, labels: ["AI and Models", "Personalization", "Data and Sync"] },
    ];

    for (const expected of cases) {
      const t = settingsT(expected.locale);
      expect(ids.map((id) => settingsGroupLabel(id, t))).toEqual(expected.labels);
    }
  });

  it("maps every Settings section title and description in both locales", () => {
    const cases: Record<Locale, Array<[SettingsAnchorId, string, string]>> = {
      "zh-Hant": [
        ["providers", "Provider 登入與憑證", "管理 AI provider 登入、訂閱與 API 憑證。"],
        ["models", "模型與任務路由", "依任務選擇模型、provider 與推理強度。"],
        ["fixed_task_runtime", "固定 AI 任務執行限制", "設定 AI 卡片生成與翻譯的模型執行上界。"],
        ["research_runtime", "AI 研究執行限制", "設定 AI 研究 session 與單次執行限制。"],
        ["investor_profile", "投資人設定", "管理投資人輪廓、風險意願與研究個人化。"],
        ["data_sources", "資料來源與排程", "查看資料來源健康度、排程與瀏覽器擴充同步狀態。"],
        ["data_storage", "市場資料", "查看價格、IV、基本面與交易日資料覆蓋。"],
        ["news_storage", "新聞資料", "查看新聞資料量、攝入狀態與最近更新。"],
        ["macro_storage", "總經資料", "查看 FRED series、資料快照與總經資料覆蓋。"],
      ],
      en: [
        ["providers", "Provider Sign-in and Credentials", "Manage AI provider sign-ins, subscriptions, and API credentials."],
        ["models", "Model and Task Routing", "Choose the model, provider, and reasoning effort for each task."],
        ["fixed_task_runtime", "Fixed AI Task Runtime Limits", "Set upper runtime limits for AI card synthesis and translation."],
        ["research_runtime", "AI Research Runtime Limits", "Set session and per-run limits for AI Research."],
        ["investor_profile", "Investor Profile", "Manage the investor profile, risk appetite, and research personalization."],
        ["data_sources", "Data Sources and Schedules", "Review data-source health, schedules, and browser extension sync."],
        ["data_storage", "Market Data", "Review price, IV, fundamentals, and trading-day data coverage."],
        ["news_storage", "News Data", "Review news volume, ingestion status, and recent updates."],
        ["macro_storage", "Macro Data", "Review FRED series, snapshots, and macro-data coverage."],
      ],
    };

    for (const locale of ["zh-Hant", "en"] as const) {
      const t = settingsT(locale);
      for (const [id, title, description] of cases[locale]) {
        expect(settingsSectionCopy(id, t)).toEqual({ title, description });
      }
    }
  });

  it("searches both locale alias sets regardless of active locale", () => {
    for (const section of BASELINE_SECTIONS) {
      for (const query of [section.title, section.description, ...section.keywords]) {
        expect(searchIds(query), `${section.id}: ${query}`).toContain(section.id);
      }
    }

    expect(searchIds("subscription credentials")).toContain("providers");
    expect(searchIds("trading-day coverage")).toContain("data_storage");
    expect(searchIds("總體經濟")).toContain("macro_storage");
  });

  it("keeps empty search in deterministic registry order", () => {
    expect(searchIds("   ")).toEqual([
      "providers",
      "models",
      "fixed_task_runtime",
      "research_runtime",
      "investor_profile",
      "data_sources",
      "data_storage",
      "news_storage",
      "macro_storage",
    ]);
  });

  it("maps every model task without backend labels", () => {
    const tasks: ModelTask[] = ["card_synthesis", "card_translation", "ai_research"];
    const cases = [
      { locale: "zh-Hant" as const, labels: ["AI 卡片生成", "卡片翻譯", "AI 研究"] },
      { locale: "en" as const, labels: ["AI Card Synthesis", "Card Translation", "AI Research"] },
    ];

    for (const expected of cases) {
      const t = settingsT(expected.locale);
      expect(tasks.map((task) => settingsTaskLabel(task, t))).toEqual(expected.labels);
    }
  });

  it("maps reviewed effort and thinking ids with stable unknown fallback", () => {
    const efforts = ["default", "none", "low", "medium", "high", "xhigh", "max"];
    const thinking = [
      "none",
      "manual_budget",
      "adaptive_opt_in",
      "adaptive_default_on",
      "adaptive_always_on",
    ];
    const cases = [
      {
        locale: "zh-Hant" as const,
        efforts: ["預設", "無", "低", "中", "高", "極高", "最大"],
        descriptions: {
          openai: [
            "不送 effort；實際檔位由目前模型與後端決定。",
            "明確送出 none；這不是未設定或供應商預設。",
            "使用較低的 reasoning effort。",
            "使用平衡的 reasoning effort。",
            "使用較高的 reasoning effort，適合較困難的綜合分析。",
            "使用 SDK 支援的高階 reasoning effort；只有在所選 model/account 支援時才使用。",
            "使用最大 reasoning effort；目前只有 GPT-5.6 系列 model 支援。",
          ],
          anthropic: [
            "不送出 output_config.effort；改用 Claude API 的預設值。",
            "透過 Anthropic output_config.effort 使用較低 effort。",
            "透過 Anthropic output_config.effort 使用中等 effort。",
            "透過 Anthropic output_config.effort 使用較高 effort。",
            "在可用時，透過 Anthropic output_config.effort 使用極高 effort。",
            "在可用時，透過 Anthropic output_config.effort 使用最大 effort。",
          ],
        },
        thinking: [
          "無特殊 thinking 行為",
          "使用手動 thinking budget",
          "可選擇 adaptive thinking",
          "預設開啟 adaptive thinking",
          "固定開啟 adaptive thinking",
        ],
      },
      {
        locale: "en" as const,
        efforts: ["Default", "None", "Low", "Medium", "High", "Extra high", "Maximum"],
        descriptions: {
          openai: [
            "Do not send effort; the current model and backend determine the effective level.",
            "Explicitly send none; this is not unset or the provider default.",
            "Low reasoning effort.",
            "Balanced reasoning effort.",
            "High reasoning effort for more difficult synthesis.",
            "SDK-supported high-end reasoning effort; only use if the selected model/account accepts it.",
            "Maximum reasoning effort; currently supported by GPT-5.6 models.",
          ],
          anthropic: [
            "Do not send output_config.effort; use the Claude API default.",
            "Lower effort via Anthropic output_config.effort.",
            "Medium effort via Anthropic output_config.effort.",
            "High effort via Anthropic output_config.effort.",
            "Extra-high effort via Anthropic output_config.effort where available.",
            "Maximum effort via Anthropic output_config.effort where available.",
          ],
        },
        thinking: [
          "No special thinking behavior",
          "Uses a manual thinking budget",
          "Adaptive thinking available",
          "Adaptive thinking on by default",
          "Adaptive thinking always on",
        ],
      },
    ];

    for (const expected of cases) {
      const t = settingsT(expected.locale);
      expect(efforts.map((id) => settingsEffortLabel(id, t))).toEqual(expected.efforts);
      const providerEfforts: Record<ModelProvider, string[]> = {
        openai: efforts,
        anthropic: ["default", "low", "medium", "high", "xhigh", "max"],
      };
      expect(providerEfforts.openai.map((id) => settingsEffortDescription("openai", id, t)))
        .toEqual(expected.descriptions.openai);
      expect(providerEfforts.anthropic.map((id) => settingsEffortDescription("anthropic", id, t)))
        .toEqual(expected.descriptions.anthropic);
      expect(thinking.map((id) => settingsThinkingLabel(id, t))).toEqual(expected.thinking);
      expect(settingsEffortLabel("future_effort", t)).toBe("future_effort");
      expect(settingsEffortDescription("openai", "future_effort", t)).toBe("future_effort");
      expect(settingsEffortDescription("anthropic", "future_effort", t)).toBe("future_effort");
      expect(settingsThinkingLabel("future_thinking", t)).toBe("future_thinking");
    }
  });

  it("maps every route source in both locales", () => {
    const sources: TaskRoute["source"][] = ["env", "db", "profile", "default"];
    const cases = [
      { locale: "zh-Hant" as const, labels: ["env 覆蓋", "DB（已儲存）", "設定檔 fallback", "內建預設"] },
      { locale: "en" as const, labels: ["Environment override", "DB (saved)", "Profile fallback", "Built-in default"] },
    ];

    for (const expected of cases) {
      const t = settingsT(expected.locale);
      expect(sources.map((source) => settingsRouteSourceLabel(source, t))).toEqual(expected.labels);
    }
  });

  it("maps every Investor preset and horizon in both locales", () => {
    const presets: InvestorPreset[] = [
      "growth", "value", "momentum", "income", "event_driven", "balanced", "custom",
    ];
    const horizons = ["intraday", "days_weeks", "months", "multi_year", "mixed"];
    const cases = [
      {
        locale: "zh-Hant" as const,
        presets: ["成長投資人（預設）", "價值", "動能", "收益", "事件驅動", "均衡", "自訂"],
        horizons: ["當沖", "數天〜數週", "數月", "多年", "混合"],
      },
      {
        locale: "en" as const,
        presets: ["Growth investor (default)", "Value", "Momentum", "Income", "Event-driven", "Balanced", "Custom"],
        horizons: ["Intraday", "Days to weeks", "Months", "Multi-year", "Mixed"],
      },
    ];

    for (const expected of cases) {
      const t = settingsT(expected.locale);
      expect(presets.map((id) => settingsInvestorPresetLabel(id, t))).toEqual(expected.presets);
      expect(horizons.map((id) => settingsInvestorHorizonLabel(id, t))).toEqual(expected.horizons);
      expect(settingsInvestorPresetLabel("future_preset" as InvestorPreset, t)).toBe("future_preset");
      expect(settingsInvestorHorizonLabel("future_horizon", t)).toBe("future_horizon");
    }
  });

  it("maps every Investor stance and mismatch state in both locales", () => {
    const stances: AssistantStance[] = [
      "off",
      "neutral",
      "aligned",
      "complementary",
      "strict_risk_control",
      "valuation_rationalist",
      "growth_opportunity",
    ];
    const mismatches: InvestorProfile["risk_mismatch"][] = [
      "none", "appetite_above_capacity", "capacity_above_appetite", "unclear",
    ];
    const enStances = [
      "Off",
      "Neutral",
      "Investor-aligned",
      "Complementary",
      "Strict risk control",
      "Valuation rationalist",
      "Growth opportunity",
    ];
    const enMismatches = [
      "Aligned",
      "Risk appetite above capacity",
      "Risk capacity above appetite",
      "Not assessed",
    ];

    const zhT = commonT("zh-Hant");
    expect(stances.map((id) => stanceLabel(id, zhT))).toEqual([
      "關閉", "中性", "對齊投資人", "互補投資人", "嚴格風控", "估值理性派", "成長機會派",
    ]);
    expect(mismatches.map((id) => mismatchLabel(id, zhT))).toEqual([
      "一致", "風險意願高於承受能力", "承受能力高於風險意願", "未評估",
    ]);

    const enT = commonT("en");
    expect.soft(stances.map((id) => stanceLabel(id, enT))).toEqual(enStances);
    expect.soft(mismatches.map((id) => mismatchLabel(id, enT))).toEqual(enMismatches);
    expect.soft(stanceLabel("future_stance" as AssistantStance, enT)).toBe("future_stance");
    expect.soft(mismatchLabel(
      "future_mismatch" as InvestorProfile["risk_mismatch"],
      enT,
    )).toBe("future_mismatch");

    for (const locale of ["zh-Hant", "en"] as const) {
      const investor = resources[locale].settings.investor as Record<string, unknown>;
      expect.soft(investor.stances, `${locale}.settings.investor.stances`).toBeUndefined();
      expect.soft(investor.mismatch, `${locale}.settings.investor.mismatch`).toBeUndefined();
    }
    const source = readFileSync(resolve(import.meta.dirname, "settingsCopy.ts"), "utf8");
    expect.soft(source).not.toMatch(/settingsStanceLabel|settingsMismatchLabel/);
  });

  it("contains no dynamic translation key or source value", () => {
    const root = resolve(import.meta.dirname, "..");
    const source = readFileSync(resolve(import.meta.dirname, "settingsCopy.ts"), "utf8");
    const backendSource = readFileSync(resolve(import.meta.dirname, "settingsBackendCopy.ts"), "utf8");
    const resources = [
      readFileSync(resolve(root, "i18n/resources/zh-Hant/settings.ts"), "utf8"),
      readFileSync(resolve(root, "i18n/resources/en/settings.ts"), "utf8"),
    ].join("\n");
    const translationCalls = `${source}\n${backendSource}`.match(/\bt\(/g) ?? [];
    const selectorCalls = `${source}\n${backendSource}`.match(/\bt\(\(\$\) => \$\./g) ?? [];

    expect(selectorCalls).toHaveLength(translationCalls.length);
    expect(`${source}\n${backendSource}`).not.toMatch(/\bt\([^)]*(?:\+|`|\[)/);
    expect(resources).not.toMatch(/NVDA|gpt-[\w.-]+|sk-(?:ant-)?[\w-]+|https?:\/\//i);
    expect(source).toContain('sourceId: "GPT-5.6"');
    expect(source).toMatch(/function stableUnknown\(value: never\): string/);

    const exported = [...source.matchAll(/export (?:type|function)\s+(\w+)/g)]
      .map((match) => match[1]);
    expect(exported).toEqual([
      "SettingsT",
      "settingsGroupLabel",
      "settingsSectionCopy",
      "settingsSearchValues",
      "settingsTaskLabel",
      "settingsEffortLabel",
      "settingsEffortDescription",
      "settingsThinkingLabel",
      "settingsRouteSourceLabel",
      "settingsInvestorPresetLabel",
      "settingsInvestorHorizonLabel",
    ]);
  });
});
