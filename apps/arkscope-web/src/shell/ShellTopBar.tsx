import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

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
  const { t } = useTranslation("shell");
  const health = status.kind === "ready"
    ? <span>{t(($) => $.topbar.sidecar.ready)}</span>
    : status.kind === "error"
      ? (
        <button
          type="button"
          className="shell-health-action"
          onClick={() => onNavigate({ kind: "view", view: "System" })}
        >
          {t(($) => $.topbar.sidecar.error)}
        </button>
      )
      : <span>{t(($) => $.topbar.sidecar.loading)}</span>;

  return (
    <header className="shell-topbar" data-developer-mode={String(developerMode)}>
      <div className="shell-topbar-primary">
        {menuControl}
        <span className="shell-topbar-identity" data-testid="shell-identity">ArkScope</span>
        <span className="shell-topbar-context" data-testid="shell-context">{contextLabel}</span>
        <span className={`shell-topbar-health ${status.kind}`} data-testid="shell-health">
          {health}
        </span>
        <span className="shell-topbar-spacer" />
        {workControl ? <span data-testid="shell-work-slot">{workControl}</span> : null}
      </div>
      {developerMode ? (
        <div
          className="shell-topbar-diagnostics"
          data-testid="shell-diagnostics"
          aria-label={t(($) => $.topbar.developerDiagnostics)}
        >
          <span>{t(($) => $.topbar.developerDiagnostics)}</span>
          <span>{t(($) => $.topbar.diagnostics.apiValue, {
            value: diagnosticValue(diagnostics.apiBase),
          })}</span>
          <span>{t(($) => $.topbar.diagnostics.toolsValue, {
            value: diagnosticValue(diagnostics.toolsRegistered),
          })}</span>
          <span>{t(($) => $.topbar.diagnostics.lastStatusValue, {
            value: diagnosticValue(diagnostics.lastStatusAt),
          })}</span>
          <span>{t(($) => $.topbar.diagnostics.cardModelValue, {
            value: diagnosticValue(diagnostics.cardModel),
          })}</span>
        </div>
      ) : null}
    </header>
  );
}
