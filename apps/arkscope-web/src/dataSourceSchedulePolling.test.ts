import { describe, expect, it } from "vitest";

import type { ScheduleSourceState } from "./api";
import {
  DATA_SOURCE_SCHEDULE_ACTIVE_POLL_MS,
  DATA_SOURCE_SCHEDULE_IDLE_POLL_MS,
  dataSourceScheduleLifecycleChanged,
  dataSourceSchedulePollMs,
} from "./dataSourceSchedulePolling";

function source(over: Partial<ScheduleSourceState> = {}): ScheduleSourceState {
  return {
    label: "IBKR 新聞",
    description: "IBKR market-news collector",
    ibkr: true,
    provider_fetch: true,
    source_mode: "direct_local",
    write_target: "market_data.db",
    source_badges: [],
    retired: false,
    retired_reason: null,
    enabled: true,
    interval_minutes: 120,
    default_interval_minutes: 120,
    running: false,
    progress: null,
    last_attempt_at: "2026-07-17T10:00:00Z",
    last_result: null,
    gap_planned: false,
    durable_state: {
      last_status: "succeeded",
      last_error: null,
      continuation: null,
      last_attempt: "2026-07-17T10:00:00Z",
      updated_at: "2026-07-17T10:01:00Z",
    },
    job_name: "collect.ibkr_news",
    ...over,
  };
}

describe("Data Sources schedule polling policy", () => {
  it("uses a 30 second idle cadence and a 5 second active cadence", () => {
    expect(dataSourceSchedulePollMs(null)).toBe(DATA_SOURCE_SCHEDULE_IDLE_POLL_MS);
    expect(dataSourceSchedulePollMs({ ibkr_news: source() }))
      .toBe(DATA_SOURCE_SCHEDULE_IDLE_POLL_MS);
    expect(dataSourceSchedulePollMs({
      polygon_news: source({ label: "Polygon", running: false }),
      ibkr_news: source({ running: true }),
    })).toBe(DATA_SOURCE_SCHEDULE_ACTIVE_POLL_MS);
    expect(DATA_SOURCE_SCHEDULE_IDLE_POLL_MS).toBe(30_000);
    expect(DATA_SOURCE_SCHEDULE_ACTIVE_POLL_MS).toBe(5_000);
  });

  it("detects starts stops fast completions and source-set changes", () => {
    const idle = { ibkr_news: source() };
    const running = { ibkr_news: source({ running: true }) };
    const completedBetweenPolls = {
      ibkr_news: source({
        running: false,
        last_attempt_at: "2026-07-17T10:30:00Z",
        durable_state: {
          last_status: "partial",
          last_error: null,
          continuation: null,
          last_attempt: "2026-07-17T10:30:00Z",
          updated_at: "2026-07-17T10:31:00Z",
        },
      }),
    };

    expect(dataSourceScheduleLifecycleChanged(null, idle)).toBe(false);
    expect(dataSourceScheduleLifecycleChanged(idle, running)).toBe(true);
    expect(dataSourceScheduleLifecycleChanged(running, completedBetweenPolls)).toBe(true);
    expect(dataSourceScheduleLifecycleChanged(idle, completedBetweenPolls)).toBe(true);
    expect(dataSourceScheduleLifecycleChanged(idle, {
      ...idle,
      polygon_news: source({ label: "Polygon" }),
    })).toBe(true);
  });

  it("ignores progress and presentation-only changes within one lifecycle revision", () => {
    const before = { ibkr_news: source({ running: true }) };
    const after = {
      ibkr_news: source({
        running: true,
        progress: { done: 17, total: 149, current: "NVDA" },
        last_result: {
          source: "ibkr_news",
          status: "partial",
          collect: {
            status: "partial",
            body_backlog: { status: "ok", scheduled_later: 13 },
          },
        },
      }),
    };

    expect(dataSourceScheduleLifecycleChanged(before, after)).toBe(false);
    expect(dataSourceScheduleLifecycleChanged(
      { polygon_news: source({ label: "Polygon" }), ibkr_news: before.ibkr_news },
      { ibkr_news: after.ibkr_news, polygon_news: source({ label: "Polygon" }) },
    )).toBe(false);
  });
});
