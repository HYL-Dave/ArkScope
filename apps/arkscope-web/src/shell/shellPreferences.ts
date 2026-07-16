export const DEVELOPER_MODE_STORAGE_KEY = "arkscope.shell.developerMode.v1";

export function readDeveloperMode(
  storage: Pick<Storage, "getItem"> = window.localStorage,
): boolean {
  try {
    return storage.getItem(DEVELOPER_MODE_STORAGE_KEY) === "enabled";
  } catch {
    return false;
  }
}

export function writeDeveloperMode(
  enabled: boolean,
  storage: Pick<Storage, "setItem"> = window.localStorage,
): void {
  try {
    storage.setItem(DEVELOPER_MODE_STORAGE_KEY, enabled ? "enabled" : "disabled");
  } catch {
    // React state remains authoritative for this browser session.
  }
}
