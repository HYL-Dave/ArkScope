import { Square } from "lucide-react";
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
  const awaitingConfirmation = status === "running"
    && stageBoundMs != null
    && stageElapsedMs >= stageBoundMs;
  const phase = awaitingConfirmation ? "awaiting-confirmation" : status;
  const announcement = awaitingConfirmation
    ? "已達上界，等待伺服器確認"
    : status === "succeeded"
      ? "工作完成"
      : status === "interrupted"
        ? "工作已中止"
        : null;

  if (status === "failed") {
    return (
      <InlineAlert state="failed" title={errorTitle ?? "工作失敗"}>
        <div>{errorDetail ?? "工作未完成，請依錯誤指示處理。"}</div>
        <div>結果：{resultLabel}</div>
      </InlineAlert>
    );
  }

  return (
    <section className="ui-bounded-progress" data-progress-phase={phase}>
      <div className="ui-bounded-progress-head">
        <StatusBadge state={stateFor(status)} label={stageLabel} />
        <span className="ui-bounded-progress-overall">總耗時 {formatElapsed(overallElapsedMs)}</span>
      </div>
      <div className="ui-bounded-progress-stage">
        <span>階段耗時 {formatElapsed(stageElapsedMs)}</span>
        {stageBoundMs != null ? <span>本階段上界 {formatElapsed(stageBoundMs)}</span> : null}
      </div>
      {awaitingConfirmation ? (
        <div className="ui-bounded-progress-grace">已達上界，等待伺服器確認</div>
      ) : null}
      {announcement ? (
        <span className="ui-visually-hidden" role="status" aria-live="polite">
          {announcement}
        </span>
      ) : null}
      <div className="ui-bounded-progress-meta">
        <span>{continuesAfterNavigation ? "離開頁面後繼續" : "離開頁面後不保證追蹤"}</span>
        <span>結果：{resultLabel}</span>
      </div>
      {status === "running" && canCancel && onCancel ? (
        <Button tone="danger" size="compact" icon={<Square size={13} />} onClick={onCancel}>
          停止
        </Button>
      ) : null}
    </section>
  );
}
