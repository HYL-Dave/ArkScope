import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { BookOpen, RefreshCw } from "lucide-react";

import {
  getMacroSnapshot,
  getMacroStatus,
  type MacroSnapshot,
  type MacroSnapshotItem,
  type MacroStatus,
  type MacroTableStat,
} from "../api";
import { formatSystemTimestamp } from "../timeDisplay";
import { IconButton } from "../ui/Button";
import { Drawer } from "../ui/Drawer";
import { InlineAlert } from "../ui/Status";
import {
  DataScheduleTable,
  dataScheduleSourceMatchesScope,
  useSharedDataScheduleControls,
} from "./dataScheduleControls";
import type { SettingsT } from "./settingsCopy";
import type { SettingsReadCache } from "./settingsReadCache";
import { isMacroIndicator, macroFrequencyLabel, macroIndicatorCopy, macroObservationPeriod } from "./macroIndicators";
import { RecordedTimestamp } from "./RecordedTimestamp";

const MACRO_TABLE_KEYS = [
  "macro_series",
  "macro_observations",
  "macro_release_dates",
  "cal_economic_events",
  "cal_earnings_events",
  "cal_ipo_events",
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
  if (table.row_count === 0) return t(($) => $.macroStorage.counts.coverageUnknown);
  return t(($) => $.macroStorage.counts.summary, {
    value: count,
    timestamp: formatSystemTimestamp(table.last_fetched_at),
  });
}

