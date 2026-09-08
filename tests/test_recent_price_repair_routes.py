from datetime import date
import threading

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import pytest

from src.api.routes import market_data
from src import prices_runtime
from src import price_repair_execution as execution
from tests.test_recent_price_repair import recent, no_network, raw_source


@pytest.fixture
def http(recent, monkeypatch):
    app = FastAPI()
    app.include_router(market_data.router)
    monkeypatch.setattr(market_data, "resolve_market_db_path", lambda: str(recent.path))
    monkeypatch.setattr(market_data, "require_db_write", lambda *args: None)
    monkeypatch.setattr(market_data, "require_profile_state_write", lambda *args: None)
    monkeypatch.setattr("src.universe_scope.resolve_active_universe", lambda: ["FORMER"])
    monkeypatch.setattr(market_data, "market_data_trading_days", lambda **kwargs: recent.service.get_coverage(universe=["FORMER"], **kwargs))
    with TestClient(app) as client:
        yield client


def test_confirmation_persists_immutable_plan_before_the_scheduler_starts(http, recent, monkeypatch):
    launched = []
    class Thread:
        def __init__(self, **kwargs):
            self.options = kwargs
        def start(self):
            options = self.options["kwargs"]
            loaded = execution.load_repair_plan(execution.repair_directory(recent.path, options["price_repair_id"]))
            assert loaded["preview"]["tickers"] == ["FORMER"]
            assert loaded["request_budget"] == {"qualification": 1, "history": 1, "total": 2}
            launched.append(self.options)
    monkeypatch.setattr(threading, "Thread", Thread)
    preview = http.get("/market-data/price-repair/preview?lookback_days=15").json()
    response = http.post("/market-data/price-repair", json={"lookback_days": 15, "preview_sha256": preview["preview_sha256"]})
    assert response.status_code == 200 and len(launched) == 1


@pytest.mark.parametrize("endpoint", ("/market-data/trading-days", "/market-data/price-repair/preview"))
def test_readonly_coverage_and_preview_default_to_fifteen_days(http, recent, monkeypatch, endpoint):
    monkeypatch.setattr("src.universe_scope.resolve_active_universe", lambda: ["FORMER"])
    monkeypatch.setattr(market_data, "TradingDayCoverageService", lambda **kwargs: recent.service)
    response = http.get(endpoint)
    assert response.status_code == 200
    assert response.json()["lookback_days"] == 15
    assert http.get(endpoint + "?lookback_days=10").json()["lookback_days"] == 10


def test_resume_keeps_original_plan_and_rechecks_both_permissions(http, recent, monkeypatch):
    plan = execution.build_repair_plan(recent.service.get_coverage(universe=["FORMER"], lookback_days=15, interval="15min"), recent.path)
    repair_id = "c" * 32
    journal = execution.RepairJournal(execution.repair_directory(recent.path, repair_id), plan)
    journal.close()
    launched = []
    class Thread:
        def __init__(self, **kwargs):
            launched.append(kwargs)
        def start(self):
            pass
    monkeypatch.setattr(threading, "Thread", Thread)
    def denied(*args):
        raise HTTPException(403, {"code": "permission_denied"})
    for permission in ("require_db_write", "require_profile_state_write"):
        with monkeypatch.context() as guard:
            guard.setattr(market_data, permission, denied)
            assert http.post(f"/market-data/price-repair/{repair_id}/resume").status_code == 403
            assert launched == []
    monkeypatch.setattr(market_data, "market_data_trading_days", lambda **kwargs: pytest.fail("must not replace the approved plan with a new universe preview"))
    response = http.post(f"/market-data/price-repair/{repair_id}/resume")
    assert response.status_code == 200
    assert launched[0]["kwargs"]["price_repair_id"] == repair_id
    assert execution.load_repair_plan(execution.repair_directory(recent.path, repair_id)) == plan


