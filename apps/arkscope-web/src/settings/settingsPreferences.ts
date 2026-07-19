import type { SettingsGroupId } from "./settingsRegistry";

export const SETTINGS_COLLAPSE_STORAGE_KEY = "arkscope.settings.collapsedGroups.v1";

const SETTINGS_GROUP_IDS = new Set<SettingsGroupId>([
  "ai_models",
  "personalization",
  "data_sync",
]);

function isSettingsGroupId(value: unknown): value is SettingsGroupId {
  return typeof value === "string" && SETTINGS_GROUP_IDS.has(value as SettingsGroupId);
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
