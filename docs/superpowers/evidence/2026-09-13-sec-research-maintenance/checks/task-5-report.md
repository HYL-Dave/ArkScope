# Task 5 Report

Status: COMPLETE for approved Task5, including both controller findings and the
stranded-WAL source-preservation repair. Focused verification is complete; this
is not a full release-runner receipt or authorization for destructive maintenance.
Base: 01ca7c58, branch codex/sec-research-integration, requested existing worktree.
No subagents, other worktrees, provider calls, real stores/config, install,
activation, app lifecycle, merge or push. The full release gate remains controller-owned.

## Checkpoint 1

Commit: `edab0f9b` (operation and durable Research protection).
Changes: capture_lock, captures, Store, issuer/tool/service/query/document/citation
owners; Research executor, legacy SSE executor, direct message/event/atomic error
publication; tests/test_sec_research_operations.py. No scheduler lock.

Operation order: operation -> issuer/document -> capture writer -> market write
-> SQLite. POSIX no-follow regular-file lock in the existing trusted root-hashed
namespace. Shared and exclusive acquisitions are nonblocking; busy is the typed
ValueError code sec_research_operation_busy. Missing stored roots are not created.
Thread-local active ownership includes process/thread/async-task identity; neither
child/copied nor stale Context objects convey reentrancy. Upgrade fails closed.
Executor protection precedes tool production and ends after terminal durable
publication, including cancellation. Direct durable reference writers also enter
the lease before their write mutex/SQLite boundary. Each worker has its own
existing copy_context invocation; no shared mutable Context reuse was introduced.

## Exact Verification

Every run uses `/home/hyl/.virtualenvs/llm_app/bin/python -B
.superpowers/sdd/2026-09-12-sec-research-release-integration/run_checks.py
NAME backend ARGS`. Each create-only NAME directory retains command.json with
the complete executed argv/environment, output.log and results.xml.

Runner SHA256: run_checks.py
2c1cc48b15f817b02cc70a99cad757a0962e875e37381fa122fca8b89796247f;
offline_pytest.py
4c74153e1ef86c35f7bbc923586de624c0ffe3f577c2853e6e4c0a78426c95ff.
Both scratch files match the tracked sealed copies.

- task5-operation-red-01: 7 failed in 0.55s, assertion failures including actual
  maintenance admission after put before metadata publication (no collection errors).
- task5-operation-green-01: 16 failed, 625 passed in 62.16s. Preserved regression
  evidence: 15 document/citation guards initially preceded pure validation; one
  read lease unnecessarily fsynced existing lock directories. Fixed in product,
  no expectation relaxation.
- task5-research-red-01: 3 failed, 7 deselected in 3.12s. Actual executor result,
  event and message boundaries admitted maintenance for success/error/cancel.
- task5-operation-green-02: 756 passed in 86.83s.
- task5-owner-red-01: 3 failed, 10 deselected in 2.68s. Stale copied Context and
  direct message/event publication assertions; no errors.
- task5-owner-green-01: 89 passed in 8.94s.
- task5-terminal-red-01: 1 failed, 3 passed, 11 deselected in 3.19s. Direct atomic
  error-terminal publication admitted maintenance. Legacy SSE protection passed.
- task5-inverse-outer-lease-01: 5 failed, 10 deselected in 3.55s. Skipped outer
  acquisition/executor/SSE leases only; put-to-publish, three Research terminal
  paths and legacy stream all failed by maintenance admission, not errors.
- task5-operation-checkpoint-01: 1119 passed in 105.43s. Tests: operations,
  capture_lock, service, queries, fact_queries, captures, store, document_service,
  document_queries, citations, tool_service, trace (test_sec_research_ prefix),
  test_research_runs.py, test_research_threads.py, test_research_output_events.py.

No concurrent runners. Inverse receipt creation: 2026-09-13 16:50:42.536905947
+0800, checkpoint output creation: 16:51:09.783027683 +0800. Inverse runner exit
was observed before restoration and checkpoint launch; source stayed frozen
during every test run.

Inverse original/restored versus mutated SHA256:

- capture_lock.py: a3c7f88d7f8b26a4562349da662b99c64aed87ff6a626b3855374ba5fc0bbc6c
  / 4b22ba4ed6f4f1de045e62e481227870f96521b4fd55ab5051a6affa40eac42a
- research_run_manager.py: a833700d14b96bed29e7c777c75f4e6f75a77566afe71ba7473cf8a9897d9fe3
  / a5456dd238516e2213a97ad4ea3996ba500a5507554fe0e08cb453da7d2cf302
- api/routes/query.py: 1eb932ffb343d25dd60f88c314472177d23d32d0f4791e7fd9cf6081e63d82ac
  / f495ca550d0de56b682a835a28973dbeb4dbbbac8ac4e428ae99a72727f604dc

## Checkpoint 2

Commit: `1d27394f` (verified portable export and restore).

Delivered actual operator entrypoints, not an unattached utility:

- `research_operation(root, *, exclusive=False, create=False)` protects capture,
  metadata, stored queries, citations and Research publication as described above.
- `export_bundle(paths, destination: Path, *, free_bytes=None) -> dict` reuses
  `backup_market_db(str(source), str(staged_db), overwrite=False)`. Its inventory
  comes from the SQLite backup, not subsequent live metadata. All registered
  objects, including historical and otherwise unreferenced registered objects,
  are copied; unregistered staging/orphan files are excluded.
- `restore_bundle(bundle: Path, destination: Path, *, database_name="market_data.db",
  free_bytes=None) -> dict` creates a new enclosing directory and derives the
  restored capture root with `SecResearchPaths.from_market_db`. Historical facts,
  filings, documents, receipts and catalog sources reopen through actual readers.
- `python -m src.sec_research export --destination ...` and `restore --bundle ...
  --destination ... --database-name ...` use those same owners. No model-facing
  filesystem operation was added. Only disposable fixtures invoked the CLI here.

Manifest: closed format `arkscope-sec-research`, version 1, `manifest.json` final
success marker; whole market SQLite database, SEC capture objects only. It
explicitly excludes independent profile/SA stores and other capture roots, not
rows already colocated in the market DB. It records the current SEC schema
fingerprint, exact relative inventory and hashes/sizes, verified graph/reference
counts, and `clear-transient-accounting-v1` normalization. Reservations/orphan
accounting are cleared only in the private backup. Its database bytes are labeled
`normalized-backup-not-source`; source-byte equivalence is not claimed.

Verification includes SQLite integrity/FK checks, strict receipt/directory JSON,
full historical catalog/document/source closure, issuer maps, registered-object
hashes and any colocated Research citations. Independent profile stores are never
opened. A WAL-mode input bundle is rejected from its binary SQLite header before
SQLite can create sidecars. Copy/hash I/O is bounded to 1 MiB chunks. Space
preflight reserves twice the full database plus object sizes, plus the existing
metadata margin, independently of the capture quota.

Create-only directory ownership, no-follow descriptor checks, exact member
enumeration and an atomic no-replace final manifest reject existing destinations,
symlinks, special/extra/missing members, unknown/duplicate manifest fields,
invalid hashes and incomplete graph closure. ENOSPC, fsync failures and injected
interruption retain an incomplete owned destination, not an accepted bundle.

Additional exact receipts (same create-only runner convention above):

| Receipt | Exact Test Output |
| --- | --- |
| task5-bundle-red-01 | 19 failed, 15 deselected in 6.35s |
| task5-bundle-green-01 | 19 passed, 15 deselected in 8.52s |
| task5-bundle-hardening-red-01 | 1 failed, 13 passed, 36 deselected in 5.09s |
| task5-bundle-green-02 | 50 passed in 13.84s |
| task5-bundle-content-red-01 | 2 failed, 2 passed, 50 deselected in 2.84s |
| task5-bundle-green-03 | 1 failed, 65 passed in 15.76s |
| task5-bundle-green-04 | 66 passed in 16.04s |
| task5-inverse-live-inventory-01 | 1 failed in 2.54s |
| task5-inverse-catalog-source-01 | 1 failed in 2.54s |
| task5-inverse-bypass-hash-01 | 1 failed in 2.73s |
| task5-inverse-existing-destination-01 | 2 failed, 52 deselected in 3.27s |
| task5-wal-admission-red-01 | 1 failed in 2.57s |
| task5-bundle-checkpoint-01 | 1270 passed in 133.15s (0:02:13) |

