# P2.8 Settings Stabilization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Status: IMPLEMENTED FOR REVIEW — NOT MERGED. Reviewer canonical A/B remains open because the Codex environment reproduces the known single-process TestClient/lifespan hang; the file-isolated fallback is strictly equal.**

**Goal:** Repair the bounded Settings overlap and stale-copy defects, add truthful scheduler progress, and rename the Investor Profile risk-appetite label without changing backend behavior or pre-implementing later P2.8 slices.

**Architecture:** Keep all transport and persistence contracts intact. Add one Data Sources-only progress component and one pure domain-state mapper, wire them into the existing `Settings.tsx` surface, and stabilize the existing tables with explicit scroll owners and reviewed widths rather than migrating them to `DataTable`. Remove two migration-era News controls from rendering while leaving their API/profile/env compatibility paths untouched.

**Tech Stack:** React 18, TypeScript 5.5, Vitest/jsdom, existing Slice 1 UI primitives, CSS, Vite.

## Implementation Evidence (2026-07-13)

Implementation branch: `codex/p2-8-settings-stabilization`, based on
`332a92b`; behavioral comparison authority remains plan base `554e94b`.

### Task commits and RED evidence

- Task 1 — `c32524b feat: add truthful source run progress`: RED because
  `SourceRunProgress` did not exist and the four known/indeterminate progress
  contracts could not import or render.
- Task 2 — `87e5490 feat: map data source states to shared status semantics`:
  RED because the pure Data Sources state mapper did not exist, including the
  required disabled/skip neutrality and no-`interrupted` contract.
- Task 3 — `96e050d feat: stabilize data source run status`: RED because the
  Settings schedule still rendered the old one-line progress/source-badge
  shape and lacked the new status/progress selectors.
- Task 4 — `0f940f3 fix: contain wide settings data tables`: RED because the
  five owner classes/minimum table widths were absent and long content had no
  explicit horizontal-scroll ownership.
- Task 5 — `4a44ce7 fix: replace migration-era settings copy`: RED because the
  two vestigial News controls and scoped migration/storage narration still
  rendered. The JSX test fixture was corrected to the repository's existing
  `React.createElement` harness before accepting RED.
- Task 6 — `113e5fd fix: rename investor risk appetite label`: RED because the
  production Investor Profile and mismatch labels still exposed
  `風險胃納`.
- Review fix — `fe83011 fix: keep skipped scheduler history truthful`: an
  independent review found that three real writer-lock paths can persist
  durable `skipped`, while the UI mapped it to `empty`/`尚未執行`; it also found
  authored scheduler copy exposing `job_runs`, `data/locks/`, and app/CLI
  internals. RED pinned neutral `上次已跳過` rendering, no status badge, the
  helper mapping, and user-language-only protection copy before the fix.

### Closed gates

- Focused frontend: `9` owner files / `63` tests passed.
- Full frontend: `41` files / `366` tests passed, exactly `+3` files / `+19`
  tests over the `38 / 347` baseline. Typecheck and production build passed;
  only the existing Vite chunk-size warning remains.
- Backend/API byte boundary against `554e94b` is empty for
  `apps/arkscope-web/src/api.ts`, `src`, `tests`, and `data_sources`.
- Static semantic gates are clean: no removed News handlers in Settings, no
  rendered `source_badges`, no polling `aria-live`, no synthesized
  `interrupted`, and no added media query. Both compatibility API exports
  remain.
- No-PG smoke passed all `24` checks with `ok: true` and `pg_attempts: []`.
- Browser gate passed at `1440x900`, `1024x768`, `961x768`, `959x768`, and
  `390x844`: no page overflow or progress/detail overlap; five table scroll
  owners remained usable; `17 / 149 · 11%`, indeterminate, disabled schedule,
  provenance, and copy contracts rendered correctly. Evidence is under
  `/tmp/arkscope-settings-stabilization-<viewport>*.png`. Temporary sidecar and
  Vite processes were stopped after capture.

### Open reviewer gate

Canonical single-process pytest did not complete in this Codex environment:
base hung for more than eight minutes in the existing FastAPI
`TestClient`/lifespan family and was terminated; no canonical pass is claimed.
As bounded fallback, virgin base/head archives were run file-isolated under
identical bare-home, scheduler-disabled, credential-scrubbed conditions. Both
collected `4185` nodes across `216` files; the same four files timed out
(`test_agents.py`, `test_api.py`, `test_monitor.py`,
`test_signal_factors_p1.py`), and the remaining `3995` tests were exactly equal:
`3894 passed / 27 failed / 1 error / 73 skipped / 20 warnings`. Problem sets,
timeout sets, totals, and normalized per-file results are all equal. Reviewer
canonical A/B is still required before merge. The later review fix changed only
TypeScript/TSX frontend files; the backend/API byte-identity gate remained
empty, so it does not alter this backend fallback comparison.

---

## 0. Authority, Baseline, and Locked Decisions

### Authority

- Product authority:
  `docs/superpowers/specs/2026-07-12-p2-8-settings-stabilization-design.md`
- Shell authority:
  `docs/superpowers/specs/2026-07-12-p2-8-canonical-shell-interaction-design.md`
- Priority authority: `docs/design/PROJECT_PRIORITY_MAP.md`
- Implementation base: `554e94b` (`docs: clear settings stabilization review`)

### Verified baseline

- Frontend: `38` files / `347` tests pass.
- `ScheduleSourceState.progress` already carries
  `{ done: number; total: number; current: string } | null`.
- `StatusBadge` and `CommonUiState` are exported from `./ui`.
- The two News controls call `setUseLocalNews()` and
  `setNormalizedNewsWrites()` from `api.ts`.
- Both controls are already hidden when `news_hard_local=true`, but their
  pre-exit branches and handlers remain in `Settings.tsx`.
- Provider, SA, FRED, credential, and schedule tables are plain existing
  tables; this slice does not convert them to `DataTable`.
- App Records remains unreachable (`enabled: false`) and is not modified.

### Locked decisions

1. This is frontend-only. No file below `src/`, `tests/`, or `data_sources/`
   changes.
2. Known schedule progress uses the real DTO: current item on its own line,
   progress track on its own line, and `done / total` plus rounded percentage
   below it.
3. Missing, invalid, or non-positive totals are indeterminate. No fabricated
   percentage or time estimate is shown.
4. Polling remains five seconds and does not use `aria-live`.
5. A disabled provider or schedule is muted domain text, not a common-state
   badge. The schedule text is `排程關閉`; manual Run remains available when
   the schedule is disabled. This surface never synthesizes `interrupted`.
6. Raw `source_badges` and technical source descriptions stop rendering. The
   DTO remains unchanged.
7. The direct-news and normalized-writes checkboxes, handlers, and imports are
   removed from `Settings.tsx`. Their `api.ts` helpers, backend routes, profile
   settings, env overrides, DTO fields, and resolution logic remain untouched.
   The direct-news OFF branch is recorded as post-exit vestigial compatibility,
   not as a user-selectable normal-mode route.
8. Normal copy preserves actionable provider/credential ownership and removes
   PG/SQLite/local/legacy/mirror/migration narration.
9. `風險胃納` becomes `風險意願`; schema field `risk_appetite`, numeric scale,
   derivation, and prompt behavior do not change.
10. No Settings extraction, IA grouping, anchors, search, shell work, startup
    optimization, or qualitative Investor Profile redesign enters this slice.
11. Existing compatibility label helpers in `marketDataDisplay.ts` may remain
    for old contracts/tests, but the touched normal Settings surfaces stop
    rendering them. Do not delete tests merely to clear old strings repo-wide.
12. No Design Kit sync is required: this adds a domain component and consumes
    existing primitives without changing primitive APIs or tokens.

### Planned test accounting

- New test files: `3`.
- Original planned collected tests: `18`; final collected tests: `19` after one
  RED-first implementation-review regression test for persisted skipped
  scheduler history.
- Existing tests rewritten in place: no net count change.
- Final frontend accounting: `41` files / `366` tests.
- Expected backend collection delta: `+0 / -0`.

