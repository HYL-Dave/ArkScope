# News Burst Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent sidecar startup / same-tick scheduler bursts from producing false provider failures caused by `market_data.db` write-lock contention, especially for Polygon/Finnhub/IBKR news.

**Architecture:** Keep the already-landed P0-C.1 scheduler backpressure (`SourceDef.writes_market_db` + one market writer per tick). Harden the news path itself by moving provider fetches outside `market_write_lock`, acquiring the cross-process market lock only around SQLite writes/telemetry, and classifying residual lock contention as retryable `skipped_lock_busy` instead of durable failed provider status. Treat mocked seams as unsafe unless a companion test consumes the real stdout/result shape or the real lock context shape.

**Tech Stack:** Python, pytest, SQLite, existing `src.service.data_scheduler`, `src.news_normalized.writer`, `src.news_normalized.ibkr_cli`, `src.market_data_direct.market_write_lock`, existing scheduler state/job telemetry.

---

## Map Check

- PG-exit is closed as of `64530bb`; this is not PG-exit work.
- This is a post-PG-exit runtime hygiene slice. It supports reliable local `job_runs` / provider health telemetry by stopping startup bursts from recording false provider failures.
- This plan intentionally does not redesign scheduler intervals, provider rate limits, FRED, S-J Phase 2, or Data Sources layout.

## Current Grounding

- `SourceDef.writes_market_db` already exists and is set on `polygon_news`, `finnhub_news`, `ibkr_news`, `ibkr_prices`, and `price_backfill`.
- `tick_once()` already fires at most one due `writes_market_db` source per tick and records `skip_kind="market_writer_backpressure"` for the rest.
- `backfill_prices_direct()` already fetches provider data outside the market write lock and takes short write locks only for SQLite write phases.
- `_run_normalized_news_writer()` still wraps `write_news_batch()` in one outer `market_write_lock()`. Since `write_news_batch()` calls `provider.fetch_articles()` and `provider.fetch_body()`, a slow news provider can hold the market lock while doing network work.
- `src.news_normalized.ibkr_cli._run_worker()` has the same issue: it wraps `write_news_batch()` in one outer `market_write_lock()`.
- Price worker retryable lock-busy classification exists (`_prices_worker_retryable_skip_reason()`), but normalized news lock-busy currently falls through the generic exception path and becomes a durable `failed`.

## Decisions Locked

1. **Do not add a queue.** Keep the scheduler's tick model: defer/skip and retry on the next due tick rather than queueing work behind a long writer.
2. **Do not expand source concurrency.** The one-market-writer-per-tick backpressure remains. This plan reduces lock hold time inside the one fired source.
3. **Cross-tick contention is handled by short locks, not another scheduler-wide running flag.** The 2026-07-04 concern was "defer while a market writer is actively running." P0-C.1 already added same-tick backpressure; this slice deliberately solves cross-tick overlap by making every fired market writer hold `market_write_lock` only for short SQLite write phases, with residual contention classified as retryable skip. No long-running queue or global "market writer active" latch is added.
4. **IBKR news participates in the same write-lock hardening.** Gateway serialization remains controlled by `ibkr_gateway_lock`; market DB writes still use `market_write_lock` but only around SQLite writes.
5. **Lock-busy is not provider failure.** A `market_data.db write lock busy (timeout)` while writing normalized news is a retryable scheduler skip (`status="skipped"`, `skip_kind="skipped_lock_busy"`, `last_error=None`), not a red provider failure.
6. **Sanitized subprocess seams must carry classification fields.** IBKR news cannot classify lock-busy from `TimeoutError` class alone because provider/network timeouts share that class. The worker stdout contract must include bounded `error` text and a `retryable` bool, mirroring `src.prices_runtime.sanitize_error()`.
7. **No live provider calls in tests.** All tests use fake providers, fake stores, or monkeypatches. The live soak is manual and happens after merge.

## File Map

- Modify: `src/news_normalized/writer.py`
  - Add an optional `write_lock_factory` argument to `write_news_batch()`.
  - Use it around SQLite write/telemetry phases only.
  - Keep provider fetch calls outside the lock.
- Modify: `src/service/data_scheduler.py`
  - Remove the outer market lock from `_run_normalized_news_writer()`.
  - Pass `market_write_lock` into `write_news_batch()`.
  - Add news lock-busy classification equivalent to price worker classification.
  - Preserve existing same-tick `market_writer_backpressure`.
- Modify: `src/news_normalized/ibkr_cli.py`
  - Remove the outer market lock from `_run_worker()`.
  - Pass `market_write_lock` into `write_news_batch()`.
  - Extend sanitized failure stdout with bounded retryability fields without exposing provider payloads.
- Test: create `tests/test_news_normalized_writer_locking.py`; run existing `tests/test_news_normalized_writer.py` and `tests/test_news_normalized_projection.py`
  - Pin provider fetches outside the injected write lock.
  - Pin SQLite write phases inside the injected write lock.
- Test: `tests/test_data_scheduler.py`
  - Pin normalized news lock-busy classification as `skipped_lock_busy`.
  - Pin startup/same-tick burst still fires only one market writer and records deferrals.
  - Add a companion test that uses the real normalized writer result shape rather than an over-mocked scheduler seam.
- Test: `tests/test_normalized_ibkr_worker.py`
  - Pin IBKR worker passes a write-lock factory to `write_news_batch()` and does not hold an outer market lock across the whole call.
