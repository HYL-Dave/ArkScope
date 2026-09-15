# C20 Direct Disposal

Baseline: `a6ea41ef`. The user explicitly approves deleting the two old
`agent_queries` rows and their table **without any archive or content review**.
This supersedes the previous archive-before-disposal proposal, not permissions
for other stored data, runtime activation, application shutdown, merge or push.

## Current Status

**C20 CLOSED: code retirement and the approved production DROP are complete.**

Before the user closed the App, its sidecar was observed at PID 357943, working directory
`/mnt/md0/PycharmProjects/ArkScope`, whose master is still `30bb31c7`.
That source's `AppRecordsLocalStore._ensure_schema()` still includes
`CREATE TABLE IF NOT EXISTS agent_queries`; report and memory tools construct
that store. Therefore the old App can recreate the table after a DROP. This is
a deployment-state issue, not a need to archive the old questions.

The user then confirmed normal App shutdown. A fresh process check found no
matching App/native-host/collector writer and `fuser` observed no open profile
handle. The unchanged `f0dd6feb` operation executed on September 15 at
06:49:29 UTC, rechecked exactly two rows, and committed the target DROP.
Its non-target schema, six protected table counts and non-target sequence
entries were unchanged. A fresh mode=ro/query_only connection, with the main
file mounted read-only and a column authorizer, returned `table: absent`.
The metadata-only receipt is `checks/execution.json`.

No question/answer content was read, printed, dumped or archived. No process
was terminated or restarted, no backup was made, and the engine remains 3.37.2.
This confirms the scoped deletion, not a new whole-database integrity baseline
or a runtime switch. The main-master source is still old; restarting it can
recreate an empty legacy table. Hand testing must use the updated branch.

## Source Change

Remove `agent_queries` from `MIGRATE_TABLES`; the two current report/memory
tables remain admitted. Both generic old-query access methods now reject that
name. Current Research stores are unchanged. Store construction does not gain
an automatic DROP: approval is for one known profile, not every existing DB.
Tests prove that explicitly removing the old table is not undone by repeated
construction and that current reports/memories remain readable.

## Verification

- Corrected RED: **3 failed / 21 passed**, exactly the old allowlist and two
  old generic read methods. The first invocation also had a new fixture missing
  required report arguments; corrected before implementation acceptance.
- Candidate SQLite 3.53.1: **297 passed**, 32.16s.
- Current-engine SQLite 3.37.2 control: **297 passed**, 29.55s.
- One-time disposal tests, in-memory only: **6 tests passed**. They cover exact
  target removal with other records/FK/integrity preserved, changed count/shape
  refusal, dependent views/FKs/indexes, denied private reads/other writes, and
  rollback when COMMIT is denied.

The offline runner is the preceding receipt's corrected, interpreter-consistent
runner; the two application files were overlaid into its disposable source copy.
Runs were serial. Selected owners: app records, memory tools, tool registry,
Research threads/runs/history/routes, and SEC trace. The complete 11,245/12 suite
is the **previous checkpoint's** acceptance, not a full rerun of this small
patch. No frontend code, dependency, Python selector or runtime changed.

The one-time script initially did not exist (expected pre-implementation test
failure). Its first implementation used `set_authorizer(None)` to reset the
callback, which the current Python build rejected on the next query. An isolated
three-query probe reproduced that difference; resetting with an explicit OK
callback fixes it. This affected only disposable verification, never production.

## Executed Operation

The one-time operation in `checks/dispose.py` ran against only the approved
main profile after the shutdown checks. It remains historical evidence/operator
code, not an application migration, installed tool or automatic startup action.
Do not repeat the completed production operation.

Within `BEGIN IMMEDIATE`, it verifies the exact old columns, two-row count and
absence of dependent schema objects; takes only schema/sequence metadata and
counts of the six current report/memory/Research tables; drops only
`main.agent_queries`; and checks the non-target schema, counts and sequence
entries before COMMIT. Its SQLite authorizer denies question/answer reads and
writes to current data tables. Any failed check rolls back. No backup, JSON
dump, content hash, REINDEX, VACUUM, manual checkpoint or SQLite update is part
of this operation. SQLite's shared `sqlite_sequence` must remain for live tables.

Execution was network-isolated, with the rest of the filesystem read-only and
existing non-target entries in the data directory remounted read-only. The
writable parent permits SQLite coordination names; this is not a kernel filename
allowlist. No immutable connection or manual checkpoint was used. Postcheck used
the already tested counts-only inventory from the previous receipt. Only the
metadata results were saved, never the deleted contents. App restart, merge,
push and interpreter replacement were not performed.
