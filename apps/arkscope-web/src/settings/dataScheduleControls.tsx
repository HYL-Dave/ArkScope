import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useTranslation } from "react-i18next";

import {
  getSchedule,
  putSchedule,
  runScheduleNow,
  type ProvidersHealthResponse,
  type ScheduleRunResult,
  type ScheduleSourceState,
} from "../api";
import {
  durableScheduleCommonState,
} from "../dataSourcesPresentation";
import {
  dataSourceScheduleLifecycleChanged,
  dataSourceSchedulePollMs,
  type DataSourceScheduleMap,
} from "../dataSourceSchedulePolling";
import {
  schedulerBodyBacklogPresentation,
  schedulerStateLabel,
} from "../marketDataDisplay";
import { SourceRunProgress } from "../SourceRunProgress";
import { formatSystemTimestamp } from "../timeDisplay";
import { StatusBadge } from "../ui";
import { shortTs } from "./DataStorageSection";
import {
  scheduleSourceCopy,
} from "./settingsBackendCopy";
import type { SettingsT } from "./settingsCopy";
import type { SettingsReadCache } from "./settingsReadCache";

type ScheduleResponse = Awaited<ReturnType<typeof getSchedule>>;

export type DataScheduleOutcome =
  | { kind: "error"; error: unknown }
  | { kind: "schedule"; source: string; result: ScheduleRunResult };

export type DataScheduleScope = "macro" | "non_macro";

export function dataScheduleSourceMatchesScope(
  state: Pick<ScheduleSourceState, "write_target">,
  scope: DataScheduleScope,
): boolean {
  const macro = state.write_target === "macro_calendar.db";
  return scope === "macro" ? macro : !macro;
}

export type DataScheduleController = {
  schedule: DataSourceScheduleMap | null;
  jobFacts: ProvidersHealthResponse["jobs"];
  busy: string;
  drafts: Record<string, string>;
  hasDrafts: boolean;
  anyRunning: boolean;
  lifecycleVersion: number;
  outcome: DataScheduleOutcome | null;
  setIntervalDraft(source: string, value: string): void;
  setEnabled(source: string, enabled: boolean): Promise<void>;
  applyInterval(source: string): Promise<void>;
  runNow(source: string): Promise<void>;
  reloadSchedule(): Promise<void>;
  pollSchedule(): Promise<void>;
  replaceJobFacts(jobs: ProvidersHealthResponse["jobs"]): void;
};

const DataScheduleControlsContext = createContext<DataScheduleController | null>(null);

function retainedSchedule(cache: SettingsReadCache): ScheduleResponse | null {
  const inspected = cache.inspect<ScheduleResponse>("data_schedule");
  return inspected.status === "missing" ? null : inspected.value;
}

function terminalStatus(source: ScheduleSourceState): string | null {
  return source.last_result?.status ?? source.durable_state?.last_status ?? null;
}

function terminalRevision(source: ScheduleSourceState): string {
  return [
    terminalStatus(source) ?? "",
    source.last_attempt_at ?? "",
    source.last_result?.at ?? "",
    source.durable_state?.last_attempt ?? "",
    source.durable_state?.updated_at ?? "",
  ].join("\0");
}

function invalidationCandidates(
  previous: DataSourceScheduleMap | null,
  next: DataSourceScheduleMap,
): Array<{ source: string; writeTarget: string }> {
  if (previous === null) return [];
  const completed: Array<{ source: string; writeTarget: string }> = [];
  for (const [source, before] of Object.entries(previous)) {
    const after = next[source];
    if (!after || after.running) continue;
    const isMacro = after.write_target === "macro_calendar.db";
    if (isMacro && terminalStatus(after) !== "succeeded") continue;
    if (!before.running && terminalRevision(before) === terminalRevision(after)) continue;
    completed.push({ source, writeTarget: after.write_target });
  }
  return completed;
}

