# Task6 Implementer Report

Latest revision: **Fix Round1** at the end, committed as 78157e62; 1064 covering
tests passed, no runner active. Earlier counts/hashes describe immutable e495d664.

Status: IMPLEMENTED, COMMITTED, SELF-REVIEWED; ready for independent controller
review. The single frozen covering run passed 1025 tests, no failures/skips,
110.53s. All six named inverse cases demonstrated their intended behavioral
assertions and exact source restoration. No runner is active; no required
implementer work remains. Actual-store rollout and full backend gate were NOT run.

Workspace: `/tmp/arkscope-research-output-boundary`.
Branch: `codex/sec-research-integration`.
BASE: `b49e09c48337cac2337b590f96368e367d6912f5`, initially clean.
Commit: `e495d664087e3201b44c3b78b44b64f47c1df77c`
(`feat(sec-research): add explicit cleanup and schema recovery`).
SEC-RECOVERY-001 and SEC-RECOVERY-002 are implemented by this commit; this report
does not change the controller-owned plan/spec status or authorize rollout.

## Controller Rulings Implemented

Controller explicitly approved unknown-schema backup-only: preview discloses
`apply_effect=raw_backup_only`; digest-approved apply with new paths can preserve
raw DB/captures, but finishes `status=blocked`, `phase=backed_up`,
`code=sec_research_unknown_owned_objects`, `recovery=inspect_raw_backup`.
There is no DROP/reset/uninstall fallback. The complete receipt records the
backup destination. Missing/unsafe/stale/uninspectable requests never silently
start a backup. Known-schema reference refusal semantics are unchanged.

Controller then identified excessive shared-market lock scopes. Full observation,
capture hashing, raw backup, unlink/directory fsync and receipt I/O now run under
the exclusive SEC operation lease but outside the global market writer lock.
Short writer-lock/BEGIN IMMEDIATE scopes own registry-to-orphan conversion,
individual charge reconciliation and schema mutation. Cheap owned-schema and
external-dependency checks remain at the destructive write point. SQLite FK
enforcement is explicitly checked ON; cleanup's actual DELETE enforces incoming
FKs after full graph/FK verification outside the writer lock. Recreated schema
FK checks are scoped to its empty owned tables, not unrelated financial history.
This is not a new generation, scheduler, compatibility or schema framework.

## Current Scope

New product files: `src/sec_research/maintenance.py`, `schema_admin.py`.
Modified product files: `__main__.py`, `operations.py`, `capture_lock.py`,
`captures.py` within `src/sec_research/`.
New tests: `tests/test_sec_research_maintenance.py`,
`tests/test_sec_research_schema_admin.py`, `tests/test_sec_research_cli.py`.
No existing tests removed. No Task3 or Task5 redesign, agents, provider/network
execution, production DB/config/.env/credential access, actual install/reset/
export/deployment, App restart, merge, push or other-worktree edits.
No priority/spec/runbook changes. All manual edits used apply_patch. Scratch is
ignored, not staged or force-added; controller owns archival and final tooling.

## Implemented Behavior

- Observational previews; descriptor-bound strict file inventory; exact relevant
  SEC schema/data/file/profile identity approval, not a whole market-file hash.
  Ordered SEC rows stream into counts and digests using primary-key order where
  available. No historical row set is accumulated for fingerprinting.
- Existing full source-graph verification and `sec_reference_closure` remain the
  authorities. All snapshots/receipts/observations/documents/attempts/directories/
  issuer-map objects survive cleanup. Both configured-profile and colocated
  Research roots are included, with case-insensitive external-FK and SQLite
  compiler/authorizer dependency protection.
- Query-only profile admission rejects explicit caller transactions untouched.
  Each observation owns a fresh read-only SQLite connection and transaction:
  `in_transaction` alone misses unfinished autocommit SELECT snapshots. No
  caller commit/rollback/cursor consumption, profile constructor, or live
  `immutable=1` use. Entirely absent Research namespace in an existing profile
  is valid empty; missing/partial/malformed roots block.
- Cleanup converts selected registry usage into orphan charges transactionally
  before unlink, restoring the exact immutable DELETE guard before commit and
  after rollback. Only durable unlink contributes measured logical freed bytes.
  Absent unresolved charges appear as `absent_charge` candidates and require
  directory sync to retire; they contribute zero newly measured freed bytes.
- Ordinary CaptureStore recovery now syncs the directory namespace before
  retiring absent-file charges. Stored reads have no recovery/sync change.
- Known-schema reset/uninstall uses the existing WAL-safe backup primitive with
  overwrite=False and all capture files, a raw-only marker, a fresh after-backup
  recheck, exclusive root protection and a scoped SQLite transaction. Reset
  immediately charges retained files. Uninstall reports schema_absent, not zero
  storage usage. Unrelated rows and SQLite shared sequences survive.
- Raw backup includes the whole SQLite database and every safely inventoried
  SEC object/staging file, registered or not. Its manifest states
  `database_bytes=sqlite-backup-unnormalized` and the existing scope exclusions:
  independent profile store, independent SA store, other capture roots. It is
  not a filesystem-forensic copy of SQLite sidecars, not a normalized canonical
  export, and canonical restore rejects it. A fresh relevant-state recheck runs
  before raw marker publication; destructive schema apply rechecks again after
  backup and before the short mutation transaction.
