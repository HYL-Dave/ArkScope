# P0-C.1 Prices Runtime Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** IMPLEMENTED 2026-07-04. Offline gate:
`pytest tests/test_prices_runtime.py tests/test_data_scheduler.py tests/test_market_data_direct.py tests/test_provider_health.py -q`
→ `160 passed`.

**Goal:** Fix the first live P0-C scheduler failures by restoring IBKR subprocess isolation, shortening `market_data.db` write-lock holds, and classifying transient market-write contention as retryable scheduler backpressure.

**Architecture:** Keep P0-C's local price authority unchanged. Move scheduled IBKR price execution behind a sanitized `python -m src.prices_runtime` worker used by both `ibkr_prices` and `price_backfill`; refactor the direct writer so provider fetch happens outside `market_write_lock`; add scheduler-level market-writer backpressure so a restored scheduler does not launch multiple DB writers in the same tick.

**Tech Stack:** Python, argparse, subprocess JSON workers, SQLite, `ib_insync`, existing `ibkr_gateway_lock`, existing `market_write_lock`, pytest.

---

## Map Check

This is not a new roadmap line. It is a P0-C runtime follow-up caused by the first live scheduler run after P0-C cutover:

- `ibkr_prices`: `There is no current event loop in thread 'sched-ibkr_prices'`
- normalized IBKR news: `normalized IBKR worker failed (TimeoutError)`
- local writers: `market_data.db write lock busy (timeout)`

The P0-C implementation is still correct at the data-authority level: prices read/write local and PG prices is archive-only. The runtime wiring needs hardening because Task 4 chose the minimal in-process adapter path even though the scheduler file already documented that IBKR/`ib_insync` is safer in its own process.

## Current Root Cause Evidence (Pre-Fix)

1. `src/service/data_scheduler.py` currently declares `ibkr_prices` as:

```python
SourceDef(
    "ibkr_prices", "IBKR 股價",
    None, None,
    ibkr=True, universe_tickers=True, default_interval_min=60,
    adapter=("src.market_data_direct", "backfill_prices_direct"),
    description="IBKR/Polygon 15min bars for the active universe → market_data.db DIRECT (no PG sync/mirror)",
)
```

`tick_once()` launches enabled sources in daemon threads named `sched-<source>`. Therefore `ibkr_prices` constructs `IBKRDataSource` / `ib_insync.IB()` in `sched-ibkr_prices`, not in a clean process main thread.

2. `price_backfill` uses the same adapter and has the same latent event-loop bug when its planner finds fillable gaps.

3. `src/market_data_direct.py::backfill_prices_direct()` currently holds `market_write_lock()` around setup, per-ticker gap detection, provider fetch, row insert, and telemetry. A full active-universe IBKR run can hold the lock for minutes, which starves normalized news writers whose lock timeout is shorter.

4. The normalized IBKR news worker already uses the correct S-A1 pattern: `python -m src.news_normalized.ibkr_cli`, `--gateway-lock-held`, provider config injection, sanitized JSON stdout, and no raw provider payload in scheduler output.

## Desired End State

- `ibkr_prices` and `price_backfill` both run via `python -m src.prices_runtime`.
- The scheduler still owns the shared IBKR Gateway lock; the worker receives `--gateway-lock-held` and does not reacquire the non-reentrant lock.
- Worker stdout is one sanitized JSON object. It contains counts, status, and bounded error classes/messages; it never includes DB paths with secrets, provider raw responses, API keys, or full tracebacks.
- `market_write_lock` is held only for local SQLite schema/canonicalization, row upsert, and telemetry. Provider network fetch is outside the lock.
- One scheduler tick starts at most one source tagged as a `market_data.db` writer. Other due writers are recorded as skipped/deferred, not failed.
- `market_data.db write lock busy (timeout)` is surfaced as retryable lock contention (`skipped_lock_busy`) instead of a durable hard failure.
- No PG price sync/mirror path is reintroduced.

## Non-Goals

