// Pure display helpers for the Settings → Models route authority UX (slice ⑤).
// The model route resolves through real env > DB > yaml > default; the badge tells the
// user WHICH authority a row currently comes from so "save" / "reset" aren't a black box.
import type { TaskRoute } from "./api";
import { settingsRouteSourceLabel, type SettingsT } from "./settings/settingsCopy";

export type RouteSource = TaskRoute["source"]; // "env" | "db" | "profile" | "default"
export type RouteBadgeTone = "active" | "fallback" | "override" | "default";

// Source badge: DB = the app-saved authority; profile = user_profile.local.yaml fallback
// (DB empty); env = an operator ARKSCOPE_* var that outranks the DB; default = built-in seed.
export function routeSourceBadge(
  source: RouteSource,
  t: SettingsT,
): { label: string; tone: RouteBadgeTone } {
  switch (source) {
    case "db":
      return { label: settingsRouteSourceLabel(source, t), tone: "active" };
    case "profile":
      return { label: settingsRouteSourceLabel(source, t), tone: "fallback" };
    case "env":
      return { label: settingsRouteSourceLabel(source, t), tone: "override" };
    case "default":
    default:
      return { label: settingsRouteSourceLabel(source, t), tone: "default" };
  }
}

// A route can be "reset to fallback" only when it has a DB row to remove — i.e. its
// resolved source is the DB. yaml/default rows have no DB row; an env override isn't
// cleared by the reset endpoint (it removes the DB row only), so offering reset there
// would mislead (the env var would still win).
export function routeIsOverridable(source: RouteSource): boolean {
  return source === "db";
}
