"""Pure, auditable financial calculations for agent workflows."""

from __future__ import annotations

import math
import statistics
from typing import Any, Iterable


_MAX_SERIES_VALUES = 128
_MAX_DCF_PERIODS = 50


def _invalid(field: str) -> ValueError:
    return ValueError(f"financial_input_invalid:{field}")


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _invalid(field)
    result = float(value)
    if not math.isfinite(result):
        raise _invalid(field)
    return result


def _series(
    values: Iterable[Any],
    field: str,
    *,
    maximum: int = _MAX_SERIES_VALUES,
    positive: bool = False,
    nonnegative: bool = False,
) -> list[float]:
    if isinstance(values, (str, bytes, dict)):
        raise _invalid(field)
    try:
        result = [_number(value, field) for value in values]
    except TypeError:
        raise _invalid(field) from None
    if not result or len(result) > maximum:
        raise _invalid(field)
    if positive and any(value <= 0 for value in result):
        raise _invalid(field)
    if nonnegative and any(value < 0 for value in result):
        raise _invalid(field)
    return result


def _nonnegative(value: Any, field: str) -> float:
    result = _number(value, field)
    if result < 0:
        raise _invalid(field)
    return result


def _optional_positive(value: Any, field: str) -> float | None:
    if value is None:
        return None
    result = _number(value, field)
    if result <= 0:
        raise _invalid(field)
    return result


def _rounded(value: float | None) -> float | None:
    if value is None:
        return None
    result = round(float(value), 10)
    return 0.0 if result == 0 else result


def calculate_compound_growth(
    start_value: float,
    end_value: float,
    periods: float,
) -> dict[str, Any]:
    """Calculate total change and CAGR for positive comparable values."""
    start = _number(start_value, "start_value")
    end = _number(end_value, "end_value")
    count = _number(periods, "periods")
    if start <= 0 or end <= 0 or count <= 0:
        raise _invalid("compound_growth_domain")
    return {
        "start_value": start,
        "end_value": end,
        "periods": count,
        "total_change": _rounded(end / start - 1),
        "compound_growth_rate": _rounded((end / start) ** (1 / count) - 1),
        "formula": {
            "total_change": "end_value / start_value - 1",
            "compound_growth_rate": (
                "(end_value / start_value) ** (1 / periods) - 1"
            ),
        },
    }


def calculate_dcf(
    free_cash_flows: list[float],
    discount_rate: float,
    terminal_growth_rate: float,
    cash: float = 0.0,
    total_debt: float = 0.0,
    shares_outstanding: float | None = None,
    current_price: float | None = None,
) -> dict[str, Any]:
    """Discount explicit FCF projections and bridge enterprise to equity value."""
    cash_flows = _series(
        free_cash_flows,
        "free_cash_flows",
        maximum=_MAX_DCF_PERIODS,
    )
    rate = _number(discount_rate, "discount_rate")
    growth = _number(terminal_growth_rate, "terminal_growth_rate")
    cash_value = _nonnegative(cash, "cash")
    debt_value = _nonnegative(total_debt, "total_debt")
    shares = _optional_positive(shares_outstanding, "shares_outstanding")
    price = _optional_positive(current_price, "current_price")
    if rate <= 0 or growth <= -1 or rate <= growth:
        raise _invalid("discount_terminal_rates")

    projection = []
    present_values = []
    for period, free_cash_flow in enumerate(cash_flows, start=1):
        discount_factor = (1 + rate) ** period
        present_value = free_cash_flow / discount_factor
        present_values.append(present_value)
        projection.append(
            {
                "period": period,
                "free_cash_flow": free_cash_flow,
                "discount_factor": _rounded(discount_factor),
                "present_value": _rounded(present_value),
            }
        )

    terminal_value = cash_flows[-1] * (1 + growth) / (rate - growth)
    pv_terminal = terminal_value / ((1 + rate) ** len(cash_flows))
    pv_projected = sum(present_values)
    enterprise_value = pv_projected + pv_terminal
    equity_value = enterprise_value + cash_value - debt_value
    per_share = equity_value / shares if shares is not None else None
    upside = per_share / price - 1 if per_share is not None and price is not None else None
    terminal_share = (
        pv_terminal / enterprise_value if enterprise_value != 0 else None
    )

    return {
        "inputs": {
            "free_cash_flows": cash_flows,
            "discount_rate": rate,
            "terminal_growth_rate": growth,
            "cash": cash_value,
            "total_debt": debt_value,
            "shares_outstanding": shares,
            "current_price": price,
        },
        "projection": projection,
        "pv_projected_cash_flows": _rounded(pv_projected),
        "terminal_value": _rounded(terminal_value),
        "pv_terminal_value": _rounded(pv_terminal),
        "terminal_value_share_of_enterprise": _rounded(terminal_share),
        "enterprise_value": _rounded(enterprise_value),
        "equity_value": _rounded(equity_value),
        "per_share_value": _rounded(per_share),
        "upside_downside": _rounded(upside),
        "formula": {
            "projected_present_value": "fcf_t / (1 + discount_rate) ** t",
            "terminal_value": (
                "final_fcf * (1 + terminal_growth_rate) / "
                "(discount_rate - terminal_growth_rate)"
            ),
            "equity_value": "enterprise_value + cash - total_debt",
            "per_share_value": "equity_value / shares_outstanding",
        },
    }


