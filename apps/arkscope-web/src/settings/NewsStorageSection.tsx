import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { getNewsStatus, type NewsStatus } from "../api";
import { formatSystemTimestamp } from "../timeDisplay";
import { DeveloperDiagnostics } from "./DeveloperDiagnostics";
import { settingsErrorPresentation } from "./settingsBackendCopy";
import type { SettingsT } from "./settingsCopy";

function newsSyncStatusLabel(status: NonNullable<NewsStatus["sync"]>["status"] | null, t: SettingsT) {
  switch (status) {
    case "running":
      return t(($) => $.dataSources.schedule.history.running);
    case "succeeded":
      return t(($) => $.dataSources.schedule.history.succeeded);
    case "failed":
      return t(($) => $.dataSources.schedule.history.failed);
    case "partial":
      return t(($) => $.dataSources.schedule.history.partial);
    case null:
      return t(($) => $.newsStorage.neverRun);
  }
}

export function NewsStorageSection({
  developerMode = false,
}: {
  developerMode?: boolean;
}) {
  const { t } = useTranslation("settings");
  const [status, setStatus] = useState<NewsStatus | null>(null);
  const [err, setErr] = useState<Error | null>(null);

  const load = useCallback(async () => {
    try {
      setStatus(await getNewsStatus());
      setErr(null);
    } catch (e) {
      setErr(e instanceof Error ? e : new Error(String(e)));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const sync = status?.sync;
  const providerStates = sync ? Object.entries(sync.providers) : [];
  const hasSyncErrors = Boolean(
    sync?.last_error
    || providerStates.some(([, provider]) => provider.last_error || provider.ticker_errors.length),
  );
  const diagnostics: Array<string | null> = [
    sync?.last_error ?? null,
    ...providerStates.flatMap(([provider, state]) => [
      state.last_error ? `${provider}: ${state.last_error}` : null,
      ...state.ticker_errors.map((error) => `${provider}/${error.ticker}: ${error.error}`),
    ]),
  ];
  const errorPresentation = err ? settingsErrorPresentation(err, t) : null;

  return (
    <div>
      <div className="settings-section-head">
        <div>
          <h2>{t(($) => $.newsStorage.title)}</h2>
          <p className="muted tiny">{t(($) => $.newsStorage.description)}</p>
        </div>
        <button className="btn-ghost" onClick={() => void load()}>
          ↻ {t(($) => $.actions.refresh)}
        </button>
      </div>

      {errorPresentation ? (
        <div className="errorbox"><p className="muted">{errorPresentation.message}</p></div>
      ) : null}
      {developerMode ? (
        <DeveloperDiagnostics diagnostics={[errorPresentation?.diagnostic]} t={t} />
      ) : null}

      {!status ? (
        <p className="muted">{t(($) => $.newsStorage.loading)}</p>
      ) : (
        <div className="settings-panel">
          <dl className="ds-kv">
            <dt>{t(($) => $.newsStorage.title)}</dt>
            <dd>
              {status.exists
                ? t(($) => $.newsStorage.available, {
                    value: status.news.row_count.toLocaleString(),
                    count: status.news.source_count,
                    timestamp: status.news.latest_published ?? "—",
                  })
                : t(($) => $.newsStorage.empty)}
            </dd>
            <dt>{t(($) => $.newsStorage.lastSuccess)}</dt>
            <dd>{formatSystemTimestamp(sync?.last_success)}</dd>
            <dt>{t(($) => $.newsStorage.lastAttempt)}</dt>
            <dd>{formatSystemTimestamp(sync?.last_attempt)}</dd>
            <dt>{t(($) => $.newsStorage.collectionStatus)}</dt>
            <dd>{newsSyncStatusLabel(sync?.status ?? null, t)}</dd>
            <dt>{t(($) => $.newsStorage.lastError)}</dt>
            <dd className={hasSyncErrors ? "refresh-err" : undefined}>
              {hasSyncErrors ? t(($) => $.errors.requestFailed) : "—"}
            </dd>
          </dl>
          {developerMode ? <DeveloperDiagnostics diagnostics={diagnostics} t={t} /> : null}
        </div>
      )}
    </div>
  );
}
