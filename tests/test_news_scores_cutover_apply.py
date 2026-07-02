import sqlite3
from contextlib import nullcontext

import pytest

from src.news_normalized import score_cutover
from src.news_normalized.schema import ensure_news_normalized_schema
from src.news_normalized.score_migration import ScoreSourceRow


def _create_score_db(path):
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys=ON")
    ensure_news_normalized_schema(conn)
    conn.execute(
        "INSERT INTO news_articles "
        "(id,source,canonical_title,published_at,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?)",
        (42, "ibkr", "Scored story", "2026-07-01T00:00:00Z", "now", "now"),
    )
    conn.execute(
        "INSERT INTO news_normalization_runs "
        "(id,policy_version,input_fingerprint,resolved_fingerprint,"
        "rejection_evidence_fingerprint,counts_json,backup_path,applied_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (1, "test", "input", "resolved", "reject", "{}", "backup.db", "now"),
    )
    conn.execute(
        "INSERT INTO news_legacy_migration_map "
        "(legacy_news_id,article_id,resolution_kind,migration_run_id,migration_fingerprint) "
        "VALUES (?,?,?,?,?)",
        (10, 42, "mapped", 1, "resolved"),
    )
    conn.commit()
    conn.close()
    return path


def _score_rows():
    return (
        ScoreSourceRow(10, "sentiment", "gpt-5.2", "high", 4.0, "2026-07-01T00:00:00Z"),
        ScoreSourceRow(10, "risk", "gpt-5.2", "high", 2.0, "2026-07-01T00:00:00Z"),
    )


def _patch_apply_io(monkeypatch, rows):
    backups = []
    monkeypatch.setattr(score_cutover, "read_pg_score_rows", lambda _dsn: tuple(rows))
    monkeypatch.setattr(score_cutover, "market_write_lock", lambda timeout=30.0: nullcontext())
    monkeypatch.setattr(
        score_cutover,
        "backup_market_db",
        lambda src, dest, overwrite=False: backups.append((src, dest, overwrite)) or dest,
    )
    return backups


def test_apply_writes_scores_audit_row_and_is_idempotent(tmp_path, monkeypatch):
    db = _create_score_db(tmp_path / "market.db")
    _patch_apply_io(monkeypatch, _score_rows())
    expected = score_cutover.preview_news_scores_cutover(db, "pg://source").fingerprint

    result = score_cutover.apply_news_scores_cutover(
        db,
        pg_dsn="pg://source",
        expected_fingerprint=expected,
        backup_path=tmp_path / "backup.db",
    )
    second = score_cutover.apply_news_scores_cutover(
        db,
        pg_dsn="pg://source",
        expected_fingerprint=expected,
        backup_path=tmp_path / "backup2.db",
    )

    assert result.inserted_or_updated == 2
    assert result.already_applied is False
    assert second.inserted_or_updated == 0
    assert second.already_applied is True
    conn = sqlite3.connect(db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM news_article_scores").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM news_score_migration_runs").fetchone()[0] == 1
    finally:
        conn.close()


def test_apply_refuses_fingerprint_drift_before_backup(tmp_path, monkeypatch):
    db = _create_score_db(tmp_path / "market.db")
    backups = _patch_apply_io(monkeypatch, _score_rows())

    with pytest.raises(score_cutover.ScoreCutoverBlocked):
        score_cutover.apply_news_scores_cutover(
            db,
            pg_dsn="pg://source",
            expected_fingerprint="wrong",
            backup_path=tmp_path / "backup.db",
        )

    assert backups == []


def test_apply_rolls_back_scores_when_validation_fails(tmp_path, monkeypatch):
    db = _create_score_db(tmp_path / "market.db")
    _patch_apply_io(monkeypatch, _score_rows())
    expected = score_cutover.preview_news_scores_cutover(db, "pg://source").fingerprint
    monkeypatch.setattr(
        score_cutover,
        "validate_applied_score_plan",
        lambda conn, plan, fingerprint: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    with pytest.raises(RuntimeError, match="boom"):
        score_cutover.apply_news_scores_cutover(
            db,
            pg_dsn="pg://source",
            expected_fingerprint=expected,
            backup_path=tmp_path / "backup.db",
        )

    conn = sqlite3.connect(db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM news_article_scores").fetchone()[0] == 0
        assert conn.execute(
            "SELECT name FROM sqlite_master WHERE name='news_score_migration_runs'"
        ).fetchone() is None
    finally:
        conn.close()
