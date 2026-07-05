# P0-C Prices Reconcile + Direct-Local Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove whether local `market_data.db.prices` is already the correct authority, then cut price ingest/reads away from PostgreSQL without bulk-copying PG rows unless the audit proves a real local gap.

**Architecture:** Audit first, write after evidence. P0-C starts with a read-only reconcile packet over PG `prices` and local SQLite `prices`, then promotes the existing direct-local price writer to the scheduled authority, retires the PG mirror/refresh path, and flips price reads to local-only. Physical PG `prices` drop is a separate batch-3 destructive operation, not part of P0-C.

**Tech Stack:** Python, SQLite, PostgreSQL/psycopg2 read-only audit, FastAPI routes, scheduler `SourceDef`, existing `src.market_data_direct` direct writer, existing `market_write_lock` / `ibkr_gateway_lock`, pytest.

---

## Map Check

`PROJECT_PRIORITY_MAP.md` P0-C is now **Prices Reconcile + Direct-Local Cutover**, not "prices migration". The live pre-plan measurement changed the premise:

- Local `data/market_data.db.prices`: `2,324,172` rows / `149` tickers.
- PG `prices`: `2,314,293` rows / `150` tickers.
- Both sides are `15min` only and end at `2026-07-02T14:15`.
- The likely explanation is the 2026-06-27 LC→HAPN alias/history stitch applied locally, but this plan treats that as a falsifiable hypothesis, not an assumption.

This plan implements the user's locked ruling:

1. Reconcile first by `(ticker, interval, datetime)` and explain PG-only/local-only rows.
2. Do not bulk copy unless the audit proves a real local gap.
3. Main work is ingest cutover: pause → final reconcile → flip writer → resume.
4. Retire price mirror/fallback in P0-C.
5. PG `prices` drop is batch-3, with N9-style dump/restore/drop approval.

Batch-2 `job_runs` cleanup can run during this plan's calendar time; P0-C must not touch `job_runs`.

## Current Grounding

### Active Local Price Authority

`src/market_data_admin.py` defines the local schema:

```sql
CREATE TABLE IF NOT EXISTS prices (
    ticker    TEXT NOT NULL,
    datetime  TEXT NOT NULL,
    interval  TEXT NOT NULL,
    open      REAL,
    high      REAL,
    low       REAL,
    close     REAL,
    volume    INTEGER,
    PRIMARY KEY (ticker, datetime, interval)
);
CREATE INDEX IF NOT EXISTS idx_prices_ticker_interval_dt
ON prices(ticker, interval, datetime);
```

`src/market_data_direct.py` already has the direct provider→SQLite path:

- `backfill_prices_direct(...)`
- `market_write_lock()`
- `provider_sync_runs` / `provider_sync_meta`
- IBKR primary + Polygon fallback
- canonicalization through `ticker_aliases`
- top-up / `INSERT OR IGNORE` behavior

### Remaining PG Price Seams

The current PG-dependent price seams are:

- `src/service/data_scheduler.py`
  - `ibkr_prices`: `collect_ibkr_prices.py --incremental --minute-only` → `--prices` PG sync → `_local_refresh()`
  - `local_incremental`: calls `_local_refresh()`
  - `_local_refresh()`: calls `incremental_update(domains=("prices",))`
- `src/market_data_admin.py`
  - `_incr_prices(...)`
  - `incremental_update(... domains=("prices",))`
  - `market_sync_meta`
  - old bootstrap/validate pricing comparison paths already partly retired by N9.
- `src/tools/backends/local_market_backend.py`
  - `query_prices(...)` falls back to `DatabaseBackend.query_prices(...)` unless market strict mode is on.
- `src/tools/backends/db_backend.py`
  - `query_prices(...)`, `get_available_tickers("prices")`, `query_health_stats()` still reference PG `prices`.
- `src/api/routes/market_data.py`
  - manual update currently still requests `("prices",)`.
  - `/market-data/status` still reports `pg_fallback_active` for market routing.

### Existing Direct Path Is Not Yet the Authority

`price_backfill` exists and is direct-local, but it is default-off and gap-planned. P0-C must decide whether to:

1. make `price_backfill` the recurring scheduled source, or
2. introduce a new named source such as `price_direct_incremental` that wraps the same direct writer with official cutover semantics.

The default should be the least new code that keeps operator intent obvious.

## Desired End State

After P0-C:

- Local `market_data.db.prices` is the runtime price authority.
- PG `prices` is archive/rollback basis only.
- No runtime scheduler/API/tool read path silently falls back to PG `prices`.
- No runtime source writes price data through PG/mirror.
- Manual `/market-data/update` no longer starts the PG price mirror.
- `market_sync_meta['prices']` is no longer a live freshness signal; direct provider telemetry is `provider_sync_*`.
- Price routes, agent price tools, coverage/status, sector performance, health, and UI price charts read local-only and return honest empty/unavailable on local misses.
- PG `prices` remains present until batch-3. P0-C does not drop it.

## Non-Goals

- No PG `prices` drop. That is batch-3 and must use a separate N9-style dump/restore/drop gate.
- No `job_runs` cleanup. Batch-2 handles PG `job_runs` after soak.
- No provider survey or replacement of IBKR/Polygon.
- No rewrite of price analytics, rollup definitions, or UI chart behavior except the local-only authority change.
- No bulk copy by default. Any backfill from PG must be explicitly justified by the reconcile report.
- No dual-write period. Cutover is pause → final reconcile → flip → resume.

## File Map

### New Files

- `src/prices_reconcile.py`
  - Pure price-key comparison and report fingerprint helpers.
  - No live connection creation.
- `scripts/migration/p0c_prices_reconcile.py`
  - Read-only CLI for live reconcile preview.
  - Reads PG and SQLite, emits deterministic JSON.
  - Later live gates call this; it never writes.
- `tests/test_prices_reconcile.py`
  - Hermetic unit tests for diff classification, alias proof, fingerprint stability, and no-bulk-copy gate.
- `docs/design/PG_EXIT_P0C_PRICES_RECONCILE_CUTOVER_PLAN.md`
  - This plan.

### Modified Files During Implementation

- `src/service/data_scheduler.py`
  - Promote direct-local price source; retire `ibkr_prices` PG sync and `local_incremental` price mirror behavior.
- `src/market_data_admin.py`
  - Retire `incremental_update(... prices ...)`, `_incr_prices`, and `market_sync_meta` price authority after direct-local cutover.
- `src/tools/backends/local_market_backend.py`
  - Remove PG `query_prices` fallback under the post-P0-C local authority.
- `src/tools/backends/db_backend.py`
  - Mark PG price methods as invalidated rollback/dead paths after P0-C; physical removal belongs to batch-3 cleanup.
- `src/api/routes/market_data.py`
  - Manual update should route to direct-local price refresh or reject the retired PG mirror.
  - Status should explain local price authority and direct provider telemetry.
