import sqlite3
import stat

import pytest

from tests.test_lifecycle_web_store import AT, setup_store


def test_web_installation_has_digest_bound_backup_and_keeps_all_existing_rows(tmp_path):
    from src.lifecycle_web_migration import preview_web_installation, apply_web_installation
    from src.lifecycle_web_schema import verify_web_journal
    path, _ = setup_store(tmp_path, install=False)
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE unrelated_payload(id INTEGER PRIMARY KEY, raw BLOB)")
        conn.execute("INSERT INTO unrelated_payload VALUES (1,?)", (b"opaque-private-fixture",))
    before = preview_web_installation(path)
    backup = tmp_path / "backup.db"
    result = apply_web_installation(path, backup_path=backup, approval_sha256=before["approval_sha256"], at=AT, app_stopped=True)
    assert result["changed"] and result["previous_rows_sha256"] == before["rows_sha256"]
    assert stat.S_IMODE(backup.stat().st_mode) == 0o600
    assert preview_web_installation(backup) == before
    assert "opaque-private" not in str(result) and len(result["backup_sha256"]) == 64
    with sqlite3.connect(path) as conn:
        verify_web_journal(conn)
        assert conn.execute("SELECT raw FROM unrelated_payload").fetchone()[0] == b"opaque-private-fixture"
    current = preview_web_installation(path)
    assert apply_web_installation(path, backup_path=tmp_path / "unused.db", approval_sha256=current["approval_sha256"], at=AT, app_stopped=True)["changed"] is False
    assert not (tmp_path / "unused.db").exists()


def test_web_installation_requires_stopped_app_before_opening_any_store(tmp_path):
    from src.lifecycle_web_migration import apply_web_installation
    with pytest.raises(ValueError, match="web_installation_app_stop_required"):
        apply_web_installation(tmp_path / "missing.db", backup_path=tmp_path / "backup.db", approval_sha256="a" * 64, at=AT, app_stopped=False)
    assert not tuple(tmp_path.iterdir())


@pytest.mark.parametrize("change", ["before_backup", "after_backup", "backup_exists"])
def test_web_installation_rejects_changed_approval_and_never_overwrites_a_backup(tmp_path, monkeypatch, change):
    from src import lifecycle_web_migration as module
    path, _ = setup_store(tmp_path, install=False)
    before = module.preview_web_installation(path)
    backup = tmp_path / "backup.db"
    def mutate():
        with sqlite3.connect(path) as conn:
            conn.execute("UPDATE security_lifecycle_cases SET updated_at='changed'")
    if change == "before_backup":
        mutate()
    elif change == "backup_exists":
        backup.write_bytes(b"must-retain")
    else:
        original = module._backup
        def changed(*args, **kwargs):
            result = original(*args, **kwargs)
            mutate()
            return result
        monkeypatch.setattr(module, "_backup", changed)
    with pytest.raises((ValueError, FileExistsError)):
        module.apply_web_installation(path, backup_path=backup, approval_sha256=before["approval_sha256"], at=AT, app_stopped=True)
    if change == "backup_exists":
        assert backup.read_bytes() == b"must-retain"
    with sqlite3.connect(path) as conn:
        assert not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name LIKE 'lifecycle_web_%'").fetchone()


def test_web_installation_rolls_back_all_new_schema_on_failure_and_preserves_backup(tmp_path, monkeypatch):
    from src import lifecycle_web_migration as module
    from src import lifecycle_web_schema as schema
    path, _ = setup_store(tmp_path, install=False)
    before = module.preview_web_installation(path)
    backup = tmp_path / "backup.db"
    original = schema.verify_web_journal
    def fail(conn):
        original(conn)
        raise ValueError("synthetic_postflight_failure")
    monkeypatch.setattr(schema, "verify_web_journal", fail)
    with pytest.raises(ValueError, match="synthetic_postflight_failure"):
        module.apply_web_installation(path, backup_path=backup, approval_sha256=before["approval_sha256"], at=AT, app_stopped=True)
    assert module.preview_web_installation(path) == before
    assert module.preview_web_installation(backup) == before
