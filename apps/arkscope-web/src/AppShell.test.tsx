/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ApiStatus, ResearchRunDTO, RuntimeConfig } from "./api";
import type { NavigationRequest, NavigationTarget } from "./shell/navigation";
import type { ResearchWorkItem, ResearchWorkState } from "./shell/researchWork";

const shellMocks = vi.hoisted(() => ({
  statusError: null as Error | null,
  work: null as ResearchWorkState | null,
  homeProps: null as Record<string, unknown> | null,
  researchProps: null as Record<string, unknown> | null,
  settingsRequests: [] as NavigationRequest[],
}));

const READY_STATUS: ApiStatus = {
  status: "ok",
  timestamp: "2026-07-17T00:00:00Z",
  tools_registered: 37,
  tool_categories: {},
  data_sources: {},
};

const ROUTE = {
  task: "card_synthesis" as const,
  provider: "openai" as const,
  model: "gpt-5.6-luna",
  effort: "high",
  source: "db" as const,
  custom: false,
  warning: null,
};

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
  card_synthesis: ROUTE,
  card_translation: { ...ROUTE, task: "card_translation" },
  ai_research: { ...ROUTE, task: "ai_research" },
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

vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return {
    ...actual,
    apiBase: "http://private-sidecar-fixture:8420",
    getStatus: vi.fn(async () => {
      if (shellMocks.statusError) throw shellMocks.statusError;
      return READY_STATUS;
    }),
    getRuntimeConfig: vi.fn(async () => RUNTIME),
  };
});

vi.mock("./shell/researchWork", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./shell/researchWork")>();
  return {
    ...actual,
    useResearchWorkRegistry: () => shellMocks.work!,
  };
});

vi.mock("./Home", () => ({
  HomeView: (props: {
    onOpenTicker: (ticker: string) => void;
    onNavigate: (view: "Home" | "Watchlist" | "System") => void;
  }) => {
    shellMocks.homeProps = props as unknown as Record<string, unknown>;
    return (
      <main data-testid="home-surface">
        Home surface
        <button type="button" onClick={() => props.onOpenTicker("mu")}>Open MU</button>
      </main>
    );
  },
}));

vi.mock("./Research", () => ({
  ResearchView: (props: {
    navigationRequest?: NavigationRequest | null;
    onObserveRun?: (run: ResearchRunDTO, title?: string) => void;
  }) => {
    shellMocks.researchProps = props as unknown as Record<string, unknown>;
    return (
      <main data-testid="research-surface">
        <pre data-testid="research-request">{JSON.stringify(props.navigationRequest ?? null)}</pre>
        <button
          type="button"
          onClick={() => props.onObserveRun?.(makeRun("observed-from-research"), "Research observer")}
        >
          Observe research run
        </button>
      </main>
    );
  },
}));

vi.mock("./Settings", () => ({
  SettingsView: (props: { navigationRequest?: NavigationRequest | null }) => {
    if (props.navigationRequest) shellMocks.settingsRequests.push(props.navigationRequest);
    return (
      <main data-testid="settings-surface">
        <pre data-testid="settings-request">{JSON.stringify(props.navigationRequest ?? null)}</pre>
      </main>
    );
  },
}));

vi.mock("./TickerDetail", () => ({
  TickerDetailView: (props: { ticker: string; onBack: () => void }) => (
    <main data-testid="ticker-detail">
      Ticker {props.ticker}
      <button type="button" onClick={props.onBack}>Back</button>
    </main>
  ),
}));

vi.mock("./Watchlist", () => ({ WatchlistView: () => <main>Watchlist surface</main> }));
vi.mock("./Universe", () => ({ UniverseView: () => <main>Universe surface</main> }));
vi.mock("./News", () => ({ NewsView: () => <main>News surface</main> }));
vi.mock("./Holdings", () => ({ HoldingsView: () => <main>Holdings surface</main> }));

import { App } from "./App";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

function makeRun(id: string): ResearchRunDTO {
  return {
    id,
    thread_id: `thread-${id}`,
    status: "running",
    question: "private-question",
    ticker: null,
    provider: "openai",
    model: "gpt-5.6-luna",
    effort: "high",
    auth_mode: "api_key",
    credential_id: "local:private",
    started_at: "2026-07-17T00:00:00Z",
    completed_at: null,
    error: null,
    token_usage: null,
    created_at: "2026-07-17T00:00:00Z",
    updated_at: "2026-07-17T00:00:00Z",
  };
}

function workItem(): ResearchWorkItem {
  return {
    runId: "run-shell",
    threadId: "thread-shell",
    threadTitle: "Shell research",
    status: "running",
    createdAt: "2026-07-17T00:00:00Z",
    startedAt: "2026-07-17T00:00:00Z",
    completedAt: null,
  };
}

function emptyWork(items: ResearchWorkItem[] = []): ResearchWorkState {
  const activeCount = items.filter((entry) => ["queued", "running"].includes(entry.status)).length;
  return {
    items,
    activeCount,
    attentionCount: items.length - activeCount,
    refresh: vi.fn(async () => {}),
    observeRun: vi.fn(),
    dismiss: vi.fn(),
  };
}

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

