/** @vitest-environment jsdom */
import React, { type ReactNode } from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { flushSync } from "react-dom";
import i18n from "i18next";
import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  AssistantStance,
  PersonalizationTrace,
  ResearchRunDTO,
} from "./api";
import { ResearchEvidenceDrawer } from "./ResearchEvidenceDrawer";
import { ResearchPersonalizationContext } from "./ResearchPersonalizationContext";
import type { Message } from "./researchReducer";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

let host: HTMLDivElement | null = null;
let root: ReturnType<typeof createRoot> | null = null;

async function renderNode(node: ReactNode): Promise<HTMLDivElement> {
  if (!host) {
    host = document.createElement("div");
    document.body.append(host);
    root = createRoot(host);
  }
  await act(async () => {
    root!.render(node);
  });
  return host;
}

async function renderTrace(value: PersonalizationTrace | null) {
  return renderNode(<ResearchPersonalizationContext trace={value} />);
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((promiseResolve) => {
    resolve = promiseResolve;
  });
  return { promise, resolve };
}

function trace(
  overrides: Partial<PersonalizationTrace> = {},
): PersonalizationTrace {
  return {
    profile_active: true,
    assistant_stance: "aligned",
    skill_mode: "off",
    suggested_skills: [],
    applied_skills: [],
    ...overrides,
  };
}

function message(
  personalization: PersonalizationTrace | null,
  runId = "run-context",
): Message {
  return {
    role: "assistant",
    content: "Saved answer",
    provider: "openai",
    model: "gpt-5.6-luna",
    effort: "high",
    tools_used: [],
    tool_calls: [],
    token_usage: null,
    tickers: null,
    elapsed_seconds: 2,
    created_at: "2026-07-22T00:03:00Z",
    personalization,
    runId,
  };
}

function run(
  personalization: PersonalizationTrace | null,
  overrides: Partial<ResearchRunDTO> = {},
): ResearchRunDTO {
  return {
    id: "run-context",
    thread_id: "thread-context",
    status: "succeeded",
    question: "What changed?",
    ticker: "MU",
    provider: "openai",
    model: "gpt-5.6-luna",
    effort: "high",
    personalization,
    auth_mode: "api_key",
    credential_id: null,
    started_at: "2026-07-22T00:01:00Z",
    completed_at: "2026-07-22T00:02:00Z",
    error: null,
    token_usage: null,
    created_at: "2026-07-22T00:00:00Z",
    updated_at: "2026-07-22T00:02:00Z",
    ...overrides,
  };
}

afterEach(() => {
  if (root) act(() => root!.unmount());
  root = null;
  host?.remove();
  host = null;
  vi.unstubAllGlobals();
});

