import type { TFunction } from "i18next";

import type {
  InvestorPreset,
  ModelProvider,
  ModelTask,
  TaskRoute,
} from "../api";
import enSettings from "../i18n/resources/en/settings";
import zhHantSettings from "../i18n/resources/zh-Hant/settings";
import type { SettingsAnchorId, SettingsGroupId } from "./settingsRegistry";

export type SettingsT = TFunction<"settings">;

function stableUnknown(value: never): string {
  return String(value);
}

type SearchCopy = {
  title: string;
  description: string;
  searchAliases: string;
};

const SETTINGS_SECTION_SEARCH: Record<
  SettingsAnchorId,
  { zh: SearchCopy; en: SearchCopy }
> = {
  providers: {
    zh: zhHantSettings.registry.sections.providers,
    en: enSettings.registry.sections.providers,
  },
  models: {
    zh: zhHantSettings.registry.sections.models,
    en: enSettings.registry.sections.models,
  },
  fixed_task_runtime: {
    zh: zhHantSettings.registry.sections.fixedTaskRuntime,
    en: enSettings.registry.sections.fixedTaskRuntime,
  },
  research_runtime: {
    zh: zhHantSettings.registry.sections.researchRuntime,
    en: enSettings.registry.sections.researchRuntime,
  },
  investor_profile: {
    zh: zhHantSettings.registry.sections.investorProfile,
    en: enSettings.registry.sections.investorProfile,
  },
  data_sources: {
    zh: zhHantSettings.registry.sections.dataSources,
    en: enSettings.registry.sections.dataSources,
  },
  data_storage: {
    zh: zhHantSettings.registry.sections.dataStorage,
    en: enSettings.registry.sections.dataStorage,
  },
  news_storage: {
    zh: zhHantSettings.registry.sections.newsStorage,
    en: enSettings.registry.sections.newsStorage,
  },
  macro_storage: {
    zh: zhHantSettings.registry.sections.macroStorage,
    en: enSettings.registry.sections.macroStorage,
  },
};

function splitAliases(value: string): string[] {
  return value.split("|").map((alias) => alias.trim()).filter(Boolean);
}

export function settingsGroupLabel(id: SettingsGroupId, t: SettingsT): string {
  switch (id) {
    case "ai_models":
      return t(($) => $.registry.groups.aiModels);
    case "personalization":
      return t(($) => $.registry.groups.personalization);
    case "data_sync":
      return t(($) => $.registry.groups.dataSync);
  }
}

export function settingsSectionCopy(
  id: SettingsAnchorId,
  t: SettingsT,
): { title: string; description: string } {
  switch (id) {
    case "providers":
      return {
        title: t(($) => $.registry.sections.providers.title),
        description: t(($) => $.registry.sections.providers.description),
      };
    case "models":
      return {
        title: t(($) => $.registry.sections.models.title),
        description: t(($) => $.registry.sections.models.description),
      };
    case "fixed_task_runtime":
      return {
        title: t(($) => $.registry.sections.fixedTaskRuntime.title),
        description: t(($) => $.registry.sections.fixedTaskRuntime.description),
      };
    case "research_runtime":
      return {
        title: t(($) => $.registry.sections.researchRuntime.title),
        description: t(($) => $.registry.sections.researchRuntime.description),
      };
    case "investor_profile":
      return {
        title: t(($) => $.registry.sections.investorProfile.title),
        description: t(($) => $.registry.sections.investorProfile.description),
      };
    case "data_sources":
      return {
        title: t(($) => $.registry.sections.dataSources.title),
        description: t(($) => $.registry.sections.dataSources.description),
      };
    case "data_storage":
      return {
        title: t(($) => $.registry.sections.dataStorage.title),
        description: t(($) => $.registry.sections.dataStorage.description),
      };
    case "news_storage":
      return {
        title: t(($) => $.registry.sections.newsStorage.title),
        description: t(($) => $.registry.sections.newsStorage.description),
      };
    case "macro_storage":
      return {
        title: t(($) => $.registry.sections.macroStorage.title),
        description: t(($) => $.registry.sections.macroStorage.description),
      };
  }
}

export function settingsSearchValues(id: SettingsAnchorId): readonly string[] {
  const copy = SETTINGS_SECTION_SEARCH[id];
  return [
    copy.zh.title,
    copy.zh.description,
    ...splitAliases(copy.zh.searchAliases),
    copy.en.title,
    copy.en.description,
    ...splitAliases(copy.en.searchAliases),
  ];
}

