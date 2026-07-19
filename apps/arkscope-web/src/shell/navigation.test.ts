import { describe, expect, it } from "vitest";

import {
  SHELL_NAV_GROUPS,
  nextNavigationRequest,
  resolveNavigationTarget,
} from "./navigation";
import { SETTINGS_ANCHOR_IDS } from "../settings/settingsRegistry";

describe("shell navigation authority", () => {
  it("publishes the approved four workflow groups in canonical order", () => {
    expect(SHELL_NAV_GROUPS.map((group) => [
      group.label,
      group.items.map((item) => [item.view, item.label]),
    ])).toEqual([
      ["探索", [["Home", "工作台"], ["Watchlist", "自選股"], ["Universe", "全部標的"], ["News", "新聞·事件"]]],
      ["研究", [["Research", "AI 研究"]]],
      ["追蹤", [["Holdings", "持倉"]]],
      ["系統", [["System", "System / Health"], ["Settings", "設定"]]],
    ]);
  });

  it("contains every shipped view exactly once", () => {
    const views = SHELL_NAV_GROUPS.flatMap((group) => group.items.map((item) => item.view));

    expect(views).toEqual([
      "Home",
      "Watchlist",
      "Universe",
      "News",
      "Research",
      "Holdings",
      "System",
      "Settings",
    ]);
    expect(new Set(views).size).toBe(views.length);
  });

  it("does not publish Notes or Alerts as planned controls", () => {
    expect(JSON.stringify(SHELL_NAV_GROUPS)).not.toMatch(/Notes|Alerts|研究筆記|告警/);
    expect(SHELL_NAV_GROUPS.every(
      (group) => group.items.every((item) => !("enabled" in item)),
    )).toBe(true);
  });

  it("resolves a ticker target to ticker detail without inventing a nav item", () => {
    const request = nextNavigationRequest(4, { kind: "ticker", ticker: " nvda " });

    expect(resolveNavigationTarget(request)).toEqual({ ticker: "NVDA" });
  });

  it("resolves Research and Settings targets to their owning shipped views", () => {
    const research = nextNavigationRequest(7, {
      kind: "research_thread",
      threadId: "thread-1",
      runId: "run-1",
    });
    expect(resolveNavigationTarget(research)).toEqual({
      view: "Research",
      research,
    });
    for (const section of SETTINGS_ANCHOR_IDS) {
      const settings = nextNavigationRequest(8, {
        kind: "settings_section",
        section,
      });
      expect(resolveNavigationTarget(settings)).toEqual({
        view: "Settings",
        settings,
      });
    }
  });

  it("increments the request sequence even when the exact target repeats", () => {
    const target = { kind: "view", view: "Holdings" } as const;
    const first = nextNavigationRequest(0, target);
    const second = nextNavigationRequest(first.sequence, target);

    expect(first).toEqual({ sequence: 1, target });
    expect(second).toEqual({ sequence: 2, target });
    expect(resolveNavigationTarget(second)).toEqual({ view: "Holdings" });
  });
});
