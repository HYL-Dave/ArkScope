/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { BackgroundWorkIndicator } from "./BackgroundWorkIndicator";
import type { NavigationTarget } from "./navigation";
import type { ResearchWorkItem, ResearchWorkState } from "./researchWork";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

function item(
  status: ResearchWorkItem["status"],
  overrides: Partial<ResearchWorkItem> = {},
): ResearchWorkItem {
  return {
    runId: `run-${status}`,
    threadId: `thread-${status}`,
    threadTitle: `${status} research`,
    status,
    createdAt: "2026-07-17T00:00:00Z",
    startedAt: status === "queued" ? null : "2026-07-17T00:01:00Z",
    completedAt: ["queued", "running"].includes(status) ? null : "2026-07-17T00:02:00Z",
    ...overrides,
  };
}

function workState(
  items: ResearchWorkItem[],
  overrides: Partial<ResearchWorkState> = {},
): ResearchWorkState {
  const activeCount = items.filter((entry) => ["queued", "running"].includes(entry.status)).length;
  return {
    items,
    activeCount,
    attentionCount: items.length - activeCount,
    refresh: vi.fn(async () => {}),
    observeRun: vi.fn(),
    dismiss: vi.fn(),
    ...overrides,
  };
}

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

async function renderIndicator({
  work = workState([]),
  researchSessionBoundMs = 900_000,
  onNavigate = vi.fn(),
}: {
  work?: ResearchWorkState;
  researchSessionBoundMs?: number | null;
  onNavigate?: (target: NavigationTarget) => void;
} = {}) {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);

  const render = async (nextWork = work) => {
    await act(async () => {
      root!.render(
        <BackgroundWorkIndicator
          work={nextWork}
          researchSessionBoundMs={researchSessionBoundMs}
          onNavigate={onNavigate}
        />,
      );
    });
  };
  await render();
  return { host, work, onNavigate, render };
}

async function click(element: Element) {
  await act(async () => {
    element.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  });
}

async function openDrawer() {
  const trigger = host?.querySelector("[data-testid='background-work-trigger']");
  expect(trigger).not.toBeNull();
  await click(trigger!);
  return trigger as HTMLElement;
}

