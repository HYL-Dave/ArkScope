"""Maintenance authorization boundaries, using only temporary SQLite stores."""

from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import socket
import sqlite3

import pytest


spec = importlib.util.spec_from_file_location("attended_disposition_test", Path(__file__).with_name("disposition.py"))
operation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(operation)
NOW = "2026-09-05T15:40:00+00:00"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("maintenance_test_network_forbidden")
    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)


@pytest.fixture
def case(tmp_path):
    from dataclasses import replace
    from src.profile_state import ProfileStateStore
    from src.portfolio_state import PortfolioStore
    from src.sa_capture_store import connect
    from src.sa_tracking_memberships import SaTrackingMembershipStore, read_sa_tracking_observations
    from src.security_lifecycle_listing_evidence import _evidence
    from src.security_lifecycle_provider_store import ProviderCheckStore
    from src.security_lifecycle_schema import create_profile_schema, create_market_schema
    from src.ticker_identity_schema import create_ticker_identity_schema
    from src.tools.backends.sa_capture_backend import SACaptureBackend
    from tests.test_security_lifecycle_provider_authority import terminal_records
    paths = {role: tmp_path / f"{role}.db" for role in ("profile", "market", "sa")}
    ProfileStateStore(paths["profile"]).import_lists([{"name": "Manual", "kind": "custom", "tickers": ["KEEP"]}])
    PortfolioStore(paths["profile"])
    with sqlite3.connect(paths["profile"]) as conn:
        create_profile_schema(conn)
        create_ticker_identity_schema(conn)
        SaTrackingMembershipStore.install(conn)
        conn.execute("CREATE TABLE model_credentials(secret TEXT)")
        conn.execute("INSERT INTO model_credentials VALUES('fake-private-value')")
    with sqlite3.connect(paths["market"]) as conn:
        create_market_schema(conn)
        conn.execute("CREATE TABLE prices(ticker TEXT, datetime TEXT, interval TEXT)")
        conn.execute("INSERT INTO prices VALUES('KEEP','2026-09-04T13:30:00Z','15min')")
    connect(str(paths["sa"])).close()
    backend = SACaptureBackend(sa_db=str(paths["sa"]), market_db=str(paths["market"]), base_path=tmp_path)
    picks = [{"symbol": ticker, "picked_date": "2023-01-01", "closed_date": ended}
             for ticker, ended in operation.TARGET_DATES.items()]
    assert backend.apply_sa_refresh("closed", picks, NOW, NOW) == 3
    observations = read_sa_tracking_observations(paths["sa"])
    SaTrackingMembershipStore(paths["profile"]).reconcile(observations, at=NOW, bootstrap_actor="attended_user")
    for ticker, ended in operation.TARGET_DATES.items():
        rows = tuple(_evidence(replace(row, ticker=ticker,
            delisted_utc=ended if row.adapter == "massive_reference" and row.listing_status == "inactive" else row.delisted_utc,
        )) for row in terminal_records())
        ProviderCheckStore(paths["profile"]).record(ticker=ticker, at="2026-09-05T01:00:00Z", evidence=rows,
            diagnostics={}, blockers=("massive_not_found",))
    expected = operation.observe(paths, at=NOW)
    return {"paths": paths, "expected": expected, "directory": tmp_path / "operation"}


def count(paths, table):
    with sqlite3.connect(paths["profile"]) as conn:
        return conn.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]