- `src/api/routes/prices.py`, `src/tools/price_tools.py`
  - Usually no code change; included in smoke/parity gates.
- `tests/test_data_scheduler.py`
- `tests/test_market_data_admin.py`
- `tests/test_sqlite_backend.py`
- `tests/test_db_backend.py`
- `tests/test_api.py`
- `tests/test_provider_health.py`
- `tests/test_trading_day_coverage.py`

## Core Gate Semantics

### G1. Reconcile Fingerprint

The read-only reconcile report must include:

- PG count, ticker count, interval distribution, min/max datetime.
- SQLite count, ticker count, interval distribution, min/max datetime.
- PG-only rows grouped by `(ticker, interval)`.
- Local-only rows grouped by `(ticker, interval)`.
- Alias-aware projection:
  - raw PG key `(ticker, interval, datetime)`
  - canonical PG key `(canonical_ticker, interval, datetime)` using local `ticker_aliases`
  - local key `(ticker, interval, datetime)`
- LC→HAPN and BRK.B→BRK B focused checks.
- Per-`(ticker, interval)` OHLCV checksum comparison over common buckets.
  - The checksum input must include `datetime`, `open`, `high`, `low`, `close`, `volume`, sorted by `datetime`.
  - `value_checksum_mismatch_count` must be reviewed separately from key coverage.
  - Expected live result is zero mismatched buckets; any mismatch blocks the "local is authority" declaration until explained.
- Example rows for each unexplained bucket, sanitized to key + OHLCV only.
- A deterministic fingerprint over the sorted report.

### G2. Bulk Copy Ban

The plan must refuse bulk copy unless all of the following are true:

1. `unexplained_pg_only_rows > 0`
2. each unexplained row is absent after alias/canonical projection
3. rows are within a reviewed date/ticker scope
4. the operator approves a deterministic small backfill plan

If `pg_only_rows` are fully explained by alias/canonicalization or already present locally under canonical keys, the implementation must not copy PG rows into SQLite.

### G3. Cutover Order

Cutover order is fixed:

1. Pause scheduler/manual price writes.
2. Run reconcile preview twice and require byte-identical reports.
3. Reviewer independently validates counts and difference buckets.
4. If needed, apply only reviewed deterministic backfill.
5. Run final reconcile.
6. Flip scheduler/writer/read routing to direct-local/local-only.
7. Resume scheduler.
8. Observe one full price cycle and run app smoke.

No dual-write. No "time-window looks quiet" shortcut. No stale fingerprint apply.

### G4. Drop Boundary

PG `prices` remains excluded after P0-C. Batch-3 must consciously invert N9's `EXCLUDED_TABLES` protection and produce a fresh dump/restore/drop approval packet.

## Task 1: Read-Only Reconcile Model

**Files:**

- Create: `src/prices_reconcile.py`
- Create: `tests/test_prices_reconcile.py`

- [ ] **Step 1: Write failing tests for deterministic price keys and alias classification**

Add to `tests/test_prices_reconcile.py`:

```python
from src.prices_reconcile import (
    PriceKey,
    classify_price_differences,
    compare_value_checksums,
    fingerprint_report,
)


def test_alias_projection_explains_pg_only_lc_rows():
    pg_rows = {
        PriceKey("LC", "15min", "2026-01-02T14:30:00+0000"),
    }
    local_rows = {
        PriceKey("HAPN", "15min", "2026-01-02T14:30:00+0000"),
    }
    report = classify_price_differences(
        pg_rows=pg_rows,
        local_rows=local_rows,
        aliases={"LC": "HAPN"},
    )

    assert report.unexplained_pg_only == ()
    assert report.alias_explained_pg_only == (
        {
            "pg_key": ("LC", "15min", "2026-01-02T14:30:00+0000"),
            "canonical_key": ("HAPN", "15min", "2026-01-02T14:30:00+0000"),
            "reason": "pg_alias_matches_local_canonical",
        },
    )


def test_unexplained_pg_only_blocks_no_bulk_copy_gate():
    pg_rows = {PriceKey("MSFT", "15min", "2026-01-02T14:30:00+0000")}
    local_rows = set()
    report = classify_price_differences(pg_rows=pg_rows, local_rows=local_rows, aliases={})

    assert report.unexplained_pg_only == (
        ("MSFT", "15min", "2026-01-02T14:30:00+0000"),
    )
    assert report.bulk_copy_allowed is False


def test_reconcile_fingerprint_is_order_stable():
    first = {
        "pg_only_by_ticker": {"LC": 2, "AAPL": 1},
        "local_only_by_ticker": {"HAPN": 3},
    }
    second = {
        "local_only_by_ticker": {"HAPN": 3},
        "pg_only_by_ticker": {"AAPL": 1, "LC": 2},
    }

    assert fingerprint_report(first) == fingerprint_report(second)


def test_value_checksum_mismatch_is_reported_by_bucket():
    mismatches = compare_value_checksums(
        pg_checksums={
            ("NVDA", "15min", "2026-01-02T14:30:00+0000"): "pg-hash",
            ("AAPL", "15min", "2026-01-02T14:30:00+0000"): "same",
        },
        local_checksums={
            ("NVDA", "15min", "2026-01-02T14:30:00+0000"): "local-hash",
            ("AAPL", "15min", "2026-01-02T14:30:00+0000"): "same",
        },
    )

    assert mismatches == (
        {
            "bucket": ("NVDA", "15min"),
            "mismatch_count": 1,
            "reason": "ohlcv_checksum_mismatch",
            "samples": (
                {
                    "key": ("NVDA", "15min", "2026-01-02T14:30:00+0000"),
                    "pg_checksum": "pg-hash",
                    "local_checksum": "local-hash",
                },
            ),
        },
    )


def test_value_checksum_ignores_single_sided_keys():
    mismatches = compare_value_checksums(
        pg_checksums={
            ("MSFT", "15min", "2026-01-02T14:30:00+0000"): "pg-only",
            ("AAPL", "15min", "2026-01-02T14:30:00+0000"): "same",
        },
        local_checksums={
            ("AAPL", "15min", "2026-01-02T14:30:00+0000"): "same",
            ("NVDA", "15min", "2026-01-02T14:30:00+0000"): "local-only",
        },
    )

    assert mismatches == ()
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
pytest tests/test_prices_reconcile.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'src.prices_reconcile'`.

- [ ] **Step 3: Implement pure model helpers**

