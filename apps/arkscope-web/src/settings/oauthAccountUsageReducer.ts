import type { OAuthAccountSnapshot } from "../api";

export type OAuthAccountUsageState = {
  snapshot: OAuthAccountSnapshot | null;
  cachedRead: {
    status: "idle" | "loading" | "loaded" | "failed";
    errorCode: string | null;
  };
  syncSend: {
    status: "idle" | "sending" | "transport_failed";
    errorCode: string | null;
  };
  backendSync: {
    errorCode: string | null;
  };
};

export type OAuthAccountUsageAction =
  | { type: "read_started" }
  | { type: "read_succeeded"; snapshot: OAuthAccountSnapshot | null }
  | { type: "read_failed"; errorCode: string }
  | { type: "sync_started" }
  | { type: "sync_succeeded"; snapshot: OAuthAccountSnapshot }
  | {
      type: "sync_failed";
      snapshot: OAuthAccountSnapshot | null;
      errorCode: string;
      credentialChanged: boolean;
    }
  | { type: "sync_transport_failed"; errorCode: string }
  | { type: "credential_changed" };

export const EMPTY_OAUTH_ACCOUNT_USAGE_STATE: OAuthAccountUsageState = {
  snapshot: null,
  cachedRead: { status: "idle", errorCode: null },
  syncSend: { status: "idle", errorCode: null },
  backendSync: { errorCode: null },
};

export function reduceOAuthAccountUsage(
  state: OAuthAccountUsageState,
  action: OAuthAccountUsageAction,
): OAuthAccountUsageState {
  switch (action.type) {
    case "read_started":
      return {
        ...state,
        cachedRead: { status: "loading", errorCode: null },
      };
    case "read_succeeded":
      return {
        ...state,
        snapshot: action.snapshot,
        cachedRead: { status: "loaded", errorCode: null },
      };
    case "read_failed":
      return {
        ...state,
        cachedRead: { status: "failed", errorCode: action.errorCode },
      };
    case "sync_started":
      return {
        ...state,
        syncSend: { status: "sending", errorCode: null },
        backendSync: { errorCode: null },
      };
    case "sync_succeeded":
      return {
        ...state,
        snapshot: action.snapshot,
        syncSend: { status: "idle", errorCode: null },
        backendSync: { errorCode: null },
      };
    case "sync_failed":
      if (action.credentialChanged) {
        return {
          ...EMPTY_OAUTH_ACCOUNT_USAGE_STATE,
          backendSync: { errorCode: action.errorCode },
        };
      }
      return {
        ...state,
        snapshot: action.snapshot ?? state.snapshot,
        syncSend: { status: "idle", errorCode: null },
        backendSync: { errorCode: action.errorCode },
      };
    case "sync_transport_failed":
      return {
        ...state,
        syncSend: {
          status: "transport_failed",
          errorCode: action.errorCode,
        },
      };
    case "credential_changed":
      return EMPTY_OAUTH_ACCOUNT_USAGE_STATE;
  }
}
