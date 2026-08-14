/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import i18n from "i18next";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  MacroSnapshot,
  MacroStatus,
  ScheduleRunResult,
  ScheduleSourceState,
} from "../api";
import { formatSystemTimestamp } from "../timeDisplay";
import { createSettingsReadCache, type SettingsReadCache } from "./settingsReadCache";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

const controls = vi.hoisted(() => ({
  status: null as MacroStatus | null,
  snapshot: null as MacroSnapshot | null,
  schedule: null as { sources: Record<string, ScheduleSourceState> } | null,
  statusQueue: [] as Array<MacroStatus | Error | Promise<MacroStatus>>,
  snapshotQueue: [] as Array<MacroSnapshot | Error | Promise<MacroSnapshot>>,
  scheduleQueue: [] as Array<
    { sources: Record<string, ScheduleSourceState> }
    | Error
    | Promise<{ sources: Record<string, ScheduleSourceState> }>
  >,
}));

function nextValue<T>(queue: Array<T | Error | Promise<T>>, fallback: T | null): Promise<T> {
  const value = queue.shift() ?? fallback;
  if (value instanceof Error) return Promise.reject(value);
  if (value == null) return Promise.reject(new Error("fixture unavailable"));
  return Promise.resolve(value);
}

vi.mock("../api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api")>();
  return {
    ...actual,
    getMacroStatus: vi.fn(() => nextValue(controls.statusQueue, controls.status)),
    getMacroSnapshot: vi.fn(() => nextValue(controls.snapshotQueue, controls.snapshot)),
    getSchedule: vi.fn(() => nextValue(controls.scheduleQueue, controls.schedule)),
    putSchedule: vi.fn(async () => ({
      source: "fred_series",
      enabled: true,
      interval_minutes: 1440,
    })),
    runScheduleNow: vi.fn(async (source: string): Promise<ScheduleRunResult> => ({
      source,
      status: "started",
    })),
  };
});

import {
  getMacroSnapshot,
  getMacroStatus,
  getSchedule,
  putSchedule,
  runScheduleNow,
} from "../api";
import { DataScheduleControlsProvider } from "./dataScheduleControls";
import { MacroStorageSection } from "./MacroStorageSection";

const statusFixture: MacroStatus = {
  macro_db: "/tmp/macro_calendar.db",
  exists: true,
  tables: {
    macro_series: { row_count: 2, last_fetched_at: "2026-07-19T03:00:00Z" },
    macro_observations: { row_count: 12, last_fetched_at: "2026-07-19T03:00:00Z" },
    macro_release_dates: { row_count: 3, last_fetched_at: "2026-07-18T03:00:00Z" },
    cal_economic_events: { row_count: 4, last_fetched_at: "2026-07-17T03:00:00Z" },
    cal_earnings_events: { row_count: 5, last_fetched_at: "2026-07-17T03:00:00Z" },
    cal_ipo_events: { row_count: 6, last_fetched_at: "2026-07-17T03:00:00Z" },
  },
  use_local_macro_setting: false,
  env_override: false,
  local_first_active: true,
};

const snapshotFixture: MacroSnapshot = {
  available: true,
  macro_db: "/tmp/macro_calendar.db",
  series_count: 2,
  observation_count: 12,
  release_dates_count: 3,
  latest_fetched_at: "2026-07-19T03:00:00Z",
  items: [
    {
      series_id: "FEDFUNDS",
      label: "Fed Funds",
      title: "Federal Funds Effective Rate",
      units: "Percent",
      value: 4.33,
      observation_date: "2026-07-01",
      fetched_at: "2026-07-19T03:00:00Z",
      realtime_start: "2026-07-01",
      realtime_end: "2026-07-01",
    },
    {
      series_id: "CPIAUCSL",
      label: "US CPI",
      title: "Consumer Price Index",
      units: "Index",
      value: 321.5,
      observation_date: "2026-06-01",
      fetched_at: "2026-07-18T03:00:00Z",
      realtime_start: "2026-06-01",
      realtime_end: "2026-06-01",
    },
  ],
  missing_series: [],
};

const MACRO_SOURCE_IDS = [
  "fred_series",
  "fred_release_dates",
  "finnhub_economic_calendar",
  "finnhub_earnings_calendar",
  "finnhub_ipo_calendar",
] as const;

