# SEC Integration And Cleanup Continuation

This is not a complete SEC release or a master merge. No production database,
private configuration, provider or running application was accessed by the
integration tests. SQLite preparation is separate from runtime activation and
actual-store integrity assessment.

## Preservation And Integration

- `ba4f2619` preserves the 45 modified SEC paths, four new code/test files and
  eight source-only analysis files: 57 paths total. Both previously untracked
  product modules are recoverable from git. Its commit explicitly records the
  historical 4-failure/758-pass result, not a release-ready claim.
- Security base: `41682675`, product candidate `ff7c4d75`. The user's supplied
  Opus review reports an independent 10166-pass/12-skip run and successful
  credential, all-cut-point stream and public-content checks. This is attributed
  external review, not a new local run or a rewrite of sealed security evidence.
- `codex/sec-research-integration` starts at that security base and replays SEC
  as `3fef138d`. Original branches remain intact; master was not changed.
- Against common base `18d46062`, nine files overlap and five have textual
  conflicts, not seventeen independently overlapping SEC core changes.

## Integration Repairs

1. SEC registrations declare a closed validator through shared `ResultPolicy`.
2. OpenAI preserves async handler identity and awaits it inside the sanitized
   exception boundary; the sync wrapper returned unawaited SEC coroutines.
3. Anthropic SEC dispatch now uses the common argument/error boundary.
4. SEC owns OAuth stop/join/deadline. A second bridge timer raced and replaced
   its closed timeout result. Other tools retain their original deadline logic.
5. The historical SEC-only redactor is deleted. All four channels use identical
   canonical serialization and wrapping. Typed rejection never silently changes
   a cited passage. Domain-specific whole-page budgeting remains.

## Verification

Commands/JUnit, review reports, source snapshots and the exact local harness are
sealed under [checks/manifest.json](checks/manifest.json). The
[final reconciliation](checks/integration-validation.json) checks actual test
identities and source/runtime stability; [run-accounting.json](checks/run-accounting.json)
records each of the65 completed run receipts separately, including32 nonzero
RED, inverse, intermediate-failure, invocation-error and census results.
No run receipt is unfinished. The SQLite build has its own per-step receipts.
Original scratch location and command paths remain provenance:
`.superpowers/sdd/2026-09-12-sec-research-release-integration/`. Restage the
archived harness into that layout to rerun it with fresh create-only run names;
do not execute the copied scripts from their evidence directory or overwrite
historical receipts. Fixture databases, HOME trees and compiled artifacts are
not included in the archive.
The copied offline runner uses disposable stores and a closed environment. Its
Python audit hook blocks production paths/providers but is not an OS sandbox.

| Run | Actual result | Meaning |
| --- | --- | --- |
| integration-red-01 | exit 4, no tests | Wrong test filename; invocation error, not RED evidence |
| integration-red-02 | 40 failed / 38 passed | Missing policy and unawaited async callback |
| integration-red-03 | 7 failed | Named policy, byte-equivalence and async owners |
| integration-green-01 | 4 failed / 414 passed | Two obsolete serializer monkeypatches, old tool count/name owners |
| integration-green-02 | 1133 passed | SEC, eight count files, skills/subagent, both OAuth drivers, output/key/card guards |
| integration-timeout-red | 2 failed / 8 passed | Both OAuth timers lose closed SEC timeout; document bytes agree |
| integration-timeout-green | 187 passed | Stop/join/timeout, adapters and OAuth regressions |
| integration-review-red | 12 failed | Actual Anthropic SDK stream loses all three SEC results; governor-stop dispatches for both CIK and ticker; transport has no cancellation callback |
| integration-review-green-01 | 2 failed / 233 passed | New owners pass; old in-flight fixture records dispatch after cancellation |
| integration-review-green-02 | 994 passed | Actual native stream, governed cancellation, body/retry closure, SEC and security/agent regressions |
| backend-full-final | 10277 passed / 2 failed / 12 skipped | First complete integration attempt; three stale count assertions in two previously unlisted lifecycle files |
| integration-last-collateral-red | 2 failed | Both full-run failures independently reproduced before changes |
| integration-last-collateral-green | 126 passed | Correct counts, exact retained routes/tools and old route/name absence; four whole affected test files |
| backend-full-reconciled | **10279 passed / 12 skipped** | Fresh complete run on frozen `ae2055e3`; zero failures/errors/warnings, 10291 exact collected/executed nodes |
| frontend-regression | **1776 passed / 123 files** | Full frontend regression; no later frontend source changes |
| frontend-typecheck | exit 0 | Existing TypeScript check |
| sqlite-application-stores | **330 passed** | Separate isolated SQLite3.53.4 candidate; not the runtime of the full backend run |

