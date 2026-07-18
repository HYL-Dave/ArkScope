import { useEffect, useMemo, useState } from "react";

import type { ResearchRunDTO, RuntimeConfig } from "./api";
import { presentResearchError } from "./researchErrors";
import type { PendingTurn } from "./researchReducer";
import type { NavigationTarget } from "./shell/navigation";
import { BoundedProgress, Button, type BoundedWorkStatus } from "./ui";

export interface ResearchProgressProjection {
  status: BoundedWorkStatus;
  stage: "creating" | "queued" | "running" | "succeeded" | "failed" | "interrupted";
  stageLabel: string;
  overallElapsedMs: number;
  stageElapsedMs: number;
  stageBoundMs: number | null;
  canCancel: boolean;
  resultLabel: string;
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
      stageLabel: "建立執行",
      overallElapsedMs: elapsed(startedAt, nowMs),
      stageElapsedMs: elapsed(startedAt, nowMs),
      stageBoundMs: null,
      canCancel: false,
      resultLabel: "建立後會在此對話顯示",
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
      stageLabel: "等待執行",
      overallElapsedMs,
      stageElapsedMs: overallElapsedMs,
      stageBoundMs: null,
      canCancel: true,
      resultLabel: "完成後顯示於此對話",
      errorCode: null,
    };
  }
  if (run.status === "running") {
    const startedAt = timestampMs(run.started_at, createdAt);
    return {
      status: "running",
      stage: "running",
      stageLabel: "模型與工具執行中",
      overallElapsedMs,
      stageElapsedMs: elapsed(startedAt, nowMs),
      stageBoundMs: runtime?.research_runtime.session_timeout_s != null
        ? runtime.research_runtime.session_timeout_s * 1_000
        : null,
      canCancel: true,
      resultLabel: "完成後顯示於此對話",
      errorCode: null,
    };
  }
  if (run.status === "succeeded") {
    return {
      status: "succeeded",
      stage: "succeeded",
      stageLabel: "研究完成",
      overallElapsedMs,
      stageElapsedMs: elapsed(timestampMs(run.started_at, createdAt), completedAt),
      stageBoundMs: null,
      canCancel: false,
      resultLabel: "已保存於此對話",
      errorCode: null,
    };
  }
  if (run.status === "cancelled" || run.status === "interrupted") {
    return {
      status: "interrupted",
      stage: "interrupted",
      stageLabel: run.status === "cancelled" ? "研究已取消" : "研究已中止",
      overallElapsedMs,
      stageElapsedMs: elapsed(timestampMs(run.started_at, createdAt), completedAt),
      stageBoundMs: null,
      canCancel: false,
      resultLabel: "已取得的內容仍保留於此對話",
      errorCode: run.error_code ?? (run.status === "cancelled" ? "run_cancelled" : "run_interrupted"),
    };
  }
  return {
    status: "failed",
    stage: "failed",
    stageLabel: "研究失敗",
    overallElapsedMs,
    stageElapsedMs: elapsed(timestampMs(run.started_at, createdAt), completedAt),
    stageBoundMs: null,
    canCancel: false,
    resultLabel: "已取得的內容仍保留於此對話",
    errorCode: run.error_code ?? "provider_call_failed",
  };
}

export function ResearchRunProgress({
  pending,
  run,
  runtime,
  developerMode = false,
  onStop,
  onNavigate,
}: {
  pending: PendingTurn | null;
  run: ResearchRunDTO | null;
  runtime: RuntimeConfig | null | undefined;
  developerMode?: boolean;
  onStop: () => void;
  onNavigate?: (target: NavigationTarget) => void;
}) {
  const [nowMs, setNowMs] = useState(() => Date.now());
  const active = Boolean(pending || run?.status === "queued" || run?.status === "running");
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
  if (!projection) return null;

  const error = projection.errorCode
    ? presentResearchError({ code: projection.errorCode, detail: run?.error, developerMode })
    : null;
  return (
    <div className="research-run-progress" data-testid="research-run-progress" data-stage={projection.stage}>
      <BoundedProgress
        status={projection.status}
        stageLabel={error?.title ?? projection.stageLabel}
        overallElapsedMs={projection.overallElapsedMs}
        stageElapsedMs={projection.stageElapsedMs}
        stageBoundMs={projection.stageBoundMs}
        continuesAfterNavigation
        canCancel={projection.canCancel}
        resultLabel={projection.resultLabel}
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
          <summary>診斷細節</summary>
          <pre>{error.developerDetail}</pre>
        </details>
      ) : null}
    </div>
  );
}
