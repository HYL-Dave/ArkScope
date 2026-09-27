"""Descriptive source comparisons, not a financial truth or materiality verdict."""

from datetime import date
from decimal import Decimal, InvalidOperation, localcontext
from itertools import combinations
import re

from src.fundamentals.metric_basis import SEC_STATEMENT_BASIS_VERSION


# Only named statement rows, never ratios, estimated EBITDA or liabilities-as-debt.
# Similar-looking provider labels outside this map remain unavailable.
METRICS = {
    "income_statement": (
        ("revenue", "Total Revenues", "money"),
        ("gross_profit", "Gross Profit", "money"),
        ("operating_income", "Operating Income", "money"),
        ("net_income", "Net Income", "money"),
        ("earnings_per_share", "Basic EPS", "per_share"),
        ("earnings_per_share_diluted", "Diluted EPS", "per_share"),
    ),
    "balance_sheet": (
        ("total_assets", "Total Assets", "money"),
        ("current_assets", "Total Current Assets", "money"),
        ("total_liabilities", "Total Liabilities", "money"),
        ("current_liabilities", "Total Current Liabilities", "money"),
    ),
    "cash_flow_statement": (
        ("net_cash_flow_from_operations", "Cash from Operations", "money"),
        ("net_cash_flow_from_investing", "Cash from Investing", "money"),
        ("net_cash_flow_from_financing", "Cash from Financing", "money"),
    ),
}


def decimal(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
        return result if result.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def number(value):
    if value == 0:
        return "0"
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def sa_records(body, period):
    return [dict(end_month=column["end_month"], period_end=None, currency=body["currency"],
                 rows=body["rows"], column_index=i, unit_note=body["unit_note"])
            for i, column in enumerate(body["columns"]) if column["kind"] == period and column["end_month"]]


def fd_records(statements, period):
    records = []
    for item in statements:
        if item.period_type != period or date.fromisoformat(item.report_period).isoformat() != item.report_period:
            continue
        declared = item.currency if isinstance(item.currency, str) and re.fullmatch(r"[A-Z]{3}", item.currency) else None
        records.append(dict(end_month=item.report_period[:7], period_end=item.report_period,
                            currency=declared, data=item.data, input_basis_version=item.input_basis_version))
    return records


def source_value(source, metric, label, kind, month):
    provider = source["provider"]
    result = dict(provider=provider, label=label if provider == "seeking_alpha" else metric,
                  status="source_unavailable", raw=None, normalized_value=None, scale=None,
                  currency=None, unit=None, period_end=None, end_month=month,
                  display_half_step=None, precision=None)
    if source["status"] != "ok":
        return result
    records = source["records"]
    matched = [record for record in records if record["end_month"] == month]
    if len(matched) != 1:
        result["status"] = "period_ambiguous" if matched else "period_missing"
        return result
    record = matched[0]
    result.update(currency=record["currency"], period_end=record["period_end"])
    if provider == "sec_edgar" and record.get("input_basis_version") != SEC_STATEMENT_BASIS_VERSION:
        result["status"] = "statement_basis_unverified"
        return result
    result["unit"] = (record["currency"] or "currency_unknown") + ("/share" if kind == "per_share" else "")
    if provider == "seeking_alpha":
        rows = [row for row in record["rows"] if row["label"] == label]
        if len(rows) != 1:
            result["status"] = "label_ambiguous" if rows else "metric_missing"
            return result
        cell = rows[0]["cells"][record["column_index"]]
        result.update(raw=cell["raw"], section=rows[0]["section"], precision="provider_display_rounded")
        value = decimal(cell["number"])
        if cell["status"] != "value" or value is None:
            result["status"] = cell["status"] if cell["status"] != "value" else "invalid_value"
            return result
        if cell["notation"] not in {"number", "currency"}:
            result["status"] = "unit_unknown"
            return result
        units = re.fullmatch(r"In (Millions|Thousands) of .+ \(([A-Z]{3})\) except per share items", record["unit_note"])
        if units is None or units[2] != record["currency"]:
            result["status"] = "unit_unknown"
            return result
        scale = Decimal(1 if kind == "per_share" else 1_000_000 if units[1] == "Millions" else 1_000)
        with localcontext() as ctx:
            ctx.prec = max(50, len(value.as_tuple().digits) + 12)
            result["display_half_step"] = number(Decimal(10) ** value.as_tuple().exponent * scale / 2)
            normalized = value * scale
    else:
        raw = record["data"].get(metric)
        result.update(raw=raw, precision="provider_numeric_float")
        value = decimal(raw)
        if value is None:
            result["status"] = "metric_missing" if raw is None else "invalid_value"
            return result
        scale, normalized = Decimal(1), value
    result.update(status="value", normalized_value=number(normalized), scale=number(scale))
    return result


def compare_values(left, right):
    result = dict(left=left["provider"], right=right["provider"], status="not_comparable",
                  basis=None, difference_right_minus_left=None, relative_difference_pct=None,
                  reasons=[], limitations=[], cause=None, materiality_assessment=None)
    reasons = result["reasons"]
    for side, value in (("left", left), ("right", right)):
        if value["status"] != "value":
            reasons.append(side + "_" + value["status"])
    if reasons:
        return result
    if not left["currency"] or not right["currency"]:
        reasons.append("currency_unknown")
    elif left["currency"] != right["currency"]:
        reasons.append("currency_mismatch")
    if left["period_end"] and right["period_end"] and left["period_end"] != right["period_end"]:
        reasons.append("period_end_mismatch")
    if reasons:
        return result
    result["basis"] = "period_end" if left["period_end"] and right["period_end"] else "displayed_period_month"
    result["limitations"] = ["accounting_definition_unverified", "revision_equivalence_unverified"]
    if result["basis"] == "displayed_period_month":
        result["limitations"].append("exact_period_unverified")
    a, b = Decimal(left["normalized_value"]), Decimal(right["normalized_value"])
    with localcontext() as ctx:
        ctx.prec = max(50, abs(a.adjusted()) + abs(b.adjusted())
                       + len(a.as_tuple().digits) + len(b.as_tuple().digits) + 32)
        difference = b - a
        half_step = sum((decimal(v["display_half_step"]) or Decimal(0) for v in (left, right)))
        result["difference_right_minus_left"] = number(difference)
        if a:
            # A descriptive relative difference against the named left source,
            # not a tolerance, recommendation or claim of economic significance.
            result["relative_difference_pct"] = number((difference / abs(a) * 100).quantize(Decimal("0.000001")))
        else:
            result["limitations"].append("relative_difference_undefined_at_zero")
        result["status"] = ("same_displayed_value" if not difference else "rounding_compatible"
                            if abs(difference) <= half_step else "difference_unexplained")
    return result


def comparison_rows(sources, statement, month):
    rows = []
    for metric, label, kind in METRICS[statement]:
        values = [source_value(source, metric, label, kind, month) for source in sources]
        rows.append(dict(metric=metric, values=values,
                         comparisons=[compare_values(a, b) for a, b in combinations(values, 2)]))
    return rows
