"""Durable operation facts stay visible without initiating collection."""

import json
from pathlib import Path
import sqlite3

import pytest

from src import market_data_direct as writer
from src import price_repair_execution as execution
from tests.test_recent_price_repair import recent, no_network, raw_source


CONTRACT = json.loads((Path(__file__).parent / "fixtures" / "price_repair_operations_v1.json").read_text())


def prepare(recent, repair_id="a" * 32):
    plan = execution.build_repair_plan(
        recent.service.get_coverage(universe=["FORMER"], lookback_days=15, interval="15min"),
        recent.path, pacing_seconds=0)
    directory = execution.repair_directory(recent.path, repair_id)
    execution.RepairJournal(directory, plan).close()
    return plan, directory


def read(recent, *, universe=("FORMER",), **kwargs):
    from src.price_repair_status import list_price_repairs
    return list_price_repairs(recent.path, universe=universe,
                              coverage_reader=recent.service.get_coverage, **kwargs)


def test_operation_listing_is_no_create_and_never_loads_a_provider(recent, monkeypatch):
    monkeypatch.setattr(writer, "_default_ibkr_src", lambda: pytest.fail("provider during status read"))
    assert read(recent) == {"version": 1, "operations": [], "total": 0, "offset": 0, "has_more": False}
    assert not (recent.path.parent / "price_repairs").exists()


def test_operation_status_is_readonly_and_does_not_project_cached_provider_material(recent, monkeypatch):
    _, directory = prepare(recent)
    original = sqlite3.connect
    before = (directory / "requests.sqlite3").read_bytes()
    def connect(path, *args, **kwargs):
        assert isinstance(path, str) and path.endswith("?mode=ro") and kwargs.get("uri") is True
        return original(path, *args, **kwargs)
    monkeypatch.setattr(sqlite3, "connect", connect)
    row = read(recent)["operations"][0]
    assert row == CONTRACT["pending"]
    assert row["state"] == "incomplete"
    assert row["requests"] == {"planned": 2, "dispatched": 0, "received": 0, "unanswered": 0}
    assert row["resume"] == {"available": True, "request_limit": 2}
    assert row["coverage"] == {"remaining_tickers": ["FORMER"], "missing_ticker_days": 11, "partial_ticker_days": 0}
    assert str(recent.path) not in json.dumps(row)
    assert "plan_sha256" not in json.dumps(row) and "conId" not in json.dumps(row)
    assert (directory / "requests.sqlite3").read_bytes() == before


def test_cached_but_uncommitted_repair_can_resume_with_zero_new_requests(recent, monkeypatch):
    plan, directory = prepare(recent)
    class Interrupted(BaseException):
        pass
    with monkeypatch.context() as fault:
        fault.setattr(execution, "_write_ticker", lambda *a: (_ for _ in ()).throw(Interrupted()))
        with pytest.raises(Interrupted):
            execution.execute_price_repair(plan, directory, source=raw_source(recent), active_scope=lambda: {"FORMER"},
                                           coverage_reader=recent.service.get_coverage, acquire_gateway_lock=False)
    row = read(recent)["operations"][0]
    assert row == CONTRACT["cached"]
    assert row["state"] == "incomplete"
    assert row["requests"] == {"planned": 2, "dispatched": 2, "received": 2, "unanswered": 0}
    assert row["resume"] == {"available": True, "request_limit": 0}
    monkeypatch.setattr(writer, "_default_ibkr_src", lambda: pytest.fail("cache-only resume must not contact provider"))
    result = execution.execute_price_repair(plan, directory, active_scope=lambda: {"FORMER"},
                                            coverage_reader=recent.service.get_coverage, acquire_gateway_lock=False)
    assert result["rows_added"] == 286
    complete = read(recent)["operations"][0]
    assert complete == CONTRACT["complete"]
    assert complete["state"] == "complete"
    assert complete["coverage"]["remaining_tickers"] == []
    assert complete["resume"] == {"available": False, "request_limit": 0}


