# PG-Exit S-H2 Financial Cache Cold-Start Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development`
> (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps
> use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the last live PostgreSQL read-through path for `financial_data_cache`; local cache
misses become honest misses and normal fundamentals/Financial Datasets flows refetch into SQLite.

**Status:** IMPLEMENTED 2026-07-03. Runtime commits: `195d78f` removes the local-market PG
fallback/promotion path; `0cbc739` updates in-code authority comments. Focused verification:
`tests/test_sqlite_backend.py` 67 passed, Financial Datasets cache backend-mode tests 5 passed,
and fundamentals cache/stored-mode tests 15 passed (87 focused tests total).

**Architecture:** This is a deletion slice, not a migration. `LocalMarketDatabaseBackend` already
has a local `SqliteBackend` cache; after S-H2 its `get_financial_cache()` reads only that local
cache and never calls `DatabaseBackend.get_financial_cache()` or promotion helper code. Plain
`DatabaseBackend` remains as a legacy/archive PG backend until N9, but the desktop local-market
runtime stops using it for cache misses.

**Tech Stack:** Python, pytest, SQLite `market_data.db`, existing `LocalMarketDatabaseBackend` /
`SqliteBackend` cache APIs.

---

## 1. Decision

S-H2 uses **cold-start, no promote**.

Evidence recorded in `PG_EXIT_S_H_ORPHAN_APP_STATE_AUDIT.md` and `PROJECT_PRIORITY_MAP.md`:

- PG `financial_data_cache` has 24 rows.
- Only 7 rows are unexpired.
- Source is 100% `sec_edgar`.
- Paid Financial Datasets rows in PG: 0.

Therefore a one-time promotion tool would rescue seven free-to-refetch SEC rows and leave behind
extra migration code. That violates the current cleanup principle: do not keep code for data that is
small, free to rebuild, and not a current authority.

## 2. Non-goals

- Do not migrate or promote PG `financial_data_cache`.
- Do not drop the PG table in this slice; N9 batch-1 handles destructive drops after dump/grep.
- Do not change `SqliteBackend.get_financial_cache()` expiry semantics.
- Do not remove `DatabaseBackend.get_financial_cache()` / `set_financial_cache()` yet; plain PG
  backend is legacy/archive until N9.
- Do not change `FinancialDatasetsClient` standalone fallback behavior. Runtime backend mode must
  stay local-primary; standalone CLI/script cleanup belongs to the scripts-retirement/N9 path.
- Do not flip `use_local_market_strict`; S-H2 removes this one fallback regardless of strict mode.

## 3. Target Behavior

Before S-H2:

- `LocalMarketDatabaseBackend.get_financial_cache()` reads local SQLite first.
- On local miss and non-strict mode, it calls PG `financial_data_cache`.
- A PG hit is read-through-promoted into local SQLite.

After S-H2:

- `LocalMarketDatabaseBackend.get_financial_cache()` reads local SQLite only.
- Local miss returns `None` in both strict and non-strict mode.
- Local read failure returns `None` after warning, as today.
- `set_financial_cache()` remains local-only.
- `/fundamentals/{ticker}?stored=true` stays read-only and returns local-cache hit or honest empty.
- Default fundamentals analysis can still refetch SEC/FD and write local cache through
  `set_financial_cache()`.

## 4. File Map

- Modify `tests/test_sqlite_backend.py`
  - Replace the old PG fallback/promotion contract with a no-PG miss contract.
  - Keep the local-hit and local-only-write tests.
- Modify `src/tools/backends/local_market_backend.py`
  - Update module docstring and financial-cache section comment.
  - Remove PG fallback/read-through promotion from `get_financial_cache()`.
  - Delete `_pg_financial_cache_row()`.
- Modify `src/fundamentals/cache.py`
  - Update docstring: generic local-market cache is now local-only too; this helper still enforces
    local-only stored fundamentals and shields against plain PG `DatabaseBackend`.
- Modify `src/market_data_admin.py`
  - Update top-level and schema comments that still describe PG fallback/promotion.
  - Keep carry-over semantics unchanged: full rebuild preserves local cache rows.
- Modify docs after implementation:
  - `docs/design/PG_EXIT_REMAINDER_SCOPING.md`
  - `docs/design/PROJECT_PRIORITY_MAP.md`
  - this plan header/status.

No new source files and no live DB writes.

## 5. Tasks

### Task 1: Pin local-only financial-cache miss

**Files:**
- Modify: `tests/test_sqlite_backend.py`

- [ ] **Step 1: Replace the old fallback test with a RED local-only miss test**

Replace `test_financial_cache_pg_fallback_and_promotion` with:

```python
def test_financial_cache_miss_is_honest_empty_without_pg(market_db, monkeypatch):
    # S-H2: financial_cache is local-only in the desktop runtime. A local miss must
    # not query PG or promote legacy rows, even when strict=False.
    db, _ = market_db
    pg_get = []

    def _pg_called(self, cache_key):
        pg_get.append(cache_key)
        raise AssertionError("financial_cache miss must not fall back to PG")

    monkeypatch.setattr(DatabaseBackend, "get_financial_cache", _pg_called)
    b = _make(db)

    assert b.get_financial_cache("mk_NVDA") is None
    assert pg_get == []
    assert b._market.get_financial_cache("mk_NVDA") is None
```

- [ ] **Step 2: Run the RED test**

Run:

```bash
/home/hyl/.virtualenvs/llm_app/bin/python -m pytest \
  tests/test_sqlite_backend.py::test_financial_cache_miss_is_honest_empty_without_pg -q
```

Expected before implementation: FAIL, because current code calls PG fallback on local miss.

- [ ] **Step 3: Keep the RED test uncommitted**

Do not commit a failing test. If the failure is the expected PG fallback call, proceed to Task 2
and commit test + implementation together after the GREEN verification.

### Task 2: Remove local-market PG fallback and promotion

**Files:**
- Modify: `src/tools/backends/local_market_backend.py`
- Test: `tests/test_sqlite_backend.py`

- [ ] **Step 1: Simplify `get_financial_cache()`**

Change the method to local-only:

```python
    # --- financial_cache (3c-C/S-H2): local-primary (set local-only; get local-only) ---

    def get_financial_cache(self, cache_key: str):
        try:
            return self._market.get_financial_cache(cache_key)
        except Exception as e:
            logger.warning(f"local get_financial_cache failed ({e})")
            return None
```

- [ ] **Step 2: Delete `_pg_financial_cache_row()`**

Remove the method entirely. It exists only for read-through promotion and should have no callers.

- [ ] **Step 3: Update `local_market_backend.py` docstrings/comments**

Replace the financial-cache module docstring block with:

```python
financial_cache (3c-C/S-H2) is LOCAL-PRIMARY, not a mirror:
  - ``set_financial_cache`` writes the LOCAL cache ONLY (never PG);
  - ``get_financial_cache`` reads the LOCAL cache ONLY. A miss is an honest miss; callers that
    need fresh data must refetch from SEC/Financial Datasets and write the local cache.
```

Also update the section comment above the method so it no longer mentions PG fallback or
read-through promotion.

- [ ] **Step 4: Run the focused backend tests**

Run:

```bash
/home/hyl/.virtualenvs/llm_app/bin/python -m pytest \
  tests/test_sqlite_backend.py::test_financial_cache_set_is_local_only \
  tests/test_sqlite_backend.py::test_financial_cache_get_local_first \
  tests/test_sqlite_backend.py::test_financial_cache_miss_is_honest_empty_without_pg \
  tests/test_sqlite_backend.py::test_strict_market_local_miss_is_honest_empty_not_pg \
  -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/tools/backends/local_market_backend.py tests/test_sqlite_backend.py
git commit -m "fix: make financial cache local-only"
```

### Task 3: Update stale cache authority docs in code

**Files:**
- Modify: `src/fundamentals/cache.py`
- Modify: `src/market_data_admin.py`

- [ ] **Step 1: Update `src/fundamentals/cache.py` docstring**

Replace the current description with:

```python
"""Local-only fundamentals cache helpers.

S-H2 makes the generic LocalMarketDatabaseBackend financial-cache path local-only.
This helper still matters because stored fundamentals must also bypass plain
PG DatabaseBackend rows and return an honest miss when no local SQLite cache exists.
"""
```

- [ ] **Step 2: Update `src/market_data_admin.py` comments**

In the top-level domain list, replace:

```python
  - 3c-C FINANCIAL_CACHE — LOCAL-PRIMARY provider/SEC cache (NOT a PG mirror): set
                 writes local-only, get is local-first w/ PG fallback + read-through
                 promotion. Preserved across rebuilds (carry-over), not validated vs
                 PG, untouched by the incremental updater. See SqliteBackend get/set.
```

with:

```python
  - 3c-C/S-H2 FINANCIAL_CACHE — LOCAL-PRIMARY provider/SEC cache (NOT a PG mirror):
                 set writes local-only, get is local-only. Preserved across rebuilds
                 (carry-over), not validated vs PG, untouched by the incremental updater.
                 See SqliteBackend get/set.
```

Also update the schema comment around `FIN_CACHE_SCHEMA` so it no longer says
`local-first with PG fallback + read-through promotion`.

- [ ] **Step 3: Run a stale-text grep**

Run:

```bash
rg -n "financial_cache.*PG fallback|read-through promotion|_pg_financial_cache_row|promotes valid rows" \
  src/tools/backends/local_market_backend.py src/fundamentals/cache.py src/market_data_admin.py
```

Expected: no matches.

- [ ] **Step 4: Commit**

```bash
git add src/fundamentals/cache.py src/market_data_admin.py
git commit -m "docs: update financial cache authority comments"
```

### Task 4: Run consumer sibling tests

**Files:**
- No production changes unless tests reveal a real bug.

This task exists because S-H1 showed that same-module tests are not enough; financial-cache consumers
must be exercised too.

- [ ] **Step 1: Run SQLite backend financial-cache suite**

Run:

```bash
/home/hyl/.virtualenvs/llm_app/bin/python -m pytest \
  tests/test_sqlite_backend.py -q
```

Expected: PASS. Existing unrelated failures in this file are not expected; investigate if any appear.

- [ ] **Step 2: Run Financial Datasets cache-backend tests**

Run:

```bash
/home/hyl/.virtualenvs/llm_app/bin/python -m pytest \
  tests/test_financial_datasets.py::TestCacheBackendMode -q
```

Expected: PASS. These tests prove paid-provider responses still cache locally or to the legacy file
fallback when backend writes fail; S-H2 must not increase paid refetch risk.

- [ ] **Step 3: Run SEC/fundamentals cache tests**

Run:

```bash
/home/hyl/.virtualenvs/llm_app/bin/python -m pytest \
  tests/test_fundamentals_sec_cache.py \
  tests/test_fundamentals_cache.py \
  tests/test_api.py::test_fundamentals_stored_mode_reads_local_cache_without_provider_fetch \
  tests/test_api.py::test_fundamentals_stored_source_path_mapping \
  tests/test_api.py::test_fundamentals_stored_expired_cache_is_honest_empty \
  -q
```

Expected: PASS. These tests prove stored fundamentals remain local-cache-only and default analysis can
still populate local cache.

- [ ] **Step 4: Run grep gate for runtime PG cache fallback**

Run:

```bash
rg -n "super\\(\\)\\.get_financial_cache|DatabaseBackend\\.get_financial_cache|_pg_financial_cache_row" \
  src tests
```

Expected:

- no matches in `src/tools/backends/local_market_backend.py`;
- allowed matches only in tests that deliberately exercise the plain `DatabaseBackend` legacy class,
  if any.

### Task 5: Update PG-exit docs and close S-H2

**Files:**
- Modify: `docs/design/PG_EXIT_REMAINDER_SCOPING.md`
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`
- Modify: `docs/design/PG_EXIT_COMPLETION_PLAN.md` if it still implies financial cache has a live PG fallback.
- Modify: this plan file.

- [x] **Step 1: Mark S-H2 done in `PG_EXIT_REMAINDER_SCOPING.md`**

Update:

- inventory row `financial_data_cache` from pending to local-only/cold-start done;
- S-H sequencing line so remaining S-H work is macro/cal proof and N9 evidence;
- N9 drop list to include PG `financial_data_cache` after final grep/dump;
- domain disposition table so financial cache says local-only; no PG read-through.

- [x] **Step 2: Add a newest-first `PROJECT_PRIORITY_MAP.md` decision log entry**

Record:

- S-H2 cold-start was chosen because PG table was 24 rows / 7 unexpired / 0 paid FD;
- runtime fallback/promotion removed;
- focused tests passed;
- next P0-B line is N9 batch-1 evidence/plan with S-H3 empty macro/cal proof folded in.

- [x] **Step 3: Update this plan header**

Change status from plan to implemented. Include the focused test count and commit hash.

- [x] **Step 4: Run docs grep**

Run:

```bash
rg -n "financial_cache.*PG fallback|financial_cache.*read-through|get_financial_cache.*falls back|promotion" \
  docs/design/PG_EXIT_REMAINDER_SCOPING.md docs/design/PROJECT_PRIORITY_MAP.md \
  docs/design/PG_EXIT_COMPLETION_PLAN.md docs/design/PG_EXIT_S_H2_FINANCIAL_CACHE_COLD_START_PLAN.md
```

Expected: no stale claims that runtime financial cache falls back to PG. Historical entries may mention
the old behavior only if explicitly dated as historical provenance.

Observed at implementation closeout: matches are confined to this implemented plan's before/after
instructions, rollback note, and dated decision-log/history/proof entries. No active runtime
authority doc describes financial-cache PG fallback as current behavior.

- [x] **Step 5: Commit**

```bash
git add docs/design/PG_EXIT_REMAINDER_SCOPING.md docs/design/PROJECT_PRIORITY_MAP.md \
  docs/design/PG_EXIT_COMPLETION_PLAN.md docs/design/PG_EXIT_S_H2_FINANCIAL_CACHE_COLD_START_PLAN.md
git commit -m "docs: close S-H2 financial cache cold-start"
```

## 6. Review Gate

Before merge, reviewer should verify:

- `LocalMarketDatabaseBackend.get_financial_cache()` has no PG call path.
- `_pg_financial_cache_row()` is gone.
- Local hits still work and local misses are honest `None`.
- `set_financial_cache()` remains local-only.
- Financial Datasets backend mode still avoids paid re-fetch loops by caching locally or file-fallback
  on backend write failure.
- Stored fundamentals remains local-cache-only and never fetches providers.
- Stale docs/header comments do not describe PG fallback as active runtime behavior.

Recommended focused gate:

```bash
/home/hyl/.virtualenvs/llm_app/bin/python -m pytest \
  tests/test_sqlite_backend.py \
  tests/test_financial_datasets.py::TestCacheBackendMode \
  tests/test_fundamentals_sec_cache.py \
  tests/test_fundamentals_cache.py \
  tests/test_api.py::test_fundamentals_stored_mode_reads_local_cache_without_provider_fetch \
  tests/test_api.py::test_fundamentals_stored_source_path_mapping \
  tests/test_api.py::test_fundamentals_stored_expired_cache_is_honest_empty \
  -q
```

Expected: PASS.

## 7. Rollback

No live data is migrated in S-H2. Rollback is a code revert before N9:

- restore `LocalMarketDatabaseBackend.get_financial_cache()` fallback/promotion behavior;
- restore docs if needed.

After N9 drops PG `financial_data_cache`, rollback to PG fallback is no longer meaningful.
