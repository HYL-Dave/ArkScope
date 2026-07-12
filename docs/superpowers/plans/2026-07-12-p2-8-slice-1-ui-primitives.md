# P2.8 Slice 1 UI Primitive Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.
>
> **Status: MERGED / ALL GATES CLOSED, 2026-07-12.** Review MF1 and SF1-SF4
> are absorbed in this document. Final code tip `df9c39b`, review-ready docs
> `c7d9c41`, and reviewer gate evidence `3449e32` were fast-forwarded into
> `master`. Reviewer canonical backend A/B passed and the authenticated Slice 1
> DesignSync companion update completed before merge.

**Goal:** Establish the minimum canonical UI primitive foundation and use it to repair the missing Holdings and Investor Profile presentation without changing their domain behavior.

**Architecture:** A small `src/ui/` package owns reviewed tokens and focused React primitives. One JSON token source supplies both TypeScript behavior and CSS custom properties; overlays use the TypeScript breakpoint rather than copying media-query literals. Holdings becomes the first DataTable/ConfirmDialog/PageHeader consumer, while Investor Profile receives only shared control/state styling and class coverage; its summary-first redesign remains Slice 5.

**Tech Stack:** React 18, TypeScript 5.5, Vite 5, Vitest/jsdom, CSS custom properties, `lucide-react` icons, existing npm workspace tooling.

**Behavioral A/B base:** `4e229a8` (canonical written design approved and Claude Design companion synchronized). The implementation worktree was created from the then-current review-cleared `master` tip so this plan and its ledger travelled with the branch; intervening commits after `4e229a8` were docs-only. Implementation stopped review-ready, then reviewer canonical A/B and DesignSync closed the two remaining gates before the user-approved fast-forward merge through `3449e32`.

## Execution Ledger

- **TDD delivery:** Tasks 1-6 landed as focused commits from `f2faebc` through
  `9d7d169`. Every planned primitive began with the named missing-module or
  missing-contract RED. Task reviews then repaired stacked-overlay ownership,
  initially-busy focus, account-scoped row identity, body-portal menu
  placement, and responsive metric/profile presentation before moving on.
- **Final implementation review:** the whole-branch review found four gaps:
  multiple row menus could remain open, Investor Profile mutations had no
  visible `running` state, proposal guardrails could overflow at 390px, and
  non-cancellable work was not stated. RED-first fixes landed in `9500d77`.
  Chrome then exposed a jsdom false positive: menu focus happened while the
  portal was still hidden. A timing RED observed `hidden, hidden`; `40a92e8`
  split positioning from focus and real Chrome then reported one menu, a
  visible focused menuitem, and correct Escape focus restoration. The final
  terminal-cancellation wording finding landed RED-first in `df9c39b`. Final
  re-review: **GREEN, no remaining findings**.
- **Fresh automated evidence at `df9c39b`:** focused frontend `8 files / 70
  tests`; full frontend `38 / 347`; typecheck and production build PASS (only
  the existing >500k chunk warning); no-PG smoke `24/24`, `ok:true`,
  `pg_attempts:[]`. Static gates retain exactly four legacy confirmation
  owners (Research, Settings, Universe, Watchlist), find no UI media-query or
  radius exception, keep literal `960` in `tokens.json`/token tests only, find
  no hard-delete copy, and prove App/Research/Settings/API/styles/backend files
  byte-unchanged from `4e229a8`.
- **Frontend base/head accounting:** a fresh virgin base run is `32 files / 296
  tests`; final head is `38 / 347`, exactly six files and **+51 tests**. The
  original +46 plan gained five review regressions: BoundedProgress +2,
  DataTable +1, and Investor Profile/class coverage +2.
- **Backend A/B:** virgin collect is strict equality `4185 -> 4185` with empty
  added/removed sets. Base attempt 1, base attempt 2, and head all stopped at
  the identical 31-byte prefix `..............EEEEEEE..........` before
  `tests/test_agents.py::TestQueryEndpoint::test_providers_endpoint`; all three
  logs share SHA-256
  `bad8cae6a1dd39f36318ca7a571577e7fa6bc1163722613b02294c49cd69893d`.
  Full counters and failure sets were never emitted in the implementation
  environment, so its attempt stayed **PENDING**; preserved evidence lives
  under `/tmp/arkscope-p2.8-s1-ab.nxivgf/logs/`.
  **Reviewer canonical A/B ✅ PASS (Fable, 2026-07-12, no hang):** virgin
  `git archive` of base `820d1b3` (merge-base) versus head `c7d9c41`,
  sequential single-process full pytest. Both sides identical:
  `30 failed / 4074 passed / 74 skipped / 18 warnings / 7 errors`; failure
  sets empty in both directions; collect added/removed `0/0`. Work dir
  `/tmp/ab_slice1_AoqO`. The frontend-only slice leaves the backend
  byte-identical, as required. Reviewer also re-ran the frontend suite in the
  branch worktree (`38 files / 347 tests` PASS + typecheck + build), the
  no-PG smoke, and every Task 7 Step 3 static ratchet independently — all
  green, exactly four legacy confirmation owners remain.
- **Visual evidence:** Holdings and Investor Profile were inspected at
  1440x900, 1024x768, 961x768, 959x768, and 390x844. At 390px the page has no
  body overflow; Holdings keeps its 705px financial table inside a 364px
  horizontal-scroll owner; menus stay within the viewport; ConfirmDialog traps
  focus, closes on Escape, and restores the row trigger. A long proposal
  specimen remained `366/366px` with wrapping and no body overflow. Lighthouse
  snapshot: Accessibility 98 / Best Practices 100; the sole accessibility
  failure is the pre-existing Settings heading-order debt owned by a later
  Settings/Profile slice.
- **Design companion:** the pre-slice companion sync remains plan
  `dfd45b4f7dbb`. The implementation session exposed no DesignSync tool, so it
  correctly reported this gate pending rather than fabricating it.
  **Slice 1 companion sync ✅ COMPLETE (Fable, authenticated session,
  2026-07-12, DesignSync plan `plan_f9c9ea59626141ed_14c603dcda45`, 9 files):**
  `--radius-lg` reconciled `10px -> 8px` as a legacy alias (no modal
  exception, per locked decision 2; app token source has no `lg`), the
  `spacing-radii` specimen relabeled to the 8px cap, and seven primitive
  specimens added under the new **Primitives** group
  (`guidelines/p28-controls / p28-page-header / p28-status / p28-overlays /
  p28-bounded-progress / p28-data-table` + the existing `shell-contract`
  card), plus a readme snapshot update (slice-1 primitives implemented,
  radius reconciliation resolved, lucide-react noted). Read-back verified:
  `list_files` shows all six new paths; `tokens/spacing.css` re-fetched and
  confirms `--radius-lg: 8px`. No Slice 2 shell or Slice 3 Research screens
  were prebuilt.

---

## Locked Decisions

1. The canonical authority is
   `docs/superpowers/specs/2026-07-12-p2-8-canonical-shell-interaction-design.md`.
   The Claude Design project is a synchronized companion. Its 2026-07-12 sync
   is complete; app behavior follows the repo spec when they differ.
2. Modal and overlay frames are **not** a new radius exception. Every general
   framed component, including Drawer and ConfirmDialog, is capped at 8px.
   Pill/chip and circular indicators remain the only radius exceptions. The
   app does not import the kit token; the companion's legacy `radius-lg` alias
   was reconciled from 10px to the same 8px cap during the Slice 1 sync.
3. `ui/tokens.json` is the single app token source for Slice 1. TypeScript reads
   it directly; `installUiTokens()` writes the corresponding CSS custom
   properties before React mounts. No generated CSS, copied breakpoint
   constant, or per-component media literal is added.
4. `shellOverlayBreakpointPx` is exactly 960. Responsive behavior is proven on
   both sides: 961 is wide and 959 is overlay. Existing 760/900/1100 debt in
   untouched legacy surfaces remains for its owning slice.
5. Slice 1 builds only the first-consumer depth:
   - Drawer is transient only; pinnable Evidence behavior waits for Slice 3.
   - BoundedProgress is compact and stage-aware; no global work registry,
     persistence, polling, or fixed-task ownership is invented.
   - DataTable supports rows, columns, row actions, inline expansion, empty
     state, and horizontal overflow. It does not add sorting, pagination, or
     virtualization.
6. Shared product state is
   `loading | empty | ready | running | partial | stale | blocked | failed |
   interrupted`. `partial` and `stale` share visual treatment but remain
   distinct machine values. Domain labels are passed in by consumers; the
   primitive does not overwrite Models/provider/coverage terminology.
7. Controls use `lucide-react` where a familiar icon exists. Icon buttons must
   have an accessible name and tooltip. No hand-authored SVG is added.
8. Holdings domain behavior is invariant. The slice may replace its
   presentation and `window.confirm`, but must preserve preview-before-apply,
   broker/manual ownership, soft close, inline editing, closed filtering,
   financial formatting, user notes, and every current request payload.
9. Investor Profile domain behavior and information order are invariant in
   this slice. Do not introduce summary-first/profile-state redesign, scenario
   calibration, qualitative score labels, or prompt changes; those belong to
   Slice 5. This slice only repairs missing classes and adopts shared control,
   alert, and status presentation.
10. No backend, API DTO, database, route, model, navigation, topbar, Research,
    Settings IA, or Reference-store change belongs here. If a green test seems
    to require one, stop and report instead of widening the slice.
11. Shared layout classes use the `ui-` namespace. The legacy Holdings-only
    tokens `section-band`, `section-head`, `actions`, `status-grid`, `metric`,
    `metric-label`, and `inline-form` are migrated, not promoted into ambiguous
    global vocabulary.

## Domain State Mapping

The first consumers publish this mapping without pretending every common state
applies everywhere:

