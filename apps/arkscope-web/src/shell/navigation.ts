export type ShellView =
  | "Home"
  | "Watchlist"
  | "Universe"
  | "News"
  | "Research"
  | "Holdings"
  | "System"
  | "Settings";

export type ShellNavIcon =
  | "dashboard"
  | "watchlist"
  | "universe"
  | "news"
  | "research"
  | "holdings"
  | "system"
  | "settings";

export interface ShellNavItem {
  view: ShellView;
  label: string;
  icon: ShellNavIcon;
}

export interface ShellNavGroup {
  label: string;
  items: readonly ShellNavItem[];
}

export const SHELL_NAV_GROUPS = [
  {
    label: "探索",
    items: [
      { view: "Home", label: "工作台", icon: "dashboard" },
      { view: "Watchlist", label: "自選股", icon: "watchlist" },
      { view: "Universe", label: "全部標的", icon: "universe" },
      { view: "News", label: "新聞·事件", icon: "news" },
    ],
  },
  {
    label: "研究",
    items: [
      { view: "Research", label: "AI 研究", icon: "research" },
    ],
  },
  {
    label: "追蹤",
    items: [
      { view: "Holdings", label: "持倉", icon: "holdings" },
    ],
  },
  {
    label: "系統",
    items: [
      { view: "System", label: "System / Health", icon: "system" },
      { view: "Settings", label: "設定", icon: "settings" },
    ],
  },
] as const satisfies readonly ShellNavGroup[];

export function shellViewLabel(view: ShellView): string {
  for (const group of SHELL_NAV_GROUPS) {
    const item = group.items.find((candidate) => candidate.view === view);
    if (item) return item.label;
  }
  throw new Error(`unknown shell view: ${String(view)}`);
}

export type EnabledSettingsSection =
  | "models"
  | "investor_profile"
  | "providers"
  | "data_storage"
  | "news_storage"
  | "macro_storage"
  | "data_sources";

export type NavigationTarget =
  | { kind: "view"; view: ShellView }
  | { kind: "ticker"; ticker: string }
  | { kind: "research_thread"; threadId: string; runId?: string }
  | { kind: "settings_section"; section: EnabledSettingsSection };

export interface NavigationRequest<T extends NavigationTarget = NavigationTarget> {
  sequence: number;
  target: T;
}

export type ResearchNavigationRequest = NavigationRequest<
  Extract<NavigationTarget, { kind: "research_thread" }>
>;

export type SettingsNavigationRequest = NavigationRequest<
  Extract<NavigationTarget, { kind: "settings_section" }>
>;

export interface ResolvedNavigationTarget {
  view?: ShellView;
  ticker?: string;
  research?: ResearchNavigationRequest;
  settings?: SettingsNavigationRequest;
}

export function nextNavigationRequest(
  currentSequence: number,
  target: NavigationTarget,
): NavigationRequest {
  return { sequence: currentSequence + 1, target };
}

export function resolveNavigationTarget(
  request: NavigationRequest,
): ResolvedNavigationTarget {
  const target = request.target;
  if (target.kind === "view") return { view: target.view };
  if (target.kind === "ticker") {
    const ticker = target.ticker.trim().toUpperCase();
    if (!ticker) throw new Error("ticker navigation target must not be empty");
    return { ticker };
  }
  if (target.kind === "research_thread") {
    return {
      view: "Research",
      research: { sequence: request.sequence, target },
    };
  }
  if (target.kind === "settings_section") {
    return {
      view: "Settings",
      settings: { sequence: request.sequence, target },
    };
  }
  const unreachable: never = target;
  throw new Error(`unsupported navigation target: ${String(unreachable)}`);
}
