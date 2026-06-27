from __future__ import annotations

import sqlite3

import pytest

import src.market_data_admin as mda
import src.news_identity_repair as nir
from src.news_identity import canonical_article_hash


def _repair_db(path, *, collision=False):
    conn = sqlite3.connect(path)
    conn.executescript(mda._NEWS_SCHEMA)
    mda._ensure_news_hash_unique(conn)
    mda._ensure_news_fts_triggers(conn)
    published = "2026-06-18T12:00:00+0000"
    conn.execute(
        "INSERT INTO news (id,ticker,title,description,source,published_at,article_hash) "
        "VALUES (1,'HAPN','same article','richarchivephrase','ibkr',?,?)",
        (published, canonical_article_hash("LC", "same article", published)),
    )
    if collision:
        conn.execute(
            "INSERT INTO news (id,ticker,title,description,source,published_at,article_hash) "
            "VALUES (2,'HAPN','same article','','ibkr',?,?)",
            (published, canonical_article_hash("HAPN", "same article", published)),
        )
    conn.commit()
    conn.close()


def _snapshot(path):
    conn = sqlite3.connect(path)
    try:
        schema = conn.execute(
            "SELECT type,name,sql FROM sqlite_master ORDER BY type,name"
        ).fetchall()
        rows = conn.execute("SELECT * FROM news ORDER BY id").fetchall()
    finally:
        conn.close()
    return path.read_bytes(), schema, rows


def test_preview_existing_db_is_zero_write(tmp_path):
    db = tmp_path / "market.db"
    _repair_db(db)
    before = _snapshot(db)

    result = nir.preview_news_identity_repair(str(db))

    assert result["exists"] is True
    assert result["updates"] == 1
    assert result["collisions"] == 0
    assert _snapshot(db) == before


def test_preview_missing_db_does_not_create_it(tmp_path):
    db = tmp_path / "absent.db"

    result = nir.preview_news_identity_repair(str(db))

    assert result == {
        "exists": False,
        "path": str(db),
        "fingerprint": None,
        "scanned": 0,
        "updates": 0,
        "collisions": 0,
    }
    assert not db.exists()


def test_preview_fingerprint_is_stable_without_intervening_write(tmp_path):
    db = tmp_path / "market.db"
    _repair_db(db, collision=True)

    first = nir.preview_news_identity_repair(str(db))
    second = nir.preview_news_identity_repair(str(db))

    assert first == second
    assert first["updates"] == 0
    assert first["collisions"] == 1
    assert len(first["fingerprint"]) == 64


def test_apply_refuses_unreviewed_fingerprint_before_backup_or_write(tmp_path, monkeypatch):
    db = tmp_path / "market.db"
    backup = tmp_path / "backup.db"
    _repair_db(db)
    before = _snapshot(db)
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))

    with pytest.raises(ValueError, match="fingerprint"):
        nir.apply_news_identity_repair(
            expected_fingerprint="not-reviewed",
            db_path=str(db),
            backup_path=str(backup),
        )

    assert not backup.exists()
    assert _snapshot(db) == before


def test_apply_backup_contains_true_pre_repair_state(tmp_path, monkeypatch):
    db = tmp_path / "market.db"
    backup = tmp_path / "backup.db"
    _repair_db(db)
    before_rows = _snapshot(db)[2]
    preview = nir.preview_news_identity_repair(str(db))
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))

    result = nir.apply_news_identity_repair(
        expected_fingerprint=preview["fingerprint"],
        db_path=str(db),
        backup_path=str(backup),
    )

    assert result["backup_path"] == str(backup)
    assert backup.exists()
    assert _snapshot(backup)[2] == before_rows


def test_apply_rolls_back_all_rows_when_post_validation_fails(tmp_path, monkeypatch):
    db = tmp_path / "market.db"
    backup = tmp_path / "backup.db"
    _repair_db(db, collision=True)
    before_rows = _snapshot(db)[2]
    preview = nir.preview_news_identity_repair(str(db))
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    real_validate = nir.validate_news_identity

    def invalid_after_write(conn):
        result = real_validate(conn)
        result["hash_mismatches"] = 1
        return result

    monkeypatch.setattr(nir, "validate_news_identity", invalid_after_write)

    with pytest.raises(RuntimeError, match="hash_mismatches"):
        nir.apply_news_identity_repair(
            expected_fingerprint=preview["fingerprint"],
            db_path=str(db),
            backup_path=str(backup),
        )

    assert _snapshot(db)[2] == before_rows
    assert backup.exists()


def test_apply_commits_collision_merge_and_fts_parity(tmp_path, monkeypatch):
    db = tmp_path / "market.db"
    _repair_db(db, collision=True)
    preview = nir.preview_news_identity_repair(str(db))
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))

    result = nir.apply_news_identity_repair(
        expected_fingerprint=preview["fingerprint"],
        db_path=str(db),
        backup_path=str(tmp_path / "backup.db"),
    )

    assert result["changes"] == {"updated": 0, "deleted": 1, "merged_fields": 1}
    conn = sqlite3.connect(db)
    try:
        assert conn.execute("SELECT id,description FROM news").fetchone() == (
            2,
            "richarchivephrase",
        )
        assert conn.execute("SELECT COUNT(*) FROM news").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM news_fts").fetchone()[0] == 1
        assert conn.execute(
            "SELECT n.id FROM news_fts f JOIN news n ON n.id=f.rowid "
            "WHERE news_fts MATCH 'richarchivephrase'"
        ).fetchone()[0] == 2
    finally:
        conn.close()


def test_apply_second_run_is_noop_without_new_backup(tmp_path, monkeypatch):
    db = tmp_path / "market.db"
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    _repair_db(db)
    first = nir.preview_news_identity_repair(str(db))
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    nir.apply_news_identity_repair(
        expected_fingerprint=first["fingerprint"],
        db_path=str(db),
        backup_path=str(backup_dir / "first.db"),
    )
    before_files = sorted(path.name for path in backup_dir.iterdir())
    second = nir.preview_news_identity_repair(str(db))

    result = nir.apply_news_identity_repair(
        expected_fingerprint=second["fingerprint"],
        db_path=str(db),
        backup_path=str(backup_dir / "must-not-exist.db"),
    )

    assert result["changes"] == {"updated": 0, "deleted": 0, "merged_fields": 0}
    assert result["backup_path"] is None
    assert sorted(path.name for path in backup_dir.iterdir()) == before_files
