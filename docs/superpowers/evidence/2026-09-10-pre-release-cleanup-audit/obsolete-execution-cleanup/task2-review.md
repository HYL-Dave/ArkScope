# Task 2 Independent Spec/Quality Review

**Result: PASS. No introduced spec or quality findings in the seven commit files.**

Reviewed Task 2 of `docs/superpowers/plans/2026-09-11-obsolete-execution-cleanup.md` and audit C05/C06 at `docs/superpowers/evidence/2026-09-10-pre-release-cleanup-audit/README.md:179` and `:180`.

- Worktree: `/tmp/arkscope-listing-sec-macro-convergence`.
- Base: `f25b10ca2ce55401460c6296205c9b2c42a18e31`; head: `36dac28df44ee6edf98f48d3d10466daeaf06f37`.
- Scope: `src/service/jobs.py`, `src/service/data_scheduler.py`, `src/daily_update.py`, `tests/test_fred_ingestion.py`, `tests/test_finnhub_ingestion.py`, `tests/test_data_scheduler.py`, `tests/test_execution_wrapper_cleanup.py`. Other worktree diffs and Tasks 1/3 were not reviewed.
- Scoped checkout files matched the commit before and after testing. Commit `git diff --check` passed. Scoped binary diff SHA-256: `0d81b512bff0e7ce7da001f728139d61acd0bcfbcfc2f487d6907580f195b122`.

## Spec And Quality Evidence

- **Deletion boundary:** At the base, the six delegates at `src/service/jobs.py:515` onward have only ingestion-test callers. The generic helpers at base `src/service/data_scheduler.py:637` and `src/daily_update.py:69` have no production callers; scheduler references are monkeypatches. The production diff deletes precisely these eight definitions and daily_update's newly unused `subprocess` import. No registry, active function body, or replacement alias was changed or added.
- **Real macro ownership:** All six job definitions remain, including the non-recurring economic backfill. `jobs.run_job` still calls shared execution directly at `src/service/jobs.py:420`; recurring sources still supply their canonical job, DAL, incremental params and writer lease at `src/service/data_scheduler.py:1249`. Existing failed/partial normalization, sanitized exceptions and canonical telemetry remain unchanged. The real execution tests and six-job API outcome controls passed.
- **Transferred contracts:** All 18 cases retain their original ingestion fakes, parameters, expected dates/symbols/limits/full-refresh results, and `pytest.raises` types/message matches. Only owner names and calls/imports move to `execute_macro_job`: `tests/test_fred_ingestion.py:695`; `tests/test_finnhub_ingestion.py:788`, `:833`, `:879`, `:928`. No behavioral case was deleted. Existing `task2-node-accounting.json` supplies the exact 18 old/new mappings, 17 modified scheduler node IDs and eight added absence IDs, consistent with the diff.
- **Real worker ownership:** `src/service/data_scheduler.py:761` retains sanitized JSON dispatch, timeout handling and output filtering; `:930` retains the prices worker. Their subprocess/environment behavior is unchanged, and the scheduler's `subprocess` import remains necessary. Daily execution still calls `run_source(..., trigger_source="cli", tickers=tickers)` at `src/daily_update.py:473`. Existing dispatch, timeout, configuration-order/store, error sanitization and daily CLI controls passed.
- **No test weakening:** Removed scheduler patches targeted an inert helper. Replacement guards observe actual `subprocess.run`, the sanitized worker, or the provider factory. Unknown-mode and price-scope tests retain their real-worker owners at `tests/test_data_scheduler.py:1253` and `:2297`. Eight explicit absence cases remain at `tests/test_execution_wrapper_cleanup.py:20`, `:24`, `:28`; all passed. No product mutation was performed for this review.
- **Imports/docs:** No newly unused import was left by these deletions. `os` and `json` at `src/daily_update.py:40` and `:42` were already unused at the base. Its old incremental/collector CLI prose at `:33` is also pre-existing, not a Task 2 regression. Searches found no current source or live Markdown recommendation using the removed helpers; dated audit/plan references are provenance, not current entrypoints.

## Independent Test Results

All runs used only `.superpowers/sdd/2026-09-11-obsolete-execution-cleanup/offline_pytest.py` with `/home/hyl/.virtualenvs/llm_app/bin/python -B`, `env -i`, and:

```text
PATH=/home/hyl/.virtualenvs/llm_app/bin:/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin
PYTHONDONTWRITEBYTECODE=1
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
ARKSCOPE_OFFLINE_TEST_WORKSPACE=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-11-obsolete-execution-cleanup/task2-review
```

| Run | Actual result | JUnit XML relative to this report |
| --- | --- | --- |
| Focused: complete fred/finnhub ingestion, data_scheduler, daily_update_wrapper, execution_wrapper_cleanup, macro_scheduler_integration and macro_scheduler_outcomes test modules | Exit 0; **504 passed in 23.34s**, no failures/skips | `task2-review/focused.xml` |
| Worker controls: complete `tests/test_prices_runtime.py` plus four synthetic normalized-worker cases listed below | Exit 0; **14 passed in 0.69s**, no failures/skips | `task2-review/worker-controls.xml` |

Additional normalized-worker selectors under `tests/test_normalized_ibkr_worker.py`:
- `test_ibkr_worker_prints_sanitized_json_without_provider_payload`
- `test_ibkr_worker_suppresses_provider_stderr_and_logging`
- `test_worker_applies_provider_config_before_gateway_construction`
- `test_apply_provider_config_passes_a_store`

**Total: 518 independently passing tests.** Collector/provider execution and the real worker-startup subprocess test were not run. Tests used synthetic providers/worker replacements and temporary state; no production data, config/.env, credentials or provider sessions were accessed. This is a bounded Task 2 review, not a full-backend or whole-slice approval. No product files were changed.
