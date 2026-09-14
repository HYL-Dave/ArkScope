# SQLite Runtime Evaluation And Operations

Status, 2026-09-15: the user approved reducing maintenance by preferring a
prebuilt runtime and accepts replacing the self-built deployment plan. No
replacement distribution/version is selected and no production switch is
authorized. The current decision is in
[Runtime And Recent Collection Policy](RUNTIME_AND_RECENT_COLLECTION_POLICY.md).

## What Changes

Do not continue preparation for activation of the custom SQLite-only library.
Its build commands are no longer the installation instructions for ArkScope.
Keep the installed App, Python/numpy/SDK environment, executable selectors and
retained databases unchanged during candidate evaluation. This does not undo
SEC features, completed cleanup or the archived SQLite defect reproducer.

Evaluate maintained prebuilt CPython plus a project virtual environment first.
This can preserve ordinary `import sqlite3` and reuse Desktop's `ARKSCOPE_PYTHON`
and the SA native host's `python_path` instead of introducing another loader.
Neither selector is changed in this step. Reuse the distribution manager's
existing installation, checksum and package inventory facilities where possible;
do not build a second manager around them.

A prebuilt SQLite DBAPI wheel is another candidate, not an automatic standard
library replacement. Its import/connection ownership, maintenance status and
all writer subprocesses would need their own acceptance. Do not select it merely
because it avoids a compiler. Do not silently compile a source distribution if
the chosen platform/Python version has no matching binary.

## Candidate Acceptance

1. Record the publisher, artifact/version, platform/Python support, published
   checksum and update process. Pin the candidate artifact without freezing
   pre-release upgrades. Keep downloads/environments separate from installed
   production paths; do not alter global PATH, shell profiles or loader settings.
2. Probe the actual candidate interpreter's `sqlite3`, not a standalone CLI.
   Record SQLite version/source ID/options and required fixes. Re-run the exact
   archived UPSERT reproducer and disposable WAL, backup, FTS5, JSON, transaction,
   foreign-key and precision checks. A version string is not complete acceptance;
   a candidate is not required to reproduce every old distro compilation flag.
3. Tie parameter limits and optional SQL grammar to real App consumers and
   behavior tests before treating them as requirements. The old verifier's
   `MAX_VARIABLE_NUMBER=250000` and UPDATE/DELETE LIMIT probes are not by themselves
   evidence that every replacement must implement those exact choices. Do not
   weaken required behavior or silently change SQL to make a candidate pass.
4. Verify current dependencies in a disposable project environment, including
   numpy/pandas and SDK/native extensions. Start from existing dependency versions;
   any necessary Python minor/dependency change must be reported and reviewed,
   not applied to the working environment as an incidental installer action.
5. Prove Desktop, SA and current writer children resolve the same admitted engine
   with preserved argv, cwd, signals and native-host stdout. Prove supported
   production entrypoints cannot silently run on an unadmitted system engine.
   Keep unmanaged development explicit without granting production-store access.
6. Run full application acceptance serially against the supplied binary. No
   SQLite archive or compiler is needed for binary acceptance. Report exactly
   which behavioral owners run, move or are removed; no hidden skips to make a
   replacement appear accepted. The unchanged full backend has now run, with
   the errors/skips and additional large-ID failures classified below. Full
   candidate admission, including real entrypoints, has not passed.

## Limited Feasibility Probe, September 15

A disposable `python-build-standalone` 20260901 Linux x86_64 artifact was checked
against its published SHA-256 before sandboxed extraction. Its Python 3.10.21
loads SQLite 3.53.1 without compilation or a loader override. The unchanged
archived UPSERT matrix passed all five cases; in-memory FTS5, JSON and decimal
TEXT checks also passed. The system Python still reports SQLite 3.37.2.
Artifact identity, isolation, raw matrix output and observed options are in
[the probe receipt](../superpowers/evidence/2026-09-15-prebuilt-runtime-spike/probe.json).

