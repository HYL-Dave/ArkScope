/** @vitest-environment jsdom */
import React, { type ComponentProps, type ComponentType } from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import i18n from "i18next";
import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  CredentialAuthType,
  InvestorProfileResponse,
  ModelCatalog,
  ModelTask,
  ResearchMessageDTO,
  ResearchRunDTO,
  ResearchThreadDTO,
  RuntimeConfig,
  TaskRoute,
} from "./api";
import { ApiError } from "./api";
import { ResearchView } from "./Research";
import { RESEARCH_SELECTION_STORAGE_KEY } from "./researchSelection";
import type { NavigationTarget } from "./shell/navigation";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

const route = (
  task: ModelTask,
  provider: "openai" | "anthropic" = "openai",
  model = "gpt-5.6-luna",
  effort = "xhigh",
): TaskRoute => ({
  task, provider, model, effort, source: "db", custom: false, warning: null,
});

const RUNTIME: RuntimeConfig = {
  anthropic: {
    model: "claude-sonnet-5", model_advanced: "claude-opus-5",
    effort: null, thinking: false, key_set: true, credentials: [],
  },
  openai: {
    model: "gpt-5.6-luna", model_advanced: "gpt-5.6-sol",
    reasoning_effort: "xhigh", key_set: true, credentials: [],
  },
  card_synthesis: route("card_synthesis"),
  card_translation: route("card_translation"),
  ai_research: route("ai_research"),
  research_runtime: {
    max_tool_calls: 60, session_timeout_s: 900, per_tool_timeout_s: 45,
    source: "db", db_saved: true, warning: null,
  },
  data_keys: {},
};

function catalog(
  openaiAuth: CredentialAuthType = "api_key",
): ModelCatalog {
  const model = (
    id: string,
    effortOptions: string[],
    over: Record<string, unknown> = {},
  ) => ({
    id, label: id, status: "visible" as const, visible_to_credential: true,
    eligible: true, reason_code: null, thinking_mode: "none",
    effort_options: effortOptions, ...over,
  });
  return {
    providers: ["openai", "anthropic"],
    tasks: [{
      id: "ai_research", label: "AI 研究", description: "",
      default_provider: "openai", recommended_model: "gpt-5.6-luna",
    }],
    current_model_ids: [
      "gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol",
      "claude-fable-5", "claude-opus-5", "claude-sonnet-5",
    ],
    retired_model_ids: ["gpt-5.4-mini", "claude-opus-4-8"],
    models: [
      ...["gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol"].map((id) => ({
        id, provider: "openai" as const, effort_options: ["low", "medium", "high", "xhigh", "max"],
      })),
      ...["claude-fable-5", "claude-opus-5", "claude-sonnet-5"].map((id) => ({
        id, provider: "anthropic" as const, effort_options: ["low", "medium", "high", "xhigh", "max"],
      })),
    ] as unknown as ModelCatalog["models"],
    effort_options: {
      openai: ["low", "medium", "high", "xhigh", "max"].map((id) => ({
        id, provider: "openai", label: id, description: "",
        applies_to_card_tasks: false,
      })),
      anthropic: ["low", "medium", "high", "xhigh", "max"].map((id) => ({
        id, provider: "anthropic", label: id, description: "",
        applies_to_card_tasks: false,
      })),
    },
    routes: {
      card_synthesis: route("card_synthesis"),
      card_translation: route("card_translation"),
      ai_research: route("ai_research"),
    },
    credentials: { openai: [], anthropic: [] },
    custom_allowed: true,
    effective: {
      providers: {
        openai: {
          credential_id: "local:7", auth_mode: openaiAuth,
          label: openaiAuth === "chatgpt_oauth" ? "ChatGPT Plus" : "OpenAI API",
        },
        anthropic: {
          credential_id: "local:4", auth_mode: "api_key", label: "Claude API",
        },
      },
      tasks: {
        ai_research: {
          verified: [], advanced: [], cache_state: "ok",
          discovered_at: "2026-07-18T00:00:00Z", current_provider: "openai",
          providers: {
            openai: {
              executable: true, reason_code: null, cache_state: "ok",
              discovered_at: "2026-07-18T00:00:00Z",
              models: [
                model("gpt-5.6-luna", ["low", "medium", "high", "xhigh", "max"]),
                model("gpt-5.6-sol", ["low", "medium", "high", "xhigh", "max"]),
                model("gpt-5.6-terra", ["low", "medium", "high", "xhigh", "max"], {
                  visible_to_credential: false,
                  reason_code: "model_not_visible",
                }),
              ],
            },
            anthropic: {
              executable: true, reason_code: null, cache_state: "seed_only",
              discovered_at: null,
              models: [
                model("claude-fable-5", ["low", "medium", "high", "xhigh", "max"], { status: "seed" }),
                model("claude-opus-5", ["low", "medium", "high", "xhigh", "max"], { status: "seed" }),
                model("claude-sonnet-5", ["low", "medium", "high", "xhigh", "max"], { status: "seed" }),
              ],
            },
          },
        },
      },
    },
  };
}

const PROFILE: InvestorProfileResponse = {
  profile: {
    enabled: false, primary_preset: "balanced", risk_appetite: null,
    risk_capacity: null, risk_mismatch: "none", holding_horizon: "",
    drawdown_tolerance_pct: null, concentration_limit_pct: null,
    preferred_edge: [], avoidances: [], behavioral_flags: [],
    freeform_notes: "", default_stance: "off", skill_mode: "off",
    last_reviewed_at: null, updated_at: null,
  },
  effective_stance: "off",
  trace: {
    profile_active: false, assistant_stance: "off", skill_mode: "off",
    suggested_skills: [], applied_skills: [],
  },
  context_preview: "",
};

function run(
  id: string,
  threadId: string,
  status: ResearchRunDTO["status"],
  over: Partial<ResearchRunDTO> = {},
): ResearchRunDTO {
  return {
    id, thread_id: threadId, status, question: "What changed?", ticker: "MU",
    provider: "openai", model: "gpt-5.6-luna", effort: "high",
    auth_mode: "api_key", credential_id: "local:7",
    started_at: status === "queued" ? null : "2026-07-18T00:01:00Z",
    completed_at: ["queued", "running"].includes(status)
      ? null
      : "2026-07-18T00:02:00Z",
    error: null, token_usage: null, created_at: "2026-07-18T00:00:00Z",
    updated_at: "2026-07-18T00:02:00Z", ...over,
  };
}

function thread(
  id: string,
  title: string,
  activeRun: ResearchRunDTO | null = null,
): ResearchThreadDTO {
  return {
    id, title, ticker: "MU", provider: "openai", model: "gpt-5.6-luna",
    created_at: "2026-07-18T00:00:00Z",
    updated_at: "2026-07-18T00:02:00Z", active_run: activeRun,
  };
}

function message(
  content: string,
  over: Partial<ResearchMessageDTO> = {},
): ResearchMessageDTO {
  return {
    role: "assistant", content, provider: "openai", model: "gpt-5.6-luna",
    effort: "high", tools_used: [], tool_calls: [], token_usage: null,
    tickers: null, elapsed_seconds: 2, is_error: false,
    created_at: "2026-07-18T00:03:00Z", personalization: null, ...over,
  };
}

