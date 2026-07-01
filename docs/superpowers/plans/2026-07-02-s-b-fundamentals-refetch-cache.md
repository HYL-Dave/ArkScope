# S-B Fundamentals Refetch/Cache Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the fundamentals domain's runtime PostgreSQL dependency by retiring the frozen `fundamentals` mirror table as an authority, serving read-only stored fundamentals from local `financial_cache`, and stopping fundamentals from the PG mirror/update path.

**Architecture:** The old `fundamentals` table becomes a legacy orphan for N9 drop; S-B must not migrate or refresh it. The read-only `/fundamentals/{ticker}?stored=true` path reads only positive local SEC cache rows from `financial_cache` and returns honest empty when no cache exists; the default analysis path still performs SEC EDGAR / Financial Datasets fallback and writes local cache. Scheduler and market-data update routes stop requesting the `fundamentals` mirror domain after news PG exit, while prices and IV remain unchanged.

**Tech Stack:** Python 3, FastAPI route functions, SQLite local `market_data.db`, existing `LocalMarketDatabaseBackend`, existing `financial_cache`, pytest, existing scheduler and market-data status routes.

---

## Scope And Non-Goals

This slice is a runtime cutover, not a data migration. It intentionally does not copy the 130 PG fundamentals rows, does not add a new fundamentals collector, and does not make provider calls from the read-only UI tab.

The authoritative future for fundamentals is:

1. `get_fundamentals_analysis()` may fetch SEC EDGAR / Financial Datasets on demand.
2. Successful SEC analysis writes a local `financial_cache` row keyed as `fundamentals_analysis:sec_edgar:{TICKER}:annual:v1`.
3. `/fundamentals/{ticker}?stored=true` reads that local cache row only.
4. The frozen `fundamentals` table remains physically present until N9, but S-B code must stop treating it as current data.

## File Map

- Create: `src/fundamentals/cache.py`
  - Owns cache-key construction and local-only reads of cached `FundamentalsResult` payloads.
  - Avoids `LocalMarketDatabaseBackend.get_financial_cache()` because that method can still PG-fallback for generic cache migration.
- Create: `tests/test_fundamentals_cache.py`
  - Pins cache-key shape, local-only read behavior, negative-cache handling, stale payload handling, and "do not call PG fallback" behavior.
- Modify: `src/tools/analysis_tools.py`
  - Reuse the new local-only helper for the SEC cache hit/negative-cache branch.
  - Keep live SEC/FD fallback and cache writes unchanged.
- Modify: `src/api/routes/fundamentals.py`
  - `stored=true` uses the new local-only cache helper instead of `dal.get_fundamentals()`.
  - Route text stops saying the stored path can PG-fallback.
- Modify: `src/tools/backends/local_market_backend.py`
  - `query_fundamentals()` stops reading the frozen local mirror table and stops falling back to PG.
  - Generic `get_financial_cache()` remains unchanged for non-S-B callers; the new helper bypasses its PG fallback only for fundamentals analysis cache reads.
- Modify: `tests/test_sqlite_backend.py`
  - Replace local/PG fallback expectations for fundamentals with retired-table / honest-empty expectations.
  - Keep direct `SqliteBackend.query_fundamentals()` tests unchanged; that low-level table reader still exists for legacy inspection until N9.
- Modify: `tests/test_api.py`
  - Stored route tests now assert local cache read, no provider fetch, and `source_path` semantics.
- Modify: `src/service/data_scheduler.py`
  - After news PG exit, `_local_refresh()` requests only `("prices", "iv")`.
- Modify: `src/api/routes/market_data.py`
  - Manual `/market-data/update` after news PG exit requests only `("prices", "iv")`.
  - Status/update docstrings no longer claim fundamentals is still mirror-updated.
- Modify: `tests/test_data_scheduler.py`
  - Post-exit refresh tests expect `("prices", "iv")`.
- Modify: tests around market-data status/update if present in `tests/test_api.py` or `tests/test_market_data_admin.py`
  - Pin that fundamentals is disabled/skipped when not requested.