- Modify: `docs/design/PG_EXIT_P0C_PRICES_RECONCILE_CUTOVER_PLAN.md`
  - Append a short post-closeout note that P0-C.1 had price hardening and this slice adds the matching news hardening.

---

### Task 1: Writer-Level Lock Injection

**Files:**
- Modify: `src/news_normalized/writer.py`
- Test: `tests/test_news_normalized_writer_locking.py`

- [ ] **Step 1: Create failing test file for provider fetch outside write lock**

Create `tests/test_news_normalized_writer_locking.py` with:

```python
import sqlite3
from contextlib import contextmanager

from src.news_normalized.models import (
    ArticleCandidate,
    BodyCandidate,
    BodyStatus,
    WriterBudget,
)
from src.news_normalized.store import NormalizedNewsStore
from src.news_normalized.writer import write_news_batch


class _FakeProvider:
    source = "polygon"

    def __init__(self, lock_state, events):
        self._lock_state = lock_state
        self._events = events

    def fetch_articles(self, ticker, since):
        self._events.append(("fetch_articles", ticker, self._lock_state["held"]))
        assert self._lock_state["held"] is False
        return [
            ArticleCandidate(
                source="polygon",
                provider_article_id=f"{ticker}-1",
                title=f"{ticker} headline",
                url=f"https://example.test/{ticker}/1",
                published_at="2026-07-05T12:00:00Z",
                primary_ticker=ticker,
                related_tickers=(ticker,),
                body=BodyCandidate(status=BodyStatus.PENDING),
            )
        ]

    def fetch_body(self, candidate):
        self._events.append(("fetch_body", candidate.provider_article_id, self._lock_state["held"]))
        assert self._lock_state["held"] is False
        return BodyCandidate(status=BodyStatus.FETCHED, raw_body="<p>body</p>", raw_format="html")


@contextmanager
def _tracking_lock(lock_state, events):
    assert lock_state["held"] is False
    lock_state["held"] = True
    events.append(("lock_enter", None, True))
    try:
        yield
    finally:
        events.append(("lock_exit", None, True))
        lock_state["held"] = False


def test_write_news_batch_fetches_outside_injected_write_lock(tmp_path):
    db = tmp_path / "market_data.db"
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    store = NormalizedNewsStore(conn)
    lock_state = {"held": False}
    events = []

    result = write_news_batch(
        store,
        _FakeProvider(lock_state, events),
        ["AAPL"],
        WriterBudget(max_articles=10, max_body_fetches=10),
        project_legacy=False,
        write_lock_factory=lambda: _tracking_lock(lock_state, events),
    )

    conn.close()
    assert result.status == "succeeded"
    assert ("fetch_articles", "AAPL", False) in events
    assert ("fetch_body", "AAPL-1", False) in events
    assert any(event[0] == "lock_enter" for event in events)
```

- [ ] **Step 2: Run the focused RED test**

Run:

```bash
pytest tests/test_news_normalized_writer_locking.py::test_write_news_batch_fetches_outside_injected_write_lock -q
```

Expected: FAIL with `TypeError: write_news_batch() got an unexpected keyword argument 'write_lock_factory'`.

- [ ] **Step 3: Add `write_lock_factory` to `write_news_batch()`**

In `src/news_normalized/writer.py`, extend the typing import:

```python
from typing import Any, Callable, Iterable, Optional, Protocol
```

Change the signature:

```python
def write_news_batch(
    store,
    provider: NewsProvider,
    tickers: Iterable[str],
    budget: WriterBudget,
    *,
    continuation: Optional[WriterContinuation] = None,
    progress_cb: Optional[Callable[[int, int, str], None]] = None,
    project_legacy: bool = False,
    write_lock_factory: Optional[Callable[[], Any]] = None,
) -> WriterResult:
```

Add this near the local counters:

```python
    def write_lock():
        return write_lock_factory() if write_lock_factory is not None else nullcontext()
```

- [ ] **Step 4: Wrap write phases, not provider fetch phases**

In `write_news_batch()`, wrap these write operations:

```python
    def upsert_candidate(candidate: ArticleCandidate):
        if not project_legacy:
            with write_lock():
                return store.upsert(candidate)

        projection = ProjectionResult()
        with write_lock():
            store.conn.execute("BEGIN IMMEDIATE")
            try:
                upsert = store.upsert_uncommitted(candidate)
                if upsert.article_id is not None and not upsert.quarantined:
                    projection = project_article_uncommitted(store.conn, upsert.article_id)
                store.conn.commit()
            except Exception:
                store.conn.rollback()
                raise
        record_projection(projection, upsert.article_id)
        return upsert
```

```python
    def update_body(candidate: ArticleCandidate, body: BodyCandidate) -> None:
        if not project_legacy:
            with write_lock():
                store.update_body(candidate, body)
            return

        projection = ProjectionResult()
        article_id: Optional[int] = None
        with write_lock():
            store.conn.execute("BEGIN IMMEDIATE")
            try:
                article_id = store.update_body_uncommitted(candidate, body)
                projection = project_article_uncommitted(store.conn, article_id)
                store.conn.commit()
            except Exception:
                store.conn.rollback()
                raise
        record_projection(projection, article_id)
```

Wrap provider telemetry setup and finish:

