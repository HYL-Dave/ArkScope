"""
DatabaseBackend — reads data from PostgreSQL.

Implements the DataBackend protocol using psycopg2 with direct SQL queries.
Designed for both self-hosted PostgreSQL (Docker) and cloud services.

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

logger = logging.getLogger(__name__)


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

    def __init__(self, dsn: str, sslmode: str = "prefer"):
        """
        Args:
            dsn: PostgreSQL connection string.
            sslmode: SSL mode (disable for local Docker, require for cloud).
        """
        self._dsn = dsn
        self._sslmode = sslmode
        self._conn: Optional[psycopg2.extensions.connection] = None

    def _get_conn(self) -> psycopg2.extensions.connection:
        """Get or create a database connection, with stale-connection detection."""
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
                connect_timeout=15,
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
        """Query news articles with scores from news_scores table.

        Args:
            ticker: Filter by ticker symbol.
            days: Number of days to look back.
            source: Data source filter ('ibkr', 'polygon', 'auto').
            scored_only: Only return articles with at least one score.
            model: Specific model to get scores from (e.g. 'gpt_5_2').
                   If None, uses the latest score per article via
                   the news_latest_scores view.
        """
        cutoff = (date.today() - timedelta(days=days)).isoformat()

        # Build score JOIN — either specific model or latest
        if model:
            # Use LATERAL subqueries to pick the latest score per
            # (news_id, score_type, model) — the UNIQUE key includes
            # reasoning_effort, so a plain JOIN can produce duplicates.
            score_join = """
                LEFT JOIN LATERAL (
                    SELECT score, model FROM news_scores
                    WHERE news_id = n.id AND score_type = 'sentiment'
                      AND model = %s
                    ORDER BY scored_at DESC LIMIT 1
                ) s_sent ON true
                LEFT JOIN LATERAL (
                    SELECT score, model FROM news_scores
                    WHERE news_id = n.id AND score_type = 'risk'
                      AND model = %s
                    ORDER BY scored_at DESC LIMIT 1
                ) s_risk ON true
            """
            params: list = [model, model, cutoff]
        else:
            score_join = """
                LEFT JOIN news_latest_scores s_sent
                    ON s_sent.news_id = n.id AND s_sent.score_type = 'sentiment'
                LEFT JOIN news_latest_scores s_risk
                    ON s_risk.news_id = n.id AND s_risk.score_type = 'risk'
            """
            params = [cutoff]

        conditions = ["n.published_at >= %s"]

        if ticker:
            conditions.append("n.ticker = %s")
            params.append(ticker.upper())

        if source != "auto":
            conditions.append("n.source = %s")
            params.append(source)

        if scored_only:
            conditions.append("(s_sent.score IS NOT NULL OR s_risk.score IS NOT NULL)")

        where = " AND ".join(conditions)
        sql = f"""
            SELECT
                TO_CHAR(n.published_at, 'YYYY-MM-DD') AS date,
                n.ticker, n.title, n.source, n.url, n.publisher,
                s_sent.score AS sentiment_score,
                s_risk.score AS risk_score,
                COALESCE(s_sent.model, s_risk.model) AS scored_model,
                n.description
            FROM news n
            {score_join}
            WHERE {where}
            ORDER BY n.published_at DESC
        """

        empty_cols = [
            "date", "ticker", "title", "source", "url",
            "publisher", "sentiment_score", "risk_score", "description",
        ]
        df = self._query_df(sql, tuple(params))
        if df.empty:
            return pd.DataFrame(columns=empty_cols)
        return df

    def query_news_search(
        self,
        query: str = "",
        ticker: Optional[str] = None,
        days: int = 30,
        limit: int = 20,
        scored_only: bool = True,
    ) -> pd.DataFrame:
        """Search news with full-text search or trigram matching.

        Uses PostgreSQL tsvector/GIN for multi-word queries and
        pg_trgm ILIKE for short/partial matches. All filtering at DB level.
        """
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        conditions = ["n.published_at >= %s"]
        params: list = [cutoff]

        # Score joins (latest scores)
        score_join = """
            LEFT JOIN news_latest_scores s_sent
                ON s_sent.news_id = n.id AND s_sent.score_type = 'sentiment'
            LEFT JOIN news_latest_scores s_risk
                ON s_risk.news_id = n.id AND s_risk.score_type = 'risk'
        """

        if ticker:
            conditions.append("n.ticker = %s")
            params.append(ticker.upper())

        if scored_only:
            conditions.append("(s_sent.score IS NOT NULL OR s_risk.score IS NOT NULL)")

        # Full-text search vs ILIKE fallback
        use_fts = bool(query.strip()) and len(query.strip()) >= 3 and self._has_search_vector()
        if use_fts:
            conditions.append("n.search_vector @@ plainto_tsquery('english', %s)")
            params.append(query)

        where = " AND ".join(conditions)

        if use_fts:
            order = (
                "ts_rank(n.search_vector, plainto_tsquery('english', %s)) DESC, "
                "n.published_at DESC"
            )
            params.append(query)
        else:
            order = "n.published_at DESC"

        # ILIKE fallback when FTS unavailable or short query
        if query.strip() and not use_fts:
            conditions.append("(n.title ILIKE %s OR n.description ILIKE %s)")
            pattern = f"%{query.strip()}%"
            params.append(pattern)
            params.append(pattern)
            where = " AND ".join(conditions)

        sql = f"""
            SELECT
                TO_CHAR(n.published_at, 'YYYY-MM-DD') AS date,
                n.ticker, n.title, n.source, n.url, n.publisher,
                s_sent.score AS sentiment_score,
                s_risk.score AS risk_score,
                n.description
            FROM news n
            {score_join}
            WHERE {where}
            ORDER BY {order}
            LIMIT %s
        """
        params.append(limit)

        df = self._query_df(sql, tuple(params))
        if df.empty:
            return pd.DataFrame(columns=[
                "date", "ticker", "title", "source", "url",
                "publisher", "sentiment_score", "risk_score", "description",
            ])
        return df

    def query_news_stats(
        self,
        ticker: Optional[str] = None,
        days: int = 30,
    ) -> pd.DataFrame:
        """Get lightweight per-ticker news statistics.

        Returns one row per ticker with article_count, scored_count,
        date_range, avg_sentiment, avg_risk. Single GROUP BY query — very fast.
        """
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        conditions = ["n.published_at >= %s"]
        params: list = [cutoff]

        if ticker:
            conditions.append("n.ticker = %s")
            params.append(ticker.upper())

        where = " AND ".join(conditions)
        sql = f"""
            SELECT
                n.ticker,
                COUNT(*) AS article_count,
                COUNT(s_sent.score) AS scored_count,
                TO_CHAR(MIN(n.published_at), 'YYYY-MM-DD') AS earliest_date,
                TO_CHAR(MAX(n.published_at), 'YYYY-MM-DD') AS latest_date,
                ROUND(AVG(s_sent.score)::numeric, 2) AS avg_sentiment,
                ROUND(AVG(s_risk.score)::numeric, 2) AS avg_risk,
                COUNT(*) FILTER (WHERE s_sent.score >= 4) AS bullish_count,
                COUNT(*) FILTER (WHERE s_sent.score <= 2) AS bearish_count
            FROM news n
            LEFT JOIN news_latest_scores s_sent
                ON s_sent.news_id = n.id AND s_sent.score_type = 'sentiment'
            LEFT JOIN news_latest_scores s_risk
                ON s_risk.news_id = n.id AND s_risk.score_type = 'risk'
            WHERE {where}
            GROUP BY n.ticker
            ORDER BY article_count DESC
        """

        df = self._query_df(sql, tuple(params))
        if df.empty:
            return pd.DataFrame(columns=[
                "ticker", "article_count", "scored_count",
                "earliest_date", "latest_date",
                "avg_sentiment", "avg_risk",
                "bullish_count", "bearish_count",
            ])
        return df

    def query_news_scores(self, news_id: int) -> pd.DataFrame:
        """Get all scores for a specific news article (multi-model comparison).

        Returns:
            DataFrame with columns: score_type, model, reasoning_effort, score, scored_at
        """
        sql = """
            SELECT score_type, model, reasoning_effort, score,
                   TO_CHAR(scored_at, 'YYYY-MM-DD"T"HH24:MI:SS') AS scored_at
            FROM news_scores
            WHERE news_id = %s
            ORDER BY scored_at DESC
        """
        df = self._query_df(sql, (news_id,))
        if df.empty:
            return pd.DataFrame(columns=[
                "score_type", "model", "reasoning_effort", "score", "scored_at",
            ])
        return df

    # --------------------------------------------------------
    # Prices
    # --------------------------------------------------------

    def query_prices(
        self,
        ticker: str,
        interval: str = "15min",
        days: int = 30,
    ) -> pd.DataFrame:
        """Query OHLCV price bars from the database.

        For daily/hourly intervals, falls back to server-side aggregation
        from 15min bars if no native rows exist at that interval.
        """
        ticker = ticker.upper()

        # Normalize interval names
        interval_map = {"1h": "1h", "hourly": "1h", "1d": "1d", "daily": "1d", "15min": "15min"}
        db_interval = interval_map.get(interval, interval)

        cutoff = (date.today() - timedelta(days=days)).isoformat()
        empty = pd.DataFrame(columns=["datetime", "open", "high", "low", "close", "volume"])

        sql = """
            SELECT
                TO_CHAR(datetime AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS+0000') AS datetime,
                open, high, low, close, volume
            FROM prices
            WHERE ticker = %s AND interval = %s AND datetime >= %s
            ORDER BY datetime ASC
        """

        df = self._query_df(sql, (ticker, db_interval, cutoff))
        if not df.empty:
            return df

        # Fallback: aggregate from 15min bars if requesting daily or hourly
        if db_interval in ("1d", "1h") and db_interval != "15min":
            trunc = "day" if db_interval == "1d" else "hour"
            agg_sql = f"""
                SELECT
                    TO_CHAR(date_trunc('{trunc}', datetime AT TIME ZONE 'UTC'),
                            'YYYY-MM-DD"T"HH24:MI:SS+0000') AS datetime,
                    (array_agg(open ORDER BY datetime ASC))[1] AS open,
                    MAX(high) AS high,
                    MIN(low) AS low,
                    (array_agg(close ORDER BY datetime DESC))[1] AS close,
                    SUM(volume) AS volume
                FROM prices
                WHERE ticker = %s AND interval = '15min' AND datetime >= %s
                GROUP BY date_trunc('{trunc}', datetime AT TIME ZONE 'UTC')
                ORDER BY 1 ASC
            """
            df = self._query_df(agg_sql, (ticker, cutoff))
            if not df.empty:
                return df

        return empty

    # --------------------------------------------------------
    # IV History
    # --------------------------------------------------------

    def query_iv_history(self, ticker: str) -> pd.DataFrame:
        """Query IV history from the database."""
        ticker = ticker.upper()

        sql = """
            SELECT
                TO_CHAR(date, 'YYYY-MM-DD') AS date,
                atm_iv, hv_30d, vrp, spot_price, num_quotes
            FROM iv_history
            WHERE ticker = %s
            ORDER BY date ASC
        """

        df = self._query_df(sql, (ticker,))
        if df.empty:
            return pd.DataFrame(columns=[
                "date", "atm_iv", "hv_30d", "vrp", "spot_price", "num_quotes",
            ])
        return df

    # --------------------------------------------------------
    # Fundamentals
    # --------------------------------------------------------

    def query_fundamentals(self, ticker: str) -> dict:
        """Query latest fundamental data from the database."""
        ticker = ticker.upper()

        sql = """
            SELECT data, TO_CHAR(snapshot_date, 'YYYY-MM-DD') AS snapshot_date
            FROM fundamentals
            WHERE ticker = %s
            ORDER BY snapshot_date DESC
            LIMIT 1
        """

        df = self._query_df(sql, (ticker,))
        if df.empty:
            return {}

        row = df.iloc[0]
        data = row["data"]
        if isinstance(data, str):
            data = json.loads(data)

        # Return in same format as FileBackend
        reports = data.get("reports", data)
        snapshot = reports.get("ReportSnapshot", {}) if isinstance(reports, dict) else {}

        return {
            "ticker": ticker,
            "collected_at": row.get("snapshot_date", ""),
            "snapshot": snapshot,
            "fin_summary": reports.get("ReportsFinSummary", {}) if isinstance(reports, dict) else {},
            "ownership": reports.get("ReportsOwnership", {}) if isinstance(reports, dict) else {},
        }

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
        """List tickers with available data of a given type."""
        table_map = {
            "news": "news",
            "prices": "prices",
            "iv_history": "iv_history",
            "fundamentals": "fundamentals",
        }

        table = table_map.get(data_type)
        if not table:
            return []

        sql = f"SELECT DISTINCT ticker FROM {table} ORDER BY ticker"
        df = self._query_df(sql)

        if df.empty:
            return []
        return df["ticker"].tolist()

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
        """Read from financial_data_cache if not expired."""
        conn = self._get_conn()
        sql = """
            SELECT data FROM financial_data_cache
            WHERE cache_key = %s AND expires_at > NOW()
        """
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (cache_key,))
                row = cur.fetchone()
                return row[0] if row else None
        except psycopg2.Error as e:
            logger.error(f"Failed to read financial cache: {e}")
            self._conn = None
            return None

    def set_financial_cache(
        self,
        cache_key: str,
        ticker: str,
        data: dict,
        ttl_days: int = 90,
        source: str = "sec_edgar",
    ) -> bool:
        """Write to financial_data_cache with TTL."""
        conn = self._get_conn()
        sql = """
            INSERT INTO financial_data_cache (cache_key, source, ticker, data, expires_at)
            VALUES (%s, %s, %s, %s, NOW() + INTERVAL '%s days')
            ON CONFLICT (cache_key) DO UPDATE SET
                data = EXCLUDED.data,
                source = EXCLUDED.source,
                fetched_at = NOW(),
                expires_at = NOW() + INTERVAL '%s days'
        """
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (
                    cache_key, source, ticker.upper(),
                    json.dumps(data), ttl_days, ttl_days,
                ))
            return True
        except psycopg2.Error as e:
            logger.error(f"Failed to write financial cache: {e}")
            self._conn = None
            return False

    # --------------------------------------------------------
    # Health / Freshness Statistics
    # --------------------------------------------------------

    def query_health_stats(self) -> Dict[str, Any]:
        """Return freshness/health statistics for all data sources.

        Public API for FreshnessRegistry — isolates health queries from
        internal implementation details. Each source query is independent
        with its own cursor: partial failure returns error detail without
        blocking other sources.

        Returns:
            Dict with keys: news, prices, iv_history, financial_cache.
            Each value is {"rows": ..., "error": str|None}.
        """
        conn = self._get_conn()
        stats: Dict[str, Any] = {}

        # News: global latest + recent 7d count per source
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT source, MAX(published_at) AS latest, "
                    "COUNT(*) FILTER (WHERE published_at > NOW() - INTERVAL '7 days') AS recent_count "
                    "FROM news GROUP BY source"
                )
                stats["news"] = {"rows": cur.fetchall(), "error": None}
        except Exception as e:
            stats["news"] = {"rows": [], "error": str(e)}

        # Prices: latest 1d bar timestamp
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT MAX(datetime) FROM prices WHERE interval='1d'")
                stats["prices"] = {"rows": cur.fetchall(), "error": None}
        except Exception as e:
            stats["prices"] = {"rows": [], "error": str(e)}

        # IV history: latest date
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT MAX(date) FROM iv_history")
                stats["iv_history"] = {"rows": cur.fetchall(), "error": None}
        except Exception as e:
            stats["iv_history"] = {"rows": [], "error": str(e)}

        # Financial cache: cached vs expired counts per source
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT source, "
                    "COUNT(*) FILTER (WHERE expires_at > NOW()) AS cached, "
                    "COUNT(*) FILTER (WHERE expires_at <= NOW()) AS expired "
                    "FROM financial_data_cache GROUP BY source"
                )
                stats["financial_cache"] = {"rows": cur.fetchall(), "error": None}
        except Exception as e:
            stats["financial_cache"] = {"rows": [], "error": str(e)}

    # ================================================================
    # Seeking Alpha Alpha Picks (Phase 11c)
    # ================================================================

    def apply_sa_refresh(
        self,
        scope: str,
        picks: list,
        attempt_ts,
        snapshot_ts,
    ) -> int:
        """Atomic per-tab refresh: mark_stale + upsert + update_meta in one transaction.

        Meta update on success:
            last_attempt_at=attempt_ts, last_success_at=snapshot_ts,
            snapshot_ts=snapshot_ts, row_count=N, ok=TRUE, last_error=NULL

        Returns count of upserted rows.
        """
        conn = self._get_conn()
        old_autocommit = conn.autocommit
        try:
            conn.autocommit = False

            with conn.cursor() as cur:
                # 1. Mark existing rows as stale if not seen in this snapshot
                cur.execute(
                    "UPDATE sa_alpha_picks SET is_stale = TRUE, updated_at = NOW() "
                    "WHERE portfolio_status = %s AND last_seen_snapshot < %s",
                    (scope, snapshot_ts),
                )

                # 2. Upsert new rows (don't touch detail_report/detail_fetched_at)
                count = 0
                for pick in picks:
                    cur.execute(
                        """
                        INSERT INTO sa_alpha_picks
                            (symbol, company, picked_date, portfolio_status,
                             is_stale, return_pct, sector, sa_rating, holding_pct,
                             raw_data, last_seen_snapshot, fetched_at, updated_at)
                        VALUES (%s, %s, %s, %s, FALSE, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                        ON CONFLICT (symbol, picked_date) DO UPDATE SET
                            company = EXCLUDED.company,
                            portfolio_status = EXCLUDED.portfolio_status,
                            is_stale = FALSE,
                            return_pct = EXCLUDED.return_pct,
                            sector = EXCLUDED.sector,
                            sa_rating = EXCLUDED.sa_rating,
                            holding_pct = EXCLUDED.holding_pct,
                            raw_data = EXCLUDED.raw_data,
                            last_seen_snapshot = EXCLUDED.last_seen_snapshot,
                            updated_at = NOW()
                        """,
                        (
                            pick.get("symbol"),
                            pick.get("company", ""),
                            pick.get("picked_date"),
                            scope,
                            pick.get("return_pct"),
                            pick.get("sector"),
                            pick.get("sa_rating"),
                            pick.get("holding_pct"),
                            json.dumps(pick.get("raw_data")) if pick.get("raw_data") else None,
                            snapshot_ts,
                        ),
                    )
                    count += 1

                # 3. Update refresh meta (success: overwrite all fields)
                cur.execute(
                    """
                    INSERT INTO sa_refresh_meta
                        (scope, last_attempt_at, last_success_at, snapshot_ts,
                         row_count, ok, last_error, updated_at)
                    VALUES (%s, %s, %s, %s, %s, TRUE, NULL, NOW())
                    ON CONFLICT (scope) DO UPDATE SET
                        last_attempt_at = EXCLUDED.last_attempt_at,
                        last_success_at = EXCLUDED.last_success_at,
                        snapshot_ts = EXCLUDED.snapshot_ts,
                        row_count = EXCLUDED.row_count,
                        ok = TRUE,
                        last_error = NULL,
                        updated_at = NOW()
                    """,
                    (scope, attempt_ts, snapshot_ts, snapshot_ts, count),
                )

            conn.commit()
            return count

        except Exception as e:
            conn.rollback()
            # Write failure meta (outside the failed transaction)
            try:
                conn.autocommit = True
                self.record_sa_refresh_failure(scope, attempt_ts, str(e))
            except Exception:
                pass
            raise
        finally:
            conn.autocommit = old_autocommit

    def record_sa_refresh_failure(self, scope: str, attempt_ts, error: str) -> None:
        """Record refresh failure in meta table.

        Only updates: last_attempt_at, ok=FALSE, last_error.
        Preserves: last_success_at, snapshot_ts, row_count.
        """
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO sa_refresh_meta
                        (scope, last_attempt_at, ok, last_error, updated_at)
                    VALUES (%s, %s, FALSE, %s, NOW())
                    ON CONFLICT (scope) DO UPDATE SET
                        last_attempt_at = EXCLUDED.last_attempt_at,
                        ok = FALSE,
                        last_error = EXCLUDED.last_error,
                        updated_at = NOW()
                    """,
                    (scope, attempt_ts, error),
                )
        except Exception as e:
            logger.error("Failed to record SA refresh failure: %s", e)

    def query_sa_picks(
        self,
        portfolio_status: Optional[str] = None,
        symbol: Optional[str] = None,
        include_stale: bool = False,
    ) -> list:
        """Query SA Alpha Picks with optional filters."""
        conn = self._get_conn()
        conditions = []
        params = []

        if portfolio_status and portfolio_status != "all":
            conditions.append("portfolio_status = %s")
            params.append(portfolio_status)

        if symbol:
            conditions.append("symbol = %s")
            params.append(symbol.upper())

        if not include_stale:
            conditions.append("is_stale = FALSE")

        where = " AND ".join(conditions) if conditions else "TRUE"
        sql = (
            f"SELECT symbol, company, picked_date, portfolio_status, is_stale, "
            f"return_pct, sector, sa_rating, holding_pct, "
            f"detail_fetched_at IS NOT NULL AS has_detail, "
            f"last_seen_snapshot, fetched_at, updated_at "
            f"FROM sa_alpha_picks WHERE {where} "
            f"ORDER BY portfolio_status, picked_date DESC"
        )

        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, tuple(params))
                rows = cur.fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            logger.error("Failed to query SA picks: %s", e)
            return []

    def get_sa_pick_detail(
        self, symbol: str, picked_date: Optional[str] = None
    ) -> Optional[dict]:
        """Get detail for a specific pick.

        picked_date=None: deterministic fallback —
            current + non-stale first, then stale, then any.
        """
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                if picked_date:
                    cur.execute(
                        "SELECT * FROM sa_alpha_picks "
                        "WHERE symbol = %s AND picked_date = %s",
                        (symbol.upper(), picked_date),
                    )
                else:
                    # Deterministic fallback: current + non-stale first
                    cur.execute(
                        "SELECT * FROM sa_alpha_picks "
                        "WHERE symbol = %s AND portfolio_status = 'current' "
                        "ORDER BY is_stale ASC, picked_date DESC LIMIT 1",
                        (symbol.upper(),),
                    )
                row = cur.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error("Failed to get SA pick detail: %s", e)
            return None

    def update_sa_pick_detail(
        self, symbol: str, picked_date: str, content: str
    ) -> bool:
        """Update detail_report for a specific pick."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE sa_alpha_picks SET detail_report = %s, "
                    "detail_fetched_at = NOW(), updated_at = NOW() "
                    "WHERE symbol = %s AND picked_date = %s",
                    (content, symbol.upper(), picked_date),
                )
                return cur.rowcount > 0
        except Exception as e:
            logger.error("Failed to update SA pick detail: %s", e)
            return False

    def get_sa_refresh_meta(self) -> dict:
        """Get per-tab refresh metadata.

        Returns: {"current": {...}, "closed": {...}}
        """
        conn = self._get_conn()
        result = {}
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM sa_refresh_meta")
                for row in cur.fetchall():
                    scope = row["scope"]
                    d = dict(row)
                    # Convert datetime fields to ISO strings
                    for k in ("last_attempt_at", "last_success_at", "snapshot_ts", "updated_at"):
                        if d.get(k):
                            d[k] = d[k].isoformat()
                    result[scope] = d
        except Exception as e:
            logger.error("Failed to get SA refresh meta: %s", e)
        return result


    def upsert_sa_market_news(self, items: list) -> int:
        """Batch upsert Seeking Alpha market-news metadata."""
        conn = self._get_conn()
        count = 0
        try:
            with conn.cursor() as cur:
                for item in items:
                    cur.execute(
                        """INSERT INTO sa_market_news
                        (news_id, url, title, published_at, published_text, tickers,
                         category, summary, comments_count, raw_data)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (news_id) DO UPDATE SET
                            url = EXCLUDED.url,
                            title = EXCLUDED.title,
                            published_at = COALESCE(EXCLUDED.published_at, sa_market_news.published_at),
                            published_text = COALESCE(EXCLUDED.published_text, sa_market_news.published_text),
                            tickers = CASE
                                WHEN COALESCE(array_length(EXCLUDED.tickers, 1), 0) > 0 THEN EXCLUDED.tickers
                                ELSE sa_market_news.tickers
                            END,
                            category = COALESCE(EXCLUDED.category, sa_market_news.category),
                            summary = COALESCE(EXCLUDED.summary, sa_market_news.summary),
                            comments_count = GREATEST(
                                COALESCE(sa_market_news.comments_count, 0),
                                COALESCE(EXCLUDED.comments_count, 0)
                            ),
                            raw_data = COALESCE(EXCLUDED.raw_data, sa_market_news.raw_data),
                            updated_at = NOW()
                        """,
                        (
                            item.get("news_id"),
                            item.get("url"),
                            item.get("title"),
                            item.get("published_at"),
                            item.get("published_text"),
                            item.get("tickers") or [],
                            item.get("category"),
                            item.get("summary"),
                            item.get("comments_count", 0),
                            psycopg2.extras.Json(item.get("raw_data")),
                        ),
                    )
                    count += 1
        except Exception as e:
            logger.error("Failed to upsert SA market news: %s", e)
        return count

    def query_sa_market_news(
        self,
        ticker: Optional[str] = None,
        keyword: Optional[str] = None,
        limit: int = 20,
    ) -> list:
        """Query recent Seeking Alpha market-news items."""
        conn = self._get_conn()
        conditions = []
        params = []
        if ticker:
            conditions.append("%s = ANY(tickers)")
            params.append(ticker.upper())
        if keyword:
            conditions.append(
                "to_tsvector('english', COALESCE(title, '') || ' ' || COALESCE(summary, '')) "
                "@@ plainto_tsquery('english', %s)"
            )
            params.append(keyword)
        where = " AND ".join(conditions) if conditions else "TRUE"
        params.append(max(1, min(int(limit or 20), 100)))
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    f"""SELECT news_id, url, title, published_at, published_text,
                        tickers, category, summary, comments_count, body_markdown,
                        detail_fetched_at, fetched_at, updated_at
                    FROM sa_market_news
                    WHERE {where}
                    ORDER BY COALESCE(published_at, fetched_at) DESC NULLS LAST, id DESC
                    LIMIT %s""",
                    tuple(params),
                )
                rows = []
                for row in cur.fetchall():
                    item = dict(row)
                    for key in ("published_at", "detail_fetched_at", "fetched_at", "updated_at"):
                        if item.get(key) and hasattr(item[key], "isoformat"):
                            item[key] = item[key].isoformat()
                    rows.append(item)
                return rows
        except Exception as e:
            logger.error("Failed to query SA market news: %s", e)
            return []

    def query_sa_market_news_need_detail(
        self,
        news_ids: list | None = None,
        detail_cache_hours: int = 24,
        limit: int = 50,
        exclude_news_ids: list | None = None,
    ) -> list:
        """Return market-news items that still need detail body fetch."""
        if limit is not None and int(limit or 0) <= 0:
            return []
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                filters = [
                    "("
                    "body_markdown IS NULL OR body_markdown = '' "
                    "OR detail_fetched_at IS NULL "
                    "OR detail_fetched_at < NOW() - (%s || ' hours')::interval"
                    ")"
                ]
                params = [int(detail_cache_hours)]
                if news_ids:
                    filters.append("news_id = ANY(%s)")
                    params.append(news_ids)
                if exclude_news_ids:
                    filters.append("NOT (news_id = ANY(%s))")
                    params.append(exclude_news_ids)
                params.append(max(1, min(int(limit or 50), 200)))
                cur.execute(
                    f"""
                    SELECT news_id, url
                    FROM sa_market_news
                    WHERE {' AND '.join(filters)}
                    ORDER BY
                      CASE WHEN body_markdown IS NULL OR body_markdown = '' THEN 0 ELSE 1 END,
                      COALESCE(detail_fetched_at, TIMESTAMPTZ '1970-01-01') ASC,
                      COALESCE(published_at, fetched_at) DESC NULLS LAST
                    LIMIT %s
                    """,
                    tuple(params),
                )
                return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            logger.error("Failed to query SA market news detail candidates: %s", e)
            return []

    def invalidate_dirty_sa_market_news_detail(self) -> int:
        """Drop cached market-news body content that matches known chrome noise."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE sa_market_news
                    SET body_markdown = NULL,
                        detail_fetched_at = NULL,
                        updated_at = NOW()
                    WHERE body_markdown IS NOT NULL
                      AND (
                        LOWER(body_markdown) LIKE '%follow seeking alpha on google%'
                        OR LOWER(body_markdown) LIKE '%recommended for you%'
                        OR LOWER(body_markdown) LIKE '%related stocks%'
                        OR LOWER(body_markdown) LIKE '%## more on %'
                        OR LOWER(body_markdown) LIKE '%### recommended for you%'
                        OR LOWER(body_markdown) LIKE '%### more trending news%'
                        OR LOWER(body_markdown) LIKE '%see more%'
                        OR LOWER(body_markdown) LIKE '%- share%'
                        OR body_markdown ~ E'^# .+\\n\\n# '
                      )
                    """
                )
                return int(cur.rowcount or 0)
        except Exception as e:
            logger.error("Failed to invalidate dirty SA market news detail cache: %s", e)
            return 0

    def save_sa_market_news_detail(self, news_id: str, body_markdown: str) -> bool:
        """Persist market-news body Markdown for a single news item."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE sa_market_news
                    SET body_markdown = %s,
                        detail_fetched_at = NOW(),
                        updated_at = NOW()
                    WHERE news_id = %s
                    """,
                    (body_markdown, news_id),
                )
                return cur.rowcount > 0
        except Exception as e:
            logger.error("Failed to save SA market news detail for %s: %s", news_id, e)
            return False

    # ============================================================
    # SA Articles + Comments (Phase 11c-v3)
    # ============================================================

    def upsert_sa_articles_meta(self, articles: list) -> int:
        """Batch upsert article metadata (no body_markdown)."""
        conn = self._get_conn()
        count = 0
        try:
            with conn.cursor() as cur:
                for a in articles:
                    cur.execute(
                        """INSERT INTO sa_articles
                        (article_id, url, title, ticker, published_date,
                         article_type, comments_count, raw_data)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (article_id) DO UPDATE SET
                            title = EXCLUDED.title,
                            url = EXCLUDED.url,
                            ticker = COALESCE(EXCLUDED.ticker, sa_articles.ticker),
                            published_date = COALESCE(EXCLUDED.published_date, sa_articles.published_date),
                            article_type = COALESCE(EXCLUDED.article_type, sa_articles.article_type),
                            comments_count = EXCLUDED.comments_count,
                            updated_at = NOW()
                        """,
                        (
                            a.get("article_id"),
                            a.get("url"),
                            a.get("title"),
                            a.get("ticker"),
                            a.get("published_date"),
                            a.get("article_type"),
                            a.get("comments_count", 0),
                            psycopg2.extras.Json(a.get("raw_data")),
                        ),
                    )
                    count += 1
        except Exception as e:
            logger.error("Failed to upsert SA articles: %s", e)
        return count

    def sanitize_corrupted_sa_comments_counts(self) -> int:
        """Repair year-prefixed comments_count corruption in SA article metadata."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE sa_articles
                    SET comments_count = CAST(SUBSTRING(comments_count::text FROM 5) AS INTEGER),
                        updated_at = NOW()
                    WHERE published_date IS NOT NULL
                      AND comments_count >= 10000
                      AND comments_count::text LIKE EXTRACT(YEAR FROM published_date)::int::text || '%'
                      AND LENGTH(comments_count::text) > 4
                      AND CAST(SUBSTRING(comments_count::text FROM 5) AS INTEGER) BETWEEN 0 AND 9999
                    """
                )
                repaired = cur.rowcount or 0
            return repaired
        except Exception as e:
            logger.error("Failed to sanitize SA comments_count rows: %s", e)
            return 0

    def _fetch_existing_article_comments(self, cur, article_id: str) -> List[Dict[str, Any]]:
        with cur.connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as fetch_cur:
            fetch_cur.execute(
                "SELECT comment_id, parent_comment_id, commenter, comment_text, upvotes, comment_date "
                "FROM sa_article_comments WHERE article_id = %s",
                (article_id,),
            )
            return [dict(row) for row in fetch_cur.fetchall()]

    def _upsert_article_comments(self, cur, article_id: str, comments: list) -> int:
        prepared_comments = _prepare_comments_for_upsert(
            self._fetch_existing_article_comments(cur, article_id),
            comments,
        )
        for comment in prepared_comments:
            cur.execute(
                """INSERT INTO sa_article_comments
                (article_id, comment_id, parent_comment_id,
                 commenter, comment_text, upvotes, comment_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (article_id, comment_id) DO UPDATE SET
                    parent_comment_id = COALESCE(sa_article_comments.parent_comment_id, EXCLUDED.parent_comment_id),
                    commenter = COALESCE(sa_article_comments.commenter, EXCLUDED.commenter),
                    comment_text = EXCLUDED.comment_text,
                    upvotes = GREATEST(COALESCE(sa_article_comments.upvotes, 0), COALESCE(EXCLUDED.upvotes, 0)),
                    comment_date = COALESCE(sa_article_comments.comment_date, EXCLUDED.comment_date)
                """,
                (
                    article_id,
                    comment.get("comment_id"),
                    comment.get("parent_comment_id"),
                    comment.get("commenter"),
                    comment.get("comment_text"),
                    comment.get("upvotes", 0),
                    comment.get("comment_date"),
                ),
            )
        cleanup = self._cleanup_article_comment_duplicates(cur, article_id)
        if cleanup["comments_deleted"] or cleanup["parent_links_repointed"]:
            logger.info(
                "Cleaned SA comment duplicates for %s: deleted=%s parent_links_repointed=%s",
                article_id,
                cleanup["comments_deleted"],
                cleanup["parent_links_repointed"],
            )
        return len(prepared_comments)

    def _cleanup_article_comment_duplicates(self, cur, article_id: str) -> Dict[str, int]:
        groups_processed = 0
        comments_deleted = 0
        parent_links_repointed = 0
        with cur.connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as fetch_cur:
            fetch_cur.execute(
                """SELECT commenter, comment_text
                FROM sa_article_comments
                WHERE article_id = %s
                GROUP BY commenter, comment_text
                HAVING COUNT(*) > 1
                """,
                (article_id,),
            )
            groups = fetch_cur.fetchall()

            for group in groups:
                fetch_cur.execute(
                    """SELECT id, comment_id, parent_comment_id, comment_date
                    FROM sa_article_comments
                    WHERE article_id = %s
                      AND commenter IS NOT DISTINCT FROM %s
                      AND comment_text IS NOT DISTINCT FROM %s
                    ORDER BY comment_date ASC NULLS LAST, id ASC
                    """,
                    (article_id, group["commenter"], group["comment_text"]),
                )
                rows = [dict(row) for row in fetch_cur.fetchall()]
                plan = _plan_comment_duplicate_cleanup(rows)
                if not plan["delete_ids"]:
                    continue
                groups_processed += 1
                for duplicate_comment_id, canonical_comment_id in plan["parent_rewrites"]:
                    cur.execute(
                        "UPDATE sa_article_comments SET parent_comment_id = %s WHERE article_id = %s AND parent_comment_id = %s",
                        (canonical_comment_id, article_id, duplicate_comment_id),
                    )
                    parent_links_repointed += cur.rowcount or 0
                for delete_id in plan["delete_ids"]:
                    cur.execute("DELETE FROM sa_article_comments WHERE id = %s", (delete_id,))
                    comments_deleted += cur.rowcount or 0
        return {
            "groups_processed": groups_processed,
            "comments_deleted": comments_deleted,
            "parent_links_repointed": parent_links_repointed,
        }

    def cleanup_mixed_null_date_comment_duplicates(self) -> Dict[str, int]:
        """Collapse safe duplicate groups where a null-date row matches a dated row."""
        conn = self._get_conn()
        old_autocommit = conn.autocommit
        groups_processed = 0
        comments_deleted = 0
        parent_links_repointed = 0
        try:
            conn.autocommit = False
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """SELECT article_id, commenter, comment_text
                    FROM sa_article_comments
                    GROUP BY article_id, commenter, comment_text
                    HAVING COUNT(*) > 1
                       AND COUNT(*) FILTER (WHERE comment_date IS NULL) >= 1
                       AND COUNT(*) FILTER (WHERE comment_date IS NOT NULL) >= 1
                       AND COUNT(DISTINCT comment_date) FILTER (WHERE comment_date IS NOT NULL) = 1
                    """
                )
                groups = cur.fetchall()
                for group in groups:
                    cur.execute(
                        """SELECT id, comment_id, parent_comment_id, comment_date
                        FROM sa_article_comments
                        WHERE article_id = %s
                          AND commenter IS NOT DISTINCT FROM %s
                          AND comment_text = %s
                        ORDER BY (comment_date IS NULL) ASC, comment_date ASC, id ASC
                        """,
                        (
                            group["article_id"],
                            group["commenter"],
                            group["comment_text"],
                        ),
                    )
                    rows = cur.fetchall()
                    canonical = next((row for row in rows if row["comment_date"] is not None), rows[0])
                    duplicates = [
                        row for row in rows
                        if row["comment_id"] != canonical["comment_id"] and row["comment_date"] is None
                    ]
                    if not duplicates:
                        continue
                    groups_processed += 1
                    for duplicate in duplicates:
                        cur.execute(
                            "UPDATE sa_article_comments SET parent_comment_id = %s "
                            "WHERE article_id = %s AND parent_comment_id = %s",
                            (
                                canonical["comment_id"],
                                group["article_id"],
                                duplicate["comment_id"],
                            ),
                        )
                        parent_links_repointed += cur.rowcount or 0
                        cur.execute(
                            "DELETE FROM sa_article_comments WHERE id = %s",
                            (duplicate["id"],),
                        )
                        comments_deleted += cur.rowcount or 0
            conn.commit()
            return {
                "groups_processed": groups_processed,
                "comments_deleted": comments_deleted,
                "parent_links_repointed": parent_links_repointed,
            }
        except Exception as e:
            conn.rollback()
            logger.error("cleanup_mixed_null_date_comment_duplicates failed: %s", e)
            raise
        finally:
            conn.autocommit = old_autocommit

    def save_article_with_comments(
        self,
        article_id: str,
        body_markdown: str,
        comments: list,
        sync_picks: bool = True,
    ) -> dict:
        """Atomic: article content + comments + pick sync in single transaction."""
        conn = self._get_conn()
        old_autocommit = conn.autocommit
        synced = 0
        try:
            conn.autocommit = False
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE sa_articles SET body_markdown = %s, "
                    "detail_fetched_at = NOW(), comments_fetched_at = NOW(), "
                    "updated_at = NOW() WHERE article_id = %s",
                    (body_markdown, article_id),
                )
                self._upsert_article_comments(cur, article_id, comments)
                if sync_picks:
                    synced = self._sync_canonical_to_picks(cur, article_id)
            conn.commit()
            return {"ok": True, "synced_picks": synced}
        except Exception as e:
            conn.rollback()
            logger.error("save_article_with_comments failed: %s", e)
            raise
        finally:
            conn.autocommit = old_autocommit

    def update_article_comments(self, article_id: str, comments: list) -> int:
        """Comments-only update (for TTL refresh). Returns count."""
        conn = self._get_conn()
        old_autocommit = conn.autocommit
        try:
            conn.autocommit = False
            with conn.cursor() as cur:
                prepared_count = self._upsert_article_comments(cur, article_id, comments)
                cur.execute(
                    "UPDATE sa_articles SET comments_fetched_at = NOW(), "
                    "updated_at = NOW() WHERE article_id = %s",
                    (article_id,),
                )
            conn.commit()
            return prepared_count
        except Exception as e:
            conn.rollback()
            logger.error("update_article_comments failed: %s", e)
            raise
        finally:
            conn.autocommit = old_autocommit

    def _sync_canonical_to_picks(self, cur, article_id: str) -> int:
        """Sync article to matching picks. Must use the passed cursor (transaction)."""
        # Get article info
        cur.execute(
            "SELECT article_id, ticker, article_type, published_date, body_markdown "
            "FROM sa_articles WHERE article_id = %s",
            (article_id,),
        )
        article = cur.fetchone()
        if not article or not article[1]:  # no ticker
            return 0
        ticker = article[1]
        article_type = article[2]
        published_date = article[3]
        body_md = article[4]

        if article_type not in ("analysis", "removal"):
            return 0
        if not body_md:
            return 0

        # Find matching picks (current + closed) — exact match first
        cur.execute(
            "SELECT id, symbol, picked_date, canonical_article_id "
            "FROM sa_alpha_picks WHERE symbol = %s",
            (ticker,),
        )
        rows = cur.fetchall()

        # Also try prefix match
        if not rows:
            cur.execute(
                "SELECT id, symbol, picked_date, canonical_article_id "
                "FROM sa_alpha_picks WHERE %s LIKE symbol || '%%' "
                "AND LENGTH(%s) <= LENGTH(symbol) * 2",
                (ticker, ticker),
            )
            rows = cur.fetchall()

        synced = 0
        for row in rows:
            pick_id, symbol, picked_date, current_canonical = row
            # Same article refresh: always allow
            if current_canonical == article_id:
                cur.execute(
                    "UPDATE sa_alpha_picks SET detail_report = %s, "
                    "detail_fetched_at = NOW(), canonical_article_id = %s, "
                    "updated_at = NOW() WHERE id = %s",
                    (body_md, article_id, pick_id),
                )
                synced += 1
                continue

            # Different article: only if closer to picked_date
            if current_canonical and published_date and picked_date:
                # Check if current canonical is closer
                cur.execute(
                    "SELECT published_date FROM sa_articles WHERE article_id = %s",
                    (current_canonical,),
                )
                existing = cur.fetchone()
                if existing and existing[0]:
                    existing_dist = abs((existing[0] - picked_date).days)
                    new_dist = abs((published_date - picked_date).days)
                    if new_dist >= existing_dist:
                        continue  # Existing canonical is closer

            # No canonical yet, or new is closer
            cur.execute(
                "UPDATE sa_alpha_picks SET detail_report = %s, "
                "detail_fetched_at = NOW(), canonical_article_id = %s, "
                "updated_at = NOW() WHERE id = %s",
                (body_md, article_id, pick_id),
            )
            synced += 1

        return synced

    def audit_unresolved_symbols(self) -> dict:
        """Find current picks without canonical article, try full-text fallback."""
        conn = self._get_conn()
        unresolved = []
        resolved = 0
        old_autocommit = conn.autocommit
        try:
            conn.autocommit = False
            with conn.cursor() as cur:
                # Current picks without canonical article
                cur.execute(
                    "SELECT id, symbol, picked_date FROM sa_alpha_picks "
                    "WHERE portfolio_status = 'current' AND is_stale = false "
                    "AND canonical_article_id IS NULL "
                    "AND detail_report IS NULL"
                )
                picks = cur.fetchall()

                for pick_id, symbol, picked_date in picks:
                    # Try exact/prefix match first (analysis/removal only)
                    cur.execute(
                        "SELECT article_id, published_date FROM sa_articles "
                        "WHERE (ticker = %s OR (ticker LIKE %s AND LENGTH(ticker) <= LENGTH(%s) * 2)) "
                        "AND article_type IN ('analysis', 'removal') "
                        "AND body_markdown IS NOT NULL "
                        "ORDER BY ABS(published_date - %s::date) "
                        "LIMIT 1",
                        (symbol, symbol + "%", symbol, str(picked_date)),
                    )
                    match = cur.fetchone()

                    # Full-text fallback
                    if not match:
                        cur.execute(
                            "SELECT article_id, published_date FROM sa_articles "
                            "WHERE body_markdown IS NOT NULL "
                            "AND article_type IN ('analysis', 'removal') "
                            "AND to_tsvector('english', COALESCE(title, '') || ' ' || "
                            "COALESCE(body_markdown, '')) "
                            "@@ plainto_tsquery('english', %s) "
                            "ORDER BY ABS(published_date - %s::date) "
                            "LIMIT 1",
                            (symbol, str(picked_date)),
                        )
                        match = cur.fetchone()

                    if match:
                        art_id = match[0]
                        # Get body for sync
                        cur.execute(
                            "SELECT body_markdown FROM sa_articles WHERE article_id = %s",
                            (art_id,),
                        )
                        body_row = cur.fetchone()
                        if body_row and body_row[0]:
                            cur.execute(
                                "UPDATE sa_alpha_picks SET detail_report = %s, "
                                "detail_fetched_at = NOW(), canonical_article_id = %s, "
                                "updated_at = NOW() WHERE id = %s",
                                (body_row[0], art_id, pick_id),
                            )
                            resolved += 1
                            continue

                    unresolved.append(symbol)

            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error("audit_unresolved_symbols failed: %s", e)
            raise
        finally:
            conn.autocommit = old_autocommit

        return {"unresolved_symbols": unresolved, "resolved_by_fulltext": resolved}

    def query_sa_articles(
        self,
        ticker: str = None,
        keyword: str = None,
        article_type: str = None,
        limit: int = 10,
    ) -> list:
        """Query SA articles with optional filters."""
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                conditions = []
                params = []
                if ticker:
                    conditions.append(
                        "(ticker = %s OR ticker LIKE %s)"
                    )
                    params.extend([ticker.upper(), ticker.upper() + "%"])
                if keyword:
                    conditions.append(
                        "to_tsvector('english', COALESCE(title, '') || ' ' || "
                        "COALESCE(body_markdown, '')) @@ plainto_tsquery('english', %s)"
                    )
                    params.append(keyword)
                if article_type:
                    conditions.append("article_type = %s")
                    params.append(article_type)

                where = " AND ".join(conditions) if conditions else "TRUE"
                params.append(limit)
                cur.execute(
                    f"SELECT article_id, url, title, ticker, published_date, "
                    f"article_type, comments_count, "
                    f"CASE WHEN body_markdown IS NOT NULL THEN true ELSE false END as has_content, "
                    f"detail_fetched_at, comments_fetched_at, "
                    f"(SELECT COUNT(*) FROM sa_article_comments c "
                    f" WHERE c.article_id = sa_articles.article_id) AS stored_comments_count "
                    f"FROM sa_articles WHERE {where} "
                    f"ORDER BY published_date DESC NULLS LAST "
                    f"LIMIT %s",
                    params,
                )
                return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.error("Failed to query SA articles: %s", e)
            return []

    def get_sa_article_with_comments(self, article_id: str) -> dict:
        """Get full article + comments."""
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM sa_articles WHERE article_id = %s",
                    (article_id,),
                )
                article = cur.fetchone()
                if not article:
                    return None

                cur.execute(
                    "SELECT comment_id, parent_comment_id, commenter, "
                    "comment_text, upvotes, comment_date "
                    "FROM sa_article_comments WHERE article_id = %s "
                    "ORDER BY comment_date ASC NULLS LAST",
                    (article_id,),
                )
                comments = [dict(r) for r in cur.fetchall()]

                result = dict(article)
                result["comments"] = comments
                # Convert datetime fields
                for k in ("published_date", "detail_fetched_at", "comments_fetched_at",
                           "fetched_at", "updated_at"):
                    if result.get(k) and hasattr(result[k], "isoformat"):
                        result[k] = result[k].isoformat()
                for c in comments:
                    if c.get("comment_date") and hasattr(c["comment_date"], "isoformat"):
                        c["comment_date"] = c["comment_date"].isoformat()

                return result
        except Exception as e:
            logger.error("Failed to get SA article with comments: %s", e)
            return None
