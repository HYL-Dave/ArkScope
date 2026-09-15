"""Current V4 membership provisioning, independent of retired converters."""

from contextlib import closing
import hashlib
from importlib import import_module
from pathlib import Path
import sqlite3
import stat
import threading

import pytest

from src.profile_state import ProfileStateStore
from src.sa_tracking_memberships import SaTrackingMembershipStore
from src.security_lifecycle_schema import verify_profile_connection
from tests.current_installation_fixtures import seeded_current_profile
from tests.test_sa_tracking_memberships import observation, AT


def owner():
    path = Path(__file__).resolve().parents[1] / "src/sa_tracking_installation.py"
    assert path.is_file(), "current V4 membership installation owner is missing"
    return import_module("src.sa_tracking_installation")


def retained_state(path):
    with closing(sqlite3.connect(path)) as conn:
        schema = conn.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_master "
            "WHERE name NOT LIKE '%sa_tracking_%' AND tbl_name NOT LIKE 'sa_tracking_%' "
            "ORDER BY type,name"
        ).fetchall()
        rows = {
            name: conn.execute(f'SELECT rowid,* FROM "{name}" ORDER BY rowid').fetchall()
            for kind, name, _, _ in schema if kind == "table"
        }
        if "sqlite_sequence" in rows:
            rows["sqlite_sequence"] = [row for row in rows["sqlite_sequence"] if not row[1].startswith("sa_tracking_")]
        return schema, rows


def capture(tmp_path):
    from src import sa_capture_store
    from tests.test_sa_capture_store import _pick

    path = tmp_path / "sa.db"
    with closing(sa_capture_store.connect(str(path))) as conn:
        _pick(conn, "BOTH", "current")
        _pick(conn, "BOTH", "closed", closed="2026-08-01")
        _pick(conn, "BOTH", "closed", closed="2026-08-15")
        _pick(conn, "CURRENT", "current")
        _pick(conn, "FORMER", "closed", closed="2026-08-20")
        conn.execute("UPDATE sa_alpha_picks SET last_seen_snapshot=?", (AT,))
        conn.commit()
    return path


def test_fixture_is_populated_current_v4_without_tracking_installation(tmp_path):
    path = seeded_current_profile(tmp_path)
    with closing(sqlite3.connect(path)) as conn:
        verify_profile_connection(conn)
        assert not SaTrackingMembershipStore.installed(conn)
        for table in (
            "security_lifecycle_cases", "security_lifecycle_evidence",
            "security_lifecycle_evidence_translations", "security_lifecycle_assessments",
            "security_lifecycle_migration_receipts", "security_lifecycle_provider_checks",
            "ticker_identity_transitions", "ticker_identity_links", "job_runs",
        ):
            assert conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] > 0
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_attended_installation_preserves_real_capture_dual_source_lineage(tmp_path):
    installation = owner()
    from src.active_universe import build_active_universe_snapshot
    from src.sa_tracking_memberships import read_sa_tracking_observations

    profile, sa = seeded_current_profile(tmp_path), capture(tmp_path)
    before = build_active_universe_snapshot(profile_db=profile, sa_db=sa)
    retained = retained_state(profile)
    observations = read_sa_tracking_observations(sa)
    assert len(observations) == 3
    dual = next(row for row in observations if row["ticker"] == "BOTH")
    assert dual["portfolio_status"] == "closed" and dual["current_observed"] is True
    preview = installation.preview_installation(profile, sa)
    assert {key: preview[key] for key in (
        "lineage_count", "current_count", "former_count", "current_observed_count", "dual_source_count",
    )} == {"lineage_count": 3, "current_count": 1, "former_count": 2,
           "current_observed_count": 2, "dual_source_count": 1}
    sa_bytes = sa.read_bytes()
    result = installation.apply_installation(profile, sa, backup_path=tmp_path / "backup.db",
        cutover_sha256=preview["cutover_sha256"], at=AT, app_stopped=True)
    after = build_active_universe_snapshot(profile_db=profile, sa_db=sa)
    assert after.tickers == before.tickers
    assert after.sources_by_ticker == before.sources_by_ticker
    assert result["actor"] == "attended_user" and result["at"] == AT
    assert result["bootstrap"] == preview
    assert {(row["ticker"], row["portfolio_status"]) for row in result["memberships"]} == {
        ("BOTH", "current"), ("BOTH", "closed"), ("CURRENT", "current"), ("FORMER", "closed"),
    }
    assert len({row["membership_id"] for row in result["memberships"]}) == 3
    assert retained_state(profile) == retained
    assert sa.read_bytes() == sa_bytes


