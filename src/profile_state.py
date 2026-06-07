"""
Local user profile-state store (SQLite).

ArkScope keeps market / collection data in PostgreSQL (via the DAL), but the
user's *research-universe state* — which named lists exist, which tickers
belong to them, soft archive/restore, free-text notes, per-ticker priority,
and classification tags — is local-first and lives here in a small standalone
SQLite database. It is intentionally NOT a DAL backend and NOT in the remote
PG: the desktop app must manage the research universe with no remote-DB
dependency.

The substrate (ProductSpec §168) has two decoupled axes:
  - **lists** — the user's work-lists (``watchlists`` + ``watchlist_memberships``,
    many-to-many, soft-archivable). The 自選股 rail and the 全部標的 list filter
    both render the ``custom``-kind lists; classification is NOT a list.
  - **tags** — two-dimensional classification (``ticker_tags``: facet × source),
    decoupled from membership: a ticker keeps its tags whether or not it sits in
    any list. ``user``/``legacy`` tags are editable; ``system``/``provider``/
    ``sec``/``broker`` are read-only external facts.
Plus ``ticker_meta`` (priority), ``ticker_notes``, and ``profile_settings``.

This is a thin store over stdlib ``sqlite3`` (no ORM). Every mutation reached
from the API funnels through the ``profile_state_write`` permission
choke-point (``src/api/permissions.py``) before it gets here.
"""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

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

CREATE TABLE IF NOT EXISTS ticker_meta (
    ticker     TEXT PRIMARY KEY,
    priority   TEXT,
    hidden_at  TEXT,
    updated_at TEXT NOT NULL
);

-- Classification tags, two-dimensional (facet × source), decoupled from list
-- membership. facet = semantic axis (category|theme|provenance|sector|industry);
-- source = authority/origin (user|legacy|system|provider:*|sec|broker), which
-- also determines editability (user/legacy editable; the rest read-only facts).
CREATE TABLE IF NOT EXISTS ticker_tags (
    ticker     TEXT NOT NULL,
    facet      TEXT NOT NULL,
    value      TEXT NOT NULL,
    source     TEXT NOT NULL DEFAULT 'user',
    created_at TEXT NOT NULL,
    PRIMARY KEY (ticker, facet, value, source)
);

CREATE INDEX IF NOT EXISTS idx_ticker_tags_ticker ON ticker_tags(ticker);
CREATE INDEX IF NOT EXISTS idx_ticker_tags_facet ON ticker_tags(facet);

