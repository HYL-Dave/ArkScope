import { describe, expect, it } from "vitest";

import { routeSourceBadge, routeIsOverridable } from "./modelRouteDisplay";

describe("routeSourceBadge", () => {
  it("labels DB authority as the saved/active app setting", () => {
    expect(routeSourceBadge("db")).toEqual({ label: "DB（已儲存）", tone: "active" });
  });
  it("labels yaml profile as a fallback, not the live authority", () => {
    expect(routeSourceBadge("profile")).toEqual({ label: "設定檔 fallback", tone: "fallback" });
  });
  it("labels an env var as an operator override that outranks the DB", () => {
    expect(routeSourceBadge("env")).toEqual({ label: "env 覆蓋", tone: "override" });
  });
  it("labels default as the built-in seed", () => {
    expect(routeSourceBadge("default")).toEqual({ label: "內建預設", tone: "default" });
  });
});

describe("routeIsOverridable", () => {
  it("only a DB-authoritative route can be reset (there is a DB row to remove)", () => {
    expect(routeIsOverridable("db")).toBe(true);
  });
  it("yaml/default/env routes have no DB row → nothing to reset", () => {
    expect(routeIsOverridable("profile")).toBe(false);
    expect(routeIsOverridable("default")).toBe(false);
    expect(routeIsOverridable("env")).toBe(false);
  });
});