export function useDataScheduleControls(
  settingsReadCache: SettingsReadCache,
): DataScheduleController {
  const [initialSchedule] = useState(() => retainedSchedule(settingsReadCache));
  const [schedule, setSchedule] = useState<DataSourceScheduleMap | null>(
    initialSchedule?.sources ?? null,
  );
  const [jobFacts, setJobFacts] = useState<ProvidersHealthResponse["jobs"]>({});
  const [busy, setBusy] = useState("");
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [outcome, setOutcome] = useState<DataScheduleOutcome | null>(null);
  const [lifecycleVersion, setLifecycleVersion] = useState(0);
  const scheduleRef = useRef<DataSourceScheduleMap | null>(initialSchedule?.sources ?? null);
  const requestSequenceRef = useRef(0);
  const acceptedSequenceRef = useRef(0);
  const pollInFlightRef = useRef<Promise<void> | null>(null);
  const mutationInFlightRef = useRef(false);
  const mountedRef = useRef(false);

  const acceptSchedule = useCallback((next: DataSourceScheduleMap, sequence: number) => {
    if (!mountedRef.current || sequence < acceptedSequenceRef.current) {
      return { accepted: false, lifecycleChanged: false };
    }
    acceptedSequenceRef.current = sequence;
    const previous = scheduleRef.current;
    scheduleRef.current = next;
    setSchedule(next);
    for (const candidate of invalidationCandidates(previous, next)) {
      settingsReadCache.invalidateDataSource(candidate.source, candidate.writeTarget);
    }
    const lifecycleChanged = dataSourceScheduleLifecycleChanged(previous, next);
    if (lifecycleChanged) setLifecycleVersion((value) => value + 1);
    return { accepted: true, lifecycleChanged };
  }, [settingsReadCache]);

  const loadSchedule = useCallback(async (
    force: boolean,
    reportError: boolean,
  ): Promise<boolean> => {
    const sequence = ++requestSequenceRef.current;
    const result = await settingsReadCache.load("data_schedule", getSchedule, { force });
    if (!mountedRef.current) return false;
    if (result.status === "success") {
      const accepted = acceptSchedule(result.value.sources, sequence);
      if (reportError) setOutcome(null);
      return accepted.lifecycleChanged;
    } else if (result.status === "error" && reportError) {
      setOutcome({ kind: "error", error: result.error });
    }
    return false;
  }, [acceptSchedule, settingsReadCache]);

  const pollSchedule = useCallback((): Promise<void> => {
    if (pollInFlightRef.current) return pollInFlightRef.current;
    const request = (async () => {
      const lifecycleChanged = await loadSchedule(true, false);
      if (lifecycleChanged) await loadSchedule(true, false);
    })().finally(() => {
      if (pollInFlightRef.current === request) pollInFlightRef.current = null;
    });
    pollInFlightRef.current = request;
    return request;
  }, [loadSchedule]);

  useEffect(() => {
    mountedRef.current = true;
    void loadSchedule(false, true);
    return () => {
      mountedRef.current = false;
      requestSequenceRef.current += 1;
    };
  }, [loadSchedule]);

  const pollIntervalMs = dataSourceSchedulePollMs(schedule);
  useEffect(() => {
    const timer = window.setInterval(() => { void pollSchedule(); }, pollIntervalMs);
    const onFocus = () => { void pollSchedule(); };
    window.addEventListener("focus", onFocus);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", onFocus);
    };
  }, [pollIntervalMs, pollSchedule]);

  const reloadSchedule = useCallback(
    async () => { await loadSchedule(true, true); },
    [loadSchedule],
  );

  const replaceJobFacts = useCallback((jobs: ProvidersHealthResponse["jobs"]) => {
    setJobFacts({ ...jobs });
  }, []);

  const setEnabled = useCallback(async (source: string, enabled: boolean) => {
    if (mutationInFlightRef.current) return;
    mutationInFlightRef.current = true;
    setBusy(source);
    try {
      await putSchedule(source, { enabled });
      settingsReadCache.invalidate("data_schedule");
      settingsReadCache.invalidate("provider_health");
      await loadSchedule(true, true);
    } catch (error) {
      if (mountedRef.current) setOutcome({ kind: "error", error });
    } finally {
      mutationInFlightRef.current = false;
      if (mountedRef.current) setBusy("");
    }
  }, [loadSchedule, settingsReadCache]);

  const applyInterval = useCallback(async (source: string) => {
    const raw = drafts[source];
    const interval = Number(raw);
    if (!raw || !Number.isFinite(interval) || mutationInFlightRef.current) return;
    mutationInFlightRef.current = true;
    setBusy(source);
    try {
      await putSchedule(source, { interval_minutes: Math.round(interval) });
      if (mountedRef.current) setDrafts((values) => ({ ...values, [source]: "" }));
      settingsReadCache.invalidate("data_schedule");
      settingsReadCache.invalidate("provider_health");
      await loadSchedule(true, true);
    } catch (error) {
      if (mountedRef.current) setOutcome({ kind: "error", error });
    } finally {
      mutationInFlightRef.current = false;
      if (mountedRef.current) setBusy("");
    }
  }, [drafts, loadSchedule, settingsReadCache]);

  const runNow = useCallback(async (source: string) => {
    if (mutationInFlightRef.current) return;
    mutationInFlightRef.current = true;
    setBusy(source);
    try {
      const result = await runScheduleNow(source);
      if (mountedRef.current) {
        setOutcome({ kind: "schedule", source, result });
      }
      settingsReadCache.invalidate("data_schedule");
      pollInFlightRef.current = null;
      await pollSchedule();
    } catch (error) {
      if (mountedRef.current) setOutcome({ kind: "error", error });
    } finally {
      mutationInFlightRef.current = false;
      if (mountedRef.current) setBusy("");
    }
  }, [pollSchedule, settingsReadCache]);

  return {
    schedule,
    jobFacts,
    busy,
    drafts,
    hasDrafts: Object.values(drafts).some((value) => value !== ""),
    anyRunning: schedule !== null && Object.values(schedule).some((source) => source.running),
    lifecycleVersion,
    outcome,
    setIntervalDraft: (source, value) => setDrafts((values) => ({ ...values, [source]: value })),
    setEnabled,
    applyInterval,
    runNow,
    reloadSchedule,
    pollSchedule,
    replaceJobFacts,
  };
}