def test_installation_preserves_all_rows_rowids_sequences_and_sql_with_private_backup(tmp_path):
    installation = owner()
    path = seeded_current_profile(tmp_path)
    retained = retained_state(path)
    before_bytes = path.read_bytes()
    before = installation.inspect_installation(path)
    assert installation.inspect_installation(path) == before
    assert path.read_bytes() == before_bytes
    assert before["schema_version"] == "v4" and not before["membership_installed"]
    backup = tmp_path / "private" / "backup.db"
    result = installation._install_memberships(path, backup_path=backup, approval_sha256=before["approval_sha256"])
    assert result["changed"] and result["membership_installed"]
    assert result["backup_sha256"] == hashlib.sha256(backup.read_bytes()).hexdigest()
    assert stat.S_IMODE(backup.stat().st_mode) == 0o600
    assert stat.S_IMODE(backup.parent.stat().st_mode) == 0o700
    assert installation.inspect_installation(backup) == before
    assert retained_state(path) == retained == retained_state(backup)
    with closing(sqlite3.connect(path)) as conn:
        verify_profile_connection(conn)
        assert conn.execute("SELECT COUNT(*) FROM sa_tracking_memberships").fetchone() == (0,)
        assert conn.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_noop_keeps_removed_memberships_and_does_not_create_a_backup(tmp_path):
    installation = owner()
    path, sa = seeded_current_profile(tmp_path), capture(tmp_path)
    preview = installation.preview_installation(path, sa)
    installation.apply_installation(path, sa, backup_path=tmp_path / "backup.db",
        cutover_sha256=preview["cutover_sha256"], at=AT, app_stopped=True)
    store = SaTrackingMembershipStore(path)
    former = next(row for row in store.list_memberships() if row["ticker"] == "FORMER")
    store.remove(former["membership_id"], at=AT)
    expected = store.list_memberships()
    current = installation.preview_installation(path, sa)
    before_bytes = path.read_bytes()
    result = installation.apply_installation(path, sa, backup_path=tmp_path / "unused.db",
        cutover_sha256=current["cutover_sha256"], at=AT, app_stopped=True)
    assert result["changed"] is False and result["memberships"] == expected
    assert path.read_bytes() == before_bytes
    assert not (tmp_path / "unused.db").exists()
    with pytest.raises(ValueError, match="preview_changed"):
        installation._install_memberships(path, backup_path=tmp_path / "unused.db",
            approval_sha256=preview["profile"]["approval_sha256"])
    assert path.read_bytes() == before_bytes


@pytest.mark.parametrize("same_source", (False, True))
def test_backup_is_create_only_and_never_overwrites_source_or_destination(tmp_path, same_source):
    installation = owner()
    path = seeded_current_profile(tmp_path)
    before = installation.inspect_installation(path)
    backup = path if same_source else tmp_path / "backup.db"
    if not same_source:
        backup.write_bytes(b"retained-backup")
    original = backup.read_bytes()
    with pytest.raises(ValueError if same_source else FileExistsError):
        installation._install_memberships(path, backup_path=backup, approval_sha256=before["approval_sha256"])
    assert backup.read_bytes() == original
    assert installation.inspect_installation(path) == before


def test_changed_profile_requires_new_preview_before_backup(tmp_path):
    installation = owner()
    path = seeded_current_profile(tmp_path)
    before = installation.inspect_installation(path)
    with sqlite3.connect(path) as conn:
        conn.execute("INSERT INTO ticker_meta VALUES ('CHANGED', NULL, NULL, 'today')")
    with pytest.raises(ValueError, match="provider_upgrade_preview_changed"):
        installation._install_memberships(path, backup_path=tmp_path / "backup.db", approval_sha256=before["approval_sha256"])
    assert not (tmp_path / "backup.db").exists()
    assert installation.inspect_installation(path)["membership_installed"] is False


