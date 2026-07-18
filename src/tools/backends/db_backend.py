"""
DatabaseBackend — reads data from PostgreSQL archive/runtime tables.

Implements the DataBackend protocol using psycopg2 with direct SQL queries.
Designed for both self-hosted PostgreSQL (Docker) and cloud services.
After N9 batch-1/2 and batch-3, market-data runtime domains that moved
local-first (``news``, ``news_scores``, ``prices``, ``iv_history``,
``fundamentals``, ``financial_data_cache``) are retired stubs here.
App-record archive methods are intentionally retained pending a separate
archive-policy decision.

Connection string format:
    postgresql://postgres:password@host:port/dbname
"""

from __future__ import annotations

from collections import defaultdict
import json
import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import pandas as pd
import psycopg2
import psycopg2.extras

from src.news_content_availability import ContentFilter, empty_content_counts

from .sqlite_backend import _IV_COLS, _NEWS_COLS, _NEWS_SEARCH_COLS, _NEWS_STATS_COLS

logger = logging.getLogger(__name__)

_PRICE_COLS = ["datetime", "open", "high", "low", "close", "volume"]


_COMMENT_SPACE_RE = re.compile(r"\s+")


def _normalize_comment_identity_value(value: Any) -> str:
    return _COMMENT_SPACE_RE.sub(" ", str(value or "")).strip()


def _normalize_comment_identity_key(commenter: Any, comment_text: Any) -> tuple[str, str]:
    return (
        _normalize_comment_identity_value(commenter).lower(),
        _normalize_comment_identity_value(comment_text).lower(),
    )


def _canonicalize_comment_date(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return text
    else:
        return str(value)

    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc).isoformat()
    return dt.astimezone(timezone.utc).isoformat()


