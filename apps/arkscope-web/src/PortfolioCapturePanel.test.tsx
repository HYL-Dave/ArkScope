/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PortfolioCapturePanel } from "./PortfolioCapturePanel";
import type {
  PortfolioCaptureRun,
  PortfolioCaptureStart,
  PortfolioCaptureStatus,
} from "./api";

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

afterEach(() => {
  if (root) act(() => root!.unmount());
  root = null;
  host?.remove();
  host = null;
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function run(over: Partial<PortfolioCaptureRun> = {}): PortfolioCaptureRun {
  return {
    id: 7,
    trigger: "scheduled",
    state: "succeeded",
    started_at: "2026-07-14T05:00:00+00:00",
    finished_at: "2026-07-14T05:00:02+00:00",
    account_leg_state: "complete",
    execution_leg_state: "complete",
    position_leg_state: "complete",
    discovered_account_count: 1,
    new_account_count: 0,
    archived_activity_count: 0,
    inserted_execution_count: 2,
    inserted_commission_count: 2,
    unmatched_count: 0,
    data_conflict_count: 0,
    error_code: null,
    error_detail: null,
    ...over,
  };
}

function status(over: Partial<PortfolioCaptureStatus> = {}): PortfolioCaptureStatus {
  const latest = run();
  return {
    settings: {
      enabled: true,
      interval_minutes: 15,
      source: "default",
      provider_configured: true,
    },
    provider_issue: null,
    running: false,
    next_due_at: "2026-07-14T05:15:00+00:00",
    latest_run: latest,
    recent_runs: [latest],
    review: null,
    ...over,
  };
}

type CaptureResponse = PortfolioCaptureStatus | PortfolioCaptureStart | {
  run_id: number;
  changes: [];
  applies: boolean;
};

function stubFetch(
  handler: (url: string, init?: RequestInit) => CaptureResponse | Promise<CaptureResponse>,
) {
  const calls: Array<{ url: string; method: string; body: unknown }> = [];
  vi.stubGlobal("fetch", vi.fn(async (url: unknown, init?: RequestInit) => {
    const resolved = String(url);
    calls.push({
      url: resolved,
      method: init?.method ?? "GET",
      body: init?.body ? JSON.parse(String(init.body)) : null,
    });
    return new Response(JSON.stringify(await handler(resolved, init)), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  }));
  return calls;
}

async function mount(onPortfolioChanged = vi.fn()) {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(<PortfolioCapturePanel onPortfolioChanged={onPortfolioChanged} />);
  });
  await flush();
  return onPortfolioChanged;
}

async function flush() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

async function clickButton(text: string) {
  const button = Array.from(host!.querySelectorAll<HTMLButtonElement>("button"))
    .find((candidate) => candidate.textContent?.includes(text));
  if (!button) throw new Error(`button not found: ${text}; text=${host!.textContent}`);
  await act(async () => {
    button.click();
  });
  await flush();
}

function setInput(input: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
  setter?.call(input, value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

describe("PortfolioCapturePanel", () => {
  it("renders_default_schedule_and_latest_component_states", async () => {
    stubFetch(() => status());
    await mount();

    const enabled = host!.querySelector<HTMLInputElement>('input[aria-label="啟用持倉同步排程"]')!;
    const interval = host!.querySelector<HTMLInputElement>('input[aria-label="持倉同步間隔（分鐘）"]')!;
    expect(enabled.checked).toBe(true);
    expect(interval.value).toBe("15");
    expect(host!.textContent).toContain("5-1440 分鐘");
    expect(host!.textContent).toContain("下一次");
    expect(host!.querySelector('[data-state="ready"]')?.textContent).toContain("成功");
    expect(host!.textContent).toContain("帳戶 · 完整");
    expect(host!.textContent).toContain("交易 · 完整");
    expect(host!.textContent).toContain("持倉 · 完整");
  });

  it("saves_enabled_and_interval_as_one_atomic_payload", async () => {
    const calls = stubFetch((url, init) => {
      if (url.endsWith("/settings") && init?.method === "PUT") {
        return status({
          settings: {
            enabled: false,
            interval_minutes: 30,
            source: "database",
            provider_configured: true,
          },
          next_due_at: null,
        });
      }
      return status();
    });
    await mount();

    const enabled = host!.querySelector<HTMLInputElement>('input[aria-label="啟用持倉同步排程"]')!;
    const interval = host!.querySelector<HTMLInputElement>('input[aria-label="持倉同步間隔（分鐘）"]')!;
    await act(async () => {
      enabled.click();
      setInput(interval, "30");
    });
    await clickButton("儲存排程");

    expect(calls.find((call) => call.method === "PUT")?.body).toEqual({
      enabled: false,
      interval_minutes: 30,
    });
    expect(host!.textContent).toContain("排程已儲存");
  });

  it("rejects_out_of_range_interval_without_fetch", async () => {
    const calls = stubFetch(() => status());
    await mount();

    const interval = host!.querySelector<HTMLInputElement>('input[aria-label="持倉同步間隔（分鐘）"]')!;
    await act(async () => setInput(interval, "1441"));
    await clickButton("儲存排程");

    expect(calls.filter((call) => call.method === "PUT")).toHaveLength(0);
    expect(host!.textContent).toContain("間隔必須是 5-1440 分鐘的整數");
  });

  it("manual_capture_starts_then_polls_until_terminal", async () => {
    vi.useFakeTimers();
    const running = run({
      id: 8,
      trigger: "manual",
      state: "running",
      finished_at: null,
      account_leg_state: "not_attempted",
      execution_leg_state: "not_attempted",
      position_leg_state: "not_attempted",
    });
    let getCount = 0;
    const calls = stubFetch((url, init) => {
      if (url.endsWith("/runs") && init?.method === "POST") {
        return { accepted: true, state: "running", run: running };
      }
      getCount += 1;
      if (getCount === 1) return status({ latest_run: null, recent_runs: [] });
      if (getCount === 2) return status({ running: true, latest_run: running, recent_runs: [running] });
      const terminal = run({ id: 8, trigger: "manual" });
      return status({ latest_run: terminal, recent_runs: [terminal] });
    });
    await mount();

    await clickButton("立即同步");
    expect(host!.querySelector('[data-state="running"]')?.textContent).toContain("執行中");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
    });

    expect(calls.some((call) => call.url.endsWith("/runs") && call.method === "POST")).toBe(true);
    expect(host!.querySelector('[data-state="ready"]')?.textContent).toContain("成功");
  });

  it("keeps_only_one_status_poll_in_flight", async () => {
    vi.useFakeTimers();
    const changed = vi.fn();
    const running = run({ id: 101, state: "running", finished_at: null });
    const terminal = run({ id: 101, state: "succeeded" });
    let reads = 0;
    let resolvePoll: ((value: PortfolioCaptureStatus) => void) | null = null;
    stubFetch(() => {
      reads += 1;
      if (reads === 1) {
        return status({ running: true, latest_run: running, recent_runs: [running] });
      }
      if (reads === 2) {
        return new Promise<PortfolioCaptureStatus>((resolve) => {
          resolvePoll = resolve;
        });
      }
      return status({ running: false, latest_run: terminal, recent_runs: [terminal] });
    });
    await mount(changed);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(4_000);
    });
    expect(reads).toBe(2);

    await act(async () => {
      resolvePoll!(status({ running: false, latest_run: terminal, recent_runs: [terminal] }));
      await Promise.resolve();
    });
    expect(changed).toHaveBeenCalledTimes(1);
  });

  it("ignores_an_older_poll_response_after_settings_save", async () => {
    vi.useFakeTimers();
    let resolvePoll: ((value: PortfolioCaptureStatus) => void) | null = null;
    let idleReads = 0;
    stubFetch((url, init) => {
      if (url.endsWith("/settings") && init?.method === "PUT") {
        return status({
          settings: {
            enabled: true,
            interval_minutes: 30,
            source: "database",
            provider_configured: true,
          },
        });
      }
      idleReads += 1;
      if (idleReads === 1) return status();
      return new Promise<PortfolioCaptureStatus>((resolve) => {
        resolvePoll = resolve;
      });
    });
    await mount();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    const interval = host!.querySelector<HTMLInputElement>('input[aria-label="持倉同步間隔（分鐘）"]')!;
    await act(async () => setInput(interval, "30"));
    await clickButton("儲存排程");

    await act(async () => {
      resolvePoll!(status());
      await Promise.resolve();
    });
    expect(interval.value).toBe("30");
  });

  it("lets_a_completed_settings_mutation_win_over_a_poll_started_while_it_was_pending", async () => {
    vi.useFakeTimers();
    let resolveSave: ((value: PortfolioCaptureStatus) => void) | null = null;
    let reads = 0;
    stubFetch((url, init) => {
      if (url.endsWith("/settings") && init?.method === "PUT") {
        return new Promise<PortfolioCaptureStatus>((resolve) => {
          resolveSave = resolve;
        });
      }
      reads += 1;
      return status();
    });
    await mount();

    const enabled = host!.querySelector<HTMLInputElement>('input[aria-label="啟用持倉同步排程"]')!;
    const saveButton = Array.from(host!.querySelectorAll<HTMLButtonElement>("button"))
      .find((button) => button.textContent?.includes("儲存排程"))!;
    await act(async () => {
      enabled.click();
      saveButton.click();
      await Promise.resolve();
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(reads).toBe(2);

    await act(async () => {
      resolveSave!(status({
        settings: {
          enabled: false,
          interval_minutes: 15,
          source: "database",
          provider_configured: true,
        },
        next_due_at: null,
      }));
      await Promise.resolve();
    });
    expect(host!.textContent).toContain("排程已停用");
  });

  it("does_not_let_a_delayed_settings_snapshot_regress_a_newer_terminal_run", async () => {
    vi.useFakeTimers();
    const changed = vi.fn();
    const prior = run({ id: 106, state: "succeeded" });
    const running = run({ id: 107, state: "running", finished_at: null });
    const terminal = run({ id: 107, state: "succeeded" });
    let resolveSave: ((value: PortfolioCaptureStatus) => void) | null = null;
    let reads = 0;
    stubFetch((url, init) => {
      if (url.endsWith("/settings") && init?.method === "PUT") {
        return new Promise<PortfolioCaptureStatus>((resolve) => {
          resolveSave = resolve;
        });
      }
      reads += 1;
      return reads === 1
        ? status({ latest_run: prior, recent_runs: [prior] })
        : status({ running: false, latest_run: terminal, recent_runs: [terminal, prior] });
    });
    await mount(changed);

    const enabled = host!.querySelector<HTMLInputElement>('input[aria-label="啟用持倉同步排程"]')!;
    const saveButton = Array.from(host!.querySelectorAll<HTMLButtonElement>("button"))
      .find((button) => button.textContent?.includes("儲存排程"))!;
    await act(async () => {
      enabled.click();
      saveButton.click();
      await Promise.resolve();
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(changed).toHaveBeenCalledTimes(1);

    await act(async () => {
      resolveSave!(status({
        settings: {
          enabled: false,
          interval_minutes: 15,
          source: "database",
          provider_configured: true,
        },
        running: true,
        latest_run: running,
        recent_runs: [running, prior],
      }));
      await Promise.resolve();
    });

    expect(host!.querySelector('[data-state="running"]')).toBeNull();
    expect(Array.from(host!.querySelectorAll('[data-state="ready"]'))
      .some((badge) => badge.textContent?.includes("成功"))).toBe(true);
    expect(host!.textContent).toContain("排程已停用");
    expect(changed).toHaveBeenCalledTimes(1);
  });

  it("clears_a_transient_poll_issue_when_a_pending_settings_save_succeeds", async () => {
    vi.useFakeTimers();
    let resolveSave: ((value: PortfolioCaptureStatus) => void) | null = null;
    let reads = 0;
    stubFetch((url, init) => {
      if (url.endsWith("/settings") && init?.method === "PUT") {
        return new Promise<PortfolioCaptureStatus>((resolve) => {
          resolveSave = resolve;
        });
      }
      reads += 1;
      if (reads === 1) return status();
      throw new Error("transient poll failure");
    });
    await mount();

    const saveButton = Array.from(host!.querySelectorAll<HTMLButtonElement>("button"))
      .find((button) => button.textContent?.includes("儲存排程"))!;
    await act(async () => {
      saveButton.click();
      await Promise.resolve();
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(host!.textContent).toContain("transient poll failure");

    await act(async () => {
      resolveSave!(status());
      await Promise.resolve();
    });
    expect(host!.textContent).not.toContain("transient poll failure");
    expect(host!.textContent).toContain("排程已儲存");
  });

  it("retries_initial_status_failure_on_the_idle_cadence", async () => {
    vi.useFakeTimers();
    let reads = 0;
    vi.stubGlobal("fetch", vi.fn(async () => {
      reads += 1;
      if (reads === 1) throw new Error("sidecar warming up");
      return new Response(JSON.stringify(status()), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }));
    await mount();

    expect(host!.textContent).toContain("sidecar warming up");
    expect(host!.querySelector<HTMLButtonElement>("button")?.disabled).toBe(true);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });

    expect(reads).toBe(2);
    expect(host!.textContent).toContain("最近一次");
  });

  it("uses_the_manual_start_run_when_the_follow_up_status_read_fails", async () => {
    const running = run({ id: 102, trigger: "manual", state: "running", finished_at: null });
    let reads = 0;
    stubFetch((url, init) => {
      if (url.endsWith("/runs") && init?.method === "POST") {
        return { accepted: true, state: "running", run: running };
      }
      reads += 1;
      if (reads === 1) return status({ latest_run: null, recent_runs: [] });
      throw new Error("status refresh failed");
    });
    await mount();

    await clickButton("立即同步");

    expect(host!.querySelector('[data-state="running"]')?.textContent).toContain("執行中");
    const captureButton = Array.from(host!.querySelectorAll<HTMLButtonElement>("button"))
      .find((button) => button.textContent?.includes("立即同步"));
    expect(captureButton?.disabled).toBe(true);
  });

  it("renders_a_rejected_manual_start_as_blocked", async () => {
    stubFetch((url, init) => {
      if (url.endsWith("/runs") && init?.method === "POST") {
        return {
          accepted: false,
          state: "blocked",
          run: null,
          error_code: "already_running",
          error_detail: "另一個同步仍在執行",
        };
      }
      return status();
    });
    await mount();

    await clickButton("立即同步");

    expect(host!.querySelector('[data-state="blocked"]')?.textContent).toContain("另一個同步仍在執行");
  });

  it("does_not_regress_a_terminal_poll_when_the_start_response_arrives_late", async () => {
    vi.useFakeTimers();
    const changed = vi.fn();
    const prior = run({ id: 102, state: "succeeded" });
    const running = run({ id: 103, trigger: "manual", state: "running", finished_at: null });
    const terminal = run({ id: 103, trigger: "manual", state: "succeeded" });
    let resolveStart: ((value: PortfolioCaptureStart) => void) | null = null;
    let reads = 0;
    stubFetch((url, init) => {
      if (url.endsWith("/runs") && init?.method === "POST") {
        return new Promise<PortfolioCaptureStart>((resolve) => {
          resolveStart = resolve;
        });
      }
      reads += 1;
      if (reads === 1) return status({ latest_run: prior, recent_runs: [prior] });
      if (reads === 2) {
        return status({ running: false, latest_run: terminal, recent_runs: [terminal, prior] });
      }
      throw new Error("follow-up status failed");
    });
    await mount(changed);

    const captureButton = Array.from(host!.querySelectorAll<HTMLButtonElement>("button"))
      .find((button) => button.textContent?.includes("立即同步"))!;
    await act(async () => {
      captureButton.click();
      await Promise.resolve();
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(changed).toHaveBeenCalledTimes(1);

    await act(async () => {
      resolveStart!({ accepted: true, state: "running", run: running });
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(host!.querySelector('[data-state="ready"]')?.textContent).toContain("成功");
    expect(host!.querySelector('[data-state="running"]')).toBeNull();
    expect(changed).toHaveBeenCalledTimes(1);
  });

  it("accepts_a_terminal_start_response_after_a_poll_saw_the_same_run_running", async () => {
    vi.useFakeTimers();
    const prior = run({ id: 107, state: "succeeded" });
    const running = run({ id: 108, trigger: "manual", state: "running", finished_at: null });
    const failed = run({
      id: 108,
      trigger: "manual",
      state: "failed",
      error_code: "capture_thread_start_failed",
      error_detail: "Capture worker startup failed",
    });
    let resolveStart: ((value: PortfolioCaptureStart) => void) | null = null;
    let reads = 0;
    stubFetch((url, init) => {
      if (url.endsWith("/runs") && init?.method === "POST") {
        return new Promise<PortfolioCaptureStart>((resolve) => {
          resolveStart = resolve;
        });
      }
      reads += 1;
      if (reads === 1) return status({ latest_run: prior, recent_runs: [prior] });
      if (reads === 2) {
        return status({ running: true, latest_run: running, recent_runs: [running, prior] });
      }
      throw new Error("follow-up status failed");
    });
    await mount();

    const captureButton = Array.from(host!.querySelectorAll<HTMLButtonElement>("button"))
      .find((button) => button.textContent?.includes("立即同步"))!;
    await act(async () => {
      captureButton.click();
      await Promise.resolve();
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(host!.querySelector('[data-state="running"]')).not.toBeNull();

    await act(async () => {
      resolveStart!({ accepted: true, state: "failed", run: failed });
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(host!.querySelector('[data-state="running"]')).toBeNull();
    expect(host!.textContent).toContain("Capture worker startup failed");
  });

  it("does_not_let_an_older_poll_clear_a_newer_action_failure", async () => {
    vi.useFakeTimers();
    let resolvePoll: ((value: PortfolioCaptureStatus) => void) | null = null;
    let reads = 0;
    stubFetch((url, init) => {
      if (url.endsWith("/settings") && init?.method === "PUT") {
        throw new Error("settings write failed");
      }
      reads += 1;
      if (reads === 1) return status();
      return new Promise<PortfolioCaptureStatus>((resolve) => {
        resolvePoll = resolve;
      });
    });
    await mount();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    await clickButton("儲存排程");
    expect(host!.textContent).toContain("settings write failed");

    await act(async () => {
      resolvePoll!(status());
      await Promise.resolve();
    });
    expect(host!.textContent).toContain("settings write failed");
  });

  it("does_not_clear_a_newer_action_failure_after_an_older_terminal_callback_finishes", async () => {
    vi.useFakeTimers();
    let resolveChanged: (() => void) | null = null;
    const changed = vi.fn(() => new Promise<void>((resolve) => {
      resolveChanged = resolve;
    }));
    const running = run({ id: 105, state: "running", finished_at: null });
    const terminal = run({ id: 105, state: "succeeded" });
    let reads = 0;
    stubFetch((url, init) => {
      if (url.endsWith("/settings") && init?.method === "PUT") {
        throw new Error("settings write failed during refresh callback");
      }
      reads += 1;
      return reads === 1
        ? status({ running: true, latest_run: running, recent_runs: [running] })
        : status({ running: false, latest_run: terminal, recent_runs: [terminal] });
    });
    await mount(changed);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
    });
    expect(changed).toHaveBeenCalledTimes(1);
    await clickButton("儲存排程");
    expect(host!.textContent).toContain("settings write failed during refresh callback");

    await act(async () => {
      resolveChanged!();
      await Promise.resolve();
    });
    expect(host!.textContent).toContain("settings write failed during refresh callback");
  });

  it("announces_a_terminal_start_detail_only_once", async () => {
    const blocked = run({
      id: 104,
      trigger: "manual",
      state: "blocked",
      error_code: "provider_config_missing",
      error_detail: "IBKR provider configuration is incomplete",
    });
    stubFetch((url, init) => {
      if (url.endsWith("/runs") && init?.method === "POST") {
        return {
          accepted: true,
          state: "blocked",
          run: blocked,
          error_code: blocked.error_code,
          error_detail: blocked.error_detail,
        };
      }
      return status({ latest_run: blocked, recent_runs: [blocked] });
    });
    await mount();

    await clickButton("立即同步");

    const matchingAlerts = Array.from(host!.querySelectorAll(".ui-inline-alert"))
      .filter((alert) => alert.textContent?.includes("IBKR provider configuration is incomplete"));
    expect(matchingAlerts).toHaveLength(1);
  });

  it("renders_partial_blocked_failed_and_interrupted_with_existing_status_badges", async () => {
    const runs = [
      run({ id: 11, state: "partial" }),
      run({ id: 10, state: "blocked" }),
      run({ id: 9, state: "failed" }),
      run({ id: 8, state: "interrupted" }),
    ];
    stubFetch(() => status({ latest_run: runs[0], recent_runs: runs }));
    await mount();

    for (const stateName of ["partial", "blocked", "failed", "interrupted"]) {
      expect(host!.querySelector(`[data-state="${stateName}"]`)).not.toBeNull();
    }
  });

  it("shows_next_due_and_recent_runs_without_raw_account_id", async () => {
    const latest = run({
      id: 12,
      state: "partial",
      error_code: "capture_partial",
      error_detail: "Account hash 8da21f requires review; no raw identifier returned",
      new_account_count: 1,
      archived_activity_count: 1,
    });
    const payloadWithUnexpectedRawField = { ...latest, raw_broker_account_id: "DU7654321" };
    stubFetch(() => status({
      latest_run: payloadWithUnexpectedRawField,
      recent_runs: [payloadWithUnexpectedRawField],
    }));
    await mount();

    expect(host!.textContent).toContain("下一次");
    expect(host!.textContent).toContain("待檢視");
    expect(host!.textContent).toContain("封存帳戶有新活動");
    expect(host!.querySelector('table[aria-label="持倉同步紀錄"] tbody tr')).not.toBeNull();
    expect(host!.textContent).not.toContain("DU7654321");
    expect(host!.textContent).not.toContain("capture_partial");
    expect(host!.textContent).toContain("同步資料不完整");
  });

  it("renders_latest_review_and_applies_that_capture_run", async () => {
    const changed = vi.fn();
    let applied = false;
    const review = {
      run_id: 55,
      changes: [{
        kind: "update",
        account_id: 3,
        account_label: "IBKR 主帳戶",
        broker_account_id_hash: "5bc54f22a3",
        broker_con_id: "265598",
        symbol: "AAPL",
        quantity: 3,
        before: { quantity: 2 },
        after: { quantity: 3 },
      }],
      applies: false,
    };
    const calls = stubFetch((url, init) => {
      if (url.endsWith("/runs/55/apply") && init?.method === "POST") {
        applied = true;
        return { run_id: 55, changes: [], applies: true };
      }
      return status({
        review: applied ? { run_id: 55, changes: [], applies: false } : review,
      });
    });
    await mount(changed);

    expect(host!.textContent).toContain("IBKR 主帳戶");
    expect(host!.textContent).toContain("AAPL");
    await clickButton("套用同步");

    expect(calls.some((call) => call.url.endsWith("/runs/55/apply") && call.method === "POST")).toBe(true);
    expect(changed).toHaveBeenCalledTimes(1);
    expect(host!.textContent).not.toContain("待套用差異");
  });

  it("clears_a_stale_review_when_post_apply_refresh_fails", async () => {
    const review = {
      run_id: 56,
      changes: [{
        kind: "update",
        account_id: 3,
        account_label: "IBKR 主帳戶",
        broker_account_id_hash: "5bc54f22a3",
        broker_con_id: "265598",
        symbol: "AAPL",
        quantity: 3,
        before: { quantity: 2 },
        after: { quantity: 3 },
      }],
      applies: false,
    };
    let reads = 0;
    stubFetch((url, init) => {
      if (url.endsWith("/runs/56/apply") && init?.method === "POST") {
        return { run_id: 56, changes: [], applies: true };
      }
      reads += 1;
      if (reads === 1) return status({ review });
      throw new Error("status refresh failed");
    });
    await mount();

    await clickButton("套用同步");

    expect(host!.textContent).not.toContain("待套用差異");
    expect(host!.textContent).toContain("status refresh failed");
    expect(host!.textContent).toContain("同步狀態載入失敗");
  });

  it("does_not_clear_a_newer_review_when_an_older_apply_response_arrives_late", async () => {
    vi.useFakeTimers();
    const oldReview = {
      run_id: 58,
      changes: [{
        kind: "update",
        account_id: 3,
        account_label: "IBKR 主帳戶",
        broker_account_id_hash: "5bc54f22a3",
        broker_con_id: "265598",
        symbol: "AAPL",
        quantity: 3,
        before: { quantity: 2 },
        after: { quantity: 3 },
      }],
      applies: false,
    };
    const newReview = {
      ...oldReview,
      run_id: 59,
      changes: [{
        ...oldReview.changes[0],
        broker_con_id: "272093",
        symbol: "MSFT",
      }],
    };
    let resolveApply: ((value: CaptureResponse) => void) | null = null;
    let reads = 0;
    stubFetch((url, init) => {
      if (url.endsWith("/runs/58/apply") && init?.method === "POST") {
        return new Promise<CaptureResponse>((resolve) => {
          resolveApply = resolve;
        });
      }
      reads += 1;
      if (reads === 1) return status({ review: oldReview });
      if (reads === 2) return status({ review: newReview });
      throw new Error("post-apply refresh failed");
    });
    await mount();

    const applyButton = Array.from(host!.querySelectorAll<HTMLButtonElement>("button"))
      .find((button) => button.textContent?.includes("套用同步"))!;
    await act(async () => {
      applyButton.click();
      await Promise.resolve();
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(host!.textContent).toContain("MSFT");

    await act(async () => {
      resolveApply!({ run_id: 58, changes: [], applies: true });
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(host!.textContent).toContain("MSFT");
    expect(host!.textContent).toContain("post-apply refresh failed");
  });

  it("shows_nullable_review_values_being_cleared", async () => {
    stubFetch(() => status({
      review: {
        run_id: 57,
        changes: [{
          kind: "update",
          account_id: 3,
          account_label: "IBKR 主帳戶",
          broker_account_id_hash: "5bc54f22a3",
          broker_con_id: "265598",
          symbol: "AAPL",
          quantity: 3,
          before: { quantity: 3, avg_cost: 100 },
          after: { quantity: 3, avg_cost: null },
        }],
        applies: false,
      },
    }));
    await mount();

    const reviewTable = host!.querySelector('table[aria-label="持倉同步待檢視差異"]')!;
    expect(reviewTable.textContent).toContain("100 → -");
  });

  it("returns_to_idle_polling_without_repeated_live_announcements_after_terminal", async () => {
    vi.useFakeTimers();
    const changed = vi.fn();
    const running = run({ id: 99, state: "running", finished_at: null });
    const terminal = run({ id: 99, state: "succeeded" });
    let reads = 0;
    stubFetch(() => {
      reads += 1;
      return reads === 1
        ? status({ running: true, latest_run: running, recent_runs: [running] })
        : status({ running: false, latest_run: terminal, recent_runs: [terminal] });
    });
    await mount(changed);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
    });
    expect(changed).toHaveBeenCalledTimes(1);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });
    expect(changed).toHaveBeenCalledTimes(1);
    expect(host!.querySelector("[aria-live]")).toBeNull();
  });
});
