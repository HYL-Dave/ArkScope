import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import type { NavigationTarget } from "../shell/navigation";
import { Button, InlineAlert } from "../ui";
import {
  presentExploreError,
  type ExploreDiagnosticRow,
  type ExploreErrorState,
} from "./explorePresentation";

export type ExploreErrorNoticeProps = {
  state: ExploreErrorState;
  developerMode: boolean;
  retryLabel: ReactNode;
  onRetry: () => void;
  onNavigate?: (target: NavigationTarget) => void;
};

export function ExploreErrorNotice({
  state,
  developerMode,
  retryLabel,
  onRetry,
  onNavigate,
}: ExploreErrorNoticeProps) {
  const { t } = useTranslation("explore");
  const presentation = presentExploreError(state, t);
  const recovery = onNavigate ? presentation.recovery : null;
  const diagnosticRows = [
    presentation.diagnostics.status,
    presentation.diagnostics.code,
    presentation.diagnostics.path,
    presentation.diagnostics.detail,
  ].filter((row): row is ExploreDiagnosticRow => row !== null);

  return (
    <InlineAlert
      state="failed"
      title={presentation.title}
      action={(
        <>
          <Button size="compact" onClick={onRetry}>{retryLabel}</Button>
          {recovery ? (
            <Button
              size="compact"
              onClick={() => onNavigate?.(recovery.target)}
            >
              {recovery.label}
            </Button>
          ) : null}
        </>
      )}
    >
      {recovery ? <p>{recovery.prompt}</p> : null}
      {developerMode ? (
        <section aria-label={presentation.diagnostics.title}>
          <strong>{presentation.diagnostics.title}</strong>
          {diagnosticRows.length > 0 ? (
            <dl>
              {diagnosticRows.map((row) => (
                <div key={row.label}>
                  <dt>{row.label}</dt>
                  <dd><code>{row.value}</code></dd>
                </div>
              ))}
            </dl>
          ) : null}
          {presentation.diagnostics.detailOmitted ? (
            <p>{presentation.diagnostics.detailOmitted}</p>
          ) : null}
        </section>
      ) : null}
    </InlineAlert>
  );
}
