/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  getResearchRun,
  type ResearchRunDTO,
  type ResearchThreadDTO,
} from "../api";
import {
  RESEARCH_WORK_STORAGE_KEY,
  useResearchWorkRegistry,
  type ResearchWorkApi,
  type ResearchWorkState,
} from "./researchWork";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

const SENSITIVE = {
  question: "private-question-fixture",
  error: "private-error-fixture",
  credential: "local:private-credential",
  answer: "private-answer-fixture",
};

function makeRun(
  status: ResearchRunDTO["status"],
  overrides: Partial<ResearchRunDTO> = {},
): ResearchRunDTO {
  return {
    id: `run-${status}`,
    thread_id: `thread-${status}`,
    status,
    question: SENSITIVE.question,
    ticker: "MU",
    provider: "openai",
    model: "gpt-5.6-luna",
    effort: "high",
    auth_mode: "api_key",
    credential_id: SENSITIVE.credential,
    started_at: status === "queued" ? null : "2026-07-17T00:01:00Z",
    completed_at: ["queued", "running"].includes(status) ? null : "2026-07-17T00:02:00Z",
    error: status === "failed" ? SENSITIVE.error : null,
    token_usage: { input_tokens: 123, output_tokens: 456 },
    created_at: "2026-07-17T00:00:00Z",
    updated_at: "2026-07-17T00:02:00Z",
    ...overrides,
  };
}

function makeThread(activeRun: ResearchRunDTO | null, overrides: Partial<ResearchThreadDTO> = {}): ResearchThreadDTO {
  return {
    id: activeRun?.thread_id ?? "thread-1",
    title: "MU 研究",
    ticker: "MU",
    provider: "openai",
    model: "gpt-5.6-luna",
    created_at: "2026-07-17T00:00:00Z",
    updated_at: "2026-07-17T00:02:00Z",
    active_run: activeRun,
    ...overrides,
  };
}

function emptyApi(overrides: Partial<ResearchWorkApi> = {}): ResearchWorkApi {
  return {
    getThreads: vi.fn(async () => ({ threads: [] })),
    getRun: vi.fn(async (runId: string) => ({ run: makeRun("running", { id: runId }) })),
    ...overrides,
  };
}

function memoryStorage(initial: Record<string, string> = {}) {
  const values = new Map(Object.entries(initial));
  return {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => { values.set(key, value); },
    value: (key: string) => values.get(key) ?? null,
  };
}

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;
let current: ResearchWorkState | null = null;

function RegistryHarness({ options }: {
  options?: Parameters<typeof useResearchWorkRegistry>[0];
}) {
  current = useResearchWorkRegistry(options);
  return <div data-testid="registry-count">{current.items.length}</div>;
}

async function flushAsync() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
  });
}

async function renderRegistry(options?: Parameters<typeof useResearchWorkRegistry>[0]) {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(<RegistryHarness options={options} />);
  });
  await flushAsync();
  return {
    state: () => {
      if (!current) throw new Error("registry state unavailable");
      return current;
    },
    unmount: () => {
      if (root) act(() => root!.unmount());
      root = null;
    },
  };
}

async function observe(run: ResearchRunDTO, title?: string) {
  await act(async () => {
    current!.observeRun(run, title);
  });
}

