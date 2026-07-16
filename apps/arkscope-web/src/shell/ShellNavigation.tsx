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

import {
  SHELL_NAV_GROUPS,
  type NavigationTarget,
  type ShellNavIcon,
  type ShellView,
} from "./navigation";

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
  return (
    <div className="app-shell-nav-groups">
      {SHELL_NAV_GROUPS.map((group) => (
        <section className="app-shell-nav-group" key={group.label}>
          <div className="app-shell-nav-group-label" data-shell-nav-group>
            {group.label}
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
                  <span>{item.label}</span>
                </button>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}
