"""
DatabaseBackend — reads data from PostgreSQL.

Implements the DataBackend protocol using psycopg2 with direct SQL queries.
Designed for both self-hosted PostgreSQL (Docker) and cloud services.

Connection string format:
    postgresql://postgres:password@host:port/dbname
"""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from typing import List, Optional

import pandas as pd
import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)


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
        """Get or create a database connection."""
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
            score_join = """
                LEFT JOIN news_scores s_sent
                    ON s_sent.news_id = n.id
                    AND s_sent.score_type = 'sentiment'
                    AND s_sent.model = %s
                LEFT JOIN news_scores s_risk
                    ON s_risk.news_id = n.id
                    AND s_risk.score_type = 'risk'
                    AND s_risk.model = %s
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