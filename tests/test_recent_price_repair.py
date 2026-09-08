"""Fifteen-day collection and bounded repair preserve historical coverage truth."""

from datetime import date, datetime, time, timedelta, timezone
import socket
import sqlite3
from types import SimpleNamespace

import pytest

from src import market_data_direct, prices_runtime
from src.market_coverage.repair import preview_price_repair
from src.market_coverage.service import TradingDayCoverageService
from tests.test_market_data_direct import _bar
from tests.test_trading_day_coverage import _Calendar, _Fixtures, _session, _slots, _create_market_db


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("recent_price_test_must_not_use_network")
    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)


@pytest.fixture
def recent(tmp_path, monkeypatch):
    path = tmp_path / "market.db"
    _create_market_db(path)
    now = datetime(2026, 9, 5, 17, tzinfo=timezone.utc)
    first, last = date(2026, 8, 21), date(2026, 9, 5)
    sessions = {first + timedelta(days=i): _session(first + timedelta(days=i))
                for i in range((last - first).days + 1) if (first + timedelta(days=i)).weekday() < 5}
    from src.market_coverage.models import CalendarDay
    calendar = {first + timedelta(days=i): sessions.get(first + timedelta(days=i), CalendarDay.closed(first + timedelta(days=i)))
                for i in range((last - first).days + 1)}
    service = TradingDayCoverageService(db_path=path, calendar_adapter=_Calendar(calendar), fixtures=_Fixtures(), clock=lambda: now)
    monkeypatch.setattr(market_data_direct, "resolve_market_db_path", lambda: str(path))
    monkeypatch.setattr(market_data_direct, "_norm_now_et", lambda value=None: now)
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    return SimpleNamespace(path=path, now=now, sessions=sessions, service=service, tmp=tmp_path)


class WindowSource:
    def __init__(self, sessions):
        self.sessions = sessions
        self.calls = []

    def fetch_historical_intraday(self, tickers, start, end, **kwargs):
        self.calls.append((tuple(tickers), start, end))
        return {ticker: [_bar(at) for day, session in self.sessions.items() if start <= day <= end for at in _slots(session)]
                for ticker in tickers}


def test_explicit_five_day_topup_preserves_the_legacy_window_diagnosis(recent, monkeypatch):
    source = WindowSource(recent.sessions)
    monkeypatch.setattr(market_data_direct, "_default_ibkr_src", lambda: source)
    monkeypatch.setattr(market_data_direct, "_default_polygon_src", lambda: pytest.fail("fallback"))
    result = prices_runtime._run_worker(tickers="FORMER", lookback_days=prices_runtime.parse_args(["--tickers", "FORMER", "--lookback-days", "5"]).lookback_days,
                                       provider="ibkr", gateway_lock_held=True, no_provider_fallback=True)
    assert result["status"] == "succeeded" and result["errors"] == {}
    assert source.calls == [(("FORMER",), date(2026, 8, 31), date(2026, 9, 4))]
    recent_coverage = recent.service.get_coverage(universe=["FORMER"], lookback_days=5, interval="15min")
    assert recent_coverage.history_gaps == []
    wider = recent.service.get_coverage(universe=["FORMER"], lookback_days=15, interval="15min")
    assert wider.history_gaps[0].reason == "before_first_local_bar"
    assert wider.history_gaps[0].missing_dates == ["2026-08-21", "2026-08-24", "2026-08-25", "2026-08-26", "2026-08-27", "2026-08-28"]
    assert preview_price_repair(wider)["tickers"] == ["FORMER"]


