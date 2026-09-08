import sqlite3

import pytest

from src.lifecycle_investigation.migration import preview_installation, apply_installation
from tests.test_security_lifecycle_population import stores


def test_cutover_is_explicit_backed_up_and_preserves_existing_content(tmp_path):
    _, profile = stores(tmp_path)
    plan = preview_installation(profile)
    assert not plan["installed"]
    with pytest.raises(ValueError, match="app_stop_required"):
        apply_installation(profile, backup_path=tmp_path / "backup", approval_sha256=plan["approval_sha256"], at="2026-09-08T00:00:00Z", app_stopped=False)
    result = apply_installation(profile, backup_path=tmp_path / "backup", approval_sha256=plan["approval_sha256"], at="2026-09-08T00:00:00Z", app_stopped=True)
    assert result["changed"] and len(result["backup_sha256"]) == 64
    assert preview_installation(tmp_path / "backup") == plan
    assert preview_installation(profile)["installed"]


def test_changed_installation_preview_is_rejected_before_backup(tmp_path):
    _, profile = stores(tmp_path)
    plan = preview_installation(profile)
    with sqlite3.connect(profile) as conn:
        conn.execute("CREATE TABLE independent_data(value TEXT)")
    with pytest.raises(ValueError, match="install_changed"):
        apply_installation(profile, backup_path=tmp_path / "backup", approval_sha256=plan["approval_sha256"], at="2026-09-08T00:00:00Z", app_stopped=True)
    assert not (tmp_path / "backup").exists()


def test_installation_preserves_unrelated_without_rowid_tables(tmp_path):
    _, profile = stores(tmp_path)
    with sqlite3.connect(profile) as conn:
        conn.execute("CREATE TABLE independent_data(key TEXT PRIMARY KEY, value TEXT) WITHOUT ROWID")
        conn.execute("INSERT INTO independent_data VALUES ('keep','unchanged')")
    plan = preview_installation(profile)
    apply_installation(profile, backup_path=tmp_path / "backup", approval_sha256=plan["approval_sha256"], at="2026-09-08T00:00:00Z", app_stopped=True)
    with sqlite3.connect(profile) as conn:
        assert conn.execute("SELECT * FROM independent_data").fetchall() == [("keep", "unchanged")]