- Unknown-schema reference counts remain visible in preview and receipt;
  `reference_status=roots_observed_closure_unverified` explicitly states that the
  unknown owned graph has not been certified. Missing/malformed roots use
  unobserved status, not an invented zero. No uncertain reference authorizes DROP.
- Uninstall removes schema only, not feature code/tool registration or schedule
  configuration. Later explicitly admitted acquisition can install a fresh
  schema; there is no tombstone/second enable flag or speculative Task7 change.

## CLI Contract

Exact argument names; all five help entrypoints were executed without resolving
stores in `task6-cli-help-01` (5 passed). Full help is in that output.log.
Argparse displays `offline_pytest.py` as the program name in this in-process
fixture; invocation as a module uses the same parser and arguments.

```text
python -m src.sec_research --help
python -m src.sec_research cleanup-preview --help
python -m src.sec_research cleanup-apply --help
python -m src.sec_research schema-preview --help
python -m src.sec_research schema-apply --help
python -m src.sec_research cleanup-preview --preview NEW_PREVIEW.json
python -m src.sec_research cleanup-apply --preview PREVIEW.json --approval-sha256 DIGEST --receipt NEW_RECEIPT.json
python -m src.sec_research schema-preview --mode reset|uninstall --preview NEW_PREVIEW.json
python -m src.sec_research schema-apply --preview PREVIEW.json --approval-sha256 DIGEST --backup NEW_BACKUP_DIR --receipt NEW_RECEIPT.json
```

These are implementation descriptions, not authorization to operate on real
stores. No yes/force/autoconfirm/startup repair or model filesystem tools.
Preview and receipt JSON are version 1. Preview/backup/initial receipt paths
are create-only, outside the capture root and market SQLite sidecars. Nested
preview shape and exact digest validation precede configured DB opening in CLI.
CLI emits a scrubbed summary and exit 0 for ready/ok, 1 for blocked/operational
failure; argparse help/usage follows argparse conventions. Valid blocked
previews are written; admission failures before receipt creation do not create
receipts. Detailed audit phase updates use an owned external file identity and
atomic, synced JSON replacement; old/partial artifacts are never auto-deleted.

`schema-apply` has no independent mode flag: reset/uninstall is bound into the
preview and approval digest. All four maintenance commands require `--preview`;
apply additionally requires `--approval-sha256` and `--receipt`; schema apply
requires `--backup`; schema preview requires `--mode {reset,uninstall}`. The only
optional argument on each is argparse `-h/--help`. Help exits 0 and invalid/missing
arguments exit 2; runtime blocked/unavailable exits 1. Top-level export/restore
remain unchanged. No flag claims App is stopped or substitutes for exclusion.

The closed v1 preview keys are: format, version, operation, mode, status, code,
state_sha256, approval_sha256, candidates, references, owned_objects,
schema_status, retained_bytes, recovery, apply_effect, reference_status.
`apply_effect` is none, cleanup, reset, uninstall or raw_backup_only. Other blocked
previews have effect none; only the explicitly disclosed unknown-schema effect
allows backup I/O. Ready canonical cleanup has verified reference closure;
unobserved or mismatched schemas never claim verified closure.

The closed v1 receipt keys are: format, version, operation, mode,
approval_sha256, status, code, phase, receipt_phase, selected, removed, remaining,
blocked, resolved_charges, freed_bytes, retained_bytes, accounting, backup,
recovery, apply_effect, references, reference_status. Cleanup selections are
relative owned keys; schema selections are owned object names. Backup metadata
records path, format, version, database hash/size/name, observed_sha256 and
capture_files count. CLI summaries exclude selected names, backup paths and
source values. `phase` describes the last observed durable resource stage;
`receipt_phase` can lag it if writing the audit fails. `complete` is returned
only after the final audit write succeeds. `freed_bytes` measures logical content
bytes following durable unlink, not filesystem free blocks or SQLite compaction.

## Retained Verification

All tests used this exact prefix, with unique create-only names and no overlap:

```text
/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-12-sec-research-release-integration/run_checks.py NAME backend -q NAMED_TESTS
```

Each NAME directory retains the complete exact command/environment in
`command.json`, original `output.log`, and `results.xml`. No ordinary pytest,
full 10k backend gate or concurrent runner ran. Runner SHA256 values matched:

```text
run_checks.py    2c1cc48b15f817b02cc70a99cad757a0962e875e37381fa122fca8b89796247f
offline_pytest.py 4c74153e1ef86c35f7bbc923586de624c0ffe3f577c2853e6e4c0a78426c95ff
```

