/** @vitest-environment jsdom */
import { describe, expect, it, vi } from "vitest";
import {
  SHELL_OVERLAY_BREAKPOINT_PX,
  UI_TOKENS,
  installUiTokens,
  shellOverlayMediaQuery,
} from "./tokens";
import { shellOverlayMatches } from "./useShellOverlay";

describe("canonical UI tokens", () => {
  it("pins the sole shell breakpoint and general radius cap", () => {
    expect(SHELL_OVERLAY_BREAKPOINT_PX).toBe(960);
    expect(Object.keys(UI_TOKENS.radiusPx)).toEqual(["xs", "sm", "md", "pill"]);
    expect(Math.max(
      UI_TOKENS.radiusPx.xs,
      UI_TOKENS.radiusPx.sm,
      UI_TOKENS.radiusPx.md,
    )).toBeLessThanOrEqual(8);
    expect(UI_TOKENS.radiusPx.pill).toBeGreaterThan(8);
    expect("lg" in UI_TOKENS.radiusPx).toBe(false);
  });

  it("installs CSS values from the same object before React mounts", () => {
    const root = document.createElement("div");
    installUiTokens(root);
    expect(root.style.getPropertyValue("--radius-xs")).toBe("4px");
    expect(root.style.getPropertyValue("--radius-sm")).toBe("6px");
    expect(root.style.getPropertyValue("--radius-md")).toBe("8px");
    expect(root.style.getPropertyValue("--radius-pill")).toBe("999px");
    expect(root.style.getPropertyValue("--shell-overlay-breakpoint")).toBe("960px");
    expect(root.style.getPropertyValue("--control-height-compact")).toBe("28px");
  });

  it("builds the only shell media query from the reviewed token", () => {
    expect(shellOverlayMediaQuery()).toBe("(max-width: 960px)");
  });

  it.each([
    [961, false],
    [959, true],
  ])("classifies %ipx on the correct side of the shell boundary", (width, expected) => {
    expect(shellOverlayMatches(width)).toBe(expected);
  });
});