def test_received_empty_history_is_not_completion_or_an_effective_cache_resume(recent):
    plan, directory = prepare(recent)
    source = raw_source(recent)
    source._ib.reqHistoricalData = lambda *args, **kwargs: []
    execution.execute_price_repair(plan, directory, source=source, active_scope=lambda: {"FORMER"},
                                   coverage_reader=recent.service.get_coverage, acquire_gateway_lock=False)
    row = read(recent)["operations"][0]
    assert row == CONTRACT["empty_response"]
    assert row["requests"]["received"] == row["requests"]["planned"] == 2
    assert row["state"] == "incomplete" and row["reason"] == "response_incomplete"
    assert row["resume"] == {"available": False, "request_limit": 0}


def test_unanswered_request_stays_explicit_and_cannot_be_reissued(recent):
    plan, directory = prepare(recent)
    journal = execution.RepairJournal(directory, plan)
    spec = plan["requests"][0]
    journal.conn.execute("INSERT INTO dispatches VALUES(?,?,?)", (execution._digest(spec), execution._json(spec), 100))
    journal.conn.commit()
    journal.close()
    row = read(recent)["operations"][0]
    assert row == CONTRACT["unanswered"]
    assert row["state"] == "incomplete" and row["reason"] == "unconfirmed_requests"
    assert row["requests"] == {"planned": 2, "dispatched": 1, "received": 0, "unanswered": 1}
    assert row["resume"] == {"available": False, "request_limit": 0}


def test_removed_scope_and_unreadable_journal_do_not_hide_healthy_operations(recent):
    prepare(recent, "a" * 32)
    _, second = prepare(recent, "b" * 32)
    blocked = read(recent, universe=())["operations"]
    assert next(row for row in blocked if row["repair_id"] == "a" * 32) == CONTRACT["scope_changed"]
    assert all(row["state"] == "blocked" and row["reason"] == "scope_changed" for row in blocked)
    with sqlite3.connect(second / "requests.sqlite3") as conn:
        conn.execute("UPDATE manifest SET sha256='corrupt'")
    rows = {row["repair_id"]: row for row in read(recent)["operations"]}
    assert rows["b" * 32] == CONTRACT["journal_unavailable"]
    assert rows["a" * 32]["resume"]["available"] is True
    assert rows["b" * 32]["state"] == "unavailable"
    assert rows["b" * 32]["scope"] is None and rows["b" * 32]["requests"] is None
    assert rows["b" * 32]["resume"] == {"available": False, "request_limit": 0}


def test_operation_history_can_page_without_silently_dropping_rows(recent):
    for key in ("a", "b", "c"):
        prepare(recent, key * 32)
    first = read(recent, limit=2)
    second = read(recent, limit=2, offset=2)
    assert first["has_more"] and not second["has_more"]
    assert first["total"] == second["total"] == 3
    assert len({row["repair_id"] for page in (first,second) for row in page["operations"]}) == 3


def test_operation_listing_rejects_symlinked_journals_without_reading_them(recent, tmp_path):
    root = recent.path.parent / "price_repairs"
    root.mkdir()
    (root / ("a" * 32)).symlink_to(tmp_path)
    row = read(recent)["operations"][0]
    assert row["state"] == "unavailable" and row["scope"] is None


@pytest.mark.parametrize("cause", ("calendar_unavailable", "clock_changed"))
def test_unavailable_coverage_never_becomes_an_empty_success(recent, cause):
    prepare(recent)
    def unavailable(**kwargs):
        coverage = recent.service.get_coverage(**kwargs)
        if cause == "clock_changed":
            return coverage.model_copy(update={"generated_at_et": "2026-09-06T13:00:00-04:00"})
        from src.market_coverage.models import CalendarHealth
        return coverage.model_copy(update={"calendar_health": coverage.calendar_health.model_copy(update={"status": CalendarHealth.UNAVAILABLE})})
    from src.price_repair_status import list_price_repairs
    row = list_price_repairs(recent.path, universe=["FORMER"], coverage_reader=unavailable)["operations"][0]
    assert row == CONTRACT["coverage_unavailable"]


