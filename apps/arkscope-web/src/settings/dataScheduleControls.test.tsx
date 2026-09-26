/** @vitest-environment jsdom */
import { readFileSync } from "node:fs";

import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import i18n from "i18next";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  IBKR_GATEWAY_UNAVAILABLE,
  getSchedule,
  putSchedule,
  runScheduleNow,
  type ScheduleRunResult,
  type ScheduleSourceState,
} from "../api";
import {
  DataScheduleControlsProvider,
  DataScheduleTable,
  useSharedDataScheduleControls,
} from "./dataScheduleControls";
import { createSettingsReadCache, type SettingsReadCache } from "./settingsReadCache";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

type ScheduleResponse = { sources: Record<string, ScheduleSourceState> };

const controls = vi.hoisted(() => ({
  schedule: null as ScheduleResponse | null,
  scheduleQueue: [] as Array<ScheduleResponse | Promise<ScheduleResponse>>,
  putCalls: [] as Array<{
    source: string;
    body: { enabled?: boolean; interval_minutes?: number };
  }>,
  runCalls: [] as string[],
  runResult: { source: "fred_series", status: "running" } as ScheduleRunResult,
}));

vi.mock("../api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api")>();
  return {
    ...actual,
    getSchedule: vi.fn(async () => {
      const queued = controls.scheduleQueue.shift();
      const value = queued === undefined ? controls.schedule : await queued;
      if (value === null) throw new Error("missing schedule fixture");
      return structuredClone(value);
    }),
    putSchedule: vi.fn(async (
      source: string,
      body: { enabled?: boolean; interval_minutes?: number },
    ) => {
      controls.putCalls.push({ source, body });
      return {
        source,
        enabled: body.enabled ?? true,
        interval_minutes: body.interval_minutes ?? 60,
      };
    }),
    runScheduleNow: vi.fn(async (source: string) => {
      controls.runCalls.push(source);
      return { ...controls.runResult, source };
    }),
  };
});

function source(
  id: string,
  over: Partial<ScheduleSourceState> = {},
): ScheduleSourceState {
  return {
    label: id,
    description: `${id} description`,
    ibkr: false,
    provider_fetch: true,
    source_mode: "direct_local",
    write_target: id.startsWith("fred_") || id.startsWith("finnhub_")
      ? "macro_calendar.db"
      : "market_data.db",
    source_badges: [],
    enabled: true,
    interval_minutes: 60,
    default_interval_minutes: 60,
    running: false,
    progress: null,
    last_attempt_at: "2026-08-13T01:00:00Z",
    last_result: null,
    durable_state: {
      last_status: "succeeded",
      last_error: null,
      continuation: null,
      last_attempt: "2026-08-13T01:00:00Z",
      updated_at: "2026-08-13T01:01:00Z",
    },
    job_name: `collect.${id}`,
    ...over,
  };
}

function response(
  entries: Array<[string, Partial<ScheduleSourceState>?]> = [
    ["polygon_news"],
    ["fred_series"],
    ["fred_release_dates"],
  ],
): ScheduleResponse {
  return {
    sources: Object.fromEntries(entries.map(([id, over]) => [id, source(id, over)])),
  };
}

function macroResult(
  id = "finnhub_economic_calendar",
  status: "failed" | "partial" | "succeeded" = "failed",
  errorCode = "finnhub_forbidden",
): ScheduleRunResult {
  const collect = {
    status,
    events_inserted: status === "partial" ? 1 : 0,
    events_mutated: 0, events_unchanged: 0, events_skipped: 0,
    error_count: 1, error_code: `macro_collection_${status}`,
    errors: ["PRIVATE_PROVIDER_DIAGNOSTIC"],
    requests: [{
      dataset: id === "finnhub_earnings_calendar" ? "earnings" : id === "finnhub_ipo_calendar" ? "ipo" : "economic",
      symbol: null, from_date: "2026-09-20", to_date: "2026-10-11",
      checked_at: "2026-09-27T01:01:00Z", response_state: "failed",
      rows_received: null, rows_accepted: null, rows_rejected: null, error_code: errorCode,
    }],
  };
  return { source: id, status, collect };
}

