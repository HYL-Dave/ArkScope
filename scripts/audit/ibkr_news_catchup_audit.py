"""Read-only IBKR normalized-news catch-up risk audit.

This script deliberately reads only local SQLite state. It does not connect to
IBKR Gateway or instantiate provider clients.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
import json
from pathlib import Path
import sqlite3
from typing import Any


PROVIDER_CAP_PER_TICKER = 300
WINDOW_DAYS = (7, 14, 30)
OBSERVED_QUIET_WINDOW = {
    "label": "observed_quiet_window_2026_06_25_to_2026_07_05",
    "start_date": "2026-06-25",
    "end_date": "2026-07-05",
}
CAVEATS = [
    "Local SQLite counts are a lower bound: articles already missed by a prior "
    "provider-side 300 cap cannot be counted locally.",
    "A ticker-window below 300 proves only that observed local rows are below "
    "the cap, not that no historical tail was ever truncated before this audit.",
    "days_to_300 estimates assume roughly stable article arrival rates and "
    "should be treated as planning guidance, not a guarantee.",
]


def _connect_ro(path: str | Path) -> sqlite3.Connection:
    uri = f"file:{Path(path)}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _as_of(value: str | None) -> date:
    if value:
        return date.fromisoformat(value)
    return datetime.utcnow().date()


def _rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _count_summary(rows: list[dict[str, Any]], count_key: str) -> dict[str, Any]:
    counts = [int(row[count_key] or 0) for row in rows]
    return {
        "tickers": len(rows),
        "min_rows": min(counts) if counts else 0,
        "max_rows": max(counts) if counts else 0,
        "avg_rows": round(sum(counts) / len(counts), 2) if counts else 0.0,
        "tickers_ge_300": sum(1 for count in counts if count >= 300),
        "tickers_ge_250": sum(1 for count in counts if count >= 250),
        "tickers_ge_200": sum(1 for count in counts if count >= 200),
        "tickers_ge_100": sum(1 for count in counts if count >= 100),
    }


def _window_rows(conn: sqlite3.Connection, *, start_date: date, count_key: str) -> list[dict[str, Any]]:
    return _rows(
        conn,
        f"""
        SELECT
            t.ticker,
            COUNT(DISTINCT a.id) AS {count_key},
            MIN(a.published_at) AS oldest,
            MAX(a.published_at) AS newest
        FROM news_articles a
        JOIN news_article_tickers t ON t.article_id = a.id
        WHERE a.source = 'ibkr'
          AND substr(a.published_at, 1, 10) >= ?
        GROUP BY t.ticker
        ORDER BY {count_key} DESC, t.ticker
        """,
        (start_date.isoformat(),),
    )


def _all_ticker_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return _rows(
        conn,
        """
        SELECT
            t.ticker,
            COUNT(DISTINCT a.id) AS total_rows,
            MIN(a.published_at) AS oldest,
            MAX(a.published_at) AS newest
        FROM news_articles a
        JOIN news_article_tickers t ON t.article_id = a.id
        WHERE a.source = 'ibkr'
        GROUP BY t.ticker
        ORDER BY total_rows DESC, t.ticker
        """,
    )


def _source_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT
            COUNT(*) AS rows,
            MIN(published_at) AS oldest,
            MAX(published_at) AS newest
        FROM news_articles
        WHERE source = 'ibkr'
        """
    ).fetchone()
    return dict(row) if row else {"rows": 0, "oldest": None, "newest": None}


