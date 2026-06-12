#!/usr/bin/env python3
"""
cut-1 freeze artifact: CSV snapshot of all PG sa_* tables + fingerprint manifest.

Replaces the runbook's original pg_dump idea — this machine has no postgres
client tools and the server is PG 17 (Ubuntu 24.04's default client is 16,
which refuses newer servers). psycopg2 COPY is version-proof and zero-install.

Purpose: belt-and-suspenders forensics/diff baseline for the cutover window.
PG rows themselves stay frozen read-only (runbook L5) — this artifact is for
detecting/diagnosing accidental PG drift, not the primary rollback (rollback =
flip the toggle back; PG still has everything).

Usage:
    python scripts/sa_pg_freeze.py --out /path/to/freeze_dir
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.market_data_admin import _pg_conn  # noqa: E402

_SA_TABLES = [
    "sa_alpha_picks", "sa_refresh_meta", "sa_articles",
    "sa_article_comments", "sa_market_news", "sa_comment_signals",
]


def main() -> int:
    ap = argparse.ArgumentParser(description="Freeze PG sa_* tables to CSV + fingerprints")
    ap.add_argument("--out", required=True, help="output directory (created if missing)")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    from scripts.migrate_sa_to_sqlite import _fingerprints_pg  # same numbers as cut-2 gate

    pg = _pg_conn()
    try:
        cur = pg.cursor()
        for table in _SA_TABLES:
            path = out / f"{table}.csv"
            with open(path, "w", encoding="utf-8") as f:
                cur.copy_expert(
                    f"COPY (SELECT * FROM {table} ORDER BY 1) TO STDOUT WITH CSV HEADER", f)
            print(f"  {table:24s} → {path} ({path.stat().st_size:,} bytes)")
        fps = _fingerprints_pg(cur)
    finally:
        pg.close()

    manifest = out / "FINGERPRINTS.txt"
    with open(manifest, "w", encoding="utf-8") as f:
        f.write(f"frozen_at = {datetime.now(timezone.utc).isoformat(timespec='seconds')}\n")
        for key, fp in fps.items():
            f.write(f"{key} rows={fp[0]} sum_id={fp[1]}\n")
    print(f"  manifest → {manifest}")
    print("✓ freeze complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
