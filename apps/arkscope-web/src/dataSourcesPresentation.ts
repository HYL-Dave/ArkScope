import type {
  ProviderStatus,
  SAExtensionHealthSegment,
  ScheduleSourceState,
} from "./api";
import type { CommonUiState } from "./ui";

export function providerCommonState(status: ProviderStatus): CommonUiState | null {
  switch (status) {
    case "connected": return "ready";
    case "stale": return "stale";
    case "maintenance": return "partial";
    case "no_signal": return "empty";
    case "not_configured":
    case "missing_key": return "blocked";
    case "disabled": return null;
  }
}

export function saSegmentCommonState(
  state: SAExtensionHealthSegment["state"],
): CommonUiState {
  if (state === "ok") return "ready";
  if (state === "warn") return "partial";
  return "failed";
}

export function durableScheduleCommonState(
  source: ScheduleSourceState,
): CommonUiState | null {
  switch (source.durable_state?.last_status) {
    case "succeeded": return "ready";
    case "partial": return "partial";
    case "failed": return "failed";
    case "running": return source.durable_state.running_stale ? "stale" : "running";
    case "skipped": return null;
    default: return source.enabled ? "empty" : null;
  }
}

export function scheduleSkipCommonState(
  reason: string | null | undefined,
): CommonUiState | null {
  return reason?.includes("already running") ? "blocked" : null;
}
