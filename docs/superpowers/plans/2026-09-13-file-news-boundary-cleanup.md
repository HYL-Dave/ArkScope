# Retained Raw-News Boundary Cleanup

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Execute RED-first and stop at a verified reviewable commit.

**Goal:** Complete the bounded C10 raw-file cleanup without changing current prices, SEC facts or SA behavior.

**Architecture:** FileBackend remains a raw-news reader, not a nominal market backend. Current LocalMarketBackend and SACaptureBackend stop constructing its unused instance; their real SQLite/SA authorities remain unchanged.

**Tech Stack:** Python, pytest, pandas, SQLite; no dependency changes.

**Spec:** `docs/superpowers/evidence/2026-09-10-pre-release-cleanup-audit/README.md`, C10. Latest user explicitly requests continuing verified cleanup, not retired compatibility stubs.

## Constraints

- Work only in `/tmp/arkscope-research-output-boundary`; never master/other worktrees.
- No provider calls, private configuration/production DB reads, actual data deletion, runtime switch, push or merge.
- Use current integration plan's offline runner and disposable fixture stores. Keep this task's notes/results in that same plan workspace.
- Preserve DataAccessLayer.base_path for its remaining capabilities; remove only the unused downstream constructor argument.
- Preserve LocalMarketBackend.query_fundamentals and all shared interfaces/current consumers. Broader fundamentals convergence is not this task.
- Preserve FileBackend's raw-news parsing, deduplication, filter and ticker listing exactly. No replacement wrappers or aliases.

## Task C10

**Product files:**
- `src/tools/backends/file_backend.py`: remove unconditional empty query_prices/query_fundamentals and obsolete capability claims; retain raw-news reader.
- `src/tools/backends/local_market_backend.py`: remove FileBackend import/construction, base_path argument and now-unused imports; keep real market methods.
- `src/tools/backends/sa_capture_backend.py`: remove base_path argument and parent forwarding only. Keep Path where still used.
- `src/tools/data_access.py`: remove base_path keyword in SACaptureBackend construction only.

**Tests to modify:**
- `tests/test_data_access.py`: replace false FileBackend/DataBackend conformance claim, add real fixture raw-news positive control, update exact runtime module inventory.
- `tests/test_eir006_retired_data_boundaries.py`: stop demanding retired-empty docstrings; keep existing source/price authority assertions.
- Mechanical constructor collateral only: `tests/test_detailed_financials.py`, `tests/test_stored_sec_projection.py`, `tests/test_active_universe.py`, `tests/test_sa_local_readers.py`, `tests/test_sqlite_backend.py`, `tests/test_security_lifecycle_terminal_workflow.py`, `tests/test_sa_capture_backend.py`, `tests/test_sa_reconciliation_native_host.py`.

**Interfaces:** LocalMarketBackend(*, market_db); SACaptureBackend(*, sa_db, market_db); FileBackend(base_path) and DataAccessLayer(base_path, backend) retain their current useful arguments.

- [ ] Collect scoped baseline before edits. No existing semantic assertion may disappear merely to make cleanup pass.
- [ ] Add RED owners in test_data_access.py:
  ```python
  assert not hasattr(FileBackend, "query_prices")
  assert not hasattr(FileBackend, "query_fundamentals")
  assert not isinstance(file_backend, DataBackend)
  ```
  Separate positive owner writes a tiny current-month parquet to a tmp_path raw-news provider directory, calls FileBackend.query_news, and asserts exact retained title/ticker/source. Do not use the main repo's news files or accept an empty result.
- [ ] Change the subprocess module-graph owner to exclude file_backend. RED must fail on its loaded-module assertion before removing the unused construction.
- [ ] Run these owners and save expected failing IDs before product edits. Expected failures: two present empty methods, false nominal conformance and unwanted module load; raw-news positive control must pass.
- [ ] Remove only the product surfaces above and adjust exact constructor keyword collateral. Re-scan all SACaptureBackend/LocalMarketBackend callers so no keyword remains hidden in a fixture.
- [ ] Run focused regressions with the current-plan runner:
  ```text
  backend -q tests/test_data_access.py tests/test_eir006_retired_data_boundaries.py tests/test_sqlite_backend.py tests/test_detailed_financials.py tests/test_stored_sec_projection.py tests/test_fundamentals_sec_cache.py tests/test_active_universe.py tests/test_sa_local_readers.py tests/test_security_lifecycle_terminal_workflow.py tests/test_sa_capture_backend.py tests/test_sa_reconciliation_native_host.py tests/test_sa_article_reconciliation_backend.py tests/test_sa_tools.py
  ```
  Require zero failures; report exact collected/pass/skip totals rather than assuming them.
- [ ] Self-review source diff and retained-owner hashes, report command receipts and any new dependency. Controller handles commit and independent review. Do not start C11 or mutate a reviewed prior task.

This is not C11 news-writer convergence, C12 collector CLI retirement, stored-data disposition or completion of SEC's remaining workflows.
