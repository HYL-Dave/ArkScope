import { useRef, useState } from "react";
import type { TFunction } from "i18next";
import { ArrowRight, Bell, X } from "lucide-react";
import { useTranslation } from "react-i18next";

import { BoundedProgress, type BoundedWorkStatus } from "../ui/BoundedProgress";
import { Button, IconButton } from "../ui/Button";
import { Drawer } from "../ui/Drawer";
import type { NavigationTarget } from "./navigation";
import type { ResearchWorkItem, ResearchWorkState } from "./researchWork";
import { shellViewLabel } from "./shellLabels";

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

function stageLabel(item: ResearchWorkItem, t: TFunction<"shell">): string {
  if (item.status === "queued") return t(($) => $.backgroundWork.stages.queued);
  if (item.status === "running") return t(($) => $.backgroundWork.stages.running);
  if (item.status === "succeeded") return t(($) => $.backgroundWork.stages.succeeded);
  if (item.status === "failed") return t(($) => $.backgroundWork.stages.failed);
  return t(($) => $.backgroundWork.stages.interrupted);
}

function WorkProgress({
  item,
  researchSessionBoundMs,
}: {
  item: ResearchWorkItem;
  researchSessionBoundMs: number | null;
}) {
  const { t } = useTranslation("shell");
  const now = Date.now();
  const end = item.completedAt;
  const overallElapsed = elapsedMs(item.createdAt, end, now);
  const stageElapsed = elapsedMs(item.startedAt ?? item.createdAt, end, now);

  return (
    <BoundedProgress
      status={progressStatus(item)}
      stageLabel={stageLabel(item, t)}
      overallElapsedMs={overallElapsed}
      stageElapsedMs={stageElapsed}
      stageBoundMs={item.status === "running" ? researchSessionBoundMs : null}
      continuesAfterNavigation={true}
      canCancel={false}
      resultLabel={t(($) => $.backgroundWork.resultDestination)}
      errorTitle={item.status === "failed" ? t(($) => $.backgroundWork.stages.failed) : undefined}
      errorDetail={item.status === "failed" ? t(($) => $.backgroundWork.failureNextStep) : undefined}
    />
  );
}

export function BackgroundWorkIndicator({
  work,
  researchSessionBoundMs,
  onNavigate,
}: BackgroundWorkIndicatorProps) {
  const { t } = useTranslation("shell");
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);

  if (work.activeCount === 0 && work.attentionCount === 0) return null;

  const countLabels = [
    work.activeCount > 0 ? t(($) => $.backgroundWork.activeCount, { count: work.activeCount }) : null,
    work.attentionCount > 0
      ? t(($) => $.backgroundWork.attentionCount, { count: work.attentionCount })
      : null,
  ].filter((value) => value !== null);
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
        aria-label={t(($) => $.backgroundWork.triggerAria, { summary: triggerLabel })}
        onClick={() => setOpen(true)}
      >
        {triggerLabel}
      </Button>
      <Drawer
        open={open}
        title={t(($) => $.backgroundWork.drawerTitle)}
        onClose={() => setOpen(false)}
        returnFocusRef={triggerRef}
        footer={<span className="muted tiny">{t(($) => $.backgroundWork.sessionScope)}</span>}
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
                <strong>{item.threadTitle ?? shellViewLabel("Research", t)}</strong>
                {!isActive(item) ? (
                  <IconButton
                    label={t(($) => $.backgroundWork.dismissAria, { runId: item.runId })}
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
                {t(($) => $.backgroundWork.openConversation)}
              </Button>
            </article>
          ))}
        </div>
      </Drawer>
    </>
  );
}
