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

_THREAD_SCHEMA = """
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
"""

_MESSAGE_SCHEMA = """
CREATE TABLE IF NOT EXISTS research_messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id       TEXT NOT NULL REFERENCES research_threads(id) ON DELETE CASCADE,
    run_id           TEXT REFERENCES research_runs(id) ON DELETE SET NULL,
    role            TEXT NOT NULL,
    content         TEXT NOT NULL DEFAULT '',
    provider        TEXT,
    model           TEXT,
    effort          TEXT,
    tools_used_json TEXT,
    tool_calls_json TEXT,
    token_usage_json TEXT,
    tickers_json    TEXT,
    elapsed_seconds REAL,
    is_error        INTEGER NOT NULL DEFAULT 0,
    error_code      TEXT,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_research_messages_thread ON research_messages(thread_id, id);
"""


MAX_THREAD_ID = 200
MAX_TOOL_CALLS_SENTINEL = "Maximum tool calls reached. Please try a simpler query."


class ResearchThreadActiveError(RuntimeError):
    """An active run prevents a destructive thread lifecycle transition."""


def valid_thread_id(tid: Optional[str]) -> bool:
    """Client-owned thread id must be non-blank and bounded (route gate + the
    stream-hook persistence gate both use this)."""
    return bool(tid) and bool(tid.strip()) and len(tid) <= MAX_THREAD_ID


def _is_retryable_failed_tail(m: ResearchMessage) -> bool:
    if m.role != "assistant":
        return False
    if getattr(m, "is_error", False):
        return True
    content = m.content or ""
    return content == MAX_TOOL_CALLS_SENTINEL or "Reached maximum number of turns" in content


def build_thread_history(
    store,
    thread_id: str,
    policy: str = "full_thread",
    *,
    exclude_last_failed_pair: bool = False,
) -> list[dict]:
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
    messages = store.list_messages(thread_id)
    if (
        exclude_last_failed_pair
        and len(messages) >= 2
        and messages[-2].role == "user"
        and _is_retryable_failed_tail(messages[-1])
    ):
        messages = messages[:-2]
    out: list[dict] = []
    for m in messages:
        if getattr(m, "is_error", False) or not m.content:
            continue
        out.append({"role": m.role, "content": m.content})
    return out


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _loads(v: Optional[str]):
    return json.loads(v) if v else None


