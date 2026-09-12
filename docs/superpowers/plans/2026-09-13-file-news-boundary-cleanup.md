# Orphan File Backend Cleanup

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Execute RED-first and stop at a verified reviewable commit.

**Goal:** Remove the unused FileBackend and its unused construction without changing current prices, news, SEC facts or SA behavior.

**Architecture:** FileBackend has no product consumer after removing its unused construction. Delete the whole module, not only its empty methods. Current LocalMarketBackend and SACaptureBackend retain their real SQLite/SA authorities. Retained data is not deleted.

**Tech Stack:** Python, pytest, pandas, SQLite; no dependency changes.

**Spec:** `docs/superpowers/evidence/2026-09-10-pre-release-cleanup-audit/README.md`, C10. Latest user explicitly requests continuing verified cleanup, not retired compatibility stubs.

## Constraints

- Work only in `/tmp/arkscope-research-output-boundary`; never master/other worktrees.
- No provider calls, private configuration/production DB reads, actual data deletion, runtime switch, push or merge.
- Use current integration plan's offline runner and disposable fixture stores. Keep this task's notes/results in that same plan workspace.
- Preserve DataAccessLayer.base_path for its remaining capabilities; remove only the unused downstream constructor argument.
- Preserve LocalMarketBackend.query_fundamentals and all shared interfaces/current consumers. Broader fundamentals convergence is not this task.
- Preserve actual current database news parsing/projection/readers. No replacement wrappers or aliases for FileBackend. Raw parquet data is untouched.

## Corrected Consumer Inventory

The initial plan incorrectly assumed a live raw-file import/repair consumer.
Controller full-source scan finds none: only FileBackend's definition, unused
LocalMarketBackend construction, tests and two prose mentions exist. Its entire
raw-reader implementation becomes orphaned after the construction is removed.
Keeping it would contradict the user's cleanup policy. The initial 4F/2P RED
and intermediate raw-parquet test checks remain historical receipts; they are
not justification to retain dead code. Add a new physical/import-absence RED
before deleting the module. No stored-data disposition is implied.

Missing mechanical collateral `tests/test_sa_routing.py` is also admitted:
remove its obsolete stub constructor argument and assert the still-supported
path on DataAccessLayer._base instead of dropping that useful assertion.

## Task C10

**Product files:**
- Delete `src/tools/backends/file_backend.py` after the new absence RED.
- `src/tools/backends/local_market_backend.py`: remove FileBackend import/construction, base_path argument and now-unused imports; keep real market methods.
- `src/tools/backends/sa_capture_backend.py`: remove base_path argument and parent forwarding only. Keep Path where still used.
- `src/tools/data_access.py`: remove base_path keyword in SACaptureBackend construction only.
- `src/tools/news_tools.py`, `src/service/job_runs_store.py`: remove stale FileBackend prose only, no behavior change.

**Tests to modify:**
- `tests/test_data_access.py`: remove obsolete FileBackend import/fixture/conformance claim; update exact runtime module inventory. Supersede the unshipped raw-reader tests explicitly in test accounting.
- `tests/test_abandoned_surface_cleanup.py`: add FileBackend physical/import-absence owners before deletion.
- `tests/test_legacy_iv_retirement_boundaries.py`: remove the deleted module from both mandatory source-file lists, retain all remaining IV assertions.
- `tests/test_eir006_retired_data_boundaries.py`: stop demanding retired-empty docstrings; keep existing source/price authority assertions.
- Mechanical constructor collateral only: `tests/test_detailed_financials.py`, `tests/test_stored_sec_projection.py`, `tests/test_active_universe.py`, `tests/test_sa_local_readers.py`, `tests/test_sqlite_backend.py`, `tests/test_security_lifecycle_terminal_workflow.py`, `tests/test_sa_capture_backend.py`, `tests/test_sa_reconciliation_native_host.py`, `tests/test_sa_routing.py`.
- `tests/test_sec_transport_cancellation.py`: cosmetic removal of extra EOF blank only, as requested by Task2 review.

**Interfaces:** LocalMarketBackend(*, market_db); SACaptureBackend(*, sa_db, market_db); DataAccessLayer(base_path, backend) retains its current useful arguments. No FileBackend interface remains.

- [x] Collect scoped baseline before edits. No existing semantic assertion may disappear merely to make cleanup pass.
- [x] Add corrected RED owners before module deletion:
  ```python
  assert not (ROOT / "src/tools/backends/file_backend.py").exists()
  assert importlib.util.find_spec("src.tools.backends.file_backend") is None
  ```
  Use existing real SQLite news fixtures as positive controls and require
  nonempty exact query results. Do not read main repo data or accept a vacuous
  empty-reader assertion. Retained price/facts/SA controls remain unchanged.
- [x] Change the subprocess module-graph owner to exclude file_backend. RED must fail on its loaded-module assertion before removing the unused construction.
- [x] Preserve the initial four missing-behavior failures as historical evidence. Run the corrected absence owners before full module deletion: physical file and import remain, so both must fail. Current SQLite news controls must pass.
- [x] Remove only the product surfaces above and adjust exact constructor keyword collateral. Re-scan all SACaptureBackend/LocalMarketBackend callers so no keyword remains hidden in a fixture.
- [x] Run focused regressions with the current-plan runner:
  ```text
  backend -q tests/test_data_access.py tests/test_eir006_retired_data_boundaries.py tests/test_sqlite_backend.py tests/test_detailed_financials.py tests/test_stored_sec_projection.py tests/test_fundamentals_sec_cache.py tests/test_active_universe.py tests/test_sa_local_readers.py tests/test_security_lifecycle_terminal_workflow.py tests/test_sa_capture_backend.py tests/test_sa_reconciliation_native_host.py tests/test_sa_article_reconciliation_backend.py tests/test_sa_tools.py
  ```
  Also run test_sa_routing.py, test_abandoned_surface_cleanup.py and
  test_legacy_iv_retirement_boundaries.py. Require zero failures; report exact
  collected/pass/skip totals rather than assuming them.
- [x] Self-review source diff and retained-owner hashes, report command receipts and any new dependency. Controller handles commit and independent review. Do not start C11 or mutate a reviewed prior task.

Implementation checkpoint: `885c2a2d`. Worker350P/1S; controller467P/1S. Both
initial RED4F/2P and corrected absence RED2F/2P are retained. The revised routing
baseline failed two obsolete stub-path assertions before their approved move to
DAL._base; it is not reported as a passing baseline.

- [x] Preserve the implementation in a scoped commit.
- [x] Independent C10 review: no findings,32 focused tests passed; all reviewer sessions ended.
- [ ] Whole backend verification on frozen product/test source.

This is not C11 news-writer convergence, C12 collector CLI retirement, stored-data disposition or completion of SEC's remaining workflows.
