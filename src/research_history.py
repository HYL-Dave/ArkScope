"""Read-only, bounded projection over persisted Research threads and runs."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.research_runs import ResearchRun, ResearchRunStore


@dataclass(frozen=True)
class ResearchHistoryQuery:
    q: str | None = None
    ticker: str | None = None
    updated_from: str | None = None
    updated_before: str | None = None
    run_state: str = "all"
    archive_mode: str = "current"
    limit: int = 50
    offset: int = 0


@dataclass(frozen=True)
class ResearchHistoryThread:
    id: str
    title: str
    ticker: str | None
    provider: str | None
    model: str | None
    created_at: str
    updated_at: str
    archived_at: str | None
    latest_run_status: str | None


ResearchHistoryItem = ResearchHistoryThread


@dataclass(frozen=True)
class ResearchHistoryPage:
    items: tuple[ResearchHistoryThread, ...]
    total: int
    limit: int
    offset: int
    active_runs: tuple[ResearchRun, ...] = ()

    @property
    def threads(self) -> tuple[ResearchHistoryThread, ...]:
        return self.items


_RUN_STATES = frozenset(
    {"all", "active", "succeeded", "failed", "interrupted", "no_run"}
)
_ARCHIVE_MODES = frozenset({"current", "archived"})
_MAX_PAGE_LIMIT = 200
_MAX_SQLITE_OFFSET = 2**63 - 1

_LATEST_RUNS_CTE = """
WITH latest_runs AS (
    SELECT
        thread_id,
        status,
        ROW_NUMBER() OVER (
            PARTITION BY thread_id
            ORDER BY created_at DESC, id DESC
        ) AS row_number
    FROM research_runs
)
"""

_THREADS_FROM = """
FROM research_threads AS t
LEFT JOIN latest_runs AS lr
    ON lr.thread_id = t.id AND lr.row_number = 1
"""

_THREAD_COLUMNS = """
    t.id,
    t.title,
    t.ticker,
    t.provider,
    t.model,
    t.created_at,
    t.updated_at,
    t.archived_at,
    lr.status AS latest_run_status
