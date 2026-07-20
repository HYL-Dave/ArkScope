import {
  Activity,
  BriefcaseBusiness,
  LayoutDashboard,
  ListFilter,
  Newspaper,
  Search,
  Settings,
  Star,
  type LucideIcon,
} from "lucide-react";
import { useTranslation } from "react-i18next";

import {
  SHELL_NAV_GROUPS,
  type NavigationTarget,
  type ShellNavIcon,
  type ShellView,
} from "./navigation";
import { shellNavGroupLabel, shellViewLabel } from "./shellLabels";

const ICONS: Record<ShellNavIcon, LucideIcon> = {
  dashboard: LayoutDashboard,
  watchlist: Star,
  universe: ListFilter,
  news: Newspaper,
  research: Search,
  holdings: BriefcaseBusiness,
  system: Activity,
  settings: Settings,
};

export interface ShellNavigationProps {
  currentView: ShellView;
  onNavigate: (target: NavigationTarget) => void;
  onAfterNavigate?: () => void;
}

export function ShellNavigation({
  currentView,
  onNavigate,
  onAfterNavigate,
}: ShellNavigationProps) {
  const { t } = useTranslation("shell");

  return (
    <div className="app-shell-nav-groups">
      {SHELL_NAV_GROUPS.map((group) => (
        <section className="app-shell-nav-group" key={group.id}>
          <div className="app-shell-nav-group-label" data-shell-nav-group>
            {shellNavGroupLabel(group.id, t)}
          </div>
          <div className="app-shell-nav-items">
            {group.items.map((item) => {
              const Icon = ICONS[item.icon];
              return (
                <button
                  key={item.view}
                  type="button"
                  className="app-shell-nav-item"
                  aria-current={currentView === item.view ? "page" : undefined}
                  onClick={() => {
                    onNavigate({ kind: "view", view: item.view });
                    onAfterNavigate?.();
                  }}
                >
                  <Icon size={16} aria-hidden="true" />
                  <span>{shellViewLabel(item.view, t)}</span>
                </button>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}
