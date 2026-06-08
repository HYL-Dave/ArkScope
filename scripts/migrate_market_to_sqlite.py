#!/usr/bin/env python3
"""
Migrate the market_data tables PostgreSQL → local SQLite (operator CLI).

Thin wrapper over ``src.market_data_admin`` (the shared lifecycle core the desktop
app also uses via the /market-data API). This CLI is the operator/backfill/debug
entry point — the app does NOT require the user to run it; it has its own
bootstrap/status/validate job API + Settings UI. Builds BOTH domains: prices (3a)
and news + FTS5 (3b).

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
    bootstrap_market,
    pg_market_counts,
    resolve_market_db_path,
    validate_market,
)


def main():
    ap = argparse.ArgumentParser(description="Migrate PG market data (prices + news) → local SQLite")
    ap.add_argument("--out", default=resolve_market_db_path())
    ap.add_argument("--dry-run", action="store_true", help="count PG rows only; write nothing")
    ap.add_argument("--validate-only", action="store_true", help="compare an existing SQLite vs PG")
    args = ap.parse_args()

    if args.dry_run:
        c = pg_market_counts()
        print(f"PG prices: {c['prices']['rows']:,} rows / {c['prices']['groups']} groups")
        print(f"PG news:   {c['news']['rows']:,} rows / {c['news']['groups']} sources")
        print("[DRY RUN] no SQLite written.")
        return 0

    if args.validate_only:
        r = validate_market(args.out)
        if not r.get("exists"):
            print(f"{args.out} does not exist.")
            return 1
        print(f"prices {r['prices']['local_rows']:,}/{r['prices']['pg_rows']:,} "
              f"{'✓' if r['prices']['match'] else '✗'} | "
              f"news {r['news']['local_rows']:,}/{r['news']['pg_rows']:,} "
              f"{'✓' if r['news']['match'] else '✗'} | "
              f"{'✓ MATCH' if r['match'] else '✗ MISMATCH'}")
        return 0 if r["match"] else 1

    last = {"w": 0}

    def cb(written, total):
        if written - last["w"] >= 100000 or written == total:
            last["w"] = written
            print(f"  …{written:,}/{total:,}", end="\r")

    print(f"Bootstrapping {args.out} (prices + news) from PG …")
    r = bootstrap_market(args.out, progress_cb=cb)
    p, n = r["prices"], r["news"]
    print(f"\nprices {p['rows']:,}/{p['total']:,} {'✓' if p['match'] else '✗'} | "
          f"news {n['rows']:,}/{n['total']:,} {'✓' if n['match'] else '✗'} | "
          f"{'✓ MATCH (swapped in)' if r['match'] else '✗ MISMATCH (discarded; existing DB kept)'}")
    return 0 if r["match"] else 1


if __name__ == "__main__":
    sys.exit(main())