```python
    with write_lock():
        _ensure_provider_sync_tables(store.conn)
        run_id = _start_provider_run(
            store.conn, provider=source, interval="news", domain="news"
        )
```

Wrap `_upsert_provider_meta(...)` calls, including `record_resumed_body_error()`:

```python
        with write_lock():
            _upsert_provider_meta(
                store.conn,
                provider=source,
                ticker=ticker,
                interval="news",
                last_bar_datetime=article.published_at,
                rows_added=0,
                error=error,
            )
```

Wrap `_finish_provider_run(...)` in both failed and success paths:

```python
        with write_lock():
            _finish_provider_run(
                store.conn,
                run_id,
                status="failed",
                tickers_scanned=tickers_scanned,
                gaps_found=0,
                rows_added=articles_inserted,
                error=str(exc),
            )
```

```python
    with write_lock():
        _finish_provider_run(
            store.conn,
            run_id,
            status="succeeded",
            tickers_scanned=tickers_scanned,
            gaps_found=0,
            rows_added=articles_inserted,
            error=None,
        )
```

Do not wrap `provider.fetch_articles(...)` or `provider.fetch_body(...)`.

- [ ] **Step 5: Run the writer locking test**

Run:

```bash
pytest tests/test_news_normalized_writer_locking.py -q
```

Expected: PASS.

- [ ] **Step 6: Run existing normalized writer tests**

Run:

```bash
pytest tests/test_news_normalized_writer.py tests/test_news_normalized_projection.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 1**

Run:

```bash
git add src/news_normalized/writer.py tests/test_news_normalized_writer_locking.py
git commit -m "fix: shorten normalized news write locks"
```

---

### Task 2: Scheduler News Writer Uses Injected Lock and Classifies Lock-Busy

**Files:**
- Modify: `src/service/data_scheduler.py`
- Test: `tests/test_data_scheduler.py`

- [ ] **Step 1: Add failing test for normalized news lock-busy skip**

In `tests/test_data_scheduler.py`, add:

```python
def test_normalized_news_lock_busy_is_retryable_skip(monkeypatch):
    import src.service.data_scheduler as ds
    import src.news_normalized.routing as routing

    monkeypatch.setattr(
        ds,
        "_read_news_write_route_for_scheduler",
        lambda: routing.NewsWriteRoute(
            mode=routing.NewsWriteMode.NORMALIZED,
            reason="normalized",
        ),
    )
    monkeypatch.setattr(ds, "_resolve_price_scope", lambda: ["AAPL"])

    def fake_writer(*args, **kwargs):
        raise TimeoutError("market_data.db write lock busy (timeout)")

    monkeypatch.setattr(ds, "_run_normalized_news_writer", fake_writer)

    res = ds.run_source("polygon_news", trigger_source="scheduler")

    assert res["status"] == "skipped"
    assert res["skip_kind"] == "skipped_lock_busy"
    assert "write lock busy" in res["reason"]
    row = ds._state_store().get("polygon_news")
    assert row["last_status"] == "skipped"
    assert row["last_error"] is None
    assert row["last_result"]["skip_kind"] == "skipped_lock_busy"
```

- [ ] **Step 2: Run the RED test**

Run:

```bash
pytest tests/test_data_scheduler.py::test_normalized_news_lock_busy_is_retryable_skip -q
```

Expected: FAIL because the result is currently `status="failed"`.

- [ ] **Step 3: Add shared lock-busy classifier**

In `src/service/data_scheduler.py`, add:

```python
def _market_write_lock_busy_reason(error: Any) -> Optional[str]:
    text = str(error or "").strip()
    if "market_data.db write lock busy" not in text:
        return None
    return text[:_ERROR_TAIL] or "market_data.db write lock busy (timeout)"
```

Then change `_prices_worker_retryable_skip_reason()` to reuse it:

```python
def _prices_worker_retryable_skip_reason(payload: Dict[str, Any]) -> Optional[str]:
    if payload.get("retryable") is not True:
        return None
    return _market_write_lock_busy_reason(payload.get("error"))
```

- [ ] **Step 4: Classify normalized news lock-busy in `run_source()`**

In the generic `except Exception as e:` block inside `run_source()`, before setting `ok = False`, add:

```python
        except Exception as e:  # noqa: BLE001
            lock_busy_reason = (
                _market_write_lock_busy_reason(e)
                if d.news_direct_source is not None
                else None
            )
            if lock_busy_reason is not None:
                result.update({
                    "status": "skipped",
                    "reason": lock_busy_reason,
                    "skip_kind": "skipped_lock_busy",
                })
                ok = True
                error = None
            else:
                ok = False
                error = str(e)[:_ERROR_TAIL]
                result["error"] = error
                logger.warning(f"scheduler source {source} failed: {error}")
```

Ensure the old body of the `except` is not duplicated.

- [ ] **Step 5: Remove the outer lock from `_run_normalized_news_writer()`**

In `_run_normalized_news_writer()`, replace:

```python
        with market_write_lock():
            store = NormalizedNewsStore(conn)
            result = write_news_batch(
                store,
                provider,
                scope,
                WriterBudget(
                    max_articles=_NORMALIZED_NEWS_MAX_ARTICLES,
                    max_body_fetches=_NORMALIZED_NEWS_MAX_BODY_FETCHES,
                ),
                project_legacy=True,
                continuation=continuation,
                progress_cb=progress_cb,
            )
