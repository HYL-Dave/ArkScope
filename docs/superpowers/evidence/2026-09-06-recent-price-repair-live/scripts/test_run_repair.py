from collections import Counter
from datetime import date
import importlib.util
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest

from src import market_data_direct as writer
from src.price_repair_execution import build_repair_plan
from tests.test_recent_price_repair import no_network, recent, raw_source
from tests.test_market_data_direct import _bar
from tests.test_trading_day_coverage import _slots


spec = importlib.util.spec_from_file_location("live_recent_repair", Path(__file__).with_name("run_repair.py"))
live = importlib.util.module_from_spec(spec)
spec.loader.exec_module(live)


@pytest.fixture
def prepared(recent):
    with sqlite3.connect(recent.path) as conn:
        rows = writer._ibkr_bars_to_rows("ONE", [_bar(at) for day, session in recent.sessions.items()
                                                  if day >= date(2026, 8, 31) for at in _slots(session)], "15min")
        writer._insert_rows(conn, rows)
    plan = build_repair_plan(recent.service.get_coverage(universe=["ONE"], lookback_days=15, interval="15min"), recent.path, pacing_seconds=0)
    return plan


def make_profile(path):
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE data_provider_config(provider TEXT,field TEXT,value TEXT)")
        conn.executemany("INSERT INTO data_provider_config VALUES(?,?,?)", [
            ("ibkr", "host", "127.0.0.1"), ("ibkr", "port", "4001"), ("ibkr", "client_id", "1"),
            ("unrelated", "api_key", "PRIVATE_TEST_KEY_NOT_FOR_REPAIR"),
        ])


def test_live_admission_binds_the_exact_authorized_plan(prepared):
    live.admit(prepared, prepared["plan_sha256"])
    with pytest.raises(live.Stopped, match="live_plan_not_approved"):
        live.admit(prepared)


def test_settings_reads_only_profile_ibkr_without_env_fallback(tmp_path, monkeypatch):
    path = tmp_path / "profile.db"
    make_profile(path)
    monkeypatch.setenv("IBKR_HOST", "198.51.100.1")
    monkeypatch.setenv("IBKR_CLIENT_ID", "100")
    assert live.settings(path) == {"host": "127.0.0.1", "port": 4001, "client_id": 21, "readonly": True, "timeout": 15}
    with sqlite3.connect(path) as conn:
        conn.execute("DELETE FROM data_provider_config WHERE field='client_id'")
    with pytest.raises(live.Stopped, match="settings_incomplete"):
        live.settings(path)


def test_configured_gateway_is_not_required_to_be_loopback(tmp_path):
    path = tmp_path / "profile.db"
    make_profile(path)
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE data_provider_config SET value='10.42.0.2' WHERE provider='ibkr' AND field='host'")
    config = live.settings(path)
    assert config["host"] == "10.42.0.2" and config["readonly"] is True
    metrics = {"socket_connection_attempts": 0}
    check = live.network_guard(config, metrics)
    check("socket.connect", (None, ("10.42.0.2", config["port"])))
    with pytest.raises(live.Stopped, match="live_network_scope"):
        check("socket.connect", (None, ("10.42.0.3", config["port"])))


def test_backup_keeps_wal_rows_and_never_overwrites_a_prior_backup(tmp_path):
    path, dest = tmp_path / "live.db", tmp_path / "backup.db"
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE value(n INTEGER)")
        conn.execute("INSERT INTO value VALUES(42)")
        conn.commit()
        assert Path(str(path) + "-wal").stat().st_size > 0
        result = live.backup(path, dest)
        assert result["quick_check"] == "ok" and len(result["sha256"]) == 64
        with sqlite3.connect(dest) as saved:
            assert saved.execute("SELECT n FROM value").fetchall() == [(42,)]
        with pytest.raises(FileExistsError):
            live.backup(path, dest)


@pytest.mark.parametrize("change", ("ticker", "date", "statement", "delete", "profile", "credential"))
def test_live_sql_guard_rejects_out_of_scope_access(recent, prepared, change):
    profile, sa = recent.tmp / "profile.db", recent.tmp / "sa.db"
    make_profile(profile)
    sa.touch()
    metrics = {"sqlite_denials": 0, "inserted_on_guarded_connections": 0}
    paths = {"market": recent.path, "profile": profile, "sa": sa}
    slot = min(live.approved_slots(prepared))
    with live.guarded_connections(paths, recent.tmp / "journal.db", live.approved_slots(prepared), metrics):
        if change == "profile":
            with pytest.raises(live.Stopped, match="database_scope"):
                sqlite3.connect(profile.as_uri() + "?mode=rw", uri=True)
        elif change == "credential":
            with sqlite3.connect(profile.as_uri() + "?mode=ro", uri=True) as conn:
                with pytest.raises(sqlite3.DatabaseError):
                    conn.execute("SELECT value FROM data_provider_config").fetchall()
        else:
            with sqlite3.connect(recent.path.as_uri() + "?mode=rw", uri=True) as conn:
                if change == "delete":
                    with pytest.raises(sqlite3.DatabaseError):
                        conn.execute("DELETE FROM prices")
                else:
                    row = (*slot, 10, 11, 9, 10.5, 100)
                    if change == "ticker":
                        row = ("UNRELATED", *row[1:])
                    elif change == "date":
                        row = (row[0], "2026-06-01T13:30:00+0000", *row[2:])
                    sql = writer._PRICE_INSERT if change != "statement" else writer._PRICE_INSERT.replace("OR IGNORE", "OR REPLACE")
                    with pytest.raises(live.Stopped):
                        conn.executemany(sql, [row])
    assert metrics["inserted_on_guarded_connections"] == 0


