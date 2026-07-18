/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  InvestorProfileResponse,
  ModelCatalog,
  ModelTask,
  ResearchMessageDTO,
  ResearchRunDTO,
  ResearchThreadDTO,
  RuntimeConfig,
  TaskRoute,
} from "./api";
import { ResearchView } from "./Research";
import type { ResearchNavigationRequest } from "./shell/navigation";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

const taskRoute = (task: ModelTask): TaskRoute => ({
  task,
  provider: "openai",
  model: "gpt-5.6-luna",
  effort: "high",
  source: "db",
  custom: false,
  warning: null,
});

const RUNTIME: RuntimeConfig = {
  anthropic: {
    model: "claude-sonnet-5",
    model_advanced: "claude-opus-4-8",
    effort: null,
    thinking: false,
    key_set: true,
    credentials: [],
  },
  openai: {
    model: "gpt-5.6-luna",
    model_advanced: "gpt-5.6-sol",
    reasoning_effort: "high",
    key_set: true,
    credentials: [],
  },
  card_synthesis: taskRoute("card_synthesis"),
  card_translation: taskRoute("card_translation"),
  ai_research: taskRoute("ai_research"),
  research_runtime: {
    max_tool_calls: 60,
    session_timeout_s: 900,
    per_tool_timeout_s: 45,
    source: "db",
    db_saved: true,
    warning: null,
  },
  data_keys: {},
};

const CATALOG: ModelCatalog = {
  providers: ["openai", "anthropic"],
  tasks: [{
    id: "ai_research",
    label: "AI 研究",
    description: "",
    default_provider: "openai",
    recommended_model: "gpt-5.6-luna",
  }],
  models: [],
  effort_options: {
    openai: [{
      id: "high",
      provider: "openai",
      label: "high",
      description: "",
      applies_to_card_tasks: false,
    }],
    anthropic: [],
  },
  routes: {
    card_synthesis: taskRoute("card_synthesis"),
    card_translation: taskRoute("card_translation"),
    ai_research: taskRoute("ai_research"),
  },
  credentials: { openai: [], anthropic: [] },
  custom_allowed: true,
  effective: {
    providers: {
      openai: { credential_id: "local:7", auth_mode: "api_key", label: "OpenAI API" },
      anthropic: { credential_id: "local:4", auth_mode: "api_key", label: "Anthropic API" },
    },
    tasks: {
      ai_research: {
        verified: [],
        advanced: [],
        cache_state: "ok",
        discovered_at: "2026-07-17T00:00:00Z",
        current_provider: "openai",
        providers: {
          openai: {
            executable: true,
            reason_code: null,
            cache_state: "ok",
            discovered_at: "2026-07-17T00:00:00Z",
            models: [{
              id: "gpt-5.6-luna",
              label: "gpt-5.6-luna",
              status: "visible",
              visible_to_credential: true,
              eligible: true,
              reason_code: null,
              thinking_mode: "none",
              effort_options: ["high"],
            }],
          },
          anthropic: {
            executable: true,
            reason_code: null,
            cache_state: "seed_only",
            discovered_at: null,
            models: [{
              id: "claude-sonnet-5",
              label: "claude-sonnet-5",
              status: "seed",
              visible_to_credential: null,
              eligible: true,
              reason_code: null,
              thinking_mode: "adaptive_default_on",
              effort_options: ["high"],
            }],
          },
        },
      },
    },
  },
};

const PROFILE: InvestorProfileResponse = {
  profile: {
    enabled: false,
    primary_preset: "balanced",
    risk_appetite: null,
    risk_capacity: null,
    risk_mismatch: "none",
    holding_horizon: "",
    drawdown_tolerance_pct: null,
    concentration_limit_pct: null,
    preferred_edge: [],
    avoidances: [],
    behavioral_flags: [],
    freeform_notes: "",
    default_stance: "off",
    skill_mode: "off",
    last_reviewed_at: null,
    updated_at: null,
  },
  effective_stance: "off",
  trace: {
    profile_active: false,
    assistant_stance: "off",
    skill_mode: "off",
    suggested_skills: [],
    applied_skills: [],
  },
  context_preview: "",
};

