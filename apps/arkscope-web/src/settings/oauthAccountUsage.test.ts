/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  OAuthAccountSnapshot,
  OAuthAccountSyncView,
  ProviderCredential,
} from "../api";
import {
  createSettingsReadCache,
  oauthAccountUsageKey,
  type SettingsReadCache,
} from "./settingsReadCache";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

const CREDENTIAL_ID = "local:7";

type Deferred<T> = {
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (error: unknown) => void;
};

function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

function snapshot(
  usedPercent: number,
  credentialId = CREDENTIAL_ID,
): OAuthAccountSnapshot {
  return {
    credential_id: credentialId,
    provider: "openai",
    auth_mode: "chatgpt_oauth",
    account_fingerprint: "f".repeat(64),
    source: "codex_app_server",
    schema_version: 1,
    observed_at: `2026-08-11T00:${String(usedPercent).padStart(2, "0")}:00+00:00`,
    status: "available",
    payload: {
      rate_limits: {
        limit_id: "plus",
        limit_name: "Plus",
        plan_type: "plus",
        primary: {
          used_percent: usedPercent,
          window_duration_minutes: 300,
          resets_at: 1_786_190_400,
        },
        secondary: null,
        rate_limit_reached_type: null,
        credits: null,
        individual_limit: null,
        spend_control_reached: null,
        status: "allowed",
        overage_status: "rejected",
        overage_resets_at: null,
        overage_disabled_reason: "out_of_credits",
      },
      rate_limits_by_limit_id: {},
      reset_credits_available: null,
      usage_summary: {
        lifetime_tokens: null,
        peak_daily_tokens: null,
        longest_running_turn_seconds: null,
        current_streak_days: null,
        longest_streak_days: null,
      },
      daily_usage_buckets: [],
    },
    updated_at: "2026-08-11T00:00:00+00:00",
  };
}

function view(
  accountSnapshot: OAuthAccountSnapshot | null,
  syncStatus: OAuthAccountSyncView["sync_status"] = "not_requested",
  syncErrorCode: string | null = null,
): OAuthAccountSyncView {
  return {
    credential_id: CREDENTIAL_ID,
    snapshot: accountSnapshot,
    sync_status: syncStatus,
    sync_error_code: syncErrorCode,
  };
}

function activeCredential(): Pick<ProviderCredential, "id" | "auth_type"> {
  return { id: CREDENTIAL_ID, auth_type: "chatgpt_oauth" };
}

async function reducerModule() {
  const path = "./oauthAccountUsageReducer";
  return import(/* @vite-ignore */ path);
}

async function hookModule() {
  const path = "./useOAuthAccountUsage";
  return import(/* @vite-ignore */ path);
}

async function settle(): Promise<void> {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

type HookHarness = {
  current: () => any;
  unmount: () => void;
};

async function renderUsageHook({
  cache = createSettingsReadCache(),
  readAccountView = vi.fn(async () => view(null)),
  syncAccountView = vi.fn(async () => view(snapshot(20), "succeeded")),
  retryDelayMs = 1_000,
}: {
  cache?: SettingsReadCache;
  readAccountView?: (credentialId: string) => Promise<OAuthAccountSyncView>;
  syncAccountView?: (credentialId: string) => Promise<OAuthAccountSyncView>;
  retryDelayMs?: number;
} = {}): Promise<HookHarness> {
  const { useOAuthAccountUsage } = await hookModule();
  const host = document.createElement("div");
  document.body.append(host);
  const root = createRoot(host);
  let latest: any = null;

  function Harness() {
    latest = useOAuthAccountUsage({
      credentials: [activeCredential()],
      settingsReadCache: cache,
      readAccountView,
      syncAccountView,
      retryDelayMs,
    });
    return React.createElement("div", { ref: latest.sectionRef });
  }

  await act(async () => {
    root.render(React.createElement(Harness));
  });
  await settle();

  return {
    current: () => latest,
    unmount: () => {
      act(() => root.unmount());
      host.remove();
    },
  };
}

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  document.body.replaceChildren();
});

