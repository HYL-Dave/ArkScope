import {
  ApiError,
  type ProviderStatus,
  type ScheduleRunResult,
} from "../api";
import type { SettingsT } from "./settingsCopy";

export type SettingsErrorPresentation = {
  message: string;
  code: string | null;
  diagnostic: string | null;
};

export type ScheduleBodyBacklogPresentation = {
  label: string;
  tone: "muted" | "warn";
  earliestNextRetryAt: string | null;
};

function providerConfigErrorMessage(code: string, t: SettingsT): string | null {
  switch (code) {
    case "provider_config_setup_required":
      return t(($) => $.dataSources.providers.config.setupRequired);
    case "provider_config_missing":
      return t(($) => $.dataSources.providers.config.missing);
    case "provider_config_change_guard":
      return t(($) => $.dataSources.providers.config.guardConsequence);
    case "provider_config_invalid_value":
    case "provider_config_import_source_invalid":
    case "provider_config_import_source_missing":
      return t(($) => $.errors.mutationFailed);
    default:
      return null;
  }
}

function knownModelReasonLabel(id: string, t: SettingsT): string | null {
  switch (id) {
    case "missing_active_credential":
      return t(($) => $.models.credentials.missing);
    case "task_auth_mode_unsupported":
      return t(($) => $.models.compatibility.unsupported);
    case "task_test_unsupported":
      return t(($) => $.models.test.unsupported);
    case "task_capability_missing":
      return t(($) => $.models.compatibility.missingCapability);
    case "model_not_visible":
      return t(($) => $.models.compatibility.modelNotVisible);
    case "model_not_in_registry":
      return t(($) => $.models.custom.unknown);
    case "discovery_unavailable":
      return t(($) => $.models.catalog.unavailable);
    case "provider_call_failed":
      return t(($) => $.models.test.failed);
    case "reauth_required":
      return t(($) => $.providers.openAI.tokenExpired);
    default:
      return null;
  }
}

export function modelReasonLabel(id: string, t: SettingsT): string {
  return knownModelReasonLabel(id, t) ?? id;
}

function apiErrorMessage(code: string, t: SettingsT): string {
  const providerMessage = providerConfigErrorMessage(code, t);
  if (providerMessage) return providerMessage;
  const modelMessage = knownModelReasonLabel(code, t);
  if (modelMessage) return modelMessage;
  switch (code) {
    case "invalid_investor_profile":
      return t(($) => $.investor.invalid);
    case "sa_extension_health_unavailable":
      return t(($) => $.dataSources.extension.interrupted);
    default:
      return t(($) => $.errors.unknown, { value: code });
  }
}

function backlogCount(value: unknown): number | null {
  if (value === undefined) return 0;
  return typeof value === "number" && Number.isInteger(value) && value >= 0
    ? value
    : null;
}

export function scheduleBodyBacklogCopy(
  result: ScheduleRunResult | null,
  t: SettingsT,
): ScheduleBodyBacklogPresentation | null {
  const backlog = result?.collect?.body_backlog;
  if (!backlog) return null;
  if (backlog.status !== "ok") {
    return {
      label: t(($) => $.dataSources.schedule.backlog.unavailable),
      tone: "warn",
      earliestNextRetryAt: null,
    };
  }

  const due = backlogCount(backlog.due_now);
  const never = backlogCount(backlog.never_attempted);
  const scheduled = backlogCount(backlog.scheduled_later);
  const notEntitled = backlogCount(backlog.provider_not_entitled);
  if (
    due === null
    || never === null
    || scheduled === null
    || notEntitled === null
    || never > due
  ) {
    return {
      label: t(($) => $.dataSources.schedule.backlog.unavailable),
      tone: "warn",
      earliestNextRetryAt: null,
    };
  }

  if (due === 0 && scheduled === 0 && notEntitled === 0) return null;

  const copy: string[] = [];
  if (due > 0) {
    copy.push(never > 0
      ? t(($) => $.dataSources.schedule.backlog.dueWithNever, {
          count: due,
          value: never,
        })
      : t(($) => $.dataSources.schedule.backlog.due, { count: due }));
  }
  if (scheduled > 0) {
    copy.push(t(($) => $.dataSources.schedule.backlog.scheduled, { count: scheduled }));
  }
  if (notEntitled > 0) {
    copy.push(t(($) => $.dataSources.schedule.backlog.notEntitled, { count: notEntitled }));
  }
  return {
    label: t(($) => $.dataSources.schedule.backlog.queue, {
      value: copy.join(" · "),
    }),
    tone: "muted",
    earliestNextRetryAt: typeof backlog.earliest_next_retry_at === "string"
      ? backlog.earliest_next_retry_at
      : null,
  };
}

