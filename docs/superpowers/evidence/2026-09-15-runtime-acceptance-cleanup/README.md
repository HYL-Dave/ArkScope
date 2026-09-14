# Runtime Acceptance Gate And C15 Removal

Completed 2026-09-15; work started September 14. Worktree:
`/tmp/arkscope-research-output-boundary`, branch
`codex/sec-research-integration`. Baseline `9dd2ab27`.

## Delivered

- `b3385a31`: selected-runtime artifact acceptance fails when its explicit
  offline source archive is absent. Unmanaged development retains an explicit
  skip. No download or automatic installed-runtime discovery was added.
- `d208eeb7`: physically remove three obsolete migration/recovery bundles and
  their superseded tests. Preserve the current incomplete-receipt write guard
  in the current schema test module. Net change for this commit: -3,651 lines.
- The activation runbook now explicitly blocks production activation until
  unselected production startup is rejected independently of wrapper variables.
  **That production requirement is not implemented by this test fix.**

No App restart, production database/configuration access, backup deletion,
schema mutation, runtime installation/activation, dependency upgrade, merge or
push was performed. The dormant analysis executor and Python sandbox scope are
unchanged. This is not complete C15/C20 closure or cross-platform acceptance.

## Cleanup Boundary

The user's continuation followed the explicit question about retiring old
migration-only recovery APIs while retaining backup files and current recovery.
The three removed source modules are:

| Source | Removed Test Module | Baseline Cases |
| --- | --- | ---: |
| `src/security_lifecycle_migration.py` | `tests/test_security_lifecycle_migration.py` | 16 |
| `src/security_lifecycle_automation_migration.py` | `tests/test_security_lifecycle_automation_migration.py` | 10 |
| `src/ticker_identity_migration.py` | `tests/test_ticker_identity_migration.py` | 14 |

This intentionally retires their module-local backup constructors, types and
`restore_coordinated_backups`, `restore_automation_profile_backup`, and
`restore_profile_backup`. No compatibility facade or replacement generic backup
API was introduced. In particular, the old main-file-copy helper is not reused
for WAL-safe runtime activation backups. Existing backup files are untouched.

The sole current-behavior test in these modules was moved with its helper:
`test_incomplete_receipt_blocks_all_lifecycle_writes` and `_new_observation`
now live in `tests/test_security_lifecycle_schema.py`. Both ASTs are identical.
The test still invokes both current stores and verifies that incomplete receipts
block `ensure_case` and `upsert_observation`. An in-process inverse control that
bypasses their checks fails with `DID NOT RAISE LifecycleWritesUnavailable`.
The inverse is a disposable pytest plugin, not a product edit.

All other removed cases exercise only the retired converters/recovery APIs.
The V1 mapping tests are not independent current-row readers: each seeds the old
schema and invokes its converter. Current manual-evidence, authority, attended
transition, canonical schema, installation/disposal and SEC recovery tests remain.
`checks/verify_cleanup.py` reproduces the absence, AST, unchanged-owner and
unbounded product/test residual-name checks without importing the application.
Historical plans, receipts and shared fixtures are retained.

## Verification

| Run | Result |
| --- | --- |
| `archive-required-red` | Expected 1 failure, 1 pass, 29 deselected: selected child previously exited 0 with a skip. |
| `archive-required-green` | 2 passed, 29 deselected. |
| `runtime-green` | 72 passed on the selected package; includes all 31 artifact cases. |
| `c15-red` | Expected 3 failures, 22 deselected: the three obsolete source files still existed. |
| `receipt-owner-move` | Both old and new owners passed before removal. |
| `receipt-owner-inverse` | Expected 1 failure when current receipt checks are bypassed. |
| `c15-green` | Operator command error, exit 4, zero tests: two guessed SEC test filenames did not exist. Retained, not counted as acceptance. |
| `c15-green-rerun` | 213 passed with the actual SEC recovery test owners. |
| `final-collect` | 11,216 test identities. |
| `full-admitted` | **11,204 passed / 12 unchanged skips / zero failures or errors.** |

The complete backend ran once, serially, in the default test order using
`-q tests/`, with no case exclusions, second pytest, census, reviewer or source
editing during execution. It took 1,489.15 pytest seconds / 1,493.359 wrapper
seconds. Frontend source was unchanged; no new frontend acceptance is claimed.

