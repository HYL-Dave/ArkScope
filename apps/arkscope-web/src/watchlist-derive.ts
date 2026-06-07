// Shared 自選股 derivation — one definition of "work-list" and "All Active" so
// the 自選股 rail, the 全部標的 list filter, and the Home overview never drift
// (they previously diverged: Home used the old cockpit-17 DTO).

import { type UniverseRow, type WatchlistSummary } from "./api";

// The user's work-lists are the custom-kind lists; classification (tier/theme/…)
// lives in tags, not lists.
export function customListNameSet(lists: WatchlistSummary[]): Set<string> {
  return new Set(lists.filter((l) => l.kind === "custom").map((l) => l.name));
}

// "All Active" = universe rows with >=1 ACTIVE membership in a custom work-list.
export function allActiveRows(rows: UniverseRow[], lists: WatchlistSummary[]): UniverseRow[] {
  const names = customListNameSet(lists);
  if (names.size === 0) return [];
  return rows.filter((r) => r.lists.some((n) => names.has(n)));
}