@pytest.mark.parametrize("entry", ("worker", "direct"))
def test_default_topup_fills_fifteen_days_without_overwriting_existing_prices(recent, monkeypatch, entry):
    source = WindowSource(recent.sessions)
    monkeypatch.setattr(market_data_direct, "_default_ibkr_src", lambda: source)
    with sqlite3.connect(recent.path) as conn:
        conn.execute("INSERT INTO prices VALUES ('FORMER','2026-08-21T13:30:00+0000','15min',77,78,76,77,10)")
        conn.execute("INSERT INTO prices VALUES ('OTHER','2026-06-01T13:30:00+0000','15min',8,9,7,8,10)")
    def run():
        if entry == "direct":
            return market_data_direct.backfill_prices_direct(
                tickers_arg="FORMER", provider="ibkr", acquire_gateway_lock=False, allow_provider_fallback=False)
        args = prices_runtime.parse_args(["--tickers", "FORMER"])
        return prices_runtime._run_worker(tickers="FORMER", lookback_days=args.lookback_days, provider="ibkr",
                                          gateway_lock_held=True, no_provider_fallback=True)
    result = run()
    assert result["status"] == "succeeded"
    assert source.calls == [(("FORMER",), date(2026, 8, 21), date(2026, 9, 4))]
    assert result["rows_added"] == 285
    assert recent.service.get_coverage(universe=["FORMER"], lookback_days=15, interval="15min").history_gaps == []
    assert run()["rows_added"] == 0
    with sqlite3.connect(recent.path) as conn:
        assert conn.execute("SELECT close FROM prices WHERE ticker='FORMER' ORDER BY datetime LIMIT 1").fetchone() == (77,)
        assert conn.execute("SELECT count(*),min(close) FROM prices WHERE ticker='OTHER'").fetchone() == (1,8)


def test_explicit_repair_reuses_fetched_response_after_write_interruption(recent, monkeypatch):
    from src import price_repair_execution as execution
    plan = execution.build_repair_plan(recent.service.get_coverage(universe=["FORMER"], lookback_days=15, interval="15min"), recent.path, pacing_seconds=0)
    source = raw_source(recent)
    journal = recent.tmp / "repair"
    class Interrupted(BaseException):
        pass
    with monkeypatch.context() as fault:
        fault.setattr(market_data_direct, "_insert_rows", lambda *args: (_ for _ in ()).throw(Interrupted()))
        with pytest.raises(Interrupted):
            execution.execute_price_repair(plan, journal, source=source, active_scope=lambda: {"FORMER"}, coverage_reader=recent.service.get_coverage,
                                           acquire_gateway_lock=False, pacing_seconds=0)
    assert len(source._ib.calls) == 2
    monkeypatch.setattr(market_data_direct, "_default_ibkr_src", lambda: pytest.fail("resume must not contact Gateway"))
    result = execution.execute_price_repair(plan, journal, active_scope=lambda: {"FORMER"}, coverage_reader=recent.service.get_coverage,
                                           acquire_gateway_lock=False, pacing_seconds=0)
    assert result["status"] == "succeeded" and result["repair_execution"]["requests_this_execution"] == 0
    assert result["repair_execution"]["requests_total"] == 2
    assert recent.service.get_coverage(universe=["FORMER"], lookback_days=15, interval="15min").history_gaps == []


def raw_source(recent):
    from data_sources.ibkr_source import IBKRDataSource
    from ib_insync import Stock
    class Raw:
        RaiseRequestErrors = False

        def __init__(self):
            self.calls = []
        def isConnected(self):
            return True
        def qualifyContracts(self, contract):
            self.calls.append(("qualification", contract.symbol))
            result = Stock(contract.symbol, "SMART", "USD")
            result.conId = 123
            return [result]
        def reqHistoricalData(self, contract, **kwargs):
            self.calls.append(("history", dict(kwargs)))
            end = datetime.strptime(kwargs["endDateTime"].split()[0], "%Y%m%d").date()
            start = end - timedelta(days=int(kwargs["durationStr"].split()[0]) - 1)
            return [SimpleNamespace(date=at, open=10, high=11, low=9, close=10.5, volume=100)
                    for day, session in recent.sessions.items() if start <= day <= end for at in _slots(session)]
        def disconnect(self):
            pass
    source = IBKRDataSource(host="127.0.0.1", port=4001, client_id=777)
    source._ib = Raw()
    source._connected = True
    source.REQUEST_DELAY = 0
    return source


def test_repair_dispatch_budget_and_cached_qualification_survive_resume(recent):
    from src import price_repair_execution as execution
    coverage = recent.service.get_coverage(universe=["FORMER"], lookback_days=15, interval="15min")
    plan = execution.build_repair_plan(coverage, recent.path, pacing_seconds=0)
    assert plan["request_budget"] == {"qualification": 1, "history": 1, "total": 2}
    source = raw_source(recent)
    journal = recent.tmp / "repair"
    result = execution.execute_price_repair(plan, journal, source=source, active_scope=lambda: {"FORMER"},
                                           coverage_reader=recent.service.get_coverage, acquire_gateway_lock=False, pacing_seconds=0)
    assert result["repair_execution"]["requests_total"] == len(source._ib.calls) == 2
    before = recent.path.read_bytes()
    replay = execution.execute_price_repair(plan, journal, source=source, active_scope=lambda: {"FORMER", "UNRELATED"},
                                           coverage_reader=recent.service.get_coverage, acquire_gateway_lock=False, pacing_seconds=0)
    assert replay["status"] == "succeeded" and replay["repair_execution"]["requests_this_execution"] == 0
    assert len(source._ib.calls) == 2 and recent.path.read_bytes() == before


