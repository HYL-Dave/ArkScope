# Obsolete Execution Cleanup

**Scope:** source-only continuation of the user's approved pre-release cleanup.
Base `f25b10ca2ce55401460c6296205c9b2c42a18e31`; runtime/test head `38319f16`.
Full backend verification is **7,966 passed / 12 skipped**, with exact7,978-node
collection/execution equality. Independent whole-slice integration review found
no findings within this scope. No production inventory or disposal is part of this run.
The parent's [publication verification](publication-verification.md) records
readback/hash checks for all 112 indexed artifacts after that review.

## Actual Changes

| Commit | Removed | Retained Current Owner |
| --- | --- | --- |
| `36dac28d` | Six test-only macro delegates, unused scheduler subprocess wrapper and daily-update command wrapper | `execute_macro_job`, actual six named jobs, sanitized workers and daily CLI |
| `2f80f452` | Three spent `src/audit` operators, empty package and duplicate monitor scheduler | Different live SA reconciliation service, monitor engine/job/tool, current universe/Former/news behavior |
| `38319f16` | Fixed two-call investigation pipeline, its execution defaults/result/error and exclusive tests | Adaptive `run_agent`; its cancellable read helper; retained journal's options decoder |

No forwarding module or retired callable replaces the deleted code. The current
draft component list now names `monitor_watchlist_scan`, not the removed scheduler.
No frontend source/test, dependency, HTTP interface, schema or production-data
change belongs to this slice. Source/test diff: 26 paths, 651 insertions and
3,626 deletions. Archived historical plans/receipts are not rewritten.

The source-read helpers and journal options class match the base AST after
ignoring locations and the added class docstring. This preserves cooperative
stop delivery and awaiting the worker even when the awaiting task is cancelled.
Current-agent owners exercise all four transport selections, exact credential
and effort, full large Unicode capture/passage grounding, source gaps and
context rejection without clipping/retry. No live LLM was needed or called.

## Verification Ledger

Raw XML, including unsuccessful attempts, is archived with `.gz` suffix.
`artifact-index.json` maps original scratch names to archives and records both
original and archived SHA-256 values. Review reports are kept verbatim, so their
original XML links may require the archive suffix. Synthetic databases, homes,
tokens, captured fixtures and test configuration are deliberately not archived.

| Check | Observed Result |
| --- | --- |
| Task 1 baseline / corrected RED / final focused | 105P / 5F + 9P / 102P |
| Task 1 independent review | Initial two coverage findings; corrected re-review9P, no remaining findings |
| Task 2 baseline / RED / restored final | 612P / 8F / 620P |
| Task 2 independent review | 518P, no findings |
| Task 3 baseline / RED / final | 281P / 4F + 19P / 270P; one unchanged config-reading node explicitly deselected from scoped runs |
| Task 3 independent review | 270P, same explicit deselection; no findings |
| Complete backend collection | 7,978 unique nodes |
| Complete backend execution | 7,966P / 12S, zero failures/errors,745.20s; exact collection and all59removed/53added IDs reconciled |
| Independent integration review | No findings; independently reconciled full XML, collection, task deltas, unchanged skips and frozen source |

The full backend run includes the Task 3 scoped deselection. Full execution is
reconciled with collection and task-specific added/removed IDs in
`verification-summary.json`; no sum of overlapping scoped runs substitutes for
that complete run. Frontend/build are not rerun for this backend-only slice;
previous frontend results are historical evidence, not a fresh claim.

### Failure And Mutation Account

- Task 1's first RED had five intended failures plus five new-fixture errors.
  The fixture selected an appendix instead of the identity passage and called a
  payload helper incorrectly. These were corrected before product edits. The
  later review-fix fixture initially used `gaps` instead of `source_gaps`, causing
  four failures; changing only that test field produced20P.
- The first broad command used an unmatched Former-membership test glob and ran
  zero tests. The corrected selection produced2,611P/7F; all seven failures were
  unchanged Node-dependent tests with a clean PATH missing the existing NVM
  directory. No product or expected value was changed. The complete affected
  disposition/current-agent/report files passed71P with corrected PATH; the full
  backend uses that same corrected PATH.
- Task 1's initial review found missing actual-agent pending-read cancellation
  and successful-finding-with-unread-supplement owners. Both are now present.
  Removing the worker await kills one named helper case; suppressing gap
  persistence kills all four mixed-outcome cases; routing reads synchronously
  kills both actual-agent cancellation cases. All mutations were restored.
  Physical pipeline/import absence was RED against the actual original code,
  not asserted as a separate post-green restoration experiment.