export function DataScheduleControlsProvider({
  settingsReadCache,
  children,
}: {
  settingsReadCache: SettingsReadCache;
  children: ReactNode;
}) {
  const controller = useDataScheduleControls(settingsReadCache);
  return (
    <DataScheduleControlsContext.Provider value={controller}>
      {children}
    </DataScheduleControlsContext.Provider>
  );
}

export function useSharedDataScheduleControls(): DataScheduleController {
  const controller = useContext(DataScheduleControlsContext);
  if (controller === null) {
    throw new Error("Data schedule controls require a provider");
  }
  return controller;
}

function jobOutcome(
  jobs: ProvidersHealthResponse["jobs"] | undefined,
  jobName: string,
  t: SettingsT,
): string {
  const row = jobs?.[jobName] as
    | { status?: string; finished_at?: string; error?: string }
    | undefined;
  if (!row) return "—";
  const timestamp = shortTs(row.finished_at ?? null);
  if (row.status === "succeeded") return `✓ ${timestamp}`;
  if (row.status === "failed") return `✗ ${timestamp}`;
  if (row.status === "running") return t(($) => $.actions.running);
  return row.status ?? "—";
}

function LastRun({
  source,
  state,
  controller,
  externalBusy,
  t,
}: {
  source: string;
  state: ScheduleSourceState;
  controller: DataScheduleController;
  externalBusy: boolean;
  t: SettingsT;
}) {
  const skipped = state.last_result?.status === "skipped";
  const historyState = durableScheduleCommonState(state);
  const durableSkipped = state.durable_state?.last_status === "skipped";
  const schedulerState = schedulerStateLabel(state.durable_state ?? null, t);
  const bodyBacklog = schedulerBodyBacklogPresentation(state.durable_state ?? null, t);
  return (
    <div className="ds-last-run">
      <div className="ds-last-run-summary">
        <span>{jobOutcome(controller.jobFacts, state.job_name, t)}</span>
        {skipped ? (
          <StatusBadge state="blocked" label={t(($) => $.dataSources.schedule.triggerSkipped)} />
        ) : null}
        {historyState !== null ? (
          <StatusBadge state={historyState} label={schedulerState.label} />
        ) : durableSkipped && !skipped ? (
          <span className="muted tiny">{schedulerState.label}</span>
        ) : null}
        {schedulerState.needsContinue ? (
          <button
            className="btn-ghost"
            disabled={externalBusy || Boolean(controller.busy) || state.running}
            onClick={() => void controller.runNow(source)}
            title={t(($) => $.dataSources.schedule.continue.title)}
          >
            {t(($) => $.dataSources.schedule.continue.label)}
          </button>
        ) : null}
      </div>
      {bodyBacklog ? (
        <div className={`tiny ${bodyBacklog.tone === "warn" ? "refresh-err" : "muted"}`}>
          {bodyBacklog.label}
          {bodyBacklog.earliestNextRetryAt
            ? <>
                {" · "}
                {t(($) => $.dataSources.schedule.backlog.earliest, {
                  timestamp: formatSystemTimestamp(bodyBacklog.earliestNextRetryAt),
                })}
              </>
            : ""}
        </div>
      ) : null}
    </div>
  );
}

