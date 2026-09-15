# C15 Current-Installation Cleanup

Branch: `codex/c15-current-installation-cleanup`.
Worktree: `/tmp/arkscope-c15-current-installation-cleanup`.
Baseline: `9bb80725238947c351e0257765c9b53280e67569`.
Scope: C15 only; the parent plan was read-only. A, B and C20 are not included.

## Current Capabilities

- `src/lifecycle_investigation/migration.py` remains the current installation
  owner, including `_snapshot`, `_preview`, `preview_installation` and
  `apply_installation`. Its only change is the helper import. The same is true
  of `disposal.py`. CLI `install-preview`, `install`, `disposal-preview` and
  `disposal-stage` remain available through `src.lifecycle_investigation`.
- `src/lifecycle_investigation/sqlite_helpers.py` owns the extracted
  `_sha_file`, `_quote_identifier` and `_encode_cell` implementations. Their
  function ASTs are identical to baseline. The historical exception spelling
  `ListingMigrationRejected`, its `RuntimeError` base, and the error argument
  `unsupported_sqlite_value` are retained as an encoding contract, not as a
  converter or forwarding module. Consumer-local `_sha_file` imports still
  support receipt-failure injection.
- `src/sa_tracking_installation.py` is the current V4 membership owner.
  `inspect_installation(profile_path)` is read-only;
  `preview_installation(profile_path, sa_path)` binds the profile and exact SA
  observations; `apply_installation(profile_path, sa_path, *, backup_path,
  cutover_sha256, at, app_stopped)` performs the attended install.
  `_install_memberships` is its private, backed-up V4 provisioning operation.
  It is the sole non-test `SaTrackingMembershipStore.install` caller.
- The explicit current operator entry is `python -m src.sa_tracking_installation`.
  Commands `inspect --profile ... --output ...`, `install-preview --profile ...
  --sa ... --output ...`, and `install --profile ... --sa ... --backup ...
  --cutover-sha256 ... --app-stopped` reach those APIs from a guarded module
  entrypoint. Paths are never defaulted, output manifests are create-only, and
  install timestamps are generated in UTC. This is a usable current entry, not
  a module referenced only by tests or historical protected-store scripts.
- Membership installation retains disabled, valid automation controls; literal
  stopped-App approval; digest checks before backup and under `BEGIN IMMEDIATE`;
  owner-only create-exclusive backup files; backup verification; atomic DDL and
  bootstrap; identity and related-security context; rollback on `BaseException`;
  integrity/foreign-key checks; and guarded, non-reconciling no-ops. Existing
  preview/receipt fields and error codes are unchanged. Read inspections now
  explicitly roll back and close on both success and failure; writable and
  backup connections also explicitly close.
- The V2/V3 listing converter and V3 provider conversion/rebuild branch are
  absent. V2/V3 inputs are rejected without conversion, backup, or repair.
  Shared schema declarations are byte-identical, including declarations used
  to derive current V4. Retained database rows are not code-retirement targets.

## Test Transfer

`tests/current_installation_fixtures.py` directly creates populated V4, with
retained lifecycle cases, runs, evidence, translations, facts, assessments,
actions, migration receipts, identity history, provider checks, sequences, and
unowned tables/indexes/views/triggers. It invokes neither retired converter.

`tests/test_sa_tracking_installation.py` transfers the provider safety guards
and listing read-snapshot concurrency/rollback guards. Coverage includes real
SA capture dual lineage, all retained cells/rowids/SQL, private backups, no
overwrite, idempotence without restoring removed intent, profile and observation
drift, atomic bootstrap, all four automation-control cases (also before no-op),
post-backup source/control changes and backup drift, persisted identity/related
security context, malformed current schemas, and missing-store no-create.

The old provider/listing converter test modules are retired. The investigation
installation, disposal/retirement, CLI, and SQLite-backup tests are unchanged.
The focused run includes the disposal test
`test_disposal_rolls_back_shared_evidence_when_receipt_publication_fails`, which
monkeypatches the consumer's `_sha_file`. The real CLI install plus resumable
36-case disposal test remains green.

`tests/test_sa_tracking_installation_cli.py` exercises the new current module
entry in real subprocesses: inspection, exact preview, attended installation,
retained rows and dual-source display, no-op, required explicit inputs,
create-only preview/backup, observation drift, and discoverable install options.

## Verification

All pytest execution was serial and confined to this worker's source in a
Bubblewrap sandbox. `run_tests.sh` and `offline_pytest.py` record the runner.
The prebuilt interpreter, its venv, and the control venv were mounted read-only
from `/tmp/arkscope-prebuilt-compat.oCmRRHrQ`; its shared `BASE/source` was never
mounted or written. The worker's synthetic source root is
`/tmp/arkscope-c15-evaluation.G7sxyGBc/source`.

