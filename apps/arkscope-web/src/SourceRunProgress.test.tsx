/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it } from "vitest";

import { SourceRunProgress } from "./SourceRunProgress";

let host: HTMLDivElement | null = null;
let root: ReturnType<typeof createRoot> | null = null;

async function mount(progress: { done: number; total: number; current: string } | null) {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(
      <SourceRunProgress
        sourceLabel="IBKR 即時股價"
        running
        progress={progress}
      />,
    );
  });
  return host;
}

afterEach(() => {
  if (root) act(() => root!.unmount());
  host?.remove();
  root = null;
  host = null;
});

describe("SourceRunProgress", () => {
  it("renders_known_progress_on_separate_lines_with_real_aria_values", async () => {
    const node = await mount({
      done: 7,
      total: 10,
      current: "BRK.B — unusually long current contract label that must wrap",
    });
    expect(node.querySelector(".source-run-current")?.textContent).toContain("BRK.B");
    expect(node.querySelector(".source-run-counts")?.textContent).toBe("7 / 10 · 70%");
    const bar = node.querySelector<HTMLElement>("[role='progressbar']");
    expect(bar?.getAttribute("aria-label")).toBe("IBKR 即時股價執行進度");
    expect(bar?.getAttribute("aria-valuemin")).toBe("0");
    expect(bar?.getAttribute("aria-valuemax")).toBe("10");
    expect(bar?.getAttribute("aria-valuenow")).toBe("7");
  });

  it("clamps_the_visual_percentage_without_inventing_a_count", async () => {
    const node = await mount({ done: 12, total: 10, current: "NVDA" });
    expect(node.querySelector(".source-run-counts")?.textContent).toBe("12 / 10 · 100%");
    expect(node.querySelector<HTMLElement>(".source-run-track-fill")?.style.width).toBe("100%");
    expect(node.querySelector("[role='progressbar']")?.getAttribute("aria-valuenow")).toBe("10");
  });

  it("renders_missing_progress_as_indeterminate_without_a_live_region", async () => {
    const node = await mount(null);
    expect(node.textContent).toContain("執行中");
    expect(node.querySelector("[role='progressbar']")).toBeNull();
    expect(node.querySelector("[aria-live]")).toBeNull();
    expect(node.querySelector(".source-run-current")).toBeNull();
  });

  it("treats_zero_or_negative_totals_as_indeterminate", async () => {
    for (const total of [0, -1]) {
      if (root) act(() => root!.unmount());
      host?.remove();
      root = null;
      host = null;
      const node = await mount({ done: 1, total, current: "AAPL" });
      expect(node.querySelector("[role='progressbar']")).toBeNull();
      expect(node.textContent).toContain("執行中");
    }
  });
});
