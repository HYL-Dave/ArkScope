import type { ScheduleSourceState } from "./api";

export const DATA_SOURCE_SCHEDULE_IDLE_POLL_MS = 30_000;
export const DATA_SOURCE_SCHEDULE_ACTIVE_POLL_MS = 5_000;

export type DataSourceScheduleMap = Record<string, ScheduleSourceState>;

export function dataSourceSchedulePollMs(
  sources: DataSourceScheduleMap | null,
): number {
  return sources && Object.values(sources).some((source) => source.running)
    ? DATA_SOURCE_SCHEDULE_ACTIVE_POLL_MS
    : DATA_SOURCE_SCHEDULE_IDLE_POLL_MS;
}

function lifecycleFingerprint(sources: DataSourceScheduleMap): string {
  return JSON.stringify(Object.keys(sources).sort().map((sourceId) => {
    const source = sources[sourceId];
    return [
      sourceId,
      source.running,
      source.last_attempt_at ?? null,
      source.durable_state?.last_status ?? null,
      source.durable_state?.last_attempt ?? null,
      source.durable_state?.updated_at ?? null,
    ];
  }));
}

export function dataSourceScheduleLifecycleChanged(
  previous: DataSourceScheduleMap | null,
  next: DataSourceScheduleMap,
): boolean {
  if (previous === null) return false;
  return lifecycleFingerprint(previous) !== lifecycleFingerprint(next);
}