async function renderApp() {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(<App />);
    await Promise.resolve();
    await Promise.resolve();
  });
  return host;
}

async function click(element: Element) {
  await act(async () => {
    element.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    await Promise.resolve();
  });
}

function button(text: string, scope: ParentNode = host!): HTMLButtonElement {
  const match = Array.from(scope.querySelectorAll("button"))
    .find((candidate) => candidate.textContent?.includes(text));
  if (!match) throw new Error(`button not found: ${text}`);
  return match;
}

beforeEach(() => {
  shellMocks.statusError = null;
  shellMocks.work = emptyWork();
  shellMocks.homeProps = null;
  shellMocks.researchProps = null;
  shellMocks.settingsRequests = [];
  window.localStorage.clear();
});

afterEach(() => {
  if (root) act(() => root!.unmount());
  root = null;
  host?.remove();
  host = null;
  vi.clearAllMocks();
});

describe("App shell integration", () => {
  it("renders the grouped shipped shell with no planned controls or right rail", async () => {
    const host = await renderApp();

    expect(Array.from(host.querySelectorAll("[data-shell-nav-group]"), (node) => node.textContent)).toEqual([
      expect.stringContaining("探索"),
      expect.stringContaining("研究"),
      expect.stringContaining("追蹤"),
      expect.stringContaining("系統"),
    ]);
    expect(host.textContent).not.toMatch(/研究筆記|告警|規劃中|面板 ‹/);
    expect(host.querySelector(".rightrail, .rail-tab")).toBeNull();
  });

  it("opens ticker detail from an exact ticker target and returns to the owning view", async () => {
    const host = await renderApp();
    await click(button("Open MU"));

    expect(host.querySelector("[data-testid='ticker-detail']")?.textContent).toContain("Ticker MU");
    expect(host.querySelector("[data-testid='shell-context']")?.textContent).toBe("MU");
    await click(button("Back"));
    expect(host.querySelector("[data-testid='home-surface']")).not.toBeNull();
  });

  it("opens the exact Research thread from a work row", async () => {
    shellMocks.work = emptyWork([workItem()]);
    const host = await renderApp();
    await click(host.querySelector("[data-testid='background-work-trigger']")!);
    await click(document.body.querySelector("[data-work-run-id='run-shell'] [data-work-open]")!);

    expect(host.querySelector("[data-testid='research-request']")?.textContent).toContain('"threadId":"thread-shell"');
    expect(host.querySelector("[data-testid='research-request']")?.textContent).toContain('"runId":"run-shell"');
  });

  it("opens the exact enabled Settings section from a status target", async () => {
    const host = await renderApp();
    await click(button("System / Health"));
    await click(button("資料來源設定"));

    expect(host.querySelector("[data-testid='settings-request']")?.textContent).toContain('"section":"data_sources"');
  });

  it("increments delivery when the same exact target is requested twice", async () => {
    await renderApp();
    await click(button("System / Health"));
    await click(button("資料來源設定"));
    await click(button("System / Health"));
    await click(button("資料來源設定"));

    const dataSourceRequests = shellMocks.settingsRequests.filter((request) => (
      request.target.kind === "settings_section" && request.target.section === "data_sources"
    ));
    expect(dataSourceRequests).toHaveLength(2);
    expect(dataSourceRequests[1]!.sequence).toBeGreaterThan(dataSourceRequests[0]!.sequence);
  });

  it("routes failed sidecar health to System Health", async () => {
    shellMocks.statusError = new Error("recognizable-private-sidecar-error");
    const host = await renderApp();
    await click(button("Sidecar 無法連線"));

    expect(host.textContent).toContain("無法連線至本機 Sidecar");
    expect(host.querySelector("[aria-current='page']")?.textContent).toContain("System / Health");
  });

  it("keeps raw sidecar errors apiBase tool and polling diagnostics out of normal shell and System view", async () => {
    shellMocks.statusError = new Error("recognizable-private-sidecar-error");
    const host = await renderApp();
    await click(button("Sidecar 無法連線"));

    expect(host.textContent).not.toContain("recognizable-private-sidecar-error");
    expect(host.textContent).not.toContain("http://private-sidecar-fixture:8420");
    expect(host.textContent).not.toContain("37 tools");
    expect(host.textContent).not.toContain("openai/gpt-5.6-luna");
    expect(host.textContent).not.toContain("Last status");
  });

  it("limits global background work membership to Research observations", async () => {
    const host = await renderApp();
    expect(shellMocks.homeProps).not.toHaveProperty("onObserveRun");
    await click(button("AI 研究"));

    expect(shellMocks.researchProps?.onObserveRun).toBe(shellMocks.work?.observeRun);
    await click(button("Observe research run"));
    expect(shellMocks.work?.observeRun).toHaveBeenCalledWith(
      expect.objectContaining({ id: "observed-from-research" }),
      "Research observer",
    );
  });
});