function run(
  id: string,
  threadId: string,
  status: ResearchRunDTO["status"],
): ResearchRunDTO {
  return {
    id,
    thread_id: threadId,
    status,
    question: "What changed?",
    ticker: "MU",
    provider: "openai",
    model: "gpt-5.6-luna",
    effort: "high",
    auth_mode: "api_key",
    credential_id: "local:7",
    started_at: status === "queued" ? null : "2026-07-17T00:01:00Z",
    completed_at: ["queued", "running"].includes(status) ? null : "2026-07-17T00:02:00Z",
    error: null,
    token_usage: status === "succeeded" ? { input_tokens: 10, output_tokens: 5 } : null,
    created_at: "2026-07-17T00:00:00Z",
    updated_at: "2026-07-17T00:02:00Z",
  };
}

function thread(
  id: string,
  title: string,
  activeRun: ResearchRunDTO | null = null,
): ResearchThreadDTO {
  return {
    id,
    title,
    ticker: "MU",
    provider: "openai",
    model: "gpt-5.6-luna",
    created_at: "2026-07-17T00:00:00Z",
    updated_at: "2026-07-17T00:02:00Z",
    active_run: activeRun,
  };
}

function persistedMessage(
  role: ResearchMessageDTO["role"],
  content: string,
  isError = false,
): ResearchMessageDTO {
  return {
    role,
    content,
    provider: role === "assistant" ? "openai" : null,
    model: role === "assistant" ? "gpt-5.6-luna" : null,
    effort: role === "assistant" ? "high" : null,
    tools_used: [],
    tool_calls: [],
    token_usage: null,
    tickers: null,
    elapsed_seconds: role === "assistant" ? 1 : null,
    is_error: isError,
    created_at: "2026-07-17T00:03:00Z",
  };
}

function json(value: unknown, status = 200): Response {
  return new Response(JSON.stringify(value), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

function stubResearchFetch({
  threads,
  exactThreads = {},
  exactResponses = {},
  messages = {},
  messageResponses = {},
  messageResponseQueues = {},
  patchResponses = {},
  threadResponse,
  createdRun,
  replayRun,
  order,
  selectionResponses,
}: {
  threads: ResearchThreadDTO[];
  exactThreads?: Record<string, ResearchThreadDTO>;
  exactResponses?: Record<string, Response | Promise<Response>>;
  messages?: Record<string, ResearchMessageDTO[]>;
  messageResponses?: Record<string, Response | Promise<Response>>;
  messageResponseQueues?: Record<string, Array<Response | Promise<Response>>>;
  patchResponses?: Record<string, ResearchThreadDTO>;
  threadResponse?: Response | Promise<Response>;
  createdRun?: ResearchRunDTO;
  replayRun?: ResearchRunDTO;
  order?: string[];
  selectionResponses?: Response[];
}) {
  const patchedThreads: Record<string, ResearchThreadDTO> = {};
  let pendingThreadResponse = threadResponse;
  return vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
    const url = new URL(String(input));
    const path = `${url.pathname}${url.search}`;
    if (path === "/config/runtime") return json(RUNTIME);
    if (path === "/query/providers") {
      return json({ providers: { openai: { available: true }, anthropic: { available: true } } });
    }
    if (path === "/config/model-catalog") return json(CATALOG);
    if (path === "/profile/investor") return json(PROFILE);
    if (url.pathname === "/research/threads" && (init?.method ?? "GET") === "GET") {
      if (pendingThreadResponse) {
        const response = pendingThreadResponse;
        pendingThreadResponse = undefined;
        return await response;
      }
      return json({
        threads: threads.map((thread) => patchedThreads[thread.id] ?? thread),
        total: threads.length,
        limit: Number(url.searchParams.get("limit") ?? 50),
        offset: Number(url.searchParams.get("offset") ?? 0),
      });
    }
    const exactMatch = url.pathname.match(/^\/research\/threads\/([^/]+)$/);
    if (exactMatch && (init?.method ?? "GET") === "GET") {
      const threadId = decodeURIComponent(exactMatch[1]);
      const exactResponse = exactResponses[threadId];
      if (exactResponse) return await exactResponse;
      const found = patchedThreads[threadId]
        ?? exactThreads[threadId]
        ?? threads.find((candidate) => candidate.id === threadId);
      return found ? json({ thread: found }) : json({ detail: "thread not found" }, 404);
    }
    if (exactMatch && init?.method === "PATCH") {
      const threadId = decodeURIComponent(exactMatch[1]);
      const patch = JSON.parse(String(init.body ?? "{}")) as { title?: string };
      const found = patchResponses[threadId]
        ?? patchedThreads[threadId]
        ?? exactThreads[threadId]
        ?? threads.find((candidate) => candidate.id === threadId);
      if (!found) return json({ detail: "thread not found" }, 404);
      const updated = { ...found, ...(patch.title === undefined ? {} : { title: patch.title }) };
      patchedThreads[threadId] = updated;
      return json({ thread: updated });
    }
    if (/^\/research\/threads\/[^/]+\/selection$/.test(url.pathname)) {
      const queued = selectionResponses?.shift();
      if (queued) return queued;
      return json({ provider: "openai", model: "gpt-5.6-luna", effort: "high" });
    }
    if (/^\/research\/threads\/[^/]+\/messages$/.test(url.pathname)) {
      const threadId = decodeURIComponent(url.pathname.split("/")[3] ?? "");
      const queuedResponse = messageResponseQueues[threadId]?.shift();
      if (queuedResponse) return await queuedResponse;
      const response = messageResponses[threadId];
      if (response) return await response;
      return json({ thread_id: threadId, messages: messages[threadId] ?? [] });
    }
    if (path === "/research/runs" && init?.method === "POST" && createdRun) {
      order?.push("create-request");
      return json({ run: createdRun });
    }
    if (/^\/research\/runs\/[^/]+\/events\?after=0$/.test(path) && replayRun) {
      order?.push("events-request");
      return json({ run: replayRun, events: [], has_more: false });
    }
    if (/^\/research\/runs\/[^/]+\/events\?after=0$/.test(path)) {
      const runId = decodeURIComponent(url.pathname.split("/")[3] ?? "");
      const active = [...threads, ...Object.values(exactThreads)]
        .map((candidate) => candidate.active_run)
        .find((candidate) => candidate?.id === runId);
      if (active) {
        return json({
          run: {
            ...active,
            status: "interrupted",
            completed_at: "2026-07-17T00:02:00Z",
          },
          events: [],
          has_more: false,
        });
      }
    }
    throw new Error(`unhandled test request: ${init?.method ?? "GET"} ${path}`);
  });
}

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

