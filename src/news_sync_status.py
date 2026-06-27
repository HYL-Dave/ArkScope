"""Read-only status model for direct provider -> SQLite news ingestion."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Optional


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def _latest(values: list[Optional[str]]) -> Optional[str]:
    present = [value for value in values if value]
    return max(present) if present else None


def read_news_sync_status(db_path: str | Path) -> Optional[dict[str, Any]]:
    """Combine aggregate direct-news runs with current per-ticker failures.

    The connection is opened in SQLite read-only mode. ``None`` means the direct
    writer has no durable telemetry yet; callers use that to replace, rather than
    accidentally retain, stale PG-mirror news status after cutover.
    """
    path = Path(db_path)
    if not path.exists():
        return None

    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        has_runs = _table_exists(conn, "provider_sync_runs")
        has_meta = _table_exists(conn, "provider_sync_meta")
        if not has_runs and not has_meta:
            return None

        runs: dict[str, dict[str, Any]] = {}
        if has_runs:
            rows = conn.execute(
                "SELECT r.* FROM provider_sync_runs r "
                "JOIN (SELECT provider, MAX(id) AS id FROM provider_sync_runs "
                "      WHERE domain='news' GROUP BY provider) latest ON latest.id=r.id "
                "ORDER BY r.provider"
            ).fetchall()
            for row in rows:
                provider = str(row["provider"])
                success = conn.execute(
                    "SELECT MAX(finished_at) FROM provider_sync_runs "
                    "WHERE domain='news' AND provider=? AND status='succeeded'",
                    (provider,),
                ).fetchone()[0]
                runs[provider] = {
                    "status": row["status"],
                    "last_success": success,
                    "last_attempt": row["finished_at"] or row["started_at"],
                    "rows_added": int(row["rows_added"] or 0),
                    "tickers_scanned": int(row["tickers_scanned"] or 0),
                    "run_error": row["error"],
                }

        errors: dict[str, list[dict[str, Any]]] = {}
        if has_meta:
            rows = conn.execute(
                "SELECT provider,ticker,last_error,updated_at FROM provider_sync_meta "
                "WHERE interval='news' AND last_error IS NOT NULL AND TRIM(last_error)<>'' "
                "ORDER BY provider,ticker"
            ).fetchall()
            for row in rows:
                errors.setdefault(str(row["provider"]), []).append({
                    "ticker": row["ticker"],
                    "error": row["last_error"],
                    "updated_at": row["updated_at"],
                })

        provider_ids = sorted(set(runs) | set(errors))
        if not provider_ids:
            return None

        providers: dict[str, dict[str, Any]] = {}
        for provider in provider_ids:
            run = runs.get(provider, {})
            ticker_errors = errors.get(provider, [])
            messages: list[str] = []
            if run.get("run_error"):
                messages.append(str(run["run_error"]))
            messages.extend(f"{item['ticker']}: {item['error']}" for item in ticker_errors)
            run_status = run.get("status")
            status = (
                "failed" if run_status == "failed"
                else "running" if run_status == "running"
                else "partial" if ticker_errors
                else run_status or "partial"
            )
            providers[provider] = {
                "status": status,
                "last_success": run.get("last_success"),
                "last_attempt": run.get("last_attempt"),
                "last_error": "; ".join(messages) or None,
                "rows_added": int(run.get("rows_added") or 0),
                "tickers_scanned": int(run.get("tickers_scanned") or 0),
                "ticker_errors": ticker_errors,
            }

        statuses = {item["status"] for item in providers.values()}
        overall = (
            "failed" if "failed" in statuses
            else "running" if "running" in statuses
            else "partial" if "partial" in statuses
            else "succeeded"
        )
        last_attempt = _latest([item["last_attempt"] for item in providers.values()])
        messages = [
            f"{provider}: {item['last_error']}"
            for provider, item in providers.items()
            if item["last_error"]
        ]
        return {
            "status": overall,
            "last_success": _latest([item["last_success"] for item in providers.values()]),
            "last_attempt": last_attempt,
            "last_error": "; ".join(messages) or None,
            "rows_added": sum(item["rows_added"] for item in providers.values()),
            "updated_at": last_attempt,
            "providers": providers,
        }
    finally:
        conn.close()


def overlay_news_sync_status(
    mirror_sync: dict[str, Any], db_path: str | Path
) -> dict[str, Any]:
    """Replace only the news slice when the direct writer is active."""
    from src.news_providers import use_local_news_enabled

    if not use_local_news_enabled():
        return mirror_sync
    out = dict(mirror_sync)
    out["news"] = read_news_sync_status(db_path)
    return out
