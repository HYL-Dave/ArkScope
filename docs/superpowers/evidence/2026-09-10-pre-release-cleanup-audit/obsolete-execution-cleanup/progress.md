# SDD ledger - plan: docs/superpowers/plans/2026-09-11-obsolete-execution-cleanup.md

Base: f25b10ca. Current user request: continue already-approved cleanup.

## Preflight

| Tasks | Shared interface / consistency check | Ruling |
| --- | --- | --- |
| 1 | Pipeline absence vs journal option decoder; agent read cancellation | Keep exact option decoding in its reader; no pipeline alias. Current run_agent controls own live behavior. |
| 2 | Wrapper removal vs existing tests importing wrappers | Transfer all ingestion arguments/validation to execute_macro_job; tests are modified collateral, not unchanged controls. |
| 3 | Scheduler removal vs old preservation owner | Update owner to current engine/job; retain non-scheduler monitor tests and different live SA reconciliation module. |
| 1 + 2 | No shared source/test file | Separate test temp roots. |
| 1 + 3 | Absence tests have separate files | Parent owns shared audit/plan documentation. |
| 2 + 3 | jobs.py is read-only positive control for Task 3 | Only Task 2 may edit jobs.py; no overlap in write sets. |

Ruling: parent implements tightly coupled Task 1 while delegating independent Tasks 2/3, following the tool's critical-path instruction. No different-model override was requested, so delegates inherit the current model.
Ruling: existing specification and repeated user cleanup approval cover this source-only continuation; no new approval for data access/disposal is inferred.
Ruling: the prior offline test launcher is mechanically copied into this plan's ignored directory; every concurrent run gets its own ARKSCOPE_OFFLINE_TEST_WORKSPACE.

## Status

- Task 1: 38319f16, final focused102P, review coverage gaps fixed; re-review9P/no findings, reviewer closed.
- Task 2: 36dac28d, baseline612P, RED8F, final620P; independent518P/no findings, reviewer closed.
- Task 3: 2f80f452, baseline281P/1deselected, RED4F/19P, final270P/1deselected; independent270P/1deselected/no findings, reviewer closed.
- Integration: full backend7966P/12S in745.20s; exact7978 collection/execution nodes,59removed/53added, unchanged12skip IDs, frozen source patch verified. Independent integration reviewer Locke returned no findings and independently reconciled counts/identities/source; reviewer closed. Final evidence archival and hash verification are the only remaining publication work.

## Setup Notes

The workspace script was not executable; invoking it through bash succeeded. The first copy attempt failed because the workspace had not been created. No product change or test result came from those setup failures.

Task 1's first RED attempt was 10 failed/4 passed. Five unintended failures were test-fixture mistakes: the new large-text test cited the first selected appendix instead of the identity passage, and the unresolved fixture called payload with an unsupported keyword/empty citation input. Corrected the test fixtures before any product edit; corrected RED is five intended ownership/absence failures plus nine passing current-agent controls. No product behavior was changed to accommodate the fixtures.

Task 1 mutation: removing await asyncio.shield(future) produced 1 failed/2 passed, specifically task_cancel; restored immediately. AST comparison of _running/_read_one/options against base succeeds for all three (ignoring added class docstring/locations). Node accounting: 23 obsolete-only removed, 14 new, focused 105 -> 96.

The first broad command used a nonexistent test_former_membership glob and ran zero tests; retained as task1-broad-invalid-glob.xml. Correcting to test_sa_tracking_memberships.py yielded 2611 passed/7 failed. All seven failures are FileNotFoundError: node in unchanged TypeScript vocabulary controls. Ruling: add the existing NVM Node directory to the clean test PATH; do not modify product or expected vocabulary. Fresh exact-file rerun and whole backend must include Node.

Node-corrected disposition/current-agent/report run: 71 passed, unchanged product. Task1 review required actual run_agent cancellation and mixed-success source-gap owners. Added six nodes (two stop modes, four transport mixed outcomes). Initial mixed test used the wrong material key gaps instead of source_gaps: 4 failed/16 passed, corrected fixture gives20P. No product logic change. Deleting gap persistence kills all four mixed owners; routing reader.read synchronously kills both agent cancellation owners. Restored both; six focused files now102P. Task1 final net105-23+20=102.

Task2 worker commit verified as seven owned paths only; no behavior cases deleted,18renamed owners/8newabsence IDs. Task3 commit verified separately; five source paths removed including empty package, two exclusive test files deleted; retained 36non-scheduler monitor nodes and live SA/universe/Former/news sources. Parent updates one stale monitor component list in current draft documentation, not dated historical entries.
