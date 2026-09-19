/** @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import i18n from "i18next";
import { afterEach, describe, expect, it } from "vitest";

import type { ApiStatus, RuntimeConfig } from "./api";
import { DashboardView, type StatusState } from "./Dashboard";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

const API_STATUS: ApiStatus = {
  status: "ok",
  timestamp: "2026-08-03T12:00:00Z",
  tools_registered: 53,
  tool_categories: {},
  data_sources: {
    news_tickers: 101,
    price_tickers: 202,
    fundamentals_tickers: 303,
    future_source_v9: 404,
  },
};

const STATUS: StatusState = { kind: "ready", status: API_STATUS };

let host: HTMLDivElement | null = null;
let root: Root | null = null;

async function renderDashboard(
  locale: "zh-Hant" | "en",
  runtime: RuntimeConfig | null = null,
) {
  await act(async () => {
    await i18n.changeLanguage(locale);
  });
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(
      <DashboardView
        status={STATUS}
        runtime={runtime}
        onRetry={() => undefined}
        developerMode
        onDeveloperModeChange={() => undefined}
        onNavigate={() => undefined}
      />,
    );
  });
  return host;
}

async function unmountDashboard() {
  if (root) {
    await act(async () => {
      root!.unmount();
    });
  }
  host?.remove();
  root = null;
  host = null;
}

afterEach(async () => {
  await unmountDashboard();
});

describe("Dashboard stored data-source presentation", () => {
  it("renders stored SEC fundamentals in both locales without raw stable ids", async () => {
    const zh = await renderDashboard("zh-Hant");
    expect(zh.textContent).toContain("新聞標的");
    expect(zh.textContent).toContain("價格標的");
    expect(zh.textContent).toContain("已儲存的 SEC 基本面");
    expect(zh.textContent).toContain("未知資料來源（future_source_v9）");
    for (const value of [101, 202, 303, 404]) {
      expect(zh.textContent).toContain(String(value));
    }
    for (const raw of ["news_tickers", "price_tickers", "fundamentals_tickers"]) {
      expect(zh.textContent).not.toContain(raw);
    }

    await unmountDashboard();
    const en = await renderDashboard("en");
    expect(en.textContent).toContain("News tickers");
    expect(en.textContent).toContain("Price tickers");
    expect(en.textContent).toContain("Stored SEC fundamentals");
    expect(en.textContent).toContain("Unknown data source (future_source_v9)");
    for (const value of [101, 202, 303, 404]) {
      expect(en.textContent).toContain(String(value));
    }
    for (const raw of ["news_tickers", "price_tickers", "fundamentals_tickers"]) {
      expect(en.textContent).not.toContain(raw);
    }
  });

  it("shows the remaining card model without retired translation settings", async () => {
    const runtime = {
      anthropic: {
        model: "claude-opus-5", model_advanced: "claude-opus-4-8",
        effort: "high", thinking: true, key_set: true, credentials: [],
      },
      openai: {
        model: "gpt-5.6-luna", model_advanced: "gpt-5.6-sol",
        reasoning_effort: "high", key_set: true, credentials: [],
      },
      card_synthesis: {
        task: "card_synthesis", provider: "anthropic", model: "claude-opus-5",
        effort: "high", source: "default", custom: false, warning: null,
      },

      ai_research: {
        task: "ai_research", provider: "openai", model: "gpt-5.6-luna",
        effort: "xhigh", source: "default", custom: false, warning: null,
      },
      research_runtime: {
        max_tool_calls: 10, session_timeout_s: 900, per_tool_timeout_s: 120,
        source: "default", db_saved: false, warning: null,
      },
      data_keys: {},
    } satisfies RuntimeConfig;

    const zh = await renderDashboard("zh-Hant", runtime);
    expect(zh.textContent).toContain("claude-opus-5");
    expect(zh.textContent).not.toContain("內容翻譯");
    expect(zh.textContent).not.toContain("card translation");

    await unmountDashboard();
    const en = await renderDashboard("en", runtime);
    expect(en.textContent).toContain("claude-opus-5");
    expect(en.textContent).not.toContain("Content translation");
    expect(en.textContent).not.toContain("card translation");
  });
});
