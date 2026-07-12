import rawTokens from "./tokens.json";

export const UI_TOKENS = Object.freeze({
  ...rawTokens,
  radiusPx: Object.freeze(rawTokens.radiusPx),
  spacePx: Object.freeze(rawTokens.spacePx),
  controlHeightPx: Object.freeze(rawTokens.controlHeightPx),
});
export const SHELL_OVERLAY_BREAKPOINT_PX = UI_TOKENS.shellOverlayBreakpointPx;

export function shellOverlayMediaQuery(): string {
  return `(max-width: ${SHELL_OVERLAY_BREAKPOINT_PX}px)`;
}

export function installUiTokens(root: HTMLElement = document.documentElement): void {
  const values: Record<string, number> = {
    "--radius-xs": UI_TOKENS.radiusPx.xs,
    "--radius-sm": UI_TOKENS.radiusPx.sm,
    "--radius-md": UI_TOKENS.radiusPx.md,
    "--radius-pill": UI_TOKENS.radiusPx.pill,
    "--shell-overlay-breakpoint": UI_TOKENS.shellOverlayBreakpointPx,
    "--control-height-compact": UI_TOKENS.controlHeightPx.compact,
    "--control-height-default": UI_TOKENS.controlHeightPx.default,
  };
  for (const [key, value] of Object.entries(UI_TOKENS.spacePx)) {
    values[`--space-${key.replace("_", "-")}`] = value;
  }
  for (const [name, value] of Object.entries(values)) {
    root.style.setProperty(name, `${value}px`);
  }
}