Separate focused runs are not an additive total or a complete backend result.
The final complete backend run contains no warnings. Unawaited-coroutine
warnings remain in pre-fix evidence.
The shared security inventory is additional count collateral: 56 tools comprise
49 ordinary JSON, 3 closed SEC JSON and 4 text policies.

`ae2055e3` corrects only test collateral and its plan: total App routes224->223
after removing GET /sec/{ticker}; both OAuth allowlists15->17 after one old tool
is replaced with three. Required lifecycle entries remain, all three SEC names
are required and the old route/name must be absent. The full-run failures were
an integration inventory omission, not preexisting failures or a runner defect.
A complete rerun `backend-full-reconciled` passed on frozen product/test source:
10279P/12S in1386.65s (runner1390.703s). The initial attempt is not combined
with126P to claim that result. There are123 added and10 removed test IDs against
the sealed security run, no duplicate IDs and the same12 skip IDs. All retained
credential/auth/tracing guards and new SEC regression suites ran without skips.
The before/after snapshots agree on1130 source files, runner, packages and
Python3.10.12/SQLite3.37.2. Source collection SHA-256:
`4f41b72c83ff98606944bae71ca8b4a8ea1afe7df8700f28cc1137d62a55129d`.
Eight removed IDs belong to the replaced old SEC catalog surfaces, one to the
orphan FileBackend nominal interface test, and one to the renamed tool-count
test. The exact IDs and all new-suite results are in the final reconciliation.

Eight process-local Task2 inverses independently removed each transport entry,
selected generic truncation, omitted worker join, removed the subagent guard,
and removed an actual required subagent tool. All eight were detected:24
expected failures,25 controls passed; fresh unmutated union30P. The worker reaped
all five intentionally detached cancellation workers and restored every mutated
attribute. Source files and the concurrent full-suite process were not modified.

## Remaining Work

Task2 review reproduced two defects after the adapter checks: nested
`asyncio.run` in the actual Anthropic streaming caller and metadata dispatch
after cancellation while waiting for the SEC governor. Fixes now await the
SEC worker in the actual stream and propagate the task's cancellation check
through metadata/map acquisition to the existing cooperative governor, dispatch,
body and retry boundaries. Legacy callers without a check keep their retry
behavior. Actual producer tests compare the entire result sent back to the
model with canonical service output. The old in-flight fixture now records
its first request before waiting, retaining its one-request/context/stop/join
assertions. Independent scoped re-review found no correctness issues and ran
51 tests successfully without warnings, including all 12 new regression cases.
Its receipt is `task2-rereview-5d979910-db4df4d9`; it pinned the unchanged C09
imports to avoid concurrent mutation interference. This is not a security-wide
or full-release review. Tasks1/4 were already reviewed, not restarted.
Tasks3/5/6/7 remain open: durable Research citations/reopening, operation leases
and export/restore, orphan cleanup/schema reset, default-disabled scheduling.
Settings and backend citations do not imply these workflows are complete.

C03 old catalog tool/forwarders/empty HTTP route are removed here. C11-C13,
C15/C20 data disposition, i18n/CSS/SQL census queues and production SQLite
admission are not marked complete. C21 remains an explicit deferred capability.
Actual data deletion still requires bounded inventory, backup and approval.

## C09 Checkpoint

The unused EODHD/Alpha Vantage/Finnhub standalone source classes and unified
factory are physically removed. Current Polygon/EDGAR/IBKR exports, Finnhub
news/calendar and EODHD census/Settings credentials remain. Current docs no
longer advertise removed adapters; dated provider comparisons are historical.
No stored data or keys were inspected or changed.

The worker observed 6 failed / 190 passed before product deletion, then
196 passed; restoring a removed leaf made its named owner fail. Controller
run `c09-controller-green` independently returned 196 passed. Seven test IDs
were added and none removed. Independent source review of `f30ee8fc` found no
lost live consumer or key-precedence regression.

Controller supplemental inverses used process-local injection, not on-disk
mutations: restoring an obsolete export, removing a retained export, and forcing
legacy-over-Massive key precedence each failed exactly its existing named owner.
Receipts: `c09-inverse-export`, `c09-inverse-retained`, `c09-inverse-key` (one
failure each); unmutated `c09-final-restore` returned 196 passed.

