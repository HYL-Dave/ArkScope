import type { ScheduleSourceState } from "./api";
import { StatusBadge } from "./ui";

export function SourceRunProgress({
  sourceLabel,
  running,
  progress,
}: {
  sourceLabel: string;
  running: boolean;
  progress: ScheduleSourceState["progress"];
}) {
  if (!running) return null;

  const known = progress !== null
    && Number.isFinite(progress.done)
    && Number.isFinite(progress.total)
    && progress.total > 0;
  const safeDone = known ? Math.max(0, progress.done) : 0;
  const boundedDone = known ? Math.min(safeDone, progress.total) : 0;
  const percent = known
    ? Math.max(0, Math.min(100, Math.round((boundedDone / progress.total) * 100)))
    : 0;

  return (
    <div className="source-run-progress" data-progress={known ? "known" : "indeterminate"}>
      <StatusBadge state="running" label="執行中" />
      {known ? (
        <>
          <div className="source-run-current">{progress.current || "處理中"}</div>
          <div
            className="source-run-track"
            role="progressbar"
            aria-label={`${sourceLabel}執行進度`}
            aria-valuemin={0}
            aria-valuemax={progress.total}
            aria-valuenow={boundedDone}
          >
            <span className="source-run-track-fill" style={{ width: `${percent}%` }} />
          </div>
          <div className="source-run-counts muted tiny">
            {safeDone} / {progress.total} · {percent}%
          </div>
        </>
      ) : null}
    </div>
  );
}