Create `src/prices_reconcile.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Iterable, Mapping, Sequence


@dataclass(frozen=True, order=True)
class PriceKey:
    ticker: str
    interval: str
    datetime: str

    def as_tuple(self) -> tuple[str, str, str]:
        return (self.ticker, self.interval, self.datetime)

    def canonical(self, aliases: Mapping[str, str]) -> "PriceKey":
        return PriceKey(aliases.get(self.ticker, self.ticker), self.interval, self.datetime)


@dataclass(frozen=True)
class PriceDiffReport:
    alias_explained_pg_only: tuple[dict[str, object], ...]
    unexplained_pg_only: tuple[tuple[str, str, str], ...]
    local_only: tuple[tuple[str, str, str], ...]
    bulk_copy_allowed: bool


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def fingerprint_report(report: Mapping[str, object]) -> str:
    return hashlib.sha256(_canonical_json(report).encode("utf-8")).hexdigest()


def compare_value_checksums(
    *,
    pg_checksums: Mapping[tuple[str, str, str], str],
    local_checksums: Mapping[tuple[str, str, str], str],
    sample_limit: int = 5,
) -> tuple[dict[str, object], ...]:
    by_bucket: dict[tuple[str, str], dict[str, object]] = {}
    common_keys = sorted(set(pg_checksums) & set(local_checksums))
    for key in common_keys:
        if pg_checksums[key] == local_checksums[key]:
            continue
        bucket = (key[0], key[1])
        entry = by_bucket.setdefault(
            bucket,
            {"bucket": bucket, "mismatch_count": 0, "reason": "ohlcv_checksum_mismatch", "samples": []},
        )
        entry["mismatch_count"] = int(entry["mismatch_count"]) + 1
        samples = entry["samples"]
        assert isinstance(samples, list)
        if len(samples) < sample_limit:
            samples.append({"key": key, "pg_checksum": pg_checksums[key], "local_checksum": local_checksums[key]})
    return tuple(
        {
            "bucket": entry["bucket"],
            "mismatch_count": entry["mismatch_count"],
            "reason": entry["reason"],
            "samples": tuple(entry["samples"]),
        }
        for _, entry in sorted(by_bucket.items())
    )


def classify_price_differences(
    *,
    pg_rows: Iterable[PriceKey],
    local_rows: Iterable[PriceKey],
    aliases: Mapping[str, str],
) -> PriceDiffReport:
    pg_set = set(pg_rows)
    local_set = set(local_rows)
    local_canon = {row.as_tuple() for row in local_set}
    alias_explained = []
    unexplained = []

    for row in sorted(pg_set - local_set):
        canonical = row.canonical(aliases)
        if canonical.as_tuple() in local_canon and canonical != row:
            alias_explained.append({
                "pg_key": row.as_tuple(),
                "canonical_key": canonical.as_tuple(),
                "reason": "pg_alias_matches_local_canonical",
            })
        else:
            unexplained.append(row.as_tuple())

    return PriceDiffReport(
        alias_explained_pg_only=tuple(alias_explained),
        unexplained_pg_only=tuple(unexplained),
        local_only=tuple(row.as_tuple() for row in sorted(local_set - pg_set)),
        bulk_copy_allowed=False,
    )
```

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```bash
pytest tests/test_prices_reconcile.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/prices_reconcile.py tests/test_prices_reconcile.py
git commit -m "feat: add prices reconcile model"
```

## Task 2: Read-Only Reconcile CLI

**Files:**

- Create: `scripts/migration/p0c_prices_reconcile.py`
- Modify: `tests/test_prices_reconcile.py`

- [ ] **Step 1: Write failing CLI tests**

Add to `tests/test_prices_reconcile.py`:

```python
import json
from pathlib import Path
from types import SimpleNamespace


def test_reconcile_cli_writes_deterministic_report(tmp_path, monkeypatch, capsys):
    from scripts.migration import p0c_prices_reconcile as cli

    output = tmp_path / "report.json"
    monkeypatch.setattr(cli, "load_pg_snapshot", lambda _url: {
        "summary": {
            "row_count": 1,
            "ticker_count": 1,
            "intervals": {"15min": 1},
            "min_datetime": "2026-01-02T14:30:00+0000",
            "max_datetime": "2026-01-02T14:30:00+0000",
        },
        "keys": [("LC", "15min", "2026-01-02T14:30:00+0000")],
        "value_checksums": {("LC", "15min", "2026-01-02T14:30:00+0000"): "pg-lc-hash"},
        "samples": [],
    })
    monkeypatch.setattr(cli, "load_sqlite_snapshot", lambda _db: {
        "summary": {
            "row_count": 1,
            "ticker_count": 1,
            "intervals": {"15min": 1},
            "min_datetime": "2026-01-02T14:30:00+0000",
            "max_datetime": "2026-01-02T14:30:00+0000",
        },
        "keys": [("HAPN", "15min", "2026-01-02T14:30:00+0000")],
        "value_checksums": {("HAPN", "15min", "2026-01-02T14:30:00+0000"): "local-hapn-hash"},
        "aliases": {"LC": "HAPN"},
        "samples": [],
    })

    code = cli.main([
        "preview",
        "--database-url", "postgres://secret@example/db",
        "--market-db", str(tmp_path / "market_data.db"),
        "--output", str(output),
    ])

    stdout = capsys.readouterr().out
    report = json.loads(output.read_text(encoding="utf-8"))
    assert code == 0
    assert "secret" not in stdout
    assert report["unexplained_pg_only_count"] == 0
    assert report["alias_explained_pg_only_count"] == 1
    assert len(report["fingerprint"]) == 64
```

- [ ] **Step 2: Run the CLI test and verify RED**

Run:

```bash
pytest tests/test_prices_reconcile.py::test_reconcile_cli_writes_deterministic_report -q
```

Expected: FAIL with `ImportError` for `scripts.migration.p0c_prices_reconcile`.

- [ ] **Step 3: Implement read-only CLI**