async function flush() {
  await act(async () => {
    for (let index = 0; index < 12; index += 1) await Promise.resolve();
    await new Promise<void>((resolve) => window.setTimeout(resolve, 0));
    for (let index = 0; index < 4; index += 1) await Promise.resolve();
  });
}

async function mountResearch({
  navigationRequest,
  onObserveRun = vi.fn(),
}: {
  navigationRequest?: ResearchNavigationRequest | null;
  onObserveRun?: (run: ResearchRunDTO, title?: string) => void;
} = {}) {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  const render = async (nextRequest = navigationRequest) => {
    await act(async () => {
      root!.render(
        <ResearchView
          onOpenTicker={vi.fn()}
          navigationRequest={nextRequest}
          onObserveRun={onObserveRun}
        />,
      );
    });
    await flush();
  };
  await render();
  return { host, render, onObserveRun };
}

async function click(element: Element) {
  await act(async () => {
    element.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    await Promise.resolve();
  });
}

async function setInput(element: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
  await act(async () => {
    setter?.call(element, value);
    element.dispatchEvent(new Event("input", { bubbles: true }));
    await Promise.resolve();
  });
}

function historyThreadButton(title: string): HTMLButtonElement {
  const match = document.querySelector(`button[aria-label='開啟對話 ${title}']`);
  if (!match) throw new Error(`history thread button not found: ${title}`);
  return match as HTMLButtonElement;
}

