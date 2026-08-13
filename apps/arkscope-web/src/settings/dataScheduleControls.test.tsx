/** @vitest-environment jsdom */
import { readFileSync } from "node:fs";

import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import i18n from "i18next";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  getSchedule,
  putSchedule,
  runScheduleNow,
  type ScheduleRunResult,
  type ScheduleSourceState,
} from "../api";
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

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

async function controlsModule() {
  const path = "./dataScheduleControls";
  return import(/* @vite-ignore */ path);
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
  sourceIds,
  externalBusy = false,
}: {
  cache?: SettingsReadCache;
  consumers?: number;
  sourceIds?: readonly string[];
  externalBusy?: boolean;
} = {}): Promise<Harness> {
  const { DataScheduleTable, useDataScheduleControls } = await controlsModule();
  const host = document.createElement("div");
  document.body.append(host);
  const root = createRoot(host);
  const latest: any[] = [];

  function Consumer({ index }: { index: number }) {
    const controller = useDataScheduleControls(cache);
    latest[index] = controller;
    return index === 0 && sourceIds
      ? React.createElement(DataScheduleTable, { controller, sourceIds, externalBusy })
      : null;
  }

  await act(async () => {
    root.render(React.createElement(
      React.Fragment,
      null,
      ...Array.from({ length: consumers }, (_, index) =>
        React.createElement(Consumer, { key: index, index })),
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
  it("shares one schedule read across visible consumers", async () => {
    const harness = await renderControls({ consumers: 2 });
    const dataSourcesOwner = readFileSync("src/settings/DataSourcesSection.tsx", "utf8");

    expect(getSchedule).toHaveBeenCalledOnce();
    expect(harness.current(0).schedule).toEqual(harness.current(1).schedule);
    expect(Object.keys(harness.current(0).schedule)).toEqual([
      "polygon_news",
      "fred_series",
      "fred_release_dates",
    ]);
    expect(dataSourcesOwner).toContain("useDataScheduleControls(settingsReadCache)");
    expect(dataSourcesOwner).toContain("<DataScheduleTable");
    expect(dataSourcesOwner).not.toMatch(/\bgetSchedule\b|\bputSchedule\b|\brunScheduleNow\b/);
    harness.unmount();
  });

  it("filters rows without changing registry truth", async () => {
    const harness = await renderControls({
      sourceIds: ["fred_release_dates", "missing_future_source", "polygon_news"],
      externalBusy: true,
    });

    const rows = Array.from(harness.host.querySelectorAll("tbody tr"));
    expect(rows.map((row) => row.getAttribute("data-source-id"))).toEqual([
      "fred_release_dates",
      "polygon_news",
    ]);
    expect(Object.keys(harness.current().schedule)).toHaveLength(3);
    expect(harness.host.querySelector("[data-schedule-error-code='unknown_schedule_source']")
      ?.getAttribute("data-source-id")).toBe("missing_future_source");
    expect(Array.from(harness.host.querySelectorAll("button, input"))).not.toHaveLength(0);
    expect(Array.from(harness.host.querySelectorAll<HTMLButtonElement | HTMLInputElement>(
      "button, input",
    )).every((control) => control.disabled)).toBe(true);
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

  it("failed skipped and busy macro runs do not invalidate stored data keys", async () => {
    for (const status of ["failed", "skipped", "busy"]) {
      const result = await transitionFromRunning("fred_series", status);
      expect(result.cache.inspect("macro_status"), status).toMatchObject({ status: "fresh" });
      expect(result.cache.inspect("macro_snapshot"), status).toMatchObject({ status: "fresh" });
      result.harness.unmount();
    }
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