The sandbox clears the environment, unshares networking, uses synthetic HOME,
state and locks, disables scheduling/tracing/plugin autoload, and blocks socket
and provider-CLI execution. It mounts only source/tests, Python data-source
modules, static skill resources, and the single census script needed by current
collection. No original `.env`, production database, configuration, auth home,
key store, or ciphertext documents were mounted. The runner has a `__main__`
guard. No paid SDK/CLI session or production operation was performed.

| Run | Exact Result |
| --- | --- |
| `red-absence` before product edits | 4 failed, 0 passed |
| `baseline-r3` original focused tests | 64 passed |
| `helper-baseline` original helper contracts | 35 passed |
| `red-current-owner` before product edits | 31 failed, 1 passed |
| `green-current-owner` first extraction check | 66 passed, 1 failed |
| `green-focused-prebuilt` | 186 passed |
| `green-focused-control` | 186 passed |
| `green-final-prebuilt` | 193 passed, SQLite 3.53.1 |
| `green-final-control` | 193 passed, SQLite 3.37.2 |
| `collect-final-prebuilt` before explicit CLI addition | 11269 collected, no errors |
| `red-current-cli` before command-handler edits | 10 failed, 0 passed |
| `green-current-cli` real subprocess entrypoint | 10 passed |
| `green-handoff-prebuilt` final scoped check | 203 passed, SQLite 3.53.1 |
| `green-handoff-control` final scoped check | 203 passed, SQLite 3.37.2 |
| `collect-handoff-prebuilt` final current collection | 11279 collected, no errors |
| `collect-handoff-control` final current collection | 11279 collected, no errors |

The first extraction-check failure was a new test's display-count assumption:
three membership identities correctly produce four display rows for the
current/former dual-source case. The assertion was corrected to check the
explicit ticker/status pairs and three unique membership identities; no product
behavior was changed to satisfy it.

Sandbox bring-up failures are separate from product RED: `baseline` had three
collection errors because the Python `data_sources` package was not mounted;
`baseline-r2` had 63 passed and one failure because static skill resources were
not mounted. `collect-prebuilt` collected 11206 tests with one collection error
because its census script was not mounted. Each missing dependency was added
read-only without mounting configuration, auth, data or protected documents.

The 13 handoff focused modules are recorded in each run's `runtime.json`.
Raw pytest logs, JUnit XML and runtime identities are retained under `runs/`;
the large collection logs and multiline pytest diagnostics use lossless,
timestamp-free gzip compression, preserving their original whitespace.
`preservation-audit.json` records the AST comparisons, preserved-file hashes,
absence of current retired imports, and the single current membership installer.
`audit_changes.py` reproduces that read-only audit with the standard library;
it parses source but imports no application code and executes no historical
script. There was no separate reviewer-agent tool available; source review was
performed against the baseline plus these independent contract checks.

## Historical Replay

All seven sealed scripts/source snapshots that reference the retired modules
remain byte-identical; their individual paths and hashes are in
`preservation-audit.json`. Their replay revision is explicitly
`9bb80725238947c351e0257765c9b53280e67569` (`9bb80725`), not the new current tree.
They are historical artifacts, not current entrypoints. No forwarding aliases
or replacement files were left at the retired module paths. These scripts were
not executed: protected-store replay would require its own authorization and
the historically appropriate environment. This is a replay pin, not a claim
that protected-store historical operations were rerun.

## Handoff Limits

No current plan/design document or existing sealed evidence was edited; the
git-crypt-smudge-bypassed ciphertext files were untouched and no keys were read
or unlocked. No merge, push, production install, disposal, runtime deployment,
or full test-suite execution was performed. Parent integration with A/B/C20 and
the final serial full suites remain parent-owned. The worktree is preserved.

## Scoped Paths

- Removed: `src/security_lifecycle_listing_migration.py` and
  `src/security_lifecycle_provider_migration.py`. No forwarding modules remain.
- Current replacements: `src/lifecycle_investigation/sqlite_helpers.py` and
  `src/sa_tracking_installation.py` (including its executable operator entry).
- Retained live consumers, helper import change only:
  `src/lifecycle_investigation/migration.py` and
  `src/lifecycle_investigation/disposal.py`.
- Retained byte-identical operator consumer:
  `src/lifecycle_investigation/__main__.py`.
- Removed converter test consumers:
  `tests/test_security_lifecycle_listing_migration.py` and
  `tests/test_security_lifecycle_provider_migration.py`.
- Added current tests/fixtures: `tests/current_installation_fixtures.py`,
  `tests/test_current_installation_cleanup.py`,
  `tests/test_lifecycle_investigation_sqlite_helpers.py`,
  `tests/test_sa_tracking_installation.py`, and
  `tests/test_sa_tracking_installation_cli.py`.
- Evidence additions are confined to
  `docs/superpowers/evidence/2026-09-15-c15-current-installation/`.
  `CHANGED_PATHS.txt` lists the exact staged paths, including raw evidence.
- The exact seven retained historical consumer paths and byte hashes are in
  `preservation-audit.json`; their replay is pinned to `9bb80725` as above.
