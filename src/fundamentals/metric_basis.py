"""Storage-free financial ratios with explicit statement comparability."""

from dataclasses import asdict, is_dataclass
from datetime import date
import math
import re


CALCULATION_VERSION = "statement-basis-v1"
SEC_STATEMENT_BASIS_VERSION = "sec-period-debt-v1"
METRIC_FIELDS = ("gross_margin", "operating_margin", "net_margin", "revenue_growth",
                 "earnings_growth", "current_ratio", "debt_to_equity", "roe", "roa",
                 "free_cash_flow", "cash_and_equivalents", "total_debt")


def statement(value):
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    if not isinstance(value, dict):
        return {}
    if "data" in value:
        return {**value["data"], **{k: value.get(k) for k in
                ("report_period", "fiscal_period", "currency", "input_basis_version")}, "period": value.get("period_type")}
    return dict(value)


def finite(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        return value if math.isfinite(value) else None
    except OverflowError:
        return None


def ratio(numerator, denominator):
    n, d = finite(numerator), finite(denominator)
    if n is None or d is None or d <= 0:
        return None
    return finite(n / d)


def total_debt(row):
    reported = finite(row.get("total_debt"))
    if reported is not None:
        return reported if reported >= 0 else None
    current, noncurrent = finite(row.get("current_debt")), finite(row.get("non_current_debt"))
    if current is None or noncurrent is None or min(current, noncurrent) < 0:
        return None
    return finite(current + noncurrent)


def verified_sec_statements(rows):
    # Do not turn an unverifiable latest observation into an older "latest".
    if not rows or rows[0].get("input_basis_version") != SEC_STATEMENT_BASIS_VERSION:
        return []
    return [row for row in rows if row.get("input_basis_version") == SEC_STATEMENT_BASIS_VERSION]


def _end(row):
    try:
        value = row.get("report_period")
        parsed = date.fromisoformat(value)
        return parsed if parsed.isoformat() == value else None
    except (TypeError, ValueError):
        return None


def same_period(left, right):
    return bool(_end(left) and _end(left) == _end(right)
                and left.get("period") in {"annual", "quarterly"}
                and left.get("period") == right.get("period")
                and left.get("currency") and left.get("currency") == right.get("currency"))


def previous_period(rows):
    if not rows:
        return None
    latest = rows[0]
    match = re.fullmatch(r"(\d{4})-(FY|Q[1-4])", str(latest.get("fiscal_period")))
    if not match or not _end(latest) or not latest.get("currency"):
        return None
    year, part = int(match[1]), match[2]
    if latest.get("period") == "annual" and part == "FY":
        previous = f"{year - 1}-FY"
        lower, upper = 350, 380
    elif latest.get("period") == "quarterly" and part.startswith("Q"):
        quarter = int(part[1])
        previous = f"{year}-Q{quarter - 1}" if quarter > 1 else f"{year - 1}-Q4"
        lower, upper = 70, 110
    else:
        return None
    candidates = [row for row in rows[1:] if row.get("fiscal_period") == previous
                  and row.get("period") == latest.get("period")
                  and row.get("currency") == latest.get("currency") and _end(row)
                  and lower <= (_end(latest) - _end(row)).days <= upper]
    return candidates[0] if len(candidates) == 1 else None


def derive_metrics(income, balance, cashflow, *, source=None):
    income, balance, cashflow = ([statement(row) for row in rows] for rows in (income, balance, cashflow))
    unverified = source == "sec_edgar" and any(row.get("input_basis_version") != SEC_STATEMENT_BASIS_VERSION
                                             for rows in (income, balance, cashflow) for row in rows)
    if source == "sec_edgar":
        income, balance, cashflow = (verified_sec_statements(rows) for rows in (income, balance, cashflow))
    inc, bal, cf = (rows[0] if rows else {} for rows in (income, balance, cashflow))
    values = {key: None for key in METRIC_FIELDS}
    basis, gaps = {}, {}

    def put(key, value, row, *, failure="inputs_unavailable", **details):
        value = finite(value)
        values[key] = round(value, 4) if value is not None and key not in {
            "free_cash_flow", "cash_and_equivalents", "total_debt"} else value
        if value is None:
            gaps[key] = failure
        else:
            basis[key] = {"report_period": row.get("report_period"), "period": row.get("period"),
                          "currency": row.get("currency"), "precision": "provider_numeric", **details}

    for key, numerator in (("gross_margin", "gross_profit"), ("operating_margin", "operating_income"),
                           ("net_margin", "net_income")):
        put(key, ratio(inc.get(numerator), inc.get("revenue")), inc, numerator=numerator, denominator="revenue")
    previous = previous_period(income)
    for key, field in (("revenue_growth", "revenue"), ("earnings_growth", "net_income")):
        current = finite(inc.get(field))
        prior = finite(previous.get(field)) if previous else None
        growth = ratio(current - prior, abs(prior)) if current is not None and prior is not None else None
        put(key, growth, inc, failure="comparable_previous_period_unavailable",
            comparison="year_over_year" if inc.get("period") == "annual" else "quarter_over_quarter",
            previous_report_period=previous.get("report_period") if previous else None)
    debt = total_debt(bal)
    put("total_debt", debt, bal, numerator="provider_reported_debt_or_complete_debt_components")
    put("cash_and_equivalents", bal.get("cash_and_equivalents"), bal)
    put("current_ratio", ratio(bal.get("current_assets"), bal.get("current_liabilities")), bal,
        numerator="current_assets", denominator="current_liabilities")
    put("debt_to_equity", ratio(debt, bal.get("shareholders_equity")), bal,
        failure="debt_unavailable" if debt is None else "positive_equity_required",
        numerator="total_debt", denominator="shareholders_equity")
    for key, denominator in (("roe", "shareholders_equity"), ("roa", "total_assets")):
        gap = ("income_unavailable" if not inc else "annual_income_required" if inc.get("period") != "annual"
               else "statement_basis_mismatch" if not same_period(inc, bal) else "inputs_unavailable")
        value = ratio(inc.get("net_income"), bal.get(denominator)) if gap == "inputs_unavailable" else None
        put(key, value, inc, failure=gap, numerator="annual_net_income", denominator=denominator,
            denominator_basis="period_end")
    put("free_cash_flow", cf.get("free_cash_flow"), cf)
    if unverified:
        gaps.update({key: "sec_statement_basis_unverified" for key, value in values.items() if value is None})
    return {**values, "metric_basis": basis, "metric_gaps": gaps, "calculation_version": CALCULATION_VERSION}