| Receipt | Actual Result |
| --- | --- |
| task6-red-01 | 42 failed, 3.26s |
| task6-red-02 | 42 failed, 3.36s |
| task6-recovery-red-01 | 1 failed, 0.29s |
| task6-cleanup-green-01 | 1 failed, 23 passed, 2.59s |
| task6-cleanup-diagnose-01 | 1 failed, 0.40s |
| task6-cleanup-diagnose-02 | 1 failed, 0.42s |
| task6-cleanup-green-02 | 24 passed, 2.56s |
| task6-admin-green-01 | 19 passed, 2.28s |
| task6-hardening-red-01 | 5 failed, 12 passed, 37 deselected, 2.47s |
| task6-admission-red-01 | 7 failed, 1 passed, 0.68s |
| task6-integrated-green-01 | 64 passed, 5.80s |
| task6-cursor-red-01 | 1 failed, 1.17s |
| task6-cursor-green-01 | 4 passed, 1.77s |
| task6-retry-red-01 | 3 failed, 0.62s |
| task6-retry-green-01 | 3 passed, 0.62s |
| task6-colocated-red-01 | 1 failed, 1.11s |
| task6-colocated-green-01 | 3 passed, 1.35s |
| task6-receipt-red-01 | 3 failed, 0.55s |
| task6-receipt-green-01 | 4 passed, 0.57s |
| task6-unknown-red-01 | 9 failed, 16 passed, 28 deselected, 1.89s |
| task6-unknown-green-01 | 25 passed, 28 deselected, 2.16s |
| task6-ingest-red-01 | 4 failed, 4 passed, 80 deselected, 1.29s |
| task6-ingest-green-01 | 8 passed, 80 deselected, 1.24s |
| task6-admin-final-focused-01 | 104 passed, 8.99s |
| task6-backup-path-red-01 | 2 failed, 0.64s |
| task6-backup-path-green-01 | 2 passed, 0.58s |
| task6-inverse-skip-recheck-02 | 1 failed, 1.18s |
| task6-inverse-event-only-01 | 2 failed, 1.48s |
| task6-inverse-charge-01 | 2 failed, 0.58s |
| task6-inverse-backup-01 | 1 failed, 0.50s |
| task6-inverse-unknown-prefix-01 | 1 failed, 0.54s |
| task6-inverse-lease-01 | 1 failed, 0.48s |
| task6-cli-help-01 | 5 passed, 0.34s |
| task6-covering-frozen-01 | 1025 passed, no failures/skips, 110.53s |

Accounting: 34 completed backend runner receipts, 13 zero / 21 nonzero retained,
0 unfinished runner invocations. Six inverse runner receipts contain eight
intended behavioral assertion failures and no collection/setup errors. The one
pre-run inverse-driver abort is additional provenance, NOT a backend receipt or
killed inverse. The charge driver's post-result formatting-check failure is
disclosed below and does not change its completed runner accounting.

Frozen coverage named 22 suites: Task6 maintenance/schema/CLI; Task5 operations,
capture locking, captures and operation admission; Task3 references/citations;
SEC store/service/tool service/issuers; document store/service/queries and
structured/fact queries; Research threads/runs/history; SQLite backup. No package
full or 10k-backend run was started, and no covering suite ran concurrently.

The initial first RED had 41 missing-owner assertions plus one fixture failure:
it tried archiving an active Research run. The only correction before the second
RED was terminalizing that disposable run first. The second RED has all 42
intended missing-owner assertions. Both original runs remain retained.

Recovery RED is a real precursor failure, not a missing-module test: unresolved
18-byte charge incorrectly became zero when directory fsync was unavailable.
First cleanup GREEN exposed Python 3.10 SQLite authorizer restoration: passing
None left subsequent SQL unauthorized. Diagnostic 01 expanded the preview's
closed failure; diagnostic 02, in ignored task6-diagnose.py, re-raised the exact
underlying sqlite3.DatabaseError. The dedicated admin connection now receives
a permissive restoration callback; no alternate SQLite/schema execution lane.

Hardening RED found colocated non-query-only verification, three AttributeError
escapes on malformed inputs, and a SQLite rollback-journal receipt collision.
The exception cases were rerun as explicit escaped-exception assertions in
admission RED; nested nonclosed previews also reached resolution and failed
their boundary owners. Original failures were not discarded or mislabeled.

Cursor RED proved real stale approval acceptance after an event-only citation
was published while the caller retained an unfinished autocommit cursor.
Retry RED proved absent charges were not selectable and final receipt failure
prematurely claimed complete. Colocated RED proved reset ignored citations in
the market DB when the configured profile was separate. Receipt RED proved
the first failed audit write prematurely claimed prepared and malformed header
values were echoed. These all have named GREEN controls listed above.

Unknown-schema RED: 9 missing-backup/disclosure/phase assertions, 16 passing
negative/help controls. GREEN includes raw whole-DB/capture preservation for
both modes, exact source DB/profile bytes unchanged, no canonical restore,
visible event-only reference count, and eleven no-backup admission negatives.
DB-copy, capture-copy, marker-publication and mid-backup stale-state failures
leave incomplete raw artifacts and support new-path retries where applicable.

Ingest RED: cleanup capture/unlink/receipt barriers and schema's after-backup
capture verification denied a different-owner ordinary writer. The other four
controls already passed. GREEN allows actual unrelated news writes at all six
I/O barriers, while two mutation barriers prove both shared-market lock and
SQLite write exclusion. Fixtures use WAL, disposable paths and timeout=0 probes,
not scheduling sleeps. The backup-destination receipt assertion separately went
RED for both modes before the path was added to the external audit.

## Inverse Provenance

All six accepted inverses ran through the unchanged parent runner, with frozen
tests, disposable fixtures and actual apply_patch source mutations. Their source
directories retain .original/.mutated byte pairs and receipt.json. Restoration
in finally checked every original product byte and all three test hashes.

| Case | Behavioral Failure |
| --- | --- |
| skip-recheck | New event-only reference no longer blocked cleanup; returned ok. |
| event-only | Cleanup accepted stale reference state; reset preview returned ready. |
| charge | Charge absent at actual unlink, and unresolved 18-byte usage became 0. |
| backup | Reset reported success but required safety DB did not exist. |
| unknown-prefix | Actual apply removed unknown owned table/row; source snapshot changed. |
| lease | Active shared operation no longer blocked cleanup; returned ok. |