def test_live_sql_guard_allows_only_authorized_inserts(recent, prepared):
    paths = {"market": recent.path, "profile": recent.tmp / "profile.db", "sa": recent.tmp / "sa.db"}
    metrics = {"sqlite_denials": 0, "inserted_on_guarded_connections": 0}
    row = (*min(live.approved_slots(prepared)), 10, 11, 9, 10.5, 100)
    with live.guarded_connections(paths, recent.tmp / "journal.db", live.approved_slots(prepared), metrics):
        with sqlite3.connect(recent.path.as_uri() + "?mode=rw", uri=True) as conn:
            assert writer._insert_rows(conn, [row]) == 1
    assert metrics == {"sqlite_denials": 0, "inserted_on_guarded_connections": 1}


def test_network_guard_rejects_non_gateway_destinations_and_ambient_secrets():
    metrics = {"socket_connection_attempts": 0}
    check = live.network_guard({"host": "127.0.0.1", "port": 4001}, metrics)
    check("socket.connect", (None, ("127.0.0.1", 4001)))
    assert metrics["socket_connection_attempts"] == 1
    for event, args in (("socket.connect", (None, ("198.51.100.1", 443))),
                        ("socket.getaddrinfo", ("example.com", 443)),
                        ("subprocess.Popen", ()), ("open", ("config/.env",))):
        with pytest.raises(live.Stopped):
            check(event, args)


def test_real_maintenance_flow_backs_up_meters_writes_and_reads_back(recent, prepared, monkeypatch):
    plan_path, profile, sa = recent.tmp / "plan.json", recent.tmp / "profile.db", recent.tmp / "sa.db"
    plan_path.write_text(json.dumps(prepared))
    make_profile(profile)
    sa.touch()
    snapshot = SimpleNamespace(tickers=("ONE",), sources_by_ticker={"ONE": ("sa_alpha_picks_former",)})
    monkeypatch.setattr(live, "build_active_universe_snapshot", lambda **kwargs: snapshot)
    monkeypatch.setattr(live, "TradingDayCoverageService", lambda **kwargs: recent.service)
    monkeypatch.setattr(live.sys, "addaudithook", lambda hook: None)
    def connect(source):
        source._ib = raw_source(recent)._ib
        source._connected = True
        return True
    monkeypatch.setattr(live.IBKRDataSource, "connect", connect)
    args = SimpleNamespace(plan=plan_path, profile=profile, sa=sa, output=recent.tmp / "output", repair_id="2" * 32)
    old_level = live.logging.root.manager.disable
    try:
        result = live.execute(args, expected=prepared["plan_sha256"])
    finally:
        live.logging.disable(old_level)
    assert result["result"]["status"] == "succeeded"
    assert result["metrics"]["actual_data_calls"] == {"qualification": 1, "history": 1}
    assert result["dispatch_reservations"] == result["received_responses"] == 2
    assert result["new_target_rows_inside_scope"] == 156
    assert result["preexisting_target_rows_changed"] == result["new_target_rows_outside_scope_observed"] == 0
    assert result["after_coverage"]["missing_ticker_days"] == 0
    assert (args.output / "market.before.db").exists()
    assert (args.output / "result.private.json").exists()


def test_backup_failure_never_attempts_gateway(recent, prepared, monkeypatch):
    plan_path, profile, sa = recent.tmp / "plan.json", recent.tmp / "profile.db", recent.tmp / "sa.db"
    plan_path.write_text(json.dumps(prepared))
    make_profile(profile)
    sa.touch()
    monkeypatch.setattr(live, "build_active_universe_snapshot", lambda **kwargs: SimpleNamespace(tickers=("ONE",)))
    monkeypatch.setattr(live, "TradingDayCoverageService", lambda **kwargs: recent.service)
    monkeypatch.setattr(live, "backup", lambda *args: (_ for _ in ()).throw(live.Stopped("backup_failed")))
    monkeypatch.setattr(live, "MeteredSource", lambda *args: SimpleNamespace(
        connect=lambda: pytest.fail("no provider before backup"), disconnect=lambda: None))
    args = SimpleNamespace(plan=plan_path, profile=profile, sa=sa, output=recent.tmp / "output", repair_id="3" * 32)
    with pytest.raises(live.Stopped, match="backup_failed"):
        live.execute(args, expected=prepared["plan_sha256"])


def test_changed_gateway_configuration_stops_before_connection(recent, prepared, monkeypatch):
    plan_path, profile, sa = recent.tmp / "plan.json", recent.tmp / "profile.db", recent.tmp / "sa.db"
    plan_path.write_text(json.dumps(prepared))
    make_profile(profile)
    sa.touch()
    monkeypatch.setattr(live, "build_active_universe_snapshot", lambda **kwargs: SimpleNamespace(tickers=("ONE",)))
    monkeypatch.setattr(live, "TradingDayCoverageService", lambda **kwargs: recent.service)
    original_backup = live.backup
    def changed(*args):
        result = original_backup(*args)
        with sqlite3.connect(profile) as conn:
            conn.execute("UPDATE data_provider_config SET value='4002' WHERE provider='ibkr' AND field='port'")
        return result
    monkeypatch.setattr(live, "backup", changed)
    monkeypatch.setattr(live.IBKRDataSource, "connect", lambda *args: pytest.fail("changed endpoint must not connect"))
    monkeypatch.setattr(live.sys, "addaudithook", lambda hook: None)
    args = SimpleNamespace(plan=plan_path, profile=profile, sa=sa, output=recent.tmp / "output", repair_id="4" * 32)
    old_level = live.logging.root.manager.disable
    try:
        with pytest.raises(live.Stopped, match="live_gateway_settings_changed"):
            live.execute(args, expected=prepared["plan_sha256"])
    finally:
        live.logging.disable(old_level)
