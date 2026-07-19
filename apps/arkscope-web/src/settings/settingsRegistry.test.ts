import { describe, expect, it } from "vitest";

import {
  SETTINGS_ANCHOR_IDS,
  SETTINGS_GROUPS,
  searchSettings,
  settingsAnchorDomId,
  settingsGroupFor,
  settingsSection,
} from "./settingsRegistry";
import {
  SETTINGS_COLLAPSE_STORAGE_KEY,
  readCollapsedSettingsGroups,
  writeCollapsedSettingsGroups,
} from "./settingsPreferences";

describe("settings workspace registry", () => {
  it("declares_three_nonempty_groups_in_workflow_order", () => {
    expect(SETTINGS_GROUPS.map((group) => [group.id, group.title])).toEqual([
      ["ai_models", "AI 與模型"],
      ["personalization", "個人化"],
      ["data_sync", "資料與同步"],
    ]);
    expect(SETTINGS_GROUPS.every((group) => group.sections.length > 0)).toBe(true);
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
    expect(searchSettings("Seeking Alpha").map((section) => section.id)).toEqual(["data_sources"]);
  });

  it("returns_deterministic_static_matches_without_dynamic_values", () => {
    expect(searchSettings(" ｍｏｄｅｌ ").map((section) => section.id)).toEqual(["models"]);
    expect(searchSettings(" ").map((section) => section.id)).toEqual(SETTINGS_ANCHOR_IDS);
    expect(searchSettings("personal brokerage account")).toEqual([]);
    expect(searchSettings("sk-user-specific-secret")).toEqual([]);
    expect(searchSettings("model")).toEqual(searchSettings("model"));
  });

  it("defaults_every_group_expanded_when_storage_is_absent", () => {
    expect(readCollapsedSettingsGroups()).toEqual(new Set());
    expect(readCollapsedSettingsGroups({ getItem: () => null })).toEqual(new Set());
  });

  it("round_trips_only_known_collapsed_group_ids", () => {
    let stored: string | null = null;
    const writer = { setItem: (key: string, value: string) => {
      expect(key).toBe(SETTINGS_COLLAPSE_STORAGE_KEY);
      stored = value;
    } };

    writeCollapsedSettingsGroups(new Set(["data_sync", "ai_models"]), writer);
    expect(stored).toBe('["ai_models","data_sync"]');
    expect(readCollapsedSettingsGroups({
      getItem: (key: string) => {
        expect(key).toBe(SETTINGS_COLLAPSE_STORAGE_KEY);
        return '["data_sync","unknown","ai_models","data_sync"]';
      },
    })).toEqual(new Set(["data_sync", "ai_models"]));
  });

  it("fails_closed_to_expanded_for_malformed_or_unknown_storage", () => {
    const cases = ["not json", "{}", '["unknown"]', "null"];

    for (const value of cases) {
      expect(readCollapsedSettingsGroups({ getItem: () => value })).toEqual(new Set());
    }
    expect(readCollapsedSettingsGroups({ getItem: () => { throw new Error("blocked"); } })).toEqual(new Set());
    expect(() => writeCollapsedSettingsGroups(
      new Set(["ai_models"]),
      { setItem: () => { throw new Error("blocked"); } },
    )).not.toThrow();
  });
});
