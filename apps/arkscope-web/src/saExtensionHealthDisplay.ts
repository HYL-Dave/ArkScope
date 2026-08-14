import type {
  SAExtensionDiagnosticEntry,
  SAExtensionDiagnosticRecurrence,
  SAExtensionHealthSegment,
  SAExtensionJobName,
} from "./api";
import { saSegmentLabel } from "./settings/settingsBackendCopy";
import type { SettingsT } from "./settings/settingsCopy";
import { formatSystemTimestamp } from "./timeDisplay";

const ORDER = [
  "config",
  "manifests",
  "launcher",
  "host_ping",
  "telemetry_binding",
  "telemetry_last",
  "market_news_repair",
  "capture_readback",
];

const SETUP_SEGMENTS = new Set([
  "config",
  "manifests",
  "launcher",
  "host_ping",
  "telemetry_binding",
  "capture_readback",
]);

const HASH_PREFIX = /^[a-f0-9]{8,12}$/;
const TARGET_REF = /^[A-Za-z0-9._:-]{1,128}$/;

const MARKS: Record<SAExtensionHealthSegment["state"], string> = {
  ok: "✓",
  warn: "—",
  fail: "✗",
};

export interface SAExtensionHealthDisplayRow {
  key: string;
  label: string;
  mark: string;
  tone: SAExtensionHealthSegment["state"];
  copy: string;
  diagnostic: string | null;
  showDetail: boolean;
}

function count(segment: SAExtensionHealthSegment, key: string): number {
  const value = segment.counts?.[key];
  return typeof value === "number" && Number.isFinite(value) && value >= 0
    ? Math.floor(value)
    : 0;
}

function safePositiveInteger(value: unknown, maximum: number): number | null {
  return typeof value === "number"
    && Number.isInteger(value)
    && value >= 0
    && value <= maximum
    ? value
    : null;
}

function safeTimestamp(value: unknown): string | null {
  if (typeof value !== "string" || value.length > 64) return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : formatSystemTimestamp(value);
}

function workloadLabel(value: unknown, t: SettingsT): string | null {
  switch (value) {
    case "sa_alpha_picks_refresh":
      return t(($) => $.dataSources.extension.workloads.alphaPicks);
    case "sa_market_news_refresh":
      return t(($) => $.dataSources.extension.workloads.marketNews);
    default:
      return null;
  }
}

function stageLabel(value: unknown, t: SettingsT): string | null {
  switch (value) {
    case "tab_navigation": return t(($) => $.dataSources.extension.stages.tabNavigation);
    case "page_readiness": return t(($) => $.dataSources.extension.stages.pageReadiness);
    case "script_injection": return t(($) => $.dataSources.extension.stages.scriptInjection);
    case "content_parse": return t(($) => $.dataSources.extension.stages.contentParse);
    case "native_transport": return t(($) => $.dataSources.extension.stages.nativeTransport);
    case "local_persistence": return t(($) => $.dataSources.extension.stages.localPersistence);
    case "reconciliation": return t(($) => $.dataSources.extension.stages.reconciliation);
    case "extension_runtime": return t(($) => $.dataSources.extension.stages.extensionRuntime);
    default: return null;
  }
}

function reasonLabel(value: unknown, t: SettingsT): string | null {
  switch (value) {
    case "access_restricted": return t(($) => $.dataSources.extension.reasons.accessRestricted);
    case "login_required": return t(($) => $.dataSources.extension.reasons.loginRequired);
    case "modal_blocked": return t(($) => $.dataSources.extension.reasons.modalBlocked);
    case "navigation_timeout": return t(($) => $.dataSources.extension.reasons.navigationTimeout);
    case "detail_timeout": return t(($) => $.dataSources.extension.reasons.detailTimeout);
    case "dom_not_ready": return t(($) => $.dataSources.extension.reasons.domNotReady);
    case "parser_empty": return t(($) => $.dataSources.extension.reasons.parserEmpty);
    case "native_host_unavailable": return t(($) => $.dataSources.extension.reasons.nativeHostUnavailable);
    case "extension_dependency_missing": return t(($) => $.dataSources.extension.reasons.extensionDependencyMissing);
    case "reconciliation_failed": return t(($) => $.dataSources.extension.reasons.reconciliationFailed);
    case "comment_scan_failed": return t(($) => $.dataSources.extension.reasons.commentScanFailed);
    case "unknown_failure": return t(($) => $.dataSources.extension.reasons.unknownFailure);
    case "tab_closed": return t(($) => $.dataSources.extension.reasons.tabClosed);
    case "browser_api_failed": return t(($) => $.dataSources.extension.reasons.browserApiFailed);
    case "script_injection_failed": return t(($) => $.dataSources.extension.reasons.scriptInjectionFailed);
    case "native_response_invalid": return t(($) => $.dataSources.extension.reasons.nativeResponseInvalid);
    case "database_busy": return t(($) => $.dataSources.extension.reasons.databaseBusy);
    case "database_integrity_failed": return t(($) => $.dataSources.extension.reasons.databaseIntegrityFailed);
    case "database_write_failed": return t(($) => $.dataSources.extension.reasons.databaseWriteFailed);
    default: return null;
  }
}