Create `scripts/migration/p0c_prices_reconcile.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from src.prices_reconcile import (
    PriceKey,
    classify_price_differences,
    compare_value_checksums,
    fingerprint_report,
)


PRICE_KEY_SQL = """
SELECT ticker, interval, datetime
FROM prices
WHERE interval = '15min'
ORDER BY ticker, interval, datetime
"""

PRICE_VALUE_SQL = """
SELECT ticker, interval, datetime, open, high, low, close, volume
FROM prices
WHERE interval = '15min'
ORDER BY ticker, interval, datetime
"""

FULL_UNEXPLAINED_KEY_LIMIT = 5000


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def connect_pg(database_url: str):
    import psycopg2

    return psycopg2.connect(database_url)


def _value_checksum_rows(rows: Iterable[tuple[object, ...]]) -> dict[tuple[str, str, str], str]:
    checksums = {}
    for ticker, interval, dt, open_, high, low, close, volume in rows:
        key = (str(ticker), str(interval), str(dt))
        h = hashlib.sha256()
        h.update(_canonical_json([str(dt), str(open_), str(high), str(low), str(close), str(volume)]).encode("utf-8"))
        checksums[key] = h.hexdigest()
    return dict(sorted(checksums.items()))


def _count_by_ticker(keys: Iterable[tuple[str, str, str]]) -> dict[str, int]:
    return dict(sorted(Counter(key[0] for key in keys).items()))


def _json_ready(value: object) -> object:
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    return value


def load_pg_snapshot(database_url: str) -> dict[str, Any]:
    conn = connect_pg(database_url)
    try:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL statement_timeout = '120s'")
            cur.execute("""
                SELECT COUNT(*), COUNT(DISTINCT ticker), MIN(datetime), MAX(datetime)
                FROM prices
            """)
            row_count, ticker_count, min_dt, max_dt = cur.fetchone()
            cur.execute("SELECT interval, COUNT(*) FROM prices GROUP BY interval ORDER BY interval")
            intervals = {str(k): int(v) for k, v in cur.fetchall()}
            cur.execute("""
                SELECT ticker, interval,
                       TO_CHAR(datetime AT TIME ZONE 'UTC',
                               'YYYY-MM-DD"T"HH24:MI:SS+0000') AS datetime
                FROM prices
                WHERE interval = '15min'
                ORDER BY ticker, interval, datetime
            """)
            keys = [(str(t), str(i), str(dt)) for t, i, dt in cur.fetchall()]
            cur.execute("""
                SELECT ticker, interval,
                       TO_CHAR(datetime AT TIME ZONE 'UTC',
                               'YYYY-MM-DD"T"HH24:MI:SS+0000') AS datetime,
                       open, high, low, close, volume
                FROM prices
                WHERE interval = '15min'
                ORDER BY ticker, interval, datetime
            """)
            value_checksums = _value_checksum_rows(cur.fetchall())
    finally:
        conn.close()
    return {
        "summary": {
            "row_count": int(row_count),
            "ticker_count": int(ticker_count),
            "intervals": intervals,
            "min_datetime": str(min_dt),
            "max_datetime": str(max_dt),
        },
        "keys": keys,
        "value_checksums": value_checksums,
        "samples": [],
    }


def load_sqlite_snapshot(market_db: str | Path) -> dict[str, Any]:
    uri = f"{Path(market_db).resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        row_count, ticker_count, min_dt, max_dt = conn.execute(
            "SELECT COUNT(*), COUNT(DISTINCT ticker), MIN(datetime), MAX(datetime) FROM prices"
        ).fetchone()
        intervals = dict(conn.execute(
            "SELECT interval, COUNT(*) FROM prices GROUP BY interval ORDER BY interval"
        ).fetchall())
        keys = [tuple(row) for row in conn.execute(PRICE_KEY_SQL).fetchall()]
        value_checksums = _value_checksum_rows(conn.execute(PRICE_VALUE_SQL).fetchall())
        aliases = {}
        if conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='ticker_aliases'"
        ).fetchone():
            aliases = {
                str(alias): str(canonical)
                for alias, canonical in conn.execute(
                    "SELECT alias, canonical FROM ticker_aliases ORDER BY alias"
                ).fetchall()
            }
    finally:
        conn.close()
    return {
        "summary": {
            "row_count": int(row_count),
            "ticker_count": int(ticker_count),
            "intervals": {str(k): int(v) for k, v in intervals.items()},
            "min_datetime": str(min_dt),
            "max_datetime": str(max_dt),
        },
        "keys": keys,
        "value_checksums": value_checksums,
        "aliases": aliases,
        "samples": [],
    }


def build_report(*, pg_snapshot: Mapping[str, Any], local_snapshot: Mapping[str, Any]) -> dict[str, Any]:
    diff = classify_price_differences(
        pg_rows=[PriceKey(*row) for row in pg_snapshot["keys"]],
        local_rows=[PriceKey(*row) for row in local_snapshot["keys"]],
        aliases=local_snapshot.get("aliases", {}),
    )
    value_mismatches = compare_value_checksums(
        pg_checksums=pg_snapshot["value_checksums"],
        local_checksums=local_snapshot["value_checksums"],
    )
    alias_explained_pg_keys = [tuple(item["pg_key"]) for item in diff.alias_explained_pg_only]
    pg_only_keys = [*alias_explained_pg_keys, *diff.unexplained_pg_only]
    unexplained_keys_truncated = len(diff.unexplained_pg_only) > FULL_UNEXPLAINED_KEY_LIMIT
    report = {
        "schema_version": 1,
        "scope": "p0c_prices_reconcile",
        "pg_summary": pg_snapshot["summary"],
        "local_summary": local_snapshot["summary"],
        "alias_explained_pg_only_count": len(diff.alias_explained_pg_only),
        "unexplained_pg_only_count": len(diff.unexplained_pg_only),
        "local_only_count": len(diff.local_only),
        "pg_only_by_ticker": _count_by_ticker(pg_only_keys),
        "alias_explained_pg_only_by_ticker": _count_by_ticker(alias_explained_pg_keys),
        "unexplained_pg_only_by_ticker": _count_by_ticker(diff.unexplained_pg_only),
        "local_only_by_ticker": _count_by_ticker(diff.local_only),
        "unexplained_pg_only_keys": [] if unexplained_keys_truncated else list(diff.unexplained_pg_only),
        "unexplained_pg_only_keys_truncated": unexplained_keys_truncated,
        "value_checksum_mismatch_count": len(value_mismatches),
        "value_checksum_mismatch_row_count": sum(int(item["mismatch_count"]) for item in value_mismatches),
        "bulk_copy_allowed": diff.bulk_copy_allowed,
        "alias_explained_pg_only_samples": list(diff.alias_explained_pg_only[:20]),
        "unexplained_pg_only_samples": list(diff.unexplained_pg_only[:20]),
        "local_only_samples": list(diff.local_only[:20]),
        "value_checksum_mismatch_samples": list(value_mismatches[:20]),
    }
    report = _json_ready(report)
    assert isinstance(report, dict)
    report["fingerprint"] = fingerprint_report(report)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P0-C read-only prices reconcile preview")
    sub = parser.add_subparsers(dest="cmd", required=True)
    preview = sub.add_parser("preview")
    preview.add_argument("--database-url", required=True)
    preview.add_argument("--market-db", required=True)
    preview.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    if args.cmd == "preview":
        report = build_report(
            pg_snapshot=load_pg_snapshot(args.database_url),
            local_snapshot=load_sqlite_snapshot(args.market_db),
        )
        Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({
            "status": "previewed",
            "fingerprint": report["fingerprint"],
            "unexplained_pg_only_count": report["unexplained_pg_only_count"],
            "value_checksum_mismatch_count": report["value_checksum_mismatch_count"],
        }, sort_keys=True))
        return 0
    parser.error(f"unknown command: {args.cmd}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```bash