"""


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _utc_bound(value: str | None, field: str) -> tuple[str | None, datetime | None]:
    if value is None:
        return None, None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"research history {field} must be a timezone-aware timestamp")

    candidate = value.strip()
    if candidate.endswith("Z"):
        candidate = f"{candidate[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ValueError(
            f"research history {field} must be a timezone-aware timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"research history {field} must be a timezone-aware timestamp")

    normalized = parsed.astimezone(timezone.utc)
    return normalized.isoformat(), normalized


def _normalized_query(
    *,
    q: str | None,
    ticker: str | None,
    updated_from: str | None,
    updated_before: str | None,
    run_state: str,
    archive_mode: str,
    limit: int,
    offset: int,
) -> ResearchHistoryQuery:
    if run_state not in _RUN_STATES:
        raise ValueError(f"invalid research run state: {run_state}")
    if archive_mode not in _ARCHIVE_MODES:
        raise ValueError(f"invalid research archive mode: {archive_mode}")
    if (
        isinstance(limit, bool)
        or not isinstance(limit, int)
        or not 1 <= limit <= _MAX_PAGE_LIMIT
    ):
        raise ValueError(f"research history limit must be between 1 and {_MAX_PAGE_LIMIT}")
    if (
        isinstance(offset, bool)
        or not isinstance(offset, int)
        or not 0 <= offset <= _MAX_SQLITE_OFFSET
    ):
        raise ValueError(
            f"research history offset must be between 0 and {_MAX_SQLITE_OFFSET}"
        )

    normalized_ticker = _optional_text(ticker)
    normalized_from, from_datetime = _utc_bound(updated_from, "updated_from")
    normalized_before, before_datetime = _utc_bound(updated_before, "updated_before")
    if (
        from_datetime is not None
        and before_datetime is not None
        and from_datetime >= before_datetime
    ):
        raise ValueError("research history updated window must be positive")

    return ResearchHistoryQuery(
        q=_optional_text(q),
        ticker=normalized_ticker.upper() if normalized_ticker else None,
        updated_from=normalized_from,
        updated_before=normalized_before,
        run_state=run_state,
        archive_mode=archive_mode,
        limit=limit,
        offset=offset,
    )


def _where(query: ResearchHistoryQuery) -> tuple[str, tuple[object, ...]]:
    clauses = [
        "t.archived_at IS NULL"
        if query.archive_mode == "current"
        else "t.archived_at IS NOT NULL"
    ]
    params: list[object] = []

    if query.q is not None:
        pattern = f"%{_escape_like(query.q)}%"
        clauses.append(
            "(t.title LIKE ? ESCAPE '\\' "
            "OR COALESCE(t.ticker, '') LIKE ? ESCAPE '\\')"
        )
        params.extend((pattern, pattern))
    if query.ticker is not None:
        clauses.append("UPPER(t.ticker) = ?")
        params.append(query.ticker)
    if query.updated_from is not None:
        clauses.append("t.updated_at >= ?")
        params.append(query.updated_from)
    if query.updated_before is not None:
        clauses.append("t.updated_at < ?")
        params.append(query.updated_before)

    if query.run_state == "active":
        clauses.append("lr.status IN ('queued', 'running')")
    elif query.run_state == "succeeded":
        clauses.append("lr.status = 'succeeded'")
    elif query.run_state == "failed":
        clauses.append("lr.status = 'failed'")
    elif query.run_state == "interrupted":
        clauses.append("lr.status IN ('cancelled', 'interrupted')")
    elif query.run_state == "no_run":
        clauses.append("lr.thread_id IS NULL")

    return " AND ".join(clauses), tuple(params)


class ResearchHistoryStore:
    """Read-only history query surface; authoritative stores own all schema."""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)

    def _connect(self) -> sqlite3.Connection:
        uri = Path(self.db_path).expanduser().resolve().as_uri() + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("PRAGMA query_only = ON")
        return conn

    @staticmethod
    def _thread(row: sqlite3.Row) -> ResearchHistoryThread:
        return ResearchHistoryThread(
            id=row["id"],
            title=row["title"],
            ticker=row["ticker"],
            provider=row["provider"],
            model=row["model"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            archived_at=row["archived_at"],
            latest_run_status=row["latest_run_status"],
        )

    def query_threads(
        self,
        *,
        q: str | None = None,
        ticker: str | None = None,
        updated_from: str | None = None,
        updated_before: str | None = None,
        run_state: str = "all",
        archive_mode: str = "current",
        limit: int = 50,
        offset: int = 0,
        run_store: ResearchRunStore | None = None,
    ) -> ResearchHistoryPage:
        query = _normalized_query(
            q=q,
            ticker=ticker,
            updated_from=updated_from,
            updated_before=updated_before,
            run_state=run_state,
            archive_mode=archive_mode,
            limit=limit,
            offset=offset,
        )
        where_sql, params = _where(query)
        count_sql = (
            f"{_LATEST_RUNS_CTE}\nSELECT COUNT(*) AS total\n"
            f"{_THREADS_FROM}\nWHERE {where_sql}"
        )
        items_sql = (
            f"{_LATEST_RUNS_CTE}\nSELECT {_THREAD_COLUMNS}\n"
            f"{_THREADS_FROM}\nWHERE {where_sql}\n"
            "ORDER BY t.updated_at DESC, t.id DESC\nLIMIT ? OFFSET ?"
        )

        active_runs: tuple[ResearchRun, ...] = ()
        with closing(self._connect()) as conn:
            conn.execute("BEGIN")
            try:
                total = int(conn.execute(count_sql, params).fetchone()["total"])
                rows = conn.execute(
                    items_sql,
                    (*params, query.limit, query.offset),
                ).fetchall()
                if run_store is not None:
                    active_by_thread = run_store.latest_active_for_threads(
                        [row["id"] for row in rows],
                        conn=conn,
                    )
                    active_runs = tuple(
                        active_by_thread[row["id"]]
                        for row in rows
                        if row["id"] in active_by_thread
                    )
            finally:
                conn.rollback()

        return ResearchHistoryPage(
            items=tuple(self._thread(row) for row in rows),
            total=total,
            limit=query.limit,
            offset=query.offset,
            active_runs=active_runs,
        )