- Task 2 restored the original FRED delegate: one named absence test failed and
  seven passed. Restore-final620P. Eighteen old ingestion cases changed owner to
  actual shared execution, retaining arguments and error assertions; no behavior
  case was dropped.
- Task 3's first baseline273P/8F was a scratch-guard fixture binding mistake:
  `_CONFIG_PATH` instead of `_MAIN_CONFIG_PATH`. The intended config reads were
  rejected; only the scratch binding changed, then281P. Four original source
  modules were restored verbatim and all four physical-absence owners failed;
  archived blob hashes match the originals. They were removed again before final
  tests. The 36 non-scheduler monitor cases remain unchanged.

### Test Count Ownership

| Slice | Removed IDs | Added IDs | Net | Interpretation |
| --- | ---: | ---: | ---: | --- |
| Task 1 | 23 | 20 | -3 | 22 old pipeline nodes plus its instrument prompt owner; 20 current-agent/absence nodes |
| Task 2 | 18 | 26 | +8 | 18 renamed real-execution owners plus eight absence nodes |
| Task 3 | 18 | 7 | -11 | 12 spent operator, five duplicate scheduler and one old preservation owner; four absence, two actual job and one tool owner |
| Total | 59 | 53 | -6 | Reconcile exact IDs, not only totals |

The base's7,984-node set is reconstructed from the preceding archived7,983-node
collection plus the exact facade-absence owner added by `e61accaf`. Runtime/test
sources from that commit through `f25b10ca` are equal. This is not described as a
new full baseline run. The prior12 skipped identities must remain unchanged.

## Mechanical Scan

Comparison against `sec-retention-helper-cleanup/post-facade-census.json.gz`:
1,091 files read,4,320 candidates,3,379 uncertainties; **exit2/review_required**.
New candidates0, dependency metadata changes0, new main-worktree untracked
names0. Nine coverage reductions are exactly six removed source paths including
the empty package and three exclusive test files. Four old orphan/test-only
module candidates disappear.

Twelve new uncertainty IDs correspond to unchanged source statements moving
lines: dynamic imports, old journal SQL and daily-update SQL preparation gaps.
`census-account.json` binds each to its old line and old uncertainty record; this
explains the delta without editing scanner output or accepting a new baseline.
Existing SQL/i18n/CSS/other uncertainties are not declared clean or authorized
for deletion. The scan enumerates only names of the main worktree's two
pre-existing untracked entries; it does not open their contents.

## Reproduction And Boundaries

From this worktree, after placing archived helper scripts back into a dedicated
`.superpowers/sdd/2026-09-11-obsolete-execution-cleanup` scratch directory:

```sh
env -i \
  PATH=/home/hyl/.virtualenvs/llm_app/bin:/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin \
  PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  ARKSCOPE_OFFLINE_TEST_WORKSPACE=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-11-obsolete-execution-cleanup/backend-full \
  /home/hyl/.virtualenvs/llm_app/bin/python -B \
  .superpowers/sdd/2026-09-11-obsolete-execution-cleanup/offline_pytest.py \
  -q tests --junitxml=.superpowers/sdd/2026-09-11-obsolete-execution-cleanup/backend-full.xml
```

Complete collection uses the same launcher with `collect_support tests
--collect-only -q` and a separate scratch root. `summarize_verification.py` checks
exact collection/execution equality, task deltas, skips and the frozen source
patch. Each concurrent run had its own temporary stores/home/locks. The copied
launcher rejects production data and `.env` reads, non-loopback networking and
real provider CLI sessions. This is a test audit guard, not an OS sandbox;
synthetic child launchers and existing local binary version checks are permitted.
No provider refresh, actual-store inventory/backup/write, App restart, merge or
push occurred. The earlier authorized WAL/SHM inventory was not rerun.

## Remaining Cleanup

The obsolete fixed orchestrator no longer blocks removal, but useful shared
consumers still do: old journal store writers/readers, review/adoption/freshness
guards, current detail projections and history relations. Extract those exact
current consumers before deleting their old implementation/schema declarations.
Populated shared SEC evidence must follow the already recorded retained-row
projection and separate data-disposition approval; absent old-web tables alone
do not authorize dropping shared history or translations.

Other audit groups retain their recorded boundaries. This is not a claim of
whole-project cleanup completion. New SEC catalog/facts/documents, three tools,
citations and portable export remain unimplemented and follow this cleanup.
