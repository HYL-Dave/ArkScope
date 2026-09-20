"""Paid requests require an explicit budget; cache reads do not spend it."""

from concurrent.futures import ThreadPoolExecutor
import asyncio
from datetime import datetime, timedelta, timezone
import json
import multiprocessing
from pathlib import Path
import sqlite3
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from data_sources.financial_datasets_client import FinancialDatasetsClient
from data_sources.financial_datasets_governance import (
    FinancialDatasetsFailure, FinancialDatasetsGovernor, FinancialDatasetsPolicy,
)


POLICY = {"enabled": True, "daily_request_limit": 3, "requests_per_minute": 3}


@pytest.fixture
def clock():
    value = [datetime(2026, 9, 20, 12, tzinfo=timezone.utc).timestamp()]
    return value, lambda: value[0]


@pytest.fixture
def client_fixture(tmp_path, monkeypatch, clock):
    from data_sources import financial_datasets_client as module

    monkeypatch.setattr(module, "_FILE_CACHE_DIR", tmp_path / "cache")
    request = Mock()
    request.return_value.status_code = 200
    request.return_value.json.return_value = {
        "income_statements": [], "balance_sheets": [], "cash_flow_statements": [],
    }
    monkeypatch.setattr(module.requests, "get", request)
    governor = FinancialDatasetsGovernor(tmp_path / "governor.db", clock=clock[1])
    client = FinancialDatasetsClient(api_key="offline-test-key", request_policy=POLICY, governor=governor)
    return client, governor, request


def test_key_alone_does_not_authorize_a_paid_cache_miss(tmp_path, monkeypatch):
    from data_sources import financial_datasets_client as module

    monkeypatch.setattr(module, "_FILE_CACHE_DIR", tmp_path / "cache")
    request = Mock()
    request.return_value.json.return_value = {"income_statements": []}
    monkeypatch.setattr(module.requests, "get", request)
    client = FinancialDatasetsClient(api_key="offline-test-key")
    with pytest.raises(RuntimeError, match="^financial_datasets_policy_unconfigured$"):
        client.get_income_statements("TEST")
    request.assert_not_called()


@pytest.mark.parametrize("config,code", [
    (None, "policy_unconfigured"), ({"enabled": True}, "policy_unconfigured"),
    ({"enabled": False}, "paid_requests_disabled"),
    ({**POLICY, "enabled": "false"}, "policy_invalid"),
    ({**POLICY, "daily_request_limit": True}, "policy_invalid"),
    ({**POLICY, "daily_request_limit": 0}, "policy_invalid"),
    ({**POLICY, "requests_per_minute": -1}, "policy_invalid"),
    ({**POLICY, "requests_per_minute": 3.5}, "policy_invalid"),
    ({**POLICY, "daily_request_limit": 2**63}, "policy_invalid"),
    ({**POLICY, "requests_per_minute": None}, "policy_unconfigured"),
])
def test_invalid_or_missing_policy_fails_before_ledger_or_network(client_fixture, config, code):
    client, governor, request = client_fixture
    client._request_policy = config
    with pytest.raises(FinancialDatasetsFailure, match="^financial_datasets_" + code + "$"):
        client.get_income_statements("TEST")
    assert not governor.path.exists()
    request.assert_not_called()


def test_local_cache_hit_needs_neither_permission_nor_ledger(client_fixture):
    client, governor, request = client_fixture
    client._cache_backend = Mock()
    now = datetime.now(timezone.utc)
    client._cache_backend.get_financial_cache_entry.return_value = {
        "source": "financial_datasets", "ticker": "TEST", "fetched_at": now.isoformat(),
        "expires_at": (now + timedelta(days=90)).isoformat(),
        "data": client._envelope({"income_statements": []}, "TEST", "quarterly", 4),
    }
    client._request_policy = None
    assert client.get_income_statements("TEST", freshness="stored") == []
    assert not governor.path.exists()
    request.assert_not_called()


