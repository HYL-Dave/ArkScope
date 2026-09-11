"""Shared SQLite backup safety and its current installation consumer."""

from contextlib import closing
import hashlib
from importlib import import_module
from pathlib import Path
import sqlite3
import stat

import pytest


ROOT = Path(__file__).resolve().parents[1]
AT = "2026-09-08T00:00:00Z"


def backup_owner():
    assert (ROOT / "src/sqlite_backup.py").is_file(), "shared SQLite backup owner is missing"
    return import_module("src.sqlite_backup")


@pytest.mark.parametrize("name", ("lifecycle_web_schema.py", "lifecycle_web_migration.py"))
def test_current_journal_has_no_obsolete_schema_owner(name):
    assert not (ROOT / "src" / name).exists()


def test_backup_captures_committed_wal_rows_without_changing_the_source(tmp_path):
    backup_connection = backup_owner().backup_connection
    source = tmp_path / "source.db"
    backup = tmp_path / "private" / "backup.db"
    with closing(sqlite3.connect(source)) as conn:
        assert conn.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
        conn.execute("PRAGMA wal_autocheckpoint=0")
        conn.execute("CREATE TABLE retained(id INTEGER PRIMARY KEY, payload BLOB)")
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.execute("INSERT INTO retained VALUES (1,?)", (b"committed-in-wal",))
        conn.commit()
        assert Path(str(source) + "-wal").stat().st_size > 0
        with closing(sqlite3.connect(source.as_uri() + "?immutable=1", uri=True)) as main_only:
            assert main_only.execute("SELECT * FROM retained").fetchall() == []
        assert backup_connection(conn, backup) is None
        assert conn.execute("SELECT * FROM retained").fetchall() == [(1, b"committed-in-wal")]
        with closing(sqlite3.connect(backup)) as restored:
            assert restored.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
            assert restored.execute("SELECT * FROM retained").fetchall() == [(1, b"committed-in-wal")]
    assert stat.S_IMODE(backup.stat().st_mode) == 0o600


def test_backup_never_overwrites_an_existing_destination(tmp_path):
    backup_connection = backup_owner().backup_connection
    existing = tmp_path / "backup.db"
    existing.write_bytes(b"owned-backup")
    with closing(sqlite3.connect(":memory:")) as conn:
        with pytest.raises(FileExistsError):
            backup_connection(conn, existing)
    assert existing.read_bytes() == b"owned-backup"


def test_backup_rejects_a_dangling_destination_symlink(tmp_path):
    backup_connection = backup_owner().backup_connection
    target = tmp_path / "must-not-create.db"
    backup = tmp_path / "backup.db"
    backup.symlink_to(target)
    with closing(sqlite3.connect(":memory:")) as conn:
        with pytest.raises(FileExistsError):
            backup_connection(conn, backup)
    assert backup.is_symlink() and not target.exists()


@pytest.mark.parametrize("failure", (False, True))
def test_backup_explicitly_closes_destination_on_success_and_failure(tmp_path, monkeypatch, failure):
    module = backup_owner()
    real_connect = sqlite3.connect
    destinations = []

    class FailingBackup(sqlite3.Connection):
        def backup(self, destination, **kwargs):
            raise OSError("synthetic backup failure")

    def connect(*args, **kwargs):
        destination = real_connect(*args, **kwargs)
        destinations.append(destination)
        return destination

    with closing(real_connect(":memory:", factory=FailingBackup if failure else sqlite3.Connection)) as conn:
        monkeypatch.setattr(module.sqlite3, "connect", connect)
        if failure:
            with pytest.raises(OSError, match="synthetic backup failure"):
                module.backup_connection(conn, tmp_path / "backup.db")
        else:
            module.backup_connection(conn, tmp_path / "backup.db")
        assert conn.execute("SELECT 1").fetchone() == (1,)
    assert len(destinations) == 1
    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        destinations[0].execute("SELECT 1")


