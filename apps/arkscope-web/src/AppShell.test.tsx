/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import i18n from "i18next";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  getRuntimeConfig,
  getStatus,
  type ApiStatus,
  type ResearchRunDTO,
  type RuntimeConfig,
} from "./api";
import { createUiLocaleController } from "./i18n/localeController";
import type { NavigationRequest, NavigationTarget } from "./shell/navigation";
import type { ResearchWorkItem, ResearchWorkState } from "./shell/researchWork";

type ExploreCapabilityProps = {
  developerMode: boolean;
  onNavigateTarget: (target: NavigationTarget) => void;
};

const shellMocks = vi.hoisted(() => ({
  statusError: null as unknown,
  statusPromise: null as Promise<ApiStatus> | null,
  work: null as ResearchWorkState | null,
  homeProps: null as Record<string, unknown> | null,
  watchlistProps: null as Record<string, unknown> | null,
  universeProps: null as Record<string, unknown> | null,
  newsProps: null as Record<string, unknown> | null,
  tickerDetailProps: null as Record<string, unknown> | null,
  researchProps: null as Record<string, unknown> | null,
  settingsProps: null as Record<string, unknown> | null,
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
  data_keys: { finnhub: false },
};

vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return {
    ...actual,
    apiBase: "http://private-sidecar-fixture:8420",
    getStatus: vi.fn(async () => {
      if (shellMocks.statusPromise) return shellMocks.statusPromise;
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
  } & Partial<ExploreCapabilityProps>) => {
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
    onNavigationConsumed?: (sequence: number) => void;
    onObserveRun?: (run: ResearchRunDTO, title?: string) => void;
  }) => {
    shellMocks.researchProps = props as unknown as Record<string, unknown>;
    return (
      <main data-testid="research-surface">
        <pre data-testid="research-request">{JSON.stringify(props.navigationRequest ?? null)}</pre>
        <button
          type="button"
          onClick={() => {
            if (props.navigationRequest) props.onNavigationConsumed?.(props.navigationRequest.sequence);
          }}
        >
          Consume research target
        </button>
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
  SettingsView: (props: {
    developerMode: boolean;
    navigationRequest?: NavigationRequest | null;
    settingsReadCache?: unknown;
    onNavigateTarget?: (target: NavigationTarget) => void;
  }) => {
    shellMocks.settingsProps = props as unknown as Record<string, unknown>;
    if (props.navigationRequest) shellMocks.settingsRequests.push(props.navigationRequest);
    return (
      <main data-testid="settings-surface">
        <pre data-testid="settings-request">{JSON.stringify(props.navigationRequest ?? null)}</pre>
        <button
          type="button"
          onClick={() => props.onNavigateTarget?.({
            kind: "universe_lifecycle",
            caseId: "slc-shell-case",
          } as never)}
        >
          Open lifecycle workflow
        </button>
      </main>
    );
  },
}));

vi.mock("./TickerDetail", () => ({
  TickerDetailView: (props: {
    ticker: string;
    onBack: () => void;
  } & Partial<ExploreCapabilityProps>) => {
    shellMocks.tickerDetailProps = props as unknown as Record<string, unknown>;
    return (
      <main data-testid="ticker-detail">
        Ticker {props.ticker}
        <button type="button" onClick={props.onBack}>Back</button>
      </main>
    );
  },
}));

vi.mock("./Watchlist", () => ({
  WatchlistView: (props: Partial<ExploreCapabilityProps>) => {
    shellMocks.watchlistProps = props as Record<string, unknown>;
    return <main data-testid="watchlist-surface">Watchlist surface</main>;
  },
}));
vi.mock("./Universe", () => ({
  UniverseView: (props: Partial<ExploreCapabilityProps> & {
    navigationRequest?: NavigationRequest | null;
  }) => {
    shellMocks.universeProps = props as Record<string, unknown>;
    return (
      <main data-testid="universe-surface">
        Universe surface
        <pre data-testid="universe-request">{JSON.stringify(props.navigationRequest ?? null)}</pre>
        <button
          type="button"
          onClick={() => props.onNavigateTarget?.({
            kind: "settings_section",
            section: "data_sources",
          })}
        >
          Recover data sources
        </button>
      </main>
    );
  },
}));
vi.mock("./News", () => ({
  NewsView: (props: Partial<ExploreCapabilityProps>) => {
    shellMocks.newsProps = props as Record<string, unknown>;
    return <main data-testid="news-surface">News surface</main>;
  },
}));
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

function button(text: string, scope: ParentNode = host!): HTMLButtonElement {
  const match = Array.from(scope.querySelectorAll("button"))
    .find((candidate) => candidate.textContent?.includes(text));
  if (!match) throw new Error(`button not found: ${text}`);
  return match;
}

function capturedSettingsReadCache(): unknown {
  return shellMocks.settingsProps?.settingsReadCache;
}

beforeEach(() => {
  shellMocks.statusError = null;
  shellMocks.statusPromise = null;
  shellMocks.work = emptyWork();
  shellMocks.homeProps = null;
  shellMocks.watchlistProps = null;
  shellMocks.universeProps = null;
  shellMocks.newsProps = null;
  shellMocks.tickerDetailProps = null;
  shellMocks.researchProps = null;
  shellMocks.settingsProps = null;
  shellMocks.settingsRequests = [];
  window.localStorage.clear();
});

afterEach(() => {
  if (root) act(() => root!.unmount());
  root = null;
  host?.remove();
  host = null;
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe("App shell integration", () => {
  it("keeps_one_Settings_cache_across_view_unmount_and_remount", async () => {
    const host = await renderApp();

    await click(button("設定"));
    const first = capturedSettingsReadCache();
    expect(first).toBeTypeOf("object");

    await click(button("工作台"));
    expect(host.querySelector("[data-testid='settings-surface']")).toBeNull();
    await click(button("設定"));

    expect(capturedSettingsReadCache()).toBe(first);
  });

  it("creates_a_fresh_Settings_cache_for_a_new_App_root", async () => {
    await renderApp();
    await click(button("設定"));
    const first = capturedSettingsReadCache();
    expect(first).toBeTypeOf("object");

    act(() => root!.unmount());
    root = null;
    host?.remove();
    host = null;
    shellMocks.settingsProps = null;

    await renderApp();
    await click(button("設定"));
    const second = capturedSettingsReadCache();

    expect(second).toBeTypeOf("object");
    expect(second).not.toBe(first);
  });

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
    await click(button("Consume research target"));
    expect(host.querySelector("[data-testid='research-request']")?.textContent).toBe("null");
    await click(button("工作台"));
    await click(button("AI 研究"));
    expect(host.querySelector("[data-testid='research-request']")?.textContent).toBe("null");
  });

  it("opens the exact enabled Settings section from a status target", async () => {
    const host = await renderApp();
    await click(button("System / Health"));
    await click(button("資料來源設定"));

    expect(host.querySelector("[data-testid='settings-request']")?.textContent).toContain('"section":"data_sources"');
  });

  it("opens the Universe lifecycle workflow from the Settings health link", async () => {
    const host = await renderApp();
    await click(button("設定"));
    await click(button("Open lifecycle workflow"));

    expect(host.querySelector("[data-testid='universe-request']")?.textContent).toContain(
      '"kind":"universe_lifecycle"',
    );
    expect(host.querySelector("[data-testid='universe-request']")?.textContent).toContain(
      '"caseId":"slc-shell-case"',
    );
  });

  it("passes Developer Mode into Settings without adding a second owner", async () => {
    const host = await renderApp();
    await click(button("System / Health"));
    const developerMode = host.querySelector<HTMLInputElement>(
      '#developer-mode-heading + label input[type="checkbox"]',
    );
    expect(developerMode).not.toBeNull();

    await act(async () => {
      developerMode!.click();
      await Promise.resolve();
    });
    await click(button("資料來源設定"));

    expect(shellMocks.settingsProps?.developerMode).toBe(true);
    expect(window.localStorage.getItem("arkscope.shell.developerMode.v1")).toBe("enabled");
    expect(Object.keys(window.localStorage)).toEqual(["arkscope.shell.developerMode.v1"]);
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

  it("renders English overlay navigation names from the shell namespace", async () => {
    stubMatchMedia(true);
    await act(async () => { await i18n.changeLanguage("en"); });
    const host = await renderApp();
    const trigger = host.querySelector('[aria-label="Open navigation"]');

    expect(trigger).not.toBeNull();
    await click(trigger!);
    const dialog = document.body.querySelector('[role="dialog"]');
    expect(dialog?.textContent).toContain("Navigation");
    expect(dialog?.querySelector('nav[aria-label="Primary navigation"]')).not.toBeNull();
  });

  it("switches locale without losing the selected shell view", async () => {
    const host = await renderApp();
    await click(button("AI 研究"));
    const surface = host.querySelector('[data-testid="research-surface"]');

    await act(async () => { await i18n.changeLanguage("en"); });
    expect(host.querySelector('[data-testid="research-surface"]')).toBe(surface);
    expect(host.querySelector('[data-testid="shell-context"]')?.textContent).toBe("AI Research");
    expect(host.querySelector("[aria-current='page']")?.textContent).toContain("AI Research");
  });

  it("switches locale without closing the background-work drawer", async () => {
    shellMocks.work = emptyWork([workItem()]);
    const host = await renderApp();
    const home = host.querySelector('[data-testid="home-surface"]');
    const trigger = host.querySelector('[data-testid="background-work-trigger"]')!;
    await click(trigger);
    const dialog = document.body.querySelector('[role="dialog"]');
    const row = document.body.querySelector("[data-work-run-id='run-shell']");
    const focusedControl = document.activeElement;

    await act(async () => { await i18n.changeLanguage("en"); });
    expect(document.body.querySelector('[role="dialog"]')).toBe(dialog);
    expect(document.body.querySelector("[data-work-run-id='run-shell']")).toBe(row);
    expect(host.querySelector('[data-testid="home-surface"]')).toBe(home);
    expect(document.activeElement).toBe(focusedControl);
    expect(dialog?.textContent).toContain("Background work");
    expect(trigger.textContent).toContain("Running 1");
  });

  it("passes Developer Mode and the shared navigation dispatcher to Explore surfaces", async () => {
    const host = await renderApp();
    await click(button("System / Health"));
    const developerMode = host.querySelector<HTMLInputElement>(
      '#developer-mode-heading + label input[type="checkbox"]',
    );
    await act(async () => {
      developerMode!.click();
      await Promise.resolve();
    });

    await click(button("工作台"));
    const homeProps = shellMocks.homeProps!;
    const dispatcher = homeProps.onNavigateTarget;
    expect(dispatcher).toEqual(expect.any(Function));
    expect(homeProps.onNavigate).not.toBe(dispatcher);

    await click(button("自選股"));
    await click(button("全部標的"));
    await click(button("新聞·事件"));
    await act(async () => {
      (dispatcher as (target: NavigationTarget) => void)({ kind: "ticker", ticker: "CAPS" });
      await Promise.resolve();
    });

    for (const props of [
      homeProps,
      shellMocks.watchlistProps!,
      shellMocks.universeProps!,
      shellMocks.newsProps!,
      shellMocks.tickerDetailProps!,
    ]) {
      expect(props.developerMode).toBe(true);
      expect(props.onNavigateTarget).toBe(dispatcher);
    }
  });

  it("routes an Explore recovery action through the exact existing Settings anchor", async () => {
    await renderApp();
    const homeDispatcher = shellMocks.homeProps?.onNavigateTarget;
    await click(button("全部標的"));

    expect(shellMocks.universeProps?.onNavigateTarget).toBe(homeDispatcher);
    expect(homeDispatcher).toEqual(expect.any(Function));
    await click(button("Recover data sources"));

    expect(shellMocks.settingsRequests).toHaveLength(1);
    expect(shellMocks.settingsRequests[0]?.target).toEqual({
      kind: "settings_section",
      section: "data_sources",
    });
  });

  it("switches locale without replacing the active Explore surface or detail ticker", async () => {
    const host = await renderApp();
    await click(button("全部標的"));
    const universe = host.querySelector('[data-testid="universe-surface"]');
    const dispatcher = shellMocks.universeProps?.onNavigateTarget;

    expect(dispatcher).toEqual(expect.any(Function));
    await act(async () => { await i18n.changeLanguage("en"); });
    expect(host.querySelector('[data-testid="universe-surface"]')).toBe(universe);

    await act(async () => {
      (dispatcher as (target: NavigationTarget) => void)({ kind: "ticker", ticker: "BRK.B" });
      await Promise.resolve();
    });
    const detail = host.querySelector('[data-testid="ticker-detail"]');
    expect(detail?.textContent).toContain("Ticker BRK.B");
    expect(shellMocks.tickerDetailProps?.ticker).toBe("BRK.B");

    await act(async () => { await i18n.changeLanguage("zh-Hant"); });
    expect(host.querySelector('[data-testid="ticker-detail"]')).toBe(detail);
    expect(shellMocks.tickerDetailProps?.ticker).toBe("BRK.B");
  });

  it("stores sidecar failures as structured System outcomes without raw Error.message", async () => {
    const hostile = Object.create(Error.prototype) as Error;
    Object.defineProperty(hostile, "message", {
      configurable: true,
      get() {
        throw new Error("raw Error.message was read");
      },
    });
    shellMocks.statusError = hostile;

    const host = await renderApp();
    await click(button("Sidecar 無法連線"));

    expect(host.textContent).toContain("無法連線至本機 Sidecar");
    expect(host.textContent).not.toContain("raw Error.message was read");
    expect(host.textContent).not.toContain("recognizable-private-sidecar-error");
  });

  it("renders System sidecar copy from the system namespace in both locales", async () => {
    let rejectStatus!: (reason: unknown) => void;
    shellMocks.statusPromise = new Promise<ApiStatus>((_resolve, reject) => {
      rejectStatus = reject;
    });
    const expected = {
      "zh-Hant": {
        loading: "正在連線至本機 Sidecar…",
        failure: "無法連線至本機 Sidecar",
        retry: "重試",
        ready: "本機 Sidecar 已連線。",
        chrome: [
          "資料來源設定",
          "Developer Mode",
          "顯示本機診斷資訊",
          "Models in use",
          "card synthesis",
          "card translation",
          "anthropic (default / advanced)",
          "openai (default / advanced)",
          "API keys present",
          "✓ set",
          "✗ missing",
          "Registry tools",
          "Server time",
          "Status",
          "Tool categories",
          "Data sources (tickers)",
        ],
      },
      en: {
        loading: "Connecting to the local Sidecar…",
        failure: "Could not connect to the local Sidecar",
        retry: "Retry",
        ready: "Local Sidecar connected.",
        chrome: [
          "Data source settings",
          "Developer Mode",
          "Show local diagnostic information",
          "Models in use",
          "card synthesis",
          "card translation",
          "anthropic (default / advanced)",
          "openai (default / advanced)",
          "API keys present",
          "✓ set",
          "✗ missing",
          "Registry tools",
          "Server time",
          "Status",
          "Tool categories",
          "Data sources (tickers)",
        ],
      },
    } as const;
    expect(Object.values(expected["zh-Hant"]).flat()).toHaveLength(20);
    expect(Object.values(expected.en).flat()).toHaveLength(20);

    const host = await renderApp();
    await click(button("System / Health"));
    expect(host.textContent).toContain(expected["zh-Hant"].loading);
    await act(async () => { await i18n.changeLanguage("en"); });
    expect(host.textContent).toContain(expected.en.loading);

    shellMocks.statusPromise = null;
    await act(async () => {
      rejectStatus(new ApiError(
        "private status failure",
        "/status?private=1",
        503,
        "sidecar_unavailable",
        "sqlite3 traceback /home/private",
      ));
      await Promise.resolve();
    });
    expect(host.textContent).toContain(expected.en.failure);
    expect(host.textContent).toContain(expected.en.retry);
    await act(async () => { await i18n.changeLanguage("zh-Hant"); });
    expect(host.textContent).toContain(expected["zh-Hant"].failure);
    expect(host.textContent).toContain(expected["zh-Hant"].retry);

    shellMocks.statusError = null;
    await click(button(expected["zh-Hant"].retry));
    expect(host.textContent).toContain(expected["zh-Hant"].ready);
    const developerMode = host.querySelector<HTMLInputElement>(
      '#developer-mode-heading + label input[type="checkbox"]',
    )!;
    await act(async () => developerMode.click());
    for (const copy of expected["zh-Hant"].chrome) {
      expect.soft(host.textContent, `zh-Hant: ${copy}`).toContain(copy);
    }

    await act(async () => { await i18n.changeLanguage("en"); });
    for (const copy of expected.en.chrome) {
      expect.soft(host.textContent, `en: ${copy}`).toContain(copy);
    }
    await act(async () => developerMode.click());
    expect(host.textContent).toContain(expected.en.ready);
  });

  it("shows only reviewed sidecar facts in Developer Mode", async () => {
    shellMocks.statusError = new ApiError(
      "private failure?token=secret",
      "/status?token=secret",
      503,
      "sidecar_unavailable",
      "sqlite3.OperationalError at /home/private/sidecar.db",
    );
    const host = await renderApp();
    await click(button("Sidecar 無法連線"));
    const developerMode = host.querySelector<HTMLInputElement>(
      '#developer-mode-heading + label input[type="checkbox"]',
    )!;
    await act(async () => developerMode.click());

    expect(host.textContent).toContain("503");
    expect(host.textContent).toContain("sidecar_unavailable");
    expect(host.textContent).toContain("/status");
    expect(host.textContent).not.toContain("private failure");
    expect(host.textContent).not.toContain("token=secret");
    expect(host.textContent).not.toContain("sqlite3");
    expect(host.textContent).not.toContain("/home/private");
  });

  it("preserves the active view focus and status state across locale changes", async () => {
    const host = await renderApp();
    await click(button("System / Health"));
    const systemView = host.querySelector("main.main");
    const developerMode = host.querySelector<HTMLInputElement>(
      '#developer-mode-heading + label input[type="checkbox"]',
    )!;
    await act(async () => developerMode.click());
    const statusValue = Array.from(host.querySelectorAll(".tile-value"))
      .find((node) => node.textContent === "ok")!;
    const settingsButton = button("資料來源設定");
    settingsButton.focus();
    const statusCalls = vi.mocked(getStatus).mock.calls.length;

    await act(async () => { await i18n.changeLanguage("en"); });

    expect(host.querySelector("main.main")).toBe(systemView);
    expect(document.activeElement).toBe(settingsButton);
    expect(Array.from(host.querySelectorAll(".tile-value")).find((node) => node.textContent === "ok"))
      .toBe(statusValue);
    expect(vi.mocked(getStatus)).toHaveBeenCalledTimes(statusCalls);
    expect(host.textContent).toContain("Data source settings");
  });

  it("issues only the locale preference PUT while System copy changes", async () => {
    const host = await renderApp();
    await click(button("System / Health"));
    const dataCalls = {
      status: vi.mocked(getStatus).mock.calls.length,
      runtime: vi.mocked(getRuntimeConfig).mock.calls.length,
    };
    const authority = {
      get: vi.fn(async () => ({ locale: "zh-Hant" as const, source: "stored" as const })),
      put: vi.fn(async (locale: "zh-Hant" | "en") => ({ locale, source: "stored" as const })),
    };
    const controller = createUiLocaleController({
      initialLocale: "zh-Hant",
      authority,
      applyLocale: (locale) => { void i18n.changeLanguage(locale); },
      writeCache: vi.fn(),
    });

    await act(async () => { await controller.setLocale("en"); });

    expect(authority.put).toHaveBeenCalledOnce();
    expect(authority.put).toHaveBeenCalledWith("en");
    expect(authority.get).not.toHaveBeenCalled();
    expect(vi.mocked(getStatus)).toHaveBeenCalledTimes(dataCalls.status);
    expect(vi.mocked(getRuntimeConfig)).toHaveBeenCalledTimes(dataCalls.runtime);
    expect(host.textContent).toContain("Local Sidecar connected.");
  });
});
