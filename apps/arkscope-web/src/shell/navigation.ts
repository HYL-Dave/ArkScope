import type { SettingsAnchorId } from "../settings/settingsRegistry";

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

export type ShellNavGroupId = "explore" | "research" | "monitor" | "system";

export interface ShellNavItem {
  view: ShellView;
  icon: ShellNavIcon;
}

export interface ShellNavGroup {
  id: ShellNavGroupId;
  items: readonly ShellNavItem[];
}

export const SHELL_NAV_GROUPS = [
  {
    id: "explore",
    items: [
      { view: "Home", icon: "dashboard" },
      { view: "Watchlist", icon: "watchlist" },
      { view: "Universe", icon: "universe" },
      { view: "News", icon: "news" },
    ],
  },
  {
    id: "research",
    items: [
      { view: "Research", icon: "research" },
    ],
  },
  {
    id: "monitor",
    items: [
      { view: "Holdings", icon: "holdings" },
    ],
  },
  {
    id: "system",
    items: [
      { view: "System", icon: "system" },
      { view: "Settings", icon: "settings" },
    ],
  },
] as const satisfies readonly ShellNavGroup[];

export type EnabledSettingsSection = SettingsAnchorId;

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