- No PG `prices` drop. That remains batch-3.
- No changes to price reconcile fingerprints, HAPN patch, or local price authority.
- No provider replacement or new IV/options work.
- No broad scheduler rewrite beyond market-writer backpressure.
- No SA/native-host changes.

## File Map

### New Files

- `src/prices_runtime.py`
  - Sanitized subprocess CLI for direct-local prices.
  - Supports `--source ibkr_prices` and `--source price_backfill` modes.
  - Parses explicit tickers/lookback/provider args from scheduler.
  - Calls `src.market_data_direct.backfill_prices_direct(...)`.
- `tests/test_prices_runtime.py`
  - Hermetic tests for parse, sanitized stdout, failure redaction, Gateway-lock flag, and no import-time stdout noise.

### Modified Files

- `src/service/data_scheduler.py`
  - Repoint `ibkr_prices` / `price_backfill` from in-process adapter to sanitized subprocess worker.
  - Add `writes_market_db` source metadata.
  - Add tick-level backpressure for due market writers.
  - Classify market-write lock contention as retryable skip.
- `src/market_data_direct.py`
  - Refactor `backfill_prices_direct` so provider fetch happens outside `market_write_lock`.
  - Preserve top-up semantics and per-ticker failure isolation.
- `tests/test_data_scheduler.py`
  - Scheduler argv tests for `python -m src.prices_runtime`.
  - Backpressure tests.
  - Lock-busy classification tests.
- `tests/test_market_data_direct.py`
  - Lock-granularity regression tests proving provider fetch is not executed while `market_write_lock` is held.
  - Existing top-up/canary behavior remains covered.
- `docs/design/PROJECT_PRIORITY_MAP.md`
  - Record P0-C.1 as a runtime hardening follow-up, not a roadmap rerank.
- `docs/design/PG_EXIT_P0C_PRICES_RECONCILE_CUTOVER_PLAN.md`
  - Add a short post-live note that Task 4's in-process IBKR adapter was corrected by P0-C.1.

## Task 1: Add Prices Subprocess Worker

**Files:**

- Create: `src/prices_runtime.py`
- Create: `tests/test_prices_runtime.py`

- [ ] **Step 1: Write failing parse and sanitization tests**

Create `tests/test_prices_runtime.py`:

```python
import json

import pytest


def test_prices_worker_requires_source_and_tickers():
    from src import prices_runtime as worker

    with pytest.raises(SystemExit) as caught:
        worker.parse_args([])

    assert caught.value.code == 2


def test_prices_worker_prints_sanitized_success_json(monkeypatch, capsys):
    from src import prices_runtime as worker

    monkeypatch.setattr(worker, "_apply_provider_config", lambda: None)
    monkeypatch.setattr(
        worker,
        "_run_worker",
        lambda **kwargs: {
            "provider": "ibkr",
            "tickers_scanned": 2,
            "gaps_found": 1,
            "rows_added": 26,
            "errors": {"AAPL": "raw provider response should be bounded"},
        },
    )

    code = worker.main([
        "--source", "ibkr_prices",
        "--tickers", "AAPL,NVDA",
        "--gateway-lock-held",
    ])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "succeeded"
    assert payload["provider"] == "ibkr"
    assert payload["tickers_scanned"] == 2
    assert payload["rows_added"] == 26
    assert payload["error_count"] == 1
    assert "raw provider response" not in json.dumps(payload)


def test_prices_worker_prints_sanitized_error_json(monkeypatch, capsys):
    from src import prices_runtime as worker

    monkeypatch.setattr(worker, "_apply_provider_config", lambda: None)

    def boom(**kwargs):
        raise RuntimeError("market_data.db write lock busy (timeout)")

    monkeypatch.setattr(worker, "_run_worker", boom)

    code = worker.main(["--source", "ibkr_prices", "--tickers", "AAPL"])

    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"
    assert payload["error_class"] == "RuntimeError"
    assert payload["retryable"] is True
    assert payload["error"] == "market_data.db write lock busy (timeout)"
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
pytest tests/test_prices_runtime.py -q
```