If implementation changes these numbers, stop and reconcile every added or
removed test before declaring review-ready.

### Stop-loss conditions

Stop and report instead of broadening the slice if any of these becomes
necessary:

- backend DTO, route, scheduler, storage, or provider changes;
- a new polling endpoint or timer;
- migration to `DataTable`;
- Settings section extraction or navigation changes beyond the ruled News
  title/copy;
- a new responsive breakpoint or viewport-scaled font;
- changes to App Records, Permissions, Portfolio, Research, or shell layout;
- sanitizing arbitrary provider/runtime error payloads rather than authored UI
  copy;
- removal of compatibility API helpers or backend tests for the hidden News
  controls.

---

## File Map

### Create

- `apps/arkscope-web/src/SourceRunProgress.tsx`
  - Data Sources-only known/indeterminate scheduler progress.
- `apps/arkscope-web/src/SourceRunProgress.test.tsx`
  - Progress truthfulness, ARIA, clamping, and no-live-region contracts.
- `apps/arkscope-web/src/dataSourcesPresentation.ts`
  - Pure mappings from existing provider/SA/schedule domain states to common UI
    states.
- `apps/arkscope-web/src/dataSourcesPresentation.test.ts`
  - Complete mapping table and duplicate-run classification.
- `apps/arkscope-web/src/SettingsStabilizationCss.test.ts`
  - Static scroll-owner/min-width/wrapping contracts that jsdom cannot lay out.

### Modify

- `apps/arkscope-web/src/Settings.tsx`
  - Progress/state wiring, scroll wrappers, authored copy, News control removal.
- `apps/arkscope-web/src/styles.css`
  - Domain progress and bounded table-layout rules; no new breakpoint.
- `apps/arkscope-web/src/SettingsProviderConfig.test.ts`
  - Non-null progress fixtures, disabled schedule, state badges, long content,
    and wrapper integration.
- `apps/arkscope-web/src/SettingsNewsStorage.test.ts`
  - News status copy and both hidden-control polarities.
- `apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts`
  - Normal Market/Macro/directory language and App Records exclusion.
- `apps/arkscope-web/src/InvestorProfilePanel.tsx`
  - Three visible risk-appetite labels.
- `apps/arkscope-web/src/InvestorProfilePanel.test.tsx`
  - Updated user-facing terminology assertions.
- `apps/arkscope-web/src/personalizationDisplay.ts`
  - Two mismatch labels.
- `apps/arkscope-web/src/personalizationDisplay.test.ts`
  - Updated mismatch label pin.
- `docs/design/PROJECT_PRIORITY_MAP.md`
  - Review-ready/merged closeout only after all gates.
- `docs/superpowers/plans/2026-07-12-p2-8-settings-stabilization.md`
  - Task ledger and final evidence.
- `docs/superpowers/specs/2026-07-12-p2-8-settings-stabilization-design.md`
  - Status flip only after implementation review/merge.

### Must not modify

- `apps/arkscope-web/src/api.ts`
- `apps/arkscope-web/src/ui/**`
- `src/**`
- `tests/**`
- `data_sources/**`
- App Records implementation/copy
- P2.8 Slice 2/3/4/5 files and behavior

---

### Task 0: Create the Isolated Worktree and Reconfirm Baseline

**Files:** none

- [ ] **Step 1: Use the required worktree workflow**

Invoke `superpowers:using-git-worktrees`, then create the implementation
worktree from the reviewed plan tip on `master`:

```bash
git worktree add /tmp/arkscope-p2-8-settings-stabilization \
  -b codex/p2-8-settings-stabilization master
ln -s /mnt/md0/PycharmProjects/ArkScope/node_modules \
  /tmp/arkscope-p2-8-settings-stabilization/node_modules
```

Do not implement in the user's main checkout. Record the actual branch-point
hash in this plan ledger; code/test behavior is still compared to authority
base `554e94b` because intervening commits are docs-only. The dependency
symlink is worktree-only and must be removed with the worktree after merge.

- [ ] **Step 2: Reconfirm the clean frontend baseline**

From the worktree:

```bash
npm test --workspace apps/arkscope-web
npm run typecheck --workspace apps/arkscope-web
npm run build --workspace apps/arkscope-web
```

Expected: `38` files / `347` tests, typecheck green, build green except the
known chunk-size warning.

- [ ] **Step 3: Reconfirm the frontend-only boundary before editing**

```bash
git diff --exit-code 554e94b -- apps/arkscope-web/src/api.ts src tests data_sources
```

Expected: no output. If a reviewed plan correction changed product/backend
files after `554e94b`, stop and rebase the authority instead of silently
absorbing it.

---

### Task 1: Add Truthful Source Run Progress

**Files:**
- Create: `apps/arkscope-web/src/SourceRunProgress.test.tsx`
- Create: `apps/arkscope-web/src/SourceRunProgress.tsx`
- Modify: `apps/arkscope-web/src/styles.css`

- [ ] **Step 1: Write four failing component tests**

Create `SourceRunProgress.test.tsx` with the repo's React 18/jsdom harness. The
four tests must be named exactly:

1. `renders_known_progress_on_separate_lines_with_real_aria_values`
2. `clamps_the_visual_percentage_without_inventing_a_count`
3. `renders_missing_progress_as_indeterminate_without_a_live_region`
4. `treats_zero_or_negative_totals_as_indeterminate`

Use this complete test shape:

```tsx
/** @vitest-environment jsdom */
import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it } from "vitest";

import { SourceRunProgress } from "./SourceRunProgress";

let host: HTMLDivElement | null = null;
let root: ReturnType<typeof createRoot> | null = null;

async function mount(progress: { done: number; total: number; current: string } | null) {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(
      <SourceRunProgress
        sourceLabel="IBKR 即時股價"
        running
        progress={progress}
      />,
    );
  });
  return host;
}

afterEach(() => {
  if (root) act(() => root!.unmount());
  host?.remove();
  root = null;
  host = null;
});

describe("SourceRunProgress", () => {
  it("renders_known_progress_on_separate_lines_with_real_aria_values", async () => {
    const node = await mount({
      done: 7,
      total: 10,
      current: "BRK.B — unusually long current contract label that must wrap",
    });
    expect(node.querySelector(".source-run-current")?.textContent).toContain("BRK.B");
    expect(node.querySelector(".source-run-counts")?.textContent).toBe("7 / 10 · 70%");
    const bar = node.querySelector<HTMLElement>("[role='progressbar']");
    expect(bar?.getAttribute("aria-label")).toBe("IBKR 即時股價執行進度");
    expect(bar?.getAttribute("aria-valuemin")).toBe("0");
    expect(bar?.getAttribute("aria-valuemax")).toBe("10");
    expect(bar?.getAttribute("aria-valuenow")).toBe("7");
  });

  it("clamps_the_visual_percentage_without_inventing_a_count", async () => {
    const node = await mount({ done: 12, total: 10, current: "NVDA" });
    expect(node.querySelector(".source-run-counts")?.textContent).toBe("12 / 10 · 100%");
    expect(node.querySelector<HTMLElement>(".source-run-track-fill")?.style.width).toBe("100%");
    expect(node.querySelector("[role='progressbar']")?.getAttribute("aria-valuenow")).toBe("10");
  });

  it("renders_missing_progress_as_indeterminate_without_a_live_region", async () => {
    const node = await mount(null);
    expect(node.textContent).toContain("執行中");
    expect(node.querySelector("[role='progressbar']")).toBeNull();
    expect(node.querySelector("[aria-live]")).toBeNull();
    expect(node.querySelector(".source-run-current")).toBeNull();
  });

  it("treats_zero_or_negative_totals_as_indeterminate", async () => {
    for (const total of [0, -1]) {
      if (root) act(() => root!.unmount());
      host?.remove();
      root = null;
      host = null;
      const node = await mount({ done: 1, total, current: "AAPL" });
      expect(node.querySelector("[role='progressbar']")).toBeNull();
      expect(node.textContent).toContain("執行中");
    }
  });
});
```

- [ ] **Step 2: Run the tests and verify the expected RED**

