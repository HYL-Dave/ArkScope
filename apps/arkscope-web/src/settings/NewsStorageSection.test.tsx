/** @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import i18n from "i18next";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { NewsProviderSync, NewsStatus } from "../api";
import { formatSystemTimestamp } from "../timeDisplay";
import { createSettingsReadCache } from "./settingsReadCache";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

vi.mock("../api", async (importOriginal) => ({
  ...await importOriginal<typeof import("../api")>(),
  getNewsStatus: vi.fn(),
  runScheduleNow: vi.fn(),
}));

import { getNewsStatus, runScheduleNow } from "../api";
import { NewsStorageSection } from "./NewsStorageSection";

const UNKNOWN = "ibkr_news_completion_unknown";
let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement;
let state: NewsStatus;

function provider(overrides: Partial<NewsProviderSync> = {}): NewsProviderSync {
  return {
    status: "succeeded", last_success: "2026-09-25T10:00:00Z", last_attempt: "2026-09-26T10:00:00Z",
    last_error: null, rows_added: 4, tickers_scanned: 2, ticker_errors: [], ...overrides,
  };
}

function sync(providers: Record<string, NewsProviderSync>): NonNullable<NewsStatus["sync"]> {
  return {
    status: "partial", last_success: "2026-09-26T10:00:00Z", last_attempt: "2026-09-26T10:00:00Z",
    last_error: Object.entries(providers).filter(([, item]) => item.last_error)
      .map(([id, item]) => `${id}: ${item.last_error}`).join("; ") || null,
    rows_added: 4, updated_at: "2026-09-26T10:00:00Z", providers,
  };
}

async function render(developerMode = false) {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(<NewsStorageSection settingsReadCache={createSettingsReadCache()} developerMode={developerMode} />);
  });
}

beforeEach(async () => {
  await i18n.changeLanguage("en");
  vi.resetAllMocks();
  state = {
    market_db: "/tmp/test-only-news.db", exists: true,
    news: { row_count: 101, source_count: 2, latest_published: "2026-09-26T08:00:00Z" },
    normalized_writes_setting: false, normalized_writes_setting_explicit: false,
    normalized_writes_env_override: false, normalized_writes_env_value: null,
    write_route: "normalized", write_route_reason: "test", sync: null,
  };
  vi.mocked(getNewsStatus).mockImplementation(async () => structuredClone(state));
});

afterEach(() => {
  if (root) act(() => root!.unmount());
  root = null;
  document.body.replaceChildren();
});

describe("NewsStorageSection collection evidence", () => {
  it("collapses ticker issues and distinguishes subscription denial from timeouts", async () => {
    state.sync = sync({ ibkr: provider({ status: "partial", ticker_errors: [
      { ticker: "AAPL", error: "ibkr_news_subscription_denied", updated_at: "2026-09-27T14:00:00Z" },
      { ticker: "MSFT", error: "ibkr_news_request_timeout", updated_at: "2026-09-27T14:00:00Z" },
    ] }) });
    await render();
    const details = host.querySelector<HTMLDetailsElement>("details[data-news-issues]");
    expect(details).not.toBeNull();
    expect(details!.open).toBe(false);
    expect(details!.querySelector("summary")?.textContent).toContain("2");
    expect(host.querySelector('[data-news-ticker="AAPL"]')?.textContent).toContain("News subscription denied");
    expect(host.querySelector('[data-news-ticker="MSFT"]')?.textContent).toContain("News request timed out");
    act(() => { details!.open = true; });
    expect(details!.open).toBe(true);
    expect(runScheduleNow).not.toHaveBeenCalled();
  });
  it.each(["en", "zh-Hant"])("shows each provider's latest outcome and attempt separately from any-provider success in %s", async (locale) => {
    await i18n.changeLanguage(locale);
    state.sync = sync({
      polygon: provider({ last_success: "2026-09-26T10:00:00Z" }),
      finnhub: provider({ status: "failed", last_attempt: "2026-09-26T09:00:00Z", last_error: "HTTP 403" }),
    });
    state.sync.status = "failed";
    await render();
    const massive = host.querySelector('[data-news-provider="polygon"]');
    const finnhub = host.querySelector('[data-news-provider="finnhub"]');
    expect(massive?.textContent).toContain("Massive");
    expect(massive?.textContent).toContain(formatSystemTimestamp("2026-09-26T10:00:00Z"));
    expect(finnhub?.textContent).toContain(formatSystemTimestamp("2026-09-26T09:00:00Z"));
    expect(finnhub?.textContent).toContain(formatSystemTimestamp("2026-09-25T10:00:00Z"));
    expect(finnhub?.textContent).toContain(locale === "en" ? "Last run failed" : "上次失敗");
    expect(host.textContent).toContain(locale === "en" ? "any provider" : "任一來源");
    expect(host.textContent).toContain(locale === "en" ? "does not establish freshness for every source" : "不代表所有來源皆為最新");
    expect(host.textContent).not.toContain("HTTP 403");
    expect(runScheduleNow).not.toHaveBeenCalled();
  });

  it.each(["en", "zh-Hant"])("presents IBKR completeness uncertainty once at the affected ticker in %s", async (locale) => {
    await i18n.changeLanguage(locale);
    state.sync = sync({ ibkr: provider({ status: "partial", last_error: `${UNKNOWN}; AAPL: ${UNKNOWN}`,
      ticker_errors: [{ ticker: "AAPL", error: UNKNOWN, updated_at: "2026-09-26T09:50:00Z" }],
    }) });
    await render();
    const issue = host.querySelector('[data-news-ticker="AAPL"]');
    expect(issue?.textContent).toContain(locale === "en" ? "Completeness unknown" : "完整性未知");
    expect(issue?.textContent).toContain(formatSystemTimestamp("2026-09-26T09:50:00Z"));
    expect(issue?.textContent).toContain(locale === "en" ? "completion was not confirmed" : "未確認收集已完整結束");
    expect(host.querySelectorAll("[data-news-issue]")).toHaveLength(1);
    expect(host.textContent).not.toContain(UNKNOWN);
    expect(host.textContent).not.toMatch(/Request failed|Collection request failed|要求失敗|收集要求失敗/);
  });

  it("keeps independent provider failures alongside per-ticker completeness issues", async () => {
    state.sync = sync({ ibkr: provider({ status: "failed", last_error: `Gateway disconnected; AAPL: ${UNKNOWN}; MSFT: HTTP 403`,
      ticker_errors: [
        { ticker: "AAPL", error: UNKNOWN, updated_at: "2026-09-26T09:50:00Z" },
        { ticker: "MSFT", error: "HTTP 403", updated_at: "2026-09-26T09:55:00Z" },
      ],
    }) });
    state.sync.status = "failed";
    await render(true);
    expect(host.querySelector('[data-news-ticker="AAPL"]')?.textContent).toContain("Completeness unknown");
    expect(host.querySelector('[data-news-ticker="MSFT"]')?.textContent).toContain("Collection request failed");
    expect(host.querySelectorAll("[data-news-issue]")).toHaveLength(3);
    expect(host.textContent?.match(/Gateway disconnected/g)).toHaveLength(1);
    expect(host.textContent?.match(/HTTP 403/g)).toHaveLength(1);
    expect(host.textContent?.match(/ibkr_news_completion_unknown/g)).toHaveLength(1);
  });

  it.each(["ibkr_news_window_incomplete", "ibkr_news_provider_window_incomplete"])("keeps %s distinct from a request failure", async (error) => {
    state.sync = sync({ ibkr: provider({ status: "partial", last_error: `AAPL: ${error}`,
      ticker_errors: [{ ticker: "AAPL", error, updated_at: "2026-09-26T09:50:00Z" }],
    }) });
    await render();
    expect(host.querySelector('[data-news-ticker="AAPL"]')?.textContent).toContain("Partially completed");
    expect(host.querySelectorAll("[data-news-issue]")).toHaveLength(1);
    expect(host.textContent).not.toContain("Collection request failed");
  });

  it("retains distinct aggregate failures even when providers have detailed issues", async () => {
    state.sync = sync({ ibkr: provider({ status: "partial", last_error: `AAPL: ${UNKNOWN}`,
      ticker_errors: [{ ticker: "AAPL", error: UNKNOWN, updated_at: "2026-09-26T09:50:00Z" }],
    }) });
    state.sync.last_error = `Aggregate storage failure; ${state.sync.last_error}`;
    state.sync.status = "failed";
    await render(true);
    expect(host.querySelectorAll("[data-news-issue]")).toHaveLength(2);
    expect(host.textContent?.match(/Aggregate storage failure/g)).toHaveLength(1);
    expect(host.textContent?.match(/ibkr_news_completion_unknown/g)).toHaveLength(1);
  });

  it("keeps a failed outcome visible when no error text or ticker details were recorded", async () => {
    state.sync = sync({ finnhub: provider({ status: "failed", last_error: null, last_success: null }) });
    state.sync.status = "failed";
    await render();
    expect(host.querySelector('[data-news-provider="finnhub"]')?.textContent).toContain("Last run failed");
    expect(host.textContent).not.toContain("Not run yet");
  });

  it("renders aggregate-only completeness uncertainty without inventing a provider run", async () => {
    state.sync = sync({});
    state.sync.last_error = UNKNOWN;
    await render();
    expect(host.textContent).toContain("Completeness unknown");
    expect(host.querySelectorAll("[data-news-provider]")).toHaveLength(0);
    expect(host.querySelectorAll("[data-news-issue]")).toHaveLength(1);
  });

  it("reloads local status with an accessible icon control and does not start a collection", async () => {
    await render();
    const refresh = host.querySelector<HTMLButtonElement>('button[aria-label="Reload status"]');
    expect(refresh).not.toBeNull();
    expect(refresh?.querySelector("svg")).not.toBeNull();
    await act(async () => { refresh!.click(); });
    expect(getNewsStatus).toHaveBeenCalledTimes(2);
    expect(runScheduleNow).not.toHaveBeenCalled();
    expect(host.textContent).toContain("Not run yet");
  });
});