Expected: FAIL with `ImportError` because `src.prices_runtime` does not exist.

- [ ] **Step 3: Implement `src/prices_runtime.py`**

Create `src/prices_runtime.py`:

```python
from __future__ import annotations

import argparse
import json
import sys
from typing import Any


MAX_ERROR_LEN = 240


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ArkScope direct-local prices worker")
    parser.add_argument("--source", choices=("ibkr_prices", "price_backfill"), required=True)
    parser.add_argument("--tickers", required=True)
    parser.add_argument("--lookback-days", type=int, default=5)
    parser.add_argument("--provider", default="ibkr", choices=("ibkr", "polygon"))
    parser.add_argument("--gateway-lock-held", action="store_true")
    return parser.parse_args(argv)


def _apply_provider_config() -> None:
    from src.data_provider_config import apply_env

    apply_env()


def _is_retryable_error(message: str) -> bool:
    return "market_data.db write lock busy" in message


def sanitize_result(result: dict[str, Any]) -> dict[str, Any]:
    errors = result.get("errors") if isinstance(result.get("errors"), dict) else {}
    return {
        "status": "succeeded",
        "provider": result.get("provider"),
        "tickers_scanned": int(result.get("tickers_scanned") or 0),
        "gaps_found": int(result.get("gaps_found") or 0),
        "rows_added": int(result.get("rows_added") or 0),
        "error_count": len(errors),
        "error_tickers": sorted(str(k) for k in errors)[:25],
    }


def sanitize_error(exc: BaseException) -> dict[str, Any]:
    msg = str(exc)[:MAX_ERROR_LEN]
    return {
        "status": "failed",
        "error_class": exc.__class__.__name__,
        "error": msg,
        "retryable": _is_retryable_error(msg),
    }


def _run_worker(*, source: str, tickers: str, lookback_days: int, provider: str, gateway_lock_held: bool) -> dict[str, Any]:
    from src.market_data_direct import backfill_prices_direct

    return backfill_prices_direct(
        tickers_arg=tickers,
        lookback_days=lookback_days,
        provider=provider,
        acquire_gateway_lock=not gateway_lock_held,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        _apply_provider_config()
        result = _run_worker(
            source=args.source,
            tickers=args.tickers,
            lookback_days=args.lookback_days,
            provider=args.provider,
            gateway_lock_held=args.gateway_lock_held,
        )
        payload = sanitize_result(result)
        code = 0
    except Exception as exc:  # noqa: BLE001 - worker boundary sanitizes every failure
        payload = sanitize_error(exc)
        code = 1
    print(json.dumps(payload, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```bash
pytest tests/test_prices_runtime.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add src/prices_runtime.py tests/test_prices_runtime.py
git commit -m "feat: add sanitized prices worker"
```

## Task 2: Repoint Scheduler Price Sources To Worker

**Files:**

- Modify: `src/service/data_scheduler.py`
- Modify: `tests/test_data_scheduler.py`

- [ ] **Step 1: Write failing scheduler argv tests**

Add to `tests/test_data_scheduler.py`:

```python
def test_p0c1_ibkr_prices_runs_prices_worker_subprocess(monkeypatch):
    calls = []

    monkeypatch.setattr(ds, "_resolve_price_scope", lambda: ["AAPL", "NVDA"])

    def fake_worker(argv):
        calls.append(argv)
        return {
            "returncode": 0,
            "payload": {
                "status": "succeeded",
                "provider": "ibkr",
                "tickers_scanned": 2,
                "rows_added": 3,
                "error_count": 0,
            },
        }

    monkeypatch.setattr(ds, "_run_sanitized_json_subprocess", fake_worker)
    monkeypatch.setattr(ds, "_local_refresh", lambda: (_ for _ in ()).throw(AssertionError("no PG mirror")))

    res = ds.run_source("ibkr_prices")

    assert res["status"] == "succeeded"
    argv = calls[-1]
    assert argv[:3] == [sys.executable, "-m", "src.prices_runtime"]
    assert "--source" in argv and "ibkr_prices" in argv
    assert "--tickers" in argv and "AAPL,NVDA" in argv
    assert "--gateway-lock-held" in argv
    assert "collect_ibkr_prices.py" not in " ".join(argv)
    assert res["local_refresh"]["skipped"] == "direct local writer (no PG mirror)"


