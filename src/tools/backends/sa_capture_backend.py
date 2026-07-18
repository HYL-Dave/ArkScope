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
from ... import sa_article_reconciliation_store as reconciliation_store
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

_COMMENT_SCAN_MODES = frozenset({"quick", "full", "backfill"})
_COMMENT_TERMINAL_STOP_REASON = "stable_bottom"
_COMMENT_TERMINAL_BOTTOM_ROUNDS = 5
_COMMENT_FULL_MISS_LIMIT = 2
_COMMENT_TERMINAL_REASON = "provider_bottom_unbridged"


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


def _provider_comment_count(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _comment_scan_usable(
    prepared_count: int, provider_count: Optional[int]
) -> bool:
    return prepared_count > 0 or provider_count == 0


def _comment_scan_mode(value: Any) -> str:
    return value if value in _COMMENT_SCAN_MODES else "quick"


def _stable_bottom_rounds(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return max(value, 0)


class SACaptureDatabaseBackend(LocalMarketDatabaseBackend):
    """DatabaseBackend whose SA domain lives in data/sa_capture.db (hard cutover)."""

    def __init__(self, dsn: str, sslmode: str = "prefer", *, sa_db: str,
                 market_db: str = "", strict: bool = False, news_strict: bool = False):
        # DatabaseBackend connects lazily (_get_conn), so constructing this with a
        # dead/fake PG DSN must not touch the network. ``strict`` threads to the market
        # overrides (local-only, no PG fallback); SA reads are already hard-local.
        super().__init__(
            dsn, sslmode, market_db=market_db, strict=strict, news_strict=news_strict
        )
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
            normalized_picks = []
            for pick in picks:
                symbol = str(pick.get("symbol") or "").strip().upper()
                picked_date = store.canon_date(pick.get("picked_date"))
                if not symbol or not picked_date:
                    raise ValueError("Alpha Picks refresh requires symbol and picked_date")
                normalized_picks.append((pick, symbol, picked_date))
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
                "lineage_id = excluded.lineage_id, "
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
                "(lineage_id, symbol, company, picked_date, closed_date, portfolio_status, "
                " is_stale, return_pct, sector, sa_rating, holding_pct, "
                " raw_data, last_seen_snapshot, fetched_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?) " + conflict_clause
            )
            count = 0
            for pick, symbol, picked_date in normalized_picks:
                lineage_id = reconciliation_store.resolve_lineage(
                    conn,
                    symbol=symbol,
                    picked_date=picked_date,
                )
                conn.execute(
                    sql,
                    (
                        lineage_id,
                        symbol,
                        pick.get("company", ""),
                        picked_date,
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
            d.pop("lineage_id", None)  # internal reconciliation identity, not legacy DTO
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
                     article_type, comments_count, raw_data, fetched_at, updated_at,
                     list_ticker, list_ticker_observed_at,
                     comments_count_observed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (article_id) DO UPDATE SET
                        title = excluded.title,
                        url = excluded.url,
                        ticker = COALESCE(excluded.ticker, sa_articles.ticker),
                        published_date = COALESCE(excluded.published_date, sa_articles.published_date),
                        article_type = COALESCE(excluded.article_type, sa_articles.article_type),
                        comments_count = CASE
                          WHEN excluded.comments_count_observed_at IS NOT NULL
                            THEN excluded.comments_count
                          ELSE sa_articles.comments_count
                        END,
                        comments_count_observed_at = COALESCE(
                            excluded.comments_count_observed_at,
                            sa_articles.comments_count_observed_at
                        ),
                        list_ticker = COALESCE(excluded.list_ticker, sa_articles.list_ticker),
                        list_ticker_observed_at = COALESCE(
                            excluded.list_ticker_observed_at,
                            sa_articles.list_ticker_observed_at
                        ),
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
                        a.get("list_ticker"),
                        store.canon_ts(a.get("list_ticker_observed_at")),
                        store.canon_ts(a.get("comments_count_observed_at")),
                        now,  # updated_at (DO UPDATE)
                    ),
                )
                conn.execute(
                    """UPDATE sa_articles
                    SET ticker = CASE
                      WHEN list_ticker IS NOT NULL AND detail_ticker IS NOT NULL
                           AND UPPER(TRIM(list_ticker)) = UPPER(TRIM(detail_ticker))
                        THEN UPPER(TRIM(list_ticker))
                      WHEN list_ticker IS NOT NULL AND detail_ticker IS NULL
                        THEN UPPER(TRIM(list_ticker))
                      WHEN detail_ticker IS NOT NULL AND list_ticker IS NULL
                        THEN UPPER(TRIM(detail_ticker))
                      ELSE ticker
                    END
                    WHERE article_id = ?
                    """,
                    (a.get("article_id"),),
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
            "SELECT id, comment_id, parent_comment_id, commenter, comment_text, "
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
        self,
        conn: sqlite3.Connection,
        article_id: str,
        prepared_comments: List[Dict[str, Any]],
    ) -> int:
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

    @staticmethod
    def _comment_recovery_transition(
        article: Dict[str, Any],
        *,
        usable: bool,
        provider_count: Optional[int],
        mode: str,
        stop_reason: Any,
        stable_bottom_rounds: int,
        had_existing_rows: bool,
        existing_overlap_count: int,
        baseline_overlap_count: int,
        pre_upsert_max_row_id: Optional[int],
        now: str,
    ) -> Dict[str, Any]:
        state = str(article.get("comment_recovery_state") or "repaired")
        started_at = article.get("comment_recovery_started_at")
        baseline_max_row_id = article.get("comment_recovery_baseline_max_row_id")
        full_misses = int(article.get("comment_recovery_full_miss_count") or 0)
        parked_at = article.get("comment_recovery_parked_at")
        last_terminal_at = article.get("comment_recovery_last_terminal_at")
        last_terminal_reason = article.get("comment_recovery_last_terminal_reason")

        if not usable:
            return {
                "state": state,
                "started_at": started_at,
                "baseline_max_row_id": baseline_max_row_id,
                "full_misses": full_misses,
                "parked_at": parked_at,
                "last_terminal_at": last_terminal_at,
                "last_terminal_reason": last_terminal_reason,
            }

        terminal_evidence = (
            mode == "backfill"
            and stop_reason == _COMMENT_TERMINAL_STOP_REASON
            and stable_bottom_rounds >= _COMMENT_TERMINAL_BOTTOM_ROUNDS
        )

        if provider_count == 0:
            state = "repaired"
            started_at = None
            baseline_max_row_id = None
            full_misses = 0
            parked_at = None
        elif state == "pending":
            if baseline_overlap_count:
                state = "repaired"
                started_at = None
                baseline_max_row_id = None
                full_misses = 0
                parked_at = None
            elif terminal_evidence:
                state = "unreachable_terminal"
                started_at = None
                baseline_max_row_id = None
                full_misses = 0
                parked_at = None
                last_terminal_at = now
                last_terminal_reason = _COMMENT_TERMINAL_REASON
            elif mode == "full":
                full_misses = min(full_misses + 1, _COMMENT_FULL_MISS_LIMIT)
                if full_misses >= _COMMENT_FULL_MISS_LIMIT and parked_at is None:
                    parked_at = now
        else:
            previous_count = _provider_comment_count(
                article.get("provider_comments_count_at_last_scan")
            )
            count_changed = (
                provider_count is not None and provider_count != previous_count
            )
            if state != "unreachable_terminal" or count_changed:
                if count_changed and had_existing_rows and not existing_overlap_count:
                    state = "pending"
                    started_at = now
                    baseline_max_row_id = pre_upsert_max_row_id
                    full_misses = 1 if mode == "full" else 0
                    parked_at = None
                    if terminal_evidence:
                        state = "unreachable_terminal"
                        started_at = None
                        baseline_max_row_id = None
                        full_misses = 0
                        last_terminal_at = now
                        last_terminal_reason = _COMMENT_TERMINAL_REASON
                elif count_changed:
                    state = "repaired"
                    started_at = None
                    baseline_max_row_id = None
                    full_misses = 0
                    parked_at = None

        return {
            "state": state,
            "started_at": started_at,
            "baseline_max_row_id": baseline_max_row_id,
            "full_misses": full_misses,
            "parked_at": parked_at,
            "last_terminal_at": last_terminal_at,
            "last_terminal_reason": last_terminal_reason,
        }

    def _capture_comment_scan(
        self,
        conn: sqlite3.Connection,
        article_id: str,
        comments: list,
        *,
        provider_comments_count: Any,
        comment_scan_mode: Any,
        comment_scan_stop_reason: Any,
        comment_scan_stable_bottom_rounds: Any,
        now: str,
    ) -> Dict[str, Any]:
        article_row = conn.execute(
            "SELECT comments_fetched_at, provider_comments_count_at_last_scan, "
            "comment_recovery_state, comment_recovery_started_at, "
            "comment_recovery_baseline_max_row_id, "
            "comment_recovery_full_miss_count, comment_recovery_parked_at, "
            "comment_recovery_last_terminal_at, "
            "comment_recovery_last_terminal_reason "
            "FROM sa_articles WHERE article_id = ?",
            (article_id,),
        ).fetchone()
        if article_row is None:
            raise ValueError(f"unknown SA article: {article_id}")
        article = dict(article_row)

        existing_rows = self._fetch_existing_article_comments(conn, article_id)
        prepared_comments = _prepare_comments_for_upsert(existing_rows, comments)
        existing_by_comment_id = {
            row["comment_id"]: row
            for row in existing_rows
            if row.get("comment_id")
        }
        prepared_ids = {
            row["comment_id"]
            for row in prepared_comments
            if row.get("comment_id")
        }
        existing_overlap_ids = prepared_ids & existing_by_comment_id.keys()
        pre_upsert_max_row_id = max(
            (int(row["id"]) for row in existing_rows), default=None
        )
        baseline_overlap_ids: set[str] = set()
        frozen_watermark = article.get("comment_recovery_baseline_max_row_id")
        if article.get("comment_recovery_state") == "pending" and frozen_watermark is not None:
            baseline_overlap_ids = {
                comment_id
                for comment_id in existing_overlap_ids
                if int(existing_by_comment_id[comment_id]["id"])
                <= int(frozen_watermark)
            }

        if existing_rows and prepared_ids and not existing_overlap_ids:
            logger.warning(
                "SA comment identity overlap dropped to zero for article %s",
                article_id,
            )

        before_count = len(existing_rows)
        prepared_count = self._upsert_article_comments(
            conn, article_id, prepared_comments
        )
        after_count = self._count_article_comments(conn, article_id)
        provider_count = _provider_comment_count(provider_comments_count)
        mode = _comment_scan_mode(comment_scan_mode)
        stable_bottom_rounds = _stable_bottom_rounds(
            comment_scan_stable_bottom_rounds
        )
        usable = _comment_scan_usable(prepared_count, provider_count)
        transition = self._comment_recovery_transition(
            article,
            usable=usable,
            provider_count=provider_count,
            mode=mode,
            stop_reason=comment_scan_stop_reason,
            stable_bottom_rounds=stable_bottom_rounds,
            had_existing_rows=bool(existing_rows),
            existing_overlap_count=len(existing_overlap_ids),
            baseline_overlap_count=len(baseline_overlap_ids),
            pre_upsert_max_row_id=pre_upsert_max_row_id,
            now=now,
        )

        if usable:
            checkpoint = (
                provider_count
                if provider_count is not None
                else article.get("provider_comments_count_at_last_scan")
            )
            conn.execute(
                "UPDATE sa_articles SET comments_fetched_at = ?, "
                "provider_comments_count_at_last_scan = ?, "
                "comment_recovery_state = ?, comment_recovery_started_at = ?, "
                "comment_recovery_baseline_max_row_id = ?, "
                "comment_recovery_full_miss_count = ?, "
                "comment_recovery_parked_at = ?, "
                "comment_recovery_last_terminal_at = ?, "
                "comment_recovery_last_terminal_reason = ?, updated_at = ? "
                "WHERE article_id = ?",
                (
                    now,
                    checkpoint,
                    transition["state"],
                    transition["started_at"],
                    transition["baseline_max_row_id"],
                    transition["full_misses"],
                    transition["parked_at"],
                    transition["last_terminal_at"],
                    transition["last_terminal_reason"],
                    now,
                    article_id,
                ),
            )

        return {
            "prepared_comments": prepared_count,
            "stored_comments_total": after_count,
            "net_new_comments": max(after_count - before_count, 0),
            "comment_scan_usable": usable,
            "comment_scan_existing_overlap_count": len(existing_overlap_ids),
            "comment_scan_baseline_overlap_count": len(baseline_overlap_ids),
            "comment_scan_identity_overlap_rate": (
                len(existing_overlap_ids) / len(prepared_ids)
                if prepared_ids
                else 0.0
            ),
            "comment_recovery_state": transition["state"],
            "comment_recovery_full_miss_count": transition["full_misses"],
            "comment_recovery_parked": transition["parked_at"] is not None,
            "comment_recovery_last_terminal_at": transition["last_terminal_at"],
            "comment_recovery_last_terminal_reason": transition[
                "last_terminal_reason"
            ],
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
        """Capture article content, detail ticker evidence, and comments atomically."""
        conn = self._sa_conn()
        try:
            now = store.now_ts()
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "UPDATE sa_articles SET body_markdown = ?, "
                "detail_fetched_at = ?, "
                "detail_ticker = COALESCE(?, detail_ticker), "
                "detail_ticker_observed_at = COALESCE(?, detail_ticker_observed_at), "
                "updated_at = ? WHERE article_id = ?",
                (
                    body_markdown,
                    now,
                    detail_ticker,
                    store.canon_ts(detail_ticker_observed_at),
                    now,
                    article_id,
                ),
            )
            conn.execute(
                """UPDATE sa_articles
                SET ticker = CASE
                  WHEN list_ticker IS NOT NULL AND detail_ticker IS NOT NULL
                       AND UPPER(TRIM(list_ticker)) = UPPER(TRIM(detail_ticker))
                    THEN UPPER(TRIM(list_ticker))
                  WHEN list_ticker IS NOT NULL AND detail_ticker IS NULL
                    THEN UPPER(TRIM(list_ticker))
                  WHEN detail_ticker IS NOT NULL AND list_ticker IS NULL
                    THEN UPPER(TRIM(detail_ticker)
                    )
                  ELSE ticker
                END
                WHERE article_id = ?
                """,
                (article_id,),
            )
            scan = self._capture_comment_scan(
                conn,
                article_id,
                comments,
                provider_comments_count=provider_comments_count,
                comment_scan_mode=comment_scan_mode,
                comment_scan_stop_reason=comment_scan_stop_reason,
                comment_scan_stable_bottom_rounds=comment_scan_stable_bottom_rounds,
                now=now,
            )
            conn.commit()
            return {"ok": True, **scan}
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            logger.error("save_article_with_comments failed: %s", e)
            raise
        finally:
            conn.close()

    def update_article_comments(
        self,
        article_id: str,
        comments: list,
        *,
        provider_comments_count=None,
        comment_scan_mode="quick",
        comment_scan_stop_reason=None,
        comment_scan_stable_bottom_rounds=0,
    ) -> Dict[str, Any]:
        """Comments-only update (refresh runs). Returns refresh stats."""
        conn = self._sa_conn()
        try:
            now = store.now_ts()
            conn.execute("BEGIN IMMEDIATE")
            result = self._capture_comment_scan(
                conn,
                article_id,
                comments,
                provider_comments_count=provider_comments_count,
                comment_scan_mode=comment_scan_mode,
                comment_scan_stop_reason=comment_scan_stop_reason,
                comment_scan_stable_bottom_rounds=comment_scan_stable_bottom_rounds,
                now=now,
            )
            conn.commit()
            return result
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            logger.error("update_article_comments failed: %s", e)
            raise
        finally:
            conn.close()

    def audit_unresolved_symbols(self) -> dict:
        """Compatibility alias for the read-only event-scoped review queue."""
        queue = self.query_sa_article_review_queue(limit=200)
        return {
            "unresolved_symbols": sorted({
                event["symbol"] for event in queue["events"]
            }),
            "resolved_by_fulltext": 0,
            "review_queue": queue,
        }

    def reconcile_sa_articles(
        self,
        *,
        pick_keys=None,
        article_ids=None,
        max_events: int = reconciliation_store.MAX_EVENTS_PER_RECONCILIATION,
        enrichment_limit: int = 4,
    ) -> dict:
        conn = self._sa_conn()
        try:
            lineage_ids = None
            if pick_keys is not None:
                lineage_ids = []
                for symbol, picked_date in pick_keys:
                    symbol_key = str(symbol or "").strip().upper()
                    canonical_date = store.canon_date(picked_date)
                    if not symbol_key or not canonical_date:
                        continue
                    row = conn.execute(
                        "SELECT lineage_id FROM sa_pick_lineages "
                        "WHERE symbol_key=? AND picked_date=?",
                        (symbol_key, canonical_date),
                    ).fetchone()
                    if row is not None:
                        lineage_ids.append(int(row[0]))
            return reconciliation_store.reconcile_events(
                conn,
                lineage_ids=lineage_ids,
                article_ids=article_ids,
                max_events=max_events,
                enrichment_limit=enrichment_limit,
            )
        finally:
            conn.close()

    def query_sa_article_review_queue(self, limit: int = 50) -> dict:
        conn = self._sa_conn()
        try:
            return reconciliation_store.list_review_queue(conn, limit=limit)
        finally:
            conn.close()

    def resolve_sa_reconciliation_event(
        self,
        *,
        symbol: str,
        role: str,
        event_anchor_date: str,
    ) -> dict:
        conn = self._sa_conn()
        try:
            return reconciliation_store.resolve_event(
                conn,
                symbol=symbol,
                role=role,
                event_anchor_date=event_anchor_date,
            )
        finally:
            conn.close()

    def accept_sa_article_link(self, **kwargs) -> dict:
        conn = self._sa_conn()
        try:
            return reconciliation_store.accept_link(conn, **kwargs)
        finally:
            conn.close()

    def reject_sa_article_candidate(self, **kwargs) -> dict:
        conn = self._sa_conn()
        try:
            return reconciliation_store.reject_candidate(conn, **kwargs)
        finally:
            conn.close()

    def preview_sa_legacy_article_links(self, limit: int = 200) -> dict:
        conn = self._sa_conn()
        try:
            return reconciliation_store.preview_legacy_links(conn, limit=limit)
        finally:
            conn.close()

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
                f"detail_fetched_at, comments_fetched_at, comments_count_observed_at, "
                f"provider_comments_count_at_last_scan, comment_recovery_state, "
                f"comment_recovery_started_at, "
                f"comment_recovery_baseline_max_row_id, "
                f"comment_recovery_full_miss_count, comment_recovery_parked_at, "
                f"comment_recovery_last_terminal_at, "
                f"comment_recovery_last_terminal_reason, "
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