def test_prepare_is_backup_and_rehearsal_only_then_exact_application(case):
    before = operation.domain_state(case["paths"]["profile"])
    result = operation.prepare(**case, clock=lambda: NOW)
    assert result["rehearsal_applied"] == 3
    assert operation.domain_state(case["paths"]["profile"]) == before
    assert count(case["paths"], "ticker_identity_transitions") == 0
    assert {row["ticker"] for row in result["targets"]} == set(operation.TARGET_DATES)
    assert result["rehearsal_universe_after"] == 1
    assert result["no_alias"] is True
    applied = operation.apply(case["paths"], case["directory"], approved_sha256=result["plan_sha256"], clock=lambda: NOW)
    assert applied["applied"] == 3
    assert applied["universe_after"] == 1
    assert applied["sa_sync_status"] == "current"
    assert applied["survives_sa_reconciliation"] is True
    assert applied["history_databases_unchanged"] is True
    assert applied["old_provider_snapshots_unchanged"] is True
    assert applied["all_reverse_ready"] is True
    assert count(case["paths"], "ticker_identity_links") == 0
    assert count(case["paths"], "ticker_identity_transition_attempts") == 3


@pytest.mark.parametrize("change", ["source", "position", "evidence", "sa"])
def test_changed_input_aborts_before_backup_or_write(case, change):
    from src.profile_state import ProfileStateStore
    from src.portfolio_state import PortfolioStore
    from src.security_lifecycle_provider_store import ProviderCheckStore
    if change == "source":
        ProfileStateStore(case["paths"]["profile"]).import_lists([{"name": "New", "kind": "custom", "tickers": ["ARCH"]}])
    elif change == "position":
        portfolio = PortfolioStore(case["paths"]["profile"])
        account = portfolio.ensure_manual_account()
        portfolio.upsert_manual_position(account_id=account.id, symbol="ARCH", quantity=1)
    elif change == "evidence":
        store = ProviderCheckStore(case["paths"]["profile"])
        old = store.latest()["ARCH"]
        store.record(ticker="ARCH", at="2026-09-05T02:00:00Z", evidence=old["evidence"], diagnostics={}, blockers=old["blockers"])
    else:
        with sqlite3.connect(case["paths"]["sa"]) as conn:
            conn.execute("UPDATE sa_alpha_picks SET last_seen_snapshot='2026-09-05T16:00:00Z'")
    with pytest.raises(operation.DispositionStopped):
        operation.prepare(**case, clock=lambda: NOW)
    assert not (case["directory"] / "profile.before.db").exists()
    assert count(case["paths"], "ticker_identity_transitions") == 0


def test_expired_evidence_stops_despite_same_record_digest(case):
    with pytest.raises(operation.DispositionStopped):
        operation.prepare(**case, clock=lambda: "2026-09-10T15:40:00Z")
    assert count(case["paths"], "ticker_identity_transitions") == 0


@pytest.mark.parametrize("change", ["approval", "backup", "preview", "production"])
def test_apply_requires_exact_rehearsal_backup_and_approval(case, change):
    result = operation.prepare(**case, clock=lambda: NOW)
    approved = result["plan_sha256"]
    if change == "approval":
        approved = "0" * 64
    elif change == "backup":
        with sqlite3.connect(case["directory"] / "profile.before.db") as conn:
            conn.execute("UPDATE watchlists SET name='changed'")
    elif change == "preview":
        path = case["directory"] / "private-plan.json"
        plan = json.loads(path.read_text())
        plan["previews"]["ARCH"]["successor_ticker"] = "WRONG"
        path.write_text(json.dumps(plan))
    else:
        with sqlite3.connect(case["paths"]["profile"]) as conn:
            conn.execute("UPDATE watchlists SET name='changed'")
    with pytest.raises(operation.DispositionStopped):
        operation.apply(case["paths"], case["directory"], approved_sha256=approved, clock=lambda: NOW)
    assert count(case["paths"], "ticker_identity_transitions") == 0


def test_started_command_cannot_be_blindly_replayed(case):
    result = operation.prepare(**case, clock=lambda: NOW)
    operation.apply(case["paths"], case["directory"], approved_sha256=result["plan_sha256"], clock=lambda: NOW)
    before = operation.domain_state(case["paths"]["profile"])
    with pytest.raises(operation.DispositionStopped, match="disposition_already_started"):
        operation.apply(case["paths"], case["directory"], approved_sha256=result["plan_sha256"], clock=lambda: NOW)
    assert operation.domain_state(case["paths"]["profile"]) == before


