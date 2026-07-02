"""Deterministic planning for moving PG ``news_scores`` into local SQLite."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Iterable, Mapping

from .scores import (
    normalize_reasoning_effort,
    normalize_score_model,
    normalize_score_type,
)


@dataclass(frozen=True)
class ScoreSourceRow:
    legacy_news_id: int
    score_type: str
    model: str
    reasoning_effort: str | None
    score: float
    scored_at: str


@dataclass(frozen=True, order=True)
class ScoreMigrationRow:
    article_id: int
    legacy_news_id: int
    score_type: str
    model: str
    reasoning_effort: str
    score: float
    scored_at: str


@dataclass(frozen=True)
class ScoreMigrationPlan:
    rows: tuple[ScoreMigrationRow, ...]
    source_rows: int
    mapped_rows: int
    unmapped_rows: int
    rejected_rows: int
    missing_legacy_rows: int
    duplicate_keys: int
    counts: dict[str, int]
    fingerprint: str


def _normalize_row(row: ScoreSourceRow, article_id: int) -> ScoreMigrationRow:
    scored_at = (row.scored_at or "").strip()
    if not scored_at:
        raise ValueError(f"score row {row.legacy_news_id} has no scored_at")
    score = float(row.score)
    if not math.isfinite(score) or not 1 <= score <= 5:
        raise ValueError(f"score row {row.legacy_news_id} has invalid score")
    return ScoreMigrationRow(
        article_id=int(article_id),
        legacy_news_id=int(row.legacy_news_id),
        score_type=normalize_score_type(row.score_type),
        model=normalize_score_model(row.model),
        reasoning_effort=normalize_reasoning_effort(row.reasoning_effort),
        score=score,
        scored_at=scored_at,
    )


def _dedupe_sort_key(row: ScoreMigrationRow) -> tuple[str, str, str, str, int]:
    return (
        row.scored_at,
        row.score_type,
        row.model,
        row.reasoning_effort,
        row.legacy_news_id,
    )


def _fingerprint(
    rows: tuple[ScoreMigrationRow, ...],
    *,
    source_rows: int,
    mapped_rows: int,
    unmapped_rows: int,
    rejected_rows: int,
    missing_legacy_rows: int,
    duplicate_keys: int,
    counts: dict[str, int],
) -> str:
    payload = {
        "counts": counts,
        "duplicate_keys": duplicate_keys,
        "mapped_rows": mapped_rows,
        "missing_legacy_rows": missing_legacy_rows,
        "rejected_rows": rejected_rows,
        "rows": [asdict(row) for row in rows],
        "source_rows": source_rows,
        "unmapped_rows": unmapped_rows,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def build_score_migration_plan(
    source_rows: Iterable[ScoreSourceRow],
    legacy_article_map: Mapping[int, int | None],
) -> ScoreMigrationPlan:
    """Build a deterministic local score migration plan from source score rows."""
    source_count = 0
    mapped_count = 0
    unmapped_count = 0
    rejected_count = 0
    missing_count = 0
    by_key: dict[tuple[int, str, str, str], ScoreMigrationRow] = {}

    for source in source_rows:
        source_count += 1
        legacy_id = int(source.legacy_news_id)
        if legacy_id not in legacy_article_map:
            unmapped_count += 1
            missing_count += 1
            continue
        article_id = legacy_article_map[legacy_id]
        if article_id is None:
            unmapped_count += 1
            rejected_count += 1
            continue
        mapped_count += 1
        row = _normalize_row(source, int(article_id))
        key = (row.article_id, row.score_type, row.model, row.reasoning_effort)
        existing = by_key.get(key)
        if existing is None or _dedupe_sort_key(row) > _dedupe_sort_key(existing):
            by_key[key] = row

    rows = tuple(sorted(by_key.values()))
    duplicate_keys = mapped_count - len(rows)
    counter: Counter[str] = Counter()
    for row in rows:
        counter[f"score_type:{row.score_type}"] += 1
        counter[f"model:{row.model}"] += 1
        counter[f"reasoning_effort:{row.reasoning_effort}"] += 1
    counts = dict(sorted(counter.items()))
    return ScoreMigrationPlan(
        rows=rows,
        source_rows=source_count,
        mapped_rows=mapped_count,
        unmapped_rows=unmapped_count,
        rejected_rows=rejected_count,
        missing_legacy_rows=missing_count,
        duplicate_keys=duplicate_keys,
        counts=counts,
        fingerprint=_fingerprint(
            rows,
            source_rows=source_count,
            mapped_rows=mapped_count,
            unmapped_rows=unmapped_count,
            rejected_rows=rejected_count,
            missing_legacy_rows=missing_count,
            duplicate_keys=duplicate_keys,
            counts=counts,
        ),
    )