afterEach(() => {
  if (root) act(() => root!.unmount());
  root = null;
  host?.remove();
  host = null;
  window.sessionStorage.clear();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Research shell navigation", () => {
  it("consumes a sequenced thread target after hydration and preserves later local thread selection", async () => {
    const target = {
      ...thread("thread-b", "Thread B"),
      archived_at: "2026-07-17T02:00:00Z",
    };
    const fetchMock = stubResearchFetch({
      threads: [thread("thread-a", "Thread A")],
      exactThreads: { "thread-b": target },
      messages: {
        "thread-b": [
          persistedMessage("user", "Retry this research"),
          persistedMessage("assistant", "Provider failed", true),
        ],
      },
    });
    vi.stubGlobal("fetch", fetchMock);
    const request = (sequence: number): ResearchNavigationRequest => ({
      sequence,
      target: { kind: "research_thread", threadId: "thread-b", runId: "source-run" },
    });
    const mounted = await mountResearch({ navigationRequest: request(1) });

    expect(host!.querySelector(".research-threads")).toBeNull();
    expect(host!.querySelector(".research-conversation-title")?.textContent).toBe("Thread B");
    const messageRequests = () => fetchMock.mock.calls
      .map(([input]) => new URL(String(input)).pathname)
      .filter((requestPath) => requestPath.endsWith("/messages"));
    expect(messageRequests()).toEqual(["/research/threads/thread-b/messages"]);
    expect(Array.from(host!.querySelectorAll("button")).some(
      (candidate) => candidate.textContent?.trim() === "重試",
    )).toBe(false);

    const history = Array.from(host!.querySelectorAll("button"))
      .find((candidate) => candidate.textContent?.trim() === "歷史");
    expect(history).toBeDefined();
    await click(history!);
    await click(historyThreadButton("Thread A"));
    expect(host!.querySelector(".research-conversation-title")?.textContent).toBe("Thread A");
    expect(messageRequests()).toEqual([
      "/research/threads/thread-b/messages",
      "/research/threads/thread-a/messages",
    ]);

    await mounted.render(request(1));
    expect(host!.querySelector(".research-conversation-title")?.textContent).toBe("Thread A");

    await mounted.render(request(2));
    expect(host!.querySelector(".research-conversation-title")?.textContent).toBe("Thread B");
  });

  it("reports each hydrated active run to the shell observer", async () => {
    const active = run("active-run", "active-thread", "running");
    const stale = run("stale-run", "stale-thread", "running");
    const threadPage = deferred<Response>();
    const activeMessages = deferred<Response>();
    const fetchMock = stubResearchFetch({
      threads: [
        thread("active-thread", "Active research"),
        thread("stale-thread", "Stale research", stale),
      ],
      exactThreads: { "active-thread": thread("active-thread", "Active research", active) },
      patchResponses: {
        "stale-thread": {
          ...thread("stale-thread", "Stale research complete"),
          latest_run_status: "succeeded",
        },
      },
      threadResponse: threadPage.promise,
      messageResponseQueues: {
        "active-thread": [
          json({ thread_id: "active-thread", messages: [] }),
          activeMessages.promise,
        ],
      },
    });
    vi.stubGlobal("fetch", fetchMock);
    const onObserveRun = vi.fn();
    const mounted = await mountResearch({ onObserveRun });

    const newThread = Array.from(host!.querySelectorAll("button"))
      .find((candidate) => candidate.textContent?.trim() === "新研究");
    await click(newThread!);
    threadPage.resolve(json({
      threads: [
        thread("active-thread", "Active research"),
        thread("stale-thread", "Stale research", stale),
      ],
      total: 2,
      limit: 50,
      offset: 0,
    }));
    await flush();

    expect(host!.querySelector(".research-conversation-title")?.textContent).toBe("新對話");
    const history = Array.from(host!.querySelectorAll("button"))
      .find((candidate) => candidate.textContent?.trim() === "歷史");
    await click(history!);
    expect(onObserveRun.mock.calls.filter(([observed]) => observed.id === stale.id)).toHaveLength(1);
    await click(document.querySelector("[aria-label='重新命名 Stale research']")!);
    await setInput(document.querySelector<HTMLInputElement>("[aria-label='對話名稱']")!, "Stale renamed");
    await click(Array.from(document.querySelectorAll("button"))
      .find((candidate) => candidate.textContent?.trim() === "儲存名稱")!);
    await vi.waitFor(() => expect(document.body.textContent).toContain("Stale renamed"));
    expect(onObserveRun.mock.calls.filter(([observed]) => observed.id === stale.id)).toHaveLength(1);
    await click(historyThreadButton("Active research"));
    const navigation: ResearchNavigationRequest = {
      sequence: 11,
      target: { kind: "research_thread", threadId: "active-thread", runId: "active-run" },
    };
    await mounted.render(navigation);
    expect(onObserveRun).toHaveBeenCalledWith(active, "Active research");
    expect(fetchMock.mock.calls.some(([input]) => (
      new URL(String(input)).pathname === "/research/runs/active-run/events"
    ))).toBe(false);

    activeMessages.resolve(json({ thread_id: "active-thread", messages: [] }));
    await flush();
    await vi.waitFor(() => expect(fetchMock.mock.calls.some(([input]) => (
      new URL(String(input)).pathname === "/research/runs/active-run/events"
    ))).toBe(true));
  });

  it("keeps selection failures fail-closed and lets the user retry", async () => {
    const transientFetch = stubResearchFetch({
      threads: [thread("thread-a", "Thread A")],
      exactResponses: { "transient-thread": json({ detail: "temporary failure" }, 500) },
    });
    vi.stubGlobal("fetch", transientFetch);
    window.sessionStorage.setItem("arkscope.aiResearch.activeThreadId", "transient-thread");
    await mountResearch();

    expect(host!.querySelector(".research-conversation-title")?.textContent).toBe("新對話");
    expect(host!.textContent).toContain("暫時無法載入指定的研究對話");
    expect(window.sessionStorage.getItem("arkscope.aiResearch.activeThreadId")).toBe("transient-thread");

    await act(async () => root!.unmount());
    root = null;
    host!.remove();
    host = null;

    const fetchMock = stubResearchFetch({
      threads: [thread("thread-a", "Thread A")],
      selectionResponses: [
        json({ detail: "temporary failure" }, 500),
        json({ provider: "openai", model: "gpt-5.6-luna", effort: "high" }),
      ],
    });
    vi.stubGlobal("fetch", fetchMock);
    window.sessionStorage.setItem("arkscope.aiResearch.activeThreadId", "missing-thread");
    await mountResearch();

    expect(host!.querySelector(".research-conversation-title")?.textContent).toBe("Thread A");
    expect(window.sessionStorage.getItem("arkscope.aiResearch.activeThreadId")).toBe("thread-a");

    const retry = await vi.waitFor(() => {
      const button = Array.from(host!.querySelectorAll("button"))
        .find((candidate) => candidate.textContent?.trim() === "重新確認模型");
      expect(button).toBeDefined();
      return button as HTMLButtonElement;
    });
    expect(host!.textContent).toContain("無法確認此對話上次使用的模型");
    const send = Array.from(host!.querySelectorAll("button"))
      .find((candidate) => candidate.textContent?.trim() === "送出") as HTMLButtonElement;
    expect(send.disabled).toBe(true);

    await click(retry);
    await vi.waitFor(() => {
      expect(host!.textContent).not.toContain("無法確認此對話上次使用的模型");
      expect(host!.textContent).toContain("研究模型：openai · gpt-5.6-luna · high");
    });
    const selectionCalls = fetchMock.mock.calls.filter(([input]) => (
      new URL(String(input)).pathname === "/research/threads/thread-a/selection"
    ));
    expect(selectionCalls).toHaveLength(2);
  });

  it("reports a created run before replay and reports the terminal replay DTO", async () => {
    const created = run("new-run", "thread-a", "running");
    const terminal = run("new-run", "thread-a", "succeeded");
    const order: string[] = [];
    const fetchMock = stubResearchFetch({
      threads: [thread("thread-a", "Thread A")],
      createdRun: created,
      replayRun: terminal,
      order,
    });
    vi.stubGlobal("fetch", fetchMock);
    window.sessionStorage.setItem("arkscope.aiResearch.activeThreadId", "thread-a");
    const onObserveRun = vi.fn((observed: ResearchRunDTO) => {
      order.push(`observe-${observed.status}`);
    });
    const mounted = await mountResearch({ onObserveRun });
    await mounted.render();
    const selectionCall = fetchMock.mock.calls.find(([input]) => (
      new URL(String(input)).pathname === "/research/threads/thread-a/selection"
    ));
    expect(selectionCall?.[1]).toEqual(expect.objectContaining({
      signal: expect.any(AbortSignal),
    }));
    let openAiRoute: HTMLButtonElement | undefined;
    await vi.waitFor(() => {
      openAiRoute = Array.from(host!.querySelectorAll("button"))
        .find((candidate) => candidate.textContent?.includes("OpenAI / gpt-5.6-luna"));
      expect(openAiRoute).toBeDefined();
    });
    await click(openAiRoute!);
    const textarea = host!.querySelector("textarea[placeholder^='輸入問題']") as HTMLTextAreaElement;
    const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")?.set;
    await act(async () => {
      setter?.call(textarea, "Run a focused update");
      textarea.dispatchEvent(new Event("input", { bubbles: true }));
    });
    const send = Array.from(host!.querySelectorAll("button"))
      .find((candidate) => candidate.textContent?.trim() === "送出") as HTMLButtonElement;
    await vi.waitFor(() => expect(send.disabled).toBe(false));
    await click(send);
    await flush();

    expect(order.indexOf("observe-running")).toBeGreaterThan(order.indexOf("create-request"));
    expect(order.indexOf("observe-running")).toBeLessThan(order.indexOf("events-request"));
    expect(order.indexOf("observe-succeeded")).toBeGreaterThan(order.indexOf("events-request"));
    expect(onObserveRun).toHaveBeenCalledWith(terminal);
  });
});