function safeTarget(value: unknown): string | null {
  switch (value) {
    case "article_detail":
    case "article_comments":
    case "market_news_detail":
    case "phase":
      return value;
    default:
      return null;
  }
}

function admittedDiagnostic(
  value: SAExtensionDiagnosticEntry,
  t: SettingsT,
): {
  entry: SAExtensionDiagnosticEntry;
  stage: string;
  reason: string;
  target: string;
  occurredAt: string;
  attemptCount: number;
} | null {
  const stage = stageLabel(value?.stage, t);
  const reason = reasonLabel(value?.reason_code, t);
  const targetKind = safeTarget(value?.target_kind);
  const occurredAt = safeTimestamp(value?.occurred_at);
  const attemptCount = safePositiveInteger(value?.attempt_count, 1000);
  if (
    !stage
    || !reason
    || !targetKind
    || !occurredAt
    || attemptCount === null
    || attemptCount < 1
    || typeof value?.retryable !== "boolean"
  ) return null;
  const targetRef = typeof value.target_ref === "string" && TARGET_REF.test(value.target_ref)
    ? value.target_ref
    : null;
  return {
    entry: value,
    stage,
    reason,
    target: targetRef ? `${targetKind} (${targetRef})` : targetKind,
    occurredAt,
    attemptCount,
  };
}

function admittedDiagnostics(
  segment: SAExtensionHealthSegment,
  t: SettingsT,
) {
  if (segment.diagnostics_status !== "recorded" || !Array.isArray(segment.diagnostics)) {
    return [];
  }
  return segment.diagnostics
    .slice(0, 32)
    .map((entry) => admittedDiagnostic(entry, t))
    .filter((entry): entry is NonNullable<typeof entry> => entry !== null);
}

function captureCounts(segment: SAExtensionHealthSegment, t: SettingsT): string | null {
  if (!segment.counts || typeof segment.counts !== "object") return null;
  const total = count(segment, "item_total");
  const retryable = count(segment, "failed_retryable");
  const complete = total > 0
    ? Math.max(0, total - retryable)
    : count(segment, "repaired") + count(segment, "already_present");
  if (total === 0 && retryable === 0 && complete === 0) return null;
  return t(($) => $.dataSources.extension.status.captureCounts, {
    complete,
    retryable,
    total,
  });
}

function diagnosticCopy(segment: SAExtensionHealthSegment, t: SettingsT): string | null {
  if (segment.diagnostics_status === "rejected") {
    return t(($) => $.dataSources.extension.status.diagnosticsRejected);
  }
  if (
    segment.diagnostics_status === "absent"
    && (segment.outcome === "degraded" || segment.outcome === "failed")
  ) {
    return t(($) => $.dataSources.extension.status.legacyCauseAbsent);
  }
  const latest = admittedDiagnostics(segment, t).at(-1);
  return latest ? `${latest.stage} · ${latest.reason}` : null;
}

function captureContext(segment: SAExtensionHealthSegment, t: SettingsT): string[] {
  const parts: string[] = [];
  const workload = workloadLabel(segment.job_name, t);
  const occurredAt = safeTimestamp(segment.occurred_at);
  if (workload) parts.push(workload);
  if (occurredAt) parts.push(occurredAt);
  return parts;
}

function recurrenceDiagnostic(
  value: SAExtensionDiagnosticRecurrence,
  t: SettingsT,
): string | null {
  const workload = workloadLabel(value?.job_name, t);
  const stage = stageLabel(value?.stage, t);
  const reason = reasonLabel(value?.reason_code, t);
  const affected = safePositiveInteger(value?.affected_run_count, 20);
  const occurredAt = safeTimestamp(value?.latest_occurred_at);
  if (!workload || !stage || !reason || affected === null || affected < 1 || !occurredAt) {
    return null;
  }
  return t(($) => $.dataSources.extension.developer.recurrence, {
    value: `${workload} / ${stage} / ${reason} / ${affected} / ${occurredAt}`,
  });
}