The unknown-prefix owner now checks source preservation AFTER calling actual
apply, before checking preview diagnostics. The inverse disables unknown-schema
admission refusal and replaces the explicit DROP allowlist with prefix inventory
targets; it demonstrates actual deletion, not just a changed preview label.
No tests were weakened, removed or altered between these inverse runs.

One initial invocation was ABORTED BEFORE RUNNER: task6-inverse-skip-recheck-01.
The driver emitted numbered unified-diff hunk headers, which the apply_patch
wrapper rejected before any product edit. No test run folder exists and zero
tests ran. Its original source directory remains, with an honestly labeled
completed aborted_before_runner receipt, original/mutated attempted bytes and
driver error/provenance. Source equality was independently confirmed by cmp.
The driver was corrected to emit bare @@ headers; a new immutable name,
task6-inverse-skip-recheck-02, is the accepted killed inverse. The abort is NOT
counted as a killed inverse or backend run.

The charge inverse's runner completed with its two expected behavioral assertion
failures; restoration and source receipt completed. The DRIVER then exited 1
because its post-check expected literal AssertionError text, while pytest's JUnit
used message="assert (None is not None)" and message="assert 0 == 18". Both exact
failures remain retained. Only the ignored driver's evidence-format predicate
was corrected to recognize either assertion representation; no rerun, product
change or test weakening was needed. All seven source directories have completed
receipt.json provenance. No unexplained or deleted source directory remains.

Frozen restored SHA256 values (also present in every applicable source receipt):

```text
maintenance.py 9c6625f9501b4c0c8f99333c6af7f10994e482b3ccf7f937c65f19c7baa32844
schema_admin.py 99ee5862e13ade64bc7afce061238845e3ef53c47393a01056c3d46989051a5f
references.py 3973bd2d7e594f034d7f284efdb7ef52ce801e531d25190981ac87af2072908f
test_sec_research_maintenance.py e6c02bfda17ea0a87461629110da354d36a3d113f84c98b4415d8be36440e254
test_sec_research_schema_admin.py 350f31e1417517bc7a00350271a334b12a1f8e87b8890b57fa668b4a32b669bf
test_sec_research_cli.py becd375d73ccf1b5df496fdc4534beafc723cb33bd9997b8a4326336cd71ba66
```

Task3 references.py has NO committed diff. No parent runner was edited. Controller
archives these source pairs and receipt records, never the fixture databases.

## Observed Fault Phases And Recovery

- Registry transaction fault after DELETE: prepared; original registry and exact
  immutability trigger restored by rollback. New preview/approval/receipt retries.
- Unlink failure: charged; file retained and 13 bytes stay charged through
  ordinary recovery. After removing the fixture fault, explicit cleanup retry
  removes it durably and reports 13 measured freed bytes.
- Directory-fsync failure after unlink: charged; zero freed reported, 18 bytes
  stay charged while ordinary recovery's directory sync still fails. A new
  explicit cleanup preview exposes the absent charge; successful namespace sync
  retires it without claiming new file bytes freed. Ordinary successful recovery
  can also retire it after its own durability check.
- Receipt failure after charge: charged, receipt_phase prepared; file and charge
  retained. After durable unlink: files_removed, receipt_phase charged; 20-byte
  charge remains until explicit/ordinary durable reconciliation. New receipts
  and approvals are required, not overwrite/reuse of earlier audit paths.
- Cleanup KeyboardInterrupt after charge: charged, explicit interrupted code;
  retained 6-byte charge and explicit retry work.
- Backup failure: prepared; no DROP, original store intact, incomplete backup
  has no raw success marker. Retry with new preview/backup/receipt paths.
- Changed state after successful backup: backed_up; no DROP. Inspect retained
  raw backup, obtain a new preview and new output paths.
- Schema transaction fault after DROP: backed_up; rollback restores original
  schema/data. Raw backup and external blocked receipt survive; new-path retry.
- Receipt failure after schema commit: schema_committed, receipt_phase backed_up;
  raw backup survives and new schema immediately charges retained 8-byte files.
  Inspect resulting schema/backup and preview current state, never blindly rerun
  the old approval or automatically restore/overwrite a store.
- Failed final audit publication: last durable resource phase files_removed or
  schema_committed, not complete; recovery is not falsely none.
- Failed first audit publication: not_started / receipt_phase not_started;
  no source mutation or backup. Fix output failure and choose a new receipt path.
- Unknown-schema backup-only success: backed_up / receipt_phase backed_up but
  status blocked, unchanged source/accounting, no removed names or freed bytes.
  Inspect the raw directory recorded in backup.path; do not attempt prefix DROP
  or canonical restore. No automatic reset fallback exists.
- Unknown-schema DB/capture/marker failure or changed relevant state before the
  raw marker: prepared, backup incomplete with .incomplete and no raw-backup.json.
  Source is untouched except the deliberate disposable stale-state injection.
  Fix the input/fault, get a fresh preview and select new backup/receipt paths.
- Admission failures (missing paths/root/profile, unsafe files, stale digest/state,
  explicit caller transaction or held shared lease): not_started; no backup or
  receipt. The missing root/profile is never recreated. Release the actual live
  owner or repair the inspected fixture outside this command, then preview again.