| Surface | Domain condition | Common state |
| --- | --- | --- |
| Holdings | initial/refresh request | `loading` |
| Holdings | loaded with no positions | `empty` |
| Holdings | loaded snapshot | `ready` |
| Holdings | mutation or IBKR preview/apply request | `running` |
| Holdings | unapplied IBKR preview differences | `partial` |
| Holdings | provider/config response prevents sync | `blocked` when the existing response exposes that fact; otherwise `failed` |
| Holdings | request failure | `failed` |
| Investor Profile | initial request | `loading` |
| Investor Profile | approved/current form available | `ready` |
| Investor Profile | save/draft/calibration request | `running` |
| Investor Profile | pending calibration proposal | `partial` |
| Investor Profile | appetite/capacity mismatch | `partial` with the existing domain label |
| Investor Profile | request failure | `failed` |

`stale` and `interrupted` have no truthful Slice 1 meaning on these two
surfaces and are tested at primitive level only.

## File Map

**Create**

- `apps/arkscope-web/src/ui/tokens.json` — sole Slice 1 token values.
- `apps/arkscope-web/src/ui/tokens.ts` — typed token exports, CSS-variable installer, and 960px query.
- `apps/arkscope-web/src/ui/useShellOverlay.ts` — responsive matchMedia hook.
- `apps/arkscope-web/src/ui/tokens.test.ts` — token/radius/breakpoint contract.
- `apps/arkscope-web/src/ui/Button.tsx` — compact command and icon controls.
- `apps/arkscope-web/src/ui/PageHeader.tsx` — canonical title/context/actions frame.
- `apps/arkscope-web/src/ui/Status.tsx` — StatusBadge and InlineAlert.
- `apps/arkscope-web/src/ui/primitives.test.tsx` — controls/header/all-state tests.
- `apps/arkscope-web/src/ui/useOverlayFocus.ts` — shared focus trap/restore behavior.
- `apps/arkscope-web/src/ui/Drawer.tsx` — transient Drawer only.
- `apps/arkscope-web/src/ui/ConfirmDialog.tsx` — consequence-aware confirmation.
- `apps/arkscope-web/src/ui/overlays.test.tsx` — focus, escape, restore, and overlay tests.
- `apps/arkscope-web/src/ui/BoundedProgress.tsx` — compact stage-aware long-work status.
- `apps/arkscope-web/src/ui/BoundedProgress.test.tsx` — bound/grace/error contract.
- `apps/arkscope-web/src/ui/DataTable.tsx` — typed columns, row menu, expansion, empty state.
- `apps/arkscope-web/src/ui/DataTable.test.tsx` — table and row-action contract.
- `apps/arkscope-web/src/ui/primitives.css` — shared primitive and first-consumer styles.
- `apps/arkscope-web/src/ui/index.ts` — public Slice 1 exports only.
- `apps/arkscope-web/src/ui/classCoverage.test.ts` — literal-class coverage for migrated files.

**Modify**

- `package.json` — lockfile workspace dependency only if npm writes root metadata.
- `package-lock.json` — resolved `lucide-react` dependency.
- `apps/arkscope-web/package.json` — add `lucide-react`.
- `apps/arkscope-web/src/main.tsx` — install tokens before mount; import primitive CSS.
- `apps/arkscope-web/src/Holdings.tsx` — first primitive consumer and style repair.
- `apps/arkscope-web/src/Holdings.test.tsx` — dialog/menu/state regressions.
- `apps/arkscope-web/src/InvestorProfilePanel.tsx` — style/state primitive adoption only.
- `apps/arkscope-web/src/InvestorProfilePanel.test.tsx` — presentation-state regressions.
- `docs/design/PROJECT_PRIORITY_MAP.md` — review-ready/verification record after implementation.
- `docs/superpowers/plans/2026-07-12-p2-8-slice-1-ui-primitives.md` — execution ledger.

**Explicitly not modified**

- `apps/arkscope-web/src/App.tsx`
- `apps/arkscope-web/src/Research.tsx`
- `apps/arkscope-web/src/Settings.tsx`
- `apps/arkscope-web/src/api.ts`
- `apps/arkscope-web/src/styles.css`; all Slice 1 styles belong in
  `ui/primitives.css`.
- all Python/backend files

---

### Task 1: Single-source tokens and responsive authority

**Files:**

- Create: `apps/arkscope-web/src/ui/tokens.json`
- Create: `apps/arkscope-web/src/ui/tokens.ts`
- Create: `apps/arkscope-web/src/ui/useShellOverlay.ts`
- Create: `apps/arkscope-web/src/ui/tokens.test.ts`
- Modify: `apps/arkscope-web/src/main.tsx`

- [x] **Step 1: Write the token contract RED tests**

Create `tokens.test.ts` with these named tests:

```ts
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
```

- [x] **Step 2: Run Task 1 tests and verify RED**

Run:

```bash
npm test --workspace apps/arkscope-web -- src/ui/tokens.test.ts
```

Expected: FAIL because `src/ui/tokens` and `useShellOverlay` do not exist.

- [x] **Step 3: Add the reviewed token source**

Create `tokens.json` exactly as the local app authority:

```json
{
  "shellOverlayBreakpointPx": 960,
  "radiusPx": {
    "xs": 4,
    "sm": 6,
    "md": 8,
    "pill": 999
  },
  "spacePx": {
    "0": 0,
    "0_5": 2,
    "1": 4,
    "1_5": 6,
    "2": 8,
    "2_5": 10,
    "3": 12,
    "3_5": 14,
    "4": 16,
    "5": 20,
    "6": 24,
    "8": 32
  },
  "controlHeightPx": {
    "compact": 28,
    "default": 32
  }
}
```

There is deliberately no `radius-lg`. Overlay/modal uses `radius-md`.

- [x] **Step 4: Implement typed exports and CSS installation**

Create `tokens.ts` with no duplicated numeric breakpoint:

```ts
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
```

Create `useShellOverlay.ts`:

```ts
import { useEffect, useState } from "react";
import { SHELL_OVERLAY_BREAKPOINT_PX, shellOverlayMediaQuery } from "./tokens";

export function shellOverlayMatches(width: number): boolean {
  return width <= SHELL_OVERLAY_BREAKPOINT_PX;
}

export function useShellOverlay(): boolean {
  const query = shellOverlayMediaQuery();
  const get = () => typeof window !== "undefined"
    && typeof window.matchMedia === "function"
    && window.matchMedia(query).matches;
  const [matches, setMatches] = useState(get);

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const media = window.matchMedia(query);
    const update = () => setMatches(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, [query]);

  return matches;
}
```

Do not add a fallback `@media (max-width: 960px)` elsewhere.

- [x] **Step 5: Install tokens before the application render**

In `main.tsx`, import `installUiTokens` and `./ui/primitives.css`, then call the
installer before `createRoot`:

```ts
import { installUiTokens } from "./ui/tokens";
import "./styles.css";
import "./ui/primitives.css";

installUiTokens(document.documentElement);
```

`primitives.css` is created in Task 2; until then, create an empty file only if
the RED-to-GREEN cycle requires the import to resolve.

- [x] **Step 6: Run Task 1 tests and typecheck**

Run:

```bash
npm test --workspace apps/arkscope-web -- src/ui/tokens.test.ts
npm run typecheck --workspace apps/arkscope-web
```

Expected: 5 parameter-expanded token tests PASS; typecheck PASS.

- [x] **Step 7: Commit Task 1**

```bash
git add apps/arkscope-web/src/main.tsx apps/arkscope-web/src/ui/tokens.json apps/arkscope-web/src/ui/tokens.ts apps/arkscope-web/src/ui/useShellOverlay.ts apps/arkscope-web/src/ui/tokens.test.ts apps/arkscope-web/src/ui/primitives.css
git commit -m "feat: add canonical ui token authority"
```

---

### Task 2: Compact controls, PageHeader, and common state presentation

**Files:**

- Modify: `apps/arkscope-web/package.json`
- Modify: `package-lock.json`
- Create: `apps/arkscope-web/src/ui/Button.tsx`
- Create: `apps/arkscope-web/src/ui/PageHeader.tsx`
- Create: `apps/arkscope-web/src/ui/Status.tsx`
- Create: `apps/arkscope-web/src/ui/primitives.test.tsx`
- Modify: `apps/arkscope-web/src/ui/primitives.css`
- Create: `apps/arkscope-web/src/ui/index.ts`

- [x] **Step 1: Add the icon dependency through the workspace**

Run:

```bash
npm install lucide-react --workspace apps/arkscope-web
```

Expected: `apps/arkscope-web/package.json` and root `package-lock.json` change;
no unrelated package is upgraded.

- [x] **Step 2: Write RED tests using the repository's jsdom harness**

Create `primitives.test.tsx`. Use `createRoot` + `act`; do not add
Testing Library. The helper is explicit:

```tsx
/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Search } from "lucide-react";
import { Button, IconButton } from "./Button";
import { PageHeader } from "./PageHeader";
import { COMMON_UI_STATES, InlineAlert, StatusBadge } from "./Status";

let root: ReturnType<typeof createRoot> | null = null;
let host: HTMLDivElement | null = null;

async function mount(node: React.ReactNode) {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => root!.render(node));
}

afterEach(() => {
  if (root) act(() => root!.unmount());
  host?.remove();
  root = null;
  host = null;
});
```

Add these exact test contracts:

```tsx
it("renders one page title with compact context and commands", async () => {
  await mount(
    <PageHeader
      eyebrow="Holdings"
      title="持倉"
      context={<span>9 positions</span>}
      actions={<Button>重新整理</Button>}
    />,
  );
  expect(host!.querySelectorAll("h1")).toHaveLength(1);
  expect(host!.textContent).toContain("9 positions");
  expect(host!.querySelector(".ui-page-header-actions button")).not.toBeNull();
});

it("keeps command-button type and disabled state explicit", async () => {
  await mount(<Button tone="primary" disabled>儲存</Button>);
  const button = host!.querySelector("button")!;
  expect(button.type).toBe("button");
  expect(button.disabled).toBe(true);
  expect(button.className).toContain("ui-button-primary");
});

it("requires an accessible label and tooltip for an icon button", async () => {
  await mount(<IconButton label="搜尋" icon={<Search />} />);
  const button = host!.querySelector("button")!;
  expect(button.getAttribute("aria-label")).toBe("搜尋");
  expect(button.title).toBe("搜尋");
  expect(button.querySelector(".ui-button-icon")?.getAttribute("aria-hidden")).toBe("true");
});

it.each(COMMON_UI_STATES)("renders %s with a visible domain label", async (state) => {
  await mount(<StatusBadge state={state} label={`domain:${state}`} />);
  const badge = host!.querySelector("[data-state]")!;
  expect(badge.getAttribute("data-state")).toBe(state);
  expect(badge.textContent).toContain(`domain:${state}`);
  expect(badge.querySelector("svg")?.getAttribute("aria-hidden")).toBe("true");
});

it("uses alert semantics for failed and blocked messages", async () => {
  await mount(<InlineAlert state="failed" title="同步失敗">重新整理後再試</InlineAlert>);
  expect(host!.querySelector('[role="alert"]')).not.toBeNull();
  expect(host!.textContent).toContain("重新整理後再試");
});

it("uses status semantics for nonterminal information", async () => {
  await mount(<InlineAlert state="partial" title="尚未套用">先檢查差異</InlineAlert>);
  expect(host!.querySelector('[role="status"]')).not.toBeNull();
});
```

The `it.each` expands to all nine machine values. `partial` and `stale` must
remain distinct `data-state` values even though they share visual tokens.

- [x] **Step 3: Run tests and verify RED**

Run:

```bash
npm test --workspace apps/arkscope-web -- src/ui/primitives.test.tsx
```

Expected: FAIL because the primitive modules do not exist.

- [x] **Step 4: Implement compact command controls**

Create `Button.tsx`:

```tsx
import React, { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";

export type ButtonTone = "primary" | "secondary" | "ghost" | "danger";
export type ButtonSize = "compact" | "default";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  tone?: ButtonTone;
  size?: ButtonSize;
  icon?: ReactNode;
  busy?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    tone = "secondary",
    size = "default",
    icon,
    busy = false,
    className = "",
    type = "button",
    disabled,
    children,
    ...rest
  },
  ref,
) {
  return (
    <button
      {...rest}
      ref={ref}
      type={type}
      disabled={disabled || busy}
      aria-busy={busy || undefined}
      className={`ui-button ui-button-${tone} ui-button-${size} ${className}`.trim()}
    >
      {icon ? <span className="ui-button-icon" aria-hidden="true">{icon}</span> : null}
      {children}
    </button>
  );
});

export interface IconButtonProps
  extends Omit<ButtonProps, "children" | "icon" | "aria-label"> {
  label: string;
  icon: ReactNode;
}

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
  { label, icon, title = label, className = "", ...rest },
  ref,
) {
  return (
    <Button
      {...rest}
      ref={ref}
      aria-label={label}
      title={title}
      className={`ui-icon-button ${className}`.trim()}
      icon={icon}
    />
  );
});
```

The icon wrapper is `aria-hidden`; the button label is authoritative.

- [x] **Step 5: Implement PageHeader**

Create `PageHeader.tsx`:

```tsx
import type { ReactNode } from "react";

export function PageHeader({
  eyebrow,
  title,
  context,
  actions,
}: {
  eyebrow?: ReactNode;
  title: ReactNode;
  context?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="ui-page-header">
      <div className="ui-page-header-copy">
        {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
        <h1>{title}</h1>
        {context ? <div className="ui-page-header-context">{context}</div> : null}
      </div>
      {actions ? <div className="ui-page-header-actions">{actions}</div> : null}
    </header>
  );
}
```

- [x] **Step 6: Implement common state presentation without re-translating domains**

Create `Status.tsx`:

```tsx
import type { ReactNode } from "react";
import {
  Activity,
  CheckCircle2,
  Circle,
  CircleSlash2,
  LoaderCircle,
  PauseCircle,
  TriangleAlert,
  XCircle,
  type LucideIcon,
} from "lucide-react";

export const COMMON_UI_STATES = [
  "loading", "empty", "ready", "running", "partial", "stale",
  "blocked", "failed", "interrupted",
] as const;
export type CommonUiState = (typeof COMMON_UI_STATES)[number];

const ICONS: Record<CommonUiState, LucideIcon> = {
  loading: LoaderCircle,
  empty: Circle,
  ready: CheckCircle2,
  running: Activity,
  partial: TriangleAlert,
  stale: TriangleAlert,
  blocked: CircleSlash2,
  failed: XCircle,
  interrupted: PauseCircle,
};

export function StatusBadge({ state, label }: { state: CommonUiState; label: ReactNode }) {
  const Icon = ICONS[state];
  return (
    <span className="ui-status-badge" data-state={state}>
      <Icon size={13} aria-hidden="true" />
      <span>{label}</span>
    </span>
  );
}

export function InlineAlert({
  state,
  title,
  children,
  action,
}: {
  state: CommonUiState;
  title: ReactNode;
  children?: ReactNode;
  action?: ReactNode;
}) {
  const urgent = state === "failed" || state === "blocked";
  return (
    <div className="ui-inline-alert" data-state={state} role={urgent ? "alert" : "status"}>
      <StatusBadge state={state} label={title} />
      {children ? <div className="ui-inline-alert-detail">{children}</div> : null}
      {action ? <div className="ui-inline-alert-action">{action}</div> : null}
    </div>
  );
}
```

- [x] **Step 7: Add the compact shared CSS**

Populate the first part of `primitives.css`. Use only installed token variables;
all framed radii are `var(--radius-md)` or smaller:

```css
.ui-button {
  min-height: var(--control-height-default);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-1-5);
  padding: 5px 11px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font: inherit;
  font-weight: 600;
  letter-spacing: 0;
  cursor: pointer;
}
.ui-button-compact { min-height: var(--control-height-compact); padding: 3px 8px; font-size: 12px; }
.ui-button-primary { background: var(--accent); border-color: var(--accent); color: #0b1020; }
.ui-button-secondary { background: var(--panel2); color: var(--fg); }
.ui-button-ghost { background: transparent; color: var(--muted); }
.ui-button-danger { background: transparent; color: var(--bad); border-color: color-mix(in srgb, var(--bad) 60%, var(--border)); }
.ui-button:hover:not(:disabled) { border-color: var(--accent); color: var(--fg); }
.ui-button-danger:hover:not(:disabled) { border-color: var(--bad); color: var(--bad); }
.ui-button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.ui-button:disabled { cursor: default; opacity: 0.55; }
.ui-button-icon { display: inline-flex; line-height: 0; }
.ui-icon-button { width: var(--control-height-default); padding: 0; }
.ui-icon-button .ui-button-icon { margin: 0; }

.ui-page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  margin-bottom: var(--space-4);
  flex-wrap: wrap;
}
.ui-page-header-copy { min-width: 0; }
.ui-page-header h1 { margin: 0; font-size: 22px; line-height: 1.25; letter-spacing: 0; }
.ui-page-header-context { margin-top: var(--space-1); color: var(--muted); }
.ui-page-header-actions { display: flex; gap: var(--space-2); flex-wrap: wrap; }

.ui-status-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1-5);
  min-height: 22px;
  padding: 1px 8px;
  border: 1px solid var(--border);
  border-radius: var(--radius-pill);
  color: var(--muted);
  font-size: 11.5px;
  white-space: nowrap;
}
.ui-status-badge[data-state="ready"] { color: var(--ok); border-color: color-mix(in srgb, var(--ok) 55%, var(--border)); }
.ui-status-badge[data-state="running"] { color: var(--accent); border-color: color-mix(in srgb, var(--accent) 55%, var(--border)); }
.ui-status-badge[data-state="partial"],
.ui-status-badge[data-state="stale"],
.ui-status-badge[data-state="blocked"] { color: var(--wait); border-color: color-mix(in srgb, var(--wait) 55%, var(--border)); }
.ui-status-badge[data-state="failed"] { color: var(--bad); border-color: color-mix(in srgb, var(--bad) 55%, var(--border)); }
.ui-status-badge[data-state="loading"] svg { animation: ui-spin 0.8s linear infinite; }

.ui-inline-alert {
  display: grid;
  grid-template-columns: max-content minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--panel2);
}
.ui-inline-alert-detail { min-width: 0; color: var(--muted); overflow-wrap: anywhere; }
.ui-inline-alert-action { justify-self: end; }
@keyframes ui-spin { to { transform: rotate(360deg); } }
```

Do not add viewport-width font scaling, negative letter spacing, decorative
gradients, nested card rules, or 10px/14px general-frame radii.

- [x] **Step 8: Export only implemented primitives**

Create `ui/index.ts`:

```ts
export * from "./Button";
export * from "./PageHeader";
export * from "./Status";
export * from "./tokens";
export * from "./useShellOverlay";
```

Later tasks append exports only after their module is green.

- [x] **Step 9: Run focused tests and typecheck**

Run:

```bash
npm test --workspace apps/arkscope-web -- src/ui/tokens.test.ts src/ui/primitives.test.tsx
npm run typecheck --workspace apps/arkscope-web
```

Expected: token tests and 14 parameter-expanded primitive tests PASS;
typecheck PASS.

- [x] **Step 10: Commit Task 2**

```bash
git add package.json package-lock.json apps/arkscope-web/package.json apps/arkscope-web/src/ui
git commit -m "feat: add compact ui state primitives"
```

---

### Task 3: Transient Drawer and ConfirmDialog focus contract

**Files:**

- Create: `apps/arkscope-web/src/ui/useOverlayFocus.ts`
- Create: `apps/arkscope-web/src/ui/Drawer.tsx`
- Create: `apps/arkscope-web/src/ui/ConfirmDialog.tsx`
- Create: `apps/arkscope-web/src/ui/overlays.test.tsx`
- Modify: `apps/arkscope-web/src/ui/primitives.css`
- Modify: `apps/arkscope-web/src/ui/index.ts`

- [x] **Step 1: Write overlay RED tests**

Create `overlays.test.tsx` with the same `createRoot`/`act` cleanup pattern as
Task 2. Stub `matchMedia` explicitly:

```ts
function stubMatchMedia(matches: boolean) {
  vi.stubGlobal("matchMedia", vi.fn((query: string) => ({
    matches,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(() => true),
  })));
}
```