afterEach(() => {
  if (root) act(() => root!.unmount());
  root = null;
  current = null;
  host?.remove();
  host = null;
  window.sessionStorage.clear();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("useResearchWorkRegistry", () => {
  it("maps queued and running runs to active work", async () => {
    const registry = await renderRegistry({ api: emptyApi(), storage: memoryStorage() });
    await observe(makeRun("queued"), "等待中的研究");
    await observe(makeRun("running"), "執行中的研究");

    expect(registry.state().items.map((item) => item.status).sort()).toEqual(["queued", "running"]);
    expect(registry.state().activeCount).toBe(2);
    expect(registry.state().attentionCount).toBe(0);
  });

  it("maps succeeded and failed runs to attention work", async () => {
    const registry = await renderRegistry({ api: emptyApi(), storage: memoryStorage() });
    await observe(makeRun("succeeded"));
    await observe(makeRun("failed"));

    expect(registry.state().activeCount).toBe(0);
    expect(registry.state().attentionCount).toBe(2);
  });

  it("maps cancelled and interrupted runs to interrupted attention", async () => {
    const registry = await renderRegistry({ api: emptyApi(), storage: memoryStorage() });
    await observe(makeRun("cancelled"));
    await observe(makeRun("interrupted"));

    expect(registry.state().items.map((item) => item.status).sort()).toEqual(["cancelled", "interrupted"]);
    expect(registry.state().attentionCount).toBe(2);
  });

  it("projects no question answer error token usage credential id or raw provider payload", async () => {
    const storage = memoryStorage();
    const registry = await renderRegistry({ api: emptyApi(), storage });
    const raw = {
      ...makeRun("failed"),
      answer: SENSITIVE.answer,
      raw_provider_payload: "private-provider-payload-fixture",
    } as ResearchRunDTO;
    await observe(raw, "私密研究標題以外的正常標題");

    const serialized = `${JSON.stringify(registry.state().items)}\n${storage.value(RESEARCH_WORK_STORAGE_KEY)}`;
    for (const value of [
      SENSITIVE.question,
      SENSITIVE.error,
      SENSITIVE.credential,
      SENSITIVE.answer,
      "private-provider-payload-fixture",
      "input_tokens",
    ]) {
      expect(serialized).not.toContain(value);
    }
  });

  it("deduplicates the same run observed by Research and shell polling", async () => {
    const registry = await renderRegistry({ api: emptyApi(), storage: memoryStorage() });
    const queued = makeRun("queued", { id: "same-run", thread_id: "same-thread" });
    const running = makeRun("running", { id: "same-run", thread_id: "same-thread" });
    await observe(queued, "舊標題");
    await observe(running, "新標題");

    expect(registry.state().items).toHaveLength(1);
    expect(registry.state().items[0]).toMatchObject({
      runId: "same-run",
      status: "running",
      threadTitle: "新標題",
    });
  });

  it("caps persisted identities at the newest 50 records", async () => {
    let now = 0;
    const storage = memoryStorage();
    await renderRegistry({ api: emptyApi(), storage, now: () => ++now });
    for (let index = 0; index < 55; index += 1) {
      await observe(makeRun("succeeded", {
        id: `run-${String(index).padStart(2, "0")}`,
        thread_id: `thread-${index}`,
      }));
    }

    const persisted = JSON.parse(storage.value(RESEARCH_WORK_STORAGE_KEY) ?? "[]") as Array<{ runId: string }>;
    expect(persisted).toHaveLength(50);
    expect(persisted.map((entry) => entry.runId)).not.toContain("run-00");
    expect(persisted.at(-1)?.runId).toBe("run-54");
  });

  it("hydrates active runs from thread summaries immediately", async () => {
    const active = makeRun("running", { id: "hydrated-run", thread_id: "hydrated-thread" });
    const api = emptyApi({
      getThreads: vi.fn(async () => ({ threads: [makeThread(active, { title: "Hydrated title" })] })),
    });
    const registry = await renderRegistry({ api, storage: memoryStorage() });

    expect(registry.state().items).toEqual([
      expect.objectContaining({ runId: "hydrated-run", threadTitle: "Hydrated title", status: "running" }),
    ]);
    expect(api.getRun).not.toHaveBeenCalled();
  });

  it("reconciles a session-observed run through getResearchRun after it leaves active summaries", async () => {
    const runId = "run/with space";
    window.sessionStorage.setItem(RESEARCH_WORK_STORAGE_KEY, JSON.stringify([
      { runId, threadId: "missing-thread", observedAt: 1 },
    ]));
    const fetchSpy = vi.fn(async (input: string | URL | Request) => {
      expect(String(input)).toContain("/research/runs/run%2Fwith%20space");
      return new Response(JSON.stringify({
        run: makeRun("succeeded", { id: runId, thread_id: "missing-thread" }),
      }), { status: 200, headers: { "Content-Type": "application/json" } });
    });
    vi.stubGlobal("fetch", fetchSpy);
    const registry = await renderRegistry({
      api: emptyApi({ getRun: getResearchRun }),
    });

    expect(fetchSpy).toHaveBeenCalledOnce();
    expect(registry.state().items).toEqual([
      expect.objectContaining({ runId, status: "succeeded", threadTitle: "AI 研究" }),
    ]);
  });

  it("preserves prior work when either polling leg fails", async () => {
    vi.useFakeTimers();
    const getThreads = vi.fn(async () => { throw new Error("thread polling failed"); });
    const getRun = vi.fn(async () => { throw new Error("run polling failed"); });
    const registry = await renderRegistry({
      api: { getThreads, getRun },
      storage: memoryStorage(),
      activePollMs: 5_000,
    });
    await observe(makeRun("running", { id: "preserved-active" }));
    await observe(makeRun("failed", { id: "preserved-terminal" }));

    await act(async () => { await vi.advanceTimersByTimeAsync(5_000); });
    await act(async () => { await registry.state().refresh(); });
    expect(getRun).toHaveBeenCalledWith("preserved-active");
    expect(getThreads).toHaveBeenCalledTimes(2);
    expect(registry.state().items.map((item) => item.runId).sort()).toEqual([
      "preserved-active",
      "preserved-terminal",
    ]);
  });

  it("polls observed active runs every five seconds discovers threads every thirty seconds without overlap and disposes both timers", async () => {
    vi.useFakeTimers();
    let resolveDiscovery: ((value: { threads: ResearchThreadDTO[] }) => void) | null = null;
    let resolveActive: ((value: { run: ResearchRunDTO }) => void) | null = null;
    const getThreads = vi.fn(() => new Promise<{ threads: ResearchThreadDTO[] }>((resolve) => {
      resolveDiscovery = resolve;
    }));
    const getRun = vi.fn((runId: string) => new Promise<{ run: ResearchRunDTO }>((resolve) => {
      resolveActive = (value) => resolve(value);
      void runId;
    }));
    const registry = await renderRegistry({
      api: { getThreads, getRun },
      storage: memoryStorage(),
      activePollMs: 5_000,
      discoveryPollMs: 30_000,
    });
    await observe(makeRun("running", { id: "timer-run" }));

    await act(async () => { await vi.advanceTimersByTimeAsync(60_000); });
    expect(getThreads).toHaveBeenCalledOnce();
    expect(getRun).toHaveBeenCalledOnce();

    await act(async () => {
      resolveDiscovery?.({ threads: [] });
      resolveActive?.({ run: makeRun("running", { id: "timer-run" }) });
      await Promise.resolve();
    });
    await act(async () => { await vi.advanceTimersByTimeAsync(30_000); });
    expect(getThreads).toHaveBeenCalledTimes(2);
    expect(getRun).toHaveBeenCalledTimes(2);

    registry.unmount();
    await vi.advanceTimersByTimeAsync(60_000);
    expect(getThreads).toHaveBeenCalledTimes(2);
    expect(getRun).toHaveBeenCalledTimes(2);
  });

  it("dismisses terminal work without hiding an active run", async () => {
    const registry = await renderRegistry({ api: emptyApi(), storage: memoryStorage() });
    await observe(makeRun("running", { id: "active-run" }));
    await observe(makeRun("succeeded", { id: "terminal-run" }));

    await act(async () => {
      registry.state().dismiss("active-run");
      registry.state().dismiss("terminal-run");
    });

    expect(registry.state().items.map((item) => item.runId)).toEqual(["active-run"]);
  });

  it("does not discover terminal runs that this desktop session never observed", async () => {
    const terminal = makeRun("succeeded", { id: "unobserved-terminal" });
    const api = emptyApi({
      getThreads: vi.fn(async () => ({ threads: [makeThread(terminal)] })),
    });
    const registry = await renderRegistry({ api, storage: memoryStorage() });

    expect(registry.state().items).toEqual([]);
    expect(api.getRun).not.toHaveBeenCalled();
  });
});