```

with:

```python
        store = NormalizedNewsStore(conn)
        result = write_news_batch(
            store,
            provider,
            scope,
            WriterBudget(
                max_articles=_NORMALIZED_NEWS_MAX_ARTICLES,
                max_body_fetches=_NORMALIZED_NEWS_MAX_BODY_FETCHES,
            ),
            project_legacy=True,
            continuation=continuation,
            progress_cb=progress_cb,
            write_lock_factory=market_write_lock,
        )
```

> **Obsolete-test cleanup (shipped in this commit):** removing the outer `market_write_lock` makes the pre-existing `test_normalized_news_route_calls_writer_under_market_lock` (`tests/test_data_scheduler.py`) assert a lock ordering that no longer exists — the writer now takes the lock internally via the injected factory. Delete only its `lock_enter`/`lock_exit` assertions (the inline pair and the final `events == [...]` list); keep its route/collector/provider/scope/budget/`project_legacy`/counts coverage. Its lock intent is now covered by the Step-6 companion test.

- [ ] **Step 6: Add companion test for real writer argument shape**

In `tests/test_data_scheduler.py`, add a test that does not mock the final writer result shape:

```python
def test_scheduler_passes_market_lock_factory_to_normalized_news_writer(monkeypatch, tmp_path):
    import src.service.data_scheduler as ds
    import src.news_normalized.routing as routing

    captured = {}

    class _Provider:
        source = "polygon"

    class _Store:
        def __init__(self, conn):
            self.conn = conn

    class _Budget:
        def __init__(self, max_articles, max_body_fetches):
            self.max_articles = max_articles
            self.max_body_fetches = max_body_fetches

    def fake_write_news_batch(store, provider, scope, budget, **kwargs):
        captured.update(kwargs)
        return {
            "status": "succeeded",
            "articles_seen": 0,
            "articles_inserted": 0,
            "bodies_fetched": 0,
            "errors": {},
            "continuation": None,
        }

    monkeypatch.setattr(ds, "_make_normalized_news_provider", lambda source: _Provider())
    monkeypatch.setattr(
        "src.market_data_admin.resolve_market_db_path",
        lambda: str(tmp_path / "market_data.db"),
    )
    monkeypatch.setattr("src.news_normalized.store.NormalizedNewsStore", _Store)
    monkeypatch.setattr("src.news_normalized.models.WriterBudget", _Budget)
    monkeypatch.setattr("src.news_normalized.writer.write_news_batch", fake_write_news_batch)

    out = ds._run_normalized_news_writer("polygon", ["AAPL"])

    assert out["status"] == "succeeded"
    assert captured["write_lock_factory"] is not None
    assert captured["project_legacy"] is True
```

- [ ] **Step 7: Run scheduler focused tests**

Run:

```bash
pytest tests/test_data_scheduler.py::test_normalized_news_lock_busy_is_retryable_skip tests/test_data_scheduler.py::test_scheduler_passes_market_lock_factory_to_normalized_news_writer tests/test_data_scheduler.py::test_tick_once_defers_extra_market_writers tests/test_data_scheduler.py::test_prices_worker_retryable_lock_busy_is_skip_not_failure -q
```

Expected: PASS.

- [ ] **Step 8: Commit Task 2**

Run:

```bash
git add src/service/data_scheduler.py tests/test_data_scheduler.py
git commit -m "fix: classify news lock contention as retryable skip"
```

---

### Task 3: IBKR News Worker Uses Short Write Locks

**Files:**
- Modify: `src/news_normalized/ibkr_cli.py`
- Test: `tests/test_normalized_ibkr_worker.py`

- [ ] **Step 1: Add failing test for worker lock injection**

In `tests/test_normalized_ibkr_worker.py`, add:

```python
def test_ibkr_worker_passes_market_lock_factory_without_outer_write_lock(monkeypatch):
    from src.news_normalized import ibkr_cli

    calls = {}

    class _Source:
        def __init__(self, client_id=None):
            self.client_id = client_id

    class _Gateway:
        def __init__(self, source):
            self.source = source
        def close(self):
            calls["closed"] = True

    class _Provider:
        source = "ibkr"
        def __init__(self, gateway, acquire_gateway_lock):
            self.gateway = gateway
            self.acquire_gateway_lock = acquire_gateway_lock

    class _Store:
        def __init__(self, conn):
            self.conn = conn

    def fake_write_news_batch(store, provider, tickers, budget, **kwargs):
        calls["kwargs"] = kwargs
        return {
            "status": "succeeded",
            "articles_seen": 0,
            "articles_inserted": 0,
            "bodies_fetched": 0,
            "errors": {},
            "continuation": None,
        }

    def forbidden_outer_lock(*args, **kwargs):
        raise AssertionError("outer market_write_lock must not wrap the whole worker")

    monkeypatch.setattr("data_sources.ibkr_source.IBKRDataSource", _Source)
    monkeypatch.setattr("src.news_normalized.ibkr_runtime.IBKRRuntimeGateway", _Gateway)
    monkeypatch.setattr("src.news_normalized.ibkr_adapter.IBKRNormalizedProvider", _Provider)
    monkeypatch.setattr("src.news_normalized.store.NormalizedNewsStore", _Store)
    monkeypatch.setattr("src.news_normalized.writer.write_news_batch", fake_write_news_batch)
    monkeypatch.setattr("src.market_data_direct.market_write_lock", forbidden_outer_lock)
    monkeypatch.setattr("src.market_data_admin.resolve_market_db_path", lambda: ":memory:")

    out = ibkr_cli._run_worker(
        ["AAPL"],
        max_articles=10,
        max_body_fetches=2,
        gateway_lock_held=True,
    )

    assert out["status"] == "succeeded"
    assert "write_lock_factory" in calls["kwargs"]
    assert calls["kwargs"]["project_legacy"] is True
    assert calls["closed"] is True
