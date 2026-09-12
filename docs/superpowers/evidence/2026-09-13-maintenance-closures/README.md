# September 13 Maintenance Closures

Base: `ef5f7b48`. Worktree: `/tmp/arkscope-research-output-boundary`, branch
`codex/sec-research-integration`. Main/master is untouched. This evidence records
bounded finished items, not completion of every SEC or cleanup task.

## Completed Scope

- EIR-001/C13: closed at `eec66b9e`, independent task review approved.
- C11: closed at `a4bf0a73` plus review fix `6cddc221`; task re-review approved.
  EIR-006 fixture-classification collateral at `1304c96d` is also reviewed.
- Final frozen backend: **10,311 passed / 12 unchanged skipped**, zero failures.
  Frontend: **1,779 passed**, typecheck/build/i18n passed. Task, whole-change and
  collateral reviews are approved. The first full failure remains recorded below.
- Git archive verification passed: 278 committed paths, no missing/extra files
  or hash mismatches. All work remains on the branch; no merge or push.
- SQLite: source-only admission path reviewed; no build/install/activation here.

## EIR-001

Removed exactly five rules for two obsolete class tokens: `.page-head` and
`.page-head-actions`, including desktop and mobile rules. The substring
`detailpage-head` is a distinct live owner, not a sixth deletion target.
All 908 retained rules/2,857 declarations are identical; parsing and independently
removing only the five old rules also reproduces the exact final CSS bytes.

Three named tests enforce desktop/media absence and a real PageHeader positive
control. Actual assertion RED is distinct from two earlier fixture-loading
errors. Independently restoring a desktop rule or media rule fails only its
named owner. All failed receipts are retained, not counted as passing checks.

Controller focused rerun: 38 passed. Full frontend: 1,779 passed / 124 files;
typecheck/build pass.
Ten real-primitive browser cases (general and Settings headers at
320/390/760/761/1440px) have identical before/after pixels and geometry, real
click/disabled-state checks, and no overlap or horizontal overflow. This is an
isolated component/CSS fixture, not a live production Settings session.
Existing React act-warning categories and Vite chunk-size warning are recorded;
neither is silently suppressed or represented as a newly introduced defect.

The wider CSS census queue remains open. The original audit C13 row specifically
shares this EIR-001 scope, so that row can close without claiming all CSS clean.

## C11

The obsolete `use_local_news` setting/environment switch, helper/arguments, PUT
`/news/settings`, five news-only status fields and unused frontend setter/label
are physically removed. The current normalized/direct writers, configuration
blockers, permission ordering, read routes and actual stored rows remain.
The removed PUT returns 405 through the retained ticker GET route, not a stub.

Actual provider_sync observations now own news overlay/health. Neither the old
setting nor article publication time can replace ingest success. Non-news sync
and IBKR's existing combined market-health semantics remain. Review R1 identified
the exceptional path that retained old news when current acquisition failed;
`6cddc221` clears that provisional slice before both the path probe and query,
keeping degradation notes and all other data. Real corrupt-current-table tests
preserve nonempty price/news observations; the path-probe failure control uses
nonempty news observations. These R1 controls do not seed nonempty financial
cache rows. Separate retained controls cover populated cache/projection behavior,
including the ten-row assertion in `tests/test_stored_sec_projection.py`.

The same owned news reader also incorrectly interpolated `?`/`#` filenames into
a SQLite URI, bypassing the intended read-only option and creating an unintended
empty sibling in disposable RED fixtures. Resolved `as_uri()` encoding fixes
this narrow defect; populated/missing-path tests prove correct reads, unchanged
fixture bytes and noncreation. No actual user-store failure is inferred.

Original scoped 300 nodes became 329 (34 removed/63 added), then R1 added three
without removal. Final worker 332P and controller 76P are separate checks, not a combined
full-suite total. Old-value validation, telemetry suppression and health-failure
ordering each have independent inverse failures followed by restored GREEN.
Initial fixture/import/constraint mistakes and their corrected assertion RED
receipts remain explicitly distinguished. The current normalized switch and
malformed-current-setting blockers were not relaxed.

Only source consumers/writers of the abandoned key are removed. The key's actual
stored-data disposal is still a separate inventory/backup operation; this source
cleanup never deletes it automatically or changes unrelated profile settings.

## Integration Follow-Up

The first frozen full run at `6cddc221` ran all 10,323 collected nodes, with
12 unchanged skips and no source/runtime/runner drift. Its one failure belongs
to `test_current_runtime_consumer_census_is_closed_and_exact`: R1's real
`market_sync_meta` fixture needed its exact filename in `_TEST_FIXTURES`.
`1304c96d` adds that one classification, with no product change, discovery
exception, removed assertion or additional node. A standalone RED and inverse
each give one failed / one passed; the restored four-file selection gives 78
passed. Independent scoped review approves the correction. This was our missed
test collateral, not another operator's interference or a product-store failure.

The fresh complete run uses `1304c96d` and unchanged offline guards. It passes
all 10,311 non-skipped tests in 1,120.439 seconds including launcher overhead.
All 10,323 collected nodes executed exactly once, with the same 12 skipped IDs.
Against the prior accepted 10,291-node suite: 66 added / 34 removed, net +32.
No source/runtime/runner drift: 1,132 product/test/runtime paths, collection hash
`73ba5da4928e312a23d0123938e65a2c5732a1d9bad0af1e6dc1f231b16b08ed`.
Retained credential-echo, tracing, task-routing and card-error safety owners ran
and passed, as did all owned news regression suites. Later commits change only
documentation/evidence. Passing subsets are not used to manufacture this total.
The initial full failure and its failed validation stay in the archive.

