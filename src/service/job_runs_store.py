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
  - **No general same-name concurrency control**: ordinary jobs may overlap.
    The audited ``sa_market_news_repair`` domain is the explicit exception and
    uses one ``BEGIN IMMEDIATE`` start-or-return-running transaction.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Literal, Optional

logger = logging.getLogger(__name__)

_VALID_STATUSES = frozenset({"running", "succeeded", "failed"})
USE_LOCAL_JOB_RUNS_KEY = "use_local_job_runs"
ENV_USE_LOCAL_JOB_RUNS = "ARKSCOPE_USE_LOCAL_JOB_RUNS"
_EXTENSION_EVENT_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_MARKET_NEWS_REPAIR_JOB_NAME = "sa_market_news_repair"
_SA_EXTENSION_DIAGNOSTIC_JOB_NAMES = frozenset(
    {
        "sa_alpha_picks_refresh",
        "sa_extension:manual_fetch",
        "sa_market_news_refresh",
        "sa_market_news_retry_recorded",
        "sa_market_news_incident_recovery",
    }
)

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


def _canonical_repair_manifest_hash(manifest: Any) -> str:
    if not isinstance(manifest, dict):
        raise ValueError("manifest_invalid")
    return __import__("hashlib").sha256(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _validate_repair_payload(payload: Any, expected_hash: str) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("manifest_invalid")
    manifest = payload.get("manifest")
    stored_hash = payload.get("manifest_hash")
    if (
        not _EXTENSION_EVENT_HASH_RE.fullmatch(str(expected_hash or ""))
        or stored_hash != expected_hash
        or _canonical_repair_manifest_hash(manifest) != expected_hash
    ):
        raise ValueError("manifest_invalid")
    return payload


JobActivityEvidence = Literal["none", "present", "unknown"]


def read_job_activity_if_exists(
    db_path: str | Path,
    job_names: Iterable[str],
) -> JobActivityEvidence:
    """Read whether any named job exists without creating or changing storage."""
    path = Path(db_path).expanduser()
    if not os.path.lexists(path):
        return "none"
    if not path.is_file():
        return "unknown"

    names = tuple(sorted({str(name) for name in job_names if str(name)}))
    if not names:
        return "none"

    conn: Optional[sqlite3.Connection] = None
    try:
        conn = sqlite3.connect(
            f"{path.resolve().as_uri()}?mode=ro",
            uri=True,
            timeout=5.0,
        )
        table = conn.execute(
            "SELECT 1 FROM sqlite_master "
            "WHERE type='table' AND name='job_runs'"
        ).fetchone()
        if table is None:
            return "none"
        placeholders = ",".join("?" for _ in names)
        row = conn.execute(
            f"SELECT 1 FROM job_runs WHERE job_name IN ({placeholders}) LIMIT 1",
            names,
        ).fetchone()
        return "present" if row is not None else "none"
    except sqlite3.Error:
        return "unknown"
    finally:
        if conn is not None:
            conn.close()


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

    def record_extension_event_once(
        self,
        *,
        client_event_id: str,
        event_hash: str,
        job_name: str,
        status: str,
        started_at: Any,
        finished_at: Any,
        result: Dict[str, Any],
        duration_ms: Optional[int],
        extension_diagnostics: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Atomically deduplicate and persist one structured extension event."""

        from src.sa.extension_diagnostics import (
            is_durable_diagnostics_projection,
        )

        event_id = str(client_event_id or "").strip()
        fingerprint = str(event_hash or "").strip().lower()
        if (
            not event_id
            or not _EXTENSION_EVENT_HASH_RE.fullmatch(fingerprint)
            or status not in {"succeeded", "failed"}
            or not isinstance(result, dict)
            or result.get("job_name") != job_name
            or result.get("db_status") != status
            or (
                extension_diagnostics is not None
                and not is_durable_diagnostics_projection(extension_diagnostics)
            )
        ):
            raise ValueError("invalid_extension_event")
        started = _to_iso(started_at)
        finished = _to_iso(finished_at)
        if not started or not finished:
            raise ValueError("invalid_extension_event")

        identity = {
            "client_event_id": event_id,
            "event_hash": fingerprint,
        }
        payload = {"extension_event": identity}
        if extension_diagnostics is not None:
            payload["extension_diagnostics"] = json.loads(
                json.dumps(extension_diagnostics, sort_keys=True)
            )
        now = _now_iso()
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            rows = conn.execute(
                """
                SELECT id, payload
                FROM job_runs
                WHERE trigger_source = 'extension'
                ORDER BY id DESC
                """
            ).fetchall()
            for row in rows:
                existing_payload = _json_load(row["payload"])
                existing = (
                    existing_payload.get("extension_event")
                    if isinstance(existing_payload, dict)
                    else None
                )
                if not isinstance(existing, dict):
                    continue
                if existing.get("client_event_id") != event_id:
                    continue
                if existing.get("event_hash") != fingerprint:
                    raise ValueError("event_conflict")
                conn.commit()
                return int(row["id"])

            cur = conn.execute(
                """
                INSERT INTO job_runs (
                    job_name, status, trigger_source, payload, result,
                    message, error, started_at, finished_at, duration_ms,
                    created_at, updated_at
                )
                VALUES (?, ?, 'extension', ?, ?, ?, NULL, ?, ?, ?, ?, ?)
                """,
                (
                    job_name,
                    status,
                    _json_dumps(payload),
                    _json_or_none(result),
                    str(result.get("derived_outcome") or ""),
                    started,
                    finished,
                    duration_ms,
                    now,
                    now,
                ),
            )
            run_id = int(cur.lastrowid)
            conn.commit()
            return run_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def completed_extension_runs_by_name(
        self,
        job_names: Optional[Iterable[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Read at most 20 completed allowlisted extension runs without writes."""

        requested = (
            _SA_EXTENSION_DIAGNOSTIC_JOB_NAMES
            if job_names is None
            else frozenset(str(name) for name in job_names)
            & _SA_EXTENSION_DIAGNOSTIC_JOB_NAMES
        )
        names = tuple(sorted(requested))
        path = Path(self.db_path).expanduser()
        if not names or not os.path.lexists(path) or not path.is_file():
            return []

        conn: Optional[sqlite3.Connection] = None
        try:
            conn = sqlite3.connect(
                f"{path.resolve().as_uri()}?mode=ro",
                uri=True,
                timeout=5.0,
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA query_only = ON")
            placeholders = ",".join("?" for _ in names)
            rows = conn.execute(
                f"""
                SELECT id, job_name, status, trigger_source, payload, result,
                       message, error, started_at, finished_at, duration_ms,
                       created_at, updated_at
                FROM job_runs
                WHERE trigger_source = 'extension'
                  AND status IN ('succeeded', 'failed')
                  AND job_name IN ({placeholders})
                ORDER BY started_at DESC, id DESC
                LIMIT 20
                """,
                names,
            ).fetchall()
            return [_serialize_local_row(dict(row)) for row in rows]
        except sqlite3.Error as exc:
            logger.warning(
                "JobRunsLocalStore.completed_extension_runs_by_name failed: %s",
                exc,
            )
            return []
        finally:
            if conn is not None:
                conn.close()

    def start_market_news_repair(
        self, *, manifest: Dict[str, Any], manifest_hash: str
    ) -> Dict[str, Any]:
        """Atomically create one repair or return the actual running manifest."""

        fingerprint = str(manifest_hash or "").lower()
        if _canonical_repair_manifest_hash(manifest) != fingerprint:
            raise ValueError("manifest_invalid")
        payload = {"manifest": manifest, "manifest_hash": fingerprint}
        now = _now_iso()
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                """
                SELECT id, job_name, status, trigger_source, payload, result,
                       message, error, started_at, finished_at, duration_ms,
                       created_at, updated_at
                FROM job_runs
                WHERE job_name=? AND status='running'
                ORDER BY id DESC LIMIT 1
                """,
                (_MARKET_NEWS_REPAIR_JOB_NAME,),
            ).fetchone()
            if existing is not None:
                row = _serialize_local_row(dict(existing))
                _validate_repair_payload(
                    row.get("payload"), row.get("payload", {}).get("manifest_hash", "")
                )
                conn.commit()
                return {"created": False, "run": row}

            initial_result = {
                "schema_version": 1,
                "lifecycle_state": "running",
                "manifest_hash": fingerprint,
                "progress": {"attempts": []},
                "resumable": True,
            }
            cur = conn.execute(
                """
                INSERT INTO job_runs (
                    job_name, status, trigger_source, payload, result, message,
                    error, started_at, created_at, updated_at
                )
                VALUES (?, 'running', 'extension', ?, ?, 'running', NULL, ?, ?, ?)
                """,
                (
                    _MARKET_NEWS_REPAIR_JOB_NAME,
                    _json_dumps(payload),
                    _json_or_none(initial_result),
                    now,
                    now,
                    now,
                ),
            )
            run_id = int(cur.lastrowid)
            row = conn.execute(
                """
                SELECT id, job_name, status, trigger_source, payload, result,
                       message, error, started_at, finished_at, duration_ms,
                       created_at, updated_at
                FROM job_runs WHERE id=?
                """,
                (run_id,),
            ).fetchone()
            conn.commit()
            return {"created": True, "run": _serialize_local_row(dict(row))}
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_market_news_repair(self, run_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Return one full repair machine row for the fixed repair API only."""

        with self._connect() as conn:
            if run_id is None:
                row = conn.execute(
                    """
                    SELECT id, job_name, status, trigger_source, payload, result,
                           message, error, started_at, finished_at, duration_ms,
                           created_at, updated_at
                    FROM job_runs WHERE job_name=?
                    ORDER BY id DESC LIMIT 1
                    """,
                    (_MARKET_NEWS_REPAIR_JOB_NAME,),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT id, job_name, status, trigger_source, payload, result,
                           message, error, started_at, finished_at, duration_ms,
                           created_at, updated_at
                    FROM job_runs WHERE job_name=? AND id=?
                    """,
                    (_MARKET_NEWS_REPAIR_JOB_NAME, int(run_id)),
                ).fetchone()
        return _serialize_local_row(dict(row)) if row is not None else None

    def checkpoint_market_news_repair(
        self,
        *,
        run_id: int,
        manifest_hash: str,
        attempt: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Merge one idempotent `(news_id, attempt_id)` repair checkpoint."""

        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            raw = conn.execute(
                "SELECT * FROM job_runs WHERE id=? AND job_name=?",
                (int(run_id), _MARKET_NEWS_REPAIR_JOB_NAME),
            ).fetchone()
            if raw is None:
                raise ValueError("repair_not_found")
            row = _serialize_local_row(dict(raw))
            payload = _validate_repair_payload(row["payload"], manifest_hash)
            if row["status"] != "running":
                raise ValueError("repair_not_running")
            target_ids = {
                item.get("news_id")
                for item in payload["manifest"].get("targets", [])
                if isinstance(item, dict)
            }
            if attempt.get("news_id") not in target_ids:
                raise ValueError("target_not_in_manifest")

            result = row.get("result") if isinstance(row.get("result"), dict) else {}
            progress = result.get("progress") if isinstance(result.get("progress"), dict) else {}
            attempts = progress.get("attempts") if isinstance(progress.get("attempts"), list) else []
            identity = (attempt.get("news_id"), attempt.get("attempt_id"))
            for existing in attempts:
                if (existing.get("news_id"), existing.get("attempt_id")) != identity:
                    continue
                if existing != attempt:
                    raise ValueError("checkpoint_conflict")
                conn.commit()
                return row

            next_attempts = [*attempts, attempt]
            next_attempts.sort(key=lambda value: (value["news_id"], value["attempt_id"]))
            next_result = {
                "schema_version": 1,
                "lifecycle_state": "running",
                "manifest_hash": manifest_hash,
                "progress": {"attempts": next_attempts},
                "resumable": True,
            }
            now = _now_iso()
            conn.execute(
                "UPDATE job_runs SET result=?, message='running', updated_at=? WHERE id=?",
                (_json_or_none(next_result), now, int(run_id)),
            )
            updated = conn.execute("SELECT * FROM job_runs WHERE id=?", (int(run_id),)).fetchone()
            conn.commit()
            return _serialize_local_row(dict(updated))
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def mark_market_news_repair_interrupted(
        self, *, run_id: int, manifest_hash: str
    ) -> Dict[str, Any]:
        """Mark a stale running repair resumable without terminalizing its row."""

        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            raw = conn.execute(
                "SELECT * FROM job_runs WHERE id=? AND job_name=?",
                (int(run_id), _MARKET_NEWS_REPAIR_JOB_NAME),
            ).fetchone()
            if raw is None:
                raise ValueError("repair_not_found")
            row = _serialize_local_row(dict(raw))
            _validate_repair_payload(row["payload"], manifest_hash)
            if row["status"] != "running":
                raise ValueError("repair_not_running")
            result = row.get("result") if isinstance(row.get("result"), dict) else {}
            next_result = {
                **result,
                "schema_version": 1,
                "lifecycle_state": "interrupted",
                "manifest_hash": manifest_hash,
                "resumable": True,
                "progress": result.get("progress", {"attempts": []}),
            }
            now = _now_iso()
            conn.execute(
                "UPDATE job_runs SET result=?, message='interrupted', updated_at=? WHERE id=?",
                (_json_or_none(next_result), now, int(run_id)),
            )
            updated = conn.execute("SELECT * FROM job_runs WHERE id=?", (int(run_id),)).fetchone()
            conn.commit()
            return _serialize_local_row(dict(updated))
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def finish_market_news_repair(
        self,
        *,
        run_id: int,
        manifest_hash: str,
        status: str,
        result: Dict[str, Any],
        error_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Atomically terminalize one repair, with result-hash idempotence."""

        if status not in {"succeeded", "failed"}:
            raise ValueError("invalid_repair_status")
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            raw = conn.execute(
                "SELECT * FROM job_runs WHERE id=? AND job_name=?",
                (int(run_id), _MARKET_NEWS_REPAIR_JOB_NAME),
            ).fetchone()
            if raw is None:
                raise ValueError("repair_not_found")
            row = _serialize_local_row(dict(raw))
            _validate_repair_payload(row["payload"], manifest_hash)
            if row["status"] != "running":
                existing_hash = (
                    row.get("result", {}).get("result_hash")
                    if isinstance(row.get("result"), dict)
                    else None
                )
                if existing_hash == result.get("result_hash"):
                    conn.commit()
                    return row
                raise ValueError("repair_not_running")
            now = _now_iso()
            conn.execute(
                """
                UPDATE job_runs
                SET status=?, result=?, message=?, error=?, finished_at=?,
                    duration_ms=CAST((julianday(?) - julianday(started_at)) * 86400000 AS INTEGER),
                    updated_at=?
                WHERE id=?
                """,
                (
                    status,
                    _json_or_none(result),
                    str(result.get("derived_outcome") or result.get("lifecycle_state") or ""),
                    error_code,
                    now,
                    now,
                    now,
                    int(run_id),
                ),
            )
            updated = conn.execute("SELECT * FROM job_runs WHERE id=?", (int(run_id),)).fetchone()
            conn.commit()
            return _serialize_local_row(dict(updated))
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def list_runs(
        self,
        *,
        job_name: Optional[str] = None,
        trigger_source: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        limit = max(1, min(int(limit), 200))
        offset = max(0, int(offset))
        try:
            with self._connect() as conn:
                where: List[str] = []
                params: List[Any] = []
                if job_name:
                    where.append("job_name=?")
                    params.append(job_name)
                if trigger_source:
                    where.append("trigger_source=?")
                    params.append(trigger_source)
                where_sql = f"WHERE {' AND '.join(where)}" if where else ""
                rows = conn.execute(
                    f"""
                    SELECT id, job_name, status, trigger_source, payload, result,
                           message, error, started_at, finished_at, duration_ms,
                           created_at, updated_at
                    FROM job_runs
                    {where_sql}
                    ORDER BY started_at DESC, id DESC
                    LIMIT ? OFFSET ?
                    """,
                    (*params, limit, offset),
                ).fetchall()
            return [_serialize_local_row(dict(row)) for row in rows]
        except Exception as exc:
            logger.warning("JobRunsLocalStore.list_runs failed: %s", exc)
            return []

    def get_runs_by_ids(
        self, *, job_name: str, run_ids: List[int]
    ) -> List[Dict[str, Any]]:
        """Read exact historical runs without coupling identity to pagination."""

        ids = sorted({int(value) for value in run_ids if int(value) > 0})
        if not ids:
            return []
        try:
            found: List[sqlite3.Row] = []
            with self._connect() as conn:
                for start in range(0, len(ids), 500):
                    chunk = ids[start : start + 500]
                    placeholders = ",".join("?" for _ in chunk)
                    found.extend(
                        conn.execute(
                            f"""
                            SELECT id, job_name, status, trigger_source, payload, result,
                                   message, error, started_at, finished_at, duration_ms,
                                   created_at, updated_at
                            FROM job_runs
                            WHERE job_name=? AND id IN ({placeholders})
                            """,
                            (job_name, *chunk),
                        ).fetchall()
                    )
            found.sort(
                key=lambda row: (str(row["started_at"]), int(row["id"])),
                reverse=True,
            )
            return [_serialize_local_row(dict(row)) for row in found]
        except Exception as exc:
            logger.warning("JobRunsLocalStore.get_runs_by_ids failed: %s", exc)
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

    def run_summary_by_name(self, job_names: List[str]) -> Optional[Dict[str, Dict[str, Any]]]:
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
            return None

    def structured_extension_summary_by_name(
        self, job_names: List[str]
    ) -> Optional[Dict[str, Dict[str, Any]]]:
        """Return latest structured attempt and derived-complete run by capture time."""

        names = [str(name) for name in job_names if str(name)]
        if not names:
            return {}
        placeholders = ",".join("?" for _ in names)
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    f"""
                    SELECT id, job_name, status, trigger_source, payload, result,
                           message, error, started_at, finished_at, duration_ms,
                           created_at, updated_at
                    FROM job_runs
                    WHERE trigger_source = 'extension'
                      AND job_name IN ({placeholders})
                    ORDER BY started_at DESC, id DESC
                    """,
                    names,
                ).fetchall()
            summary: Dict[str, Dict[str, Any]] = {}
            for raw_row in rows:
                row = _serialize_local_row(dict(raw_row))
                identity = row.get("payload", {}).get("extension_event")
                result = row.get("result")
                if not isinstance(identity, dict) or not isinstance(result, dict):
                    continue
                if not identity.get("client_event_id") or not identity.get("event_hash"):
                    continue
                item = summary.setdefault(
                    row["job_name"],
                    {"latest_attempt": None, "latest_derived_complete": None},
                )
                if item["latest_attempt"] is None:
                    item["latest_attempt"] = row
                if (
                    item["latest_derived_complete"] is None
                    and result.get("derived_outcome") == "complete"
                    and result.get("healthy_anchor_eligible") is True
                ):
                    item["latest_derived_complete"] = row
            return summary
        except Exception as exc:
            logger.warning(
                "JobRunsLocalStore.structured_extension_summary_by_name failed: %s",
                exc,
            )
            return None


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
    """Return the post-N9 effective routing state.

    The legacy profile/env value is still read when available so existing
    provenance tests and diagnostics can observe it, but false no longer routes
    runtime writes back to PG.
    """
    checker = getattr(dal, "_profile_setting_truthy", None)
    if callable(checker):
        checker(USE_LOCAL_JOB_RUNS_KEY, ENV_USE_LOCAL_JOB_RUNS)
    return True


def get_job_runs_store(dal: Any):
    """Return the post-N9 local job-runs store.

    Explicit false is retained only as a historical rollback/provenance value.
    Runtime writes and reads use ``profile_state.db``.
    """
    _local_job_runs_enabled(dal)
    from src.app_records_store import resolve_profile_state_db_path

    return JobRunsLocalStore(resolve_profile_state_db_path(dal))