describe("OAuth account usage reducer", () => {
  it("success snapshot replaces the previous observation", async () => {
    const { EMPTY_OAUTH_ACCOUNT_USAGE_STATE, reduceOAuthAccountUsage } = await reducerModule();
    const first = snapshot(18);
    const second = snapshot(21);
    const seeded = reduceOAuthAccountUsage(EMPTY_OAUTH_ACCOUNT_USAGE_STATE, {
      type: "read_succeeded",
      snapshot: first,
    });

    const result = reduceOAuthAccountUsage(seeded, {
      type: "sync_succeeded",
      snapshot: second,
    });

    expect(result.snapshot).toEqual(second);
    expect(result.syncSend).toEqual({ status: "idle", errorCode: null });
    expect(result.backendSync).toEqual({ errorCode: null });
  });

  it("decoded failure with snapshot adopts the authoritative snapshot", async () => {
    const { EMPTY_OAUTH_ACCOUNT_USAGE_STATE, reduceOAuthAccountUsage } = await reducerModule();
    const prior = reduceOAuthAccountUsage(EMPTY_OAUTH_ACCOUNT_USAGE_STATE, {
      type: "read_succeeded",
      snapshot: snapshot(18),
    });

    const result = reduceOAuthAccountUsage(prior, {
      type: "sync_failed",
      snapshot: snapshot(22),
      errorCode: "version_incompatible",
      credentialChanged: false,
    });

    expect(result.snapshot?.payload.rate_limits.primary?.used_percent).toBe(22);
    expect(result.backendSync.errorCode).toBe("version_incompatible");
  });

  it("decoded failure without snapshot retains the prior observation", async () => {
    const { EMPTY_OAUTH_ACCOUNT_USAGE_STATE, reduceOAuthAccountUsage } = await reducerModule();
    const retained = snapshot(18);
    const prior = reduceOAuthAccountUsage(EMPTY_OAUTH_ACCOUNT_USAGE_STATE, {
      type: "read_succeeded",
      snapshot: retained,
    });

    const result = reduceOAuthAccountUsage(prior, {
      type: "sync_failed",
      snapshot: null,
      errorCode: "adapter_unavailable",
      credentialChanged: false,
    });

    expect(result.snapshot).toEqual(retained);
    expect(result.backendSync.errorCode).toBe("adapter_unavailable");
  });

  it("credential change clears the observation", async () => {
    const { EMPTY_OAUTH_ACCOUNT_USAGE_STATE, reduceOAuthAccountUsage } = await reducerModule();
    const prior = reduceOAuthAccountUsage(EMPTY_OAUTH_ACCOUNT_USAGE_STATE, {
      type: "read_succeeded",
      snapshot: snapshot(18),
    });

    const result = reduceOAuthAccountUsage(prior, { type: "credential_changed" });

    expect(result).toEqual(EMPTY_OAUTH_ACCOUNT_USAGE_STATE);
  });

  it("read errors and sync errors never clear each other", async () => {
    const { EMPTY_OAUTH_ACCOUNT_USAGE_STATE, reduceOAuthAccountUsage } = await reducerModule();
    const syncFailed = reduceOAuthAccountUsage(EMPTY_OAUTH_ACCOUNT_USAGE_STATE, {
      type: "sync_failed",
      snapshot: null,
      errorCode: "version_incompatible",
      credentialChanged: false,
    });
    const bothFailed = reduceOAuthAccountUsage(syncFailed, {
      type: "read_failed",
      errorCode: "cached_read_failed",
    });
    const readRecovered = reduceOAuthAccountUsage(bothFailed, {
      type: "read_succeeded",
      snapshot: snapshot(19),
    });
    const nextSync = reduceOAuthAccountUsage(readRecovered, { type: "sync_started" });
    const readFailedAgain = reduceOAuthAccountUsage(nextSync, {
      type: "read_failed",
      errorCode: "cached_read_failed",
    });
    const decodedFailure = reduceOAuthAccountUsage(readFailedAgain, {
      type: "sync_failed",
      snapshot: snapshot(20),
      errorCode: "provider_request_rejected",
      credentialChanged: false,
    });
    const syncRecovered = reduceOAuthAccountUsage(readFailedAgain, {
      type: "sync_succeeded",
      snapshot: snapshot(21),
    });

    expect(bothFailed.cachedRead.errorCode).toBe("cached_read_failed");
    expect(bothFailed.backendSync.errorCode).toBe("version_incompatible");
    expect(readRecovered.backendSync.errorCode).toBe("version_incompatible");
    expect(nextSync.cachedRead).toEqual({ status: "loaded", errorCode: null });
    expect(decodedFailure.cachedRead).toEqual({
      status: "failed",
      errorCode: "cached_read_failed",
    });
    expect(syncRecovered.cachedRead).toEqual({
      status: "failed",
      errorCode: "cached_read_failed",
    });
  });

  it("transport failure stays distinct from decoded backend failure", async () => {
    const { EMPTY_OAUTH_ACCOUNT_USAGE_STATE, reduceOAuthAccountUsage } = await reducerModule();
    const sending = reduceOAuthAccountUsage(EMPTY_OAUTH_ACCOUNT_USAGE_STATE, {
      type: "sync_started",
    });
    const transport = reduceOAuthAccountUsage(sending, {
      type: "sync_transport_failed",
      errorCode: "sync_transport_failed",
    });
    const decoded = reduceOAuthAccountUsage(sending, {
      type: "sync_failed",
      snapshot: null,
      errorCode: "provider_request_rejected",
      credentialChanged: false,
    });

    expect(transport.syncSend).toEqual({
      status: "transport_failed",
      errorCode: "sync_transport_failed",
    });
    expect(transport.backendSync.errorCode).toBeNull();
    expect(decoded.syncSend).toEqual({ status: "idle", errorCode: null });
    expect(decoded.backendSync.errorCode).toBe("provider_request_rejected");
  });
});

