# Obsolete Execution Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Execute the approved cleanup in this isolated worktree with RED-first owners and independent review.

**Goal:** Remove the abandoned fixed-two-call investigation pipeline, test-only execution wrappers, spent operator CLIs and independent monitor scheduler without removing current behavior or data.

**Architecture:** Keep the adaptive investigation agent as the only investigation orchestrator. Its single-consumer asynchronous source-read helper belongs in that agent. Existing journal option decoding stays beside its retained reader until the separately owned shared-journal cleanup. Current macro execution, sanitized workers and monitor engine remain the real entrypoints.

**Tech Stack:** Python, asyncio, SQLite fixtures, pytest, repository census.

**Spec:** `docs/superpowers/specs/2026-09-10-sec-research-substrate-design.md` sections 3/9/11; `docs/superpowers/evidence/2026-09-10-pre-release-cleanup-audit/README.md` C04/C05/C06/C14/C16 and `sec-schema-ownership.md`.

## Global Constraints

- Base `f25b10ca`, branch `codex/listing-sec-macro-convergence`, existing linked worktree only.
- Source cleanup approval is already given. No production read/write, backup, schema disposal, provider session, merge, push or App restart in this plan.
- Use the completed retention manifest, not another database read. Seven absent old-web tables do not make populated shared evidence disposable.
- Preserve active API-key/OAuth dispatch, captured model/auth/effort, cancellation, source gaps, current approval/reversal/history, Former removals, prices/news/SA, credentials and schedules.
- No forwarding alias, retired handler, fabricated success, new migration framework or dependency change.
- Tests use temporary stores and synthetic providers. Archive RED/green/test-node accounting; remove only this plan's scratch after review.
- New SEC research tools, shared review/store extraction and actual data disposition are not claimed complete by this slice.

## Task 1: Remove The Fixed Investigation Orchestrator

**Files:**
- Modify `src/lifecycle_investigation/agent.py`, `src/lifecycle_web_store.py`.
- Delete `src/security_lifecycle_web_pipeline.py`, `tests/test_security_lifecycle_web_pipeline.py`.
- Modify `tests/test_lifecycle_web_store.py`, `tests/test_lifecycle_web_review.py`, `tests/test_lifecycle_source_read_report.py`, `tests/test_lifecycle_web_instrument_scope.py`.
- Create `tests/test_lifecycle_investigation_execution_cleanup.py` for absence and current-agent behavior owners.

**Interfaces:** `run_agent(...)` remains unchanged. Move `_read_one(reader, url, control, pool)` byte-for-byte into its only current consumer, preserving stop propagation and worker join. The retained journal's `WebInvestigationOptions` decoding dataclass moves into `lifecycle_web_store`, with identical fields and validation; no default-execution factory survives.

- [x] Baseline: run pipeline, current-agent, source-report, instrument-scope and retained-journal tests. Collect full node IDs before deletion.
- [x] RED: add the negative owner below and an AST import owner prohibiting the old pipeline from current source:

```python
def test_fixed_investigation_pipeline_is_physically_absent():
    assert not (ROOT / "src/security_lifecycle_web_pipeline.py").exists()
```

  Expected RED: the file exists and the current agent/store still import it.
- [x] Add current-agent controls using injected synthetic models/readers: all four transports keep exact selection/credential/effort; a failed source produces a typed gap and measured diagnostics without retry; a pending source read stops and joins on cancellation; large/Unicode captures remain whole with traceable passages; context-limit rejection neither clips nor retries. Keep per-instrument grounding checks on current finding validation. Use actual `run_agent`, not a copied old orchestrator. Review added two missing transfers: real-agent pending cancellation and successful finding with unread supplement.
- [x] Move only the two retained primitives and delete the old pipeline/result/error/defaults. Replace test fixture imports with the retained journal owner. Keep journal report/acceptance tests that have real retained readers, creating their measured report through the actual source reader rather than the removed pipeline. Delete only exclusively abandoned orchestration assertions; name replacement/current owners in evidence.
- [x] Run focused tests, then complete lifecycle/current approval/identity/provider suites. Baseline105P; corrected RED5F/9P; final focused102P. Broad2611P/7missing-Node failures; corrected complete disposition/agent/report files71P. Join/gap/synchronous-read mutants kill1/4/2 named cases; initial real-file/import RED protects removal. No mutation is committed. Whole backend integration remains below.
- [x] Review and commit the self-contained source change: `38319f16`, scoped re-review9P and no remaining findings.

## Task 2: Remove Test-Only Macro And Subprocess Wrappers

**Files:** `src/service/jobs.py`, `src/service/data_scheduler.py`, `src/daily_update.py`; `tests/test_fred_ingestion.py`, `tests/test_finnhub_ingestion.py`, `tests/test_data_scheduler.py`, `tests/test_daily_update_wrapper.py`; new `tests/test_execution_wrapper_cleanup.py`. Positive controls: `tests/test_macro_scheduler_integration.py`, current worker environment/timeout tests.

