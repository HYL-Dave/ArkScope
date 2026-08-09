export const SETTINGS_READ_CACHE_MAX_ENTRIES = 32;
export const SETTINGS_READ_CACHE_MAX_ENTRY_BYTES = 512 * 1024;
export const SETTINGS_READ_CACHE_MAX_TOTAL_BYTES = 4 * 1024 * 1024;

type FixedSettingsReadKey =
  | "model_catalog"
  | "data_schedule"
  | "provider_health"
  | "provider_config"
  | "sa_extension_health"
  | "market_data_status"
  | "news_status"
  | "macro_status"
  | "macro_snapshot";

export type SettingsReadKey =
  | FixedSettingsReadKey
  | `oauth_account_usage:${string}`
  | `trading_day_coverage:15min:${number}`;

export type SettingsReadInspection<T> =
  | { status: "missing" }
  | {
      status: "fresh" | "stale";
      value: T;
      receivedAt: number;
    };

export type SettingsReadOutcome<T> =
  | {
      status: "success";
      source: "cache" | "loader";
      retained: boolean;
      value: T;
    }
  | {
      status: "discarded";
      source: "loader";
      retained: false;
      value: T;
    }
  | {
      status: "error";
      error: unknown;
    };

export interface SettingsReadPolicy {
  freshMs: number;
  hardRetentionMs: number;
  idle: boolean;
}

type RetainedEntry = {
  value: unknown;
  receivedAt: number;
  bytes: number;
  lastAccess: number;
};

type InFlight = {
  generation: number;
  promise: Promise<SettingsReadOutcome<unknown>>;
};

const SECOND = 1_000;
const MINUTE = 60 * SECOND;
const COVERAGE_PREFIX = "trading_day_coverage:15min:";
const ACCOUNT_PREFIX = "oauth_account_usage:";
const COVERAGE_LOOKBACKS = [10, 15, 30, 60] as const;

const FIXED_POLICIES: Readonly<Record<FixedSettingsReadKey, SettingsReadPolicy>> = {
  model_catalog: { freshMs: 60 * SECOND, hardRetentionMs: 15 * MINUTE, idle: true },
  data_schedule: { freshMs: 30 * SECOND, hardRetentionMs: 5 * MINUTE, idle: true },
  provider_health: { freshMs: 30 * SECOND, hardRetentionMs: 15 * MINUTE, idle: true },
  provider_config: { freshMs: 60 * SECOND, hardRetentionMs: 15 * MINUTE, idle: true },
  sa_extension_health: { freshMs: 5 * MINUTE, hardRetentionMs: 30 * MINUTE, idle: false },
  market_data_status: { freshMs: 60 * SECOND, hardRetentionMs: 15 * MINUTE, idle: true },
  news_status: { freshMs: 60 * SECOND, hardRetentionMs: 15 * MINUTE, idle: true },
  macro_status: { freshMs: 60 * SECOND, hardRetentionMs: 15 * MINUTE, idle: true },
  macro_snapshot: { freshMs: 60 * SECOND, hardRetentionMs: 15 * MINUTE, idle: true },
};

const DATA_SYNC_FIXED_KEYS: readonly FixedSettingsReadKey[] = [
  "data_schedule",
  "provider_health",
  "provider_config",
  "sa_extension_health",
  "market_data_status",
  "news_status",
  "macro_status",
  "macro_snapshot",
];