A durable raw-backup.json certifies only a completed raw safety backup. A later
schema transaction/recheck/audit failure may correctly leave that valid backup
while the operation remains blocked at backed_up or schema_committed. It is not
a success marker for schema mutation. On audit I/O failure the last durable
receipt can lag actual resource state; inspect before choosing any recovery.

## Commit And Self-Review

Self-review covered the complete Task6 diff, reference/root admission,
unknown backup-only branch, short write scopes, immutable-trigger rollback,
external dependency handling and durable phase transitions. git diff --check
and git diff --cached --check passed; source/test restoration and parent runner
hashes match. No unresolved implementation finding remains. No justified
ownership split was needed beyond the approved two modules and narrow helpers.

Commit contains exactly nine files, 2068 insertions and 6 deletions:

```text
M src/sec_research/__main__.py
M src/sec_research/capture_lock.py
M src/sec_research/captures.py
A src/sec_research/maintenance.py
M src/sec_research/operations.py
A src/sec_research/schema_admin.py
A tests/test_sec_research_cli.py
A tests/test_sec_research_maintenance.py
A tests/test_sec_research_schema_admin.py
```

No existing tests were removed; the three new files collect 104 Task6 controls.
No controller helper, runbook, evidence archive, ledger, .superpowers artifact or
Task3 references.py change is in the commit. Post-commit git status --short
--branch printed only `## codex/sec-research-integration`, a clean tracked tree.
No product or test bytes changed after the frozen suite. Controller now owns
independent review, evidence sealing, full final gate and any integration decision.

Exact staging/commit checks executed (all exit 0 unless stated):

```sh
git diff --check
git add src/sec_research/__main__.py src/sec_research/capture_lock.py src/sec_research/captures.py src/sec_research/operations.py src/sec_research/maintenance.py src/sec_research/schema_admin.py tests/test_sec_research_maintenance.py tests/test_sec_research_schema_admin.py tests/test_sec_research_cli.py
git diff --cached --check
git diff --cached --stat
git diff --cached -- src/sec_research/maintenance.py src/sec_research/schema_admin.py
git commit -m "feat(sec-research): add explicit cleanup and schema recovery"
git status --short --branch
git log -1 --format='%H%n%s'
git show --format= --name-status HEAD
git diff b49e09c48337cac2337b590f96368e367d6912f5 HEAD -- src/sec_research/references.py
```

## Residual Limits

POSIX/no-follow/cooperating-root-lock assumptions remain;
arbitrary external SQL/filesystem editors are not excluded by the App lease.
WAL fixture tests establish ordinary writer progress during read snapshots;
rollback-journal SQLite may itself delay writers during a read transaction. No
startup journal-mode change is introduced. Actual schema mutation duration still
depends on SQLite and data volume; reducing writer-lock scope is not a fixed
latency guarantee. Hashing/closure verification remains deliberate disk I/O under
the exclusive SEC lease. Ordered row fingerprints are bounded, but the compact
reference/file inventory and inherited 16 MiB operator JSON bound can still block
exceptionally large previews; no automatic batching or implicit cleanup exists.
Raw safety backups are not canonical exports or automatic restore instructions.
The final complete backend gate and actual-store rollout remain controller-owned
and unperformed. No full-release or actual-store integrity claim is made.

## Exact Runner Commands

Historical command inventory, not instructions to repeat create-only names.
These shell variables abbreviate only the exact constant executable and runner
prefix. Full child argv/environment, XML and original logs are retained beside
each command.json. Inverse rows below were invoked by the driver, not twice.

