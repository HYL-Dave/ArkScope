# Shared News Bootstrap Target Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the initial news request target 14 days through one authority, without changing saved cursors or provider coverage semantics.

**Architecture:** A shared `timedelta` in `src/news_collection_policy.py` replaces three independent seven-day defaults. Consumers access the module attribute when constructing requests; their date parsing and response handling remain separate.

**Tech Stack:** Python, pytest, existing direct/normalized news adapters.

**Spec:** `docs/design/RUNTIME_AND_RECENT_COLLECTION_POLICY.md`, recent-news target only. Provider entitlement discovery/reporting, C12 client extraction, runtime activation, and SA collection are separate work.

## Global Constraints

- The default request target is **14 calendar days**, per source and ticker without a usable cursor.
- This target is not provider entitlement or proof of observed coverage.
- Existing cursors, mappings, deduplication, and incomplete/unknown IBKR results remain unchanged.
- Offline tests only, with injected providers and disposable databases. No live credentials, production database access, or runtime activation.
- Use the existing integration worktree; do not merge or push before user hand testing.

## Task 1: Converge Bootstrap Request Construction

**Files:**
- Create: `src/news_collection_policy.py`
- Modify: `src/news_providers.py`
- Modify: `src/news_normalized/provider_adapters.py`
- Modify: `src/news_normalized/ibkr_runtime.py`
- Test: `tests/test_news_bootstrap_policy.py`
- Update: `docs/design/RUNTIME_AND_RECENT_COLLECTION_POLICY.md`, `docs/design/PROJECT_PRIORITY_MAP.md`

**Interfaces:**
- Produces `news_collection_policy.INITIAL_NEWS_LOOKBACK: timedelta`.
- Consumed by `_since_to_start`, `_cursor_bounds`, and strict `IBKRRuntimeGateway.fetch_headlines` only when no usable cursor exists.
- Existing public adapter signatures and output structures do not change.

- [x] **Step 1: Behavioral RED.** Inject fake collectors into both direct adapters and both normalized adapters; inject a strict fake IBKR source. Freeze UTC time to `2026-09-14T12:34:56Z`. Fetch a nonempty page through each real adapter and assert its observed start is `2026-08-31` (REST) or `2026-08-31T12:34:56Z` (IBKR):

  ```python
  assert call["start"] == date(2026, 8, 31)
  # Strict IBKR retains timestamp precision:
  assert call["start_dt"] == datetime(2026, 8, 31, 12, 34, 56, tzinfo=timezone.utc)
  ```

  Run `pytest -q tests/test_news_bootstrap_policy.py` in the disposable offline runner. Expected RED: five assertion failures showing September 7 rather than August 31, not collection/import errors.

- [x] **Step 2: Minimal GREEN.** Add the module and replace all three defaults with module access:

  ```python
  from datetime import timedelta
  INITIAL_NEWS_LOOKBACK = timedelta(days=14)
  ```

  ```python
  from src import news_collection_policy
  # REST fallback:
  return today - news_collection_policy.INITIAL_NEWS_LOOKBACK
  # Normalized fallback returns (date, None); IBKR subtracts from UTC now.
  ```

  Remove the now-unused local constants and `timedelta` imports, preserving parsing and the non-strict IBKR fallback. Rerun the same five tests; expect five passes.

- [x] **Step 3: Authority and retained-contract guards.** Replace the shared value after importing the adapters, call all five real adapters, and assert each request uses the replacement:

  ```python
  monkeypatch.setattr(news_collection_policy, "INITIAL_NEWS_LOOKBACK", timedelta(days=3))
  assert call["start"] == date(2026, 9, 11)
  ```

  Also cover malformed/missing cursor fallback, recent and older cursors, exact Massive timestamp retention, source/ticker isolation and writer deduplication. Feed IBKR a saturated seven-day page while requesting fourteen days; consume observed headlines, then assert `IBKRNewsCoverageIncomplete("ibkr_news_window_incomplete")`. Preserve unknown-completion, no-entitled-provider, and non-strict fallback behavior. Run existing direct/normalized writer, adapter, IBKR worker, scheduler and telemetry tests unchanged alongside the new owner.

- [x] **Step 4: Acceptance and evidence.** Freeze product/test sources; run the complete backend suite once, with no concurrent pytest sessions. Retain RED/GREEN command records and JUnit results. Update current-state documents to mark only the shared target complete, with remaining policy work explicit. Review the diff, run `git diff --check`, and commit the bounded change after verification.

## Result

Source commit `8b468771`. RED 5 failed -> GREEN 5 passed; expanded controls
304 passed. Full backend 11,114 passed / 12 unchanged skips, exact 11,126 nodes,
+48/-0. No source/runtime/runner drift or new census findings. Evidence:
`docs/superpowers/evidence/2026-09-14-news-bootstrap-policy/README.md`.
