export interface SettingsNavigationGuard {
  readonly dirty: boolean;
  readonly busy: boolean;
  readonly reason: string | null;
}

export type SettingsNavigationGuardReporter = (guard: SettingsNavigationGuard) => void;

export const CLEAR_SETTINGS_NAVIGATION_GUARD: SettingsNavigationGuard = Object.freeze({
  dirty: false,
  busy: false,
  reason: null,
});