- Modify: `docs/design/PG_EXIT_REMAINDER_SCOPING.md`
  - Mark S-B implemented after code is verified; explain that `fundamentals` is an N9 orphan and `financial_cache` is the local authority for read-only stored fundamentals.

## Task 1: Add Local-Only Fundamentals Cache Helper

**Files:**
- Create: `src/fundamentals/cache.py`
- Create: `src/fundamentals/__init__.py`
- Create: `tests/test_fundamentals_cache.py`

- [ ] **Step 1: Write failing tests for cache key and local-only reads**

Create `tests/test_fundamentals_cache.py`:

```python
from __future__ import annotations

from src.fundamentals.cache import (
    fundamentals_analysis_cache_key,
    read_cached_sec_fundamentals,
)
from src.tools.schemas import FundamentalsResult


class _LocalStore:
    def __init__(self, rows):
        self.rows = dict(rows)
        self.calls = []

    def get_financial_cache(self, cache_key):
        self.calls.append(cache_key)
        return self.rows.get(cache_key)


class _LocalMarketBackend:
    def __init__(self, rows):
        self._market = _LocalStore(rows)
        self.pg_calls = []

    def get_financial_cache(self, cache_key):
        self.pg_calls.append(cache_key)
        raise AssertionError("generic LocalMarketDatabaseBackend cache getter must not run")


def test_fundamentals_analysis_cache_key_is_stable():
    assert (
        fundamentals_analysis_cache_key("aapl", "annual")
        == "fundamentals_analysis:sec_edgar:AAPL:annual:v1"
    )
    assert (
        fundamentals_analysis_cache_key(" nvda ", "quarterly")
        == "fundamentals_analysis:sec_edgar:NVDA:quarterly:v1"
    )


def test_read_cached_sec_fundamentals_uses_local_market_store_without_pg_fallback():
    key = fundamentals_analysis_cache_key("AAPL")
    backend = _LocalMarketBackend({
        key: FundamentalsResult(
            ticker="AAPL",
            data_source="sec_edgar",
            snapshot_date="2025-12-31",
            roe=0.21,
        ).model_dump()
    })

    result, negative = read_cached_sec_fundamentals(backend, "AAPL")

    assert negative is False
    assert result is not None
    assert result.ticker == "AAPL"
    assert result.data_source == "sec_edgar"
    assert result.roe == 0.21
    assert backend._market.calls == [key]
    assert backend.pg_calls == []


def test_read_cached_sec_fundamentals_returns_empty_on_miss():
    result, negative = read_cached_sec_fundamentals(_LocalMarketBackend({}), "MSFT")
    assert result is None
    assert negative is False


def test_read_cached_sec_fundamentals_recognizes_negative_cache():
    key = fundamentals_analysis_cache_key("VISN")
    result, negative = read_cached_sec_fundamentals(
        _LocalMarketBackend({key: {"_negative": True}}),
        "VISN",
    )
    assert result is None
    assert negative is True


def test_read_cached_sec_fundamentals_ignores_incompatible_payload():
    key = fundamentals_analysis_cache_key("BAD")
    result, negative = read_cached_sec_fundamentals(
        _LocalMarketBackend({key: {"ticker": object()}}),
        "BAD",
    )
    assert result is None
    assert negative is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_fundamentals_cache.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.fundamentals'`.

- [ ] **Step 3: Add package and helper implementation**

Create `src/fundamentals/__init__.py`:

```python
"""Fundamentals local-cache helpers and future provider orchestration."""
```

Create `src/fundamentals/cache.py`:

```python
"""Local-only fundamentals cache helpers.

The generic LocalMarketDatabaseBackend.get_financial_cache path can still PG-fallback
to migrate legacy cache rows. S-B needs a stricter contract for fundamentals:
read local SQLite cache only, then return an honest miss.
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Tuple

from src.tools.schemas import FundamentalsResult

logger = logging.getLogger(__name__)


def fundamentals_analysis_cache_key(ticker: str, period: str = "annual") -> str:
    return f"fundamentals_analysis:sec_edgar:{ticker.strip().upper()}:{period}:v1"


def _local_cache_reader(backend: Any):
    if backend is None:
        return None
    market = getattr(backend, "_market", None)
    if market is not None and hasattr(market, "get_financial_cache"):
        return market.get_financial_cache
    module = type(backend).__module__
    if module == "src.tools.backends.db_backend":
        return None
    if hasattr(backend, "get_financial_cache"):
        return backend.get_financial_cache
    return None


def read_cached_sec_fundamentals(
    backend: Any,
    ticker: str,
    period: str = "annual",
) -> Tuple[Optional[FundamentalsResult], bool]:
    """Return (cached_result, negative_cached) from local cache only."""
    reader = _local_cache_reader(backend)
    if reader is None:
        return None, False
    cache_key = fundamentals_analysis_cache_key(ticker, period)
    try:
        payload = reader(cache_key)
    except Exception as exc:  # noqa: BLE001 - cache read must not break callers.
        logger.debug("local fundamentals cache read failed for %s: %s", cache_key, exc)
        return None, False
    if not payload:
        return None, False
    if isinstance(payload, dict) and payload.get("_negative"):
        return None, True
    try:
        result = FundamentalsResult.model_validate(payload)
    except Exception:  # noqa: BLE001 - stale/incompatible cache shape is a miss.
        return None, False
    if not result.snapshot_date and result.data_source == "none":
        return None, False
    return result, False
```

- [ ] **Step 4: Run helper tests**

Run:

```bash
pytest tests/test_fundamentals_cache.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

Run:

```bash
git add src/fundamentals/__init__.py src/fundamentals/cache.py tests/test_fundamentals_cache.py
git commit -m "feat: add local-only fundamentals cache helper"
```

## Task 2: Use Local-Only SEC Cache In Analysis Path

**Files:**
- Modify: `src/tools/analysis_tools.py`
- Modify: `tests/test_fundamentals_sec_cache.py`

- [ ] **Step 1: Add failing test proving LocalMarket cache reads bypass PG fallback**

Append this test to `tests/test_fundamentals_sec_cache.py`:

```python
def test_sec_cache_hit_with_local_market_backend_does_not_pg_fallback(monkeypatch):
    from src.tools.schemas import FundamentalsResult

    class _Market:
        def __init__(self):
            self.calls = []
        def get_financial_cache(self, cache_key):
            self.calls.append(cache_key)
            return FundamentalsResult(
                ticker="AAPL",
                data_source="sec_edgar",
                snapshot_date="2025-12-31",
                roe=0.33,
            ).model_dump()

    class _LocalMarketLike:
        def __init__(self):
            self._market = _Market()
            self.pg_calls = []
        def get_financial_cache(self, cache_key):
            self.pg_calls.append(cache_key)
            raise AssertionError("PG cache fallback must not be used for fundamentals")
        def set_financial_cache(self, *args, **kwargs):
            raise AssertionError("cache hit must not write")

    class _DAL:
        def __init__(self):
            self._backend = _LocalMarketLike()
        def get_fundamentals(self, ticker):
            return FundamentalsResult(ticker=ticker.upper())

    monkeypatch.setattr(at, "_is_fd_enabled", lambda dal: False)
    dal = _DAL()

    result = at.get_fundamentals_analysis(dal, "AAPL")

    assert result.data_source == "sec_edgar"
    assert result.roe == 0.33
    assert dal._backend._market.calls == [
        "fundamentals_analysis:sec_edgar:AAPL:annual:v1"
    ]
    assert dal._backend.pg_calls == []
```

- [ ] **Step 2: Run the new test to verify it fails**

Run:

```bash
pytest tests/test_fundamentals_sec_cache.py::test_sec_cache_hit_with_local_market_backend_does_not_pg_fallback -q
```

Expected: FAIL with `AssertionError: PG cache fallback must not be used for fundamentals`.

- [ ] **Step 3: Update analysis_tools to use helper**

In `src/tools/analysis_tools.py`, replace the SEC cache-read block:

```python
    _cache_be = getattr(dal, "_backend", None)
    _sec_key = f"fundamentals_analysis:sec_edgar:{ticker.upper()}:{period}:v1"
    _sec_negative_cached = False
    if _cache_be is not None and hasattr(_cache_be, "get_financial_cache"):
        try:
            hit = _cache_be.get_financial_cache(_sec_key)
        except Exception:  # noqa: BLE001 — cache read must never break the analysis
            hit = None
        if hit is not None:
            if hit.get("_negative"):
                _sec_negative_cached = True  # skip the live SEC fetch; FD branch still runs
            else:
                try:
                    return FundamentalsResult.model_validate(hit)
                except Exception:  # noqa: BLE001 — stale/incompatible cache shape → re-fetch
                    pass