function scheduleSource(
  sourceId: typeof MACRO_SOURCE_IDS[number],
  enabled: boolean,
): ScheduleSourceState {
  return {
    label: sourceId,
    description: `${sourceId} description`,
    ibkr: false,
    provider_fetch: true,
    source_mode: "direct_local",
    write_target: "macro_calendar.db",
    source_badges: [],
    enabled,
    interval_minutes: sourceId === "fred_release_dates" ? 10080 : 1440,
    default_interval_minutes: sourceId === "fred_release_dates" ? 10080 : 1440,
    running: false,
    progress: null,
    last_attempt_at: null,
    last_result: null,
    durable_state: null,
    job_name: `fetch_${sourceId}`,
  };
}

function scheduleFixture(
  enabled: readonly string[] = [],
): { sources: Record<string, ScheduleSourceState> } {
  return {
    sources: Object.fromEntries(MACRO_SOURCE_IDS.map((sourceId) => [
      sourceId,
      scheduleSource(sourceId, enabled.includes(sourceId)),
    ])),
  };
}

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: Error) => void;
  const promise = new Promise<T>((accept, decline) => {
    resolve = accept;
    reject = decline;
  });
  return { promise, resolve, reject };
}

async function flush() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

async function renderMacro(settingsReadCache: SettingsReadCache = createSettingsReadCache()) {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(
      <DataScheduleControlsProvider settingsReadCache={settingsReadCache}>
        <MacroStorageSection settingsReadCache={settingsReadCache} />
      </DataScheduleControlsProvider>,
    );
  });
  await flush();
}

function dispose() {
  if (root) act(() => root!.unmount());
  root = null;
  host?.remove();
  host = null;
}

function refreshButton(): HTMLButtonElement {
  const button = Array.from(host!.querySelectorAll<HTMLButtonElement>("button"))
    .find((candidate) => candidate.textContent?.trim() === "重新讀取狀態");
  if (!button) throw new Error("missing refresh command");
  return button;
}

beforeEach(async () => {
  await i18n.changeLanguage("zh-Hant");
  controls.status = statusFixture;
  controls.snapshot = snapshotFixture;
  controls.schedule = scheduleFixture();
  controls.statusQueue = [];
  controls.snapshotQueue = [];
  controls.scheduleQueue = [];
  vi.mocked(getMacroStatus).mockClear();
  vi.mocked(getMacroSnapshot).mockClear();
  vi.mocked(getSchedule).mockClear();
  vi.mocked(putSchedule).mockClear();
  vi.mocked(runScheduleNow).mockClear();
});

afterEach(() => {
  dispose();
  document.body.replaceChildren();
});

