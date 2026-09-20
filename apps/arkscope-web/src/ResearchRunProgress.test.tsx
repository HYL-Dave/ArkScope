/** @vitest-environment jsdom */
import React, { type ComponentProps } from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import i18n from "i18next";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ResearchRunDTO, RuntimeConfig } from "./api";
import { ResearchRunProgress } from "./ResearchRunProgress";
import type { PendingTurn } from "./researchReducer";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

const RUNTIME = {
  research_runtime: {
    max_tool_calls: 60,
    session_timeout_s: 900,
    per_tool_timeout_s: 45,
    source: "db",
    db_saved: true,
    warning: null,
  },
} as RuntimeConfig;

function run(
  status: ResearchRunDTO["status"],
  over: Partial<ResearchRunDTO> = {},
): ResearchRunDTO {
  return {
    id: `run-${status}`,
    thread_id: "thread-progress",
    status,
    question: "SOURCE_QUESTION",
    ticker: "MU",
    provider: "openai",
    model: "gpt-5.6-luna",
    effort: "high",
    auth_mode: "api_key",
    credential_id: "local:7",
    started_at: status === "queued" ? null : "2026-07-20T00:00:05Z",
    completed_at: ["queued", "running"].includes(status)
      ? null
      : "2026-07-20T00:00:12Z",
    error: null,
    token_usage: null,
    created_at: "2026-07-20T00:00:00Z",
    updated_at: "2026-07-20T00:00:12Z",
    ...over,
  };
}

function pending(over: Partial<PendingTurn> = {}): PendingTurn {
  return {
    threadId: "thread-progress",
    runId: null,
    startedAt: Date.parse("2026-07-20T00:00:00Z"),
    provider: "openai",
    model: "gpt-5.6-luna",
    effort: "high",
    interimText: "",
    trace: [],
    thinkingActive: true,
    turnCount: 0,
    tickers: ["MU"],
    ...over,
  };
}

type ProgressProps = ComponentProps<typeof ResearchRunProgress>;

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;
let currentProps: ProgressProps | null = null;

async function flush() {
  await act(async () => {
    for (let index = 0; index < 6; index += 1) await Promise.resolve();
  });
}

async function mountProgress(over: Partial<ProgressProps> = {}) {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  currentProps = {
    pending: null,
    run: run("succeeded"),
    runtime: RUNTIME,
    developerMode: false,
    onStop: vi.fn(),
    onNavigate: vi.fn(),
    ...over,
  };
  await act(async () => {
    root!.render(<ResearchRunProgress {...currentProps!} />);
  });
  await flush();
}

async function rerenderProgress(over: Partial<ProgressProps>) {
  currentProps = { ...currentProps!, ...over };
  await act(async () => {
    root!.render(<ResearchRunProgress {...currentProps!} />);
  });
  await flush();
}

function progressNode(): HTMLElement {
  const node = host!.querySelector<HTMLElement>("[data-testid='research-run-progress']");
  if (!node) throw new Error("Research progress node not found");
  return node;
}

afterEach(async () => {
  if (root) act(() => root!.unmount());
  root = null;
  host?.remove();
  host = null;
  currentProps = null;
  vi.restoreAllMocks();
  await i18n.changeLanguage("zh-Hant");
});

