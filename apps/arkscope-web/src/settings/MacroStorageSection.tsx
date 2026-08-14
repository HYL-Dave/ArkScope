import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { RefreshCw } from "lucide-react";

import {
  getMacroSnapshot,
  getMacroStatus,
  type MacroSnapshot,
  type MacroSnapshotItem,
  type MacroStatus,
  type MacroTableStat,
} from "../api";
import { formatSystemTimestamp } from "../timeDisplay";
import { Button } from "../ui/Button";
import { InlineAlert } from "../ui/Status";
import { DataScheduleTable, useSharedDataScheduleControls } from "./dataScheduleControls";
import type { SettingsT } from "./settingsCopy";
import type { SettingsReadCache } from "./settingsReadCache";

const MACRO_TABLE_KEYS = [
  "macro_series",
  "macro_observations",
  "macro_release_dates",
  "cal_economic_events",
  "cal_earnings_events",
  "cal_ipo_events",
] as const;

const MACRO_SCHEDULE_SOURCE_IDS = [
  "fred_series",
  "fred_release_dates",
  "finnhub_economic_calendar",
  "finnhub_earnings_calendar",
  "finnhub_ipo_calendar",
] as const;

function macroTableLabel(key: typeof MACRO_TABLE_KEYS[number], t: SettingsT): string {
  switch (key) {
    case "macro_series":
      return t(($) => $.macroStorage.kinds.fredSeries);
    case "macro_observations":
      return t(($) => $.macroStorage.kinds.fredObservations);
    case "macro_release_dates":
      return t(($) => $.macroStorage.kinds.fredReleases);
    case "cal_economic_events":
      return t(($) => $.macroStorage.kinds.economicEvents);
    case "cal_earnings_events":
      return t(($) => $.macroStorage.kinds.earningsEvents);
    case "cal_ipo_events":
      return t(($) => $.macroStorage.kinds.ipoEvents);
  }
}

function storedCoverage(table: MacroTableStat | undefined, t: SettingsT): string {
  if (!table) return t(($) => $.macroStorage.availability.tableUnavailable);
  const count = t(($) => $.macroStorage.counts.stored, {
    value: table.row_count.toLocaleString(),
  });
  if (table.row_count === 0) return count;
  return t(($) => $.macroStorage.counts.summary, {
    value: count,
    timestamp: formatSystemTimestamp(table.last_fetched_at),
  });
}

function snapshotValue(item: MacroSnapshotItem): string {
  if (item.value == null || !Number.isFinite(item.value)) return "—";
  const value = item.value.toLocaleString();
  return item.units ? `${value} ${item.units}` : value;
}