export function settingsErrorPresentation(
  error: unknown,
  t: SettingsT,
): SettingsErrorPresentation {
  if (error instanceof ApiError) {
    return {
      message: error.code
        ? apiErrorMessage(error.code, t)
        : t(($) => $.errors.requestFailed),
      code: error.code,
      diagnostic: error.diagnostic,
    };
  }
  return {
    message: t(($) => $.errors.requestFailed),
    code: null,
    diagnostic: error instanceof Error ? error.message : null,
  };
}

export function providerName(id: string, t: SettingsT): string {
  switch (id) {
    case "polygon":
      return t(($) => $.dataSources.providers.names.polygon);
    case "finnhub":
      return t(($) => $.dataSources.providers.names.finnhub);
    case "fred":
      return t(($) => $.dataSources.providers.names.fred);
    case "financial_datasets":
      return t(($) => $.dataSources.providers.names.financialDatasets);
    case "ibkr":
      return t(($) => $.dataSources.providers.names.ibkr);
    case "sec_edgar":
      return t(($) => $.dataSources.providers.names.secEdgar);
    case "seeking_alpha":
      return t(($) => $.dataSources.providers.names.seekingAlpha);
    default:
      return id;
  }
}

export function providerConfigFieldLabel(
  provider: string,
  field: string,
  t: SettingsT,
): string {
  switch (provider) {
    case "polygon":
    case "finnhub":
    case "fred":
    case "financial_datasets":
      if (field === "api_key") return t(($) => $.dataSources.providers.fields.apiKey);
      break;
    case "ibkr":
      switch (field) {
        case "host":
          return t(($) => $.dataSources.providers.fields.gatewayHost);
        case "port":
          return t(($) => $.dataSources.providers.fields.gatewayPort);
        case "client_id":
          return t(($) => $.dataSources.providers.fields.clientId);
      }
      break;
    case "sec_edgar":
      if (field === "user_agent") {
        return t(($) => $.dataSources.providers.fields.contactEmail);
      }
      break;
  }
  return [provider, field].join(".");
}

export function providerKeySourceLabel(source: string, t: SettingsT): string {
  switch (source) {
    case "app":
      return t(($) => $.dataSources.labels.app);
    case "env":
      return t(($) => $.dataSources.labels.environment);
    case "config/.env":
      return source;
    case "missing":
      return t(($) => $.dataSources.providers.health.notConfigured);
    case "mixed":
      return t(($) => $.dataSources.labels.mixedSources);
    case "not_required":
      return t(($) => $.dataSources.labels.noKey);
    default:
      return source;
  }
}

export function providerClientDomainLabel(domain: string, t: SettingsT): string {
  switch (domain) {
    case "manual":
      return t(($) => $.dataSources.providers.clientDomains.manual);
    case "options":
      return t(($) => $.dataSources.providers.clientDomains.options);
    case "prices":
      return t(($) => $.dataSources.providers.clientDomains.prices);
    case "news":
      return t(($) => $.dataSources.providers.clientDomains.news);
    case "iv":
      return t(($) => $.dataSources.providers.clientDomains.iv);
    case "quotes":
      return t(($) => $.dataSources.providers.clientDomains.quotes);
    case "holdings":
      return t(($) => $.dataSources.providers.clientDomains.holdings);
    case "portfolio_capture":
      return t(($) => $.dataSources.providers.clientDomains.portfolioCapture);
    default:
      return domain;
  }
}

export function providerHealthCopy(
  id: string,
  status: ProviderStatus,
  t: SettingsT,
): { label: string; detail: string } {
  let label: string;
  switch (status) {
    case "connected":
      label = t(($) => $.dataSources.providers.health.connected);
      break;
    case "stale":
      label = t(($) => $.dataSources.providers.health.stale);
      break;
    case "maintenance":
      label = t(($) => $.dataSources.providers.health.maintenance);
      break;
    case "no_signal":
      label = t(($) => $.dataSources.providers.health.noSignal);
      break;
    case "not_configured":
      label = t(($) => $.dataSources.providers.health.notConfigured);
      break;
    case "missing_key":
      label = t(($) => $.dataSources.providers.health.missingKey);
      break;
    case "disabled":
      label = t(($) => $.dataSources.providers.health.disabled);
      break;
  }
  return {
    label,
    detail: t(($) => $.dataSources.providers.health.detail, {
      providerId: providerName(id, t),
      value: label,
    }),
  };
}