```sh
PY=/home/hyl/.virtualenvs/llm_app/bin/python
RUNNER=.superpowers/sdd/2026-09-12-sec-research-release-integration/run_checks.py
"$PY" -B "$RUNNER" task6-admin-final-focused-01 backend -q tests/test_sec_research_maintenance.py tests/test_sec_research_schema_admin.py tests/test_sec_research_cli.py # exit 0
"$PY" -B "$RUNNER" task6-admin-green-01 backend -q tests/test_sec_research_schema_admin.py tests/test_sec_research_cli.py # exit 0
"$PY" -B "$RUNNER" task6-admission-red-01 backend -q tests/test_sec_research_maintenance.py::test_malformed_apply_input_blocks_without_io tests/test_sec_research_cli.py::test_cli_rejects_nonclosed_preview_before_resolving_database # exit 1
"$PY" -B "$RUNNER" task6-backup-path-green-01 backend -q tests/test_sec_research_schema_admin.py::test_unknown_schema_discloses_backup_only_and_preserves_source # exit 0
"$PY" -B "$RUNNER" task6-backup-path-red-01 backend -q tests/test_sec_research_schema_admin.py::test_unknown_schema_discloses_backup_only_and_preserves_source # exit 1
"$PY" -B "$RUNNER" task6-cleanup-diagnose-01 backend -q tests/test_sec_research_maintenance.py::test_unrelated_market_rows_do_not_invalidate_approval # exit 1
"$PY" -B "$RUNNER" task6-cleanup-diagnose-02 backend -q .superpowers/sdd/2026-09-12-sec-research-release-integration/task6-diagnose.py # exit 1
"$PY" -B "$RUNNER" task6-cleanup-green-01 backend -q tests/test_sec_research_maintenance.py # exit 1
"$PY" -B "$RUNNER" task6-cleanup-green-02 backend -q tests/test_sec_research_maintenance.py # exit 0
"$PY" -B "$RUNNER" task6-cli-help-01 backend -q -rP tests/test_sec_research_cli.py::test_cli_help_does_not_resolve_stores # exit 0
"$PY" -B "$RUNNER" task6-colocated-green-01 backend -q tests/test_sec_research_schema_admin.py::test_schema_reset_refuses_colocated_research_references tests/test_sec_research_schema_admin.py::test_schema_reset_refuses_research_references tests/test_sec_research_maintenance.py::test_cleanup_colocated_empty_research_roots_use_query_only_snapshot # exit 0
"$PY" -B "$RUNNER" task6-colocated-red-01 backend -q tests/test_sec_research_schema_admin.py::test_schema_reset_refuses_colocated_research_references # exit 1
"$PY" -B "$RUNNER" task6-covering-frozen-01 backend -q tests/test_sec_research_maintenance.py tests/test_sec_research_schema_admin.py tests/test_sec_research_cli.py tests/test_sec_research_operations.py tests/test_sec_research_capture_lock.py tests/test_sec_research_captures.py tests/test_sec_research_operation_admission.py tests/test_sec_research_references.py tests/test_sec_research_citations.py tests/test_sec_research_store.py tests/test_sec_research_service.py tests/test_sec_research_tool_service.py tests/test_sec_research_issuers.py tests/test_sec_research_document_store.py tests/test_sec_research_document_service.py tests/test_sec_research_document_queries.py tests/test_sec_research_queries.py tests/test_sec_research_fact_queries.py tests/test_research_threads.py tests/test_research_runs.py tests/test_research_history.py tests/test_sqlite_backup.py # exit 0
"$PY" -B "$RUNNER" task6-cursor-green-01 backend -q tests/test_sec_research_maintenance.py::test_unfinished_autocommit_cursor_is_not_a_fresh_profile_snapshot tests/test_sec_research_maintenance.py::test_stale_caller_read_transaction_is_not_a_fresh_recheck tests/test_sec_research_maintenance.py::test_new_reference_invalidates_cleanup_preview tests/test_sec_research_maintenance.py::test_cleanup_colocated_empty_research_roots_use_query_only_snapshot # exit 0
"$PY" -B "$RUNNER" task6-cursor-red-01 backend -q tests/test_sec_research_maintenance.py::test_unfinished_autocommit_cursor_is_not_a_fresh_profile_snapshot # exit 1
"$PY" -B "$RUNNER" task6-hardening-red-01 backend -q tests/test_sec_research_maintenance.py tests/test_sec_research_schema_admin.py -k 'colocated or malformed_apply or journal or receipt_failure or cancellation or corrupt_retained or changed_capture or unresolved_absent or known_definition' # exit 1
"$PY" -B "$RUNNER" task6-ingest-green-01 backend -q tests/test_sec_research_maintenance.py tests/test_sec_research_schema_admin.py -k 'ordinary_market_writer or excludes_ordinary_writer' # exit 0
"$PY" -B "$RUNNER" task6-ingest-red-01 backend -q tests/test_sec_research_maintenance.py tests/test_sec_research_schema_admin.py -k 'ordinary_market_writer or excludes_ordinary_writer' # exit 1
"$PY" -B "$RUNNER" task6-integrated-green-01 backend -q tests/test_sec_research_maintenance.py tests/test_sec_research_schema_admin.py tests/test_sec_research_cli.py # exit 0
"$PY" -B "$RUNNER" task6-inverse-backup-01 backend -q tests/test_sec_research_schema_admin.py::test_schema_reset_requires_backup_and_exclusive_lease # exit 1
"$PY" -B "$RUNNER" task6-inverse-charge-01 backend -q tests/test_sec_research_maintenance.py::test_registered_orphan_unlink_failure_remains_charged tests/test_sec_research_maintenance.py::test_failed_directory_durability_charge_survives_ordinary_recovery # exit 1
"$PY" -B "$RUNNER" task6-inverse-event-only-01 backend -q tests/test_sec_research_maintenance.py::test_new_reference_invalidates_cleanup_preview tests/test_sec_research_schema_admin.py::test_schema_reset_refuses_research_references # exit 1
"$PY" -B "$RUNNER" task6-inverse-lease-01 backend -q tests/test_sec_research_maintenance.py::test_cleanup_requires_fresh_exclusive_lease # exit 1
"$PY" -B "$RUNNER" task6-inverse-skip-recheck-02 backend -q tests/test_sec_research_maintenance.py::test_new_reference_invalidates_cleanup_preview # exit 1
"$PY" -B "$RUNNER" task6-inverse-unknown-prefix-01 backend -q tests/test_sec_research_schema_admin.py::test_unknown_owned_objects_are_not_prefix_drop_targets # exit 1
"$PY" -B "$RUNNER" task6-receipt-green-01 backend -q tests/test_sec_research_maintenance.py::test_first_receipt_failure_never_claims_a_durable_prepared_phase tests/test_sec_research_maintenance.py::test_invalid_preview_headers_are_not_echoed_in_receipts tests/test_sec_research_maintenance.py::test_unrelated_market_rows_do_not_invalidate_approval # exit 0
"$PY" -B "$RUNNER" task6-receipt-red-01 backend -q tests/test_sec_research_maintenance.py::test_first_receipt_failure_never_claims_a_durable_prepared_phase tests/test_sec_research_maintenance.py::test_invalid_preview_headers_are_not_echoed_in_receipts # exit 1
"$PY" -B "$RUNNER" task6-recovery-red-01 backend -q tests/test_sec_research_maintenance.py::test_recovery_cannot_clear_absent_charge_without_directory_sync # exit 1
"$PY" -B "$RUNNER" task6-red-01 backend -q tests/test_sec_research_maintenance.py tests/test_sec_research_schema_admin.py tests/test_sec_research_cli.py # exit 1
"$PY" -B "$RUNNER" task6-red-02 backend -q tests/test_sec_research_maintenance.py tests/test_sec_research_schema_admin.py tests/test_sec_research_cli.py # exit 1
"$PY" -B "$RUNNER" task6-retry-green-01 backend -q tests/test_sec_research_maintenance.py::test_explicit_cleanup_retry_resolves_absent_charge_only_after_directory_sync tests/test_sec_research_maintenance.py::test_cleanup_final_receipt_failure_does_not_claim_durable_completion tests/test_sec_research_schema_admin.py::test_schema_final_receipt_failure_reports_committed_schema_not_completion # exit 0
"$PY" -B "$RUNNER" task6-retry-red-01 backend -q tests/test_sec_research_maintenance.py::test_explicit_cleanup_retry_resolves_absent_charge_only_after_directory_sync tests/test_sec_research_maintenance.py::test_cleanup_final_receipt_failure_does_not_claim_durable_completion tests/test_sec_research_schema_admin.py::test_schema_final_receipt_failure_reports_committed_schema_not_completion # exit 1
"$PY" -B "$RUNNER" task6-unknown-green-01 backend -q tests/test_sec_research_schema_admin.py tests/test_sec_research_cli.py -k 'unknown or help' # exit 0
"$PY" -B "$RUNNER" task6-unknown-red-01 backend -q tests/test_sec_research_schema_admin.py tests/test_sec_research_cli.py -k 'unknown or help' # exit 1
```

