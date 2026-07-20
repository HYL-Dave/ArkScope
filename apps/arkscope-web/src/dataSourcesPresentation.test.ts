import { describe, expect, it } from "vitest";

import {
  durableScheduleCommonState,
  providerCommonState,
  saSegmentCommonState,
  scheduleSkipCommonState,
} from "./dataSourcesPresentation";
import type { ScheduleSourceState } from "./api";

const schedule = (over: Partial<ScheduleSourceState> = {}): ScheduleSourceState => ({
  label: "Polygon news",
  description: "collector",
  ibkr: false,
  provider_fetch: true,
  source_mode: "direct_local",
  write_target: "market_data.db",
  source_badges: [],
  retired: false,
  retired_reason: null,
  enabled: true,
  interval_minutes: 30,
  default_interval_minutes: 30,
  running: false,
  progress: null,
  last_attempt_at: null,
  last_result: null,
  gap_planned: false,
  durable_state: null,
  job_name: "collect.polygon_news",
  ...over,
});

describe("Data Sources common-state mapping", () => {
  it("maps_badged_provider_statuses_and_leaves_disabled_neutral", () => {
    expect({
      connected: providerCommonState("connected"),
      stale: providerCommonState("stale"),
      maintenance: providerCommonState("maintenance"),
      no_signal: providerCommonState("no_signal"),
      not_configured: providerCommonState("not_configured"),
      missing_key: providerCommonState("missing_key"),
      disabled: providerCommonState("disabled"),
      future_status: providerCommonState("future_status"),
    }).toEqual({
      connected: "ready",
      stale: "stale",
      maintenance: "partial",
      no_signal: "empty",
      not_configured: "blocked",
      missing_key: "blocked",
      disabled: null,
      future_status: null,
    });
  });

  it("maps_sa_segments_to_ready_partial_and_failed", () => {
    expect(["ok", "warn", "fail"].map((state) =>
      saSegmentCommonState(state as "ok" | "warn" | "fail")))
      .toEqual(["ready", "partial", "failed"]);
  });

  it("maps_durable_schedule_history_without_confusing_disabled_schedule_state", () => {
    expect(durableScheduleCommonState(schedule({
      durable_state: { last_status: "succeeded", last_error: null, continuation: null, last_attempt: null, updated_at: null },
    }))).toBe("ready");
    expect(durableScheduleCommonState(schedule({
      durable_state: { last_status: "partial", last_error: null, continuation: { deferred: ["NVDA"] }, last_attempt: null, updated_at: null },
    }))).toBe("partial");
    expect(durableScheduleCommonState(schedule({
      durable_state: { last_status: "failed", last_error: "boom", continuation: null, last_attempt: null, updated_at: null },
    }))).toBe("failed");
    expect(durableScheduleCommonState(schedule({
      durable_state: { last_status: "skipped", last_error: null, continuation: null, last_attempt: null, updated_at: null },
    }))).toBeNull();
    expect(durableScheduleCommonState(schedule({ enabled: true }))).toBe("empty");
    expect(durableScheduleCommonState(schedule({ enabled: false }))).toBeNull();
  });

  it("maps_duplicate_skips_to_blocked_and_other_skips_to_neutral", () => {
    expect(scheduleSkipCommonState("already running in another process")).toBe("blocked");
    expect(scheduleSkipCommonState("IBKR gateway busy (lock timeout)")).toBeNull();
    expect(scheduleSkipCommonState(null)).toBeNull();
  });
});
