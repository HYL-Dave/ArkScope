"""Local scheduler state (scheduler-hardening v1.2) — per-source durable state in profile_state.db.

Moves the scheduler's last-attempt / outcome / failure-reason off the PG ``job_runs`` archive into
a single local SQLite table so restart continuity (interval backoff) and the "why did it fail /
what's still missing" surface work with NO PG (PG stays an optional archive). One row per source:

    scheduler_state(source PK, last_attempt, last_status, last_error, continuation, last_result, updated_at)

``last_status`` includes ``partial`` as a FIRST-CLASS local value (a budget-bounded run that saved
a continuation, v1.3) — deliberately NOT mapped into PG ``job_runs``' status enum, which is left
untouched. ``continuation`` / ``last_result`` are JSON. Same path + idiom as the other
profile_state.db stores (CardRunStore, etc.). v1.2 adds the store + wires two scheduler touchpoints;
it does NOT change scheduling behavior.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS scheduler_state (
    source        TEXT PRIMARY KEY,
    last_attempt  TEXT,            -- ISO UTC: the genuine run-start time (interval backoff seed)
    last_status   TEXT,            -- running | succeeded | failed | skipped | partial
    last_error    TEXT,            -- NULL once a run succeeds (cleared by record_outcome)
    continuation  TEXT,            -- JSON: remaining scope after a partial (v1.3); NULL when none
    last_result   TEXT,            -- JSON: the last run's result dict (for the Settings surface)
    updated_at    TEXT NOT NULL
);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S%z")


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S%z")


def _parse_iso(s: str) -> datetime:
    """Parse our stored ISO ('...+0000') tz-aware — Python 3.10's fromisoformat needs a colon
    in the offset, so normalize the '+0000'/'Z' tail first."""
    t = s.strip()
    if t.endswith("Z"):
        t = t[:-1] + "+00:00"
    elif len(t) >= 5 and t[-5] in "+-" and t[-3] != ":":   # '+0000' → '+00:00'
        t = t[:-2] + ":" + t[-2:]
    return datetime.fromisoformat(t)


class SchedulerStateStore:
    """Per-source durable scheduler state over ``profile_state.db`` (local-primary; no PG)."""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._write_lock = threading.Lock()
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 5000")
        return conn

    def _ensure_schema(self) -> None:
        with self._write_lock, self._connect() as conn:
            try:
                conn.execute("PRAGMA journal_mode = WAL")
            except sqlite3.OperationalError:
                pass
            conn.executescript(_SCHEMA)

    def record_attempt(self, source: str, when: datetime) -> None:
        """Genuine run-start: set last_attempt + status='running'. Preserves last_error /
        last_result / continuation (the prior outcome stays visible while this run is in flight)."""
        with self._write_lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO scheduler_state (source, last_attempt, last_status, updated_at) "
                "VALUES (?,?, 'running', ?) "
                "ON CONFLICT(source) DO UPDATE SET last_attempt=excluded.last_attempt, "
                "last_status='running', updated_at=excluded.updated_at",
                (source, _iso(when), _now_iso()))

    def record_outcome(self, source: str, *, status: str, error: Optional[str] = None,
                       result: Optional[Dict[str, Any]] = None,
                       continuation: Optional[Dict[str, Any]] = None) -> None:
        """Terminal outcome: set last_status/last_error/last_result/continuation (each explicit —
        error=None CLEARS a stale error, continuation=None CLEARS a prior partial's scope).
        Preserves last_attempt (set by record_attempt at run start)."""
        with self._write_lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO scheduler_state (source, last_status, last_error, continuation, "
                "last_result, updated_at) VALUES (?,?,?,?,?,?) "
                "ON CONFLICT(source) DO UPDATE SET last_status=excluded.last_status, "
                "last_error=excluded.last_error, continuation=excluded.continuation, "
                "last_result=excluded.last_result, updated_at=excluded.updated_at",
                (source, status, error,
                 json.dumps(continuation) if continuation is not None else None,
                 json.dumps(result) if result is not None else None, _now_iso()))

    def get(self, source: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM scheduler_state WHERE source=?", (source,)).fetchone()
        return self._row_to_dict(row) if row else None

    def all(self) -> Dict[str, Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM scheduler_state").fetchall()
        return {r["source"]: self._row_to_dict(r) for r in rows}

    def last_attempts(self) -> Dict[str, datetime]:
        """Per-source last_attempt as tz-aware datetimes — for seeding _LAST_ATTEMPT on boot."""
        out: Dict[str, datetime] = {}
        with self._connect() as conn:
            for r in conn.execute(
                    "SELECT source, last_attempt FROM scheduler_state WHERE last_attempt IS NOT NULL"):
                try:
                    out[r["source"]] = _parse_iso(r["last_attempt"])
                except ValueError:
                    continue
        return out

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        for k in ("continuation", "last_result"):
            if d.get(k):
                try:
                    d[k] = json.loads(d[k])
                except (ValueError, TypeError):
                    d[k] = None
        return d
