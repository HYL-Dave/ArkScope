"""Read-only preview gate for local news score cutover."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Iterable, Mapping

from src.market_data_direct import backup_market_db, market_write_lock

from .score_migration import (
    ScoreMigrationPlan,
    ScoreMigrationRow,
    ScoreSourceRow,
    build_score_migration_plan,
)
from .schema import begin_news_normalized_schema_transaction
from .scores import (
    normalize_reasoning_effort,
    normalize_score_model,
    normalize_score_type,
)


@dataclass(frozen=True)
class ScoreCutoverPreviewReport:
    fingerprint: str
    pg_score_rows: int
    mapped_rows: int
    unmapped_rows: int
    duplicate_keys: int
    article_count: int
    score_type_counts: dict[str, int]
    model_counts: dict[str, int]
    reasoning_effort_counts: dict[str, int]
    latest_scored_at: str | None
    malformed_rows: int
    would_apply: bool

    def to_json_dict(self) -> dict:
        return {
            "article_count": self.article_count,
            "duplicate_keys": self.duplicate_keys,
            "fingerprint": self.fingerprint,
            "latest_scored_at": self.latest_scored_at,
            "malformed_rows": self.malformed_rows,
            "mapped_rows": self.mapped_rows,
            "model_counts": self.model_counts,
            "pg_score_rows": self.pg_score_rows,
            "reasoning_effort_counts": self.reasoning_effort_counts,
            "score_type_counts": self.score_type_counts,
            "unmapped_rows": self.unmapped_rows,
            "would_apply": self.would_apply,
        }


class ScoreCutoverBlocked(RuntimeError):
    """Raised when the reviewed score cutover gate cannot safely proceed."""


@dataclass(frozen=True)
class ScoreCutoverApplyResult:
    fingerprint: str
    inserted_or_updated: int
    already_applied: bool
    backup_path: str

    def to_json_dict(self) -> dict:
        return {
            "already_applied": self.already_applied,
            "backup_path": self.backup_path,
            "fingerprint": self.fingerprint,
            "inserted_or_updated": self.inserted_or_updated,
        }


def preview_news_scores_cutover(
    market_db: str | Path, pg_dsn: str
) -> ScoreCutoverPreviewReport:
    """Return a deterministic, read-only score cutover report."""
    report, _plan = _build_score_cutover_state(market_db, pg_dsn)
    return report


def apply_news_scores_cutover(
    market_db: str | Path,
    *,
    pg_dsn: str,
    expected_fingerprint: str,
    backup_path: str | Path,
) -> ScoreCutoverApplyResult:
    """Apply the reviewed score cutover plan to the local market DB."""
    market_db = Path(market_db)
    backup_path = Path(backup_path)
    current, _ = _build_score_cutover_state(market_db, pg_dsn)
    _require_expected_fingerprint(current.fingerprint, expected_fingerprint)

    with market_write_lock(timeout=30.0):
        locked, plan = _build_score_cutover_state(market_db, pg_dsn)
        _require_expected_fingerprint(locked.fingerprint, expected_fingerprint)
        if _score_run_exists(market_db, expected_fingerprint):
            return ScoreCutoverApplyResult(
                fingerprint=expected_fingerprint,
                inserted_or_updated=0,
                already_applied=True,
                backup_path=str(backup_path),
            )
        created_backup = backup_market_db(
            str(market_db), str(backup_path), overwrite=False
        )
        if created_backup is None:
            raise FileNotFoundError(f"market DB does not exist: {market_db}")

        conn = sqlite3.connect(market_db)
        try:
            begin_news_normalized_schema_transaction(conn)
            _ensure_score_migration_run_table(conn)
            written = _upsert_score_rows(conn, plan.rows)
            conn.execute(
                "INSERT INTO news_score_migration_runs "
                "(fingerprint,counts_json,backup_path,applied_at) VALUES (?,?,?,?)",
                (
                    expected_fingerprint,
                    json.dumps(locked.to_json_dict(), sort_keys=True),
                    str(backup_path),
                    _utc_now(),
                ),
            )
            validate_applied_score_plan(conn, plan, expected_fingerprint)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    conn = _open_read_only(market_db)
    try:
        validate_applied_score_plan(conn, plan, expected_fingerprint)
    finally:
        conn.close()
    return ScoreCutoverApplyResult(
        fingerprint=expected_fingerprint,
        inserted_or_updated=written,
        already_applied=False,
        backup_path=str(backup_path),
    )


def validate_applied_score_plan(
    conn: sqlite3.Connection, plan: ScoreMigrationPlan, fingerprint: str
) -> None:
    """Validate score rows and audit row for an applied plan."""
    expected_rows = len(plan.rows)
    actual_rows = conn.execute("SELECT COUNT(*) FROM news_article_scores").fetchone()[0]
    if actual_rows != expected_rows:
        raise ScoreCutoverBlocked(
            f"news_article_scores row count mismatch: {actual_rows} != {expected_rows}"
        )
    missing_articles = conn.execute(
        "SELECT COUNT(*) FROM news_article_scores s "
        "LEFT JOIN news_articles a ON a.id = s.article_id WHERE a.id IS NULL"
    ).fetchone()[0]
    if missing_articles:
        raise ScoreCutoverBlocked("news_article_scores contains missing article references")
    invalid_scores = conn.execute(
        "SELECT COUNT(*) FROM news_article_scores "
        "WHERE score_type NOT IN ('sentiment','risk') OR score < 1 OR score > 5"
    ).fetchone()[0]
    if invalid_scores:
        raise ScoreCutoverBlocked("news_article_scores contains invalid scores")
    audit = conn.execute(
        "SELECT COUNT(*) FROM news_score_migration_runs WHERE fingerprint=?",
        (fingerprint,),
    ).fetchone()[0]
    if audit != 1:
        raise ScoreCutoverBlocked("score migration audit row missing")


def _build_score_cutover_state(
    market_db: str | Path, pg_dsn: str
) -> tuple[ScoreCutoverPreviewReport, ScoreMigrationPlan]:
    conn = _open_read_only(market_db)
    try:
        mapping = read_legacy_article_map(conn)
    finally:
        conn.close()
    source_rows = tuple(read_pg_score_rows(pg_dsn))
    valid_rows, malformed_rows = _valid_source_rows(source_rows)
    plan = build_score_migration_plan(valid_rows, mapping)
    return (
        _report_from_plan(plan, source_rows=len(source_rows), malformed_rows=malformed_rows),
        plan,
    )


def read_legacy_article_map(conn: sqlite3.Connection) -> dict[int, int | None]:
    """Read legacy news id to normalized article id mapping, preserving rejections."""
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='news_legacy_migration_map'"
    ).fetchone()
    if not exists:
        return {}
    return {
        int(row["legacy_news_id"]): (
            None if row["article_id"] is None else int(row["article_id"])
        )
        for row in conn.execute(
            "SELECT legacy_news_id, article_id FROM news_legacy_migration_map"
        ).fetchall()
    }


def read_pg_score_rows(pg_dsn: str) -> tuple[ScoreSourceRow, ...]:
    """Read PG ``news_scores`` rows as immutable source rows."""
    import psycopg2  # Imported lazily so hermetic tests do not need a PG connection.

    conn = psycopg2.connect(pg_dsn)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT news_id, score_type, model, reasoning_effort, score, scored_at "
                "FROM news_scores ORDER BY news_id, score_type, model, reasoning_effort"
            )
            rows = []
            for news_id, score_type, model, effort, score, scored_at in cur.fetchall():
                rows.append(
                    ScoreSourceRow(
                        legacy_news_id=int(news_id),
                        score_type=str(score_type),
                        model=str(model),
                        reasoning_effort=None if effort is None else str(effort),
                        score=float(score),
                        scored_at=_scored_at_to_text(scored_at),
                    )
                )
            return tuple(rows)
    finally:
        conn.close()


def _open_read_only(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{Path(path)}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    return conn


def _require_expected_fingerprint(current: str, expected: str) -> None:
    if current != expected:
        raise ScoreCutoverBlocked(
            f"score cutover fingerprint mismatch: {current} != {expected}"
        )


def _score_run_exists(db_path: Path, fingerprint: str) -> bool:
    conn = _open_read_only(db_path)
    try:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name='news_score_migration_runs'"
        ).fetchone()
        if not exists:
            return False
        return (
            conn.execute(
                "SELECT 1 FROM news_score_migration_runs WHERE fingerprint=?",
                (fingerprint,),
            ).fetchone()
            is not None
        )
    finally:
        conn.close()


def _ensure_score_migration_run_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS news_score_migration_runs ("
        "id INTEGER PRIMARY KEY,"
        "fingerprint TEXT NOT NULL UNIQUE,"
        "counts_json TEXT NOT NULL,"
        "backup_path TEXT NOT NULL,"
        "applied_at TEXT NOT NULL)"
    )


def _upsert_score_rows(
    conn: sqlite3.Connection, rows: tuple[ScoreMigrationRow, ...]
) -> int:
    for row in rows:
        conn.execute(
            "INSERT INTO news_article_scores "
            "(article_id,score_type,model,reasoning_effort,score,scored_at,source,"
            "source_legacy_news_id,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(article_id,score_type,model,reasoning_effort) DO UPDATE SET "
            "score=excluded.score,"
            "scored_at=excluded.scored_at,"
            "source=excluded.source,"
            "source_legacy_news_id=excluded.source_legacy_news_id,"
            "updated_at=excluded.updated_at",
            (
                row.article_id,
                row.score_type,
                row.model,
                row.reasoning_effort,
                row.score,
                row.scored_at,
                "pg_news_scores_cutover",
                row.legacy_news_id,
                _utc_now(),
                _utc_now(),
            ),
        )
    return len(rows)


def _valid_source_rows(
    rows: Iterable[ScoreSourceRow],
) -> tuple[tuple[ScoreSourceRow, ...], int]:
    valid: list[ScoreSourceRow] = []
    malformed = 0
    for row in rows:
        try:
            normalize_score_type(row.score_type)
            normalize_score_model(row.model)
            normalize_reasoning_effort(row.reasoning_effort)
            score = float(row.score)
            if not 1 <= score <= 5:
                raise ValueError("invalid score")
            if not (row.scored_at or "").strip():
                raise ValueError("missing scored_at")
        except (TypeError, ValueError):
            malformed += 1
            continue
        valid.append(row)
    return tuple(valid), malformed


def _report_from_plan(
    plan: ScoreMigrationPlan, *, source_rows: int, malformed_rows: int
) -> ScoreCutoverPreviewReport:
    score_type_counts = _prefix_counts(plan.counts, "score_type:")
    model_counts = _prefix_counts(plan.counts, "model:")
    effort_counts = _prefix_counts(plan.counts, "reasoning_effort:")
    latest_scored_at = max((row.scored_at for row in plan.rows), default=None)
    article_count = len({row.article_id for row in plan.rows})
    payload = {
        "article_count": article_count,
        "duplicate_keys": plan.duplicate_keys,
        "fingerprint": plan.fingerprint,
        "latest_scored_at": latest_scored_at,
        "malformed_rows": malformed_rows,
        "mapped_rows": plan.mapped_rows,
        "model_counts": model_counts,
        "pg_score_rows": source_rows,
        "reasoning_effort_counts": effort_counts,
        "score_type_counts": score_type_counts,
        "unmapped_rows": plan.unmapped_rows,
        "would_apply": plan.mapped_rows > 0 and malformed_rows == 0,
    }
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return ScoreCutoverPreviewReport(
        fingerprint=fingerprint,
        pg_score_rows=source_rows,
        mapped_rows=plan.mapped_rows,
        unmapped_rows=plan.unmapped_rows,
        duplicate_keys=plan.duplicate_keys,
        article_count=article_count,
        score_type_counts=score_type_counts,
        model_counts=model_counts,
        reasoning_effort_counts=effort_counts,
        latest_scored_at=latest_scored_at,
        malformed_rows=malformed_rows,
        would_apply=payload["would_apply"],
    )


def _prefix_counts(counts: Mapping[str, int], prefix: str) -> dict[str, int]:
    return {
        key.removeprefix(prefix): value
        for key, value in counts.items()
        if key.startswith(prefix)
    }


def _scored_at_to_text(value) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
