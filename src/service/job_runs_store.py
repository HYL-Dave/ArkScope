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

import logging
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