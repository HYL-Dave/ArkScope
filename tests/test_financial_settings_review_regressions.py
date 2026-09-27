"""Review regressions with synthetic observations and mocked metered pages."""

import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import threading
from unittest.mock import Mock

import pytest

from data_sources.financial_datasets_client import FinancialDatasetsClient
from src.fundamentals import read_service
from src.fundamentals.tool_results import apply_financial_result_budget
from src.tools.result_policy import serialize_tool_result
from tests.financial_read_fixtures import financial_local
from tests.test_common_financial_read import read, route, paid, FD
from tests.test_financial_read_settings import KEY, DEFAULTS


BASE = "https://api.financialdatasets.ai/financials/income-statements"


def configure(count, period="annual"):
    values = deepcopy(DEFAULTS)
    values["fd_periods"][period] = dict.fromkeys(values["fd_periods"][period], count)
    route([FD]).set_setting(KEY, json.dumps(values))


def rows(count, period="annual"):
    result = []
    for index in range(count):
        year = 2025 - (index if period == "annual" else index // 4)
        month = 12 if period == "annual" else 12 - (index % 4) * 3
        day = 31 if month in (3, 12) else 30
        result.append(dict(ticker="AAPL", period=period, currency="USD",
            report_period=f"{year}-{month:02d}-{day}", fiscal_period=f"{year}-FY",
            revenue=1000 - index))
    return result


def retain(dal, count, *, age_days=1, period="annual", prefix="income", key="income_statements", from_file=False):
    fetched = datetime.now(timezone.utc) - timedelta(days=age_days)
    payload = {key: rows(count, period)}
    cache_key = f"fd_v1_{prefix}_AAPL_{period}_{count}"
    envelope = FinancialDatasetsClient._envelope(payload, "AAPL", period, count)
    if from_file:
        assert FinancialDatasetsClient()._write_file_cache(cache_key, "AAPL", envelope,
            fetched, fetched + timedelta(days=180))
        return
    assert dal._backend.set_financial_cache(cache_key, "AAPL", envelope,
        source=FD, fetched_at=fetched.isoformat(), expires_at=(fetched + timedelta(days=180)).isoformat())


@pytest.mark.parametrize("channel", ["chatgpt", "claude"])
def test_no_additional_metered_pages_after_bridge_timeout(financial_local, monkeypatch, channel):
    dal, http, _ = financial_local
    configure(25)
    paid(dal, http, monkeypatch)
    release, completed = threading.Event(), threading.Event()
    real_read = read_service.read_financials

    def observed_read(*args, **kwargs):
        try:
            return real_read(*args, **kwargs)
        finally:
            completed.set()

    monkeypatch.setattr(read_service, "read_financials", observed_read)
    calls = []
    all_rows = rows(25)

    def reply(url, **kwargs):
        index = len(calls)
        calls.append(url)
        if index == 0:
            assert release.wait(5), "review fixture was not released"
        body = {"income_statements": all_rows[index * 10:(index + 1) * 10]}
        if index < 2:
            body["next_page_url"] = BASE + f"?cursor=page-{index + 1}"
        return Mock(status_code=200, json=lambda: body)

    http.side_effect = reply

    async def scenario():
        from src.tools.registry import create_default_registry
        registry = create_default_registry()
        arguments = dict(ticker="AAPL", period="annual", statement="income_statement",
            source=FD, freshness="refresh")
        async def finish_in_flight_request():
            await asyncio.sleep(0.3)
            release.set()

        response = asyncio.create_task(finish_in_flight_request())
        try:
            if channel == "chatgpt":
                from src.auth_drivers.chatgpt_oauth_driver import OpenAIChatGPTOAuthDriver
                ok, result = await OpenAIChatGPTOAuthDriver(registry=registry, dal=dal,
                    per_tool_timeout_s=0.1)._invoke_tool(name="get_fundamentals_analysis",
                        args=arguments, token=None)
                assert not ok and "timed out" in result
            else:
                from src.auth_drivers.claude_code_sdk_driver import _invoke_bridged_tool
                result = await _invoke_bridged_tool(name="get_fundamentals_analysis", registry=registry,
                    dal=dal, token=None, args=arguments, per_tool_timeout_s=0.1)
                assert result["is_error"] and "timed out" in result["content"][0]["text"]
            at_timeout = len(calls)
        finally:
            release.set()
            await response
            assert await asyncio.to_thread(completed.wait, 5), "review worker did not finish"
        print(f"{channel}: requests_at_timeout={at_timeout}, after_worker_finished={len(calls)}")
        assert len(calls) == at_timeout, "new paid cursor pages started after the tool already timed out"
        assert len(calls) == 1
        assert dal._backend.get_financial_cache_entry("fd_v1_income_AAPL_annual_25") is None

    asyncio.run(scenario())


@pytest.mark.parametrize("from_file", [False, True])
def test_retained_month_readable_across_request_scopes(financial_local, from_file):
    dal, http, _ = financial_local
    configure(3)
    retain(dal, 3, age_days=2, from_file=from_file)
    first = read(dal, source=FD, statement="income_statement", end_month="2023-12", freshness="stored")
    assert len(first.income_statements) == 1
    configure(1)
    retain(dal, 1, age_days=1)
    if not from_file:
        assert dal._backend.get_financial_cache_entry("fd_v1_income_AAPL_annual_3") is not None
    second = read(dal, source=FD, statement="income_statement", end_month="2023-12", freshness="stored")
    http.assert_not_called()
    print("historical read after narrower observation:", second.status, [gap.code for gap in second.read_gaps])
    assert len(second.income_statements) == 1, "the older month remains retained in a separate request scope"
    assert second.read_id == first.read_id
    assert second.source_observations[0]["requested_periods"] == 3
    latest = read(dal, source=FD, statement="income_statement", freshness="stored")
    assert len(latest.income_statements) == 1
    assert latest.source_observations[0]["requested_periods"] == 1


def test_one_period_page_of_long_history_fits_default_cap(financial_local):
    dal, http, _ = financial_local
    configure(80, "quarterly")
    for prefix, key in [("income", "income_statements"), ("balance", "balance_sheets"),
                        ("cashflow", "cash_flow_statements")]:
        retain(dal, 80, period="quarterly", prefix=prefix, key=key)
    result = read(dal, source=FD, period="quarterly", freshness="stored", period_limit=1)
    assert len(result.income_statements) == len(result.balance_sheet) == len(result.cash_flow_statements) == 1
    payload = serialize_tool_result(result, tool_name="get_fundamentals_analysis")
    sizes = {key: len(json.dumps(value, separators=(",", ":"))) for key, value in result.model_dump().items()}
    print("one-period payload chars:", len(payload), "coverage chars:", sizes["coverage"],
        "observation chars:", sizes["source_observations"])
    reduced = json.loads(apply_financial_result_budget(payload, dal))
    http.assert_not_called()
    assert reduced["status"] != "unavailable", reduced
    assert reduced["metric_basis"] == result.metric_basis
    assert reduced["income_statements"] == [row.model_dump() for row in result.income_statements]
    assert reduced["coverage"]["metadata_scope"] == "returned_page"
    assert set(reduced["coverage"]["retained_period_counts"].values()) == {80}
    for observation in reduced["source_observations"]:
        assert observation["retained_period_count"] == 80
        assert observation["report_periods_scope"] == "returned_page"
        assert observation["report_periods"] == ["2025-12-31"]
    next_page = read(dal, source=FD, period="quarterly", freshness="stored", period_limit=1,
        read_id=result.read_id, period_offset=1)
    assert next_page.read_id == result.read_id and next_page.metric_basis == result.metric_basis
    assert next_page.income_statements[0].report_period == "2025-09-30"
    minimal = json.loads(apply_financial_result_budget(serialize_tool_result(next_page,
        tool_name="get_fundamentals_analysis"), dal))
    assert minimal["source_observations"][0]["report_periods"] == ["2025-09-30"]


@pytest.mark.parametrize("channel", ["openai", "anthropic", "chatgpt", "claude"])
@pytest.mark.parametrize("phase", ["in_flight", "admission"])
def test_cancellation_joins_worker_without_followup_pages(financial_local, monkeypatch, channel, phase):
    from data_sources.financial_datasets_governance import FinancialDatasetsGovernor
    from tests.test_freshness_tool_channels import invoke

    dal, http, _ = financial_local
    configure(25)
    paid(dal, http, monkeypatch)
    started, release = threading.Event(), threading.Event()
    admitted = []
    original_reserve = FinancialDatasetsGovernor.reserve

    def reserve(self, *args, **kwargs):
        admitted.append(True)
        if phase == "admission":
            started.set()
            assert release.wait(5)
        return original_reserve(self, *args, **kwargs)

    monkeypatch.setattr(FinancialDatasetsGovernor, "reserve", reserve)

    def reply(*args, **kwargs):
        if phase == "in_flight":
            started.set()
            assert release.wait(5)
        return Mock(status_code=200, json=lambda: {"income_statements": rows(10),
            "next_page_url": BASE + "?cursor=next"})

    http.side_effect = reply

    async def scenario():
        task = asyncio.create_task(invoke(channel, "get_fundamentals_analysis", dict(ticker="AAPL",
            period="annual", statement="income_statement", source=FD, freshness="refresh"), dal,
            allow_errors=True))
        try:
            assert await asyncio.to_thread(started.wait, 5)
            task.cancel()
            await asyncio.sleep(0.02)
            assert not task.done(), "cancelled tools must still own their in-flight request"
            task.cancel()
        finally:
            release.set()
        try:
            await asyncio.wait_for(task, 5)
        except asyncio.CancelledError:
            pass
        assert http.call_count == (1 if phase == "in_flight" else 0)
        assert len(admitted) == 1
        assert dal._backend.get_financial_cache_entry("fd_v1_income_AAPL_annual_25") is None

    asyncio.run(scenario())


@pytest.mark.parametrize("limit,action", [(1, "increase_financial_tool_output_setting"),
    (2, "repeat_same_read_with_smaller_page")])
def test_oversize_recovery_never_recommends_an_impossible_smaller_page(limit, action):
    from src.fundamentals.tool_results import financial_result_reducer

    payload = json.dumps(dict(status="ok", pagination={"limit": limit},
        metric_basis={"revenue": {"evidence": "x" * 5000}}))
    result, _ = financial_result_reducer(payload, budget=800)
    assert json.loads(result)["required_action"] == action


@pytest.mark.parametrize("channel", ["openai", "anthropic", "chatgpt", "claude"])
def test_minimum_page_and_basis_survive_each_channel_with_large_history(financial_local, channel):
    from tests.test_freshness_tool_channels import invoke
    from tests.test_sec_research_tool_adapters import unwrap

    dal, http, _ = financial_local
    configure(80, "quarterly")
    for prefix, key in [("income", "income_statements"), ("balance", "balance_sheets"),
                        ("cashflow", "cash_flow_statements")]:
        retain(dal, 80, period="quarterly", prefix=prefix, key=key)
    arguments = dict(ticker="AAPL", source=FD, period="quarterly", freshness="stored", period_limit=1)
    expected = read(dal, **arguments)
    result = unwrap(asyncio.run(invoke(channel, "get_fundamentals_analysis", arguments, dal)))
    assert result["status"] == "ok"
    assert result["read_id"] == expected.read_id
    assert result["metric_basis"] == expected.metric_basis
    assert result["coverage"]["metadata_scope"] == "returned_page"
    http.assert_not_called()


def test_page_metadata_preserves_sa_month_precision_and_retained_counts(financial_local):
    from src.sa.company_store import save_capture
    from tests.financial_read_fixtures import sa_payload
    from src.fundamentals.tool_results import _page_metadata

    dal, http, _ = financial_local
    save_capture(sa_payload())
    result = read(dal, source="seeking_alpha", statement="income_statement", period_limit=1).model_dump()
    facts, basis = deepcopy(result["income_statements"]), deepcopy(result["metric_basis"])
    assert _page_metadata(result)
    assert result["source_observations"][0]["report_periods"] == ["2025-12"]
    assert result["source_observations"][0]["retained_period_count"] == 2
    assert len(result["coverage"]["statements"]["income_statement"]) == 1
    assert result["income_statements"] == facts and result["metric_basis"] == basis
    projected = deepcopy(result)
    assert _page_metadata(result) and result == projected
    http.assert_not_called()


def test_cancellation_interrupts_acquisition_lock_wait(monkeypatch):
    import fcntl
    from src.fundamentals.execution import invoke_financial_tool
    from src.fundamentals.reuse import acquisition_lock

    waiting = threading.Event()

    def occupied(*_args):
        waiting.set()
        raise BlockingIOError()

    monkeypatch.setattr(fcntl, "flock", occupied)

    def worker():
        with acquisition_lock(["cancel-test"]):
            pytest.fail("cancelled lock waiter acquired")

    async def scenario():
        task = asyncio.create_task(invoke_financial_tool(worker))
        assert await asyncio.to_thread(waiting.wait, 5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 2)
        # The next worker has a new cancellation scope, not a poisoned context.
        assert await invoke_financial_tool(lambda: "ok") == "ok"

    asyncio.run(scenario())
