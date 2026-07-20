/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import i18n from "i18next";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ModelCatalog, ModelTask, NewsStatus, TaskRoute } from "./api";
import { formatSystemTimestamp } from "./timeDisplay";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

const mocked = vi.hoisted(() => ({
  newsStatus: null as NewsStatus | null,
  newsError: null as Error | null,
}));

const emptyCatalog: ModelCatalog = {
  providers: ["anthropic", "openai"],
  tasks: [],
  models: [],
  effort_options: { anthropic: [], openai: [] },
  routes: {} as Record<ModelTask, TaskRoute>,
  credentials: { anthropic: [], openai: [] },
  custom_allowed: true,
};

vi.mock("./api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./api")>();
  return {
    ...actual,
    getModelCatalog: vi.fn(async () => emptyCatalog),
    getNewsStatus: vi.fn(async () => {
      if (mocked.newsError) throw mocked.newsError;
      return mocked.newsStatus;
    }),
    setNormalizedNewsWrites: vi.fn(),
    setUseLocalNews: vi.fn(),
  };
});

import { getNewsStatus } from "./api";
import { SettingsView } from "./Settings";

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

function dispose() {
  if (root) act(() => root!.unmount());
  host?.remove();
  root = null;
  host = null;
}

const newsStatus = (over: Partial<NewsStatus> = {}): NewsStatus => ({
  market_db: "/tmp/market.db",
  exists: true,
  news: { row_count: 10, source_count: 2, latest_published: "2026-06-27T00:00:00+00:00" },
  use_local_news_setting: true,
  setting_explicit: true,
  env_override: true,
  env_value: true,
  direct_active: true,
  normalized_writes_setting: false,
  normalized_writes_setting_explicit: false,
  normalized_writes_env_override: false,
  normalized_writes_env_value: null,
  write_route: "normalized",
  write_route_reason: "test",
  news_pg_exit_completed: true,
  news_hard_local: true,
  pg_news_route_available: false,
  sync: null,
  ...over,
});

function newsSync(
  status: NonNullable<NewsStatus["sync"]>["status"],
  over: Partial<NonNullable<NewsStatus["sync"]>> = {},
): NonNullable<NewsStatus["sync"]> {
  return {
    status,
    last_success: "2026-07-20T03:00:00Z",
    last_attempt: "2026-07-21T04:05:06Z",
    last_error: null,
    rows_added: 7,
    updated_at: "2026-07-21T04:05:07Z",
    providers: {},
    ...over,
  };
}

async function flush() {
  await act(async () => {
    await Promise.resolve();
  });
}

async function renderNewsSection(developerMode = false) {
  window.localStorage.setItem("arkscope.settings.activeGroup.v1", "data_sync");
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(React.createElement(SettingsView, {
      runtime: null,
      developerMode,
      onRuntimeChanged: vi.fn(),
    }));
  });
  await flush();
  await flush();
}

beforeEach(async () => {
  await i18n.changeLanguage("zh-Hant");
  vi.clearAllMocks();
});

afterEach(() => {
  dispose();
  mocked.newsStatus = null;
  mocked.newsError = null;
  vi.clearAllMocks();
});

