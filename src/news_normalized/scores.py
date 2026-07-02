"""Helpers for local multi-model news score storage and reads."""

from __future__ import annotations

import re

_MODEL_SEP_RE = re.compile(r"[\s.\-]+")
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SCORE_TYPES = {"sentiment", "risk"}


def normalize_score_type(value: str | None) -> str:
    """Normalize and validate a score type stored in ``news_article_scores``."""
    score_type = (value or "").strip().casefold()
    if score_type not in _SCORE_TYPES:
        raise ValueError(f"invalid score_type: {value!r}")
    return score_type


def normalize_score_model(model: str | None) -> str:
    """Return the storage/query model key used by score imports and readers."""
    normalized = _MODEL_SEP_RE.sub("_", (model or "").strip().casefold()).strip("_")
    if not normalized:
        raise ValueError("score model is required")
    return normalized


def normalize_reasoning_effort(value: str | None) -> str:
    """Return empty string for NULL/blank effort and stripped lower-case otherwise."""
    return (value or "").strip().casefold()


def score_key(
    article_id: int, score_type: str, model: str, effort: str | None
) -> tuple[int, str, str, str]:
    """Return the canonical upsert key for ``news_article_scores``."""
    return (
        int(article_id),
        normalize_score_type(score_type),
        normalize_score_model(model),
        normalize_reasoning_effort(effort),
    )


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def latest_score_cte(
    score_type: str, *, alias: str, model: str | None = None
) -> str:
    """Return a CTE selecting the latest score per article for one score type."""
    if not _IDENT_RE.fullmatch(alias):
        raise ValueError(f"invalid SQL alias: {alias!r}")
    normalized_type = normalize_score_type(score_type)
    clauses = [f"score_type = {_sql_literal(normalized_type)}"]
    if model is not None:
        clauses.append(f"model = {_sql_literal(normalize_score_model(model))}")
    where = " AND ".join(clauses)
    return f"""
{alias} AS (
    SELECT article_id, score, model, reasoning_effort, scored_at
    FROM (
        SELECT article_id, score, model, reasoning_effort, scored_at,
               ROW_NUMBER() OVER (
                   PARTITION BY article_id
                   ORDER BY scored_at DESC, model DESC, reasoning_effort DESC
               ) AS rn
        FROM news_article_scores
        WHERE {where}
    )
    WHERE rn = 1
)""".strip()