RED explanations: absent command assertions; final success marker initially
coexisted with `.incomplete`; nonempty issuer-map tuple/list representation and
large UTF-8 document verification exposed two product defects. The sole failure
in bundle-green-03 was a new test requesting document index mode and then expecting
a passage; corrected to request the explicit query and additionally assert exact
full document bytes. No expectations were changed to hide runner interference.
WAL-admission RED showed SQLite was reached for a purportedly normalized WAL
input; the binary-header admission guard now precedes it.

Named bundle inverse owners, each an assertion failure without test errors:

- Live inventory: `test_export_uses_backup_inventory_during_concurrent_publish`.
  Mutated `_inventory(staged)` to `_inventory(live)`; inventory disagreement killed it.
- Omit catalog source: `test_export_restore_preserves_wal_and_historical_citations`.
  Omitted the historical catalog snapshot object; actual closure verification killed it.
- Bypass hash: `test_bundle_rejects_corrupt_unreferenced_registered_object`.
  Removed both pre-restore and copy hash equality; acceptance of damaged bytes killed it.
- Accept existing destination: `test_create_only_publication_never_overwrites_competing_destination`
  with `-k 'create_only_publication and empty'`; accepting an existing empty enclosing
  directory failed both export and restore owners.

All four operations.py inverses were individually restored to SHA256
`131eb4e3a5cbc2e31d6ecfdd4dd839078a0d3aca1d55add73ad5652f1d5e78ca`
before the next run. Mutant hashes in the order above:

```text
da73d1b67a2f72679cd4e2f4c57b9dd02828d81c7f15db1af90091b3bb562375
65ab416100f32becf9d666b92539e1ade4226dae80c75950ebf6ccd96016bb94
d419b13361bf1a08add238686cfa4dddd7a1145b22f9348fa1ffb9c33e26defe
4317463f490b78c48cbd07bc2362318c55c86e8d59c71171376f359ed74e5c55
```

## Checkpoint 3

Commit: `1704ffc4` (closed maintenance admission and source preservation).

Controller finding 1 was reproduced in both actual execution paths:
`execute_research_run` and `schedule_research_run` left the admitted row queued
after busy acquisition escaped. The legacy StreamingResponse terminated with a
transport exception. Admission now catches only the closed
`sec_research_operation_busy` failure before entering provider/result production.
Managed runs reuse the existing atomic `fail_queued_run_handoff` transaction,
extended with an optional validated `error_code`, to commit failed status, one
error replay event and one linked error message. This lane accepts no tool results
and publishes no SEC references, so it does not reacquire the unavailable shared
lease. It never claims the provider ran, sets no started/personalization/usage
trace, and does not weaken the guarded result-bearing terminalization path.
Already terminal runs are not retried or appended again.

Legacy busy admission yields one closed error SSE and a normal final HTTP body;
no new user turn or provider dispatch was admitted. ASGI 2.3 and 2.4 paths both
complete. Available direct/scheduled/SSE controls still succeed. The public code
and English/Traditional Chinese presentation identify maintenance rather than
mislabeling it as a provider failure. Normal result-to-event-to-message protection,
before-reference admission, cancellation and output-boundary cleanup remain covered.
No scheduler registry, scheduling algorithm or scheduler lock was changed.

Controller finding 2 was reproduced for export below the source capture root
(including objects/child) and restore below the input bundle. These operations
previously succeeded while modifying their sources. Destination equal to or below
that source boundary now fails `sec_research_bundle_path_invalid` before backup,
database admission or destination creation. Six boundary cases assert unchanged
source members/digests; subsequent valid sibling export/restore controls succeed.
The two equal-path RED cases already refused existing destinations but exposed
the more specific path-boundary rejection ordering; the four nested cases exposed
actual source mutation.

