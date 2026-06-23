"""
SACaptureDatabaseBackend — slice 3d prep-2: every Seeking-Alpha (sa_*) method of
the PostgreSQL DatabaseBackend re-implemented against data/sa_capture.db.

HARD CUTOVER SEMANTICS (runbook L1 / SPEC LOCK #9): every sa_* override hits
ONLY sa_capture.db. NEVER super() for sa_* methods, never a PG fallback — not
even on empty results (an empty local read is an honest zero; PG is frozen at
flip, and a fallback would resurrect stale rows and mask un-ported readers).
Rollback = flip the toggle back, not a fallback.

Why a subclass of LocalMarketDatabaseBackend: ~10 SA DAL methods gate on
``isinstance(backend, DatabaseBackend)`` (data_access.py) — a wrapper would fail
them and SILENTLY DROP SA WRITES (runbook risk #1). Extending LMDB lets this one
class also serve the use_local_market + use_local_sa both-on case; with
``market_db=""`` LMDB's market overrides degrade safely to PG through their
existing per-call try/except (SqliteBackend only opens the file at query time).
All non-SA methods inherit unchanged.

Connection + value discipline comes from src/sa_capture_store.py exclusively:
``store.connect()`` (WAL + busy_timeout + foreign_keys=ON + schema ensured +
sqlite3.Row) / ``store.connect(read_only=True)`` for pure reads, and
``canon_ts()/canon_date()/now_ts()`` at EVERY write boundary — ONE on-disk
timestamp format, because apply_sa_refresh's mark-stale is a lexicographic TEXT
compare. Never SQL CURRENT_TIMESTAMP/NOW(). FTS5 mirrors are maintained by
schema TRIGGERS — write methods never touch the *_fts tables.

Dialect sweep (runbook §1 PG-isms):
  - %s / %(x)s → ?; RealDictCursor → sqlite3.Row; NOW()/INTERVAL arithmetic →
    Python-computed canonical strings passed as parameters;
  - TEXT[] → junction tables (writes replace = DELETE+INSERT inside the parent
    row's transaction; reads re-assemble Python lists under the same dict key);
  - JSONB → TEXT (json.dumps on write, json.loads on read — matching psycopg2's
    automatic jsonb→dict conversion);
  - to_tsvector @@ plainto_tsquery → FTS5 MATCH on the trigger-maintained
    mirrors, tokenized-AND with phrase-quoting (sqlite_backend._fts_match);
  - GREATEST → max(); FILTER (WHERE …) → SUM(CASE …); SUBSTRING/EXTRACT(YEAR) →
    substr; IS NOT DISTINCT FROM → IS; ``ORDER BY col DESC NULLS LAST`` →
    ``ORDER BY (col IS NULL), col DESC``; boolean columns are 0/1 on disk and
    converted back to Python bools on read for PG shape parity;
  - the PG regex operator ``~`` → a per-connection REGEXP function (Python re).

NOT ported on purpose:
  - sa_comment_signals WRITES (comment_signal_backfill / extract job) — paused
    second writer, follow-up #1 (runbook L3). db_backend.py contains NO
    sa_comment_signals read helpers (the signal readers are raw ``_get_conn()``
    bypassers in sa_tools/sa_digest_tools → prep-3, not this class).
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from ... import sa_capture_store as store
from .db_backend import (
    DatabaseBackend,  # noqa: F401  (re-exported for isinstance users/tests)
    _plan_comment_duplicate_cleanup,
    _prepare_comments_for_upsert,
)
from .local_market_backend import LocalMarketDatabaseBackend
from .sqlite_backend import SqliteBackend

logger = logging.getLogger(__name__)

# PG: body_markdown ~ E'^# .+\n\n# '  (POSIX, '.' does not cross newlines —
# same semantics as Python re.search without DOTALL; '^' anchors string start).
_DIRTY_BODY_PATTERN = r"^# .+\n\n# "

_EPOCH_TS = "1970-01-01T00:00:00+00:00"  # COALESCE floor, canonical format


def _regexp(pattern: str, value: Optional[str]) -> int:
    """SQLite REGEXP user function: ``X REGEXP Y`` calls ``regexp(Y, X)``."""
    if value is None:
        return 0
    return 1 if re.search(pattern, value) else 0


def _fts_match(q: str) -> str:
    """plainto_tsquery parity: tokenized-AND, operator-neutralizing phrase quotes
    (the shipped 3b precedent in SqliteBackend)."""
    return SqliteBackend._fts_match(q)


def _loads(value: Any) -> Any:
    """json.loads TEXT → dict/list, matching psycopg2's automatic jsonb decode."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return value
    return value


def _parse_date(value: Any) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


