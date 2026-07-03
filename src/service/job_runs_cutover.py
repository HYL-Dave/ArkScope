"""S-H1 job_runs PG-to-local cutover preview/apply helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any

from src.app_records_migrate import backup_profile_state_db
from src.service.job_runs_store import (
    USE_LOCAL_JOB_RUNS_KEY,
    _SQLITE_SCHEMA as SQLITE_JOB_RUNS_SCHEMA,
)


_JOB_RUN_COLUMNS = (
    "id",
    "job_name",
    "status",
    "trigger_source",
    "payload",
    "result",
    "message",
    "error",
    "started_at",
    "finished_at",
    "duration_ms",
    "created_at",
    "updated_at",
)

_PROFILE_SETTINGS_SCHEMA = """
CREATE TABLE IF NOT EXISTS profile_settings (
    key        TEXT PRIMARY KEY,
    value      TEXT,
    updated_at TEXT NOT NULL
);
"""

_MIGRATION_RUNS_SCHEMA = """
CREATE TABLE IF NOT EXISTS job_runs_migration_runs (
    id INTEGER PRIMARY KEY,
    fingerprint TEXT NOT NULL UNIQUE,
    counts_json TEXT NOT NULL,
    backup_path TEXT NOT NULL,
    applied_at TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class JobRunsCutoverPreviewReport:
    fingerprint: str
    pg_rows: int
    local_rows: int
    latest_started_at: str | None
    status_counts: dict[str, int]
    job_name_counts: dict[str, int]
    post_preview_pg_rows: int
    post_preview_growth: int
    blockers: list[str]
    would_apply: bool

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "blockers": self.blockers,
            "fingerprint": self.fingerprint,
            "job_name_counts": self.job_name_counts,
            "latest_started_at": self.latest_started_at,
            "local_rows": self.local_rows,
            "pg_rows": self.pg_rows,
            "post_preview_growth": self.post_preview_growth,
            "post_preview_pg_rows": self.post_preview_pg_rows,
            "status_counts": self.status_counts,
            "would_apply": self.would_apply,
        }


@dataclass(frozen=True)
class JobRunsCutoverApplyResult:
    fingerprint: str
    inserted: int
    already_applied: bool
    backup_path: str

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "already_applied": self.already_applied,
            "backup_path": self.backup_path,
            "fingerprint": self.fingerprint,
            "inserted": self.inserted,
        }


class JobRunsCutoverBlocked(RuntimeError):
    """Raised when the reviewed job_runs cutover gate cannot safely proceed."""


def preview_job_runs_cutover(
    profile_db: str | Path, pg_dsn: str
) -> JobRunsCutoverPreviewReport:
    """Return a deterministic, no-create preview for S-H1 job_runs migration."""
    report, _source_rows = _build_preview_state(profile_db, pg_dsn)
    return report


def _build_preview_state(
    profile_db: str | Path, pg_dsn: str
) -> tuple[JobRunsCutoverPreviewReport, tuple[dict[str, Any], ...]]:
    source_rows = tuple(_canonical_row(row) for row in read_pg_job_runs(pg_dsn))
    local_rows = tuple(read_local_job_runs(profile_db))
    post_rows = tuple(read_pg_job_runs(pg_dsn))
    return (
        _report_from_rows(
            source_rows,
            local_rows,
            post_preview_pg_rows=len(post_rows),
        ),
        source_rows,
    )