def repair_setup(recent, tickers=("FORMER",)):
    from src import price_repair_execution as execution
    plan = execution.build_repair_plan(recent.service.get_coverage(universe=tickers, lookback_days=15, interval="15min"), recent.path, pacing_seconds=0)
    return execution, plan, raw_source(recent), recent.tmp / "repair"


def run_repair(recent, execution, plan, source, journal, **options):
    return execution.execute_price_repair(plan, journal, source=source, active_scope=options.pop("active_scope", lambda: {"FORMER", "OTHER"}),
                                         coverage_reader=recent.service.get_coverage, acquire_gateway_lock=False, **options)


def test_resume_reuses_a_completed_qualification_before_the_first_history_request(recent, monkeypatch):
    execution, plan, source, journal = repair_setup(recent)
    dispatch = execution.RepairJournal.dispatch
    class Interrupted(BaseException):
        pass
    def after_qualification(self, kind, *args, **kwargs):
        result = dispatch(self, kind, *args, **kwargs)
        if kind == "qualification":
            raise Interrupted()
        return result
    with monkeypatch.context() as fault:
        fault.setattr(execution.RepairJournal, "dispatch", after_qualification)
        with pytest.raises(Interrupted):
            run_repair(recent, execution, plan, source, journal)
    assert [row[0] for row in source._ib.calls] == ["qualification"]
    result = run_repair(recent, execution, plan, source, journal)
    assert result["status"] == "succeeded"
    assert result["repair_execution"]["requests_this_execution"] == 1
    assert [row[0] for row in source._ib.calls] == ["qualification", "history"]


def test_unknown_dispatch_is_not_retried_but_other_authorized_items_can_finish(recent, monkeypatch):
    execution, plan, source, journal = repair_setup(recent, ("FORMER", "OTHER"))
    history = source._ib.reqHistoricalData
    class Interrupted(BaseException):
        pass
    def interrupted(*args, **kwargs):
        history(*args, **kwargs)
        raise Interrupted()
    with monkeypatch.context() as fault:
        fault.setattr(source._ib, "reqHistoricalData", interrupted)
        with pytest.raises(Interrupted):
            run_repair(recent, execution, plan, source, journal)
    assert len(source._ib.calls) == 2
    result = run_repair(recent, execution, plan, source, journal)
    assert result["status"] == "partial"
    assert result["errors"] == {"FORMER": "price_repair_dispatch_unknown"}
    assert len(source._ib.calls) == 4
    assert result["repair_execution"]["requests_total"] == plan["request_budget"]["total"] == 4
    assert recent.service.get_coverage(universe=["OTHER"], lookback_days=15, interval="15min").history_gaps == []


@pytest.mark.parametrize("field,value", (("useRTH", False), ("barSizeSetting", "1 min"), ("whatToShow", "BID"), ("durationStr", "120 D")))
def test_actual_request_parameters_must_match_the_authorized_plan(recent, monkeypatch, field, value):
    execution, plan, source, journal = repair_setup(recent)
    fetch = source.fetch_historical_intraday
    def changed(*args, request_runner, **kwargs):
        def runner(kind, context, operation, call_args, call_kwargs):
            if kind == "history":
                call_kwargs = {**call_kwargs, field: value}
            return request_runner(kind, context, operation, call_args, call_kwargs)
        return fetch(*args, request_runner=runner, **kwargs)
    monkeypatch.setattr(source, "fetch_historical_intraday", changed)
    with pytest.raises(execution.PriceRepairError, match="price_repair_unplanned_request"):
        run_repair(recent, execution, plan, source, journal)
    assert [row[0] for row in source._ib.calls] == ["qualification"]
    with sqlite3.connect(recent.path) as conn:
        assert conn.execute("SELECT count(*) FROM prices").fetchone()[0] == 0


