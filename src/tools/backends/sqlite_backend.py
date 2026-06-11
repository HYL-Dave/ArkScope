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


class SqliteBackend:
    """Local market-data backend over ``market_data.db`` (3a prices + 3b news/FTS5)."""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)

    def _connect(self) -> sqlite3.Connection:
        # Read-only: the backend never writes (migration owns writes).
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def query_prices(self, ticker: str, interval: str = "15min", days: int = 30) -> pd.DataFrame:
        """OHLCV bars for ``ticker`` over the last ``days`` at ``interval``.

        Returns native rows at the requested interval; for 1d/1h with no native
        rows, rolls up from stored 15min bars (first-open / max-high / min-low /
        last-close / sum-volume) — same definition as the PG path. Empty frame on
        any miss (LocalMarketDatabaseBackend then falls back to PG).
        """
        ticker = ticker.upper()
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
        """Local news articles (UNSCORED). Score-dependent requests
        (``scored_only`` / a specific ``model``) cannot be served locally → return
        empty so LocalMarketDatabaseBackend falls back to PG (where news_scores live)."""
        empty = pd.DataFrame(columns=_NEWS_COLS)
        if scored_only or model:
            return empty
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        conds, params = ["published_at >= ?"], [cutoff]
        if ticker:
            conds.append("ticker = ?")
            params.append(ticker.upper())
        if source != "auto":
            conds.append("source = ?")
            params.append(source)
        sql = (
            "SELECT substr(published_at, 1, 10) AS date, ticker, title, source, url, publisher, "
            "NULL AS sentiment_score, NULL AS risk_score, NULL AS scored_model, description "
            f"FROM news WHERE {' AND '.join(conds)} ORDER BY published_at DESC"
        )
        return self._news_df(sql, params, _NEWS_COLS)

    def query_news_search(self, query: str = "", ticker: Optional[str] = None, days: int = 30,
                          limit: int = 20, scored_only: bool = True) -> pd.DataFrame:
        """Local full-text news search via SQLite FTS5 (bm25 ranking), with a LIKE
        fallback for <3-char queries — mirroring the PG tsvector + ILIKE-fallback
        path. Scored requests → empty (PG fallback)."""
        empty = pd.DataFrame(columns=_NEWS_SEARCH_COLS)
        if scored_only:
            return empty
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        cols = ("substr(n.published_at, 1, 10) AS date, n.ticker, n.title, n.source, n.url, "
                "n.publisher, NULL AS sentiment_score, NULL AS risk_score, n.description")
        q = (query or "").strip()
        conds, params = ["n.published_at >= ?"], [cutoff]
        if ticker:
            conds.append("n.ticker = ?")
            params.append(ticker.upper())
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
                        limit: int = 50, offset: int = 0) -> dict:
        """Score-free local news feed for the 新聞·事件 surface: FULL
        ``published_at`` timestamps, newest first, paginated, with window facets
        (total / per-source / per-day counts over the SAME filters). Search uses
        FTS5 tokenized-AND (≥3 chars) or LIKE for shorter queries.

        ``available`` is False when the local DB/table is missing (pre-3b DB) so
        the router can fall back to PG; an available-but-empty result is an
        honest zero, NOT a fallback trigger."""
        empty = {"available": False, "items": [], "total": 0, "sources": {}, "days": {}}
        try:
            conn = self._connect()
        except sqlite3.OperationalError:
            return empty
        try:
            cutoff = (date.today() - timedelta(days=days)).isoformat()
            conds, params = ["n.published_at >= ?"], [cutoff]
            base_from = "news n"
            if ticker:
                conds.append("n.ticker = ?")
                params.append(ticker.upper())
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
            where = " AND ".join(conds)

            total = conn.execute(
                f"SELECT COUNT(*) FROM {base_from} WHERE {where}", params).fetchone()[0]
            sources = dict(conn.execute(
                f"SELECT n.source, COUNT(*) FROM {base_from} WHERE {where} "
                "GROUP BY n.source", params).fetchall())
            day_counts = dict(conn.execute(
                f"SELECT substr(n.published_at, 1, 10), COUNT(*) FROM {base_from} "
                f"WHERE {where} GROUP BY 1 ORDER BY 1", params).fetchall())
            # Searching → RELEVANCE order (bm25, title weighted 10x over
            # description so passing mentions in summaries rank below real title
            # hits); browsing → chronological. bm25 is ascending-better in FTS5.
            order = ("bm25(news_fts, 10.0, 1.0), n.published_at DESC"
                     if base_from.startswith("news_fts") else "n.published_at DESC")
            rows = conn.execute(
                f"SELECT n.published_at, n.ticker, n.title, n.url, n.publisher, "
                f"n.source, n.description FROM {base_from} WHERE {where} "
                f"ORDER BY {order} LIMIT ? OFFSET ?",
                [*params, max(1, min(200, limit)), max(0, offset)]).fetchall()
            items = [{"published_at": r[0], "ticker": r[1], "title": r[2],
                      "url": r[3], "publisher": r[4], "source": r[5],
                      "description": clean_snippet(r[6])} for r in rows]
            return {"available": True, "items": items, "total": total,
                    "sources": sources, "days": day_counts}
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
        try:
            conn = self._connect()
        except sqlite3.OperationalError:
            return empty
        try:
            rows = conn.execute(
                "SELECT date, atm_iv, hv_30d, vrp, spot_price, num_quotes FROM iv_history "
                "WHERE ticker = ? ORDER BY date ASC",
                (ticker.upper(),),
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
        ticker = ticker.upper()
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