```

with:

```python
    from src.fundamentals.cache import read_cached_sec_fundamentals

    _cache_be = getattr(dal, "_backend", None)
    cached_sec, _sec_negative_cached = read_cached_sec_fundamentals(
        _cache_be, ticker, period
    )
    if cached_sec is not None:
        return cached_sec
```

Leave the existing `set_financial_cache(...)` calls unchanged so successful SEC fetches still populate local cache.

- [ ] **Step 4: Run SEC cache tests**

Run:

```bash
pytest tests/test_fundamentals_sec_cache.py tests/test_fundamentals_cache.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 2**

Run:

```bash
git add src/tools/analysis_tools.py tests/test_fundamentals_sec_cache.py
git commit -m "fix: keep fundamentals SEC cache reads local-only"
```

## Task 3: Retire Frozen Fundamentals Table From LocalMarket Backend

**Files:**
- Modify: `src/tools/backends/local_market_backend.py`
- Modify: `tests/test_sqlite_backend.py`

- [ ] **Step 1: Replace fallback test with retired-table expectation**

In `tests/test_sqlite_backend.py`, replace `test_fundamentals_local_then_pg_fallback` with:

```python
def test_fundamentals_mirror_table_retired_no_pg_fallback(market_db, monkeypatch):
    db, _ = market_db
    hit = []
    monkeypatch.setattr(
        DatabaseBackend,
        "query_fundamentals",
        lambda self, ticker: (
            hit.append(ticker),
            {"ticker": ticker, "snapshot": "PG"},
        )[1],
    )
    b = _make(db)

    assert b.query_fundamentals("AAPL") == {}
    assert b.query_fundamentals("UNKNOWN") == {}
    assert hit == []
```

Replace `test_provenance_fundamentals_recorded` with:

```python
def test_provenance_fundamentals_records_none_after_mirror_retirement(
    market_db, monkeypatch
):
    from src.tools.backends import provenance

    db, _ = market_db
    hit = []
    monkeypatch.setattr(
        DatabaseBackend,
        "query_fundamentals",
        lambda self, t: hit.append(t) or {"ticker": t, "snapshot": {"x": 1}},
    )
    b = _make(db)

    provenance.reset()
    assert b.query_fundamentals("AAPL") == {}
    assert provenance.read("fundamentals") == "none"
    provenance.reset()
    assert b.query_fundamentals("UNKNOWN") == {}
    assert provenance.read("fundamentals") == "none"
    assert hit == []
```

Keep the lower-level `SqliteBackend.query_fundamentals(...)` tests unchanged; they document the legacy table shape until N9 physically drops it.

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_sqlite_backend.py::test_fundamentals_mirror_table_retired_no_pg_fallback tests/test_sqlite_backend.py::test_provenance_fundamentals_records_none_after_mirror_retirement -q
```

Expected: FAIL because `LocalMarketDatabaseBackend.query_fundamentals()` still reads the local mirror table and PG fallback.

- [ ] **Step 3: Retire LocalMarket fundamentals mirror read**

In `src/tools/backends/local_market_backend.py`, replace `query_fundamentals` with:

```python
    def query_fundamentals(self, ticker: str) -> dict:
        """The PG-mirrored fundamentals table is retired as an authority.

        Use get_fundamentals_analysis() for live SEC/Financial-Datasets fallback and
        /fundamentals/{ticker}?stored=true for local financial_cache hits. The old
        fundamentals table remains inspectable through SqliteBackend until N9, but
        LocalMarketDatabaseBackend must not serve or PG-fallback it as current data.
        """
        provenance.record("fundamentals", "none")
        return {}