@pytest.mark.parametrize("change", ("shape", "content", "binding"))
def test_request_response_tampering_is_rejected_before_any_new_request(recent, monkeypatch, change):
    import json
    execution, plan, source, journal = repair_setup(recent)
    class Interrupted(BaseException):
        pass
    with monkeypatch.context() as fault:
        fault.setattr(market_data_direct, "_insert_rows", lambda *args: (_ for _ in ()).throw(Interrupted()))
        with pytest.raises(Interrupted):
            run_repair(recent, execution, plan, source, journal)
    with sqlite3.connect(journal / "requests.sqlite3") as conn:
        if change == "shape":
            conn.execute("UPDATE responses SET payload='{}'")
        else:
            key = execution._digest(next(row for row in plan["requests"] if row["kind"] == "history"))
            payload, seal = conn.execute("SELECT payload,sha256 FROM responses WHERE request_key=?", (key,)).fetchone()
            value = json.loads(payload)
            if change == "content":
                value["data"][0]["open"] = 999
            else:
                value["request_key"] = "f" * 64
                seal = execution._digest(value)
            conn.execute("UPDATE responses SET payload=?,sha256=? WHERE request_key=?", (json.dumps(value), seal, key))
    with pytest.raises(execution.PriceRepairError, match="price_repair_integrity"):
        run_repair(recent, execution, plan, source, journal)
    assert len(source._ib.calls) == 2


def test_removed_target_blocks_request_without_blocking_an_unrelated_new_membership(recent):
    execution, plan, source, journal = repair_setup(recent)
    result = run_repair(recent, execution, plan, source, journal, active_scope=lambda: {"UNRELATED"})
    assert result["status"] == "failed" and result["errors"] == {"FORMER": "price_repair_scope_changed"}
    assert source._ib.calls == []
    result = run_repair(recent, execution, plan, source, journal, active_scope=lambda: {"FORMER", "UNRELATED"})
    assert result["status"] == "succeeded" and len(source._ib.calls) == 2


def test_target_removed_after_response_is_not_written(recent, monkeypatch):
    execution, plan, source, journal = repair_setup(recent)
    active = {"FORMER"}
    history = source._ib.reqHistoricalData
    def removed(*args, **kwargs):
        response = history(*args, **kwargs)
        active.clear()
        return response
    monkeypatch.setattr(source._ib, "reqHistoricalData", removed)
    result = run_repair(recent, execution, plan, source, journal, active_scope=lambda: active)
    assert result["errors"] == {"FORMER": "price_repair_scope_changed"}
    with sqlite3.connect(recent.path) as conn:
        assert conn.execute("SELECT count(*) FROM prices").fetchone()[0] == 0


@pytest.mark.parametrize("outcome", ("empty", "partial", "failure", "no_contract"))
def test_incomplete_or_failed_provider_result_is_never_retried_or_called_complete(recent, monkeypatch, outcome):
    execution, plan, source, journal = repair_setup(recent)
    history = source._ib.reqHistoricalData
    qualify = source._ib.qualifyContracts
    def limited(*args, **kwargs):
        bars = history(*args, **kwargs)
        if outcome == "failure":
            raise RuntimeError("PRIVATE_PROVIDER_TEXT")
        return [] if outcome == "empty" else bars[:1]
    def absent(*args, **kwargs):
        qualify(*args, **kwargs)
        return []
    if outcome == "no_contract":
        monkeypatch.setattr(source._ib, "qualifyContracts", absent)
    else:
        monkeypatch.setattr(source._ib, "reqHistoricalData", limited)
    monkeypatch.setattr(market_data_direct, "_default_polygon_src", lambda: pytest.fail("fallback"))
    first = run_repair(recent, execution, plan, source, journal)
    calls = len(source._ib.calls)
    second = run_repair(recent, execution, plan, source, journal)
    assert first["status"] == second["status"] == "failed"
    assert len(source._ib.calls) == calls and second["repair_execution"]["requests_this_execution"] == 0
    assert "PRIVATE_PROVIDER_TEXT" not in str(first) + str(second)


