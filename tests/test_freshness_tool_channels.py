"""The two API-key and two OAuth adapters retain explicit freshness choices."""

import asyncio
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


async def invoke(channel, name, arguments, dal):
    from src.tools.registry import create_default_registry

    if channel == "openai":
        from agents.tool_context import ToolContext
        from src.agents.openai_agent.tools import create_openai_tools
        tool = next(t for t in create_openai_tools(dal) if t.name == "tool_" + name)
        payload = json.dumps(arguments)
        context = ToolContext(context=None, tool_name=tool.name, tool_call_id="freshness-test", tool_arguments=payload)
        return await tool.on_invoke_tool(context, payload)
    if channel == "anthropic":
        from src.agents.anthropic_agent.tools import execute_tool_async
        return await execute_tool_async(name, arguments, dal)
    registry = create_default_registry()
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


@pytest.mark.parametrize("channel", ["openai", "anthropic", "chatgpt", "claude"])
@pytest.mark.parametrize("price_fields,basis", [({"close": 99.0}, "previous_close"), ({"last": 101.0}, "last_trade")])
def test_quote_age_and_unknowns_survive_all_channels(channel, price_fields, basis, monkeypatch):
    from src.tools import current_quote as module
    from tests.test_sec_research_tool_adapters import unwrap

    seen = []
    def fetch(ticker, max_age_seconds):
        seen.append((ticker, max_age_seconds))
        return module._quote_from_ibkr_payload(ticker, price_fields, max_age_seconds=max_age_seconds)
    monkeypatch.setattr(module, "_fetch_ibkr_quote", fetch)
    result = unwrap(asyncio.run(invoke(channel, "get_current_quote",
        {"ticker": "AAPL", "source": "ibkr", "max_age_seconds": 17}, object())))
    assert seen == [("AAPL", 17)]
    assert result["max_age_seconds"] == 17 and result["price_basis"] == basis
    assert result["market_data_type"] == "unknown" and result["timestamp"] is None
    assert result["stale"] is (True if basis == "previous_close" else None)


@pytest.mark.parametrize("channel", ["openai", "anthropic", "chatgpt", "claude"])
@pytest.mark.parametrize("freshness", ["stored", "auto", None])
def test_fd_period_policy_and_original_acquisition_time_survive_all_channels(
    channel, freshness, monkeypatch, tmp_path,
):
    from data_sources import financial_datasets_client as fd_module
    from src.tools.backends.local_market_backend import LocalMarketBackend
    from src.fundamentals.cache import fundamentals_analysis_cache_key
    from tests.test_sec_research_tool_adapters import unwrap

    monkeypatch.setenv("FINANCIAL_DATASETS_API_KEY", "offline-test-key")
    monkeypatch.setattr(fd_module, "_FILE_CACHE_DIR", tmp_path / "files")
    http = Mock(side_effect=AssertionError("stored statements must not spend"))
    monkeypatch.setattr(fd_module.requests, "get", http)
    sec = Mock(side_effect=AssertionError("FD-only fixture must not acquire SEC data"))
    monkeypatch.setattr("data_sources.sec_edgar_financials.SECEdgarFinancials", sec)
    backend = LocalMarketBackend(market_db=str(tmp_path / "market.db"))
    now = datetime.now(timezone.utc)
    fetched = now - timedelta(days=2 if freshness is None else 20)
    expires = now + timedelta(days=70)
    assert backend.set_financial_cache(fundamentals_analysis_cache_key("AAPL", "quarterly"), "AAPL", {"_negative": True})
    for prefix, dataset, limit in [("income", "income_statements", 4), ("balance", "balance_sheets", 1), ("cashflow", "cash_flow_statements", 4)]:
        item = {"ticker": "AAPL", "report_period": "2026-06-30", "fiscal_period": "2026-Q3",
                "period": "quarterly", "currency": "USD"}
        data = fd_module.FinancialDatasetsClient._envelope({dataset: [item]}, "AAPL", "quarterly", limit)
        assert backend.set_financial_cache(f"fd_v1_{prefix}_AAPL_quarterly_{limit}", "AAPL", data,
            source="financial_datasets", fetched_at=fetched.isoformat(), expires_at=expires.isoformat())
    dal = SimpleNamespace(_backend=backend, get_user_profile=lambda: {
        "data_preferences": {"paid_sources": {"financial_datasets": {"enabled": True}}}})
    arguments = {"ticker": "AAPL", "period": "quarterly"}
    if freshness is not None:
        arguments.update(freshness=freshness, max_age_seconds=30 * 86400)
    result = unwrap(asyncio.run(invoke(channel, "get_fundamentals_analysis", arguments, dal)))
    assert result["data_source"] == "financial_datasets", result
    assert result["income_statements"][0]["period_type"] == "quarterly"
    assert len(result["source_observations"]) == 3
    for observed in result["source_observations"]:
        assert observed["fetched_at"] == fetched.isoformat()
        assert observed["freshness_mode"] == (freshness or "auto") and observed["retrieval"] == "stored"
        assert observed["within_max_age"] is True
        assert "latest_period_verified" not in observed
    assert result["acquisition_gaps"] == []
    http.assert_not_called()
    sec.assert_not_called()