Add these named contracts:

1. `closed_drawer_renders_nothing_and_reserves_no_width`
2. `open_drawer_close_button_closes_and_restores_its_trigger`
3. `drawer_escape_closes_and_restores_the_trigger`
4. `drawer_tabs_between_its_own_focusable_controls`
5. `drawer_marks_961px_as_wide`
6. `drawer_marks_959px_as_shell_overlay`
7. `confirm_dialog_focuses_cancel_for_a_destructive_action`
8. `confirm_dialog_cancel_does_not_confirm_and_restores_focus`
9. `confirm_dialog_confirms_once_then_uses_fallback_if_the_trigger_disappears`
10. `confirm_dialog_escape_cancels_only_when_not_busy`

The critical assertions are:

```tsx
expect(document.querySelector('[role="dialog"]')).toBeNull(); // closed
expect(dialog.getAttribute("aria-modal")).toBe("true");
expect(dialog.getAttribute("data-shell-overlay")).toBe("true"); // 959
expect(dialog.getAttribute("data-shell-overlay")).toBe("false"); // 961
expect(document.activeElement?.textContent).toContain("取消");
expect(onConfirm).toHaveBeenCalledTimes(1);
expect(onCancel).not.toHaveBeenCalled();
```

Test 2 must focus the visible close button, click it, assert `onClose` exactly
once, and assert focus returns to the supplied trigger. Escape/backdrop coverage
does not substitute for the visible close affordance.

Test 9 removes the original trigger in its confirm handler, closes the dialog,
and proves focus lands on the supplied `fallbackFocusRef`.
Test 10 proves idle Escape calls Cancel and never Confirm, then rerenders with
`busy=true` and proves Escape calls neither callback.

The restore test must render a real trigger and toggle `open` from component
state. It must not call the primitive function directly.

- [x] **Step 2: Run overlay tests and verify RED**

Run:

```bash
npm test --workspace apps/arkscope-web -- src/ui/overlays.test.tsx
```

Expected: FAIL because Drawer/ConfirmDialog do not exist.

- [x] **Step 3: Implement one focus boundary for both overlays**

Create `useOverlayFocus.ts`:

```ts
import { useEffect, useRef, type RefObject } from "react";

const FOCUSABLE = [
  "button:not([disabled])",
  "a[href]",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  '[tabindex]:not([tabindex="-1"])',
].join(",");

function focusables(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE));
}

export function useOverlayFocus({
  open,
  containerRef,
  initialFocusRef,
  returnFocusRef,
  fallbackFocusRef,
  onEscape,
}: {
  open: boolean;
  containerRef: RefObject<HTMLElement | null>;
  initialFocusRef?: RefObject<HTMLElement | null>;
  returnFocusRef?: RefObject<HTMLElement | null>;
  fallbackFocusRef?: RefObject<HTMLElement | null>;
  onEscape: () => void;
}) {
  const onEscapeRef = useRef(onEscape);
  onEscapeRef.current = onEscape;

  useEffect(() => {
    if (!open || !containerRef.current) return;
    const container = containerRef.current;
    const previous = returnFocusRef?.current
      ?? (document.activeElement instanceof HTMLElement ? document.activeElement : null);
    const initial = initialFocusRef?.current ?? focusables(container)[0] ?? container;
    initial.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented) return;
      if (event.key === "Escape") {
        event.preventDefault();
        onEscapeRef.current();
        return;
      }
      if (event.key !== "Tab") return;
      const items = focusables(container);
      if (items.length === 0) {
        event.preventDefault();
        container.focus();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      if (previous?.isConnected) previous.focus();
      else fallbackFocusRef?.current?.focus();
    };
  }, [containerRef, fallbackFocusRef, initialFocusRef, open, returnFocusRef]);
}
```

Do not fork a second focus implementation in ConfirmDialog.

- [x] **Step 4: Implement transient Drawer only**

Create `Drawer.tsx`:

```tsx
import { useId, useRef, type ReactNode, type RefObject } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { IconButton } from "./Button";
import { useOverlayFocus } from "./useOverlayFocus";
import { useShellOverlay } from "./useShellOverlay";

export function Drawer({
  open,
  title,
  onClose,
  returnFocusRef,
  children,
  footer,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  returnFocusRef?: RefObject<HTMLElement | null>;
  children: ReactNode;
  footer?: ReactNode;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const titleId = useId();
  const shellOverlay = useShellOverlay();
  useOverlayFocus({
    open,
    containerRef: panelRef,
    initialFocusRef: closeRef,
    returnFocusRef,
    onEscape: onClose,
  });
  if (!open) return null;

  return createPortal(
    <div
      className="ui-overlay-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <aside
        ref={panelRef}
        className="ui-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        data-shell-overlay={String(shellOverlay)}
        tabIndex={-1}
      >
        <header className="ui-overlay-head">
          <h2 id={titleId}>{title}</h2>
          <IconButton
            ref={closeRef}
            label="關閉"
            tone="ghost"
            icon={<X size={18} />}
            onClick={onClose}
          />
        </header>
        <div className="ui-drawer-body">{children}</div>
        {footer ? <footer className="ui-drawer-footer">{footer}</footer> : null}
      </aside>
    </div>,
    document.body,
  );
}
```

`IconButton` is already `forwardRef` compatible from Task 2; do not replace it
with an untyped cast or a second trigger wrapper.

- [x] **Step 5: Implement consequence-aware ConfirmDialog**

Create `ConfirmDialog.tsx`:

```tsx
import { useId, useRef, type ReactNode, type RefObject } from "react";
import { createPortal } from "react-dom";
import { Button } from "./Button";
import { useOverlayFocus } from "./useOverlayFocus";

export function ConfirmDialog({
  open,
  title,
  consequence,
  confirmLabel,
  cancelLabel = "取消",
  tone = "danger",
  busy = false,
  onConfirm,
  onCancel,
  returnFocusRef,
  fallbackFocusRef,
}: {
  open: boolean;
  title: string;
  consequence: ReactNode;
  confirmLabel: string;
  cancelLabel?: string;
  tone?: "primary" | "danger";
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  returnFocusRef?: RefObject<HTMLElement | null>;
  fallbackFocusRef?: RefObject<HTMLElement | null>;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const titleId = useId();
  const consequenceId = useId();
  useOverlayFocus({
    open,
    containerRef: panelRef,
    initialFocusRef: cancelRef,
    returnFocusRef,
    fallbackFocusRef,
    onEscape: () => {
      if (!busy) onCancel();
    },
  });
  if (!open) return null;

  return createPortal(
    <div className="ui-overlay-backdrop">
      <section
        ref={panelRef}
        className="ui-confirm-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={consequenceId}
        tabIndex={-1}
      >
        <h2 id={titleId}>{title}</h2>
        <div id={consequenceId} className="ui-confirm-consequence">{consequence}</div>
        <div className="ui-confirm-actions">
          <Button ref={cancelRef} onClick={onCancel} disabled={busy}>{cancelLabel}</Button>
          <Button tone={tone} onClick={onConfirm} busy={busy}>{confirmLabel}</Button>
        </div>
      </section>
    </div>,
    document.body,
  );
}
```

The default focus is Cancel. No hidden hard-delete wording or generic “Are you
sure?” copy is generated by the primitive; the consumer supplies consequences.

- [x] **Step 6: Add overlay CSS with an 8px maximum radius**

Append:

```css
.ui-overlay-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  justify-content: flex-end;
  background: rgba(0, 0, 0, 0.56);
}
.ui-drawer {
  width: min(420px, calc(100vw - var(--space-8)));
  height: 100%;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  background: var(--panel);
  border-left: 1px solid var(--border);
  border-radius: var(--radius-md) 0 0 var(--radius-md);
  box-shadow: 0 8px 28px rgba(0, 0, 0, 0.4);
}
.ui-drawer[data-shell-overlay="true"] {
  width: min(100vw, 420px);
  border-radius: 0;
}
.ui-overlay-head {
  min-height: 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border);
}
.ui-overlay-head h2, .ui-confirm-dialog h2 { margin: 0; font-size: 16px; letter-spacing: 0; }
.ui-drawer-body { min-height: 0; overflow: auto; padding: var(--space-3); }
.ui-drawer-footer { padding: var(--space-3); border-top: 1px solid var(--border); }
.ui-confirm-dialog {
  width: min(480px, calc(100vw - var(--space-8)));
  margin: auto;
  padding: var(--space-4);
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: 0 8px 28px rgba(0, 0, 0, 0.4);
}
.ui-confirm-consequence { margin-top: var(--space-3); color: var(--muted); overflow-wrap: anywhere; }
.ui-confirm-actions { display: flex; justify-content: flex-end; gap: var(--space-2); margin-top: var(--space-4); }
```

The Drawer breakpoint is driven by `data-shell-overlay`; this file contains no
`@media` shell breakpoint.

- [x] **Step 7: Export the green overlay modules**

Append to `ui/index.ts`:

```ts
export * from "./ConfirmDialog";
export * from "./Drawer";
```

- [x] **Step 8: Run focused tests, typecheck, and radius/breakpoint gates**

Run:

```bash
npm test --workspace apps/arkscope-web -- src/ui/overlays.test.tsx src/ui/tokens.test.ts
npm run typecheck --workspace apps/arkscope-web
rg -n "@media|border-radius:\s*(10|14)px|radius-lg" apps/arkscope-web/src/ui
```

Expected: 10 overlay tests and 5 token tests PASS; typecheck PASS. The `rg`
command may show test prose asserting forbidden values, but must show no
production CSS/TS declaration of a shell media query or 10px/14px frame radius.

- [x] **Step 9: Commit Task 3**

```bash
git add apps/arkscope-web/src/ui
git commit -m "feat: add accessible ui overlays"
```

---

### Task 4: Compact stage-aware BoundedProgress

**Files:**

- Create: `apps/arkscope-web/src/ui/BoundedProgress.tsx`
- Create: `apps/arkscope-web/src/ui/BoundedProgress.test.tsx`
- Modify: `apps/arkscope-web/src/ui/primitives.css`
- Modify: `apps/arkscope-web/src/ui/index.ts`

