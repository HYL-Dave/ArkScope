/** @vitest-environment jsdom */
import { afterEach, describe, expect, it, vi } from "vitest";

import * as api from "./api";

const CONFIG = {
  enabled: true,
  interval_minutes: 30,
  batch_limit: 2,
  apply_profile_transitions: false,
} as const;

const STATUS = {
  config_status: "valid",
  config: CONFIG,
  schedule: {
    status: "scheduled",
    last_attempt_at: "2026-08-31T04:55:00Z",
    next_scheduled_at: "2026-08-31T05:25:00Z",
  },
  telemetry_status: "valid",
  last_status: "partial",
  last_result: {
    status: "partial",
    reason: "case_processing_blocked",
    selected: 1,
    processed: 1,
    accepted: 0,
    drafted: 0,
    blocked: 1,
    failed: 0,
    skipped_current: 0,
    case_ids: ["slc_case_1"],
    result_version: 2,
    case_outcomes: { slc_case_1: "blocked" },
  },
  active_incident: {
    case_failures: {
      slc_case_2: { run_id: "slar_failed", recovery: "new_attempt" },
    },
    scheduler_failure: null,
  },
  latest_failed_runs: [{
    run_id: "slar_failed",
    case_id: "slc_case_2",
    failure_code: "internal_error",
    started_at: "2026-08-31T04:50:00Z",
    finished_at: "2026-08-31T04:50:01Z",
    updated_at: "2026-08-31T04:50:01Z",
  }],
  current_progress: [{
    trigger: "manual_case",
    request_id: "slao_request_1",
    case_id: "slc_case_1",
    started_at: "2026-08-31T05:00:00Z",
    current_stage: "listing",
    completed_stages: ["preparing", "sec"],
    skipped_stages: [],
  }],
} as const;

function response(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("security lifecycle automation API", () => {
  it("parses the closed status contract from the lifecycle endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(STATUS));
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      (api as typeof api & {
        getSecurityLifecycleAutomationStatus: () => Promise<unknown>;
      }).getSecurityLifecycleAutomationStatus(),
    ).resolves.toEqual(STATUS);

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(String(url)).toBe("http://127.0.0.1:8420/security-lifecycle/automation");
    expect(init.method).toBeUndefined();
  });

  it("PUTs the complete config without implicit defaults", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response({
      config_status: "valid",
      config: CONFIG,
    }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      (api as typeof api & {
        updateSecurityLifecycleAutomationConfig: (
          config: typeof CONFIG,
        ) => Promise<unknown>;
      }).updateSecurityLifecycleAutomationConfig(CONFIG),
    ).resolves.toEqual({ config_status: "valid", config: CONFIG });

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(String(url)).toBe("http://127.0.0.1:8420/security-lifecycle/automation");
    expect(init.method).toBe("PUT");
    expect(JSON.parse(String(init.body))).toEqual(CONFIG);
    expect(Object.keys(JSON.parse(String(init.body)))).toEqual([
      "enabled",
      "interval_minutes",
      "batch_limit",
      "apply_profile_transitions",
    ]);
  });

  it("dispatches due and case runs through their distinct attended endpoints", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(response({
        scope: "due",
        status: "started",
        request_id: "slao_due",
      }))
      .mockResolvedValueOnce(response({
        scope: "case",
        status: "started",
        request_id: "slao_case",
        case_id: "slc/case 1",
      }));
    vi.stubGlobal("fetch", fetchMock);
    const typed = api as typeof api & {
      runDueSecurityLifecycleAutomation: () => Promise<unknown>;
      runSecurityLifecycleCaseAutomation: (caseId: string) => Promise<unknown>;
    };

    await expect(typed.runDueSecurityLifecycleAutomation()).resolves.toEqual({
      scope: "due",
      status: "started",
      request_id: "slao_due",
    });
    await expect(typed.runSecurityLifecycleCaseAutomation("slc/case 1")).resolves.toEqual({
      scope: "case",
      status: "started",
      request_id: "slao_case",
      case_id: "slc/case 1",
    });

    expect(String(fetchMock.mock.calls[0][0])).toBe(
      "http://127.0.0.1:8420/security-lifecycle/automation/run",
    );
    expect(String(fetchMock.mock.calls[1][0])).toBe(
      "http://127.0.0.1:8420/security-lifecycle/cases/slc%2Fcase%201/automation/run",
    );
    expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBe("POST");
    expect((fetchMock.mock.calls[1][1] as RequestInit).method).toBe("POST");
  });

  it.each([
    ["schedule status", { ...STATUS, schedule: { ...STATUS.schedule, status: "paused" } }],
    ["progress stage", {
      ...STATUS,
      current_progress: [{ ...STATUS.current_progress[0], current_stage: "llm" }],
    }],
    ["case outcome", {
      ...STATUS,
      last_result: {
        ...STATUS.last_result,
        case_outcomes: { slc_case_1: "ignored" },
      },
    }],
  ])("rejects an unknown %s before it reaches presentation code", async (_name, body) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response(body)));

    await expect(
      (api as typeof api & {
        getSecurityLifecycleAutomationStatus: () => Promise<unknown>;
      }).getSecurityLifecycleAutomationStatus(),
    ).rejects.toThrow("security_lifecycle_automation_contract");
  });

  it("rejects an unknown dispatch status", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({
      scope: "due",
      status: "queued",
    })));

    await expect(
      (api as typeof api & {
        runDueSecurityLifecycleAutomation: () => Promise<unknown>;
      }).runDueSecurityLifecycleAutomation(),
    ).rejects.toThrow("security_lifecycle_automation_contract");
  });
});
