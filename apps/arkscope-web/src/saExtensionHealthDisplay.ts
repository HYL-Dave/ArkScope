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
  "capture_readback",
];

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
  detail: string;
}

export function displaySAExtensionSegments(
  segments: SAExtensionHealthSegment[],
  t: SettingsT,
): SAExtensionHealthDisplayRow[] {
  const byKey = new Map(segments.map((segment) => [segment.key, segment]));
  const ordered = [
    ...ORDER.filter((key) => byKey.has(key)).map((key) => byKey.get(key)!),
    ...segments.filter((segment) => !ORDER.includes(segment.key)),
  ];
  return ordered.map((segment) => ({
    key: segment.key,
    label: saSegmentLabel(segment.key, t),
    mark: MARKS[segment.state] ?? "—",
    tone: segment.state,
    detail: segment.detail,
  }));
}