describe("Research run progress", () => {
  it("maps every bounded run status in both locales", async () => {
    const cases: Array<{
      stage: string;
      pending: PendingTurn | null;
      run: ResearchRunDTO | null;
      zh: string;
      en: string;
    }> = [
      { stage: "creating", pending: pending(), run: null, zh: "建立執行", en: "Creating run" },
      { stage: "queued", pending: null, run: run("queued"), zh: "等待執行", en: "Waiting to run" },
      { stage: "running", pending: null, run: run("running"), zh: "模型與工具執行中", en: "Running model and tools" },
      { stage: "succeeded", pending: null, run: run("succeeded"), zh: "研究完成", en: "Research completed" },
      { stage: "failed", pending: null, run: run("failed"), zh: "Provider 呼叫失敗", en: "Provider call failed" },
      { stage: "interrupted", pending: null, run: run("interrupted"), zh: "研究已中止", en: "Research interrupted" },
      { stage: "cancelled", pending: null, run: run("cancelled"), zh: "研究已取消", en: "Research cancelled" },
    ];

    await i18n.changeLanguage("zh-Hant");
    await mountProgress({ pending: cases[0].pending, run: cases[0].run });
    for (const item of cases) {
      await rerenderProgress({ pending: item.pending, run: item.run });
      expect(progressNode().dataset.stage).toBe(item.stage);
      expect(progressNode().textContent).toContain(item.zh);
    }

    await act(async () => { await i18n.changeLanguage("en"); });
    await flush();
    for (const item of cases) {
      await rerenderProgress({ pending: item.pending, run: item.run });
      expect(progressNode().dataset.stage).toBe(item.stage);
      expect(progressNode().textContent).toContain(item.en);
    }
  });

  it("preserves exact progress and token values", async () => {
    await i18n.changeLanguage("en");
    const tokenUsage = Object.freeze({
      input_tokens: 123456789,
      output_tokens: 987654321,
    });
    const completed = Object.freeze(run("succeeded", { token_usage: tokenUsage }));
    await mountProgress({ run: completed });
    const node = progressNode();
    expect(node.textContent).toContain("Research completed");
    expect(node.textContent).toContain("Overall elapsed 12s");
    expect(node.textContent).toContain("Stage elapsed 7s");
    expect(completed.token_usage).toEqual({
      input_tokens: 123456789,
      output_tokens: 987654321,
    });

    await act(async () => { await i18n.changeLanguage("zh-Hant"); });
    await flush();
    expect(progressNode()).toBe(node);
    expect(node.textContent).toContain("總耗時 12s");
    expect(node.textContent).toContain("階段耗時 7s");
    expect(completed.token_usage?.input_tokens).toBe(123456789);
    expect(completed.token_usage?.output_tokens).toBe(987654321);
  });

  it("renders semantic failure facts without raw detail", async () => {
    await i18n.changeLanguage("en");
    await mountProgress({
      run: run("failed", {
        error_code: "model_timeout",
        error: "RAW_PROVIDER_DETAIL access_token=SECRET",
      }),
      developerMode: false,
    });
    const node = progressNode();
    expect(node.textContent).toContain("Model run timed out");
    expect(node.textContent).toContain(
      "The model did not finish within the current AI Research runtime bound.",
    );
    expect(node.textContent).not.toContain("RAW_PROVIDER_DETAIL");
    expect(node.textContent).not.toContain("SECRET");
  });

  it("does not promise continuing work for an unverified saved completion", async () => {
    await i18n.changeLanguage("en");
    await mountProgress({ run: run("interrupted", { error_code: "run_completion_unverified" }) });
    const node = progressNode();
    expect(node.textContent).toContain("Saved completion could not be verified");
    expect(node.textContent).toContain("Existing output has been retained without claiming completion.");
    expect(node.textContent).not.toContain("Continues after leaving this page");
    expect(node.querySelector("button")).toBeNull();
  });

  it("preserves node identity while locale changes", async () => {
    await i18n.changeLanguage("zh-Hant");
    await mountProgress({ run: run("running") });
    const rootNode = progressNode();
    const bounded = rootNode.querySelector(".ui-bounded-progress")!;
    const stop = Array.from(rootNode.querySelectorAll("button")).find((candidate) => (
      candidate.textContent?.trim() === "停止"
    ))!;
    stop.focus();

    await act(async () => { await i18n.changeLanguage("en"); });
    await flush();

    expect(progressNode()).toBe(rootNode);
    expect(rootNode.querySelector(".ui-bounded-progress")).toBe(bounded);
    expect(Array.from(rootNode.querySelectorAll("button")).find((candidate) => (
      candidate.textContent?.trim() === "Stop"
    ))).toBe(stop);
    expect(rootNode.textContent).toContain("Running model and tools");
    expect(document.activeElement).toBe(stop);
  });

  it("keeps the completion destination contract unchanged", async () => {
    await i18n.changeLanguage("en");
    await mountProgress({ run: run("succeeded") });
    const node = progressNode();
    expect(node.textContent).toContain("Continues after leaving this page");
    expect(node.textContent).toContain("Cannot be cancelled here");
    expect(node.textContent).toContain("Result: Saved in this conversation");
    expect(node.querySelector("button")).toBeNull();

    await act(async () => { await i18n.changeLanguage("zh-Hant"); });
    await flush();
    expect(progressNode()).toBe(node);
    expect(node.textContent).toContain("離開頁面後繼續");
    expect(node.textContent).toContain("結果：已保存於此對話");
  });
});
