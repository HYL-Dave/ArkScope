"""Real calculator dispatch through both offline OAuth tool boundaries."""

import asyncio
import inspect
import json
from types import SimpleNamespace

import pytest

from tests.test_financial_calculation_tools import TOOL_NAMES, offline_calculators


@pytest.fixture
def registry():
    from src.tools.registry import create_default_registry

    return create_default_registry()


@pytest.fixture(params=["chatgpt", "claude"])
def oauth(request, registry):
    if request.param == "chatgpt":
        from src.auth_drivers.chatgpt_oauth_driver import OpenAIChatGPTOAuthDriver

        driver = OpenAIChatGPTOAuthDriver(registry=registry, dal=object(), per_tool_timeout_s=5)
        tools = driver._build_tools()
        schemas = {t["name"]: t["parameters"] for t in tools}
        assert all(t["strict"] is False for t in tools if t["name"] in TOOL_NAMES)

        async def invoke(name, arguments):
            return await driver._invoke_tool(name=name, args=arguments, token=None)
    else:
        from src.auth_drivers.claude_code_sdk_driver import build_ark_mcp_server

        _, tools = build_ark_mcp_server(
            registry=registry, dal=object(), token=None, per_tool_timeout_s=5,
        )
        schemas = {t.name: t.input_schema for t in tools}
        handlers = {t.name: t.handler for t in tools}

        async def invoke(name, arguments):
            assert name in handlers, f"Claude OAuth inventory is missing {name}"
            result = await handlers[name](arguments)
            return not result["is_error"], result["content"][0]["text"]

    return SimpleNamespace(schemas=schemas, invoke=invoke)


def test_oauth_calculator_schemas_keep_optional_arguments_optional(oauth, registry):
    assert TOOL_NAMES <= oauth.schemas.keys()
    for name in TOOL_NAMES:
        parameters = inspect.signature(registry.get(name).function).parameters
        schema = oauth.schemas[name]
        assert set(schema["properties"]) == set(parameters)
        assert set(schema["required"]) == {
            name for name, p in parameters.items() if p.default is inspect.Parameter.empty
        }
    assert oauth.schemas["calculate_implied_valuation"]["properties"]["value_basis"]["enum"] == [
        "enterprise_value", "equity_value",
    ]


@pytest.mark.parametrize("name,arguments,expected", [
    (
        "calculate_compound_growth",
        {"start_value": 100, "end_value": 121, "periods": 2},
        {"start_value": 100, "end_value": 121, "periods": 2,
         "total_change": 0.21, "compound_growth_rate": 0.1},
    ),
    (
        "calculate_dcf",
        {"free_cash_flows": [110, 121], "discount_rate": 0.1, "terminal_growth_rate": 0.02,
         "cash": 50, "total_debt": 25, "shares_outstanding": 10, "current_price": 120},
        {"inputs": {"free_cash_flows": [110, 121], "discount_rate": 0.1,
                    "terminal_growth_rate": 0.02, "cash": 50, "total_debt": 25,
                    "shares_outstanding": 10, "current_price": 120},
         "enterprise_value": 1475, "equity_value": 1500,
         "per_share_value": 150, "upside_downside": 0.25},
    ),
    (
        "calculate_peer_statistics",
        {"values": [8, 10, 12], "target_value": 12},
        {"values": [8, 10, 12], "count": 3, "mean": 10, "median": 10,
         "target_value": 12, "target_premium_to_median": 0.2},
    ),
    (
        "calculate_implied_valuation",
        {"target_metric": 100, "multiples": [8, 10, 12], "value_basis": "enterprise_value",
         "cash": 50, "total_debt": 20, "shares_outstanding": 10, "current_price": 100},
        {"inputs": {"target_metric": 100, "multiples": [8, 10, 12],
                    "value_basis": "enterprise_value", "cash": 50, "total_debt": 20,
                    "shares_outstanding": 10, "current_price": 100},
         "valuations": [
             {"multiple": 8, "enterprise_value": 800, "equity_value": 830,
              "per_share_value": 83, "upside_downside": -0.17},
             {"multiple": 10, "enterprise_value": 1000, "equity_value": 1030,
              "per_share_value": 103, "upside_downside": 0.03},
             {"multiple": 12, "enterprise_value": 1200, "equity_value": 1230,
              "per_share_value": 123, "upside_downside": 0.23},
         ]},
    ),
    (
        "calculate_implied_valuation",
        {"target_metric": 100, "multiples": [10], "value_basis": "equity_value",
         "cash": 50, "total_debt": 20, "shares_outstanding": 10, "current_price": 80},
        {"valuations": [
            {"multiple": 10, "enterprise_value": None, "equity_value": 1000,
             "per_share_value": 100, "upside_downside": 0.25},
        ]},
    ),
    (
        "calculate_weighted_scenarios",
        {"values": [80, 100, 140], "weights": [0.25, 0.5, 0.25],
         "labels": ["bear", "base", "bull"], "current_price": 100},
        {"weighted_value": 105, "current_price": 100, "upside_downside": 0.05,
         "scenarios": [
             {"label": "bear", "value": 80, "weight": 0.25, "contribution": 20},
             {"label": "base", "value": 100, "weight": 0.5, "contribution": 50},
             {"label": "bull", "value": 140, "weight": 0.25, "contribution": 35},
         ]},
    ),
    (
        "calculate_dcf",
        {"free_cash_flows": [110, 121], "discount_rate": 0.1, "terminal_growth_rate": 0.02},
        {"inputs": {"free_cash_flows": [110, 121], "discount_rate": 0.1,
                    "terminal_growth_rate": 0.02, "cash": 0, "total_debt": 0,
                    "shares_outstanding": None, "current_price": None},
         "enterprise_value": 1475, "equity_value": 1475,
         "per_share_value": None, "upside_downside": None},
    ),
    (
        "calculate_peer_statistics",
        {"values": [8, 10, 12]},
        {"median": 10, "target_value": None, "target_premium_to_median": None},
    ),
    (
        "calculate_implied_valuation",
        {"target_metric": 100, "multiples": [10], "value_basis": "enterprise_value"},
        {"inputs": {"target_metric": 100, "multiples": [10],
                    "value_basis": "enterprise_value", "cash": 0, "total_debt": 0,
                    "shares_outstanding": None, "current_price": None},
         "valuations": [
             {"multiple": 10, "enterprise_value": 1000, "equity_value": 1000,
              "per_share_value": None, "upside_downside": None},
         ]},
    ),
    (
        "calculate_weighted_scenarios",
        {"values": [80, 120], "weights": [0.5, 0.5]},
        {"weighted_value": 100, "current_price": None, "upside_downside": None,
         "scenarios": [
             {"label": "scenario_1", "value": 80, "weight": 0.5, "contribution": 40},
             {"label": "scenario_2", "value": 120, "weight": 0.5, "contribution": 60},
         ]},
    ),
])
def test_oauth_dispatches_real_calculators_without_data_access(oauth, name, arguments, expected):
    ok, payload = asyncio.run(oauth.invoke(name, arguments))
    assert ok, payload
    result = json.loads(payload)
    assert {key: result[key] for key in expected} == expected
    assert result["formula"]