pytest tests/test_prices_reconcile.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/prices_reconcile.py scripts/migration/p0c_prices_reconcile.py tests/test_prices_reconcile.py
git commit -m "feat: add prices reconcile preview"
```

## Task 3: Live Audit Gate

**Files:**

- Modify: `docs/design/PG_EXIT_P0C_PRICES_RECONCILE_CUTOVER_PLAN.md`
- Output during execution: `scratchpad/p0c-prices-reconcile-1.json`, `scratchpad/p0c-prices-reconcile-2.json`

- [ ] **Step 1: Ensure `scratchpad/` is ignored**

Run:

```bash
git check-ignore -q scratchpad || printf '\nscratchpad/\n' >> .gitignore
```

If `.gitignore` changes, commit it separately:

```bash
git add .gitignore
git commit -m "chore: ignore scratchpad artifacts"
```

- [ ] **Step 2: Pause price writers**

Before running live audit, pause:

- scheduler
- manual `/market-data/update`
- any `price_backfill`
- any old `ibkr_prices`
- any manual `collect_ibkr_prices.py`

Verify with:

```bash
ps -eo pid,ppid,etimes,stat,cmd | rg 'data_scheduler|collect_ibkr_prices|price_backfill|p0c_prices_reconcile' || true
```

Expected: no active writer except the current read-only `p0c_prices_reconcile` process when it is running.

- [ ] **Step 3: Run preview twice**

Run:

```bash
PY=/home/hyl/.virtualenvs/llm_app/bin/python3
DB=/mnt/md0/PycharmProjects/ArkScope/data/market_data.db
OUT1=scratchpad/p0c-prices-reconcile-1.json
OUT2=scratchpad/p0c-prices-reconcile-2.json

"$PY" scripts/migration/p0c_prices_reconcile.py preview \
  --database-url "$DATABASE_URL" \
  --market-db "$DB" \
  --output "$OUT1"

"$PY" scripts/migration/p0c_prices_reconcile.py preview \
  --database-url "$DATABASE_URL" \
  --market-db "$DB" \
  --output "$OUT2"

cmp "$OUT1" "$OUT2"
```

Expected: `cmp` exits `0`.

- [ ] **Step 4: Reviewer must verify the report**

Reviewer checks:

- `pg_summary.row_count == 2,314,293` or explains drift.
- `local_summary.row_count == 2,324,172` or explains drift.
- `unexplained_pg_only_count == 0` to skip bulk copy.
- If `unexplained_pg_only_count > 0`, review samples and grouping before any implementation can proceed.
- `value_checksum_mismatch_count == 0`; any OHLCV mismatch bucket blocks cutover until explained.
- LC→HAPN appears in `alias_explained_pg_only_samples` or the report explains why the original hypothesis was false.
- no raw DB URL or secrets in stdout/report.

- [ ] **Step 5: Gate result**

If `unexplained_pg_only_count == 0` and `value_checksum_mismatch_count == 0`:

```text
Decision: local prices is authority; no bulk copy.
```

If `unexplained_pg_only_count > 0` or `value_checksum_mismatch_count > 0`:

```text
Decision: P0-C implementation pauses. Write a small deterministic reconciliation/backfill plan scoped only to reviewed keys or mismatched buckets.
```

Commit only docs describing the reviewed gate:

```bash
git add docs/design/PG_EXIT_P0C_PRICES_RECONCILE_CUTOVER_PLAN.md
git commit -m "docs: record P0-C prices reconcile gate"
```

## Task 4: Promote Direct-Local Price Ingest

**Files:**

- Modify: `src/service/data_scheduler.py`
- Modify: `tests/test_data_scheduler.py`
- Possibly create: `src/prices_runtime.py` if the implementation chooses a thin `python -m src...` entrypoint.

- [ ] **Step 1: Write failing tests for scheduler source semantics**

Add tests to `tests/test_data_scheduler.py`:

```python
def test_p0c_ibkr_prices_no_longer_uses_pg_sync(monkeypatch):
    import src.market_data_direct as mdd
    seen = {}

    def fake_backfill(**kwargs):
        seen.update(kwargs)
        return {"provider": "ibkr", "tickers_scanned": 1, "rows_added": 2, "errors": {}}

    monkeypatch.setattr(mdd, "backfill_prices_direct", fake_backfill)
    monkeypatch.setattr(ds, "_resolve_price_scope", lambda: ["NVDA"])
    monkeypatch.setattr(ds, "_run_subprocess",
                        lambda argv: (_ for _ in ()).throw(AssertionError("no PG sync/subprocess")))
    monkeypatch.setattr(ds, "_local_refresh",
                        lambda: (_ for _ in ()).throw(AssertionError("no PG mirror refresh")))

    res = ds.run_source("ibkr_prices")

    assert res["status"] == "succeeded"
    assert seen["tickers_arg"] == "NVDA"
    assert seen["acquire_gateway_lock"] is False
    assert res["local_refresh"]["skipped"] == "direct local writer (no PG mirror)"


def test_local_incremental_retired_after_p0c():
    res = ds.run_source("local_incremental")
    assert res["status"] == "failed"
    assert "prices PG mirror retired by P0-C" in res["error"]
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
pytest tests/test_data_scheduler.py::test_p0c_ibkr_prices_no_longer_uses_pg_sync \
       tests/test_data_scheduler.py::test_local_incremental_retired_after_p0c -q
```

Expected: FAIL because `ibkr_prices` still uses `collect_ibkr_prices.py` and `local_incremental` still calls `_local_refresh()`.

- [ ] **Step 3: Implement scheduler cutover**

Implementation options:

1. Minimal: change `ibkr_prices` from `collector=["collect_ibkr_prices.py", ...]`, `sync_flag="--prices"` to `adapter=("src.market_data_direct", "backfill_prices_direct")`, `sync_flag=None`.
2. If subprocess isolation is required, create `src/prices_runtime.py` and invoke it as `python -m src.prices_runtime`, matching S-A1. The module must sanitize stdout and hold no secrets.

For the minimal route, update `src/service/data_scheduler.py`:

```python
SourceDef(
    "ibkr_prices", "IBKR 股價",
    None, None,
    ibkr=True, universe_tickers=True, default_interval_min=60,
    adapter=("src.market_data_direct", "backfill_prices_direct"),
    description="IBKR/Polygon → market_data.db DIRECT (no PG sync/mirror); P0-C price authority",
),
```

Then add `_N9_RETIRED_SOURCES` or a new retired-source map entry:

```python
_P0C_RETIRED_SOURCES = {
    "local_incremental": "prices PG mirror retired by P0-C; use ibkr_prices/price_backfill direct-local",
}
```

and gate `run_source` before executing `local_incremental`.

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```bash
pytest tests/test_data_scheduler.py::test_p0c_ibkr_prices_no_longer_uses_pg_sync \
       tests/test_data_scheduler.py::test_local_incremental_retired_after_p0c \
       tests/test_data_scheduler.py::test_price_backfill_uses_planner_scope_no_pg_no_mirror \
       tests/test_data_scheduler.py::test_price_backfill_serializes_behind_ibkr_lock -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/service/data_scheduler.py tests/test_data_scheduler.py