Exact inverse-driver invocations:

```sh
INVERSES=.superpowers/sdd/2026-09-12-sec-research-release-integration/task6-inverses.py
"$PY" -B "$INVERSES" skip-recheck task6-inverse-skip-recheck-01 # driver exit 1, aborted before runner
"$PY" -B "$INVERSES" skip-recheck task6-inverse-skip-recheck-02 # driver exit 0, expected runner exit 1
"$PY" -B "$INVERSES" event-only task6-inverse-event-only-01 # driver exit 0
"$PY" -B "$INVERSES" charge task6-inverse-charge-01 # runner completed exit 1; driver post-check exit 1, detailed above
"$PY" -B "$INVERSES" backup task6-inverse-backup-01 # driver exit 0
"$PY" -B "$INVERSES" unknown-prefix task6-inverse-unknown-prefix-01 # driver exit 0
"$PY" -B "$INVERSES" lease task6-inverse-lease-01 # driver exit 0
```

## Fix Round1

Base: `3194de5e6210ee516c58157f24b48926e413c60c`; Hypatia's R1/R2 accepted by
controller. Commit: `78157e62f0526b90898a2a4b77c1d6ffe6a9a15b`.
Status: implemented, verified, committed, self-reviewed; ready for scoped
rereview. No runner is active. All five fix-round runners completed serially;
two zero / three retained nonzero, no collection/setup errors or aborted driver.
Scope is only maintenance.py, schema_admin.py, __main__.py and the three named
Task6 test files. No operations/capture/Task3 redesign, frontend edits/tests,
provider/production DB/config access, deployment, restart, merge or push.
Controller's untracked docs/design/SEC_RESEARCH_OPERATIONS.md is untouched.

- R1: every operator preview/receipt/backup destination excludes the actual
  profile DB and its -journal/-wal/-shm names as well as the market namespace.
  CLI resolves the profile path once, checks destinations before opening it or
  creating outputs, and opens that same query-only path. Direct applies obtain
  the path from caller profile admission before admitting either output. No
  public maintenance API/CLI flag or preview/receipt format changed.
- R2: each apply retains its originally acquired SEC-exclusive context in a
  standard ExitStack until failure-audit finalization and resource close finish.
  There is no release/reacquire window. Short market transactions are unchanged.
  Barriers prove different-owner SEC operations are denied while ordinary market
  writes commit; observed enter/audit/exit order also detects release/reacquire.
- Tests add 32 profile-namespace combinations (four reserved names over direct
  helpers and CLI preview/apply outputs), five failed-stage lease barriers, and
  two no-lease/no-audit admission negatives. Two existing successful CLI controls
  now also prove a normal separate rollback-journal profile writer succeeds.
  No existing test was removed or weakened.

| Run | Result |
| --- | --- |
| task6-fix1-red-01 | exit 1; 29 assertion failures, 10 passed, 104 deselected; 3.50s |
| task6-fix1-green-01 | exit 0; 41 passed, 102 deselected; 2.69s |
| task6-fix1-inverse-profile-outputs-01 | expected exit 1; 24 failed, 8 passed; 2.66s |
| task6-fix1-inverse-failure-audit-lease-01 | expected exit 1; 5 failed, 2 passed; 1.06s |
| task6-fix1-covering-frozen-01 | exit 0; 1064 passed, no failures/skips; 112.61s |

