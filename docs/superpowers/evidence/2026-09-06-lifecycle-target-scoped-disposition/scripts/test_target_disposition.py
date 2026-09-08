"""Target-scoped service boundaries, with concurrent temporary-store writers."""

from contextlib import closing, contextmanager
import importlib.util
import json
from pathlib import Path
import socket
import sqlite3

import pytest


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


operation = load("scoped_disposition", Path(__file__).with_name("disposition.py"))
old_tests = load("disposition_seed_fixture", operation.V1 / "scripts/test_disposition.py")
NOW = old_tests.NOW
LATER = "2026-09-05T17:00:00+00:00"
TARGETS = ("ARCH", "LTHM", "TA")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("scoped_maintenance_network_forbidden")
    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)


@pytest.fixture
def case(tmp_path):
    value = old_tests.case.__wrapped__(tmp_path)
    for path in value["paths"].values():
        with closing(sqlite3.connect(path)) as conn:
            assert conn.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
    return value


def rows(path, sql):
    with closing(sqlite3.connect(path)) as conn:
        return conn.execute(sql).fetchall()


def refresh_time(path, value=LATER):
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("UPDATE sa_alpha_picks SET last_seen_snapshot=?", (value,))
        conn.commit()


def execute(case, prepared):
    return operation.apply(case["paths"], case["directory"], approved_sha256=prepared["plan_sha256"], clock=lambda: LATER)


def add_unrelated_current(case):
    from src.sa_tracking_memberships import reconcile_sa_tracking
    from src.tools.backends.sa_capture_backend import SACaptureBackend
    backend = SACaptureBackend(sa_db=str(case["paths"]["sa"]), market_db=str(case["paths"]["market"]),
                               base_path=case["paths"]["sa"].parent)
    assert backend.apply_sa_refresh("current", [{"symbol": "OTHER", "picked_date": "2026-09-01"}], LATER, LATER) == 1
    assert reconcile_sa_tracking(profile_db=case["paths"]["profile"], sa_db=case["paths"]["sa"], at=LATER)


def test_timestamp_only_refresh_before_and_after_rehearsal_is_allowed(case):
    bindings = rows(case["paths"]["profile"], "SELECT * FROM sa_tracking_bindings ORDER BY lineage_id")
    refresh_time(case["paths"]["sa"], "2026-09-05T16:00:00Z")
    prepared = operation.prepare(**case, clock=lambda: NOW)
    refresh_time(case["paths"]["sa"])
    applied = execute(case, prepared)
    assert applied["applied"] == 3 and applied["universe_after"] == 1
    assert rows(case["paths"]["profile"], "SELECT * FROM sa_tracking_bindings ORDER BY lineage_id") == bindings
    assert applied["sa_sync_status"] == "pending"


def test_unrelated_capture_and_profile_changes_are_not_approval_vetoes(case):
    prepared = operation.prepare(**case, clock=lambda: NOW)
    add_unrelated_current(case)
    with closing(sqlite3.connect(case["paths"]["profile"])) as conn:
        conn.execute("UPDATE watchlists SET name='ordinary background change'")
        conn.commit()
    unrelated = rows(case["paths"]["profile"], "SELECT * FROM sa_tracking_memberships WHERE ticker='OTHER'")
    applied = execute(case, prepared)
    assert applied["applied"] == 3 and applied["universe_after"] == 2
    assert rows(case["paths"]["profile"], "SELECT * FROM sa_tracking_memberships WHERE ticker='OTHER'") == unrelated
    assert rows(case["paths"]["profile"], "SELECT name FROM watchlists") == [("ordinary background change",)]


def test_crawler_can_commit_while_private_rehearsal_runs(case, monkeypatch):
    from src.ticker_identity_service import TickerIdentityService
    original_connect = sqlite3.connect
    preview = TickerIdentityService.preview_case
    observed = []
    def with_crawler(service, *args, **kwargs):
        with closing(original_connect(case["paths"]["sa"], timeout=0)) as conn:
            conn.execute("UPDATE sa_alpha_picks SET last_seen_snapshot=?", (LATER,))
            conn.commit()
        observed.append(True)
        return preview(service, *args, **kwargs)
    monkeypatch.setattr(TickerIdentityService, "preview_case", with_crawler)
    prepared = operation.prepare(**case, clock=lambda: NOW)
    assert prepared["rehearsal_applied"] == 3 and len(observed) == 3
    assert rows(case["paths"]["profile"], "SELECT count(*) FROM ticker_identity_transitions") == [(0,)]


