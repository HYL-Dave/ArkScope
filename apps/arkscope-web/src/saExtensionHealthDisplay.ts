import type { SAExtensionHealthSegment } from "./api";

const ORDER = [
  "config",
  "manifests",
  "launcher",
  "host_ping",
  "telemetry_binding",
  "telemetry_last",
  "capture_readback",
];

const LABELS: Record<string, string> = {
  config: "設定檔",
  manifests: "瀏覽器註冊",
  launcher: "啟動器",
  host_ping: "主機測試",
  telemetry_binding: "遙測綁定",
  telemetry_last: "最近遙測",
  capture_readback: "資料回讀",
};

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
): SAExtensionHealthDisplayRow[] {
  const byKey = new Map(segments.map((segment) => [segment.key, segment]));
  const ordered = [
    ...ORDER.filter((key) => byKey.has(key)).map((key) => byKey.get(key)!),
    ...segments.filter((segment) => !ORDER.includes(segment.key)),
  ];
  return ordered.map((segment) => ({
    key: segment.key,
    label: LABELS[segment.key] ?? segment.key,
    mark: MARKS[segment.state] ?? "—",
    tone: segment.state,
    detail: segment.detail,
  }));
}
