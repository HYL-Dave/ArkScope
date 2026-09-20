# Schedule Status Layout

Base: `52037620f1f661bfc7fd8f696de7e101fdfdff5c`.
Branch: `codex/schedule-status-layout`.

## Scope

- Move live progress out of the narrow action column into the status column.
- Keep one live running indicator, without suppressing retained terminal
  outcomes, stale warnings, skipped-trigger facts, or the body backlog.
- Mark a retained outcome as the last run when another run is active.
- Remove summary height clipping; let timestamps and long status text wrap.
- Use source-labelled icon controls and stable control column dimensions.
- Apply the same presentation to the existing data and macro schedule tables.
- Preserve the controller, API requests, polling, locking, and scheduler policy.

The four new accessibility labels are in both locale dictionaries. Current
Settings leaf counts change from 1053 to 1057; overall counts from 2984 to 2988.
Each new key is listed as a post-Slice addition in the existing historical
inventory test. Its historical counts remain unchanged.

## Verification

- RED: 4 failures / 29 passes before implementation. Owners were
  `dataScheduleControls.test.tsx` (duplicate running text in both locales and
  progress separated from retained failure) and `SettingsCss.test.ts`
  (summary height clipping).
- Final full frontend suite: 124 files / 1856 tests passed, exit 0.
  Three cases were added to the previous 1853-test suite.
- `tsc --noEmit`: exit 0.
- `vite build`: exit 0. The existing large-chunk warning remains; no bundle
  threshold or build setting was changed.
- Playwright / isolated headless Chrome: 18 combinations, no geometry issues
  or browser errors. Locales: en, zh-Hant. Viewport widths: 390, 1067, 1440.
  Scenarios: the reported running/skipped/prior-failure mix, long partial
  outcomes with body backlog, and the shared macro table.
- At 390px the table retains its own horizontal scroll container. Status and
  action columns can be reached by scrolling; this is not a stacked mobile UI.
- Browser control checks: apply an interval, start a simulated run, keep the
  button disabled while running, then restore it at completion. The action
  button does not move when an interval draft appears or is applied.
- The same browser harness reproduced clipped warnings on the base revision.

An initial sandboxed full run hit 19 child-process `EPERM` errors. Rerunning
with the approved process permissions exposed the real i18n collateral: new
control labels needed resource ownership and exact inventory updates. Those
were fixed; no scanner rules or historical test expectations were relaxed.

Temporary browser harness and screenshots:
`/tmp/arkscope-schedule-status-preview/` (`check_layout.py`, `main.tsx`, and
`evidence/layout-report.json`). The preview at `http://127.0.0.1:8456/` uses
synthetic data and controller callbacks, not the live API. Browser page
requests outside that origin were denied; none were attempted.

## Isolation

No production database was opened, no real collection was triggered, and no
running App process was restarted or modified. The master worktree and its
two pre-existing untracked documentation items were left alone. This UI-only
branch has not been merged or pushed. Backend regression and live provider
acquisition were not rerun for this presentation change.