```

This test is intentionally strict: before implementation it fails because the worker calls the outer `market_write_lock`.

- [ ] **Step 2: Run the RED test**

Run:

```bash
pytest tests/test_normalized_ibkr_worker.py::test_ibkr_worker_passes_market_lock_factory_without_outer_write_lock -q
```

Expected: FAIL with `AssertionError: outer market_write_lock must not wrap the whole worker`.

- [ ] **Step 3: Remove outer lock and pass lock factory**

In `src/news_normalized/ibkr_cli.py`, replace:

```python
            conn = sqlite3.connect(resolve_market_db_path(), timeout=10.0)
            with market_write_lock():
                store = NormalizedNewsStore(conn)
                return write_news_batch(
                    store,
                    provider,
                    tickers,
                    WriterBudget(max_articles, max_body_fetches),
                    project_legacy=True,
                )
```

with:

```python
            conn = sqlite3.connect(resolve_market_db_path(), timeout=10.0)
            store = NormalizedNewsStore(conn)
            return write_news_batch(
                store,
                provider,
                tickers,
                WriterBudget(max_articles, max_body_fetches),
                project_legacy=True,
                write_lock_factory=market_write_lock,
            )
```

> **Obsolete-test cleanup (shipped in this commit):** removing the worker's outer `market_write_lock` makes the pre-existing `test_ibkr_worker_standalone_acquires_gateway_lock_before_market_lock` (`tests/test_normalized_ibkr_worker.py`) obsolete — the worker no longer calls `market_write_lock()` itself (it delegates it to the writer as a factory), so its `market_enter < write < market_exit` ordering can never hold and its local fake `write_news_batch` lacks `**kwargs`. Widen that fake's signature with `**kwargs` and delete only the `market_enter`/`market_exit` ordering assertions; keep the gateway-lock and `client_id == 31` coverage. The Step-1 factory test now covers the no-outer-lock intent.

- [ ] **Step 4: Run worker tests**

Run:

```bash
pytest tests/test_normalized_ibkr_worker.py -q
```

Expected: PASS. Confirm existing stdout sanitization tests still pass; this task must not leak title/url/id/body into worker stdout.

- [ ] **Step 5: Commit Task 3**

Run:

```bash
git add src/news_normalized/ibkr_cli.py tests/test_normalized_ibkr_worker.py
git commit -m "fix: shorten ibkr news worker write locks"
```

---

### Task 3.5: IBKR News Sanitized Lock-Busy Classification

**Files:**
- Modify: `src/news_normalized/ibkr_cli.py`
- Modify: `src/service/data_scheduler.py`
- Test: `tests/test_normalized_ibkr_worker.py`
- Test: `tests/test_data_scheduler.py`

- [ ] **Step 1: Add failing worker sanitization tests**

In `tests/test_normalized_ibkr_worker.py`, add:

```python
def test_sanitize_worker_error_marks_market_lock_busy_retryable():
    from src.news_normalized.ibkr_cli import sanitize_worker_error

    payload = sanitize_worker_error(
        TimeoutError("market_data.db write lock busy (timeout)")
    )

    assert payload["status"] == "failed"
    assert payload["error_classes"] == ["TimeoutError"]
    assert payload["retryable"] is True
    assert payload["error"] == "market_data.db write lock busy (timeout)"


def test_sanitize_worker_error_does_not_mark_generic_timeout_retryable():
    from src.news_normalized.ibkr_cli import sanitize_worker_error

    payload = sanitize_worker_error(TimeoutError("provider request timed out"))

    assert payload["status"] == "failed"
    assert payload["error_classes"] == ["TimeoutError"]
    assert payload["retryable"] is False
    assert payload["error"] == ""
```

- [ ] **Step 2: Run the RED worker sanitization tests**

Run:

```bash
pytest tests/test_normalized_ibkr_worker.py::test_sanitize_worker_error_marks_market_lock_busy_retryable tests/test_normalized_ibkr_worker.py::test_sanitize_worker_error_does_not_mark_generic_timeout_retryable -q
```

Expected: FAIL because `retryable` and `error` are not currently in the sanitized worker payload.

- [ ] **Step 3: Add bounded retryability fields to IBKR worker errors**

In `src/news_normalized/ibkr_cli.py`, add:

```python
_MAX_ERROR_LEN = 600


def _is_retryable_worker_error(message: str) -> bool:
    return "market_data.db write lock busy" in message
```

Then change `sanitize_worker_error()` so only retryable lock-busy errors expose bounded text:

```python
def sanitize_worker_error(exc: BaseException) -> dict[str, Any]:
    message = str(exc)[:_MAX_ERROR_LEN]
    retryable = _is_retryable_worker_error(message)
    payload = {"status": "failed"}
    for key in _COUNT_KEYS:
        payload[key] = 0
    payload["error_count"] = 1
    payload["error_classes"] = [type(exc).__name__]
    payload["error"] = message if retryable else ""
    payload["retryable"] = retryable
    return payload
