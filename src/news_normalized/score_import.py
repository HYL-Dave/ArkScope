"""Local import of scored Parquet columns into ``news_article_scores``."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
import sqlite3
from typing import Iterable

import pandas as pd

from src.tools.backends.file_backend import detect_score_columns

from .scores import normalize_reasoning_effort, normalize_score_model, normalize_score_type


@dataclass(frozen=True, order=True)
class LocalScoreImportRow:
    article_id: int
    score_type: str
    model: str
    reasoning_effort: str
    score: float
    scored_at: str


@dataclass(frozen=True)
class LocalScoreImportPlan:
    rows: tuple[LocalScoreImportRow, ...]
    source_rows: int
    score_rows: int
    unmatched_rows: int
    fingerprint: str

    def to_json_dict(self) -> dict:
        return {
            "fingerprint": self.fingerprint,
            "score_rows": self.score_rows,
            "source_rows": self.source_rows,
            "unmatched_rows": self.unmatched_rows,
        }


def build_local_score_import_plan(
    market_db: str | Path, parquet_files: Iterable[str | Path]
) -> LocalScoreImportPlan:
    conn = sqlite3.connect(market_db)
    conn.row_factory = sqlite3.Row
    try:
        hash_map = _legacy_hash_article_map(conn)
        provider_map = _provider_key_article_map(conn)
    finally:
        conn.close()

    source_rows = 0
    unmatched_rows = 0
    rows_by_key: dict[tuple[int, str, str, str], LocalScoreImportRow] = {}
    for parquet_file in sorted(Path(p) for p in parquet_files):
        df = pd.read_parquet(parquet_file)
        score_cols = detect_score_columns(df)
        for _, record in df.iterrows():
            source_rows += 1
            article_id = _resolve_article_id(record, hash_map, provider_map)
            if article_id is None:
                unmatched_rows += 1
                continue
            scored_at = _text(record.get("scored_at")) or _text(record.get("published_at"))
            for score_type, model, effort, column in score_cols:
                score = _score_value(record.get(column))
                if score is None or not scored_at:
                    continue
                row = LocalScoreImportRow(
                    article_id=article_id,
                    score_type=normalize_score_type(score_type),
                    model=normalize_score_model(model),
                    reasoning_effort=normalize_reasoning_effort(effort),
                    score=score,
                    scored_at=scored_at,
                )
                key = (row.article_id, row.score_type, row.model, row.reasoning_effort)
                existing = rows_by_key.get(key)
                if existing is None or row.scored_at >= existing.scored_at:
                    rows_by_key[key] = row

    rows = tuple(sorted(rows_by_key.values()))
    return LocalScoreImportPlan(
        rows=rows,
        source_rows=source_rows,
        score_rows=len(rows),
        unmatched_rows=unmatched_rows,
        fingerprint=_fingerprint(rows, source_rows, unmatched_rows),
    )


def apply_local_score_import_plan(
    market_db: str | Path, plan: LocalScoreImportPlan
) -> int:
    conn = sqlite3.connect(market_db)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("BEGIN IMMEDIATE")
        for row in plan.rows:
            conn.execute(
                "INSERT INTO news_article_scores "
                "(article_id,score_type,model,reasoning_effort,score,scored_at,source,"
                "created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(article_id,score_type,model,reasoning_effort) DO UPDATE SET "
                "score=excluded.score,"
                "scored_at=excluded.scored_at,"
                "source=excluded.source,"
                "updated_at=excluded.updated_at",
                (
                    row.article_id,
                    row.score_type,
                    row.model,
                    row.reasoning_effort,
                    row.score,
                    row.scored_at,
                    "local_parquet_score_import",
                    row.scored_at,
                    row.scored_at,
                ),
            )
        conn.commit()
        return len(plan.rows)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def parquet_files_under(news_dir: str | Path) -> tuple[Path, ...]:
    return tuple(sorted(Path(news_dir).glob("**/*.parquet")))


def _legacy_hash_article_map(conn: sqlite3.Connection) -> dict[str, int]:
    tables = _tables(conn)
    if "news" not in tables or "news_legacy_migration_map" not in tables:
        return {}
    return {
        str(row["article_hash"]): int(row["article_id"])
        for row in conn.execute(
            "SELECT n.article_hash, m.article_id FROM news n "
            "JOIN news_legacy_migration_map m ON m.legacy_news_id = n.id "
            "WHERE n.article_hash IS NOT NULL AND m.article_id IS NOT NULL"
        ).fetchall()
    }


def _provider_key_article_map(conn: sqlite3.Connection) -> dict[tuple[str, str], int]:
    if "news_article_keys" not in _tables(conn):
        return {}
    return {
        (str(row["source"]).casefold(), str(row["key_value"])): int(row["article_id"])
        for row in conn.execute(
            "SELECT source,key_value,article_id FROM news_article_keys "
            "WHERE key_kind='provider_id'"
        ).fetchall()
    }


def _resolve_article_id(record, hash_map, provider_map) -> int | None:
    article_hash = _text(record.get("article_hash"))
    if article_hash and article_hash in hash_map:
        return hash_map[article_hash]
    source = (_text(record.get("source")) or _text(record.get("source_api"))).casefold()
    provider_id = _text(record.get("provider_article_id"))
    if source and provider_id:
        return provider_map.get((source, provider_id))
    return None


def _score_value(value) -> float | None:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(score) or not 1 <= score <= 5:
        return None
    return score


def _text(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def _tables(conn: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }


def _fingerprint(
    rows: tuple[LocalScoreImportRow, ...], source_rows: int, unmatched_rows: int
) -> str:
    payload = {
        "rows": [asdict(row) for row in rows],
        "source_rows": source_rows,
        "unmatched_rows": unmatched_rows,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