function json(value: unknown, status = 200): Response {
  return new Response(JSON.stringify(value), {
    status, headers: { "Content-Type": "application/json" },
  });
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

type FetchOptions = {
  catalog?: ModelCatalog;
  profile?: InvestorProfileResponse;
  threads?: ResearchThreadDTO[];
  messages?: Record<string, ResearchMessageDTO[]>;
  selections?: Record<string, unknown>;
  events?: Record<string, Response | Promise<Response>>;
  runDetails?: Record<string, Response | Promise<Response>>;
  cancelResponse?: Response | Promise<Response>;
  createResponder?: (
    body: Record<string, unknown>,
    index: number,
  ) => Response | Promise<Response>;
};

function stubFetch(options: FetchOptions = {}) {
  const cat = options.catalog ?? catalog();
  const threads = options.threads ?? [];
  const created = new Map<string, ResearchRunDTO>();
  let createIndex = 0;
  return vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
    const raw = typeof input === "string"
      ? input
      : input instanceof URL ? input.href : input.url;
    const url = new URL(raw);
    const method = init?.method ?? "GET";
    if (url.pathname === "/config/runtime") return json(RUNTIME);
    if (url.pathname === "/query/providers") {
      return json({
        providers: { openai: { available: true }, anthropic: { available: true } },
      });
    }
    if (url.pathname === "/config/model-catalog") return json(cat);
    if (url.pathname === "/profile/investor") return json(options.profile ?? PROFILE);
    if (url.pathname === "/research/threads" && method === "GET") {
      return json({ threads, total: threads.length, limit: 50, offset: 0 });
    }
    const exact = url.pathname.match(/^\/research\/threads\/([^/]+)$/);
    if (exact && method === "GET") {
      const found = threads.find((item) => item.id === decodeURIComponent(exact[1]));
      return found ? json({ thread: found }) : json({ detail: "not found" }, 404);
    }
    const selection = url.pathname.match(/^\/research\/threads\/([^/]+)\/selection$/);
    if (selection) {
      const id = decodeURIComponent(selection[1]);
      return json(options.selections?.[id] ?? {
        provider: "openai", model: "gpt-5.6-luna", effort: "high",
      });
    }
    const messages = url.pathname.match(/^\/research\/threads\/([^/]+)\/messages$/);
    if (messages) {
      const id = decodeURIComponent(messages[1]);
      return json({ thread_id: id, messages: options.messages?.[id] ?? [] });
    }
    if (url.pathname === "/research/runs" && method === "POST") {
      const body = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
      if (options.createResponder) {
        return await options.createResponder(body, createIndex++);
      }
      const createdRun = run("created-run", String(body.thread_id), "succeeded", {
        provider: String(body.provider), model: String(body.model),
        effort: String(body.effort),
      });
      created.set(createdRun.id, createdRun);
      return json({ run: createdRun });
    }
    const events = url.pathname.match(/^\/research\/runs\/([^/]+)\/events$/);
    if (events) {
      const id = decodeURIComponent(events[1]);
      const configured = options.events?.[id];
      if (configured) return await configured;
      const active = threads.map((item) => item.active_run)
        .find((item) => item?.id === id);
      return json({
        run: created.get(id) ?? active ?? run(id, "thread-a", "succeeded"),
        events: [], has_more: false,
      });
    }
    const detail = url.pathname.match(/^\/research\/runs\/([^/]+)$/);
    if (detail && method === "GET") {
      const id = decodeURIComponent(detail[1]);
      const configured = options.runDetails?.[id];
      if (configured) return await configured;
      return json({ run: created.get(id) ?? run(id, "thread-a", "succeeded") });
    }
    if (/^\/research\/runs\/[^/]+\/cancel$/.test(url.pathname)) {
      if (options.cancelResponse) return await options.cancelResponse;
      return json({ run: run("cancelled-run", "thread-a", "cancelled") });
    }
    throw new Error("unhandled test request: " + method + " " + url.pathname + url.search);
  });
}

type FutureProps = ComponentProps<typeof ResearchView> & {
  runtime?: RuntimeConfig | null;
  developerMode?: boolean;
  onNavigate?: (target: NavigationTarget) => void;
};
const WorkspaceResearchView = ResearchView as ComponentType<FutureProps>;

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

let matchMediaNarrow = false;
const matchMediaListeners = new Set<() => void>();

function stubMatchMedia(narrow: boolean) {
  matchMediaNarrow = narrow;
  matchMediaListeners.clear();
  vi.stubGlobal("matchMedia", vi.fn((query: string) => ({
    get matches() { return matchMediaNarrow; }, media: query, onchange: null,
    addEventListener: vi.fn((_type: string, listener: () => void) => matchMediaListeners.add(listener)),
    removeEventListener: vi.fn((_type: string, listener: () => void) => matchMediaListeners.delete(listener)),
    addListener: vi.fn(), removeListener: vi.fn(),
    dispatchEvent: vi.fn(() => true),
  })));
}

async function setShellNarrow(narrow: boolean) {
  matchMediaNarrow = narrow;
  await act(async () => {
    for (const listener of matchMediaListeners) listener();
    await Promise.resolve();
  });
  await flush();
}

async function flush() {
  await act(async () => {
    for (let index = 0; index < 10; index += 1) await Promise.resolve();
    await new Promise<void>((resolve) => window.setTimeout(resolve, 0));
    for (let index = 0; index < 4; index += 1) await Promise.resolve();
  });
}

async function mountResearch({
  narrow = false,
  onNavigate = vi.fn(),
}: {
  narrow?: boolean;
  onNavigate?: (target: NavigationTarget) => void;
} = {}) {
  stubMatchMedia(narrow);
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(
      <WorkspaceResearchView
        onOpenTicker={vi.fn()}
        runtime={RUNTIME}
        developerMode={false}
        onNavigate={onNavigate}
      />,
    );
  });
  await flush();
  return { host, onNavigate };
}

function unmount() {
  if (root) act(() => root!.unmount());
  root = null;
  host?.remove();
  host = null;
}

function button(name: string): HTMLButtonElement | undefined {
  return Array.from(document.querySelectorAll("button")).find((item) => (
    item.getAttribute("aria-label") === name || item.textContent?.trim() === name
  )) as HTMLButtonElement | undefined;
}

function buttonContaining(text: string): HTMLButtonElement | undefined {
  return Array.from(document.querySelectorAll("button")).find(
    (item) => item.textContent?.includes(text),
  ) as HTMLButtonElement | undefined;
}

function select(label: string): HTMLSelectElement | null {
  const direct = document.querySelector<HTMLSelectElement>(
    "select[aria-label='" + label + "']",
  );
  if (direct) return direct;
  const owner = Array.from(document.querySelectorAll("label")).find(
    (item) => item.textContent?.includes(label),
  );
  return owner?.querySelector("select") ?? null;
}

async function click(element: Element) {
  await act(async () => {
    (element as HTMLElement).click();
    await Promise.resolve();
  });
  await flush();
}

async function setTextarea(value: string) {
  const area = document.querySelector("textarea") as HTMLTextAreaElement;
  const setter = Object.getOwnPropertyDescriptor(
    HTMLTextAreaElement.prototype, "value",
  )?.set;
  await act(async () => {
    setter?.call(area, value);
    area.dispatchEvent(new Event("input", { bubbles: true }));
    await Promise.resolve();
  });
}

async function setInput(element: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(
    HTMLInputElement.prototype, "value",
  )?.set;
  await act(async () => {
    setter?.call(element, value);
    element.dispatchEvent(new Event("input", { bubbles: true }));
    await Promise.resolve();
  });
  await flush();
}

async function setSelect(element: HTMLSelectElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(
    HTMLSelectElement.prototype, "value",
  )?.set;
  await act(async () => {
    setter?.call(element, value);
    element.dispatchEvent(new Event("change", { bubbles: true }));
    await Promise.resolve();
  });
  await flush();
}

afterEach(async () => {
  unmount();
  window.localStorage.clear();
  window.sessionStorage.clear();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  await i18n.changeLanguage("zh-Hant");
});