def test_operation_route_reads_durable_history_without_write_permission_or_dispatch(http, recent, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("read-only history must not write or dispatch")
    monkeypatch.setattr(market_data, "require_db_write", forbidden)
    monkeypatch.setattr(market_data, "require_profile_state_write", forbidden)
    monkeypatch.setattr("src.service.data_scheduler.run_source", forbidden)
    response = http.get("/market-data/price-repair/operations")
    assert response.status_code == 200
    assert response.json() == {"version": 1, "operations": [], "total": 0, "offset": 0, "has_more": False}
    plan = execution.build_repair_plan(recent.service.get_coverage(universe=["FORMER"], lookback_days=15, interval="15min"), recent.path)
    execution.RepairJournal(execution.repair_directory(recent.path, "c" * 32), plan).close()
    response = http.get("/market-data/price-repair/operations?limit=1")
    assert response.status_code == 200
    row = response.json()["operations"][0]
    assert row["repair_id"] == "c" * 32 and row["resume"]["available"]
    assert str(recent.path) not in response.text and "plan_sha256" not in response.text
    for query in ("limit=0", "limit=21", "offset=-1"):
        assert http.get("/market-data/price-repair/operations?" + query).status_code == 422


def test_single_operation_read_is_independent_of_history_pagination(http, recent, monkeypatch):
    from src.price_repair_status import price_repair_status
    plan = execution.build_repair_plan(recent.service.get_coverage(universe=["FORMER"], lookback_days=15, interval="15min"), recent.path)
    for digit in "abcdef":
        execution.RepairJournal(execution.repair_directory(recent.path, digit * 32), plan).close()
    expected = price_repair_status(recent.path, "a" * 32, universe=["FORMER"])
    def forbidden(*args, **kwargs):
        pytest.fail("one operation read must not page history, write or dispatch")
    monkeypatch.setattr("src.price_repair_status.list_price_repairs", forbidden)
    monkeypatch.setattr(market_data, "require_db_write", forbidden)
    monkeypatch.setattr(market_data, "require_profile_state_write", forbidden)
    monkeypatch.setattr("src.service.data_scheduler.run_source", forbidden)
    response = http.get("/market-data/price-repair/" + "a" * 32)
    assert response.status_code == 200
    assert response.json() == expected
    assert http.get("/market-data/price-repair/not-a-repair").status_code == 422


@pytest.mark.parametrize("state", ("complete", "scope_changed", "unanswered"))
def test_resume_rechecks_coverage_and_scope_before_dispatch(http, recent, monkeypatch, state):
    repair_id = "d" * 32
    plan = execution.build_repair_plan(recent.service.get_coverage(universe=["FORMER"], lookback_days=15, interval="15min"), recent.path, pacing_seconds=0)
    directory = execution.repair_directory(recent.path, repair_id)
    journal = execution.RepairJournal(directory, plan)
    if state == "unanswered":
        spec = plan["requests"][0]
        journal.conn.execute("INSERT INTO dispatches VALUES(?,?,?)", (execution._digest(spec), execution._json(spec), 100))
        journal.conn.commit()
    journal.close()
    if state == "complete":
        execution.execute_price_repair(plan, directory, source=raw_source(recent), active_scope=lambda: {"FORMER"},
                                       coverage_reader=recent.service.get_coverage, acquire_gateway_lock=False)
    if state == "scope_changed":
        monkeypatch.setattr("src.universe_scope.resolve_active_universe", lambda: [])
    launched = []
    class Thread:
        def __init__(self, **kwargs):
            launched.append(kwargs)
        def start(self):
            pass
    monkeypatch.setattr(threading, "Thread", Thread)
    response = http.post(f"/market-data/price-repair/{repair_id}/resume")
    assert launched == []
    if state == "complete":
        assert response.status_code == 200 and response.json()["status"] == "nothing_to_repair"
    else:
        assert response.status_code == 409 and response.json()["detail"]["code"] == "price_repair_resume_unavailable"


def test_worker_requires_a_prepared_plan_before_loading_provider_configuration(recent, monkeypatch, capsys):
    monkeypatch.setattr(prices_runtime, "_apply_provider_config", lambda: pytest.fail("configuration must not load for an unapproved repair"))
    result = prices_runtime.main(["--tickers", "FORMER", "--lookback-days", "15", "--as-of-date", "2026-09-05",
                                  "--no-provider-fallback", "--repair-id", "a" * 32])
    assert result == 1
    assert "price_repair_not_prepared" in capsys.readouterr().out


def test_real_worker_uses_prepared_plan_and_refuses_parameter_changes(recent, monkeypatch):
    plan = execution.build_repair_plan(recent.service.get_coverage(universe=["FORMER"], lookback_days=15, interval="15min"), recent.path, pacing_seconds=0)
    repair_id = "a" * 32
    journal = execution.RepairJournal(execution.repair_directory(recent.path, repair_id), plan)
    journal.close()
    from src import universe_scope
    monkeypatch.setattr(universe_scope, "resolve_active_universe", lambda: ["FORMER", "OTHER"])
    source = raw_source(recent)
    monkeypatch.setattr("src.market_data_direct._default_ibkr_src", lambda: source)
    for kwargs in ({"tickers": "OTHER"}, {"lookback_days": 120}, {"provider": "polygon"}, {"no_provider_fallback": False}, {"as_of_date": date(2026, 9, 4)}):
        options = dict(tickers="FORMER", lookback_days=15, provider="ibkr", gateway_lock_held=True,
                       no_provider_fallback=True, as_of_date=date(2026, 9, 5), repair_id=repair_id)
        with pytest.raises(execution.PriceRepairError, match="price_repair_plan_changed"):
            prices_runtime._run_worker(**(options | kwargs))
        assert source._ib.calls == []
    result = prices_runtime._run_worker(tickers="FORMER", lookback_days=15, provider="ibkr", gateway_lock_held=True,
                                       no_provider_fallback=True, as_of_date=date(2026, 9, 5), repair_id=repair_id)
    safe = prices_runtime.sanitize_result(result)
    assert safe["status"] == "succeeded" and safe["repair_execution"]["requests_total"] == 2