export function settingsTaskLabel(task: ModelTask, t: SettingsT): string {
  switch (task) {
    case "card_synthesis":
      return t(($) => $.models.tasks.cardSynthesis.label);
    case "card_translation":
      return t(($) => $.models.tasks.cardTranslation.label);
    case "ai_research":
      return t(($) => $.models.tasks.aiResearch.label);
  }
}

export function settingsEffortLabel(id: string, t: SettingsT): string {
  switch (id) {
    case "default":
      return t(($) => $.models.effort.default);
    case "none":
      return t(($) => $.models.effort.none);
    case "low":
      return t(($) => $.models.effort.low);
    case "medium":
      return t(($) => $.models.effort.medium);
    case "high":
      return t(($) => $.models.effort.high);
    case "xhigh":
      return t(($) => $.models.effort.xhigh);
    case "max":
      return t(($) => $.models.effort.max);
    default:
      return id;
  }
}

export function settingsEffortDescription(
  provider: ModelProvider,
  id: string,
  t: SettingsT,
): string {
  switch (provider) {
    case "openai":
      switch (id) {
        case "default":
          return t(($) => $.models.effortDescriptions.openai.default);
        case "none":
          return t(($) => $.models.effortDescriptions.openai.none);
        case "low":
          return t(($) => $.models.effortDescriptions.openai.low);
        case "medium":
          return t(($) => $.models.effortDescriptions.openai.medium);
        case "high":
          return t(($) => $.models.effortDescriptions.openai.high);
        case "xhigh":
          return t(($) => $.models.effortDescriptions.openai.xhigh);
        case "max":
          return t(($) => $.models.effortDescriptions.openai.max, {
            sourceId: "GPT-5.6",
          });
        default:
          return id;
      }
    case "anthropic":
      switch (id) {
        case "default":
          return t(($) => $.models.effortDescriptions.anthropic.default);
        case "low":
          return t(($) => $.models.effortDescriptions.anthropic.low);
        case "medium":
          return t(($) => $.models.effortDescriptions.anthropic.medium);
        case "high":
          return t(($) => $.models.effortDescriptions.anthropic.high);
        case "xhigh":
          return t(($) => $.models.effortDescriptions.anthropic.xhigh);
        case "max":
          return t(($) => $.models.effortDescriptions.anthropic.max);
        default:
          return id;
      }
  }
}

export function settingsThinkingLabel(id: string, t: SettingsT): string {
  switch (id) {
    case "none":
      return t(($) => $.models.thinking.none);
    case "manual_budget":
      return t(($) => $.models.thinking.manualBudget);
    case "adaptive_opt_in":
      return t(($) => $.models.thinking.adaptiveOptIn);
    case "adaptive_default_on":
      return t(($) => $.models.thinking.adaptiveDefaultOn);
    case "adaptive_always_on":
      return t(($) => $.models.thinking.adaptiveAlwaysOn);
    default:
      return id;
  }
}

export function settingsRouteSourceLabel(
  source: TaskRoute["source"],
  t: SettingsT,
): string {
  switch (source) {
    case "env":
      return t(($) => $.models.route.sources.env);
    case "db":
      return t(($) => $.models.route.sources.db);
    case "profile":
      return t(($) => $.models.route.sources.profile);
    case "default":
      return t(($) => $.models.route.sources.default);
  }
}

export function settingsInvestorPresetLabel(
  id: InvestorPreset,
  t: SettingsT,
): string {
  switch (id) {
    case "growth":
      return t(($) => $.investor.presets.growth);
    case "value":
      return t(($) => $.investor.presets.value);
    case "momentum":
      return t(($) => $.investor.presets.momentum);
    case "income":
      return t(($) => $.investor.presets.income);
    case "event_driven":
      return t(($) => $.investor.presets.eventDriven);
    case "balanced":
      return t(($) => $.investor.presets.balanced);
    case "custom":
      return t(($) => $.investor.presets.custom);
    default:
      return stableUnknown(id);
  }
}

export function settingsInvestorHorizonLabel(id: string, t: SettingsT): string {
  switch (id) {
    case "intraday":
      return t(($) => $.investor.horizons.intraday);
    case "days_weeks":
      return t(($) => $.investor.horizons.daysWeeks);
    case "months":
      return t(($) => $.investor.horizons.months);
    case "multi_year":
      return t(($) => $.investor.horizons.multiYear);
    case "mixed":
      return t(($) => $.investor.horizons.mixed);
    default:
      return id;
  }
}
