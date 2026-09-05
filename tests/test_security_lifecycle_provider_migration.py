from __future__ import annotations

import sqlite3

import pytest

from src.profile_state import ProfileStateStore
from src.security_lifecycle_schema import create_v3_profile_schema, verify_profile_connection


def test_cutover_preserves_dual_source_lineage_from_real_capture_rows(tmp_path):
    from src import sa_capture_store
    from src.active_universe import build_active_universe_snapshot
    from src.portfolio_state import PortfolioStore
    from src.sa_tracking_memberships import read_sa_tracking_observations
    from src.security_lifecycle_provider_migration import preview_provider_cutover, apply_provider_cutover
    from tests.test_sa_capture_store import _pick

    profile, sa = tmp_path / "profile.db", tmp_path / "sa.db"
    ProfileStateStore(profile)
    PortfolioStore(profile)
    with sqlite3.connect(profile) as conn:
        create_v3_profile_schema(conn)
    conn = sa_capture_store.connect(str(sa))
    try:
        _pick(conn, "BOTH", "current")
        _pick(conn, "BOTH", "closed", closed="2026-08-01")
        _pick(conn, "BOTH", "closed", closed="2026-08-15")
        _pick(conn, "CURRENT", "current")
        _pick(conn, "FORMER", "closed", closed="2026-08-20")
        conn.execute("UPDATE sa_alpha_picks SET last_seen_snapshot='2026-09-05T01:00:00Z'")
        conn.commit()
    finally:
        conn.close()
    before = build_active_universe_snapshot(profile_db=profile, sa_db=sa)
    rows = read_sa_tracking_observations(sa)
    assert len(rows) == 3
    dual = next(row for row in rows if row["ticker"] == "BOTH")
    assert dual["portfolio_status"] == "closed"
    assert dual.get("current_observed") is True
    preview = preview_provider_cutover(profile, sa)
    apply_provider_cutover(profile, sa, backup_path=tmp_path / "backup.db",
                           cutover_sha256=preview["cutover_sha256"], at="2026-09-05T01:01:00Z", app_stopped=True)
    after = build_active_universe_snapshot(profile_db=profile, sa_db=sa)
    assert after.tickers == before.tickers
    assert after.sources_by_ticker == before.sources_by_ticker


def test_provider_upgrade_preserves_old_rows_and_has_create_only_backup(tmp_path):
    from src.security_lifecycle_provider_migration import preflight_provider_upgrade, upgrade_provider_authority

    path = tmp_path / "profile.db"
    ProfileStateStore(path)
    with sqlite3.connect(path) as conn:
        create_v3_profile_schema(conn)
        conn.execute("INSERT INTO security_lifecycle_cases VALUES ('old', 'sec_edgar', 'ref', 'OLD', 'then', 'then')")
    preflight = preflight_provider_upgrade(path)
    backup = tmp_path / "backup.db"
    result = upgrade_provider_authority(path, backup_path=backup, approval_sha256=preflight["approval_sha256"])
    assert result["changed"] is True
    assert preflight_provider_upgrade(backup) == preflight
    with sqlite3.connect(path) as conn:
        verify_profile_connection(conn)
        assert conn.execute("SELECT source, source_ref FROM security_lifecycle_cases").fetchall() == [("sec_edgar", "ref")]
        assert conn.execute("SELECT COUNT(*) FROM sa_tracking_memberships").fetchone() == (0,)
        assert conn.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    current = preflight_provider_upgrade(path)
    assert upgrade_provider_authority(path, backup_path=tmp_path / "unused.db", approval_sha256=current["approval_sha256"])["changed"] is False
    assert not (tmp_path / "unused.db").exists()


def test_changed_profile_requires_new_migration_preview(tmp_path):
    from src.security_lifecycle_provider_migration import preflight_provider_upgrade, upgrade_provider_authority

    path = tmp_path / "profile.db"
    ProfileStateStore(path)
    with sqlite3.connect(path) as conn:
        create_v3_profile_schema(conn)
    preflight = preflight_provider_upgrade(path)
    with sqlite3.connect(path) as conn:
        conn.execute("INSERT INTO ticker_meta VALUES ('NEW', NULL, NULL, 'today')")
    with pytest.raises(ValueError, match="provider_upgrade_preview_changed"):
        upgrade_provider_authority(path, backup_path=tmp_path / "backup.db", approval_sha256=preflight["approval_sha256"])
    assert not (tmp_path / "backup.db").exists()


