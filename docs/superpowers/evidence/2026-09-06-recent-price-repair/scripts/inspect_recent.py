"""Read bounded metadata from the previously authorized private backup only."""

import argparse
from collections import Counter
from contextlib import closing
import json
from pathlib import Path
import sqlite3


READS = {
    "provider_sync_runs": {"provider", "domain", "interval", "started_at", "status", "tickers_scanned", "rows_added"},
    "watchlist_memberships": {"ticker", "created_at", "archived_at"},
    "sa_tracking_memberships": {"ticker", "accepted_at", "created_at", "reason"},
    "universe_source_memberships": {"ticker", "source_key", "created_at", "archived_at"},
}


def readonly(path):
    conn = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    def authorize(action, table, column, database, trigger):
        if action == sqlite3.SQLITE_READ:
            return sqlite3.SQLITE_OK if table in READS and (not column or column in READS[table]) else sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK if action in {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_FUNCTION} else sqlite3.SQLITE_DENY
    conn.set_authorizer(authorize)
    return conn


def inspect(inventory, market, profile):
    gaps = inventory["coverage"]["current_15"]["history_gaps"]
    targets = sorted(row["ticker"] for row in gaps)
    if not targets or len(targets) != len(set(targets)):
        raise ValueError("recent_inventory_targets")
    groups = Counter((tuple(inventory["sources_by_ticker"][row["ticker"]]), row["first_local_bar_at"], row["reason"]) for row in gaps)
    marks = ",".join("?" for _ in targets)
    with closing(readonly(profile)) as conn:
        manual = [dict(row) for row in conn.execute(
            f"SELECT ticker, created_at, archived_at FROM watchlist_memberships WHERE ticker IN ({marks})", targets)]
        sa = [dict(row) for row in conn.execute(
            f"SELECT ticker, accepted_at, created_at, reason FROM sa_tracking_memberships WHERE ticker IN ({marks})", targets)]
    with closing(readonly(market)) as conn:
        runs = [dict(row) for row in conn.execute(
            "SELECT substr(started_at,1,10) AS commit_phase_date, status, tickers_scanned, "
            "count(*) AS run_count, sum(rows_added) AS rows_added "
            "FROM provider_sync_runs WHERE provider='ibkr' AND domain='prices' AND interval='15min' "
            "AND started_at >= ? AND started_at < ? GROUP BY 1,2,3 ORDER BY 1,2,3",
            ("2026-08-21", "2026-09-06"))]
    return {
        "source": "existing_private_backup_and_post_disposition_inventory",
        "affected_tickers": len(targets),
        "missing_ticker_days": sum(len(row["missing_dates"]) for row in gaps),
        "source_and_first_bar_groups": [
            {"sources": list(sources), "first_local_bar_at": first, "reason": reason, "count": count}
            for (sources, first, reason), count in sorted(groups.items())],
        "manual_membership_created_dates": dict(sorted(Counter(row["created_at"][:10] for row in manual).items())),
        "sa_membership_created_dates": dict(sorted(Counter(row["created_at"][:10] for row in sa).items())),
        "sa_membership_reasons": dict(sorted(Counter(row["reason"] for row in sa).items())),
        "ibkr_commit_phase_runs": runs,
        "request_parameters_retained_by_provider_sync_runs": False,
        "price_rows_have_inserted_at": False,
        "first_bar_is_not_ipo_or_membership_time": True,
        "provider_requests": 0, "production_writes": 0, "credential_fields_read": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--market", required=True, type=Path)
    parser.add_argument("--profile", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(json.loads(args.inventory.read_text()), args.market, args.profile), sort_keys=True))


if __name__ == "__main__":
    main()