git commit -m "feat: route scheduled prices direct local"
```

## Task 5: Retire Price Mirror Admin Paths

**Files:**

- Modify: `src/market_data_admin.py`
- Modify: `src/api/routes/market_data.py`
- Modify: `tests/test_market_data_admin.py`

- [ ] **Step 1: Write failing tests for retired mirror paths**

Add to `tests/test_market_data_admin.py`:

```python
def test_p0c_incremental_update_prices_is_retired(tmp_path):
    import src.market_data_admin as mda

    out = tmp_path / "market_data.db"
    conn = sqlite3.connect(out)
    conn.executescript(mda._PRICES_SCHEMA)
    conn.close()

    res = mda.incremental_update(str(out), domains=("prices",))

    assert res["ok"] is False
    assert res["prices"]["skipped"] == "prices PG mirror retired by P0-C"


def test_p0c_manual_update_rejects_retired_mirror(store):
    from src.api.routes import market_data as route

    assert route._manual_update_domains(store) == ()
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
pytest tests/test_market_data_admin.py::test_p0c_incremental_update_prices_is_retired \
       tests/test_market_data_admin.py::test_p0c_manual_update_rejects_retired_mirror -q
```

Expected: FAIL because `incremental_update` still tries PG and manual update returns `("prices",)`.

- [ ] **Step 3: Retire mirror behavior**

Add a helper in `src/market_data_admin.py`:

```python
def prices_mirror_retired_result() -> dict:
    return {
        "ok": False,
        "rows_added": 0,
        "error": "prices PG mirror retired by P0-C; use direct-local price writer",
        "skipped": "prices PG mirror retired by P0-C",
    }
```

Change `incremental_update`:

```python
prices = (
    prices_mirror_retired_result()
    if "prices" in active_domains
    else _domain_disabled_result()
)
```

Change `src/api/routes/market_data.py`:

```python
def _manual_update_domains(store: ProfileStateStore) -> tuple[str, ...] | None:
    return ()
```

and have `update_route` return a 409 retired mirror error when domains is empty, or route to the direct-local price source if the UI should still support "update prices now". Pick one behavior in this task and test it. The lower-risk v1 behavior is reject-with-message; `schedule/run_now` already exists for provider sources.

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```bash
pytest tests/test_market_data_admin.py tests/test_data_scheduler.py -q
```

Expected: PASS for focused tests; any existing broad-suite failures must be classified before proceeding.

- [ ] **Step 5: Commit**

```bash
git add src/market_data_admin.py src/api/routes/market_data.py tests/test_market_data_admin.py
git commit -m "chore: retire prices PG mirror paths"
```

## Task 6: Local-Only Price Reads

**Files:**

- Modify: `src/tools/backends/local_market_backend.py`
- Modify: `src/tools/backends/db_backend.py`
- Modify: `tests/test_sqlite_backend.py`
- Modify: `tests/test_news_pg_unreachable.py`

- [ ] **Step 1: Write failing tests for local-only price miss**

Add to `tests/test_sqlite_backend.py`:

```python
def test_p0c_prices_miss_is_honest_empty_no_pg(market_db, monkeypatch):
    from src.tools.backends.db_backend import DatabaseBackend

    db, _ = market_db
    hit = []
    monkeypatch.setattr(
        DatabaseBackend,
        "query_prices",
        lambda self, *a, **k: hit.append(True) or (_ for _ in ()).throw(AssertionError("PG fallback forbidden")),
    )

    b = _make(db)
    assert b.query_prices("UNKNOWN", days=30).empty
    assert hit == []
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
pytest tests/test_sqlite_backend.py::test_p0c_prices_miss_is_honest_empty_no_pg -q
```

Expected: FAIL because `LocalMarketDatabaseBackend.query_prices` currently falls back to `DatabaseBackend.query_prices` when not strict.

This task must also flip the two existing fallback-contract tests that encode the old behavior:

- `tests/test_sqlite_backend.py::test_prices_fallback_to_pg` currently expects `UNKNOWN` prices to return `_PG_SENTINEL`; rewrite it to expect honest empty and no `DatabaseBackend.query_prices` call.
- `tests/test_sqlite_backend.py::test_news_hard_local_does_not_make_market_strict` currently asserts prices can still fall back to `_PG_SENTINEL` while news is hard-local; keep the news assertion and update the price assertion to post-P0-C local-only semantics.

- [ ] **Step 3: Remove price fallback**

Change `src/tools/backends/local_market_backend.py`:

```python
def query_prices(self, ticker: str, interval: str = "15min", days: int = 30) -> pd.DataFrame:
    try:
        df = self._market.query_prices(ticker, interval=interval, days=days)
    except Exception as e:
        logger.warning(f"local market query_prices failed ({e})")
        return pd.DataFrame()
    return df if df is not None else pd.DataFrame()
```

Update docstrings to say PG fallback for prices is retired by P0-C.

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```bash
pytest tests/test_sqlite_backend.py tests/test_news_pg_unreachable.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/tools/backends/local_market_backend.py tests/test_sqlite_backend.py tests/test_news_pg_unreachable.py
git commit -m "chore: make price reads local only"
```

## Task 7: Status, Health, and UI/API Smoke Surface

**Files:**

- Modify: `src/api/routes/market_data.py`
- Modify: `src/service/provider_health.py`
- Modify: `tests/test_market_data_admin.py`
- Modify: `tests/test_provider_health.py`
- Possibly modify frontend status text after backend semantics are stable.

- [ ] **Step 1: Write failing tests for status semantics**

Add to `tests/test_market_data_admin.py`:

```python
def test_p0c_market_status_reports_prices_local_authority(monkeypatch):
    from src.api.routes import market_data as route

    class Store:
        def get_setting(self, key):
            return "true"

    monkeypatch.setattr(route, "local_market_stats", lambda _path: {
        "exists": True,
        "prices": {"row_count": 10, "ticker_count": 1, "latest_datetime": "2026-07-02T14:15:00+0000"},
        "news": {},
        "iv": {},
        "fundamentals": {},
        "financial_cache": {},
    })
    monkeypatch.setattr(route, "read_sync_meta", lambda _path: {"prices": {"last_success": "old"}})
    monkeypatch.setattr(route, "overlay_news_sync_status", lambda sync, _path: sync)

    out = route.market_data_status(Store())

    assert out["prices_authority"] == "local"
    assert out["pg_fallback_active"] is False
    assert out["sync"]["prices"]["retired"] is True
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
pytest tests/test_market_data_admin.py::test_p0c_market_status_reports_prices_local_authority -q
```

Expected: FAIL because route does not yet expose `prices_authority` and still reports PG fallback semantics.

- [ ] **Step 3: Implement status semantics**

Update `/market-data/status` response to include:

```python
"prices_authority": "local",
"pg_fallback_active": False,
"price_mirror_retired": True,
```

Keep the old keys if the frontend depends on them, but make their values honest.

- [ ] **Step 4: Run focused API tests**

Run:

```bash
pytest tests/test_market_data_admin.py tests/test_provider_health.py tests/test_api.py -q
```

Expected: PASS or existing live-data-only failures classified.

- [ ] **Step 5: Commit**

```bash
git add src/api/routes/market_data.py src/service/provider_health.py tests/test_market_data_admin.py tests/test_provider_health.py
git commit -m "chore: report local price authority"
```

## Task 8: Cutover Dry-Run on DB Copy

**Files:**

- No code required if Tasks 1-7 are complete.
- Output during execution: copy DB and smoke logs under `scratchpad/`.

- [ ] **Step 1: Copy live DB with SQLite backup API**

Run:

```bash
PY=/home/hyl/.virtualenvs/llm_app/bin/python3
"$PY" - <<'PY'
import sqlite3
from pathlib import Path
src = Path("data/market_data.db")
dst = Path("scratchpad/p0c-market-data-copy.db")
dst.parent.mkdir(exist_ok=True)
dst.unlink(missing_ok=True)
with sqlite3.connect(src) as s, sqlite3.connect(dst) as d:
    s.backup(d)
