# Task 1 EIR-001 Handoff

Status: implementation and all requested Task 1 verification gates complete.
No concrete blocker remains. Controller owns independent review, staging,
commits, evidence sealing/index, and the issue-register closure.

## Workspace And Scope

- Worktree: `/tmp/arkscope-research-output-boundary`.
- Branch: `codex/sec-research-integration`.
- Product comparison base: `5526bc40dc8d62efa6dd819cf1ffc99d8acff7ce`.
- Current HEAD: `de506754b0b91d9e16281979c5dca9af2fdfc453`, the controller's
  C11-plan-only clarification. The controller's uncommitted
  `docs/design/PROJECT_PRIORITY_MAP.md` changes were also left untouched.
- Read the Task 1 brief first, then plan constraints and EIR-001. No previous
  `.superpowers` plan workspace was read or written; no agents were spawned.
- Sole Task 1 product writer and test runner through this handoff. Commands
  ran serially; product/test source was frozen for final focused/full frontend,
  typecheck, and build. No backend, private config/data, DB, provider, or live
  App was used. No dependency, issue-register, or other CSS-family edits.
- No `git add`, commit, merge, push, or reset. Final `git diff --cached --quiet`
  exited 0. Branch and worktree remain in place.

## Changed Product Files

1. `apps/arkscope-web/src/styles.css`: removed exactly five obsolete rules,
   23 lines / 13 declarations. There are two obsolete class tokens, not five
   classes. No substring-based deletion was used.
2. `apps/arkscope-web/src/retiredPageHeader.test.tsx`: added three tests. The
   named desktop/media absence owners parse actual CSS into CSSOM, recurse
   through grouping rules, and match complete `.page-head`/`.page-head-actions`
   tokens. Nonempty parsing guards prevent vacuous success. A real PageHeader
   renders title/context/actions; `.detailpage-head` and all five current
   `.ui-page-header*` selector forms retain nonempty styling positive controls.

| Removed Selector | Base Line | Context | Declarations |
| --- | ---: | --- | ---: |
| `.page-head` | 950 | desktop | 5 |
| `.page-head h1` | 957 | desktop descendant of exact obsolete class | 2 |
| `.page-head-actions` | 961 | desktop | 4 |
| `.page-head` | 1404 | `@media (max-width: 760px)` | 1 |
| `.page-head-actions` | 1407 | `@media (max-width: 760px)` | 1 |

`detailpage-head` is retained, as are `PageHeader.tsx`, `Button.tsx`, tokens,
`primitives.css`, `shell.css`, `settings.css`, and all unrelated declarations.
The wider 88-candidate CSS census queue is not closed by this work.

## Census And Equivalence

Evidence: `task1-css-before.json`, `task1-css-after.json`, `task1-css-final.json`.
The reproducible workspace-only auditor is `task1_css_audit.cjs`.

- Searched 143 actual frontend source/entry/config files, excluding tests and
  maintenance scripts from the consumer census. TypeScript AST inventory:
  1,105 class attributes/properties, including 56 dynamic JSX class attributes.
- Reviewed templates, conditional class strings, primitive `className` props,
  table-column class properties, `cls` forwarding, `changeClass`, `tagClass`,
  and status/tone class construction. Exact obsolete-token search returned no
  consumers (rg exit 1); broad substring hits identify retained PageHeader,
  detail-header, and overlay-header owners. Full commands, match output, class
  expressions, and string-literal inventory are in the census JSON files.
- Base CSS: 913 rules, of which exactly five are retired. Final CSS: 908 rules.
  All 2,857 declarations of those 908 retained rules are identical, including
  order, at-rule context, property/value, and `!important` state.
- Stronger byte check: parse base with installed PostCSS, remove only the five
  independently enumerated obsolete rules, serialize, and require exact equality
  to final CSS bytes. This passed both after deletion and after both inverses.
  This also preserves retained comments, whitespace, and non-rule contents.
- All 293 tracked frontend files were compared with base. Only `styles.css`
  differs; the new test is the 294th entry in the final source identity map.
- Auditor: Node 22.14.0, PostCSS 8.5.15, TypeScript 5.9.3, all already installed.
  No package manifest or lockfile changed.