const NEWS_SOURCES = new Set(["polygon_news", "finnhub_news", "ibkr_news"]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function hasRunningScheduleSource(value: unknown): boolean {
  if (!isRecord(value)) return false;
  const sourceMap = isRecord(value.sources) ? value.sources : value;
  return Object.values(sourceMap).some((candidate) =>
    isRecord(candidate) && candidate.running === true,
  );
}

function requireLocalCredentialId(localCredentialId: string): string {
  const value = localCredentialId.trim();
  const storedLocalId = /^local:[1-9]\d*$/.test(value);
  if (
    !value
    || value.length > 256
    || /[\u0000-\u001f\u007f]/.test(value)
    || (value.includes(":") && !storedLocalId)
  ) {
    throw new Error("invalid local credential id");
  }
  return value;
}

export function oauthAccountUsageKey(
  localCredentialId: string,
): `oauth_account_usage:${string}` {
  return `${ACCOUNT_PREFIX}${requireLocalCredentialId(localCredentialId)}`;
}

export function tradingDayCoverageKey(
  lookback: number,
): `trading_day_coverage:15min:${number}` {
  if (!Number.isSafeInteger(lookback) || lookback <= 0) {
    throw new Error("invalid trading-day coverage lookback");
  }
  return `${COVERAGE_PREFIX}${lookback}`;
}

function assertSettingsReadKey(key: string): asserts key is SettingsReadKey {
  if (Object.hasOwn(FIXED_POLICIES, key)) return;
  if (key.startsWith(ACCOUNT_PREFIX)) {
    requireLocalCredentialId(key.slice(ACCOUNT_PREFIX.length));
    return;
  }
  if (key.startsWith(COVERAGE_PREFIX)) {
    const raw = key.slice(COVERAGE_PREFIX.length);
    if (/^[1-9]\d*$/.test(raw) && Number.isSafeInteger(Number(raw))) return;
  }
  throw new Error(`unknown Settings read resource: ${key}`);
}

export function settingsReadPolicy(key: SettingsReadKey, value?: unknown): SettingsReadPolicy {
  assertSettingsReadKey(key);
  if (key.startsWith(ACCOUNT_PREFIX)) {
    return { freshMs: 5 * MINUTE, hardRetentionMs: 15 * MINUTE, idle: true };
  }
  if (key.startsWith(COVERAGE_PREFIX)) {
    return { freshMs: 5 * MINUTE, hardRetentionMs: 30 * MINUTE, idle: key === tradingDayCoverageKey(10) };
  }
  if (key === "data_schedule") {
    return {
      ...FIXED_POLICIES.data_schedule,
      freshMs: hasRunningScheduleSource(value) ? 5 * SECOND : 30 * SECOND,
    };
  }
  return FIXED_POLICIES[key as FixedSettingsReadKey];
}

function serializedByteSize(value: unknown): number | null {
  try {
    const serialized = JSON.stringify(value, (_key, candidate: unknown) => {
      if (
        candidate instanceof Error
        || candidate instanceof Promise
        || candidate === undefined
        || typeof candidate === "function"
        || typeof candidate === "symbol"
        || typeof candidate === "bigint"
      ) {
        throw new TypeError("value is not cache-serializable");
      }
      return candidate;
    });
    if (serialized === undefined) return null;
    return new TextEncoder().encode(serialized).byteLength;
  } catch {
    return null;
  }
}

export interface SettingsReadCache {
  inspect<T>(key: SettingsReadKey, now?: number): SettingsReadInspection<T>;
  load<T>(
    key: SettingsReadKey,
    loader: () => Promise<T>,
    options?: { force?: boolean },
  ): Promise<SettingsReadOutcome<T>>;
  replace<T>(key: SettingsReadKey, value: T, now?: number): SettingsReadOutcome<T>;
  invalidate(key: SettingsReadKey): void;
  invalidateCredentialAccount(localCredentialId: string): void;
  invalidateDataSource(source: string): void;
  invalidateAllDataSyncReads(): void;
  clear(): void;
}

class MemorySettingsReadCache implements SettingsReadCache {
  private readonly clock: () => number;
  private readonly generations = new Map<SettingsReadKey, number>();
  private readonly retained = new Map<SettingsReadKey, RetainedEntry>();
  private readonly inFlight = new Map<SettingsReadKey, InFlight>();
  private accessSequence = 0;
  private retainedBytes = 0;

  constructor(clock: () => number) {
    this.clock = clock;
  }

  inspect<T>(key: SettingsReadKey, now = this.clock()): SettingsReadInspection<T> {
    assertSettingsReadKey(key);
    const entry = this.retained.get(key);
    if (!entry) return { status: "missing" };
    const policy = settingsReadPolicy(key, entry.value);
    const age = Math.max(0, now - entry.receivedAt);
    if (age > policy.hardRetentionMs) {
      this.removeRetained(key);
      return { status: "missing" };
    }
    entry.lastAccess = this.nextAccess();
    return {
      status: age <= policy.freshMs ? "fresh" : "stale",
      value: entry.value as T,
      receivedAt: entry.receivedAt,
    };
  }

  load<T>(
    key: SettingsReadKey,
    loader: () => Promise<T>,
    options: { force?: boolean } = {},
  ): Promise<SettingsReadOutcome<T>> {
    assertSettingsReadKey(key);
    const inspected = this.inspect<T>(key);
    if (!options.force && inspected.status === "fresh") {
      return Promise.resolve({
        status: "success",
        source: "cache",
        retained: true,
        value: inspected.value,
      });
    }
    const generation = this.generation(key);
    const existing = this.inFlight.get(key);
    if (existing?.generation === generation) {
      return existing.promise as Promise<SettingsReadOutcome<T>>;
    }

    let launched: Promise<T>;
    try {
      launched = loader();
    } catch (error) {
      return Promise.resolve({ status: "error", error });
    }

    const holder: InFlight = {
      generation,
      promise: Promise.resolve({ status: "error", error: new Error("uninitialized") }),
    };
    const promise = Promise.resolve(launched)
      .then<SettingsReadOutcome<T>>((value) => {
        if (this.generation(key) !== generation) {
          return { status: "discarded", source: "loader", retained: false, value };
        }
        return this.retainCurrentValue(key, value, this.clock());
      })
      .catch((error: unknown): SettingsReadOutcome<T> => ({ status: "error", error }))
      .finally(() => {
        if (this.inFlight.get(key) === holder) this.inFlight.delete(key);
      });
    holder.promise = promise as Promise<SettingsReadOutcome<unknown>>;
    this.inFlight.set(key, holder);
    return promise;
  }

  replace<T>(key: SettingsReadKey, value: T, now = this.clock()): SettingsReadOutcome<T> {
    assertSettingsReadKey(key);
    return this.retainCurrentValue(key, value, now);
  }

  invalidate(key: SettingsReadKey): void {
    assertSettingsReadKey(key);
    this.generations.set(key, this.generation(key) + 1);
    this.removeRetained(key);
    this.inFlight.delete(key);
  }

  invalidateCredentialAccount(localCredentialId: string): void {
    this.invalidate(oauthAccountUsageKey(localCredentialId));
  }

  invalidateDataSource(source: string): void {
    if (source === "ibkr_prices") {
      this.invalidate("market_data_status");
      for (const key of this.coverageKeys()) this.invalidate(key);
      return;
    }
    if (NEWS_SOURCES.has(source)) {
      this.invalidate("news_status");
      this.invalidate("market_data_status");
      return;
    }
    this.invalidateAllDataSyncReads();
  }

  invalidateAllDataSyncReads(): void {
    for (const key of DATA_SYNC_FIXED_KEYS) this.invalidate(key);
    for (const key of this.coverageKeys()) this.invalidate(key);
  }

  clear(): void {
    const keys = this.knownKeys();
    for (const key of keys) {
      this.generations.set(key, this.generation(key) + 1);
    }
    this.retained.clear();
    this.inFlight.clear();
    this.retainedBytes = 0;
  }

  private generation(key: SettingsReadKey): number {
    return this.generations.get(key) ?? 0;
  }

  private retainCurrentValue<T>(
    key: SettingsReadKey,
    value: T,
    receivedAt: number,
  ): SettingsReadOutcome<T> {
    const bytes = serializedByteSize(value);
    if (bytes === null || bytes > SETTINGS_READ_CACHE_MAX_ENTRY_BYTES) {
      return { status: "success", source: "loader", retained: false, value };
    }
    this.removeHardExpired(receivedAt);
    this.removeRetained(key);
    const entry: RetainedEntry = {
      value,
      receivedAt,
      bytes,
      lastAccess: this.nextAccess(),
    };
    this.retained.set(key, entry);
    this.retainedBytes += bytes;
    this.evictToBounds();
    return {
      status: "success",
      source: "loader",
      retained: this.retained.get(key) === entry,
      value,
    };
  }

  private nextAccess(): number {
    this.accessSequence += 1;
    return this.accessSequence;
  }

  private removeHardExpired(now: number): void {
    for (const [key, entry] of this.retained) {
      if (Math.max(0, now - entry.receivedAt) > settingsReadPolicy(key, entry.value).hardRetentionMs) {
        this.removeRetained(key);
      }
    }
  }

  private removeRetained(key: SettingsReadKey): void {
    const entry = this.retained.get(key);
    if (!entry) return;
    this.retained.delete(key);
    this.retainedBytes -= entry.bytes;
  }

  private evictToBounds(): void {
    while (
      this.retained.size > SETTINGS_READ_CACHE_MAX_ENTRIES
      || this.retainedBytes > SETTINGS_READ_CACHE_MAX_TOTAL_BYTES
    ) {
      let oldestKey: SettingsReadKey | null = null;
      let oldestAccess = Number.POSITIVE_INFINITY;
      for (const [key, entry] of this.retained) {
        if (entry.lastAccess < oldestAccess) {
          oldestAccess = entry.lastAccess;
          oldestKey = key;
        }
      }
      if (oldestKey === null) break;
      this.removeRetained(oldestKey);
    }
  }

  private knownKeys(): Set<SettingsReadKey> {
    return new Set([
      ...this.generations.keys(),
      ...this.retained.keys(),
      ...this.inFlight.keys(),
    ]);
  }

  private coverageKeys(): Set<`trading_day_coverage:15min:${number}`> {
    const keys = new Set(COVERAGE_LOOKBACKS.map(tradingDayCoverageKey));
    for (const key of this.knownKeys()) {
      if (key.startsWith(COVERAGE_PREFIX)) {
        keys.add(key as `trading_day_coverage:15min:${number}`);
      }
    }
    return keys;
  }
}

export function createSettingsReadCache(
  options: { clock?: () => number } = {},
): SettingsReadCache {
  return new MemorySettingsReadCache(options.clock ?? Date.now);
}

export type SettingsIdleWarmupKey =
  | "model_catalog"
  | "data_schedule"
  | "provider_health"
  | "provider_config"
  | "market_data_status"
  | "trading_day_coverage:15min:10"
  | "news_status"
  | "macro_status"
  | "macro_snapshot";

const IDLE_WARMUP_KEYS: readonly SettingsIdleWarmupKey[] = [
  "model_catalog",
  "data_schedule",
  "provider_health",
  "provider_config",
  "market_data_status",
  "trading_day_coverage:15min:10",
  "news_status",
  "macro_status",
  "macro_snapshot",
];

export interface SettingsIdleScheduler {
  schedule(callback: () => void | Promise<void>): unknown;
  cancel(handle: unknown): void;
}

export interface SettingsIdleWarmupOptions {
  cache: SettingsReadCache;
  loaders: Partial<Record<SettingsIdleWarmupKey, () => Promise<unknown>>>;
  selectActiveOAuthLocalIds?: (modelCatalog: unknown) => readonly string[];
  loadOAuthAccountUsage?: (localCredentialId: string) => Promise<unknown>;
  scheduler?: SettingsIdleScheduler;
}

function defaultIdleScheduler(): SettingsIdleScheduler {
  if (typeof globalThis.requestIdleCallback === "function") {
    return {
      schedule: (callback) => globalThis.requestIdleCallback(() => { void callback(); }),
      cancel: (handle) => globalThis.cancelIdleCallback(Number(handle)),
    };
  }
  return {
    schedule: (callback) => globalThis.setTimeout(() => { void callback(); }, 0),
    cancel: (handle) => globalThis.clearTimeout(Number(handle)),
  };
}

export function scheduleSettingsIdleWarmup(options: SettingsIdleWarmupOptions): () => void {
  const scheduler = options.scheduler ?? defaultIdleScheduler();
  const allowed = new Set<string>(IDLE_WARMUP_KEYS);
  for (const key of Object.keys(options.loaders)) {
    if (!allowed.has(key)) throw new Error(`invalid idle warmup resource: ${key}`);
  }
  let cancelled = false;
  let started = false;

  const run = async () => {
    if (cancelled || started) return;
    started = true;
    const modelLoader = options.loaders.model_catalog;
    let modelCatalog: unknown = null;
    if (modelLoader) {
      const modelOutcome = await options.cache.load("model_catalog", modelLoader);
      if (modelOutcome.status === "success") {
        modelCatalog = modelOutcome.value;
      }
    }

    const staticLoads = IDLE_WARMUP_KEYS
      .filter((key) => key !== "model_catalog")
      .flatMap((key) => {
        const loader = options.loaders[key];
        return loader ? [options.cache.load(key, loader)] : [];
      });
    await Promise.allSettled(staticLoads);

    if (
      modelCatalog !== null
      && options.selectActiveOAuthLocalIds
      && options.loadOAuthAccountUsage
    ) {
      const ids = options.selectActiveOAuthLocalIds(modelCatalog);
      const uniqueIds = [...new Set(ids.map(requireLocalCredentialId))];
      await Promise.allSettled(uniqueIds.map((localCredentialId) =>
        options.cache.load(
          oauthAccountUsageKey(localCredentialId),
          () => options.loadOAuthAccountUsage!(localCredentialId),
        ),
      ));
    }
  };

  const handle = scheduler.schedule(run);
  return () => {
    if (started || cancelled) return;
    cancelled = true;
    scheduler.cancel(handle);
  };
}
