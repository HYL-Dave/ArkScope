import { Square } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Button } from "./Button";
import { InlineAlert, StatusBadge, type CommonUiState } from "./Status";

export type BoundedWorkStatus = "running" | "succeeded" | "failed" | "interrupted";

function stateFor(status: BoundedWorkStatus): CommonUiState {
  if (status === "succeeded") return "ready";
  return status;
}

export function formatElapsed(ms: number): string {
  const seconds = Math.max(0, Math.floor(ms / 1000));
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return minutes > 0 ? `${minutes}m ${String(rest).padStart(2, "0")}s` : `${rest}s`;
}

export function BoundedProgress({
  status,
  stageLabel,
  overallElapsedMs,
  stageElapsedMs,
  stageBoundMs,
  continuesAfterNavigation,
  canCancel,
  resultLabel,
  onCancel,
  errorTitle,
  errorDetail,
}: {
  status: BoundedWorkStatus;
  stageLabel: string;
  overallElapsedMs: number;
  stageElapsedMs: number;
  stageBoundMs?: number | null;
  continuesAfterNavigation: boolean;
  canCancel: boolean;
  resultLabel: string;
  onCancel?: () => void;
  errorTitle?: string;
  errorDetail?: string;
}) {
  const { t } = useTranslation("common");
  const awaitingConfirmation = status === "running"
    && stageBoundMs != null
    && stageElapsedMs >= stageBoundMs;
  const phase = awaitingConfirmation ? "awaiting-confirmation" : status;
  const cancellationAvailable = status === "running" && canCancel && Boolean(onCancel);
  const announcement = awaitingConfirmation
    ? t(($) => $.boundedProgress.awaitingConfirmation)
    : status === "succeeded"
      ? t(($) => $.boundedProgress.completedAnnouncement)
      : status === "interrupted"
        ? t(($) => $.boundedProgress.interruptedAnnouncement)
        : null;

  if (status === "failed") {
    return (
      <InlineAlert
        state="failed"
        title={errorTitle ?? t(($) => $.boundedProgress.failureTitle)}
      >
        <div>{errorDetail ?? t(($) => $.boundedProgress.failureDetail)}</div>
        <div>{t(($) => $.boundedProgress.result, { destination: resultLabel })}</div>
      </InlineAlert>
    );
  }

  return (
    <section className="ui-bounded-progress" data-progress-phase={phase}>
      <div className="ui-bounded-progress-head">
        <StatusBadge state={stateFor(status)} label={stageLabel} />
        <span className="ui-bounded-progress-overall">
          {t(($) => $.boundedProgress.overallElapsed, {
            duration: formatElapsed(overallElapsedMs),
          })}
        </span>
      </div>
      <div className="ui-bounded-progress-stage">
        <span>
          {t(($) => $.boundedProgress.stageElapsed, {
            duration: formatElapsed(stageElapsedMs),
          })}
        </span>
        {stageBoundMs != null ? (
          <span>
            {t(($) => $.boundedProgress.stageBound, {
              duration: formatElapsed(stageBoundMs),
            })}
          </span>
        ) : null}
      </div>
      {awaitingConfirmation ? (
        <div className="ui-bounded-progress-grace">
          {t(($) => $.boundedProgress.awaitingConfirmation)}
        </div>
      ) : null}
      {announcement ? (
        <span className="ui-visually-hidden" role="status" aria-live="polite">
          {announcement}
        </span>
      ) : null}
      <div className="ui-bounded-progress-meta">
        <span>
          {continuesAfterNavigation
            ? t(($) => $.boundedProgress.continuesAfterNavigation)
            : t(($) => $.boundedProgress.trackingNotGuaranteed)}
        </span>
        <span>
          {cancellationAvailable
            ? t(($) => $.boundedProgress.cancellationAvailable)
            : t(($) => $.boundedProgress.cancellationUnavailable)}
        </span>
        <span>{t(($) => $.boundedProgress.result, { destination: resultLabel })}</span>
      </div>
      {cancellationAvailable ? (
        <Button tone="danger" size="compact" icon={<Square size={13} />} onClick={onCancel}>
          {t(($) => $.actions.stop)}
        </Button>
      ) : null}
    </section>
  );
}
