"""No production store is opened by these maintenance-boundary tests."""

from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import socket
import sqlite3
import sys

import pytest


SPEC = importlib.util.spec_from_file_location("tracking_readonly_inventory", Path(__file__).with_name("inventory.py"))
inventory = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = inventory
SPEC.loader.exec_module(inventory)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail("inventory_test_attempted_network")
    monkeypatch.setattr(socket, "create_connection", denied)
    monkeypatch.setattr(socket.socket, "connect", denied)


def stores(tmp_path):
    paths = {role: tmp_path / f"{role}.db" for role in ("profile", "market", "sa")}
    for path in paths.values():
        with sqlite3.connect(path) as conn:
            conn.execute("CREATE TABLE watchlists (id INTEGER, name TEXT)")
            conn.execute("INSERT INTO watchlists VALUES (1, 'local')")
            conn.execute("CREATE TABLE model_credentials (secret TEXT)")
            conn.execute("INSERT INTO model_credentials VALUES ('synthetic-secret')")
    return paths


@pytest.mark.parametrize("query", (
    "SELECT secret FROM model_credentials",
    "UPDATE watchlists SET name='changed'",
    "CREATE TABLE unexpected (id INTEGER)",
    "PRAGMA query_only=OFF",
    "ATTACH DATABASE ':memory:' AS extra",
))
def test_sql_scope_rejects_secrets_and_mutation(tmp_path, query):
    paths = stores(tmp_path)
    with inventory.guarded_connections(paths) as guard:
        with sqlite3.connect(paths["profile"].as_uri() + "?mode=ro", uri=True) as conn:
            assert conn.execute("SELECT name FROM watchlists").fetchall() == [("local",)]
            with pytest.raises(sqlite3.DatabaseError):
                conn.execute(query)
        assert guard.denials
    with sqlite3.connect(paths["profile"]) as conn:
        assert conn.execute("SELECT name FROM watchlists").fetchone() == ("local",)


def test_sql_scope_also_rejects_unneeded_position_values(tmp_path):
    paths = stores(tmp_path)
    with sqlite3.connect(paths["profile"]) as conn:
        conn.execute("CREATE TABLE portfolio_positions (symbol TEXT, closed_at TEXT, quantity REAL)")
        conn.execute("INSERT INTO portfolio_positions VALUES ('LIVE', NULL, 12)")
    with inventory.guarded_connections(paths):
        with sqlite3.connect(paths["profile"].as_uri() + "?mode=ro", uri=True) as conn:
            assert conn.execute("SELECT symbol,closed_at FROM portfolio_positions").fetchall() == [("LIVE", None)]
            with pytest.raises(sqlite3.DatabaseError):
                conn.execute("SELECT quantity FROM portfolio_positions")


@pytest.mark.parametrize("variant", ("bare", "rw", "memory", "other", "bytes_rw"))
def test_connection_boundary_requires_exact_readonly_uris(tmp_path, variant):
    paths = stores(tmp_path)
    names = {"bare": str(paths["profile"]), "rw": paths["profile"].as_uri() + "?mode=rw",
             "memory": ":memory:", "other": (tmp_path / "other.db").as_uri() + "?mode=ro",
             "bytes_rw": (paths["profile"].as_uri() + "?mode=rw").encode()}
    with inventory.guarded_connections(paths):
        with pytest.raises(inventory.InventoryStopped, match="inventory_connection_scope"):
            sqlite3.connect(names[variant], uri=True)


def test_database_change_invalidates_inventory_even_if_other_fields_match(tmp_path):
    paths = stores(tmp_path)
    original_connect = sqlite3.connect
    with inventory.guarded_connections(paths) as guard:
        monitor = sqlite3.connect(paths["profile"].as_uri() + "?mode=ro", uri=True)
        before = inventory.data_versions({"profile": monitor})
        with original_connect(paths["profile"]) as writer:
            writer.execute("UPDATE watchlists SET name='external change'")
        with pytest.raises(inventory.InventoryStopped, match="inventory_inputs_changed"):
            inventory.require_stable(before, inventory.data_versions({"profile": monitor}))
        assert not guard.denials
        monitor.close()


@pytest.mark.parametrize("event,args", (
    ("socket.connect", ()), ("socket.getaddrinfo", ()), ("subprocess.Popen", ()),
    ("os.system", ()), ("open", ("/tmp/config/.env", "r", 0)),
    ("open", ("/tmp/auth.json", "r", 0)),
))
def test_process_boundary_denies_ambient_auth_and_external_execution(tmp_path, event, args):
    hook = inventory.audit_for(stores(tmp_path))
    with pytest.raises(inventory.InventoryStopped):
        hook(event, args)


def test_process_boundary_denies_raw_database_copy_but_allows_source_code(tmp_path):
    paths = stores(tmp_path)
    hook = inventory.audit_for(paths)
    with pytest.raises(inventory.InventoryStopped, match="inventory_raw_database_read_forbidden"):
        hook("open", (bytes(paths["profile"]), "rb", 0))
    hook("open", (str(Path(__file__)), "r", 0))
    hook("sqlite3.connect", ((paths["profile"].as_uri() + "?mode=ro").encode(),))


