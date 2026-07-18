/** @vitest-environment jsdom */
import React, { useCallback, useRef, useState } from "react";
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
import { getResearchMessages, getResearchThread } from "./api";
import { ResearchHistoryDrawer } from "./ResearchHistoryDrawer";
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

type HistoryThread = ResearchThreadDTO & {
  archived_at: string | null;
  latest_run_status: ResearchRunDTO["status"] | null;
};

function run(id: string, threadId: string, status: ResearchRunDTO["status"]): ResearchRunDTO {
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
    token_usage: null,
    created_at: "2026-07-17T00:00:00Z",
    updated_at: "2026-07-17T00:02:00Z",
  };
}

function thread(
  id: string,
  title: string,
  options: {
    archivedAt?: string | null;
    latestRunStatus?: ResearchRunDTO["status"] | null;
    activeRun?: ResearchRunDTO | null;
    ticker?: string | null;
    updatedAt?: string;
  } = {},
): HistoryThread {
  return {
    id,
    title,
    ticker: options.ticker === undefined ? "MU" : options.ticker,
    provider: "openai",
    model: "gpt-5.6-luna",
    created_at: "2026-07-17T00:00:00Z",
    updated_at: options.updatedAt ?? "2026-07-17T00:02:00Z",
    archived_at: options.archivedAt ?? null,
    latest_run_status: options.latestRunStatus ?? null,
    active_run: options.activeRun ?? null,
  };
}

function message(content: string): ResearchMessageDTO {
  return {
    role: "assistant",
    content,
    provider: "openai",
    model: "gpt-5.6-luna",
    effort: "high",
    tools_used: [],
    tool_calls: [],
    token_usage: null,
    tickers: null,
    elapsed_seconds: 1,
    is_error: false,
    created_at: "2026-07-17T00:03:00Z",
    personalization: null,
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

type RequestOverride = (
  url: URL,
  init: RequestInit | undefined,
) => Response | Promise<Response> | undefined;

function createResearchFetch({
  current = [],
  archived = [],
  messages = {},
  exact = {},
  total,
  override,
}: {
  current?: HistoryThread[];
  archived?: HistoryThread[];
  messages?: Record<string, ResearchMessageDTO[]>;
  exact?: Record<string, HistoryThread>;
  total?: number;
  override?: RequestOverride;
} = {}) {
  const state = { current: [...current], archived: [...archived] };
  const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
    const url = new URL(String(input));
    const method = init?.method ?? "GET";
    const custom = override?.(url, init);
    if (custom !== undefined) return await custom;
    if (url.pathname === "/config/runtime") return json(RUNTIME);
    if (url.pathname === "/query/providers") {
      return json({ providers: { openai: { available: true }, anthropic: { available: true } } });
    }
    if (url.pathname === "/config/model-catalog") return json(CATALOG);
    if (url.pathname === "/profile/investor") return json(PROFILE);
    if (url.pathname === "/research/threads" && method === "GET") {
      const rows = url.searchParams.get("archived") === "archived"
        ? state.archived
        : state.current;
      return json({
        threads: rows,
        total: total ?? rows.length,
        limit: Number(url.searchParams.get("limit") ?? 50),
        offset: Number(url.searchParams.get("offset") ?? 0),
      });
    }
    const exactMatch = url.pathname.match(/^\/research\/threads\/([^/]+)$/);
    if (exactMatch && method === "GET") {
      const id = decodeURIComponent(exactMatch[1]);
      const found = exact[id]
        ?? state.current.find((candidate) => candidate.id === id)
        ?? state.archived.find((candidate) => candidate.id === id);
      return found ? json({ thread: found }) : json({ detail: "thread not found" }, 404);
    }
    if (exactMatch && method === "PATCH") {
      const id = decodeURIComponent(exactMatch[1]);
      const patch = JSON.parse(String(init?.body ?? "{}")) as { title?: string; archived?: boolean };
      const source = [...state.current, ...state.archived];
      const found = source.find((candidate) => candidate.id === id);
      if (!found) return json({ detail: "thread not found" }, 404);
      const updated = {
        ...found,
        ...(patch.title === undefined ? {} : { title: patch.title }),
        ...(patch.archived === undefined
          ? {}
          : { archived_at: patch.archived ? "2026-07-18T01:00:00Z" : null }),
      };
      state.current = state.current.filter((candidate) => candidate.id !== id);
      state.archived = state.archived.filter((candidate) => candidate.id !== id);
      (updated.archived_at ? state.archived : state.current).push(updated);
      return json({ thread: updated });
    }
    if (exactMatch && method === "DELETE") {
      const id = decodeURIComponent(exactMatch[1]);
      state.current = state.current.filter((candidate) => candidate.id !== id);
      state.archived = state.archived.filter((candidate) => candidate.id !== id);
      return json({ thread_id: id, deleted: true });
    }
    const messageMatch = url.pathname.match(/^\/research\/threads\/([^/]+)\/messages$/);
    if (messageMatch) {
      const id = decodeURIComponent(messageMatch[1]);
      return json({ thread_id: id, messages: messages[id] ?? [] });
    }
    const selectionMatch = url.pathname.match(/^\/research\/threads\/([^/]+)\/selection$/);
    if (selectionMatch) {
      return json({ provider: "openai", model: "gpt-5.6-luna", effort: "high" });
    }
    throw new Error(`unhandled test request: ${method} ${url.pathname}${url.search}`);
  });
  return { fetchMock, state };
}

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