describe("MacroStorageSection", () => {
  it("caches_status_and_snapshot_independently_and_refreshes_only_requested_legs", async () => {
    const now = Date.parse("2026-08-09T02:00:00Z");
    const cache = createSettingsReadCache({ clock: () => now });
    cache.replace("macro_status", statusFixture, now);
    cache.replace("macro_snapshot", snapshotFixture, now - 120_000);
    cache.replace("news_status", { marker: "news" }, now);
    const refreshedSnapshot = {
      ...snapshotFixture,
      observation_count: 19,
      items: [{ ...snapshotFixture.items[0], value: 4.5 }],
    };
    const snapshotRefresh = deferred<MacroSnapshot>();
    controls.snapshotQueue = [snapshotRefresh.promise];

    await renderMacro(cache);
    expect(host!.textContent).toContain("12 筆已儲存");
    expect(host!.textContent).toContain("Fed Funds");
    expect(getMacroStatus).not.toHaveBeenCalled();
    expect(getMacroSnapshot).toHaveBeenCalledOnce();

    await act(async () => {
      snapshotRefresh.resolve(refreshedSnapshot);
      await Promise.resolve();
    });
    expect(host!.textContent).toContain("4.5");
    expect(getMacroStatus).not.toHaveBeenCalled();
    expect(getMacroSnapshot).toHaveBeenCalledOnce();

    vi.mocked(getMacroStatus).mockClear();
    vi.mocked(getMacroSnapshot).mockClear();
    await act(async () => {
      refreshButton().click();
      await Promise.resolve();
    });
    expect(getMacroStatus).toHaveBeenCalledOnce();
    expect(getMacroSnapshot).toHaveBeenCalledOnce();
    expect(cache.inspect("news_status").status).toBe("fresh");
  });

  it("reloads_both_mounted_macro_legs_after_data_sync_invalidation", async () => {
    const cache = createSettingsReadCache();
    cache.replace("macro_status", statusFixture);
    cache.replace("macro_snapshot", snapshotFixture);
    controls.status = {
      ...statusFixture,
      tables: {
        ...statusFixture.tables,
        macro_observations: { row_count: 99, last_fetched_at: "2026-08-10T03:00:00Z" },
      },
    };
    controls.snapshot = {
      ...snapshotFixture,
      items: [{ ...snapshotFixture.items[0], label: "Updated Fed Funds", value: 4.5 }],
    };

    await renderMacro(cache);
    expect(getMacroStatus).not.toHaveBeenCalled();
    expect(getMacroSnapshot).not.toHaveBeenCalled();

    await act(async () => {
      cache.invalidateAllDataSyncReads();
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(getMacroStatus).toHaveBeenCalledOnce();
    expect(getMacroSnapshot).toHaveBeenCalledOnce();
    expect(host!.textContent).toContain("99 筆已儲存");
    expect(host!.textContent).toContain("Updated Fed Funds");
  });

  it("loads_status_and_snapshot_independently_and_renders_both_truths", async () => {
    await renderMacro();

    expect(getMacroStatus).toHaveBeenCalledOnce();
    expect(getMacroSnapshot).toHaveBeenCalledOnce();
    expect(host!.textContent).toContain("總經資料");
    expect(host!.textContent).toContain("12 筆已儲存");
    expect(host!.textContent).toContain("Fed Funds");
    expect(host!.textContent).toContain("FEDFUNDS");
    expect(host!.textContent).toContain("4.33");
    expect(host!.textContent).toContain("經濟事件");
    expect(host!.querySelector('[data-testid="fred-snapshot-scroll"]')).not.toBeNull();
    expect(host!.querySelector('[data-state="partial"]')).toBeNull();
  });

  it("preserves_snapshot_details_when_status_leg_fails", async () => {
    controls.statusQueue = [new Error("RAW_STATUS_TRANSPORT_SECRET")];
    await renderMacro();

    expect(host!.textContent).toContain("Fed Funds");
    expect(host!.querySelector('[data-state="partial"]')).not.toBeNull();
    expect(host!.textContent).not.toContain("RAW_STATUS_TRANSPORT_SECRET");
  });

  it("preserves_status_coverage_when_snapshot_leg_fails", async () => {
    controls.snapshotQueue = [new Error("RAW_SNAPSHOT_TRANSPORT_SECRET")];
    await renderMacro();

    expect(host!.textContent).toContain("12 筆已儲存");
    expect(host!.textContent).toContain("經濟事件");
    expect(host!.querySelector('[data-state="partial"]')).not.toBeNull();
    expect(host!.textContent).not.toContain("RAW_SNAPSHOT_TRANSPORT_SECRET");
  });

  it("renders_missing_database_and_table_as_unavailable_not_empty_success", async () => {
    controls.status = { ...statusFixture, exists: false, tables: {} };
    controls.snapshot = { ...snapshotFixture, available: false, items: [] };
    await renderMacro();
    expect(host!.textContent).toContain("資料庫或必要資料表目前不可用");
    expect(host!.textContent).not.toContain("0 筆已儲存");

    dispose();
    controls.status = {
      ...statusFixture,
      exists: true,
      tables: { cal_ipo_events: { row_count: 1, last_fetched_at: null } },
    };
    await renderMacro();
    expect(host!.textContent).toContain("資料庫或必要資料表目前不可用");
  });

  it("renders_zero_rows_as_zero_stored_without_claiming_never_run", async () => {
    controls.status = {
      ...statusFixture,
      tables: Object.fromEntries(Object.keys(statusFixture.tables).map((key) => [
        key,
        { row_count: 0, last_fetched_at: null },
      ])),
    };
    controls.snapshot = {
      ...snapshotFixture,
      series_count: 0,
      observation_count: 0,
      release_dates_count: 0,
      latest_fetched_at: null,
      items: [],
    };
    await renderMacro();

    expect(host!.textContent).toContain("0 筆已儲存");
    expect(host!.textContent).not.toMatch(/從未|尚未收集|抓取成功為空/);
  });

  it("renders five macro schedule rows and all three automation states", async () => {
    await renderMacro();

    expect(host!.querySelectorAll("[data-testid='schedule-scroll'] tbody tr")).toHaveLength(5);
    expect(host!.textContent).toContain("App 自動更新未啟用");

    dispose();
    controls.schedule = scheduleFixture(["fred_series", "finnhub_ipo_calendar"]);
    await renderMacro();
    expect(host!.textContent).toContain("2 個資料來源已啟用 App 自動更新");

    dispose();
    controls.schedule = null;
    controls.scheduleQueue = [new Error("RAW_SCHEDULE_READ_FAILURE")];
    await renderMacro();
    expect(host!.textContent).toContain("無法確認 App 自動更新狀態");
    expect(host!.textContent).not.toContain("RAW_SCHEDULE_READ_FAILURE");
  });

  it("labels local status reload separately from provider updates", async () => {
    await renderMacro();
    vi.mocked(getMacroStatus).mockClear();
    vi.mocked(getMacroSnapshot).mockClear();
    vi.mocked(getSchedule).mockClear();

    await act(async () => refreshButton().click());
    await flush();

    expect(getMacroStatus).toHaveBeenCalledOnce();
    expect(getMacroSnapshot).toHaveBeenCalledOnce();
    expect(getSchedule).not.toHaveBeenCalled();
    expect(putSchedule).not.toHaveBeenCalled();
    expect(runScheduleNow).not.toHaveBeenCalled();
    expect(host!.textContent).toContain(
      "「重新讀取狀態」只會讀取本機資料，不會向資料供應商抓取資料。",
    );
  });

  it("keeps failed and busy runs visible without rewriting stored timestamps", async () => {
    const schedule = scheduleFixture();
    schedule.sources.fred_series = {
      ...schedule.sources.fred_series,
      last_attempt_at: "2026-08-13T02:00:00Z",
      durable_state: {
        last_status: "failed",
        last_error: "provider_config_missing",
        continuation: null,
        last_attempt: "2026-08-13T02:00:00Z",
        updated_at: "2026-08-13T02:00:01Z",
      },
    };
    schedule.sources.fred_release_dates = {
      ...schedule.sources.fred_release_dates,
      last_result: {
        source: "fred_release_dates",
        status: "skipped",
        reason: "macro_calendar_busy",
      },
    };
    controls.schedule = schedule;
    await renderMacro();

    const failedRow = host!.querySelector("[data-source-id='fred_series']");
    const busyRow = host!.querySelector("[data-source-id='fred_release_dates']");
    expect(failedRow?.textContent).toContain("上次失敗");
    expect(busyRow?.textContent).toContain("新觸發已略過");
    expect(host!.textContent).toContain(formatSystemTimestamp("2026-07-19T03:00:00Z"));
    expect(host!.textContent).toContain("12 筆已儲存");
  });

  it("renders bilingual manual update copy without ingestion wording", async () => {
    await renderMacro();

    expect(host!.textContent).toContain(
      "可在下方設定五個資料來源的自動更新排程，或按「立即更新」手動執行",
    );
    expect(host!.textContent).not.toContain("攝入");

    await act(async () => { await i18n.changeLanguage("en"); });
    expect(host!.textContent).toContain(
      "Configure automatic schedules for the five sources below or choose Run now for a manual update.",
    );
    expect(host!.textContent).not.toMatch(/ingestion|攝入/i);
  });

  it("refresh_reloads_each_leg_once_without_raw_exception_copy", async () => {
    const oldStatus = deferred<MacroStatus>();
    const oldSnapshot = deferred<MacroSnapshot>();
    const newestStatus = {
      ...statusFixture,
      tables: {
        ...statusFixture.tables,
        macro_observations: { row_count: 99, last_fetched_at: "2026-07-20T03:00:00Z" },
      },
    };
    const newestSnapshot = {
      ...snapshotFixture,
      items: [{ ...snapshotFixture.items[0], label: "Newest Fed Funds", value: 4.5 }],
    };
    controls.statusQueue = [oldStatus.promise, newestStatus];
    controls.snapshotQueue = [oldSnapshot.promise, newestSnapshot];
    await renderMacro();

    await act(async () => refreshButton().click());
    await flush();
    expect(getMacroStatus).toHaveBeenCalledOnce();
    expect(getMacroSnapshot).toHaveBeenCalledOnce();

    await act(async () => {
      oldStatus.resolve(statusFixture);
      oldSnapshot.resolve(snapshotFixture);
      await Promise.resolve();
    });
    await act(async () => refreshButton().click());
    await flush();
    expect(getMacroStatus).toHaveBeenCalledTimes(2);
    expect(getMacroSnapshot).toHaveBeenCalledTimes(2);
    expect(host!.textContent).toContain("Newest Fed Funds");
    expect(host!.textContent).toContain("99 筆已儲存");

    controls.statusQueue = [new Error("RAW_LATE_STATUS_EXCEPTION")];
    controls.snapshotQueue = [new Error("RAW_LATE_SNAPSHOT_EXCEPTION")];
    await act(async () => refreshButton().click());
    await flush();
    expect(getMacroStatus).toHaveBeenCalledTimes(3);
    expect(getMacroSnapshot).toHaveBeenCalledTimes(3);
    expect(host!.textContent).toContain("Newest Fed Funds");
    expect(host!.textContent).not.toMatch(/RAW_LATE_STATUS_EXCEPTION|RAW_LATE_SNAPSHOT_EXCEPTION/);
  });

  it("renders English Macro Data status snapshot and table headings", async () => {
    await i18n.changeLanguage("en");
    const withoutTable = (tableName: string): MacroStatus["tables"] =>
      Object.fromEntries(Object.entries(statusFixture.tables).filter(([key]) =>
        key !== tableName));
    const optionalTableMissing = withoutTable("cal_ipo_events");
    const requiredTableMissing = withoutTable("macro_observations");
    const cases: Array<{
      status: MacroStatus;
      expectedUnavailable: "table" | "database";
    }> = [
      {
        status: { ...statusFixture, tables: optionalTableMissing },
        expectedUnavailable: "table",
      },
      {
        status: { ...statusFixture, exists: false },
        expectedUnavailable: "database",
      },
      {
        status: { ...statusFixture, tables: requiredTableMissing },
        expectedUnavailable: "database",
      },
    ];

    for (const [index, scenario] of cases.entries()) {
      controls.status = scenario.status;
      await renderMacro();

      expect.soft(host!.querySelector("h2")?.textContent).toBe("Macro Data");
      expect.soft(host!.textContent).toContain("FRED Snapshot");
      expect.soft(host!.textContent).toContain("12 stored");
      expect.soft(host!.textContent).toContain(
        `12 stored · last fetched ${formatSystemTimestamp("2026-07-19T03:00:00Z")}`,
      );
      expect.soft(host!.textContent).toContain("FEDFUNDS");
      expect.soft(host!.textContent).toContain("Federal Funds Effective Rate");
      expect.soft(host!.textContent).toContain("4.33 Percent");
      expect.soft(host!.textContent).toContain("2026-07-01");
      expect.soft(host!.textContent).toContain(
        formatSystemTimestamp("2026-07-19T03:00:00Z"),
      );
      expect.soft(Array.from(host!.querySelectorAll(".settings-fred-table th")).map((node) => node.textContent))
        .toEqual(["Series ID", "Name", "Latest value", "Observation date", "Last fetch"]);

      if (scenario.expectedUnavailable === "table") {
        const ipoLabel = Array.from(host!.querySelectorAll("dt")).find((node) =>
          node.textContent === "IPO Events");
        expect.soft(ipoLabel?.nextElementSibling?.textContent).toBe("Unavailable");
        expect.soft(host!.querySelector('[data-state="blocked"]')).toBeNull();
      } else {
        expect.soft(host!.querySelector('[data-state="blocked"]')?.textContent)
          .toContain("The database or required tables are currently unavailable");
      }
      expect.soft(host!.textContent).not.toContain("Macro Data is currently unavailable");
      expect(getMacroStatus).toHaveBeenCalledTimes(index + 1);
      expect(getMacroSnapshot).toHaveBeenCalledTimes(index + 1);
      dispose();
    }
  });

  it("switches locale without refetching either status leg", async () => {
    await renderMacro();
    expect(getMacroStatus).toHaveBeenCalledOnce();
    expect(getMacroSnapshot).toHaveBeenCalledOnce();
    expect(host!.textContent).toContain("總經資料");
    expect(host!.textContent).toContain("FEDFUNDS");
    expect(host!.textContent).toContain("12 筆已儲存");

    await act(async () => {
      await i18n.changeLanguage("en");
    });

    expect(getMacroStatus).toHaveBeenCalledOnce();
    expect(getMacroSnapshot).toHaveBeenCalledOnce();
    expect(host!.textContent).toContain("Macro Data");
    expect(host!.textContent).toContain("FEDFUNDS");
    expect(host!.textContent).toContain("12 stored");
    expect(host!.textContent).toContain("2026-07-01");
  });
});