def test_bounded_endpoint_fanout_and_cache_hits(client_fixture):
    client, governor, request = client_fixture
    client.get_income_statements("TEST")
    client.get_income_statements("TEST", freshness="stored")
    assert request.call_count == 1
    client.get_balance_sheets("TEST")
    client.get_cash_flow_statements("TEST")
    assert request.call_count == 3
    with pytest.raises(FinancialDatasetsFailure, match="budget_exhausted"):
        client.get_income_statements("ANOTHER")
    assert request.call_count == 3
    assert all(call.kwargs["allow_redirects"] is False for call in request.call_args_list)
    assert request.return_value.close.call_count == 3
    assert b"offline-test-key" not in governor.path.read_bytes()


def test_timeout_is_counted_and_not_retried(client_fixture):
    import requests

    client, governor, request = client_fixture
    request.side_effect = requests.Timeout("PRIVATE provider diagnostic")
    for _ in range(3):
        with pytest.raises(FinancialDatasetsFailure, match="^financial_datasets_request_failed$"):
            client.get_income_statements("TEST")
    with pytest.raises(FinancialDatasetsFailure, match="budget_exhausted"):
        client.get_income_statements("TEST")
    assert request.call_count == 3


def test_budget_persists_across_instances_and_separates_keys(tmp_path, clock):
    path = tmp_path / "ledger.db"
    policy = FinancialDatasetsPolicy(1, 1)
    FinancialDatasetsGovernor(path, clock=clock[1]).reserve("first-key", policy)
    another = FinancialDatasetsGovernor(path, clock=clock[1])
    with pytest.raises(FinancialDatasetsFailure, match="budget_exhausted"):
        another.reserve("first-key", policy)
    another.reserve("second-key", policy)


def test_rolling_minute_and_utc_day_are_independent(tmp_path, clock):
    value, now = clock
    governor = FinancialDatasetsGovernor(tmp_path / "ledger.db", clock=now)
    policy = FinancialDatasetsPolicy(2, 1)
    governor.reserve("key", policy)
    value[0] += 59.999
    with pytest.raises(FinancialDatasetsFailure, match="rate_limited"):
        governor.reserve("key", policy)
    value[0] += .002
    governor.reserve("key", policy)
    value[0] += 61
    with pytest.raises(FinancialDatasetsFailure, match="budget_exhausted"):
        governor.reserve("key", policy)
    value[0] += 86400
    governor.reserve("key", policy)
    value[0] -= 1
    with pytest.raises(FinancialDatasetsFailure, match="clock_regressed"):
        governor.reserve("key", policy)


def test_previous_day_request_still_consumes_rolling_window(tmp_path, clock):
    value, now = clock
    value[0] = datetime(2026, 9, 20, 23, 59, 50, tzinfo=timezone.utc).timestamp()
    governor = FinancialDatasetsGovernor(tmp_path / "ledger.db", clock=now)
    policy = FinancialDatasetsPolicy(1, 1)
    governor.reserve("key", policy)
    value[0] += 15
    with pytest.raises(FinancialDatasetsFailure, match="rate_limited"):
        governor.reserve("key", policy)
    value[0] += 45
    governor.reserve("key", policy)


def reserve_from_worker(args):
    path, at = args
    try:
        FinancialDatasetsGovernor(Path(path), clock=lambda: at).reserve("shared-key", FinancialDatasetsPolicy(3, 3))
        return "admitted"
    except FinancialDatasetsFailure as exc:
        return exc.code


@pytest.mark.parametrize("processes", (False, True), ids=("threads", "processes"))
def test_concurrent_consumers_cannot_overspend(tmp_path, clock, processes):
    args = [(str(tmp_path / "ledger.db"), clock[1]())] * 12
    if processes:
        with multiprocessing.get_context("spawn").Pool(4) as pool:
            results = pool.map(reserve_from_worker, args)
    else:
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(reserve_from_worker, args))
    assert results.count("admitted") == 3
    assert results.count("financial_datasets_budget_exhausted") == 9


def test_corrupt_ledger_never_resets_or_dispatches(client_fixture):
    client, governor, request = client_fixture
    governor.path.write_bytes(b"corrupt budget evidence")
    with pytest.raises(FinancialDatasetsFailure, match="governor_unavailable"):
        client.get_income_statements("TEST")
    request.assert_not_called()
    assert governor.path.read_bytes() == b"corrupt budget evidence"