One controller command also used nonexistent npm script `check:i18n`. It failed
before any check ran. The actual `check:i18n-literals` script was read from
`package.json` and rerun successfully (37 candidates/20 signatures/zero debt).
No script or source expectation was changed to accommodate the typo.

The archive contains 75 completed command receipts, 24 with nonzero exit codes.
Those include intentional RED/inverse checks, census review-required results,
documented setup mistakes and the initial full failure. They are not 75 passing
checks, nor an additive test count. `run-accounting.json` preserves every run;
`closure-validation.json` identifies the final accepted full result separately.

| Final check | Result / receipt |
| --- | --- |
| Complete backend | `backend-accepted-full`: 10,311P / 12S |
| Exact nodes, skips, source and runtime | `closure-validation.json`: all ten checks true |
| Complete frontend | `frontend-accepted`: 1,779P / 124 files |
| Typecheck / build / i18n | `frontend-typecheck-accepted`, `frontend-build-accepted`, `frontend-i18n-literals-accepted`: exit 0 |
| Responsive before/after | `task1-browser-before` / `task1-browser-after`: ten identical pairs |
| Review | `task1-review.md`, `task2-r1-review.md`, `final-review.md` plus `collateral-eir006-review.md`: approved |
| Census | `census-maintenance-accepted`: exit 2 / review_required, detailed reconciliation below |

Paths in this table are relative to `checks/`. Archived execution scripts and
commands retain their original plan-workspace identities; they are not installed
product commands. The standalone Git verifier can run directly from this folder:

```bash
python -B docs/superpowers/evidence/2026-09-13-maintenance-closures/verify_archive.py HEAD
```

The [Git verification receipt](archive-verification.json) reads commit
`ac0743ef59bdd7368ddde58553757ddb5ab371a0`, not just the working directory.
It verifies all 277 payloads plus the manifest, including explicitly staged
ignored logs and 20 browser screenshots. Manifest SHA-256:
`84f7debaba96e010199323834946ade3ad9628e4da1c7d4978b3d92c4a955e60`.
Later closure-document commits leave these sealed bytes unchanged. The archived
progress ledger is the pre-seal snapshot; this receipt and completed plan own
the final delivery status. Disposable DBs, homes and runtime binaries are not
archived; only this plan's scratch is removed after Git verification.

Raw `checks/task-1-brief.md` retains its original extra newline at EOF, so a
whole-range `git diff --check` flags that one archived-brief whitespace item.
It is deliberately preserved as historical bytes, not silently reformatted.
The product/test diff passes the whitespace check; no runtime exception or test
expectation is involved.

## Census

Against `ef5f7b48`, final source `1304c96d` gives 1,148 read/4,330 candidate
occurrences/3,463 uncertainties. No new candidate IDs, coverage reductions,
dependency metadata changes or main-worktree untracked-name drift. Fifteen
removed occurrences are exactly five CSS rules + ten paired locale leaves;
they have 13 unique
IDs because repeated desktop/media selectors share two IDs.

Raw comparison still reports 175 new uncertainty IDs and review_required/exit 2.
All 175 match prior metadata excluding location (two also match Python source
nodes); eight unmatched removals are the five old translation calls, one test binding
and the old setting read/write. This does not turn metadata matching into proof
of all program semantics or resolve the existing scanner queues. The first
unique-ID reconciliation and subsequent multiplicity-aware report both remain.

## SQLite Admission

The prior 3.53.4 candidate evidence remains
[separately sealed](../2026-09-12-sec-integration/sqlite-candidate.md).
This batch does not rerun or overwrite it. Source-only examination identifies
an app-private immutable SQLite library and an executable wrapper around the
unchanged Python as the minimal Linux preparation path. Electron and installed
SA host have separate executable selectors; both must participate. The analysis
Python child deliberately strips loader variables, so it needs a narrow runtime
admission change, not wholesale inherited environment access.

Preserve existing bind-capacity/privacy behavior by default and verify package
relocation, actual mapped library/source ID, every writing child, and rollback.
The official [compile-options documentation](https://sqlite.org/compile.html)
explains that these settings affect behavior and recommends testing customized
builds; the historical candidate tests do not certify a differently built
deployment artifact. Actual configuration readback, a stopped-writer maintenance
window, coherent backups and full integrity checking still precede activation.
No actual-store health or corruption is inferred from a synthetic reproducer.
Exact entrypoints, compile-profile differences and the maintenance prerequisites
are recorded in [the source-only preflight](checks/sqlite-admission-preflight.md).

## Remaining Work

- SEC durable Research references, operation leases/export/restore, recovery
  commands and schedule. Release Tasks 3/5 protect references and operations;
  recovery Task 6 depends on them. Backend document citations alone are not all
  durable Research roots, so cleanup/reset cannot be treated as ready independent
  deletions.
- C12 collector/news entrypoints, C15/C20 and actual old stored-data/schema/key
  disposition; i18n, broader CSS and SQL-scanner queues. C21 remains deferred.
- Formal SQLite packaging/readmission/activation, not a Python/numpy upgrade.

No production DB/config/key read, provider call, real data deletion, actual App
restart, installation, master merge or push occurred. Test stores/browser homes
are disposable; one product writer/test runner owns this worktree at a time.