**Interfaces:** Existing `execute_macro_job(job_name, dal, params, *, writer_lease=None)` and `jobs.run_job` remain current; all six macro job names and their truthful failed/partial outcomes survive. Current daily update and sanitized worker dispatch are unchanged.

- [x] Recheck callers and collect baseline nodes. Add RED absence owners for six `_run_fetch_*` delegates, scheduler `_run_subprocess` and daily `run_command`:

```python
@pytest.mark.parametrize("name", MACRO_DELEGATES)
def test_macro_delegate_is_absent(name):
    assert not hasattr(jobs, name)
```

  Expected RED: each named symbol exists.
- [x] Delete only those definitions and newly unused imports. Move old ingestion parameter/validation tests to the real shared entrypoint:

```python
result = execute_macro_job("fetch_fred_release_dates", dal="dal-x", params=params)
```

  Keep all existing expected ingestion arguments and errors. Remove obsolete monkeypatches of `_run_subprocess`; patch real workers only where the test's behavior needs it.
- [x] Verify six real job entrypoints, partial/error telemetry, argument validation, worker environment and timeout tests. Baseline612P, RED8F, final620P; restore-symbol mutation1F/7P, restored620P. Eighteen node renames preserve assertions; eight new absence nodes; no deleted behavior case.
- [x] Review and commit only this task's files: `36dac28d`; independent review518P, no findings.

## Task 3: Remove Spent Operators And Duplicate Monitoring Scheduler

**Files:** delete `src/audit/sa_article_reconciliation.py`, `src/audit/universe_retirement.py`, `src/audit/ibkr_news_catchup_audit.py`, `src/monitor/scheduler.py`; inspect/delete an empty `src/audit/__init__.py` only after confirming no remaining members. Delete exclusive `tests/test_universe_retirement_audit.py`, `tests/test_ibkr_news_catchup_audit.py`; modify `tests/test_monitor.py`, `tests/test_legacy_agent_surface_retirement.py`; create `tests/test_spent_operator_cleanup.py`. Update only current entrypoint documentation that advertises these commands; do not rewrite archived plans/receipts.

**Interfaces:** Preserve the different, live `src/sa_article_reconciliation.py`, monitor engine/tools, `src/service/jobs.py` monitor branch, current universe/Former membership and IBKR news catch-up behavior. Task 3 must not edit Task 2's production files.

- [x] Verify module/CLI entrypoints and collect baseline node IDs without executing any operator against real stores.
- [x] RED: four physical absence tests below; change the old engine-and-scheduler preservation owner to engine-and-current-job behavior before deletion:

```python
@pytest.mark.parametrize("relative", SPENT_MODULES)
def test_spent_module_is_absent(relative):
    assert not (ROOT / relative).exists()
```

  Expected RED: four files still exist. Positive control: monitor job runs an injected engine and reports its actual result; real SA reconciliation imports/runs on fixtures.
- [x] Delete only the four modules and their exclusive tests. Keep all non-scheduler monitor tests, current history/evidence and runbooks explicitly marked historical. Current component list in DESKTOP_APP_VISION_DRAFT is updated; no current command recipe found. No private configuration read.
- [x] Run monitor/tools/jobs, SA reconciliation, active universe/Former and IBKR news controls. Baseline281P/final270P, one unchanged config fixture explicitly left to parent full run; four restored-original-file mutations fail four absence owners. Eighteen removed/seven new nodes; all36non-scheduler monitor nodes retained.
- [x] Review and commit only this task's files: `2f80f452`; independent review270P/one explicit deselection, no findings.

## Integration And Evidence

- [x] Parent reviews disjoint patches and all named collateral; record any rulings and test count changes. Task accounting is -3/+8/-11; verify the resulting -6 against complete collection/execution below.
- [x] Fresh full backend run with isolated temp stores, clean environment and provider/production access rejection: 7,966 passed / 12 skipped in745.20s. Exact7,978 collection/execution IDs; baseline7,984 minus59removed plus53added. Original12skips unchanged; tested runtime/test diff unchanged since run start.
- [x] Re-run mechanical census against the prior reviewed baseline. No new candidates, dependency metadata or untracked-name changes. Nine exact file reductions; twelve relocated uncertainty IDs each matched unchanged source lines and prior uncertainty records. Raw exit2/review_required remains; no baseline rewrite or data deletion.
- [x] Independent whole-slice spec/quality review: no findings, independently reconciled full identities/accounting and retained entrypoints. Archive publication/hash verification remains parent-owned below.
- [x] Update audit dispositions and priority-map checkpoint, accurately retaining unresolved shared-reader/schema cleanup. Archived112 indexed artifacts with full source/archive hash readback; independent integration review is clean. Only this plan's scratch was removed after verification. Branch remains local; App and master untouched. Evidence: `docs/superpowers/evidence/2026-09-10-pre-release-cleanup-audit/obsolete-execution-cleanup/README.md`.