function stubMatchMedia(matches: boolean) {
  vi.stubGlobal("matchMedia", vi.fn((query: string) => ({
    matches,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(() => true),
  })));
}

async function flush() {
  await act(async () => {
    for (let index = 0; index < 12; index += 1) await Promise.resolve();
    await new Promise<void>((resolve) => window.setTimeout(resolve, 0));
    for (let index = 0; index < 4; index += 1) await Promise.resolve();
  });
}

const ACTIVE_THREAD_SESSION_KEY = "arkscope.aiResearch.activeThreadId";

function ResearchHistoryHarness({
  navigationRequest,
  narrow,
}: {
  navigationRequest?: ResearchNavigationRequest | null;
  narrow: boolean;
}) {
  const [historyOpen, setHistoryOpen] = useState(false);
  const [selectedThread, setSelectedThread] = useState<ResearchThreadDTO | null>(null);
  const [messages, setMessages] = useState<ResearchMessageDTO[]>([]);
  const [activeRunIds, setActiveRunIds] = useState<ReadonlySet<string>>(new Set());
  const historyTriggerRef = useRef<HTMLButtonElement>(null);
  const hydrationSequenceRef = useRef(0);

  const hydrate = useCallback(async (thread: ResearchThreadDTO) => {
    const sequence = ++hydrationSequenceRef.current;
    setSelectedThread(thread);
    window.sessionStorage.setItem(ACTIVE_THREAD_SESSION_KEY, thread.id);
    const response = await getResearchMessages(thread.id);
    if (sequence !== hydrationSequenceRef.current) return;
    setMessages(response.messages);
  }, []);

  const handleInitialRowsReady = useCallback(async (
    rows: readonly ResearchThreadDTO[],
  ) => {
    setActiveRunIds(new Set(
      rows.flatMap((thread) => thread.active_run ? [thread.active_run.id] : []),
    ));
    const requestedId = navigationRequest?.target.threadId
      ?? window.sessionStorage.getItem(ACTIVE_THREAD_SESSION_KEY);
    let target = requestedId
      ? rows.find((thread) => thread.id === requestedId) ?? null
      : rows[0] ?? null;
    if (requestedId && !target) {
      target = (await getResearchThread(requestedId)).thread;
    }
    if (target) await hydrate(target);
  }, [hydrate, navigationRequest]);

  const handleThreadUpdated = useCallback((updated: ResearchThreadDTO) => {
    setSelectedThread((current) => current?.id === updated.id ? updated : current);
    setActiveRunIds((current) => {
      const next = new Set(current);
      if (updated.active_run) next.add(updated.active_run.id);
      return next;
    });
  }, []);

  const handleThreadDeleted = useCallback((id: string) => {
    setSelectedThread((current) => {
      if (current?.id !== id) return current;
      hydrationSequenceRef.current += 1;
      setMessages([]);
      window.sessionStorage.removeItem(ACTIVE_THREAD_SESSION_KEY);
      return null;
    });
  }, []);

  return (
    <main className="main research">
      <header className="ui-page-header">
        <h1>AI 研究</h1>
        <button ref={historyTriggerRef} type="button" onClick={() => setHistoryOpen(true)}>
          歷史
        </button>
      </header>
      <section className="research-convo">
        <h2 className="research-conversation-title">
          {selectedThread?.title ?? "新對話"}
        </h2>
        <div className="research-messages">
          {messages.length ? messages.map((item, index) => (
            <p key={`${item.created_at}-${index}`}>{item.content}</p>
          )) : <p>問一個開放式問題</p>}
        </div>
        <textarea placeholder="輸入問題" />
        <button type="button" disabled={Boolean(selectedThread?.archived_at)}>送出</button>
      </section>
      <ResearchHistoryDrawer
        open={historyOpen}
        onClose={() => setHistoryOpen(false)}
        activeThreadId={selectedThread?.id ?? null}
        activeRunIds={activeRunIds}
        onInitialRowsReady={(rows) => void handleInitialRowsReady(rows)}
        onSelect={(thread) => {
          void hydrate(thread);
          if (narrow) setHistoryOpen(false);
        }}
        onThreadUpdated={handleThreadUpdated}
        onThreadDeleted={handleThreadDeleted}
        returnFocusRef={historyTriggerRef}
      />
    </main>
  );
}

