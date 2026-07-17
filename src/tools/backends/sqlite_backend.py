"""
SqliteBackend — local-first market-data backend (3a prices + 3b news + 3c iv/fund/cache).

Part of the PostgreSQL → local SQLite migration (see
``docs/design/DATA_COLLECTION_AND_LOCAL_STORAGE_PLAN.md`` §3/§4). This backend
serves the *market_data* domain from a local ``market_data.db`` (SQLite, WAL).
It is NOT a full ``DataBackend`` — only the methods used by
:class:`~src.tools.backends.local_market_backend.LocalMarketDatabaseBackend` are
implemented: 3a = ``query_prices``; 3b = ``query_news`` (unscored) +
``query_news_search`` (FTS5); 3c-A = ``query_iv_history`` + ``query_fundamentals``;
3c-C = ``get_financial_cache`` + ``set_financial_cache`` (LOCAL-PRIMARY cache);
plus ``get_available_tickers('prices'|'news'|'iv_history'|'fundamentals')``.
Score-dependent reads (news_scores deferred) and everything else stay on PostgreSQL.

Reads open the DB **read-only** (``mode=ro``); the data tables are written only by
the migration/lifecycle (market_data_admin), never here — with ONE exception:
``set_financial_cache`` is the local-primary cache's single writable path (opens a
WAL + busy_timeout connection). The on-disk ``datetime`` is stored as the same UTC
string PostgreSQL emits (``YYYY-MM-DDTHH:MM:SS+0000``) so 15min rows pass through
unchanged and 1h/1d roll up by string-prefix grouping in pandas — the SQLite
analogue of the PG ``date_trunc`` aggregation (no ``date_trunc`` in SQLite),
matching the FileBackend resample contract.
"""

from __future__ import annotations

import html as _html
import json
import logging
import re
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import List, Optional

import pandas as pd

from src.news_content_availability import (
    ContentFilter,
    empty_content_counts,
    news_content_sql,
)
from src.news_normalized.scores import normalize_score_model

logger = logging.getLogger(__name__)

_PRICE_COLS = ["datetime", "open", "high", "low", "close", "volume"]
_INTERVAL_MAP = {"1h": "1h", "hourly": "1h", "1d": "1d", "daily": "1d", "15min": "15min"}
# query_iv_history output shape (match DatabaseBackend exactly).
_IV_COLS = ["date", "atm_iv", "hv_30d", "vrp", "spot_price", "num_quotes"]

_TAG_RE = re.compile(r"<[^>]+>")


def clean_snippet(text, limit: int = 280):
    """Plain-text excerpt for feed previews: strip HTML tags, decode entities,
    collapse whitespace, truncate. IBKR (DJ-N etc.) descriptions are stored as
    raw ~500-char HTML fragments — rendered verbatim they read as markup junk.
    Read-time cleanup only; the stored mirror stays verbatim."""
    if not text:
        return text
    out = _html.unescape(_TAG_RE.sub(" ", text))
    out = re.sub(r"\s+", " ", out).strip()
    return out[:limit] + ("…" if len(out) > limit else "")

# query_news / query_news_search output shapes (match DatabaseBackend). Local news
# has NO scores (news_scores deferred) → score columns are always NULL here.
_NEWS_COLS = ["date", "ticker", "title", "source", "url", "publisher",
              "sentiment_score", "risk_score", "scored_model", "description"]
_NEWS_SEARCH_COLS = ["date", "ticker", "title", "source", "url", "publisher",
                     "sentiment_score", "risk_score", "description"]
_NEWS_STATS_COLS = [
    "ticker", "article_count", "scored_count", "earliest_date", "latest_date",
    "avg_sentiment", "avg_risk", "bullish_count", "bearish_count",
]