def test_p0c1_price_backfill_runs_prices_worker_with_planned_scope(monkeypatch):
    from src.scheduler_planner import BackfillPlan

    calls = []
    monkeypatch.setattr(ds, "_resolve_price_scope", lambda: ["AAPL", "NVDA"])
    monkeypatch.setattr(
        ds,
        "_plan_price_backfill_scope",
        lambda scope: BackfillPlan(tickers=["AAPL"], lookback_days=3, candidate_count=1),
    )
    monkeypatch.setattr(
        ds,
        "_run_sanitized_json_subprocess",
        lambda argv: calls.append(argv) or {
            "returncode": 0,
            "payload": {
                "status": "succeeded",
                "provider": "ibkr",
                "tickers_scanned": 1,
                "rows_added": 26,
                "error_count": 0,
            },
        },
    )

    res = ds.run_source("price_backfill")

    assert res["status"] == "succeeded"
    argv = calls[-1]
    assert argv[:3] == [sys.executable, "-m", "src.prices_runtime"]
    assert "--source" in argv and "price_backfill" in argv
    assert "--tickers" in argv and "AAPL" in argv
    assert "--lookback-days" in argv and "3" in argv
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
pytest tests/test_data_scheduler.py::test_p0c1_ibkr_prices_runs_prices_worker_subprocess \
       tests/test_data_scheduler.py::test_p0c1_price_backfill_runs_prices_worker_with_planned_scope -q
```

Expected: FAIL because both sources still call the in-process adapter.

- [ ] **Step 3: Repoint source execution**

In `src/service/data_scheduler.py`:

1. Keep `SourceDef.adapter` for non-IBKR REST adapters.
2. Add a new `prices_worker: bool = False` field to `SourceDef`.
3. Mark both `ibkr_prices` and `price_backfill` as prices-worker sources.
4. In `run_source`, before the generic adapter branch, build:

```python
argv = [
    sys.executable,
    "-m",
    "src.prices_runtime",
    "--source",
    source,
    "--tickers",
    ",".join(scope_or_plan_tickers),
    "--lookback-days",
    str(lookback_days),
    "--provider",
    "ibkr",
    "--gateway-lock-held",
]
step = _run_sanitized_json_subprocess(argv)
result["collect"] = step["payload"]
if step["returncode"] != 0:
    payload = step["payload"]
    raise RuntimeError(_sanitized_worker_failure_message(payload))
collected = True
```

Preserve the existing per-source and IBKR Gateway locks in `run_source`. The worker receives `--gateway-lock-held` and must not reacquire the Gateway lock.

- [ ] **Step 4: Update existing P0-C tests**

Update existing tests that currently monkeypatch `src.market_data_direct.backfill_prices_direct` through the scheduler. They should now monkeypatch `_run_sanitized_json_subprocess` and assert worker argv. Keep direct `market_data_direct` unit tests for the writer itself.

- [ ] **Step 5: Run focused scheduler tests**

Run:

```bash
pytest tests/test_data_scheduler.py::test_p0c1_ibkr_prices_runs_prices_worker_subprocess \
       tests/test_data_scheduler.py::test_p0c1_price_backfill_runs_prices_worker_with_planned_scope \
       tests/test_data_scheduler.py::test_price_backfill_serializes_behind_ibkr_lock \
       tests/test_data_scheduler.py::test_p0c_ibkr_prices_no_longer_uses_pg_sync -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 2**

```bash
git add src/service/data_scheduler.py tests/test_data_scheduler.py
git commit -m "fix: run IBKR prices through subprocess worker"
```

## Task 3: Fetch Prices Outside `market_write_lock`