@pytest.mark.parametrize("fail_bootstrap", (False, True))
def test_membership_bootstrap_is_atomic_with_the_schema_upgrade(tmp_path, monkeypatch, fail_bootstrap):
    from src.sa_tracking_memberships import SaTrackingMembershipStore
    from src.security_lifecycle_provider_migration import preflight_provider_upgrade, upgrade_provider_authority
    path = tmp_path / "profile.db"
    ProfileStateStore(path)
    with sqlite3.connect(path) as conn:
        create_v3_profile_schema(conn)
    before = preflight_provider_upgrade(path)
    observation = {"lineage_id": 1, "ticker": "ARCH", "picked_date": "2023-01-01",
                   "portfolio_status": "closed", "observed_at": "2026-09-05T01:00:00Z"}
    original = SaTrackingMembershipStore.reconcile_in_transaction
    def bootstrap(conn, *args, **kwargs):
        assert conn.in_transaction
        original(conn, *args, **kwargs)
        if fail_bootstrap:
            raise ValueError("bootstrap_failed")
    monkeypatch.setattr(SaTrackingMembershipStore, "reconcile_in_transaction", staticmethod(bootstrap))
    kwargs = dict(backup_path=tmp_path / "backup.db", approval_sha256=before["approval_sha256"],
                  bootstrap_observations=(observation,), at="2026-09-05T01:01:00Z")
    if fail_bootstrap:
        with pytest.raises(ValueError, match="bootstrap_failed"):
            upgrade_provider_authority(path, **kwargs)
        assert preflight_provider_upgrade(path) == before
    else:
        upgrade_provider_authority(path, **kwargs)
        assert SaTrackingMembershipStore(path).active_sources() == {"sa_alpha_picks_former": {"ARCH"}}
        with sqlite3.connect(path) as conn:
            assert conn.execute("SELECT actor FROM sa_tracking_events").fetchall() == [("attended_user",)]
            assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    assert preflight_provider_upgrade(tmp_path / "backup.db") == before


def test_upgrade_preserves_real_v3_evidence_translations_identity_and_unowned_sql(tmp_path):
    from tests.test_security_lifecycle_listing_migration import _seeded_v2_profile
    from src.security_lifecycle_listing_migration import preflight_listing_authority_migration, create_listing_authority_backup, migrate_listing_authority_schema
    from src.security_lifecycle_provider_migration import preflight_provider_upgrade, upgrade_provider_authority
    path = _seeded_v2_profile(tmp_path)
    v2 = preflight_listing_authority_migration(path)
    backup = create_listing_authority_backup(path, tmp_path / "v2-backup.db", approval_sha256=v2.approval_sha256)
    migrate_listing_authority_schema(path, approval_sha256=v2.approval_sha256, backup_sha256=backup.sha256)
    ProfileStateStore(path)
    with sqlite3.connect(path) as conn:
        names = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        before = {name: conn.execute(f'SELECT rowid,* FROM "{name}" ORDER BY rowid').fetchall() for name in names}
        unowned_sql = conn.execute("SELECT name,sql FROM sqlite_master WHERE name NOT LIKE 'security_lifecycle_%' AND name NOT LIKE 'idx_security_lifecycle_%' AND sql IS NOT NULL ORDER BY name").fetchall()
    preview = preflight_provider_upgrade(path)
    upgrade_provider_authority(path, backup_path=tmp_path / "v3-backup.db", approval_sha256=preview["approval_sha256"])
    with sqlite3.connect(path) as conn:
        for name, rows in before.items():
            assert conn.execute(f'SELECT rowid,* FROM "{name}" ORDER BY rowid').fetchall() == rows, name
        for name, sql in unowned_sql:
            assert conn.execute("SELECT sql FROM sqlite_master WHERE name=?", (name,)).fetchone()[0] == sql