def _ensure_thread_schema(db_path: str | Path) -> None:
    """Create only the thread-owned table before run/message dependents."""
    with sqlite3.connect(str(db_path), timeout=5.0) as conn:
        conn.execute("PRAGMA busy_timeout = 5000")
        try:
            conn.execute("PRAGMA journal_mode = WAL")
        except sqlite3.OperationalError:
            pass
        conn.executescript(_THREAD_SCHEMA)
        conn.commit()


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
    run_id: Optional[str]
    role: str
    content: str
    provider: Optional[str]
    model: Optional[str]
    effort: Optional[str]
    tools_used: list
    tool_calls: list
    token_usage: Optional[dict]
    tickers: Optional[list]
    elapsed_seconds: Optional[float]
    is_error: bool
    error_code: Optional[str]
    personalization: Optional[dict]
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
        with self._write_lock:
            _ensure_thread_schema(self.db_path)

            # Messages may link to runs, so the run store must create its
            # authoritative tables before fresh message creation or migration.
            from src.research_runs import ResearchRunStore

            ResearchRunStore(self.db_path)

            with self._connect() as conn:
                conn.executescript(_MESSAGE_SCHEMA)
                # Tolerate pre-existing message tables and concurrent first
                # constructors using the established additive-column pattern.
                cols = {
                    r[1]
                    for r in conn.execute(
                        "PRAGMA table_info(research_messages)"
                    ).fetchall()
                }
                migrations = (
                    ("is_error", "is_error INTEGER NOT NULL DEFAULT 0"),
                    ("effort", "effort TEXT"),
                    ("personalization_json", "personalization_json TEXT"),
                    (
                        "run_id",
                        "run_id TEXT REFERENCES research_runs(id) ON DELETE SET NULL",
                    ),
                    ("error_code", "error_code TEXT"),
                )
                for column, definition in migrations:
                    if column in cols:
                        continue
                    try:
                        conn.execute(
                            f"ALTER TABLE research_messages ADD COLUMN {definition}"
                        )
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
            id=r["id"], thread_id=r["thread_id"], run_id=r["run_id"],
            role=r["role"], content=r["content"],
            provider=r["provider"], model=r["model"], effort=r["effort"],
            tools_used=_loads(r["tools_used_json"]) or [],
            tool_calls=_loads(r["tool_calls_json"]) or [],
            token_usage=_loads(r["token_usage_json"]),
            tickers=_loads(r["tickers_json"]),
            elapsed_seconds=r["elapsed_seconds"],
            is_error=bool(r["is_error"]),
            error_code=r["error_code"],
            personalization=_loads(r["personalization_json"]),
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
        run_id: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        effort: Optional[str] = None,
        tools_used: Optional[list] = None,
        tool_calls: Optional[list] = None,
        token_usage: Optional[dict] = None,
        tickers: Optional[list] = None,
        elapsed_seconds: Optional[float] = None,
        is_error: bool = False,
        error_code: Optional[str] = None,
        personalization: Optional[dict] = None,
        now: Optional[str] = None,
    ) -> ResearchMessage:
        ts = now or _now()
        with self._write_lock, self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO research_messages
                    (thread_id, run_id, role, content, provider, model, effort, tools_used_json,
                     tool_calls_json, token_usage_json, tickers_json, elapsed_seconds,
                     is_error, error_code, personalization_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    thread_id, run_id, role, content, provider, model, effort,
                    json.dumps(tools_used) if tools_used is not None else None,
                    json.dumps(tool_calls) if tool_calls is not None else None,
                    json.dumps(token_usage) if token_usage is not None else None,
                    json.dumps(tickers) if tickers is not None else None,
                    elapsed_seconds, 1 if is_error else 0, error_code,
                    json.dumps(personalization) if personalization is not None else None,
                    ts,
                ),
            )
            # Bump the parent thread's activity so list_threads orders it first.
            conn.execute("UPDATE research_threads SET updated_at = ? WHERE id = ?", (ts, thread_id))
            conn.commit()
            mid = cur.lastrowid
            r = conn.execute("SELECT * FROM research_messages WHERE id = ?", (mid,)).fetchone()
        return self._message(r)

    def rename_thread(
        self,
        thread_id: str,
        title: str,
        *,
        now: Optional[str] = None,
    ) -> Optional[ResearchThread]:
        return self.update_thread_lifecycle(thread_id, title=title, now=now)

    def set_thread_archived(
        self,
        thread_id: str,
        archived: bool,
        *,
        now: Optional[str] = None,
    ) -> Optional[ResearchThread]:
        return self.update_thread_lifecycle(
            thread_id,
            archived=archived,
            now=now,
        )

    def update_thread_lifecycle(
        self,
        thread_id: str,
        *,
        title: Optional[str] = None,
        archived: Optional[bool] = None,
        now: Optional[str] = None,
    ) -> Optional[ResearchThread]:
        """Atomically apply one lifecycle patch under the SQLite writer lock."""
        if title is None and archived is None:
            raise ValueError("at least one lifecycle field is required")
        ts = now or _now()
        with self._write_lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            current = conn.execute(
                "SELECT * FROM research_threads WHERE id = ?", (thread_id,)
            ).fetchone()
            if current is None:
                conn.rollback()
                return None
            if archived is True:
                active = conn.execute(
                    "SELECT 1 FROM research_runs "
                    "WHERE thread_id = ? AND status IN ('queued','running') LIMIT 1",
                    (thread_id,),
                ).fetchone()
                if active is not None:
                    raise ResearchThreadActiveError(thread_id)

            assignments: list[str] = []
            params: list[object] = []
            if title is not None:
                assignments.append("title = ?")
                params.append(title)
            if archived is not None:
                assignments.append("archived_at = ?")
                params.append(ts if archived else None)
            assignments.append("updated_at = ?")
            params.extend((ts, thread_id))
            conn.execute(
                f"UPDATE research_threads SET {', '.join(assignments)} WHERE id = ?",
                params,
            )
            row = conn.execute(
                "SELECT * FROM research_threads WHERE id = ?", (thread_id,)
            ).fetchone()
            conn.commit()
        return self._thread(row)

    def delete_thread(self, thread_id: str) -> bool:
        """Delete one persisted research conversation and all of its messages."""
        with self._write_lock, self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            current = conn.execute(
                "SELECT 1 FROM research_threads WHERE id = ?", (thread_id,)
            ).fetchone()
            if current is None:
                conn.rollback()
                return False
            active = conn.execute(
                "SELECT 1 FROM research_runs "
                "WHERE thread_id = ? AND status IN ('queued','running') LIMIT 1",
                (thread_id,),
            ).fetchone()
            if active is not None:
                raise ResearchThreadActiveError(thread_id)
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
