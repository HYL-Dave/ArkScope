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
      return status({ review: applied ? null : review });
    });
    await mount(changed);

    expect(host!.textContent).toContain("IBKR 主帳戶");
    expect(host!.textContent).toContain("AAPL");
    await clickButton("套用同步");

    expect(calls.some((call) => call.url.endsWith("/runs/55/apply") && call.method === "POST")).toBe(true);
    expect(changed).toHaveBeenCalledTimes(1);
    expect(host!.textContent).not.toContain("待套用差異");
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