Run:

```bash
npm test --workspace apps/arkscope-web -- src/SourceRunProgress.test.tsx
```

Expected: FAIL because `./SourceRunProgress` does not exist. A syntax, harness,
or environment failure is not the accepted RED.

- [ ] **Step 3: Implement the minimal domain component**

Create `SourceRunProgress.tsx`:

```tsx
import type { ScheduleSourceState } from "./api";
import { StatusBadge } from "./ui";

export function SourceRunProgress({
  sourceLabel,
  running,
  progress,
}: {
  sourceLabel: string;
  running: boolean;
  progress: ScheduleSourceState["progress"];
}) {
  if (!running) return null;

  const known = progress !== null
    && Number.isFinite(progress.done)
    && Number.isFinite(progress.total)
    && progress.total > 0;
  const safeDone = known ? Math.max(0, progress.done) : 0;
  const boundedDone = known ? Math.min(safeDone, progress.total) : 0;
  const percent = known
    ? Math.max(0, Math.min(100, Math.round((boundedDone / progress.total) * 100)))
    : 0;

  return (
    <div className="source-run-progress" data-progress={known ? "known" : "indeterminate"}>
      <StatusBadge state="running" label="執行中" />
      {known ? (
        <>
          <div className="source-run-current">{progress.current || "處理中"}</div>
          <div
            className="source-run-track"
            role="progressbar"
            aria-label={`${sourceLabel}執行進度`}
            aria-valuemin={0}
            aria-valuemax={progress.total}
            aria-valuenow={boundedDone}
          >
            <span className="source-run-track-fill" style={{ width: `${percent}%` }} />
          </div>
          <div className="source-run-counts muted tiny">
            {safeDone} / {progress.total} · {percent}%
          </div>
        </>
      ) : null}
    </div>
  );
}
```

Add only these CSS rules to the Data Sources block in `styles.css`:

```css
.source-run-progress {
  display: grid;
  gap: 5px;
  min-width: 0;
}
.source-run-current {
  min-width: 0;
  white-space: normal;
  overflow-wrap: anywhere;
  line-height: 1.35;
}
.source-run-track {
  width: 100%;
  height: 6px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--panel2);
}
.source-run-track-fill {
  display: block;
  height: 100%;
  background: var(--accent);
}
.source-run-counts {
  white-space: nowrap;
}
```

Do not add `aria-live`, animation, elapsed time, a generic progress primitive,
or another timer.

- [ ] **Step 4: Run focused tests and typecheck**

```bash
npm test --workspace apps/arkscope-web -- src/SourceRunProgress.test.tsx
npm run typecheck --workspace apps/arkscope-web
```

Expected: `4` progress tests pass; typecheck passes.

- [ ] **Step 5: Commit Task 1**

```bash
git add apps/arkscope-web/src/SourceRunProgress.tsx \
  apps/arkscope-web/src/SourceRunProgress.test.tsx \
  apps/arkscope-web/src/styles.css
git commit -m "feat: add truthful source run progress"
```

---

### Task 2: Add Data Sources Common-State Mapping

**Files:**
- Create: `apps/arkscope-web/src/dataSourcesPresentation.test.ts`
- Create: `apps/arkscope-web/src/dataSourcesPresentation.ts`

- [ ] **Step 1: Write four failing pure-mapping tests**

Create `dataSourcesPresentation.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import {
  durableScheduleCommonState,
  providerCommonState,
  saSegmentCommonState,
  scheduleSkipCommonState,
} from "./dataSourcesPresentation";
import type { ScheduleSourceState } from "./api";

const schedule = (over: Partial<ScheduleSourceState> = {}): ScheduleSourceState => ({
  label: "Polygon news",
  description: "collector",
  ibkr: false,
  provider_fetch: true,
  source_mode: "direct_local",
  write_target: "market_data.db",
  source_badges: [],
  retired: false,
  retired_reason: null,
  enabled: true,
  interval_minutes: 30,
  default_interval_minutes: 30,
  running: false,
  progress: null,
  last_attempt_at: null,
  last_result: null,
  gap_planned: false,
  durable_state: null,
  job_name: "collect.polygon_news",
  ...over,
});

describe("Data Sources common-state mapping", () => {
  it("maps_badged_provider_statuses_and_leaves_disabled_neutral", () => {
    expect({
      connected: providerCommonState("connected"),
      stale: providerCommonState("stale"),
      maintenance: providerCommonState("maintenance"),
      no_signal: providerCommonState("no_signal"),
      not_configured: providerCommonState("not_configured"),
      missing_key: providerCommonState("missing_key"),
      disabled: providerCommonState("disabled"),
    }).toEqual({
      connected: "ready",
      stale: "stale",
      maintenance: "partial",
      no_signal: "empty",
      not_configured: "blocked",
      missing_key: "blocked",
      disabled: null,
    });
  });

  it("maps_sa_segments_to_ready_partial_and_failed", () => {
    expect(["ok", "warn", "fail"].map((state) =>
      saSegmentCommonState(state as "ok" | "warn" | "fail")))
      .toEqual(["ready", "partial", "failed"]);
  });

  it("maps_durable_schedule_history_without_confusing_disabled_schedule_state", () => {
    expect(durableScheduleCommonState(schedule({
      durable_state: { last_status: "succeeded", last_error: null, continuation: null, last_attempt: null, updated_at: null },
    }))).toBe("ready");
    expect(durableScheduleCommonState(schedule({
      durable_state: { last_status: "partial", last_error: null, continuation: { deferred: ["NVDA"] }, last_attempt: null, updated_at: null },
    }))).toBe("partial");
    expect(durableScheduleCommonState(schedule({
      durable_state: { last_status: "failed", last_error: "boom", continuation: null, last_attempt: null, updated_at: null },
    }))).toBe("failed");
    expect(durableScheduleCommonState(schedule({ enabled: true }))).toBe("empty");
    expect(durableScheduleCommonState(schedule({ enabled: false }))).toBeNull();
  });

  it("maps_duplicate_skips_to_blocked_and_other_skips_to_neutral", () => {
    expect(scheduleSkipCommonState("already running in another process")).toBe("blocked");
    expect(scheduleSkipCommonState("IBKR gateway busy (lock timeout)")).toBeNull();
    expect(scheduleSkipCommonState(null)).toBeNull();
  });
});
```

- [ ] **Step 2: Verify the expected RED**

```bash
npm test --workspace apps/arkscope-web -- src/dataSourcesPresentation.test.ts
```

Expected: FAIL because `dataSourcesPresentation.ts` does not exist.

- [ ] **Step 3: Implement the pure mapping module**

Create `dataSourcesPresentation.ts`:

```ts
import type {
  ProviderStatus,
  SAExtensionHealthSegment,
  ScheduleSourceState,
} from "./api";
import type { CommonUiState } from "./ui";

export function providerCommonState(status: ProviderStatus): CommonUiState | null {
  switch (status) {
    case "connected": return "ready";
    case "stale": return "stale";
    case "maintenance": return "partial";
    case "no_signal": return "empty";
    case "not_configured":
    case "missing_key": return "blocked";
    case "disabled": return null;
  }
}

export function saSegmentCommonState(
  state: SAExtensionHealthSegment["state"],
): CommonUiState {
  if (state === "ok") return "ready";
  if (state === "warn") return "partial";
  return "failed";
}

export function durableScheduleCommonState(
  source: ScheduleSourceState,
): CommonUiState | null {
  switch (source.durable_state?.last_status) {
    case "succeeded": return "ready";
    case "partial": return "partial";
    case "failed": return "failed";
    case "running": return source.durable_state.running_stale ? "stale" : "running";
    default: return source.enabled ? "empty" : null;
  }
}

export function scheduleSkipCommonState(
  reason: string | null | undefined,
): CommonUiState | null {
  return reason?.includes("already running") ? "blocked" : null;
}
```

This module classifies presentation only. It must not derive provider health,
schedule completeness, or retry policy. It must not return `interrupted`:
that common state is reserved for an actually cancelled/interrupted work item,
which this surface does not currently expose.