Additional source audit: a crashed disposable SQLite writer leaves a committed
WAL with no open writer. The existing read-write backup source connection changed
the main database hash and removed this WAL on close. A RED fork/waitpid fixture
reproduced that behavior without any provider process. The same existing backup
primitive now opens its source with a read-only SQLite URI. Committed WAL contents
are retained in the exported snapshot and source main/WAL hashes remain unchanged.
No third backup primitive was introduced.

| Receipt | Exact Selection / Output |
| --- | --- |
| task5-stranded-wal-red-01 | operations::test_export_does_not_checkpoint_stranded_source_wal; 1 failed in 2.64s |
| task5-review-red-01 | operations -k 'busy_admission or destination_cannot_mutate'; 9 failed, 3 passed, 56 deselected in 5.06s |
| task5-maintenance-ui-red-01 | researchErrors.test.tsx; 1 failed, 7 passed; 337ms |
| task5-review-green-01 | operations + sqlite_backup; 80 passed in 19.55s |
| task5-maintenance-ui-green-01 | researchErrors.test.tsx + researchReducer.test.ts + i18n/researchPresentation.test.ts; 99 passed; 415ms |
| task5-admission-asgi-green-01 | operations -k busy_admission; 8 passed, 62 deselected in 2.46s |
| task5-inverse-busy-admission-01 | operations -k 'busy_admission and maintenance and not 2.3'; 3 failed, 67 deselected in 2.51s |
| task5-inverse-source-overlap-01 | operations -k destination_cannot_mutate; 6 failed, 64 deselected in 4.67s |
| task5-inverse-stranded-wal-01 | operations::test_export_does_not_checkpoint_stranded_source_wal; 1 failed in 2.63s |
| task5-repair-checkpoint-01 | full focused selection below; 1390 passed in 151.71s (0:02:31) |
| task5-maintenance-ui-typecheck-01 | frontend run typecheck; tsc --noEmit, exit 0; runner 11.593s |

Here `operations` means `tests/test_sec_research_operations.py` and `sqlite_backup`
means `tests/test_sqlite_backup.py`. Each backend row retains its full exact argv
in that receipt's command.json and unabridged output.log/results.xml. Frontend
receipts use the same run_checks.py with `frontend test -- PATHS` or
`frontend run typecheck`, its existing offline_node.cjs guard and existing installed
dependencies. No install, real app server or app lifecycle was started.

The three new inverses were restored individually before subsequent verification:

| File / Mutation | Original And Restored SHA256 | Mutant SHA256 |
| --- | --- | --- |
| research_run_manager.py / raise busy before terminalization | 33b2f369833355549f331015a68d509ebc132ec0524818273ce510089413c9c7 | ba7420e233060586f4121c0377d74a755a91a69b1b88620a9c9c275795cbe4db |
| api/routes/query.py / raise busy before SSE handling | 24229a1323e0fb18a1f6be2a9e3af30d72689c124d08339dfbe09709d595d54c | 4ab01ca889532517c6b968c94158adc14a4a0956bfcd356f2e63c28b5f298b42 |
| sec_research/operations.py / bypass both source-overlap guards | 8c53b44e3f514eb666e1436db999963088bd0836caf15d0b546480052327ba37 | 597e38f3c63ba0f1706f2490a832c97c1a84aa747e356a94f799c07387dbb315 |
| market_data_direct.py / open backup source read-write | 3138197929ffb5ccee80aa2c58e23cfcc19971cb5d214fac737eb8e240a534ea | f4b115ca91dc4b9603076a85a8240f3da6b3f9e2a008112b8f690b1458711dbc |

## Final Verification

Exact final focused command, run with source frozen:

```sh
/home/hyl/.virtualenvs/llm_app/bin/python -B \
  .superpowers/sdd/2026-09-12-sec-research-release-integration/run_checks.py \
  task5-repair-checkpoint-01 backend -q \
  tests/test_sec_research_operations.py \
  tests/test_sec_research_capture_lock.py \
  tests/test_sec_research_service.py \
  tests/test_sec_research_queries.py \
  tests/test_sec_research_fact_queries.py \
  tests/test_sec_research_captures.py \
  tests/test_sec_research_store.py \
  tests/test_sec_research_document_service.py \
  tests/test_sec_research_document_store.py \
  tests/test_sec_research_document_queries.py \
  tests/test_sec_research_citations.py \
  tests/test_sec_research_references.py \
  tests/test_sec_research_issuers.py \
  tests/test_sec_research_tool_service.py \
  tests/test_sec_research_trace.py \
  tests/test_research_runs.py \
  tests/test_research_threads.py \
  tests/test_research_output_events.py \
  tests/test_research_output_lifetimes.py \
  tests/test_sqlite_backup.py \
  tests/test_market_data_direct.py
```

Output: `1390 passed in 151.71s (0:02:31)`, exit 0. Task5 operations file now
contains 70 collected cases; all are covered here. Checkpoint 2 used the same
selection except output_lifetimes and market_data_direct, before the additional
15 admission/source-preservation cases. Final `git diff --check` was clean.

Sequential-run audit of all 33 Task5 receipts, excluding the controller's
task5-resume-baseline: no overlaps. Compared each output.log creation time with
the preceding command.json completion time; every process completion was also
observed before any restoration/edit/next runner. The original queried
inverse/checkpoint ordering remains valid, not exploratory or interference-tainted.
Latest receipt ordering (UTC):

```text
inverse-busy-admission-01  09:29:06.037 -> 09:29:09.339
inverse-source-overlap-01  09:29:36.254 -> 09:29:41.725
inverse-stranded-wal-01    09:30:11.367 -> 09:30:14.815
repair-checkpoint-01      09:31:01.395 -> 09:33:34.546
maintenance-ui-typecheck-01 09:33:41.991 -> 09:33:53.584
```

No runners remain active. Product/test sources were not changed after their
covering GREEN runs; only this report follows the third checkpoint.

## Changed Files

Exact Task5 paths relative to base 01ca7c58:

```text
.superpowers/sdd/2026-09-12-sec-research-release-integration/task-5-report.md
apps/arkscope-web/src/i18n/resources/en/research.ts
apps/arkscope-web/src/i18n/resources/zh-Hant/research.ts
apps/arkscope-web/src/researchErrors.test.tsx
apps/arkscope-web/src/researchErrors.ts
src/api/routes/query.py
src/market_data_direct.py
src/research_errors.py
src/research_run_manager.py
src/research_runs.py
src/research_threads.py
src/sec_research/__main__.py
src/sec_research/capture_lock.py
src/sec_research/captures.py
src/sec_research/citations.py
src/sec_research/document_queries.py
src/sec_research/document_store.py
src/sec_research/fact_queries.py
src/sec_research/issuer_store.py
src/sec_research/operations.py
src/sec_research/queries.py
src/sec_research/references.py
src/sec_research/service.py
src/sec_research/store.py
src/sec_research/tool_service.py
tests/test_sec_research_operations.py
```

## Residual Concerns

- Task6 deletion/reset is not implemented or admitted here. It must use the
  verified backup/lease boundary; these leases are not scheduler or provider locks.
- Coordination assumes the existing trusted lock namespace is not replaced
  externally. All participants must acquire this root's operation lease; unrelated
  tools bypassing this protocol cannot be coordinated by it.
- Research shared leases conservatively span whole executions, including provider
  waits. Maintenance therefore reports busy until durable publication/cleanup ends.
  The only admission-failure write exception is the reference-free queued failure
  transaction described above, with its existing Research mutex/SQLite ordering.
- Publication currently requires Linux/POSIX no-follow primitives and atomic
  renameat2 no-replace support. Unsupported publication fails explicitly, not by
  falling back to overwriting paths or unlocked operation.
- Durable Research error persistence still requires writable Research SQLite;
  storage failure recovery remains the existing reconciliation path. This task
  does not claim process-crash recovery beyond that path or a scheduler redesign.
- Whole-market backup may include colocated non-SEC rows; it is not a credentials
  scrubber. Independent profile/SA stores and other captures are explicitly out of
  scope. No real export/restore, activation, runtime SQLite deployment decision or
  full release gate was performed. Those remain controller-owned.