def apply_job_runs_cutover(
    profile_db: str | Path,
    *,
    pg_dsn: str,
    expected_fingerprint: str,
    backup_path: str | Path,
) -> JobRunsCutoverApplyResult:
    """Apply the reviewed S-H1 job_runs migration to profile_state.db."""
    profile_db = Path(profile_db)
    backup_path = Path(backup_path)
    report, _ = _build_preview_state(profile_db, pg_dsn)
    _require_expected_fingerprint(report.fingerprint, expected_fingerprint)
    _require_applyable(report)
    if _migration_run_exists(profile_db, expected_fingerprint):
        return JobRunsCutoverApplyResult(
            fingerprint=expected_fingerprint,
            inserted=0,
            already_applied=True,
            backup_path=str(backup_path),
        )

    created_backup = backup_profile_state_db(str(profile_db), str(backup_path))
    if created_backup is None:
        raise FileNotFoundError(f"profile DB does not exist: {profile_db}")

    post_backup_report, source_rows = _build_preview_state(profile_db, pg_dsn)
    _require_expected_fingerprint(post_backup_report.fingerprint, expected_fingerprint)
    _require_applyable(post_backup_report)

    conn = sqlite3.connect(profile_db)
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.executescript(SQLITE_JOB_RUNS_SCHEMA)
        conn.executescript(_PROFILE_SETTINGS_SCHEMA)
        conn.executescript(_MIGRATION_RUNS_SCHEMA)
        inserted = _insert_job_run_rows(conn, source_rows)
        counts_json = json.dumps(report.to_json_dict(), sort_keys=True, separators=(",", ":"))
        now = _utc_now()
        conn.execute(
            "INSERT INTO job_runs_migration_runs "
            "(fingerprint,counts_json,backup_path,applied_at) VALUES (?,?,?,?)",
            (expected_fingerprint, counts_json, str(backup_path), now),
        )
        conn.execute(
            "INSERT INTO profile_settings (key,value,updated_at) VALUES (?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, "
            "updated_at=excluded.updated_at",
            (USE_LOCAL_JOB_RUNS_KEY, "true", now),
        )
        validate_applied_job_runs_plan(conn, source_rows, expected_fingerprint)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    conn = _open_read_only(profile_db)
    try:
        validate_applied_job_runs_plan(conn, source_rows, expected_fingerprint)
    finally:
        conn.close()
    return JobRunsCutoverApplyResult(
        fingerprint=expected_fingerprint,
        inserted=inserted,
        already_applied=False,
        backup_path=str(backup_path),
    )


def validate_applied_job_runs_plan(
    conn: sqlite3.Connection, rows: tuple[dict[str, Any], ...], fingerprint: str
) -> None:
    actual_rows = conn.execute("SELECT COUNT(*) FROM job_runs").fetchone()[0]
    if actual_rows != len(rows):
        raise JobRunsCutoverBlocked(
            f"job_runs row count mismatch: {actual_rows} != {len(rows)}"
        )
    if rows:
        max_id = max(int(row["id"]) for row in rows)
        actual_max = conn.execute("SELECT MAX(id) FROM job_runs").fetchone()[0]
        if int(actual_max or 0) != max_id:
            raise JobRunsCutoverBlocked(
                f"job_runs max id mismatch: {actual_max} != {max_id}"
            )
    audit = conn.execute(
        "SELECT COUNT(*) FROM job_runs_migration_runs WHERE fingerprint=?",
        (fingerprint,),
    ).fetchone()[0]
    if audit != 1:
        raise JobRunsCutoverBlocked("job_runs migration audit row missing")
    setting = conn.execute(
        "SELECT value FROM profile_settings WHERE key=?",
        (USE_LOCAL_JOB_RUNS_KEY,),
    ).fetchone()
    if setting is None or setting[0] != "true":
        raise JobRunsCutoverBlocked("use_local_job_runs profile setting was not enabled")


def read_pg_job_runs(pg_dsn: str) -> tuple[dict[str, Any], ...]:
    """Read PG job_runs rows as JSON-safe dicts."""
    import psycopg2
    import psycopg2.extras

    conn = psycopg2.connect(pg_dsn)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id,job_name,status,trigger_source,payload,result,message,error,"
                "started_at,finished_at,duration_ms,created_at,updated_at "
                "FROM job_runs ORDER BY id"
            )
            return tuple(_canonical_row(dict(row)) for row in cur.fetchall())
    finally:
        conn.close()


def read_local_job_runs(profile_db: str | Path) -> tuple[dict[str, Any], ...]:
    path = Path(profile_db)
    if not path.exists():
        return ()
    conn = _open_read_only(path)
    try:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='job_runs'"
        ).fetchone()
        if not exists:
            return ()
        rows = conn.execute(
            "SELECT id,job_name,status,trigger_source,payload,result,message,error,"
            "started_at,finished_at,duration_ms,created_at,updated_at "
            "FROM job_runs ORDER BY id"
        ).fetchall()
        return tuple(_canonical_row(dict(row)) for row in rows)
    finally:
        conn.close()


