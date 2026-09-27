import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { RefreshCw } from "lucide-react";
import { getNewsStatus, type NewsStatus } from "../api";
import { formatSystemTimestamp } from "../timeDisplay";
import { IconButton } from "../ui/Button";
import { DeveloperDiagnostics } from "./DeveloperDiagnostics";
import { providerName, settingsErrorPresentation } from "./settingsBackendCopy";
import type { SettingsT } from "./settingsCopy";
import type { SettingsReadCache } from "./settingsReadCache";

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

function ownNewsError(message: string | null | undefined, children: string[], repeated: string[]): string | null {
  let own = message?.trim() ?? "";
  // The status API appends the complete child summary to each parent error.
  // Remove only that exact suffix so independent run/storage failures survive.
  const summary = children.join("; ");
  if (own === summary) return null;
  if (summary && own.endsWith(`; ${summary}`)) own = own.slice(0, -summary.length - 2);
  return !own || repeated.includes(own) ? null : own;
}

function NewsIssue({ error, t }: { error: string; t: SettingsT }) {
  const unknown = error === "ibkr_news_completion_unknown";
  const incomplete = error === "ibkr_news_window_incomplete" || error === "ibkr_news_provider_window_incomplete";
  return <p data-news-issue className={unknown || incomplete ? "muted tiny" : "refresh-err tiny"}>
    {unknown ? t(($) => $.newsStorage.completenessUnknown)
      : error === "ibkr_news_subscription_denied" ? t(($) => $.newsStorage.subscriptionDenied)
      : error === "ibkr_news_request_timeout" ? t(($) => $.newsStorage.requestTimeout)
      : incomplete ? newsSyncStatusLabel("partial", t) : t(($) => $.newsStorage.collectionFailed)}
  </p>;
}

export function NewsStorageSection({
  developerMode = false,
  settingsReadCache,
}: {
  developerMode?: boolean;
  settingsReadCache: SettingsReadCache;
}) {
  const { t } = useTranslation("settings");
  const { t: commonT } = useTranslation("common");
  const [status, setStatus] = useState<NewsStatus | null>(() => {
    const inspected = settingsReadCache.inspect<NewsStatus>("news_status");
    return inspected.status === "missing" ? null : inspected.value;
  });
  const [err, setErr] = useState<Error | null>(null);

  const load = useCallback(async (force = false) => {
    const result = await settingsReadCache.load("news_status", getNewsStatus, { force });
    if (result.status === "success") {
      setStatus(result.value);
      setErr(null);
    } else if (result.status === "error") {
      setErr(result.error instanceof Error ? result.error : new Error(String(result.error)));
    }
  }, [settingsReadCache]);

  useEffect(() => {
    void load(false);
  }, [load]);
  useEffect(() => settingsReadCache.subscribeInvalidation(
    "news_status",
    () => { void load(false); },
  ), [load, settingsReadCache]);

  const sync = status?.sync;
  const providerStates = sync ? Object.entries(sync.providers) : [];
  const providers = providerStates.map(([provider, state]) => ({
    provider,
    state,
    error: ownNewsError(state.last_error,
      state.ticker_errors.map((issue) => `${issue.ticker}: ${issue.error}`),
      state.ticker_errors.map((issue) => issue.error)),
  }));
  const aggregateError = ownNewsError(sync?.last_error,
    providerStates.filter(([, state]) => state.last_error).map(([provider, state]) => `${provider}: ${state.last_error}`),
    providerStates.flatMap(([, state]) => state.last_error ? [state.last_error] : []));
  const diagnostics: Array<string | null> = [
    aggregateError,
    ...providers.flatMap(({ provider, state, error }) => [
      error ? `${provider}: ${error}` : null,
      ...state.ticker_errors.map((issue) => `${provider}/${issue.ticker}: ${issue.error}`),
    ]),
  ];
  const errorPresentation = err ? settingsErrorPresentation(err, t, commonT) : null;

  return (
    <div className="settings-news-data">
      <div className="settings-section-head">
        <div>
          <h2>{t(($) => $.newsStorage.title)}</h2>
          <p className="muted tiny">{t(($) => $.newsStorage.description)}</p>
        </div>
        <IconButton label={t(($) => $.actions.refreshStatus)} icon={<RefreshCw size={16} />}
          onClick={() => void load(true)} />
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
        <div>
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
            <dt>{t(($) => $.newsStorage.anyProviderSuccess)}</dt>
            <dd>{formatSystemTimestamp(sync?.last_success)}</dd>
            <dt>{t(($) => $.newsStorage.lastAttempt)}</dt>
            <dd>{formatSystemTimestamp(sync?.last_attempt)}</dd>
            <dt>{t(($) => $.newsStorage.collectionStatus)}</dt>
            <dd>{newsSyncStatusLabel(sync?.status ?? null, t)}</dd>
          </dl>
          <p className="muted tiny">{t(($) => $.newsStorage.freshnessScope)}</p>
          {aggregateError ? <NewsIssue error={aggregateError} t={t} /> : null}
          {providers.map(({ provider, state, error }) => {
            const name = providerName(provider === "polygon" ? "massive" : provider, t);
            return <section key={provider} data-news-provider={provider} aria-label={name}>
              <h3>{name}</h3>
              <dl className="ds-kv">
                <dt>{t(($) => $.newsStorage.collectionStatus)}</dt>
                <dd>{newsSyncStatusLabel(state.status, t)}</dd>
                <dt>{t(($) => $.newsStorage.lastAttempt)}</dt>
                <dd>{formatSystemTimestamp(state.last_attempt)}</dd>
                <dt>{t(($) => $.newsStorage.lastSuccess)}</dt>
                <dd>{formatSystemTimestamp(state.last_success)}</dd>
                <dt>{t(($) => $.newsStorage.latestRunCounts)}</dt>
                <dd>{t(($) => $.newsStorage.runCounts, { rows: state.rows_added, tickers: state.tickers_scanned })}</dd>
              </dl>
              {error ? <NewsIssue error={error} t={t} /> : null}
              {state.ticker_errors.length > 0 ? <details data-news-issues>
                <summary>{t(($) => $.newsStorage.tickerIssues)} ({state.ticker_errors.length})</summary>
                <ul>
                  {state.ticker_errors.map((issue) => <li key={issue.ticker} data-news-ticker={issue.ticker}>
                    <strong>{issue.ticker}</strong>{" "}
                    <span className="muted tiny">{formatSystemTimestamp(issue.updated_at)}</span>
                    <NewsIssue error={issue.error} t={t} />
                  </li>)}
                </ul>
              </details> : null}
            </section>;
          })}
          {developerMode ? <DeveloperDiagnostics diagnostics={diagnostics} t={t} /> : null}
        </div>
      )}
    </div>
  );
}