describe("ResearchPersonalizationContext", () => {
  it("renders legacy null as no snapshot", async () => {
    const node = await renderTrace(null);
    expect(node.textContent).toContain("這筆歷史執行沒有儲存個人化情境。");
    expect(node.textContent).not.toContain("本次執行未啟用個人化。");
    expect(node.querySelector("pre")).toBeNull();

    await renderTrace(trace({ context_snapshot: null }));
    expect(node.textContent).toContain("這筆歷史執行沒有儲存個人化情境。");
    expect(node.querySelector("pre")).toBeNull();
  });

  it("renders empty snapshot as disabled", async () => {
    const node = await renderTrace(trace({
      profile_active: false,
      assistant_stance: "off",
      context_snapshot: "",
    }));

    expect(node.textContent).toContain("本次執行未啟用個人化。");
    expect(node.textContent).not.toContain("這筆歷史執行沒有儲存個人化情境。");
    expect(node.querySelector("pre")).toBeNull();
  });

  it("renders active exact source text byte for byte", async () => {
    const source = "Investor context:\n  虧損時保持紀律\n한국어 원문\n日本語の原文\n";
    const node = await renderTrace(trace({ context_snapshot: source }));

    expect(node.textContent).toContain("本次執行已套用個人化。");
    expect(node.querySelector("pre")?.textContent).toBe(source);
  });

  it("distinguishes run context from current Settings context", async () => {
    const selected = trace({
      assistant_stance: "neutral",
      context_snapshot: "SELECTED_MESSAGE_SOURCE",
    });
    const fetched = trace({
      assistant_stance: "growth_opportunity",
      context_snapshot: "FETCHED_RUN_SOURCE",
    });
    const fetchedRun = run(fetched);
    vi.stubGlobal("fetch", vi.fn(async () => new Response(
      JSON.stringify({ run: fetchedRun }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    )));

    await renderNode(
      <ResearchEvidenceDrawer
        open
        pinned={false}
        onClose={vi.fn()}
        onPinnedChange={vi.fn()}
        message={message(selected)}
        activeTrace={[]}
        activeRun={fetchedRun}
        developerMode={false}
      />,
    );

    expect(document.body.textContent).toContain("本次執行的個人化情境");
    expect(document.body.textContent).toContain("不是目前的投資人設定");
    expect(document.body.textContent).not.toContain("目前的個人化情境");
    expect(document.querySelector(".research-personalization-context-source")?.textContent)
      .toBe("SELECTED_MESSAGE_SOURCE");

    await renderNode(
      <ResearchEvidenceDrawer
        open
        pinned={false}
        onClose={vi.fn()}
        onPinnedChange={vi.fn()}
        message={message(null)}
        activeTrace={[]}
        activeRun={fetchedRun}
        developerMode={false}
      />,
    );
    expect(document.querySelector(".research-personalization-context-source")?.textContent)
      .toBe("FETCHED_RUN_SOURCE");
  });

  it("never exposes the previous run context while a newly selected run is pending", async () => {
    const runAResponse = deferred<Response>();
    const runBResponse = deferred<Response>();
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = typeof input === "string"
        ? input
        : input instanceof URL
          ? input.href
          : input.url;
      if (url.endsWith("/run-a")) return runAResponse.promise;
      if (url.endsWith("/run-b")) return runBResponse.promise;
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const drawer = (runId: string) => (
      <ResearchEvidenceDrawer
        open
        pinned={false}
        onClose={vi.fn()}
        onPinnedChange={vi.fn()}
        message={message(null, runId)}
        activeTrace={[]}
        activeRun={null}
        developerMode={false}
      />
    );

    await renderNode(drawer("run-a"));
    await act(async () => {
      runAResponse.resolve(new Response(
        JSON.stringify({
          run: run(trace({ context_snapshot: "RUN_A_CONTEXT" }), { id: "run-a" }),
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ));
    });
    expect(document.querySelector(".research-personalization-context-source")?.textContent)
      .toBe("RUN_A_CONTEXT");

    act(() => {
      flushSync(() => {
        root!.render(drawer("run-b"));
      });
      expect(document.body.textContent).not.toContain("RUN_A_CONTEXT");
    });

    await act(async () => {
      await Promise.resolve();
    });
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(document.body.textContent).not.toContain("RUN_A_CONTEXT");
    expect(document.body.textContent).not.toContain("RUN_B_CONTEXT");

    await act(async () => {
      runBResponse.resolve(new Response(
        JSON.stringify({
          run: run(trace({ context_snapshot: "RUN_B_CONTEXT" }), { id: "run-b" }),
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ));
    });
    expect(document.querySelector(".research-personalization-context-source")?.textContent)
      .toBe("RUN_B_CONTEXT");
    expect(document.body.textContent).not.toContain("RUN_A_CONTEXT");
  });

  it("switches locale without changing source context or disclosure state", async () => {
    const source = "原始情境\n  English stays source\n한국어도 그대로\n";
    const node = await renderTrace(trace({ context_snapshot: source }));
    const disclosure = node.querySelector("details");
    const sourceNode = node.querySelector(".research-personalization-context-source");
    expect(disclosure).not.toBeNull();
    expect(sourceNode?.textContent).toBe(source);

    act(() => {
      disclosure!.open = true;
    });
    await act(async () => {
      await i18n.changeLanguage("en");
    });

    expect(node.textContent).toContain("Personalization context for this run");
    expect(node.textContent).toContain("not your current Investor Profile");
    expect(node.textContent).toContain(
      "Emphasizes evidence and trade-offs that fit your stated investor profile.",
    );
    expect(node.querySelector("details")).toBe(disclosure);
    expect(disclosure?.open).toBe(true);
    expect(node.querySelector(".research-personalization-context-source")).toBe(sourceNode);
    expect(sourceNode?.textContent).toBe(source);
  });

  it("maps closed stance effect copy without deriving it from context text", async () => {
    const cases: Array<[AssistantStance, string]> = [
      ["off", "個人化已關閉，助手不會套用投資人設定重點。"],
      ["neutral", "維持平衡分析，不偏向你目前的看法。"],
      ["aligned", "強調符合你投資人設定的證據與取捨。"],
      ["complementary", "補充與你慣用方法互補的觀點與風險。"],
      ["strict_risk_control", "優先檢視下行風險、部位大小與風控紀律。"],
      ["valuation_rationalist", "優先檢視估值、假設與價格相對價值。"],
      ["growth_opportunity", "優先檢視成長持續性、上行驅動因素與機會成本。"],
    ];
    const misleadingSource = "neutral aligned strict_risk_control growth_opportunity";

    for (const [stance, expected] of cases) {
      const node = await renderNode(
        <ResearchPersonalizationContext
          trace={trace({ assistant_stance: stance, context_snapshot: misleadingSource })}
        />,
      );
      expect(node.querySelector("[data-testid='research-personalization-stance-effect']")?.textContent)
        .toBe(expected);
      expect(node.querySelector("pre")?.textContent).toBe(misleadingSource);
    }
  });
});
