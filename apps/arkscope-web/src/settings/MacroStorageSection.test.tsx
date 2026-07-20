/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import i18n from "i18next";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { MacroSnapshot, MacroStatus } from "../api";
import { formatSystemTimestamp } from "../timeDisplay";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

const controls = vi.hoisted(() => ({
  status: null as MacroStatus | null,
  snapshot: null as MacroSnapshot | null,
  statusQueue: [] as Array<MacroStatus | Error | Promise<MacroStatus>>,
  snapshotQueue: [] as Array<MacroSnapshot | Error | Promise<MacroSnapshot>>,
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
  };
});

import { getMacroSnapshot, getMacroStatus } from "../api";
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
  auto_refresh_enabled: true,
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

async function renderMacro() {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(<MacroStorageSection />);
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
    .find((candidate) => candidate.textContent?.trim() === "重新整理");
  if (!button) throw new Error("missing refresh command");
  return button;
}

beforeEach(async () => {
  await i18n.changeLanguage("zh-Hant");
  controls.status = statusFixture;
  controls.snapshot = snapshotFixture;
  controls.statusQueue = [];
  controls.snapshotQueue = [];
  vi.mocked(getMacroStatus).mockClear();
  vi.mocked(getMacroSnapshot).mockClear();
});

afterEach(() => {
  dispose();
  document.body.replaceChildren();
});

describe("MacroStorageSection", () => {
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

  it("keeps_stored_data_neutral_when_auto_refresh_is_off", async () => {
    controls.snapshot = { ...snapshotFixture, auto_refresh_enabled: false };
    await renderMacro();

    expect(host!.textContent).toContain("自動刷新關閉");
    expect(host!.textContent).toContain("Fed Funds");
    expect(host!.textContent).toContain("最後抓取");
    expect(host!.querySelector('[data-state="failed"]')).toBeNull();
    expect(host!.querySelector('[data-state="blocked"]')).toBeNull();
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
    expect(getMacroStatus).toHaveBeenCalledTimes(2);
    expect(getMacroSnapshot).toHaveBeenCalledTimes(2);
    expect(host!.textContent).toContain("Newest Fed Funds");
    expect(host!.textContent).toContain("99 筆已儲存");

    await act(async () => {
      oldStatus.reject(new Error("RAW_LATE_STATUS_EXCEPTION"));
      oldSnapshot.reject(new Error("RAW_LATE_SNAPSHOT_EXCEPTION"));
      await Promise.resolve();
    });
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
      expect.soft(host!.textContent).toContain("FEDFUNDS");
      expect.soft(host!.textContent).toContain("Federal Funds Effective Rate");
      expect.soft(host!.textContent).toContain("4.33 Percent");
      expect.soft(host!.textContent).toContain("2026-07-01");
      expect.soft(host!.textContent).toContain(
        formatSystemTimestamp("2026-07-19T03:00:00Z"),
      );
      expect.soft(Array.from(host!.querySelectorAll("th")).map((node) => node.textContent))
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