def test_interrupted_apply_keeps_real_receipts_and_requires_readback(case, monkeypatch):
    from src.ticker_identity_service import TickerIdentityService
    result = operation.prepare(**case, clock=lambda: NOW)
    execute = TickerIdentityService.execute_transition
    calls = []
    def interrupted(service, *args, **kwargs):
        calls.append(args[0])
        if len(calls) == 2:
            raise RuntimeError("simulated interruption")
        return execute(service, *args, **kwargs)
    monkeypatch.setattr(TickerIdentityService, "execute_transition", interrupted)
    with pytest.raises(RuntimeError, match="simulated interruption"):
        operation.apply(case["paths"], case["directory"], approved_sha256=result["plan_sha256"], clock=lambda: NOW)
    actual = operation.recorded_status(case["paths"])
    assert actual["recorded_applied"] == 1 and actual["recorded_approved"] == 1
    assert actual["targets"] == [{"ticker": "ARCH", "status": "applied"}, {"ticker": "LTHM", "status": "approved"}]
    assert (case["directory"] / "production/ARCH-applied.json").is_file()
    assert not (case["directory"] / "production/LTHM-applied.json").exists()
    with pytest.raises(operation.DispositionStopped, match="disposition_already_started"):
        operation.apply(case["paths"], case["directory"], approved_sha256=result["plan_sha256"], clock=lambda: NOW)


def test_unrelated_state_change_during_write_boundary_is_not_ignored(case, monkeypatch):
    from src.ticker_identity_service import TickerIdentityService
    result = operation.prepare(**case, clock=lambda: NOW)
    approve = TickerIdentityService.approve_case
    original_connect = sqlite3.connect
    def changed(service, *args, **kwargs):
        with original_connect(case["paths"]["profile"]) as conn:
            conn.execute("UPDATE watchlists SET name='concurrent edit'")
        return approve(service, *args, **kwargs)
    monkeypatch.setattr(TickerIdentityService, "approve_case", changed)
    with pytest.raises(operation.DispositionStopped, match="disposition_unrelated_state_changed"):
        operation.apply(case["paths"], case["directory"], approved_sha256=result["plan_sha256"], clock=lambda: NOW)
    assert count(case["paths"], "ticker_identity_transitions") == 0


def test_preview_cannot_expand_to_alias_or_another_source(case):
    result = operation.prepare(**case, clock=lambda: NOW)
    plan = json.loads((case["directory"] / "private-plan.json").read_text())
    original = plan["previews"]["ARCH"]
    operation.require_effects(original, case["expected"]["targets"][0])
    for field, value in (("successor_ticker", "WRONG"), ("transition_kind", "symbol_continuation")):
        with pytest.raises(operation.DispositionStopped):
            operation.require_effects({**original, field: value}, case["expected"]["targets"][0])
    altered = json.loads(json.dumps(original))
    altered["effects"]["watchlists"]["archive"] = [{"list_id": 5, "ticker": "ARCH"}]
    with pytest.raises(operation.DispositionStopped):
        operation.require_effects(altered, case["expected"]["targets"][0])


@pytest.mark.parametrize("sql", [
    "SELECT secret FROM model_credentials", "UPDATE prices SET ticker='BAD'",
    "UPDATE security_lifecycle_provider_checks SET state='active'", "DELETE FROM sa_tracking_memberships",
    "CREATE TABLE surprise(value TEXT)", "UPDATE profile_settings SET value='true'",
])
def test_sql_boundary_denies_credentials_history_ddl_and_other_writes(case, sql):
    path = case["paths"]["market"] if "prices" in sql else case["paths"]["profile"]
    if sql.startswith("SELECT secret"):
        with sqlite3.connect(path) as conn:
            assert conn.execute(sql).fetchone() == ("fake-private-value",)
    with operation.connections(case["paths"], writable_profile=True) as denied:
        with sqlite3.connect(str(path)) as conn:
            with pytest.raises(sqlite3.DatabaseError):
                conn.execute(sql)
        assert denied


