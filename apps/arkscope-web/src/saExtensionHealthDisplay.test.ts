import { describe, expect, it } from "vitest";

import { displaySAExtensionSegments } from "./saExtensionHealthDisplay";
import type { SAExtensionHealthSegment } from "./api";

const seg = (key: string, state: SAExtensionHealthSegment["state"], detail = "detail"): SAExtensionHealthSegment => ({
  key,
  state,
  detail,
});

describe("displaySAExtensionSegments", () => {
  it("renders the fixed native-host chain order with zh labels and symbols", () => {
    const rows = displaySAExtensionSegments([
      seg("capture_readback", "warn", "尚未有第一次擷取"),
      seg("telemetry_binding", "ok", "config 綁定本次 sidecar"),
      seg("config", "ok", "設定檔有效"),
      seg("host_ping", "fail", "主機測試失敗"),
      seg("manifests", "ok", "Firefox manifest"),
      seg("launcher", "ok", "launcher 可執行"),
      seg("telemetry_last", "warn", "尚未有 telemetry"),
    ]);

    expect(rows.map((row) => row.label)).toEqual([
      "設定檔",
      "瀏覽器註冊",
      "啟動器",
      "主機測試",
      "遙測綁定",
      "最近遙測",
      "資料回讀",
    ]);
    expect(rows.map((row) => row.mark)).toEqual(["✓", "✓", "✓", "✗", "✓", "—", "—"]);
    expect(rows[3].detail).toBe("主機測試失敗");
  });

  it("keeps unknown segment keys visible", () => {
    const rows = displaySAExtensionSegments([seg("future_segment", "ok", "ok")]);

    expect(rows).toEqual([
      { key: "future_segment", label: "future_segment", mark: "✓", tone: "ok", detail: "ok" },
    ]);
  });
});
