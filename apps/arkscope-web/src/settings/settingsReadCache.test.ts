import { describe, expect, it, vi } from "vitest";

const modulePath = "./settingsReadCache";

async function loadCacheModule() {
  return import(/* @vite-ignore */ modulePath);
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((accept, decline) => {
    resolve = accept;
    reject = decline;
  });
  return { promise, resolve, reject };
}

describe("Settings read cache", () => {
  it("returns_a_fresh_retained_value_without_invoking_its_loader", async () => {
    const { createSettingsReadCache } = await loadCacheModule();
    let now = 1_000;
    const cache = createSettingsReadCache({ clock: () => now });
    cache.replace("model_catalog", { models: ["model-a"] });
    const loader = vi.fn(async () => ({ models: ["model-b"] }));

    now += 59_000;
    const outcome = await cache.load("model_catalog", loader);

    expect(outcome).toEqual({
      status: "success",
      source: "cache",
      retained: true,
      value: { models: ["model-a"] },
    });
    expect(loader).not.toHaveBeenCalled();
  });

  it("renders_a_stale_retained_value_while_one_revalidation_runs", async () => {
    const { createSettingsReadCache } = await loadCacheModule();
    let now = 0;
    const cache = createSettingsReadCache({ clock: () => now });
    cache.replace("model_catalog", { version: "old" });
    now = 61_000;
    const pending = deferred<{ version: string }>();

    const loading = cache.load("model_catalog", () => pending.promise);

    expect(cache.inspect("model_catalog")).toMatchObject({
      status: "stale",
      value: { version: "old" },
    });
    pending.resolve({ version: "new" });
    await expect(loading).resolves.toMatchObject({
      status: "success",
      source: "loader",
      retained: true,
      value: { version: "new" },
    });
    expect(cache.inspect("model_catalog")).toMatchObject({
      status: "fresh",
      value: { version: "new" },
    });
  });

  it("shares_one_loader_across_visible_and_idle_callers", async () => {
    const { createSettingsReadCache } = await loadCacheModule();
    const cache = createSettingsReadCache();
    const pending = deferred<{ value: number }>();
    const loader = vi.fn(() => pending.promise);

    const visible = cache.load("provider_health", loader);
    const idle = cache.load("provider_health", loader);

    expect(visible).toBe(idle);
    expect(loader).toHaveBeenCalledOnce();
    pending.resolve({ value: 7 });
    await expect(Promise.all([visible, idle])).resolves.toEqual([
      { status: "success", source: "loader", retained: true, value: { value: 7 } },
      { status: "success", source: "loader", retained: true, value: { value: 7 } },
    ]);
  });

  it("discards_old_generation_completion_after_invalidation", async () => {
    const { createSettingsReadCache } = await loadCacheModule();
    const cache = createSettingsReadCache();
    const pending = deferred<{ generation: string }>();

    const oldLoad = cache.load("provider_config", () => pending.promise);
    cache.invalidate("provider_config");
    pending.resolve({ generation: "old" });

    await expect(oldLoad).resolves.toEqual({
      status: "discarded",
      source: "loader",
      retained: false,
      value: { generation: "old" },
    });
    expect(cache.inspect("provider_config")).toEqual({ status: "missing" });
  });

  it("preserves_stale_success_after_ordinary_revalidation_failure", async () => {
    const { createSettingsReadCache } = await loadCacheModule();
    let now = 0;
    const cache = createSettingsReadCache({ clock: () => now });
    cache.replace("news_status", { articles: 10 });
    now = 61_000;

    const outcome = await cache.load("news_status", async () => {
      throw new Error("offline");
    });

    expect(outcome.status).toBe("error");
    expect(cache.inspect("news_status")).toMatchObject({
      status: "stale",
      value: { articles: 10 },
    });
  });

  it("does_not_resurrect_invalidated_success_after_mutation_failure", async () => {
    const { createSettingsReadCache } = await loadCacheModule();
    const cache = createSettingsReadCache();
    cache.replace("data_schedule", { sources: [{ status: "idle" }] });
    cache.invalidate("data_schedule");

    const outcome = await cache.load("data_schedule", async () => {
      throw new Error("mutation failed");
    });

    expect(outcome.status).toBe("error");
    expect(cache.inspect("data_schedule")).toEqual({ status: "missing" });
  });

  it("evicts_hard_expired_success_before_render", async () => {
    const { createSettingsReadCache } = await loadCacheModule();
    let now = 0;
    const cache = createSettingsReadCache({ clock: () => now });
    cache.replace("model_catalog", { models: ["old"] });

    now = 15 * 60_000 + 1;

    expect(cache.inspect("model_catalog")).toEqual({ status: "missing" });
    expect(cache.inspect("model_catalog")).toEqual({ status: "missing" });
  });

  it("evicts_least_recently_used_entries_at_the_entry_cap", async () => {
    const { createSettingsReadCache, oauthAccountUsageKey } = await loadCacheModule();
    const cache = createSettingsReadCache();

    for (let index = 0; index < 32; index += 1) {
      cache.replace(oauthAccountUsageKey(`credential-${index}`), { index });
    }
    expect(cache.inspect(oauthAccountUsageKey("credential-0")).status).toBe("fresh");
    cache.replace(oauthAccountUsageKey("credential-32"), { index: 32 });

    expect(cache.inspect(oauthAccountUsageKey("credential-1"))).toEqual({ status: "missing" });
    expect(cache.inspect(oauthAccountUsageKey("credential-0"))).toMatchObject({ status: "fresh" });
    expect(cache.inspect(oauthAccountUsageKey("credential-32"))).toMatchObject({ status: "fresh" });
  });

  it("refuses_retention_above_the_per_entry_byte_cap", async () => {
    const { createSettingsReadCache } = await loadCacheModule();
    const cache = createSettingsReadCache();
    const value = { payload: "x".repeat(512 * 1024) };

    const outcome = cache.replace("macro_snapshot", value);

    expect(outcome).toEqual({ status: "success", source: "loader", retained: false, value });
    expect(cache.inspect("macro_snapshot")).toEqual({ status: "missing" });
  });

  it("evicts_least_recently_used_entries_at_the_total_byte_cap", async () => {
    const { createSettingsReadCache, oauthAccountUsageKey } = await loadCacheModule();
    const cache = createSettingsReadCache();
    const payload = "x".repeat(500_000);

    for (let index = 0; index < 9; index += 1) {
      cache.replace(oauthAccountUsageKey(`large-${index}`), { index, payload });
    }

    expect(cache.inspect(oauthAccountUsageKey("large-0"))).toEqual({ status: "missing" });
    expect(cache.inspect(oauthAccountUsageKey("large-8"))).toMatchObject({ status: "fresh" });
  });

  it("returns_but_does_not_retain_non_serializable_values", async () => {
    const { createSettingsReadCache } = await loadCacheModule();
    const cache = createSettingsReadCache();
    const value: { self?: unknown } = {};
    value.self = value;

    const outcome = cache.replace("macro_status", value);

    expect(outcome).toEqual({ status: "success", source: "loader", retained: false, value });
    expect(cache.inspect("macro_status")).toEqual({ status: "missing" });

    const nestedError = { diagnostic: new Error("not cache data") };
    expect(cache.replace("macro_status", nestedError)).toMatchObject({ retained: false });
    expect(cache.inspect("macro_status")).toEqual({ status: "missing" });

    const nestedPromise = { pending: Promise.resolve("not cache data") };
    expect(cache.replace("macro_status", nestedPromise)).toMatchObject({ retained: false });
    expect(cache.inspect("macro_status")).toEqual({ status: "missing" });
  });

  it("forces_manual_refresh_past_freshness_while_joining_single_flight", async () => {
    const { createSettingsReadCache } = await loadCacheModule();
    const cache = createSettingsReadCache();
    cache.replace("market_data_status", { revision: 1 });
    const pending = deferred<{ revision: number }>();
    const loader = vi.fn(() => pending.promise);

    const first = cache.load("market_data_status", loader, { force: true });
    const second = cache.load("market_data_status", loader, { force: true });

    expect(first).toBe(second);
    expect(loader).toHaveBeenCalledOnce();
    pending.resolve({ revision: 2 });
    await expect(first).resolves.toMatchObject({ value: { revision: 2 }, retained: true });
  });

  it("invalidates_only_one_local_credential_account_key", async () => {
    const { createSettingsReadCache, oauthAccountUsageKey } = await loadCacheModule();
    const cache = createSettingsReadCache();
    const first = oauthAccountUsageKey("credential-a");
    const second = oauthAccountUsageKey("credential-b");
    cache.replace(first, { account: "a" });
    cache.replace(second, { account: "b" });

    cache.invalidateCredentialAccount("credential-a");

    expect(cache.inspect(first)).toEqual({ status: "missing" });
    expect(cache.inspect(second)).toMatchObject({ status: "fresh", value: { account: "b" } });
  });

  it("maps_price_and_news_sources_to_exact_downstream_keys", async () => {
    const { createSettingsReadCache, tradingDayCoverageKey } = await loadCacheModule();
    const cache = createSettingsReadCache();
    const coverage10 = tradingDayCoverageKey(10);
    const coverage30 = tradingDayCoverageKey(30);
    cache.replace("market_data_status", { revision: 1 });
    cache.replace(coverage10, { lookback: 10 });
    cache.replace(coverage30, { lookback: 30 });
    cache.replace("news_status", { revision: 1 });
    cache.replace("macro_status", { revision: 1 });

    cache.invalidateDataSource("ibkr_prices");
    expect(cache.inspect("market_data_status")).toEqual({ status: "missing" });
    expect(cache.inspect(coverage10)).toEqual({ status: "missing" });
    expect(cache.inspect(coverage30)).toEqual({ status: "missing" });
    expect(cache.inspect("news_status")).toMatchObject({ status: "fresh" });

    cache.replace("market_data_status", { revision: 2 });
    cache.invalidateDataSource("polygon_news");
    expect(cache.inspect("market_data_status")).toEqual({ status: "missing" });
    expect(cache.inspect("news_status")).toEqual({ status: "missing" });
    expect(cache.inspect("macro_status")).toMatchObject({ status: "fresh" });
  });

  it("invalidates_all_data_sync_reads_for_an_unknown_source", async () => {
    const {
      createSettingsReadCache,
      oauthAccountUsageKey,
      tradingDayCoverageKey,
    } = await loadCacheModule();
    const cache = createSettingsReadCache();
    const accountKey = oauthAccountUsageKey("credential-a");
    const dataKeys = [
      "data_schedule",
      "provider_health",
      "provider_config",
      "sa_extension_health",
      "market_data_status",
      tradingDayCoverageKey(10),
      "news_status",
      "macro_status",
      "macro_snapshot",
    ];
    for (const key of dataKeys) cache.replace(key, { key });
    cache.replace("model_catalog", { models: [] });
    cache.replace(accountKey, { account: "a" });

    cache.invalidateDataSource("future_source_v9");

    for (const key of dataKeys) expect(cache.inspect(key)).toEqual({ status: "missing" });
    expect(cache.inspect("model_catalog")).toMatchObject({ status: "fresh" });
    expect(cache.inspect(accountKey)).toMatchObject({ status: "fresh" });
  });

  it("idle_warmup_calls_only_allowlisted_local_GETs_once", async () => {
    const { createSettingsReadCache, scheduleSettingsIdleWarmup } = await loadCacheModule();
    const cache = createSettingsReadCache();
    const calls: string[] = [];
    let scheduled: (() => Promise<void>) | null = null;
    const scheduler = {
      schedule(callback: () => Promise<void>) {
        scheduled = callback;
        return 17;
      },
      cancel: vi.fn(),
    };
    const keys = [
      "model_catalog",
      "data_schedule",
      "provider_health",
      "provider_config",
      "market_data_status",
      "trading_day_coverage:15min:10",
      "news_status",
      "macro_status",
      "macro_snapshot",
    ] as const;
    const loaders = Object.fromEntries(keys.map((key) => [
      key,
      async () => {
        calls.push(key);
        return key === "model_catalog" ? { credentials: [] } : { key };
      },
    ]));

    scheduleSettingsIdleWarmup({ cache, loaders, scheduler });
    await scheduled!();
    await scheduled!();

    expect(calls).toEqual(keys);
    expect(calls).not.toContain("sa_extension_health");
    expect(() => scheduleSettingsIdleWarmup({
      cache,
      loaders: { ...loaders, sa_extension_health: async () => ({}) },
      scheduler,
    })).toThrow(/idle warmup resource/i);
  });

  it("idle_warmup_primes_account_usage_only_from_validated_active_OAuth_local_ids", async () => {
    const {
      createSettingsReadCache,
      oauthAccountUsageKey,
      scheduleSettingsIdleWarmup,
    } = await loadCacheModule();
    const cache = createSettingsReadCache();
    const catalog = {
      credentials: [
        { id: "local-oauth", auth_mode: "chatgpt_oauth", active: true },
        { id: "local-api", auth_mode: "api_key", active: true },
      ],
    };
    let scheduled: (() => Promise<void>) | null = null;
    const accountLoader = vi.fn(async (localId: string) => ({ local_id: localId, used: 0.25 }));
    const selectActiveOAuthLocalIds = vi.fn((value: unknown) => {
      expect(value).toEqual(catalog);
      return ["local-oauth"];
    });

    scheduleSettingsIdleWarmup({
      cache,
      loaders: { model_catalog: async () => catalog },
      selectActiveOAuthLocalIds,
      loadOAuthAccountUsage: accountLoader,
      scheduler: {
        schedule(callback: () => Promise<void>) {
          scheduled = callback;
          return 1;
        },
        cancel: vi.fn(),
      },
    });
    await scheduled!();

    expect(selectActiveOAuthLocalIds).toHaveBeenCalledOnce();
    expect(accountLoader).toHaveBeenCalledOnce();
    expect(accountLoader).toHaveBeenCalledWith("local-oauth");
    expect(cache.inspect(oauthAccountUsageKey("local-oauth"))).toMatchObject({
      status: "fresh",
      value: { local_id: "local-oauth", used: 0.25 },
    });
    expect(cache.inspect(oauthAccountUsageKey("local-api"))).toEqual({ status: "missing" });

    const invalidatedCache = createSettingsReadCache();
    const pendingCatalog = deferred<typeof catalog>();
    const discardedAccountLoader = vi.fn(async () => ({ used: 0.5 }));
    let discardedRun: (() => Promise<void>) | null = null;
    scheduleSettingsIdleWarmup({
      cache: invalidatedCache,
      loaders: { model_catalog: () => pendingCatalog.promise },
      selectActiveOAuthLocalIds: () => ["stale-local-oauth"],
      loadOAuthAccountUsage: discardedAccountLoader,
      scheduler: {
        schedule(callback: () => Promise<void>) {
          discardedRun = callback;
          return 2;
        },
        cancel: vi.fn(),
      },
    });
    const running = discardedRun!();
    invalidatedCache.invalidate("model_catalog");
    pendingCatalog.resolve(catalog);
    await running;
    expect(discardedAccountLoader).not.toHaveBeenCalled();
  });
});
