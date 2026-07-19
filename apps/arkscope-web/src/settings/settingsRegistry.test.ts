import { describe, expect, it } from "vitest";

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

describe("settings workspace registry", () => {
  it("declares_three_nonempty_groups_in_workflow_order", () => {
    expect(SETTINGS_GROUPS.map((group) => [group.id, group.title])).toEqual([
      ["ai_models", "AI 與模型"],
      ["personalization", "個人化"],
      ["data_sync", "資料與同步"],
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

    expect(ai.sections.slice(0, 2).map((section) => [section.id, section.title])).toEqual([
      ["providers", "Provider 登入與憑證"],
      ["models", "模型與任務路由"],
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
    expect(settingsSection("fixed_task_runtime").title).toBe("固定 AI 任務執行限制");
    expect(settingsSection("research_runtime").title).toBe("AI 研究執行限制");
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
    expect(settingsSection("macro_storage").title).toBe("總經資料");
    expect(settingsSection("data_sources").keywords).not.toContain("fred");
    expect(SETTINGS_GROUPS.flatMap((group) => group.sections.map((section) => section.title)))
      .not.toEqual(expect.arrayContaining([
        expect.stringMatching(/Calendar|行事曆|\s·\s/),
      ]));
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