## Test Receipts

All paths below are relative to this report's current plan workspace. Each
`run_checks.py` run directory contains its exact `command.json` (command, cwd,
closed environment, exit code, elapsed time) and unabridged `output.log`.
Failed receipts were not overwritten or deleted.

| Receipt Directory | Command After `frontend` / `browser` Mode | Result |
| --- | --- | --- |
| `task1-baseline-frontend/` | `test` | exit 0; 123 files, 1,776 tests passed |
| `task1-red/` | `test -- src/retiredPageHeader.test.tsx` | exit 1; three CSS-loading guard failures; not acceptance RED |
| `task1-assertion-red/` | same | exit 1; URL/file-loading error before test collection; not acceptance RED |
| `task1-assertion-red-2/` | same | exit 1; two intended absence failures, one positive-control pass |
| `task1-browser-before/` | `--phase before` | exit 0; 10 before cases passed |
| `task1-green-focused/` | focused command below | exit 0; 4 files, 38 tests passed |
| `task1-browser-after/` | `--phase after --compare .../task1-browser-before/browser` | exit 0; 10 cases, zero changed pixels each |
| `task1-inverse-desktop/` | `test -- src/retiredPageHeader.test.tsx` | exit 1; desktop absence alone failed; two controls passed |
| `task1-inverse-media/` | same | exit 1; media absence alone failed; two controls passed |
| `task1-restored-focused/` | focused command below | exit 0; 4 files, 38 tests passed |
| `task1-full-frontend/` | `test` | exit 0; 124 files, 1,779 tests passed; 14.115s |
| `task1-typecheck/` | `run typecheck` | exit 0; `tsc --noEmit`; 11.260s |
| `task1-build/` | `run build` | exit 0; `tsc --noEmit && vite build`; 14.563s |

Focused command:

```text
test -- src/retiredPageHeader.test.tsx src/ui/primitives.test.tsx src/shell/ShellCss.test.ts src/SettingsCss.test.ts
```

Rerun prefix from the worktree root:

```text
/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-13-maintenance-closures/run_checks.py <fresh-receipt-name> frontend
```

The acceptance RED reported desktop selectors `.page-head`, `.page-head h1`,
`.page-head-actions`, and the two media selectors before any product CSS edit.
Final total reconciles exactly: 1,776 baseline tests + 3 new tests = 1,779,
with no removed, skipped, or todo tests in the suite result.

For the desktop inverse, the entire original five-declaration `.page-head`
rule was temporarily restored at its original location. Only the named desktop
absence owner failed with `expected [ '.page-head' ] to deeply equal []`.
It was removed before independently restoring the original media
`.page-head-actions { width: 100%; }` rule. Only the media owner failed with
`expected [ '.page-head-actions' ] to deeply equal []`. Both restorations used
`apply_patch`; final CSS returned to the exact reviewed SHA-256 below.

Build: Vite 5.4.21, 2,210 modules; emitted CSS 103.01 kB and JS 1,185.31 kB.
The build reports its >500 kB chunk-size warning; no build failure. Existing
React act-warning message categories are unchanged between baseline and full
suite. The new test's own act-environment warning was corrected using the
existing test convention before inverses and final frozen verification.

## Responsive Visual Gate

- Fixture: `task1-fixture/index.html`, `task1-fixture/fixture.tsx`, served by
  `task1_fixture_server.mjs`. No product fixture route, App import, API import,
  provider, or live backend. Real PageHeader/Button components and real UI token
  installation; shipped CSS loaded in the same order as the product entry:
  `styles.css`, `shell/shell.css`, `ui/primitives.css`, `settings/settings.css`.
- `browser_check.py` uses disposable Playwright Chromium 145.0.7632.6, DPR 1,
  height 900, widths 320/390/760/761/1440, in general-header and Settings-lede
  cases. Both before and after were captured from the actual worktree CSS;
  the before capture preceded CSS deletion, not a recreated approximation.
- Ten screenshots per phase, all 10 pairs pixel-identical and geometry-identical.
  Results include 668-740 unique colors per image, correct actual theme color,
  real icon rendering, 22px header title, flex/wrapping controls, retained detail
  header flex/12px gap, no text overflow, horizontal overflow, title/action
  overlap, button overlap, or header/detail overlap.