- [x] **Step 1: Write BoundedProgress RED tests**

Create `BoundedProgress.test.tsx` with the house jsdom harness and these named
tests:

1. `shows_overall_and_stage_elapsed_without_a_fake_percentage`
2. `labels_the_bound_as_belonging_to_the_current_stage`
3. `enters_server_confirmation_grace_at_the_stage_bound`
4. `does_not_enter_grace_before_the_stage_bound`
5. `shows_navigation_cancel_and_result_ownership_truthfully`
6. `renders_a_typed_terminal_failure_without_a_progress_bar`
7. `maps_cancelled_work_to_interrupted`

Use this representative assertion shape:

```tsx
await mount(
  <BoundedProgress
    status="running"
    stageLabel="模型執行"
    overallElapsedMs={930_000}
    stageElapsedMs={900_000}
    stageBoundMs={900_000}
    continuesAfterNavigation
    canCancel
    resultLabel="AI 卡片列表"
    onCancel={onCancel}
  />,
);

expect(host!.textContent).toContain("模型執行");
expect(host!.textContent).toContain("已達上界，等待伺服器確認");
expect(host!.textContent).toContain("結果：AI 卡片列表");
expect(host!.querySelector('[role="progressbar"]')).toBeNull();
expect(host!.querySelector('[data-progress-phase="awaiting-confirmation"]')).not.toBeNull();
expect(host!.querySelector(".ui-bounded-progress")?.hasAttribute("aria-live")).toBe(false);
expect(host!.querySelector('[role="status"][aria-live="polite"]')?.textContent)
  .toContain("已達上界");
```

The test must distinguish `overallElapsedMs=930_000` from
`stageElapsedMs=900_000`; it may not render `930 / 900` as one ratio.

- [x] **Step 2: Run Task 4 tests and verify RED**

Run:

```bash
npm test --workspace apps/arkscope-web -- src/ui/BoundedProgress.test.tsx
```

Expected: FAIL because `BoundedProgress` does not exist.

- [x] **Step 3: Implement the compact bounded-work contract**

Create `BoundedProgress.tsx`:

```tsx
import { Square } from "lucide-react";
import { Button } from "./Button";
import { InlineAlert, StatusBadge, type CommonUiState } from "./Status";

export type BoundedWorkStatus = "running" | "succeeded" | "failed" | "interrupted";

function stateFor(status: BoundedWorkStatus): CommonUiState {
  if (status === "succeeded") return "ready";
  return status;
}

export function formatElapsed(ms: number): string {
  const seconds = Math.max(0, Math.floor(ms / 1000));
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return minutes > 0 ? `${minutes}m ${String(rest).padStart(2, "0")}s` : `${rest}s`;
}

export function BoundedProgress({
  status,
  stageLabel,
  overallElapsedMs,
  stageElapsedMs,
  stageBoundMs,
  continuesAfterNavigation,
  canCancel,
  resultLabel,
  onCancel,
  errorTitle,
  errorDetail,
}: {
  status: BoundedWorkStatus;
  stageLabel: string;
  overallElapsedMs: number;
  stageElapsedMs: number;
  stageBoundMs?: number | null;
  continuesAfterNavigation: boolean;
  canCancel: boolean;
  resultLabel: string;
  onCancel?: () => void;
  errorTitle?: string;
  errorDetail?: string;
}) {
  const awaitingConfirmation = status === "running"
    && stageBoundMs != null
    && stageElapsedMs >= stageBoundMs;
  const phase = awaitingConfirmation ? "awaiting-confirmation" : status;
  const announcement = awaitingConfirmation
    ? "已達上界，等待伺服器確認"
    : status === "succeeded"
      ? "工作完成"
      : status === "interrupted"
        ? "工作已中止"
        : null;

  if (status === "failed") {
    return (
      <InlineAlert state="failed" title={errorTitle ?? "工作失敗"}>
        <div>{errorDetail ?? "工作未完成，請依錯誤指示處理。"}</div>
        <div>結果：{resultLabel}</div>
      </InlineAlert>
    );
  }

  return (
    <section className="ui-bounded-progress" data-progress-phase={phase}>
      <div className="ui-bounded-progress-head">
        <StatusBadge state={stateFor(status)} label={stageLabel} />
        <span className="ui-bounded-progress-overall">總耗時 {formatElapsed(overallElapsedMs)}</span>
      </div>
      <div className="ui-bounded-progress-stage">
        <span>階段耗時 {formatElapsed(stageElapsedMs)}</span>
        {stageBoundMs != null ? <span>本階段上界 {formatElapsed(stageBoundMs)}</span> : null}
      </div>
      {awaitingConfirmation ? (
        <div className="ui-bounded-progress-grace">已達上界，等待伺服器確認</div>
      ) : null}
      {announcement ? (
        <span className="ui-visually-hidden" role="status" aria-live="polite">
          {announcement}
        </span>
      ) : null}
      <div className="ui-bounded-progress-meta">
        <span>{continuesAfterNavigation ? "離開頁面後繼續" : "離開頁面後不保證追蹤"}</span>
        <span>結果：{resultLabel}</span>
      </div>
      {status === "running" && canCancel && onCancel ? (
        <Button tone="danger" size="compact" icon={<Square size={13} />} onClick={onCancel}>
          停止
        </Button>
      ) : null}
    </section>
  );
}
```

There is intentionally no `progress` element, percentage, ETA, persistence,
job registry, or polling behavior. The elapsed-time container is not a live
region; only grace and terminal state transitions are announced, so polling
updates cannot be read aloud every second.

- [x] **Step 4: Add compact BoundedProgress styles**

Append:

```css
.ui-bounded-progress {
  display: grid;
  gap: var(--space-2);
  padding: var(--space-3);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--panel2);
}
.ui-bounded-progress-head,
.ui-bounded-progress-stage,
.ui-bounded-progress-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.ui-bounded-progress-overall,
.ui-bounded-progress-stage,
.ui-bounded-progress-meta { color: var(--muted); font-size: 11.5px; }
.ui-bounded-progress-grace { color: var(--wait); font-weight: 600; }
.ui-bounded-progress > .ui-button { justify-self: start; }
.ui-visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
```

- [x] **Step 5: Export and run the focused battery**

Append:

```ts
export * from "./BoundedProgress";
```

Run:

```bash
npm test --workspace apps/arkscope-web -- src/ui/BoundedProgress.test.tsx src/ui/primitives.test.tsx
npm run typecheck --workspace apps/arkscope-web
```

Expected: 7 BoundedProgress tests and the Task 2 primitive tests PASS;
typecheck PASS.

- [x] **Step 6: Commit Task 4**

```bash
git add apps/arkscope-web/src/ui
git commit -m "feat: add bounded work progress primitive"
```

---

### Task 5: DataTable contract and Holdings first-consumer migration

**Files:**

- Create: `apps/arkscope-web/src/ui/DataTable.tsx`
- Create: `apps/arkscope-web/src/ui/DataTable.test.tsx`
- Modify: `apps/arkscope-web/src/ui/primitives.css`
- Modify: `apps/arkscope-web/src/ui/index.ts`
- Modify: `apps/arkscope-web/src/Holdings.tsx`
- Modify: `apps/arkscope-web/src/Holdings.test.tsx`

- [x] **Step 1: Write generic DataTable RED tests**

Create `DataTable.test.tsx` with the standard jsdom harness. Add these five
tests:

1. `renders_typed_columns_and_rows`
2. `renders_one_full_width_empty_row`
3. `opens_a_labelled_row_action_menu_flips_from_viewport_edge_and_runs_one_action`
4. `escape_closes_the_row_menu_and_restores_its_trigger`
5. `renders_an_inline_expansion_directly_after_its_owner_row`

Representative setup:

```tsx
type Row = { id: number; symbol: string; closed: boolean };
const columns: DataTableColumn<Row>[] = [
  { id: "symbol", header: "Symbol", render: (row) => row.symbol },
];
const rows = [{ id: 1, symbol: "NVDA", closed: false }];

await mount(
  <DataTable
    ariaLabel="Positions"
    rows={rows}
    columns={columns}
    rowKey={(row) => row.id}
    rowLabel={(row) => row.symbol}
    emptyText="尚無持倉"
    actions={(row) => [
      { id: "edit", label: "編輯", onSelect: () => onEdit(row) },
      { id: "close", label: "關閉", tone: "danger", onSelect: () => onClose(row) },
    ]}
  />,
);
```

The menu trigger must be discoverable as `button[aria-label="NVDA 操作"]`, use
`aria-haspopup="menu"`, and expose `aria-expanded`. Menu item labels remain
text, not icon-only commands. Test 3 stubs the menu bounding rectangle below
`window.innerHeight`, asserts `data-placement="up"`, then selects one action.
Because placement runs in `useLayoutEffect`, install the single prototype stub
**before** clicking the trigger:

```ts
const rect = (top: number, height: number): DOMRect => ({
  x: 0,
  y: top,
  top,
  left: 0,
  width: 132,
  height,
  right: 132,
  bottom: top + height,
  toJSON: () => ({}),
});
Object.defineProperty(window, "innerHeight", { value: 600, configurable: true });
vi.spyOn(Element.prototype, "getBoundingClientRect").mockImplementation(function () {
  if ((this as Element).classList.contains("ui-row-action-menu")) return rect(580, 120);
  if ((this as Element).matches('button[aria-haspopup="menu"]')) return rect(500, 28);
  return rect(0, 0);
});

// Only now click the trigger; stubbing the menu element afterward is too late.
```

- [x] **Step 2: Write Holdings migration RED tests before changing production**

Update the current Holdings tests, preserving every existing payload assertion.
Replace `soft closes a manual row after confirmation` with a stronger dialog
test:

