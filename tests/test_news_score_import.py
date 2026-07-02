import json
import sqlite3

import pandas as pd

from scripts.scoring import import_news_scores_local as import_cli
from src.news_normalized.schema import ensure_news_normalized_schema
from src.news_normalized.score_import import (
    apply_local_score_import_plan,
    build_local_score_import_plan,
)


def _create_import_db(path):
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(
        "CREATE TABLE news (id INTEGER PRIMARY KEY, article_hash TEXT UNIQUE)"
    )
    ensure_news_normalized_schema(conn)
    conn.executemany(
        "INSERT INTO news_articles "
        "(id,source,provider_article_id,canonical_title,published_at,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?,?)",
        [
            (42, "ibkr", "provider-42", "Legacy hash story", "2026-07-01T00:00:00Z", "now", "now"),
            (43, "ibkr", "DJ-N$1", "Provider key story", "2026-07-01T00:00:00Z", "now", "now"),
        ],
    )
    conn.execute(
        "INSERT INTO news_normalization_runs "
        "(id,policy_version,input_fingerprint,resolved_fingerprint,"
        "rejection_evidence_fingerprint,counts_json,backup_path,applied_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (1, "test", "input", "resolved", "reject", "{}", "backup.db", "now"),
    )
    conn.execute("INSERT INTO news VALUES (?,?)", (10, "hash-42"))
    conn.execute(
        "INSERT INTO news_legacy_migration_map "
        "(legacy_news_id,article_id,resolution_kind,migration_run_id,migration_fingerprint) "
        "VALUES (?,?,?,?,?)",
        (10, 42, "mapped", 1, "resolved"),
    )
    conn.execute(
        "INSERT INTO news_article_keys "
        "(article_id,source,key_kind,key_value,created_at) VALUES (?,?,?,?,?)",
        (43, "ibkr", "provider_id", "DJ-N$1", "now"),
    )
    conn.commit()
    conn.close()
    return path


def _write_parquet(path, rows):
    pd.DataFrame(rows).to_parquet(path, index=False)
    return path


def test_import_plan_matches_by_legacy_article_hash(tmp_path):
    db = _create_import_db(tmp_path / "market.db")
    parquet = _write_parquet(
        tmp_path / "scores.parquet",
        [
            {
                "article_hash": "hash-42",
                "published_at": "2026-07-01T00:00:00Z",
                "sentiment_gpt_5_2_high": 4,
            }
        ],
    )

    plan = build_local_score_import_plan(db, [parquet])

    assert plan.source_rows == 1
    assert plan.score_rows == 1
    assert plan.unmatched_rows == 0
    assert plan.rows[0].article_id == 42
    assert plan.rows[0].model == "gpt_5_2"
    assert plan.rows[0].reasoning_effort == "high"


def test_import_plan_matches_by_normalized_provider_key(tmp_path):
    db = _create_import_db(tmp_path / "market.db")
    parquet = _write_parquet(
        tmp_path / "scores.parquet",
        [
            {
                "source": "ibkr",
                "provider_article_id": "DJ-N$1",
                "published_at": "2026-07-01T00:00:00Z",
                "risk_o4_mini": 2,
            }
        ],
    )

    plan = build_local_score_import_plan(db, [parquet])

    assert plan.source_rows == 1
    assert plan.score_rows == 1
    assert plan.unmatched_rows == 0
    assert plan.rows[0].article_id == 43
    assert plan.rows[0].score_type == "risk"
    assert plan.rows[0].model == "o4_mini"
    assert plan.rows[0].reasoning_effort == ""


def test_import_plan_counts_unmatched_rows_without_fuzzy_matching(tmp_path):
    db = _create_import_db(tmp_path / "market.db")
    parquet = _write_parquet(
        tmp_path / "scores.parquet",
        [
            {
                "article_hash": "missing",
                "title": "Legacy hash story",
                "published_at": "2026-07-01T00:00:00Z",
                "sentiment_gpt_5_2_high": 5,
            }
        ],
    )

    plan = build_local_score_import_plan(db, [parquet])

    assert plan.source_rows == 1
    assert plan.score_rows == 0
    assert plan.unmatched_rows == 1
    assert plan.rows == ()


def test_import_apply_is_idempotent(tmp_path):
    db = _create_import_db(tmp_path / "market.db")
    parquet = _write_parquet(
        tmp_path / "scores.parquet",
        [
            {
                "source": "ibkr",
                "provider_article_id": "DJ-N$1",
                "published_at": "2026-07-01T00:00:00Z",
                "risk_o4_mini": 2,
            }
        ],
    )
    plan = build_local_score_import_plan(db, [parquet])

    first = apply_local_score_import_plan(db, plan)
    second = apply_local_score_import_plan(db, plan)

    assert first == 1
    assert second == 1
    conn = sqlite3.connect(db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM news_article_scores").fetchone()[0] == 1
    finally:
        conn.close()


def test_import_cli_dry_run_writes_sanitized_json(tmp_path):
    db = _create_import_db(tmp_path / "market.db")
    news_dir = tmp_path / "news"
    news_dir.mkdir()
    _write_parquet(
        news_dir / "scores.parquet",
        [
            {
                "source": "ibkr",
                "provider_article_id": "DJ-N$1",
                "title": "SECRET TITLE",
                "url": "https://secret.example",
                "published_at": "2026-07-01T00:00:00Z",
                "risk_o4_mini": 2,
            }
        ],
    )
    output = tmp_path / "preview.json"

    assert import_cli.main(
        ["--market-db", str(db), "--news-dir", str(news_dir), "--dry-run", "--output", str(output)]
    ) == 0

    text = output.read_text()
    payload = json.loads(text)
    assert payload["score_rows"] == 1
    assert "SECRET TITLE" not in text
    assert "secret.example" not in text
