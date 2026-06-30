/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ModelCatalog, ModelTask, NewsStatus, TaskRoute } from "./api";

const mocked = vi.hoisted(() => ({
  newsStatus: null as NewsStatus | null,
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
    getNewsStatus: vi.fn(async () => mocked.newsStatus),
    setNormalizedNewsWrites: vi.fn(),
    setUseLocalNews: vi.fn(),
  };
});

import { SettingsView } from "./Settings";

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

afterEach(() => {
  if (root) {
    act(() => root!.unmount());
    root = null;
  }
  host?.remove();
  host = null;
});

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

async function flush() {
  await act(async () => {
    await Promise.resolve();
  });
}

describe("SettingsView news storage copy", () => {
  it("hides the legacy local-news env hint after news PG exit", async () => {
    mocked.newsStatus = newsStatus();
    host = document.createElement("div");
    document.body.append(host);
    root = createRoot(host);

    await act(async () => {
      root!.render(React.createElement(SettingsView, {
        runtime: null,
        onRuntimeChanged: vi.fn(),
      }));
    });
    await flush();

    const newsButton = Array.from(host.querySelectorAll("button")).find((button) =>
      button.textContent?.includes("News Ingestion"));
    if (!newsButton) throw new Error("missing News Ingestion section button");

    await act(async () => {
      newsButton.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    });
    await flush();

    expect(host.textContent).toContain("已退出（不可回退到 PG）");
    expect(host.textContent).not.toContain("ARKSCOPE_USE_LOCAL_NEWS");
  });
});
