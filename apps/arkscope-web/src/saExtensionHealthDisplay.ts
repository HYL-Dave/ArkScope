import type { SAExtensionHealthSegment } from "./api";
import { saSegmentLabel } from "./settings/settingsBackendCopy";
import type { SettingsT } from "./settings/settingsCopy";

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

const STABLE_CODE = /^[a-z][a-z0-9_]{0,63}$/;
const HASH_PREFIX = /^[a-f0-9]{8,12}$/;

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
    case "detail_failures_recorded": {
      const failed = count(segment, "failed_retryable");
      value = failed === 1
        ? t(($) => $.dataSources.extension.status.detailFailuresRecorded_one, { count: failed })
        : t(($) => $.dataSources.extension.status.detailFailuresRecorded_other, { count: failed });
      break;
    }
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
    const safeCode = typeof segment.code === "string" && STABLE_CODE.test(segment.code)
      ? segment.code
      : null;
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
          : safeCode
            ? t(($) => $.dataSources.extension.status.developerCode, { code: safeCode })
            : null
        : null,
      showDetail: !isSetup,
    };
  });
}