function snapshotValue(item: MacroSnapshotItem): string {
  if (item.value == null || !Number.isFinite(item.value)) return "—";
  const value = item.value.toLocaleString();
  return value;
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
  const [guideItem, setGuideItem] = useState<MacroSnapshotItem | null>(null);
  const guideButtonRef = useRef<HTMLButtonElement | null>(null);

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
    : Object.values(scheduleController.schedule)
        .filter((state) => dataScheduleSourceMatchesScope(state, "macro") && state.enabled)
        .length;
  const automationStatus = enabledScheduleCount === null
    ? t(($) => $.macroStorage.schedule.unknown)
    : enabledScheduleCount === 0
      ? t(($) => $.macroStorage.schedule.disabled)
      : enabledScheduleCount === 1
        ? t(($) => $.macroStorage.schedule.enabledCount_one, { count: enabledScheduleCount })
        : t(($) => $.macroStorage.schedule.enabledCount_other, { count: enabledScheduleCount });

  return (
    <div className="settings-macro-sections">
      <div className="settings-section-head">
        <div>
          <h2>{t(($) => $.macroStorage.title)}</h2>
          <p className="muted tiny">{t(($) => $.macroStorage.description)}</p>
        </div>
        <IconButton
          tone="ghost"
          size="compact"
          label={t(($) => $.actions.refreshStatus)}
          icon={<RefreshCw size={15} />}
          busy={loading}
          onClick={() => void load(true)}
        />
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
        <div className="settings-data-band">
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
          <p className="muted tiny">{t(($) => $.macroStorage.counts.coverageNote)}</p>
        </div>
      ) : null}

      <div className="settings-data-band">
        <div className="settings-section-head">
          <h3>{t(($) => $.macroStorage.schedule.title)}</h3>
          <span className="muted tiny">{automationStatus}</span>
        </div>
        <p className="muted tiny">{t(($) => $.macroStorage.schedule.historyNote)}</p>
        <DataScheduleTable
          controller={scheduleController}
          scope="macro"
        />
      </div>

      {snapshot?.available ? (
        <div className="settings-data-band">
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
            <div className="settings-table-scroll settings-records" data-testid="fred-snapshot-scroll"
              tabIndex={0} role="region" aria-label={t(($) => $.macroStorage.snapshot.title)}>
              <table className="ds-table settings-fred-table settings-responsive-table">
                <colgroup><col /><col /><col /><col /><col /><col /></colgroup>
                <thead>
                  <tr>
                    <th>{t(($) => $.macroStorage.headings.seriesId)}</th>
                    <th>{t(($) => $.macroStorage.headings.name)}</th>
                    <th>{t(($) => $.macroStorage.headings.latestValue)}</th>
                    <th>{t(($) => $.macroStorage.headings.units)}</th>
                    <th>{t(($) => $.macroStorage.headings.observationDate)}</th>
                    <th>{t(($) => $.macroStorage.headings.lastFetch)}</th>
                  </tr>
                </thead>
                <tbody>
                  {snapshot.items.map((item) => (
                    <tr key={item.series_id}>
                      <td data-label={t(($) => $.macroStorage.headings.seriesId)}><div className="settings-fred-series">
                        <code>{item.series_id}</code>
                        {isMacroIndicator(item.series_id) ? <IconButton
                          size="compact" tone="ghost" icon={<BookOpen size={15} />}
                          label={t(($) => $.macroStorage.guide.open, { id: item.series_id })}
                          onClick={(event) => {
                            guideButtonRef.current = event.currentTarget;
                            setGuideItem(item);
                          }}
                        /> : null}
                      </div></td>
                      <td data-label={t(($) => $.macroStorage.headings.name)}>
                        <strong title={item.title ?? undefined}>{item.label}</strong>
                        <div className="muted tiny">{macroFrequencyLabel(item.frequency, t)}</div>
                      </td>
                      <td className="settings-fred-value" data-label={t(($) => $.macroStorage.headings.latestValue)}>{snapshotValue(item)}</td>
                      <td data-label={t(($) => $.macroStorage.headings.units)}>{item.units ?? "—"}</td>
                      <td className="settings-fred-period" data-label={t(($) => $.macroStorage.headings.observationDate)} title={item.observation_date ?? undefined}>{macroObservationPeriod(item)}</td>
                      <td className="settings-fred-fetched" data-label={t(($) => $.macroStorage.headings.lastFetch)}><RecordedTimestamp value={item.fetched_at} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : null}
      <Drawer open={guideItem !== null} title={guideItem?.label ?? ""}
        onClose={() => setGuideItem(null)} returnFocusRef={guideButtonRef}>
        {guideItem && isMacroIndicator(guideItem.series_id) ? <div className="settings-indicator-guide">
          <h3>{guideItem.title ?? guideItem.series_id}</h3>
          <p>{macroIndicatorCopy(guideItem.series_id, t)}</p>
          <dl className="ds-kv">
            <FragmentKV label={t(($) => $.macroStorage.headings.units)} value={guideItem.units ?? "—"} />
            <FragmentKV label={t(($) => $.macroStorage.guide.frequency)} value={macroFrequencyLabel(guideItem.frequency, t)} />
            <FragmentKV label={t(($) => $.macroStorage.guide.adjustment)} value={guideItem.seasonal_adjustment ?? "—"} />
            <FragmentKV label={t(($) => $.macroStorage.headings.observationDate)} value={guideItem.observation_date ?? "—"} />
            <FragmentKV label={t(($) => $.macroStorage.headings.lastFetch)} value={formatSystemTimestamp(guideItem.fetched_at)} />
          </dl>
          <p>{t(($) => $.macroStorage.guide.periodNote)}</p>
          <p>{guideItem.revision_strategy === "latest_only"
            ? t(($) => $.macroStorage.guide.initialRelease)
            : guideItem.revision_strategy === "full_vintages"
              ? t(($) => $.macroStorage.guide.vintages)
              : t(($) => $.macroStorage.guide.revisionUnknown)}</p>
          <p>{t(($) => $.macroStorage.guide.interpretationNote)}</p>
          <a href={`https://fred.stlouisfed.org/series/${guideItem.series_id}`} target="_blank" rel="noreferrer">
            {t(($) => $.macroStorage.guide.source)}
          </a>
        </div> : null}
      </Drawer>
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