def test_unrelated_writer_at_apply_boundary_keeps_its_change(case, monkeypatch):
    from src.ticker_identity_service import TickerIdentityService
    prepared = operation.prepare(**case, clock=lambda: NOW)
    original_connect = sqlite3.connect
    approve = TickerIdentityService.approve_case
    def changed(service, *args, **kwargs):
        with closing(original_connect(case["paths"]["profile"], timeout=0)) as conn:
            conn.execute("UPDATE watchlists SET name='independent writer'")
            conn.commit()
        return approve(service, *args, **kwargs)
    monkeypatch.setattr(TickerIdentityService, "approve_case", changed)
    assert execute(case, prepared)["applied"] == 3
    assert rows(case["paths"]["profile"], "SELECT name FROM watchlists") == [("independent writer",)]


def test_disposition_never_reconciles_live_sa_bindings(case, monkeypatch):
    from src import sa_tracking_memberships
    reconcile = sa_tracking_memberships.reconcile_sa_tracking
    seen = []
    def checked(*, profile_db, **kwargs):
        assert Path(profile_db) != case["paths"]["profile"], "live reconciliation is outside this command"
        seen.append(str(profile_db))
        return reconcile(profile_db=profile_db, **kwargs)
    monkeypatch.setattr(sa_tracking_memberships, "reconcile_sa_tracking", checked)
    prepared = operation.prepare(**case, clock=lambda: NOW)
    assert execute(case, prepared)["applied"] == 3


@pytest.mark.parametrize("change", ["source", "position", "evidence", "sa_status", "sa_anchor", "sa_missing"])
def test_target_material_changes_still_stop_before_application(case, change):
    from src.profile_state import ProfileStateStore
    from src.portfolio_state import PortfolioStore
    from src.security_lifecycle_provider_store import ProviderCheckStore
    prepared = operation.prepare(**case, clock=lambda: NOW)
    if change == "source":
        ProfileStateStore(case["paths"]["profile"]).import_lists([{"name": "New", "kind": "custom", "tickers": ["ARCH"]}])
    elif change == "position":
        portfolio = PortfolioStore(case["paths"]["profile"])
        account = portfolio.ensure_manual_account()
        portfolio.upsert_manual_position(account_id=account.id, symbol="ARCH", quantity=1)
    elif change == "evidence":
        store = ProviderCheckStore(case["paths"]["profile"])
        old = store.latest()["ARCH"]
        store.record(ticker="ARCH", at=LATER, evidence=old["evidence"], diagnostics={}, blockers=old["blockers"])
    else:
        column, value = {"sa_status": ("portfolio_status", "current"), "sa_anchor": ("picked_date", "2024-01-01"),
                         "sa_missing": ("is_stale", 1)}[change]
        with closing(sqlite3.connect(case["paths"]["sa"])) as conn:
            conn.execute(f"UPDATE sa_alpha_picks SET {column}=? WHERE symbol='ARCH'", (value,))
            conn.commit()
    with pytest.raises((operation.DispositionStopped, ValueError)):
        execute(case, prepared)
    assert rows(case["paths"]["profile"], "SELECT count(*) FROM ticker_identity_transitions") == [(0,)]


def test_pinned_backup_is_consistent_while_all_sources_accept_new_commits(case):
    before = {role: rows(path, "SELECT count(*) FROM sqlite_master") for role, path in case["paths"].items()}
    original_profile = rows(case["paths"]["profile"], "SELECT name FROM watchlists")
    original_sa = rows(case["paths"]["sa"], "SELECT last_seen_snapshot FROM sa_alpha_picks ORDER BY lineage_id")
    with operation.pinned_snapshots(case["paths"]) as readers:
        # These commits prove that pinning does not retain any writer reservation.
        with closing(sqlite3.connect(case["paths"]["profile"], timeout=0)) as conn:
            conn.execute("UPDATE watchlists SET name='concurrent'")
            conn.commit()
        refresh_time(case["paths"]["sa"])
        with closing(sqlite3.connect(case["paths"]["market"], timeout=0)) as conn:
            conn.execute("INSERT INTO prices VALUES('KEEP','2026-09-04T13:45:00Z','15min')")
            conn.commit()
        backup = case["paths"]["profile"].parent / "pinned.db"
        observed = []
        def during_copy(*args):
            refresh_time(case["paths"]["sa"], "2026-09-05T17:01:00Z")
            observed.append(True)
        operation.backup_snapshot(readers["profile"], backup, progress=during_copy)
        assert observed and rows(backup, "SELECT name FROM watchlists") == original_profile
        assert readers["sa"].execute("SELECT last_seen_snapshot FROM sa_alpha_picks ORDER BY lineage_id").fetchall() == original_sa
        assert readers["market"].execute("SELECT count(*) FROM prices").fetchone() == (1,)
    assert rows(case["paths"]["profile"], "SELECT name FROM watchlists") == [("concurrent",)]
    assert rows(case["paths"]["market"], "SELECT count(*) FROM prices") == [(2,)]
    assert {role: rows(path, "SELECT count(*) FROM sqlite_master") for role, path in case["paths"].items()} == before


