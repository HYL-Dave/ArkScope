/** @vitest-environment jsdom */
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { useLifecycleSourceCheck } from "./useLifecycleSourceCheck";

const api = vi.hoisted(() => ({ getSecurityLifecycleAutomationStatus: vi.fn(), runSecurityLifecycleCaseAutomation: vi.fn() }));
vi.mock("../api", () => api);
const idle = { last_status: "success", current_progress: [], telemetry_status: "valid", active_incident: null,
  schedule: { last_attempt_at: "2026-09-05T01:00:00Z" }, last_result: { case_ids: ["slc_old"] } };
const running = { ...idle, last_status: "running" };
const done = { ...idle, schedule: { last_attempt_at: "2026-09-05T01:01:00Z" }, last_result: { case_ids: ["slc_target"] } };
let root: Root, host: HTMLDivElement;
let latest: ReturnType<typeof useLifecycleSourceCheck>;
const completed = vi.fn();
function Harness() { latest = useLifecycleSourceCheck(completed); return null; }
beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  vi.useFakeTimers(); vi.clearAllMocks();
  api.getSecurityLifecycleAutomationStatus.mockReset().mockResolvedValue(idle);
  api.runSecurityLifecycleCaseAutomation.mockReset().mockResolvedValue({ status: "started", request_id: "request_1" });
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
});
afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.useRealTimers(); vi.unstubAllGlobals(); });
async function mount() { await act(async () => root.render(<Harness />)); }
async function tick() { await act(async () => vi.advanceTimersByTimeAsync(2000)); }
async function start() { await act(async () => latest.start("slc_target")); }

it("initial read never dispatches a source check or repeatedly polls idle state", async () => {
  await mount(); await tick();
  expect(api.getSecurityLifecycleAutomationStatus).toHaveBeenCalledTimes(1);
  expect(api.runSecurityLifecycleCaseAutomation).not.toHaveBeenCalled();
  expect(completed).not.toHaveBeenCalled();
});
it("continues polling a durable running job through a temporary read failure", async () => {
  api.getSecurityLifecycleAutomationStatus.mockResolvedValueOnce(running).mockRejectedValueOnce(new Error("offline")).mockResolvedValue(done);
  await mount(); await tick();
  expect(latest.readFailed).toBe(true);
  await tick();
  expect(api.getSecurityLifecycleAutomationStatus).toHaveBeenCalledTimes(3);
  expect(latest.readFailed).toBe(false);
  expect(completed).toHaveBeenCalledTimes(1);
});
it("keeps an attended request pending while durable running has no memory progress", async () => {
  await mount();
  api.getSecurityLifecycleAutomationStatus.mockResolvedValue(running);
  await start(); await tick();
  expect(latest.busy).toBe(true);
  expect(completed).not.toHaveBeenCalled();
  api.getSecurityLifecycleAutomationStatus.mockResolvedValue(done);
  await tick();
  expect(latest.busy).toBe(false);
  expect(completed).toHaveBeenCalledTimes(1);
});
it("does not use a stale same-case result as completion of a new request", async () => {
  api.getSecurityLifecycleAutomationStatus.mockResolvedValue({ ...idle, last_result: { case_ids: ["slc_target"] } });
  await mount(); await start(); await tick();
  expect(latest.busy).toBe(true);
  expect(completed).not.toHaveBeenCalled();
});
it("does not use another case's running or completed job as the request receipt", async () => {
  await mount();
  api.getSecurityLifecycleAutomationStatus.mockResolvedValue(running);
  await start();
  api.getSecurityLifecycleAutomationStatus.mockResolvedValue({ ...done, last_result: { case_ids: ["slc_other"] } });
  await tick();
  expect(latest.busy).toBe(true);
  expect(completed).not.toHaveBeenCalled();
});
it("keeps polling a pending request after a read failure without another POST", async () => {
  await mount();
  api.getSecurityLifecycleAutomationStatus.mockRejectedValueOnce(new Error("offline")).mockResolvedValue(done);
  await start(); await tick();
  expect(latest.busy).toBe(false);
  expect(completed).toHaveBeenCalledTimes(1);
  expect(api.runSecurityLifecycleCaseAutomation).toHaveBeenCalledTimes(1);
});
it("rejects a stale status response after explicit refresh", async () => {
  let release!: (value: unknown) => void;
  api.getSecurityLifecycleAutomationStatus.mockImplementationOnce(() => new Promise((resolve) => { release = resolve; })).mockResolvedValue(running);
  await mount(); await act(async () => latest.refresh());
  await act(async () => release(idle));
  expect(latest.status?.last_status).toBe("running");
});
it("prevents double dispatch before the first promise settles", async () => {
  let release!: (value: unknown) => void;
  api.runSecurityLifecycleCaseAutomation.mockImplementation(() => new Promise((resolve) => { release = resolve; }));
  await mount();
  await act(async () => { void latest.start("slc_target"); void latest.start("slc_target"); });
  expect(api.runSecurityLifecycleCaseAutomation).toHaveBeenCalledTimes(1);
  await act(async () => release({ status: "started", request_id: "request_1" }));
});
it("checks a lost dispatch response through durable reads and never automatically retries it", async () => {
  await mount();
  api.runSecurityLifecycleCaseAutomation.mockRejectedValue(new Error("response_lost"));
  api.getSecurityLifecycleAutomationStatus.mockResolvedValue(running);
  await start();
  expect(latest.busy).toBe(true);
  expect(latest.error).toBe(true);
  api.getSecurityLifecycleAutomationStatus.mockResolvedValue(done);
  await tick();
  expect(completed).toHaveBeenCalledTimes(1);
  expect(latest.busy).toBe(false);
  expect(api.runSecurityLifecycleCaseAutomation).toHaveBeenCalledTimes(1);
});
it("a rejected dispatch does not pretend a background request started", async () => {
  await mount(); api.runSecurityLifecycleCaseAutomation.mockResolvedValue({ status: "unavailable", reason: "disabled" });
  await start();
  expect(latest.busy).toBe(false);
  expect(latest.error).toBe(true);
  expect(completed).not.toHaveBeenCalled();
});
it("polling stops after unmount without dispatching or invoking completion", async () => {
  api.getSecurityLifecycleAutomationStatus.mockResolvedValue(running);
  await mount(); await act(async () => root.unmount());
  const count = api.getSecurityLifecycleAutomationStatus.mock.calls.length;
  await tick();
  expect(api.getSecurityLifecycleAutomationStatus).toHaveBeenCalledTimes(count);
  expect(completed).not.toHaveBeenCalled();
});
