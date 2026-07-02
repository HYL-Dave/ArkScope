import json
import sqlite3

from scripts.migration import news_scores_cutover as cutover_cli
from src.news_normalized import score_cutover
from src.news_normalized.score_migration import ScoreSourceRow


def _create_mapping_db(path):
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE news_legacy_migration_map ("
        "legacy_news_id INTEGER PRIMARY KEY, article_id INTEGER, rejection_reason TEXT)"
    )
    conn.executemany(
        "INSERT INTO news_legacy_migration_map VALUES (?,?,?)",
        [(10, 42, None), (11, None, "weak_ambiguity")],
    )
    conn.commit()
    conn.close()
    return path


def _source_rows():
    return [
        ScoreSourceRow(10, "sentiment", "gpt-5.2", "high", 4.0, "2026-07-01T00:00:00Z"),
        ScoreSourceRow(11, "risk", "gpt-5.2", None, 2.0, "2026-07-01T00:00:00Z"),
    ]


def test_preview_writes_deterministic_json_and_does_not_create_score_table(
    tmp_path, monkeypatch
):
    db = _create_mapping_db(tmp_path / "market.db")
    monkeypatch.setattr(score_cutover, "read_pg_score_rows", lambda _dsn: _source_rows())
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    assert cutover_cli.main(["preview", "--db", str(db), "--pg-dsn", "postgres://secret", "--output", str(first)]) == 0
    assert cutover_cli.main(["preview", "--db", str(db), "--pg-dsn", "postgres://secret", "--output", str(second)]) == 0

    assert first.read_bytes() == second.read_bytes()
    payload = json.loads(first.read_text())
    assert payload["pg_score_rows"] == 2
    assert payload["mapped_rows"] == 1
    assert payload["unmapped_rows"] == 1
    assert payload["would_apply"] is True
    assert "secret" not in first.read_text()

    conn = sqlite3.connect(db)
    try:
        assert conn.execute(
            "SELECT name FROM sqlite_master WHERE name='news_article_scores'"
        ).fetchone() is None
    finally:
        conn.close()


def test_preview_malformed_rows_make_would_apply_false(tmp_path, monkeypatch):
    db = _create_mapping_db(tmp_path / "market.db")
    monkeypatch.setattr(
        score_cutover,
        "read_pg_score_rows",
        lambda _dsn: [
            ScoreSourceRow(10, "quality", "gpt-5.2", "high", 4.0, "2026-07-01T00:00:00Z")
        ],
    )
    output = tmp_path / "preview.json"

    assert cutover_cli.main(["preview", "--db", str(db), "--pg-dsn", "postgres://secret", "--output", str(output)]) == 0

    payload = json.loads(output.read_text())
    assert payload["would_apply"] is False
    assert payload["malformed_rows"] == 1
    assert "quality" not in output.read_text()
