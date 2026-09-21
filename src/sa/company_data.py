"""Versioned SA display-table validation. No provider requests or financial inference."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
import re
from urllib.parse import urlsplit

from src.tools.result_policy import MAX_OUTPUT_BYTES


LAYOUT_ID = "sa.financial-table.v1"
PATHS = {
    "income-statement": "income_statement",
    "balance-sheet": "balance_sheet",
    "cash-flow-statement": "cash_flow_statement",
}
VIEWS = {"Annual": "annual", "Quarterly": "quarterly"}
_TITLE_PARTS = {
    "income_statement": "Income Statement",
    "balance_sheet": "Balance Sheet",
    "cash_flow_statement": "Cash Flow",
}
_ANCHORS = {
    "income_statement": {"Total Revenues", "Net Income"},
    "balance_sheet": {"Total Assets", "Total Liabilities"},
    "cash_flow_statement": {"Cash from Operations", "Cash from Investing", "Cash from Financing"},
}
_MONTHS = {name: i for i, name in enumerate(
    ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1)}
_NUMBER = re.compile(r"[+-]?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?\Z", re.ASCII)
_CAPTURE_KEYS = {
    "schema_version", "layout_id", "source_url", "ticker", "title", "heading",
    "captured_at", "controls", "unit_note", "headers", "rows",
}


class CompanyDataFailure(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def require(condition, code="sa_company_layout_unrecognized"):
    if not condition:
        raise CompanyDataFailure(code)


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def symbol(value):
    require(type(value) is str, "sa_company_ticker_invalid")
    value = value.strip().upper()
    require(bool(re.fullmatch(r"[A-Z][A-Z0-9.-]{0,19}", value, re.ASCII)), "sa_company_ticker_invalid")
    return value


def _text(value):
    require(type(value) is str and bool(value.strip()))
    return " ".join(value.split())


def clean_value(raw, *, currency=None):
    require(type(raw) is str, "sa_company_value_unrecognized")
    value = raw.strip()
    missing = {"-": "not_available", "\u2014": "not_available", "N/A": "not_available",
               "NM": "not_meaningful", "N/M": "not_meaningful", "N.M.": "not_meaningful",
               "NA": "not_available", "Not Applicable": "not_applicable"}
    if value in missing:
        return {"raw": raw, "status": missing[value], "number": None, "notation": None}
    if re.search(r"subscribe|upgrade|premium|sign in|log in|unlock", value, re.I):
        raise CompanyDataFailure("sa_company_access_restricted")
    notation = "percent" if value.endswith("%") else "number"
    if notation == "percent":
        value = value[:-1].strip()
    if value.startswith("(") and value.endswith(")"):
        value = "-" + value[1:-1]
    value = value.replace("\u2212", "-")
    currency_symbol = {"USD": "$", "EUR": "\u20ac", "GBP": "\u00a3", "JPY": "\u00a5"}.get(currency)
    sign = value[:1] if value[:1] in {"+", "-"} else ""
    unsigned = value[len(sign):]
    if currency_symbol and unsigned.startswith(currency_symbol):
        require(notation != "percent", "sa_company_value_unrecognized")
        notation = "currency"
        value = sign + unsigned[len(currency_symbol):]
    require(bool(_NUMBER.fullmatch(value)), "sa_company_value_unrecognized")
    number = Decimal(value.replace(",", ""))
    return {"raw": raw, "status": "value", "number": str(number), "notation": notation}


def normalize_capture(payload, *, now=None):
    require(type(payload) is dict and set(payload) == _CAPTURE_KEYS)
    require(type(payload["schema_version"]) is int and payload["schema_version"] == 1)
    require(payload["layout_id"] == LAYOUT_ID)
    try:
        size = len(canonical_json(payload).encode("utf-8"))
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise CompanyDataFailure("sa_company_layout_unrecognized") from exc
    require(size <= MAX_OUTPUT_BYTES, "sa_company_capture_too_large")
    ticker = symbol(payload["ticker"])
    require(ticker == payload["ticker"], "sa_company_identity_mismatch")
    require(type(payload["source_url"]) is str, "sa_company_identity_mismatch")
    try:
        url = urlsplit(payload["source_url"])
    except ValueError as exc:
        raise CompanyDataFailure("sa_company_identity_mismatch") from exc
    path = url.path.split("/")
    require(url.scheme == "https" and url.netloc == "seekingalpha.com"
            and not url.query and not url.fragment and len(path) == 4
            and path[1:3] == ["symbol", ticker] and path[3] in PATHS, "sa_company_identity_mismatch")
    statement = PATHS[path[3]]
    title, heading = _text(payload["title"]), _text(payload["heading"])
    require(f"({ticker})" in title and _TITLE_PARTS[statement] in title
            and heading.startswith(ticker + " - "), "sa_company_identity_mismatch")
    try:
        captured = datetime.fromisoformat(payload["captured_at"].replace("Z", "+00:00"))
        require(captured.tzinfo is not None, "sa_company_capture_time_invalid")
        captured = captured.astimezone(timezone.utc)
    except (AttributeError, TypeError, ValueError) as exc:
        raise CompanyDataFailure("sa_company_capture_time_invalid") from exc
    now = now or datetime.now(timezone.utc)
    require(captured <= now + timedelta(minutes=5), "sa_company_capture_time_invalid")
    controls = payload["controls"]
    require(type(controls) is dict and set(controls) == {"period", "view", "order", "currency"})
    require(all(type(value) is str for value in controls.values()))
    require(controls["period"] in VIEWS and controls["view"] == "Absolute", "sa_company_view_unsupported")
    require(controls["order"] in {"Latest on the Left", "Latest on the Right"})
    unit_note = _text(payload["unit_note"])
    units = re.fullmatch(r"In (Millions|Thousands) of (.+ \(([A-Z]{3})\)) except per share items", unit_note)
    require(units is not None and units[2] == controls["currency"], "sa_company_units_unrecognized")
    headers = payload["headers"]
    require(type(headers) is list and len(headers) >= 3
            and all(type(h) is dict and set(h) == {"id", "label"} for h in headers))
    require(headers[:2] == [{"id": "value-header", "label": "Line Item"},
                            {"id": "chart-header", "label": "Price Chart"}])
    columns, identities, months = [], set(), []
    for header in headers[2:]:
        label = _text(header["label"])
        require(header["id"] == label.lower().replace(" ", "-") + "-column-header"
                and label not in identities)
        identities.add(label)
        if label in {"TTM", "Last Report"}:
            require(label == ("Last Report" if statement == "balance_sheet" else "TTM"))
            columns.append({"label": label, "kind": "latest_report" if label == "Last Report" else "trailing",
                            "end_month": None, "period_end": None})
        else:
            match = re.fullmatch(r"([A-Z][a-z]{2}) (\d{4})", label, re.ASCII)
            require(match is not None and match[1] in _MONTHS)
            month = f"{match[2]}-{_MONTHS[match[1]]:02d}"
            months.append(month)
            columns.append({"label": label, "kind": VIEWS[controls["period"]],
                            "end_month": month, "period_end": None})
    require(bool(months))
    require(months == sorted(months, reverse=controls["order"] == "Latest on the Left"))
    special = [i for i, column in enumerate(columns) if column["kind"] in {"trailing", "latest_report"}]
    require(not special or special == [0 if controls["order"] == "Latest on the Left" else len(columns) - 1])
    require(controls["period"] != "Quarterly" or not special, "sa_company_view_unsupported")
    if controls["period"] == "Annual":
        require(len({month[:4] for month in months}) == len(months), "sa_company_view_unsupported")
    # Calendar labels are source evidence, never invented exact fiscal end dates.
    rows, section, seen, labels, values = [], None, set(), set(), 0
    require(type(payload["rows"]) is list and bool(payload["rows"]))
    for row in payload["rows"]:
        require(type(row) is dict and set(row) == {"kind", "label", "values"})
        label = _text(row["label"])
        require(type(row["values"]) is list)
        if row["kind"] == "section":
            require(not row["values"])
            section = label
            continue
        require(row["kind"] == "data" and section is not None
                and len(row["values"]) == len(headers) - 1 and row["values"][0] == "")
        require((section, label) not in seen)
        seen.add((section, label))
        labels.add(label)
        cells = [clean_value(value, currency=units[3]) for value in row["values"][1:]]
        values += sum(cell["status"] == "value" for cell in cells)
        rows.append({"section": section, "label": label, "cells": cells})
    require(_ANCHORS[statement] <= labels)
    require(values > 0, "sa_company_values_unavailable")
    structure = {"layout_id": LAYOUT_ID, "statement": statement, "view": controls["period"],
                 "column_kinds": sorted(column["kind"] for column in columns),
                 "rows": [[row["section"], row["label"]] for row in rows],
                 "scale": units[1], "value_view": controls["view"]}
    body = {
        "provider": "seeking_alpha", "ticker": ticker, "statement": statement,
        "view": VIEWS[controls["period"]], "currency": units[3],
        "source_url": payload["source_url"], "layout_id": LAYOUT_ID,
        "structure_sha256": digest(structure), "unit_note": unit_note,
        "value_basis": "provider_display_not_rescaled", "precision": "provider_display_rounded",
        "columns": columns, "rows": rows,
        "coverage": {"scope": "displayed_table", "row_count": len(rows), "column_count": len(columns),
                     "missing_cells": sum(cell["status"] != "value" for row in rows for cell in row["cells"])},
    }
    return {"observation_id": digest(body), "captured_at": captured.isoformat(), "body": body}


def company_result_reducer(payload, *, budget):
    """Whole JSON or an actionable page-size error, never sliced financial text."""
    inner, wrapped = payload, False
    prefix, suffix = '<tool_output tool="get_sa_company_data">\n', '\n</tool_output>'
    if payload.startswith(prefix) and payload.endswith(suffix):
        inner, wrapped = payload[len(prefix):-len(suffix)], True
    try:
        value = json.loads(inner)
        require(type(value) is dict and value.get("status") in {"ok", "unavailable"}, "sa_company_result_invalid")
        require(value.get("provider") == "seeking_alpha", "sa_company_result_invalid")
        canonical_json(value)
        if len(payload) <= budget:
            return payload, {}
        failure = {"status": "unavailable", "provider": "seeking_alpha", "error_code": "sa_company_page_too_large",
                   "observation_id": value.get("observation_id"), "required_action": "read_same_observation_with_smaller_page"}
    except (CompanyDataFailure, ValueError, TypeError, RecursionError):
        failure = {"status": "unavailable", "provider": "seeking_alpha", "error_code": "sa_company_result_invalid"}
    result = canonical_json(failure)
    return (prefix + result + suffix if wrapped else result), {"failure": failure["error_code"]}
