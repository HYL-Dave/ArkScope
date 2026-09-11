# Current Journal Cleanup And SEC Foundation

Date: 2026-09-11. Base: `2842c497dabfdb0b13c315e22b206128eba9f57d`.
Worktree: `/tmp/arkscope-listing-sec-macro-convergence`.
Status: bounded implementation and independent reviews complete. Fresh complete
backend verification: **8,116 passed / 12 unchanged skips**, 772.31 seconds.
Source commits: `e2f77cb7` (cleanup/current safeguards), `3095e1ad` (SEC foundation).

This is the next bounded cleanup batch, **not** completion of the whole audit or
the new SEC workflow. No provider, production DB, `.env`, credential store,
installation, App restart, merge or push is part of this batch. Test databases are
temporary. Main-worktree untracked entries are enumerated by name only.

## Implemented Scope

- Delete the old case-scoped store, review, projection, schema and migration.
  Current `lifecycle_investigation.review` directly owns confirmation/acceptance;
  no forwarding facade or old-table fallback remains. Delete the orphan fixed
  two-phase usage-report helpers; retain unchanged current token observations.
- Preserve current assessment IDs, approval packet keys, gap acknowledgement,
  provider vetoes, transactional rechecks, idempotency, reversal and captured
  provider/auth/model/citation provenance. A retained field named `web` is a
  persisted current contract, not permission to revive an old writer.
- Current owned reads capture rows under one snapshot, close the connection,
  then decode large sources. Caller-owned reads retain the caller's transaction.
  Validated adoption binds source hashes, model steps and call records inside
  the later write transaction. No persisted schema/digest format changes.
- Current readback validates bound completed-call usage, typed source gaps and
  source-read reports. Completed observations survive cancellation/deadline;
  recording failure leaves usage unknown without fabricating success.
- Extract a create-exclusive SQLite backup primitive with explicit destination
  connection closure. Current installation/disposal still require their existing
  approvals, snapshots, backups and rollback/receipt guards.
- Remove obsolete population inventory and `web_runs` detail. Keep the current
  registered review tool and shared evidence/translation/history reference checks.
  Resolve FK targets using SQLite's actual case-insensitive identity rules before
  deciding whether unrelated referenced data must be retained.
- Implement SEC-specific typed capacity settings over the existing profile
  string store: exact 100 GiB default, adjustable positive integer bytes, NULL and
  malformed values rejected without repair. Implement DB-derived portable paths
  with relative-key and symlink-escape checks. Neither operation allocates space.

Only ignored bytecode remained in this worktree's `src/audit/`; it was inspected
and removed. This is not a claim that every user's local ignored directory was
scanned or deleted.

## Review-Driven Corrections

The original task reviews and their corrections are separate artifacts. Initial
findings are not overwritten with later PASS labels.

1. Transferred tests exposed current adoption binding omissions (steps/calls),
   owned-read decoding under a rollback-journal read transaction, malformed gaps,
   missing usage/readback validation and a malformed model-context TypeError.
   Useful old guarantees were transferred to current owners, not deleted to keep
   the suite green.
2. Independent Task 1 review found a new producer/validator mismatch: a completed
   reply was counted before its result step, and stop/deadline prevented that
   write. The real controller reproduction used no row tampering. Record already
   completed work, then count it and check stop/deadline. No extra model call,
   retry, fallback or authority relaxation is introduced.
3. Independent Task 2 review found a pre-existing case-sensitive FK matching
   defect. Upper/mixed-case references with CASCADE could bypass generic retained
   dependencies. Canonical SQLite lookup now covers profile and market stages,
   including a dependency added after preview or backup. Distinct non-ASCII
   SQLite names are not merged by Python Unicode casefolding.
