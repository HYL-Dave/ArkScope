/** @vitest-environment jsdom */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { afterEach, expect, it, vi } from "vitest";
import * as api from "../api";
import { webPreflightFixture, webRunFixture } from "./webFixtures";

const fixture = JSON.parse(readFileSync(resolve(import.meta.dirname, "../../../../tests/fixtures/lifecycle_current_v1.json"), "utf8"));
afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers(); vi.unstubAllGlobals(); });
function response(value: unknown) {
  const fetch = vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify(value))));
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

it("validates Web run shape at the actual read boundary and never dispatches on read", async () => {
  const fetch = response(webRunFixture);
  expect(await api.getLifecycleWebRun("run-1")).toEqual(webRunFixture);
  expect(fetch.mock.calls[0][1]?.method ?? "GET").toBe("GET");
  response({ ...webRunFixture, finding: { ...webRunFixture.finding, citations: undefined } });
  await expect(api.getLifecycleWebRun("run-1")).rejects.toThrow("lifecycle_web_payload_invalid");
});
it("binds Web reads and cancellation receipts to the exact requested run or case", async () => {
  response(webRunFixture);
  await expect(api.getLifecycleWebRun("different-run")).rejects.toThrow("lifecycle_current_payload_invalid");
  await expect(api.latestLifecycleWebRun("different-case")).rejects.toThrow("lifecycle_current_payload_invalid");
  await expect(api.cancelLifecycleWebRun("different-run")).rejects.toThrow("lifecycle_current_payload_invalid");
  response(null);
  expect(await api.latestLifecycleWebRun("case-1")).toBeNull();
  await expect(api.getLifecycleWebRun("run-1")).rejects.toThrow();
});
it("binds the launch preview to its exact case and public question", async () => {
  response(webPreflightFixture);
  expect(await api.getLifecycleWebPreflight("case-1", "listing_status")).toEqual(webPreflightFixture);
  await expect(api.getLifecycleWebPreflight("different-case", "listing_status")).rejects.toThrow();
  await expect(api.getLifecycleWebPreflight("case-1", "symbol_continuation")).rejects.toThrow();
});
it("validates an explicit Web start receipt without retrying malformed success", async () => {
  const fetch = response({ run_id: "run-1", created: "true" });
  const body = { question: "listing_status" as const, preflight_sha256: "a".repeat(64), request_key: "one-request" };
  await expect(api.startLifecycleWebRun("case-1", body)).rejects.toThrow("lifecycle_web_payload_invalid");
  expect(fetch).toHaveBeenCalledOnce();
  expect(fetch.mock.calls[0][1]?.method).toBe("POST");
  expect(JSON.parse(fetch.mock.calls[0][1]?.body)).toEqual(body);
});
it("checks the exact Web confirmation receipt and never turns a rejection into another execution", async () => {
  for (const change of [{ case_id: "other" }, { packet_sha256: "b".repeat(64) }, { source_ticker: "OTHER" }, { execute_on: "2026-09-07" }]) {
    const fetch = response({ ...fixture.confirmation, ...change });
    await expect(api.confirmLifecycleWebReview("run-1", fixture.packet)).rejects.toThrow("lifecycle_current_payload_invalid");
    expect(fetch).toHaveBeenCalledOnce();
  }
  const fetch = response(fixture.confirmation);
  expect(await api.confirmLifecycleWebReview("run-1", fixture.packet)).toEqual(fixture.confirmation);
  expect(JSON.parse(fetch.mock.calls[0][1]?.body)).toEqual({ packet_sha256: fixture.packet.packet_sha256,
    action: fixture.packet.action, ...fixture.packet.options });
});

it("acknowledges only the validated source gaps shown with the confirmed packet", async () => {
  const packet = { ...fixture.packet, source_gaps: [{ url: "https://news.example.com/notice", reason: "source_unavailable" }] };
  const fetch = response(fixture.confirmation);
  await api.confirmLifecycleWebReview("run-1", packet);
  expect(fetch).toHaveBeenCalledOnce();
  expect(JSON.parse(fetch.mock.calls[0][1]?.body)).toEqual({ packet_sha256: packet.packet_sha256,
    action: packet.action, ...packet.options, acknowledge_source_gaps: true });
});