`checks/full-reconciliation.json` verifies all 18 checks: collected/executed
identity equality, no duplicates, unchanged skip identities, exact approved
removals, retained safety owners, actual package selection and engine, package
payload hashes, and no source/SDK/runner drift. The immutable source anchor is
`d208eeb762d8275dc3d0abdf65d5e504d2a608e4`.
There are 1,163 frozen source paths, with collection SHA-256
`cb2fda1db34e143b1aa1f0f58c8b518fc78489c4fdade4b6ed9e7f5b0b8c801b`.

Against the preceding 11,250-node full run, exactly 40 identities were removed
from the three declared test modules and six added: three physical-absence
parameters, two missing-archive controls, and the moved receipt owner. Thus
11,250 - 40 + 6 = 11,216. The removal allowance is the exact baseline identities
of those three modules, not a blanket permission to lose tests.

The selected runtime remains the unchanged SQLite 3.53.4 generation from the
[preparation receipt](../2026-09-14-private-sqlite-runtime/README.md), relocated
within owned scratch. The complete run's `runtime.json` records the actual
package library and verified manifest. All 31 artifact cases passed without
skips; contract/build/startup cases passed 30/3/8 respectively. The separate
unmanaged interpreter still uses system 3.37.2. This is not evidence of installed
App activation or every dormant child process using the new engine.

## Census And Review

The identical current scanner was run against `9dd2ab27` and the final source:
1,185 -> 1,179 read files, 4,310 -> 4,317 candidates, 3,285 -> 3,231 uncertainties.
Comparison reports ten new column candidates, zero new uncertainties, zero
dependency/untracked changes and exactly six deleted-file coverage reductions.
Exit 2 / `review_required` is deliberately retained.

All ten candidates belong to `security_lifecycle_migration_receipts`:
`completed_at`, `expected_kinds`, `expected_legacy_assessments`,
`expected_legacy_rows`, `expected_observations`, `legacy_mapping_sha256`,
`market_snapshot_sha256`, `migration_key`, `started_at`, and `updated_at`.
Their former converter readers disappeared. They are retained receipt metadata,
not approved DROP targets; the live write gate still reads `phase`.
The net seven-candidate increase is ten columns minus three removed Python
module candidates. This is a scoped disposition, not a claim of a clean census.

A bounded read-only independent review of the three module caller/test boundaries
and final `9dd2ab27..d208eeb7` diff found no blocking issues. One runbook wording
correction was applied: explicitly selected package verification does inspect
that package, although no installed runtime is discovered automatically. The
reviewer ran no tests and was closed before the complete backend started.

## Remaining Work

- C15: the older provider migration/census evidence-script chains still need
  retained-reader ownership separation. The mixed listing-migration helpers are
  still consumed by current installation/disposal and cannot simply be deleted.
- C20: actual `agent_queries` retained-row/schema disposition is still open.
  This batch neither inventories production rows nor authorizes a DROP. Current
  reports, memories, conversations, citations and usage remain unchanged.
- Production activation: first implement and test an independent durable
  production startup requirement, including launcher bypass and isolated
  development scope. Then arrange the separately approved stopped-writer
  inventory, coherent backups, full integrity checks, installation and switch.
- Windows/macOS runtime admission and the planned Python sandbox remain separate.

Follow [the runtime runbook](../../../design/SQLITE_RUNTIME_OPERATIONS.md).
The accepted runtime is upgradeable; this checkpoint does not freeze future
pre-release dependency versions.

## Evidence Layout

`checks/manifest.json` hashes an explicit allowlist of copied runner/source-check
files, command receipts, raw logs/JUnit, source freezes, reconciliation and census
reports. Gzip preserves exact decompressed bytes with no timestamps. No source
archive, binary, fixture database/HOME, credentials or unrelated scratch is copied.
The preceding preparation receipt and its 109 artifacts are unmodified.

Command receipts identify the original source root and disposable workspace
`.superpowers/sdd/2026-09-14-runtime-acceptance-gate`. These sealed runner copies
expect that scratch depth; they are not new application entrypoints. Reproduction
requires the explicitly reviewed offline source ZIP and a prepared package at
the runner's `package/` location. Do not point the runner at production stores or
substitute an installed runtime for the missing source archive.