print(dst)
PY
```

- [ ] **Step 2: Run read-only smoke against copy**

Run:

```bash
ARKSCOPE_MARKET_DB=scratchpad/p0c-market-data-copy.db \
pytest tests/test_sqlite_backend.py::test_prices_local_when_present \
       tests/test_sqlite_backend.py::test_p0c_prices_miss_is_honest_empty_no_pg \
       tests/test_api.py::TestPriceEndpoints::test_get_prices -q
```

Expected: PASS. Do not skip price route smoke.

- [ ] **Step 3: Reconcile copy row counts**

Run:

```bash
sqlite3 scratchpad/p0c-market-data-copy.db \
  "select count(*), count(distinct ticker), min(datetime), max(datetime) from prices;"
```

Expected: equals live local baseline from the reviewed reconcile report.

- [ ] **Step 4: Record dry-run result**

Append to this plan's "Live Gate Record" section:

```text
Dry-run copy: PASS
copy rows: <count>
price route smoke: PASS
local-only miss smoke: PASS
```

Commit docs:

```bash
git add docs/design/PG_EXIT_P0C_PRICES_RECONCILE_CUTOVER_PLAN.md
git commit -m "docs: record P0-C dry-run gate"
```

## Task 9: Live Cutover Gate

**Files:**

- Modify after success:
  - `docs/design/PG_EXIT_P0C_PRICES_RECONCILE_CUTOVER_PLAN.md`
  - `docs/design/PG_EXIT_REMAINDER_SCOPING.md`
  - `docs/design/PROJECT_PRIORITY_MAP.md`
  - `docs/design/PG_EXIT_COMPLETION_PLAN.md`

- [ ] **Step 1: Quiet window**

Pause:

- scheduler
- manual price updates
- Firefox/native host if it can trigger health/job side effects
- any direct price backfill
- old `collect_ibkr_prices.py`

Run:

```bash
ps -eo pid,ppid,etimes,stat,cmd | rg 'data_scheduler|collect_ibkr_prices|price_backfill|p0c_prices_reconcile' || true
```

Expected: no active writer.

- [ ] **Step 2: Run final reconcile twice**

Run the Task 3 preview twice. Reports must be byte-identical and match the reviewed fingerprint.

- [ ] **Step 3: Backup market DB**

Use `backup_market_db(... overwrite=False)`:

```bash
PY=/home/hyl/.virtualenvs/llm_app/bin/python3
"$PY" - <<'PY'
from datetime import datetime, timezone
from src.market_data_admin import resolve_market_db_path
from src.market_data_direct import backup_market_db
db = resolve_market_db_path()
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
backup = f"{db}.bak-pre-p0c-prices-{stamp}.db"
print(backup_market_db(db, backup, overwrite=False))
PY
```

- [ ] **Step 4: Apply routing/config cutover**

There is no data write if the reconcile gate says no backfill. The live cutover is deploying the already-merged code and ensuring these profile flags:

- `use_local_market=true`
- `use_local_market_strict=true` or equivalent post-P0-C local-only behavior
- scheduled `ibkr_prices` direct-local enabled
- retired `local_incremental` disabled

If profile changes are needed, record exact keys and before/after values without secrets.

- [ ] **Step 5: Resume scheduler and run one manual direct-local smoke**

Run:

```bash
PY=/home/hyl/.virtualenvs/llm_app/bin/python3
"$PY" - <<'PY'
from src.service.data_scheduler import run_source
print(run_source("ibkr_prices", trigger_source="api", tickers=["NVDA"]))
PY
```

Expected:

- status `succeeded`, `partial`, or a reviewed provider unavailability state.
- no `sync` key invoking PG.
- `local_refresh.skipped == "direct local writer (no PG mirror)"`.
- no secrets in output.

- [ ] **Step 6: App smoke**

Run:

```bash
pytest tests/test_api.py::TestPriceEndpoints::test_get_prices \
       tests/test_sqlite_backend.py::test_prices_local_when_present \
       tests/test_provider_health.py -q
```

Also manually hit or ask the user to hit:

- `GET /prices/NVDA?interval=15min&days=7`
- `GET /prices/NVDA/change?days=30`
- `GET /market-data/status`
- `GET /providers/health`
- one agent/tool call to `get_ticker_prices`.

- [ ] **Step 7: Docs sync**

Record:

- reviewed reconcile fingerprint
- whether any backfill was applied
- backup path
- live cutover result
- scheduler source state
- remaining PG objects: `prices` retained as archive/rollback until batch-3, `job_runs` until batch-2, app-records if still present

Commit:

```bash
git add docs/design/PG_EXIT_P0C_PRICES_RECONCILE_CUTOVER_PLAN.md \
        docs/design/PG_EXIT_REMAINDER_SCOPING.md \
        docs/design/PROJECT_PRIORITY_MAP.md \
        docs/design/PG_EXIT_COMPLETION_PLAN.md
git commit -m "docs: record P0-C prices cutover"
```

## Task 10: Batch-3 Prep Note Only

**Files:**

- Modify: `docs/design/PG_EXIT_REMAINDER_SCOPING.md`

- [ ] **Step 1: Add a batch-3 queue item**

Add:

```markdown
- Batch-3: PG `prices` destructive drop after P0-C has soaked. Requires fresh
  targeted dump, restore proof, explicit approval, and a conscious removal of
  `prices` from the N9 excluded-table protection.