def test_non_wal_database_is_not_reconfigured_by_maintenance(case):
    with closing(sqlite3.connect(case["paths"]["sa"])) as conn:
        assert conn.execute("PRAGMA journal_mode=DELETE").fetchone() == ("delete",)
    with pytest.raises(operation.DispositionStopped, match="disposition_wal_required"):
        operation.prepare(**case, clock=lambda: NOW)
    assert not case["directory"].exists()
    assert rows(case["paths"]["sa"], "PRAGMA journal_mode") == [("delete",)]


@pytest.mark.parametrize("other", ("LTHM", "OTHER"))
def test_command_cannot_modify_another_membership_but_owned_row_can_commit(case, other):
    add_unrelated_current(case)
    original = rows(case["paths"]["profile"], "SELECT * FROM sa_tracking_memberships ORDER BY ticker")
    target = case["expected"]["targets"][0]
    with operation.connections(case["paths"], target=target):
        with closing(sqlite3.connect(case["paths"]["profile"])) as conn:
            with pytest.raises(operation.DispositionStopped, match="disposition_row_scope"):
                with conn:
                    conn.execute("UPDATE sa_tracking_memberships SET removed_at=? WHERE ticker=?", (LATER, other))
    assert rows(case["paths"]["profile"], "SELECT * FROM sa_tracking_memberships ORDER BY ticker") == original
    with operation.connections(case["paths"], target=target):
        with closing(sqlite3.connect(case["paths"]["profile"])) as conn, conn:
            conn.execute("UPDATE sa_tracking_memberships SET removed_at=? WHERE ticker='ARCH'", (LATER,))
    assert rows(case["paths"]["profile"], "SELECT removed_at FROM sa_tracking_memberships WHERE ticker='ARCH'") == [(LATER,)]


def test_case_write_ownership_has_positive_and_negative_controls(case):
    from src.security_lifecycle_investigation import SecurityLifecycleInvestigationStore
    target = case["expected"]["targets"][0]
    with operation.connections(case["paths"], target=target):
        with closing(sqlite3.connect(case["paths"]["profile"])) as conn:
            store = SecurityLifecycleInvestigationStore(conn)
            with pytest.raises(operation.DispositionStopped, match="disposition_row_scope"):
                store.ensure_case(source="listing_authority", source_ref="listing:KEEP", ticker="KEEP", at=NOW)
            store.ensure_case(source="listing_authority", source_ref="listing:ARCH", ticker="ARCH", at=NOW)
    assert rows(case["paths"]["profile"], "SELECT ticker FROM security_lifecycle_cases") == [("ARCH",)]


@pytest.mark.parametrize("bypass", ("implicit", "sql_commit", "cursor_commit", "native_commit", "script"))
def test_transaction_validation_cannot_be_bypassed(case, bypass):
    with operation.connections(case["paths"], target=case["expected"]["targets"][0]):
        with closing(sqlite3.connect(case["paths"]["profile"])) as conn:
            if bypass == "implicit":
                with pytest.raises(sqlite3.DatabaseError):
                    conn.execute("UPDATE sa_tracking_memberships SET removed_at=? WHERE ticker='LTHM'", (NOW,))
            else:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("UPDATE sa_tracking_memberships SET removed_at=? WHERE ticker='LTHM'", (NOW,))
                with pytest.raises((sqlite3.DatabaseError, operation.DispositionStopped)):
                    if bypass == "sql_commit":
                        conn.execute("COMMIT")
                    elif bypass == "cursor_commit":
                        conn.cursor().execute("COMMIT")
                    elif bypass == "native_commit":
                        sqlite3.Connection.commit(conn)
                    else:
                        conn.executescript("COMMIT;")
                conn.rollback()
    assert rows(case["paths"]["profile"], "SELECT count(*) FROM sa_tracking_memberships WHERE removed_at IS NOT NULL") == [(0,)]


@pytest.mark.parametrize("sql", (
    "SELECT secret FROM model_credentials", "UPDATE prices SET ticker='BAD'",
    "UPDATE security_lifecycle_provider_checks SET state='active'", "DELETE FROM sa_tracking_memberships",
    "CREATE TABLE surprise(value TEXT)", "UPDATE profile_settings SET value='true'",
    "UPDATE sa_tracking_bindings SET observed_at='2026-09-05T17:00:00Z'",
    "UPDATE sa_tracking_memberships SET ticker='BAD'", "UPDATE ticker_meta SET priority=1",
))
def test_sql_scope_still_denies_secrets_history_schema_and_binding_writes(case, sql):
    path = case["paths"]["market"] if "prices" in sql else case["paths"]["profile"]
    if "SELECT secret" in sql:
        assert rows(path, sql) == [("fake-private-value",)]
    with operation.connections(case["paths"], target=case["expected"]["targets"][0]) as denied:
        with closing(sqlite3.connect(path)) as conn:
            conn.execute("BEGIN")
            with pytest.raises(sqlite3.DatabaseError):
                conn.execute(sql)
            conn.rollback()
        assert denied