class SACaptureDatabaseBackend(LocalMarketDatabaseBackend):
    """DatabaseBackend whose SA domain lives in data/sa_capture.db (hard cutover)."""

    def __init__(self, dsn: str, sslmode: str = "prefer", *, sa_db: str,
                 market_db: str = "", strict: bool = False):
        # DatabaseBackend connects lazily (_get_conn), so constructing this with a
        # dead/fake PG DSN must not touch the network. ``strict`` threads to the market
        # overrides (local-only, no PG fallback); SA reads are already hard-local.
        super().__init__(dsn, sslmode, market_db=market_db, strict=strict)
        self._sa_db = sa_db

    # ------------------------------------------------------------------
    # connections (per-call: the native host is a fresh process per message)
    # ------------------------------------------------------------------

    def _sa_conn(self) -> sqlite3.Connection:
        return store.connect(self._sa_db)

    def _sa_read(self) -> sqlite3.Connection:
        return store.connect(self._sa_db, read_only=True)

    # ================================================================
    # Alpha Picks refresh (atomic per-tab)
    # ================================================================

    def apply_sa_refresh(self, scope: str, picks: list, attempt_ts, snapshot_ts) -> int:
        """Atomic per-tab refresh: mark-stale + upsert loop + meta upsert in ONE
        transaction (BEGIN IMMEDIATE). The upsert never touches
        detail_report/detail_fetched_at. Returns count of upserted rows.

        Failure path mirrors the PG version: rollback, then record failure meta in
        a FRESH transaction (own connection), then re-raise.
        """
        attempt = store.canon_ts(attempt_ts) or store.now_ts()
        snapshot = store.canon_ts(snapshot_ts) or store.now_ts()
        conn = self._sa_conn()
        try:
            now = store.now_ts()
            conn.execute("BEGIN IMMEDIATE")

            # 1. Mark rows not seen in this snapshot as stale — lexicographic TEXT
            #    compare; correct because BOTH sides are canon_ts-canonical.
            conn.execute(
                "UPDATE sa_alpha_picks SET is_stale = 1, updated_at = ? "
                "WHERE portfolio_status = ? AND last_seen_snapshot < ?",
                (now, scope, snapshot),
            )

            # 2. Upsert picks against the scope-asymmetric PARTIAL unique indexes
            #    (sql/014/015 parity, rebuilt verbatim in sa_capture_store._SCHEMA).
            update_set = (
                "company = excluded.company, "
                "closed_date = excluded.closed_date, "
                "is_stale = 0, "
                "return_pct = excluded.return_pct, "
                "sector = excluded.sector, "
                "sa_rating = excluded.sa_rating, "
                "holding_pct = excluded.holding_pct, "
                "raw_data = excluded.raw_data, "
                "last_seen_snapshot = excluded.last_seen_snapshot, "
                "updated_at = ?"
            )
            if scope == "closed":
                conflict_clause = (
                    "ON CONFLICT (symbol, picked_date, portfolio_status, closed_date) "
                    "WHERE portfolio_status = 'closed' DO UPDATE SET " + update_set
                )
            else:
                conflict_clause = (
                    "ON CONFLICT (symbol, picked_date, portfolio_status) "
                    "WHERE portfolio_status = 'current' DO UPDATE SET " + update_set
                )
            sql = (
                "INSERT INTO sa_alpha_picks "
                "(symbol, company, picked_date, closed_date, portfolio_status, "
                " is_stale, return_pct, sector, sa_rating, holding_pct, "
                " raw_data, last_seen_snapshot, fetched_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?) " + conflict_clause
            )
            count = 0
            for pick in picks:
                conn.execute(
                    sql,
                    (
                        pick.get("symbol"),
                        pick.get("company", ""),
                        store.canon_date(pick.get("picked_date")),
                        store.canon_date(pick.get("closed_date")),
                        scope,
                        pick.get("return_pct"),
                        pick.get("sector"),
                        pick.get("sa_rating"),
                        pick.get("holding_pct"),
                        json.dumps(pick.get("raw_data")) if pick.get("raw_data") else None,
                        snapshot,
                        now,  # fetched_at (INSERT only — PG column default NOW())
                        now,  # updated_at (INSERT)
                        now,  # updated_at (DO UPDATE)
                    ),
                )
                count += 1

            # 3. Refresh meta (success: overwrite all fields, ok=1)
            conn.execute(
                "INSERT INTO sa_refresh_meta "
                "(scope, last_attempt_at, last_success_at, snapshot_ts, "
                " row_count, ok, last_error, updated_at) "
                "VALUES (?, ?, ?, ?, ?, 1, NULL, ?) "
                "ON CONFLICT (scope) DO UPDATE SET "
                "    last_attempt_at = excluded.last_attempt_at, "
                "    last_success_at = excluded.last_success_at, "
                "    snapshot_ts = excluded.snapshot_ts, "
                "    row_count = excluded.row_count, "
                "    ok = 1, last_error = NULL, updated_at = ?",
                (scope, attempt, snapshot, snapshot, count, now, now),
            )

            conn.commit()
            return count

        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            # Failure meta in a FRESH transaction (PG path: db_backend ~:1321-1329)
            try:
                self.record_sa_refresh_failure(scope, attempt_ts, str(e))
            except Exception:
                pass
            raise
        finally:
            conn.close()

    def record_sa_refresh_failure(self, scope: str, attempt_ts, error: str) -> None:
        """Record refresh failure. Only touches last_attempt_at / ok=0 / last_error
        (+ updated_at); preserves last_success_at, snapshot_ts, row_count."""
        try:
            conn = self._sa_conn()
        except Exception as e:
            logger.error("Failed to record SA refresh failure: %s", e)
            return
        try:
            now = store.now_ts()
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO sa_refresh_meta "
                "(scope, last_attempt_at, ok, last_error, updated_at) "
                "VALUES (?, ?, 0, ?, ?) "
                "ON CONFLICT (scope) DO UPDATE SET "
                "    last_attempt_at = excluded.last_attempt_at, "
                "    ok = 0, last_error = excluded.last_error, updated_at = ?",
                (scope, store.canon_ts(attempt_ts) or now, error, now, now),
            )
            conn.commit()
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            logger.error("Failed to record SA refresh failure: %s", e)
        finally:
            conn.close()

    # ================================================================
    # Alpha Picks reads
    # ================================================================

    def query_sa_picks(
        self,
        portfolio_status: Optional[str] = None,
        symbol: Optional[str] = None,
        include_stale: bool = False,
    ) -> list:
        """Query SA Alpha Picks with optional filters (local only)."""
        conditions = []
        params: list = []
        if portfolio_status and portfolio_status != "all":
            conditions.append("portfolio_status = ?")
            params.append(portfolio_status)
        if symbol:
            conditions.append("symbol = ?")
            params.append(symbol.upper())
        if not include_stale:
            conditions.append("is_stale = 0")
        where = " AND ".join(conditions) if conditions else "1"
        try:
            conn = self._sa_read()
        except Exception as e:
            logger.error("Failed to query SA picks: %s", e)
            return []
        try:
            rows = conn.execute(
                f"SELECT symbol, company, picked_date, closed_date, portfolio_status, "
                f"is_stale, return_pct, sector, sa_rating, holding_pct, "
                f"detail_fetched_at IS NOT NULL AS has_detail, "
                f"last_seen_snapshot, fetched_at, updated_at "
                f"FROM sa_alpha_picks WHERE {where} "
                f"ORDER BY portfolio_status, picked_date DESC",
                tuple(params),
            ).fetchall()
            out = []
            for r in rows:
                d = dict(r)
                d["is_stale"] = bool(d["is_stale"])      # PG boolean parity
                d["has_detail"] = bool(d["has_detail"])  # PG boolean parity
                out.append(d)
            return out
        except Exception as e:
            logger.error("Failed to query SA picks: %s", e)
            return []
        finally:
            conn.close()

    def get_sa_pick_detail(
        self, symbol: str, picked_date: Optional[str] = None
    ) -> Optional[dict]:
        """Detail for one pick. picked_date=None → deterministic fallback:
        current + non-stale first, then stale, then any (PG-identical ordering)."""
        try:
            conn = self._sa_read()
        except Exception as e:
            logger.error("Failed to get SA pick detail: %s", e)
            return None
        try:
            if picked_date:
                row = conn.execute(
                    "SELECT * FROM sa_alpha_picks "
                    "WHERE symbol = ? AND picked_date = ? "
                    "ORDER BY CASE portfolio_status WHEN 'current' THEN 0 ELSE 1 END, "
                    "is_stale ASC LIMIT 1",
                    (symbol.upper(), store.canon_date(picked_date)),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM sa_alpha_picks "
                    "WHERE symbol = ? AND portfolio_status = 'current' "
                    "ORDER BY is_stale ASC, picked_date DESC LIMIT 1",
                    (symbol.upper(),),
                ).fetchone()
            if not row:
                return None
            d = dict(row)
            d["is_stale"] = bool(d["is_stale"])
            d["raw_data"] = _loads(d.get("raw_data"))  # psycopg2 jsonb→dict parity
            return d
        except Exception as e:
            logger.error("Failed to get SA pick detail: %s", e)
            return None
        finally:
            conn.close()

    def update_sa_pick_detail(self, symbol: str, picked_date: str, content: str) -> bool:
        """Update detail_report for a specific pick."""
        try:
            conn = self._sa_conn()
        except Exception as e:
            logger.error("Failed to update SA pick detail: %s", e)
            return False
        try:
            now = store.now_ts()
            cur = conn.execute(
                "UPDATE sa_alpha_picks SET detail_report = ?, "
                "detail_fetched_at = ?, updated_at = ? "
                "WHERE symbol = ? AND picked_date = ?",
                (content, now, now, symbol.upper(), store.canon_date(picked_date)),
            )
            conn.commit()
            return cur.rowcount > 0
        except Exception as e:
            logger.error("Failed to update SA pick detail: %s", e)
            return False
        finally:
            conn.close()

    def get_sa_refresh_meta(self) -> dict:
        """Per-tab refresh metadata: {"current": {...}, "closed": {...}}.

        FIXES the PG version's unguarded ``.isoformat()`` (db_backend ~:1464-1466,
        AttributeError → silent {}): timestamps here are already canonical TEXT and
        are returned as-is. ``ok`` is converted back to a Python bool for parity.
        """
        result: dict = {}
        try:
            conn = self._sa_read()
        except Exception as e:
            logger.error("Failed to get SA refresh meta: %s", e)
            return result
        try:
            for row in conn.execute("SELECT * FROM sa_refresh_meta").fetchall():
                d = dict(row)
                d["ok"] = bool(d["ok"])
                result[d["scope"]] = d
        except Exception as e:
            logger.error("Failed to get SA refresh meta: %s", e)
        finally:
            conn.close()
        return result

    # ================================================================
    # Market news
    # ================================================================

    def upsert_sa_market_news(self, items: list) -> int:
        """Batch upsert market-news metadata. Per-item transaction (PG ran with
        autocommit per statement, so earlier items persist if a later one fails).

        Conflict semantics (PG parity): bumps updated_at NOT fetched_at; never
        touches body_markdown/detail_fetched_at; comments_count = GREATEST→max;
        published_*/category/summary/raw_data COALESCE-keep; the PG
        ``CASE WHEN array_length(EXCLUDED.tickers,1) > 0`` merge becomes: a
        non-empty incoming set REPLACES the junction rows (DELETE+INSERT in the
        same transaction), an empty one keeps the existing rows.
        """
        try:
            conn = self._sa_conn()
        except Exception as e:
            logger.error("Failed to upsert SA market news: %s", e)
            return 0
        count = 0
        try:
            for item in items:
                now = store.now_ts()
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(
                    """INSERT INTO sa_market_news
                    (news_id, url, title, published_at, published_text,
                     category, summary, comments_count, raw_data, fetched_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (news_id) DO UPDATE SET
                        url = excluded.url,
                        title = excluded.title,
                        published_at = COALESCE(excluded.published_at, sa_market_news.published_at),
                        published_text = COALESCE(excluded.published_text, sa_market_news.published_text),
                        category = COALESCE(excluded.category, sa_market_news.category),
                        summary = COALESCE(excluded.summary, sa_market_news.summary),
                        comments_count = MAX(COALESCE(sa_market_news.comments_count, 0),
                                             COALESCE(excluded.comments_count, 0)),
                        raw_data = COALESCE(excluded.raw_data, sa_market_news.raw_data),
                        updated_at = ?
                    """,
                    (
                        item.get("news_id"),
                        item.get("url"),
                        item.get("title"),
                        store.canon_ts(item.get("published_at")),
                        item.get("published_text"),
                        item.get("category"),
                        item.get("summary"),
                        item.get("comments_count", 0),
                        # None → SQL NULL so COALESCE keeps the existing payload.
                        # (PG passed Json(None) == jsonb 'null', which psycopg2
                        # decodes back to None — read shape is identical.)
                        json.dumps(item.get("raw_data"))
                        if item.get("raw_data") is not None else None,
                        now,  # fetched_at (INSERT only)
                        now,  # updated_at (INSERT)
                        now,  # updated_at (DO UPDATE)
                    ),
                )
                tickers = [t for t in (item.get("tickers") or []) if t]
                if tickers:
                    row = conn.execute(
                        "SELECT id FROM sa_market_news WHERE news_id = ?",
                        (item.get("news_id"),),
                    ).fetchone()
                    if row:
                        conn.execute(
                            "DELETE FROM sa_market_news_tickers WHERE news_row_id = ?",
                            (row["id"],),
                        )
                        conn.executemany(
                            "INSERT OR IGNORE INTO sa_market_news_tickers "
                            "(news_row_id, ticker) VALUES (?, ?)",
                            [(row["id"], t) for t in tickers],
                        )
                conn.commit()
                count += 1
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            logger.error("Failed to upsert SA market news: %s", e)
        finally:
            conn.close()
        return count

    @staticmethod
    def _market_news_tickers(conn: sqlite3.Connection, row_ids: list) -> Dict[int, list]:
        """Junction rows for a set of news row ids, insertion (rowid) order —
        replaces reading the PG TEXT[] column. One query, not N+1."""
        if not row_ids:
            return {}
        placeholders = ",".join("?" * len(row_ids))
        out: Dict[int, list] = {}
        for r in conn.execute(
            f"SELECT news_row_id, ticker FROM sa_market_news_tickers "
            f"WHERE news_row_id IN ({placeholders}) ORDER BY rowid",
            tuple(row_ids),
        ):
            out.setdefault(r["news_row_id"], []).append(r["ticker"])
        return out

    def query_sa_market_news(
        self,
        ticker: Optional[str] = None,
        keyword: Optional[str] = None,
        limit: int = 20,
    ) -> list:
        """Recent market-news items. ``= ANY(tickers)`` → junction membership;
        tsvector search → sa_market_news_fts MATCH (phrase-quoted tokens);
        ``tickers`` is returned as a Python list (reader/UI contract)."""
        conditions = []
        params: list = []
        if ticker:
            conditions.append(
                "n.id IN (SELECT news_row_id FROM sa_market_news_tickers WHERE ticker = ?)"
            )
            params.append(ticker.upper())
        if keyword:
            match = _fts_match(keyword)
            if not match:
                return []  # plainto_tsquery('') matches nothing
            conditions.append(
                "n.id IN (SELECT rowid FROM sa_market_news_fts "
                "WHERE sa_market_news_fts MATCH ?)"
            )
            params.append(match)
        where = " AND ".join(conditions) if conditions else "1"
        params.append(max(1, min(int(limit or 20), 100)))
        try:
            conn = self._sa_read()
        except Exception as e:
            logger.error("Failed to query SA market news: %s", e)
            return []
        try:
            rows = conn.execute(
                f"""SELECT n.id, n.news_id, n.url, n.title, n.published_at,
                    n.published_text, n.category, n.summary, n.comments_count,
                    n.body_markdown, n.detail_fetched_at, n.fetched_at, n.updated_at
                FROM sa_market_news n
                WHERE {where}
                ORDER BY (COALESCE(n.published_at, n.fetched_at) IS NULL),
                         COALESCE(n.published_at, n.fetched_at) DESC, n.id DESC
                LIMIT ?""",
                tuple(params),
            ).fetchall()
            tickers_by_row = self._market_news_tickers(conn, [r["id"] for r in rows])
            out = []
            for r in rows:
                d = dict(r)
                row_id = d.pop("id")  # internal join key, not part of the PG shape
                out.append({
                    "news_id": d["news_id"],
                    "url": d["url"],
                    "title": d["title"],
                    "published_at": d["published_at"],  # already canonical TEXT
                    "published_text": d["published_text"],
                    "tickers": tickers_by_row.get(row_id, []),
                    "category": d["category"],
                    "summary": d["summary"],
                    "comments_count": d["comments_count"],
                    "body_markdown": d["body_markdown"],
                    "detail_fetched_at": d["detail_fetched_at"],
                    "fetched_at": d["fetched_at"],
                    "updated_at": d["updated_at"],
                })
            return out
        except Exception as e:
            logger.error("Failed to query SA market news: %s", e)
            return []
        finally:
            conn.close()

    def query_sa_market_news_recent_ids(self, limit: int = 200) -> list[str]:
        """Recent market-news IDs, newest first."""
        try:
            conn = self._sa_read()
        except Exception as e:
            logger.error("Failed to query SA market news recent ids: %s", e)
            return []
        try:
            rows = conn.execute(
                "SELECT news_id FROM sa_market_news "
                "WHERE news_id IS NOT NULL AND news_id <> '' "
                "ORDER BY (COALESCE(published_at, fetched_at) IS NULL), "
                "COALESCE(published_at, fetched_at) DESC, id DESC LIMIT ?",
                (max(1, min(int(limit or 200), 1000)),),
            ).fetchall()
            return [row[0] for row in rows if row and row[0]]
        except Exception as e:
            logger.error("Failed to query SA market news recent ids: %s", e)
            return []
        finally:
            conn.close()

    def query_sa_market_news_need_detail(
        self,
        news_ids: list | None = None,
        detail_cache_hours: int = 24,
        limit: int = 50,
        exclude_news_ids: list | None = None,
        published_within_hours: int | None = None,
    ) -> list:
        """Market-news items still needing a detail body fetch. PG's
        ``NOW() - (N || ' hours')::interval`` becomes Python-computed canonical
        cutoff strings compared lexicographically."""
        if limit is not None and int(limit or 0) <= 0:
            return []
        now_dt = datetime.now(timezone.utc)
        filters = [
            "(body_markdown IS NULL OR body_markdown = '' "
            "OR detail_fetched_at IS NULL OR detail_fetched_at < ?)"
        ]
        params: list = [store.canon_ts(now_dt - timedelta(hours=int(detail_cache_hours)))]
        if news_ids:
            filters.append(f"news_id IN ({','.join('?' * len(news_ids))})")
            params.extend(news_ids)
        if exclude_news_ids:
            filters.append(f"news_id NOT IN ({','.join('?' * len(exclude_news_ids))})")
            params.extend(exclude_news_ids)
        if published_within_hours is not None:
            filters.append("COALESCE(published_at, fetched_at) >= ?")
            params.append(store.canon_ts(now_dt - timedelta(hours=int(published_within_hours))))
        params.append(max(1, min(int(limit or 50), 200)))
        try:
            conn = self._sa_read()
        except Exception as e:
            logger.error("Failed to query SA market news detail candidates: %s", e)
            return []
        try:
            rows = conn.execute(
                f"""SELECT news_id, url FROM sa_market_news
                WHERE {' AND '.join(filters)}
                ORDER BY
                  CASE WHEN body_markdown IS NULL OR body_markdown = '' THEN 0 ELSE 1 END,
                  COALESCE(detail_fetched_at, '{_EPOCH_TS}') ASC,
                  (COALESCE(published_at, fetched_at) IS NULL),
                  COALESCE(published_at, fetched_at) DESC
                LIMIT ?""",
                tuple(params),
            ).fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error("Failed to query SA market news detail candidates: %s", e)
            return []
        finally:
            conn.close()

    def invalidate_dirty_sa_market_news_detail(self) -> int:
        """Drop cached market-news bodies matching known chrome noise. The PG
        ``~`` regex predicate runs through a per-connection REGEXP function."""
        try:
            conn = self._sa_conn()
        except Exception as e:
            logger.error("Failed to invalidate dirty SA market news detail cache: %s", e)
            return 0
        try:
            conn.create_function("regexp", 2, _regexp)
            now = store.now_ts()
            conn.execute("BEGIN IMMEDIATE")
            cur = conn.execute(
                """UPDATE sa_market_news
                SET body_markdown = NULL,
                    detail_fetched_at = NULL,
                    updated_at = ?
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
                    OR body_markdown REGEXP ?
                  )
                """,
                (now, _DIRTY_BODY_PATTERN),
            )
            conn.commit()
            return int(cur.rowcount or 0)
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            logger.error("Failed to invalidate dirty SA market news detail cache: %s", e)
            return 0
        finally:
            conn.close()

    def save_sa_market_news_detail(self, news_id: str, body_markdown: str) -> bool:
        """Persist a single market-news body Markdown."""
        try:
            conn = self._sa_conn()
        except Exception as e:
            logger.error("Failed to save SA market news detail for %s: %s", news_id, e)
            return False
        try:
            now = store.now_ts()
            cur = conn.execute(
                "UPDATE sa_market_news SET body_markdown = ?, "
                "detail_fetched_at = ?, updated_at = ? WHERE news_id = ?",
                (body_markdown, now, now, news_id),
            )
            conn.commit()
            return cur.rowcount > 0
        except Exception as e:
            logger.error("Failed to save SA market news detail for %s: %s", news_id, e)
            return False
        finally:
            conn.close()

    # ================================================================
    # Articles + comments
    # ================================================================

    def upsert_sa_articles_meta(self, articles: list) -> int:
        """Batch upsert article metadata (no body_markdown). Per-item transaction
        (PG autocommit parity: earlier items persist if a later one fails)."""
        try:
            conn = self._sa_conn()
        except Exception as e:
            logger.error("Failed to upsert SA articles: %s", e)
            return 0
        count = 0
        try:
            for a in articles:
                now = store.now_ts()
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(
                    """INSERT INTO sa_articles
                    (article_id, url, title, ticker, published_date,
                     article_type, comments_count, raw_data, fetched_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (article_id) DO UPDATE SET
                        title = excluded.title,
                        url = excluded.url,
                        ticker = COALESCE(excluded.ticker, sa_articles.ticker),
                        published_date = COALESCE(excluded.published_date, sa_articles.published_date),
                        article_type = COALESCE(excluded.article_type, sa_articles.article_type),
                        comments_count = excluded.comments_count,
                        updated_at = ?
                    """,
                    (
                        a.get("article_id"),
                        a.get("url"),
                        a.get("title"),
                        a.get("ticker"),
                        store.canon_date(a.get("published_date")),
                        a.get("article_type"),
                        a.get("comments_count", 0),
                        json.dumps(a.get("raw_data")) if a.get("raw_data") is not None else None,
                        now,  # fetched_at (INSERT only)
                        now,  # updated_at (INSERT)
                        now,  # updated_at (DO UPDATE)
                    ),
                )
                conn.commit()
                count += 1
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            logger.error("Failed to upsert SA articles: %s", e)
        finally:
            conn.close()
        return count

    def sanitize_corrupted_sa_comments_counts(self) -> int:
        """Repair year-prefixed comments_count corruption. PG's
        EXTRACT(YEAR FROM published_date) → substr(published_date, 1, 4)
        (published_date is canonical 'YYYY-MM-DD' TEXT);
        SUBSTRING(x FROM 5) → substr(x, 5)."""
        try:
            conn = self._sa_conn()
        except Exception as e:
            logger.error("Failed to sanitize SA comments_count rows: %s", e)
            return 0
        try:
            now = store.now_ts()
            conn.execute("BEGIN IMMEDIATE")
            cur = conn.execute(
                """UPDATE sa_articles
                SET comments_count = CAST(substr(CAST(comments_count AS TEXT), 5) AS INTEGER),
                    updated_at = ?
                WHERE published_date IS NOT NULL
                  AND comments_count >= 10000
                  AND CAST(comments_count AS TEXT) LIKE substr(published_date, 1, 4) || '%'
                  AND LENGTH(CAST(comments_count AS TEXT)) > 4
                  AND CAST(substr(CAST(comments_count AS TEXT), 5) AS INTEGER) BETWEEN 0 AND 9999
                """,
                (now,),
            )
            conn.commit()
            return int(cur.rowcount or 0)
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            logger.error("Failed to sanitize SA comments_count rows: %s", e)
            return 0
        finally:
            conn.close()

    # -- internal comment helpers (operate on the caller's open connection so
    #    they stay inside the caller's transaction, like the PG cursor versions) --

    def _fetch_existing_article_comments(
        self, conn: sqlite3.Connection, article_id: str
    ) -> List[Dict[str, Any]]:
        rows = conn.execute(
            "SELECT comment_id, parent_comment_id, commenter, comment_text, "
            "upvotes, comment_date "
            "FROM sa_article_comments WHERE article_id = ?",
            (article_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def _count_article_comments(self, conn: sqlite3.Connection, article_id: str) -> int:
        row = conn.execute(
            "SELECT COUNT(*) FROM sa_article_comments WHERE article_id = ?",
            (article_id,),
        ).fetchone()
        return int(row[0] or 0) if row else 0

    def _upsert_article_comments(
        self, conn: sqlite3.Connection, article_id: str, comments: list
    ) -> int:
        # Re-parenting / identity-merge logic is the SHARED module-level helper
        # from db_backend (_prepare_comments_for_upsert) — zero logic duplication.
        prepared_comments = _prepare_comments_for_upsert(
            self._fetch_existing_article_comments(conn, article_id),
            comments,
        )
        now = store.now_ts()
        for comment in prepared_comments:
            conn.execute(
                """INSERT INTO sa_article_comments
                (article_id, comment_id, parent_comment_id,
                 commenter, comment_text, upvotes, comment_date, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (article_id, comment_id) DO UPDATE SET
                    parent_comment_id = COALESCE(sa_article_comments.parent_comment_id, excluded.parent_comment_id),
                    commenter = COALESCE(sa_article_comments.commenter, excluded.commenter),
                    comment_text = excluded.comment_text,
                    upvotes = MAX(COALESCE(sa_article_comments.upvotes, 0), COALESCE(excluded.upvotes, 0)),
                    comment_date = COALESCE(sa_article_comments.comment_date, excluded.comment_date)
                """,
                (
                    article_id,
                    comment.get("comment_id"),
                    comment.get("parent_comment_id"),
                    comment.get("commenter"),
                    comment.get("comment_text"),
                    comment.get("upvotes", 0),
                    store.canon_ts(comment.get("comment_date")),  # write boundary
                    now,  # fetched_at (INSERT only — PG column default NOW())
                ),
            )
        cleanup = self._cleanup_article_comment_duplicates(conn, article_id)
        if cleanup["comments_deleted"] or cleanup["parent_links_repointed"]:
            logger.info(
                "Cleaned SA comment duplicates for %s: deleted=%s parent_links_repointed=%s",
                article_id,
                cleanup["comments_deleted"],
                cleanup["parent_links_repointed"],
            )
        return len(prepared_comments)

    def _cleanup_article_comment_duplicates(
        self, conn: sqlite3.Connection, article_id: str
    ) -> Dict[str, int]:
        groups_processed = 0
        comments_deleted = 0
        parent_links_repointed = 0
        groups = conn.execute(
            "SELECT commenter, comment_text FROM sa_article_comments "
            "WHERE article_id = ? "
            "GROUP BY commenter, comment_text HAVING COUNT(*) > 1",
            (article_id,),
        ).fetchall()
        for group in groups:
            # IS NOT DISTINCT FROM → SQLite's null-safe IS
            rows = [dict(row) for row in conn.execute(
                "SELECT id, comment_id, parent_comment_id, comment_date "
                "FROM sa_article_comments "
                "WHERE article_id = ? AND commenter IS ? AND comment_text IS ? "
                "ORDER BY (comment_date IS NULL), comment_date ASC, id ASC",
                (article_id, group["commenter"], group["comment_text"]),
            ).fetchall()]
            plan = _plan_comment_duplicate_cleanup(rows)
            if not plan["delete_ids"]:
                continue
            groups_processed += 1
            for duplicate_comment_id, canonical_comment_id in plan["parent_rewrites"]:
                cur = conn.execute(
                    "UPDATE sa_article_comments SET parent_comment_id = ? "
                    "WHERE article_id = ? AND parent_comment_id = ?",
                    (canonical_comment_id, article_id, duplicate_comment_id),
                )
                parent_links_repointed += cur.rowcount or 0
            for delete_id in plan["delete_ids"]:
                # FK ON DELETE CASCADE purges sa_comment_signals (+ mention
                # junctions) — foreign_keys=ON comes free from store.connect.
                cur = conn.execute(
                    "DELETE FROM sa_article_comments WHERE id = ?", (delete_id,)
                )
                comments_deleted += cur.rowcount or 0
        return {
            "groups_processed": groups_processed,
            "comments_deleted": comments_deleted,
            "parent_links_repointed": parent_links_repointed,
        }

    def cleanup_mixed_null_date_comment_duplicates(self) -> Dict[str, int]:
        """Collapse safe duplicate groups where a null-date row matches a dated row.
        PG's COUNT(*) FILTER (WHERE …) → SUM(CASE WHEN … THEN 1 ELSE 0 END);
        COUNT(DISTINCT …) already ignores NULLs in both engines."""
        conn = self._sa_conn()
        groups_processed = 0
        comments_deleted = 0
        parent_links_repointed = 0
        try:
            conn.execute("BEGIN IMMEDIATE")
            groups = conn.execute(
                """SELECT article_id, commenter, comment_text
                FROM sa_article_comments
                GROUP BY article_id, commenter, comment_text
                HAVING COUNT(*) > 1
                   AND SUM(CASE WHEN comment_date IS NULL THEN 1 ELSE 0 END) >= 1
                   AND SUM(CASE WHEN comment_date IS NOT NULL THEN 1 ELSE 0 END) >= 1
                   AND COUNT(DISTINCT comment_date) = 1
                """
            ).fetchall()
            for group in groups:
                rows = conn.execute(
                    """SELECT id, comment_id, parent_comment_id, comment_date
                    FROM sa_article_comments
                    WHERE article_id = ? AND commenter IS ? AND comment_text = ?
                    ORDER BY (comment_date IS NULL) ASC, comment_date ASC, id ASC
                    """,
                    (group["article_id"], group["commenter"], group["comment_text"]),
                ).fetchall()
                canonical = next(
                    (row for row in rows if row["comment_date"] is not None), rows[0]
                )
                duplicates = [
                    row for row in rows
                    if row["comment_id"] != canonical["comment_id"]
                    and row["comment_date"] is None
                ]
                if not duplicates:
                    continue
                groups_processed += 1
                for duplicate in duplicates:
                    cur = conn.execute(
                        "UPDATE sa_article_comments SET parent_comment_id = ? "
                        "WHERE article_id = ? AND parent_comment_id = ?",
                        (
                            canonical["comment_id"],
                            group["article_id"],
                            duplicate["comment_id"],
                        ),
                    )
                    parent_links_repointed += cur.rowcount or 0
                    cur = conn.execute(
                        "DELETE FROM sa_article_comments WHERE id = ?",
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
            try:
                conn.rollback()
            except Exception:
                pass
            logger.error("cleanup_mixed_null_date_comment_duplicates failed: %s", e)
            raise
        finally:
            conn.close()

    def save_article_with_comments(
        self,
        article_id: str,
        body_markdown: str,
        comments: list,
        sync_picks: bool = True,
    ) -> dict:
        """Atomic: article content + comments + pick sync in a single transaction."""
        conn = self._sa_conn()
        synced = 0
        try:
            now = store.now_ts()
            conn.execute("BEGIN IMMEDIATE")
            before_count = self._count_article_comments(conn, article_id)
            conn.execute(
                "UPDATE sa_articles SET body_markdown = ?, "
                "detail_fetched_at = ?, comments_fetched_at = ?, "
                "updated_at = ? WHERE article_id = ?",
                (body_markdown, now, now, now, article_id),
            )
            prepared_count = self._upsert_article_comments(conn, article_id, comments)
            after_count = self._count_article_comments(conn, article_id)
            if sync_picks:
                synced = self._sync_canonical_to_picks(conn, article_id)
            conn.commit()
            return {
                "ok": True,
                "synced_picks": synced,
                "prepared_comments": prepared_count,
                "stored_comments_total": after_count,
                "net_new_comments": max(after_count - before_count, 0),
            }
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            logger.error("save_article_with_comments failed: %s", e)
            raise
        finally:
            conn.close()

    def update_article_comments(self, article_id: str, comments: list) -> Dict[str, int]:
        """Comments-only update (refresh runs). Returns refresh stats."""
        conn = self._sa_conn()
        try:
            now = store.now_ts()
            conn.execute("BEGIN IMMEDIATE")
            before_count = self._count_article_comments(conn, article_id)
            prepared_count = self._upsert_article_comments(conn, article_id, comments)
            conn.execute(
                "UPDATE sa_articles SET comments_fetched_at = ?, "
                "updated_at = ? WHERE article_id = ?",
                (now, now, article_id),
            )
            after_count = self._count_article_comments(conn, article_id)
            conn.commit()
            return {
                "prepared_comments": prepared_count,
                "stored_comments_total": after_count,
                "net_new_comments": max(after_count - before_count, 0),
            }
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            logger.error("update_article_comments failed: %s", e)
            raise
        finally:
            conn.close()

    def _sync_canonical_to_picks(self, conn: sqlite3.Connection, article_id: str) -> int:
        """Sync an article into matching picks (same connection = same txn).
        PG date subtraction on DATE columns → Python date math on the canonical
        'YYYY-MM-DD' TEXT values."""
        article = conn.execute(
            "SELECT article_id, ticker, article_type, published_date, body_markdown "
            "FROM sa_articles WHERE article_id = ?",
            (article_id,),
        ).fetchone()
        if not article or not article["ticker"]:
            return 0
        ticker = article["ticker"]
        article_type = article["article_type"]
        published_date = article["published_date"]
        body_md = article["body_markdown"]

        if article_type not in ("analysis", "removal"):
            return 0
        if not body_md:
            return 0

        rows = conn.execute(
            "SELECT id, symbol, picked_date, canonical_article_id "
            "FROM sa_alpha_picks WHERE symbol = ?",
            (ticker,),
        ).fetchall()
        if not rows:
            rows = conn.execute(
                "SELECT id, symbol, picked_date, canonical_article_id "
                "FROM sa_alpha_picks WHERE ? LIKE symbol || '%' "
                "AND LENGTH(?) <= LENGTH(symbol) * 2",
                (ticker, ticker),
            ).fetchall()

        now = store.now_ts()
        synced = 0
        for row in rows:
            pick_id = row["id"]
            picked_date = row["picked_date"]
            current_canonical = row["canonical_article_id"]
            if current_canonical == article_id:
                conn.execute(
                    "UPDATE sa_alpha_picks SET detail_report = ?, "
                    "detail_fetched_at = ?, canonical_article_id = ?, "
                    "updated_at = ? WHERE id = ?",
                    (body_md, now, article_id, now, pick_id),
                )
                synced += 1
                continue

            if current_canonical and published_date and picked_date:
                existing = conn.execute(
                    "SELECT published_date FROM sa_articles WHERE article_id = ?",
                    (current_canonical,),
                ).fetchone()
                if existing and existing["published_date"]:
                    existing_dt = _parse_date(existing["published_date"])
                    new_dt = _parse_date(published_date)
                    picked_dt = _parse_date(picked_date)
                    if existing_dt and new_dt and picked_dt:
                        existing_dist = abs((existing_dt - picked_dt).days)
                        new_dist = abs((new_dt - picked_dt).days)
                        if new_dist >= existing_dist:
                            continue  # existing canonical is closer

            conn.execute(
                "UPDATE sa_alpha_picks SET detail_report = ?, "
                "detail_fetched_at = ?, canonical_article_id = ?, "
                "updated_at = ? WHERE id = ?",
                (body_md, now, article_id, now, pick_id),
            )
            synced += 1

        return synced

    def audit_unresolved_symbols(self) -> dict:
        """Current picks without a canonical article; try exact/prefix ticker match,
        then a full-text fallback.

        LOCKED DECISION (runbook L8 / out-of-scope list): the PG
        to_tsvector/plainto_tsquery fallback DEGRADES to LIKE '%symbol%' in v1 —
        no stemming/tokenization — which can change unresolved counts vs PG.
        Explicitly accepted; FTS5-ifying this audit is a follow-up.
        """
        conn = self._sa_conn()
        unresolved: list = []
        resolved = 0
        try:
            now = store.now_ts()
            conn.execute("BEGIN IMMEDIATE")
            picks = conn.execute(
                "SELECT id, symbol, picked_date FROM sa_alpha_picks "
                "WHERE portfolio_status = 'current' AND is_stale = 0 "
                "AND canonical_article_id IS NULL "
                "AND detail_report IS NULL"
            ).fetchall()

            for pick in picks:
                pick_id, symbol, picked_date = pick["id"], pick["symbol"], pick["picked_date"]
                # exact/prefix ticker match first (analysis/removal only); PG's
                # ABS(published_date - %s::date) → julianday delta; PG's default
                # ASC NULLS LAST → explicit (… IS NULL) prefix.
                match = conn.execute(
                    "SELECT article_id, published_date FROM sa_articles "
                    "WHERE (ticker = ? OR (ticker LIKE ? AND LENGTH(ticker) <= LENGTH(?) * 2)) "
                    "AND article_type IN ('analysis', 'removal') "
                    "AND body_markdown IS NOT NULL "
                    "ORDER BY (published_date IS NULL), "
                    "ABS(julianday(published_date) - julianday(?)) "
                    "LIMIT 1",
                    (symbol, symbol + "%", symbol, picked_date),
                ).fetchone()

                if not match:
                    # v1 LIKE degradation of the PG full-text fallback (see docstring)
                    match = conn.execute(
                        "SELECT article_id, published_date FROM sa_articles "
                        "WHERE body_markdown IS NOT NULL "
                        "AND article_type IN ('analysis', 'removal') "
                        "AND (title LIKE ? OR body_markdown LIKE ?) "
                        "ORDER BY (published_date IS NULL), "
                        "ABS(julianday(published_date) - julianday(?)) "
                        "LIMIT 1",
                        (f"%{symbol}%", f"%{symbol}%", picked_date),
                    ).fetchone()

                if match:
                    art_id = match["article_id"]
                    body_row = conn.execute(
                        "SELECT body_markdown FROM sa_articles WHERE article_id = ?",
                        (art_id,),
                    ).fetchone()
                    if body_row and body_row["body_markdown"]:
                        conn.execute(
                            "UPDATE sa_alpha_picks SET detail_report = ?, "
                            "detail_fetched_at = ?, canonical_article_id = ?, "
                            "updated_at = ? WHERE id = ?",
                            (body_row["body_markdown"], now, art_id, now, pick_id),
                        )
                        resolved += 1
                        continue

                unresolved.append(symbol)

            conn.commit()
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            logger.error("audit_unresolved_symbols failed: %s", e)
            raise
        finally:
            conn.close()

        return {"unresolved_symbols": unresolved, "resolved_by_fulltext": resolved}

    def query_sa_articles(
        self,
        ticker: str = None,
        keyword: str = None,
        article_type: str = None,
        limit: int = 10,
    ) -> list:
        """Query SA articles with optional filters; keyword search runs against the
        trigger-maintained sa_articles_fts mirror (title + body_markdown, same
        corpus as the PG GIN expression index)."""
        conditions = []
        params: list = []
        if ticker:
            conditions.append("(ticker = ? OR ticker LIKE ?)")
            params.extend([ticker.upper(), ticker.upper() + "%"])
        if keyword:
            match = _fts_match(keyword)
            if not match:
                return []
            conditions.append(
                "sa_articles.id IN (SELECT rowid FROM sa_articles_fts "
                "WHERE sa_articles_fts MATCH ?)"
            )
            params.append(match)
        if article_type:
            conditions.append("article_type = ?")
            params.append(article_type)
        where = " AND ".join(conditions) if conditions else "1"
        params.append(int(limit))
        try:
            conn = self._sa_read()
        except Exception as e:
            logger.error("Failed to query SA articles: %s", e)
            return []
        try:
            rows = conn.execute(
                f"SELECT article_id, url, title, ticker, published_date, "
                f"article_type, comments_count, "
                f"CASE WHEN body_markdown IS NOT NULL THEN 1 ELSE 0 END AS has_content, "
                f"detail_fetched_at, comments_fetched_at, "
                f"(SELECT COUNT(*) FROM sa_article_comments c "
                f" WHERE c.article_id = sa_articles.article_id) AS stored_comments_count "
                f"FROM sa_articles WHERE {where} "
                f"ORDER BY (published_date IS NULL), published_date DESC "
                f"LIMIT ?",
                tuple(params),
            ).fetchall()
            out = []
            for r in rows:
                d = dict(r)
                d["has_content"] = bool(d["has_content"])  # PG boolean parity
                out.append(d)
            return out
        except Exception as e:
            logger.error("Failed to query SA articles: %s", e)
            return []
        finally:
            conn.close()

    def get_sa_article_with_comments(self, article_id: str) -> dict:
        """Full article + ordered comment list. raw_data is json.loads'd to match
        psycopg2's jsonb→dict; timestamps are canonical TEXT already (no
        .isoformat conversion needed)."""
        try:
            conn = self._sa_read()
        except Exception as e:
            logger.error("Failed to get SA article with comments: %s", e)
            return None
        try:
            article = conn.execute(
                "SELECT * FROM sa_articles WHERE article_id = ?",
                (article_id,),
            ).fetchone()
            if not article:
                return None
            comments = [dict(r) for r in conn.execute(
                "SELECT comment_id, parent_comment_id, commenter, "
                "comment_text, upvotes, comment_date "
                "FROM sa_article_comments WHERE article_id = ? "
                "ORDER BY (comment_date IS NULL), comment_date ASC",
                (article_id,),
            ).fetchall()]
            result = dict(article)
            result["comments"] = comments
            result["raw_data"] = _loads(result.get("raw_data"))
            return result
        except Exception as e:
            logger.error("Failed to get SA article with comments: %s", e)
            return None
        finally:
            conn.close()