```

- [ ] **Step 4: Run LocalMarket backend tests**

Run:

```bash
pytest tests/test_sqlite_backend.py::test_fundamentals_mirror_table_retired_no_pg_fallback tests/test_sqlite_backend.py::test_provenance_fundamentals_records_none_after_mirror_retirement tests/test_sqlite_backend.py::test_query_fundamentals_latest_snapshot tests/test_sqlite_backend.py::test_query_fundamentals_partial_and_empty tests/test_sqlite_backend.py::test_query_fundamentals_same_day_tiebreak_by_id -q
```

Expected: PASS. The first two prove the LocalMarket authority is retired; the last three prove the raw SQLite legacy table reader still behaves for inspection/tests.

- [ ] **Step 5: Commit Task 3**

Run:

```bash
git add src/tools/backends/local_market_backend.py tests/test_sqlite_backend.py
git commit -m "fix: retire mirrored fundamentals from local backend"
```

## Task 4: Route Stored Fundamentals To Local Financial Cache

**Files:**
- Modify: `src/api/routes/fundamentals.py`
- Modify: `tests/test_api.py`

- [ ] **Step 1: Add failing API tests for cache-backed stored mode**

In `tests/test_api.py`, replace `test_fundamentals_stored_mode_no_provider_fetch` with:

```python
def test_fundamentals_stored_mode_reads_local_cache_without_provider_fetch(monkeypatch):
    """stored=true is read-only: it may read local financial_cache, but never enters
    the SEC/Financial-Datasets fetch chain and never reads the retired mirror table."""
    from src.api.routes import fundamentals as fr
    from src.tools.schemas import FundamentalsResult

    calls = {"analysis": 0, "dal": 0}

    class _Backend:
        def __init__(self):
            self.rows = {
                "fundamentals_analysis:sec_edgar:AAPL:annual:v1":
                    FundamentalsResult(
                        ticker="AAPL",
                        data_source="sec_edgar",
                        snapshot_date="2025-12-31",
                        roe=0.22,
                    ).model_dump()
            }
        def get_financial_cache(self, cache_key):
            return self.rows.get(cache_key)

    class _FakeDAL:
        backend_type = "LocalMarketDatabaseBackend"
        def __init__(self):
            self._backend = _Backend()
        def get_fundamentals(self, ticker):
            calls["dal"] += 1
            raise AssertionError("stored=true must not read retired fundamentals table")

    def _spy_analysis(dal, ticker):
        calls["analysis"] += 1
        return FundamentalsResult(ticker=ticker.upper(), data_source="sec_edgar")

    monkeypatch.setattr(fr, "get_fundamentals_analysis", _spy_analysis)
    dal = _FakeDAL()

    out = fr.fundamentals("AAPL", stored=True, dal=dal)

    assert calls == {"analysis": 0, "dal": 0}
    assert out["data_source"] == "sec_edgar"
    assert out["snapshot_date"] == "2025-12-31"
    assert out["roe"] == 0.22
    assert out["source_path"] == "local_cache"

    out2 = fr.fundamentals("AAPL", stored=False, dal=dal)
    assert calls["analysis"] == 1
    assert out2["data_source"] == "sec_edgar"
```

Replace `test_fundamentals_stored_source_path_mapping` with:

```python
def test_fundamentals_stored_source_path_mapping(monkeypatch):
    """/fundamentals/{ticker}?stored=true reports local_cache or none."""
    from src.api.routes import fundamentals as fr
    from src.tools.schemas import FundamentalsResult

    class _CachedDAL(_FakeDALBT):
        def __init__(self):
            super().__init__("LocalMarketDatabaseBackend")
            self._backend = self
        def get_financial_cache(self, cache_key):
            return FundamentalsResult(
                ticker="AAPL",
                data_source="sec_edgar",
                snapshot_date="2025-12-31",
            ).model_dump()

    out = fr.fundamentals("AAPL", stored=True, dal=_CachedDAL())
    assert out["source_path"] == "local_cache"

    class _EmptyDAL(_FakeDALBT):
        def __init__(self):
            super().__init__("LocalMarketDatabaseBackend")
            self._backend = self
        def get_financial_cache(self, cache_key):
            return None

    out = fr.fundamentals("AAPL", stored=True, dal=_EmptyDAL())
    assert out["source_path"] == "none"
    assert out["data_source"] == "none"
    assert out["snapshot_date"] is None
