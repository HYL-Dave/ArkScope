import {
  useCallback,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
  type RefObject,
} from "react";

import {
  getCredentialAccountUsage,
  syncCredentialAccountUsage,
  type OAuthAccountSnapshot,
  type OAuthAccountSyncView,
  type ProviderCredential,
} from "../api";
import {
  EMPTY_OAUTH_ACCOUNT_USAGE_STATE,
  reduceOAuthAccountUsage,
  type OAuthAccountUsageAction,
  type OAuthAccountUsageState,
} from "./oauthAccountUsageReducer";
import {
  oauthAccountUsageKey,
  type SettingsReadCache,
} from "./settingsReadCache";

const DEFAULT_READ_RETRY_MS = 1_000;
const DEFAULT_SYNC_COOLDOWN_MS = 10_000;
const FINGERPRINT_PATTERN = /^[a-f0-9]{64}$/;
const SNAPSHOT_SOURCES = new Set([
  "codex_app_server",
  "claude_rate_limit_event",
  "anthropic_oauth_probe",
]);

type OAuthCredentialIdentity = Pick<ProviderCredential, "id" | "auth_type">;
type AccountReader = (credentialId: string) => Promise<OAuthAccountSyncView>;
type AccountSyncer = (credentialId: string) => Promise<OAuthAccountSyncView>;

type StateEnvelope =
  | { credentialId: string; action: OAuthAccountUsageAction }
  | { credentialId: string; clear: true };

