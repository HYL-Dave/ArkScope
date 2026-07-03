#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.prices_reconcile import (  # noqa: E402
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


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def connect_pg(database_url: str):
    import psycopg2

    return psycopg2.connect(database_url)


def _value_checksum_rows(rows: Iterable[tuple[object, ...]]) -> dict[tuple[str, str], str]:
    hashes = {}
    for ticker, interval, dt, open_, high, low, close, volume in rows:
        bucket = (str(ticker), str(interval))
        h = hashes.get(bucket)
        if h is None:
            h = hashlib.sha256()
            hashes[bucket] = h
        h.update(
            _canonical_json(
                [str(dt), str(open_), str(high), str(low), str(close), str(volume)]
            ).encode("utf-8")
        )
    return {bucket: h.hexdigest() for bucket, h in sorted(hashes.items())}


def load_pg_snapshot(database_url: str) -> dict[str, Any]:
    conn = connect_pg(database_url)
    try:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET LOCAL statement_timeout = '120s'")
            cur.execute(
                """
                SELECT COUNT(*), COUNT(DISTINCT ticker), MIN(datetime), MAX(datetime)
                FROM prices
                """
            )
            row_count, ticker_count, min_dt, max_dt = cur.fetchone()
            cur.execute("SELECT interval, COUNT(*) FROM prices GROUP BY interval ORDER BY interval")
            intervals = {str(k): int(v) for k, v in cur.fetchall()}
            cur.execute(
                """
                SELECT ticker, interval,
                       TO_CHAR(datetime AT TIME ZONE 'UTC',
                               'YYYY-MM-DD"T"HH24:MI:SS+0000') AS datetime
                FROM prices
                WHERE interval = '15min'
                ORDER BY ticker, interval, datetime
                """
            )
            keys = [(str(t), str(i), str(dt)) for t, i, dt in cur.fetchall()]
            cur.execute(
                """
                SELECT ticker, interval,
                       TO_CHAR(datetime AT TIME ZONE 'UTC',
                               'YYYY-MM-DD"T"HH24:MI:SS+0000') AS datetime,
                       open, high, low, close, volume
                FROM prices
                WHERE interval = '15min'
                ORDER BY ticker, interval, datetime
                """
            )
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
        intervals = dict(
            conn.execute(
                "SELECT interval, COUNT(*) FROM prices GROUP BY interval ORDER BY interval"
            ).fetchall()
        )
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
    report = {
        "schema_version": 1,
        "scope": "p0c_prices_reconcile",
        "pg_summary": pg_snapshot["summary"],
        "local_summary": local_snapshot["summary"],
        "alias_explained_pg_only_count": len(diff.alias_explained_pg_only),
        "unexplained_pg_only_count": len(diff.unexplained_pg_only),
        "local_only_count": len(diff.local_only),
        "value_checksum_mismatch_count": len(value_mismatches),
        "bulk_copy_allowed": diff.bulk_copy_allowed,
        "alias_explained_pg_only_samples": list(diff.alias_explained_pg_only[:20]),
        "unexplained_pg_only_samples": list(diff.unexplained_pg_only[:20]),
        "local_only_samples": list(diff.local_only[:20]),
        "value_checksum_mismatch_samples": list(value_mismatches[:20]),
    }
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
        Path(args.output).write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    "status": "previewed",
                    "fingerprint": report["fingerprint"],
                    "unexplained_pg_only_count": report["unexplained_pg_only_count"],
                    "value_checksum_mismatch_count": report["value_checksum_mismatch_count"],
                },
                sort_keys=True,
            )
        )
        return 0
    parser.error(f"unknown command: {args.cmd}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