- [ ] **Step 4: Run focused tests and typecheck**

```bash
npm test --workspace apps/arkscope-web -- src/dataSourcesPresentation.test.ts
npm run typecheck --workspace apps/arkscope-web
```

Expected: `4` mapping tests pass; typecheck passes.

- [ ] **Step 5: Commit Task 2**

```bash
git add apps/arkscope-web/src/dataSourcesPresentation.ts \
  apps/arkscope-web/src/dataSourcesPresentation.test.ts
git commit -m "feat: map data source states to shared status semantics"
```

---

### Task 3: Wire Progress, Status, and Disabled Schedule Presentation

**Files:**
- Modify: `apps/arkscope-web/src/SettingsProviderConfig.test.ts`
- Modify: `apps/arkscope-web/src/Settings.tsx`

- [ ] **Step 1: Make the schedule fixture controllable**

Add these fields to the hoisted `mocked` object in
`SettingsProviderConfig.test.ts`:

```ts
scheduleRunning: false,
scheduleProgress: null as { done: number; total: number; current: string } | null,
```

Use them only for `polygon_news`:

```ts
running: mocked.scheduleRunning,
progress: mocked.scheduleProgress,
```

Reset both fields in `afterEach`.

Append one deterministic disabled provider to the existing `health.providers`
fixture so the neutral provider path is tested through real Settings JSX:

```ts
{
  id: "retired_provider",
  label: "Retired provider",
  kind: "macro",
  status: "disabled",
  enabled: false,
  disabled_reason: "retired",
  key_present: true,
  key_source: "not_required",
  key_vars: [],
  last_success_at: null,
  last_attempt_at: null,
  last_error: null,
  detail: "",
  signals: {},
  key_import_suggested: false,
},
```

- [ ] **Step 2: Add two RED integration tests and rewrite one obsolete sibling**

Add exactly two new tests:

```ts
it("renders_known_schedule_progress_without_covering_the_last_run_cell", async () => {
  mocked.scheduleRunning = true;
  mocked.scheduleProgress = {
    done: 17,
    total: 149,
    current: "BRK.B — long current contract name that must wrap inside the progress cell",
  };
  await renderDataSources();
  const row = Array.from(host!.querySelectorAll("tr")).find((node) =>
    node.textContent?.includes("Polygon news"));
  if (!row) throw new Error("missing schedule row");
  expect(row.querySelector(".source-run-current")?.textContent).toContain("BRK.B");
  expect(row.querySelector(".source-run-counts")?.textContent).toBe("17 / 149 · 11%");
  expect(row.querySelector("[role='progressbar']")).not.toBeNull();
  expect(row.querySelector(".ds-last-run-cell")?.textContent).toContain("已跳過");
});

it("shows_disabled_provider_and_schedule_states_as_neutral_text", async () => {
  await renderDataSources();
  const providerRow = Array.from(host!.querySelectorAll("tr")).find((node) =>
    node.textContent?.includes("Retired provider"));
  if (!providerRow) throw new Error("missing disabled provider row");
  expect(providerRow.textContent).toContain("已停用");
  expect(providerRow.querySelector(".ui-status-badge")).toBeNull();
  expect(providerRow.querySelector(".ds-chip")).toBeNull();
  expect(providerRow.querySelector(".muted")).not.toBeNull();

  const row = Array.from(host!.querySelectorAll("tr")).find((node) =>
    node.textContent?.includes("價格缺口補抓"));
  if (!row) throw new Error("missing price_backfill row");
  expect(row.textContent).toContain("排程關閉");
  const scheduleCell = row.querySelectorAll("td")[1];
  expect(scheduleCell?.querySelector(".ui-status-badge")).toBeNull();
  expect(scheduleCell?.querySelector(".ds-schedule-disabled")?.textContent).toBe("排程關閉");
  expect(Array.from(row.querySelectorAll("button")).some((button) =>
    button.textContent?.includes("Run"))).toBe(true);
});
```

Rewrite the existing test
`renders scheduler source badges from backend metadata instead of provider_fetch heuristics`
in place as:

```ts
it("does_not_render_storage_route_source_badges", async () => {
  await renderDataSources();
  const row = Array.from(host!.querySelectorAll("tr")).find((node) =>
    node.textContent?.includes("價格缺口補抓"));
  if (!row) throw new Error("missing price_backfill row");
  expect(row.querySelector("td")?.textContent?.replace(/\s+/g, "").trim())
    .toBe("價格缺口補抓");
  expect(row.textContent).not.toContain("IBKR/Polygon");
  expect(row.textContent).not.toContain("直寫本地");
});
```

The exact first-cell assertion preserves the source label while proving that
the three backend `source_badges` are absent. Do not apply a negative
`缺口補抓` assertion to the whole row because that phrase is also the source's
real label.

Also evolve the existing FRED provider test, without adding a test, to assert:

```ts
expect(row.querySelector(".ui-status-badge")?.getAttribute("data-state")).toBe("ready");
```

- [ ] **Step 3: Run the integration file and verify RED**

```bash
npm test --workspace apps/arkscope-web -- src/SettingsProviderConfig.test.ts
```

Expected RED reasons:

- no `.source-run-current` or progressbar exists;
- disabled rows still say only `關`;
- raw source badges remain visible;
- provider status still uses `ds-chip`.

- [ ] **Step 4: Wire the new presentation code**

In `Settings.tsx`:

1. Import `SourceRunProgress`, `StatusBadge`, and the four mapping helpers.
2. Add this local presentation helper beside `DataSourcesSection` and replace
   provider status chips with `<ProviderHealthState provider={p} />`:

```tsx
function ProviderHealthState({ provider }: { provider: ProviderHealth }) {
  const state = providerCommonState(provider.status);
  return state === null
    ? <span className="muted tiny">{providerHealthStatusLabel(provider)}</span>
    : <StatusBadge state={state} label={providerHealthStatusLabel(provider)} />;
}
```

3. Replace SA status chips with:

```tsx
<StatusBadge
  state={saSegmentCommonState(row.tone)}
  label={row.tone === "ok" ? "正常" : row.tone === "warn" ? "注意" : "失敗"}
/>
```

4. In `renderLastRun`, compute the two independent axes before returning JSX:

```ts
const skipState = scheduleSkipCommonState(skippedReason);
const historyState = durableScheduleCommonState(s);
```

   Render an already-running skip with a `blocked` `StatusBadge`. Render every
   other skipped attempt as muted domain text with no common-state badge;
   Gateway busy, writer-lock busy, and pending-manual-continue are not
   cancelled work and must not borrow `interrupted`:

```tsx
{skippedReason && (
  skipState === null ? (
    <span className="muted tiny" title={skippedReason}>
      已跳過：{skippedSummary}
    </span>
  ) : (
    <StatusBadge state={skipState} label="新觸發已略過" />
  )
)}
```

   Render the durable/never-run axis separately so a transient skip never
   rewrites the prior durable outcome:

```tsx
{historyState !== null && (
  <StatusBadge
    state={historyState}
    label={`${ss.label}${durableError ? `：${compactMessage(durableError)}` : ""}`}
  />
)}
```
5. Delete only the `(s.source_badges ?? []).map(...)` JSX. Keep the DTO.
6. In the schedule control cell, keep the checkbox and replace the current
   one-character `開` / `關` label with:

```tsx
<span className={s.enabled ? "tiny" : "muted tiny ds-schedule-disabled"}>
  {s.enabled ? "排程開啟" : "排程關閉"}
</span>
```

7. Replace the running `ds-chip` in the Run cell with:

```tsx
<SourceRunProgress
  sourceLabel={s.label}
  running={s.running}
  progress={s.progress}
/>
```

Keep the existing manual Run button in the non-running branch regardless of
`s.enabled`.

- [ ] **Step 5: Run focused regression and typecheck**

```bash
npm test --workspace apps/arkscope-web -- \
  src/SourceRunProgress.test.tsx \
  src/dataSourcesPresentation.test.ts \
  src/SettingsProviderConfig.test.ts \
  src/marketDataDisplay.test.ts
npm run typecheck --workspace apps/arkscope-web
```