4. Task 1 re-review found the corresponding reservation boundary: local budget
   reservation can increment before its journal write succeeds. Result accounting
   now reads the durable reservation count; the local limit remains unchanged.
   Failed pre-dispatch work is zero, while a committed reservation whose local
   acknowledgement fails remains an unknown outcome. The complete run in progress
   at discovery was interrupted (5,299 passed / 12 skipped, exit 2), archived as a
   partial checkpoint, and is not counted as a successful complete suite.
5. R2 review exposed two more producer edges: a failed final count read entered
   model-correctable feedback, and a committed result step with lost local
   acknowledgement disagreed with the in-memory totals. Host journal callbacks
   and final count reads now fail terminally through the existing controller,
   without redispatch or a final payload. This includes source and agent-action
   writes. Already committed evidence stays readable; UI reports unknown usage
   when no trustworthy final payload exists. Strict read validation is not
   weakened and acknowledgement failure is not presumed to mean rollback.
6. R3 review followed this failure through web-source cleanup: `finally` still
   performed a stop check before recording completed I/O, masking the original
   write failure as cancellation. R4 records the completed read with the same
   terminal host boundary as model observations; it does not dispatch work.
   Six promoted before/after-commit/normal controls preserve the read report and
   the failed/code/no-result outcome. The second incomplete full run was stopped
   before editing (4,724 passed / 12 skipped, exit 2); it is not acceptance.

## Verification And Accounting

Final collection and execution contain exactly **8,128 unique nodes**, reconciled
against the immutable 7,978-node baseline in `verification-summary.json`. There
are no failures/errors and all 12 skip identities are unchanged. All 51 changed
source/test path hashes or absences match the reviewed snapshot before and after
the full run and after both source commits. Task1 R4 and integration R4 reviews
report no remaining source blockers; Task2 R1 and Task3 reviews passed their
unchanged scopes. Focused checkpoints are not substituted for full-suite results.
The runner includes the reviewed Node PATH, isolates
fixture stores/HOME, and rejects production files and external network. It is a
test harness, not an OS sandbox.

| Scope | Removed IDs | Added IDs | Net |
| --- | ---: | ---: | ---: |
| Task1 transferred current owners | 184 | 143 | -41 |
| Parent current integrity/interruption owners | 0 | 39 | +39 |
| Task2 schema/backup/population/FK protection | 7 | 33 | +26 |
| SEC config/path foundation | 0 | 126 | +126 |
| Total | 191 | 341 | +150 |

The Task1 ledger maps 169 removed IDs to actual current behavioral replacements,
14 to exclusively obsolete subcontracts, and one to the already-approved current
unknown-event-date plus attended-execution-date policy. The old unconditional
model-date veto is not restored. Task2 removes six old installer nodes and its
old-web-only disposal node; useful backup/retention properties have new owners.
See the exact node lists and owner ledgers, not just aggregate arithmetic.

Useful intermediate checkpoints:

- Parent baseline: 85 passed; physical absence RED: four assertion failures.
- Parent integration focus before late review corrections: 684 passed.
- Transferred current owners/control set: 428 passed at its stated snapshot.
- Task 2 initial final: 149 passed; FK correction final: 164 passed.
- SEC foundation final: 128 passed, including two unchanged profile controls.
- Completed-reply correction: 65 passed including four new boundary owners.
- Durable-reservation correction: 155 passed, including shared-control tests and
  success / cancel-before-reservation / recording failure / lost acknowledgement.
- Final host-journal boundary: RED 8 failed / 25 passed; restored 192 passed,
  including real before/after-commit controls, final-read failure, pending calls
  and existing cancellation/cleanup owners. Four obsolete usage-helper absence
  owners separately failed before deletion; their restored scope passed 73.
- Web-source finalization correction: RED 4 failed / 2 passed; restored 206
  passed, including source-report and execution-cleanup controls.
- Independent Task1 R4: 55 passed, no remaining blocker; separate integration
  review validates the combined identity, census and source boundaries.
- Reopened source-report branch: inverse 3 failed/5 passed; restored 8 passed.