@pytest.mark.parametrize("table", ("fd_request_accounts", "fd_request_starts"))
def test_missing_ledger_table_never_repairs_or_dispatches(client_fixture, table):
    client, governor, request = client_fixture
    governor.reserve(client.api_key, FinancialDatasetsPolicy(3, 3))
    with sqlite3.connect(governor.path) as conn:
        conn.execute("DROP TABLE " + table)
    before = governor.path.read_bytes()
    with pytest.raises(FinancialDatasetsFailure, match="governor_unavailable"):
        client.get_income_statements("TEST")
    request.assert_not_called()
    assert governor.path.read_bytes() == before


@pytest.mark.parametrize("payload", [
    {}, {"error": "private upstream diagnostic"}, {"balance_sheets": []},
    {"income_statements": None}, {"income_statements": ["invalid row"]}, [],
])
def test_invalid_response_is_not_cached_as_absent_financials(client_fixture, payload):
    client, governor, request = client_fixture
    request.return_value.json.return_value = payload
    with pytest.raises(FinancialDatasetsFailure, match="^financial_datasets_response_invalid$"):
        client.get_income_statements("TEST")
    request.assert_called_once()
    request.return_value.close.assert_called_once()
    assert not (governor.path.parent / "cache").exists()
    with sqlite3.connect(governor.path) as conn:
        assert conn.execute("SELECT attempts FROM fd_request_accounts").fetchone() == (1,)


def test_rate_limit_cooldown_is_shared_and_not_retried(client_fixture, clock):
    client, governor, request = client_fixture
    request.return_value.status_code = 429
    request.return_value.headers = {"Retry-After": "120"}
    with pytest.raises(FinancialDatasetsFailure, match="rate_limited"):
        client.get_income_statements("TEST")
    clock[0][0] += 61
    with pytest.raises(FinancialDatasetsFailure, match="rate_limited"):
        FinancialDatasetsGovernor(governor.path, clock=clock[1]).reserve("offline-test-key", FinancialDatasetsPolicy(3, 3))
    assert request.call_count == 1
    request.return_value.close.assert_called_once()
    clock[0][0] += 59
    request.return_value.status_code = 200
    client.get_income_statements("TEST")
    assert request.call_count == 2


@pytest.mark.parametrize("status,code", [
    (302, "redirect_refused"), (401, "access_denied"),
    (402, "payment_required"), (403, "access_denied"),
])
def test_http_refusal_is_closed_and_consumes_attempt(client_fixture, status, code):
    import requests

    client, governor, request = client_fixture
    request.return_value.status_code = status
    if status >= 400:
        request.return_value.raise_for_status.side_effect = requests.HTTPError("PRIVATE provider diagnostic")
    with pytest.raises(FinancialDatasetsFailure, match="^financial_datasets_" + code + "$"):
        client.get_income_statements("TEST")
    request.assert_called_once()
    assert request.call_args.kwargs["allow_redirects"] is False
    request.return_value.json.assert_not_called()
    request.return_value.close.assert_called_once()
    assert not (governor.path.parent / "cache").exists()
    with sqlite3.connect(governor.path) as conn:
        assert conn.execute("SELECT attempts FROM fd_request_accounts").fetchone() == (1,)


@pytest.mark.parametrize("ticker,period,limit", [("../../outside", "annual", 1), ("TEST", "bad", 1), ("TEST", "annual", True)])
def test_invalid_query_never_reaches_cache_or_governor(client_fixture, ticker, period, limit):
    client, governor, request = client_fixture
    with pytest.raises(FinancialDatasetsFailure, match="query_invalid"):
        client.get_income_statements(ticker, period=period, limit=limit)
    request.assert_not_called()
    assert not governor.path.exists()


@pytest.fixture
def fallback_dal(monkeypatch):
    monkeypatch.setenv("FINANCIAL_DATASETS_API_KEY", "offline-test-key")
    backend = Mock()
    backend.get_financial_cache_entry.return_value = None
    sec = Mock()
    sec.get_income_statement.return_value = []
    sec.get_balance_sheet.return_value = []
    sec.get_cash_flow_statement.return_value = []
    monkeypatch.setattr("data_sources.sec_edgar_financials.SECEdgarFinancials", lambda: sec)
    return SimpleNamespace(_backend=backend, get_user_profile=lambda: {
        "data_preferences": {"paid_sources": {"financial_datasets": {"enabled": True}}},
    })