@pytest.mark.parametrize("days,expected_chunks", ((15, 1), (60, 1), (61, 1), (62, 1), (65, 2), (120, 2)))
def test_budget_runs_real_chunker_and_counts_both_request_types(days, expected_chunks):
    plan = {"provider": "ibkr", "fallback_allowed": False, "interval": "15min",
            "tickers": ["ONE", "TWO"], "lookback_days": days, "as_of_date": "2026-09-05"}
    result = inventory.simulate_requests(plan, now=datetime(2026, 9, 5, 15, tzinfo=timezone.utc))
    assert len(result["chunks"]) == 2 * expected_chunks
    assert result["qualification_requests"] == 2 * expected_chunks
    assert result["historical_requests"] == 2 * expected_chunks
    assert result["total_data_requests"] == 4 * expected_chunks
    assert all(row["interval"] == "15 mins" and row["rth_only"] for row in result["chunks"])
    assert result["observed_provider_requests"] == 0


def test_weekend_boundary_is_not_mistaken_for_an_extra_fetch_day():
    plan = {"provider": "ibkr", "fallback_allowed": False, "interval": "15min",
            "tickers": ["ONE"], "lookback_days": 62, "as_of_date": "2026-09-05"}
    result = inventory.simulate_requests(plan, now=datetime(2026, 9, 5, 15, tzinfo=timezone.utc))
    # July 5 and September 5 are outside the actual completed trading span.
    assert result["fetch_start"] == "2026-07-06"
    assert result["fetch_end"] == "2026-09-04"
    assert result["chunks"][0]["calendar_days"] == 61


def test_budget_fetches_complete_window_not_only_visible_gap():
    plan = {"provider": "ibkr", "fallback_allowed": False, "interval": "15min", "tickers": ["ONE"],
            "lookback_days": 120, "as_of_date": "2026-09-05",
            "gaps": [{"ticker": "ONE", "missing_dates": ["2026-09-04"], "partial_dates": []}]}
    result = inventory.simulate_requests(plan, now=datetime(2026, 9, 5, 15, tzinfo=timezone.utc))
    assert result["total_data_requests"] == 4
    assert result["fetch_start"] == "2026-05-08"
    assert result["fetch_end"] == "2026-09-04"
    assert result["chunks"][0]["start"] == "2026-05-08"
    assert result["chunks"][-1]["end"] == "2026-09-04"


def test_empty_repair_never_simulates_provider_requests():
    result = inventory.simulate_requests({"provider": "ibkr", "fallback_allowed": False,
        "interval": "15min", "tickers": [], "lookback_days": 15, "as_of_date": "2026-09-05"},
        now=datetime(2026, 9, 5, 15, tzinfo=timezone.utc))
    assert result["total_data_requests"] == 0


def test_target_inventory_uses_real_projection_and_never_accepts_assessments(tmp_path):
    from tests.test_security_lifecycle_terminal_workflow import setup_workflow
    from src.active_universe import build_active_universe_snapshot
    c = setup_workflow(tmp_path, ticker="ARCH", event_available=False, assess=False)
    paths = {role: c[role] for role in ("profile", "market", "sa")}
    with inventory.guarded_connections(paths):
        scope = build_active_universe_snapshot(profile_db=c["profile"], sa_db=c["sa"])
        with sqlite3.connect(c["profile"].as_uri() + "?mode=ro", uri=True) as conn:
            row, private = inventory.target_inventory(conn, "ARCH", scope.sources_by_ticker,
                now=datetime(2026, 9, 5, 15, tzinfo=timezone.utc))
    assert row["listing_state"] == "inactive"
    assert row["continuation_state"] == "unavailable"
    assert row["open_position"] is False
    assert row["watchlist_archives"] == 1
    assert row["sa_memberships_to_suppress"] == 1
    assert row["ready_for_new_attended_preview"] is True
    assert private["effects"]["watchlists"]["archive"][0]["ticker"] == "ARCH"
    with sqlite3.connect(c["profile"]) as conn:
        assert conn.execute("SELECT count(*) FROM security_lifecycle_assessments").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM ticker_identity_transitions").fetchone()[0] == 0


def test_open_position_is_a_veto_not_a_quantity_export(tmp_path):
    from tests.test_security_lifecycle_terminal_workflow import setup_workflow
    from src.active_universe import build_active_universe_snapshot
    from src.portfolio_state import PortfolioStore
    c = setup_workflow(tmp_path, ticker="ARCH", event_available=False, assess=False)
    store = PortfolioStore(c["profile"])
    account = store.ensure_manual_account()
    store.upsert_manual_position(account_id=account.id, symbol="ARCH", quantity=5)
    paths = {role: c[role] for role in ("profile", "market", "sa")}
    with inventory.guarded_connections(paths):
        scope = build_active_universe_snapshot(profile_db=c["profile"], sa_db=c["sa"])
        with sqlite3.connect(c["profile"].as_uri() + "?mode=ro", uri=True) as conn:
            row, _ = inventory.target_inventory(conn, "ARCH", scope.sources_by_ticker,
                now=datetime(2026, 9, 5, 15, tzinfo=timezone.utc))
    assert row["open_position"] is True
    assert row["ready_for_new_attended_preview"] is False