- Refresh click and disabled Export state passed in every case. Inspected
  general mobile/desktop and Settings mobile/desktop screenshots visually.
- Each pass records 180 fixture-origin requests, zero denied/external requests,
  zero failed requests, zero console errors, and zero page errors. Service workers
  were blocked; server-initiated network connections were blocked. Vite used
  `configFile: false`, `envFile: false`, a workspace-only cache, and loopback
  binding. No existing user browser session or profile was used.
- Metrics, source/screenshot hashes and request lists:
  `task1-browser-before/browser/results.json` and
  `task1-browser-after/browser/results.json`.
- Screenshots: `task1-browser-{before,after}/browser/{general,settings}-{320,390,760,761,1440}.png`.

## Intermediate Failures

Detailed terminal diagnostics and remedies: `task1-infrastructure-failures.md`.
The first test import yielded empty CSS under Vitest; the next URL-based read
was rewritten by Vite. Neither was counted as RED. Using the existing
cwd/resolve/readFileSync pattern produced the intended assertion RED.

The initial auditor rejected the controller's documented HEAD advancement;
it now verifies ancestry while still comparing every frontend file against
5526bc40. The first server attempt selected Vite's CJS entry, then the corrected
ESM attempt encountered the overly broad DNS guard during numeric-loopback
listen. Permitting only `127.0.0.1` lookup fixed binding without allowing outbound
connections. No failed browser visual run occurred; both visual passes exited 0.

## Frozen Identity And Cleanup

Final SHA-256 values, also recorded in `task1-css-final.json`:

```text
styles.css: f3b6298d377ba4e0a27c59d6dcd1dd7d427e2c959d3f5c1b1c709752d9deb327
retiredPageHeader.test.tsx: b4511cd0c0e4525a1b3776a407226e23de285b97ae58e004c2d37878c966ed26
run_checks.py: 2c1cc48b15f817b02cc70a99cad757a0962e875e37381fa122fca8b89796247f
offline_node.cjs: 35f45243a42cf069225ff91e726779333c33bb9a3abc4c1f694404c3810b728b
retained semantic inventory: 9c1efedb6d1b587c3bcca7f23e3924f540d8d4d9a3644bc1448a751abb14acd5
```

Both browser receipts record `browserClosed: true`. Fixture server PID 3376929
received SIGTERM and its exec session exited 0. `task1-server.json` records
`closed: true` at `2026-09-12T19:21:31.859Z` (03:21:31 Asia/Taipei on Sep 13).
Final `ps -p 3376929` found no process and `ss -ltnp '( sport = :8457 )'`
showed no listener. All own test/typecheck/build sessions have completed.
Final `git diff --check` passed. No server is left running for this handoff.

Workspace-only authored files: this report, `task1-infrastructure-failures.md`,
`task1_css_audit.cjs`, `task1_fixture_server.mjs`, `browser_check.py`, and the two
`task1-fixture/` files. Generated evidence consists of the three census JSONs,
server receipt, and the run directories listed above. Disposable homes and
`task1-vite-cache/` remain ignored, as do screenshots and build output; none has
been staged. The copied offline runners were not changed.

## Self-Review

- No blocking findings within the approved change. The product diff is exactly
  two CSS deletion hunks plus the named new test file; independent byte and
  declaration comparisons rule out collateral CSS edits.
- Exact token matching does not confuse `detailpage-head` or `ui-page-header`
  with either obsolete class. The real-component positive control and both
  independent inverse failures demonstrate that the absence owners are active.
- CSSOM tests enumerate media rules without pretending jsdom performs responsive
  layout; the separate real Chromium gate verifies actual layout before/after.
- All final frontend gates ran on restored, frozen source. Known unrelated act
  warnings and the build size warning are reported, not hidden or expanded into
  unrelated fixes. No live application/provider/DB integration claim is made.
- Independent review was not spawned because explicitly prohibited. Controller
  can now review the two product files and retained receipts, commit, and close
  EIR-001 only. The issue register, broader CSS queue, Task 2, and Task 3 remain
  controller-owned; this report does not claim they are complete.
