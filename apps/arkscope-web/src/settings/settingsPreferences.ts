import { SETTINGS_GROUPS, type SettingsGroupId } from "./settingsRegistry";

export const SETTINGS_ACTIVE_GROUP_STORAGE_KEY = "arkscope.settings.activeGroup.v1";
export const RETIRED_SETTINGS_COLLAPSE_STORAGE_KEY = "arkscope.settings.collapsedGroups.v1";

const DEFAULT_SETTINGS_GROUP = SETTINGS_GROUPS[0].id;

function isSettingsGroupId(value: unknown): value is SettingsGroupId {
  return typeof value === "string" && SETTINGS_GROUPS.some((group) => group.id === value);
}

export function readActiveSettingsGroup(
  storage?: Pick<Storage, "getItem">,
): SettingsGroupId {
  try {
    const resolvedStorage = storage ?? (typeof window === "undefined" ? undefined : window.localStorage);
    if (!resolvedStorage) return DEFAULT_SETTINGS_GROUP;
    const raw = resolvedStorage.getItem(SETTINGS_ACTIVE_GROUP_STORAGE_KEY);
    return isSettingsGroupId(raw) ? raw : DEFAULT_SETTINGS_GROUP;
  } catch {
    return DEFAULT_SETTINGS_GROUP;
  }
}

export function writeActiveSettingsGroup(
  group: SettingsGroupId,
  storage?: Pick<Storage, "setItem"> & Partial<Pick<Storage, "removeItem">>,
): void {
  try {
    const resolvedStorage = storage ?? (typeof window === "undefined" ? undefined : window.localStorage);
    if (!resolvedStorage) return;
    resolvedStorage.setItem(
      SETTINGS_ACTIVE_GROUP_STORAGE_KEY,
      isSettingsGroupId(group) ? group : DEFAULT_SETTINGS_GROUP,
    );
    try {
      resolvedStorage.removeItem?.(RETIRED_SETTINGS_COLLAPSE_STORAGE_KEY);
    } catch {
      // Retired-state cleanup cannot invalidate the accepted new preference.
    }
  } catch {
    // Preferences fail closed to the first workflow group.
  }
}
