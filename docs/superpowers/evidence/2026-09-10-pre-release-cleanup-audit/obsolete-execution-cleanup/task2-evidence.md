# Task 2 Evidence

Scope: Task 2 only of docs/superpowers/plans/2026-09-11-obsolete-execution-cleanup.md; audit C05/C06 in docs/superpowers/evidence/2026-09-10-pre-release-cleanup-audit/README.md:179-180.

Worktree: /tmp/arkscope-listing-sec-macro-convergence
Branch: codex/listing-sec-macro-convergence
Baseline commit: f25b10ca2ce55401460c6296205c9b2c42a18e31
Task 2 commit: 36dac28d (refactor(service): remove test-only execution wrappers)
Commit readback confirmed exactly the seven owned changed paths below; all owned paths are clean. Task 2 code is frozen for parent integration testing.

## Changes

- src/service/jobs.py
- src/service/data_scheduler.py
- src/daily_update.py
- tests/test_fred_ingestion.py
- tests/test_finnhub_ingestion.py
- tests/test_data_scheduler.py
- tests/test_execution_wrapper_cleanup.py

- Removed six service macro delegates, scheduler _run_subprocess, daily run_command and its newly unused subprocess import.
- No additions to production code. jobs.run_job, all six job definitions, execute_macro_job, outcome normalization, sanitized workers, daily main and _RunTelemetry remain unchanged.
- Moved all 18 ingestion argument/default/validation cases to the actual execute_macro_job entrypoint. Existing assertion statements, pytest.raises contracts, ingestion argument fixtures and ingestion fakes were preserved; only the entrypoint imports/calls and test owner names changed.
- Removed 16 obsolete scheduler patch sites, including its inert autouse patch. The 15 directly changed test functions expand to 17 existing node IDs. Guards now observe subprocess.run, the real sanitized news worker, or the real provider factory as appropriate. The unknown-mode and price-scope owners already guarded their real workers, so only their obsolete duplicate patches were removed.
- tests/test_daily_update_wrapper.py was owned but did not require edits. All eight existing CLI/status/scope nodes passed unchanged.
- No other agents' source or documentation was edited. No data, credentials, config/.env, or launcher changes; no production reads, provider sessions, App restart, merge or push.

## Verification

All tests used the supplied offline launcher, a clean env, disabled bytecode/plugin autoload, and separate task2 run directories. Commands are reproduced in task2-test-commands.txt. Each run has an adjacent .log and a run-directory junit.xml; the launcher's basetemp is that run directory's pytest/.

| Stage | Exit | Outcome | Evidence stem |
| --- | --- | --- | --- |
| Baseline | 0 | 612 passed | task2-baseline-20260911-01 |
| RED before source edits | 1 | 8 expected absence failures | task2-red-20260911-01 |
| Green | 0 | 620 passed | task2-green-20260911-01 |
| Restore-symbol mutation | 1 | 1 expected failure, 7 passed | task2-mutation-20260911-01 |
| After mutation removal | 0 | 620 passed | task2-restored-green-20260911-01 |

Mutation: restored the original _run_fetch_fred_series definition immediately before _summarize_result in src/service/jobs.py. Only tests/test_execution_wrapper_cleanup.py::test_macro_delegate_is_absent[_run_fetch_fred_series] failed. The definition was removed again with apply_patch before the final run. No mutation is retained.

Positive controls include the entire macro scheduler integration and outcome suites (six named API jobs, honest failed/partial history and status, sanitization, validation and locking), sanitized worker startup/config/timeout tests, prices runtime, job history/telemetry and the unchanged daily CLI tests. No runner or test expectation was weakened to obtain green.

## Node Accounting

- Baseline: 612 nodes. Final: 620 nodes. Net: +8.
- Removed IDs: 18 renamed ingestion IDs, each mapped to a replacement current-entrypoint owner.
- New IDs: those 18 replacement IDs plus 8 absence IDs.
- Deleted behavior cases: none.
- Directly modified existing scheduler IDs: 17. Its autouse fixture patch removal also applies to all 136 scheduler nodes; they all passed.
- task2-node-accounting.json lists every exact removed/new/modified ID, the 18 old-to-new mappings, RED/mutation statuses and unchanged daily nodes.
- task2-baseline-nodes.txt and task2-restored-green-nodes.txt retain the full exact collected IDs, extracted from the verbose pytest runs and cross-checked for expected counts.

## Reference Check And Review

- task2-reference-check.txt records baseline references (git grep against f25b10ca), current src/tests/data_sources references, and all Markdown documentation references.
- Current source has no reference to the eight deleted names. Only the new negative owners refer to them in tests.
- Current production macro callers remain src/service/jobs.py:404,420 and src/service/data_scheduler.py:1241,1249; the shared authority is src/macro_calendar/execution.py:235.
- Markdown hits are the existing C05/C06 audit record and this approved cleanup plan. No live current documentation recommendation needs editing; historical evidence is untouched.
- Reviewed the owned diff: all production changes are the specified deletions, ingestion assertions remain, and worker dispatch/output/timeout/env boundaries are unchanged. git diff --check passed for the owned tracked files.
- Independent whole-slice review and the full backend integration run remain parent responsibilities, not claimed by this worker. Evidence stays in this plan scratch for the parent to archive; no scratch cleanup performed.
