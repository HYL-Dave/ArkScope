#!/usr/bin/env python3
"""Analyze Seeking Alpha market-news density and suggest ET auto-sync windows."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.service.sa_market_news_density import summarize_market_news_density
from src.tools.db_config import load_database_url, load_sslmode


def _connect():
    env_path = PROJECT_ROOT / "config" / ".env"
    dsn = load_database_url(env_path)
    if not dsn:
        raise RuntimeError("DATABASE_URL not found in config/.env")
    sslmode = load_sslmode(env_path, dsn)
    return psycopg2.connect(dsn, sslmode=sslmode, connect_timeout=15)


def _fetch_rows(days: int) -> list[dict]:
    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            params = []
            where = ""
            if days > 0:
                where = "WHERE COALESCE(published_at, fetched_at) >= NOW() - (%s || ' days')::interval"
                params.append(int(days))
            cur.execute(
                f"""
                SELECT news_id,
                       published_at,
                       fetched_at,
                       detail_fetched_at,
                       comments_count,
                       tickers
                FROM sa_market_news
                {where}
                ORDER BY COALESCE(published_at, fetched_at) ASC NULLS LAST
                """,
                tuple(params),
            )
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def _print_windows(title: str, windows: list[dict]) -> None:
    print(f"\n{title}")
    if not windows:
        print("  no samples")
        return
    for window in windows:
        print(
            "  {start}-{end} ET -> every {interval} min "
            "(avg {avg:.2f}/hr, expected {expected:.2f}/run)".format(
                start=window["start_et"],
                end=window["end_et"],
                interval=window["interval_minutes"],
                avg=window["avg_items_per_hour"],
                expected=window["expected_items_per_sync"],
            )
        )


def _print_top_buckets(title: str, profile: list[dict], limit: int = 8) -> None:
    print(f"\n{title}")
    if not profile:
        print("  no samples")
        return
    ranked = sorted(profile, key=lambda row: row["avg_items_per_hour"], reverse=True)[:limit]
    for row in ranked:
        print(
            "  {label} ET -> avg {avg:.2f}/hr, median {median:.2f}/bucket, p90 {p90:.2f}, suggest {interval} min".format(
                label=row["bucket_label"],
                avg=row["avg_items_per_hour"],
                median=row["median_items_per_bucket_day"],
                p90=row["p90_items_per_bucket_day"],
                interval=row["recommended_interval_minutes"],
            )
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze SA market-news publish density and recommend ET sync windows.",
    )
    parser.add_argument("--days", type=int, default=30, help="Lookback window in days (0 = all history).")
    parser.add_argument(
        "--bucket-minutes",
        type=int,
        default=30,
        help="Aggregation bucket size in minutes (must divide 60; default: 30).",
    )
    parser.add_argument(
        "--target-items-per-sync",
        type=float,
        default=3.0,
        help="Longest interval is chosen if expected new items per sync stay under this target.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit raw JSON instead of a human-readable summary.",
    )
    args = parser.parse_args()

    rows = _fetch_rows(args.days)
    summary = summarize_market_news_density(
        rows,
        bucket_minutes=args.bucket_minutes,
        target_items_per_sync=args.target_items_per_sync,
    )

    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
        return 0

    date_range = summary.get("date_range_et") or {}
    print("SA Market News Density Analysis")
    print(f"  rows: {summary['total_items']}")
    print(f"  ET range: {date_range.get('start')} -> {date_range.get('end')}")
    print(f"  bucket size: {summary['bucket_minutes']} min")
    print(f"  target backlog per sync: {summary['target_items_per_sync']:.2f}")

    _print_windows("Weekday recommended windows", summary["weekday_windows"])
    _print_windows("Weekend recommended windows", summary["weekend_windows"])
    _print_top_buckets("Top weekday ET buckets", summary["weekday_profile"])
    _print_top_buckets("Top weekend ET buckets", summary["weekend_profile"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