@pytest.mark.parametrize("failure", (None, ValueError, KeyboardInterrupt))
def test_membership_bootstrap_is_atomic_with_ddl_and_attended_receipts(tmp_path, monkeypatch, failure):
    installation = owner()
    path = seeded_current_profile(tmp_path)
    before = installation.inspect_installation(path)
    retained = retained_state(path)
    original = SaTrackingMembershipStore.reconcile_in_transaction

    def bootstrap(conn, *args, **kwargs):
        assert conn.in_transaction
        original(conn, *args, **kwargs)
        if failure:
            raise failure("bootstrap_failed")

    monkeypatch.setattr(SaTrackingMembershipStore, "reconcile_in_transaction", staticmethod(bootstrap))
    kwargs = dict(backup_path=tmp_path / "backup.db", approval_sha256=before["approval_sha256"],
        bootstrap_observations=(observation(1, "ARCH"),), at=AT)
    if failure:
        with pytest.raises(failure, match="bootstrap_failed"):
            installation._install_memberships(path, **kwargs)
        assert installation.inspect_installation(path) == before
    else:
        installation._install_memberships(path, **kwargs)
        assert SaTrackingMembershipStore(path).active_sources() == {"sa_alpha_picks_former": {"ARCH"}}
        with closing(sqlite3.connect(path)) as conn:
            assert conn.execute("SELECT actor FROM sa_tracking_events").fetchall() == [("attended_user",)]
            assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    assert retained_state(path) == retained
    assert installation.inspect_installation(tmp_path / "backup.db") == before


@pytest.mark.parametrize("stopped", (False, None, 1, "true"))
def test_attended_installation_requires_stopped_app_before_opening_stores(tmp_path, stopped):
    installation = owner()
    with pytest.raises(ValueError, match="app_stop_required"):
        installation.apply_installation(tmp_path / "profile.db", tmp_path / "sa.db",
            backup_path=tmp_path / "backup.db", cutover_sha256="a" * 64, at=AT, app_stopped=stopped)
    assert list(tmp_path.iterdir()) == []


def test_attended_preview_binds_the_exact_real_sa_observation_set(tmp_path):
    installation = owner()
    profile, sa = seeded_current_profile(tmp_path), capture(tmp_path)
    preview = installation.preview_installation(profile, sa)
    with sqlite3.connect(sa) as conn:
        conn.execute("UPDATE sa_alpha_picks SET last_seen_snapshot='2026-09-05T02:00:00Z' WHERE symbol='BOTH'")
    with pytest.raises(ValueError, match="provider_cutover_preview_changed"):
        installation.apply_installation(profile, sa, backup_path=tmp_path / "backup.db",
            cutover_sha256=preview["cutover_sha256"], at=AT, app_stopped=True)
    assert not (tmp_path / "backup.db").exists()
    assert installation.inspect_installation(profile)["membership_installed"] is False


@pytest.mark.parametrize("setting,value", (
    ("enabled", "true"), ("apply_profile_transitions", "true"),
    ("enabled", None), ("interval_minutes", "invalid"),
))
def test_valid_disabled_automation_is_required_before_backup_and_noop(tmp_path, setting, value):
    installation = owner()
    path = seeded_current_profile(tmp_path)
    store = ProfileStateStore(path)
    store.set_setting(f"security_lifecycle.automation.{setting}", value)
    before = installation.inspect_installation(path)
    with pytest.raises(ValueError, match="provider_upgrade_automation_disable_required"):
        installation._install_memberships(path, backup_path=tmp_path / "backup.db", approval_sha256=before["approval_sha256"])
    assert not (tmp_path / "backup.db").exists()
    assert installation.inspect_installation(path) == before
    with sqlite3.connect(path) as conn:
        SaTrackingMembershipStore.install(conn)
    current = installation.inspect_installation(path)
    with pytest.raises(ValueError, match="provider_upgrade_automation_disable_required"):
        installation._install_memberships(path, backup_path=tmp_path / "unused.db", approval_sha256=current["approval_sha256"])
    assert not (tmp_path / "unused.db").exists()


