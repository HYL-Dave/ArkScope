"""Persistence layer for service job executions (P0.2).

``JobRunsStore`` writes to the ``job_runs`` table (sql/011) so that:

  - ``GET /jobs/status`` returns DB-backed last_status / last_started_at
    instead of process-local memory that vanishes on restart.
  - ``GET /jobs/history`` exposes per-run history with pagination.
  - Schedulers / Chrome extension / dashboard can observe job state
    independently of the process that ran them.

Design contract:

  - **Persistence is best-effort**: a DB outage must NOT fail the job.
    All store methods catch psycopg2 errors, log, and return ``None`` /
    empty results so callers can degrade to process-local state.
  - **FileBackend is a no-op**: when the DAL is on FileBackend the store
    reports ``is_available() == False`` and methods return early.
  - **No same-name concurrency control**: per the priority-map decision,
    a job can be started while a previous run is still ``running``.
    Each call records a new row.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Local import guarded so this module can be imported in environments
# without psycopg2 (e.g. FileBackend-only test runs).
try:
    import psycopg2
    import psycopg2.extras
except Exception:  # pragma: no cover - import failure not expected in service env
    psycopg2 = None  # type: ignore[assignment]


_VALID_STATUSES = frozenset({"running", "succeeded", "failed"})
USE_LOCAL_JOB_RUNS_KEY = "use_local_job_runs"
ENV_USE_LOCAL_JOB_RUNS = "ARKSCOPE_USE_LOCAL_JOB_RUNS"

_SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS job_runs (
    id              INTEGER PRIMARY KEY,
    job_name        TEXT NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('running', 'succeeded', 'failed')),
    trigger_source  TEXT NOT NULL DEFAULT 'api',
    payload         TEXT NOT NULL DEFAULT '{}',
    result          TEXT,
    message         TEXT,
    error           TEXT,
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    duration_ms     INTEGER,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_job_runs_name_started_at
    ON job_runs (job_name, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_job_runs_status_started_at
    ON job_runs (status, started_at DESC);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _to_iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        if getattr(value, "tzinfo", None):
            return value.astimezone(timezone.utc).isoformat(timespec="seconds")
        return value.replace(tzinfo=timezone.utc).isoformat(timespec="seconds")
    text = str(value).strip()
    return text.replace("Z", "+00:00") if text.endswith("Z") else text


def _json_dumps(value: Optional[Dict[str, Any]]) -> str:
    return json.dumps(value or {}, sort_keys=True)


def _json_or_none(value: Optional[Dict[str, Any]]) -> Optional[str]:
    return json.dumps(value, sort_keys=True) if value is not None else None


def _json_load(value: Any) -> Any:
    if value is None or isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return value


class JobRunsStore:
    """Thin SQL helper around the ``job_runs`` table.

    Construct with a DAL; the store inspects ``dal._backend`` to decide
    whether DB calls are possible.
    """

    def __init__(self, dal: Any) -> None:
        self._dal = dal
        self._backend = getattr(dal, "_backend", None)

    # -- availability --------------------------------------------------------

    def is_available(self) -> bool:
        """True iff the DAL is backed by a DatabaseBackend with a usable conn."""
        if self._backend is None:
            return False
        return hasattr(self._backend, "_get_conn")

    # -- writes --------------------------------------------------------------

    def create_run(
        self,
        job_name: str,
        *,
        trigger_source: str = "api",
        payload: Optional[Dict[str, Any]] = None,
    ) -> Optional[int]:
        """Insert a row in the ``running`` state. Returns the new run id, or None.

        ``None`` is returned when the store is unavailable or the insert
        fails — callers should log and continue with process-local state.
        """
        if not self.is_available():
            return None
        if psycopg2 is None:  # pragma: no cover - guarded import path
            return None
        try:
            conn = self._backend._get_conn()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO job_runs (job_name, status, trigger_source, payload)
                    VALUES (%s, 'running', %s, %s)
                    RETURNING id
                    """,
                    (
                        job_name,
                        trigger_source,
                        psycopg2.extras.Json(payload or {}),
                    ),
                )
                row = cur.fetchone()
            return int(row[0]) if row else None
        except Exception as exc:
            logger.warning("JobRunsStore.create_run failed for %s: %s", job_name, exc)
            return None

    def finish_run(
        self,
        run_id: Optional[int],
        *,
        status: str,
        message: Optional[str] = None,
        error: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[int] = None,
    ) -> bool:
        """Update one run row to a terminal state. Returns True on success."""
        if run_id is None:
            return False
        if status not in _VALID_STATUSES:
            raise ValueError(f"invalid job status: {status!r}")
        if status == "running":
            raise ValueError("finish_run requires a terminal status")
        if not self.is_available():
            return False
        if psycopg2 is None:  # pragma: no cover
            return False
        try:
            conn = self._backend._get_conn()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE job_runs
                    SET status = %s,
                        message = %s,
                        error = %s,
                        result = %s,
                        finished_at = NOW(),
                        duration_ms = COALESCE(%s, EXTRACT(EPOCH FROM (NOW() - started_at)) * 1000)::INTEGER,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (
                        status,
                        message,
                        error,
                        psycopg2.extras.Json(result) if result is not None else None,
                        duration_ms,
                        run_id,
                    ),
                )
                rowcount = cur.rowcount
            return rowcount > 0
        except Exception as exc:
            logger.warning("JobRunsStore.finish_run failed for run_id=%s: %s", run_id, exc)
            return False

    def record_completed_run(
        self,
        job_name: str,
        *,
        status: str,
        started_at: Any,
        finished_at: Optional[Any] = None,
        trigger_source: str = "extension",
        payload: Optional[Dict[str, Any]] = None,
        result: Optional[Dict[str, Any]] = None,
        message: Optional[str] = None,
        error: Optional[str] = None,
        duration_ms: Optional[int] = None,
    ) -> Optional[int]:
        """Insert a row that's already in a terminal state.

        Used by the Chrome extension: it only contacts native messaging
        AFTER a sync flow finishes, so we never see the ``running`` state.
        Caller-supplied ``started_at`` (and optional ``finished_at``)
        preserve the wall-clock the extension observed; ``duration_ms`` is
        computed server-side from the timestamps when not supplied.

        Returns the new run id, or ``None`` on error / unavailable store.
        """
        if status not in _VALID_STATUSES or status == "running":
            raise ValueError(f"record_completed_run requires terminal status, got {status!r}")
        if not self.is_available():
            return None
        if psycopg2 is None:  # pragma: no cover
            return None
        try:
            conn = self._backend._get_conn()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO job_runs (
                        job_name, status, trigger_source, payload, result,
                        message, error, started_at, finished_at, duration_ms
                    )
                    VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, COALESCE(%s, NOW()),
                        COALESCE(
                            %s,
                            EXTRACT(EPOCH FROM (COALESCE(%s::timestamptz, NOW()) - %s::timestamptz)) * 1000
                        )::INTEGER
                    )
                    RETURNING id
                    """,
                    (
                        job_name,
                        status,
                        trigger_source,
                        psycopg2.extras.Json(payload or {}),
                        psycopg2.extras.Json(result) if result is not None else None,
                        message,
                        error,
                        started_at,
                        finished_at,
                        duration_ms,
                        finished_at,
                        started_at,
                    ),
                )
                row = cur.fetchone()
            return int(row[0]) if row else None
        except Exception as exc:
            logger.warning(
                "JobRunsStore.record_completed_run failed for %s: %s", job_name, exc
            )
            return None

    # -- reads ---------------------------------------------------------------

    def list_runs(
        self,
        *,
        job_name: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Paginated history. Returns [] when unavailable or on error."""
        if not self.is_available():
            return []
        limit = max(1, min(int(limit), 200))
        offset = max(0, int(offset))
        try:
            conn = self._backend._get_conn()
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                if job_name:
                    cur.execute(
                        """
                        SELECT id, job_name, status, trigger_source, payload, result,
                               message, error, started_at, finished_at, duration_ms,
                               created_at, updated_at
                        FROM job_runs
                        WHERE job_name = %s
                        ORDER BY started_at DESC
                        LIMIT %s OFFSET %s
                        """,
                        (job_name, limit, offset),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id, job_name, status, trigger_source, payload, result,
                               message, error, started_at, finished_at, duration_ms,
                               created_at, updated_at
                        FROM job_runs
                        ORDER BY started_at DESC
                        LIMIT %s OFFSET %s
                        """,
                        (limit, offset),
                    )
                rows = cur.fetchall()
            return [_serialize_row(dict(r)) for r in rows]
        except Exception as exc:
            logger.warning("JobRunsStore.list_runs failed: %s", exc)
            return []

    def latest_runs_by_name(self) -> Dict[str, Dict[str, Any]]:
        """Return the most recent run per job_name as ``{name: row_dict}``.

        Used by ``/jobs/status`` to merge DB last-state with the static
        catalog. Returns an empty dict when unavailable or on error.
        """
        if not self.is_available():
            return {}
        try:
            conn = self._backend._get_conn()
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT DISTINCT ON (job_name)
                        id, job_name, status, trigger_source, payload, result,
                        message, error, started_at, finished_at, duration_ms,
                        created_at, updated_at
                    FROM job_runs
                    ORDER BY job_name, started_at DESC, id DESC
                    """
                )
                rows = cur.fetchall()
            return {r["job_name"]: _serialize_row(dict(r)) for r in rows}
        except Exception as exc:
            logger.warning("JobRunsStore.latest_runs_by_name failed: %s", exc)
            return {}

    def run_summary_by_name(self, job_names: List[str]) -> Dict[str, Dict[str, Any]]:
        """Return last successful and last terminal run timestamps per job."""
        names = [str(name) for name in job_names if str(name)]
        if not names or not self.is_available():
            return {}
        try:
            conn = self._backend._get_conn()
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT job_name,
                           MAX(finished_at) FILTER (WHERE status = 'succeeded')
                               AS last_success_at,
                           MAX(finished_at) AS last_any_at
                    FROM job_runs
                    WHERE job_name = ANY(%s)
                    GROUP BY job_name
                    """,
                    (names,),
                )
                rows = cur.fetchall()
            return {
                row["job_name"]: {
                    "last_success_at": _to_iso(row.get("last_success_at")),
                    "last_any_at": _to_iso(row.get("last_any_at")),
                }
                for row in rows
            }
        except Exception as exc:
            logger.warning("JobRunsStore.run_summary_by_name failed: %s", exc)
            return {}


class JobRunsLocalStore:
    """SQLite twin of ``JobRunsStore`` over local ``profile_state.db``."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 5000")
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            try:
                conn.execute("PRAGMA journal_mode = WAL")
            except sqlite3.OperationalError:
                pass
            conn.executescript(_SQLITE_SCHEMA)

    def is_available(self) -> bool:
        return True

    def create_run(
        self,
        job_name: str,
        *,
        trigger_source: str = "api",
        payload: Optional[Dict[str, Any]] = None,
    ) -> Optional[int]:
        now = _now_iso()
        try:
            with self._connect() as conn:
                cur = conn.execute(
                    """
                    INSERT INTO job_runs (
                        job_name, status, trigger_source, payload,
                        started_at, created_at, updated_at
                    )
                    VALUES (?, 'running', ?, ?, ?, ?, ?)
                    """,
                    (job_name, trigger_source, _json_dumps(payload), now, now, now),
                )
                return int(cur.lastrowid)
        except Exception as exc:
            logger.warning("JobRunsLocalStore.create_run failed for %s: %s", job_name, exc)
            return None

    def finish_run(
        self,
        run_id: Optional[int],
        *,
        status: str,
        message: Optional[str] = None,
        error: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[int] = None,
    ) -> bool:
        if run_id is None:
            return False
        if status not in _VALID_STATUSES:
            raise ValueError(f"invalid job status: {status!r}")
        if status == "running":
            raise ValueError("finish_run requires a terminal status")
        now = _now_iso()
        try:
            with self._connect() as conn:
                cur = conn.execute(
                    """
                    UPDATE job_runs
                    SET status=?,
                        message=?,
                        error=?,
                        result=?,
                        finished_at=?,
                        duration_ms=COALESCE(
                            ?,
                            CAST((julianday(?) - julianday(started_at)) * 86400000 AS INTEGER),
                            duration_ms
                        ),
                        updated_at=?
                    WHERE id=?
                    """,
                    (
                        status,
                        message,
                        error,
                        _json_or_none(result),
                        now,
                        duration_ms,
                        now,
                        now,
                        run_id,
                    ),
                )
                return cur.rowcount > 0
        except Exception as exc:
            logger.warning("JobRunsLocalStore.finish_run failed for run_id=%s: %s", run_id, exc)
            return False

    def record_completed_run(
        self,
        job_name: str,
        *,
        status: str,
        started_at: Any,
        finished_at: Optional[Any] = None,
        trigger_source: str = "extension",
        payload: Optional[Dict[str, Any]] = None,
        result: Optional[Dict[str, Any]] = None,
        message: Optional[str] = None,
        error: Optional[str] = None,
        duration_ms: Optional[int] = None,
        id: Optional[int] = None,
    ) -> Optional[int]:
        if status not in _VALID_STATUSES or status == "running":
            raise ValueError(f"record_completed_run requires terminal status, got {status!r}")
        now = _now_iso()
        started = _to_iso(started_at)
        finished = _to_iso(finished_at) or now
        columns = ["job_name", "status", "trigger_source", "payload", "result",
                   "message", "error", "started_at", "finished_at", "duration_ms",
                   "created_at", "updated_at"]
        values: List[Any] = [
            job_name,
            status,
            trigger_source,
            _json_dumps(payload),
            _json_or_none(result),
            message,
            error,
            started,
            finished,
            duration_ms,
            now,
            now,
        ]
        if id is not None:
            columns.insert(0, "id")
            values.insert(0, id)
        placeholders = ",".join("?" for _ in columns)
        try:
            with self._connect() as conn:
                cur = conn.execute(
                    f"INSERT INTO job_runs ({','.join(columns)}) VALUES ({placeholders})",
                    values,
                )
                return int(id if id is not None else cur.lastrowid)
        except Exception as exc:
            logger.warning(
                "JobRunsLocalStore.record_completed_run failed for %s: %s",
                job_name,
                exc,
            )
            return None

    def list_runs(
        self,
        *,
        job_name: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        limit = max(1, min(int(limit), 200))
        offset = max(0, int(offset))
        try:
            with self._connect() as conn:
                if job_name:
                    rows = conn.execute(
                        """
                        SELECT id, job_name, status, trigger_source, payload, result,
                               message, error, started_at, finished_at, duration_ms,
                               created_at, updated_at
                        FROM job_runs
                        WHERE job_name=?
                        ORDER BY started_at DESC, id DESC
                        LIMIT ? OFFSET ?
                        """,
                        (job_name, limit, offset),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT id, job_name, status, trigger_source, payload, result,
                               message, error, started_at, finished_at, duration_ms,
                               created_at, updated_at
                        FROM job_runs
                        ORDER BY started_at DESC, id DESC
                        LIMIT ? OFFSET ?
                        """,
                        (limit, offset),
                    ).fetchall()
            return [_serialize_local_row(dict(row)) for row in rows]
        except Exception as exc:
            logger.warning("JobRunsLocalStore.list_runs failed: %s", exc)
            return []

    def latest_runs_by_name(self) -> Dict[str, Dict[str, Any]]:
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT id, job_name, status, trigger_source, payload, result,
                           message, error, started_at, finished_at, duration_ms,
                           created_at, updated_at
                    FROM job_runs
                    ORDER BY job_name, started_at DESC, id DESC
                    """
                ).fetchall()
            latest: Dict[str, Dict[str, Any]] = {}
            for row in rows:
                d = dict(row)
                if d["job_name"] not in latest:
                    latest[d["job_name"]] = _serialize_local_row(d)
            return latest
        except Exception as exc:
            logger.warning("JobRunsLocalStore.latest_runs_by_name failed: %s", exc)
            return {}

    def run_summary_by_name(self, job_names: List[str]) -> Dict[str, Dict[str, Any]]:
        names = [str(name) for name in job_names if str(name)]
        if not names:
            return {}
        placeholders = ",".join("?" for _ in names)
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    f"""
                    SELECT job_name,
                           MAX(CASE WHEN status = 'succeeded' THEN finished_at END)
                               AS last_success_at,
                           MAX(finished_at) AS last_any_at
                    FROM job_runs
                    WHERE job_name IN ({placeholders})
                    GROUP BY job_name
                    """,
                    names,
                ).fetchall()
            return {
                row["job_name"]: {
                    "last_success_at": row["last_success_at"],
                    "last_any_at": row["last_any_at"],
                }
                for row in rows
            }
        except Exception as exc:
            logger.warning("JobRunsLocalStore.run_summary_by_name failed: %s", exc)
            return {}