```

Do not include article title, URL, provider id, body fields, or arbitrary exception text. The bounded message is allowed only for the known `market_data.db write lock busy` string because the scheduler needs that classifier. Generic provider/network `TimeoutError` remains classified by `error_classes` only.

- [ ] **Step 4: Run worker sanitization tests**

Run:

```bash
pytest tests/test_normalized_ibkr_worker.py::test_sanitize_worker_error_marks_market_lock_busy_retryable tests/test_normalized_ibkr_worker.py::test_sanitize_worker_error_does_not_mark_generic_timeout_retryable -q
```

Expected: PASS.

- [ ] **Step 5: Add failing parser/classifier test for real sanitized shape**

In `tests/test_data_scheduler.py`, add:

```python
def test_ibkr_news_worker_stdout_parse_preserves_retryable_lock_busy():
    import json as _json
    import src.service.data_scheduler as ds
    from src.news_normalized.ibkr_cli import sanitize_worker_error

    failure = _json.dumps(
        sanitize_worker_error(
            TimeoutError("market_data.db write lock busy (timeout)")
        )
    )
    payload = ds._parse_sanitized_worker_stdout(failure)

    assert payload["retryable"] is True
    assert "write lock busy" in payload["error"]
    assert payload["error_classes"] == ["TimeoutError"]
    assert ds._normalized_worker_retryable_skip_reason(payload) is not None

    provider_failure = _json.dumps(
        sanitize_worker_error(TimeoutError("provider request timed out"))
    )
    provider_payload = ds._parse_sanitized_worker_stdout(provider_failure)
    assert provider_payload["retryable"] is False
    assert provider_payload["error"] == ""
    assert ds._normalized_worker_retryable_skip_reason(provider_payload) is None
```

- [ ] **Step 6: Run RED parser/classifier test**

Run:

```bash
pytest tests/test_data_scheduler.py::test_ibkr_news_worker_stdout_parse_preserves_retryable_lock_busy -q
```

Expected: FAIL because `_parse_sanitized_worker_stdout()` does not allowlist `error` / `retryable`, and `_normalized_worker_retryable_skip_reason()` does not exist yet.

- [ ] **Step 7: Allowlist error/retryable in normalized worker stdout parser**

In `src/service/data_scheduler.py`, update `_parse_sanitized_worker_stdout()` after `error_count`:

```python
    error = str(raw.get("error") or "").strip()
    payload["error"] = error[:_ERROR_TAIL] if error else ""
    payload["retryable"] = raw.get("retryable") is True
```

Then add:

```python
def _normalized_worker_retryable_skip_reason(payload: Dict[str, Any]) -> Optional[str]:
    if payload.get("retryable") is not True:
        return None
    return _market_write_lock_busy_reason(payload.get("error"))
```

- [ ] **Step 8: Classify IBKR news worker payload before raising failure**

In the `ibkr_news` normalized subprocess branch inside `run_source()`, change:

```python
                    if step["returncode"] != 0:
                        raise RuntimeError(
                            _sanitized_worker_failure_message(step["payload"])
                        )
```

to:

```python
                    if step["returncode"] != 0:
                        reason = _normalized_worker_retryable_skip_reason(step["payload"])
                        if reason is not None:
                            result.update({
                                "status": "skipped",
                                "reason": reason,
                                "skip_kind": "skipped_lock_busy",
                            })
                        else:
                            raise RuntimeError(
                                _sanitized_worker_failure_message(step["payload"])
                            )
```

- [ ] **Step 9: Add run_source payload classification test**

In `tests/test_data_scheduler.py`, add:

```python
def test_ibkr_news_worker_lock_busy_payload_is_skip_not_failure(monkeypatch):
    import src.service.data_scheduler as ds
    import src.news_normalized.routing as routing

    class _Lock:
        def acquire(self, *args, **kwargs):
            return True

        def release(self):
            pass

    monkeypatch.setattr(
        ds,
        "_read_news_write_route_for_scheduler",
        lambda: routing.NewsWriteRoute(
            mode=routing.NewsWriteMode.NORMALIZED,
            reason="normalized",
        ),
    )
    monkeypatch.setattr(ds, "_resolve_price_scope", lambda: ["AAPL"])
    monkeypatch.setattr(ds, "_IBKR_LOCK", _Lock())
    monkeypatch.setattr(ds, "_IBKR_FLOCK", _Lock())
    monkeypatch.setattr(
        ds,
        "_run_sanitized_json_subprocess",
        lambda argv: {
            "returncode": 1,
            "payload": {
                "status": "failed",
                "articles_seen": 0,
                "articles_inserted": 0,
                "bodies_fetched": 0,
                "error_count": 1,
                "error_classes": ["TimeoutError"],
                "error": "market_data.db write lock busy (timeout)",
                "retryable": True,
            },
        },
    )

    res = ds.run_source("ibkr_news", trigger_source="scheduler")

    assert res["status"] == "skipped"
    assert res["skip_kind"] == "skipped_lock_busy"
    assert "write lock busy" in res["reason"]
    row = ds._state_store().get("ibkr_news")
    assert row["last_status"] == "skipped"
    assert row["last_error"] is None
