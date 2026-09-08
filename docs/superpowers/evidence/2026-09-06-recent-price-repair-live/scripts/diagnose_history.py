"""Read price-job counters, never raw errors, payloads or credentials."""

import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3


def inspect(profile):
    with closing(sqlite3.connect(profile.resolve().as_uri() + "?mode=ro", uri=True)) as conn:
        conn.execute("PRAGMA query_only=ON")
        conn.row_factory = sqlite3.Row
        def authorizer(action, table, column, database, trigger):
            if action == sqlite3.SQLITE_READ:
                return sqlite3.SQLITE_OK if table == "job_runs" and column in {
                    "job_name", "started_at", "status", "duration_ms", "result",
                } else sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK if action in {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_FUNCTION} else sqlite3.SQLITE_DENY
        conn.set_authorizer(authorizer)
        rows = conn.execute("""
            SELECT started_at, status, duration_ms, json_valid(result) AS result_valid,
                   CASE WHEN json_valid(result) THEN json_extract(result,'$.ticker_count') END AS target_count,
                   CASE WHEN json_valid(result) THEN json_extract(result,'$.collect.status') END AS collect_status,
                   CASE WHEN json_valid(result) THEN json_extract(result,'$.collect.tickers_scanned') END AS scanned,
                   CASE WHEN json_valid(result) THEN json_extract(result,'$.collect.succeeded_ticker_count') END AS succeeded,
                   CASE WHEN json_valid(result) THEN json_extract(result,'$.collect.rows_added') END AS rows_added,
                   CASE WHEN json_valid(result) THEN json_extract(result,'$.collect.error_count') END AS error_count,
                   CASE WHEN json_valid(result) THEN json_extract(result,'$.collect.unresolved_after_fetch_count') END AS unresolved,
                   CASE WHEN json_valid(result) THEN json_extract(result,'$.collect.error_tickers') END AS error_tickers,
                   CASE WHEN json_valid(result) THEN json_extract(result,'$.collect.error_class') END AS error_class,
                   CASE WHEN json_valid(result) THEN json_extract(result,'$.collect.error_code') END AS error_code,
                   CASE WHEN json_valid(result) THEN json_extract(result,'$.price_repair.lookback_days') END AS repair_lookback_days
            FROM job_runs WHERE job_name IN ('collect.ibkr_prices','daily_update.ibkr_prices')
              AND started_at >= '2026-08-21' AND started_at < '2026-09-07'
            ORDER BY started_at LIMIT 201
        """).fetchall()
    if len(rows) > 200:
        raise ValueError("price_history_bound_exceeded")
    return {
        "source": "profile_db_price_job_numeric_and_typed_projection",
        "job_count": len(rows), "rows": [dict(row) for row in rows],
        "raw_payload_or_error_read": False, "credential_read": False,
        "writes": 0, "provider_requests": 0,
        "historical_default_before_former_change": 5,
        "exact_historical_cli_arguments_retained": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.profile), sort_keys=True))


if __name__ == "__main__":
    main()