def test_repair_does_not_fold_unrelated_aliases_or_write_outside_requested_rth_slots(recent, monkeypatch):
    with sqlite3.connect(recent.path) as conn:
        conn.execute("CREATE TABLE ticker_aliases (alias TEXT PRIMARY KEY, canonical TEXT NOT NULL)")
        conn.execute("INSERT INTO ticker_aliases VALUES ('OLD', 'NEW')")
        conn.execute("INSERT INTO prices VALUES ('OLD','2026-06-01T13:30:00+0000','15min',1,1,1,1,1)")
    execution, plan, source, journal = repair_setup(recent)
    history = source._ib.reqHistoricalData
    def extra(*args, **kwargs):
        bars = history(*args, **kwargs)
        return bars + [SimpleNamespace(date=datetime(2026, 8, 21, 1, tzinfo=timezone.utc), open=3, high=3, low=3, close=3, volume=3)]
    monkeypatch.setattr(source._ib, "reqHistoricalData", extra)
    result = run_repair(recent, execution, plan, source, journal)
    assert result["status"] == "succeeded"
    with sqlite3.connect(recent.path) as conn:
        assert conn.execute("SELECT ticker,datetime FROM prices WHERE ticker<>'FORMER'").fetchall() == [("OLD", "2026-06-01T13:30:00+0000")]
        assert conn.execute("SELECT count(*) FROM prices WHERE ticker='FORMER'").fetchone()[0] == 11 * 26


def test_plan_binds_dates_budget_provider_and_integer_types(recent):
    import copy
    execution, plan, _, _ = repair_setup(recent)
    for key, value in (("request_budget", {"qualification": True, "history": 1, "total": 2}), ("version", 2), ("pacing_seconds", -1)):
        changed = copy.deepcopy(plan)
        changed[key] = value
        changed["plan_sha256"] = execution._digest({k: v for k, v in changed.items() if k != "plan_sha256"})
        with pytest.raises(execution.PriceRepairError, match="price_repair_integrity"):
            execution.validate_repair_plan(changed)


def test_sealed_plan_edit_is_rejected_before_gateway_or_journal_creation(recent):
    import copy
    execution, plan, source, journal = repair_setup(recent)
    changed = copy.deepcopy(plan)
    changed["pacing_seconds"] = 0.5
    with pytest.raises(execution.PriceRepairError, match="price_repair_integrity"):
        run_repair(recent, execution, changed, source, journal)
    assert source._ib.calls == [] and not journal.exists()


def test_gateway_failure_attempts_connection_once_not_once_per_ticker(recent, monkeypatch):
    execution, plan, source, journal = repair_setup(recent, ("FORMER", "OTHER"))
    connections = []
    monkeypatch.setattr(source, "connect", lambda: connections.append(True) and True)
    result = run_repair(recent, execution, plan, source, journal)
    assert result["status"] == "failed"
    assert len(connections) == 1 and source._ib.calls == []


def test_scheduler_preserves_measured_repair_diagnostics_and_typed_failures(recent):
    import json
    from src.service import data_scheduler
    execution, plan, source, journal = repair_setup(recent)
    result = run_repair(recent, execution, plan, source, journal)
    payload = prices_runtime.sanitize_result(result)
    parsed = data_scheduler._parse_sanitized_prices_worker_stdout(json.dumps(payload))
    assert parsed["repair_execution"] == payload["repair_execution"]
    for code in ("price_repair_integrity", "price_repair_not_prepared", "price_repair_plan_changed"):
        failure = prices_runtime.sanitize_error(execution.PriceRepairError(code))
        parsed = data_scheduler._parse_sanitized_prices_worker_stdout(json.dumps(failure))
        assert parsed["error_code"] == code
        assert data_scheduler._sanitized_prices_worker_failure_message(parsed) == code
    payload["repair_execution"]["requests_total"] = True
    assert data_scheduler._parse_sanitized_prices_worker_stdout(json.dumps(payload)) is None


def test_planned_source_never_reconnects_after_execution_has_admitted_connection(recent, monkeypatch):
    from data_sources.ibkr_source import IBKRPriceDataError
    source = raw_source(recent)
    source._connected = False
    monkeypatch.setattr(source, "connect", lambda: pytest.fail("unbudgeted reconnect"))
    with pytest.raises(IBKRPriceDataError, match="ibkr_gateway_unavailable"):
        source.fetch_historical_intraday(["FORMER"], date(2026, 8, 21), date(2026, 8, 28), request_runner=lambda *args: pytest.fail("dispatch"))
    assert source._ib.calls == []


