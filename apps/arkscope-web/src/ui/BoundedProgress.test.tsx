/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BoundedProgress } from "./BoundedProgress";

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

async function mount(node: React.ReactNode) {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => root!.render(node));
}

afterEach(() => {
  if (root) act(() => root!.unmount());
  host?.remove();
  root = null;
  host = null;
});

const baseProps = {
  stageLabel: "模型執行",
  overallElapsedMs: 930_000,
  stageElapsedMs: 120_000,
  stageBoundMs: 900_000,
  continuesAfterNavigation: true,
  canCancel: false,
  resultLabel: "AI 卡片列表",
};

describe("BoundedProgress", () => {
  it("shows_overall_and_stage_elapsed_without_a_fake_percentage", async () => {
    await mount(<BoundedProgress {...baseProps} status="running" />);

    expect(host!.textContent).toContain("總耗時 15m 30s");
    expect(host!.textContent).toContain("階段耗時 2m 00s");
    expect(host!.textContent).not.toContain("930 / 900");
    expect(host!.textContent).not.toContain("%");
    expect(host!.textContent).not.toContain("ETA");
    expect(host!.querySelector('[role="progressbar"]')).toBeNull();
  });

  it("labels_the_bound_as_belonging_to_the_current_stage", async () => {
    await mount(
      <BoundedProgress
        {...baseProps}
        status="running"
        stageElapsedMs={300_000}
        stageBoundMs={600_000}
      />,
    );

    expect(host!.textContent).toContain("階段耗時 5m 00s");
    expect(host!.textContent).toContain("本階段上界 10m 00s");
    expect(host!.textContent).not.toContain("總耗時 5m 00s");
  });

  it("enters_server_confirmation_grace_at_the_stage_bound", async () => {
    await mount(
      <BoundedProgress
        {...baseProps}
        status="running"
        stageElapsedMs={900_000}
        stageBoundMs={900_000}
      />,
    );

    expect(host!.textContent).toContain("已達上界，等待伺服器確認");
    expect(host!.querySelector('[data-progress-phase="awaiting-confirmation"]')).not.toBeNull();
    expect(host!.querySelector(".ui-bounded-progress")?.hasAttribute("aria-live")).toBe(false);
    expect(host!.querySelector('[role="status"][aria-live="polite"]')?.textContent)
      .toContain("已達上界");
  });

  it("does_not_enter_grace_before_the_stage_bound", async () => {
    await mount(
      <BoundedProgress
        {...baseProps}
        status="running"
        stageElapsedMs={899_999}
        stageBoundMs={900_000}
      />,
    );

    expect(host!.querySelector('[data-progress-phase="awaiting-confirmation"]')).toBeNull();
    expect(host!.textContent).not.toContain("等待伺服器確認");
    expect(host!.querySelector('[role="status"][aria-live="polite"]')).toBeNull();
  });

  it("shows_navigation_cancel_and_result_ownership_truthfully", async () => {
    const onCancel = vi.fn();
    await mount(
      <BoundedProgress
        {...baseProps}
        status="running"
        canCancel
        onCancel={onCancel}
      />,
    );

    expect(host!.textContent).toContain("離開頁面後繼續");
    expect(host!.textContent).toContain("結果：AI 卡片列表");
    const cancel = host!.querySelector("button")!;
    expect(cancel.textContent).toContain("停止");
    await act(async () => cancel.click());
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("states_when_running_work_cannot_be_cancelled_here", async () => {
    await mount(<BoundedProgress {...baseProps} status="running" />);

    expect(host!.textContent).toContain("無法從此處取消");
    expect(host!.querySelector("button")).toBeNull();
  });

  it("does_not_claim_terminal_work_can_still_be_cancelled", async () => {
    await mount(
      <BoundedProgress
        {...baseProps}
        status="succeeded"
        canCancel
        onCancel={vi.fn()}
      />,
    );

    expect(host!.textContent).toContain("無法從此處取消");
    expect(host!.textContent).not.toContain("可從此處取消");
    expect(host!.querySelector("button")).toBeNull();
  });

  it("renders_a_typed_terminal_failure_without_a_progress_bar", async () => {
    await mount(
      <BoundedProgress
        {...baseProps}
        status="failed"
        errorTitle="模型執行失敗"
        errorDetail="伺服器拒絕了這次工作。"
      />,
    );

    expect(host!.querySelector('[role="alert"][data-state="failed"]')).not.toBeNull();
    expect(host!.textContent).toContain("模型執行失敗");
    expect(host!.textContent).toContain("伺服器拒絕了這次工作。");
    expect(host!.textContent).toContain("結果：AI 卡片列表");
    expect(host!.querySelector('[role="progressbar"]')).toBeNull();
    expect(host!.querySelector('[aria-live]')).toBeNull();
  });

  it("maps_cancelled_work_to_interrupted", async () => {
    await mount(<BoundedProgress {...baseProps} status="interrupted" />);

    expect(host!.querySelector('[data-state="interrupted"]')).not.toBeNull();
    expect(host!.textContent).toContain("工作已中止");
    expect(host!.querySelector('[role="status"][aria-live="polite"]')?.textContent)
      .toContain("工作已中止");
    expect(host!.querySelector('[role="progressbar"]')).toBeNull();
  });
});