def test_backup_and_plan_are_private_and_create_only(case):
    operation.prepare(**case, clock=lambda: NOW)
    assert case["directory"].stat().st_mode & 0o077 == 0
    for path in case["directory"].glob("*"):
        if path.is_file():
            assert path.stat().st_mode & 0o077 == 0
    with pytest.raises(operation.DispositionStopped):
        operation.prepare(**case, clock=lambda: NOW)


def test_execution_code_change_stops_before_production_write(case, monkeypatch):
    result = operation.prepare(**case, clock=lambda: NOW)
    monkeypatch.setattr(operation, "runtime_hashes", lambda: {"changed.py": "0" * 64})
    with pytest.raises(operation.DispositionStopped, match="disposition_runtime_changed"):
        operation.apply(case["paths"], case["directory"], approved_sha256=result["plan_sha256"], clock=lambda: NOW)
    assert count(case["paths"], "ticker_identity_transitions") == 0


def test_identical_database_at_another_path_is_not_authorized(case):
    result = operation.prepare(**case, clock=lambda: NOW)
    paths = {**case["paths"], "profile": case["directory"] / "profile.before.db"}
    with pytest.raises(operation.DispositionStopped, match="disposition_database_paths_changed"):
        operation.apply(paths, case["directory"], approved_sha256=result["plan_sha256"], clock=lambda: NOW)
    assert count(case["paths"], "ticker_identity_transitions") == 0


def test_sqlite_wal_changes_are_bound_not_only_the_main_database(tmp_path):
    path = tmp_path / "wal.db"
    with operation.closing(sqlite3.connect(path)) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE example(value INTEGER)")
        conn.commit()
        before = operation.database_digest(path)
        main_before = operation.file_digest(path)
        conn.execute("INSERT INTO example VALUES(1)")
        conn.commit()
        assert operation.file_digest(path) == main_before
        assert operation.database_digest(path) != before


@pytest.mark.parametrize("event", ["socket.connect", "socket.getaddrinfo", "subprocess.Popen", "os.posix_spawn"])
def test_runtime_audit_rejects_external_execution_before_dispatch(case, event):
    guard = operation.audit_for(case["paths"], case["directory"])
    with pytest.raises(operation.DispositionStopped, match="disposition_external_execution_forbidden"):
        guard(event, ())


def test_independent_readback_needs_applied_receipts_and_real_projection(case):
    spec = importlib.util.spec_from_file_location("disposition_readback_test", Path(__file__).with_name("readback.py"))
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    with pytest.raises(ValueError, match="readback_target_still_tracked"):
        reader.run(case["paths"], plan_sha256="0" * 64)
    result = operation.prepare(**case, clock=lambda: NOW)
    paths = {role: case["directory"] / f"{role}.before.db" for role in ("profile", "market", "sa")}
    paths["profile"] = case["directory"] / "profile.rehearsal.db"
    readback = reader.run(paths, plan_sha256=result["plan_sha256"])
    assert readback["status"] == "readonly_receipt_readback_passed"
    assert readback["universe_count"] == 1
    assert all(row["projected_applied"] and row["reverse_ready"] for row in readback["targets"])


def test_reserved_sources_reject_external_writer_and_release_afterward(case):
    with operation.reserve_sources(case["paths"], roles=("market", "sa")):
        with sqlite3.connect(case["paths"]["sa"], timeout=0) as other:
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                other.execute("BEGIN IMMEDIATE")
    with sqlite3.connect(case["paths"]["sa"], timeout=0) as other:
        other.execute("BEGIN IMMEDIATE")
        other.rollback()
