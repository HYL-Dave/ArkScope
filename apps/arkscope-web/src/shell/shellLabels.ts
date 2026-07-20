import type { TFunction } from "i18next";

import type { ShellNavGroupId, ShellView } from "./navigation";

type ShellT = TFunction<"shell">;

export function shellNavGroupLabel(id: ShellNavGroupId, t: ShellT): string {
  switch (id) {
    case "explore": return t(($) => $.navigation.groups.explore);
    case "research": return t(($) => $.navigation.groups.research);
    case "monitor": return t(($) => $.navigation.groups.monitor);
    case "system": return t(($) => $.navigation.groups.system);
  }
}

export function shellViewLabel(view: ShellView, t: ShellT): string {
  switch (view) {
    case "Home": return t(($) => $.navigation.views.home);
    case "Watchlist": return t(($) => $.navigation.views.watchlist);
    case "Universe": return t(($) => $.navigation.views.universe);
    case "News": return t(($) => $.navigation.views.news);
    case "Research": return t(($) => $.navigation.views.research);
    case "Holdings": return t(($) => $.navigation.views.holdings);
    case "System": return t(($) => $.navigation.views.system);
    case "Settings": return t(($) => $.navigation.views.settings);
  }
}