```

- [ ] **Step 10: Run Task 3.5 tests**

Run:

```bash
pytest \
  tests/test_normalized_ibkr_worker.py::test_sanitize_worker_error_marks_market_lock_busy_retryable \
  tests/test_normalized_ibkr_worker.py::test_sanitize_worker_error_does_not_mark_generic_timeout_retryable \
  tests/test_data_scheduler.py::test_ibkr_news_worker_stdout_parse_preserves_retryable_lock_busy \
  tests/test_data_scheduler.py::test_ibkr_news_worker_lock_busy_payload_is_skip_not_failure \
  -q
```

Expected: PASS.

- [ ] **Step 11: Run existing sanitization secrecy tests**

Run:

```bash
pytest \
  tests/test_normalized_ibkr_worker.py \
  tests/test_data_scheduler.py::test_normalized_ibkr_worker_failure_hides_raw_child_stderr \
  tests/test_data_scheduler.py::test_normalized_ibkr_worker_invalid_stdout_is_generic_failure \
  -q
```

Expected: PASS. Existing assertions that worker stdout does not include article title/url/id/body/provider payload must remain green. The new `error` field must not reintroduce arbitrary exception text.

- [ ] **Step 12: Commit Task 3.5**

Run:

```bash
git add src/news_normalized/ibkr_cli.py src/service/data_scheduler.py tests/test_normalized_ibkr_worker.py tests/test_data_scheduler.py
git commit -m "fix: preserve retryable ibkr news worker errors"
```

---

### Task 3.6: Writer Re-raises Lock-Busy From Write Phases (post-review P1 fix)

> **Reviewer finding (2026-07-05, post-implementation):** with the lock moved inside
> `write_news_batch()`, the writer's resumable-error catch blocks could swallow a
> `TimeoutError("market_data.db write lock busy (timeout)")` raised by a write-phase lock
> acquisition into the per-article/per-ticker `errors` dict, returning `status="partial"`
> instead of propagating — so mid-batch lock contention surfaced as a durable partial
> (and, via the rc=0 IBKR worker path, as `error_classes=["ProviderError"]`), violating
> the slice contract that lock contention is always a retryable `skipped_lock_busy`.
> Reproduced with a lock factory that succeeds at run-start and times out on the first
> article write.
>
> **Fix (shipped):** `src/news_normalized/writer.py` adds `_is_market_lock_busy()`
> (substring match on the `market_write_lock` message) and re-raises before resumable
> handling at all four swallow sites: the deferred-body resume catch, the candidate
> upsert catch, the body-update catch, and the per-ticker outer catch. Three RED-first
> tests in `tests/test_news_normalized_writer_locking.py` inject a flaky lock factory
> (succeeds at run-start, times out at acquisition N) and assert `write_news_batch()`
> raises the lock-busy `TimeoutError` from the upsert, body-update, and deferred-resume
> phases. Classification then composes with Task 2 (in-process) and Task 3.5 (worker)
> untouched. Commit: `fix: reraise lock busy from news write phases`.

---

### Task 4: Startup Burst Regression Gate

**Files:**
- Modify: `tests/test_data_scheduler.py`
- Modify: `src/service/data_scheduler.py` only if the new burst tests expose a scheduler logic gap.

- [ ] **Step 1: Add all-market-writers burst test**

In `tests/test_data_scheduler.py`, add:

```python
def test_startup_burst_defers_all_extra_market_writers(monkeypatch):
    import src.service.data_scheduler as ds
    now = datetime(2026, 7, 5, tzinfo=timezone.utc)
    due_sources = {
        "polygon_news",
        "finnhub_news",
        "ibkr_news",
        "ibkr_prices",
        "price_backfill",
    }
    fired = []
    skipped = []

    monkeypatch.setattr(
        ds,
        "source_config",
        lambda source: {"enabled": source in due_sources, "interval_minutes": 1},
    )
    monkeypatch.setattr(ds, "_is_due", lambda source, current: source in due_sources)
    monkeypatch.setattr(ds, "_record_result", lambda result: skipped.append(result) or result)

    out = ds.tick_once(now, fire=fired.append)

    assert out == fired
    assert len(fired) == 1
    assert fired[0] in due_sources
    deferred = [row for row in skipped if row.get("skip_kind") == "market_writer_backpressure"]
    assert {row["source"] for row in deferred} == due_sources - {fired[0]}
    assert all(row["status"] == "skipped" for row in deferred)
```

- [ ] **Step 2: Run the burst test**

Run:

```bash
pytest tests/test_data_scheduler.py::test_startup_burst_defers_all_extra_market_writers -q
```

Expected: PASS. If it fails, fix `tick_once()` without changing the defer-not-queue decision.

- [ ] **Step 3: Verify no durable failed status for deferred burst rows**

Add:

```python
def test_market_writer_backpressure_is_not_failed(monkeypatch):
    import src.service.data_scheduler as ds
    now = datetime(2026, 7, 5, tzinfo=timezone.utc)

    monkeypatch.setattr(
        ds,
        "source_config",
        lambda source: {
            "enabled": source in {"polygon_news", "finnhub_news"},
            "interval_minutes": 1,
        },
    )
    monkeypatch.setattr(
        ds,
        "_is_due",
        lambda source, current: source in {"polygon_news", "finnhub_news"},
    )

    ds.tick_once(now, fire=lambda source: None)

    row = ds._state_store().get("finnhub_news")
    if row is not None:
        assert row["last_status"] != "failed"