def calculate_peer_statistics(
    values: list[float],
    target_value: float | None = None,
) -> dict[str, Any]:
    """Summarize a peer metric and flag absolute population z-scores above two."""
    series = _series(values, "values")
    target = None if target_value is None else _number(target_value, "target_value")
    mean_value = statistics.fmean(series)
    median_value = statistics.median(series)
    population_std = statistics.pstdev(series)
    sample_std = statistics.stdev(series) if len(series) > 1 else None
    if len(series) > 1:
        first_quartile, _, third_quartile = statistics.quantiles(
            series,
            n=4,
            method="inclusive",
        )
    else:
        first_quartile = third_quartile = series[0]
    outliers = []
    if population_std > 0:
        for index, value in enumerate(series):
            z_score = (value - mean_value) / population_std
            if abs(z_score) > 2:
                outliers.append(
                    {
                        "index": index,
                        "value": value,
                        "z_score": _rounded(z_score),
                    }
                )
    premium = (
        target / median_value - 1
        if target is not None and median_value != 0
        else None
    )
    return {
        "values": series,
        "count": len(series),
        "mean": _rounded(mean_value),
        "median": _rounded(median_value),
        "minimum": min(series),
        "maximum": max(series),
        "first_quartile": _rounded(first_quartile),
        "third_quartile": _rounded(third_quartile),
        "population_standard_deviation": _rounded(population_std),
        "sample_standard_deviation": _rounded(sample_std),
        "target_value": target,
        "target_premium_to_median": _rounded(premium),
        "outliers": outliers,
        "outlier_method": "absolute population z-score > 2",
        "formula": {
            "target_premium_to_median": "target_value / median - 1",
            "z_score": "(value - mean) / population_standard_deviation",
        },
    }


def calculate_implied_valuation(
    target_metric: float,
    multiples: list[float],
    value_basis: str,
    cash: float = 0.0,
    total_debt: float = 0.0,
    shares_outstanding: float | None = None,
    current_price: float | None = None,
) -> dict[str, Any]:
    """Apply explicit peer multiples without conflating EV and equity bases."""
    metric = _number(target_metric, "target_metric")
    multiple_values = _series(multiples, "multiples", positive=True)
    if metric <= 0:
        raise _invalid("target_metric")
    if value_basis not in {"enterprise_value", "equity_value"}:
        raise _invalid("value_basis")
    cash_value = _nonnegative(cash, "cash")
    debt_value = _nonnegative(total_debt, "total_debt")
    shares = _optional_positive(shares_outstanding, "shares_outstanding")
    price = _optional_positive(current_price, "current_price")

    valuations = []
    for multiple in multiple_values:
        implied_value = metric * multiple
        if value_basis == "enterprise_value":
            enterprise_value: float | None = implied_value
            equity_value = implied_value + cash_value - debt_value
        else:
            enterprise_value = None
            equity_value = implied_value
        per_share = equity_value / shares if shares is not None else None
        upside = per_share / price - 1 if per_share is not None and price is not None else None
        valuations.append(
            {
                "multiple": multiple,
                "enterprise_value": _rounded(enterprise_value),
                "equity_value": _rounded(equity_value),
                "per_share_value": _rounded(per_share),
                "upside_downside": _rounded(upside),
            }
        )

    return {
        "inputs": {
            "target_metric": metric,
            "multiples": multiple_values,
            "value_basis": value_basis,
            "cash": cash_value,
            "total_debt": debt_value,
            "shares_outstanding": shares,
            "current_price": price,
        },
        "valuations": valuations,
        "formula": {
            "implied_value": "target_metric * multiple",
            "enterprise_to_equity": "enterprise_value + cash - total_debt",
            "per_share_value": "equity_value / shares_outstanding",
        },
    }


def calculate_weighted_scenarios(
    values: list[float],
    weights: list[float],
    labels: list[str] | None = None,
    current_price: float | None = None,
) -> dict[str, Any]:
    """Calculate a probability-weighted value from explicit scenario inputs."""
    scenario_values = _series(values, "values")
    scenario_weights = _series(weights, "weights", nonnegative=True)
    if len(scenario_values) != len(scenario_weights):
        raise _invalid("scenario_lengths")
    weight_sum = sum(scenario_weights)
    if not math.isclose(weight_sum, 1.0, rel_tol=0.0, abs_tol=1e-8):
        raise _invalid("weights_sum")
    if labels is None:
        scenario_labels = [f"scenario_{index}" for index in range(1, len(values) + 1)]
    else:
        if (
            not isinstance(labels, list)
            or len(labels) != len(scenario_values)
            or any(
                not isinstance(label, str)
                or not label.strip()
                or len(label.strip()) > 80
                for label in labels
            )
        ):
            raise _invalid("labels")
        scenario_labels = [label.strip() for label in labels]
    price = _optional_positive(current_price, "current_price")

    scenarios = []
    weighted_value = 0.0
    for label, value, weight in zip(
        scenario_labels,
        scenario_values,
        scenario_weights,
    ):
        contribution = value * weight
        weighted_value += contribution
        scenarios.append(
            {
                "label": label,
                "value": value,
                "weight": weight,
                "contribution": _rounded(contribution),
            }
        )
    upside = weighted_value / price - 1 if price is not None else None
    return {
        "scenarios": scenarios,
        "weight_sum": _rounded(weight_sum),
        "weighted_value": _rounded(weighted_value),
        "minimum_value": min(scenario_values),
        "maximum_value": max(scenario_values),
        "current_price": price,
        "upside_downside": _rounded(upside),
        "formula": {
            "weighted_value": "sum(value * weight for each scenario)",
            "upside_downside": "weighted_value / current_price - 1",
        },
    }
