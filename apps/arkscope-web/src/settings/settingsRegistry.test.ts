import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import i18n from "i18next";
import { describe, expect, it } from "vitest";

import { SettingsDirectory } from "./SettingsDirectory";
import type { SettingsAnchorId } from "./settingsRegistry";
import {
  SETTINGS_ANCHOR_IDS,
  SETTINGS_GROUPS,
  searchSettings,
  settingsAnchorDomId,
  firstSettingsAnchor,
  settingsGroup,
  settingsGroupFor,
  settingsSection,
} from "./settingsRegistry";
import {
  RETIRED_SETTINGS_COLLAPSE_STORAGE_KEY,
  SETTINGS_ACTIVE_GROUP_STORAGE_KEY,
  readActiveSettingsGroup,
  writeActiveSettingsGroup,
} from "./settingsPreferences";

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

describe("settings workspace registry", () => {
  it("declares_three_nonempty_groups_in_workflow_order", () => {
    expect(SETTINGS_GROUPS.map((group) => group.id)).toEqual([
      "ai_models",
      "personalization",
      "data_sync",
    ]);
    expect(SETTINGS_GROUPS.every((group) => group.sections.length > 0)).toBe(true);
    expect(settingsGroup("ai_models")).toBe(SETTINGS_GROUPS[0]);
    expect(settingsGroup("personalization")).toBe(SETTINGS_GROUPS[1]);
    expect(settingsGroup("data_sync")).toBe(SETTINGS_GROUPS[2]);
    expect(firstSettingsAnchor("ai_models")).toBe("providers");
    expect(firstSettingsAnchor("personalization")).toBe("investor_profile");
    expect(firstSettingsAnchor("data_sync")).toBe("data_sources");
  });

  it("assigns_every_shipped_anchor_exactly_once", () => {
    const flattened = SETTINGS_GROUPS.flatMap((group) => group.sections.map((section) => section.id));

    expect(flattened).toEqual([
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
    expect(SETTINGS_ANCHOR_IDS).toEqual(flattened);
    expect(new Set(flattened).size).toBe(flattened.length);
    expect(flattened.map((id) => settingsSection(id).id)).toEqual(flattened);
    expect(flattened.map((id) => settingsAnchorDomId(id))).toEqual(
      flattened.map((id) => `settings-${id}`),
    );
  });

  it("keeps_provider_login_separate_and_before_model_routing", () => {
    const ai = SETTINGS_GROUPS[0];

    expect(ai.sections.slice(0, 2).map((section) => section.id)).toEqual([
      "providers",
      "models",
    ]);
    expect(settingsGroupFor("providers")).toBe(ai);
    expect(settingsGroupFor("models")).toBe(ai);
  });

  it("keeps_fixed_and_research_limits_adjacent_to_model_routing", () => {
    expect(SETTINGS_GROUPS[0].sections.map((section) => section.id)).toEqual([
      "providers",
      "models",
      "fixed_task_runtime",
      "research_runtime",
    ]);
    expect(settingsSection("fixed_task_runtime").group).toBe("ai_models");
    expect(settingsSection("research_runtime").group).toBe("ai_models");
  });

  it("excludes_app_records_permissions_and_empty_advanced_groups", () => {
    const serialized = JSON.stringify(SETTINGS_GROUPS);

    expect(serialized).not.toMatch(/app_records|permissions|App and Advanced/);
    expect(SETTINGS_GROUPS).toHaveLength(3);
  });

  it("indexes_reviewed_chinese_english_and_provider_terms", () => {
    expect(searchSettings("OAuth").map((section) => section.id)).toEqual(["providers"]);
    expect(searchSettings("api key").map((section) => section.id)).toEqual(["providers"]);
    expect(searchSettings("AI 研究").map((section) => section.id)).toEqual(["research_runtime"]);
    expect(searchSettings("投資人").map((section) => section.id)).toEqual(["investor_profile"]);
    expect(searchSettings("FRED").map((section) => section.id)).toEqual(["macro_storage"]);
    expect(searchSettings("snapshot").map((section) => section.id)).toEqual(["macro_storage"]);
    expect(searchSettings("series").map((section) => section.id)).toEqual(["macro_storage"]);
    expect(searchSettings("observation").map((section) => section.id)).toEqual(["macro_storage"]);
    expect(searchSettings("Seeking Alpha").map((section) => section.id)).toEqual(["data_sources"]);
    expect(searchSettings("IBKR client id").map((section) => section.id)).toEqual(["data_sources"]);
    expect(searchSettings("schedule").map((section) => section.id)).toEqual(["data_sources"]);
    expect(searchSettings("health").map((section) => section.id)).toEqual(["data_sources"]);
    expect(searchSettings("FRED snapshot").map((section) => section.id)).toEqual(["macro_storage"]);
    expect(settingsGroupFor("macro_storage").id).toBe("data_sync");
    expect(searchSettings("fred").map((section) => section.id)).not.toContain("data_sources");
  });

  it("stores only semantic ids and no visible source-language copy", () => {
    expect(SETTINGS_GROUPS.every((group) => (
      JSON.stringify(Object.keys(group).sort()) === JSON.stringify(["id", "sections"])
    ))).toBe(true);
    expect(SETTINGS_GROUPS.flatMap((group) => group.sections).every((section) => (
      JSON.stringify(Object.keys(section).sort()) === JSON.stringify(["group", "id"])
    ))).toBe(true);
    expect(JSON.stringify(SETTINGS_GROUPS)).not.toMatch(
      /AI 與模型|Provider 登入與憑證|AI and Models|Provider Sign-in and Credentials/,
    );
  });

  it("resolves registry copy through the active locale", async () => {
    const props = {
      query: "",
      currentTarget: "providers" as const,
      activeGroup: "ai_models" as const,
      onQueryChange: () => undefined,
      onSelect: () => undefined,
    };
    await i18n.changeLanguage("en");
    const english = renderToStaticMarkup(createElement(SettingsDirectory, props));
    expect(english).toContain("AI and Models");
    expect(english).toContain("Provider Sign-in and Credentials");
    expect(english).not.toContain("Provider 登入與憑證");

    await i18n.changeLanguage("zh-Hant");
    const chinese = renderToStaticMarkup(createElement(SettingsDirectory, props));
    expect(chinese).toContain("AI 與模型");
    expect(chinese).toContain("Provider 登入與憑證");
  });

  it("keeps bilingual search metadata independent from rendered locale", async () => {
    const idsFor = (query: string) => searchSettings(query).map((section) => section.id);
    const bilingualQueries: ReadonlyArray<[string, SettingsAnchorId]> = [
      ["Provider Sign-in and Credentials", "providers"],
      ["subscription credentials", "providers"],
      ["Model and Task Routing", "models"],
      ["Fixed AI Task Runtime Limits", "fixed_task_runtime"],
      ["AI Research Runtime Limits", "research_runtime"],
      ["Investor Profile", "investor_profile"],
      ["Data Sources and Schedules", "data_sources"],
      ["trading-day coverage", "data_storage"],
      ["News Data", "news_storage"],
      ["Macro Data", "macro_storage"],
    ];

    for (const locale of ["zh-Hant", "en"] as const) {
      await i18n.changeLanguage(locale);
      for (const section of BASELINE_SECTIONS) {
        for (const query of [section.title, section.description, ...section.keywords]) {
          expect(idsFor(query), `${locale}: ${section.id}: ${query}`).toContain(section.id);
        }
      }
      for (const [query, id] of bilingualQueries) {
        expect(idsFor(query), `${locale}: ${id}: ${query}`).toContain(id);
      }
      expect(idsFor("   ")).toEqual(SETTINGS_ANCHOR_IDS);
    }
  });

  it("returns_deterministic_static_matches_without_dynamic_values", () => {
    expect(searchSettings(" ｍｏｄｅｌ ").map((section) => section.id)).toEqual(["models"]);
    expect(searchSettings(" ").map((section) => section.id)).toEqual(SETTINGS_ANCHOR_IDS);
    expect(searchSettings("personal brokerage account")).toEqual([]);
    expect(searchSettings("sk-user-specific-secret")).toEqual([]);
    expect(searchSettings("model")).toEqual(searchSettings("model"));
  });

  it("defaults_active_group_to_ai_models_without_storage", () => {
    expect(readActiveSettingsGroup()).toBe("ai_models");
    expect(readActiveSettingsGroup({ getItem: () => null })).toBe("ai_models");
  });

  it("round_trips_only_known_active_group_ids", () => {
    let stored: string | null = null;
    const storage = {
      setItem: (key: string, value: string) => {
        expect(key).toBe(SETTINGS_ACTIVE_GROUP_STORAGE_KEY);
        stored = value;
      },
      getItem: (key: string) => {
        expect(key).toBe(SETTINGS_ACTIVE_GROUP_STORAGE_KEY);
        return stored;
      },
      removeItem: () => undefined,
    };

    writeActiveSettingsGroup("data_sync", storage);
    expect(stored).toBe("data_sync");
    expect(readActiveSettingsGroup(storage)).toBe("data_sync");

    writeActiveSettingsGroup("unknown" as never, storage);
    expect(stored).toBe("ai_models");
  });

  it("fails_closed_to_ai_models_for_malformed_unknown_or_unavailable_storage", () => {
    const cases = ["not json", "{}", '["data_sync"]', "unknown", ""];

    for (const value of cases) {
      expect(readActiveSettingsGroup({ getItem: () => value })).toBe("ai_models");
    }
    expect(readActiveSettingsGroup({ getItem: () => { throw new Error("blocked"); } })).toBe("ai_models");
    expect(() => writeActiveSettingsGroup(
      "personalization",
      { setItem: () => { throw new Error("blocked"); } },
    )).not.toThrow();
  });

  it("never_reads_or_interprets_the_retired_collapse_key", () => {
    expect(readActiveSettingsGroup({
      getItem: (key: string) => {
        if (key === RETIRED_SETTINGS_COLLAPSE_STORAGE_KEY) {
          throw new Error("retired collapse state was read");
        }
        expect(key).toBe(SETTINGS_ACTIVE_GROUP_STORAGE_KEY);
        return "personalization";
      },
    })).toBe("personalization");
  });

  it("best_effort_cleanup_failure_never_blocks_active_group_write", () => {
    let stored: string | null = null;
    const storage = {
      setItem: (_key: string, value: string) => { stored = value; },
      removeItem: (key: string) => {
        expect(key).toBe(RETIRED_SETTINGS_COLLAPSE_STORAGE_KEY);
        throw new Error("cleanup blocked");
      },
    };

    expect(() => writeActiveSettingsGroup("personalization", storage)).not.toThrow();
    expect(stored).toBe("personalization");
    expect(readActiveSettingsGroup({ getItem: () => stored })).toBe("personalization");
  });
});