```

This test allows no row if `_record_result()` stays in-memory only; it forbids durable failed status.

- [ ] **Step 4: Run scheduler suite subset**

Run:

```bash
pytest tests/test_data_scheduler.py -q
```

Expected: PASS. If this file is too slow, run the new tests plus the existing lock/backpressure tests and document the narrowed set in the final review.

- [ ] **Step 5: Commit Task 4**

Run:

```bash
git add tests/test_data_scheduler.py src/service/data_scheduler.py
git commit -m "test: pin scheduler startup burst backpressure"
```

If `src/service/data_scheduler.py` did not change, omit it from `git add`.

---

### Task 5: Focused Verification and Docs Note

**Files:**
- Modify: `docs/design/PG_EXIT_P0C_PRICES_RECONCILE_CUTOVER_PLAN.md`

- [ ] **Step 1: Run focused backend tests**

Run:

```bash
pytest \
  tests/test_news_normalized_writer_locking.py \
  tests/test_data_scheduler.py \
  tests/test_normalized_ibkr_worker.py \
  tests/test_provider_health.py \
  tests/test_market_data_direct.py::test_backfill_fetches_provider_rows_outside_market_write_lock \
  -q
```

Expected: PASS.

- [ ] **Step 2: Compile touched runtime modules**

Run:

```bash
python -m compileall \
  src/news_normalized/writer.py \
  src/news_normalized/ibkr_cli.py \
  src/service/data_scheduler.py
```

Expected: exit 0.

- [ ] **Step 3: Run diff hygiene**

Run:

```bash
git diff --check
```

Expected: no output.

- [ ] **Step 4: Add docs note**

Append a short note to `docs/design/PG_EXIT_P0C_PRICES_RECONCILE_CUTOVER_PLAN.md` near the P0-C.1 runtime hardening record:

```markdown
**P0-C.2 news burst hardening (2026-07-05):** normalized Polygon/Finnhub/IBKR news writers now use short `market_write_lock` sections only around SQLite write/telemetry phases; provider fetches occur outside the market DB lock. Residual `market_data.db write lock busy` errors are classified as retryable `skipped_lock_busy`, and same-tick market writer bursts remain deferred via `market_writer_backpressure`.
```

- [ ] **Step 5: Commit Task 5**

Run:

```bash
git add docs/design/PG_EXIT_P0C_PRICES_RECONCILE_CUTOVER_PLAN.md
git commit -m "docs: record news burst hardening"
```

If the docs note is intentionally skipped, do not create an empty commit; record that in the implementation review.

---

### Task 6: Live Sidecar Soak

**Files:**
- No code changes.
- Evidence output can stay in `scratchpad/` and should not be committed unless the reviewer requests it.

- [ ] **Step 1: Pre-soak state**

Before restarting sidecar, record:

```bash
python -m scripts.smoke.pg_unreachable_e2e --output scratchpad/news-burst-pre-e2e.json
```

Expected: `ok:true`, `pg_attempts:[]`.

- [ ] **Step 2: Enable the normal startup scenario**

Use the app's Settings to leave the scheduler in the user's normal enabled/disabled state. Do not manually start multiple provider runs during the first tick.

- [ ] **Step 3: Restart sidecar**

Start the sidecar normally. Let it run for at least two scheduler ticks (`TICK_SECONDS=30`, so wait at least 70 seconds).

- [ ] **Step 4: Inspect provider/job status**

Check `/status`, `/schedule`, and Data Sources UI. Required observations:

- No Polygon/Finnhub/IBKR news source records a durable provider failure with `market_data.db write lock busy`.
- If contention occurs, it appears as `status="skipped"` with `skip_kind="skipped_lock_busy"` or `skip_kind="market_writer_backpressure"`.
- The UI must not show a red provider failure for lock-busy contention.

- [ ] **Step 5: Post-soak E2E**

Run:

```bash
python -m scripts.smoke.pg_unreachable_e2e --output scratchpad/news-burst-post-e2e.json
```

Expected: `ok:true`, `pg_attempts:[]`.

- [ ] **Step 6: Review and close**

Summarize:

- focused test commands and pass counts;
- whether startup produced any `skipped_lock_busy` / `market_writer_backpressure`;
- whether any true provider failure remained;
- whether PG-unreachable E2E stayed green.

Do not mark this slice complete until the reviewer sees both the test results and the sidecar soak summary.

---

## Self-Review Notes

- Spec coverage:
  - Fetch outside lock: Task 1 + Task 3.
  - News skipped lock-busy parity: Task 2.
  - Existing tick backpressure preserved and broadened in tests: Task 4.
  - P0-C.1 mocked seam lessons: Task 2 companion test + Task 3 stdout/worker shape test.
  - Live startup evidence: Task 6.
- Scope intentionally excludes:
  - queueing deferred jobs;
  - changing source intervals;
  - FRED enablement/product semantics;
  - S-J Phase 2 config fallback strictness;
  - Data Sources layout cleanup beyond correctly classifying status.
- Known implementation risk:
  - `write_news_batch()` interleaves reads, provider fetches, and writes. The implementation must not wrap read+fetch loops in `market_write_lock`; only write/telemetry operations should use the injected lock context.
  - If a lock-busy timeout happens after a provider fetch but before a write, the run may be skipped and retried later. This is acceptable: article providers are idempotent by provider id / canonical identity, and retrying is better than recording a false provider failure.
