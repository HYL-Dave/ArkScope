"""Supported same-source arithmetic with precision and missing-input evidence."""

from datetime import date
from decimal import localcontext
import math
import re

from src.fundamentals.contracts import FinancialGap, Provider
from src.fundamentals.metric_basis import METRIC_FIELDS, derive_metrics
from src.fundamentals.source_comparison import decimal
from src.tools.schemas import FinancialStatement


_VALUATION_INPUTS = {
    "market_cap": ("qualified_price", "outstanding_shares"),
    "pe_ratio": ("qualified_price", "trailing_earnings_per_share"),
    "forward_pe": ("qualified_price", "forward_earnings_per_share"),
    "ps_ratio": ("market_cap", "trailing_revenue"),
    "pb_ratio": ("market_cap", "shareholders_equity"),
    "dividend_yield": ("qualified_price", "annual_dividend_per_share"),
    "beta": ("comparable_price_history", "benchmark_history"),
}
_RATIOS = {
    "gross_margin": ("gross_profit", "revenue"),
    "operating_margin": ("operating_income", "revenue"),
    "net_margin": ("net_income", "revenue"),
    "current_ratio": ("current_assets", "current_liabilities"),
}
_REQUIRED = {**_RATIOS, **_VALUATION_INPUTS,
    "total_debt": ("interest_bearing_debt",),
    "debt_to_equity": ("interest_bearing_debt", "shareholders_equity"),
    "cash_and_equivalents": ("cash_and_equivalents",),
    "free_cash_flow": ("free_cash_flow",),
    "revenue_growth": ("revenue", "comparable_previous_period", "exact_period_identity"),
    "earnings_growth": ("net_income", "comparable_previous_period", "exact_period_identity"),
    "roa": ("annual_net_income", "total_assets", "exact_period_identity"),
    "roe": ("annual_net_income", "shareholders_equity", "exact_period_identity"),
}
_BALANCE_METRICS = {"current_ratio", "total_debt", "cash_and_equivalents", "debt_to_equity"}


def _currency(row):
    return row.currency if row and isinstance(row.currency, str) and re.fullmatch(r"[A-Z]{3}", row.currency) else None


def _reference(row):
    return dict(provider=row.provider, observation_id=row.observation_id, end_month=row.end_month,
                report_period=row.report_period, period=row.period_type, currency=row.currency,
                column_index=row.column_index)


def _sa_ratio(row, numerator, denominator):
    if row is None:
        return None, "inputs_unavailable"
    if not _currency(row):
        return None, "currency_unknown"
    if (row.provider != "seeking_alpha" or row.period_precision != "month"
            or not row.observation_id or type(row.column_index) is not int
            or row.column_index < 0 or not row.end_month or row.report_period is not None):
        return None, "same_column_required"
    operands = []
    for key in (numerator, denominator):
        cell = row.value_metadata.get(key)
        if cell is None:
            return None, "inputs_unavailable"
        if cell.status != "value":
            return None, cell.status
        if cell.currency != row.currency:
            return None, "currency_mismatch"
        value = decimal(cell.normalized_value)
        if (cell.precision != "provider_display_rounded" or cell.unit != row.currency
                or value is None or value != decimal(row.data.get(key))):
            return None, "same_column_required"
        operands.append(value)
    n, d = operands
    if d <= 0:
        return None, "positive_denominator_required"
    with localcontext() as context:
        context.prec = max(50, len(n.as_tuple().digits) + len(d.as_tuple().digits) + 16)
        value = float(n / d)
    return (round(value, 4), None) if math.isfinite(value) else (None, "inputs_unavailable")


def _fd_rows(rows):
    if not rows:
        return [], "inputs_unavailable"
    if not _currency(rows[0]):
        return [], "currency_unknown"
    qualified = []
    for row in rows:
        try:
            exact = bool(row.report_period and date.fromisoformat(row.report_period).isoformat() == row.report_period)
        except (TypeError, ValueError):
            exact = False
        if (row.provider == "financial_datasets" and row.period_precision == "day"
                and exact and _currency(row)):
            qualified.append(row)
        elif not qualified:
            return [], "exact_period_identity_unavailable"
    return qualified, None


def derive_common_metrics(income: list[FinancialStatement], balance: list[FinancialStatement],
                          cashflow: list[FinancialStatement], *, source: Provider) -> dict:
    if source not in {"seeking_alpha", "financial_datasets"}:
        raise ValueError("unsupported financial source")
    values = {key: None for key in (*METRIC_FIELDS, *_VALUATION_INPUTS)}
    basis, gaps = {}, {}
    groups = {"income": income, "balance": balance, "cashflow": cashflow}
    if source == "seeking_alpha":
        gaps.update({key: "mapping_not_reviewed" for key in METRIC_FIELDS})
        gaps.update({key: "exact_period_identity_unavailable"
                     for key in ("revenue_growth", "earnings_growth", "roe", "roa")})
        for key, (numerator, denominator) in _RATIOS.items():
            rows = balance if key == "current_ratio" else income
            row = rows[0] if rows else None
            value, gap = _sa_ratio(row, numerator, denominator)
            values[key] = value
            if gap:
                gaps[key] = gap
            else:
                gaps.pop(key, None)
                basis[key] = {**_reference(row), "precision": "provider_display_rounded",
                              "numerator": numerator, "denominator": denominator}
    else:
        qualified, blocked = {}, {}
        for name, rows in groups.items():
            qualified[name], blocked[name] = _fd_rows(rows)
        derived = derive_metrics(qualified["income"], qualified["balance"], qualified["cashflow"], source=source)
        values.update({key: derived[key] for key in METRIC_FIELDS})
        gaps.update(derived["metric_gaps"])
        for key in METRIC_FIELDS:
            group = "balance" if key in _BALANCE_METRICS else "cashflow" if key == "free_cash_flow" else "income"
            if blocked[group]:
                values[key] = None
                gaps[key] = blocked[group]
                continue
            if key in derived["metric_basis"]:
                row = qualified[group][0]
                basis[key] = {**derived["metric_basis"][key], **_reference(row), "precision": "provider_numeric_float"}
                required = ("income", "balance") if key in {"roe", "roa"} else (group,)
                basis[key]["input_observations"] = [
                    _reference(item) for name in required for item in qualified[name]
                    if item.report_period in {basis[key].get("report_period"), basis[key].get("previous_report_period")}
                ]
    gaps.update({key: "inputs_unavailable" for key in _VALUATION_INPUTS})
    input_gaps = [FinancialGap(provider=source, code=code, metric=key, required_inputs=list(_REQUIRED[key]))
                  for key, code in gaps.items()]
    return {**values, "metric_basis": basis, "metric_gaps": gaps, "input_gaps": input_gaps,
            "calculation_version": "common-statements-v1"}
