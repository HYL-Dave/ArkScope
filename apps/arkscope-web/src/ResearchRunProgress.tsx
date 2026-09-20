import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Square } from "lucide-react";

import type { ResearchRunDTO, RuntimeConfig } from "./api";
import { researchProgressCopy } from "./i18n/researchPresentation";
import { presentResearchError } from "./researchErrors";
import type { PendingTurn } from "./researchReducer";
import type { NavigationTarget } from "./shell/navigation";
import { BoundedProgress, Button, InlineAlert, type BoundedWorkStatus } from "./ui";

export interface ResearchProgressProjection {
  status: BoundedWorkStatus;
  stage: "creating" | "queued" | "running" | "succeeded" | "failed" | "interrupted" | "cancelled";
  overallElapsedMs: number;
  stageElapsedMs: number;
  stageBoundMs: number | null;
  canCancel: boolean;
  errorCode: string | null;
}

function timestampMs(value: string | null | undefined, fallback: number): number {
  if (!value) return fallback;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function elapsed(start: number, end: number): number {
  return Math.max(0, end - start);
}

export function projectResearchProgress({
  pending,
  run,
  runtime,
  nowMs,
}: {
  pending: PendingTurn | null;
  run: ResearchRunDTO | null;
  runtime: RuntimeConfig | null | undefined;
  nowMs: number;
}): ResearchProgressProjection | null {
  if (!pending && !run) return null;
  if (!run) {
    const startedAt = pending?.startedAt ?? nowMs;
    return {
      status: "running",
      stage: "creating",
      overallElapsedMs: elapsed(startedAt, nowMs),
      stageElapsedMs: elapsed(startedAt, nowMs),
      stageBoundMs: null,
      canCancel: false,
      errorCode: null,
    };
  }

  const createdAt = timestampMs(run.created_at, pending?.startedAt ?? nowMs);
  const completedAt = run.completed_at ? timestampMs(run.completed_at, nowMs) : nowMs;
  const overallElapsedMs = elapsed(createdAt, completedAt);
  if (run.status === "queued") {
    return {
      status: "running",
      stage: "queued",
      overallElapsedMs,
      stageElapsedMs: overallElapsedMs,
      stageBoundMs: null,
      canCancel: true,
      errorCode: null,
    };
  }
  if (run.status === "running") {
    const startedAt = timestampMs(run.started_at, createdAt);
    return {
      status: "running",
      stage: "running",
      overallElapsedMs,
      stageElapsedMs: elapsed(startedAt, nowMs),
      stageBoundMs: runtime?.research_runtime.session_timeout_s != null
        ? runtime.research_runtime.session_timeout_s * 1_000
        : null,
      canCancel: true,
      errorCode: null,
    };
  }
  if (run.status === "succeeded") {
    return {
      status: "succeeded",
      stage: "succeeded",
      overallElapsedMs,
      stageElapsedMs: elapsed(timestampMs(run.started_at, createdAt), completedAt),
      stageBoundMs: null,
      canCancel: false,
      errorCode: null,
    };
  }
  if (run.status === "cancelled" || run.status === "interrupted") {
    return {
      status: "interrupted",
      stage: run.status,
      overallElapsedMs,
      stageElapsedMs: elapsed(timestampMs(run.started_at, createdAt), completedAt),
      stageBoundMs: null,
      canCancel: false,
      errorCode: run.error_code ?? (run.status === "cancelled" ? "run_cancelled" : "run_interrupted"),
    };
  }
  return {
    status: "failed",
    stage: "failed",
    overallElapsedMs,
    stageElapsedMs: elapsed(timestampMs(run.started_at, createdAt), completedAt),
    stageBoundMs: null,
    canCancel: false,
    errorCode: run.error_code ?? "provider_call_failed",
  };
}

export function ResearchRunProgress({
  pending,
  run,
  runtime,
  developerMode = false,
  persistenceFailed = false,
  onStop,
  onNavigate,
}: {
  pending: PendingTurn | null;
  run: ResearchRunDTO | null;
  runtime: RuntimeConfig | null | undefined;
  developerMode?: boolean;
  persistenceFailed?: boolean;
  onStop: () => void;
  onNavigate?: (target: NavigationTarget) => void;
}) {
  const { t: researchT, i18n: researchI18n } = useTranslation("research");
  const { t: commonT } = useTranslation("common");
  const researchLocale = researchI18n.resolvedLanguage;
  const [nowMs, setNowMs] = useState(() => Date.now());
  const active = !persistenceFailed && Boolean(pending || run?.status === "queued" || run?.status === "running");
  useEffect(() => {
    if (!active) return;
    setNowMs(Date.now());
    const timer = window.setInterval(() => setNowMs(Date.now()), 1_000);
    return () => window.clearInterval(timer);
  }, [active, run?.id]);

  const projection = useMemo(
    () => projectResearchProgress({ pending, run, runtime, nowMs }),
    [nowMs, pending, run, runtime],
  );
  const progressCopy = useMemo(
    () => projection ? researchProgressCopy(projection.stage, researchT) : null,
    [projection, researchLocale, researchT],
  );
  if (persistenceFailed) {
    return (
      <div className="research-run-progress" data-testid="research-run-progress" data-stage="persistence_failed">
        <InlineAlert state="blocked" title={researchT(($) => $.errors.persistenceTitle)} action={
          <Button tone="danger" size="compact" icon={<Square size={13} />} onClick={onStop}>
            {commonT(($) => $.actions.stop)}
          </Button>
        }>
          {researchT(($) => $.errors.persistenceDetail)}
        </InlineAlert>
      </div>
    );
  }
  if (!projection || !progressCopy) return null;

  const error = projection.errorCode
    ? presentResearchError(
      { code: projection.errorCode, detail: run?.error, developerMode },
      researchT,
    )
    : null;
  if (projection.errorCode === "run_completion_unverified" && error) {
    return (
      <div className="research-run-progress" data-testid="research-run-progress" data-stage={projection.stage}>
        <InlineAlert state="interrupted" title={error.title}>{error.detail}</InlineAlert>
      </div>
    );
  }
  return (
    <div className="research-run-progress" data-testid="research-run-progress" data-stage={projection.stage}>
      <BoundedProgress
        status={projection.status}
        stageLabel={error?.title ?? progressCopy.stageLabel}
        overallElapsedMs={projection.overallElapsedMs}
        stageElapsedMs={projection.stageElapsedMs}
        stageBoundMs={projection.stageBoundMs}
        continuesAfterNavigation
        canCancel={projection.canCancel}
        resultLabel={progressCopy.resultLabel}
        onCancel={onStop}
        errorTitle={error?.title}
        errorDetail={error?.detail}
      />
      {error?.actionLabel && error.target && onNavigate ? (
        <Button
          size="compact"
          tone="secondary"
          onClick={() => onNavigate(error.target!)}
        >
          {error.actionLabel}
        </Button>
      ) : null}
      {error?.developerDetail ? (
        <details className="research-diagnostic">
          <summary>{researchT(($) => $.progress.diagnosticDetails)}</summary>
          <pre>{error.developerDetail}</pre>
        </details>
      ) : null}
    </div>
  );
}