function failedMacro(id = "finnhub_economic_calendar", status: "failed" | "partial" = "failed") {
  return source(id, {
    last_attempt_at: "2026-09-27T01:00:00Z",
    durable_state: {
      last_status: status, last_error: `macro_collection_${status}`, continuation: null,
      last_attempt: "2026-09-27T01:00:00Z", updated_at: "2026-09-27T01:01:00Z",
      last_result: macroResult(id, status),
    },
  });
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

async function settle(): Promise<void> {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

type Harness = {
  current: (index?: number) => any;
  host: HTMLDivElement;
  unmount: () => void;
};

async function renderControls({
  cache = createSettingsReadCache(),
  consumers = 1,
  scopes,
  externalBusy = false,
}: {
  cache?: SettingsReadCache;
  consumers?: number;
  scopes?: Array<"macro" | "non_macro">;
  externalBusy?: boolean;
} = {}): Promise<Harness> {
  const host = document.createElement("div");
  document.body.append(host);
  const root = createRoot(host);
  const latest: any[] = [];

  function Consumer({ index }: { index: number }) {
    const controller = useSharedDataScheduleControls();
    latest[index] = controller;
    const scope = scopes?.[index];
    return scope
      ? React.createElement(
          "div",
          { "data-schedule-scope": scope },
          React.createElement(
            DataScheduleTable,
            { controller, scope, externalBusy },
          ),
        )
      : null;
  }

  await act(async () => {
    root.render(React.createElement(
      DataScheduleControlsProvider,
      {
        settingsReadCache: cache,
        children: Array.from({ length: consumers }, (_, index) =>
          React.createElement(Consumer, { key: index, index })),
      },
    ));
  });
  await settle();

  return {
    current: (index = 0) => latest[index],
    host,
    unmount: () => {
      act(() => root.unmount());
      host.remove();
    },
  };
}

async function transitionFromRunning(
  sourceId: string,
  terminalStatus: string,
  writeTarget = "macro_calendar.db",
): Promise<{ cache: SettingsReadCache; harness: Harness }> {
  const cache = createSettingsReadCache();
  const running = response([[
    sourceId,
    {
      running: true,
      write_target: writeTarget,
      durable_state: {
        last_status: "running",
        last_error: null,
        continuation: null,
        last_attempt: "2026-08-13T01:00:00Z",
        updated_at: "2026-08-13T01:00:00Z",
      },
    },
  ]]);
  cache.replace("data_schedule", running);
  cache.replace("macro_status", { marker: "status" });
  cache.replace("macro_snapshot", { marker: "snapshot" });
  cache.replace("news_status", { marker: "news" });
  controls.schedule = response([[
    sourceId,
    {
      running: false,
      write_target: writeTarget,
      last_result: { source: sourceId, status: terminalStatus },
      durable_state: {
        last_status: terminalStatus,
        last_error: terminalStatus === "failed" ? "typed_failure" : null,
        continuation: null,
        last_attempt: "2026-08-13T01:00:00Z",
        updated_at: "2026-08-13T01:02:00Z",
      },
    },
  ]]);
  const harness = await renderControls({ cache });
  await act(async () => {
    await harness.current().pollSchedule();
  });
  return { cache, harness };
}

beforeEach(async () => {
  await i18n.changeLanguage("zh-Hant");
  controls.schedule = response();
  controls.scheduleQueue = [];
  controls.putCalls = [];
  controls.runCalls = [];
  controls.runResult = { source: "fred_series", status: "running" };
  vi.mocked(getSchedule).mockClear();
  vi.mocked(putSchedule).mockClear();
  vi.mocked(runScheduleNow).mockClear();
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  document.body.replaceChildren();
});

describe("Data schedule controls", () => {
  it.each([
    ["en", "failed"], ["en", "partial"], ["zh-Hant", "failed"], ["zh-Hant", "partial"],
  ] as const)("shows the durable Finnhub endpoint denial for %s %s without changing collection", async (locale, status) => {
    await i18n.changeLanguage(locale);
    controls.schedule = { sources: { finnhub_economic_calendar: failedMacro("finnhub_economic_calendar", status) } };
    const harness = await renderControls({ scopes: ["macro"] });
    try {
      const detail = harness.host.querySelector(".ds-last-run-cell")!;
      expect(detail.textContent).toContain("403");
      expect(detail.textContent).toContain(locale === "en" ? "Finnhub economic calendar" : "Finnhub 經濟日曆");
      expect(detail.textContent).toContain(locale === "en" ? "API key does not establish endpoint access" : "有 API 金鑰不代表具備端點權限");
      expect(detail.textContent).not.toMatch(/PRIVATE_PROVIDER_DIAGNOSTIC|finnhub_forbidden|macro_collection_failed|premium|enterprise/i);
      expect(harness.current().schedule.finnhub_economic_calendar.interval_minutes).toBe(60);
      expect(getSchedule).toHaveBeenCalledOnce();
      expect(putSchedule).not.toHaveBeenCalled();
      expect(runScheduleNow).not.toHaveBeenCalled();
    } finally { harness.unmount(); }
  });

  it.each([
    ["finnhub_earnings_calendar", "Finnhub earnings calendar"],
    ["finnhub_ipo_calendar", "Finnhub IPO calendar"],
  ])("keeps the endpoint reason scoped to %s", async (id, label) => {
    await i18n.changeLanguage("en");
    controls.schedule = { sources: { [id]: failedMacro(id) } };
    const harness = await renderControls({ scopes: ["macro"] });
    try {
      const detail = harness.host.querySelector(".ds-last-run-cell")!;
      expect(detail.textContent).toContain(`${label}:`);
      expect(detail.textContent).toContain("403");
      expect(detail.textContent).not.toContain("economic calendar");
    } finally { harness.unmount(); }
  });

  it.each(["live", "job envelope", "job normalized"])("reads the typed receipt from a current %s result", async (origin) => {
    const id = "finnhub_economic_calendar";
    const state = failedMacro();
    state.durable_state = null;
    state.last_result = origin === "live" ? { ...macroResult(), at: "2026-09-27T01:01:00Z" } : null;
    controls.schedule = { sources: { [id]: state } };
    const harness = await renderControls({ scopes: ["macro"] });
    try {
      if (origin !== "live") act(() => harness.current().replaceJobFacts({
        [state.job_name]: {
          status: "failed", finished_at: "2026-09-27T01:01:00Z",
          result: origin === "job envelope" ? macroResult() : macroResult().collect,
        },
      }));
      expect(harness.host.querySelector(".ds-last-run-cell")?.textContent).toContain("403");
    } finally { harness.unmount(); }
  });

  it.each([
    ["finnhub_unauthorized", "401"],
    ["finnhub_rate_limited", "429"],
    ["finnhub_transport_failed", "Provider connection failed"],
    ["finnhub_calendar_response_invalid", "Invalid calendar response"],
    ["finnhub_calendar_rows_rejected", "Calendar rows rejected"],
    ["PRIVATE_TOKEN=secret", "Macro collection issue"],
  ])("localizes %s without exposing raw diagnostics", async (code, expected) => {
    await i18n.changeLanguage("en");
    const state = failedMacro();
    state.durable_state!.last_result = macroResult("finnhub_economic_calendar", "failed", code);
    state.durable_state!.last_error = "PRIVATE_TOKEN=secret";
    controls.schedule = { sources: { finnhub_economic_calendar: state } };
    const harness = await renderControls({ scopes: ["macro"] });
    try {
      const text = harness.host.querySelector(".ds-last-run-cell")!.textContent;
      expect(text).toContain(expected);
      expect(text).not.toMatch(/PRIVATE_|finnhub_|secret/);
    } finally { harness.unmount(); }
  });

  it.each(["durable", "live", "job"])("does not revive an older denial after a newer %s success", async (latest) => {
    const state = failedMacro();
    const previousResult = macroResult();
    const success = { source: "finnhub_economic_calendar", status: "succeeded", at: "2026-09-27T02:01:00Z" };
    if (latest === "durable") {
      state.durable_state = {
        ...state.durable_state!, last_status: "succeeded", last_error: null,
        last_result: success, last_attempt: "2026-09-27T02:00:00Z", updated_at: "2026-09-27T02:01:00Z",
      };
      state.last_result = { ...previousResult, at: "2026-09-27T01:01:00Z" };
    } else if (latest === "live") state.last_result = success;
    controls.schedule = { sources: { finnhub_economic_calendar: state } };
    const harness = await renderControls({ scopes: ["macro"] });
    try {
      act(() => harness.current().replaceJobFacts({
        [state.job_name]: latest === "job"
          ? { status: "succeeded", finished_at: "2026-09-27T02:01:00Z", result: success }
          : { status: "failed", finished_at: "2026-09-27T01:01:00Z", result: previousResult },
      }));
      expect(harness.host.querySelector(".ds-last-run-cell")?.textContent).not.toContain("403");
    } finally { harness.unmount(); }
  });

  it("replaces the displayed denial with a newer success while retaining older job facts", async () => {
    const state = failedMacro();
    controls.schedule = { sources: { finnhub_economic_calendar: state } };
    const harness = await renderControls({ scopes: ["macro"] });
    try {
      act(() => harness.current().replaceJobFacts({
        [state.job_name]: { status: "failed", finished_at: "2026-09-27T01:01:00Z", result: macroResult() },
      }));
      expect(harness.host.querySelector(".ds-last-run-cell")?.textContent).toContain("403");
      state.durable_state = {
        ...state.durable_state!, last_status: "succeeded", last_error: null, last_result: null,
        last_attempt: "2026-09-27T02:00:00Z", updated_at: "2026-09-27T02:01:00Z",
      };
      await act(async () => { await harness.current().reloadSchedule(); });
      expect(harness.host.querySelector(".ds-last-run-cell")?.textContent).not.toContain("403");
    } finally { harness.unmount(); }
  });

  it.each([null, "invalid-time", "2026-09-27T01:01:00Z"])("does not assert a current denial when success cannot be ordered at %s", async (finishedAt) => {
    const state = failedMacro();
    controls.schedule = { sources: { finnhub_economic_calendar: state } };
    const harness = await renderControls({ scopes: ["macro"] });
    try {
      act(() => harness.current().replaceJobFacts({
        [state.job_name]: { status: "succeeded", finished_at: finishedAt, result: { status: "succeeded" } },
      }));
      expect(harness.host.querySelector(".ds-last-run-cell")?.textContent).not.toContain("403");
    } finally { harness.unmount(); }
  });

  it("uses a generic reason for a newer failure instead of borrowing an older typed denial", async () => {
    await i18n.changeLanguage("en");
    const state = failedMacro();
    state.last_result = { source: "finnhub_economic_calendar", status: "failed", at: "2026-09-27T02:01:00Z" };
    controls.schedule = { sources: { finnhub_economic_calendar: state } };
    const harness = await renderControls({ scopes: ["macro"] });
    try {
      const text = harness.host.querySelector(".ds-last-run-cell")!.textContent;
      expect(text).toContain("Macro collection issue");
      expect(text).not.toContain("403");
    } finally { harness.unmount(); }
  });

  it.each(["succeeded", "running", "skipped"])("ignores leftover receipt details when the durable outcome is %s", async (status) => {
    const state = failedMacro();
    state.durable_state!.last_status = status;
    controls.schedule = { sources: { finnhub_economic_calendar: state } };
    const harness = await renderControls({ scopes: ["macro"] });
    try {
      expect(harness.host.querySelector(".ds-last-run-cell")?.textContent).not.toContain("403");
    } finally { harness.unmount(); }
  });

  it.each(["zh-Hant", "en"])("shows one live status and prevents duplicate runs in %s", async (language) => {
    await i18n.changeLanguage(language);
    controls.schedule = response([["polygon_news", {
      running: true,
      progress: { done: 9, total: 183, current: "AMAT" },
      last_result: { source: "polygon_news", status: "skipped" },
      durable_state: {
        last_status: "running",
        last_error: null,
        continuation: null,
        last_attempt: "2026-08-13T01:00:00Z",
        updated_at: "2026-08-13T01:00:00Z",
      },
    }]]);
    const harness = await renderControls({ scopes: ["non_macro"] });
    try {
      act(() => harness.current().replaceJobFacts({
        "collect.polygon_news": { status: "running" },
      }));
      const row = harness.host.querySelector("tbody tr")!;
      const runningLabel = i18n.t(($) => $.actions.running, { ns: "settings" });
      expect(row.textContent!.split(runningLabel)).toHaveLength(2);
      expect(row.querySelectorAll('[data-state="running"]')).toHaveLength(1);
      expect(row.textContent).toContain(language === "en" ? "New trigger skipped" : "新觸發已略過");
      expect(row.querySelector("[role='progressbar']")?.getAttribute("aria-valuenow")).toBe("9");

      const run = row.querySelector<HTMLButtonElement>("button[aria-label]")!;
      expect(run).not.toBeNull();
      expect(run.disabled).toBe(true);
      act(() => run.click());
      expect(runScheduleNow).not.toHaveBeenCalled();

      controls.schedule = response([["polygon_news"]]);
      await act(async () => {
        harness.current().replaceJobFacts({
          "collect.polygon_news": { status: "succeeded", finished_at: "2026-08-13T01:02:00Z" },
        });
        await harness.current().pollSchedule();
      });
      expect(row.querySelector("[role='progressbar']")).toBeNull();
      expect(row.textContent).not.toContain(runningLabel);
      expect(row.textContent).toContain(language === "en" ? "Last run succeeded" : "上次成功");
      expect(run.disabled).toBe(false);
      await act(async () => run.click());
      expect(controls.runCalls).toEqual(["polygon_news"]);
    } finally {
      harness.unmount();
    }
  });

  it("keeps the previous failure and skipped trigger visible during an indeterminate retry", async () => {
    controls.schedule = response([["ibkr_prices", {
      running: true,
      last_result: { source: "ibkr_prices", status: "skipped" },
      durable_state: {
        last_status: "failed",
        last_error: IBKR_GATEWAY_UNAVAILABLE,
        continuation: null,
        last_attempt: "2026-08-13T01:00:00Z",
        updated_at: "2026-08-13T01:00:00Z",
      },
    }]]);
    const harness = await renderControls({ scopes: ["non_macro"] });
    try {
      act(() => harness.current().replaceJobFacts({
        "collect.ibkr_prices": { status: "failed", finished_at: "2026-08-13T01:02:00Z" },
      }));
      const status = harness.host.querySelector(".ds-last-run-cell")!;
      expect(status.textContent).toContain("執行中");
      expect(status.textContent).toContain("最近一次");
      expect(status.textContent).toContain("IBKR Gateway 無法連線");
      expect(status.textContent).toContain("新觸發已略過");
      expect(status.textContent).toContain("08-13");
      expect(status.querySelector("[role='progressbar']")).toBeNull();
      expect(status.textContent).not.toContain("0%");
    } finally {
      harness.unmount();
    }
  });

  it("shares one schedule read across visible consumers", async () => {
    vi.useFakeTimers();
    const harness = await renderControls({ consumers: 2 });
    const dataSourcesOwner = readFileSync("src/settings/DataSourcesSection.tsx", "utf8");

    expect(getSchedule).toHaveBeenCalledOnce();
    expect(harness.current(0)).toBe(harness.current(1));
    expect(Object.keys(harness.current(0).schedule)).toEqual([
      "polygon_news",
      "fred_series",
      "fred_release_dates",
    ]);
    act(() => { vi.advanceTimersByTime(30_000); });
    await settle();
    expect(getSchedule).toHaveBeenCalledTimes(2);
    expect(dataSourcesOwner).toContain("useSharedDataScheduleControls()");
    expect(dataSourcesOwner).not.toContain("useDataScheduleControls(settingsReadCache)");
    expect(dataSourcesOwner).toContain("<DataScheduleTable");
    expect(dataSourcesOwner).not.toMatch(/\bgetSchedule\b|\bputSchedule\b|\brunScheduleNow\b/);
    harness.unmount();
  });

  it("partitions schedule rows by write target without changing registry truth", async () => {
    controls.schedule = response([
      ["polygon_news", { write_target: "market_data.db" }],
      ["fred_series", { write_target: "macro_calendar.db" }],
      ["future_macro_source_v9", { write_target: "macro_calendar.db" }],
      ["future_local_source_v9", { write_target: "future_local.db" }],
    ]);
    const harness = await renderControls({
      consumers: 2,
      scopes: ["non_macro", "macro"],
    });

    const renderedIds = (scope: "macro" | "non_macro") => Array.from(
      harness.host.querySelectorAll(
        `[data-schedule-scope='${scope}'] tbody tr`,
      ),
      (row) => row.getAttribute("data-source-id"),
    );
    const nonMacro = renderedIds("non_macro");
    const macro = renderedIds("macro");
    expect(nonMacro).toEqual([
      "polygon_news",
      "future_local_source_v9",
    ]);
    expect(macro).toEqual([
      "fred_series",
      "future_macro_source_v9",
    ]);
    expect(nonMacro.filter((sourceId) => macro.includes(sourceId))).toEqual([]);
    expect([...nonMacro, ...macro].sort()).toEqual(
      Object.keys(harness.current().schedule).sort(),
    );
    expect(harness.current(0)).toBe(harness.current(1));
    for (const row of harness.host.querySelectorAll("tbody tr")) {
      expect(row.querySelector("input[type='checkbox']")).not.toBeNull();
      expect(row.querySelector("input[type='number']")).not.toBeNull();
      expect(row.querySelector("button")?.hasAttribute("disabled")).toBe(false);
    }
    harness.unmount();
  });

  it("manual run sends exactly one POST and follows terminal state", async () => {
    const idle = response([["fred_series"]]);
    const running = response([["fred_series", {
      running: true,
      durable_state: {
        last_status: "running",
        last_error: null,
        continuation: null,
        last_attempt: "2026-08-13T01:00:00Z",
        updated_at: "2026-08-13T01:00:00Z",
      },
    }]]);
    const complete = response([["fred_series", {
      running: false,
      last_result: { source: "fred_series", status: "succeeded" },
      durable_state: {
        last_status: "succeeded",
        last_error: null,
        continuation: null,
        last_attempt: "2026-08-13T01:00:00Z",
        updated_at: "2026-08-13T01:02:00Z",
      },
    }]]);
    controls.schedule = idle;
    const harness = await renderControls();
    vi.mocked(getSchedule).mockClear();
    const oldPoll = deferred<ScheduleResponse>();
    controls.scheduleQueue = [oldPoll.promise, running, complete];
    let passivePoll!: Promise<void>;
    act(() => {
      passivePoll = harness.current().pollSchedule();
    });
    await settle();
    expect(getSchedule).toHaveBeenCalledOnce();

    let firstRun!: Promise<void>;
    let duplicateRun!: Promise<void>;
    act(() => {
      firstRun = harness.current().runNow("fred_series");
      duplicateRun = harness.current().runNow("fred_series");
    });
    await settle();
    expect(getSchedule).toHaveBeenCalledTimes(3);
    oldPoll.resolve(idle);
    await act(async () => {
      await Promise.all([passivePoll, firstRun, duplicateRun]);
    });
    expect(runScheduleNow).toHaveBeenCalledOnce();
    expect(harness.current().schedule.fred_series.durable_state.last_status).toBe("succeeded");
    harness.unmount();

    vi.mocked(getSchedule).mockClear();
    vi.mocked(runScheduleNow).mockClear();
    const cache = createSettingsReadCache();
    cache.replace("macro_status", { marker: "status" });
    cache.replace("macro_snapshot", { marker: "snapshot" });
    const beforeFastRun = response([["fred_series", {
      last_attempt_at: "2026-08-13T01:00:00Z",
      last_result: { source: "fred_series", status: "succeeded", at: "2026-08-13T01:00:01Z" },
    }]]);
    const fastComplete = response([["fred_series", {
      last_attempt_at: "2026-08-13T01:10:00Z",
      last_result: { source: "fred_series", status: "succeeded", at: "2026-08-13T01:10:01Z" },
      durable_state: {
        last_status: "succeeded",
        last_error: null,
        continuation: null,
        last_attempt: "2026-08-13T01:10:00Z",
        updated_at: "2026-08-13T01:10:01Z",
      },
    }]]);
    controls.schedule = beforeFastRun;
    const fastHarness = await renderControls({ cache });
    controls.runResult = { source: "fred_series", status: "started" };
    controls.scheduleQueue = [fastComplete, fastComplete];
    await act(async () => {
      await fastHarness.current().runNow("fred_series");
    });

    expect(runScheduleNow).toHaveBeenCalledOnce();
    expect(fastHarness.current().schedule.fred_series.running).toBe(false);
    expect(cache.inspect("macro_status")).toEqual({ status: "missing" });
    expect(cache.inspect("macro_snapshot")).toEqual({ status: "missing" });
    fastHarness.unmount();
  });

  it("enable and interval mutations invalidate the shared schedule key", async () => {
    const cache = createSettingsReadCache();
    cache.replace("provider_health", { marker: "health" });
    cache.replace("macro_status", { marker: "macro" });
    const invalidations: string[] = [];
    cache.subscribeInvalidation("data_schedule", (key) => invalidations.push(key));
    cache.subscribeInvalidation("provider_health", (key) => invalidations.push(key));
    const harness = await renderControls({ cache });

    await act(async () => {
      await harness.current().setEnabled("fred_series", false);
    });
    act(() => harness.current().setIntervalDraft("fred_series", "10080"));
    await settle();
    await act(async () => {
      await harness.current().applyInterval("fred_series");
    });

    expect(controls.putCalls).toEqual([
      { source: "fred_series", body: { enabled: false } },
      { source: "fred_series", body: { interval_minutes: 10080 } },
    ]);
    expect(invalidations).toEqual([
      "data_schedule",
      "provider_health",
      "data_schedule",
      "provider_health",
    ]);
    expect(cache.inspect("macro_status")).toMatchObject({ status: "fresh" });
    harness.unmount();
  });

  it("successful macro sources invalidate exact stored data keys", async () => {
    const series = await transitionFromRunning("fred_series", "succeeded");
    expect(series.cache.inspect("macro_status")).toEqual({ status: "missing" });
    expect(series.cache.inspect("macro_snapshot")).toEqual({ status: "missing" });
    expect(series.cache.inspect("news_status")).toMatchObject({ status: "fresh" });
    series.harness.unmount();

    const release = await transitionFromRunning("fred_release_dates", "succeeded");
    expect(release.cache.inspect("macro_status")).toEqual({ status: "missing" });
    expect(release.cache.inspect("macro_snapshot")).toMatchObject({ status: "fresh" });
    expect(release.cache.inspect("news_status")).toMatchObject({ status: "fresh" });
    release.harness.unmount();
  });

  it("skipped and busy macro runs do not invalidate stored data keys", async () => {
    for (const status of ["skipped", "busy"]) {
      const result = await transitionFromRunning("fred_series", status);
      expect(result.cache.inspect("macro_status"), status).toMatchObject({ status: "fresh" });
      expect(result.cache.inspect("macro_snapshot"), status).toMatchObject({ status: "fresh" });
      result.harness.unmount();
    }
  });

  it.each([
    ["fred_series", "missing"],
    ["fred_release_dates", "fresh"],
    ["finnhub_economic_calendar", "fresh"],
    ["finnhub_earnings_calendar", "fresh"],
    ["finnhub_ipo_calendar", "fresh"],
  ])("failed macro attempts for %s invalidate possible committed writes", async (id, snapshotStatus) => {
    const { cache, harness } = await transitionFromRunning(id, "failed");
    expect(cache.inspect("macro_status")).toEqual({ status: "missing" });
    expect(cache.inspect("macro_snapshot")).toMatchObject({ status: snapshotStatus });
    expect(cache.inspect("news_status")).toMatchObject({ status: "fresh" });
    harness.unmount();
  });

  it.each([
    ["fred_series", "missing"],
    ["fred_release_dates", "fresh"],
    ["finnhub_economic_calendar", "fresh"],
    ["finnhub_earnings_calendar", "fresh"],
    ["finnhub_ipo_calendar", "fresh"],
  ])("partial macro completion for %s invalidates only owned cache keys", async (id, snapshotStatus) => {
    const { cache, harness } = await transitionFromRunning(id, "partial");
    expect(cache.inspect("macro_status")).toEqual({ status: "missing" });
    expect(cache.inspect("macro_snapshot")).toMatchObject({ status: snapshotStatus });
    expect(cache.inspect("news_status")).toMatchObject({ status: "fresh" });
    harness.unmount();
  });

  it.each(["partial", "failed"])("fast %s macro completions invalidate once without an observed running state", async (status) => {
    const cache = createSettingsReadCache();
    controls.schedule = response([["fred_series"]]);
    const harness = await renderControls({ cache });
    cache.replace("macro_status", { marker: "status" });
    cache.replace("macro_snapshot", { marker: "snapshot" });
    cache.replace("news_status", { marker: "news" });
    controls.schedule = response([["fred_series", {
      last_attempt_at: "2026-08-13T01:10:00Z",
      last_result: { source: "fred_series", status, at: "2026-08-13T01:10:01Z" },
      durable_state: {
        last_status: status,
        last_error: `macro_collection_${status}`,
        continuation: null,
        last_attempt: "2026-08-13T01:10:00Z",
        updated_at: "2026-08-13T01:10:01Z",
      },
    }]]);
    await act(async () => { await harness.current().pollSchedule(); });
    expect(cache.inspect("macro_status")).toEqual({ status: "missing" });
    expect(cache.inspect("macro_snapshot")).toEqual({ status: "missing" });
    expect(cache.inspect("news_status")).toMatchObject({ status: "fresh" });
    cache.replace("macro_status", { marker: "new status" });
    cache.replace("macro_snapshot", { marker: "new snapshot" });
    await act(async () => { await harness.current().pollSchedule(); });
    expect(cache.inspect("macro_status")).toMatchObject({ status: "fresh" });
    expect(cache.inspect("macro_snapshot")).toMatchObject({ status: "fresh" });
    harness.unmount();
  });

  it("classifies future macro sources by write target and fails closed to both macro keys", async () => {
    const result = await transitionFromRunning(
      "future_macro_source_v9",
      "succeeded",
      "macro_calendar.db",
    );

    expect(result.cache.inspect("macro_status")).toEqual({ status: "missing" });
    expect(result.cache.inspect("macro_snapshot")).toEqual({ status: "missing" });
    expect(result.cache.inspect("news_status")).toMatchObject({ status: "fresh" });
    result.harness.unmount();
  });

  it("mount idle focus visibility and local status reload send zero POSTs", async () => {
    vi.useFakeTimers();
    const harness = await renderControls();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
      window.dispatchEvent(new Event("focus"));
      document.dispatchEvent(new Event("visibilitychange"));
      await harness.current().reloadSchedule();
    });

    expect(vi.mocked(getSchedule).mock.calls.length).toBeGreaterThanOrEqual(3);
    expect(putSchedule).not.toHaveBeenCalled();
    expect(runScheduleNow).not.toHaveBeenCalled();
    harness.unmount();
  });
});
