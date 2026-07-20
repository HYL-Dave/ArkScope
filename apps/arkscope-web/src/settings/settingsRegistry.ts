import { settingsSearchValues } from "./settingsCopy";

export type SettingsGroupId = "ai_models" | "personalization" | "data_sync";

export type SettingsAnchorId =
  | "providers"
  | "models"
  | "fixed_task_runtime"
  | "research_runtime"
  | "investor_profile"
  | "data_sources"
  | "data_storage"
  | "news_storage"
  | "macro_storage";

export interface SettingsSectionDefinition {
  id: SettingsAnchorId;
  group: SettingsGroupId;
}

export interface SettingsGroupDefinition {
  id: SettingsGroupId;
  sections: readonly SettingsSectionDefinition[];
}

export const SETTINGS_GROUPS: readonly SettingsGroupDefinition[] = [
  {
    id: "ai_models",
    sections: [
      {
        id: "providers",
        group: "ai_models",
      },
      {
        id: "models",
        group: "ai_models",
      },
      {
        id: "fixed_task_runtime",
        group: "ai_models",
      },
      {
        id: "research_runtime",
        group: "ai_models",
      },
    ],
  },
  {
    id: "personalization",
    sections: [
      {
        id: "investor_profile",
        group: "personalization",
      },
    ],
  },
  {
    id: "data_sync",
    sections: [
      {
        id: "data_sources",
        group: "data_sync",
      },
      {
        id: "data_storage",
        group: "data_sync",
      },
      {
        id: "news_storage",
        group: "data_sync",
      },
      {
        id: "macro_storage",
        group: "data_sync",
      },
    ],
  },
];

export const SETTINGS_ANCHOR_IDS = SETTINGS_GROUPS.flatMap(
  (group) => group.sections.map((section) => section.id),
) as readonly SettingsAnchorId[];

const SECTIONS_BY_ID = new Map<SettingsAnchorId, SettingsSectionDefinition>(
  SETTINGS_GROUPS.flatMap((group) => group.sections.map((section) => [section.id, section] as const)),
);

const GROUPS_BY_SECTION_ID = new Map<SettingsAnchorId, SettingsGroupDefinition>(
  SETTINGS_GROUPS.flatMap((group) => group.sections.map((section) => [section.id, group] as const)),
);

const GROUPS_BY_ID = new Map<SettingsGroupId, SettingsGroupDefinition>(
  SETTINGS_GROUPS.map((group) => [group.id, group] as const),
);

export function settingsSection(id: SettingsAnchorId): SettingsSectionDefinition {
  const section = SECTIONS_BY_ID.get(id);
  if (!section) throw new Error(`unknown settings section: ${String(id)}`);
  return section;
}

export function settingsGroupFor(id: SettingsAnchorId): SettingsGroupDefinition {
  const group = GROUPS_BY_SECTION_ID.get(id);
  if (!group) throw new Error(`unknown settings section: ${String(id)}`);
  return group;
}

export function settingsGroup(id: SettingsGroupId): SettingsGroupDefinition {
  const group = GROUPS_BY_ID.get(id);
  if (!group) throw new Error(`unknown settings group: ${String(id)}`);
  return group;
}

export function firstSettingsAnchor(id: SettingsGroupId): SettingsAnchorId {
  const section = settingsGroup(id).sections[0];
  if (!section) throw new Error(`settings group has no sections: ${String(id)}`);
  return section.id;
}

export function settingsAnchorDomId(id: SettingsAnchorId): string {
  return `settings-${id}`;
}

function normalizeSearchValue(value: string): string {
  return value.normalize("NFKC").trim().toLowerCase();
}

export function searchSettings(query: string): readonly SettingsSectionDefinition[] {
  const normalizedQuery = normalizeSearchValue(query);
  const sections = SETTINGS_GROUPS.flatMap((group) => group.sections);
  if (!normalizedQuery) return sections;

  return sections.filter((section) => {
    return settingsSearchValues(section.id)
      .some((value) => normalizeSearchValue(value).includes(normalizedQuery));
  });
}