describe("SettingsView news storage copy", () => {
  it("renders_normal_news_status_without_migration_narration", async () => {
    mocked.newsStatus = newsStatus();
    await renderNewsSection();

    const section = host!.querySelector('[data-settings-anchor="news_storage"]');
    expect(section?.querySelector("h2")?.textContent).toBe("新聞資料");
    expect(host!.textContent).toContain("10 篇 · 2 來源");
    expect(host!.textContent).toContain("最近收集成功");
    expect(host!.textContent).toContain("各來源排程與手動執行由 Data Sources 管理。");
    expect(host!.textContent).not.toMatch(/PostgreSQL|PG exit|SQLite|legacy|mirror|本地新聞庫/);
  });

  it("hides_both_migration_controls_even_for_a_pre_exit_compatibility_response", async () => {
    mocked.newsStatus = newsStatus({
      news_hard_local: false,
      news_pg_exit_completed: false,
      pg_news_route_available: true,
      direct_active: false,
    });
    await renderNewsSection();
    const newsAnchor = host!.querySelector('[data-settings-anchor="news_storage"]')!;
    expect(newsAnchor.querySelectorAll("input[type='checkbox']")).toHaveLength(0);
    expect(host!.textContent).not.toContain("Legacy local writer");
    expect(host!.textContent).not.toContain("Normalized news writes");
    const api = await import("./api");
    expect(api.setUseLocalNews).not.toHaveBeenCalled();
    expect(api.setNormalizedNewsWrites).not.toHaveBeenCalled();
  });

  it("renders_empty_and_failed_news_statuses_as_user_outcomes", async () => {
    mocked.newsStatus = newsStatus({
      exists: false,
      news: { row_count: 0, source_count: 0, latest_published: null },
    });
    await renderNewsSection();
    expect(host!.textContent).toContain("尚無資料");
    expect(host!.textContent).not.toContain("尚未建立");

    dispose();
    mocked.newsError = new Error("news status unavailable");
    await renderNewsSection();
    expect(host!.textContent).toContain("要求失敗，請稍後再試。");
    expect(host!.textContent).not.toContain("news status unavailable");
    expect(host!.querySelector(".errorbox")).not.toBeNull();
  });

  it("renders English news storage copy without changing counts", async () => {
    await i18n.changeLanguage("en");
    const cases = [
      ["running", "Running"],
      ["succeeded", "Last run succeeded"],
      ["failed", "Last run failed"],
      ["partial", "Partially completed"],
    ] as const;

    for (const [status, expectedStatus] of cases) {
      mocked.newsStatus = newsStatus({ sync: newsSync(status) });
      await renderNewsSection();
      const section = host!.querySelector('[data-settings-anchor="news_storage"]');
      if (!section) throw new Error("missing News Data section");
      expect(section.querySelector("h2")?.textContent).toBe("News Data");
      expect(section.textContent).toContain("10 articles · 2 sources · latest 2026-06-27T00:00:00+00:00");
      expect(section.textContent).toContain("Latest successful collection");
      expect(section.textContent).toContain(formatSystemTimestamp("2026-07-20T03:00:00Z"));
      expect(section.textContent).toContain("Latest collection attempt");
      expect(section.textContent).toContain(formatSystemTimestamp("2026-07-21T04:05:06Z"));
      expect(section.textContent).toContain(expectedStatus);
      dispose();
    }

    expect(getNewsStatus).toHaveBeenCalledTimes(4);
  });

  it("hides provider and sync errors outside Developer Mode", async () => {
    const syncDiagnostic = "RAW_NEWS_SYNC_DETAIL";
    const providerDiagnostic = "RAW_NEWS_PROVIDER_DETAIL";
    mocked.newsStatus = newsStatus({
      sync: newsSync("failed", {
        last_error: syncDiagnostic,
        providers: {
          polygon: {
            status: "failed",
            last_success: null,
            last_attempt: "2026-07-21T04:05:06Z",
            last_error: providerDiagnostic,
            rows_added: 0,
            tickers_scanned: 1,
            ticker_errors: [{
              ticker: "AAPL",
              error: "RAW_NEWS_TICKER_DETAIL",
              updated_at: "2026-07-21T04:05:07Z",
            }],
          },
        },
      }),
    });

    await renderNewsSection(false);
    expect(host!.textContent).toContain("上次失敗");
    expect(host!.textContent).not.toContain(syncDiagnostic);
    expect(host!.textContent).not.toContain(providerDiagnostic);
    expect(host!.querySelector(".developer-diagnostics")).toBeNull();

    dispose();
    await renderNewsSection(true);
    expect(host!.querySelector(".developer-diagnostics")).not.toBeNull();
    expect(host!.textContent).toContain(syncDiagnostic);
    expect(host!.textContent).toContain(providerDiagnostic);
    expect(getNewsStatus).toHaveBeenCalledTimes(2);
  });
});
