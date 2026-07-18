"""Local server-owned AI Research run store.

`research_threads` / `research_messages` remain the final transcript authority.
This module owns durable run metadata plus a replay buffer of AgentEvent frames so
the browser can detach/reattach without owning execution.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from src.research_threads import ResearchThreadStore

_SCHEMA = """
CREATE TABLE IF NOT EXISTS research_runs (
    id               TEXT PRIMARY KEY,
    thread_id        TEXT NOT NULL REFERENCES research_threads(id) ON DELETE CASCADE,
    status           TEXT NOT NULL,
    question         TEXT NOT NULL,
    ticker           TEXT,
    provider         TEXT NOT NULL,
    model            TEXT NOT NULL,
    effort           TEXT,
    assistant_stance TEXT,
    auth_mode        TEXT,
    credential_id    TEXT,
    started_at       TEXT,
    completed_at     TEXT,
    error            TEXT,
    token_usage_json TEXT,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_research_runs_thread ON research_runs(thread_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_research_runs_status ON research_runs(status, updated_at DESC);

CREATE TABLE IF NOT EXISTS research_run_events (
    run_id      TEXT NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    seq         INTEGER NOT NULL,
    type        TEXT NOT NULL,
    data_json   TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    PRIMARY KEY (run_id, seq)
);
"""

ACTIVE_STATUSES = ("queued", "running")
TERMINAL_STATUSES = ("succeeded", "failed", "cancelled", "interrupted")
MAX_ACTIVE_THREAD_BATCH = 200


class ResearchRunUnavailableError(RuntimeError):
    """The owning thread cannot accept a new run in its current state."""

    def __init__(self, thread_id: str, reason: str):
        self.thread_id = thread_id
        self.reason = reason
        super().__init__(f"research thread is unavailable for a new run: {reason}")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _loads(v: Optional[str]):
    return json.loads(v) if v else None


@dataclass
class ResearchRun:
    id: str
    thread_id: str
    status: str
    question: str
    ticker: Optional[str]
    provider: str
    model: str
    effort: Optional[str]
    assistant_stance: Optional[str]
    auth_mode: Optional[str]
    credential_id: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]
    error: Optional[str]
    token_usage: Optional[dict]
    created_at: str
    updated_at: str


@dataclass
class ResearchRunEvent:
    run_id: str
    seq: int
    type: str
    data: dict
    created_at: str


class ResearchRunStore:
    """SQLite store for server-owned AI Research runs and replayable events."""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._write_lock = threading.Lock()
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _ensure_schema(self) -> None:
        from src.research_threads import _ensure_thread_schema

        _ensure_thread_schema(self.db_path)
        with self._write_lock, self._connect() as conn:
            try:
                conn.execute("PRAGMA journal_mode = WAL")
            except sqlite3.OperationalError:
                pass
            conn.executescript(_SCHEMA)
            # Migration: pre-existing research_runs tables gain the Track A
            # stance column (same tolerant ALTER pattern as the other stores).
            cols = {r[1] for r in conn.execute("PRAGMA table_info(research_runs)").fetchall()}
            if "assistant_stance" not in cols:
                try:
                    conn.execute("ALTER TABLE research_runs ADD COLUMN assistant_stance TEXT")
                except sqlite3.OperationalError:
                    pass
            conn.commit()

    @staticmethod
    def _run(r: sqlite3.Row) -> ResearchRun:
        return ResearchRun(
            id=r["id"], thread_id=r["thread_id"], status=r["status"],
            question=r["question"], ticker=r["ticker"], provider=r["provider"],
            model=r["model"], effort=r["effort"],
            assistant_stance=r["assistant_stance"], auth_mode=r["auth_mode"],
            credential_id=r["credential_id"], started_at=r["started_at"],
            completed_at=r["completed_at"], error=r["error"],
            token_usage=_loads(r["token_usage_json"]), created_at=r["created_at"],
            updated_at=r["updated_at"],
        )

    @staticmethod
    def _event(r: sqlite3.Row) -> ResearchRunEvent:
        return ResearchRunEvent(
            run_id=r["run_id"], seq=r["seq"], type=r["type"],
            data=_loads(r["data_json"]) or {}, created_at=r["created_at"],
        )

    def create_run(
        self,
        *,
        id: str,
        thread_id: str,
        question: str,
        ticker: Optional[str],
        provider: str,
        model: str,
        effort: Optional[str],
        auth_mode: Optional[str],
        credential_id: Optional[str],
        assistant_stance: Optional[str] = None,
    ) -> ResearchRun:
        with self._write_lock, self._connect() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                run = self._create_run_on_connection(
                    conn,
                    id=id,
                    thread_id=thread_id,
                    question=question,
                    ticker=ticker,
                    provider=provider,
                    model=model,
                    effort=effort,
                    auth_mode=auth_mode,
                    credential_id=credential_id,
                    assistant_stance=assistant_stance,
                )
                conn.commit()
            except BaseException:
                conn.rollback()
                raise
        return run

    def _create_run_on_connection(
        self,
        conn: sqlite3.Connection,
        *,
        id: str,
        thread_id: str,
        question: str,
        ticker: Optional[str],
        provider: str,
        model: str,
        effort: Optional[str],
        auth_mode: Optional[str],
        credential_id: Optional[str],
        assistant_stance: Optional[str] = None,
        now: Optional[str] = None,
    ) -> ResearchRun:
        """Apply the run-owned insert on a caller-managed transaction."""
        ts = now or _now()
        thread = conn.execute(
            "SELECT archived_at FROM research_threads WHERE id = ?",
            (thread_id,),
        ).fetchone()
        if thread is None:
            raise ResearchRunUnavailableError(thread_id, "missing")
        if thread["archived_at"] is not None:
            raise ResearchRunUnavailableError(thread_id, "archived")
        active = conn.execute(
            "SELECT 1 FROM research_runs "
            "WHERE thread_id = ? AND status IN ('queued','running') LIMIT 1",
            (thread_id,),
        ).fetchone()
        if active is not None:
            raise ResearchRunUnavailableError(thread_id, "active_run")
        conn.execute(
            """
            INSERT INTO research_runs
              (id, thread_id, status, question, ticker, provider, model, effort,
               assistant_stance, auth_mode, credential_id, created_at, updated_at)
            VALUES (?, ?, 'queued', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                id, thread_id, question, ticker, provider, model, effort,
                assistant_stance, auth_mode, credential_id, ts, ts,
            ),
        )
        row = conn.execute(
            "SELECT * FROM research_runs WHERE id = ?", (id,)
        ).fetchone()
        assert row is not None
        return self._run(row)

    def _require_shared_database(self, thread_store: ResearchThreadStore) -> None:
        try:
            same_database = Path(self.db_path).samefile(thread_store.db_path)
        except OSError:
            same_database = (
                Path(self.db_path).resolve() == Path(thread_store.db_path).resolve()
            )
        if self.db_path == ":memory:" or not same_database:
            raise ValueError(
                "thread_store and run_store must use the same SQLite database"
            )

    def create_run_with_user_message(
        self,
        *,
        thread_store: ResearchThreadStore,
        new_thread_title: Optional[str],
        id: str,
        thread_id: str,
        question: str,
        user_content: str,
        user_tickers: Optional[list],
        ticker: Optional[str],
        provider: str,
        model: str,
        effort: Optional[str],
        auth_mode: Optional[str],
        credential_id: Optional[str],
        assistant_stance: Optional[str] = None,
        retry_last_failed: bool = False,
    ) -> tuple[ResearchRun, list[dict]]:
        """Atomically queue a run, snapshot history, and persist its user turn."""
        self._require_shared_database(thread_store)

        ts = _now()
        with self._write_lock, thread_store._write_lock, self._connect() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                if new_thread_title is not None:
                    thread_store._ensure_thread_on_connection(
                        conn,
                        id=thread_id,
                        title=new_thread_title,
                        ticker=ticker,
                        provider=provider,
                        model=model,
                        now=ts,
                    )
                run = self._create_run_on_connection(
                    conn,
                    id=id,
                    thread_id=thread_id,
                    question=question,
                    ticker=ticker,
                    provider=provider,
                    model=model,
                    effort=effort,
                    auth_mode=auth_mode,
                    credential_id=credential_id,
                    assistant_stance=assistant_stance,
                    now=ts,
                )
                history = thread_store._build_thread_history_on_connection(
                    conn,
                    thread_id,
                    exclude_last_failed_pair=retry_last_failed,
                )
                thread_store._append_message_on_connection(
                    conn,
                    thread_id=thread_id,
                    role="user",
                    content=user_content,
                    tickers=user_tickers,
                    now=ts,
                )
                conn.commit()
            except BaseException:
                conn.rollback()
                raise
        return run, history

    def fail_queued_run_handoff(
        self,
        *,
        run_id: str,
        thread_store: ResearchThreadStore,
        message: str,
    ) -> ResearchRun:
        """Atomically record a scheduler handoff failure for a queued run."""
        self._require_shared_database(thread_store)
        ts = _now()
        with self._write_lock, thread_store._write_lock, self._connect() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                failed_run = self._mark_terminal_on_connection(
                    conn,
                    run_id,
                    "failed",
                    error=message,
                    expected_status="queued",
                    now=ts,
                )
                if failed_run is None:
                    raise RuntimeError("queued research run is unavailable")
                self._append_event_on_connection(
                    conn,
                    run_id,
                    "error",
                    {"error": message},
                    now=ts,
                )
                thread_store._append_message_on_connection(
                    conn,
                    thread_id=failed_run.thread_id,
                    run_id=run_id,
                    role="assistant",
                    content=message,
                    provider=failed_run.provider,
                    model=failed_run.model,
                    effort=failed_run.effort,
                    is_error=True,
                    now=ts,
                )
                conn.commit()
            except BaseException:
                conn.rollback()
                raise
        return failed_run

    def get_run(self, run_id: str) -> Optional[ResearchRun]:
        with self._connect() as conn:
            r = conn.execute("SELECT * FROM research_runs WHERE id = ?", (run_id,)).fetchone()
        return self._run(r) if r else None

    def latest_active_for_thread(self, thread_id: str) -> Optional[ResearchRun]:
        with self._connect() as conn:
            r = conn.execute(
                "SELECT * FROM research_runs WHERE thread_id = ? AND status IN ('queued','running') "
                "ORDER BY created_at DESC LIMIT 1",
                (thread_id,),
            ).fetchone()
        return self._run(r) if r else None

    def latest_active_for_threads(
        self,
        thread_ids: Sequence[str],
        *,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, ResearchRun]:
        """Resolve one latest active run per thread with one bounded query."""
        if isinstance(thread_ids, (str, bytes)) or not isinstance(thread_ids, Sequence):
            raise TypeError("thread_ids must be a bounded sequence")
        if len(thread_ids) > MAX_ACTIVE_THREAD_BATCH:
            raise ValueError(
                f"thread_ids cannot exceed {MAX_ACTIVE_THREAD_BATCH} entries"
            )
        if not thread_ids:
            return {}
        if any(not isinstance(thread_id, str) for thread_id in thread_ids):
            raise TypeError("thread_ids must contain strings")

        unique_ids = tuple(dict.fromkeys(thread_ids))
        placeholders = ",".join("?" for _ in unique_ids)
        sql = (
            f"SELECT * FROM research_runs WHERE thread_id IN ({placeholders}) "
            "AND status IN ('queued','running') "
            "ORDER BY thread_id ASC, created_at DESC, id DESC"
        )
        if conn is not None:
            rows = conn.execute(sql, unique_ids).fetchall()
        else:
            with self._connect() as owned_conn:
                rows = owned_conn.execute(
                    sql,
                    unique_ids,
                ).fetchall()

        latest: dict[str, ResearchRun] = {}
        for row in rows:
            latest.setdefault(row["thread_id"], self._run(row))
        return latest

    def mark_running(self, run_id: str) -> None:
        ts = _now()
        with self._write_lock, self._connect() as conn:
            conn.execute(
                "UPDATE research_runs SET status = 'running', started_at = COALESCE(started_at, ?), "
                "updated_at = ? WHERE id = ? AND status = 'queued'",
                (ts, ts, run_id),
            )
            conn.commit()

    def _mark_terminal_on_connection(
        self,
        conn: sqlite3.Connection,
        run_id: str,
        status: str,
        *,
        error: Optional[str] = None,
        token_usage: Optional[dict] = None,
        expected_status: Optional[str] = None,
        now: Optional[str] = None,
    ) -> Optional[ResearchRun]:
        if status not in TERMINAL_STATUSES:
            raise ValueError(f"invalid terminal status: {status}")
        ts = now or _now()
        expected_clause = " AND status = ?" if expected_status is not None else ""
        params = [
            status,
            ts,
            ts,
            error,
            json.dumps(token_usage) if token_usage is not None else None,
            run_id,
        ]
        if expected_status is not None:
            params.append(expected_status)
        cur = conn.execute(
            "UPDATE research_runs SET status = ?, completed_at = ?, updated_at = ?, "
            f"error = ?, token_usage_json = ? WHERE id = ?{expected_clause}",
            params,
        )
        if cur.rowcount == 0:
            return None
        row = conn.execute(
            "SELECT * FROM research_runs WHERE id = ?", (run_id,)
        ).fetchone()
        assert row is not None
        return self._run(row)

    def mark_terminal(
        self,
        run_id: str,
        status: str,
        *,
        error: Optional[str] = None,
        token_usage: Optional[dict] = None,
    ) -> None:
        with self._write_lock, self._connect() as conn:
            self._mark_terminal_on_connection(
                conn,
                run_id,
                status,
                error=error,
                token_usage=token_usage,
            )
            conn.commit()

    def _append_event_on_connection(
        self,
        conn: sqlite3.Connection,
        run_id: str,
        type: str,
        data: dict,
        *,
        now: Optional[str] = None,
    ) -> ResearchRunEvent:
        ts = now or _now()
        row = conn.execute(
            "SELECT COALESCE(MAX(seq), 0) + 1 AS next_seq "
            "FROM research_run_events WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        seq = int(row["next_seq"])
        conn.execute(
            "INSERT INTO research_run_events (run_id, seq, type, data_json, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (run_id, seq, type, json.dumps(data), ts),
        )
        conn.execute(
            "UPDATE research_runs SET updated_at = ? WHERE id = ?", (ts, run_id)
        )
        return ResearchRunEvent(
            run_id=run_id,
            seq=seq,
            type=type,
            data=data,
            created_at=ts,
        )

    def append_event(self, run_id: str, type: str, data: dict) -> ResearchRunEvent:
        with self._write_lock, self._connect() as conn:
            event = self._append_event_on_connection(conn, run_id, type, data)
            conn.commit()
        return event

    def list_events(self, run_id: str, *, after: int = 0, limit: int = 500) -> list[ResearchRunEvent]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM research_run_events WHERE run_id = ? AND seq > ? "
                "ORDER BY seq ASC LIMIT ?",
                (run_id, after, limit),
            ).fetchall()
        return [self._event(r) for r in rows]

    def reconcile_interrupted(self, *, thread_store=None) -> list[str]:
        """Mark orphaned queued/running runs terminal on process boot/store init.

        When a thread_store is provided, also persist an error assistant turn so
        reload never shows a dangling user message after a sidecar crash.
        """
        ts = _now()
        with self._write_lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM research_runs WHERE status IN ('queued','running')"
            ).fetchall()
            ids = [r["id"] for r in rows]
            for run_id in ids:
                conn.execute(
                    "UPDATE research_runs SET status = 'interrupted', completed_at = ?, "
                    "updated_at = ?, error = ? WHERE id = ?",
                    (ts, ts, "research run interrupted by sidecar restart", run_id),
                )
            conn.commit()
        if thread_store is not None:
            for row in rows:
                try:
                    thread_store.append_message(
                        thread_id=row["thread_id"],
                        role="assistant",
                        content="research run interrupted by sidecar restart",
                        provider=row["provider"],
                        model=row["model"],
                        elapsed_seconds=None,
                        is_error=True,
                    )
                except Exception:
                    # Best-effort reconciliation; the run row remains terminal.
                    pass
        return ids