Expected: focused tests pass. `marketDataDisplay.test.ts` retains its old
domain-label contracts; no compatibility helper is deleted to force green.

- [ ] **Step 6: Commit Task 3**

```bash
git add apps/arkscope-web/src/Settings.tsx \
  apps/arkscope-web/src/SettingsProviderConfig.test.ts
git commit -m "feat: stabilize data source run status"
```

---

### Task 4: Add Explicit Responsive Table Ownership

**Files:**
- Create: `apps/arkscope-web/src/SettingsStabilizationCss.test.ts`
- Modify: `apps/arkscope-web/src/SettingsProviderConfig.test.ts`
- Modify: `apps/arkscope-web/src/Settings.tsx`
- Modify: `apps/arkscope-web/src/styles.css`

- [ ] **Step 1: Add long-content fixtures**

Extend the Provider Config mock with a deterministic SA response:

```ts
getSAExtensionHealth: vi.fn(async () => ({
  ok: false,
  generated_at: "2026-07-12T00:00:00+00:00",
  segments: [{
    key: "capture_readback",
    state: "warn" as const,
    detail:
      "No capture has arrived from the browser extension for the selected account; " +
      "check the native-host binding and retry the extension health check.",
  }],
})),
```

Keep the existing long FRED title and long schedule error fixtures. Extend one
provider `last_error` with a long unbroken request identifier.

- [ ] **Step 2: Write two RED integration tests**

Add exactly:

```ts
it("wraps_each_wide_data_source_table_in_an_explicit_scroll_owner", async () => {
  await renderDataSources();
  for (const id of [
    "provider-health-scroll",
    "sa-health-scroll",
    "fred-snapshot-scroll",
    "provider-config-scroll",
    "schedule-scroll",
  ]) {
    const owner = host!.querySelector(`[data-testid='${id}']`);
    expect(owner?.classList.contains("settings-table-scroll")).toBe(true);
    expect(owner?.querySelector("table")).not.toBeNull();
  }
});

it("marks_long_runtime_content_as_wrap_capable", async () => {
  await renderDataSources();
  const wrapCells = Array.from(host!.querySelectorAll(".settings-wrap-text"));
  expect(wrapCells.some((cell) => cell.textContent?.includes("native-host binding"))).toBe(true);
  expect(wrapCells.some((cell) => cell.textContent?.includes("Treasury Securities"))).toBe(true);
  expect(host!.querySelector(".ds-last-run-cell.settings-wrap-text")).not.toBeNull();
});
```

- [ ] **Step 3: Write two RED CSS contract tests**

Create `SettingsStabilizationCss.test.ts`:

```ts
/// <reference types="node" />
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const here = fileURLToPath(new URL(".", import.meta.url));
const css = readFileSync(resolve(here, "./styles.css"), "utf8");

function rule(selector: string): string {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return css.match(new RegExp(`${escaped}\\s*\\{([^}]*)\\}`))?.[1] ?? "";
}

describe("Settings stabilization CSS contracts", () => {
  it("gives_wide_settings_tables_one_horizontal_scroll_owner_and_reviewed_min_widths", () => {
    expect(rule(".settings-table-scroll")).toMatch(/overflow-x:\s*auto/);
    for (const selector of [
      ".settings-provider-health-table",
      ".settings-sa-health-table",
      ".settings-fred-table",
      ".settings-provider-config-table",
      ".settings-schedule-table",
    ]) {
      expect(rule(selector)).toMatch(/min-width:\s*\d+px/);
      expect(rule(selector)).not.toMatch(/font-size:/);
    }
  });

  it("lets_designated_detail_cells_wrap_without_shrinking_type", () => {
    expect(rule(".settings-wrap-text")).toMatch(/white-space:\s*normal/);
    expect(rule(".settings-wrap-text")).toMatch(/overflow-wrap:\s*anywhere/);
    expect(rule(".settings-wrap-text")).not.toMatch(/font-size:/);
  });
});
```

- [ ] **Step 4: Verify RED for structure, not harness errors**

```bash
npm test --workspace apps/arkscope-web -- \
  src/SettingsProviderConfig.test.ts \
  src/SettingsStabilizationCss.test.ts
```

Expected: missing scroll owners/classes and CSS rules. Existing tests must still
reach the rendered Data Sources section.

- [ ] **Step 5: Add wrappers and reviewed widths**

For each existing table, insert the wrapper opening immediately before its
`<table>` and the wrapper closing immediately after its matching `</table>`.
For Provider health, the resulting opening tags are:

```tsx
<div className="settings-table-scroll" data-testid="provider-health-scroll">
  <table className="data-table settings-provider-health-table">
```

and the existing table closing becomes:

```tsx
  </table>
</div>
```

Use the corresponding test IDs and table classes:

| Surface | Test ID | Table class | Minimum width |
| --- | --- | --- | ---: |
| Provider health | `provider-health-scroll` | `settings-provider-health-table` | 760px |
| SA extension | `sa-health-scroll` | `settings-sa-health-table` | 720px |
| FRED snapshot | `fred-snapshot-scroll` | `settings-fred-table` | 760px |
| Provider config | `provider-config-scroll` | `settings-provider-config-table` | 940px |
| Schedule | `schedule-scroll` | `settings-schedule-table` | 980px |

Remove the two inline `tableLayout: "fixed"` styles from SA and FRED. Keep the
schedule table fixed-layout, but move ownership to
`.settings-schedule-table`. Add `settings-wrap-text` to provider error/detail,
SA detail, FRED title/label, and `.ds-last-run-cell`.

Add:

```css
.settings-table-scroll {
  width: 100%;
  max-width: 100%;
  overflow-x: auto;
  overscroll-behavior-inline: contain;
}
.settings-provider-health-table { min-width: 760px; }
.settings-sa-health-table { min-width: 720px; table-layout: auto; }
.settings-fred-table { min-width: 760px; table-layout: auto; }
.settings-provider-config-table { min-width: 940px; }
.settings-schedule-table { min-width: 980px; table-layout: fixed; }
.settings-wrap-text {
  white-space: normal;
  overflow-wrap: anywhere;
}
```

Replace the table's old `ds-schedule` class with `settings-schedule-table` and
change the existing `.ds-schedule td`, `.ds-schedule`, and five column-width
selectors to `.settings-schedule-table`. Preserve `vertical-align: middle` and
the reviewed 22/10/16/16/36 column split. Do not add an `@media` rule.

- [ ] **Step 6: Run focused tests, typecheck, and build**

```bash
npm test --workspace apps/arkscope-web -- \
  src/SettingsProviderConfig.test.ts \
  src/SettingsStabilizationCss.test.ts
npm run typecheck --workspace apps/arkscope-web
npm run build --workspace apps/arkscope-web
```

Expected: focused tests, typecheck, and build pass. The existing Vite chunk
warning is not a failure.

- [ ] **Step 7: Commit Task 4**

```bash
git add apps/arkscope-web/src/Settings.tsx \
  apps/arkscope-web/src/styles.css \
  apps/arkscope-web/src/SettingsProviderConfig.test.ts \
  apps/arkscope-web/src/SettingsStabilizationCss.test.ts
git commit -m "fix: contain wide settings data tables"
```

---

### Task 5: Replace Migration Narration and Retire News UI Controls

**Files:**
- Modify: `apps/arkscope-web/src/SettingsNewsStorage.test.ts`
- Modify: `apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts`
- Modify: `apps/arkscope-web/src/SettingsProviderConfig.test.ts`
- Modify: `apps/arkscope-web/src/SettingsStabilizationCss.test.ts`
- Modify: `apps/arkscope-web/src/Settings.tsx`

- [ ] **Step 1: Rewrite existing copy tests before implementation**

Evolve the existing News test in place to expect:

```ts
expect(host.textContent).toContain("新聞資料狀態 · News Data");
expect(host.textContent).toContain("10 篇 · 2 來源");
expect(host.textContent).toContain("最近收集成功");
expect(host.textContent).not.toMatch(/PostgreSQL|PG exit|SQLite|legacy|mirror|本地新聞庫/);
```