export function providerTestCopy(
  id: string,
  ok: boolean | null,
  t: SettingsT,
): string {
  const providerId = providerName(id, t);
  if (ok === true) {
    return t(($) => $.dataSources.providers.test.passed, { providerId });
  }
  if (ok === false) {
    return t(($) => $.dataSources.providers.test.failed, { providerId });
  }
  return t(($) => $.dataSources.providers.test.unavailable, { providerId });
}

export function scheduleSourceCopy(
  id: string,
  t: SettingsT,
): { label: string; description: string } {
  switch (id) {
    case "polygon_news":
      return {
        label: t(($) => $.dataSources.schedule.sources.polygonNews.label),
        description: t(($) => $.dataSources.schedule.sources.polygonNews.description),
      };
    case "finnhub_news":
      return {
        label: t(($) => $.dataSources.schedule.sources.finnhubNews.label),
        description: t(($) => $.dataSources.schedule.sources.finnhubNews.description),
      };
    case "ibkr_news":
      return {
        label: t(($) => $.dataSources.schedule.sources.ibkrNews.label),
        description: t(($) => $.dataSources.schedule.sources.ibkrNews.description),
      };
    case "ibkr_prices":
      return {
        label: t(($) => $.dataSources.schedule.sources.ibkrPrices.label),
        description: t(($) => $.dataSources.schedule.sources.ibkrPrices.description),
      };
    case "iv_history":
      return {
        label: t(($) => $.dataSources.schedule.sources.ivHistory.label),
        description: t(($) => $.dataSources.schedule.sources.ivHistory.description),
      };
    case "local_incremental":
      return {
        label: t(($) => $.dataSources.schedule.sources.localIncremental.label),
        description: t(($) => $.dataSources.schedule.sources.localIncremental.description),
      };
    case "price_backfill":
      return {
        label: t(($) => $.dataSources.schedule.sources.priceBackfill.label),
        description: t(($) => $.dataSources.schedule.sources.priceBackfill.description),
      };
    default:
      return {
        label: id,
        description: t(($) => $.dataSources.schedule.unknownSourceDescription, {
          sourceId: id,
        }),
      };
  }
}

export function scheduleOutcomeCopy(
  source: string,
  result: ScheduleRunResult | null,
  t: SettingsT,
): string {
  const sourceId = scheduleSourceCopy(source, t).label;
  let outcome: string;
  if (!result) {
    outcome = t(($) => $.dataSources.schedule.history.notRun);
  } else {
    switch (result.status) {
      case "running":
        outcome = t(($) => $.dataSources.schedule.history.running);
        break;
      case "succeeded":
        outcome = t(($) => $.dataSources.schedule.history.succeeded);
        break;
      case "partial":
        outcome = t(($) => $.dataSources.schedule.history.partial);
        break;
      case "failed":
        outcome = t(($) => $.dataSources.schedule.history.failed);
        break;
      case "skipped":
        outcome = t(($) => $.dataSources.schedule.history.skipped);
        break;
      default:
        outcome = t(($) => $.dataSources.schedule.history.unknown, {
          value: result.status,
        });
        break;
    }
  }
  return t(($) => $.dataSources.schedule.history.withSource, {
    sourceId,
    value: outcome,
  });
}

export function saSegmentLabel(key: string, t: SettingsT): string {
  switch (key) {
    case "config":
      return t(($) => $.dataSources.extension.segments.config);
    case "manifests":
      return t(($) => $.dataSources.extension.segments.manifests);
    case "launcher":
      return t(($) => $.dataSources.extension.segments.launcher);
    case "host_ping":
      return t(($) => $.dataSources.extension.segments.hostPing);
    case "telemetry_binding":
      return t(($) => $.dataSources.extension.segments.telemetryBinding);
    case "telemetry_last":
      return t(($) => $.dataSources.extension.segments.telemetryLast);
    case "capture_readback":
      return t(($) => $.dataSources.extension.segments.captureReadback);
    default:
      return key;
  }
}

export function diagnosticValue(
  developerMode: boolean,
  value: unknown,
): string | null {
  if (!developerMode) return null;
  if (value instanceof Error) return value.message.trim() || null;
  if (typeof value === "string") return value.trim() || null;
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  if (typeof value === "boolean") return String(value);
  return null;
}