```tsx
it("soft closes a manual row only after ConfirmDialog approval", async () => {
  const legacyConfirm = vi.fn(() => { throw new Error("window.confirm must not run"); });
  vi.stubGlobal("confirm", legacyConfirm);
  const calls = stubFetch((url, init) => {
    if (init?.method === "DELETE") {
      return manualPosition({ closed_at: "2026-07-10T00:00:00Z" });
    }
    return snapshot({ positions: [manualPosition()] });
  });
  await mount();
  await flush();

  const trigger = host!.querySelector<HTMLButtonElement>('button[aria-label="NVDA 操作"]')!;
  await act(async () => {
    trigger.click();
  });
  await act(async () => {
    (await buttonByText("關閉")).click();
  });

  expect(host!.querySelector('[role="dialog"]')?.textContent).toContain("顯示已關閉");
  expect(calls.some((call) => call.method === "DELETE")).toBe(false);
  expect(legacyConfirm).not.toHaveBeenCalled();

  await act(async () => { (await buttonByText("取消")).click(); });
  expect(calls.some((call) => call.method === "DELETE")).toBe(false);
  expect(document.activeElement).toBe(trigger);

  await act(async () => {
    trigger.click();
  });
  await act(async () => { (await buttonByText("關閉")).click(); });
  await act(async () => { (await buttonByText("確認關閉")).click(); });
  expect(calls.find((call) => call.method === "DELETE")?.url)
    .toMatch(/\/portfolio\/positions\/40$/);
});
```

Make the Holdings test accounting exact:

- add exactly one new test,
  `shows_loading_before_the_first_portfolio_response`, using a deferred first
  GET and asserting `data-state="loading"`;
- evolve `renders accounts, positions, and currency basis` to assert one `h1`
  PageHeader and the `ready` status;
- evolve `shows ibkr preview as review before applying` to defer the preview
  response, assert `running` while pending, then resolve and assert `partial`
  while preserving every current financial value;
- evolve `does not render a close action for ibkr rows` to open the row menu and
  prove it contains Edit but no Close;
- evolve the manual edit test to prove the editor row follows its owner row and
  still submits the exact current payload;
- leave closed filtering and option separation assertions unchanged.

Do not delete or weaken the existing numeric validation, explicit-null,
read-only sync, apply-refresh, aggregate toggle, or payload tests.

- [x] **Step 3: Run the two suites and verify RED for the intended reasons**

Run:

```bash
npm test --workspace apps/arkscope-web -- src/ui/DataTable.test.tsx src/Holdings.test.tsx
```

Expected: DataTable import fails; new Holdings selectors fail because the row
menu, PageHeader state, and ConfirmDialog are not wired. Existing behavior tests
remain green except the intentionally replaced confirmation test.

- [x] **Step 4: Implement the typed DataTable and row-action menu**

Create `DataTable.tsx`:

```tsx
import { Fragment, useEffect, useLayoutEffect, useRef, useState, type Key, type ReactNode } from "react";
import { MoreHorizontal } from "lucide-react";
import { IconButton } from "./Button";

export interface DataTableColumn<Row> {
  id: string;
  header: ReactNode;
  render: (row: Row) => ReactNode;
  align?: "left" | "right";
  className?: string;
}

export interface DataTableAction<Row> {
  id: string;
  label: string;
  tone?: "default" | "danger";
  disabled?: boolean;
  onSelect: (row: Row, trigger: HTMLButtonElement) => void;
}

function RowActionMenu<Row>({
  row,
  label,
  actions,
}: {
  row: Row;
  label: string;
  actions: DataTableAction<Row>[];
}) {
  const [open, setOpen] = useState(false);
  const [placement, setPlacement] = useState<"up" | "down">("down");
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    if (!open || !menuRef.current || !triggerRef.current) return;
    const menu = menuRef.current.getBoundingClientRect();
    const trigger = triggerRef.current.getBoundingClientRect();
    setPlacement(
      menu.bottom > window.innerHeight && trigger.top >= menu.height ? "up" : "down",
    );
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onPointer = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.defaultPrevented) return;
      if (event.key !== "Escape") return;
      event.preventDefault();
      setOpen(false);
      triggerRef.current?.focus();
    };
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className="ui-row-actions" ref={rootRef}>
      <IconButton
        ref={triggerRef}
        label={`${label} 操作`}
        tone="ghost"
        size="compact"
        icon={<MoreHorizontal size={17} />}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      />
      {open ? (
        <div ref={menuRef} className="ui-row-action-menu" role="menu" data-placement={placement}>
          {actions.map((action) => (
            <button
              key={action.id}
              type="button"
              role="menuitem"
              className={action.tone === "danger" ? "danger" : ""}
              disabled={action.disabled}
              onClick={() => {
                setOpen(false);
                if (triggerRef.current) action.onSelect(row, triggerRef.current);
              }}
            >
              {action.label}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function DataTable<Row>({
  ariaLabel,
  rows,
  columns,
  rowKey,
  rowLabel,
  emptyText,
  actions,
  renderExpandedRow,
}: {
  ariaLabel: string;
  rows: readonly Row[];
  columns: readonly DataTableColumn<Row>[];
  rowKey: (row: Row) => Key;
  rowLabel: (row: Row) => string;
  emptyText: string;
  actions?: (row: Row) => DataTableAction<Row>[];
  renderExpandedRow?: (row: Row) => ReactNode;
}) {
  const actionColumn = Boolean(actions);
  const columnCount = columns.length + (actionColumn ? 1 : 0);
  return (
    <div className="ui-data-table-wrap">
      <table className="ui-data-table" aria-label={ariaLabel}>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.id} className={column.className} data-align={column.align ?? "left"}>
                {column.header}
              </th>
            ))}
            {actionColumn ? <th className="ui-data-table-action-head">操作</th> : null}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr><td className="ui-data-table-empty" colSpan={columnCount}>{emptyText}</td></tr>
          ) : rows.map((row) => {
            const expanded = renderExpandedRow?.(row);
            const rowActions = actions?.(row) ?? [];
            return (
              <Fragment key={rowKey(row)}>
                <tr>
                  {columns.map((column) => (
                    <td key={column.id} className={column.className} data-align={column.align ?? "left"}>
                      {column.render(row)}
                    </td>
                  ))}
                  {actionColumn ? (
                    <td className="ui-data-table-actions">
                      {rowActions.length ? (
                        <RowActionMenu row={row} label={rowLabel(row)} actions={rowActions} />
                      ) : null}
                    </td>
                  ) : null}
                </tr>
                {expanded ? (
                  <tr className="ui-data-table-expanded"><td colSpan={columnCount}>{expanded}</td></tr>
                ) : null}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
```

Keep the generic type consistent; do not use `any` to silence row typing.

- [x] **Step 5: Style DataTable, menus, and the existing Holdings class family**

Append to `primitives.css`:

```css
.ui-data-table-wrap { width: 100%; overflow-x: auto; border: 1px solid var(--border); border-radius: var(--radius-md); }
.ui-data-table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
.ui-data-table th { color: var(--muted); font-size: 11.5px; font-weight: 600; text-align: left; white-space: nowrap; }
.ui-data-table th, .ui-data-table td { padding: 8px 10px; border-bottom: 1px solid color-mix(in srgb, var(--border) 65%, transparent); vertical-align: top; }
.ui-data-table tbody tr:last-child > td { border-bottom: 0; }
.ui-data-table [data-align="right"] { text-align: right; font-variant-numeric: tabular-nums; }
.ui-data-table-empty { color: var(--muted); text-align: center; padding: var(--space-6); }
.ui-data-table-action-head, .ui-data-table-actions { width: 1%; text-align: right; white-space: nowrap; }
.ui-data-table-expanded > td { background: var(--panel2); }
.ui-row-actions { position: relative; display: inline-flex; }
.ui-row-action-menu { position: absolute; z-index: 20; top: calc(100% + 4px); right: 0; min-width: 132px; padding: 4px; border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--panel); box-shadow: 0 4px 14px rgba(0, 0, 0, 0.3); }
.ui-row-action-menu[data-placement="up"] { top: auto; bottom: calc(100% + 4px); }
.ui-row-action-menu button { width: 100%; display: block; padding: 6px 8px; border: 0; border-radius: var(--radius-xs); background: transparent; color: var(--fg); text-align: left; font: inherit; cursor: pointer; }
.ui-row-action-menu button:hover:not(:disabled), .ui-row-action-menu button:focus-visible { background: var(--panel2); outline: none; }
.ui-row-action-menu button.danger { color: var(--bad); }

.ui-section-band { width: 100%; padding: var(--space-4) 0; border-top: 1px solid var(--border); }
.ui-section-band:first-of-type { border-top: 0; padding-top: 0; }
.ui-section-head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); margin-bottom: var(--space-3); flex-wrap: wrap; }
.ui-section-head h2 { margin: 0; font-size: 15px; letter-spacing: 0; }
.ui-action-row { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
.ui-status-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: var(--space-2); }
.ui-metric { min-width: 0; padding: var(--space-3); border: 1px solid var(--border); border-radius: var(--radius-md); background: var(--panel); }
.ui-metric-label { display: block; color: var(--muted); font-size: 11.5px; margin-bottom: var(--space-1); }
.ui-inline-form { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: var(--space-2); align-items: end; }
.ui-inline-form label { display: grid; gap: var(--space-1); color: var(--muted); font-size: 11.5px; }
.ui-inline-form input, .ui-inline-form select, .ui-inline-form textarea { min-height: var(--control-height-default); min-width: 0; padding: 5px 8px; border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--panel2); color: var(--fg); font: inherit; }
```

These are full-width bands, not floating section cards. Account metrics are
allowed repeated framed items and are never nested inside another card.

- [x] **Step 6: Migrate Holdings to PageHeader, state primitives, and DataTable**

Apply these structural changes without changing API calls:

1. Import `PortfolioSyncChange` from `api.ts` and the green UI exports from
   `./ui`.
   Replace every Holdings command `<button>` with shared `Button`/`IconButton`;
   `btn-primary` and `btn-secondary` must disappear. Replace
   `section-band`, `section-head`, `actions`, `status-grid`, `metric`,
   `metric-label`, and `inline-form` with their `ui-*` names from Step 5.
   `table-wrap` disappears because DataTable owns its responsive wrapper.