describe("Research workspace contracts", () => {
  it("renders the complete English Research workspace around original source content", async () => {
    await i18n.changeLanguage("en");
    const sourceTitle = "SOURCE::MU / Research 原始標題";
    const sourceQuestion = "SOURCE_QUESTION::<keep exactly>";
    const generatedAnswer = "GENERATED_BYTES_ß_研究_[]{}";
    vi.stubGlobal("fetch", stubFetch({
      threads: [thread("thread-english", sourceTitle)],
      messages: {
        "thread-english": [
          message(sourceQuestion, { role: "user" }),
          message(generatedAnswer),
        ],
      },
    }));
    window.sessionStorage.setItem(
      "arkscope.aiResearch.activeThreadId",
      "thread-english",
    );

    await mountResearch();
    await vi.waitFor(() => expect(host!.textContent).toContain(generatedAnswer));

    expect(host!.querySelector("h1")?.textContent).toBe("AI Research");
    expect(button("History")).toBeDefined();
    expect(button("Evidence")).toBeDefined();
    expect(button("New Research")).toBeDefined();
    expect(host!.querySelector("textarea")?.getAttribute("placeholder")).toBe(
      "Ask a question... (Enter to send, Shift+Enter for a new line)",
    );
    expect(host!.querySelector(".research-conversation-title")?.textContent).toBe(sourceTitle);
    expect(host!.textContent).toContain(sourceQuestion);
    expect(host!.textContent).toContain(generatedAnswer);
  });

  it("switches locale without remounting the workspace or resetting thread draft focus or drawers", async () => {
    await i18n.changeLanguage("zh-Hant");
    const fetchMock = stubFetch({
      threads: [thread("thread-stable", "SOURCE_THREAD_TITLE")],
      messages: {
        "thread-stable": [message("SOURCE_ANSWER", {
          tool_calls: [{
            name: "source_tool",
            input: { source: "SOURCE_INPUT" },
            result_preview: "SOURCE_RESULT",
          }],
        })],
      },
    });
    vi.stubGlobal("fetch", fetchMock);
    window.sessionStorage.setItem("arkscope.aiResearch.activeThreadId", "thread-stable");
    await mountResearch();
    await vi.waitFor(() => expect(button("查看證據")).toBeDefined());
    await setTextarea("SOURCE_DRAFT_NOT_TRANSLATED");
    await click(button("查看證據")!);
    await click(document.querySelector("[aria-label='釘選']")!);
    await click(button("歷史")!);

    const workspace = host!.querySelector(".research-workspace")!;
    const textarea = host!.querySelector("textarea") as HTMLTextAreaElement;
    const modelSelect = select("模型")!;
    const modelGroup = modelSelect.querySelector("optgroup")!;
    const modelOption = modelGroup.querySelector("option")!;
    const evidenceDrawer = host!.querySelector(".ui-drawer-inline")!;
    const historyDrawer = document.querySelector("[role='dialog']")!;
    const search = document.querySelector("[aria-label='搜尋歷史']") as HTMLInputElement;
    await setInput(search, "SOURCE_SEARCH_DRAFT");
    search.focus();
    const researchRequests = fetchMock.mock.calls.filter(([input]) => (
      new URL(String(input)).pathname.startsWith("/research/")
    )).length;

    await act(async () => { await i18n.changeLanguage("en"); });
    await flush();

    expect(host!.querySelector(".research-workspace")).toBe(workspace);
    expect(host!.querySelector("textarea")).toBe(textarea);
    expect(select("Model")).toBe(modelSelect);
    expect(modelSelect.querySelector("optgroup")).toBe(modelGroup);
    expect(modelGroup.querySelector("option")).toBe(modelOption);
    expect(textarea.value).toBe("SOURCE_DRAFT_NOT_TRANSLATED");
    expect(host!.querySelector(".ui-drawer-inline")).toBe(evidenceDrawer);
    expect(document.querySelector("[role='dialog']")).toBe(historyDrawer);
    expect(document.querySelector("[aria-label='Search history']")).toBe(search);
    expect(search.value).toBe("SOURCE_SEARCH_DRAFT");
    expect(document.activeElement).toBe(search);
    expect(historyDrawer.textContent).toContain("Research History");
    expect(evidenceDrawer.textContent).toContain("Evidence and Run Details");
    expect(fetchMock.mock.calls.filter(([input]) => (
      new URL(String(input)).pathname.startsWith("/research/")
    ))).toHaveLength(researchRequests);
  });

  it("localizes unselected suggestions and freezes the selected draft across locale changes", async () => {
    await i18n.changeLanguage("zh-Hant");
    vi.stubGlobal("fetch", stubFetch());
    await mountResearch();

    const suggestion = buttonContaining("最近 SA 對 SMCI")!;
    expect(suggestion.textContent).toContain("最近 SA 對 SMCI 有什麼新文章");

    await act(async () => { await i18n.changeLanguage("en"); });
    await flush();
    expect(buttonContaining("What new Seeking Alpha articles")).toBe(suggestion);

    await click(suggestion);
    const textarea = host!.querySelector("textarea") as HTMLTextAreaElement;
    const selectedDraft = "What new Seeking Alpha articles and comment themes are there for SMCI?";
    expect(textarea.value).toBe(selectedDraft);

    await act(async () => { await i18n.changeLanguage("zh-Hant"); });
    await flush();
    expect(textarea.value).toBe(selectedDraft);
    expect(buttonContaining("最近 SA 對 SMCI")).toBe(suggestion);
  });

  it("preserves transcript tool model effort and generated answer bytes", async () => {
    await i18n.changeLanguage("en");
    const originalEffortSummary = i18n.getResource(
      "en",
      "research",
      "workspace.effortSummary",
    ) as string;
    i18n.addResource("en", "research", "workspace.effortSummary", "::effort={{effort}}::");
    try {
      const generatedAnswer = "GENERATED_SOURCE_BYTES::<alpha>&研究[]{}";
      const toolInput = { query: "SOURCE_QUERY::<do-not-localize>", count: 7 };
      const toolResult = "SOURCE_RESULT::<verbatim>";
      const sourceEffort = "source-effort::<>&{{raw}}";
      vi.stubGlobal("fetch", stubFetch({
        threads: [thread("thread-bytes", "SOURCE_TITLE::<verbatim>")],
        messages: {
          "thread-bytes": [message(generatedAnswer, {
            provider: "future-provider",
            model: "model/source-v1",
            effort: sourceEffort,
            tool_calls: [{ name: "source_tool_id", input: toolInput, result_preview: toolResult }],
          })],
        },
      }));
      window.sessionStorage.setItem("arkscope.aiResearch.activeThreadId", "thread-bytes");
      await mountResearch();
      await vi.waitFor(() => expect(host!.textContent).toContain(generatedAnswer));

      const answerBubble = host!.querySelector(".research-bubble.assistant")!;
      const model = answerBubble.querySelector(".research-model")!;
      expect(model.textContent).toBe(
        `future-provider/model/source-v1 ::effort=${sourceEffort}::`,
      );
      await click(answerBubble.querySelector(".research-bubble-actions button")!);
      expect(document.querySelector("[role='dialog']")?.textContent).toContain(
        "Evidence and Run Details",
      );
      const input = document.querySelector(".research-evidence-input")!;
      const preview = document.querySelector(".research-evidence-preview")!;
      expect(input.textContent).toBe(JSON.stringify(toolInput, null, 2));
      expect(preview.textContent).toBe(toolResult);

      await act(async () => { await i18n.changeLanguage("zh-Hant"); });
      await flush();
      expect(host!.querySelector(".research-bubble.assistant")).toBe(answerBubble);
      expect(answerBubble.textContent).toContain(generatedAnswer);
      expect(answerBubble.querySelector(".research-model")).toBe(model);
      expect(model.textContent).toBe(`future-provider/model/source-v1 · ${sourceEffort}`);
      expect(document.querySelector(".research-evidence-input")).toBe(input);
      expect(input.textContent).toBe(JSON.stringify(toolInput, null, 2));
      expect(document.querySelector(".research-evidence-preview")).toBe(preview);
      expect(preview.textContent).toBe(toolResult);
    } finally {
      i18n.addResource("en", "research", "workspace.effortSummary", originalEffortSummary);
    }
  });

  it("renders late stream outcomes in the current locale without replaying the request", async () => {
    await i18n.changeLanguage("zh-Hant");
    const createResult = deferred<Response>();
    const fetchMock = stubFetch({ createResponder: () => createResult.promise });
    vi.stubGlobal("fetch", fetchMock);
    await mountResearch();
    const prompt = "SOURCE_LATE_PROMPT::<verbatim>";
    await setTextarea(prompt);
    await click(button("送出")!);
    await vi.waitFor(() => expect(fetchMock.mock.calls.filter(([, init]) => (
      init?.method === "POST"
    ))).toHaveLength(1));

    await act(async () => {
      await i18n.changeLanguage("en");
      createResult.resolve(json({
        detail: { code: "provider_call_failed", message: "RAW_LATE_DIAGNOSTIC" },
      }, 503));
      await Promise.resolve();
    });
    await flush();
    await vi.waitFor(() => expect(host!.textContent).toContain("Provider call failed"));

    expect(host!.textContent).toContain(prompt);
    expect(host!.textContent).toContain(
      "The Provider could not complete this Research call. Try again later.",
    );
    expect(host!.textContent).not.toContain("RAW_LATE_DIAGNOSTIC");
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(1);
  });

  it("uses structured thread not-found facts instead of parsing Error.message", async () => {
    await i18n.changeLanguage("en");
    const missingCopy = "The requested Research conversation was not found and may have been deleted.";
    const genericCopy = "The requested Research conversation could not be loaded. Try again later.";
    const cases = [
      { id: "missing-null", code: null, expected: missingCopy },
      { id: "missing-code", code: "thread_missing", expected: missingCopy },
      {
        id: "wrong-status-null",
        code: null,
        status: 500,
        expected: genericCopy,
      },
      {
        id: "wrong-status-code",
        code: "thread_missing",
        status: 409,
        expected: genericCopy,
      },
      { id: "unknown-code", code: "future_missing_code", expected: genericCopy },
      {
        id: "wrong-child",
        code: "thread_missing",
        errorPath: "/research/threads/wrong-child/events",
        expected: genericCopy,
      },
      {
        id: "wrong-query",
        code: null,
        errorPath: "/research/threads/wrong-query?force=true",
        expected: genericCopy,
      },
    ] as const;

    for (const scenario of cases) {
      const status = "status" in scenario ? scenario.status : 404;
      unmount();
      window.sessionStorage.clear();
      const baseFetch = stubFetch();
      const requestedPath = `/research/threads/${scenario.id}`;
      const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
        const url = new URL(
          typeof input === "string" ? input : input instanceof URL ? input.href : input.url,
        );
        if (url.pathname === requestedPath) {
          if ("errorPath" in scenario) {
            throw new ApiError(
              "PLANTED_MESSAGE_NOT_AUTHORITY",
              scenario.errorPath,
              status,
              scenario.code,
              "RAW_DIAGNOSTIC_NOT_NORMAL_UI",
            );
          }
          return json({
            detail: scenario.code === null
              ? "PLANTED_MESSAGE_NOT_AUTHORITY"
              : {
                  code: scenario.code,
                  message: "PLANTED_MESSAGE_NOT_AUTHORITY",
                },
          }, status);
        }
        return await baseFetch(input, init);
      });
      vi.stubGlobal("fetch", fetchMock);
      window.sessionStorage.setItem("arkscope.aiResearch.activeThreadId", scenario.id);

      await mountResearch();
      await vi.waitFor(() => expect(host!.textContent).toContain(scenario.expected));
      expect(host!.textContent).not.toContain("PLANTED_MESSAGE");
      expect(host!.textContent).not.toContain("RAW_DIAGNOSTIC");
      expect(fetchMock.mock.calls.filter(([input]) => (
        new URL(String(input)).pathname === requestedPath
      ))).toHaveLength(1);
    }
  });

  it("keeps active progress and error chrome localized in one mounted workspace", async () => {
    await i18n.changeLanguage("zh-Hant");
    const active = run("run-active", "thread-active", "running", {
      error_code: null,
    });
    const activeEvents = deferred<Response>();
    vi.stubGlobal("fetch", stubFetch({
      threads: [thread("thread-active", "SOURCE_ACTIVE_THREAD", active)],
      messages: {
        "thread-active": [message("RAW_ERROR_DETAIL", {
          is_error: true,
          error_code: "model_timeout",
          error: "RAW_ERROR_DETAIL",
        })],
      },
      events: { "run-active": activeEvents.promise },
    }));
    window.sessionStorage.setItem("arkscope.aiResearch.activeThreadId", "thread-active");
    await mountResearch();
    await vi.waitFor(() => expect(host!.querySelector("[data-stage='running']")).not.toBeNull());
    const progress = host!.querySelector("[data-stage='running']")!;
    const errorBubble = host!.querySelector(".research-bubble.assistant.failed")!;

    await act(async () => { await i18n.changeLanguage("en"); });
    await flush();
    expect(host!.querySelector("[data-stage='running']")).toBe(progress);
    expect(progress.textContent).toContain("Running model and tools");
    expect(host!.querySelector(".research-bubble.assistant.failed")).toBe(errorBubble);
    expect(errorBubble.textContent).toContain("Model run timed out");
    expect(errorBubble.textContent).not.toContain("RAW_ERROR_DETAIL");
  });

  it("keeps model selection metadata and no decorated-label reverse parsing", async () => {
    await i18n.changeLanguage("en");
    const sourceCatalog = catalog("chatgpt_oauth");
    const openAi = sourceCatalog.effective?.tasks.ai_research?.providers?.openai;
    expect(openAi).toBeDefined();
    if (!openAi) throw new Error("Research catalog fixture must include OpenAI");
    const selected = openAi.models.find((entry) => entry.id === "gpt-5.6-luna");
    expect(selected).toBeDefined();
    if (!selected) throw new Error("Research catalog fixture must include gpt-5.6-luna");
    selected.label = "Luna display · SOURCE / decorated";
    const fetchMock = stubFetch({ catalog: sourceCatalog });
    vi.stubGlobal("fetch", fetchMock);
    await mountResearch();
    await vi.waitFor(() => expect(host!.querySelector(
      ".research-pickerbar .research-pick select",
    )).not.toBeNull());
    const modelSelect = host!.querySelector<HTMLSelectElement>(
      ".research-pickerbar .research-pick select",
    )!;
    expect(modelSelect.selectedOptions[0]?.textContent).toContain(
      "Luna display · SOURCE / decorated",
    );

    expect(host!.textContent).toContain("Last explicit selection");
    expect(host!.textContent).toContain("ChatGPT subscription sign-in");
    expect(host!.textContent).toContain("Uses subscription quota, not API billing");
    await setTextarea("SOURCE_MODEL_SELECTION_PROMPT");
    await click(button("Send")!);
    await vi.waitFor(() => expect(fetchMock.mock.calls.some(([, init]) => (
      init?.method === "POST"
    ))).toBe(true));
    const createCall = fetchMock.mock.calls.find(([, init]) => init?.method === "POST")!;
    const body = JSON.parse(String(createCall[1]?.body)) as Record<string, unknown>;
    expect(body).toMatchObject({
      provider: "openai",
      model: "gpt-5.6-luna",
      effort: "xhigh",
    });
    expect(String(body.model)).not.toContain("Luna display");
  });

  it("reactively localizes shared stance and trace without remounting Research", async () => {
    await i18n.changeLanguage("zh-Hant");
    const enabledProfile: InvestorProfileResponse = {
      ...PROFILE,
      profile: {
        ...PROFILE.profile,
        enabled: true,
        default_stance: "complementary",
      },
      effective_stance: "complementary",
      trace: {
        profile_active: true,
        assistant_stance: "complementary",
        skill_mode: "suggest_only",
        suggested_skills: ["source-suggested-skill"],
        applied_skills: ["source-applied-skill"],
      },
    };
    const savedApplied = message("Saved applied source answer", {
      personalization: enabledProfile.trace,
    });
    const savedSuggested = message("Saved suggested source answer", {
      personalization: {
        ...enabledProfile.trace,
        suggested_skills: ["source-suggested-skill"],
        applied_skills: [],
      },
    });
    const fetchMock = stubFetch({
      profile: enabledProfile,
      threads: [thread("thread-personalization", "Personalization research")],
      messages: { "thread-personalization": [savedApplied, savedSuggested] },
    });
    vi.stubGlobal("fetch", fetchMock);
    window.sessionStorage.setItem(
      "arkscope.aiResearch.activeThreadId",
      "thread-personalization",
    );
    await mountResearch();
    await vi.waitFor(() => expect(select("立場")).not.toBeNull());

    const stanceSelect = select("立場")!;
    await setSelect(stanceSelect, "growth_opportunity");
    await setTextarea("Keep this Research draft");
    const question = host!.querySelector("textarea") as HTMLTextAreaElement;
    const [appliedBubble, suggestedBubble] = [
      ...host!.querySelectorAll(".research-bubble.assistant"),
    ];
    const model = appliedBubble.querySelector(".research-model")!;
    const requestCount = fetchMock.mock.calls.length;
    expect(appliedBubble.textContent).toContain(
      "立場：互補投資人　套用技能：source-applied-skill",
    );
    expect(suggestedBubble.textContent).toContain(
      "立場：互補投資人　建議技能：source-suggested-skill",
    );

    await act(async () => {
      await i18n.changeLanguage("en");
    });
    await flush();

    expect(select("Stance")).toBe(stanceSelect);
    expect(stanceSelect.value).toBe("growth_opportunity");
    expect(stanceSelect.selectedOptions[0]?.textContent).toBe("Growth opportunity");
    expect(host!.querySelector("textarea")).toBe(question);
    expect(question.value).toBe("Keep this Research draft");
    const relocalizedBubbles = [
      ...host!.querySelectorAll(".research-bubble.assistant"),
    ];
    expect(relocalizedBubbles[0]).toBe(appliedBubble);
    expect(relocalizedBubbles[1]).toBe(suggestedBubble);
    expect(appliedBubble.querySelector(".research-model")).toBe(model);
    expect(model.textContent).toBe("openai/gpt-5.6-luna · high");
    expect(appliedBubble.textContent).toContain(
      "Stance: Complementary　Applied skills: source-applied-skill",
    );
    expect(suggestedBubble.textContent).toContain(
      "Stance: Complementary　Suggested skills: source-suggested-skill",
    );
    expect(fetchMock).toHaveBeenCalledTimes(requestCount);
  });

  it("keeps surrounding Research chrome and source model values unchanged", async () => {
    await i18n.changeLanguage("zh-Hant");
    const personalization = {
      profile_active: true,
      assistant_stance: "complementary" as const,
      skill_mode: "suggest_only" as const,
      suggested_skills: ["source-suggested-skill"],
      applied_skills: ["source-applied-skill"],
    };
    vi.stubGlobal("fetch", stubFetch({
      threads: [thread("thread-evidence-trace", "Evidence trace")],
      messages: {
        "thread-evidence-trace": [message("Source model answer", {
          personalization,
        })],
      },
    }));
    window.sessionStorage.setItem(
      "arkscope.aiResearch.activeThreadId",
      "thread-evidence-trace",
    );
    await mountResearch();
    await click(button("查看證據")!);

    const row = (label: string) => [...document.querySelectorAll(".research-run-detail-list > div")]
      .find((candidate) => candidate.querySelector("dt")?.textContent === label);
    const stanceValue = row("立場")?.querySelector("dd")!;
    const routeValue = row("路線")?.querySelector("dd")!;
    const skillValue = row("套用技能")?.querySelector("dd")!;
    expect(stanceValue.textContent).toBe("互補投資人");
    expect(routeValue.textContent).toBe("openai · gpt-5.6-luna · high");
    expect(skillValue.textContent).toBe("source-applied-skill");

    await act(async () => {
      await i18n.changeLanguage("en");
    });
    await flush();

    expect(row("Stance")?.querySelector("dd")).toBe(stanceValue);
    expect(stanceValue.textContent).toBe("Complementary");
    expect(row("Route")?.querySelector("dd")).toBe(routeValue);
    expect(routeValue.textContent).toBe("openai · gpt-5.6-luna · high");
    expect(row("Applied skills")?.querySelector("dd")).toBe(skillValue);
    expect(skillValue.textContent).toBe("source-applied-skill");
  });

  it("1. exposes New research, History, and Evidence in PageHeader without fixed side columns", async () => {
    vi.stubGlobal("fetch", stubFetch());
    await mountResearch();

    const actions = Array.from(
      host!.querySelectorAll(".ui-page-header-actions button"),
    ).map((item) => item.textContent?.trim());
    expect.soft(actions).toEqual(expect.arrayContaining(["新研究", "歷史", "證據"]));
    expect.soft(host!.querySelector(".research-grid")).toBeNull();
    expect.soft(host!.querySelector(".research-threads")).toBeNull();
    expect.soft(host!.querySelector(".research-trace")).toBeNull();
  });

  it("2. initializes new AI Research with the current Luna xhigh preference", async () => {
    vi.stubGlobal("fetch", stubFetch());
    await mountResearch();

    expect(select("模型")?.value).toBe("gpt-5.6-luna");
    expect(select("effort")?.value).toBe("xhigh");
    const context = host!.querySelector(".ui-page-header-context")?.textContent ?? "";
    expect.soft(context).toContain("openai · gpt-5.6-luna · xhigh");
    expect.soft(context).toContain("上次明確選擇");
  });

  it("3. uses effective provider/model/effort blocks and exposes disabled reasons", async () => {
    const cat = catalog();
    const anthropic = cat.effective!.tasks.ai_research!.providers!.anthropic!;
    anthropic.executable = false;
    anthropic.reason_code = "task_auth_mode_unsupported";
    vi.stubGlobal("fetch", stubFetch({ catalog: cat }));
    await mountResearch();

    const provider = buttonContaining("Anthropic");
    expect.soft(provider?.disabled).toBe(true);
    expect.soft(provider?.textContent).toContain("此登入方式不支援這個任務");
    const hidden = Array.from(select("模型")?.options ?? [])
      .find((option) => option.value === "gpt-5.6-terra");
    expect.soft(hidden?.disabled).toBe(true);
    expect.soft(hidden?.textContent).toContain("探索清單未顯示");
    expect.soft(Array.from(select("effort")?.options ?? []).map((option) => option.value))
      .not.toEqual(expect.arrayContaining(["default", "none"]));
    expect.soft(Array.from(select("模型")?.options ?? []).map((option) => option.value))
      .not.toEqual(expect.arrayContaining(["gpt-5.4-mini", "claude-opus-4-8"]));
    const context = host!.querySelector(".ui-page-header-context")?.textContent ?? "";
    expect.soft(context).toContain(" · xhigh");
  });

  it("recovers a blocked legacy effort when the selected provider is clicked", async () => {
    const threadId = "legacy-default-recovery";
    vi.stubGlobal("fetch", stubFetch({
      threads: [thread(threadId, "Legacy effort")],
      selections: {
        [threadId]: { provider: "openai", model: "gpt-5.6-sol", effort: "default" },
      },
    }));
    window.sessionStorage.setItem("arkscope.aiResearch.activeThreadId", threadId);
    await mountResearch();
    await vi.waitFor(() => expect(button("送出")?.disabled).toBe(true));

    await click(buttonContaining("OpenAI")!);
    await vi.waitFor(() => {
      expect(select("模型")?.value).toBe("gpt-5.6-luna");
      expect(select("effort")?.value).toBe("");
    });
    await setSelect(select("effort")!, "xhigh");
    await setTextarea("Recover the legacy route");
    await vi.waitFor(() => expect(button("送出")?.disabled).toBe(false));
  });

  it("recovers a retired historical model when the selected provider is clicked", async () => {
    const threadId = "retired-model-recovery";
    vi.stubGlobal("fetch", stubFetch({
      threads: [thread(threadId, "Retired model")],
      selections: {
        [threadId]: { provider: "openai", model: "gpt-5.4-mini", effort: "low" },
      },
    }));
    window.sessionStorage.setItem("arkscope.aiResearch.activeThreadId", threadId);
    await mountResearch();
    await vi.waitFor(() => expect(button("送出")?.disabled).toBe(true));

    await click(buttonContaining("OpenAI")!);
    await vi.waitFor(() => {
      expect(select("模型")?.value).toBe("gpt-5.6-luna");
      expect(select("effort")?.value).toBe("");
    });
    await setSelect(select("effort")!, "xhigh");
    await setTextarea("Recover the retired route");
    await vi.waitFor(() => expect(button("送出")?.disabled).toBe(false));
  });

  it("recovers an active incomplete edit when the selected provider is clicked", async () => {
    vi.stubGlobal("fetch", stubFetch());
    await mountResearch();
    await setSelect(select("模型")!, "gpt-5.6-sol");
    expect(select("effort")?.value).toBe("");

    await click(buttonContaining("OpenAI")!);
    await vi.waitFor(() => {
      expect(select("模型")?.value).toBe("gpt-5.6-luna");
      expect(select("effort")?.value).toBe("");
    });
    await setSelect(select("effort")!, "xhigh");
    await setTextarea("Recover the incomplete edit");
    await vi.waitFor(() => expect(button("送出")?.disabled).toBe(false));
  });

  it("4. distinguishes subscription quota from API-key usage in provider context", async () => {
    vi.stubGlobal("fetch", stubFetch({ catalog: catalog("chatgpt_oauth") }));
    await mountResearch();

    const openai = buttonContaining("OpenAI");
    const anthropic = buttonContaining("Anthropic");
    expect.soft(openai?.textContent).toContain("ChatGPT 訂閱登入");
    expect.soft(anthropic?.textContent).toContain("API key");
    expect.soft(host!.textContent).toContain("使用訂閱額度，非 API 帳單");
    if (anthropic) await click(anthropic);
    expect.soft(select("effort")?.value).toBe("");
    const effort = select("effort");
    if (effort) await setSelect(effort, "low");
    expect.soft(host!.textContent).toContain("使用 API 額度，會計入 API 帳單");
  });

  it("5. blocks Send for an invalid saved tuple and navigates exactly to Models settings", async () => {
    window.localStorage.setItem(RESEARCH_SELECTION_STORAGE_KEY, JSON.stringify({
      version: 1,
      tuple: { provider: "openai", model: "gpt-removed", effort: "high" },
    }));
    const onNavigate = vi.fn();
    vi.stubGlobal("fetch", stubFetch());
    await mountResearch({ onNavigate });
    await setTextarea("Keep this draft");

    expect.soft(button("送出")?.disabled).toBe(true);
    expect.soft(host!.textContent).toContain("此登入的探索清單未顯示此模型");
    const settings = button("前往模型設定");
    expect(settings).toBeDefined();
    if (!settings) return;
    await click(settings);
    expect(onNavigate).toHaveBeenCalledWith({
      kind: "settings_section", section: "models",
    });
  });

  it("6. requires a real effort after a model change and sends the persisted low tuple in a new conversation", async () => {
    const fetchMock = stubFetch();
    vi.stubGlobal("fetch", fetchMock);
    await mountResearch();
    const model = select("模型");
    expect(model).not.toBeNull();
    if (!model) return;
    await setSelect(model, "gpt-5.6-sol");
    await setTextarea("Do not silently fallback");

    const effort = select("effort");
    expect.soft(effort?.value).toBe("");
    expect.soft(effort?.getAttribute("aria-invalid")).toBe("true");
    expect.soft(button("送出")?.disabled).toBe(true);
    expect.soft(window.localStorage.getItem(RESEARCH_SELECTION_STORAGE_KEY)).toBeNull();
    if (!effort) return;
    await setSelect(effort, "low");
    const saved = JSON.parse(
      window.localStorage.getItem(RESEARCH_SELECTION_STORAGE_KEY) ?? "null",
    );
    expect(saved?.tuple).toEqual({
      provider: "openai", model: "gpt-5.6-sol", effort: "low",
    });
    await click(button("新研究")!);
    await setTextarea("Persist low exactly");
    await click(button("送出")!);
    await vi.waitFor(() => expect(fetchMock.mock.calls.some(([input, init]) => (
      new URL(typeof input === "string" ? input : (input as Request).url).pathname === "/research/runs"
      && init?.method === "POST"
    ))).toBe(true));
    const create = fetchMock.mock.calls.find(([input, init]) => (
      new URL(typeof input === "string" ? input : (input as Request).url).pathname === "/research/runs"
      && init?.method === "POST"
    ));
    expect(JSON.parse(String(create?.[1]?.body ?? "{}"))).toMatchObject({
      provider: "openai", model: "gpt-5.6-sol", effort: "low",
    });
  });

  it("7. includes semantic provider, model, and effort in every create request", async () => {
    let resolveFirst!: (response: Response) => void;
    const firstCreate = new Promise<Response>((resolve) => { resolveFirst = resolve; });
    const secondEvents = new Promise<Response>(() => undefined);
    const oldRun = run("old-run", "thread-a", "succeeded");
    const fetchMock = stubFetch({
      threads: [thread("thread-a", "Existing research", oldRun)],
      selections: {
        "thread-a": { provider: "openai", model: "gpt-5.6-luna", effort: "xhigh" },
      },
      events: { "run-b": secondEvents },
      createResponder: (body, index) => index === 0
        ? firstCreate
        : json({ run: run("run-b", String(body.thread_id), "running") }),
    });
    vi.stubGlobal("fetch", fetchMock);
    window.sessionStorage.setItem("arkscope.aiResearch.activeThreadId", "thread-a");
    await mountResearch();
    await setTextarea("Create a complete semantic tuple");
    const send = button("送出");
    expect(send?.disabled).toBe(false);
    if (!send) return;
    await click(send);

    const create = fetchMock.mock.calls.find(([input, init]) => (
      new URL(typeof input === "string" ? input : (input as Request).url).pathname
        === "/research/runs"
      && init?.method === "POST"
    ));
    expect(create).toBeDefined();
    const body = JSON.parse(String(create?.[1]?.body ?? "{}"));
    expect(body).toMatchObject({
      provider: "openai", model: "gpt-5.6-luna", effort: "xhigh",
    });
    expect.soft(host!.textContent).toContain("建立執行");
    expect.soft(host!.textContent).not.toContain("研究完成");

    await click(button("新研究")!);
    await setTextarea("Second request owns the workspace");
    await click(button("送出")!);
    await vi.waitFor(() => expect(fetchMock.mock.calls.some(([input]) => (
      new URL(typeof input === "string" ? input : (input as Request).url).pathname
        === "/research/runs/run-b/events"
    ))).toBe(true));
    resolveFirst(json({ run: run("run-a", "thread-a", "running") }));
    await flush();
    expect(fetchMock.mock.calls.some(([input]) => (
      new URL(typeof input === "string" ? input : (input as Request).url).pathname
        === "/research/runs/run-a/events"
    ))).toBe(false);
  });

  it("does not install default when a completed run returns null effort", async () => {
    const completion = deferred<Response>();
    let threadId = "";
    vi.stubGlobal("fetch", stubFetch({
      events: { "null-effort-run": completion.promise },
      createResponder: (body) => {
        threadId = String(body.thread_id);
        return json({ run: run("null-effort-run", threadId, "running") });
      },
    }));
    await mountResearch();
    await setTextarea("Retain nullable run provenance");
    await click(button("送出")!);
    await vi.waitFor(() => expect(select("effort")?.value).toBe("high"));

    await act(async () => {
      completion.resolve(json({
        run: run("null-effort-run", threadId, "succeeded", { effort: null }),
        events: [], has_more: false,
      }));
      await Promise.resolve();
    });
    await vi.waitFor(() => {
      expect(select("effort")?.value).toBe("");
      expect(button("送出")?.disabled).toBe(true);
    });
  });

  it.each([
    { label: "null", effort: null },
    { label: "blank", effort: "  " },
  ])("makes completed $label effort authoritative over the submitted low selection", async ({ effort }) => {
    const completion = deferred<Response>();
    let threadId = "";
    vi.stubGlobal("fetch", stubFetch({
      events: { "completed-provenance-run": completion.promise },
      createResponder: (body) => {
        threadId = String(body.thread_id);
        return json({ run: run("completed-provenance-run", threadId, "running") });
      },
    }));
    await mountResearch();
    const model = select("模型");
    if (!model) throw new Error("Research model picker must be available");
    await setSelect(model, "gpt-5.6-sol");
    const effortPicker = select("effort");
    if (!effortPicker) throw new Error("Research effort picker must be available");
    await setSelect(effortPicker, "low");
    await setTextarea("Completed provenance wins");
    await click(button("送出")!);

    await act(async () => {
      completion.resolve(json({
        run: run("completed-provenance-run", threadId, "succeeded", {
          model: "gpt-5.6-sol", effort,
        }),
        events: [], has_more: false,
      }));
      await Promise.resolve();
    });
    await vi.waitFor(() => {
      expect(select("effort")?.value).toBe("");
      expect(button("送出")?.disabled).toBe(true);
    });
    expect(JSON.parse(window.localStorage.getItem(RESEARCH_SELECTION_STORAGE_KEY) ?? "null"))
      .toMatchObject({ tuple: { provider: "openai", model: "gpt-5.6-sol", effort: "low" } });

    await click(button("新研究")!);
    expect(select("模型")?.value).toBe("gpt-5.6-sol");
    expect(select("effort")?.value).toBe("low");
  });

  it.each([
    { label: "default effort", tuple: { provider: "openai", model: "gpt-5.6-luna", effort: "default" } },
    { label: "none effort", tuple: { provider: "openai", model: "gpt-5.6-luna", effort: "none" } },
    { label: "retired model", tuple: { provider: "openai", model: "gpt-5.4-mini", effort: "low" } },
  ])("keeps historical $label in provenance instead of picker options", async ({ tuple }) => {
    const threadId = `legacy-${tuple.effort}-${tuple.model}`;
    vi.stubGlobal("fetch", stubFetch({
      threads: [thread(threadId, "Legacy provenance")],
      selections: { [threadId]: tuple },
    }));
    window.sessionStorage.setItem("arkscope.aiResearch.activeThreadId", threadId);
    await mountResearch();
    await vi.waitFor(() => expect(button("送出")?.disabled).toBe(true));

    expect(host!.querySelector(".ui-page-header-context")?.textContent)
      .toContain(`${tuple.provider} · ${tuple.model} · ${tuple.effort}`);
    if (tuple.model === "gpt-5.4-mini") {
      expect(Array.from(select("模型")?.options ?? []).map((option) => option.value))
        .not.toContain(tuple.model);
    } else {
      expect(Array.from(select("effort")?.options ?? []).map((option) => option.value))
        .not.toContain(tuple.effort);
    }
    expect(select("effort")?.value).toBe("");
    if (tuple.model === "gpt-5.4-mini") expect(select("模型")?.value).toBe("");
  });

  it("8. keeps an active draft editable with disabled Send and separate Stop and queues nothing", async () => {
    const active = run("active-run", "thread-a", "running");
    const never = new Promise<Response>(() => undefined);
    const fetchMock = stubFetch({
      threads: [thread("thread-a", "Active research", active)],
      events: { "active-run": never },
      cancelResponse: json({ detail: "cancel failed" }, 503),
    });
    vi.stubGlobal("fetch", fetchMock);
    window.sessionStorage.setItem("arkscope.aiResearch.activeThreadId", "thread-a");
    await mountResearch();
    await setTextarea("A local draft while the run continues");

    const area = document.querySelector("textarea") as HTMLTextAreaElement;
    expect.soft(area.disabled).toBe(false);
    expect.soft(area.value).toBe("A local draft while the run continues");
    expect.soft(button("送出")?.disabled).toBe(true);
    expect.soft(button("停止")).toBeDefined();
    button("送出")?.click();
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === "POST"))
      .toHaveLength(0);
    await click(button("停止")!);
    expect.soft(button("送出")?.disabled).toBe(true);
    expect.soft(button("停止")).toBeDefined();
    expect.soft(area.value).toBe("A local draft while the run continues");
    expect(fetchMock.mock.calls.filter(([input, init]) => (
      init?.method === "POST"
      && new URL(typeof input === "string" ? input : (input as Request).url).pathname
        === "/research/runs"
    ))).toHaveLength(0);
  });

  it("9. shows factual queued/running timing, the configured bound, and confirmation grace", async () => {
    const now = Date.now();
    const queued = run("timed-run", "thread-a", "queued", {
      created_at: new Date(now - 1_201_000).toISOString(),
    });
    let resolveEvent!: (response: Response) => void;
    const event = new Promise<Response>((resolve) => { resolveEvent = resolve; });
    vi.stubGlobal("fetch", stubFetch({
      threads: [thread("thread-a", "Timed research", queued)],
      events: { "timed-run": event },
    }));
    window.sessionStorage.setItem("arkscope.aiResearch.activeThreadId", "thread-a");
    await mountResearch();

    expect.soft(host!.textContent).toContain("等待執行");
    expect.soft(host!.textContent).not.toContain("本階段上界");
    resolveEvent(json({
      run: {
        ...queued, status: "running",
        started_at: new Date(now - 901_000).toISOString(),
      },
      events: [], has_more: false,
    }));
    await flush();
    expect.soft(host!.textContent).toContain("模型與工具執行中");
    expect.soft(host!.textContent).toContain("總耗時 20m 01s");
    expect.soft(host!.textContent).toContain("階段耗時 15m 01s");
    expect.soft(host!.textContent).toContain("本階段上界 15m 00s");
    expect.soft(host!.textContent).toContain("已達上界，等待伺服器確認");
  });

  it("10. makes narrow History/Evidence exclusive and permits only wide nonempty Evidence to pin", async () => {
    const evidence = message("Completed answer", {
      run_id: "run-evidence",
      tool_calls: [{
        name: "search_news", input: { ticker: "MU" },
        result_preview: "Reviewed source preview",
      }],
      tools_used: ["search_news"],
      personalization: {
        profile_active: true, assistant_stance: "neutral", skill_mode: "suggest_only",
        suggested_skills: [], applied_skills: ["evidence-first"],
      },
    });
    const options = {
      threads: [thread("thread-a", "Evidence research")],
      messages: { "thread-a": [evidence] },
      runDetails: {
        "run-evidence": json({ run: run("run-evidence", "thread-a", "succeeded", {
          effort: "default",
          assistant_stance: "growth_opportunity",
          token_usage: { total_input_tokens: 100, total_output_tokens: 20, total_tokens: 120 },
        }) }),
      },
    };
    vi.stubGlobal("fetch", stubFetch(options));
    window.sessionStorage.setItem("arkscope.aiResearch.activeThreadId", "thread-a");
    await mountResearch({ narrow: true });
    await click(button("歷史")!);
    const evidenceButton = button("證據");
    expect(evidenceButton).toBeDefined();
    if (!evidenceButton) return;
    await click(evidenceButton);
    expect.soft(document.querySelectorAll("[role='dialog']")).toHaveLength(1);
    expect.soft(document.querySelector("[role='dialog']")?.textContent).toContain("證據");
    expect.soft(document.querySelector("[role='dialog']")?.textContent).not.toContain("研究歷史");
    expect.soft(document.querySelector("[role='dialog']")?.textContent).toContain("中性");
    expect.soft(document.querySelector("[role='dialog']")?.textContent).not.toContain("成長機會派");
    expect.soft(document.querySelector("[role='dialog']")?.textContent).toContain("openai · gpt-5.6-luna · Provider 預設");
    expect.soft(document.querySelector("[role='dialog']")?.textContent).not.toContain(" · default");
    expect.soft(document.querySelector("[role='dialog']")?.textContent).toContain("總輸入 tokens");
    expect.soft(document.querySelector("[role='dialog']")?.textContent).not.toContain("total_input_tokens");

    unmount();
    vi.stubGlobal("fetch", stubFetch(options));
    window.sessionStorage.setItem("arkscope.aiResearch.activeThreadId", "thread-a");
    await mountResearch({ narrow: false });
    await click(button("證據")!);
    const pin = button("釘選");
    expect(pin).toBeDefined();
    if (!pin) return;
    await click(pin);
    const inline = document.querySelector("aside[role='complementary']");
    expect.soft(inline?.textContent).toContain("search_news");
    expect.soft(document.querySelector("[role='dialog']")).toBeNull();
    await click(button("歷史")!);
    expect.soft(document.querySelector("aside[role='complementary']")).not.toBeNull();
    expect.soft(document.querySelector("[role='dialog']")?.textContent).toContain("研究歷史");
    await setShellNarrow(true);
    const remainingDialog = document.querySelector<HTMLElement>("[role='dialog']");
    expect.soft(document.querySelectorAll("[role='dialog']")).toHaveLength(1);
    expect.soft(remainingDialog?.textContent).toContain("研究歷史");
    expect.soft(remainingDialog?.contains(document.activeElement)).toBe(true);
    expect.soft(document.querySelector("aside[role='complementary']")).toBeNull();
  });

  it("11. auto-closes and unpins empty Evidence and reserves zero width", async () => {
    const withEvidence = thread("thread-a", "With evidence");
    const empty = thread("thread-b", "Empty evidence");
    vi.stubGlobal("fetch", stubFetch({
      threads: [withEvidence, empty],
      messages: {
        "thread-a": [message("Answer", {
          tool_calls: [{ name: "search_news", result_preview: "One source" }],
        })],
        "thread-b": [message("Answer without tools")],
      },
    }));
    window.sessionStorage.setItem("arkscope.aiResearch.activeThreadId", "thread-a");
    await mountResearch({ narrow: false });
    const evidenceButton = button("證據");
    expect(evidenceButton).toBeDefined();
    if (!evidenceButton) return;
    await click(evidenceButton);
    await click(button("釘選")!);
    await click(button("歷史")!);
    const emptyRow = document.querySelector(
      "button[aria-label='開啟對話 Empty evidence']",
    );
    expect(emptyRow).not.toBeNull();
    if (!emptyRow) return;
    await click(emptyRow);

    expect.soft(document.querySelector("aside[role='complementary']")).toBeNull();
    expect.soft(host!.querySelector(".research-trace")).toBeNull();
    await click(button("證據")!);
    expect.soft(document.querySelector("[role='dialog']")?.textContent)
      .toContain("此回合沒有可用的工具證據紀錄");
    expect.soft(button("釘選")).toBeUndefined();
  });

  it("12. preserves a completed transcript and presents partial state when run details fail", async () => {
    const raw = "diagnostic backend exploded";
    const fetchMock = stubFetch({
      threads: [thread("thread-a", "Completed research")],
      messages: {
        "thread-a": [message("Durable completed answer", {
          run_id: "run-detail-fails",
          tool_calls: [{ name: "search_news", result_preview: "Stored preview" }],
        })],
      },
      runDetails: {
        "run-detail-fails": json({ detail: raw }, 503),
      },
    });
    vi.stubGlobal("fetch", fetchMock);
    window.sessionStorage.setItem("arkscope.aiResearch.activeThreadId", "thread-a");
    await mountResearch();
    const evidence = button("證據");
    expect(evidence).toBeDefined();
    if (!evidence) return;
    await click(evidence);
    await vi.waitFor(() => expect(fetchMock.mock.calls.some(([input]) => (
      new URL(typeof input === "string" ? input : (input as Request).url).pathname
        === "/research/runs/run-detail-fails"
    ))).toBe(true));

    expect.soft(host!.querySelector(".research-bubble.assistant")?.textContent)
      .toContain("Durable completed answer");
    expect.soft(document.querySelector("[data-state='partial']")).not.toBeNull();
    expect.soft(document.body.textContent).toContain("執行詳情");
    expect.soft(document.body.textContent).not.toContain(raw);

    unmount();
    const unrelatedLatest = run("run-latest", "thread-legacy", "running");
    const activeEvents = json({
      run: unrelatedLatest,
      events: [{
        run_id: "run-latest", seq: 1, type: "tool_start",
        data: { tool: "active_only_tool", input: { ticker: "MU" } },
        created_at: "2026-07-18T00:01:30Z",
      }],
      has_more: false,
    });
    const legacyFetch = stubFetch({
      threads: [thread("thread-legacy", "Legacy research", unrelatedLatest)],
      messages: { "thread-legacy": [message("Legacy answer without run link", {
        token_usage: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
        tools_used: ["search_news"],
        personalization: {
          profile_active: true, assistant_stance: "neutral", skill_mode: "suggest_only",
          suggested_skills: [], applied_skills: ["legacy-skill"],
        },
      })] },
      events: { "run-latest": activeEvents },
    });
    vi.stubGlobal("fetch", legacyFetch);
    window.sessionStorage.setItem("arkscope.aiResearch.activeThreadId", "thread-legacy");
    await mountResearch();
    const messageEvidenceButton = button("查看證據")!;
    await click(messageEvidenceButton);

    expect.soft(document.body.textContent).toContain("此舊回合沒有精確 run 連結");
    expect.soft(document.body.textContent).toContain("openai · gpt-5.6-luna · high");
    expect.soft(document.body.textContent).toContain("輸入 tokens");
    expect.soft(document.body.textContent).toContain("legacy-skill");
    expect.soft(document.body.textContent).not.toContain("active_only_tool");
    expect.soft(legacyFetch.mock.calls.some(([input]) => (
      new URL(typeof input === "string" ? input : (input as Request).url).pathname
        === "/research/runs/run-latest"
    ))).toBe(false);
    await click(button("關閉")!);
    expect(document.activeElement).toBe(messageEvidenceButton);

    unmount();
    vi.stubGlobal("fetch", stubFetch({
      threads: [thread("thread-cancelled", "Cancelled research")],
      messages: {
        "thread-cancelled": [message("raw cancellation detail", {
          is_error: true,
          error_code: "run_cancelled",
          error: "raw cancellation detail",
        })],
      },
    }));
    window.sessionStorage.setItem("arkscope.aiResearch.activeThreadId", "thread-cancelled");
    await mountResearch();
    const cancelledBubble = host!.querySelector(".research-bubble.assistant");
    expect.soft(cancelledBubble?.getAttribute("data-state")).toBe("interrupted");
    expect.soft(cancelledBubble?.textContent).toContain("研究已取消");
    expect.soft(cancelledBubble?.textContent).not.toContain("raw cancellation detail");
  });
});
