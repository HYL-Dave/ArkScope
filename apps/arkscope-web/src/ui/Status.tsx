import type { ReactNode } from "react";
import {
  Activity,
  CheckCircle2,
  Circle,
  CircleSlash2,
  LoaderCircle,
  PauseCircle,
  TriangleAlert,
  XCircle,
  type LucideIcon,
} from "lucide-react";

export const COMMON_UI_STATES = [
  "loading", "empty", "ready", "running", "partial", "stale",
  "blocked", "failed", "interrupted",
] as const;
export type CommonUiState = (typeof COMMON_UI_STATES)[number];

const ICONS: Record<CommonUiState, LucideIcon> = {
  loading: LoaderCircle,
  empty: Circle,
  ready: CheckCircle2,
  running: Activity,
  partial: TriangleAlert,
  stale: TriangleAlert,
  blocked: CircleSlash2,
  failed: XCircle,
  interrupted: PauseCircle,
};

export function StatusBadge({ state, label }: { state: CommonUiState; label: ReactNode }) {
  const Icon = ICONS[state];
  return (
    <span className="ui-status-badge" data-state={state}>
      <Icon size={13} aria-hidden="true" />
      <span>{label}</span>
    </span>
  );
}

export function InlineAlert({
  state,
  title,
  children,
  action,
}: {
  state: CommonUiState;
  title: ReactNode;
  children?: ReactNode;
  action?: ReactNode;
}) {
  const urgent = state === "failed" || state === "blocked";
  return (
    <div className="ui-inline-alert" data-state={state} role={urgent ? "alert" : "status"}>
      <StatusBadge state={state} label={title} />
      {children ? <div className="ui-inline-alert-detail">{children}</div> : null}
      {action ? <div className="ui-inline-alert-action">{action}</div> : null}
    </div>
  );
}
