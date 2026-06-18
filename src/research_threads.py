"""
Local store for AI 研究 conversation threads + messages (SQLite) — Layer C-2b.

C-2a held threads in React state (ephemeral). This persists them so they survive
reload. Column names match the C-2a in-memory DTO (spec §6a) verbatim, so the
client→server write is a pure write-through with no UI-state reshape.

Local-first: lives in the same standalone SQLite DB as the profile-state and
card-run stores (``data/profile_state.db``), NEVER the remote PG. Mirrors
``CardRunStore`` (src/card_runs.py): module ``_now``, per-instance ``_write_lock``,
``_connect`` with busy_timeout, WAL-best-effort schema init.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_SCHEMA = """
CREATE TABLE IF NOT EXISTS research_threads (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    ticker      TEXT,
    provider    TEXT,
    model       TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    archived_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_research_threads_updated ON research_threads(updated_at DESC);

CREATE TABLE IF NOT EXISTS research_messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id       TEXT NOT NULL REFERENCES research_threads(id) ON DELETE CASCADE,
    role            TEXT NOT NULL,
    content         TEXT NOT NULL DEFAULT '',
    provider        TEXT,
    model           TEXT,
    tools_used_json TEXT,
    tool_calls_json TEXT,
    token_usage_json TEXT,
    tickers_json    TEXT,
    elapsed_seconds REAL,
    is_error        INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_research_messages_thread ON research_messages(thread_id, id);
"""


MAX_THREAD_ID = 200


def valid_thread_id(tid: Optional[str]) -> bool:
    """Client-owned thread id must be non-blank and bounded (route gate + the
    stream-hook persistence gate both use this)."""
    return bool(tid) and bool(tid.strip()) and len(tid) <= MAX_THREAD_ID


def build_thread_history(store, thread_id: str, policy: str = "full_thread") -> list[dict]:
    """Provider-neutral prompt-context history for a thread (C-2c, plan §4/§5).

    Returns the prior conversation as ``[{role, content}, ...]`` to seed the
    agent — content ONLY (no tool_calls/token_usage/tickers/metadata leak into
    context). The persisted transcript is never mutated; this is prompt-context
    selection, not memory deletion.

    - ``full_thread`` (default): every prior NON-error, non-empty user/assistant
      message, in order. No silent truncation.
    - ``no_history``: explicit opt-out → ``[]``.
    - ``recent_messages`` / ``summary_plus_recent``: reserved (plan §5) — raise,
      so a cap/summary can't ship implicitly before it's designed.
    """
    if policy == "no_history":
        return []
    if policy != "full_thread":
        raise ValueError(f"unsupported history policy (reserved, not yet built): {policy}")
    out: list[dict] = []
    for m in store.list_messages(thread_id):
        if getattr(m, "is_error", False) or not m.content:
            continue
        out.append({"role": m.role, "content": m.content})
    return out


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _loads(v: Optional[str]):
    return json.loads(v) if v else None


@dataclass
class ResearchThread:
    id: str  # client-owned stable id (e.g. crypto.randomUUID), agreed reducer↔store
    title: str
    ticker: Optional[str]
    provider: Optional[str]
    model: Optional[str]
    created_at: str
    updated_at: str
    archived_at: Optional[str] = None


@dataclass
class ResearchMessage:
    id: int
    thread_id: str
    role: str
    content: str
    provider: Optional[str]
    model: Optional[str]
    tools_used: list
    tool_calls: list
    token_usage: Optional[dict]
    tickers: Optional[list]
    elapsed_seconds: Optional[float]
    is_error: bool
    created_at: str


class ResearchThreadStore:
    """Local SQLite store for AI 研究 threads + their messages."""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._write_lock = threading.Lock()
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("PRAGMA foreign_keys = ON")  # honour the messages→threads CASCADE
        return conn

    def _ensure_schema(self) -> None:
        with self._write_lock, self._connect() as conn:
            try:
                conn.execute("PRAGMA journal_mode = WAL")
            except sqlite3.OperationalError:
                pass
            conn.executescript(_SCHEMA)
            # Migration: add is_error to a pre-existing research_messages table.
            # Tolerant of the concurrent-first-construct race (duplicate column =
            # another constructor added it), per CardRunStore's pattern.
            cols = {r[1] for r in conn.execute("PRAGMA table_info(research_messages)").fetchall()}
            if "is_error" not in cols:
                try:
                    conn.execute("ALTER TABLE research_messages ADD COLUMN is_error INTEGER NOT NULL DEFAULT 0")
                except sqlite3.OperationalError:
                    pass
            conn.commit()

    # --- row mappers -----------------------------------------------------

    @staticmethod
    def _thread(r: sqlite3.Row) -> ResearchThread:
        return ResearchThread(
            id=r["id"], title=r["title"], ticker=r["ticker"], provider=r["provider"],
            model=r["model"], created_at=r["created_at"], updated_at=r["updated_at"],
            archived_at=r["archived_at"],
        )

    @staticmethod
    def _message(r: sqlite3.Row) -> ResearchMessage:
        return ResearchMessage(
            id=r["id"], thread_id=r["thread_id"], role=r["role"], content=r["content"],
            provider=r["provider"], model=r["model"],
            tools_used=_loads(r["tools_used_json"]) or [],
            tool_calls=_loads(r["tool_calls_json"]) or [],
            token_usage=_loads(r["token_usage_json"]),
            tickers=_loads(r["tickers_json"]),
            elapsed_seconds=r["elapsed_seconds"],
            is_error=bool(r["is_error"]),
            created_at=r["created_at"],
        )

    # --- writes ----------------------------------------------------------

    def ensure_thread(
        self,
        *,
        id: str,
        title: str,
        ticker: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        now: Optional[str] = None,
    ) -> ResearchThread:
        """Idempotent create: the per-turn stream hook calls this every turn, so
        a second call with an existing id is a no-op (title/created_at frozen)."""
        ts = now or _now()
        with self._write_lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO research_threads (id, title, ticker, provider, model, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO NOTHING",
                (id, title, ticker, provider, model, ts, ts),
            )
            conn.commit()
        got = self.get_thread(id)
        assert got is not None
        return got

    def append_message(
        self,
        *,
        thread_id: str,
        role: str,
        content: str = "",
        provider: Optional[str] = None,
        model: Optional[str] = None,
        tools_used: Optional[list] = None,
        tool_calls: Optional[list] = None,
        token_usage: Optional[dict] = None,
        tickers: Optional[list] = None,
        elapsed_seconds: Optional[float] = None,
        is_error: bool = False,
        now: Optional[str] = None,
    ) -> ResearchMessage:
        ts = now or _now()
        with self._write_lock, self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO research_messages
                    (thread_id, role, content, provider, model, tools_used_json,
                     tool_calls_json, token_usage_json, tickers_json, elapsed_seconds,
                     is_error, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    thread_id, role, content, provider, model,
                    json.dumps(tools_used) if tools_used is not None else None,
                    json.dumps(tool_calls) if tool_calls is not None else None,
                    json.dumps(token_usage) if token_usage is not None else None,
                    json.dumps(tickers) if tickers is not None else None,
                    elapsed_seconds, 1 if is_error else 0, ts,
                ),
            )
            # Bump the parent thread's activity so list_threads orders it first.
            conn.execute("UPDATE research_threads SET updated_at = ? WHERE id = ?", (ts, thread_id))
            conn.commit()
            mid = cur.lastrowid
            r = conn.execute("SELECT * FROM research_messages WHERE id = ?", (mid,)).fetchone()
        return self._message(r)

    def delete_thread(self, thread_id: str) -> bool:
        """Delete one persisted research conversation and all of its messages."""
        with self._write_lock, self._connect() as conn:
            cur = conn.execute("DELETE FROM research_threads WHERE id = ?", (thread_id,))
            conn.commit()
        return cur.rowcount > 0

    # --- reads -----------------------------------------------------------

    def get_thread(self, thread_id: str) -> Optional[ResearchThread]:
        with self._connect() as conn:
            r = conn.execute("SELECT * FROM research_threads WHERE id = ?", (thread_id,)).fetchone()
        return self._thread(r) if r else None

    def list_threads(self, *, limit: int = 50, include_archived: bool = False) -> list[ResearchThread]:
        where = "" if include_archived else "WHERE archived_at IS NULL"
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM research_threads {where} ORDER BY updated_at DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._thread(r) for r in rows]

    def list_messages(self, thread_id: str) -> list[ResearchMessage]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM research_messages WHERE thread_id = ? ORDER BY id ASC", (thread_id,)
            ).fetchall()
        return [self._message(r) for r in rows]
