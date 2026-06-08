#!/usr/bin/env python3
"""
Migrate the market_data PRICES table PostgreSQL → local SQLite (slice 3a).

Phase 1 of the local-first storage split
(``docs/design/DATA_COLLECTION_AND_LOCAL_STORAGE_PLAN.md`` §4). Reads every
``prices`` row from PostgreSQL and writes ``market_data.db`` (SQLite, WAL),
storing ``datetime`` as the SAME UTC string PG emits
(``YYYY-MM-DDTHH:MM:SS+0000``) so :class:`SqliteBackend` reads pass through and
roll up identically. Validates row-count + a per-(ticker,interval) checksum.

This is a REGENERABLE mirror (prices can always be re-fetched), so the migration
is safe to re-run; it recreates the table from scratch each run.

Usage:
    python scripts/migrate_market_to_sqlite.py                 # → data/market_data.db
    python scripts/migrate_market_to_sqlite.py --out /tmp/x.db
    python scripts/migrate_market_to_sqlite.py --dry-run       # counts only, no write
    python scripts/migrate_market_to_sqlite.py --validate-only # re-check an existing db

After it passes, activate routing with:
    ARKSCOPE_USE_LOCAL_MARKET=1  (market_data.db must exist; PG stays the fallback)
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PROJECT_ROOT))

_SCHEMA = """
CREATE TABLE IF NOT EXISTS prices (
    ticker    TEXT NOT NULL,
    datetime  TEXT NOT NULL,   -- UTC 'YYYY-MM-DDTHH:MM:SS+0000' (matches PG TO_CHAR)
    interval  TEXT NOT NULL,   -- '15min' | '1h' | '1d'
    open      REAL,
    high      REAL,
    low       REAL,
    close     REAL,
    volume    INTEGER,
    PRIMARY KEY (ticker, datetime, interval)
);
CREATE INDEX IF NOT EXISTS idx_prices_ticker_interval_dt ON prices(ticker, interval, datetime);
"""

# Same UTC string format SqliteBackend expects and PG's query_prices emits.
_PG_SELECT = """
    SELECT
        ticker,
        TO_CHAR(datetime AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS+0000') AS datetime,
        interval, open, high, low, close, volume
    FROM prices
    ORDER BY ticker, interval, datetime
"""


def _pg_conn():
    """Connect to PG using the project's resolved DSN (config/.env)."""
    from src.tools.data_access import DataAccessLayer
    from src.tools.db_config import load_sslmode

    dal = DataAccessLayer(db_dsn="auto")
    dsn = dal._load_env_db_dsn()
    if not dsn:
        raise SystemExit("No DATABASE_URL in config/.env — cannot read PG prices.")
    import psycopg2

    sslmode = load_sslmode(_PROJECT_ROOT / "config" / ".env", dsn)
    return psycopg2.connect(dsn, sslmode=sslmode)


def _pg_checksum(cur) -> dict:
    """Per-(ticker,interval) row count from PG — the validation fingerprint."""
    cur.execute("SELECT ticker, interval, COUNT(*) FROM prices GROUP BY ticker, interval")
    return {(t, iv): n for t, iv, n in cur.fetchall()}


def _sqlite_checksum(conn) -> dict:
    rows = conn.execute(
        "SELECT ticker, interval, COUNT(*) FROM prices GROUP BY ticker, interval"
    ).fetchall()
    return {(t, iv): n for t, iv, n in rows}


def migrate(out_path: str, dry_run: bool, batch: int = 20000) -> int:
    pg = _pg_conn()
    try:
        cur = pg.cursor()
        cur.execute("SELECT COUNT(*) FROM prices")
        total = cur.fetchone()[0]
        print(f"PG prices rows: {total:,}")
        pg_sum = _pg_checksum(cur)
        print(f"PG (ticker,interval) groups: {len(pg_sum)}")
        if dry_run:
            print("[DRY RUN] no SQLite written.")
            return 0

        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        if Path(out_path).exists():
            Path(out_path).unlink()  # regenerable mirror: rebuild clean
        sconn = sqlite3.connect(out_path)
        try:
            try:
                sconn.execute("PRAGMA journal_mode = WAL")
            except sqlite3.OperationalError:
                pass
            sconn.executescript(_SCHEMA)

            cur.execute(_PG_SELECT)
            written = 0
            while True:
                rows = cur.fetchmany(batch)
                if not rows:
                    break
                sconn.executemany(
                    "INSERT OR IGNORE INTO prices "
                    "(ticker, datetime, interval, open, high, low, close, volume) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    rows,
                )
                sconn.commit()
                written += len(rows)
                print(f"  …{written:,}/{total:,}", end="\r")
            print(f"\nWrote {written:,} rows → {out_path}")

            # --- validate: row count + per-group checksum ---
            sqlite_total = sconn.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
            sq_sum = _sqlite_checksum(sconn)
        finally:
            sconn.close()
    finally:
        pg.close()

    ok = sqlite_total == total and sq_sum == pg_sum
    print(f"validate: rows {sqlite_total:,}/{total:,} | groups {len(sq_sum)}/{len(pg_sum)} "
          f"| {'✓ MATCH' if ok else '✗ MISMATCH'}")
    if not ok:
        diffs = [(k, pg_sum.get(k), sq_sum.get(k)) for k in set(pg_sum) | set(sq_sum)
                 if pg_sum.get(k) != sq_sum.get(k)]
        for k, p, s in diffs[:20]:
            print(f"  mismatch {k}: PG={p} SQLite={s}")
        return 1
    return 0


def validate_only(out_path: str) -> int:
    if not Path(out_path).exists():
        print(f"{out_path} does not exist.")
        return 1
    pg = _pg_conn()
    try:
        cur = pg.cursor()
        cur.execute("SELECT COUNT(*) FROM prices")
        pg_total = cur.fetchone()[0]
        pg_sum = _pg_checksum(cur)
    finally:
        pg.close()
    sconn = sqlite3.connect(f"file:{out_path}?mode=ro", uri=True)
    try:
        sq_total = sconn.execute("SELECT COUNT(*) FROM prices").fetchone()[0]
        sq_sum = _sqlite_checksum(sconn)
    finally:
        sconn.close()
    ok = sq_total == pg_total and sq_sum == pg_sum
    print(f"validate-only: rows {sq_total:,}/{pg_total:,} | "
          f"groups {len(sq_sum)}/{len(pg_sum)} | {'✓ MATCH' if ok else '✗ MISMATCH'}")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="Migrate PG prices → local SQLite market_data.db")
    ap.add_argument("--out", default=os.environ.get("ARKSCOPE_MARKET_DB")
                    or str(_PROJECT_ROOT / "data" / "market_data.db"))
    ap.add_argument("--dry-run", action="store_true", help="count PG rows only; write nothing")
    ap.add_argument("--validate-only", action="store_true", help="compare an existing SQLite vs PG")
    args = ap.parse_args()

    if args.validate_only:
        sys.exit(validate_only(args.out))
    sys.exit(migrate(args.out, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
