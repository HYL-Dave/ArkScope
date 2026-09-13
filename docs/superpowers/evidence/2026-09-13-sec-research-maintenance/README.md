# SEC Protected Maintenance Continuation

Status: **Tasks5/6 source implementation accepted**, including independent reviews
and a fresh complete offline regression. This is not a complete SEC release or
actual-store deployment. Continuation base: `7401e656`; tested product/test source:
`78157e62f0526b90898a2a4b77c1d6ffe6a9a15b`; docs-only pre-run HEAD: `254307e3`.
The [parent plan](../../plans/2026-09-12-sec-research-release-integration.md)
still has Task7 scheduling and Task8 wider cleanup/release acceptance open.

## Delivered Scope

- Task5 protects complete SEC operations, including capture-to-reference
  publication, pinned/multi-read operations, and Research result-to-durable
  citation commits. The existing capture-writer flock alone did not cover these
  lifetimes. This is not a duplicate scheduler job lock.
- Create-only portable export/restore validates exact manifest member names,
  types, hashes and reference closure. It backs up the whole market database
  consistently and packages SEC capture objects, not a separate profile/SA
  database or arbitrary external files. It is not a whole-profile backup.
- SEC-RECOVERY-001 supplies observational cleanup previews, digest-bound apply,
  current retained-reference rechecks and external receipts. Interrupted deletion
  remains charged until filesystem durability and accounting are reconciled.
- SEC-RECOVERY-002 supplies explicit reset/uninstall of the exact current SEC
  schema, with backup, fresh-state recheck and unrelated-data preservation.
  Unknown owned shapes may produce only an explicitly approved raw safety backup;
  they remain blocked from deletion. There is no prefix DROP or startup repair.

Long reference scans, file hashing, backup, unlink and audit publication do not
hold the global market writer lock. SEC exclusivity still covers the entire
maintenance operation, including failure audit. Normal market/profile writer
positive controls remain part of acceptance. Output admission protects both
market/profile database files and their SQLite sidecars.

Commands, scope and recovery states are documented in the
[operator runbook](../../../design/SEC_RESEARCH_OPERATIONS.md).

## Review And Corrections

The [initial Task5 report](task5-worker-report-initial.md) retains its original
RED/intermediate/inverse results, not a retrospective all-green account.
Task5 review found stranded Research admission failures and bundle member-type
confusion; `4dfa0d37` fixes both and
[scoped re-review](checks/task5-rereview-1.md) accepts them.

Task6 review found separate-profile sidecar/output collisions and failure audit
occurring after SEC lease release. `78157e62` fixes both. The
[final scoped review](checks/task6-rereview-1.md) accepts R1/R2 and the two-line
locale inventory collateral, with no new scoped finding. Fix-round evidence
retains RED29F/10P, GREEN41P, killed inverses24F and5F, and the restored1064P
covering run. Initial and fix-round inverse readbacks are pinned to their
respective immutable checkpoints, not confused with later legitimate edits.

The first full frontend attempt was1829P/1F: the locale inventory still expected
224 Research leaves instead of the actual236. `3194de5e` changes only the two
exact inventory constants. The failed receipt, focused14P and final full1830P
are all retained; no test or diagnostic output was suppressed.

## Final Verification

| Gate | Actual Result |
| --- | --- |
| Complete backend, single runner | **10827 passed, 12 unchanged skipped**, zero failures/errors;1320.185s runner |
| Collection/JUnit reconciliation | **10839 collected = executed**, no duplicate nodes;244 added,0 removed from citation acceptance |
| Frozen source/runtime | 1151 paths; no source, runner, SDK hook, package, Python or SQLite drift |
| Complete frontend, restored | **1830 passed /126 files** |
| Typecheck / build / i18n literals | All exit0; existing i18next debug and large-bundle warning retained |
| Source-only census | exit2/review_required;4355 candidates,3543 uncertainties,1167 files read |
| Receipt accounting |92 completed run receipts,52 nonzero retained; no unclassified failure or unfinished run |

The full backend ran alone with frozen source. No census, frontend or second
pytest session ran concurrently. Its [reconciliation](checks/task6-final-validation.json)
verifies the unchanged12 skip identities, retained safety owners and maintenance,
operation and citation suites. Source collection SHA256:
`93c470af219d947f4d25842ae942c9d9d3fa2d40649531cf6b5044e2ceae8c91`.

The census added25 candidates:24 consumed locale leaves and the operator
`__main__` entrypoint. Raw177 new uncertainty IDs separate into103 positional
and74 new/changed records; see the [adjudication](checks/task6-census-adjudication.md).
Coverage reductions, dependency drift and main-worktree untracked-name drift
are zero. SQL findings remain with CENSUS-SQL-001 rather than being relabeled
empty or used as automatic deletion permission. Wider cleanup is not closed.

[Run accounting](checks/task6-final-accounting.json) keeps expected RED/inverse
failures, corrected fixture/helper failures and earlier census review results
separate from final acceptance; these are not totals of unique tests. A final
controller helper invocation initially wrote the after-freeze JSON in the
worktree root instead of scratch. The validator stopped before comparison;
the unchanged file was moved to the intended path and validation then passed.
No product/test edit or full-suite rerun was needed for that path error.

## Boundaries And Remaining Work

No production DB/config/credential access, provider call, actual-store
export/restore, cleanup/reset, installation, App restart, merge or push occurred.
All destructive and concurrent-writer checks use disposable fixtures. Evidence
includes selected reports, diffs, command receipts, logs, JUnit and original/mutant
source hashes; fixture databases, HOME/credentials and runtime binaries are
excluded by the [archive manifest](checks/manifest.json).

SQLite remains3.37.2 in the unchanged Python3.10.12 runtime used for this gate.
The prior isolated3.53.4 candidate evidence is not activation. App-private
unchanged-Python deployment direction has been asked of the user; packaging,
relocation/compile-profile validation and the stopped-writer backup/integrity
window remain separate. No permission to activate is inferred.

Task7 scheduling, Task8 release acceptance, remaining C12/C15/C20 cleanup and
the i18n/SQL census queues remain open. Actual-store maintenance needs its own
observed preview and execution approval; this milestone does not claim those
stores have been cleaned or reset.