```

- [ ] **Step 2: Run API tests to verify they fail**

Run:

```bash
pytest tests/test_api.py::test_fundamentals_stored_mode_reads_local_cache_without_provider_fetch tests/test_api.py::test_fundamentals_stored_source_path_mapping -q
```

Expected: FAIL because the route still calls `dal.get_fundamentals()`.

- [ ] **Step 3: Update stored route**

In `src/api/routes/fundamentals.py`, change the `stored` description to:

```python
        description="Stored-only: return ONLY the local fundamentals financial_cache "
        "snapshot with NO external fetch and NO PG fallback. Default (false) runs "
        "the full analysis (SEC EDGAR → Financial Datasets fallback).",
```

Add this import near the existing route imports:

```python
from src.tools.schemas import FundamentalsResult
```

Replace the stored branch:

```python
    if stored:
        provenance.reset()
        result = dal.get_fundamentals(ticker)
        if result.snapshot_date:
            result.data_source = "ibkr"  # stored IBKR snapshot origin (mirrors analysis step 1)
        # TRUE per-call origin of the stored read (local | pg_fallback | pg | file | none).
        source = provenance.read("fundamentals") or provenance.fallback(
            dal.backend_type, not result.snapshot_date)
        return {**result.model_dump(), "source_path": source}
```

with:

```python
    if stored:
        from src.fundamentals.cache import read_cached_sec_fundamentals

        provenance.reset()
        cached, _negative = read_cached_sec_fundamentals(
            getattr(dal, "_backend", None),
            ticker,
            "annual",
        )
        if cached is not None:
            provenance.record("fundamentals", "local_cache")
            return {**cached.model_dump(), "source_path": "local_cache"}
        provenance.record("fundamentals", "none")
        empty = FundamentalsResult(ticker=ticker.upper())
        return {**empty.model_dump(), "source_path": "none"}
```

The empty result is constructed directly so `stored=true` cache misses do not touch the retired `fundamentals` table, do not enter the SEC/FD analysis path, and do not PG-fallback.

- [ ] **Step 4: Run API tests**

Run:

```bash
pytest tests/test_api.py::test_fundamentals_stored_mode_reads_local_cache_without_provider_fetch tests/test_api.py::test_fundamentals_stored_source_path_mapping tests/test_fundamentals_cache.py tests/test_fundamentals_sec_cache.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 4**

Run:

```bash
git add src/api/routes/fundamentals.py tests/test_api.py
git commit -m "fix: serve stored fundamentals from local cache"
```

## Task 5: Stop Fundamentals PG Mirror Refresh After News Exit

**Files:**
- Modify: `src/service/data_scheduler.py`
- Modify: `src/api/routes/market_data.py`
- Modify: `tests/test_data_scheduler.py`
- Modify: market-data route tests if present in `tests/test_api.py`

- [ ] **Step 1: Update scheduler tests to expect prices + IV only**

In `tests/test_data_scheduler.py`, update `test_post_exit_ibkr_local_refresh_excludes_news_domain` fake result to mark fundamentals disabled:

```python
                "fundamentals": {"skipped": "domain disabled"},
```

Then update its assertions:

```python
    assert calls == [("prices", "iv")]
    assert res == {
        "ok": True,
        "domains": {"prices": 1, "news": None, "iv": 2, "fundamentals": None},
        "skipped_domains": {
            "news": "domain disabled",
            "fundamentals": "domain disabled",
        },
    }
```

Apply the same expectation to `test_local_refresh_excludes_news_when_pg_exit_audit_cannot_be_read`:

```python
    assert calls == [("prices", "iv")]
    assert res["domains"]["news"] is None
    assert res["domains"]["fundamentals"] is None
    assert res["skipped_domains"] == {
        "news": "domain disabled",
        "fundamentals": "domain disabled",
    }
```

- [ ] **Step 2: Run scheduler tests to verify they fail**

Run:

```bash
pytest tests/test_data_scheduler.py::test_post_exit_ibkr_local_refresh_excludes_news_domain tests/test_data_scheduler.py::test_local_refresh_excludes_news_when_pg_exit_audit_cannot_be_read -q
```

Expected: FAIL because `_local_refresh()` still requests `("prices", "iv", "fundamentals")`.

- [ ] **Step 3: Update scheduler local refresh domains**

In `src/service/data_scheduler.py`, replace:

```python
            domains = (
                ("prices", "iv", "fundamentals")
                if _news_pg_exit_assume_completed_for_refresh(market_db)
                else None
            )
```

with:

```python
            domains = (
                ("prices", "iv")
                if _news_pg_exit_assume_completed_for_refresh(market_db)
                else None
            )
```

- [ ] **Step 4: Update manual market-data update domains**

In `src/api/routes/market_data.py`, replace `_manual_update_domains`:

```python
    if profile_done or audit_state is True or audit_state is None:
        return ("prices", "iv", "fundamentals")
```

with:

```python
    if profile_done or audit_state is True or audit_state is None:
        return ("prices", "iv")
```

Also update the `update_route` docstring line:

```python
    prices + news + iv + fundamentals before news PG exit; prices + iv after
    fundamentals S-B and news exit).
```

Use this clearer replacement:

```python
    prices + news + iv + fundamentals before news PG exit; prices + iv after
    news/fundamentals PG-exit slices). Append-only to the live DB — routing can stay
```

- [ ] **Step 5: Run focused scheduler and route tests**

Run:

```bash
pytest tests/test_data_scheduler.py::test_post_exit_ibkr_local_refresh_excludes_news_domain tests/test_data_scheduler.py::test_local_refresh_excludes_news_when_pg_exit_audit_cannot_be_read tests/test_api.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 5**

Run:

```bash
git add src/service/data_scheduler.py src/api/routes/market_data.py tests/test_data_scheduler.py tests/test_api.py
git commit -m "fix: stop fundamentals PG mirror refresh"
```

## Task 6: Status, Health, And Documentation Cleanup

**Files:**
- Modify: `src/api/routes/market_data.py`
- Modify: `docs/design/PG_EXIT_REMAINDER_SCOPING.md`
- Modify tests only if a status assertion needs text updates

- [ ] **Step 1: Add status note test if route tests already assert status shape**

Search:

```bash
rg -n "market_data_status|/market-data/status|sync.*fundamentals|fundamentals.*sync" tests src apps
```

If there is an existing `market_data_status` test, update it to expect a new response field:

```python
assert out["fundamentals_mode"] == "local_cache_refetch"
```

If there is no route unit test for `market_data_status`, skip adding a broad new status test in this slice and implement only the static response field in Step 2. The final verification command in Task 7 will exercise import/serialization.

- [ ] **Step 2: Add explicit status field**

In `src/api/routes/market_data.py`, add this key to the `market_data_status` return dict near `"financial_cache"`:

```python
        "fundamentals_mode": "local_cache_refetch",