def test_preview_binds_automation_controls_but_not_unrelated_settings(tmp_path):
    installation = owner()
    path = seeded_current_profile(tmp_path)
    store = ProfileStateStore(path)
    before = installation.inspect_installation(path)
    store.set_setting("unrelated.private.setting", "not-part-of-installation")
    assert installation.inspect_installation(path) == before
    store.set_setting("security_lifecycle.automation.batch_limit", "1")
    changed = installation.inspect_installation(path)
    assert changed["approval_sha256"] != before["approval_sha256"]
    with pytest.raises(ValueError, match="preview_changed"):
        installation._install_memberships(path, backup_path=tmp_path / "unused.db", approval_sha256=before["approval_sha256"])
    result = installation._install_memberships(path, backup_path=tmp_path / "backup.db", approval_sha256=changed["approval_sha256"])
    assert result["changed"] is True
    assert result["automation"] == {"valid": True, "enabled": False, "apply_profile_transitions": False}


@pytest.mark.parametrize("target", ("source_controls", "source_rows", "backup"))
def test_installation_rechecks_backup_and_locked_profile_before_ddl(tmp_path, monkeypatch, target):
    installation = owner()
    path = seeded_current_profile(tmp_path)
    before = installation.inspect_installation(path)
    backup = tmp_path / "backup.db"
    inspect = installation.inspect_installation

    def changed_after_backup(candidate):
        assert Path(candidate) == backup
        if target == "backup":
            with sqlite3.connect(backup) as conn:
                conn.execute("UPDATE security_lifecycle_cases SET updated_at='changed'")
        result = inspect(candidate)
        if target == "source_controls":
            ProfileStateStore(path).set_setting("security_lifecycle.automation.enabled", "true")
        elif target == "source_rows":
            with sqlite3.connect(path) as conn:
                conn.execute("UPDATE security_lifecycle_cases SET updated_at='changed'")
        return result

    monkeypatch.setattr(installation, "inspect_installation", changed_after_backup)
    code = "backup_changed" if target == "backup" else "preview_changed"
    with pytest.raises(ValueError, match=code):
        installation._install_memberships(path, backup_path=backup, approval_sha256=before["approval_sha256"])
    assert inspect(path)["membership_installed"] is False
    if target == "backup":
        assert inspect(path) == before
    else:
        assert inspect(backup) == before


@pytest.mark.parametrize("version", (2, 3))
def test_obsolete_schemas_are_rejected_without_conversion_or_backup(tmp_path, version):
    installation = owner()
    from src import security_lifecycle_schema as schema

    path = tmp_path / "obsolete.db"
    ProfileStateStore(path)
    with sqlite3.connect(path) as conn:
        getattr(schema, f"create_v{version}_profile_schema")(conn)
    before = path.read_bytes()
    with pytest.raises(schema.LifecycleSchemaMismatch):
        installation.inspect_installation(path)
    with pytest.raises(schema.LifecycleSchemaMismatch):
        installation._install_memberships(path, backup_path=tmp_path / "backup.db", approval_sha256="a" * 64)
    assert path.read_bytes() == before
    assert not (tmp_path / "backup.db").exists()


def test_inspection_uses_one_read_snapshot_during_concurrent_writer_commit(tmp_path, monkeypatch):
    installation = owner()
    path = seeded_current_profile(tmp_path)
    with sqlite3.connect(path) as conn:
        assert conn.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
        conn.execute("PRAGMA wal_autocheckpoint=0")
    before = installation.inspect_installation(path)
    started, committed = threading.Event(), threading.Event()
    errors = []

    def writer():
        try:
            assert started.wait(timeout=5)
            with sqlite3.connect(path, timeout=5) as conn:
                conn.execute("UPDATE security_lifecycle_cases SET updated_at='concurrent'")
        except BaseException as error:
            errors.append(error)
        finally:
            committed.set()

    real_digest = installation._digest

    def pause_digest(conn):
        assert conn.in_transaction
        started.set()
        assert committed.wait(timeout=5)
        return real_digest(conn)

    monkeypatch.setattr(installation, "_digest", pause_digest)
    thread = threading.Thread(target=writer)
    thread.start()
    try:
        during = installation.inspect_installation(path)
    finally:
        thread.join(timeout=5)
    assert not thread.is_alive() and errors == []
    monkeypatch.setattr(installation, "_digest", real_digest)
    assert during == before
    assert installation.inspect_installation(path) != before


