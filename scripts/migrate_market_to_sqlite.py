#!/usr/bin/env python3
"""
Migrate the market_data PRICES table PostgreSQL → local SQLite (operator CLI).

Thin wrapper over ``src.market_data_admin`` (the shared lifecycle core the desktop
app also uses via the /market-data API). This CLI is the operator/backfill/debug
entry point — the app does NOT require the user to run it; it has its own
bootstrap/status/validate job API + Settings UI (slice 3a.1).

Usage:
    python scripts/migrate_market_to_sqlite.py                 # → data/market_data.db
    python scripts/migrate_market_to_sqlite.py --out /tmp/x.db
    python scripts/migrate_market_to_sqlite.py --dry-run       # PG counts only, no write
    python scripts/migrate_market_to_sqlite.py --validate-only # re-check an existing db

After it passes, activate routing via the app Settings toggle (persisted) or
ARKSCOPE_USE_LOCAL_MARKET=1 (PG stays the fallback).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.market_data_admin import (  # noqa: E402
    bootstrap_prices,
    pg_price_counts,
    resolve_market_db_path,
    validate_prices,
)


def main():
    ap = argparse.ArgumentParser(description="Migrate PG prices → local SQLite market_data.db")
    ap.add_argument("--out", default=resolve_market_db_path())
    ap.add_argument("--dry-run", action="store_true", help="count PG rows only; write nothing")
    ap.add_argument("--validate-only", action="store_true", help="compare an existing SQLite vs PG")
    args = ap.parse_args()

    if args.dry_run:
        counts = pg_price_counts()
        print(f"PG prices rows: {counts['rows']:,} | (ticker,interval) groups: {counts['groups']}")
        print("[DRY RUN] no SQLite written.")
        return 0

    if args.validate_only:
        r = validate_prices(args.out)
        if not r.get("exists"):
            print(f"{args.out} does not exist.")
            return 1
        print(f"validate-only: rows {r['local_rows']:,}/{r['pg_rows']:,} | "
              f"groups {r['local_groups']}/{r['pg_groups']} | "
              f"{'✓ MATCH' if r['match'] else '✗ MISMATCH'}")
        return 0 if r["match"] else 1

    last = {"written": 0}

    def cb(written, total):
        if written - last["written"] >= 100000 or written == total:
            last["written"] = written
            print(f"  …{written:,}/{total:,}", end="\r")

    print(f"Bootstrapping {args.out} from PG …")
    r = bootstrap_prices(args.out, progress_cb=cb)
    print(f"\nwrote {r['rows']:,}/{r['total']:,} rows | groups {r['groups']}/{r['pg_groups']} | "
          f"{'✓ MATCH (swapped in)' if r['match'] else '✗ MISMATCH (discarded; existing DB kept)'}")
    return 0 if r["match"] else 1


if __name__ == "__main__":
    sys.exit(main())