def test_planned_request_pacing_survives_resume_and_clock_rollback_is_not_slept_through(recent, monkeypatch):
    execution, _, source, journal_path = repair_setup(recent)
    plan = execution.build_repair_plan(recent.service.get_coverage(universe=["FORMER"], lookback_days=15, interval="15min"), recent.path, pacing_seconds=1.5)
    from ib_insync import Stock
    now, sleeps = [100.0], []
    def sleep(seconds):
        sleeps.append(seconds)
        now[0] += seconds
    monkeypatch.setattr(execution, "time", SimpleNamespace(time=lambda: now[0], sleep=sleep))
    context = {key: value for key, value in plan["requests"][0].items() if key != "kind"}
    journal = execution.RepairJournal(journal_path, plan)
    qualified = journal.dispatch("qualification", context, source._ib.qualifyContracts, (Stock("FORMER", "SMART", "USD"),), {}, active_scope=lambda: {"FORMER"})
    journal.close()
    journal = execution.RepairJournal(journal_path, plan)
    options = dict(endDateTime="20260904 23:59:59 US/Eastern", durationStr="15 D", barSizeSetting="15 mins", whatToShow="TRADES", useRTH=True, formatDate=1)
    now[0] = 99.0
    with pytest.raises(execution.PriceRepairError, match="price_repair_clock_changed"):
        journal.dispatch("history", context, source._ib.reqHistoricalData, (qualified[0],), options, active_scope=lambda: {"FORMER"})
    assert sleeps == [] and len(source._ib.calls) == 1
    now[0] = 100.25
    journal.dispatch("history", context, source._ib.reqHistoricalData, (qualified[0],), options, active_scope=lambda: {"FORMER"})
    assert sleeps == [1.25] and len(source._ib.calls) == 2
    journal.close()


def test_readback_unavailable_is_not_empty_success(recent, monkeypatch):
    execution, plan, source, journal = repair_setup(recent)
    coverage = recent.service.get_coverage(universe=["FORMER"], lookback_days=15, interval="15min")
    unavailable = coverage.model_copy(update={"observation_health": coverage.observation_health.model_copy(update={"status": "unavailable"}), "history_gaps": []})
    with pytest.raises(execution.PriceRepairError, match="price_coverage_unavailable"):
        execution.execute_price_repair(plan, journal, source=source, active_scope=lambda: {"FORMER"},
                                       coverage_reader=lambda **kwargs: unavailable, acquire_gateway_lock=False)
    assert source._ib.calls == []


def test_half_day_and_holiday_repair_uses_calendar_slots_not_twenty_six_per_day(recent):
    from src.market_coverage.models import CalendarDay
    execution, _, source, journal = repair_setup(recent)
    half = date(2026, 8, 21)
    recent.sessions[half] = _session(half, close_time=time(13))
    holiday = date(2026, 8, 24)
    del recent.sessions[holiday]
    calendar = {date(2026, 8, 21) + timedelta(days=i): recent.sessions.get(date(2026, 8, 21) + timedelta(days=i), CalendarDay.closed(date(2026, 8, 21) + timedelta(days=i))) for i in range(16)}
    service = TradingDayCoverageService(db_path=recent.path, calendar_adapter=_Calendar(calendar), fixtures=_Fixtures(), clock=lambda: recent.now)
    plan = execution.build_repair_plan(service.get_coverage(universe=["FORMER"], lookback_days=15, interval="15min"), recent.path, pacing_seconds=0)
    assert len(plan["slots"][half.isoformat()]) == 14 and holiday.isoformat() not in plan["slots"]
    result = execution.execute_price_repair(plan, journal, source=source, active_scope=lambda: {"FORMER"}, coverage_reader=service.get_coverage, acquire_gateway_lock=False)
    assert result["status"] == "succeeded" and result["rows_added"] == 9 * 26 + 14


def test_approved_coverage_clock_does_not_expand_to_later_intraday_slots(recent, monkeypatch):
    execution, _, source, journal = repair_setup(recent)
    from src.market_coverage.models import CalendarDay
    at = datetime(2026, 9, 4, 15, tzinfo=timezone.utc)
    calendar = {date(2026, 8, 20) + timedelta(days=i): recent.sessions.get(date(2026, 8, 20) + timedelta(days=i), CalendarDay.closed(date(2026, 8, 20) + timedelta(days=i))) for i in range(17)}
    service = TradingDayCoverageService(db_path=recent.path, calendar_adapter=_Calendar(calendar), fixtures=_Fixtures(), clock=lambda: at)
    plan = execution.build_repair_plan(service.get_coverage(universe=["FORMER"], lookback_days=15, interval="15min"), recent.path, pacing_seconds=0)
    clocks = []
    def reader(*, db_path, clock):
        clocks.append(clock())
        return TradingDayCoverageService(db_path=db_path, calendar_adapter=_Calendar(calendar), fixtures=_Fixtures(), clock=clock)
    monkeypatch.setattr(execution, "TradingDayCoverageService", reader)
    result = execution.execute_price_repair(plan, journal, source=source, active_scope=lambda: {"FORMER"}, acquire_gateway_lock=False)
    assert result["status"] == "succeeded" and clocks == [at]
    with sqlite3.connect(recent.path) as conn:
        assert conn.execute("SELECT max(datetime) FROM prices").fetchone()[0] < "2026-09-04T15:00:00+0000"