def test_one_unanswered_ticker_does_not_block_safe_remaining_requests(recent):
    plan = execution.build_repair_plan(recent.service.get_coverage(universe=["FORMER", "OTHER"], lookback_days=15, interval="15min"), recent.path, pacing_seconds=0)
    directory = execution.repair_directory(recent.path, "a" * 32)
    journal = execution.RepairJournal(directory, plan)
    spec = plan["requests"][0]
    journal.conn.execute("INSERT INTO dispatches VALUES(?,?,?)", (execution._digest(spec), execution._json(spec), 100))
    journal.conn.commit()
    journal.close()
    row = read(recent, universe=("FORMER", "OTHER"))["operations"][0]
    assert row["reason"] == "unconfirmed_requests"
    assert row["requests"] == {"planned": 4, "dispatched": 1, "received": 0, "unanswered": 1}
    assert row["resume"] == {"available": True, "request_limit": 2}
    source = raw_source(recent)
    result = execution.execute_price_repair(plan, directory, source=source, active_scope=lambda: {"FORMER", "OTHER"},
                                            coverage_reader=recent.service.get_coverage, acquire_gateway_lock=False)
    assert result["repair_execution"]["requests_this_execution"] == row["resume"]["request_limit"]
    assert result["errors"] == {"FORMER": "price_repair_dispatch_unknown"}
    assert source._ib.calls[0] == ("qualification", "OTHER")
    assert len(source._ib.calls) == 2


def test_readonly_journal_holds_one_verified_snapshot(recent):
    plan, directory = prepare(recent)
    with sqlite3.connect(directory / "requests.sqlite3") as connection:
        connection.execute("PRAGMA journal_mode=WAL")
    reader = execution.RepairJournal(directory, plan, readonly=True)
    writer = execution.RepairJournal(directory, plan)
    try:
        spec = plan["requests"][0]
        value = {"request_key": execution._digest(spec), "code": None, "data": []}
        writer.conn.execute("INSERT INTO dispatches VALUES(?,?,?)", (value["request_key"], execution._json(spec), 100))
        writer.conn.execute("INSERT INTO responses VALUES(?,?,?)", (value["request_key"], execution._json(value), execution._digest(value)))
        writer.conn.commit()
        assert reader.count() == 0
        assert reader.response(spec) is None
    finally:
        reader.close()
        writer.close()
    reader = execution.RepairJournal(directory, plan, readonly=True)
    try:
        assert reader.count() == 1 and reader.response(spec) == []
    finally:
        reader.close()


def test_unrelated_universe_addition_does_not_change_an_original_repair(recent):
    prepare(recent)
    row = read(recent, universe=("FORMER", "UNRELATED"))["operations"][0]
    assert row == CONTRACT["pending"]


def test_partial_response_already_applied_is_not_a_useful_cache_resume(recent):
    plan, directory = prepare(recent)
    source = raw_source(recent)
    history = source._ib.reqHistoricalData
    source._ib.reqHistoricalData = lambda *args, **kwargs: history(*args, **kwargs)[:10]
    execution.execute_price_repair(plan, directory, source=source, active_scope=lambda: {"FORMER"},
                                   coverage_reader=recent.service.get_coverage, acquire_gateway_lock=False)
    row = read(recent)["operations"][0]
    assert row["state"] == "incomplete" and row["reason"] == "response_incomplete"
    assert row["coverage"] == {"remaining_tickers": ["FORMER"], "missing_ticker_days": 10, "partial_ticker_days": 1}
    assert row["resume"] == {"available": False, "request_limit": 0}