@pytest.mark.parametrize("name,arguments,field", [
    ("calculate_compound_growth", {"start_value": 0, "end_value": 1, "periods": 1},
     "compound_growth_domain"),
    ("calculate_compound_growth", {"start_value": True, "end_value": 1, "periods": 1},
     "start_value"),
    ("calculate_compound_growth", {"start_value": "100", "end_value": 121, "periods": 2},
     "start_value"),
    ("calculate_dcf", {"free_cash_flows": [1], "discount_rate": 0.02,
                       "terminal_growth_rate": 0.02}, "discount_terminal_rates"),
    ("calculate_dcf", {"free_cash_flows": [], "discount_rate": 0.1,
                       "terminal_growth_rate": 0.02}, "free_cash_flows"),
    ("calculate_dcf", {"free_cash_flows": ["110"], "discount_rate": 0.1,
                       "terminal_growth_rate": 0.02}, "free_cash_flows"),
    ("calculate_dcf", {"free_cash_flows": [1], "discount_rate": 0.1,
                       "terminal_growth_rate": 0.02, "shares_outstanding": 0},
     "shares_outstanding"),
    ("calculate_peer_statistics", {"values": []}, "values"),
    ("calculate_peer_statistics", {"values": [True]}, "values"),
    ("calculate_peer_statistics", {"values": "10,12"}, "values"),
    ("calculate_peer_statistics", {"values": [1], "target_value": "2"}, "target_value"),
    ("calculate_implied_valuation", {"target_metric": 100, "multiples": [10],
                                     "value_basis": "unknown"}, "value_basis"),
    ("calculate_implied_valuation", {"target_metric": 100, "multiples": [-10],
                                     "value_basis": "enterprise_value"}, "multiples"),
    ("calculate_weighted_scenarios", {"values": [1, 2], "weights": [0.5, 0.4]},
     "weights_sum"),
    ("calculate_weighted_scenarios", {"values": [1, 2], "weights": [1]},
     "scenario_lengths"),
    ("calculate_weighted_scenarios", {"values": [1], "weights": [1], "labels": [1]},
     "labels"),
    ("calculate_weighted_scenarios", {"values": [1], "weights": [True]}, "weights"),
    ("calculate_weighted_scenarios", {"values": [1], "weights": [1], "current_price": 0},
     "current_price"),
])
def test_oauth_rejects_invalid_calculator_inputs(oauth, name, arguments, field):
    ok, payload = asyncio.run(oauth.invoke(name, arguments))
    assert not ok
    assert f"financial_input_invalid:{field}" in payload


@pytest.mark.parametrize("name", sorted(TOOL_NAMES))
def test_oauth_rejects_missing_calculator_arguments(oauth, name):
    ok, payload = asyncio.run(oauth.invoke(name, {}))
    assert not ok
    assert "required positional argument" in payload


def test_oauth_rejects_unknown_calculator_arguments(oauth):
    ok, payload = asyncio.run(oauth.invoke("calculate_compound_growth", {
        "start_value": 100, "end_value": 121, "periods": 2, "ticker": "AAPL",
    }))
    assert not ok
    assert "unexpected keyword argument" in payload


@pytest.mark.parametrize("channel", ["chatgpt", "claude"])
@pytest.mark.parametrize("name", [
    "save_report", "save_memory", "web_browse", "get_detailed_financials", "calculate_greeks",
])
def test_oauth_calculator_exposure_does_not_admit_other_tools(channel, name, registry):
    from src.auth_drivers.chatgpt_oauth_driver import OpenAIChatGPTOAuthDriver
    from src.auth_drivers.claude_code_sdk_driver import _invoke_bridged_tool

    if channel == "chatgpt":
        driver = OpenAIChatGPTOAuthDriver(registry=registry, dal=object())
        ok, payload = asyncio.run(driver._invoke_tool(name=name, args={}, token=None))
    else:
        result = asyncio.run(_invoke_bridged_tool(
            name=name, args={}, registry=registry, dal=object(), token=None, per_tool_timeout_s=5,
        ))
        ok, payload = not result["is_error"], result["content"][0]["text"]
    assert not ok
    assert "allowlist veto" in payload
