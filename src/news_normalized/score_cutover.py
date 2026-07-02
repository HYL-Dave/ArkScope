"""Read-only preview gate for local news score cutover."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Iterable, Mapping

from .score_migration import (
    ScoreMigrationPlan,
    ScoreSourceRow,
    build_score_migration_plan,
)
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


def preview_news_scores_cutover(
    market_db: str | Path, pg_dsn: str
) -> ScoreCutoverPreviewReport:
    """Return a deterministic, read-only score cutover report."""
    conn = _open_read_only(market_db)
    try:
        mapping = read_legacy_article_map(conn)
    finally:
        conn.close()
    source_rows = tuple(read_pg_score_rows(pg_dsn))
    valid_rows, malformed_rows = _valid_source_rows(source_rows)
    plan = build_score_migration_plan(valid_rows, mapping)
    return _report_from_plan(plan, source_rows=len(source_rows), malformed_rows=malformed_rows)


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