class SqliteBackend:
    """Local market-data backend over ``market_data.db`` (3a prices + 3b news/FTS5)."""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)

    def _connect(self) -> sqlite3.Connection:
        # Read-only: the backend never writes (migration owns writes).
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def _canon(self, ticker: str) -> str:
        """Resolve a query ticker to its canonical spelling via ticker_aliases, so an alias
        (e.g. 'BRK.B') reaches the canonical rows ('BRK B') across domains. Upper-cased first
        (callers already do). No-op + safe on a pre-canon DB with no ticker_aliases table."""
        t = ticker.upper()
        try:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT canonical FROM ticker_aliases WHERE alias = ?", (t,)).fetchone()
            finally:
                conn.close()
            return row[0] if row else t
        except sqlite3.OperationalError:
            return t  # no ticker_aliases table (pre-canon DB) → passthrough

    def query_prices(self, ticker: str, interval: str = "15min", days: int = 30) -> pd.DataFrame:
        """OHLCV bars for ``ticker`` over the last ``days`` at ``interval``.

        Returns native rows at the requested interval; for 1d/1h with no native
        rows, rolls up from stored 15min bars (first-open / max-high / min-low /
        last-close / sum-volume) — same definition as the PG path. Empty frame on
        any miss (LocalMarketDatabaseBackend then falls back to PG).
        """
        ticker = self._canon(ticker)
        db_interval = _INTERVAL_MAP.get(interval, interval)
        # cutoff is a date string; ISO datetime strings sort lexicographically, so
        # `datetime >= 'YYYY-MM-DD'` correctly includes all of that day onward.
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        empty = pd.DataFrame(columns=_PRICE_COLS)

        try:
            conn = self._connect()
        except sqlite3.OperationalError:
            return empty  # db missing/unreadable → caller falls back to PG
        try:
            native = conn.execute(
                "SELECT datetime, open, high, low, close, volume FROM prices "
                "WHERE ticker = ? AND interval = ? AND datetime >= ? ORDER BY datetime ASC",
                (ticker, db_interval, cutoff),
            ).fetchall()
            if native:
                return pd.DataFrame([tuple(r) for r in native], columns=_PRICE_COLS)

            if db_interval in ("1d", "1h"):
                raw = conn.execute(
                    "SELECT datetime, open, high, low, close, volume FROM prices "
                    "WHERE ticker = ? AND interval = '15min' AND datetime >= ? ORDER BY datetime ASC",
                    (ticker, cutoff),
                ).fetchall()
                if raw:
                    return self._rollup(
                        pd.DataFrame([tuple(r) for r in raw], columns=_PRICE_COLS), db_interval
                    )
        except sqlite3.OperationalError as e:
            logger.warning(f"SqliteBackend.query_prices({ticker}): {e}")
            return empty
        finally:
            conn.close()
        return empty

    @staticmethod
    def _rollup(df: pd.DataFrame, db_interval: str) -> pd.DataFrame:
        """Aggregate 15min bars up to 1d/1h by UTC-string prefix (SQLite analogue
        of PG ``date_trunc``). datetime strings are ``YYYY-MM-DDTHH:MM:SS+0000``."""
        if df.empty:
            return df
        prefix = 10 if db_interval == "1d" else 13  # 'YYYY-MM-DD' | 'YYYY-MM-DDTHH'
        suffix = "T00:00:00+0000" if db_interval == "1d" else ":00:00+0000"
        df = df.sort_values("datetime")
        bucket = df["datetime"].str.slice(0, prefix)
        agg = df.groupby(bucket, sort=True).agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
        )
        agg.index = [k + suffix for k in agg.index]
        out = agg.reset_index().rename(columns={"index": "datetime"})
        return out[_PRICE_COLS]

    # --- news (3b): article corpus, NO scores; FTS5 full-text search ---------

    def query_news(self, ticker: Optional[str] = None, days: int = 30, source: str = "auto",
                   scored_only: bool = True, model: Optional[str] = None) -> pd.DataFrame:
        """Local news articles, local-first sentiment.

        ``news_scores`` is RETIRED (see DATA_COLLECTION plan §4 decision 2026-06-23):
        the local ``news`` table carries an OPTIONAL 1-5 ``sentiment_score`` (written
        on-demand by LLM analysis going forward) — NOT a multi-model PG join. So:
          - ``scored_only=True`` returns only rows whose local ``sentiment_score`` is set
            (empty if the column is absent / unpopulated — an HONEST empty, no PG);
          - a specific ``model`` is meaningless locally (no per-model scores) → empty;
          - ``risk_score``/``scored_model`` stay NULL (retired)."""
        empty = pd.DataFrame(columns=_NEWS_COLS)
        if self._news_score_tables_available():
            return self._query_news_with_normalized_scores(
                ticker=ticker,
                days=days,
                source=source,
                scored_only=scored_only,
                model=model,
            )
        if model:
            return empty  # per-model scoring absent locally
        has_sent = self._news_has_column("sentiment_score")
        if scored_only and not has_sent:
            return empty  # no local sentiment column yet → nothing scored to serve
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        conds, params = ["published_at >= ?"], [cutoff]
        if ticker:
            conds.append("ticker = ?")
            params.append(self._canon(ticker))
        if source != "auto":
            conds.append("source = ?")
            params.append(source)
        if scored_only:
            conds.append("sentiment_score IS NOT NULL")
        sent_expr = "sentiment_score" if has_sent else "NULL"
        sql = (
            f"SELECT substr(published_at, 1, 10) AS date, ticker, title, source, url, publisher, "
            f"{sent_expr} AS sentiment_score, NULL AS risk_score, NULL AS scored_model, description "
            f"FROM news WHERE {' AND '.join(conds)} ORDER BY published_at DESC"
        )
        return self._news_df(sql, params, _NEWS_COLS)

    def query_health_stats(self) -> dict:
        """Local recompute of freshness/health stats from market_data.db — SAME shape as
        DatabaseBackend.query_health_stats (``{news,prices,iv_history,financial_cache}``,
        each ``{"rows": [positional tuples], "error": str|None}``), so provider-health /
        freshness stop needing PG. A missing optional table is an honest empty (error None),
        not a failure — same 'tolerate a pre-X DB' stance as the rest of the local backend."""
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        news_cutoff = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S+0000")
        now_iso = now.isoformat(timespec="seconds")
        stats: dict = {}

        def _q(key: str, table: str, sql: str, params: tuple = ()) -> None:
            try:
                conn = self._connect()
                try:
                    exists = conn.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
                    ).fetchone()
                    rows = [tuple(r) for r in conn.execute(sql, params).fetchall()] if exists else []
                finally:
                    conn.close()
                stats[key] = {"rows": rows, "error": None}
            except Exception as e:  # noqa: BLE001
                stats[key] = {"rows": [], "error": str(e)}

        _q("news", "news",
           "SELECT source, MAX(published_at) AS latest, "
           "SUM(CASE WHEN published_at > ? THEN 1 ELSE 0 END) AS recent_count "
           "FROM news GROUP BY source", (news_cutoff,))
        _q("prices", "prices", "SELECT MAX(datetime) FROM prices")
        _q("iv_history", "iv_history", "SELECT MAX(date) FROM iv_history")
        _q("financial_cache", "financial_cache",
           "SELECT source, "
           "SUM(CASE WHEN expires_at > ? THEN 1 ELSE 0 END) AS cached, "
           "SUM(CASE WHEN expires_at <= ? THEN 1 ELSE 0 END) AS expired, "
           "MAX(fetched_at) AS latest_fetched "
           "FROM financial_cache GROUP BY source", (now_iso, now_iso))
        return stats

    def _news_has_column(self, col: str) -> bool:
        """Whether the local ``news`` table has ``col`` — lets query_news degrade
        gracefully on a pre-sentiment market_data.db (column added by market_data_admin)."""
        try:
            conn = self._connect()
            try:
                cols = {r[1] for r in conn.execute("PRAGMA table_info(news)").fetchall()}
            finally:
                conn.close()
            return col in cols
        except Exception:
            return False

    def _news_score_tables_available(self) -> bool:
        try:
            conn = self._connect()
        except sqlite3.OperationalError:
            return False
        try:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            return (
                "news_article_scores" in tables
                and (
                    "news_legacy_migration_map" in tables
                    or "news_legacy_projection_map" in tables
                )
            )
        except sqlite3.OperationalError:
            return False
        finally:
            conn.close()

    @staticmethod
    def _score_map_joins() -> str:
        return (
            "LEFT JOIN news_legacy_migration_map m ON m.legacy_news_id = n.id "
            "LEFT JOIN news_legacy_projection_map p ON p.legacy_news_id = n.id"
        )

    @staticmethod
    def _news_content_projection(conn: sqlite3.Connection) -> tuple[str, str, str]:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        map_tables = [
            table
            for table in (
                "news_legacy_migration_map",
                "news_legacy_projection_map",
            )
            if table in tables
        ]
        if not {
            "news_articles",
            "news_article_bodies",
        }.issubset(tables) or not map_tables:
            return "", "'unknown'", "NULL"

        joins: list[str] = []
        article_ids: list[str] = []
        if "news_legacy_migration_map" in map_tables:
            joins.append(
                "LEFT JOIN news_legacy_migration_map m "
                "ON m.legacy_news_id = n.id"
            )
            article_ids.append("m.article_id")
        if "news_legacy_projection_map" in map_tables:
            joins.append(
                "LEFT JOIN news_legacy_projection_map p "
                "ON p.legacy_news_id = n.id"
            )
            article_ids.append("p.article_id")

        article_expr = (
            f"COALESCE({', '.join(article_ids)})"
            if len(article_ids) > 1
            else article_ids[0]
        )
        joins.extend(
            (
                f"LEFT JOIN news_articles a ON a.id = {article_expr}",
                "LEFT JOIN news_article_bodies b ON b.article_id = a.id",
            )
        )
        availability_sql, recovery_sql = news_content_sql(
            "b.body_status", "a.source"
        )
        return " ".join(joins), availability_sql, recovery_sql

    @staticmethod
    def _sql_literal(value: str) -> str:
        return "'" + value.replace("'", "''") + "'"

    def _score_lookup_expr(
        self,
        score_type: str,
        column: str,
        *,
        model: Optional[str],
        article_expr: str = "COALESCE(m.article_id, p.article_id)",
    ) -> str:
        if column not in {"score", "model"}:
            raise ValueError(f"unsupported score lookup column: {column}")
        clauses = [
            f"s.article_id = {article_expr}",
            f"s.score_type = {self._sql_literal(score_type)}",
        ]
        if model:
            clauses.append(f"s.model = {self._sql_literal(normalize_score_model(model))}")
        where = " AND ".join(clauses)
        return (
            f"(SELECT s.{column} FROM news_article_scores s "
            f"WHERE {where} "
            "ORDER BY s.scored_at DESC, s.model DESC, s.reasoning_effort DESC LIMIT 1)"
        )

    def _query_news_with_normalized_scores(
        self,
        *,
        ticker: Optional[str],
        days: int,
        source: str,
        scored_only: bool,
        model: Optional[str],
    ) -> pd.DataFrame:
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        conds, params = ["n.published_at >= ?"], [cutoff]
        if ticker:
            conds.append("n.ticker = ?")
            params.append(self._canon(ticker))
        if source != "auto":
            conds.append("n.source = ?")
            params.append(source)
        sent_score = self._score_lookup_expr("sentiment", "score", model=model)
        risk_score = self._score_lookup_expr("risk", "score", model=model)
        sent_model = self._score_lookup_expr("sentiment", "model", model=model)
        risk_model = self._score_lookup_expr("risk", "model", model=model)
        if scored_only or model:
            conds.append(f"({sent_score} IS NOT NULL OR {risk_score} IS NOT NULL)")
        sql = (
            "SELECT substr(n.published_at, 1, 10) AS date, n.ticker AS ticker, "
            "n.title AS title, n.source AS source, n.url AS url, n.publisher AS publisher, "
            f"{sent_score} AS sentiment_score, {risk_score} AS risk_score, "
            f"COALESCE({sent_model}, {risk_model}) AS scored_model, n.description AS description "
            "FROM news n "
            f"{self._score_map_joins()} "
            f"WHERE {' AND '.join(conds)} ORDER BY n.published_at DESC"
        )
        return self._news_df(sql, params, _NEWS_COLS)

    def query_news_search(self, query: str = "", ticker: Optional[str] = None, days: int = 30,
                          limit: int = 20, scored_only: bool = True) -> pd.DataFrame:
        """Local full-text news search via SQLite FTS5 (bm25 ranking), with a LIKE
        fallback for <3-char queries — mirroring the PG tsvector + ILIKE-fallback path.

        news_scores RETIRED (§4 decision 2026-06-23): sentiment is local-first, so a SCORED
        search returns only rows whose local 1-5 ``sentiment_score`` is set (empty if the
        column is absent/unpopulated — an HONEST empty, NOT a PG fallback trigger). Same
        contract as ``query_news``; ``risk_score`` stays NULL (retired)."""
        empty = pd.DataFrame(columns=_NEWS_SEARCH_COLS)
        if self._news_score_tables_available():
            return self._query_news_search_with_normalized_scores(
                query=query, ticker=ticker, days=days, limit=limit, scored_only=scored_only
            )
        has_sent = self._news_has_column("sentiment_score")
        if scored_only and not has_sent:
            return empty  # no local sentiment column yet → nothing scored to serve
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        sent_expr = "n.sentiment_score" if has_sent else "NULL"
        cols = (f"substr(n.published_at, 1, 10) AS date, n.ticker, n.title, n.source, n.url, "
                f"n.publisher, {sent_expr} AS sentiment_score, NULL AS risk_score, n.description")
        q = (query or "").strip()
        conds, params = ["n.published_at >= ?"], [cutoff]
        if scored_only:
            conds.append("n.sentiment_score IS NOT NULL")
        if ticker:
            conds.append("n.ticker = ?")
            params.append(self._canon(ticker))
        if len(q) >= 3:
            match = self._fts_match(q)
            sql = (
                f"SELECT {cols} FROM news_fts f JOIN news n ON n.id = f.rowid "
                f"WHERE news_fts MATCH ? AND {' AND '.join(conds)} "
                "ORDER BY bm25(news_fts), n.published_at DESC LIMIT ?"
            )
            params = [match, *params, limit]
        else:
            if q:  # short query → LIKE fallback
                conds.append("(n.title LIKE ? OR n.description LIKE ?)")
                params += [f"%{q}%", f"%{q}%"]
            sql = (f"SELECT {cols} FROM news n WHERE {' AND '.join(conds)} "
                   "ORDER BY n.published_at DESC LIMIT ?")
            params.append(limit)
        return self._news_df(sql, params, _NEWS_SEARCH_COLS)

    def _query_news_search_with_normalized_scores(
        self,
        *,
        query: str,
        ticker: Optional[str],
        days: int,
        limit: int,
        scored_only: bool,
    ) -> pd.DataFrame:
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        q = (query or "").strip()
        conds, params = ["n.published_at >= ?"], [cutoff]
        sent_score = self._score_lookup_expr("sentiment", "score", model=None)
        risk_score = self._score_lookup_expr("risk", "score", model=None)
        cols = (
            "substr(n.published_at, 1, 10) AS date, n.ticker, n.title, n.source, n.url, "
            f"n.publisher, {sent_score} AS sentiment_score, "
            f"{risk_score} AS risk_score, n.description"
        )
        if scored_only:
            conds.append(f"({sent_score} IS NOT NULL OR {risk_score} IS NOT NULL)")
        if ticker:
            conds.append("n.ticker = ?")
            params.append(self._canon(ticker))
        if len(q) >= 3:
            match = self._fts_match(q)
            base_from = (
                "news_fts f JOIN news n ON n.id = f.rowid "
                f"{self._score_map_joins()}"
            )
            conds.insert(0, "news_fts MATCH ?")
            params.insert(0, match)
            order = "bm25(news_fts), n.published_at DESC"
        else:
            base_from = (
                "news n "
                f"{self._score_map_joins()}"
            )
            if q:
                conds.append("(n.title LIKE ? OR n.description LIKE ?)")
                params += [f"%{q}%", f"%{q}%"]
            order = "n.published_at DESC"
        sql = (
            f"SELECT {cols} FROM {base_from} WHERE {' AND '.join(conds)} "
            f"ORDER BY {order} LIMIT ?"
        )
        params.append(limit)
        return self._news_df(sql, params, _NEWS_SEARCH_COLS)

    def query_news_stats(self, ticker: Optional[str] = None, days: int = 30) -> pd.DataFrame:
        """Local news statistics for the scout tool — counts, date range, and (when the
        local news table carries it) 1-5 ``sentiment_score`` aggregates.

        news_scores RETIRED (§4 decision 2026-06-23): sentiment is local-first. When the
        local ``sentiment_score`` column exists, scored_count / avg_sentiment / bullish
        (>=4) / bearish (<=2) aggregate it; a pre-sentiment DB falls back to 0/NULL. ``risk``
        is fully retired → always NULL. No PG."""
        if self._news_score_tables_available():
            return self._query_news_stats_with_normalized_scores(ticker=ticker, days=days)
        has_sent = self._news_has_column("sentiment_score")
        if has_sent:
            scored_count = "SUM(CASE WHEN sentiment_score IS NOT NULL THEN 1 ELSE 0 END)"
            avg_sent = "AVG(sentiment_score)"
            bullish = "SUM(CASE WHEN sentiment_score >= 4 THEN 1 ELSE 0 END)"
            bearish = "SUM(CASE WHEN sentiment_score <= 2 THEN 1 ELSE 0 END)"
        else:
            scored_count, avg_sent, bullish, bearish = "0", "NULL", "0", "0"
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        conds, params = ["published_at >= ?"], [cutoff]
        if ticker:
            conds.append("ticker = ?")
            params.append(self._canon(ticker))
        sql = (
            f"SELECT ticker, COUNT(*) AS article_count, {scored_count} AS scored_count, "
            "substr(MIN(published_at), 1, 10) AS earliest_date, "
            "substr(MAX(published_at), 1, 10) AS latest_date, "
            f"{avg_sent} AS avg_sentiment, NULL AS avg_risk, "
            f"{bullish} AS bullish_count, {bearish} AS bearish_count "
            f"FROM news WHERE {' AND '.join(conds)} "
            "GROUP BY ticker ORDER BY article_count DESC"
        )
        return self._news_df(sql, params, _NEWS_STATS_COLS)

    def _query_news_stats_with_normalized_scores(
        self, *, ticker: Optional[str], days: int
    ) -> pd.DataFrame:
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        conds, params = ["n.published_at >= ?"], [cutoff]
        if ticker:
            conds.append("n.ticker = ?")
            params.append(self._canon(ticker))
        sent_score = self._score_lookup_expr("sentiment", "score", model=None)
        risk_score = self._score_lookup_expr("risk", "score", model=None)
        sql = (
            "SELECT n.ticker AS ticker, COUNT(*) AS article_count, "
            f"SUM(CASE WHEN {sent_score} IS NOT NULL OR {risk_score} IS NOT NULL "
            "THEN 1 ELSE 0 END) AS scored_count, "
            "substr(MIN(n.published_at), 1, 10) AS earliest_date, "
            "substr(MAX(n.published_at), 1, 10) AS latest_date, "
            f"AVG({sent_score}) AS avg_sentiment, "
            f"AVG({risk_score}) AS avg_risk, "
            f"SUM(CASE WHEN {sent_score} >= 4 THEN 1 ELSE 0 END) AS bullish_count, "
            f"SUM(CASE WHEN {sent_score} <= 2 THEN 1 ELSE 0 END) AS bearish_count "
            "FROM news n "
            f"{self._score_map_joins()} "
            f"WHERE {' AND '.join(conds)} "
            "GROUP BY n.ticker ORDER BY article_count DESC"
        )
        return self._news_df(sql, params, _NEWS_STATS_COLS)

    @staticmethod
    def _fts_match(q: str) -> str:
        """Tokenized-AND FTS5 MATCH expression: each whitespace token is quoted
        (neutralizing operator syntax — quotes, AND/OR, parens) and AND-joined.
        Parity with PG ``plainto_tsquery`` (which ANDs lexemes) instead of the
        narrower exact-phrase match the first version used."""
        tokens = [t.replace('"', '""') for t in q.split()]
        return " AND ".join(f'"{t}"' for t in tokens)

    def query_news_feed(self, q: Optional[str] = None, ticker: Optional[str] = None,
                        source: Optional[str] = None, days: int = 30,
                        limit: int = 50, offset: int = 0,
                        content: ContentFilter = "all") -> dict:
        """Score-free local news feed for the 新聞·事件 surface: FULL
        ``published_at`` timestamps, newest first, paginated, with window facets
        (total / per-source / per-day counts over the SAME filters). Search uses
        FTS5 tokenized-AND (≥3 chars) or LIKE for shorter queries.

        ``available`` is False when the local DB/table is missing (pre-3b DB) so
        the router can fall back to PG; an available-but-empty result is an
        honest zero, NOT a fallback trigger."""
        empty = {
            "available": False,
            "items": [],
            "total": 0,
            "sources": {},
            "days": {},
            "content_counts": empty_content_counts(),
        }
        try:
            conn = self._connect()
        except sqlite3.OperationalError:
            return empty
        try:
            cutoff = (date.today() - timedelta(days=days)).isoformat()
            conds, params = ["n.published_at >= ?"], [cutoff]
            base_from = "news n"
            content_joins, availability_sql, recovery_sql = (
                self._news_content_projection(conn)
            )
            if ticker:
                conds.append("n.ticker = ?")
                params.append(self._canon(ticker))
            if source and source != "auto":
                conds.append("n.source = ?")
                params.append(source)
            ql = (q or "").strip()
            if len(ql) >= 3:
                base_from = "news_fts f JOIN news n ON n.id = f.rowid"
                conds.insert(0, "news_fts MATCH ?")
                params.insert(0, self._fts_match(ql))
            elif ql:
                conds.append("(n.title LIKE ? OR n.description LIKE ?)")
                params += [f"%{ql}%", f"%{ql}%"]
            if content_joins:
                base_from = f"{base_from} {content_joins}"
            common_where = " AND ".join(conds)

            content_counts = empty_content_counts()
            for row in conn.execute(
                f"SELECT {availability_sql}, COUNT(*) FROM {base_from} "
                f"WHERE {common_where} GROUP BY 1",
                params,
            ).fetchall():
                key = row[0]
                if key in content_counts:
                    content_counts[key] = int(row[1])

            selected_params = list(params)
            selected_where = common_where
            if content != "all":
                selected_where += f" AND ({availability_sql}) = ?"
                selected_params.append(content)

            total = conn.execute(
                f"SELECT COUNT(*) FROM {base_from} WHERE {selected_where}",
                selected_params,
            ).fetchone()[0]
            sources = dict(conn.execute(
                f"SELECT n.source, COUNT(*) FROM {base_from} "
                f"WHERE {selected_where} GROUP BY n.source",
                selected_params,
            ).fetchall())
            day_counts = dict(conn.execute(
                f"SELECT substr(n.published_at, 1, 10), COUNT(*) FROM {base_from} "
                f"WHERE {selected_where} GROUP BY 1 ORDER BY 1",
                selected_params,
            ).fetchall())
            # Searching → RELEVANCE order (bm25, title weighted 10x over
            # description so passing mentions in summaries rank below real title
            # hits); browsing → chronological. bm25 is ascending-better in FTS5.
            order = (
                "bm25(news_fts, 10.0, 1.0), n.published_at DESC, n.id DESC"
                if base_from.startswith("news_fts")
                else "n.published_at DESC, n.id DESC"
            )
            rows = conn.execute(
                f"SELECT n.published_at, n.ticker, n.title, n.url, n.publisher, "
                f"n.source, n.description, {availability_sql}, {recovery_sql} "
                f"FROM {base_from} WHERE {selected_where} "
                f"ORDER BY {order} LIMIT ? OFFSET ?",
                [*selected_params, max(1, min(200, limit)), max(0, offset)]
            ).fetchall()
            items = [{"published_at": r[0], "ticker": r[1], "title": r[2],
                      "url": r[3], "publisher": r[4], "source": r[5],
                      "description": clean_snippet(r[6]),
                      "content_availability": r[7],
                      "content_recovery": r[8]} for r in rows]
            return {"available": True, "items": items, "total": total,
                    "sources": sources, "days": day_counts,
                    "content_counts": content_counts}
        except sqlite3.OperationalError as e:
            logger.warning(f"SqliteBackend.query_news_feed: {e}")
            return empty
        finally:
            conn.close()

    def _news_df(self, sql: str, params: list, cols: list) -> pd.DataFrame:
        try:
            conn = self._connect()
        except sqlite3.OperationalError:
            return pd.DataFrame(columns=cols)
        try:
            rows = conn.execute(sql, params).fetchall()
            return pd.DataFrame([tuple(r) for r in rows], columns=cols) if rows \
                else pd.DataFrame(columns=cols)
        except sqlite3.OperationalError as e:
            logger.warning(f"SqliteBackend news query failed ({e})")
            return pd.DataFrame(columns=cols)
        finally:
            conn.close()

    # --- iv history + fundamentals (3c-A): read-mostly snapshots -------------

    def query_iv_history(self, ticker: str) -> pd.DataFrame:
        """Local IV history for ``ticker`` (ordered by date ASC) — same columns as
        the PG path. Empty frame on any miss (caller falls back to PG)."""
        empty = pd.DataFrame(columns=_IV_COLS)
        ticker = self._canon(ticker)
        try:
            conn = self._connect()
        except sqlite3.OperationalError:
            return empty
        try:
            rows = conn.execute(
                "SELECT date, atm_iv, hv_30d, vrp, spot_price, num_quotes FROM iv_history "
                "WHERE ticker = ? ORDER BY date ASC",
                (ticker,),
            ).fetchall()
            return pd.DataFrame([tuple(r) for r in rows], columns=_IV_COLS) if rows else empty
        except sqlite3.OperationalError as e:
            logger.warning(f"SqliteBackend.query_iv_history({ticker}): {e}")
            return empty
        finally:
            conn.close()

    def query_fundamentals(self, ticker: str) -> dict:
        """Latest local fundamentals snapshot for ``ticker``. Returns the same dict
        shape as the PG path (``snapshot`` / ``fin_summary`` / ``ownership`` pulled
        out of the stored ReportSnapshot JSON). Empty ``{}`` on any miss (PG fallback)."""
        ticker = self._canon(ticker)
        try:
            conn = self._connect()
        except sqlite3.OperationalError:
            return {}
        try:
            row = conn.execute(
                # id DESC tiebreaks same-day snapshots → deterministic latest (== PG path)
                "SELECT data, snapshot_date FROM fundamentals "
                "WHERE ticker = ? ORDER BY snapshot_date DESC, id DESC LIMIT 1",
                (ticker,),
            ).fetchone()
        except sqlite3.OperationalError as e:
            logger.warning(f"SqliteBackend.query_fundamentals({ticker}): {e}")
            return {}
        finally:
            conn.close()
        if row is None:
            return {}
        try:
            data = json.loads(row["data"]) if isinstance(row["data"], str) else row["data"]
        except (ValueError, TypeError):
            return {}
        reports = data.get("reports", data) if isinstance(data, dict) else {}
        if not isinstance(reports, dict):
            reports = {}
        return {
            "ticker": ticker,
            "collected_at": row["snapshot_date"] or "",
            "snapshot": reports.get("ReportSnapshot", {}),
            "fin_summary": reports.get("ReportsFinSummary", {}),
            "ownership": reports.get("ReportsOwnership", {}),
        }

    # --- financial_cache (3c-C): the ONE writable path, local-primary -----------

    @staticmethod
    def _utc_now_iso() -> str:
        # Same format the cache stores expires_at in → string compare is chronological.
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _connect_rw(self) -> sqlite3.Connection:
        """Writable connection — used ONLY by ``set_financial_cache`` (every other
        method here is read-only). WAL + busy_timeout so a cache write is safe
        alongside the read-only routing reads."""
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.execute("PRAGMA busy_timeout = 10000")
        try:
            conn.execute("PRAGMA journal_mode = WAL")
        except sqlite3.OperationalError:
            pass
        return conn

    def get_financial_cache(self, cache_key: str) -> Optional[dict]:
        """LOCAL financial_cache read (cache_key-keyed), expiry-checked against now.
        Returns None on miss / expired / missing table (pre-3c-C DB) so
        LocalMarketDatabaseBackend can fall back to PG."""
        try:
            conn = self._connect()  # read-only
        except sqlite3.OperationalError:
            return None
        try:
            row = conn.execute(
                "SELECT data FROM financial_cache WHERE cache_key = ? AND expires_at > ?",
                (cache_key, self._utc_now_iso()),
            ).fetchone()
        except sqlite3.OperationalError:
            return None  # table absent (pre-3c-C DB) etc.
        finally:
            conn.close()
        if row is None:
            return None
        try:
            return json.loads(row["data"]) if isinstance(row["data"], str) else row["data"]
        except (ValueError, TypeError):
            return None

    def set_financial_cache(self, cache_key: str, ticker: str, data: dict,
                            ttl_days: int = 90, source: str = "sec_edgar",
                            *, fetched_at: Optional[str] = None,
                            expires_at: Optional[str] = None) -> bool:
        """LOCAL-only financial_cache write — the single writable entry point of this
        backend. ``fetched_at``/``expires_at`` may be passed explicitly to promote an
        existing PG row verbatim (preserving its TTL); otherwise derived from
        ``ttl_days`` at now. Best-effort: returns False on any failure.

        Serialized against a bootstrap rebuild via ``_CACHE_WRITE_LOCK`` so a write
        racing the swap is queued (lands in the swapped-in DB) rather than dropped
        with the old inode."""
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        if fetched_at is None:
            fetched_at = now.isoformat(timespec="seconds")
        if expires_at is None:
            expires_at = (now + timedelta(days=ttl_days)).isoformat(timespec="seconds")
        from src.market_data_admin import _FIN_CACHE_SCHEMA, _CACHE_WRITE_LOCK
        with _CACHE_WRITE_LOCK:
            try:
                conn = self._connect_rw()
            except sqlite3.OperationalError as e:
                # must not be silent: a False here can mean a PAID response goes
                # uncached upstream (FinancialDatasetsClient warns + file-falls-back)
                logger.warning(f"SqliteBackend.set_financial_cache({cache_key}): "
                               f"cannot open DB for write ({e})")
                return False
            try:
                conn.executescript(_FIN_CACHE_SCHEMA)  # tolerate a pre-3c-C DB
                conn.execute(
                    "INSERT INTO financial_cache "
                    "(cache_key, source, ticker, data, fetched_at, expires_at) "
                    "VALUES (?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(cache_key) DO UPDATE SET "
                    "  source=excluded.source, ticker=excluded.ticker, data=excluded.data, "
                    "  fetched_at=excluded.fetched_at, expires_at=excluded.expires_at",
                    (cache_key, source, ticker.upper(), json.dumps(data), fetched_at, expires_at),
                )
                conn.commit()
                return True
            except (sqlite3.OperationalError, sqlite3.IntegrityError, TypeError, ValueError) as e:
                logger.warning(f"SqliteBackend.set_financial_cache({cache_key}): {e}")
                return False
            finally:
                conn.close()

    def get_available_tickers(self, data_type: str) -> List[str]:
        """Distinct tickers for a local domain (prices 3a / news 3b / iv_history /
        fundamentals 3c-A)."""
        table = {"prices": "prices", "news": "news",
                 "iv_history": "iv_history", "fundamentals": "fundamentals"}.get(data_type)
        if table is None:
            return []
        try:
            conn = self._connect()
        except sqlite3.OperationalError:
            return []
        try:
            rows = conn.execute(f"SELECT DISTINCT ticker FROM {table} ORDER BY ticker").fetchall()
            return [r[0] for r in rows]
        except sqlite3.OperationalError:
            return []
        finally:
            conn.close()

    def close(self) -> None:  # symmetry with DatabaseBackend; nothing persistent to close
        pass