function developerDiagnostic(segment: SAExtensionHealthSegment, t: SettingsT): string | null {
  if (segment.diagnostics_status !== "recorded") return null;
  const values: string[] = [];
  const workload = workloadLabel(segment.job_name, t);
  if (workload) {
    values.push(t(($) => $.dataSources.extension.developer.jobName, { value: workload }));
  }
  for (const item of admittedDiagnostics(segment, t)) {
    values.push(t(($) => $.dataSources.extension.developer.stage, { value: item.stage }));
    values.push(t(($) => $.dataSources.extension.developer.reason, { value: item.reason }));
    values.push(t(($) => $.dataSources.extension.developer.target, { value: item.target }));
    values.push(t(($) => $.dataSources.extension.developer.occurredAt, { value: item.occurredAt }));
    values.push(t(($) => $.dataSources.extension.developer.retryable, {
      value: String(item.entry.retryable),
    }));
    values.push(t(($) => $.dataSources.extension.developer.attemptCount, {
      value: item.attemptCount,
    }));
  }
  const omitted = safePositiveInteger(segment.diagnostics_omitted_count, 10_000);
  if (omitted !== null && omitted > 0) {
    values.push(t(($) => $.dataSources.extension.developer.omittedCount, { value: omitted }));
  }
  if (Array.isArray(segment.diagnostic_recurrence)) {
    for (const item of segment.diagnostic_recurrence.slice(0, 640)) {
      const recurrence = recurrenceDiagnostic(item, t);
      if (recurrence) values.push(recurrence);
    }
  }
  return values.length > 0 ? values.join(" · ") : null;
}

function structuredDetail(
  segment: SAExtensionHealthSegment,
  t: SettingsT,
): string {
  const status = segment.code;
  let value: string;
  switch (status) {
    case "capture_complete":
      value = t(($) => $.dataSources.extension.status.captureComplete);
      break;
    case "capture_skipped":
      value = t(($) => $.dataSources.extension.status.captureSkipped);
      break;
    case "capture_degraded":
      value = t(($) => $.dataSources.extension.status.captureDegraded);
      break;
    case "capture_failed":
      value = t(($) => $.dataSources.extension.status.captureFailed);
      break;
    case "telemetry_not_recorded":
      value = t(($) => $.dataSources.extension.status.telemetryNotRecorded);
      break;
    case "repair_active":
      value = t(($) => $.dataSources.extension.status.repairActive);
      break;
    case "repair_complete":
      value = t(($) => $.dataSources.extension.status.repairComplete);
      break;
    case "repair_retryable": {
      const failed = count(segment, "failed_retryable");
      value = failed === 1
        ? t(($) => $.dataSources.extension.status.repairRetryable_one, { count: failed })
        : t(($) => $.dataSources.extension.status.repairRetryable_other, { count: failed });
      break;
    }
    default:
      value = t(($) => $.dataSources.extension.status.unknownWarning);
      break;
  }

  if (
    status === "capture_complete"
    || status === "capture_skipped"
    || status === "capture_degraded"
    || status === "capture_failed"
  ) {
    const context = captureContext(segment, t);
    const counts = captureCounts(segment, t);
    const cause = diagnosticCopy(segment, t);
    value = [...context, value, ...(counts ? [counts] : []), ...(cause ? [cause] : [])]
      .join(" · ");
    const omitted = safePositiveInteger(segment.diagnostics_omitted_count, 10_000);
    if (segment.diagnostics_status === "recorded" && omitted !== null && omitted > 0) {
      value += ` · ${t(($) => $.dataSources.extension.status.additionalDiagnostics, { count: omitted })}`;
    }
  } else if (status?.startsWith("repair_")) {
    const occurredAt = safeTimestamp(segment.occurred_at);
    if (occurredAt) value += ` · ${occurredAt}`;
  }

  const prefix = segment.manifest_hash_prefix?.toLowerCase();
  if (prefix && HASH_PREFIX.test(prefix)) {
    value += ` · ${t(($) => $.dataSources.extension.status.manifestPrefix, { hash: prefix })}`;
  }
  return value;
}

export function displaySAExtensionSegments(
  segments: SAExtensionHealthSegment[],
  t: SettingsT,
  developerMode = false,
): SAExtensionHealthDisplayRow[] {
  const byKey = new Map(segments.map((segment) => [segment.key, segment]));
  const ordered = [
    ...ORDER.filter((key) => byKey.has(key)).map((key) => byKey.get(key)!),
    ...segments.filter((segment) => !ORDER.includes(segment.key)),
  ];
  return ordered.map((segment) => {
    const isSetup = SETUP_SEGMENTS.has(segment.key) && !segment.code;
    return {
      key: segment.key,
      label: saSegmentLabel(segment.key, t),
      mark: MARKS[segment.state] ?? "—",
      tone: segment.state,
      copy: isSetup
        ? String(segment.detail ?? "")
        : structuredDetail(segment, t),
      diagnostic: developerMode
        ? isSetup
          ? String(segment.detail ?? "").trim() || null
          : developerDiagnostic(segment, t)
        : null,
      showDetail: !isSetup,
    };
  });
}