-- Small key/value bag for app-managed profile settings (e.g. default watchlist).
CREATE TABLE IF NOT EXISTS profile_settings (
    key        TEXT PRIMARY KEY,
    value      TEXT,
    updated_at TEXT NOT NULL
);
"""

_PRIORITIES = ("high", "medium", "low")

# source families a user may edit/remove via the API; the rest are read-only
# facts owned by import/providers.
EDITABLE_TAG_SOURCES = ("user", "legacy")


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

    ``lists`` / ``list_ids`` are the ACTIVE memberships (back-compat). The
    membership read-model distinguishes them from archived ones so an archived
    ticker doesn't lose its list provenance (needed for archived management and
    the future "remove from THIS list" vs "global archive" distinction):
      - ``archived_lists`` — list names where the membership exists but is
        archived (membership archived OR its list archived).
      - ``all_lists`` — every list the ticker belongs to (active + archived).
    """

    ticker: str
    lists: list[str]
    list_ids: list[int]
    archived: bool
    note_count: int
    all_lists: list[str] = field(default_factory=list)
    archived_lists: list[str] = field(default_factory=list)


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

    # Class-level lock serializing schema setup across CONCURRENT first
    # construction. ``get_profile_store`` is lru_cache'd, but lru_cache does not
    # hold its lock during the factory call, so a burst of first requests builds
    # several instances at once — each with its own ``_write_lock``. Without a
    # shared lock, one instance's tag migration (table briefly without ``facet``)
    # races another's ``CREATE INDEX … (facet)`` → "no such column: facet". A
    # class-level lock makes the migration + index creation atomic.
    _schema_lock = threading.Lock()

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._write_lock = threading.Lock()
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 5000")  # wait out brief write locks
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _ensure_schema(self) -> None:
        with self._schema_lock, self._write_lock, self._connect() as conn:
            # WAL best-effort: it errors immediately if another connection is open
            # (concurrent first-construction via lru_cache cache-miss); skip on fail.
            try:
                conn.execute("PRAGMA journal_mode = WAL")
            except sqlite3.OperationalError:
                pass
            # Migrate the old ticker_tags shape FIRST: _SCHEMA's facet index would
            # otherwise error against a pre-existing v1 table (no facet column).
            self._migrate_tags_v2(conn)
            conn.executescript(_SCHEMA)
            # Idempotent column add for a pre-existing ticker_meta (universe
            # suppression). CREATE TABLE IF NOT EXISTS above won't alter it.
            cols = {r[1] for r in conn.execute("PRAGMA table_info(ticker_meta)").fetchall()}
            if "hidden_at" not in cols:
                try:
                    conn.execute("ALTER TABLE ticker_meta ADD COLUMN hidden_at TEXT")
                except sqlite3.OperationalError:
                    pass
            # Provenance is user-editable (lifecycle: added → closed), so a
            # previously-seeded read-only 'system' provenance becomes editable
            # 'legacy'. Idempotent (0 rows after the first run); read-only
            # 'system' is reserved for a future authoritative crawl pipeline.
            conn.execute(
                "UPDATE OR IGNORE ticker_tags SET source = 'legacy' "
                "WHERE facet = 'provenance' AND source = 'system'"
            )
            conn.execute(
                "DELETE FROM ticker_tags WHERE facet = 'provenance' AND source = 'system'"
            )
            conn.commit()

    @staticmethod
    def _migrate_tags_v2(conn) -> None:
        """Migrate a v1 ``ticker_tags(ticker, tag, source)`` table to the
        two-dimensional ``(ticker, facet, value, source)`` model.

        Only USER tags are preserved (``user`` → ``user`` on the ``theme`` facet) —
        they are the one irreplaceable thing. All ``config:*`` rows are DROPPED:
        they were a crude bootstrap artifact (e.g. category "Seeking Picks
        Industrials") and ``import-universe`` re-seeds the proper model
        (``legacy:category`` + ``provenance`` + ``legacy:theme``) cleanly, so
        keeping the old ones would double-tag. The local DB is gitignored and the
        config classification is fully regenerable. Idempotent: a no-op once v2.
        """
        cols = {r[1] for r in conn.execute("PRAGMA table_info(ticker_tags)").fetchall()}
        if "tag" not in cols or "facet" in cols:
            return  # already v2 (or freshly created with the new schema)
        try:
            conn.execute("DROP TABLE IF EXISTS ticker_tags__v2")  # clean any prior partial
            conn.execute(
                """
                CREATE TABLE ticker_tags__v2 (
                    ticker     TEXT NOT NULL,
                    facet      TEXT NOT NULL,
                    value      TEXT NOT NULL,
                    source     TEXT NOT NULL DEFAULT 'user',
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (ticker, facet, value, source)
                )
                """
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO ticker_tags__v2 (ticker, facet, value, source, created_at)
                SELECT ticker, 'theme', tag, source, created_at
                FROM ticker_tags
                WHERE source NOT LIKE 'config:%'
                """
            )
            conn.execute("DROP TABLE ticker_tags")
            conn.execute("ALTER TABLE ticker_tags__v2 RENAME TO ticker_tags")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ticker_tags_ticker ON ticker_tags(ticker)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ticker_tags_facet ON ticker_tags(facet)")
        except sqlite3.OperationalError:
            # Another constructor won the race (concurrent first-construction);
            # the table is already migrated. Clean up our scratch table if left.
            try:
                conn.execute("DROP TABLE IF EXISTS ticker_tags__v2")
            except sqlite3.OperationalError:
                pass

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
            archived = [
                m for m in ms if m["archived_at"] is not None or m["list_archived_at"] is not None
            ]
            # all_lists: every list the ticker belongs to, de-duplicated, active first.
            seen: set[str] = set()
            all_lists: list[str] = []
            for m in [*active, *archived]:
                if m["list_name"] not in seen:
                    seen.add(m["list_name"])
                    all_lists.append(m["list_name"])
            out[t] = TickerAggregate(
                ticker=t,
                lists=[m["list_name"] for m in active],
                list_ids=[m["list_id"] for m in active],
                archived=bool(ms) and not active,
                note_count=note_counts.get(t, 0),
                all_lists=all_lists,
                archived_lists=[m["list_name"] for m in archived],
            )
        return out

    def get_ticker(self, ticker: str) -> TickerAggregate:
        t = _norm(ticker)
        return self.get_aggregate([t]).get(t, TickerAggregate(t, [], [], False, 0))

    def all_tickers(self) -> list[str]:
        """Distinct tickers across all list memberships (the imported universe).

        Includes archived members; the caller filters via ``get_aggregate``.
        """
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT ticker FROM watchlist_memberships ORDER BY ticker"
            ).fetchall()
        return [r["ticker"] for r in rows]

    def get_priorities(self, tickers) -> dict[str, str]:
        """User-set priority per ticker (only those with one). Overrides any
        profile-derived priority in the cockpit/universe DTOs."""
        keys = _dedup_norm(tickers)
        if not keys:
            return {}
        ph = ",".join("?" * len(keys))
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT ticker, priority FROM ticker_meta "
                f"WHERE ticker IN ({ph}) AND priority IS NOT NULL",
                keys,
            ).fetchall()
        return {r["ticker"]: r["priority"] for r in rows}

    def set_priority(self, ticker: str, priority: Optional[str]) -> None:
        """Set (or clear, with None) a ticker's user priority. high|medium|low."""
        t = _norm(ticker)
        if not t:
            raise ValueError("ticker is required")
        if priority is not None and priority not in _PRIORITIES:
            raise ValueError(f"invalid priority: {priority}")
        now = _now()
        with self._write_lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO ticker_meta (ticker, priority, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(ticker) DO UPDATE SET priority = excluded.priority, "
                "updated_at = excluded.updated_at",
                (t, priority, now),
            )
            conn.commit()

    # --- universe suppression (hide a tracked ticker from 全部標的) ----------

    def set_universe_hidden(self, ticker: str, hidden: bool) -> None:
        """Hide (or unhide) a ticker from the 全部標的 inventory.

        The inventory is sourced from the active-universe catalog, so a dead /
        duplicate ticker (e.g. a delisted symbol, or BRK.B vs BRK B) would
        otherwise reappear on every load. Suppression is a persistent per-ticker
        flag in ``ticker_meta`` that survives re-import; it does NOT touch the
        ``priority`` column on the same row.
        """
        t = _norm(ticker)
        if not t:
            raise ValueError("ticker is required")
        val = _now() if hidden else None
        now = _now()
        with self._write_lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO ticker_meta (ticker, hidden_at, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(ticker) DO UPDATE SET hidden_at = excluded.hidden_at, "
                "updated_at = excluded.updated_at",
                (t, val, now),
            )
            conn.commit()

    def get_hidden_tickers(self) -> set[str]:
        """The set of tickers suppressed from the universe inventory."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT ticker FROM ticker_meta WHERE hidden_at IS NOT NULL"
            ).fetchall()
        return {r["ticker"] for r in rows}

    # --- tags (two-dimensional facet × source, DECOUPLED from list membership) --

    def get_tags(self, tickers) -> dict[str, list[dict]]:
        """Per-ticker tags as ``{ticker: [{"facet","value","source"}, ...]}``.

        Tags are classification metadata (category / theme / provenance / …),
        intentionally decoupled from watchlist membership: a ticker keeps its tags
        whether or not it sits in any list. Only tickers with at least one tag
        appear in the result; rows are ordered ``facet`` then ``source`` then
        ``value`` so a ticker's chips render deterministically.
        """
        keys = _dedup_norm(tickers)
        if not keys:
            return {}
        ph = ",".join("?" * len(keys))
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT ticker, facet, value, source FROM ticker_tags "
                f"WHERE ticker IN ({ph}) ORDER BY ticker, facet, source, value",
                keys,
            ).fetchall()
        out: dict[str, list[dict]] = {}
        for r in rows:
            out.setdefault(r["ticker"], []).append(
                {"facet": r["facet"], "value": r["value"], "source": r["source"]}
            )
        return out

    def tag_catalog(self) -> dict[str, list[str]]:
        """Distinct tag values per facet (``{facet: [value, ...]}``) across all
        tickers — feeds the detail-page "pick from existing" classifier so a user
        applies an established theme/category instead of retyping it."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT facet, value FROM ticker_tags ORDER BY facet, value"
            ).fetchall()
        out: dict[str, list[str]] = {}
        for r in rows:
            out.setdefault(r["facet"], []).append(r["value"])
        return out

    def add_tag(self, ticker: str, value: str, *, facet: str = "theme", source: str = "user") -> None:
        """Attach a tag to a ticker (idempotent). Defaults to a user theme tag."""
        t = _norm(ticker)
        val = (value or "").strip()
        fac = (facet or "theme").strip() or "theme"
        src = (source or "user").strip() or "user"
        if not t:
            raise ValueError("ticker is required")
        if not val:
            raise ValueError("tag value is required")
        with self._write_lock, self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO ticker_tags (ticker, facet, value, source, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (t, fac, val, src, _now()),
            )
            conn.commit()

    def remove_tag(
        self, ticker: str, value: str, *, facet: str = "theme", source: Optional[str] = None
    ) -> bool:
        """Detach a tag from a ticker.

        Without ``source`` this removes only the ``user`` tag for that
        ``(facet, value)``. Read-only families (``system`` / ``provider:*`` /
        ``sec`` / ``broker``) are facts owned by import/providers, so the API
        layer must restrict ``source`` to the editable families
        (:data:`EDITABLE_TAG_SOURCES`); this store method itself deletes exactly
        what it is told.
        """
        t = _norm(ticker)
        val = (value or "").strip()
        fac = (facet or "theme").strip() or "theme"
        with self._write_lock, self._connect() as conn:
            if source is None:
                cur = conn.execute(
                    "DELETE FROM ticker_tags WHERE ticker = ? AND facet = ? AND value = ? "
                    "AND source = 'user'",
                    (t, fac, val),
                )
            else:
                cur = conn.execute(
                    "DELETE FROM ticker_tags WHERE ticker = ? AND facet = ? AND value = ? "
                    "AND source = ?",
                    (t, fac, val, source),
                )
            conn.commit()
            return cur.rowcount > 0

    def seed_tags(self, groups) -> dict:
        """Additive, idempotent bootstrap seed of tags from config-shaped groups.

        ``groups`` is an iterable of mappings ``{"facet", "value", "source"?, "tickers"}``.
        Duplicate ``(ticker, facet, value, source)`` rows are ignored. This is a
        ONE-TIME bootstrap from the (now demoted) config — purely additive: it
        never deletes or replaces existing tags, so ``user``/``legacy`` edits made
        in the app always survive a re-import. The old config rows are cleaned up
        once by the schema migration, not here. Returns ``{"tags_added": N}``.

        EXPLICIT importer — only call from a gated write action, never a read path.
        """
        now = _now()
        tags_added = 0
        with self._write_lock, self._connect() as conn:
            for spec in groups:
                value = (spec.get("value") or "").strip()
                facet = (spec.get("facet") or "").strip()
                if not value or not facet:
                    continue
                src = (spec.get("source") or "user").strip() or "user"
                for t in _dedup_norm(spec.get("tickers") or []):
                    cur = conn.execute(
                        "INSERT OR IGNORE INTO ticker_tags (ticker, facet, value, source, created_at) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (t, facet, value, src, now),
                    )
                    tags_added += cur.rowcount
            conn.commit()
        return {"tags_added": tags_added}

    # --- profile settings (small key/value bag) --------------------------

    def get_setting(self, key: str) -> Optional[str]:
        with self._connect() as conn:
            r = conn.execute(
                "SELECT value FROM profile_settings WHERE key = ?", (key,)
            ).fetchone()
        return r["value"] if r else None

    def set_setting(self, key: str, value: Optional[str]) -> None:
        with self._write_lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO profile_settings (key, value, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
                "updated_at = excluded.updated_at",
                (key, value, _now()),
            )
            conn.commit()

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

    # --- list CRUD + membership (user-created lists) --------------------

    def _list_summary(self, conn, list_id: int) -> Optional[WatchlistSummary]:
        r = conn.execute(
            """
            SELECT w.id, w.name, w.kind, w.position, w.archived_at,
                   SUM(CASE WHEN m.ticker IS NOT NULL AND m.archived_at IS NULL
                            THEN 1 ELSE 0 END) AS active_count,
                   SUM(CASE WHEN m.ticker IS NOT NULL THEN 1 ELSE 0 END) AS total_count
            FROM watchlists w
            LEFT JOIN watchlist_memberships m ON m.list_id = w.id
            WHERE w.id = ?
            GROUP BY w.id, w.name, w.kind, w.position, w.archived_at
            """,
            (list_id,),
        ).fetchone()
        if not r:
            return None
        return WatchlistSummary(
            id=r["id"], name=r["name"], kind=r["kind"], position=r["position"],
            archived=r["archived_at"] is not None,
            active_count=int(r["active_count"] or 0), total_count=int(r["total_count"] or 0),
        )

    def create_list(self, name: str, kind: Optional[str] = None) -> WatchlistSummary:
        n = (name or "").strip()
        if not n:
            raise ValueError("list name is required")
        now = _now()
        with self._write_lock, self._connect() as conn:
            pos = conn.execute(
                "SELECT COALESCE(MAX(position), -1) + 1 AS p FROM watchlists"
            ).fetchone()["p"]
            try:
                cur = conn.execute(
                    "INSERT INTO watchlists (name, kind, position, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (n, kind or _infer_kind(n), pos, now, now),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"a list named '{n}' already exists") from exc
            conn.commit()
            summary = self._list_summary(conn, cur.lastrowid)
        assert summary is not None
        return summary

    def rename_list(self, list_id: int, name: str) -> WatchlistSummary:
        n = (name or "").strip()
        if not n:
            raise ValueError("list name is required")
        with self._write_lock, self._connect() as conn:
            if not conn.execute("SELECT 1 FROM watchlists WHERE id = ?", (list_id,)).fetchone():
                raise KeyError(f"list {list_id} not found")
            try:
                conn.execute(
                    "UPDATE watchlists SET name = ?, updated_at = ? WHERE id = ?",
                    (n, _now(), list_id),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"a list named '{n}' already exists") from exc
            conn.commit()
            summary = self._list_summary(conn, list_id)
        assert summary is not None
        return summary

    def delete_list(self, list_id: int) -> bool:
        """Hard-delete a list and its memberships (FK ON DELETE CASCADE).

        This removes the list as a container; the tickers themselves survive in
        any OTHER lists they belong to. (Distinct from archiving a ticker.)
        """
        with self._write_lock, self._connect() as conn:
            cur = conn.execute("DELETE FROM watchlists WHERE id = ?", (list_id,))
            conn.commit()
            return cur.rowcount > 0

    def delete_non_custom_lists(self) -> int:
        """Delete every non-``custom`` list (and its memberships, via cascade).

        The de-mess: config-seeded tier/holdings/interested/theme/imported_profile
        lists are retired — classification now lives in tags, and the only lists
        are user work-lists (``custom``). Inventory is sourced from the active
        universe catalog, so dropping these memberships never loses a tracked
        ticker. Idempotent; returns the number of lists removed.
        """
        with self._write_lock, self._connect() as conn:
            cur = conn.execute("DELETE FROM watchlists WHERE kind != 'custom'")
            conn.commit()
            return cur.rowcount

    def add_member(self, list_id: int, ticker: str) -> None:
        """Add a ticker to a specific list (reactivates an archived membership)."""
        t = _norm(ticker)
        if not t:
            raise ValueError("ticker is required")
        now = _now()
        with self._write_lock, self._connect() as conn:
            if not conn.execute("SELECT 1 FROM watchlists WHERE id = ?", (list_id,)).fetchone():
                raise KeyError(f"list {list_id} not found")
            existing = conn.execute(
                "SELECT archived_at FROM watchlist_memberships WHERE list_id = ? AND ticker = ?",
                (list_id, t),
            ).fetchone()
            if existing is None:
                pos = conn.execute(
                    "SELECT COALESCE(MAX(position), -1) + 1 AS p "
                    "FROM watchlist_memberships WHERE list_id = ?",
                    (list_id,),
                ).fetchone()["p"]
                conn.execute(
                    "INSERT INTO watchlist_memberships "
                    "(list_id, ticker, position, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (list_id, t, pos, now, now),
                )
            elif existing["archived_at"] is not None:
                conn.execute(
                    "UPDATE watchlist_memberships SET archived_at = NULL, updated_at = ? "
                    "WHERE list_id = ? AND ticker = ?",
                    (now, list_id, t),
                )
            conn.commit()

    def remove_member(self, list_id: int, ticker: str) -> bool:
        """Remove a ticker from THIS list only (hard-delete the membership).

        Distinct from ``archive_ticker`` (global soft-archive across all lists):
        the ticker stays active in any other list it belongs to.
        """
        t = _norm(ticker)
        with self._write_lock, self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM watchlist_memberships WHERE list_id = ? AND ticker = ?",
                (list_id, t),
            )
            conn.commit()
            return cur.rowcount > 0

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