def _report_from_rows(
    source_rows: tuple[dict[str, Any], ...],
    local_rows: tuple[dict[str, Any], ...],
    *,
    post_preview_pg_rows: int,
) -> JobRunsCutoverPreviewReport:
    status_counts: dict[str, int] = {}
    job_name_counts: dict[str, int] = {}
    latest_started_at = None
    for row in source_rows:
        status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
        job_name_counts[row["job_name"]] = job_name_counts.get(row["job_name"], 0) + 1
        started_at = row.get("started_at")
        if started_at and (latest_started_at is None or started_at > latest_started_at):
            latest_started_at = started_at

    blockers = _local_subset_blockers(source_rows, local_rows)
    fingerprint = hashlib.sha256(
        json.dumps(source_rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return JobRunsCutoverPreviewReport(
        fingerprint=fingerprint,
        pg_rows=len(source_rows),
        local_rows=len(local_rows),
        latest_started_at=latest_started_at,
        status_counts=dict(sorted(status_counts.items())),
        job_name_counts=dict(sorted(job_name_counts.items())),
        post_preview_pg_rows=post_preview_pg_rows,
        post_preview_growth=max(0, post_preview_pg_rows - len(source_rows)),
        blockers=blockers,
        would_apply=not blockers,
    )


def _local_subset_blockers(
    source_rows: tuple[dict[str, Any], ...],
    local_rows: tuple[dict[str, Any], ...],
) -> list[str]:
    source_by_id = {int(row["id"]): row for row in source_rows}
    blockers: list[str] = []
    for local in local_rows:
        row_id = int(local["id"])
        source = source_by_id.get(row_id)
        if source is None:
            blockers.append(f"local row id {row_id} is absent from PG source")
        elif local != source:
            blockers.append(f"local row differs from PG source for id {row_id}")
    return blockers


def _insert_job_run_rows(
    conn: sqlite3.Connection, rows: tuple[dict[str, Any], ...]
) -> int:
    inserted = 0
    for row in rows:
        cur = conn.execute(
            "INSERT OR IGNORE INTO job_runs "
            "(id,job_name,status,trigger_source,payload,result,message,error,"
            "started_at,finished_at,duration_ms,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            tuple(_sqlite_value(row[column]) for column in _JOB_RUN_COLUMNS),
        )
        inserted += cur.rowcount
    return inserted


def _migration_run_exists(profile_db: Path, fingerprint: str) -> bool:
    if not profile_db.exists():
        return False
    conn = _open_read_only(profile_db)
    try:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name='job_runs_migration_runs'"
        ).fetchone()
        if not exists:
            return False
        return (
            conn.execute(
                "SELECT 1 FROM job_runs_migration_runs WHERE fingerprint=?",
                (fingerprint,),
            ).fetchone()
            is not None
        )
    finally:
        conn.close()


def _require_expected_fingerprint(current: str, expected: str) -> None:
    if current != expected:
        raise JobRunsCutoverBlocked(
            f"job_runs cutover fingerprint mismatch: {current} != {expected}"
        )


def _require_applyable(report: JobRunsCutoverPreviewReport) -> None:
    if report.blockers:
        raise JobRunsCutoverBlocked(
            "job_runs cutover blocked: " + "; ".join(report.blockers)
        )


def _canonical_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "job_name": str(row["job_name"]),
        "status": str(row["status"]),
        "trigger_source": str(row.get("trigger_source") or "api"),
        "payload": _json_value(row.get("payload")) or {},
        "result": _json_value(row.get("result")),
        "message": row.get("message"),
        "error": row.get("error"),
        "started_at": _time_text(row.get("started_at")),
        "finished_at": _time_text(row.get("finished_at")),
        "duration_ms": None if row.get("duration_ms") is None else int(row["duration_ms"]),
        "created_at": _time_text(row.get("created_at")),
        "updated_at": _time_text(row.get("updated_at")),
    }


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return value


def _sqlite_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return value


def _time_text(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    text = str(value).strip()
    return text.replace("Z", "+00:00") if text.endswith("Z") else text


def _open_read_only(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{Path(path)}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