export type UseOAuthAccountUsageResult = {
  states: Record<string, OAuthAccountUsageState>;
  cooldownUntil: Record<string, number>;
  sectionRef: RefObject<HTMLDivElement>;
  readAccountUsage: (credentialId: string, force?: boolean) => Promise<void>;
  syncAccountUsage: (credentialId: string) => Promise<void>;
  invalidateAccountUsage: (credentialId: string) => void;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isRateLimitWindow(value: unknown): boolean {
  if (value === null) return true;
  if (!isRecord(value)) return false;
  const usedPercent = value.used_percent;
  const duration = value.window_duration_minutes;
  const resetsAt = value.resets_at;
  return (usedPercent === null
      || (typeof usedPercent === "number"
        && Number.isFinite(usedPercent)
        && usedPercent >= 0
        && usedPercent <= 100))
    && (duration === null
      || (typeof duration === "number" && Number.isInteger(duration) && duration >= 0))
    && (resetsAt === null
      || (typeof resetsAt === "number" && Number.isFinite(resetsAt) && resetsAt >= 0));
}

function isRateLimitStatus(value: unknown): boolean {
  return value === null
    || value === "allowed"
    || value === "allowed_warning"
    || value === "rejected";
}

function requireCredentialBoundSnapshot(
  credentialId: string,
  value: unknown,
): OAuthAccountSnapshot {
  if (!isRecord(value)) throw new Error("invalid OAuth account snapshot");
  const providerAuthPair = (value.provider === "openai" && value.auth_mode === "chatgpt_oauth")
    || (value.provider === "anthropic" && value.auth_mode === "claude_code_oauth");
  const providerSourcePair = (value.provider === "openai" && value.source === "codex_app_server")
    || (value.provider === "anthropic"
      && (value.source === "claude_rate_limit_event"
        || value.source === "anthropic_oauth_probe"));
  if (
    value.credential_id !== credentialId
    || !providerAuthPair
    || !providerSourcePair
    || typeof value.account_fingerprint !== "string"
    || !FINGERPRINT_PATTERN.test(value.account_fingerprint)
    || typeof value.source !== "string"
    || !SNAPSHOT_SOURCES.has(value.source)
    || value.schema_version !== 1
    || value.status !== "available"
    || typeof value.observed_at !== "string"
    || !Number.isFinite(Date.parse(value.observed_at))
    || typeof value.updated_at !== "string"
    || !Number.isFinite(Date.parse(value.updated_at))
    || !isRecord(value.payload)
    || !isRecord(value.payload.rate_limits)
  ) {
    throw new Error("invalid credential-bound OAuth account snapshot");
  }
  const limits = value.payload.rate_limits;
  if (
    !isRateLimitWindow(limits.primary)
    || !isRateLimitWindow(limits.secondary)
    || !isRateLimitStatus(limits.status)
    || !isRateLimitStatus(limits.overage_status)
  ) {
    throw new Error("invalid OAuth account rate-limit snapshot");
  }
  return value as unknown as OAuthAccountSnapshot;
}

function requireCredentialBoundView(
  credentialId: string,
  value: unknown,
): OAuthAccountSyncView {
  if (!isRecord(value) || value.credential_id !== credentialId) {
    throw new Error("credential-bound account response mismatch");
  }
  if (
    value.sync_status !== "not_requested"
    && value.sync_status !== "succeeded"
    && value.sync_status !== "failed"
    && value.sync_status !== "unsupported"
  ) {
    throw new Error("invalid OAuth account sync status");
  }
  if (value.sync_error_code !== null && typeof value.sync_error_code !== "string") {
    throw new Error("invalid OAuth account sync error");
  }
  if (value.snapshot !== null) requireCredentialBoundSnapshot(credentialId, value.snapshot);
  return value as unknown as OAuthAccountSyncView;
}

export async function loadValidatedOAuthAccountSnapshot(
  credentialId: string,
  reader: AccountReader = getCredentialAccountUsage,
): Promise<OAuthAccountSnapshot | null> {
  const view = requireCredentialBoundView(credentialId, await reader(credentialId));
  return view.snapshot === null
    ? null
    : requireCredentialBoundSnapshot(credentialId, view.snapshot);
}

function statesReducer(
  states: Record<string, OAuthAccountUsageState>,
  envelope: StateEnvelope,
): Record<string, OAuthAccountUsageState> {
  if ("clear" in envelope) {
    if (!(envelope.credentialId in states)) return states;
    const next = { ...states };
    delete next[envelope.credentialId];
    return next;
  }
  return {
    ...states,
    [envelope.credentialId]: reduceOAuthAccountUsage(
      states[envelope.credentialId] ?? EMPTY_OAUTH_ACCOUNT_USAGE_STATE,
      envelope.action,
    ),
  };
}

export function useOAuthAccountUsage({
  credentials,
  settingsReadCache,
  readAccountView = getCredentialAccountUsage,
  syncAccountView = syncCredentialAccountUsage,
  retryDelayMs = DEFAULT_READ_RETRY_MS,
  cooldownMs = DEFAULT_SYNC_COOLDOWN_MS,
}: {
  credentials: readonly OAuthCredentialIdentity[];
  settingsReadCache: SettingsReadCache;
  readAccountView?: AccountReader;
  syncAccountView?: AccountSyncer;
  retryDelayMs?: number;
  cooldownMs?: number;
}): UseOAuthAccountUsageResult {
  const [states, dispatch] = useReducer(statesReducer, {});
  const [cooldownUntil, setCooldownUntil] = useState<Record<string, number>>({});
  const sectionRef = useRef<HTMLDivElement>(null);
  const epochs = useRef(new Map<string, number>());
  const retryTimers = useRef(new Map<string, number>());
  const retryUsed = useRef(new Set<string>());
  const cooldownTimers = useRef(new Map<string, number>());
  const cooldownDeadlines = useRef(new Map<string, number>());
  const syncInFlight = useRef(new Map<string, Promise<void>>());
  const credentialIdentity = useRef(new Map<string, string>());
  const credentialsRef = useRef(credentials);
  const readRef = useRef<UseOAuthAccountUsageResult["readAccountUsage"] | null>(null);
  const [documentVisible, setDocumentVisible] = useState(
    () => typeof document === "undefined" || document.visibilityState !== "hidden",
  );
  const [sectionInViewport, setSectionInViewport] = useState(
    () => typeof window === "undefined" || typeof window.IntersectionObserver === "undefined",
  );

  credentialsRef.current = credentials;
  const credentialKey = useMemo(
    () => credentials
      .map((credential) => `${credential.id}\0${credential.auth_type}`)
      .sort()
      .join("\0"),
    [credentials],
  );

  const currentEpoch = useCallback((credentialId: string): number =>
    epochs.current.get(credentialId) ?? 0, []);

  const advanceEpoch = useCallback((credentialId: string): number => {
    const next = currentEpoch(credentialId) + 1;
    epochs.current.set(credentialId, next);
    return next;
  }, [currentEpoch]);

  const cancelRetry = useCallback((credentialId: string, resetEpisode: boolean) => {
    const timer = retryTimers.current.get(credentialId);
    if (timer !== undefined) {
      window.clearTimeout(timer);
      retryTimers.current.delete(credentialId);
    }
    if (resetEpisode) retryUsed.current.delete(credentialId);
  }, []);

  const clearCooldown = useCallback((credentialId: string) => {
    const timer = cooldownTimers.current.get(credentialId);
    if (timer !== undefined) {
      window.clearTimeout(timer);
      cooldownTimers.current.delete(credentialId);
    }
    cooldownDeadlines.current.delete(credentialId);
    setCooldownUntil((previous) => {
      if (!(credentialId in previous)) return previous;
      const next = { ...previous };
      delete next[credentialId];
      return next;
    });
  }, []);

  const invalidateAccountUsage = useCallback((credentialId: string) => {
    advanceEpoch(credentialId);
    settingsReadCache.invalidateCredentialAccount(credentialId);
    cancelRetry(credentialId, true);
    clearCooldown(credentialId);
    syncInFlight.current.delete(credentialId);
    dispatch({ credentialId, clear: true });
  }, [advanceEpoch, cancelRetry, clearCooldown, settingsReadCache]);

  const scheduleRetry = useCallback((credentialId: string, epoch: number) => {
    if (retryUsed.current.has(credentialId) || retryTimers.current.has(credentialId)) return;
    retryUsed.current.add(credentialId);
    const timer = window.setTimeout(() => {
      retryTimers.current.delete(credentialId);
      if (currentEpoch(credentialId) !== epoch) return;
      void readRef.current?.(credentialId, true);
    }, retryDelayMs);
    retryTimers.current.set(credentialId, timer);
  }, [currentEpoch, retryDelayMs]);

  const readAccountUsage = useCallback(async (credentialId: string, force = false) => {
    const epoch = currentEpoch(credentialId);
    const key = oauthAccountUsageKey(credentialId);
    const retained = settingsReadCache.inspect<OAuthAccountSnapshot | null>(key);
    if (retained.status !== "missing") {
      try {
        const snapshot = retained.value === null
          ? null
          : requireCredentialBoundSnapshot(credentialId, retained.value);
        dispatch({ credentialId, action: { type: "read_succeeded", snapshot } });
        if (retained.status === "fresh" && !force) {
          cancelRetry(credentialId, true);
          return;
        }
      } catch {
        settingsReadCache.invalidate(key);
      }
    }

    dispatch({ credentialId, action: { type: "read_started" } });
    const outcome = await settingsReadCache.load<OAuthAccountSnapshot | null>(
      key,
      () => loadValidatedOAuthAccountSnapshot(credentialId, readAccountView),
      { force },
    );
    if (currentEpoch(credentialId) !== epoch || outcome.status === "discarded") return;
    if (outcome.status === "success") {
      const snapshot = outcome.value === null
        ? null
        : requireCredentialBoundSnapshot(credentialId, outcome.value);
      cancelRetry(credentialId, true);
      dispatch({ credentialId, action: { type: "read_succeeded", snapshot } });
      return;
    }
    dispatch({
      credentialId,
      action: { type: "read_failed", errorCode: "cached_read_failed" },
    });
    scheduleRetry(credentialId, epoch);
  }, [cancelRetry, currentEpoch, readAccountView, scheduleRetry, settingsReadCache]);
  readRef.current = readAccountUsage;

  const syncAccountUsage = useCallback((credentialId: string): Promise<void> => {
    const now = Date.now();
    if ((cooldownDeadlines.current.get(credentialId) ?? 0) > now) return Promise.resolve();
    const existing = syncInFlight.current.get(credentialId);
    if (existing) return existing;

    const until = now + cooldownMs;
    cooldownDeadlines.current.set(credentialId, until);
    setCooldownUntil((previous) => ({ ...previous, [credentialId]: until }));
    const priorTimer = cooldownTimers.current.get(credentialId);
    if (priorTimer !== undefined) window.clearTimeout(priorTimer);
    const cooldownTimer = window.setTimeout(() => {
      cooldownTimers.current.delete(credentialId);
      cooldownDeadlines.current.delete(credentialId);
      setCooldownUntil((previous) => {
        const next = { ...previous };
        delete next[credentialId];
        return next;
      });
    }, cooldownMs);
    cooldownTimers.current.set(credentialId, cooldownTimer);

    const epoch = currentEpoch(credentialId);
    dispatch({ credentialId, action: { type: "sync_started" } });
    let request!: Promise<void>;
    request = (async () => {
      try {
        const view = requireCredentialBoundView(
          credentialId,
          await syncAccountView(credentialId),
        );
        if (currentEpoch(credentialId) !== epoch) return;

        if (view.sync_status === "succeeded" && view.snapshot !== null) {
          const snapshot = requireCredentialBoundSnapshot(credentialId, view.snapshot);
          settingsReadCache.invalidateCredentialAccount(credentialId);
          settingsReadCache.replace(oauthAccountUsageKey(credentialId), snapshot);
          dispatch({ credentialId, action: { type: "sync_succeeded", snapshot } });
          return;
        }

        const errorCode = view.sync_error_code ?? "sync_failed";
        const credentialChanged = errorCode === "credential_changed_during_sync";
        const snapshot = view.snapshot === null
          ? null
          : requireCredentialBoundSnapshot(credentialId, view.snapshot);
        if (credentialChanged) {
          advanceEpoch(credentialId);
          settingsReadCache.invalidateCredentialAccount(credentialId);
          cancelRetry(credentialId, true);
        } else if (snapshot !== null) {
          settingsReadCache.invalidateCredentialAccount(credentialId);
          settingsReadCache.replace(oauthAccountUsageKey(credentialId), snapshot);
        }
        dispatch({
          credentialId,
          action: {
            type: "sync_failed",
            snapshot,
            errorCode,
            credentialChanged,
          },
        });
      } catch {
        if (currentEpoch(credentialId) !== epoch) return;
        dispatch({
          credentialId,
          action: {
            type: "sync_transport_failed",
            errorCode: "sync_transport_failed",
          },
        });
      } finally {
        if (syncInFlight.current.get(credentialId) === request) {
          syncInFlight.current.delete(credentialId);
        }
      }
    })();
    syncInFlight.current.set(credentialId, request);
    return request;
  }, [
    advanceEpoch,
    cancelRetry,
    cooldownMs,
    currentEpoch,
    settingsReadCache,
    syncAccountView,
  ]);

  useEffect(() => {
    const next = new Map(credentials.map((credential) => [credential.id, credential.auth_type]));
    for (const [credentialId, authType] of credentialIdentity.current) {
      const nextAuthType = next.get(credentialId);
      if (nextAuthType === authType) continue;
      advanceEpoch(credentialId);
      cancelRetry(credentialId, true);
      clearCooldown(credentialId);
      syncInFlight.current.delete(credentialId);
      dispatch({ credentialId, clear: true });
      if (nextAuthType !== undefined) {
        settingsReadCache.invalidateCredentialAccount(credentialId);
      }
    }
    credentialIdentity.current = next;
    for (const credential of credentials) {
      void readAccountUsage(credential.id);
    }
  }, [
    advanceEpoch,
    cancelRetry,
    clearCooldown,
    credentialKey,
    readAccountUsage,
    settingsReadCache,
  ]);

  useEffect(() => {
    const onVisibilityChange = () =>
      setDocumentVisible(document.visibilityState !== "hidden");
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => document.removeEventListener("visibilitychange", onVisibilityChange);
  }, []);

  useEffect(() => {
    const target = sectionRef.current;
    if (!target || typeof window.IntersectionObserver === "undefined") return undefined;
    const observer = new window.IntersectionObserver((entries) => {
      setSectionInViewport(entries.some((entry) => entry.isIntersecting));
    });
    observer.observe(target);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const onFocus = () => {
      if (!documentVisible || !sectionInViewport) return;
      for (const credential of credentialsRef.current) {
        void readRef.current?.(credential.id);
      }
    };
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [documentVisible, sectionInViewport]);

  useEffect(() => () => {
    for (const credentialId of credentialIdentity.current.keys()) advanceEpoch(credentialId);
    for (const timer of retryTimers.current.values()) window.clearTimeout(timer);
    for (const timer of cooldownTimers.current.values()) window.clearTimeout(timer);
    retryTimers.current.clear();
    cooldownTimers.current.clear();
    cooldownDeadlines.current.clear();
    syncInFlight.current.clear();
  }, [advanceEpoch]);

  return {
    states,
    cooldownUntil,
    sectionRef,
    readAccountUsage,
    syncAccountUsage,
    invalidateAccountUsage,
  };
}
