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

export type SettingsSubsectionId =
  | "provider_health"
  | "sa_extension_health"
  | "provider_connections"
  | "source_schedules"
  | "security_lifecycle"
  | "trading_day_coverage";

export type SettingsLocationId = SettingsAnchorId | SettingsSubsectionId;

export interface SettingsSectionDefinition {
  id: SettingsAnchorId;
  group: SettingsGroupId;
}

export interface SettingsGroupDefinition {
  id: SettingsGroupId;
  sections: readonly SettingsSectionDefinition[];
}

export interface SettingsSubsectionDefinition {
  id: SettingsSubsectionId;
  parent: SettingsAnchorId;
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

export const SETTINGS_SUBSECTIONS: readonly SettingsSubsectionDefinition[] = [
  { id: "provider_health", parent: "data_sources" },
  { id: "sa_extension_health", parent: "data_sources" },
  { id: "provider_connections", parent: "data_sources" },
  { id: "source_schedules", parent: "data_sources" },
  { id: "security_lifecycle", parent: "data_storage" },
  { id: "trading_day_coverage", parent: "data_storage" },
];

const SECTIONS_BY_ID = new Map<SettingsAnchorId, SettingsSectionDefinition>(
  SETTINGS_GROUPS.flatMap((group) => group.sections.map((section) => [section.id, section] as const)),
);

const GROUPS_BY_SECTION_ID = new Map<SettingsAnchorId, SettingsGroupDefinition>(
  SETTINGS_GROUPS.flatMap((group) => group.sections.map((section) => [section.id, group] as const)),
);

const GROUPS_BY_ID = new Map<SettingsGroupId, SettingsGroupDefinition>(
  SETTINGS_GROUPS.map((group) => [group.id, group] as const),
);

const SUBSECTIONS_BY_ID = new Map<SettingsSubsectionId, SettingsSubsectionDefinition>(
  SETTINGS_SUBSECTIONS.map((subsection) => [subsection.id, subsection]),
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

export function settingsSubsectionsFor(
  id: SettingsAnchorId,
): readonly SettingsSubsectionDefinition[] {
  return SETTINGS_SUBSECTIONS.filter((subsection) => subsection.parent === id);
}

export function settingsParentAnchor(id: SettingsLocationId): SettingsAnchorId {
  if (SECTIONS_BY_ID.has(id as SettingsAnchorId)) return id as SettingsAnchorId;
  const subsection = SUBSECTIONS_BY_ID.get(id as SettingsSubsectionId);
  if (!subsection) throw new Error(`unknown settings location: ${String(id)}`);
  return subsection.parent;
}

export function settingsGroupForLocation(id: SettingsLocationId): SettingsGroupDefinition {
  return settingsGroupFor(settingsParentAnchor(id));
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

export function settingsLocationDomId(id: SettingsLocationId): string {
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