2. Add `pendingClose: PortfolioPosition | null` state,
   `closeTriggerRef = useRef<HTMLElement | null>(null)`, and
   `closedFilterRef = useRef<HTMLInputElement | null>(null)`, then remove every
   `window.confirm` call. Attach `closedFilterRef` to the existing
   “顯示已關閉持倉” checkbox so confirmed removal has a stable focus fallback.
3. `onCloseRow(position)` performs only the existing DELETE/load sequence; it
   clears `pendingClose` in `finally`.
4. Render one `PageHeader` directly under `<main className="main">`. Its context
   is a StatusBadge computed in this precedence:

```ts
const viewState = err
  ? { state: "failed" as const, label: "載入失敗" }
  : snapshot == null || loading
    ? { state: "loading" as const, label: "載入持倉" }
    : busy
      ? { state: "running" as const, label: "更新中" }
      : positions.length === 0
        ? { state: "empty" as const, label: "尚無持倉" }
        : { state: "ready" as const, label: `${positions.length} 筆持倉` };
```

5. Replace the raw error paragraph with `InlineAlert state="failed"`; retain
   the exact backend message as detail for now because typed Holdings errors are
   not this slice's authority.
6. Render unapplied non-empty preview as
   `StatusBadge state="partial" label="待套用變更"` beside the existing truth
   copy.
7. Use `DataTable<PortfolioSyncChange>` for preview and
   `DataTable<PortfolioPosition>` for both normal and option positions. Numeric
   columns use `align: "right"`; all current format helpers remain unchanged.
8. Row actions are:
   - all rows: Edit;
   - open manual rows only: Close, tone danger, saving the DataTable-provided
     trigger into `closeTriggerRef.current` before setting `pendingClose`;
   - closed rows: no Close;
   - IBKR rows: never Close and never broker-owned field editing.
9. Preserve the current expanded inline editor via `renderExpandedRow`.
10. Render one ConfirmDialog at the end of the surface:

```tsx
<ConfirmDialog
  open={pendingClose != null}
  title={pendingClose ? `關閉 ${pendingClose.symbol}` : "關閉持倉"}
  consequence="這是軟關閉；持倉與筆記會保留，之後可在「顯示已關閉」檢視中查看。"
  confirmLabel="確認關閉"
  busy={pendingClose != null && busy === `close-${pendingClose.id}`}
  returnFocusRef={closeTriggerRef}
  fallbackFocusRef={closedFilterRef}
  onCancel={() => setPendingClose(null)}
  onConfirm={() => { if (pendingClose) void onCloseRow(pendingClose); }}
/>
```

Do not create a hard-delete action or a manual close action for IBKR rows.

- [x] **Step 7: Export DataTable and run the full Holdings battery**

Append:

```ts
export * from "./DataTable";
```

Run:

```bash
npm test --workspace apps/arkscope-web -- src/ui/DataTable.test.tsx src/Holdings.test.tsx src/ui/overlays.test.tsx
npm run typecheck --workspace apps/arkscope-web
```

Expected: all existing Holdings contracts plus the new menu/dialog/state tests
PASS. There must be no `act()` warning introduced by portal cleanup.

- [x] **Step 8: Run the Holdings-specific ratchets**

Run:

```bash
rg -n "window\.confirm|confirm\(" apps/arkscope-web/src/Holdings.tsx
rg -n "hard.?delete|permanent.?delete" apps/arkscope-web/src/Holdings.tsx
rg -n 'className="(btn-primary|btn-secondary|table-wrap|section-band|section-head|actions|status-grid|metric|metric-label|inline-form)(\s|\")' apps/arkscope-web/src/Holdings.tsx
```

Expected: all three commands return no matches.

- [x] **Step 9: Commit Task 5**

```bash
git add apps/arkscope-web/src/ui apps/arkscope-web/src/Holdings.tsx apps/arkscope-web/src/Holdings.test.tsx
git commit -m "feat: migrate holdings to shared ui primitives"
```

---

### Task 6: Investor Profile style repair and migrated-class coverage

**Files:**

- Modify: `apps/arkscope-web/src/InvestorProfilePanel.tsx`
- Modify: `apps/arkscope-web/src/InvestorProfilePanel.test.tsx`
- Modify: `apps/arkscope-web/src/ui/primitives.css`
- Create: `apps/arkscope-web/src/ui/classCoverage.test.ts`

- [x] **Step 1: Write Investor Profile presentation RED tests**

Keep all six current domain tests. Add exactly two tests:

1. `pending_profile_request_uses_loading_state_not_bare_text`
2. `request_failure_uses_alert_semantics`

Then evolve two existing tests without adding test cases:

- `starts_calibration_sends_message_and_shows_proposal_rationale` also asserts
  the pending proposal's `partial` state;
- `save_button_puts_profile` also asserts the success notice's `ready` state.

For the loading test, make `fetch` return a never-resolving promise so the
initial state is observable:

```tsx
it("pending_profile_request_uses_loading_state_not_bare_text", async () => {
  vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(() => {})));
  await mount();
  expect(host!.querySelector('[data-state="loading"]')?.textContent).toContain("載入投資人設定");
});
```

Extend the existing calibration proposal test with:

```ts
expect(host!.querySelector('[data-state="partial"]')?.textContent).toContain("校準提案");
```

Do not change the approved-profile payload, proposal endpoint, message journal,
risk mismatch derivation, or effective-stance assertions.

- [x] **Step 2: Write the literal class-coverage RED test**

Create `classCoverage.test.ts` in the default Node environment:

```ts
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const here = fileURLToPath(new URL(".", import.meta.url));
const css = [
  resolve(here, "../styles.css"),
  resolve(here, "./primitives.css"),
].map((path) => readFileSync(path, "utf8")).join("\n");

function literalClasses(source: string): string[] {
  return Array.from(source.matchAll(/className="([^"]+)"/g))
    .flatMap((match) => match[1].split(/\s+/))
    .filter(Boolean);
}

function hasSelector(name: string): boolean {
  const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`\\.${escaped}(?=[\\s.{:#,>+~\\[])`).test(css);
}

describe("migrated component class coverage", () => {
  it.each([
    ["Holdings", resolve(here, "../Holdings.tsx")],
    ["InvestorProfilePanel", resolve(here, "../InvestorProfilePanel.tsx")],
  ])("defines every literal class used by %s", (_name, path) => {
    const classes = [...new Set(literalClasses(readFileSync(path, "utf8")))];
    const missing = classes.filter((name) => !hasSelector(name));
    expect(missing).toEqual([]);
  });
});
```

This gate intentionally covers only the two migrated consumers. It does not
declare the untouched monolithic app clean.

- [x] **Step 3: Run tests and verify RED**

Run:

```bash
npm test --workspace apps/arkscope-web -- src/InvestorProfilePanel.test.tsx src/ui/classCoverage.test.ts
```

Expected: presentation-state tests fail; class coverage reports the current
undefined families, including `investor-profile-panel`, `ip-grid`, `ip-chip`,
`ip-calibration`, `ip-actions`, `ip-guardrail`, and `ip-calibration-log`.

- [x] **Step 4: Adopt shared state/command primitives without redesigning profile semantics**

In `InvestorProfilePanel.tsx`:

- import `Button`, `InlineAlert`, and `StatusBadge` from `./ui`;
- loading renders `StatusBadge state="loading" label="載入投資人設定"`;
- every command uses `Button` with the same disabled condition and handler;
- the latest draft proposal heading includes
  `StatusBadge state="partial" label="待核准校準提案"`;
- the mismatch line uses the existing `mismatchLabel(mismatch)` as the domain
  label. Map every existing non-`none` value (`unclear`,
  `appetite_above_capacity`, and `capacity_above_appetite`) to `partial`; map
  `none` to `ready`. Do not derive a holdings comparison;
- notice renders `InlineAlert state="ready" title={notice}`;
- error renders `InlineAlert state="failed" title="投資人設定失敗">{err}</InlineAlert>`.

Keep the current DOM ordering: description, enable toggle, raw fields,
preferences, freeform, calibration, mismatch, skill note, draft/save. Slice 5
owns the future hierarchy.

- [x] **Step 5: Add the complete Investor Profile class family**

Append styles that are scoped and unframed at the section level:

```css
.investor-profile-panel { display: grid; gap: var(--space-4); min-width: 0; }
.investor-profile-panel h3, .investor-profile-panel h4 { margin: 0; letter-spacing: 0; }
.investor-profile-panel > label,
.ip-grid > label,
.ip-calibration > label { display: grid; gap: var(--space-1); color: var(--muted); }
.investor-profile-panel input[type="text"],
.investor-profile-panel input[type="number"],
.investor-profile-panel select,
.investor-profile-panel textarea {
  width: 100%;
  min-width: 0;
  min-height: var(--control-height-default);
  padding: 5px 8px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--panel2);
  color: var(--fg);
  font: inherit;
}
.investor-profile-panel textarea { min-height: 88px; resize: vertical; }
.investor-profile-panel input:focus-visible,
.investor-profile-panel select:focus-visible,
.investor-profile-panel textarea:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; }
.ip-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: var(--space-3); }
.investor-profile-panel fieldset { margin: 0; padding: var(--space-3) 0 0; border: 0; border-top: 1px solid var(--border); }
.investor-profile-panel legend { padding: 0; margin-bottom: var(--space-2); color: var(--fg); font-weight: 600; }
.ip-chip { display: inline-flex; align-items: center; gap: var(--space-1-5); margin: 0 var(--space-2) var(--space-2) 0; padding: 3px 8px; border: 1px solid var(--border); border-radius: var(--radius-pill); color: var(--muted); }
.ip-chip input { margin: 0; }
.ip-calibration { display: grid; gap: var(--space-3); padding: var(--space-4) 0; border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); }
.ip-calibration-log { display: grid; gap: var(--space-2); max-height: 240px; overflow: auto; padding-left: var(--space-3); border-left: 2px solid var(--border); }
.ip-actions { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
.ip-guardrail { display: flex; align-items: flex-start; gap: var(--space-2); padding: var(--space-2) 0; color: var(--muted); }
.ip-guardrail ul { margin: 0; padding-left: var(--space-5); }
```

Do not turn `.investor-profile-panel`, `.ip-calibration`, or `.ip-guardrail`
into nested cards.

- [x] **Step 6: Run focused profile/class tests and the two consumer suites**

Run:

```bash
npm test --workspace apps/arkscope-web -- src/InvestorProfilePanel.test.tsx src/Holdings.test.tsx src/ui/classCoverage.test.ts src/ui/primitives.test.tsx
npm run typecheck --workspace apps/arkscope-web
```

Expected: all existing profile and Holdings tests plus new state/class tests
PASS; `missing` is `[]`; typecheck PASS.

- [x] **Step 7: Commit Task 6**

```bash
git add apps/arkscope-web/src/InvestorProfilePanel.tsx apps/arkscope-web/src/InvestorProfilePanel.test.tsx apps/arkscope-web/src/ui/primitives.css apps/arkscope-web/src/ui/classCoverage.test.ts
git commit -m "fix: repair investor profile presentation"
```

---

### Task 7: Mechanical ratchets, full verification, visual proof, and review handoff

**Files:**

- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`
- Modify: `docs/superpowers/plans/2026-07-12-p2-8-slice-1-ui-primitives.md`
- External authenticated review after code GREEN: Claude Design component
  specimens and radius reconciliation; no repo file is written by DesignSync.

- [x] **Step 1: Run the complete focused frontend battery**

Run:

```bash
npm test --workspace apps/arkscope-web -- \
  src/ui/tokens.test.ts \
  src/ui/primitives.test.tsx \
  src/ui/overlays.test.tsx \
  src/ui/BoundedProgress.test.tsx \
  src/ui/DataTable.test.tsx \
  src/ui/classCoverage.test.ts \
  src/Holdings.test.tsx \
  src/InvestorProfilePanel.test.tsx
```

Expected: all focused tests PASS with no React `act`, portal cleanup, unhandled
promise, or accessibility warnings.

- [x] **Step 2: Run the complete frontend suite and exact accounting**

The base is authoritative and was rechecked while writing this plan:

```text
Test Files  32 passed (32)
Tests       296 passed (296)
```

This plan adds six test files and exactly 51 net tests after review hardening:

| Task | Net tests |
| --- | ---: |
| Tokens | 5 |
| Controls/PageHeader/common state | 14 |
| Drawer/ConfirmDialog | 10 |
| BoundedProgress | 9 |
| DataTable + one new Holdings state test | 7 |
| Investor Profile + class coverage | 6 |
| **Total** | **51** |

Run:

```bash
npm --workspace apps/arkscope-web test
npm --workspace apps/arkscope-web run typecheck
npm --workspace apps/arkscope-web run build
```

Expected: `38 files / 347 tests`, typecheck PASS, production build PASS. Any
count other than +51 is a finding: reconcile the named-test ledger rather than
rounding or weakening it.

- [x] **Step 3: Run static ratchets**

Run each command and inspect the complete untruncated output:

```bash
rg -l "window\.confirm|\bconfirm\(" apps/arkscope-web/src --glob '*.tsx'
```

Expected remaining legacy owners, exactly:

```text
apps/arkscope-web/src/Research.tsx
apps/arkscope-web/src/Settings.tsx
apps/arkscope-web/src/Universe.tsx
apps/arkscope-web/src/Watchlist.tsx
```

Holdings must be absent; no new owner may appear.

```bash
rg -n "@media" apps/arkscope-web/src/ui
rg -n "border-radius:\s*(10|14)px|radius-lg" apps/arkscope-web/src/ui
rg -n "960" apps/arkscope-web/src/ui
rg -n "hard.?delete|permanent.?delete" apps/arkscope-web/src/Holdings.tsx apps/arkscope-web/src/InvestorProfilePanel.tsx
```

Expected: the first, second, and fourth checks have zero production matches.
The `960` check is limited to `tokens.json` and `tokens.test.ts`; no component,
hook, or CSS file duplicates the literal. Test prose may name forbidden values
only when asserting their absence.

```bash
npm test --workspace apps/arkscope-web -- src/ui/classCoverage.test.ts
git diff --exit-code 4e229a8 -- \
  apps/arkscope-web/src/App.tsx \
  apps/arkscope-web/src/Research.tsx \
  apps/arkscope-web/src/Settings.tsx \
  apps/arkscope-web/src/api.ts \
  apps/arkscope-web/src/styles.css \
  src tests
```

Expected: class coverage PASS; diff command has no output. This proves Slice 1
did not smuggle shell/Research/Settings/API/backend behavior into the primitive
foundation.

- [x] **Step 4: Run no-PG/fresh-start smoke**

Run:

```bash
python src/smoke/pg_unreachable_e2e.py
```

Expected: `ok: true`, all checks pass, and `pg_attempts: []`.

- [x] **Step 5: Run visual and interaction checks at the required viewports**

Start the branch web server after the production build. Use 8430 if free;
otherwise select the next free 84xx port and report the actual URL:

```bash
npm run dev --workspace apps/arkscope-web -- --host 127.0.0.1
```

With the normal local sidecar, inspect Holdings and Settings → Investor Profile
at:

- 1440x900
- 1024x768
- 961x768
- 959x768
- 390x844

Capture screenshots under `/tmp`, not the repository. Verify:

1. PageHeader, account metrics, forms, and actions do not overlap or resize
   unpredictably.
2. Holdings financial columns retain readable type and use horizontal scrolling
   rather than compressed/overlapping text.
3. The row-action menu remains within the viewport at 390px.
4. ConfirmDialog fits at every viewport, focuses Cancel, traps Tab, closes on
   Escape, and returns focus to the row trigger.
5. Closed filtering, options separation, preview-before-apply, and inline edit
   remain visible and usable.
6. Investor Profile has no browser-default unstyled control family, no nested
   cards, and no clipped calibration journal/actions.
7. At 961 and 959, no migrated component introduces a second shell breakpoint
   or layout jump. The app shell itself remains Slice 2 behavior.
8. Color is not the only state signal: every badge/alert also has icon and text.

Drawer and BoundedProgress are not wired into product surfaces in Slice 1.
Their visual specimens are checked during the Design Kit sync in Step 8; do not
add a hidden product route or permanent component gallery to manufacture a
consumer.

- [x] **Step 6: Run canonical backend A/B and frontend base/head accounting**

Compare virgin archives of base `4e229a8` and the final tip under identical
environment isolation.

Backend acceptance, because no backend/test file is modified:

- failure sets identical in both directions;
- passed/skipped/warning/error counters exactly identical;
- collected backend tests added/removed = `0/0`;
- no generated artifact remains in either archive.

Frontend acceptance:

- base `32/296`;
- head `38/347`;
- all tests pass on both sides;
- delta is exactly six files and 51 tests.

If the known single-process TestClient/lifespan noise appears, preserve logs and
use the established reviewer canonical protocol. Do not claim a partial A/B as
PASS.

- [x] **Step 7: Mark implementation review-ready, not complete**

After Steps 1-5 pass, and after Step 6 either passes or records the known
single-process hang without claiming a partial PASS:

1. Change this plan header to `IMPLEMENTED FOR REVIEW`.
2. Record each RED reason, focused/full counts, static gates, screenshots, smoke,
   and A/B evidence.
3. Add a newest-first map entry identifying the branch/tip and review focus.
4. Do not mark Slice 1 shipped/live and do not merge.

- [x] **Step 8: Reviewer checkpoint and incremental Design Kit sync**

Reviewer focus:

1. token source is physically single and 960 is not copied;
2. no general framed radius exceeds 8px;
3. Drawer/ConfirmDialog focus and cleanup are real DOM tests;
4. BoundedProgress keeps stage/overall bounds distinct and has no fake percent;
5. DataTable menu/inline expansion preserve Holdings payload behavior;
6. ConfirmDialog removes only the Holdings `window.confirm` owner;
7. Investor Profile changes remain presentation-only;
8. class coverage cannot pass by substring false positives.

After code review is green, the authenticated DesignSync owner updates only the
Slice 1 companion depth:

- reconcile `radius-lg` to 8px or remove it; do not add a modal exception;
- add component specimens for Button/IconButton, PageHeader, StatusBadge/
  InlineAlert, transient Drawer, ConfirmDialog, compact BoundedProgress, and
  DataTable row actions;
- do not prebuild Slice 2 shell or Slice 3 Research screens.

Read back all changed Design files and record the DesignSync plan ID in this
plan/map. External sync failure blocks visual closeout but must not trigger an
unreviewed app-code workaround.

- [x] **Step 9: Commit review-ready documentation and stop**

```bash
git add docs/design/PROJECT_PRIORITY_MAP.md docs/superpowers/plans/2026-07-12-p2-8-slice-1-ui-primitives.md
git commit -m "docs: mark ui primitives review-ready"
```

Stop for user approval. Do not fast-forward master, delete the worktree, or
start Slice 2/Notes from this plan.

---

## Stop Conditions

Stop and report instead of widening scope if any of these occurs:

1. A primitive requires changes to `App.tsx`, Research, Settings IA, `api.ts`,
   or backend code to turn green.
2. Drawer needs pinnable Evidence behavior, persistent work ownership, or a
   background-job store.
3. BoundedProgress needs invented percentages, ETA, polling, or persistence.
4. DataTable migration changes a Holdings request payload, permits manual
   broker-field edits, hard deletes a position, or exposes Close for IBKR rows.
5. Investor Profile tests require changing profile normalization, proposal
   approval, calibration storage, prompt injection, qualitative risk meaning,
   or control order.
6. A new visual frame requires radius over 8px.
7. A second shell breakpoint literal appears outside `tokens.json`/token tests.
8. Full frontend accounting is not exactly +51 or backend A/B changes.
9. Visual checks show overlap, clipped controls, unreadable financial columns,
   or a dialog/menu outside the viewport.

## Review Handoff

Implementation is complete only when Tasks 1-7 are implemented, automated and
visual evidence is recorded, review is green, and the incremental Design Kit
sync is read back. Merge remains a separate user decision.