def test_all_schema_exporters_offer_freshness_options():
    from src.tools.registry import create_default_registry
    from src.agents.anthropic_agent.tools import get_anthropic_tools
    from src.agents.openai_agent.tools import create_openai_tools

    registry = create_default_registry()
    for name, required in (
        ("get_current_quote", {"max_age_seconds"}),
        ("get_fundamentals_analysis", {"period", "freshness", "max_age_seconds"}),
        ("get_detailed_financials", {"freshness", "max_age_seconds"}),
    ):
        assert required <= {p.name for p in registry.get(name).parameters}
        native_anthropic = next(t for t in get_anthropic_tools() if t["name"] == name)
        assert required <= set(native_anthropic["input_schema"]["properties"])
        native_openai = next(t for t in create_openai_tools(object()) if t.name == "tool_" + name)
        assert required <= set(native_openai.params_json_schema["properties"])


@pytest.mark.parametrize("age", [True, "60"])
@pytest.mark.parametrize("channel,name", [
    (channel, name)
    for channel in ("openai", "anthropic", "chatgpt", "claude")
    for name in ("get_current_quote", "get_fundamentals_analysis", "get_detailed_financials")
    if name != "get_detailed_financials" or channel in ("openai", "anthropic")
])
def test_invalid_age_is_not_coerced_into_acquisition_authority(channel, age, name, monkeypatch):
    from src.tools import current_quote
    from src.tools import analysis_tools

    acquire_quote = Mock(side_effect=AssertionError("invalid age must not request a quote"))
    read_fundamentals = Mock(side_effect=AssertionError("invalid age must not start data access"))
    monkeypatch.setattr(current_quote, "_fetch_ibkr_quote", acquire_quote)
    monkeypatch.setattr(analysis_tools, "read_entry", read_fundamentals)
    monkeypatch.setattr(analysis_tools, "cached_dataset", read_fundamentals)
    arguments = {"ticker": "AAPL"}
    if name == "get_current_quote":
        arguments.update(source="ibkr", max_age_seconds=age)
    else:
        arguments.update(freshness="auto", max_age_seconds=age)
    result = asyncio.run(invoke(channel, name, arguments, object()))
    assert result
    acquire_quote.assert_not_called()
    read_fundamentals.assert_not_called()


@pytest.mark.parametrize("channel", ["openai", "anthropic"])
def test_retired_fd_only_arguments_cannot_silently_enable_auto_acquisition(channel, monkeypatch):
    from src.tools import analysis_tools

    access = Mock(side_effect=AssertionError("an obsolete stored flag must not turn into default auto"))
    monkeypatch.setattr(analysis_tools, "read_entry", access)
    result = asyncio.run(invoke(channel, "get_fundamentals_analysis", {
        "ticker": "AAPL", "fd_freshness": "stored",
    }, object()))
    assert result
    access.assert_not_called()


def test_detailed_financials_remains_outside_oauth_allowlists():
    from src.auth_drivers.claude_code_sdk_driver import _RESEARCH_READONLY_TOOLS as claude
    from src.auth_drivers.chatgpt_oauth_driver import _RESEARCH_READONLY_TOOLS as chatgpt

    assert "get_detailed_financials" not in claude
    assert "get_detailed_financials" not in chatgpt
