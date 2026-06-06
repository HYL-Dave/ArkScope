"""
Local user profile-state store (SQLite).

ArkScope keeps market / collection data in PostgreSQL (via the DAL), but the
user's *research-universe state* — which named lists exist, which tickers
belong to them, soft archive/restore, and free-text notes — is local-first and
lives here in a small standalone SQLite database. It is intentionally NOT a DAL
backend and NOT in the remote PG: the desktop app must manage the research
universe with no remote-DB dependency.

The substrate matches ProductSpec §168: watchlists are *multi-list tabs* with
many-to-many ticker membership and stable ordering. The v0 cockpit UI only
renders a single aggregate "All Active" view + an Archived filter, but the
schema already supports multiple named lists / tabs so that surface can grow
without a migration.

This is a thin store over stdlib ``sqlite3`` (no ORM). Every mutation reached
from the API funnels through the ``profile_state_write`` permission
choke-point (``src/api/permissions.py``) before it gets here.
"""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS watchlists (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    kind        TEXT NOT NULL DEFAULT 'custom',
    position    INTEGER NOT NULL DEFAULT 0,
    archived_at TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS watchlist_memberships (
    list_id     INTEGER NOT NULL REFERENCES watchlists(id) ON DELETE CASCADE,
    ticker      TEXT NOT NULL,
    position    INTEGER NOT NULL DEFAULT 0,
    archived_at TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    PRIMARY KEY (list_id, ticker)
);

CREATE INDEX IF NOT EXISTS idx_membership_ticker ON watchlist_memberships(ticker);

CREATE TABLE IF NOT EXISTS ticker_notes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker     TEXT NOT NULL,
    body       TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ticker_notes_ticker ON ticker_notes(ticker);
"""


def _now() -> str:
    """UTC ISO-8601 timestamp (seconds precision)."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _norm(ticker: str | None) -> str:
    return (ticker or "").strip().upper()


def _dedup_norm(tickers) -> list[str]:
    keys: list[str] = []
    for t in tickers:
        n = _norm(t)
        if n and n not in keys:
            keys.append(n)
    return keys


def _infer_kind(name: str) -> str:
    n = (name or "").lower()
    if "holding" in n:
        return "holdings"
    if "interest" in n:
        return "interested"
    if n.startswith("theme") or ":" in n:
        return "theme"
    return "custom"


@dataclass
class WatchlistSummary:
    id: int
    name: str
    kind: str
    position: int
    archived: bool
    active_count: int
    total_count: int


@dataclass
class TickerAggregate:
    """A ticker's roll-up across all lists, for the cockpit join.

    ``archived`` is True only when the ticker has memberships but none of them
    are active (membership-level soft archive); a ticker with no membership at
    all defaults to active.
    """

    ticker: str
    lists: list[str]
    list_ids: list[int]
    archived: bool
    note_count: int


@dataclass
class Note:
    id: int
    ticker: str
    body: str
    created_at: str
    updated_at: str


class ProfileStateStore:
    """Local SQLite store for multi-list watchlist membership and notes.

    A fresh connection is opened per operation (cheap for SQLite) so the store
    is safe to share across FastAPI's threadpool; writes are additionally
    serialized in-process by a lock to avoid ``database is locked`` under the
    occasional concurrent write.
    """

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._write_lock = threading.Lock()
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _ensure_schema(self) -> None:
        with self._write_lock, self._connect() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.executescript(_SCHEMA)
            conn.commit()

    # --- universe import (EXPLICIT — never run from a read path) ---------

    def import_lists(self, named_lists) -> dict:
        """Additive, archive-preserving seed of named lists + memberships.

        ``named_lists`` is an iterable of mappings ``{"name", "kind"?, "tickers"}``.
        A ticker may appear in several lists (duplicate membership is allowed by
        design). Idempotent: missing lists/memberships are created, but the
        ``archived_at`` of an existing membership is NEVER touched, so user
        archives survive re-imports. Returns a ``{lists_created, memberships_added}``
        summary.

        This is the EXPLICIT importer — it must only be called from a gated
        write action (bootstrap / re-import), never from a read endpoint.
        """
        now = _now()
        lists_created = 0
        memberships_added = 0
        with self._write_lock, self._connect() as conn:
            lists = {r["name"]: r["id"] for r in conn.execute("SELECT id, name FROM watchlists")}
            max_pos = conn.execute(
                "SELECT COALESCE(MAX(position), -1) AS p FROM watchlists"
            ).fetchone()["p"]
            for spec in named_lists:
                name = (spec.get("name") or "").strip()
                if not name:
                    continue
                kind = spec.get("kind") or _infer_kind(name)
                if name not in lists:
                    max_pos += 1
                    cur = conn.execute(
                        "INSERT INTO watchlists (name, kind, position, created_at, updated_at) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (name, kind, max_pos, now, now),
                    )
                    lists[name] = cur.lastrowid
                    lists_created += 1
                list_id = lists[name]
                for t in _dedup_norm(spec.get("tickers") or []):
                    exists = conn.execute(
                        "SELECT 1 FROM watchlist_memberships WHERE list_id = ? AND ticker = ?",
                        (list_id, t),
                    ).fetchone()
                    if exists:
                        continue
                    pos = conn.execute(
                        "SELECT COALESCE(MAX(position), -1) + 1 AS p "
                        "FROM watchlist_memberships WHERE list_id = ?",
                        (list_id,),
                    ).fetchone()["p"]
                    conn.execute(
                        "INSERT INTO watchlist_memberships "
                        "(list_id, ticker, position, created_at, updated_at) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (list_id, t, pos, now, now),
                    )
                    memberships_added += 1
            conn.commit()
        return {"lists_created": lists_created, "memberships_added": memberships_added}

    def sync_universe(self, rows) -> dict:
        """Seed one list per ``group`` from overview-shaped rows (delegates to
        :meth:`import_lists`). Kept for the overview-groups import source.

        ``rows`` is any iterable of mappings with ``ticker`` and ``group`` keys.
        Additive / archive-preserving (see ``import_lists``).
        """
        by_group: dict[str, list[str]] = {}
        for r in rows:
            group = (r.get("group") or "Watchlist").strip() or "Watchlist"
            ticker = _norm(r.get("ticker"))
            if ticker:
                by_group.setdefault(group, []).append(ticker)
        named = [{"name": g, "tickers": ts} for g, ts in by_group.items()]
        return self.import_lists(named)

    # --- reads -----------------------------------------------------------

    def list_watchlists(self, include_archived: bool = False) -> list[WatchlistSummary]:
        where = "" if include_archived else "WHERE w.archived_at IS NULL"
        sql = f"""
            SELECT w.id, w.name, w.kind, w.position, w.archived_at,
                   SUM(CASE WHEN m.ticker IS NOT NULL AND m.archived_at IS NULL
                            THEN 1 ELSE 0 END) AS active_count,
                   SUM(CASE WHEN m.ticker IS NOT NULL THEN 1 ELSE 0 END) AS total_count
            FROM watchlists w
            LEFT JOIN watchlist_memberships m ON m.list_id = w.id
            {where}
            GROUP BY w.id, w.name, w.kind, w.position, w.archived_at
            ORDER BY w.position, w.id
        """
        with self._connect() as conn:
            rows = conn.execute(sql).fetchall()
        return [
            WatchlistSummary(
                id=r["id"],
                name=r["name"],
                kind=r["kind"],
                position=r["position"],
                archived=r["archived_at"] is not None,
                active_count=int(r["active_count"] or 0),
                total_count=int(r["total_count"] or 0),
            )
            for r in rows
        ]

    def get_aggregate(self, tickers) -> dict[str, TickerAggregate]:
        """Per-ticker roll-up (active lists + archived flag + note count).

        Always returns an entry for every normalized ticker in ``tickers``
        (defaults to active / no-list / 0-notes for unknown tickers).
        """
        keys = _dedup_norm(tickers)
        if not keys:
            return {}
        ph = ",".join("?" * len(keys))
        with self._connect() as conn:
            mem_rows = conn.execute(
                f"""
                SELECT m.ticker, m.list_id, w.name AS list_name,
                       m.archived_at, w.archived_at AS list_archived_at
                FROM watchlist_memberships m
                JOIN watchlists w ON w.id = m.list_id
                WHERE m.ticker IN ({ph})
                """,
                keys,
            ).fetchall()
            note_counts = {
                r["ticker"]: r["n"]
                for r in conn.execute(
                    f"SELECT ticker, COUNT(*) AS n FROM ticker_notes "
                    f"WHERE ticker IN ({ph}) GROUP BY ticker",
                    keys,
                )
            }

        by_ticker: dict[str, list] = {}
        for r in mem_rows:
            by_ticker.setdefault(r["ticker"], []).append(r)

        out: dict[str, TickerAggregate] = {}
        for t in keys:
            ms = by_ticker.get(t, [])
            active = [
                m for m in ms if m["archived_at"] is None and m["list_archived_at"] is None
            ]
            out[t] = TickerAggregate(
                ticker=t,
                lists=[m["list_name"] for m in active],
                list_ids=[m["list_id"] for m in active],
                archived=bool(ms) and not active,
                note_count=note_counts.get(t, 0),
            )
        return out

    def get_ticker(self, ticker: str) -> TickerAggregate:
        t = _norm(ticker)
        return self.get_aggregate([t]).get(t, TickerAggregate(t, [], [], False, 0))

    def list_notes(self, ticker: str) -> list[Note]:
        t = _norm(ticker)
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM ticker_notes WHERE ticker = ? "
                "ORDER BY created_at DESC, id DESC",
                (t,),
            ).fetchall()
        return [
            Note(
                id=r["id"],
                ticker=r["ticker"],
                body=r["body"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )
            for r in rows
        ]

    # --- writes ----------------------------------------------------------

    def archive_ticker(self, ticker: str) -> TickerAggregate:
        """Soft-archive a ticker: mark all its active memberships archived."""
        t = _norm(ticker)
        if not t:
            raise ValueError("ticker is required")
        now = _now()
        with self._write_lock, self._connect() as conn:
            exists = conn.execute(
                "SELECT 1 FROM watchlist_memberships WHERE ticker = ? LIMIT 1",
                (t,),
            ).fetchone()
            if not exists:
                raise KeyError(f"{t} is not in any watchlist")
            conn.execute(
                "UPDATE watchlist_memberships SET archived_at = ?, updated_at = ? "
                "WHERE ticker = ? AND archived_at IS NULL",
                (now, now, t),
            )
            conn.commit()
        return self.get_ticker(t)

    def restore_ticker(self, ticker: str) -> TickerAggregate:
        """Restore a ticker: clear archived_at on all its archived memberships."""
        t = _norm(ticker)
        if not t:
            raise ValueError("ticker is required")
        now = _now()
        with self._write_lock, self._connect() as conn:
            exists = conn.execute(
                "SELECT 1 FROM watchlist_memberships WHERE ticker = ? LIMIT 1",
                (t,),
            ).fetchone()
            if not exists:
                raise KeyError(f"{t} is not in any watchlist")
            conn.execute(
                "UPDATE watchlist_memberships SET archived_at = NULL, updated_at = ? "
                "WHERE ticker = ? AND archived_at IS NOT NULL",
                (now, t),
            )
            conn.commit()
        return self.get_ticker(t)

    def add_note(self, ticker: str, body: str) -> Note:
        t = _norm(ticker)
        text = (body or "").strip()
        if not t:
            raise ValueError("ticker is required")
        if not text:
            raise ValueError("note body is required")
        now = _now()
        with self._write_lock, self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO ticker_notes (ticker, body, created_at, updated_at) "
                "VALUES (?, ?, ?, ?)",
                (t, text, now, now),
            )
            conn.commit()
            note_id = cur.lastrowid
        return Note(id=note_id, ticker=t, body=text, created_at=now, updated_at=now)

    def delete_note(self, ticker: str, note_id: int) -> bool:
        t = _norm(ticker)
        with self._write_lock, self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM ticker_notes WHERE id = ? AND ticker = ?",
                (note_id, t),
            )
            conn.commit()
        return cur.rowcount > 0