Evolve the two active Post-PG storage tests in place:

```ts
expect(host!.textContent).toContain("市場資料 · Market Data");
expect(host!.textContent).toContain("價格");
expect(host!.textContent).toContain("財務快取");
expect(host!.textContent).not.toMatch(
  /PG fallback|SQLite|local authority|本地市場資料庫|本地市場庫|本地路由/,
);
```

```ts
expect(host!.textContent).toContain("總經與行事曆 · Macro / Calendar");
expect(host!.textContent).toContain("FRED 序列");
expect(host!.textContent).toContain("Finnhub 付費方案");
expect(host!.textContent).not.toMatch(/PostgreSQL|PG|SQLite|local-only|本地總經庫|本地路由/);
```

Keep the existing App Records absence test unchanged.

Extend the existing second test in `SettingsStabilizationCss.test.ts` without
adding a collected test. Read `Settings.tsx`, extract only the four enabled
normal sections, and pin every authored migration term that is present in the
RED baseline:

```ts
const settingsSource = readFileSync(resolve(here, "./Settings.tsx"), "utf8");

function sourceSection(start: string, end: string): string {
  const from = settingsSource.indexOf(start);
  const to = settingsSource.indexOf(end, from + start.length);
  expect(from).toBeGreaterThanOrEqual(0);
  expect(to).toBeGreaterThan(from);
  return settingsSource.slice(from, to);
}
```

Rename the existing wrapping test to
`keeps_detail_cells_wrap_capable_and_normal_sections_free_of_migration_copy`
and append:

```ts
const normalSections = [
  sourceSection("function DataStorageSection()", "function NewsStorageSection()"),
  sourceSection("function NewsStorageSection()", "function TradingDayCoveragePanel()"),
  sourceSection("function MacroStorageSection()", "function FragmentKV("),
  sourceSection("function DataSourcesSection()", "type ModelEntryGroup"),
].join("\n");
expect(normalSections).not.toMatch(
  /PostgreSQL|PG exit|PG mirror|PG fallback|PG 同步|PG 鏡像|SQLite|local authority|local-primary|local-only|本地市場資料庫|本地市場庫|本地路由|本地新聞庫|本地總經庫|本地快照|本地 SA|存本地|market_data\.db|macro_calendar\.db|direct-local|legacy local|legacy config|strict DB-first/,
);
expect(normalSections).toContain("config/.env");
```

This is deliberately source-scoped: it excludes unreachable App Records,
backend compatibility DTOs, comments outside the four owners, and archival
documents.

Evolve the existing Data Sources source-badge and FRED tests in
`SettingsProviderConfig.test.ts` without adding tests. The rendered surface
must prove every currently visible authored migration string is gone while the
actionable credential source remains:

```ts
expect(host!.textContent).not.toMatch(
  /直寫本地 SQLite|direct-local|PG 同步|鏡像|FRED 本地快照|本地快照|存本地|strict DB-first|legacy config/,
);
expect(host!.textContent).toContain("config/.env");
```

In the rewritten source-badge test, also assert the source cell has no
technical description tooltip:

```ts
expect(row.querySelector("td")?.hasAttribute("title")).toBe(false);
```

In the evolved FRED provider test, assert the provider cell no longer exposes
`p.detail` through `title`:

```ts
expect(row.querySelector("td")?.hasAttribute("title")).toBe(false);
```

- [ ] **Step 2: Add exactly four new tests**

In `SettingsNewsStorage.test.ts`, extend the hoisted mock with:

```ts
newsError: null as Error | null,
```

and make `getNewsStatus` throw that error when present. Extract the current
mount/open sequence into `renderNewsSection()`, update its section-button query
from `News Ingestion` to `News Data`, and add a local `dispose()` used by both
`afterEach` and the multi-state test. Reset `newsError` and clear mocks after
each test.

Use these exact seams:

```ts
getNewsStatus: vi.fn(async () => {
  if (mocked.newsError) throw mocked.newsError;
  return mocked.newsStatus;
}),
```

```ts
function dispose() {
  if (root) act(() => root!.unmount());
  host?.remove();
  root = null;
  host = null;
}

async function renderNewsSection() {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  await act(async () => {
    root!.render(<SettingsView runtime={null} onRuntimeChanged={vi.fn()} />);
  });
  await flush();
  const button = Array.from(host.querySelectorAll("button")).find((node) =>
    node.textContent?.includes("News Data"));
  if (!button) throw new Error("missing News Data section button");
  await act(async () => {
    button.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
  });
  await flush();
}

afterEach(() => {
  dispose();
  mocked.newsStatus = null;
  mocked.newsError = null;
  vi.clearAllMocks();
});
```

Add to `SettingsNewsStorage.test.ts`:

```ts
it("hides_both_migration_controls_even_for_a_pre_exit_compatibility_response", async () => {
  mocked.newsStatus = newsStatus({
    news_hard_local: false,
    news_pg_exit_completed: false,
    pg_news_route_available: true,
    direct_active: false,
  });
  await renderNewsSection();
  expect(host!.querySelectorAll("input[type='checkbox']")).toHaveLength(0);
  expect(host!.textContent).not.toContain("Legacy local writer");
  expect(host!.textContent).not.toContain("Normalized news writes");
  const api = await import("./api");
  expect(api.setUseLocalNews).not.toHaveBeenCalled();
  expect(api.setNormalizedNewsWrites).not.toHaveBeenCalled();
});
```

Add the News empty/failure contract:

```ts
it("renders_empty_and_failed_news_statuses_as_user_outcomes", async () => {
  mocked.newsStatus = newsStatus({
    exists: false,
    news: { row_count: 0, source_count: 0, latest_published: null },
  });
  await renderNewsSection();
  expect(host!.textContent).toContain("尚無資料");
  expect(host!.textContent).not.toContain("尚未建立");

  dispose();
  mocked.newsError = new Error("news status unavailable");
  await renderNewsSection();
  expect(host!.textContent).toContain("news status unavailable");
  expect(host!.querySelector(".errorbox")).not.toBeNull();
});
```

In `SettingsPostPgExitStorage.test.ts`, add this hoisted state, assign the two
existing fixtures into it after their declarations, and make the API mocks use
it:

```ts
const mocked = vi.hoisted(() => ({
  marketStatus: null as MarketDataStatus | null,
  macroStatus: null as MacroStatus | null,
  marketError: null as Error | null,
  macroError: null as Error | null,
}));
```

`getMarketDataStatus` and `getMacroStatus` throw their matching error when
present and otherwise return the matching status. Extract the existing unmount
logic into `dispose()`. In `afterEach`, call `dispose()`, restore the original
fixtures, and clear both errors.

Use these exact mocks and reset:

```ts
mocked.marketStatus = marketStatus;
mocked.macroStatus = macroStatus;

getMarketDataStatus: vi.fn(async () => {
  if (mocked.marketError) throw mocked.marketError;
  return mocked.marketStatus!;
}),
getMacroStatus: vi.fn(async () => {
  if (mocked.macroError) throw mocked.macroError;
  return mocked.macroStatus!;
}),
```

```ts
function dispose() {
  if (root) act(() => root!.unmount());
  host?.remove();
  root = null;
  host = null;
}

afterEach(() => {
  dispose();
  mocked.marketStatus = marketStatus;
  mocked.macroStatus = macroStatus;
  mocked.marketError = null;
  mocked.macroError = null;
});
```

Add to `SettingsPostPgExitStorage.test.ts`:

```ts
it("uses_normal_user_outcomes_in_the_enabled_settings_directory", async () => {
  await renderSettings();
  expect(host!.textContent).toContain("價格、新聞、IV、基本面與財務快取狀態");
  expect(host!.textContent).toContain("新聞資料量、最新文章、收集狀態與最近錯誤");
  expect(host!.textContent).toContain("FRED 總經資料與經濟、財報、IPO 行事曆狀態");
  expect(host!.textContent).not.toMatch(/PG mirror routes|PostgreSQL exit|本地總經/);
});
```

Add one combined state test for the two storage-status surfaces:

```ts
it("renders_market_empty_and_macro_failed_states_as_user_outcomes", async () => {
  mocked.marketStatus = {
    ...marketStatus,
    exists: false,
  };
  await renderSettings();
  await openSection("Data Storage");
  expect(host!.textContent).toContain("尚無資料");
  expect(host!.textContent).not.toContain("尚未建立");

  dispose();
  mocked.marketStatus = marketStatus;
  mocked.macroError = new Error("macro status unavailable");
  await renderSettings();
  await openSection("Macro / Calendar");
  expect(host!.textContent).toContain("macro status unavailable");
  expect(host!.querySelector(".errorbox")).not.toBeNull();
  expect(host!.textContent).not.toMatch(/SQLite|PG fallback|local-only/);
});
```

- [ ] **Step 3: Verify RED**

```bash
npm test --workspace apps/arkscope-web -- \
  src/SettingsNewsStorage.test.ts \
  src/SettingsPostPgExitStorage.test.ts \
  src/SettingsProviderConfig.test.ts \
  src/SettingsStabilizationCss.test.ts
```

Expected: old titles/copy/checkbox branches/source narration make the tests
fail. The App Records absence test remains green.

- [ ] **Step 4: Apply the exact normal-mode copy**

Update enabled directory entries:

```ts
{
  id: "data_storage",
  title: "Data Storage",
  description: "價格、新聞、IV、基本面與財務快取狀態。",
  enabled: true,
},
{
  id: "news_storage",
  title: "News Data",
  description: "新聞資料量、最新文章、收集狀態與最近錯誤。",
  enabled: true,
},
{
  id: "macro_storage",
  title: "Macro / Calendar",
  description: "FRED 總經資料與經濟、財報、IPO 行事曆狀態。",
  enabled: true,
},
```

Use these panel headings and descriptions:

```tsx
<h2>市場資料 · Market Data</h2>
<p className="muted tiny">
  顯示價格、新聞、隱含波動率、基本面與財務快取的資料量、最新時間及最近更新。
  資料抓取由 Data Sources 管理。
</p>
```

```tsx
<h2>新聞資料狀態 · News Data</h2>
<p className="muted tiny">
  顯示新聞資料量、最新文章、最近收集時間與錯誤。各來源排程與手動執行由 Data Sources 管理。
</p>
```

```tsx
<h2>總經與行事曆 · Macro / Calendar</h2>
<p className="muted tiny">
  顯示 FRED 序列與觀測值，以及經濟、財報與 IPO 行事曆資料。
  經濟行事曆需要 Finnhub 付費方案；未取得授權時會維持不可用。
</p>
```

For Data Sources use:

```tsx
<p className="muted tiny">
  集中檢視各資料來源的健康狀態、連線設定、排程與手動執行。
  每個來源可獨立設定；IBKR 工作會共用 Gateway 鎖以避免重疊。
</p>
```

Apply these label/content changes without changing response handling:

- `本地市場庫` -> `市場資料`;
- Market, News, and Macro use `尚無資料` for an empty response, never
  database-creation language such as `尚未建立`;
- remove the Market `本地路由` row and `local authority` action row;
- financial cache text ends after latest-fetch time;
- trading-day coverage intro no longer names `market_data.db`;
- `本地新聞庫` -> `新聞資料`;
- remove all News route/read/PostgreSQL rows; retain count, latest article,
  collection success/attempt/status/error;
- `最近 direct 成功/嘗試` -> `最近收集成功/嘗試`;
- `Direct 狀態` -> `收集狀態`;
- `本地總經庫` -> `總經資料`;
- remove Macro route and local-only explanatory rows;
- `FRED 本地快照` -> `FRED 資料快照` and remove database-name narration;
- rewrite `fredProviderDetail()` to `資料快照可用` / `尚無資料`;
- SA copy describes extension/native host/sidecar/data-receipt checks without
  storage backend narration;
- credential copy says source labels identify where a value is managed and
  that App saves apply immediately; remove the DB-first/legacy runtime-policy
  paragraph while preserving per-field `App`, env, and `config/.env` labels;
- remove the now-unused `cfgEnvFallback` React state and setter while leaving
  `getProvidersConfig()` and its response type unchanged; remove the now-unused
  `ProviderEnvFallbackState` type import from `Settings.tsx` as well;
- remove authored raw `source_badges` and source-description tooltips; runtime
  errors remain visible and wrap-capable.

The tooltip removal applies specifically to `title={s.description}` on
schedule-source cells and `title={p.detail}` on provider cells. Do not remove
the visible provider-error column or the expandable full last-run message.

- [ ] **Step 5: Remove only the two News UI mutation branches**

From `Settings.tsx` remove:

- imports `setUseLocalNews`, `setNormalizedNewsWrites`;
- `busy` state in `NewsStorageSection`;
- `toggleLocalNews()` and `toggleNormalizedWrites()`;
- both checkbox branches and their env-hint paragraphs;
- `disabled={busy}` from the News refresh button.

Do not edit `api.ts`, backend routes, News DTO fields, or backend tests.

- [ ] **Step 6: Keep compatibility helpers/tests out of the normal render path**

Remove the now-unused `marketRoutingLabel`, `macroRoutingLabel`,
`newsRoutingLabel`, `newsWriteRouteLabel`, `newsPostgresRouteLabel`, and
`newsReadSurfaceLabel` imports from `Settings.tsx`. Do not delete their exports
or unit tests in this bounded slice.

Evolve the two FRED tests in `SettingsProviderConfig.test.ts` in place to expect
`資料快照`, not `本地快照`, while retaining counts and timestamps.

- [ ] **Step 7: Run copy/control regression and a scoped rendered-text gate**

```bash
npm test --workspace apps/arkscope-web -- \
  src/SettingsNewsStorage.test.ts \
  src/SettingsPostPgExitStorage.test.ts \
  src/SettingsProviderConfig.test.ts \
  src/SettingsStabilizationCss.test.ts \
  src/marketDataDisplay.test.ts
```

Then verify API/backend byte identity:

```bash
git diff --exit-code 554e94b -- \
  apps/arkscope-web/src/api.ts \
  src tests data_sources
```

Expected: all focused tests pass; diff command has no output. Do not run a
repo-wide migration-word deletion gate because App Records, comments, DTOs,
and archival docs are intentionally preserved.

- [ ] **Step 8: Commit Task 5**

```bash
git add apps/arkscope-web/src/Settings.tsx \
  apps/arkscope-web/src/SettingsNewsStorage.test.ts \
  apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts \
  apps/arkscope-web/src/SettingsProviderConfig.test.ts \
  apps/arkscope-web/src/SettingsStabilizationCss.test.ts
git commit -m "fix: replace migration-era settings copy"
```

---

### Task 6: Rename Risk Appetite in the Investor Profile UI

**Files:**
- Modify: `apps/arkscope-web/src/InvestorProfilePanel.test.tsx`
- Modify: `apps/arkscope-web/src/personalizationDisplay.test.ts`
- Modify: `apps/arkscope-web/src/InvestorProfilePanel.tsx`
- Modify: `apps/arkscope-web/src/personalizationDisplay.ts`

- [ ] **Step 1: Change test expectations first**

Replace only user-facing assertions:

```ts
expect(host!.textContent).toContain("風險意願高於承受能力");
expect(host!.textContent).toContain("風險意願(1-10)");
expect(host!.textContent).toContain("風險意願與風險承受能力");
expect(host!.textContent).not.toContain("風險胃納");
```

and:

```ts
expect(mismatchLabel("appetite_above_capacity")).toBe("風險意願高於承受能力");
expect(mismatchLabel("capacity_above_appetite")).toBe("承受能力高於風險意願");
```

Do not rename TypeScript fields, payload keys, or test fixture properties.

- [ ] **Step 2: Verify RED**

```bash
npm test --workspace apps/arkscope-web -- \
  src/InvestorProfilePanel.test.tsx \
  src/personalizationDisplay.test.ts
```

Expected: failures show the old visible term `風險胃納`.