def test_cutover_requires_stopped_app_and_exact_sa_observation_set(tmp_path, monkeypatch):
    from src import security_lifecycle_provider_migration as migration
    from tests.test_sa_tracking_memberships import observation, AT
    path = tmp_path / "profile.db"
    ProfileStateStore(path)
    with sqlite3.connect(path) as conn:
        create_v3_profile_schema(conn)
    rows = [observation(1, "ARCH")]
    monkeypatch.setattr(migration, "read_sa_tracking_observations", lambda path: tuple(rows))
    preview = migration.preview_provider_cutover(path, "unused-sa-path")
    assert preview["former_count"] == 1
    kwargs = dict(backup_path=tmp_path / "backup.db", cutover_sha256=preview["cutover_sha256"], at=AT)
    with pytest.raises(ValueError, match="app_stop_required"):
        migration.apply_provider_cutover(path, "unused-sa-path", app_stopped=False, **kwargs)
    rows.append(observation(2, "NEW", "current"))
    with pytest.raises(ValueError, match="preview_changed"):
        migration.apply_provider_cutover(path, "unused-sa-path", app_stopped=True, **kwargs)
    assert not (tmp_path / "backup.db").exists()
    rows.pop()
    receipt = migration.apply_provider_cutover(path, "unused-sa-path", app_stopped=True, **kwargs)
    assert receipt["memberships"][0]["state"] == "tracking"
    assert receipt["actor"] == "attended_user"


@pytest.mark.parametrize("setting,value", (
    ("enabled", "true"),
    ("apply_profile_transitions", "true"),
    ("enabled", None),
    ("interval_minutes", "invalid"),
))
def test_provider_upgrade_requires_valid_disabled_automation_before_backup(tmp_path, setting, value):
    from src.security_lifecycle_provider_migration import preflight_provider_upgrade, upgrade_provider_authority

    path = tmp_path / "profile.db"
    store = ProfileStateStore(path)
    with sqlite3.connect(path) as conn:
        create_v3_profile_schema(conn)
    store.set_setting(f"security_lifecycle.automation.{setting}", value)
    preview = preflight_provider_upgrade(path)
    backup = tmp_path / "backup.db"
    with pytest.raises(ValueError, match="provider_upgrade_automation_disable_required"):
        upgrade_provider_authority(path, backup_path=backup, approval_sha256=preview["approval_sha256"])
    assert not backup.exists()
    assert preflight_provider_upgrade(path)["schema_version"] == "v3"


def test_migration_preview_binds_automation_controls_but_not_other_settings(tmp_path):
    from src.security_lifecycle_provider_migration import preflight_provider_upgrade, upgrade_provider_authority

    path = tmp_path / "profile.db"
    store = ProfileStateStore(path)
    with sqlite3.connect(path) as conn:
        create_v3_profile_schema(conn)
    preview = preflight_provider_upgrade(path)
    store.set_setting("unrelated.private.setting", "not-part-of-cutover")
    assert preflight_provider_upgrade(path) == preview
    store.set_setting("security_lifecycle.automation.batch_limit", "1")
    changed = preflight_provider_upgrade(path)
    assert changed["approval_sha256"] != preview["approval_sha256"]
    with pytest.raises(ValueError, match="provider_upgrade_preview_changed"):
        upgrade_provider_authority(path, backup_path=tmp_path / "old.db", approval_sha256=preview["approval_sha256"])
    result = upgrade_provider_authority(path, backup_path=tmp_path / "backup.db", approval_sha256=changed["approval_sha256"])
    assert result["changed"] is True
    assert result["automation"] == {"valid": True, "enabled": False, "apply_profile_transitions": False}


def test_provider_upgrade_rechecks_controls_after_backup(tmp_path, monkeypatch):
    from src import security_lifecycle_provider_migration as migration

    path = tmp_path / "profile.db"
    store = ProfileStateStore(path)
    with sqlite3.connect(path) as conn:
        create_v3_profile_schema(conn)
    preview = migration.preflight_provider_upgrade(path)
    original = migration.preflight_provider_upgrade

    def changed_after_backup(backup_path):
        result = original(backup_path)
        store.set_setting("security_lifecycle.automation.enabled", "true")
        return result

    monkeypatch.setattr(migration, "preflight_provider_upgrade", changed_after_backup)
    with pytest.raises(ValueError, match="provider_upgrade_preview_changed"):
        migration.upgrade_provider_authority(path, backup_path=tmp_path / "backup.db", approval_sha256=preview["approval_sha256"])
    assert original(path)["schema_version"] == "v3"