describe("useOAuthAccountUsage ownership", () => {
  it("credential change invalidates the cache entry and focus cannot resurrect it", async () => {
    const cache = createSettingsReadCache();
    cache.replace(oauthAccountUsageKey(CREDENTIAL_ID), snapshot(18));
    const readAccountView = vi.fn(async () => view(null));
    const syncAccountView = vi.fn(async () =>
      view(null, "failed", "credential_changed_during_sync"));
    const harness = await renderUsageHook({ cache, readAccountView, syncAccountView });

    expect(harness.current().states[CREDENTIAL_ID].snapshot).not.toBeNull();
    await act(async () => {
      await harness.current().syncAccountUsage(CREDENTIAL_ID);
    });
    expect(cache.inspect(oauthAccountUsageKey(CREDENTIAL_ID))).toEqual({ status: "missing" });
    expect(harness.current().states[CREDENTIAL_ID].snapshot).toBeNull();

    await act(async () => {
      window.dispatchEvent(new Event("focus"));
    });
    await settle();
    expect(readAccountView).toHaveBeenCalledOnce();
    expect(harness.current().states[CREDENTIAL_ID].snapshot).toBeNull();
    harness.unmount();
  });

  it("a read completion from before the last mutation is discarded", async () => {
    const cache = createSettingsReadCache();
    const pending = deferred<OAuthAccountSyncView>();
    const harness = await renderUsageHook({
      cache,
      readAccountView: vi.fn(() => pending.promise),
    });

    act(() => harness.current().invalidateAccountUsage(CREDENTIAL_ID));
    await act(async () => pending.resolve(view(snapshot(18))));
    await settle();

    expect(cache.inspect(oauthAccountUsageKey(CREDENTIAL_ID))).toEqual({ status: "missing" });
    expect(harness.current().states[CREDENTIAL_ID]).toBeUndefined();
    harness.unmount();
  });

  it("the bounded retry arms once per consecutive failure episode", async () => {
    vi.useFakeTimers();
    const readAccountView = vi.fn()
      .mockRejectedValueOnce(new Error("first"))
      .mockRejectedValueOnce(new Error("retry"))
      .mockResolvedValueOnce(view(snapshot(19)))
      .mockRejectedValueOnce(new Error("next episode"))
      .mockRejectedValueOnce(new Error("next retry"));
    const harness = await renderUsageHook({ readAccountView, retryDelayMs: 10 });
    await settle();

    expect(readAccountView).toHaveBeenCalledTimes(1);
    await act(async () => vi.advanceTimersByTimeAsync(10));
    expect(readAccountView).toHaveBeenCalledTimes(2);
    await act(async () => vi.advanceTimersByTimeAsync(100));
    expect(readAccountView).toHaveBeenCalledTimes(2);

    await act(async () => harness.current().readAccountUsage(CREDENTIAL_ID, true));
    expect(harness.current().states[CREDENTIAL_ID].cachedRead.status).toBe("loaded");
    await act(async () => harness.current().readAccountUsage(CREDENTIAL_ID, true));
    await act(async () => vi.advanceTimersByTimeAsync(10));
    expect(readAccountView).toHaveBeenCalledTimes(5);
    await act(async () => vi.advanceTimersByTimeAsync(100));
    expect(readAccountView).toHaveBeenCalledTimes(5);
    harness.unmount();
  });

  it("mount focus and idle events never emit a provider post", async () => {
    const syncAccountView = vi.fn(async () => view(snapshot(20), "succeeded"));
    const requestIdleCallback = vi.fn();
    vi.stubGlobal("requestIdleCallback", requestIdleCallback);
    const harness = await renderUsageHook({ syncAccountView });

    await act(async () => {
      window.dispatchEvent(new Event("focus"));
      document.dispatchEvent(new Event("visibilitychange"));
    });
    await settle();

    expect(syncAccountView).not.toHaveBeenCalled();
    expect(requestIdleCallback).not.toHaveBeenCalled();
    harness.unmount();
  });

  it("every cache write stores a validated snapshot only", async () => {
    const cache = createSettingsReadCache();
    const first = snapshot(18);
    const second = snapshot(21);
    const harness = await renderUsageHook({
      cache,
      readAccountView: vi.fn(async () => view(first)),
      syncAccountView: vi.fn(async () => view(second, "succeeded")),
    });
    await settle();

    expect(cache.inspect(oauthAccountUsageKey(CREDENTIAL_ID))).toMatchObject({ value: first });
    expect(cache.inspect(oauthAccountUsageKey(CREDENTIAL_ID))).not.toMatchObject({
      value: { sync_status: expect.anything() },
    });

    await act(async () => harness.current().syncAccountUsage(CREDENTIAL_ID));
    expect(cache.inspect(oauthAccountUsageKey(CREDENTIAL_ID))).toMatchObject({ value: second });
    expect(cache.inspect(oauthAccountUsageKey(CREDENTIAL_ID))).not.toMatchObject({
      value: { sync_status: expect.anything() },
    });
    harness.unmount();
  });

  it("stale epoch completions are rejected", async () => {
    const cache = createSettingsReadCache();
    const pending = deferred<OAuthAccountSyncView>();
    const harness = await renderUsageHook({
      cache,
      syncAccountView: vi.fn(() => pending.promise),
    });

    let request!: Promise<void>;
    act(() => {
      request = harness.current().syncAccountUsage(CREDENTIAL_ID);
    });
    act(() => harness.current().invalidateAccountUsage(CREDENTIAL_ID));
    await act(async () => pending.resolve(view(snapshot(25), "succeeded")));
    await request;
    await settle();

    expect(cache.inspect(oauthAccountUsageKey(CREDENTIAL_ID))).toEqual({ status: "missing" });
    expect(harness.current().states[CREDENTIAL_ID]).toBeUndefined();
    harness.unmount();
  });
});