def test_current_installation_backup_preserves_unrelated_rows_and_is_idempotent(tmp_path):
    from src.lifecycle_investigation.migration import apply_installation, preview_installation
    from src.lifecycle_investigation.schema import verify_journal
    from tests.test_security_lifecycle_population import persist, stores

    _, profile = stores(tmp_path)
    case_id = persist(profile, {"source": "sec_edgar", "source_ref": "retained", "ticker": "OLD"})
    with closing(sqlite3.connect(profile)) as conn:
        conn.execute("CREATE TABLE unrelated_payload(id INTEGER PRIMARY KEY, raw BLOB)")
        conn.execute("INSERT INTO unrelated_payload VALUES (1,?)", (b"opaque-private-fixture",))
        conn.commit()
    before = preview_installation(profile)
    backup = tmp_path / "backup.db"
    result = apply_installation(profile, backup_path=backup, approval_sha256=before["approval_sha256"], at=AT, app_stopped=True)
    assert result["changed"] is True
    assert result["backup_sha256"] == hashlib.sha256(backup.read_bytes()).hexdigest()
    assert stat.S_IMODE(backup.stat().st_mode) == 0o600
    assert preview_installation(backup) == before
    assert "opaque-private" not in str(result)
    with closing(sqlite3.connect(profile)) as conn:
        verify_journal(conn)
        assert conn.execute("SELECT raw FROM unrelated_payload").fetchall() == [(b"opaque-private-fixture",)]
        assert conn.execute("SELECT case_id FROM security_lifecycle_cases").fetchall() == [(case_id,)]
    current = preview_installation(profile)
    assert apply_installation(profile, backup_path=tmp_path / "unused.db", approval_sha256=current["approval_sha256"], at=AT, app_stopped=True)["changed"] is False
    assert not (tmp_path / "unused.db").exists()


def test_current_installation_requires_stopped_app_before_opening_any_store(tmp_path):
    from src.lifecycle_investigation.migration import apply_installation

    with pytest.raises(ValueError, match="investigation_install_app_stop_required"):
        apply_installation(tmp_path / "missing.db", backup_path=tmp_path / "backup.db", approval_sha256="a" * 64, at=AT, app_stopped=False)
    assert not tuple(tmp_path.iterdir())


@pytest.mark.parametrize("change", ("after_backup", "backup_exists"))
def test_current_installation_rejects_backup_races_and_existing_destinations(tmp_path, monkeypatch, change):
    from src.lifecycle_investigation import migration
    from tests.test_security_lifecycle_population import stores

    _, profile = stores(tmp_path)
    before = migration.preview_installation(profile)
    backup = tmp_path / "backup.db"
    if change == "backup_exists":
        backup.write_bytes(b"must-retain")
        expected = FileExistsError
    else:
        original = migration.preview_installation

        def changed(path):
            result = original(path)
            with closing(sqlite3.connect(profile)) as conn:
                conn.execute("CREATE TABLE independent_data(value TEXT)")
                conn.commit()
            return result

        monkeypatch.setattr(migration, "preview_installation", changed)
        expected = ValueError
    with pytest.raises(expected):
        migration.apply_installation(profile, backup_path=backup, approval_sha256=before["approval_sha256"], at=AT, app_stopped=True)
    if change == "backup_exists":
        assert backup.read_bytes() == b"must-retain"
    with closing(sqlite3.connect(profile)) as conn:
        assert not conn.execute("SELECT 1 FROM sqlite_master WHERE name='lifecycle_investigation_jobs'").fetchone()


def test_current_installation_rolls_back_schema_on_postflight_failure(tmp_path, monkeypatch):
    from src.lifecycle_investigation import migration, schema
    from tests.test_security_lifecycle_population import stores

    _, profile = stores(tmp_path)
    before = migration.preview_installation(profile)
    backup = tmp_path / "backup.db"
    original = schema.verify_journal

    def fail(conn):
        original(conn)
        raise ValueError("synthetic_postflight_failure")

    monkeypatch.setattr(schema, "verify_journal", fail)
    with pytest.raises(ValueError, match="synthetic_postflight_failure"):
        migration.apply_installation(profile, backup_path=backup, approval_sha256=before["approval_sha256"], at=AT, app_stopped=True)
    assert migration.preview_installation(profile) == before
    assert migration.preview_installation(backup) == before