def _merge_comment_record(target: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    if not target.get("commenter") and incoming.get("commenter"):
        target["commenter"] = incoming.get("commenter")
    if len(_normalize_comment_identity_value(incoming.get("comment_text"))) > len(
        _normalize_comment_identity_value(target.get("comment_text"))
    ):
        target["comment_text"] = incoming.get("comment_text")
    target["upvotes"] = max(
        int(target.get("upvotes") or 0),
        int(incoming.get("upvotes") or 0),
    )
    if not target.get("comment_date") and incoming.get("comment_date"):
        target["comment_date"] = incoming.get("comment_date")
    if not target.get("parent_comment_id") and incoming.get("parent_comment_id"):
        target["parent_comment_id"] = incoming.get("parent_comment_id")
    return target


def _comment_duplicate_sort_key(row: Dict[str, Any]) -> tuple[Any, ...]:
    return (
        0 if row.get("comment_date") is not None else 1,
        0 if row.get("parent_comment_id") else 1,
        row.get("comment_date") or datetime.max.replace(tzinfo=timezone.utc),
        row.get("id") or 0,
        row.get("comment_id") or "",
    )



def _plan_comment_duplicate_cleanup(rows: List[Dict[str, Any]]) -> Dict[str, List[Any]]:
    if len(rows) <= 1:
        return {"delete_ids": [], "parent_rewrites": []}

    normalized_rows: List[Dict[str, Any]] = []
    for row in rows:
        row_copy = dict(row)
        row_copy["comment_date"] = _canonicalize_comment_date(row_copy.get("comment_date"))
        if row_copy.get("comment_date"):
            row_copy["comment_date"] = datetime.fromisoformat(
                row_copy["comment_date"].replace("Z", "+00:00")
            )
        normalized_rows.append(row_copy)

    delete_ids: List[Any] = []
    parent_rewrites: Dict[str, str] = {}
    grouped_by_date: Dict[Optional[str], List[Dict[str, Any]]] = defaultdict(list)
    for row in normalized_rows:
        key = row["comment_date"].isoformat() if row.get("comment_date") else None
        grouped_by_date[key].append(row)

    kept_rows: List[Dict[str, Any]] = []
    for date_rows in grouped_by_date.values():
        date_rows.sort(key=_comment_duplicate_sort_key)
        keeper = date_rows[0]
        kept_rows.append(keeper)
        for duplicate in date_rows[1:]:
            if duplicate.get("comment_id") and keeper.get("comment_id"):
                parent_rewrites[duplicate["comment_id"]] = keeper["comment_id"]
            delete_ids.append(duplicate["id"])

    null_rows = [row for row in kept_rows if row.get("comment_date") is None]
    dated_rows = [row for row in kept_rows if row.get("comment_date") is not None]
    if len(dated_rows) == 1 and null_rows:
        canonical = dated_rows[0]
        for duplicate in null_rows:
            if duplicate.get("comment_id") and canonical.get("comment_id"):
                parent_rewrites[duplicate["comment_id"]] = canonical["comment_id"]
            delete_ids.append(duplicate["id"])
        kept_rows = [canonical]

    filtered_rows = [
        row for row in kept_rows
        if row.get("id") not in set(delete_ids) and row.get("comment_date") is not None
    ]
    filtered_rows.sort(key=_comment_duplicate_sort_key)
    removed_indexes = set()
    for i, left in enumerate(filtered_rows):
        if i in removed_indexes:
            continue
        left_dt = left.get("comment_date")
        if left_dt is None:
            continue
        for j in range(i + 1, len(filtered_rows)):
            if j in removed_indexes:
                continue
            right = filtered_rows[j]
            right_dt = right.get("comment_date")
            if right_dt is None:
                continue
            delta = right_dt - left_dt
            if delta == timedelta(hours=8):
                if left.get("comment_id") and right.get("comment_id"):
                    parent_rewrites[left["comment_id"]] = right["comment_id"]
                delete_ids.append(left["id"])
                removed_indexes.add(i)
                break
            if delta > timedelta(hours=8):
                break

    unique_delete_ids = list(dict.fromkeys(delete_ids))
    unique_parent_rewrites = [(src, dst) for src, dst in parent_rewrites.items() if src and dst and src != dst]
    return {"delete_ids": unique_delete_ids, "parent_rewrites": unique_parent_rewrites}


def _select_existing_comment_match(
    candidates: List[Dict[str, Any]], incoming_date: Optional[str]
) -> Optional[Dict[str, Any]]:
    if not candidates:
        return None

    same_date = [
        c for c in candidates if incoming_date and c.get("comment_date") == incoming_date
    ]
    if same_date:
        return same_date[0]

    null_date = [c for c in candidates if not c.get("comment_date")]
    dated = [c for c in candidates if c.get("comment_date")]

    if incoming_date:
        if len(candidates) == 1 and len(null_date) == 1:
            return null_date[0]
        return None

    if len(dated) == 1:
        return dated[0]
    if not dated and len(null_date) == 1:
        return null_date[0]
    return None


def _prepare_comments_for_upsert(
    existing_rows: List[Dict[str, Any]], incoming_comments: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    existing_by_key: Dict[tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for row in existing_rows:
        row_copy = dict(row)
        row_copy["comment_date"] = _canonicalize_comment_date(row_copy.get("comment_date"))
        key = _normalize_comment_identity_key(
            row_copy.get("commenter"), row_copy.get("comment_text")
        )
        existing_by_key[key].append(row_copy)

    prepared: List[Dict[str, Any]] = []
    prepared_by_id: Dict[str, Dict[str, Any]] = {}
    id_map: Dict[str, str] = {}

    for incoming in incoming_comments:
        item = dict(incoming)
        item["comment_date"] = _canonicalize_comment_date(item.get("comment_date"))
        key = _normalize_comment_identity_key(item.get("commenter"), item.get("comment_text"))
        candidates = existing_by_key.get(key, [])
        match = _select_existing_comment_match(candidates, item.get("comment_date"))

        if match:
            item["comment_id"] = match.get("comment_id")
            item["comment_date"] = item.get("comment_date") or match.get("comment_date")
            if not item.get("parent_comment_id") and match.get("parent_comment_id"):
                item["parent_comment_id"] = match.get("parent_comment_id")
            _merge_comment_record(match, item)
        else:
            existing_by_key[key].append(dict(item))

        original_id = incoming.get("comment_id")
        canonical_id = item.get("comment_id")
        if original_id and canonical_id:
            id_map[original_id] = canonical_id

        if canonical_id in prepared_by_id:
            _merge_comment_record(prepared_by_id[canonical_id], item)
            continue

        prepared_item = dict(item)
        prepared_by_id[canonical_id] = prepared_item
        prepared.append(prepared_item)

    for item in prepared:
        parent = item.get("parent_comment_id")
        if parent and parent in id_map:
            item["parent_comment_id"] = id_map[parent]
        if item.get("parent_comment_id") == item.get("comment_id"):
            item["parent_comment_id"] = None

    return prepared


class DatabaseBackend:
    """
    PostgreSQL data backend.

    Uses psycopg2 for direct SQL queries. Connection pooling is handled
    by creating connections on demand with a simple single-connection cache.
    """

    def __init__(self, dsn: str, sslmode: str = "prefer", connect_timeout: int = 15):
        """
        Args:
            dsn: PostgreSQL connection string.
            sslmode: SSL mode (disable for local Docker, require for cloud).
            connect_timeout: psycopg2 connect timeout (s). Local-only/strict mode passes a
                short value so a residual PG path fails FAST instead of hanging a desktop
                app when PG is unreachable.
        """
        self._dsn = dsn
        self._sslmode = sslmode
        self._connect_timeout = connect_timeout
        self._conn: Optional[psycopg2.extensions.connection] = None

    def _get_conn(self) -> psycopg2.extensions.connection:
        """Get or create a database connection, with stale-connection detection."""
        if not self._dsn:
            raise RuntimeError("PostgreSQL is not configured")
        if self._conn is not None and not self._conn.closed:
            # Ping to detect server-side disconnects (idle timeout etc.)
            try:
                with self._conn.cursor() as cur:
                    cur.execute("SELECT 1")
            except (psycopg2.OperationalError, psycopg2.InterfaceError):
                logger.info("Stale DB connection detected, reconnecting...")
                try:
                    self._conn.close()
                except Exception:
                    pass
                self._conn = None

        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(
                self._dsn,
                sslmode=self._sslmode,
                connect_timeout=self._connect_timeout,
            )
            self._conn.autocommit = True
        return self._conn

    def _query_df(self, sql: str, params: tuple = ()) -> pd.DataFrame:
        """Execute a query and return results as a DataFrame."""
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
            if not rows:
                return pd.DataFrame()
            return pd.DataFrame(rows)
        except psycopg2.Error as e:
            logger.error(f"Database query error: {e}")
            # Reset connection on error
            self._conn = None
            return pd.DataFrame()

    def _has_search_vector(self) -> bool:
        """Check if news.search_vector column exists (migration 006)."""
        if not hasattr(self, "_search_vector_ok"):
            df = self._query_df(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'news' AND column_name = 'search_vector'"
            )
            self._search_vector_ok = not df.empty
        return self._search_vector_ok

    def close(self):
        """Close the database connection."""
        if self._conn and not self._conn.closed:
            self._conn.close()
            self._conn = None

    # --------------------------------------------------------
    # News
    # --------------------------------------------------------

    def query_news(
        self,
        ticker: Optional[str] = None,
        days: int = 30,
        source: str = "auto",
        scored_only: bool = True,
        model: Optional[str] = None,
    ) -> pd.DataFrame:
        """Retired PG news surface; runtime authority is local SQLite."""
        return pd.DataFrame(columns=_NEWS_COLS)

    def query_news_feed(self, q: Optional[str] = None, ticker: Optional[str] = None,
                        source: Optional[str] = None, days: int = 30,
                        limit: int = 50, offset: int = 0,
                        content: ContentFilter = "all") -> dict:
        """Retired PG news feed surface."""
        return {
            "available": False,
            "items": [],
            "total": 0,
            "sources": {},
            "days": {},
            "content_counts": empty_content_counts(),
        }

    def query_news_search(
        self,
        query: str = "",
        ticker: Optional[str] = None,
        days: int = 30,
        limit: int = 20,
        scored_only: bool = True,
    ) -> pd.DataFrame:
        """Retired PG news search surface."""
        return pd.DataFrame(columns=_NEWS_SEARCH_COLS)

    def query_news_stats(
        self,
        ticker: Optional[str] = None,
        days: int = 30,
    ) -> pd.DataFrame:
        """Retired PG news stats surface."""
        return pd.DataFrame(columns=_NEWS_STATS_COLS)

    def query_news_scores(self, news_id: int) -> pd.DataFrame:
        """Retired PG news score surface."""
        return pd.DataFrame(columns=[
            "score_type", "model", "reasoning_effort", "score", "scored_at",
        ])

    # --------------------------------------------------------
    # Prices
    # --------------------------------------------------------

    def query_prices(
        self,
        ticker: str,
        interval: str = "15min",
        days: int = 30,
    ) -> pd.DataFrame:
        """Retired PG prices surface; runtime authority is local SQLite after P0-C."""
        return pd.DataFrame(columns=_PRICE_COLS)

    # --------------------------------------------------------
    # IV History
    # --------------------------------------------------------

    def query_iv_history(self, ticker: str) -> pd.DataFrame:
        """Retired PG IV history surface."""
        return pd.DataFrame(columns=_IV_COLS)

    # --------------------------------------------------------
    # Fundamentals
    # --------------------------------------------------------

    def query_fundamentals(self, ticker: str) -> dict:
        """Retired PG fundamentals surface."""
        return {}

    # --------------------------------------------------------
    # SEC Filings (same as FileBackend — API-based, not in DB)
    # --------------------------------------------------------

    def query_sec_filings(
        self,
        ticker: str,
        filing_types: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        SEC filing metadata.

        SEC filings are fetched via SEC EDGAR API, not stored in DB.
        Returns empty DataFrame (same as FileBackend).
        """
        return pd.DataFrame(columns=[
            "ticker", "filing_type", "filed_date", "url",
            "accession_number", "description", "period_of_report",
        ])

    # --------------------------------------------------------
    # Available tickers
    # --------------------------------------------------------

    def get_available_tickers(self, data_type: str) -> List[str]:
        """Retired PG ticker listing surface for market-data domains."""
        return []

    # --------------------------------------------------------
    # Research Reports
    # --------------------------------------------------------

    def insert_report(
        self,
        title: str,
        tickers: List[str],
        report_type: str,
        summary: str,
        conclusion: Optional[str] = None,
        confidence: Optional[float] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        file_path: Optional[str] = None,
        tools_used: Optional[List[str]] = None,
        tool_calls: Optional[int] = None,
        duration_seconds: Optional[float] = None,
        tokens_in: Optional[int] = None,
        tokens_out: Optional[int] = None,
    ) -> Optional[int]:
        """Insert a research report and return its ID."""
        conn = self._get_conn()
        sql = """
            INSERT INTO research_reports (
                title, tickers, report_type, summary, conclusion,
                confidence, provider, model, file_path,
                tools_used, tool_calls, duration_seconds,
                tokens_in, tokens_out
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s
            ) RETURNING id
        """
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (
                    title, tickers, report_type, summary, conclusion,
                    confidence, provider, model, file_path,
                    json.dumps(tools_used) if tools_used else None,
                    tool_calls, duration_seconds,
                    tokens_in, tokens_out,
                ))
                row = cur.fetchone()
                return row[0] if row else None
        except psycopg2.Error as e:
            logger.error(f"Failed to insert report: {e}")
            self._conn = None
            return None

    def query_reports(
        self,
        ticker: Optional[str] = None,
        days: int = 30,
        report_type: Optional[str] = None,
        limit: int = 20,
    ) -> pd.DataFrame:
        """Query research reports metadata."""
        from datetime import timedelta
        cutoff = (date.today() - timedelta(days=days)).isoformat()

        conditions = ["created_at >= %s"]
        params: list = [cutoff]

        if ticker:
            conditions.append("%s = ANY(tickers)")
            params.append(ticker.upper())

        if report_type:
            conditions.append("report_type = %s")
            params.append(report_type)

        where = " AND ".join(conditions)
        sql = f"""
            SELECT id, title, tickers, report_type, summary, conclusion,
                   confidence, model, file_path, tool_calls, duration_seconds,
                   TO_CHAR(created_at, 'YYYY-MM-DD"T"HH24:MI:SS') AS created_at
            FROM research_reports
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT %s
        """
        params.append(limit)

        df = self._query_df(sql, tuple(params))
        if df.empty:
            return pd.DataFrame(columns=[
                "id", "title", "tickers", "report_type", "summary",
                "conclusion", "confidence", "model", "file_path",
                "tool_calls", "duration_seconds", "created_at",
            ])
        return df

    def get_report_metadata(self, report_id: int) -> Optional[dict]:
        """Get full metadata for a single report."""
        sql = """
            SELECT id, title, tickers, report_type, summary, conclusion,
                   confidence, provider, model, file_path,
                   tools_used, tool_calls, duration_seconds,
                   tokens_in, tokens_out,
                   TO_CHAR(created_at, 'YYYY-MM-DD"T"HH24:MI:SS') AS created_at
            FROM research_reports
            WHERE id = %s
        """
        df = self._query_df(sql, (report_id,))
        if df.empty:
            return None
        return df.iloc[0].to_dict()

    # --------------------------------------------------------
    # Agent Memory (Episodic Memory — Phase 15)
    # --------------------------------------------------------

    def insert_memory(
        self,
        title: str,
        content: str,
        category: str = "note",
        tickers: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        importance: int = 5,
        source: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        file_path: Optional[str] = None,
    ) -> Optional[int]:
        """Insert a memory and return its ID."""
        conn = self._get_conn()
        sql = """
            INSERT INTO agent_memories (
                title, content, category, tickers, tags,
                importance, source, provider, model, file_path
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s
            ) RETURNING id
        """
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (
                    title, content, category, tickers, tags,
                    importance, source, provider, model, file_path,
                ))
                row = cur.fetchone()
                return row[0] if row else None
        except psycopg2.Error as e:
            logger.error(f"Failed to insert memory: {e}")
            self._conn = None
            return None

    def query_memories(
        self,
        query: str = "",
        category: Optional[str] = None,
        tickers: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        days: int = 90,
        limit: int = 10,
    ) -> pd.DataFrame:
        """Query memories with optional full-text search."""
        cutoff = (date.today() - timedelta(days=days)).isoformat()

        conditions = ["created_at >= %s"]
        params: list = [cutoff]

        # Full-text search
        if query.strip():
            conditions.append(
                "to_tsvector('english', title || ' ' || content) "
                "@@ plainto_tsquery('english', %s)"
            )
            params.append(query)

        if category:
            conditions.append("category = %s")
            params.append(category)

        if tickers:
            conditions.append("tickers && %s")
            params.append([t.upper() for t in tickers])

        if tags:
            conditions.append("tags && %s")
            params.append(tags)

        where = " AND ".join(conditions)

        # Order by relevance if searching, otherwise by importance + date
        if query.strip():
            order = (
                "ts_rank(to_tsvector('english', title || ' ' || content), "
                "plainto_tsquery('english', %s)) DESC, importance DESC"
            )
            params.append(query)
        else:
            order = "importance DESC, created_at DESC"

        sql = f"""
            SELECT id, title, content, category, tickers, tags,
                   importance, source,
                   TO_CHAR(created_at, 'YYYY-MM-DD"T"HH24:MI:SS') AS created_at
            FROM agent_memories
            WHERE {where}
            ORDER BY {order}
            LIMIT %s
        """
        params.append(limit)

        return self._query_df(sql, tuple(params))

    def list_memories_meta(
        self,
        category: Optional[str] = None,
        days: int = 90,
        limit: int = 20,
    ) -> pd.DataFrame:
        """List memory metadata (no full content body)."""
        cutoff = (date.today() - timedelta(days=days)).isoformat()

        conditions = ["created_at >= %s"]
        params: list = [cutoff]

        if category:
            conditions.append("category = %s")
            params.append(category)

        where = " AND ".join(conditions)
        sql = f"""
            SELECT id, title, category, tickers, tags, importance,
                   TO_CHAR(created_at, 'YYYY-MM-DD"T"HH24:MI:SS') AS created_at
            FROM agent_memories
            WHERE {where}
            ORDER BY importance DESC, created_at DESC
            LIMIT %s
        """
        params.append(limit)

        return self._query_df(sql, tuple(params))

    def delete_memory(self, memory_id: int) -> Optional[str]:
        """Delete a memory. Returns its file_path (or None if not found)."""
        conn = self._get_conn()
        sql = "DELETE FROM agent_memories WHERE id = %s RETURNING file_path"
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (memory_id,))
                row = cur.fetchone()
                return row[0] if row else None
        except psycopg2.Error as e:
            logger.error(f"Failed to delete memory: {e}")
            self._conn = None
            return None

    # --------------------------------------------------------
    # Agent Queries
    # --------------------------------------------------------

    def insert_agent_query(
        self,
        question: str,
        answer: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        tools_used: Optional[List[str]] = None,
        duration_ms: Optional[int] = None,
        tokens_in: Optional[int] = None,
        tokens_out: Optional[int] = None,
    ) -> Optional[int]:
        """Insert an agent query log and return its ID."""
        conn = self._get_conn()
        sql = """
            INSERT INTO agent_queries (
                question, answer, provider, model,
                tools_used, duration_ms, tokens_in, tokens_out
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (
                    question, answer, provider, model,
                    json.dumps(tools_used) if tools_used else None,
                    duration_ms, tokens_in, tokens_out,
                ))
                row = cur.fetchone()
                return row[0] if row else None
        except psycopg2.Error as e:
            logger.error(f"Failed to insert agent query: {e}")
            self._conn = None
            return None

    # --------------------------------------------------------
    # Financial Data Cache
    # --------------------------------------------------------

    def get_financial_cache(self, cache_key: str) -> Optional[dict]:
        """Retired PG financial cache surface; runtime cache is local-only."""
        return None

    def set_financial_cache(
        self,
        cache_key: str,
        ticker: str,
        data: dict,
        ttl_days: int = 90,
        source: str = "sec_edgar",
    ) -> bool:
        """Retired PG financial cache surface; runtime cache is local-only."""
        return False

    # --------------------------------------------------------
    # Health / Freshness Statistics
    # --------------------------------------------------------

    def query_health_stats(self) -> Dict[str, Any]:
        """Retired PG market-data health surface; provider health reads local stores."""
        return {
            "news": {"rows": [], "error": None},
            "prices": {"rows": [], "error": None},
            "iv_history": {"rows": [], "error": None},
            "financial_cache": {"rows": [], "error": None},
        }

    # ================================================================
    # Seeking Alpha (retired PG surface)
    # ================================================================
    # PG sa_* tables were archived/dropped in N9 batch-1. Runtime SA reads/writes
    # route through SACaptureDatabaseBackend / sa_capture.db. These methods remain
    # as tombstone-compatible stubs so old DatabaseBackend call sites fail closed
    # without opening PG.

    def apply_sa_refresh(
        self,
        scope: str,
        picks: list,
        attempt_ts,
        snapshot_ts,
    ) -> int:
        return 0

    def record_sa_refresh_failure(self, scope: str, attempt_ts, error: str) -> None:
        return None

    def query_sa_picks(
        self,
        portfolio_status: Optional[str] = None,
        symbol: Optional[str] = None,
        include_stale: bool = False,
    ) -> list:
        return []

    def get_sa_pick_detail(
        self, symbol: str, picked_date: Optional[str] = None
    ) -> Optional[dict]:
        return None

    def update_sa_pick_detail(
        self, symbol: str, picked_date: str, content: str
    ) -> bool:
        return False

    def get_sa_refresh_meta(self) -> dict:
        return {}

    def upsert_sa_market_news(self, items: list) -> int:
        return 0

    def query_sa_market_news(
        self,
        ticker: Optional[str] = None,
        keyword: Optional[str] = None,
        limit: int = 20,
    ) -> list:
        return []

    def query_sa_market_news_recent_ids(self, limit: int = 200) -> list[str]:
        return []

    def query_sa_market_news_need_detail(
        self,
        news_ids: list | None = None,
        detail_cache_hours: int = 24,
        limit: int = 50,
        exclude_news_ids: list | None = None,
        published_within_hours: int | None = None,
    ) -> list:
        return []

    def invalidate_dirty_sa_market_news_detail(self) -> int:
        return 0

    def save_sa_market_news_detail(self, news_id: str, body_markdown: str) -> bool:
        return False

    def upsert_sa_articles_meta(self, articles: list) -> int:
        return 0

    def sanitize_corrupted_sa_comments_counts(self) -> int:
        return 0

    def cleanup_mixed_null_date_comment_duplicates(self) -> Dict[str, int]:
        return {
            "groups_processed": 0,
            "comments_deleted": 0,
            "parent_links_repointed": 0,
        }

    def save_article_with_comments(
        self,
        article_id: str,
        body_markdown: str,
        comments: list,
        *,
        detail_ticker: str | None = None,
        detail_ticker_observed_at=None,
        provider_comments_count=None,
        comment_scan_mode="quick",
        comment_scan_stop_reason=None,
        comment_scan_stable_bottom_rounds=0,
    ) -> dict:
        return {
            "ok": False,
            "prepared_comments": 0,
            "stored_comments_total": 0,
            "net_new_comments": 0,
            "reason": "pg_sa_retired",
        }

    def update_article_comments(
        self,
        article_id: str,
        comments: list,
        *,
        provider_comments_count=None,
        comment_scan_mode="quick",
        comment_scan_stop_reason=None,
        comment_scan_stable_bottom_rounds=0,
    ) -> Dict[str, int]:
        return {
            "prepared_comments": 0,
            "stored_comments_total": 0,
            "net_new_comments": 0,
        }

    def audit_unresolved_symbols(self) -> dict:
        return {"unresolved_symbols": [], "resolved_by_fulltext": 0}

    def reconcile_sa_articles(self, **kwargs) -> dict:
        return {
            "status": "unavailable",
            "reason": "pg_sa_retired",
            "enrichment": [],
        }

    def query_sa_article_review_queue(self, limit: int = 50) -> dict:
        return {"events": [], "total": 0}

    def resolve_sa_reconciliation_event(self, **kwargs) -> dict:
        return {"status": "unavailable", "reason": "pg_sa_retired"}

    def accept_sa_article_link(self, **kwargs) -> dict:
        return {"status": "unavailable", "reason": "pg_sa_retired"}

    def reject_sa_article_candidate(self, **kwargs) -> dict:
        return {"status": "unavailable", "reason": "pg_sa_retired"}

    def query_sa_articles(
        self,
        ticker: str = None,
        keyword: str = None,
        article_type: str = None,
        limit: int = 10,
    ) -> list:
        return []

    def get_sa_article_with_comments(self, article_id: str) -> dict:
        return None
