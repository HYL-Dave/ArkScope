// Pure display helpers for the Settings → Models route authority UX (slice ⑤).
// The model route resolves through real env > DB > yaml > default; the badge tells the
// user WHICH authority a row currently comes from so "save" / "reset" aren't a black box.
import type { TaskRoute } from "./api";

export type RouteSource = TaskRoute["source"]; // "env" | "db" | "profile" | "default"
export type RouteBadgeTone = "active" | "fallback" | "override" | "default";

// Source badge: DB = the app-saved authority; profile = user_profile.local.yaml fallback
// (DB empty); env = an operator ARKSCOPE_* var that outranks the DB; default = built-in seed.
export function routeSourceBadge(source: RouteSource): { label: string; tone: RouteBadgeTone } {
  switch (source) {
    case "db":
      return { label: "DB（已儲存）", tone: "active" };
    case "profile":
      return { label: "設定檔 fallback", tone: "fallback" };
    case "env":
      return { label: "env 覆蓋", tone: "override" };
    case "default":
    default:
      return { label: "內建預設", tone: "default" };
  }
}

// A route can be "reset to fallback" only when it has a DB row to remove — i.e. its
// resolved source is the DB. yaml/default rows have no DB row; an env override isn't
// cleared by the reset endpoint (it removes the DB row only), so offering reset there
// would mislead (the env var would still win).
export function routeIsOverridable(source: RouteSource): boolean {
  return source === "db";
}