This proves a no-local-build route, not App compatibility. The candidate has
`MAX_VARIABLE_NUMBER=32766` and no UPDATE ORDER BY LIMIT grammar. A targeted text
search outside the old runtime found no explicit occurrences, but does not prove
dynamic SQL or parameter workloads fit. It also contains 3.53.1 rather than the
newer 3.53.4 in [upstream release history](https://www.sqlite.org/changes.html).
Review required fixes and actual consumers before admitting this or another
candidate. That initial spike exercised no project dependencies, App tests, real
entrypoints, WAL/backup tests or production stores. Nothing was deployed. The
subsequent project evaluation is recorded separately below.

## Project Compatibility Evaluation, September 15

At `f42e7909`, the same artifact ran a disposable 89-wheel project environment
without compilation or dependency version drift. Eight reused database behavior
probes and the five unchanged UPSERT cases passed. The single full backend run
returned **11,147 pass / 26 setup errors / 43 skips**, exit 1, exactly 11,216
cases. This is evaluation evidence, not green acceptance:

- All 26 errors come from the old contract fixture's `_sqlite3.__file__`
  assumption. This CPython has a built-in module; the fixture fails before its
  behavioral checks. Transfer useful startup/engine/safety owners during the
  replacement, rather than inventing a module path to make the fixture pass.
- Of 43 skips, 31 are source-dependent old launch tests and 12 are existing
  manual IBKR/SEC checks. No new skip or changed expectation was introduced.
  Do not rebuild SQLite to satisfy a fixture being replaced.
- Five additional large-ID cases fail at the candidate's 32,766 parameter limit
  and pass in a disposable system-engine control with the same wheels. Owners:
  `sa_capture_backend`, `sa_article_reconciliation_store` and
  `security_lifecycle_fact_kernel`. A single JSON-bound ID set is proposed,
  pending confirmation, with ordering/limits, empty inputs, integer range and
  citation-preserving deletion semantics retained. No product SQL was changed.

The first attempted full run was invalidated because a temporary runner missing
its main guard reentered pytest from spawn workers. None of its counts are used.
After correction, the affected-module preflight passed 915 cases and the new
full run had exactly one main entry. The current receipt preserves the runners,
source identity, isolated environment, raw results and failure cases:
[prebuilt project compatibility](../superpowers/evidence/2026-09-15-prebuilt-runtime-compatibility/README.md).

SQLite 3.53.1 still needs review against subsequent fixes; neither the full suite
nor bounded WAL stress proves all those fixes irrelevant. Desktop/SA/production
writer entrypoint acceptance, the replacement/removal patch and production
cutover remain open. No installed interpreter, original dependency environment,
selector, production store or running App was changed by this evaluation.

## Replacement And Removal Boundary

Current source at `8ef04a60` still contains `src/sqlite_runtime/build.py`,
`contract.py`, `launch.py`, package initialization and the early check in
`src/__init__.py`. The corresponding tests are `test_sqlite_runtime_build.py`,
`test_sqlite_runtime_contract.py`, `test_sqlite_runtime_launch.py` and
`test_sqlite_runtime_startup.py`. This policy revision changes none of them.

Once the candidate passes, the replacement patch owns removing superseded
self-build/custom-loader code and build-only tests, together with their obsolete
archive environment variable and source-only acceptance gate. Do not retain a
permanent fallback builder or forwarding aliases. Replace early engine checks
and preserve real startup, corruption/mismatch, descendant and native-host
behavioral tests in the same change; do not just delete their coverage.

The current launch-test fixture rebuilds its own disposable package and still
requires `ARKSCOPE_TEST_SQLITE_ARCHIVE` when a custom runtime is selected. That
is an existing self-build-test dependency, not a general requirement to execute
SQLite. Its September 15 evidence remains valid for the old artifact only.
Existing preparation commands and test receipts are retained in the
[historical preparation evidence](../superpowers/evidence/2026-09-14-private-sqlite-runtime/README.md)
and [acceptance evidence](../superpowers/evidence/2026-09-15-runtime-acceptance-cleanup/README.md),
not as an active deployment recipe.

## Production Window Remains Separate

After replacement acceptance and separate approval of the operational window,
inventory supported writers/stores, stop writers, make coherent WAL-safe backups
and run full integrity checks on verification copies before changing selectors.
Retain referenced SEC content and recovery bindings. Do not use `immutable=1`
on live WAL stores or silently repair data. No new production access is implied
by the prebuilt-first decision.

Verify actual App/SA/child engine identity before resuming writes. After resumed
writes, changing an executable path alone is not proved rollback. No automatic
fallback, REINDEX, VACUUM, schema reset or database deletion belongs to activation.

Linux remains the initial target. Windows/macOS acceptance and the Python sandbox
are separate workstreams; a publisher offering those binaries does not prove
ArkScope support. Do not reconnect or widen the dormant analysis executor.