def test_existing_output_cannot_be_overwritten(tmp_path):
    inventory.private_write(tmp_path, "receipt.json", {"status": "first"})
    with pytest.raises(FileExistsError):
        inventory.private_write(tmp_path, "receipt.json", {"status": "second"})
    assert (tmp_path / "receipt.json").stat().st_mode & 0o777 == 0o600


def test_full_inventory_uses_real_coverage_and_preserves_all_source_rows(tmp_path, monkeypatch):
    from tests.test_security_lifecycle_terminal_workflow import setup_workflow
    from tests.test_trading_day_coverage import _create_market_db
    c = setup_workflow(tmp_path, ticker="ARCH", event_available=False, assess=False)
    _create_market_db(c["market"])
    paths = {role: c[role] for role in ("profile", "market", "sa")}
    before = {}
    for role, path in paths.items():
        with sqlite3.connect(path) as conn:
            before[role] = tuple(conn.iterdump())
    monkeypatch.setattr(inventory, "TARGETS", ("ARCH",))
    with inventory.guarded_connections(paths) as guard:
        try:
            result, private = inventory.collect(paths, now=datetime(2026, 9, 5, 15, tzinfo=timezone.utc))
        except Exception:
            assert not guard.denials
            raise
        assert not guard.denials
    assert result["universe_before"] == 2
    assert result["hypothetical_universe_after"] == 1
    assert result["hypothetical_removed_targets"] == ["ARCH"]
    assert result["production_writes"] == result["provider_requests"] == 0
    assert result["coverage"]["hypothetical_after_approved_removal_120"]["total_data_requests"] == 4
    assert private["coverage"]["hypothetical_after_approved_removal_120"]["preview"]["tickers"] == ["LIVE"]
    for role, path in paths.items():
        with sqlite3.connect(path) as conn:
            assert tuple(conn.iterdump()) == before[role]


def test_full_inventory_cannot_publish_after_a_mid_read_source_change(tmp_path, monkeypatch):
    from tests.test_security_lifecycle_terminal_workflow import setup_workflow
    from tests.test_trading_day_coverage import _create_market_db
    c = setup_workflow(tmp_path, ticker="ARCH", event_available=False, assess=False)
    _create_market_db(c["market"])
    paths = {role: c[role] for role in ("profile", "market", "sa")}
    monkeypatch.setattr(inventory, "TARGETS", ("ARCH",))
    connect = sqlite3.connect
    coverage = inventory.coverage_inventory
    changed = []
    def coverage_then_external_change(*args, **kwargs):
        result = coverage(*args, **kwargs)
        if not changed:
            with connect(c["profile"]) as writer:
                writer.execute("UPDATE watchlists SET name='new name'")
            changed.append(True)
        return result
    monkeypatch.setattr(inventory, "coverage_inventory", coverage_then_external_change)
    with inventory.guarded_connections(paths):
        with pytest.raises(inventory.InventoryStopped, match="inventory_inputs_changed"):
            inventory.collect(paths, now=datetime(2026, 9, 5, 15, tzinfo=timezone.utc))
    assert changed == [True]


def test_pending_sa_diagnostic_distinguishes_timestamps_from_real_changes(tmp_path):
    from src.sa_tracking_memberships import SaTrackingMembershipStore
    spec = importlib.util.spec_from_file_location("tracking_sync_test", Path(__file__).with_name("sync_inventory.py"))
    sync = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sync)
    path = tmp_path / "profile.db"
    with sqlite3.connect(path) as conn:
        SaTrackingMembershipStore.install(conn)
    observed = [{"lineage_id": i, "ticker": ticker, "picked_date": "2023-01-01", "portfolio_status": "closed",
                 "current_observed": False, "observed_at": "2026-09-05T01:00:00+00:00"}
                for i, ticker in enumerate(("ARCH", "LTHM", "TA", "LIVE"), 1)]
    SaTrackingMembershipStore(path).reconcile(observed, at="2026-09-05T01:00:00+00:00", bootstrap_actor="attended_user")
    changed = [observed[0], {**observed[1], "observed_at": "2026-09-05T02:00:00+00:00"},
               {**observed[2], "current_observed": True}, {**observed[3], "ticker": "RENAMED"},
               {**observed[3], "lineage_id": 5, "ticker": "NEW"}]
    with sqlite3.connect(path) as conn:
        result = sync.synchronization_details(conn, changed)
    assert result["change_counts"] == {"unchanged": 1, "timestamp_only": 1, "content_changed": 1, "anchor_changed": 1, "unbound_lineage": 1}
    assert result["target_changes"] == {"ARCH": ["unchanged"], "LTHM": ["timestamp_only"], "TA": ["content_changed"]}
