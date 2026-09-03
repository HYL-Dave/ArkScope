from __future__ import annotations

import asyncio
import json
import math
import re
from unittest.mock import MagicMock

import pytest


TOOL_NAMES = {
    "calculate_compound_growth",
    "calculate_dcf",
    "calculate_implied_valuation",
    "calculate_peer_statistics",
    "calculate_weighted_scenarios",
}


def _unwrap(result: str) -> str:
    match = re.search(r"<tool_output[^>]*>\n(.*)\n</tool_output>", result, re.DOTALL)
    return match.group(1) if match else result


def test_compound_growth_returns_auditable_inputs_and_rates():
    from src.tools.financial_calculation_tools import calculate_compound_growth

    result = calculate_compound_growth(100.0, 121.0, 2.0)

    assert result == {
        "start_value": 100.0,
        "end_value": 121.0,
        "periods": 2.0,
        "total_change": 0.21,
        "compound_growth_rate": 0.1,
        "formula": {
            "total_change": "end_value / start_value - 1",
            "compound_growth_rate": "(end_value / start_value) ** (1 / periods) - 1",
        },
    }


def test_dcf_returns_projection_terminal_and_equity_bridge():
    from src.tools.financial_calculation_tools import calculate_dcf

    result = calculate_dcf(
        free_cash_flows=[110.0, 121.0],
        discount_rate=0.10,
        terminal_growth_rate=0.02,
        cash=50.0,
        total_debt=25.0,
        shares_outstanding=10.0,
        current_price=120.0,
    )

    assert result["inputs"]["free_cash_flows"] == [110.0, 121.0]
    assert result["pv_projected_cash_flows"] == pytest.approx(200.0)
    assert result["terminal_value"] == pytest.approx(1542.75)
    assert result["pv_terminal_value"] == pytest.approx(1275.0)
    assert result["enterprise_value"] == pytest.approx(1475.0)
    assert result["equity_value"] == pytest.approx(1500.0)
    assert result["per_share_value"] == pytest.approx(150.0)
    assert result["upside_downside"] == pytest.approx(0.25)
    assert result["formula"]["terminal_value"].startswith("final_fcf")


def test_peer_statistics_are_deterministic_and_flag_extreme_values():
    from src.tools.financial_calculation_tools import calculate_peer_statistics

    values = [10.0] * 9 + [100.0]
    result = calculate_peer_statistics(values, target_value=12.0)

    assert result["count"] == 10
    assert result["mean"] == pytest.approx(19.0)
    assert result["median"] == pytest.approx(10.0)
    assert result["minimum"] == 10.0
    assert result["maximum"] == 100.0
    assert result["target_premium_to_median"] == pytest.approx(0.2)
    assert result["outliers"] == [
        {"index": 9, "value": 100.0, "z_score": pytest.approx(3.0)},
    ]
    assert result["outlier_method"] == "absolute population z-score > 2"


def test_implied_valuation_keeps_enterprise_and_equity_values_distinct():
    from src.tools.financial_calculation_tools import calculate_implied_valuation

    result = calculate_implied_valuation(
        target_metric=100.0,
        multiples=[8.0, 10.0, 12.0],
        value_basis="enterprise_value",
        cash=50.0,
        total_debt=20.0,
        shares_outstanding=10.0,
        current_price=100.0,
    )

    assert [row["enterprise_value"] for row in result["valuations"]] == [
        800.0, 1000.0, 1200.0,
    ]
    assert [row["equity_value"] for row in result["valuations"]] == [
        830.0, 1030.0, 1230.0,
    ]
    assert [row["per_share_value"] for row in result["valuations"]] == [
        83.0, 103.0, 123.0,
    ]
    assert [row["upside_downside"] for row in result["valuations"]] == pytest.approx(
        [-0.17, 0.03, 0.23]
    )


def test_weighted_scenarios_require_explicit_probabilities():
    from src.tools.financial_calculation_tools import calculate_weighted_scenarios

    result = calculate_weighted_scenarios(
        values=[80.0, 100.0, 140.0],
        weights=[0.25, 0.5, 0.25],
        labels=["bear", "base", "bull"],
        current_price=100.0,
    )

    assert result["weighted_value"] == pytest.approx(105.0)
    assert result["upside_downside"] == pytest.approx(0.05)
    assert result["scenarios"] == [
        {"label": "bear", "value": 80.0, "weight": 0.25, "contribution": 20.0},
        {"label": "base", "value": 100.0, "weight": 0.5, "contribution": 50.0},
        {"label": "bull", "value": 140.0, "weight": 0.25, "contribution": 35.0},
    ]


@pytest.mark.parametrize(
    ("function_name", "kwargs"),
    [
        ("calculate_compound_growth", {"start_value": 0, "end_value": 1, "periods": 1}),
        (
            "calculate_dcf",
            {
                "free_cash_flows": [1.0],
                "discount_rate": 0.02,
                "terminal_growth_rate": 0.02,
            },
        ),
        ("calculate_peer_statistics", {"values": [math.nan]}),
        (
            "calculate_implied_valuation",
            {"target_metric": 1, "multiples": [10], "value_basis": "unknown"},
        ),
        (
            "calculate_weighted_scenarios",
            {"values": [1, 2], "weights": [0.5, 0.4]},
        ),
    ],
)
def test_invalid_financial_inputs_fail_loudly(function_name, kwargs):
    from src.tools import financial_calculation_tools as calculators

    with pytest.raises(ValueError, match="financial_input_invalid"):
        getattr(calculators, function_name)(**kwargs)


def test_all_agent_surfaces_expose_the_same_financial_calculators():
    from src.agents.anthropic_agent.tools import get_anthropic_tools
    from src.agents.openai_agent.tools import create_openai_tools
    from src.tools.registry import create_default_registry

    registry = create_default_registry()
    assert TOOL_NAMES <= set(registry.list_names())
    assert all(registry.get(name).requires_dal is False for name in TOOL_NAMES)
    assert TOOL_NAMES <= {tool["name"] for tool in get_anthropic_tools()}
    assert {f"tool_{name}" for name in TOOL_NAMES} <= {
        tool.name for tool in create_openai_tools(MagicMock())
    }


def test_anthropic_dispatch_crosses_the_real_calculator_boundary():
    from src.agents.anthropic_agent.tools import execute_tool

    result = json.loads(
        _unwrap(execute_tool(
            "calculate_weighted_scenarios",
            {
                "values": [80, 100, 140],
                "weights": [0.25, 0.5, 0.25],
                "labels": ["bear", "base", "bull"],
            },
            MagicMock(),
        ))
    )
    assert result["weighted_value"] == 105.0


def test_openai_dispatch_crosses_the_real_calculator_boundary():
    from src.agents.openai_agent.tools import create_openai_tools

    tool = next(
        candidate
        for candidate in create_openai_tools(MagicMock())
        if candidate.name == "tool_calculate_weighted_scenarios"
    )
    raw_result = asyncio.run(
        tool.on_invoke_tool(
            MagicMock(),
            json.dumps(
                {
                    "values": [80, 100, 140],
                    "weights": [0.25, 0.5, 0.25],
                    "labels": ["bear", "base", "bull"],
                    "current_price": None,
                }
            ),
        )
    )

    assert json.loads(_unwrap(raw_result))["weighted_value"] == 105.0