def test_thirty_two_target_shape_uses_sixty_four_requests_to_fill_190_days_only(recent):
    from src import price_repair_execution as execution
    tickers = [f"F{i:02}" for i in range(31)] + ["CURRENT"]
    rows = [(ticker, market_data_direct._normalize_utc(at), "15min", 20, 21, 19, 20, 200)
            for ticker in tickers for day, session in recent.sessions.items()
            if day >= date(2026, 8, 27 if ticker == "CURRENT" else 31) for at in _slots(session)]
    with sqlite3.connect(recent.path) as conn:
        conn.executemany("INSERT INTO prices VALUES (?,?,?,?,?,?,?,?)", rows)
        conn.execute("INSERT INTO prices VALUES ('UNRELATED','2026-06-05T13:30:00+0000','15min',1,1,1,1,1)")
    before = recent.service.get_coverage(universe=tickers, lookback_days=15, interval="15min")
    plan = execution.build_repair_plan(before, recent.path, pacing_seconds=0)
    assert sum(len(row.missing_dates) for row in before.history_gaps) == 190
    assert plan["request_budget"] == {"qualification": 32, "history": 32, "total": 64}
    source = raw_source(recent)
    result = execution.execute_price_repair(plan, recent.tmp / "large-repair", source=source,
                                           active_scope=lambda: set(tickers) | {"UNRELATED"},
                                           coverage_reader=recent.service.get_coverage, acquire_gateway_lock=False)
    assert result["status"] == "succeeded" and result["rows_added"] == 190 * 26
    assert len(source._ib.calls) == result["repair_execution"]["requests_total"] == 64
    assert recent.service.get_coverage(universe=tickers, lookback_days=15, interval="15min").history_gaps == []
    with sqlite3.connect(recent.path) as conn:
        assert conn.execute("SELECT count(*) FROM prices WHERE open=20").fetchone()[0] == len(rows)
        assert conn.execute("SELECT count(*) FROM prices WHERE ticker='UNRELATED'").fetchone()[0] == 1


def test_repair_writer_does_not_create_a_missing_market_database(recent):
    execution, plan, _, _ = repair_setup(recent)
    recent.path.unlink()
    with pytest.raises(sqlite3.OperationalError):
        execution._write_ticker(plan, "FORMER", [], lambda: {"FORMER"})
    assert not recent.path.exists()


def test_repair_writer_reserves_alias_identity_before_insert(recent, monkeypatch):
    execution, plan, source, journal = repair_setup(recent)
    load_aliases = market_data_direct._load_ticker_aliases
    def reserved(conn):
        assert conn.in_transaction, "alias identity and price insertion must share a transaction"
        return load_aliases(conn)
    monkeypatch.setattr(market_data_direct, "_load_ticker_aliases", reserved)
    assert run_repair(recent, execution, plan, source, journal)["status"] == "succeeded"


def test_changed_alias_blocks_cached_price_write_without_requerying_provider(recent, monkeypatch):
    execution, plan, source, journal = repair_setup(recent)
    history = source._ib.reqHistoricalData
    def renamed(*args, **kwargs):
        values = history(*args, **kwargs)
        with sqlite3.connect(recent.path) as conn:
            conn.execute("CREATE TABLE ticker_aliases (alias TEXT PRIMARY KEY, canonical TEXT)")
            conn.execute("INSERT INTO ticker_aliases VALUES ('FORMER','RENAMED')")
        return values
    monkeypatch.setattr(source._ib, "reqHistoricalData", renamed)
    result = run_repair(recent, execution, plan, source, journal)
    assert result["errors"] == {"FORMER": "price_repair_scope_changed"}
    assert len(source._ib.calls) == 2
    with sqlite3.connect(recent.path) as conn:
        assert conn.execute("SELECT count(*) FROM prices").fetchone()[0] == 0