- [ ] **Step 3: Apply the four ruled UI replacements**

In production frontend code replace:

- `風險胃納(1-10)` -> `風險意願(1-10)`;
- `風險胃納 vs 承受能力:` -> `風險意願與風險承受能力:`;
- `風險胃納高於承受能力` -> `風險意願高於承受能力`;
- `承受能力高於風險胃納` -> `承受能力高於風險意願`.

- [ ] **Step 4: Run focused tests and the production-string gate**

```bash
npm test --workspace apps/arkscope-web -- \
  src/InvestorProfilePanel.test.tsx \
  src/personalizationDisplay.test.ts
rg -n "風險胃納" \
  apps/arkscope-web/src/InvestorProfilePanel.tsx \
  apps/arkscope-web/src/personalizationDisplay.ts
```

Expected: tests pass; `rg` exits `1` with no output. Historical plan/spec text
is not rewritten.

- [ ] **Step 5: Commit Task 6**

```bash
git add apps/arkscope-web/src/InvestorProfilePanel.tsx \
  apps/arkscope-web/src/InvestorProfilePanel.test.tsx \
  apps/arkscope-web/src/personalizationDisplay.ts \
  apps/arkscope-web/src/personalizationDisplay.test.ts
git commit -m "fix: rename investor risk appetite label"
```

---

### Task 7: Full Verification, Visual Gate, and Review-Ready Ledger

**Files:**
- Modify: `docs/superpowers/plans/2026-07-12-p2-8-settings-stabilization.md`
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`

- [x] **Step 1: Run every focused owner suite**

```bash
npm test --workspace apps/arkscope-web -- \
  src/SourceRunProgress.test.tsx \
  src/dataSourcesPresentation.test.ts \
  src/SettingsStabilizationCss.test.ts \
  src/SettingsProviderConfig.test.ts \
  src/SettingsNewsStorage.test.ts \
  src/SettingsPostPgExitStorage.test.ts \
  src/InvestorProfilePanel.test.tsx \
  src/personalizationDisplay.test.ts \
  src/marketDataDisplay.test.ts
```

Expected: all focused tests pass.

- [x] **Step 2: Run full frontend gates and reconcile exact accounting**

```bash
npm test --workspace apps/arkscope-web
npm run typecheck --workspace apps/arkscope-web
npm run build --workspace apps/arkscope-web
```

Expected:

- `41` test files pass;
- `366` tests pass;
- typecheck passes;
- production build passes;
- only the known Vite chunk-size warning may remain.

If the count is not exactly `+19 / -0` from the `38 / 347` baseline, collect
base/head test names and reconcile before continuing.

- [x] **Step 3: Run static scope and semantic ratchets**

```bash
git diff --exit-code 554e94b -- apps/arkscope-web/src/api.ts src tests data_sources
rg -n "setUseLocalNews|setNormalizedNewsWrites|toggleLocalNews|toggleNormalizedWrites" \
  apps/arkscope-web/src/Settings.tsx
rg -n "source_badges" apps/arkscope-web/src/Settings.tsx
rg -n "aria-live" apps/arkscope-web/src/SourceRunProgress.tsx
rg -n '"interrupted"' apps/arkscope-web/src/dataSourcesPresentation.ts
git diff -U0 554e94b -- apps/arkscope-web/src/styles.css | rg "^\+@media"
```

Expected:

- byte-identity diff has no output;
- the four source `rg` commands and the added-media diff gate exit `1` with
  no output;
- `api.ts` still exports both News compatibility helpers;
- no new breakpoint or live region exists.

Confirm the compatibility helpers remain:

```bash
rg -n "export function setUseLocalNews|export function setNormalizedNewsWrites" \
  apps/arkscope-web/src/api.ts
```

Expected: two exports found.

- [x] **Step 4: Run no-PG/fresh-start smoke**

```bash
python src/smoke/pg_unreachable_e2e.py
```

Expected: `ok: true`, all checks pass, and `pg_attempts: []`.

- [x] **Step 5: Run browser checks with long-content and real-progress fixtures**

Start one scheduler-disabled sidecar against a disposable profile DB:

```bash
ARKSCOPE_DISABLE_SCHEDULER=1 \
ARKSCOPE_PROFILE_DB=/tmp/arkscope-settings-stabilization-profile.db \
python -m src.api
```

Start Vite on 8431, or the next free 84xx port:

```bash
npm run dev --workspace apps/arkscope-web -- --host 127.0.0.1 --port 8431
```

Use browser request interception or the same deterministic fixtures from
`SettingsProviderConfig.test.ts` so the schedule response contains:

```json
{
  "running": true,
  "progress": {
    "done": 17,
    "total": 149,
    "current": "BRK.B — long current contract name that must wrap inside the progress cell"
  }
}
```

Capture screenshots under `/tmp`, not the repository, at:

- 1440x900
- 1024x768
- 961x768
- 959x768
- 390x844

At every viewport verify:

1. current item, progress track, count, and last-run details do not overlap;
2. SA detail, FRED title, provider error, credential content, and schedule rows
   stay readable through their own horizontal scroll regions;
3. the page itself has no horizontal overflow;
4. type size is unchanged;
5. known progress exposes the real percentage, while null/zero progress shows
   only `執行中`;
6. disabled schedule says `排程關閉` without a status badge and still offers
   manual Run;
7. no raw source badges or migration narration appear;
8. `config/.env` and App/env credential provenance remain visible;
9. Market, News, Macro, and Data Sources loading/error/ready content remains
   usable;
10. 961 and 959 do not introduce a new layout breakpoint.

Stop both temporary processes after screenshots. Do not restart the user's
desktop app from the implementation worktree.

- [ ] **Step 6: Run canonical backend A/B**

Codex-environment attempt reproduced the known single-process
`TestClient`/lifespan hang. The file-isolated virgin fallback is strictly equal
as recorded in the implementation evidence above; reviewer canonical A/B is
the remaining merge gate.

Compare virgin archives of base `554e94b` and final tip under identical
environment isolation. Acceptance:

- backend collected tests `+0 / -0`;
- failure sets identical in both directions;
- passed/skipped/warning/error counters exactly equal;
- no generated artifact remains in either archive.

Because this is frontend-only, any backend delta is a finding, not an accepted
side effect.

- [x] **Step 7: Record evidence and mark implementation review-ready**

In this plan header append:

- commit list by task;
- each RED reason;
- focused/full frontend counts;
- typecheck/build result;
- static gate outputs;
- no-PG smoke result;
- screenshot paths and viewport checks;
- canonical A/B counters;
- any accepted pre-existing warning.

Change this plan status to:

```markdown
> **Status: IMPLEMENTED FOR REVIEW — NOT MERGED.**
```

Insert a newest-first Priority Map decision-log entry stating that the bounded
stabilization is implementation-review-ready and Portfolio 1.1 remains next
only after merge. Do not mark the design spec implemented or merged yet.

- [x] **Step 8: Commit the review-ready ledger**

```bash
git add docs/superpowers/plans/2026-07-12-p2-8-settings-stabilization.md \
  docs/design/PROJECT_PRIORITY_MAP.md
git commit -m "docs: mark settings stabilization review ready"
```

Stop here. Do not merge. Request implementation review with emphasis on:

1. News compatibility paths remaining byte-identical;
2. no fake progress or polling live region;
3. disabled schedule neutrality;
4. scroll ownership at 961/959/390;
5. rendered copy rather than repository-wide string deletion;
6. exact `+19 / -0` frontend accounting and backend `+0 / -0`.

---

## Post-Review Merge Closeout

Only after review is GREEN and canonical A/B passes:

1. fast-forward merge;
2. change the design spec status to `LIVE / MERGED`;
3. change this plan status to `LIVE COMPLETE / MERGED`;
4. update the Priority Map with merge commit and final evidence;
5. record `risk appetite` -> `風險意願` in the project terminology memory;
6. remove the implementation worktree/branch;
7. restart the normal desktop app once so the new frontend bundle is loaded;
8. promote Portfolio 1.1 design, not P2.8 Slice 2, unless the user records a
   newer sequence ruling.