Ledger correction at sealing: the worker's final `c09-report.md` also contains
completed `c09-resume-*` inverses, not only its earlier partial handoff. Raw
JUnit confirms three named1F inverses, their1P restorations and a196P final run.
Those receipts predate the controller's process-local replications and both
complete-backend runs; all possible mutated paths match the frozen source.
The controller had misread the completion status, so its extra inverses are
independent repeat checks, not completion of missing worker work. Both receipt
sets are preserved and their pass totals must not be added together.
C09 is accepted within this scope; it is not cleanup-wide completion.

## C10 Checkpoint

Removed the whole orphan FileBackend and its unused construction/constructor
argument through LocalMarketBackend, SACaptureBackend and DAL. The initial plan
incorrectly assumed a retained raw-file import consumer. A full non-test source
scan found none; keeping that reader after removing the unused construction
would have created a new orphan. Raw files and actual database news/prices/SA/
financial_cache are untouched. The new FileBackend file/import absence owners
were RED before full deletion. Existing concrete SQLite news/search tests are
the positive controls, not an invented empty reader.

The SA routing stub was missing from initial constructor collateral. Its path
assertions now test the actual retained DAL._base while preserving routing
assertions. The old FileBackend nominal-protocol test is removed, replaced by
the two named absence owners; temporary unshipped raw-reader tests are superseded.
Task2's extra EOF blank is removed without changing its test assertions.

Worker: initial 4 failed / 2 passed; corrected absence RED 2 failed / 2 passed;
revised GREEN 350 passed / 1 skipped. Controller expanded regression:
`c10-controller-green`, **467 passed / 1 skipped**. Independent review of
`fc3c4668..885c2a2d` found no issues and returned32 passed, including exact
nonempty SQLite news/FTS/prices/cache, SA and routing controls. No provider or
actual data was read. The complete rerun after the separate lifecycle count
collateral correction passed as recorded above; no C10 product change followed
its independent review.

## Census Checkpoint

Baseline `41682675` against frozen product `885c2a2d`:4345 candidates,3471
uncertainties,1146 source files read. Zero new candidates, dependency metadata
changes or untracked-path drift. Five coverage reductions are precisely C09's
four removed source/factory modules and C10's FileBackend.

34 new SQL uncertainty IDs replace34 old IDs. `reconcile_census.py` pairs every
entry by equal ASTs at the old/new line locations and identical metadata,
not merely matching totals. These are line moves across six source files;
CENSUS-SQL-001 remains open, not repaired by this classification. The old empty
GET /sec/{ticker} candidate disappears; sec_research_tools is no longer
test-only because it is now wired. Scanner exit2 remains honest review_required,
not a zero-debt claim or a production-data deletion manifest.

The delivery census at `6caed84e` independently repeats4345 candidates/3471
uncertainties/1146 source files, zero new candidates/dependency/untracked drift
and the same five deletions and34 AST-identical line moves. It observes211
documentation files rather than210 at the earlier checkpoint. Subsequent
sealing/status-document edits are not retroactively part of that observation.

## SQLite And Deployment

The [SQLite candidate report](sqlite-candidate.md) records the verified3.53.4
source, actual mapped library, unchanged UPSERT reproducer and standalone plus
application-store tests. It is not an installed upgrade: the App runtime remains
3.37.2. Full production integrity assessment, WAL-consistent backup, coordinated
runtime/launcher activation and rollback are still required before any stored
schema disposition. Python3.13 is a separate numerical-dependency decision,
not a prerequisite for SQLite-only preparation. No production database, private
selector, running App, master branch or remote was changed in this batch.

## Next Bounded Cleanup

[C11 news routing plan](../../plans/2026-09-13-news-routing-cleanup.md) is prepared,
not implemented. It corrects the earlier narrow diagnosis: the obsolete toggle
does not select a writer but malformed values can still block collection, as
well as hide current telemetry. Removing obsolete value validation must retain
current normalized-setting/source-requirement validation. C12's real collector
CLI consumers are deliberately not treated as unreachable modules.

## Seal Readback

Readback verified all328 manifest entries,187 compressed files and3,829,670
stored bytes against both their source and stored SHA-256 values. No extra
files, fixture stores/HOME trees or compiled binaries are admitted. All65 run
receipts are complete and all ten final integration checks pass. Manifest
SHA-256: `1e4ae0dcef2bc2b29b6c494fe7e21c8d8d54b943412a3186dc793b3ac325c112`.
Later status documentation is outside the create-only checks archive.
