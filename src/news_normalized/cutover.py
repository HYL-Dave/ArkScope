"""Immutable preview and audit gate for the N8a news PostgreSQL exit."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from typing import Any, Mapping

from src.market_data_direct import backup_market_db, market_write_lock
from src.profile_state import ProfileStateStore

from .routing import NEWS_PG_EXIT_COMPLETED_KEY, USE_NORMALIZED_NEWS_WRITES_KEY
from .schema import begin_news_normalized_schema_transaction


class CutoverBlocked(RuntimeError):
    """Raised when the reviewed PG-exit gate cannot safely proceed."""


REQUIRED_VALIDATION_GATES = (
    "polygon",
    "finnhub",
    "ibkr",
    "projection_parity",
    "pg_unreachable",
)


@dataclass(frozen=True)
class CutoverPreviewReport:
    fingerprint: str
    legacy_max_id: int
    legacy_row_count: int
    normalized_row_count: int
    normalized_only_count: int
    unmapped_legacy_rows: int
    per_source: dict[str, dict[str, dict[str, Any]]]
    unmapped_rows: list[dict[str, Any]]

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "fingerprint": self.fingerprint,
            "legacy_max_id": self.legacy_max_id,
            "legacy_row_count": self.legacy_row_count,
            "normalized_row_count": self.normalized_row_count,
            "normalized_only_count": self.normalized_only_count,
            "unmapped_legacy_rows": self.unmapped_legacy_rows,
            "per_source": self.per_source,
            "unmapped_rows": self.unmapped_rows,
        }


@dataclass(frozen=True)
class CutoverBeginResult:
    run_id: int
    status: str
    backup_path: str
    fingerprint: str

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "backup_path": self.backup_path,
            "fingerprint": self.fingerprint,
        }


@dataclass(frozen=True)
class CutoverStatusResult:
    run_id: int
    status: str

    def to_json_dict(self) -> dict[str, Any]:
        return {"run_id": self.run_id, "status": self.status}


def preview_news_pg_exit(db_path: str | Path) -> CutoverPreviewReport:
    """Return a deterministic, read-only cutover report for one market DB."""
    db_path = Path(db_path)
    conn = _open_read_only(db_path)
    try:
        legacy_max_id = _legacy_max_id(conn)
        legacy_row_count = _count(conn, "news")
        normalized_row_count = _count(conn, "news_articles")
        normalized_only_count = _normalized_only_count(conn)
        unmapped_rows = _unmapped_legacy_rows(conn)
        report_payload = {
            "legacy_max_id": legacy_max_id,
            "legacy_row_count": legacy_row_count,
            "normalized_row_count": normalized_row_count,
            "normalized_only_count": normalized_only_count,
            "unmapped_legacy_rows": len(unmapped_rows),
            "per_source": {
                "legacy": _per_source(conn, "news"),
                "normalized": _per_source(conn, "news_articles"),
            },
            "unmapped_rows": unmapped_rows,
        }
        fingerprint = _fingerprint(report_payload)
        return CutoverPreviewReport(fingerprint=fingerprint, **report_payload)
    finally:
        conn.close()


def begin_news_pg_exit(
    db_path: str | Path,
    *,
    expected_report: CutoverPreviewReport | Mapping[str, Any],
    backup_path: str | Path,
    profile_db: str | Path | None = None,
) -> CutoverBeginResult:
    """Reserve a backup and write one immutable ``testing`` audit row."""
    db_path = Path(db_path)
    backup_path = Path(backup_path)
    profile_db = _profile_db_path(profile_db)
    current = preview_news_pg_exit(db_path)
    expected = coerce_preview_report(expected_report)
    _require_no_unmapped_legacy_rows(current)
    _require_exact_report(expected, current)

    with market_write_lock(timeout=30.0):
        locked = preview_news_pg_exit(db_path)
        _require_no_unmapped_legacy_rows(locked)
        _require_exact_report(expected, locked)

        created_backup = backup_market_db(
            str(db_path), str(backup_path), overwrite=False
        )
        if created_backup is None:
            raise FileNotFoundError(f"market DB does not exist: {db_path}")

        # Re-check after the backup and before any DDL/audit write. A scheduler should
        # be paused, but this catches an accidental local writer deterministically.
        post_backup = preview_news_pg_exit(db_path)
        _require_no_unmapped_legacy_rows(post_backup)
        _require_exact_report(expected, post_backup)

        conn = sqlite3.connect(db_path)
        try:
            begin_news_normalized_schema_transaction(conn)
            cursor = conn.execute(
                "INSERT INTO news_pg_exit_runs "
                "(preflight_fingerprint,legacy_max_id,legacy_row_count,"
                "normalized_row_count,normalized_only_count,backup_path,status,"
                "started_at) VALUES (?,?,?,?,?,?,?,?)",
                (
                    post_backup.fingerprint,
                    post_backup.legacy_max_id,
                    post_backup.legacy_row_count,
                    post_backup.normalized_row_count,
                    post_backup.normalized_only_count,
                    str(backup_path),
                    "testing",
                    _utc_now(),
                ),
            )
            run_id = int(cursor.lastrowid)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        ProfileStateStore(profile_db).set_setting(
            USE_NORMALIZED_NEWS_WRITES_KEY, "true"
        )
    return CutoverBeginResult(
        run_id=run_id,
        status="testing",
        backup_path=str(backup_path),
        fingerprint=current.fingerprint,
    )


def finalize_news_pg_exit(
    db_path: str | Path,
    *,
    run_id: int,
    validation_json_path: str | Path,
    profile_db: str | Path | None = None,
) -> CutoverStatusResult:
    validation_json = _read_validated_validation_json(validation_json_path)
    _complete_run_status(
        db_path,
        run_id=run_id,
        validation_json=validation_json,
        completed_at=_utc_now(),
    )
    ProfileStateStore(_profile_db_path(profile_db)).set_setting(
        NEWS_PG_EXIT_COMPLETED_KEY, "true"
    )
    return CutoverStatusResult(run_id=run_id, status="completed")


def rollback_news_pg_exit(
    db_path: str | Path,
    *,
    run_id: int,
    profile_db: str | Path | None = None,
) -> CutoverStatusResult:
    _require_run_testing(db_path, run_id=run_id)
    profile = ProfileStateStore(_profile_db_path(profile_db))
    previous_normalized_setting = profile.get_setting(USE_NORMALIZED_NEWS_WRITES_KEY)
    profile.set_setting(USE_NORMALIZED_NEWS_WRITES_KEY, "false")
    try:
        _update_run_status_from_testing(
            db_path,
            run_id=run_id,
            status="rolled_back",
            validation_json=None,
            completed_at=_utc_now(),
        )
    except Exception:
        profile.set_setting(USE_NORMALIZED_NEWS_WRITES_KEY, previous_normalized_setting)
        raise
    return CutoverStatusResult(run_id=run_id, status="rolled_back")


def coerce_preview_report(
    report: CutoverPreviewReport | Mapping[str, Any],
) -> CutoverPreviewReport:
    if isinstance(report, CutoverPreviewReport):
        return report
    data = dict(report)
    return CutoverPreviewReport(
        fingerprint=str(data["fingerprint"]),
        legacy_max_id=int(data["legacy_max_id"]),
        legacy_row_count=int(data["legacy_row_count"]),
        normalized_row_count=int(data["normalized_row_count"]),
        normalized_only_count=int(data["normalized_only_count"]),
        unmapped_legacy_rows=int(data["unmapped_legacy_rows"]),
        per_source=dict(data["per_source"]),
        unmapped_rows=list(data["unmapped_rows"]),
    )


def _open_read_only(db_path: Path) -> sqlite3.Connection:
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return bool(
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
    )


def _count(conn: sqlite3.Connection, table: str) -> int:
    if not _table_exists(conn, table):
        return 0
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def _legacy_max_id(conn: sqlite3.Connection) -> int:
    if not _table_exists(conn, "news"):
        return 0
    value = conn.execute("SELECT MAX(id) FROM news").fetchone()[0]
    return int(value or 0)


def _per_source(
    conn: sqlite3.Connection, table: str
) -> dict[str, dict[str, Any]]:
    if not _table_exists(conn, table):
        return {}
    rows = conn.execute(
        f"SELECT source,COUNT(*) AS count,MAX(published_at) AS latest "
        f"FROM {table} GROUP BY source ORDER BY source"
    ).fetchall()
    return {
        str(row["source"]): {
            "count": int(row["count"]),
            "latest_published_at": row["latest"],
        }
        for row in rows
    }


def _normalized_only_count(conn: sqlite3.Connection) -> int:
    if not _table_exists(conn, "news_articles"):
        return 0
    conditions = []
    if _table_exists(conn, "news_legacy_migration_map"):
        conditions.append(
            "NOT EXISTS ("
            "SELECT 1 FROM news_legacy_migration_map m "
            "WHERE m.article_id=a.id)"
        )
    if _table_exists(conn, "news_legacy_projection_map"):
        conditions.append(
            "NOT EXISTS ("
            "SELECT 1 FROM news_legacy_projection_map p "
            "WHERE p.article_id=a.id)"
        )
    if not conditions:
        return _count(conn, "news_articles")
    sql = "SELECT COUNT(*) FROM news_articles a WHERE " + " AND ".join(conditions)
    return int(conn.execute(sql).fetchone()[0])


def _unmapped_legacy_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    if not _table_exists(conn, "news"):
        return []
    where = ""
    if _table_exists(conn, "news_legacy_migration_map"):
        where = (
            " WHERE NOT EXISTS ("
            "SELECT 1 FROM news_legacy_migration_map m "
            "WHERE m.legacy_news_id=n.id)"
        )
    rows = conn.execute(
        "SELECT id,ticker,title,source,published_at,article_hash,url "
        f"FROM news n{where} ORDER BY id"
    ).fetchall()
    return [
        {
            "legacy_news_id": int(row["id"]),
            "ticker": row["ticker"],
            "title": row["title"],
            "source": row["source"],
            "published_at": row["published_at"],
            "article_hash": row["article_hash"],
            "url": row["url"],
        }
        for row in rows
    ]


def _fingerprint(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode()).hexdigest()


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _require_exact_report(
    expected: CutoverPreviewReport, current: CutoverPreviewReport
) -> None:
    if expected.to_json_dict() != current.to_json_dict():
        raise CutoverBlocked("expected report changed")


def _require_no_unmapped_legacy_rows(report: CutoverPreviewReport) -> None:
    if report.unmapped_legacy_rows:
        raise CutoverBlocked(f"unmapped legacy rows: {report.unmapped_legacy_rows}")


def _read_validated_validation_json(path: str | Path) -> str:
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, Mapping):
        raise CutoverBlocked("validation JSON must be an object")
    unexpected = set(data).difference(REQUIRED_VALIDATION_GATES)
    if unexpected:
        raise CutoverBlocked(
            f"unexpected validation gate(s): {', '.join(sorted(unexpected))}"
        )
    for gate in REQUIRED_VALIDATION_GATES:
        if data.get(gate) != "passed":
            raise CutoverBlocked(
                f"validation gate {gate} must be exactly 'passed'"
            )
    return _canonical_json(data)


def _update_run_status_from_testing(
    db_path: str | Path,
    *,
    run_id: int,
    status: str,
    validation_json: str | None,
    completed_at: str,
) -> None:
    conn = sqlite3.connect(db_path)
    try:
        with conn:
            if not _table_exists(conn, "news_pg_exit_runs"):
                raise CutoverBlocked("cutover audit table is missing")
            cursor = conn.execute(
                "UPDATE news_pg_exit_runs "
                "SET status=?,completed_at=?,validation_json=? "
                "WHERE id=? AND status='testing'",
                (status, completed_at, validation_json, run_id),
            )
            if cursor.rowcount != 1:
                raise CutoverBlocked(f"run is not in testing status: {run_id}")
    finally:
        conn.close()


def _require_run_testing(db_path: str | Path, *, run_id: int) -> None:
    conn = sqlite3.connect(db_path)
    try:
        if not _table_exists(conn, "news_pg_exit_runs"):
            raise CutoverBlocked("cutover audit table is missing")
        row = conn.execute(
            "SELECT status FROM news_pg_exit_runs WHERE id=?", (run_id,)
        ).fetchone()
        if row is None or row[0] != "testing":
            raise CutoverBlocked(f"run is not in testing status: {run_id}")
    finally:
        conn.close()


def _complete_run_status(
    db_path: str | Path,
    *,
    run_id: int,
    validation_json: str,
    completed_at: str,
) -> None:
    conn = sqlite3.connect(db_path)
    try:
        with conn:
            if not _table_exists(conn, "news_pg_exit_runs"):
                raise CutoverBlocked("cutover audit table is missing")
            row = conn.execute(
                "SELECT status,validation_json FROM news_pg_exit_runs WHERE id=?",
                (run_id,),
            ).fetchone()
            if row is None:
                raise CutoverBlocked(f"run is not in testing status: {run_id}")
            current_status, current_validation_json = row
            if current_status == "completed":
                if current_validation_json != validation_json:
                    raise CutoverBlocked(
                        f"run is already completed with different validation: {run_id}"
                    )
                return
            if current_status != "testing":
                raise CutoverBlocked(f"run is not in testing status: {run_id}")
            cursor = conn.execute(
                "UPDATE news_pg_exit_runs "
                "SET status=?,completed_at=?,validation_json=? "
                "WHERE id=? AND status='testing'",
                ("completed", completed_at, validation_json, run_id),
            )
            if cursor.rowcount != 1:
                raise CutoverBlocked(f"run is not in testing status: {run_id}")
    finally:
        conn.close()


def _profile_db_path(profile_db: str | Path | None) -> Path:
    if profile_db is not None:
        return Path(profile_db)
    env_profile_db = os.environ.get("ARKSCOPE_PROFILE_DB")
    if env_profile_db:
        return Path(env_profile_db)
    return Path(__file__).resolve().parents[2] / "data" / "profile_state.db"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