def _serialize_local_row(row: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(row)
    out["payload"] = _json_load(out.get("payload")) or {}
    out["result"] = _json_load(out.get("result"))
    return out


def _env_truthy(value: Optional[str]) -> Optional[bool]:
    if value is None:
        return None
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _local_job_runs_enabled(dal: Any) -> bool:
    checker = getattr(dal, "_profile_setting_truthy", None)
    if callable(checker):
        value = checker(USE_LOCAL_JOB_RUNS_KEY, ENV_USE_LOCAL_JOB_RUNS)
        if isinstance(value, bool):
            return value
        return _env_truthy(str(value)) is True
    env = _env_truthy(os.environ.get(ENV_USE_LOCAL_JOB_RUNS))
    return bool(env)


def get_job_runs_store(dal: Any):
    """Return the active job-runs store.

    The default remains PG-backed until the S-H1 migration apply flips
    ``use_local_job_runs``. Explicit false is the rollback lever until N9.
    """
    if _local_job_runs_enabled(dal):
        from src.app_records_store import resolve_profile_state_db_path

        return JobRunsLocalStore(resolve_profile_state_db_path(dal))
    return JobRunsStore(dal)


def _serialize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Serialize psycopg2 row dict for JSON-safe transport.

    psycopg2 returns ``datetime`` objects for TIMESTAMPTZ columns; the
    API response models use ISO 8601 strings. Convert here so callers
    don't have to.
    """
    out = dict(row)
    for key in ("started_at", "finished_at", "created_at", "updated_at"):
        v = out.get(key)
        if v is not None and hasattr(v, "isoformat"):
            out[key] = v.isoformat()
    return out