```

- [ ] **Step 2: Commit**

```bash
git add docs/design/PG_EXIT_REMAINDER_SCOPING.md
git commit -m "docs: queue prices PG drop as batch3"
```

## Review Gates

Before implementation starts, reviewer must confirm:

- Audit task can falsify LC→HAPN instead of assuming it.
- `bulk_copy_allowed` is false by default and cannot become true without reviewed unexplained PG-only rows.
- Audit report compares OHLCV value checksums by `(ticker, interval)`, not only key coverage.
- The scheduled price source no longer invokes `collect_ibkr_prices.py`, `migrate_to_supabase --prices`, or `_local_refresh()`.
- Local price miss does not call PG.
- Manual update no longer starts the PG price mirror.
- PG `prices` is not dropped in P0-C.
- `job_runs` is untouched.

## Live Gate Record

Status: **P0-C LIVE COMPLETE (2026-07-04). Local prices are the runtime authority; scheduled ingest is direct-local; legacy PG mirror/read fallback is retired. PG `prices` physical drop remains batch-3.**

```text
Reviewed reconcile fingerprint (final): 61bbf613c1fe94dd6558dc4bcc2bae7f9624e238df9c8114ed9a4e23da2580d2
Audit iterations: v1 49e15e6b… (bucket-level checksums, superseded) → v2 a77b1222…
  (intersection checksums; unexplained {HAPN:315}, drift 11 buckets/288 rows)
  → final 61bbf613… after the HAPN patch.
PG summary: 2,314,293 rows / 150 tickers / 15min only
Local summary (post-patch): 2,324,487 rows / 149 tickers / 15min only
Alias-explained PG-only: 15,530 (LC→HAPN — hypothesis CONFIRMED)
Unexplained PG-only: 0 (was 315, all HAPN partial-day gaps over 16 days 2026-01-26..06-05)
Value drift: 19 rows / 10 tickers remain, all 2026-06-23 volume-revision noise
  (OHLC identical) — keep-local per ruling. HAPN's 269 truncated-bar rows adopted PG.
Bulk copy applied: NO. Scoped deterministic HAPN patch only:
  patch fingerprint ebe085be9e2dd86bbc77802ef69537468bd6043827700390504d9f37193ac630
  (315 INSERT + 269 UPDATE, insert-only outside preimage-verified updates;
  copy dry-run + idempotent rerun proven; audit row in prices_patch_runs).
Backup path: data/market_data.db.bak-pre-p0c-hapn-patch-20260703T232813Z.db
Cutover backup path: data/market_data.db.bak-pre-p0c-cutover-20260704T000609505759Z.db
Cutover implementation:
  Task 4 commit 5deee9e — scheduled ibkr_prices routes to direct-local writer.
  Task 5 commit e3218db — legacy price PG mirror update paths return retired/409.
  Task 6 commit becdfa5 — price reads are local-only; misses are honest empty.
  Task 7 commit d8ce7cd — status/provider health report local price authority.
  Task 8 commit bc2ab0f — dry-run copy record.
Dry-run copy: PASS (scratchpad/p0c-market-data-copy.db via SQLite backup API).
Copy prices: 2,324,487 rows / 149 tickers / 2024-01-02T14:30:00+0000..2026-07-02T14:15:00+0000.
Dry-run tests:
  pytest tests/test_sqlite_backend.py::test_prices_local_when_present
         tests/test_sqlite_backend.py::test_p0c_prices_miss_is_honest_empty_no_pg -q
  → PASS (2 passed).
Route-level price smoke on copy: PASS (prices_for_ticker("NVDA", interval="15min", days=7)
  returned 81 bars through DataAccessLayer + LocalMarketDatabaseBackend).
Full TestClient price smoke: BLOCKED in this worktree by app startup/TestClient lifespan hang
  before request dispatch (faulthandler shows TestClient.__enter__ waiting on the portal while
  the event-loop thread is idle). This was not used as a pass/fail signal for price route logic.
Live cutover: FF-merged to master at bc2ab0f after final preview ×2 byte-identical.
Final live preview: fingerprint 61bbf613c1fe94dd6558dc4bcc2bae7f9624e238df9c8114ed9a4e23da2580d2,
  unexplained_pg_only_count=0, value_checksum_mismatch_count=10, value_checksum_mismatch_row_count=19.
Post-cutover smoke: PASS on live main checkout:
  - prices_for_ticker("NVDA", interval="15min", days=7) returned 81 bars.
  - LocalMarketDatabaseBackend.query_prices("ZZZZ") returned honest empty without PG.
  - /market-data/status route function reports prices_authority=local,
    price_mirror_retired=true, pg_fallback_active=false.
  - data_scheduler.SOURCES["ibkr_prices"].adapter == ("src.market_data_direct", "backfill_prices_direct");
    local_incremental is retired with the P0-C message.
```

### P0-C.1 Runtime Hardening Follow-up

The first scheduler resume after P0-C exposed a runtime wiring flaw, not a data-authority flaw:
`ibkr_prices` ran the `ib_insync` direct writer as an in-process adapter inside the
`sched-ibkr_prices` worker thread and failed with `There is no current event loop in thread
'sched-ibkr_prices'`. `price_backfill` shares the same adapter and therefore the same latent
bug. The same resume also exposed `market_data.db write lock busy (timeout)` because
`backfill_prices_direct()` held `market_write_lock` while fetching provider data across the
active universe.

P0-C.1 was implemented as the required follow-up:
`docs/design/PG_EXIT_P0C1_PRICES_RUNTIME_HARDENING_PLAN.md`. It keeps the P0-C data gate
unchanged, but moves both IBKR price sources behind a sanitized `python -m src.prices_runtime`
worker, fetches provider rows outside the SQLite write lock, adds one-market-writer-per-tick
backpressure, and classifies lock-busy as retryable skip rather than durable failed.

Offline gate:

```text
pytest tests/test_prices_runtime.py tests/test_data_scheduler.py tests/test_market_data_direct.py tests/test_provider_health.py -q
→ 160 passed
```

**P0-C.2 news burst hardening (2026-07-05):** normalized Polygon/Finnhub/IBKR news writers now use short `market_write_lock` sections only around SQLite write/telemetry phases; provider fetches occur outside the market DB lock. Residual `market_data.db write lock busy` errors are classified as retryable `skipped_lock_busy`, and same-tick market writer bursts remain deferred via `market_writer_backpressure`.

## Self-Review Notes

- The plan covers user review points (a)-(e):
  - (a) PG-only/local-only key attribution is explicit and alias hypotheses are falsifiable.
  - (b) no-bulk-copy is a gate with specific conditions, not a slogan.
  - (c) cutover order is pause → reconcile → flip → resume; direct writer maps to the existing S-A1-style no-PG writer discipline.
  - (d) mirror retirement includes scheduler, manual update, market admin, market_sync_meta, read fallback, and status.
  - (e) PG drop=batch-3 and `job_runs` untouched are Non-Goals.
- This first plan is docs-only. No runtime code is changed by this commit.