@pytest.mark.parametrize("channel", ("openai", "anthropic", "chatgpt", "claude"))
def test_all_channels_expose_unconfigured_spend_as_a_gap(
    channel, fallback_dal, client_fixture,
):
    from tests.test_sec_research_tool_adapters import unwrap
    from src.tools.registry import create_default_registry

    _, _, request = client_fixture
    dal = fallback_dal
    name, arguments = "get_fundamentals_analysis", {"ticker": "TEST"}

    async def invoke():
        if channel == "openai":
            from agents.tool_context import ToolContext
            from src.agents.openai_agent.tools import create_openai_tools
            tool = next(t for t in create_openai_tools(dal) if t.name == "tool_" + name)
            assert "Financial Datasets" in tool.description and "charges" in tool.description
            payload = json.dumps(arguments)
            context = ToolContext(context=None, tool_name=tool.name, tool_call_id="offline-fd", tool_arguments=payload)
            return await tool.on_invoke_tool(context, payload)
        if channel == "anthropic":
            from src.agents.anthropic_agent.tools import execute_tool_async, get_anthropic_tools
            description = next(t["description"] for t in get_anthropic_tools() if t["name"] == name)
            assert "Financial Datasets" in description and "charges" in description
            return await execute_tool_async(name, arguments, dal)
        registry = create_default_registry()
        description = registry.get(name).description
        assert "Financial Datasets" in description and "charges" in description
        if channel == "chatgpt":
            from src.auth_drivers.chatgpt_oauth_driver import OpenAIChatGPTOAuthDriver
            ok, result = await OpenAIChatGPTOAuthDriver(registry=registry, dal=dal)._invoke_tool(
                name=name, args=arguments, token=None)
            assert ok
            return result
        from src.auth_drivers.claude_code_sdk_driver import _invoke_bridged_tool
        result = await _invoke_bridged_tool(name=name, args=arguments, registry=registry,
                                          dal=dal, token=None, per_tool_timeout_s=5)
        assert not result["is_error"]
        return result["content"][0]["text"]

    result = unwrap(asyncio.run(invoke()))
    assert result["data_source"] == "none"
    assert result["acquisition_gaps"] == [
        {"provider": "sec_edgar", "code": "sec_financials_unavailable"},
        {"provider": "financial_datasets", "dataset": "income_statements", "code": "financial_datasets_policy_unconfigured"},
        {"provider": "financial_datasets", "dataset": "balance_sheets", "code": "financial_datasets_not_attempted_after_refusal"},
        {"provider": "financial_datasets", "dataset": "cash_flow_statements", "code": "financial_datasets_not_attempted_after_refusal"},
    ]
    request.assert_not_called()


def test_partial_paid_result_is_preserved_and_fanout_stops(
    client_fixture, fallback_dal, monkeypatch,
):
    from src.tools.analysis_tools import get_fundamentals_analysis
    from data_sources import financial_datasets_client as module
    from tests.test_financial_datasets import MOCK_INCOME_RESPONSE

    client, _, request = client_fixture
    client._request_policy = {**POLICY, "daily_request_limit": 1}
    client._cache_backend = fallback_dal._backend
    request.return_value.json.return_value = MOCK_INCOME_RESPONSE
    monkeypatch.setattr(module, "FinancialDatasetsClient", lambda **kwargs: client)
    result = get_fundamentals_analysis(fallback_dal, "AAPL")
    assert result.data_source == "financial_datasets"
    assert result.income_statements[0].data["revenue"] == 416161000000.0
    assert result.acquisition_gaps == [
        {"provider": "sec_edgar", "code": "sec_financials_unavailable"},
        {"provider": "financial_datasets", "dataset": "balance_sheets", "code": "financial_datasets_budget_exhausted"},
        {"provider": "financial_datasets", "dataset": "cash_flow_statements", "code": "financial_datasets_not_attempted_after_refusal"},
    ]
    assert result.balance_sheet == [] and result.cash_flow_statements == []
    assert request.call_count == 1