async function mountResearch({
  backend,
  navigationRequest,
  narrow = false,
}: {
  backend: ReturnType<typeof createResearchFetch>;
  navigationRequest?: ResearchNavigationRequest | null;
  narrow?: boolean;
}) {
  stubMatchMedia(narrow);
  vi.stubGlobal("fetch", backend.fetchMock);
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(
      <ResearchHistoryHarness
        navigationRequest={navigationRequest}
        narrow={narrow}
      />,
    );
  });
  await flush();
  return { host, fetchMock: backend.fetchMock };
}

function buttonByText(text: string, scope: ParentNode = document): HTMLButtonElement {
  const button = Array.from(scope.querySelectorAll<HTMLButtonElement>("button"))
    .find((candidate) => candidate.textContent?.trim() === text);
  if (!button) throw new Error(`button not found: ${text}`);
  return button;
}

function controlByLabel<T extends HTMLInputElement | HTMLSelectElement>(label: string): T {
  const control = document.querySelector<T>(`[aria-label='${label}']`);
  if (!control) throw new Error(`control not found: ${label}`);
  return control;
}

async function click(element: Element) {
  await act(async () => {
    element.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    await Promise.resolve();
  });
}

async function setInput(element: HTMLInputElement | HTMLTextAreaElement, value: string) {
  const prototype = element instanceof HTMLTextAreaElement
    ? HTMLTextAreaElement.prototype
    : HTMLInputElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set;
  await act(async () => {
    setter?.call(element, value);
    element.dispatchEvent(new Event("input", { bubbles: true }));
    await Promise.resolve();
  });
}

async function setSelect(element: HTMLSelectElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value")?.set;
  await act(async () => {
    setter?.call(element, value);
    element.dispatchEvent(new Event("change", { bubbles: true }));
    await Promise.resolve();
  });
}

function requestUrls(fetchMock: ReturnType<typeof vi.fn>, pathname: string): URL[] {
  return fetchMock.mock.calls
    .map(([input]) => new URL(String(input)))
    .filter((url) => url.pathname === pathname);
}

afterEach(() => {
  if (root) act(() => root!.unmount());
  root = null;
  host?.remove();
  host = null;
  window.sessionStorage.clear();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  document.body.replaceChildren();
});