export function DataScheduleTable({
  controller,
  scope,
  externalBusy = false,
}: {
  controller: DataScheduleController;
  scope: DataScheduleScope;
  externalBusy?: boolean;
}) {
  const { t } = useTranslation("settings");
  const schedule = controller.schedule;
  if (schedule === null) {
    return <p className="muted tiny">{t(($) => $.dataSources.loading)}</p>;
  }
  const rows = Object.entries(schedule)
    .filter(([, state]) => dataScheduleSourceMatchesScope(state, scope));

  return (
    <div className="settings-table-scroll" data-testid="schedule-scroll">
        <table className="data-table settings-schedule-table">
          <thead>
            <tr>
              <th>{t(($) => $.dataSources.headings.source)}</th>
              <th>{t(($) => $.dataSources.headings.schedule)}</th>
              <th>{t(($) => $.dataSources.headings.intervalMinutes)}</th>
              <th>{t(($) => $.dataSources.headings.runNow)}</th>
              <th>{t(($) => $.dataSources.headings.lastRun)}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([source, state]) => {
              const copy = scheduleSourceCopy(source, t);
              return (
                <tr key={source} data-source-id={source}>
                  <td className="settings-schedule-source-cell">
                    {copy.label}
                    <div className="muted tiny">{copy.description}</div>
                  </td>
                  <td>
                    <label className="ds-toggle">
                      <input
                        type="checkbox"
                        checked={state.enabled}
                        disabled={externalBusy || controller.busy === source}
                        onChange={(event) => void controller.setEnabled(source, event.target.checked)}
                      />
                      <span className={state.enabled ? "tiny" : "muted tiny ds-schedule-disabled"}>
                        {state.enabled
                          ? t(($) => $.dataSources.labels.scheduleEnabled)
                          : t(($) => $.dataSources.labels.scheduleDisabled)}
                      </span>
                    </label>
                  </td>
                  <td>
                    <input
                      className="ds-interval"
                      type="number"
                      min={5}
                      placeholder={String(state.interval_minutes)}
                      value={controller.drafts[source] ?? ""}
                      disabled={externalBusy || controller.busy === source}
                      onChange={(event) => controller.setIntervalDraft(source, event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") void controller.applyInterval(source);
                      }}
                    />
                    {controller.drafts[source] ? (
                      <button
                        className="btn-ghost tiny"
                        disabled={externalBusy || Boolean(controller.busy)}
                        onClick={() => void controller.applyInterval(source)}
                      >
                        {t(($) => $.actions.apply)}
                      </button>
                    ) : null}
                  </td>
                  <td>
                    {state.running ? (
                      <SourceRunProgress
                        sourceLabel={copy.label}
                        running={state.running}
                        progress={state.progress}
                      />
                    ) : (
                      <button
                        className="btn-ghost"
                        disabled={externalBusy || Boolean(controller.busy)}
                        onClick={() => void controller.runNow(source)}
                      >
                        ▶ {t(($) => $.actions.run)}
                      </button>
                    )}
                  </td>
                  <td className="muted tiny ds-last-run-cell settings-wrap-text">
                    <LastRun
                      source={source}
                      state={state}
                      controller={controller}
                      externalBusy={externalBusy}
                      t={t}
                    />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
  );
}
