import { SETTINGS_GROUPS, type SettingsGroupId } from "./settingsRegistry";

export const SETTINGS_COLLAPSE_STORAGE_KEY = "arkscope.settings.collapsedGroups.v1";
export const SETTINGS_ACTIVE_GROUP_STORAGE_KEY = "arkscope.settings.activeGroup.v1";
export const RETIRED_SETTINGS_COLLAPSE_STORAGE_KEY = SETTINGS_COLLAPSE_STORAGE_KEY;

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

export function readCollapsedSettingsGroups(
  storage?: Pick<Storage, "getItem">,
): ReadonlySet<SettingsGroupId> {
  try {
    const resolvedStorage = storage ?? (typeof window === "undefined" ? undefined : window.localStorage);
    if (!resolvedStorage) return new Set();
    const raw = resolvedStorage.getItem(SETTINGS_COLLAPSE_STORAGE_KEY);
    if (raw == null) return new Set();
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return new Set();
    return new Set(parsed.filter(isSettingsGroupId));
  } catch {
    return new Set();
  }
}

export function writeCollapsedSettingsGroups(
  collapsed: ReadonlySet<SettingsGroupId>,
  storage?: Pick<Storage, "setItem">,
): void {
  try {
    const resolvedStorage = storage ?? (typeof window === "undefined" ? undefined : window.localStorage);
    if (!resolvedStorage) return;
    const serialized = [...collapsed].filter(isSettingsGroupId).sort();
    resolvedStorage.setItem(SETTINGS_COLLAPSE_STORAGE_KEY, JSON.stringify(serialized));
  } catch {
    // Preferences fail closed to all groups expanded.
  }
}
