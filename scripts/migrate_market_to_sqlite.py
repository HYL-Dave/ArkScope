#!/usr/bin/env python3
"""
Migrate the market_data tables PostgreSQL → local SQLite (operator CLI).

Thin wrapper over ``src.market_data_admin`` (the shared lifecycle core the desktop
app also uses via the /market-data API). This CLI is the operator/backfill/debug
entry point — the app does NOT require the user to run it; it has its own
bootstrap/status/validate job API + Settings UI. Builds all domains: prices (3a),
news + FTS5 (3b), iv_history + fundamentals (3c-A).

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
    ap = argparse.ArgumentParser(
        description="Migrate PG market data (prices + news + iv + fundamentals) → local SQLite")
    ap.add_argument("--out", default=resolve_market_db_path())
    ap.add_argument("--dry-run", action="store_true", help="count PG rows only; write nothing")
    ap.add_argument("--validate-only", action="store_true", help="compare an existing SQLite vs PG")
    args = ap.parse_args()

    if args.dry_run:
        c = pg_market_counts()
        print(f"PG prices:       {c['prices']['rows']:,} rows / {c['prices']['groups']} groups")
        print(f"PG news:         {c['news']['rows']:,} rows / {c['news']['groups']} sources")
        print(f"PG iv_history:   {c['iv']['rows']:,} rows")
        print(f"PG fundamentals: {c['fundamentals']['rows']:,} rows")
        print("[DRY RUN] no SQLite written.")
        return 0

    def _dom(r, key, label):  # one '<label> local/pg ✓|✗' segment
        d = r[key]
        local = d.get("local_rows", d.get("rows"))
        pg = d.get("pg_rows", d.get("total"))
        return f"{label} {local:,}/{pg:,} {'✓' if d['match'] else '✗'}"

    if args.validate_only:
        r = validate_market(args.out)
        if not r.get("exists"):
            print(f"{args.out} does not exist.")
            return 1
        print(" | ".join([_dom(r, "prices", "prices"), _dom(r, "news", "news"),
                           _dom(r, "iv", "iv"), _dom(r, "fundamentals", "fund"),
                           "✓ MATCH" if r["match"] else "✗ MISMATCH"]))
        return 0 if r["match"] else 1

    last = {"w": 0}

    def cb(written, total):
        if written - last["w"] >= 100000 or written == total:
            last["w"] = written
            print(f"  …{written:,}/{total:,}", end="\r")

    print(f"Bootstrapping {args.out} (prices + news + iv + fundamentals) from PG …")
    r = bootstrap_market(args.out, progress_cb=cb)
    print("\n" + " | ".join([
        _dom(r, "prices", "prices"), _dom(r, "news", "news"),
        _dom(r, "iv", "iv"), _dom(r, "fundamentals", "fund"),
        "✓ MATCH (swapped in)" if r["match"] else "✗ MISMATCH (discarded; existing DB kept)"]))
    return 0 if r["match"] else 1


if __name__ == "__main__":
    sys.exit(main())