export function MacroStorageSection({
  settingsReadCache,
}: {
  settingsReadCache: SettingsReadCache;
}) {
  const { t } = useTranslation("settings");
  const scheduleController = useSharedDataScheduleControls();
  const [status, setStatus] = useState<MacroStatus | null>(() => {
    const inspected = settingsReadCache.inspect<MacroStatus>("macro_status");
    return inspected.status === "missing" ? null : inspected.value;
  });
  const [snapshot, setSnapshot] = useState<MacroSnapshot | null>(() => {
    const inspected = settingsReadCache.inspect<MacroSnapshot>("macro_snapshot");
    return inspected.status === "missing" ? null : inspected.value;
  });
  const [statusUnavailable, setStatusUnavailable] = useState(false);
  const [snapshotUnavailable, setSnapshotUnavailable] = useState(false);
  const [loading, setLoading] = useState(false);
  const mountedRef = useRef(false);
  const sequenceRef = useRef(0);

  const load = useCallback(async (force = false) => {
    const sequence = ++sequenceRef.current;
    setLoading(true);
    const [statusResult, snapshotResult] = await Promise.all([
      settingsReadCache.load("macro_status", getMacroStatus, { force }),
      settingsReadCache.load("macro_snapshot", getMacroSnapshot, { force }),
    ]);
    if (!mountedRef.current || sequence !== sequenceRef.current) return;

    if (statusResult.status === "success") {
      setStatus(statusResult.value);
      setStatusUnavailable(false);
    } else if (statusResult.status === "error") {
      setStatusUnavailable(true);
    }
    if (snapshotResult.status === "success") {
      setSnapshot(snapshotResult.value);
      setSnapshotUnavailable(false);
    } else if (snapshotResult.status === "error") {
      setSnapshotUnavailable(true);
    }
    setLoading(false);
  }, [settingsReadCache]);

  useEffect(() => {
    mountedRef.current = true;
    void load(false);
    return () => {
      mountedRef.current = false;
    };
  }, [load]);
  useEffect(() => {
    const reload = () => { void load(false); };
    const unsubscribeStatus = settingsReadCache.subscribeInvalidation("macro_status", reload);
    const unsubscribeSnapshot = settingsReadCache.subscribeInvalidation("macro_snapshot", reload);
    return () => {
      unsubscribeStatus();
      unsubscribeSnapshot();
    };
  }, [load, settingsReadCache]);

  const tables = status?.tables ?? {};
  const statusAvailable = Boolean(
    status?.exists && tables.macro_series && tables.macro_observations,
  );
  const bothTransportLegsUnavailable = statusUnavailable && snapshotUnavailable
    && status == null && snapshot == null;
  const oneTransportLegUnavailable = !bothTransportLegsUnavailable
    && (statusUnavailable || snapshotUnavailable);
  const domainUnavailable = (status != null && !statusAvailable)
    || (snapshot != null && !snapshot.available);
  const enabledScheduleCount = scheduleController.schedule === null
    ? null
    : MACRO_SCHEDULE_SOURCE_IDS.filter(
        (source) => scheduleController.schedule?.[source]?.enabled,
      ).length;
  const automationStatus = enabledScheduleCount === null
    ? t(($) => $.macroStorage.schedule.unknown)
    : enabledScheduleCount === 0
      ? t(($) => $.macroStorage.schedule.disabled)
      : enabledScheduleCount === 1
        ? t(($) => $.macroStorage.schedule.enabledCount_one, { count: enabledScheduleCount })
        : t(($) => $.macroStorage.schedule.enabledCount_other, { count: enabledScheduleCount });

  return (
    <div>
      <div className="settings-section-head">
        <div>
          <h2>{t(($) => $.macroStorage.title)}</h2>
          <p className="muted tiny">{t(($) => $.macroStorage.description)}</p>
        </div>
        <Button
          tone="ghost"
          size="compact"
          icon={<RefreshCw size={15} />}
          aria-busy={loading || undefined}
          onClick={() => void load(true)}
        >
          {t(($) => $.actions.refreshStatus)}
        </Button>
      </div>

      {bothTransportLegsUnavailable ? (
        <InlineAlert state="failed" title={t(($) => $.macroStorage.availability.unavailable)}>
          {t(($) => $.macroStorage.messages.unavailableDetail)}
        </InlineAlert>
      ) : null}
      {oneTransportLegUnavailable ? (
        <InlineAlert state="partial" title={t(($) => $.macroStorage.availability.partial)}>
          {t(($) => $.macroStorage.messages.partialDetail)}
        </InlineAlert>
      ) : null}
      {domainUnavailable ? (
        <InlineAlert
          state="blocked"
          title={t(($) => $.macroStorage.availability.databaseUnavailable)}
        />
      ) : null}

      {status == null && snapshot == null && loading ? (
        <p className="muted">{t(($) => $.macroStorage.loading)}</p>
      ) : null}

      {statusAvailable ? (
        <div className="settings-panel">
          <h3>{t(($) => $.macroStorage.headings.storedCoverage)}</h3>
          <dl className="ds-kv">
            {MACRO_TABLE_KEYS.map((key) => (
              <FragmentKV
                key={key}
                label={macroTableLabel(key, t)}
                value={storedCoverage(tables[key], t)}
              />
            ))}
          </dl>
        </div>
      ) : null}

      <div className="settings-panel">
        <div className="settings-section-head">
          <h3>{t(($) => $.dataSources.schedule.title)}</h3>
          <span className="muted tiny">{automationStatus}</span>
        </div>
        <DataScheduleTable
          controller={scheduleController}
          sourceIds={MACRO_SCHEDULE_SOURCE_IDS}
        />
      </div>

      {snapshot?.available ? (
        <div className="settings-panel">
          <div className="settings-section-head">
            <div>
              <h3>{t(($) => $.macroStorage.snapshot.title)}</h3>
              <p className="muted tiny">
                {snapshot.latest_fetched_at
                  ? t(($) => $.macroStorage.counts.summary, {
                      value: t(($) => $.macroStorage.counts.stored, {
                        value: snapshot.observation_count.toLocaleString(),
                      }),
                      timestamp: formatSystemTimestamp(snapshot.latest_fetched_at),
                    })
                  : t(($) => $.macroStorage.counts.stored, {
                      value: snapshot.observation_count.toLocaleString(),
                    })}
              </p>
            </div>
          </div>

          {snapshot.items.length === 0 ? (
            <p className="muted">{t(($) => $.macroStorage.counts.zero)}</p>
          ) : (
            <div className="settings-table-scroll" data-testid="fred-snapshot-scroll">
              <table className="ds-table settings-fred-table">
                <thead>
                  <tr>
                    <th>{t(($) => $.macroStorage.headings.seriesId)}</th>
                    <th>{t(($) => $.macroStorage.headings.name)}</th>
                    <th>{t(($) => $.macroStorage.headings.latestValue)}</th>
                    <th>{t(($) => $.macroStorage.headings.observationDate)}</th>
                    <th>{t(($) => $.macroStorage.headings.lastFetch)}</th>
                  </tr>
                </thead>
                <tbody>
                  {snapshot.items.map((item) => (
                    <tr key={item.series_id}>
                      <td>{item.series_id}</td>
                      <td>
                        <strong>{item.label}</strong>
                        {item.title && item.title !== item.label
                          ? <div className="muted tiny">{item.title}</div>
                          : null}
                      </td>
                      <td>{snapshotValue(item)}</td>
                      <td>{item.observation_date ?? "—"}</td>
                      <td>{formatSystemTimestamp(item.fetched_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}

function FragmentKV({ label, value }: { label: string; value: string }) {
  return (
    <>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </>
  );
}