def test_target_capture_change_between_preview_and_commit_is_vetoed(case, monkeypatch):
    prepared = operation.prepare(**case, clock=lambda: NOW)
    reservation = operation.reserve
    original_connect = sqlite3.connect
    @contextmanager
    def after_preview(paths, roles):
        if paths == case["paths"] and roles == ("sa",):
            with closing(original_connect(paths["sa"])) as conn:
                conn.execute("UPDATE sa_alpha_picks SET portfolio_status='current' WHERE symbol='ARCH'")
                conn.commit()
        with reservation(paths, roles):
            yield
    monkeypatch.setattr(operation, "reserve", after_preview)
    with pytest.raises(operation.DispositionStopped, match="disposition_target_sa_material_changed"):
        execute(case, prepared)
    assert rows(case["paths"]["profile"], "SELECT count(*) FROM ticker_identity_transitions") == [(0,)]


def test_sa_reservations_are_short_and_release_before_receipt_publication(case, monkeypatch):
    from src.ticker_identity_service import TickerIdentityService
    prepared = operation.prepare(**case, clock=lambda: NOW)
    original_connect, approve, publish = sqlite3.connect, TickerIdentityService.approve_case, operation.write
    locked, released = [], []
    def at_approval(service, *args, **kwargs):
        with closing(original_connect(case["paths"]["sa"], timeout=0)) as conn:
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                conn.execute("UPDATE sa_alpha_picks SET last_seen_snapshot=?", (LATER,))
            locked.append(True)
        return approve(service, *args, **kwargs)
    def at_receipt(directory, name, value):
        if name.endswith(("-approved.json", "-applied.json")):
            with closing(original_connect(case["paths"]["sa"], timeout=0)) as conn:
                conn.execute("UPDATE sa_alpha_picks SET last_seen_snapshot=?", (LATER,))
                conn.commit()
                released.append(True)
        return publish(directory, name, value)
    monkeypatch.setattr(TickerIdentityService, "approve_case", at_approval)
    monkeypatch.setattr(operation, "write", at_receipt)
    assert execute(case, prepared)["applied"] == 3
    assert len(locked) == 3 and len(released) == 6


@pytest.mark.parametrize("change", ("approval", "backup", "runtime", "preview", "path"))
def test_rehearsal_authorization_still_binds_artifacts_and_runtime(case, monkeypatch, change):
    prepared = operation.prepare(**case, clock=lambda: NOW)
    paths = case["paths"]
    if change == "approval":
        prepared["plan_sha256"] = "0" * 64
    elif change == "backup":
        with closing(sqlite3.connect(case["directory"] / "profile.before.db")) as conn:
            conn.execute("UPDATE watchlists SET name='changed'")
            conn.commit()
    elif change == "runtime":
        monkeypatch.setattr(operation, "runtime_hashes", lambda: {"changed.py": "0" * 64})
    elif change == "path":
        paths = {**paths, "profile": case["directory"] / "profile.before.db"}
    else:
        path = case["directory"] / "private-plan.json"
        plan = json.loads(path.read_text())
        plan["previews"]["ARCH"]["successor_ticker"] = "WRONG"
        path.write_text(json.dumps(plan))
    with pytest.raises(operation.DispositionStopped):
        operation.apply(paths, case["directory"], approved_sha256=prepared["plan_sha256"], clock=lambda: LATER)
    assert rows(case["paths"]["profile"], "SELECT count(*) FROM ticker_identity_transitions") == [(0,)]


def test_partial_application_keeps_receipts_and_cannot_be_blindly_replayed(case, monkeypatch):
    from src.ticker_identity_service import TickerIdentityService
    prepared = operation.prepare(**case, clock=lambda: NOW)
    execute_transition = TickerIdentityService.execute_transition
    calls = []
    def interrupted(service, *args, **kwargs):
        calls.append(args[0])
        if len(calls) == 2:
            raise RuntimeError("simulated interruption")
        return execute_transition(service, *args, **kwargs)
    monkeypatch.setattr(TickerIdentityService, "execute_transition", interrupted)
    with pytest.raises(RuntimeError, match="simulated interruption"):
        execute(case, prepared)
    assert rows(case["paths"]["profile"], "SELECT source_ticker,status FROM ticker_identity_transitions ORDER BY source_ticker") == [
        ("ARCH", "applied"), ("LTHM", "approved")]
    assert (case["directory"] / "production/ARCH-applied.json").is_file()
    with pytest.raises(operation.DispositionStopped, match="disposition_already_started"):
        execute(case, prepared)