const currentDetail = { version: 1, as_of: fixture.attention.as_of, item: fixture.attention.items[0], web_runs: [] };
it.each([
  { name: "current detail", call: () => api.getCurrentLifecycleReview(currentDetail.item.review_id), value: currentDetail },
  { name: "latest result", call: () => api.latestLifecycleWebRun("case-1"), value: webRunFixture },
  { name: "run result", call: () => api.getLifecycleWebRun("run-1"), value: webRunFixture },
  { name: "cancel receipt", call: () => api.cancelLifecycleWebRun("run-1"), value: webRunFixture },
  { name: "review packet", call: () => api.getLifecycleWebReview("run-1"), value: fixture.packet },
  { name: "confirm receipt", call: () => api.confirmLifecycleWebReview("run-1", fixture.packet), value: fixture.confirmation },
])("gives retained-source validation its own receipt budget: $name", async ({ call, value }) => {
  const timer = vi.spyOn(window, "setTimeout");
  const fetch = response(value);
  await call();
  expect(timer.mock.calls.map((row) => row[1])).toEqual([180_000]);
  expect(fetch).toHaveBeenCalledOnce();
});

it("accepts a slow verified local result without retrying or starting another investigation", async () => {
  vi.useFakeTimers();
  const fetch = vi.fn((_path: string, options: RequestInit) => new Promise<Response>((resolve, reject) => {
    window.setTimeout(() => resolve(new Response(JSON.stringify(webRunFixture))), 80_000);
    options.signal?.addEventListener("abort", () => reject(Object.assign(new Error("aborted"), { name: "AbortError" })));
  }));
  vi.stubGlobal("fetch", fetch);
  const result = api.getLifecycleWebRun("run-1").then((value) => ({ value }), (error) => ({ error }));
  await vi.advanceTimersByTimeAsync(80_000);
  expect(await result).toEqual({ value: webRunFixture });
  expect(fetch).toHaveBeenCalledOnce();
  expect(fetch.mock.calls[0][1].method ?? "GET").toBe("GET");
  expect(fetch.mock.calls[0][1].signal?.aborted).toBe(false);
});

it("still bounds a stalled receipt read and never retries it", async () => {
  vi.useFakeTimers();
  const fetch = vi.fn((_path: string, options: RequestInit) => new Promise<Response>((_resolve, reject) => {
    options.signal?.addEventListener("abort", () => reject(Object.assign(new Error("aborted"), { name: "AbortError" })));
  }));
  vi.stubGlobal("fetch", fetch);
  let outcome: unknown;
  void api.getLifecycleWebRun("run-1").then((value) => { outcome = value; }, (error) => { outcome = error; });
  await vi.advanceTimersByTimeAsync(179_999);
  expect(outcome).toBeUndefined();
  await vi.advanceTimersByTimeAsync(1);
  expect(outcome).toBeInstanceOf(Error);
  expect(String(outcome)).toContain("timed out after 180s");
  expect(fetch).toHaveBeenCalledOnce();
  expect(fetch.mock.calls[0][1].signal?.aborted).toBe(true);
});

it.each(["preflight", "start"])("does not increase the unrelated dispatch/default request budget: %s", async (operation) => {
  const timer = vi.spyOn(window, "setTimeout");
  const fetch = response(operation === "preflight" ? webPreflightFixture : { run_id: "run-1", created: true });
  if (operation === "preflight") await api.getLifecycleWebPreflight("case-1", "listing_status");
  else await api.startLifecycleWebRun("case-1", { question: "listing_status", preflight_sha256: "a".repeat(64), request_key: "single-request" });
  expect(timer.mock.calls.map((row) => row[1])).toEqual([15_000]);
  expect(fetch).toHaveBeenCalledOnce();
});
