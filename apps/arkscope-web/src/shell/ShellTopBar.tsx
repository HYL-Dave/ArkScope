import type { ReactNode } from "react";

import type { StatusState } from "../Dashboard";
import type { NavigationTarget } from "./navigation";

export interface ShellDiagnostics {
  apiBase: string;
  toolsRegistered: number | null;
  lastStatusAt: string | null;
  cardModel: string | null;
}

export interface ShellTopBarProps {
  contextLabel: string;
  status: StatusState;
  developerMode: boolean;
  diagnostics: ShellDiagnostics;
  workControl?: ReactNode;
  onNavigate: (target: NavigationTarget) => void;
  menuControl?: ReactNode;
}

function diagnosticValue(value: string | number | null): string {
  return value === null || value === "" ? "—" : String(value);
}

export function ShellTopBar({
  contextLabel,
  status,
  developerMode,
  diagnostics,
  workControl,
  onNavigate,
  menuControl,
}: ShellTopBarProps) {
  const health = status.kind === "ready"
    ? <span>Sidecar 已連線</span>
    : status.kind === "error"
      ? (
        <button
          type="button"
          className="shell-health-action"
          onClick={() => onNavigate({ kind: "view", view: "System" })}
        >
          Sidecar 無法連線
        </button>
      )
      : <span>正在連線</span>;

  return (
    <header className={`topbar shell-topbar ${developerMode ? "developer" : "normal"}`}>
      <div className="shell-topbar-primary">
        {menuControl}
        <span className="brand shell-topbar-identity" data-testid="shell-identity">ArkScope</span>
        <span className="shell-topbar-context" data-testid="shell-context">{contextLabel}</span>
        <span className={`shell-topbar-health ${status.kind}`} data-testid="shell-health">
          {health}
        </span>
        <span className="spacer" />
        {workControl ? <span data-testid="shell-work-slot">{workControl}</span> : null}
      </div>
      {developerMode ? (
        <div
          className="shell-topbar-diagnostics"
          data-testid="shell-diagnostics"
          aria-label="Developer diagnostics"
        >
          <span>Developer diagnostics</span>
          <span>API {diagnosticValue(diagnostics.apiBase)}</span>
          <span>Tools {diagnosticValue(diagnostics.toolsRegistered)}</span>
          <span>Last status {diagnosticValue(diagnostics.lastStatusAt)}</span>
          <span>Card model {diagnosticValue(diagnostics.cardModel)}</span>
        </div>
      ) : null}
    </header>
  );
}