```

This field tells the UI/API consumer that `fundamentals` row counts are legacy table stats, while the active stored path is local `financial_cache` plus refetch-capable analysis.

- [ ] **Step 3: Update scoping doc**

In `docs/design/PG_EXIT_REMAINDER_SCOPING.md`, update the fundamentals row in §12.3 from:

```markdown
| Fundamentals | local table has only 130 stored snapshots; default analysis already does stored → SEC EDGAR → Financial Datasets; stored-only UI path can still PG-fallback unless strict | fast win: stop fundamentals mirror/sync, make stored path local-only with honest empty, rely on local financial cache + SEC/paid fallback |
```

to:

```markdown
| Fundamentals | S-B retires the frozen `fundamentals` mirror table as an authority; `stored=true` reads only local positive SEC `financial_cache` rows and otherwise returns honest empty; default analysis remains SEC EDGAR / Financial Datasets refetch with local cache | PG-free after S-B; old `fundamentals` table is an N9 drop-orphan |
```

Update §12.4 gate 1 from:

```markdown
1. set stored-only fundamentals reads to local-only under PG-exit (no PG fallback),
```

to:

```markdown
1. set stored-only fundamentals reads to local `financial_cache` only (no PG fallback, no provider fetch),
```

Update §12.7 first item from:

```markdown
1. **S-B fundamentals refetch/cache:** local-only stored reads + provider fallback retained.
```

to:

```markdown
1. **S-B fundamentals refetch/cache:** local-cache stored reads + provider fallback retained. **Status: implemented** once the S-B code commit lands.
```

- [ ] **Step 4: Run placeholder scan**

Run:

```bash
rg -n "TBD|TODO|FIXME|fundamentals.*PG fallback|stored.*PG" docs/design/PG_EXIT_REMAINDER_SCOPING.md src/api/routes/fundamentals.py src/api/routes/market_data.py
```

Expected: no stale claim that stored fundamentals PG-fallback is active. Matches in historical sections are acceptable only if the line explicitly says it was retired.

- [ ] **Step 5: Commit Task 6**

Run:

```bash
git add src/api/routes/market_data.py docs/design/PG_EXIT_REMAINDER_SCOPING.md
git commit -m "docs: mark fundamentals PG exit complete"
```

## Task 7: Read-Only Live Audit And Final Verification

**Files:**
- No code changes expected.

- [ ] **Step 1: Audit old fundamentals table scope**

Run:

```bash
python - <<'PY'
import sqlite3
from pathlib import Path

db = Path("data/market_data.db").resolve()
conn = sqlite3.connect(f"{db.as_uri()}?mode=ro", uri=True)
try:
    rows = conn.execute(
        "SELECT ticker, MAX(snapshot_date) FROM fundamentals GROUP BY ticker ORDER BY ticker"
    ).fetchall()
    print({"ticker_count": len(rows), "sample": rows[:10]})
finally:
    conn.close()
PY
```

Expected: read-only report of the frozen legacy table; no write, no schema change. Record the ticker count and sample in the final answer. This satisfies the S-B "non-US / uncovered symbols need awareness" gate at the level available without live SEC calls; any suspicious non-US/ADR tickers from the sample or full output should be noted for a later provider-coverage pass.

- [ ] **Step 2: Verify SEC User-Agent/cache contract remains intact**

Run:

```bash
pytest tests/test_fundamentals_sec_cache.py tests/test_fundamentals_cache.py -q
```

Expected: PASS. This confirms SEC cache reads/writes and User-Agent canonicalization still hold.

- [ ] **Step 3: Verify API/backend/scheduler surfaces**

Run:

```bash
pytest tests/test_api.py tests/test_sqlite_backend.py tests/test_data_scheduler.py tests/test_provider_health.py tests/test_fundamentals_sec_cache.py tests/test_fundamentals_cache.py -q
```

Expected: PASS.

- [ ] **Step 4: Verify no runtime PG sync still targets fundamentals after news exit**

Run:

```bash
rg -n '"prices", "iv", "fundamentals"|--fundamentals|fundamentals.*PG fallback|query_fundamentals\\(' src/service src/api src/tools tests | head -n 200
```

Expected:
- No `("prices", "iv", "fundamentals")` tuple remains in scheduler/API post-exit update code.
- `--fundamentals` may still appear in `scripts/migrate_to_supabase.py` and docs as a legacy/N9 target; that is acceptable until N9.
- `query_fundamentals(` remains as an interface and low-level legacy table reader; LocalMarket backend must be retired/honest-empty.

- [ ] **Step 5: Check worktree**

Run:

```bash
git status --short
```

Expected: only pre-existing unrelated dirty `config/tickers_core.json` / `trained_models/*` remain. No uncommitted S-B files.

## Self-Review Checklist

- S-B removes stored fundamentals PG fallback: Task 3 and Task 4.
- S-B preserves default SEC/FD analysis and local cache writes: Task 2 and Task 7.
- S-B avoids generic financial_cache PG fallback for fundamentals cache reads: Task 1 and Task 2.
- S-B stops fundamentals PG mirror refresh after news exit: Task 5.
- S-B records docs/status semantics and N9 orphan status: Task 6.
- S-B does not migrate 130 PG rows and does not add a provider collector: no task creates such code.
