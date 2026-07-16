import { useRef, useState } from "react";
import { ArrowRight, Bell, X } from "lucide-react";

import { BoundedProgress, type BoundedWorkStatus } from "../ui/BoundedProgress";
import { Button, IconButton } from "../ui/Button";
import { Drawer } from "../ui/Drawer";
import type { NavigationTarget } from "./navigation";
import type { ResearchWorkItem, ResearchWorkState } from "./researchWork";

export interface BackgroundWorkIndicatorProps {
  work: ResearchWorkState;
  researchSessionBoundMs: number | null;
  onNavigate: (target: NavigationTarget) => void;
}

function isActive(item: ResearchWorkItem): boolean {
  return item.status === "queued" || item.status === "running";
}

function timestampMs(value: string | null | undefined, fallback: number): number {
  const parsed = value ? Date.parse(value) : Number.NaN;
  return Number.isFinite(parsed) ? parsed : fallback;
}

function elapsedMs(start: string | null | undefined, end: string | null | undefined, now: number): number {
  const startMs = timestampMs(start, now);
  const endMs = timestampMs(end, now);
  return Math.max(0, endMs - startMs);
}

function progressStatus(item: ResearchWorkItem): BoundedWorkStatus {
  if (item.status === "queued" || item.status === "running") return "running";
  if (item.status === "succeeded") return "succeeded";
  if (item.status === "failed") return "failed";
  return "interrupted";
}

function stageLabel(item: ResearchWorkItem): string {
  if (item.status === "queued") return "等待執行";
  if (item.status === "running") return "AI 研究執行中";
  if (item.status === "succeeded") return "研究完成";
  if (item.status === "failed") return "研究未完成";
  return "研究已中止";
}

function WorkProgress({
  item,
  researchSessionBoundMs,
}: {
  item: ResearchWorkItem;
  researchSessionBoundMs: number | null;
}) {
  const now = Date.now();
  const end = item.completedAt;
  const overallElapsed = elapsedMs(item.createdAt, end, now);
  const stageElapsed = elapsedMs(item.startedAt ?? item.createdAt, end, now);

  return (
    <BoundedProgress
      status={progressStatus(item)}
      stageLabel={stageLabel(item)}
      overallElapsedMs={overallElapsed}
      stageElapsedMs={stageElapsed}
      stageBoundMs={item.status === "running" ? researchSessionBoundMs : null}
      continuesAfterNavigation={true}
      canCancel={false}
      resultLabel="結果留在 AI 研究對話"
      errorTitle={item.status === "failed" ? "研究未完成" : undefined}
      errorDetail={item.status === "failed" ? "開啟原對話查看可採取的下一步。" : undefined}
    />
  );
}

export function BackgroundWorkIndicator({
  work,
  researchSessionBoundMs,
  onNavigate,
}: BackgroundWorkIndicatorProps) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);

  if (work.activeCount === 0 && work.attentionCount === 0) return null;

  const countLabels = [
    work.activeCount > 0 ? `執行中 ${work.activeCount}` : null,
    work.attentionCount > 0 ? `待查看 ${work.attentionCount}` : null,
  ].filter((value): value is string => value !== null);
  const triggerLabel = countLabels.join(" · ");

  const navigateToWork = (item: ResearchWorkItem) => {
    onNavigate({
      kind: "research_thread",
      threadId: item.threadId,
      runId: item.runId,
    });
    if (!isActive(item)) work.dismiss(item.runId);
    setOpen(false);
  };

  return (
    <>
      <Button
        ref={triggerRef}
        data-testid="background-work-trigger"
        size="compact"
        tone="ghost"
        icon={<Bell size={15} />}
        aria-label={`AI 研究背景工作：${triggerLabel}`}
        onClick={() => setOpen(true)}
      >
        {triggerLabel}
      </Button>
      <Drawer
        open={open}
        title="背景工作"
        onClose={() => setOpen(false)}
        returnFocusRef={triggerRef}
        footer={<span className="muted tiny">僅顯示此桌面工作階段觀察到的 AI 研究。</span>}
      >
        <div className="shell-work-list">
          {work.items.map((item) => (
            <article
              key={item.runId}
              className="shell-work-row"
              data-work-run-id={item.runId}
              data-work-status={item.status}
            >
              <div className="shell-work-row-head">
                <strong>{item.threadTitle}</strong>
                {!isActive(item) ? (
                  <IconButton
                    label={`忽略 ${item.runId}`}
                    tone="ghost"
                    size="compact"
                    icon={<X size={14} />}
                    onClick={() => work.dismiss(item.runId)}
                  />
                ) : null}
              </div>
              <WorkProgress item={item} researchSessionBoundMs={researchSessionBoundMs} />
              <Button
                className="shell-work-open"
                data-work-open
                size="compact"
                tone="secondary"
                icon={<ArrowRight size={14} />}
                onClick={() => navigateToWork(item)}
              >
                開啟對話
              </Button>
            </article>
          ))}
        </div>
      </Drawer>
    </>
  );
}