Reports disclose invalid intermediate fixtures and collection/setup attempts;
none is relabelled as a runtime defect or a successful baseline. Mutation logs
distinguish expected failing owners from the redundant traversal mutation that
survived. No frontend, native Windows, live provider or application hand-test
result is claimed for this backend-only batch.

The final R4 source census reads 1,093 files and records 4,309 candidate rows / 3,352
uncertainties. These are scanner candidates, not that many proven dead modules.
Against the prior frozen census, the two new candidates are the deliberately
unfinished SEC config/path modules, currently used by tests only. The 12 file
reductions are exactly five removed old modules and seven removed test modules.
All 32 new SQL uncertainty IDs map to unchanged source lines relocated during
the extraction. Dependency metadata and main-worktree untracked names do not
change. `census-r4-account.json` retains the final snapshot's raw
exit-2/review-required result;
the baseline and scanner were not weakened to make it pass.

Raw XML (including failed and interrupted attempts), immutable review packages,
node ledgers, census reports and reproduction helpers are archived beside this
file. `artifact-index.json` binds archive and original bytes by SHA-256. XML,
review packages and the full node list are gzip-compressed; Python helper sources
use `.py.txt`. Report links retain their original scratch paths, so the index is
the mapping to published copies. Fixture homes, tokens, databases and support
tarballs are not archived. `verify_publication.py.txt` checks archive hashes,
tested source, exact patch identity and node accounting without opening a DB.
Publication readback passed: **140 indexed artifacts, 4,523,445 archived bytes,
51 source/test paths**, exact patch and node accounting verified at `3095e1ad`.
Only this README and the index are deliberately unindexed metadata. The archived
scratch ledger ends at the pre-publication checkpoint; this README and the
checked-in plan record final completion of the bounded batch.

The broad staged whitespace check reports seven blank-at-EOF warnings in
byte-preserved report archives (`integration-r4-review.md`, `task1-r1-review.md`,
`task1-r2-review.md`, `task1-r3-review.md`, `task1-review.md`,
`task1-tests-owner-transfers.md`, `task2-r1-report.md`). They are retained rather
than altering sealed evidence. Runtime/tests and current editable documentation
pass their scoped whitespace checks; no global whitespace rule was relaxed.

## Remaining Work

The actual-store retention manifest from the previous authorized inventory still
governs data disposition. Seven absent old-web tables do not mean the populated
shared case/history/translation data can be dropped. No renewed inventory,
production backup, row deletion or schema disposal was performed here.

Other audit candidates remain: old catalog/backend and provider/sync surfaces,
news rollback/collector-CLI semantics, remaining helper/tool closure, and the
existing CSS/i18n maintenance owners. The scanner is not a proof of total absence.

SEC catalog and exact structured facts, source capture/capacity reservation,
portable export/restore, citations, three-tool registration across all four
transports, schedules and UI remain unimplemented. This foundation cannot yet be
hand-tested as a complete SEC research feature. Future file publication must
address concurrent path replacement; resolution-time checks are not atomic I/O.

## SQLite Assessment

The clean selected Python links SQLite 3.37.2 and reproduces the redundant-UPSERT
index defect in `:memory:` mode. The indexed and table counts diverge (3 vs 2);
full `integrity_check` detects it while `quick_check` reports `ok`. This does not
establish any corruption in ArkScope's actual databases or the running sidecar's
selected interpreter. The scoped source review found no matching SQL combination.

The reported UPSERT fix is 3.45.2, but the separate WAL-reset race needs later
fixes (3.51.3 or the documented backports). Select and verify an application-local
Python/SQLite build, not merely a new CLI or venv on the same base interpreter.
No runtime upgrade was performed; it cannot retroactively repair existing data.
See the detailed `sqlite-research.md` artifact and the official
[UPSERT release note](https://sqlite.org/releaselog/3_45_2.html),
[WAL-reset documentation](https://sqlite.org/wal.html#walreset) and
[release history](https://sqlite.org/changes.html).