def _provider_runs(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return _rows(
        conn,
        """
        SELECT provider, domain, status, tickers_scanned, rows_added, error,
               started_at, finished_at
        FROM provider_sync_runs
        WHERE provider = 'ibkr' AND domain = 'news'
        ORDER BY id DESC
        LIMIT 8
        """,
    )


def _scheduler_state(conn: sqlite3.Connection) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT source, last_attempt, last_status, last_error, updated_at,
               last_result, continuation
        FROM scheduler_state
        WHERE source = 'ibkr_news'
        """
    ).fetchone()
    if row is None:
        return None
    data = dict(row)
    for key in ("last_result", "continuation"):
        if data.get(key):
            try:
                data[key] = json.loads(data[key])
            except json.JSONDecodeError:
                pass
    return data


def _days_to_300(rows_30d: int) -> float | None:
    if rows_30d <= 0:
        return None
    return round(PROVIDER_CAP_PER_TICKER / (rows_30d / 30.0), 1)


def _top_tickers(all_rows: list[dict[str, Any]], rows_30d: dict[str, int]) -> list[dict[str, Any]]:
    out = []
    for row in all_rows[:30]:
        ticker = row["ticker"]
        count_30d = int(rows_30d.get(ticker, 0))
        item = dict(row)
        item["rows_30d"] = count_30d
        item["estimated_days_to_300_from_30d_rate"] = _days_to_300(count_30d)
        out.append(item)
    return out


def _gap_check(conn: sqlite3.Connection, *, label: str, start_date: str, end_date: str) -> dict[str, Any]:
    rows = _rows(
        conn,
        """
        SELECT
            t.ticker,
            COUNT(DISTINCT a.id) AS rows,
            MIN(a.published_at) AS oldest,
            MAX(a.published_at) AS newest
        FROM news_articles a
        JOIN news_article_tickers t ON t.article_id = a.id
        WHERE a.source = 'ibkr'
          AND substr(a.published_at, 1, 10) >= ?
          AND substr(a.published_at, 1, 10) <= ?
        GROUP BY t.ticker
        ORDER BY rows DESC, t.ticker
        """,
        (start_date, end_date),
    )
    summary = _count_summary(rows, "rows")
    summary.update(
        {
            "label": label,
            "start_date": start_date,
            "end_date": end_date,
            "top_tickers": rows[:30],
            "assessment": "at_or_above_cap" if summary["tickers_ge_300"] else "below_cap",
        }
    )
    return summary


def build_report(market_db: str | Path, profile_db: str | Path, *, as_of: str | None = None) -> dict[str, Any]:
    as_of_date = _as_of(as_of)
    with _connect_ro(market_db) as market_conn, _connect_ro(profile_db) as profile_conn:
        windows = {}
        window_rows_by_name = {}
        for days in WINDOW_DAYS:
            key = f"{days}d"
            rows = _window_rows(
                market_conn,
                start_date=as_of_date - timedelta(days=days),
                count_key=f"rows_{days}d",
            )
            window_rows_by_name[key] = rows
            summary = _count_summary(rows, f"rows_{days}d")
            summary["top_tickers"] = rows[:30]
            windows[key] = summary

        rows_30d = {
            row["ticker"]: int(row["rows_30d"] or 0)
            for row in window_rows_by_name.get("30d", [])
        }
        all_rows = _all_ticker_rows(market_conn)
        gap = _gap_check(market_conn, **OBSERVED_QUIET_WINDOW)

        current_cadence = "ok" if windows["7d"]["tickers_ge_300"] == 0 else "at_risk"
        long_quiet = "ok" if windows["30d"]["tickers_ge_300"] == 0 else "at_risk"
        return {
            "ok": True,
            "source": "ibkr",
            "as_of": as_of_date.isoformat(),
            "provider_cap_per_ticker": PROVIDER_CAP_PER_TICKER,
            "source_summary": _source_summary(market_conn),
            "windows": windows,
            "top_tickers": _top_tickers(all_rows, rows_30d),
            "gap_checks": [gap],
            "scheduler_state": _scheduler_state(profile_conn),
            "provider_runs": _provider_runs(market_conn),
            "caveats": list(CAVEATS),
            "writer_budget_note": (
                "src.news_normalized.ibkr_cli.DEFAULT_MAX_ARTICLES is 50000; "
                "the catch-up risk is provider-side 300/ticker, not writer budget."
            ),
            "risk": {
                "current_cadence": current_cadence,
                "long_quiet_window": long_quiet,
                "reason": (
                    "IBKR reqHistoricalNews returns only the 300 most-recent "
                    "headlines per ticker"
                ),
            },
        }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit IBKR news catch-up cap risk.")
    parser.add_argument("--market-db", default="data/market_data.db")
    parser.add_argument("--profile-db", default="data/profile_state.db")
    parser.add_argument("--as-of", default=None)
    parser.add_argument("--json-out", default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(args.market_db, args.profile_db, as_of=args.as_of)
    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    summary = {
        "ok": report["ok"],
        "as_of": report["as_of"],
        "current_cadence": report["risk"]["current_cadence"],
        "long_quiet_window": report["risk"]["long_quiet_window"],
        "max_7d": report["windows"]["7d"]["max_rows"],
        "max_30d": report["windows"]["30d"]["max_rows"],
        "gap_max": report["gap_checks"][0]["max_rows"],
    }
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