@pytest.mark.parametrize("related", (False, True))
def test_bootstrap_uses_persisted_identity_links_and_related_security_context(tmp_path, related):
    installation = owner()
    path = seeded_current_profile(tmp_path)
    successor = "RELATED" if related else "NEW"
    if related:
        with sqlite3.connect(path) as conn:
            conn.execute("UPDATE security_lifecycle_assessments SET counterparty_ticker='RELATED'")
            conn.execute("UPDATE security_lifecycle_assessment_outcomes SET outcome='acquisition_stock'")
    retained = retained_state(path)
    before = installation.inspect_installation(path)
    installation._install_memberships(path, backup_path=tmp_path / "backup.db",
        approval_sha256=before["approval_sha256"],
        bootstrap_observations=(observation(1, "OLD"), observation(2, successor)), at=AT)
    with closing(sqlite3.connect(path)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM sa_tracking_bindings").fetchone() == (2,)
        members = conn.execute("SELECT ticker,reason,accepted_at IS NOT NULL FROM sa_tracking_memberships ORDER BY ticker").fetchall()
        expected = [("OLD", "bootstrap_accepted", 1)]
        if related:
            expected.append(("RELATED", "related_security", 0))
        assert members == expected
    displayed = SaTrackingMembershipStore(path).list_memberships()
    assert {(row["ticker"], row["state"]) for row in displayed} == (
        {("NEW", "tracking"), ("RELATED", "candidate")} if related else {("NEW", "tracking")}
    )
    assert retained_state(path) == retained


@pytest.mark.parametrize("damage", ("foreign_key", "missing_table", "changed_table", "partial_membership"))
def test_malformed_current_profile_is_rejected_without_backup_or_repair(tmp_path, damage):
    installation = owner()
    from src.security_lifecycle_schema import LifecycleSchemaMismatch

    path = seeded_current_profile(tmp_path)
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute({
            "foreign_key": "UPDATE security_lifecycle_evidence SET case_id='missing'",
            "missing_table": "DROP TABLE security_lifecycle_provider_checks",
            "changed_table": "ALTER TABLE security_lifecycle_evidence ADD COLUMN unreviewed TEXT",
            "partial_membership": "CREATE TABLE sa_tracking_memberships(value TEXT)",
        }[damage])
    before = path.read_bytes()
    error = ValueError if damage == "partial_membership" else LifecycleSchemaMismatch
    with pytest.raises(error):
        installation.inspect_installation(path)
    with pytest.raises(error):
        installation._install_memberships(path, backup_path=tmp_path / "backup.db", approval_sha256="a" * 64)
    assert path.read_bytes() == before
    assert not (tmp_path / "backup.db").exists()


def test_inspection_and_installation_do_not_create_a_missing_profile(tmp_path):
    installation = owner()
    path = tmp_path / "absent.db"
    with pytest.raises(sqlite3.OperationalError):
        installation.inspect_installation(path)
    with pytest.raises(sqlite3.OperationalError):
        installation._install_memberships(path, backup_path=tmp_path / "backup.db", approval_sha256="a" * 64)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("failure", (False, True))
def test_inspection_rolls_back_and_closes_read_snapshot_on_success_and_error(tmp_path, monkeypatch, failure):
    installation = owner()
    path = seeded_current_profile(tmp_path)
    before = path.read_bytes()
    real_connect = sqlite3.connect
    opened = []

    class TrackingConnection(sqlite3.Connection):
        rollback_calls = 0
        close_calls = 0

        def rollback(self):
            self.rollback_calls += 1
            return super().rollback()

        def close(self):
            self.close_calls += 1
            return super().close()

    def connect(*args, **kwargs):
        conn = real_connect(*args, **kwargs, factory=TrackingConnection)
        opened.append(conn)
        return conn

    preflight = installation._preflight

    def inspect(conn):
        assert conn.in_transaction
        assert conn.execute("PRAGMA query_only").fetchone() == (1,)
        if failure:
            raise ValueError("forced_inspection_failure")
        return preflight(conn)

    monkeypatch.setattr(installation.sqlite3, "connect", connect)
    monkeypatch.setattr(installation, "_preflight", inspect)
    if failure:
        with pytest.raises(ValueError, match="forced_inspection_failure"):
            installation.inspect_installation(path)
    else:
        installation.inspect_installation(path)
    assert len(opened) == 1
    assert opened[0].rollback_calls == opened[0].close_calls == 1
    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        opened[0].execute("SELECT 1")
    assert path.read_bytes() == before