**Files:**

- Modify: `src/market_data_direct.py`
- Modify: `tests/test_market_data_direct.py`

- [ ] **Step 1: Write failing lock-granularity test**

Add to `tests/test_market_data_direct.py`:

```python
def test_backfill_fetches_provider_rows_outside_market_write_lock(tmp_path, monkeypatch):
    import src.market_data_direct as mdd

    db = tmp_path / "market_data.db"
    in_lock = {"value": False}
    fetch_observed_lock = []

    @contextmanager
    def fake_market_lock(timeout=30.0, poll=0.5):
        in_lock["value"] = True
        try:
            yield
        finally:
            in_lock["value"] = False

    def fake_fetch(*args, **kwargs):
        fetch_observed_lock.append(in_lock["value"])
        return [("AAPL", "2026-07-03T10:00:00+0000", "15min", 1.0, 1.0, 1.0, 1.0, 100)]

    monkeypatch.setattr(mdd, "market_write_lock", fake_market_lock)
    monkeypatch.setattr(mdd, "_fetch_rows_for_gaps", fake_fetch)
    monkeypatch.setattr(mdd, "detect_price_gaps", lambda *a, **k: {"AAPL": ["2026-07-03"]})

    res = mdd.backfill_prices_direct(
        tickers_arg="AAPL",
        db_path=str(db),
        ibkr_src=_FakeIBKR(),
        polygon_src=None,
        today=date(2026, 7, 4),
        now_et=datetime(2026, 7, 4, 12, 0, tzinfo=ZoneInfo("US/Eastern")),
        acquire_gateway_lock=False,
    )

    assert res["rows_added"] == 1
    assert fetch_observed_lock == [False]
```

Use the existing `_FakeIBKR` helper already present in `tests/test_market_data_direct.py`; do not create a live IBKR dependency.

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
pytest tests/test_market_data_direct.py::test_backfill_fetches_provider_rows_outside_market_write_lock -q
```

Expected: FAIL because `_fetch_rows_for_gaps` currently runs while `market_write_lock` is held.

- [ ] **Step 3: Refactor writer into prepare/fetch/commit phases**

In `src/market_data_direct.py`, keep `backfill_prices_direct(...)` as the public API but refactor `_run_backfill_body` into:

```python
def _prepare_price_scope_under_lock(path: str, raw: list[str], interval: str) -> list[str]:
    with market_write_lock():
        preflight_canonicalize(path)
        conn = sqlite3.connect(path, timeout=10.0)
        try:
            conn.execute("PRAGMA busy_timeout = 10000")
            conn.executescript(_PRICES_SCHEMA)
            _ensure_provider_sync_tables(conn)
            aliases = _load_ticker_aliases(conn)
            scope, seen = [], set()
            for t in raw:
                c = aliases.get(t.upper(), t.upper())
                if c not in seen:
                    seen.add(c)
                    scope.append(c)
            return scope
        finally:
            conn.close()
```

Fetch outside the lock:

```python
buffered: dict[str, dict[str, Any]] = {}
for i, canon in enumerate(scope, 1):
    try:
        zero_bar = detect_price_gaps(
            [canon],
            interval=interval,
            lookback_days=lookback_days,
            db_path=path,
            today=end,
            now_et=now_et,
        )[canon]
        rows = _fetch_rows_for_gaps(canon, fetch_days, interval, provider, ibkr_src, polygon_src)
        buffered[canon] = {"rows": rows, "gaps": zero_bar, "error": None}
    except Exception as e:
        buffered[canon] = {"rows": [], "gaps": [], "error": str(e)}
    if progress_cb:
        progress_cb(i, total, canon)