afterEach(() => {
  if (root) act(() => root!.unmount());
  root = null;
  host?.remove();
  host = null;
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("BackgroundWorkIndicator", () => {
  it("renders no control and no reserved drawer width for an empty registry", async () => {
    const { host } = await renderIndicator();

    expect(host.childElementCount).toBe(0);
    expect(document.body.querySelector("[role='dialog']")).toBeNull();
  });

  it("labels one control with separate active and attention counts", async () => {
    const { host, render } = await renderIndicator({ work: workState([item("running")]) });
    let trigger = host.querySelector("[data-testid='background-work-trigger']");
    expect(trigger?.textContent).toContain("執行中 1");
    expect(host.querySelectorAll("[data-testid='background-work-trigger']")).toHaveLength(1);

    await render(workState([item("succeeded")]));
    trigger = host.querySelector("[data-testid='background-work-trigger']");
    expect(trigger?.textContent).toContain("待查看 1");
    expect(host.querySelectorAll("[data-testid='background-work-trigger']")).toHaveLength(1);
  });

  it("opens a transient Drawer and returns focus to the trigger on close", async () => {
    await renderIndicator({ work: workState([item("running")]) });
    const trigger = host!.querySelector("[data-testid='background-work-trigger']") as HTMLElement;
    trigger.focus();
    await click(trigger);

    expect(document.body.querySelector("[role='dialog']")?.textContent).toContain("背景工作");
    const close = document.body.querySelector("button[aria-label='關閉']");
    expect(document.activeElement).toBe(close);
    await click(close!);
    expect(document.body.querySelector("[role='dialog']")).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });

  it("renders queued work without a fabricated stage bound", async () => {
    await renderIndicator({ work: workState([item("queued")]) });
    await openDrawer();
    const row = document.body.querySelector("[data-work-run-id='run-queued']");

    expect(row?.textContent).toContain("等待執行");
    expect(row?.textContent).not.toContain("本階段上界");
  });

  it("renders running work against the configured Research session bound", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-17T00:01:10Z"));
    await renderIndicator({ work: workState([item("running")]), researchSessionBoundMs: 900_000 });
    await openDrawer();
    const row = document.body.querySelector("[data-work-run-id='run-running']");

    expect(row?.textContent).toContain("AI 研究執行中");
    expect(row?.textContent).toContain("本階段上界 15m 00s");
    expect(row?.textContent).toContain("階段耗時 10s");
  });

  it("renders succeeded failed and interrupted rows with common states", async () => {
    await renderIndicator({ work: workState([
      item("succeeded"),
      item("failed"),
      item("interrupted"),
    ]) });
    await openDrawer();

    expect(document.body.textContent).toContain("研究完成");
    expect(document.body.textContent).toContain("研究未完成");
    expect(document.body.textContent).toContain("研究已中止");
  });

  it("never renders raw run errors answers credential identifiers or token usage", async () => {
    const rawValues = [
      "private-run-error",
      "private-answer",
      "local:private-credential",
      "input_tokens",
    ];
    const unsafe = {
      ...item("failed"),
      error: rawValues[0],
      answer: rawValues[1],
      credential_id: rawValues[2],
      token_usage: { input_tokens: 100 },
    } as ResearchWorkItem;
    await renderIndicator({ work: workState([unsafe]) });
    await openDrawer();

    for (const value of rawValues) expect(document.body.textContent).not.toContain(value);
  });

  it("navigates to the exact owning Research thread and optional run", async () => {
    const onNavigate = vi.fn<(target: NavigationTarget) => void>();
    await renderIndicator({
      work: workState([item("running", { runId: "run-exact", threadId: "thread-exact" })]),
      onNavigate,
    });
    await openDrawer();
    await click(document.body.querySelector("[data-work-run-id='run-exact'] [data-work-open]")!);

    expect(onNavigate).toHaveBeenCalledWith({
      kind: "research_thread",
      threadId: "thread-exact",
      runId: "run-exact",
    });
    expect(document.body.querySelector("[role='dialog']")).toBeNull();
  });

  it("marks terminal attention handled only after navigation or explicit dismissal", async () => {
    const dismiss = vi.fn();
    const onNavigate = vi.fn<(target: NavigationTarget) => void>();
    await renderIndicator({
      work: workState([
        item("succeeded", { runId: "open-terminal", threadId: "open-thread" }),
        item("failed", { runId: "dismiss-terminal", threadId: "dismiss-thread" }),
      ], { dismiss }),
      onNavigate,
    });
    await openDrawer();
    expect(dismiss).not.toHaveBeenCalled();

    await click(document.body.querySelector("[data-work-run-id='open-terminal'] [data-work-open]")!);
    expect(onNavigate).toHaveBeenCalledOnce();
    expect(dismiss).toHaveBeenCalledWith("open-terminal");
    expect(onNavigate.mock.invocationCallOrder[0]).toBeLessThan(dismiss.mock.invocationCallOrder[0]);

    await openDrawer();
    await click(document.body.querySelector("button[aria-label='忽略 dismiss-terminal']")!);
    expect(dismiss).toHaveBeenCalledWith("dismiss-terminal");
    expect(onNavigate).toHaveBeenCalledOnce();
  });

  it("contains no global cancel action and explains that work continues after navigation", async () => {
    await renderIndicator({ work: workState([item("running")]) });
    await openDrawer();
    const dialog = document.body.querySelector("[role='dialog']");

    expect(dialog?.textContent).toContain("離開頁面後繼續");
    expect(dialog?.textContent).toContain("結果：結果留在 AI 研究對話");
    expect(Array.from(dialog?.querySelectorAll("button") ?? [], (button) => button.textContent)).not.toContain("停止");
  });
});