describe("Research history drawer", () => {
  it("renders conversation as the only permanent workspace region", async () => {
    const backend = createResearchFetch({
      current: [thread("thread-a", "Thread A")],
      messages: { "thread-a": [message("Transcript A")] },
    });
    await mountResearch({ backend });

    expect(host!.querySelector(".ui-page-header")).not.toBeNull();
    expect(host!.querySelector(".research-convo")).not.toBeNull();
    expect(host!.querySelector(".research-grid")).toBeNull();
    expect(host!.querySelector(".research-threads")).toBeNull();
    expect(host!.querySelector(".research-trace")).toBeNull();
    expect(document.querySelector("[role='dialog']")).toBeNull();
  });

  it("opens a focus-managed history Drawer and loads a bounded metadata page", async () => {
    const backend = createResearchFetch({
      current: [thread("thread-a", "Thread A"), thread("thread-b", "Thread B")],
      total: 51,
    });
    await mountResearch({ backend });

    const trigger = buttonByText("歷史", host!);
    trigger.focus();
    await click(trigger);

    const drawer = document.querySelector<HTMLElement>("[role='dialog'][aria-modal='true']");
    expect(drawer?.textContent).toContain("研究歷史");
    expect(document.activeElement).toBe(document.querySelector("[aria-label='關閉']"));
    expect(drawer?.textContent).toContain("Thread A");
    expect(drawer?.textContent).toContain("Thread B");
    expect(drawer?.textContent).toContain("2 / 51");
    const historyRequest = requestUrls(backend.fetchMock, "/research/threads")[0];
    expect(Number(historyRequest.searchParams.get("limit"))).toBeGreaterThan(0);
    expect(Number(historyRequest.searchParams.get("limit"))).toBeLessThanOrEqual(200);
    expect(historyRequest.searchParams.get("offset")).toBe("0");
    expect(backend.fetchMock.mock.calls.find(([input]) => (
      new URL(String(input)).pathname === "/research/threads"
    ))?.[1]).toEqual(expect.objectContaining({ signal: expect.any(AbortSignal) }));

    await click(document.querySelector("[aria-label='關閉']")!);
    expect(document.activeElement).toBe(trigger);
  });

  it("serializes filters with local-day UTC bounds, resets offset, and ignores an older filter response", async () => {
    const pageTwoResult = deferred<Response>();
    const oldResult = deferred<Response>();
    const backend = createResearchFetch({
      current: [thread("thread-a", "Thread A")],
      total: 80,
      override: (url) => {
        if (url.pathname !== "/research/threads") return undefined;
        if (url.searchParams.get("q") === "old") return oldResult.promise;
        if (url.searchParams.get("q") === "new") {
          return json({ threads: [thread("thread-new", "Newest match")], total: 80, limit: 50, offset: 0 });
        }
        if (url.searchParams.get("offset") === "50") {
          return pageTwoResult.promise;
        }
        return undefined;
      },
    });
    await mountResearch({ backend });
    await click(buttonByText("歷史", host!));
    await click(buttonByText("載入更多"));
    await vi.waitFor(() => expect(
      requestUrls(backend.fetchMock, "/research/threads")
        .some((url) => url.searchParams.get("offset") === "50"),
    ).toBe(true));

    await setInput(controlByLabel<HTMLInputElement>("搜尋歷史"), "old");
    await setInput(controlByLabel<HTMLInputElement>("Ticker"), "mu");
    await setInput(controlByLabel<HTMLInputElement>("更新日期起日"), "2026-07-17");
    await setInput(controlByLabel<HTMLInputElement>("更新日期迄日"), "2026-07-18");
    await setSelect(controlByLabel<HTMLSelectElement>("執行狀態"), "failed");
    await vi.waitFor(() => expect(
      requestUrls(backend.fetchMock, "/research/threads")
        .some((url) => url.searchParams.get("q") === "old"),
    ).toBe(true));
    await setInput(controlByLabel<HTMLInputElement>("搜尋歷史"), "new");
    await vi.waitFor(() => expect(document.body.textContent).toContain("Newest match"));
    const currentLoadMore = buttonByText("載入更多");
    expect(currentLoadMore.disabled).toBe(false);
    expect(currentLoadMore.getAttribute("aria-busy")).toBeNull();

    const finalRequest = [...requestUrls(backend.fetchMock, "/research/threads")]
      .reverse()
      .find((url) => url.searchParams.get("q") === "new")!;
    expect(finalRequest.searchParams.get("ticker")).toBe("MU");
    expect(finalRequest.searchParams.get("run_state")).toBe("failed");
    expect(finalRequest.searchParams.get("offset")).toBe("0");
    expect(finalRequest.searchParams.get("updated_from")).toBe(
      new Date(2026, 6, 17).toISOString(),
    );
    expect(finalRequest.searchParams.get("updated_before")).toBe(
      new Date(2026, 6, 19).toISOString(),
    );

    pageTwoResult.resolve(json({
      threads: [thread("thread-page-2", "Page two")],
      total: 80,
      limit: 50,
      offset: 50,
    }));
    oldResult.resolve(json({ threads: [thread("thread-old", "Stale match")], total: 1, limit: 50, offset: 0 }));
    await flush();
    expect(document.body.textContent).toContain("Newest match");
    expect(document.body.textContent).not.toContain("Page two");
    expect(document.body.textContent).not.toContain("Stale match");
  });

  it("appends deterministic pages without duplicating thread IDs", async () => {
    const backend = createResearchFetch({
      override: (url) => {
        if (url.pathname !== "/research/threads") return undefined;
        const page = url.searchParams.get("offset") === "50"
          ? [thread("thread-b", "Thread B duplicate"), thread("thread-c", "Thread C")]
          : [thread("thread-a", "Thread A"), thread("thread-b", "Thread B")];
        return json({ threads: page, total: 52, limit: 50, offset: Number(url.searchParams.get("offset") ?? 0) });
      },
    });
    await mountResearch({ backend });
    await click(buttonByText("歷史", host!));
    await click(buttonByText("載入更多"));
    await vi.waitFor(() => expect(
      document.querySelectorAll("[data-research-history-row]"),
    ).toHaveLength(3));

    const ids = Array.from(document.querySelectorAll<HTMLElement>("[data-research-history-row]"))
      .map((row) => row.dataset.researchHistoryRow);
    expect(ids).toEqual(["thread-a", "thread-b", "thread-c"]);
    expect(ids.filter((id) => id === "thread-b")).toHaveLength(1);
  });

  it("hydrates only the latest selected transcript and closes the narrow Drawer", async () => {
    const firstMessages = deferred<Response>();
    const messageRequests: string[] = [];
    const backend = createResearchFetch({
      current: [
        thread("thread-a", "Thread A"),
        thread("thread-b", "Thread B"),
        thread("thread-c", "Thread C"),
      ],
      override: (url) => {
        const match = url.pathname.match(/^\/research\/threads\/([^/]+)\/messages$/);
        if (!match) return undefined;
        const id = decodeURIComponent(match[1]);
        messageRequests.push(id);
        if (id === "thread-a") return firstMessages.promise;
        return json({ thread_id: id, messages: [message(`Transcript ${id}`)] });
      },
    });
    await mountResearch({ backend, narrow: true });
    await click(buttonByText("歷史", host!));
    await click(document.querySelector("[aria-label='開啟對話 Thread B']")!);
    await vi.waitFor(() => expect(host!.textContent).toContain("Transcript thread-b"));

    expect(document.querySelector("[role='dialog']")).toBeNull();
    expect(messageRequests).toEqual(["thread-a", "thread-b"]);
    expect(messageRequests).not.toContain("thread-c");

    firstMessages.resolve(json({ thread_id: "thread-a", messages: [message("Late transcript A")] }));
    await flush();
    expect(host!.textContent).toContain("Transcript thread-b");
    expect(host!.textContent).not.toContain("Late transcript A");
  });

  it("fetches an exact archived out-of-page shell navigation target", async () => {
    const target = thread("thread-z", "Archived target", {
      archivedAt: "2026-07-18T00:00:00Z",
      latestRunStatus: "succeeded",
    });
    const backend = createResearchFetch({
      current: [thread("thread-a", "Thread A")],
      exact: { "thread-z": target },
      messages: {
        "thread-a": [message("Transcript A")],
        "thread-z": [message("Exact archived transcript")],
      },
    });
    const navigationRequest: ResearchNavigationRequest = {
      sequence: 7,
      target: { kind: "research_thread", threadId: "thread-z", runId: "run-z" },
    };
    await mountResearch({ backend, navigationRequest });
    await vi.waitFor(() => expect(host!.textContent).toContain("Exact archived transcript"));

    expect(requestUrls(backend.fetchMock, "/research/threads/thread-z")).toHaveLength(1);
    const messagePaths = backend.fetchMock.mock.calls
      .map(([input]) => new URL(String(input)).pathname)
      .filter((path) => path.endsWith("/messages"));
    expect(messagePaths).toEqual(["/research/threads/thread-z/messages"]);
    expect(window.sessionStorage.getItem("arkscope.aiResearch.activeThreadId")).toBe("thread-z");
    expect(host!.querySelector(".research-conversation-title")?.textContent).toContain("Archived target");
  });

  it("renames inline, rejects a blank title locally, and updates the selected heading", async () => {
    const backend = createResearchFetch({
      current: [thread("thread-a", "Thread A")],
      messages: { "thread-a": [message("Transcript A")] },
    });
    await mountResearch({ backend });
    await click(buttonByText("歷史", host!));
    await click(document.querySelector("[aria-label='重新命名 Thread A']")!);

    const rename = controlByLabel<HTMLInputElement>("對話名稱");
    await setInput(rename, "   ");
    await click(buttonByText("儲存名稱"));
    expect(document.body.textContent).toContain("名稱不可空白");
    expect(backend.fetchMock.mock.calls.filter(([, init]) => init?.method === "PATCH")).toHaveLength(0);

    await setInput(rename, "Renamed research");
    await click(buttonByText("儲存名稱"));
    await vi.waitFor(() => expect(
      document.querySelector("[data-research-history-row='thread-a']")?.textContent,
    ).toContain("Renamed research"));
    expect(host!.querySelector(".research-conversation-title")?.textContent).toBe("Renamed research");
    const patchCall = backend.fetchMock.mock.calls.find(([, init]) => init?.method === "PATCH");
    expect(JSON.parse(String(patchCall?.[1]?.body))).toEqual({ title: "Renamed research" });
  });

  it("blocks active archive, keeps an archived selected transcript inert, and restores it on unarchive", async () => {
    const active = run("run-active", "thread-b", "running");
    let archiveAttempts = 0;
    const backend = createResearchFetch({
      current: [
        thread("thread-a", "Thread A", { latestRunStatus: "succeeded" }),
        thread("thread-b", "Thread B", { latestRunStatus: "running", activeRun: active }),
      ],
      messages: { "thread-a": [message("Transcript A")] },
      override: (url, init) => {
        if (url.pathname !== "/research/threads/thread-a" || init?.method !== "PATCH") return undefined;
        const patch = JSON.parse(String(init.body)) as { archived?: boolean };
        if (patch.archived && archiveAttempts++ === 0) {
          return json({ detail: "active research run prevents archiving this thread" }, 409);
        }
        return undefined;
      },
    });
    await mountResearch({ backend });
    const textarea = host!.querySelector<HTMLTextAreaElement>("textarea[placeholder^='輸入問題']")!;
    await setInput(textarea, "Follow up");
    await click(buttonByText("歷史", host!));

    const activeArchive = document.querySelector<HTMLButtonElement>("[aria-label='封存 Thread B']")!;
    expect(activeArchive.disabled).toBe(true);
    expect(activeArchive.title).toContain("執行中");
    await click(document.querySelector("[aria-label='封存 Thread A']")!);
    await vi.waitFor(() => expect(document.body.textContent).toContain("仍有研究執行中"));
    expect(document.querySelector("[data-research-history-row='thread-a']")).not.toBeNull();

    await click(document.querySelector("[aria-label='封存 Thread A']")!);
    await vi.waitFor(() => expect(
      document.querySelector("[data-research-history-row='thread-a']"),
    ).toBeNull());
    expect(host!.textContent).toContain("Transcript A");
    expect(buttonByText("送出", host!).disabled).toBe(true);

    await setSelect(controlByLabel<HTMLSelectElement>("封存狀態"), "archived");
    await vi.waitFor(() => expect(
      document.querySelector("[data-research-history-row='thread-a']"),
    ).not.toBeNull());
    await click(document.querySelector("[aria-label='取消封存 Thread A']")!);
    await vi.waitFor(() => expect(buttonByText("送出", host!).disabled).toBe(false));
    const patches = backend.fetchMock.mock.calls
      .filter(([, init]) => init?.method === "PATCH")
      .map(([, init]) => JSON.parse(String(init?.body)));
    expect(patches).toEqual([{ archived: true }, { archived: true }, { archived: false }]);
  });

  it("uses ConfirmDialog and preserves a thread on cancel or 409 before successful delete", async () => {
    let deleteAttempts = 0;
    let historyCalls = 0;
    const staleRefresh = deferred<Response>();
    const backend = createResearchFetch({
      current: [thread("thread-a", "Thread A"), thread("thread-b", "Thread B")],
      messages: { "thread-a": [message("Transcript A")] },
      override: (url, init) => {
        if (url.pathname === "/research/threads" && (init?.method ?? "GET") === "GET") {
          historyCalls += 1;
          if (historyCalls === 2) return staleRefresh.promise;
          return undefined;
        }
        if (url.pathname !== "/research/threads/thread-a" || init?.method !== "DELETE") return undefined;
        deleteAttempts += 1;
        return deleteAttempts === 1
          ? json({ detail: "active research run prevents deleting this thread" }, 409)
          : json({ thread_id: "thread-a", deleted: true });
      },
    });
    await mountResearch({ backend });
    await click(buttonByText("歷史", host!));
    await click(document.querySelector("[aria-label='重新整理歷史']")!);
    await vi.waitFor(() => expect(historyCalls).toBe(2));
    await click(document.querySelector("[aria-label='永久刪除 Thread A']")!);
    expect(document.querySelector(".ui-confirm-dialog")?.textContent).toContain("永久刪除");
    await click(buttonByText("取消"));
    expect(deleteAttempts).toBe(0);
    expect(document.querySelector("[data-research-history-row='thread-a']")).not.toBeNull();

    await click(document.querySelector("[aria-label='永久刪除 Thread A']")!);
    await click(buttonByText("永久刪除"));
    await vi.waitFor(() => expect(document.body.textContent).toContain("仍有研究執行中"));
    expect(document.querySelector(".ui-confirm-dialog")?.textContent).toContain("仍有研究執行中");
    expect(document.querySelector("[data-research-history-row='thread-a']")).not.toBeNull();
    expect(host!.textContent).toContain("Transcript A");

    await click(buttonByText("永久刪除"));
    await vi.waitFor(() => expect(
      document.querySelector("[data-research-history-row='thread-a']"),
    ).toBeNull());
    expect(document.querySelector("[data-research-history-row='thread-b']")).not.toBeNull();
    expect(window.sessionStorage.getItem("arkscope.aiResearch.activeThreadId")).toBeNull();
    expect(host!.textContent).not.toContain("Transcript A");
    expect(host!.textContent).toContain("問一個開放式問題");

    staleRefresh.resolve(json({
      threads: [thread("thread-a", "Thread A"), thread("thread-b", "Thread B")],
      total: 2,
      limit: 50,
      offset: 0,
    }));
    await flush();
    expect(document.querySelector("[data-research-history-row='thread-a']")).toBeNull();
  });

  it("preserves prior rows as stale after refresh failure and retries without an empty result", async () => {
    let historyCalls = 0;
    const backend = createResearchFetch({
      override: (url) => {
        if (url.pathname !== "/research/threads") return undefined;
        historyCalls += 1;
        if (historyCalls === 2) return json({ detail: "temporary failure" }, 503);
        const rows = historyCalls >= 3
          ? [thread("thread-a", "Thread A"), thread("thread-b", "Thread B")]
          : [thread("thread-a", "Thread A")];
        return json({ threads: rows, total: rows.length, limit: 50, offset: 0 });
      },
    });
    await mountResearch({ backend });
    await click(buttonByText("歷史", host!));
    await click(document.querySelector("[aria-label='重新整理歷史']")!);
    await vi.waitFor(() => expect(document.body.textContent).toContain("資料可能已過期"));

    expect(document.querySelector("[data-research-history-row='thread-a']")).not.toBeNull();
    expect(document.body.textContent).not.toContain("找不到符合條件的對話");
    await click(buttonByText("重試"));
    await vi.waitFor(() => expect(
      document.querySelector("[data-research-history-row='thread-b']"),
    ).not.toBeNull());
    expect(document.body.textContent).not.toContain("資料可能已過期");
    expect(historyCalls).toBe(3);
  });
});