```

Commit under a short lock:

```python
with market_write_lock():
    conn = sqlite3.connect(path, timeout=10.0)
    try:
        conn.execute("PRAGMA busy_timeout = 10000")
        conn.executescript(_PRICES_SCHEMA)
        _ensure_provider_sync_tables(conn)
        run_id = _start_provider_run(conn, provider=provider, interval=interval)
        try:
            for canon, item in buffered.items():
                rollup["tickers_scanned"] += 1
                rollup["gaps_found"] += len(item["gaps"])
                if item["error"]:
                    rollup["errors"][canon] = item["error"]
                    _upsert_provider_meta(conn, provider=provider, ticker=canon,
                                          interval=interval, last_bar_datetime=None,
                                          rows_added=0, error=item["error"])
                    continue
                added = _insert_rows(conn, item["rows"])
                rollup["rows_added"] += added
                last_bar = item["rows"][-1][1] if item["rows"] else None
                _upsert_provider_meta(conn, provider=provider, ticker=canon,
                                      interval=interval, last_bar_datetime=last_bar,
                                      rows_added=added, error=None)
            _finish_provider_run(conn, run_id, status="succeeded",
                                 tickers_scanned=rollup["tickers_scanned"],
                                 gaps_found=rollup["gaps_found"],
                                 rows_added=rollup["rows_added"], error=None)
        except Exception:
            _finish_provider_run(conn, run_id, status="failed",
                                 tickers_scanned=rollup["tickers_scanned"],
                                 gaps_found=rollup["gaps_found"],
                                 rows_added=rollup["rows_added"], error="commit failed")
            raise
    finally:
        conn.close()
```

Do not hold the market lock during provider `connect()`, `detect_price_gaps()`, or `_fetch_rows_for_gaps()`. If a commit-phase lock timeout happens, raise `TimeoutError("market_data.db write lock busy (timeout)")` unchanged so the worker can classify it retryable.

- [ ] **Step 4: Run writer tests**

Run:

```bash
pytest tests/test_market_data_direct.py -q
```

Expected: PASS. Existing top-up, canary, alias, provider fallback, and telemetry tests must continue to pass.

- [ ] **Step 5: Commit Task 3**

```bash
git add src/market_data_direct.py tests/test_market_data_direct.py
git commit -m "fix: fetch price bars outside market write lock"
```

## Task 4: Add Scheduler Market-Writer Backpressure

**Files:**

- Modify: `src/service/data_scheduler.py`
- Modify: `tests/test_data_scheduler.py`

- [ ] **Step 1: Write failing tick-level backpressure test**

Add to `tests/test_data_scheduler.py`:

```python
def test_tick_once_defers_extra_market_writers(monkeypatch):
    now = datetime(2026, 7, 4, tzinfo=timezone.utc)
    fired = []
    skipped = []

    monkeypatch.setattr(ds, "source_config", lambda source: {"enabled": source in {"ibkr_prices", "polygon_news"}, "interval_minutes": 1})
    monkeypatch.setattr(ds, "_is_due", lambda source, now: source in {"ibkr_prices", "polygon_news"})
    monkeypatch.setattr(ds, "_record_result", lambda result: skipped.append(result) or result)

    ds.tick_once(now, fire=lambda source: fired.append(source))

    assert fired == ["polygon_news"]
    assert skipped == [{
        "source": "ibkr_prices",
        "status": "skipped",
        "reason": "market_data.db writer already scheduled this tick",
        "skip_kind": "market_writer_backpressure",
    }]
```

If source iteration order differs, adjust the test to assert exactly one market writer fires and the other is skipped. The invariant is one market writer per tick, not a specific source priority unless the implementation defines one.

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
pytest tests/test_data_scheduler.py::test_tick_once_defers_extra_market_writers -q
```

Expected: FAIL because `tick_once()` currently fires every due source.

- [ ] **Step 3: Add source metadata and tick gate**

Extend `SourceDef`:

```python
writes_market_db: bool = False
```

Set `writes_market_db=True` for:

- `polygon_news`
- `finnhub_news`
- `ibkr_news`
- `ibkr_prices`
- `price_backfill`

Do not set it for retired `local_incremental`.

Change `tick_once()`:

```python
market_writer_fired = False
for source, d in SOURCES.items():
    if not _is_due(source, now):
        continue
    if d.writes_market_db and market_writer_fired:
        _record_result({
            "source": source,
            "status": "skipped",
            "reason": "market_data.db writer already scheduled this tick",
            "skip_kind": "market_writer_backpressure",
        })
        continue
    fired.append(source)
    if d.writes_market_db:
        market_writer_fired = True
    if fire is not None:
        fire(source)
    else:
        threading.Thread(
            target=run_source, args=(source, "scheduler"),
            name=f"sched-{source}", daemon=True,
        ).start()
```

This is tick-level backpressure only. Existing per-source locks and IBKR locks still protect concurrent manual/API runs.

- [ ] **Step 4: Run scheduler tests**

Run:

```bash
pytest tests/test_data_scheduler.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 4**

```bash
git add src/service/data_scheduler.py tests/test_data_scheduler.py
git commit -m "fix: add market writer scheduler backpressure"
```

## Task 5: Classify Lock-Busy As Retryable Skip

**Files:**

- Modify: `src/service/data_scheduler.py`
- Modify: `apps/arkscope-web/src/marketDataDisplay.ts` only if backend status vocabulary needs frontend label changes.
- Modify: `tests/test_data_scheduler.py`
- Modify: `apps/arkscope-web/src/marketDataDisplay.test.ts` only if frontend label changes are made.

- [ ] **Step 1: Write failing worker retryable classification test**

Add to `tests/test_data_scheduler.py`:

```python
def test_prices_worker_retryable_lock_busy_is_skip_not_failure(monkeypatch):
    monkeypatch.setattr(ds, "_resolve_price_scope", lambda: ["AAPL"])
    monkeypatch.setattr(
        ds,
        "_run_sanitized_json_subprocess",
        lambda argv: {
            "returncode": 1,
            "payload": {
                "status": "failed",
                "error_class": "TimeoutError",
                "error": "market_data.db write lock busy (timeout)",
                "retryable": True,
            },
        },
    )

    res = ds.run_source("ibkr_prices")

    assert res["status"] == "skipped"
    assert res["skip_kind"] == "skipped_lock_busy"
    assert "write lock busy" in res["reason"]
    row = ds._state_store().get("ibkr_prices")
    assert row["last_status"] == "skipped"
    assert row["last_error"] is None
    assert row["last_result"]["skip_kind"] == "skipped_lock_busy"
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
pytest tests/test_data_scheduler.py::test_prices_worker_retryable_lock_busy_is_skip_not_failure -q
```

Expected: FAIL because worker nonzero currently becomes a failed scheduler outcome.

- [ ] **Step 3: Implement retryable skip handling**

In `run_source`, when sanitized worker payload has `retryable: true`, make the terminal scheduler outcome a skip, not a failure:

```python
result.update({
    "source": source,
    "status": "skipped",
    "reason": payload.get("error") or "retryable worker failure",
    "skip_kind": "skipped_lock_busy",
})
ok = True
error = None
collected = True
```

Do not return before the common outcome block. The run has already passed `record_attempt()`, so returning directly would leave durable `scheduler_state.last_status='running'`. Let the common `_state_store().record_outcome(... status='skipped' ...)` path persist the skip and clear stale errors.

Also ensure PG `job_runs` telemetry stores this as a non-failed result:

```python
finish_status = "failed" if result["status"] == "failed" else "succeeded"
store.finish_run(run_id, status=finish_status, message=None if finish_status == "succeeded" else error, error=error, result=result)
```

This must happen before any generic exception handler turns the payload into `failed`.

- [ ] **Step 4: Run focused tests**

Run:

```bash
pytest tests/test_data_scheduler.py::test_prices_worker_retryable_lock_busy_is_skip_not_failure \
       tests/test_data_scheduler.py::test_skip_does_not_overwrite_durable_outcome -q