RED includes the actual R1 failure: backup at the absent profile-journal name
creates a directory and the subsequent ordinary profile write raises
OperationalError. Other sidecar cases prove unwanted output or changed SQLite
mode. The five R2 failures prove the original lease exited before failure audit.
The inverses remove only profile-path exclusion or release only the SEC context
before failure audit (audit descriptors remain open). All failures are behavioral
assertions, no collection/setup errors. Both drivers exited 0; no abort this round.
Both *-source directories retain original/mutated source pairs and completed
receipt.json, exact restored byte hashes and frozen test hashes. Original six
inverses remain pinned to e495d664 and were not rerun or reinterpreted.

Observed durable phases and recovery: R1 rejection and invalid-digest admission
are not_started, with no output/audit/lease; choose an external new output path
and valid fresh approval. Cleanup transaction failure is prepared with rollback;
unlink failure is charged with the 8-byte retained file still charged. Schema
backup failure is prepared without starting backup; post-DROP rollback and
post-backup stale-state refusal are backed_up with the source schema intact and
raw backup retained. Their blocked receipts are now published before the original
SEC lease exits. Remove the fault, inspect the retained state/backup, then use a
new preview/approval and new output paths; do not blindly repeat the old approval.

Remaining concerns: no new architectural issue identified in scoped self-review.
Existing POSIX/cooperating-lease, raw-backup-vs-canonical, WAL read concurrency and
source-only limitations above remain. This fix does not authorize actual stores.
Parent runners remain byte-identical. No product/test change after inverse freeze.
Post-commit hashes match the inverse source receipts and pre-cover freeze;
tracked files/index are clean. Only the untouched controller runbook is untracked.
Commit contains exactly the six scoped files. git diff --check, cached --check,
scoped diff review (including -w to inspect the lifetime deindent), and post-commit
git diff HEAD --exit-code all passed. No remaining R1/R2 concern identified;
independent rereview, controller evidence and full release gates remain separate.

Final SHA256 (original/mutated pairs and restoration receipts remain in the two
task6-fix1-inverse-*-source directories, with no fixture DBs intended for archive):

```text
maintenance.py 0d64f3d0c8b3bc50df5c5d7cc96a8e826e2e710078c518459e5d5350b96c0a90
schema_admin.py 963276ac7f1a086451e056c349beda08e93151f5f2ffe2ee095018ae301c305b
__main__.py b78fc2e58849ae56525fb0d74e93336f3c3b3e52769bb58b491b83bc02040079
test_sec_research_maintenance.py f9f5f5bf54c8d4808bf8b9caa19347844a5a6b1fd4242b1ea2847543995f15d3
test_sec_research_schema_admin.py 9cfc414192921510d0c29f61310dd2933aff2efe114939e132ec64255c7e1236
test_sec_research_cli.py 0f05033f1e945dfd48c7e9bb9a909bc5171009ae799ae27cf1073403a5163634
```

Exact commands (all within /tmp/arkscope-research-output-boundary; P/R/I are only
abbreviations, original full child argv/environment/log/XML remain per run):

```sh
P=/home/hyl/.virtualenvs/llm_app/bin/python
R=.superpowers/sdd/2026-09-12-sec-research-release-integration/run_checks.py
I=.superpowers/sdd/2026-09-12-sec-research-release-integration/task6-inverses.py
"$P" -B "$R" task6-fix1-red-01 backend -q tests/test_sec_research_maintenance.py tests/test_sec_research_schema_admin.py tests/test_sec_research_cli.py -k 'profile_sqlite_namespace or failure_audit_keeps_original or admission_failure_has_no_lease'
"$P" -B "$R" task6-fix1-green-01 backend -q tests/test_sec_research_maintenance.py tests/test_sec_research_schema_admin.py tests/test_sec_research_cli.py -k 'profile_sqlite_namespace or failure_audit_keeps_original or admission_failure_has_no_lease or explicit_preview_approval'
"$P" -B "$I" profile-outputs task6-fix1-inverse-profile-outputs-01
"$P" -B "$I" failure-audit-lease task6-fix1-inverse-failure-audit-lease-01
"$P" -B "$R" task6-fix1-covering-frozen-01 backend -q tests/test_sec_research_maintenance.py tests/test_sec_research_schema_admin.py tests/test_sec_research_cli.py tests/test_sec_research_operations.py tests/test_sec_research_capture_lock.py tests/test_sec_research_captures.py tests/test_sec_research_operation_admission.py tests/test_sec_research_references.py tests/test_sec_research_citations.py tests/test_sec_research_store.py tests/test_sec_research_service.py tests/test_sec_research_tool_service.py tests/test_sec_research_issuers.py tests/test_sec_research_document_store.py tests/test_sec_research_document_service.py tests/test_sec_research_document_queries.py tests/test_sec_research_queries.py tests/test_sec_research_fact_queries.py tests/test_research_threads.py tests/test_research_runs.py tests/test_research_history.py tests/test_sqlite_backup.py
git add src/sec_research/maintenance.py src/sec_research/schema_admin.py src/sec_research/__main__.py tests/test_sec_research_maintenance.py tests/test_sec_research_schema_admin.py tests/test_sec_research_cli.py
git diff --cached --check
git diff --cached --stat
git diff --cached --name-only
git commit -m "fix(sec-research): protect profile outputs and failure audit lease"
git log -1 --format='%H%n%s'
git status --short --branch
git diff HEAD --exit-code
git show --format= --name-status HEAD
```