```

If frontend display vocabulary changed, run the frontend test from `apps/arkscope-web`:

```bash
npm test -- marketDataDisplay.test.ts
```

Expected: PASS. If frontend display vocabulary is unchanged, no frontend files should be modified.

- [ ] **Step 5: Commit Task 5**

```bash
git add src/service/data_scheduler.py tests/test_data_scheduler.py
git commit -m "fix: classify price lock contention as retryable skip"
```

## Task 6: Runtime Smoke, Docs, and Operator Guidance

**Files:**

- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`
- Modify: `docs/design/PG_EXIT_P0C_PRICES_RECONCILE_CUTOVER_PLAN.md`
- Modify: `docs/design/PG_EXIT_COMPLETION_PLAN.md` if runtime status wording currently implies prices are fully soaked.

- [ ] **Step 1: Run offline focused gate**

Run:

```bash
pytest tests/test_prices_runtime.py tests/test_data_scheduler.py tests/test_market_data_direct.py tests/test_provider_health.py -q
```

Expected: PASS.

- [ ] **Step 2: Run frontend gate if status labels changed**

If frontend files changed, run:

```bash
cd apps/arkscope-web
npm test
npm run build
```

Expected: all frontend tests pass and build succeeds.

- [ ] **Step 3: Run one live scheduler smoke with IBKR prices disabled unless explicitly approved**

Default live smoke after merge:

1. Keep `ibkr_prices` and `price_backfill` disabled until code is merged.
2. Enable SA auto sync and non-IBKR sources if desired.
3. Run one scheduler tick / restart sidecar.
4. Verify Data Sources no longer shows market-write lock failures for news.

Optional IBKR prices smoke after user approval:

1. Enable only `ibkr_prices`.
2. Trigger Run Now once.
3. Expect either:
   - `succeeded` with sanitized worker payload, or
   - `skipped` with `skip_kind=skipped_lock_busy` / IBKR busy, not thread event-loop failure.

- [ ] **Step 4: Update docs**

Append to the P0-C plan live notes:

```markdown
### P0-C.1 Runtime Hardening

First scheduler resume after P0-C exposed that `ibkr_prices` and `price_backfill` cannot run
as in-process adapters in scheduler threads because `ib_insync` expects an event loop. P0-C.1
moved both through `python -m src.prices_runtime`, shortened `market_write_lock` holds by
fetching provider rows before the commit lock, and added market-writer backpressure so a
restored scheduler does not launch several local DB writers in one tick.
```

Add a newest-first decision log entry to `PROJECT_PRIORITY_MAP.md` §10 with:

- observed three live errors,
- root cause,
- fix summary,
- confirmation that this is P0-C runtime hardening, not roadmap rerank.

- [ ] **Step 5: Commit Task 6**

```bash
git add docs/design/PROJECT_PRIORITY_MAP.md docs/design/PG_EXIT_P0C_PRICES_RECONCILE_CUTOVER_PLAN.md docs/design/PG_EXIT_COMPLETION_PLAN.md
git commit -m "docs: record P0-C prices runtime hardening"
```

## Review Gates

Before merge:

```bash
pytest tests/test_prices_runtime.py tests/test_data_scheduler.py tests/test_market_data_direct.py tests/test_provider_health.py -q
```

If frontend changed:

```bash
cd apps/arkscope-web
npm test
npm run build
```

After merge but before re-enabling IBKR price schedules:

- `ibkr_prices` disabled.
- `price_backfill` disabled.
- SA sync may be enabled independently.
- Scheduler restart should not produce new market lock failures from news.

After optional IBKR price smoke:

- No `There is no current event loop in thread 'sched-ibkr_prices'`.
- No raw provider output in scheduler status.
- Lock contention appears as skipped/deferred, not durable failed.

## Self-Review Notes

- This plan covers both `ibkr_prices` and `price_backfill`.
- It treats existing scheduler comments about IBKR subprocess isolation as a hard constraint.
- It does not reintroduce PG price sync or PG fallback.
- It moves fetch outside `market_write_lock`, addressing the structural lock starvation rather than only adding timeouts.
- It leaves normalized IBKR news TimeoutError classification for a later slice unless it persists after lock starvation is removed.
